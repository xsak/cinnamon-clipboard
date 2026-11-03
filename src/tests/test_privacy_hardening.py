import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cinnamon_clipboard.core.clipboard import ClipboardManager
from cinnamon_clipboard.core.database import (
    HistoryDatabase,
    ensure_private_dir,
    restrict_private_files,
)
from cinnamon_clipboard.core.settings import SettingsManager


def mode(path):
    return stat.S_IMODE(os.lstat(path).st_mode)


class TestPrivateStorage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_secure_delete_is_enabled_on_every_connection(self):
        db = HistoryDatabase(self.root / "history.db")
        with db._get_connection() as conn:
            self.assertEqual(conn.execute("PRAGMA secure_delete").fetchone()[0], 1)

    def test_deleted_text_is_removed_from_the_file(self):
        db = HistoryDatabase(self.root / "history.db")
        db.add_item("text", "SECRET-TOKEN-12345", "SECRET-TOKEN-12345")
        with db._get_connection() as conn:
            item_id = conn.execute("SELECT id FROM history").fetchone()[0]
        db.delete_item(item_id)
        self.assertNotIn(b"SECRET-TOKEN-12345", (self.root / "history.db").read_bytes())

    def test_ensure_private_dir_fixes_existing_permissions(self):
        folder = self.root / "data"
        folder.mkdir(mode=0o775)
        os.chmod(folder, 0o775)
        ensure_private_dir(folder)
        self.assertEqual(mode(folder), 0o700)

    def test_ensure_private_dir_leaves_symlink_target_alone(self):
        target = self.root / "elsewhere"
        target.mkdir()
        os.chmod(target, 0o755)
        link = self.root / "data"
        link.symlink_to(target)

        ensure_private_dir(link)
        self.assertEqual(mode(target), 0o755)

    def test_restrict_private_files_fixes_old_images_only(self):
        media = self.root / "media"
        media.mkdir()
        old_image = media / "old.png"
        old_image.write_bytes(b"png")
        os.chmod(old_image, 0o664)
        outside = self.root / "outside.txt"
        outside.write_text("not ours to change")
        os.chmod(outside, 0o644)
        (media / "link.png").symlink_to(outside)
        (media / "subdir").mkdir(mode=0o755)

        restrict_private_files(media)

        self.assertEqual(mode(old_image), 0o600)
        self.assertEqual(mode(outside), 0o644)
        self.assertEqual(mode(media / "subdir") & 0o777, 0o755)


class TestSettingsPrivacy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.home = Path(self.temp_dir.name)
        home_patch = patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def test_config_dir_is_private(self):
        SettingsManager()
        self.assertEqual(mode(self.home / ".config" / "cinnamon-clipboard"), 0o700)

    def test_ignored_apps_default_includes_password_managers(self):
        self.assertIn("keepassxc", SettingsManager().get("ignored_apps"))

    def test_invalid_ignored_apps_resets_config(self):
        config_dir = self.home / ".config" / "cinnamon-clipboard"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"ignored_apps": "keepassxc"}')
        settings = SettingsManager()
        self.assertTrue(settings.config_was_reset)

    def test_parse_app_list(self):
        self.assertEqual(
            SettingsManager.parse_app_list(" KeePassXC, bitwarden,,keepassxc , "),
            ["keepassxc", "bitwarden"],
        )


class FakeWindow:
    def __init__(self, xid, parent=None, wm_class=None):
        self.id = xid
        self.parent = parent
        self.wm_class = wm_class

    def query_tree(self):
        root = self
        while root.parent is not None:
            root = root.parent
        return SimpleNamespace(root=root, parent=self.parent or 0)

    def get_wm_class(self):
        return self.wm_class


ROOT = FakeWindow(1)


class FakeDisplay:
    def __init__(self, owner, focus):
        self.owner = owner
        self.focus = focus

    def intern_atom(self, name):
        return 99

    def get_selection_owner(self, atom):
        return self.owner

    def get_input_focus(self):
        return SimpleNamespace(focus=self.focus)


def make_manager(owner, focus, ignored_apps):
    manager = ClipboardManager.__new__(ClipboardManager)
    manager.x11_file_clipboard = SimpleNamespace(display=FakeDisplay(owner, focus))
    manager.settings = SimpleNamespace(get=lambda key: ignored_apps)
    return manager


class TestIgnoredApps(unittest.TestCase):
    def setUp(self):
        # Cinnamon's clipboard daemon owns the clipboard through a window without WM_CLASS.
        self.daemon_owner = FakeWindow(10, parent=ROOT)
        frame = FakeWindow(20, parent=ROOT)
        self.keepass_focus = FakeWindow(21, parent=frame, wm_class=("keepassxc", "KeePassXC"))
        self.editor_focus = FakeWindow(31, parent=ROOT, wm_class=("xed", "Xed"))

    def test_copy_in_focused_ignored_app_is_skipped(self):
        manager = make_manager(self.daemon_owner, self.keepass_focus, ["keepassxc"])
        self.assertTrue(manager._is_from_ignored_app())

    def test_copy_from_ignored_app_owning_clipboard_is_skipped(self):
        owner = FakeWindow(40, parent=ROOT, wm_class=("bitwarden", "Bitwarden"))
        manager = make_manager(owner, self.editor_focus, ["bitwarden"])
        self.assertTrue(manager._is_from_ignored_app())

    def test_copy_in_other_app_is_recorded(self):
        manager = make_manager(self.daemon_owner, self.editor_focus, ["keepassxc"])
        self.assertFalse(manager._is_from_ignored_app())

    def test_names_are_compared_case_insensitively(self):
        manager = make_manager(self.daemon_owner, self.keepass_focus, ["KeePassXC"])
        self.assertTrue(manager._is_from_ignored_app())

    def test_empty_list_records_everything(self):
        manager = make_manager(self.daemon_owner, self.keepass_focus, [])
        self.assertFalse(manager._is_from_ignored_app())

    def test_no_owner_and_no_focus(self):
        manager = make_manager(0, 1, ["keepassxc"])
        self.assertFalse(manager._is_from_ignored_app())


if __name__ == "__main__":
    unittest.main()
