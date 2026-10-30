import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cinnamon_clipboard.core.settings import SettingsManager


class TestSettingsManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name)
        self.config_dir = self.home / ".config" / "cinnamon-clipboard"
        self.config_path = self.config_dir / "config.json"
        self.home_patch = patch.object(Path, "home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def make_settings(self, initial_data=None):
        if initial_data is not None:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(
                json.dumps(initial_data),
                encoding="utf-8",
            )
        return SettingsManager()

    def test_default_settings(self):
        settings = self.make_settings()

        self.assertEqual(settings.get("history_mode"), "persistent")
        self.assertEqual(settings.get("max_history"), 50)
        self.assertTrue(settings.get("enable_history"))
        self.assertTrue(settings.get("save_images"))
        self.assertTrue(settings.get("save_files"))
        self.assertFalse(settings.get("autostart"))
        self.assertFalse(settings.config_was_reset)

    def test_valid_settings_are_loaded(self):
        settings = self.make_settings({
            "max_history": 100,
            "history_mode": "temporary",
            "enable_history": False,
            "autostart": True,
            "shortcut": "<Ctrl>v",
        })

        self.assertEqual(settings.get("max_history"), 100)
        self.assertEqual(settings.get("history_mode"), "temporary")
        self.assertFalse(settings.get("enable_history"))
        self.assertTrue(settings.get("autostart"))
        self.assertEqual(settings.get("shortcut"), "<Ctrl>v")
        self.assertFalse(settings.config_was_reset)

    def test_invalid_settings_reset_to_defaults(self):
        invalid_configs = [
            {"max_history": 999},
            {"history_mode": "invalid"},
            {"enable_history": "yes"},
            {"autostart": 1},
            {"shortcut": 123},
        ]

        for invalid_config in invalid_configs:
            with self.subTest(config=invalid_config):
                # Cada caso utiliza su propio directorio.
                with tempfile.TemporaryDirectory() as temp:
                    home = Path(temp)

                    with patch.object(Path, "home", return_value=home):
                        config_dir = (
                            home / ".config" / "cinnamon-clipboard"
                        )
                        config_dir.mkdir(parents=True)
                        (config_dir / "config.json").write_text(
                            json.dumps(invalid_config),
                            encoding="utf-8",
                        )

                        settings = SettingsManager()

                        self.assertTrue(settings.config_was_reset)
                        self.assertEqual(
                            settings.get("history_mode"),
                            "persistent",
                        )
                        self.assertEqual(settings.get("max_history"), 50)

                        # La configuración recuperada debe poder leerse.
                        saved = json.loads(
                            (config_dir / "config.json").read_text(
                                encoding="utf-8"
                            )
                        )
                        self.assertEqual(saved["max_history"], 50)

    def test_changes_are_persisted(self):
        settings = self.make_settings()

        self.assertTrue(settings.set("max_history", 75))
        self.assertTrue(settings.set("history_mode", "temporary"))

        reloaded = SettingsManager()

        self.assertEqual(reloaded.get("max_history"), 75)
        self.assertEqual(reloaded.get("history_mode"), "temporary")

    def test_failed_save_rolls_back_setting(self):
        settings = self.make_settings()
        previous_value = settings.get("max_history")

        with patch.object(settings, "save", return_value=False):
            result = settings.set("max_history", 100)

        self.assertFalse(result)
        self.assertEqual(settings.get("max_history"), previous_value)

    def test_failed_atomic_save_preserves_existing_file(self):
        settings = self.make_settings()

        # Crear primero una configuración válida en disco.
        self.assertTrue(settings.save())

        original_content = self.config_path.read_text(encoding="utf-8")

        settings.settings["max_history"] = 75

        with patch(
            "cinnamon_clipboard.core.settings.os.replace",
            side_effect=OSError("Simulated write failure"),
        ):
            result = settings.save()

        self.assertFalse(result)

        # El archivo anterior no debe quedar parcialmente sobrescrito.
        self.assertEqual(
            self.config_path.read_text(encoding="utf-8"),
            original_content,
        )

        # No deben quedar archivos temporales abandonados.
        leftovers = list(self.config_dir.glob(".config.*.tmp"))
        self.assertEqual(leftovers, [])

    def test_autostart_can_be_enabled_and_disabled(self):
        settings = self.make_settings()
        autostart_path = (
            self.home / ".config" / "autostart"
            / "cinnamon-clipboard.desktop"
        )

        self.assertTrue(settings.set_autostart(True))
        self.assertTrue(autostart_path.is_file())
        self.assertTrue(settings.get("autostart"))

        desktop_entry = autostart_path.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", desktop_entry)
        self.assertTrue(desktop_entry.endswith("\n"))

        self.assertTrue(settings.set_autostart(False))
        self.assertFalse(autostart_path.exists())
        self.assertFalse(settings.get("autostart"))

    def test_autostart_refuses_symlink(self):
        settings = self.make_settings()

        autostart_dir = self.home / ".config" / "autostart"
        autostart_dir.mkdir(parents=True)

        target = self.home / "important-file"
        target.write_text("Do not modify", encoding="utf-8")

        autostart_path = autostart_dir / "cinnamon-clipboard.desktop"
        autostart_path.symlink_to(target)

        result = settings.set_autostart(True)

        self.assertFalse(result)
        self.assertTrue(autostart_path.is_symlink())
        self.assertEqual(
            target.read_text(encoding="utf-8"),
            "Do not modify",
        )


if __name__ == "__main__":
    unittest.main()