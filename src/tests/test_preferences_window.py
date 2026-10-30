
import unittest
from unittest.mock import Mock
from types import SimpleNamespace

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk

from cinnamon_clipboard.i18n import _
from cinnamon_clipboard.installation import PACKAGE_MANAGED
from cinnamon_clipboard.ui.preferences_window import PreferencesWindow


class FakeSettingsManager:
    def __init__(self, values=None):
        self.settings = {
            "enable_history": True,
            "history_mode": "persistent",
            "max_history": 50,
            "save_images": True,
            "save_files": True,
            "autostart": False,
            "focus_first_item": True,
            "paste_on_select": True,
            "shortcut": "<Ctrl><Alt>v",
            "check_updates": True,
        }

        if values:
            self.settings.update(values)

        self.save_calls = 0

    def get(self, key):
        return self.settings.get(key)

    def save(self):
        self.save_calls += 1
        return True

    def snapshot_autostart_file(self):
        return None

    def restore_autostart_file(self, snapshot):
        return True

    def set_autostart(self, enabled):
        self.settings["autostart"] = enabled
        return True


class FakeClipboardManager:
    def __init__(self):
        self.apply_max_history = Mock()
        self._clean_persistent_storage = Mock()


class TestPreferencesWindow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        initialized, _ = Gtk.init_check(None)
        if not initialized:
            raise unittest.SkipTest(
                "GTK display unavailable. Run tests inside a graphical session."
            )

    def setUp(self):
        self.settings = FakeSettingsManager()
        self.clipboard = FakeClipboardManager()
        self.shortcut_callback = Mock()

        self.window = PreferencesWindow(
            settings_manager=self.settings,
            clipboard_manager=self.clipboard,
            on_shortcut_changed_callback=self.shortcut_callback,
        )

    def tearDown(self):
        try:
            self.window.destroy()
        except Exception:
            pass

    def _find_widget(self, widget, widget_type):
        if isinstance(widget, widget_type):
            return widget

        if hasattr(widget, "get_children"):
            for child in widget.get_children():
                result = self._find_widget(child, widget_type)
                if result:
                    return result

        return None

    def _find_button(self, widget, label):
        if isinstance(widget, Gtk.Button):
            if widget.get_label() == label:
                return widget

        if hasattr(widget, "get_children"):
            for child in widget.get_children():
                result = self._find_button(child, label)
                if result:
                    return result

        return None

    # 1. Pestañas

    def test_notebook_tabs_are_created(self):
        notebook = self._find_widget(self.window, Gtk.Notebook)

        self.assertIsNotNone(
            notebook,
            "PreferencesWindow should contain a Gtk.Notebook",
        )

        labels = []

        for index in range(notebook.get_n_pages()):
            tab = notebook.get_tab_label(
                notebook.get_nth_page(index)
            )
            labels.append(tab.get_text())

        self.assertIn(_("History and Privacy"), labels)
        self.assertIn(_("Content Capture"), labels)
        self.assertIn(_("System and Shortcut"), labels)

        if not PACKAGE_MANAGED:
            self.assertIn(_("Updates"), labels)

    # 2. Switches

    def test_switches_reflect_saved_settings(self):
        self.assertTrue(self.window.switch_enable.get_active())
        self.assertTrue(self.window.switch_images.get_active())
        self.assertTrue(self.window.switch_files.get_active())
        self.assertFalse(self.window.switch_autostart.get_active())
        self.assertTrue(self.window.switch_focus_first.get_active())
        self.assertTrue(self.window.switch_paste_select.get_active())
        self.assertTrue(self.window.switch_check_updates.get_active())

    def test_history_mode_radio_buttons_reflect_saved_setting(self):
        self.assertTrue(self.window.radio_persistent.get_active())
        self.assertFalse(self.window.radio_temporary.get_active())

        self.window.destroy()

        self.settings = FakeSettingsManager({
            "history_mode": "temporary"
        })

        self.window = PreferencesWindow(
            self.settings,
            self.clipboard,
        )

        self.assertFalse(self.window.radio_persistent.get_active())
        self.assertTrue(self.window.radio_temporary.get_active())

    # 3. Guardar

    def test_save_persists_temporary_changes(self):
        self.window._set_temp("save_images", False)
        self.window._set_temp("save_files", False)
        self.window._set_temp("max_history", 100)
        self.window._set_temp("focus_first_item", False)

        self.window._on_save_clicked(None)

        self.assertFalse(self.settings.get("save_images"))
        self.assertFalse(self.settings.get("save_files"))
        self.assertEqual(self.settings.get("max_history"), 100)
        self.assertFalse(self.settings.get("focus_first_item"))

        self.assertEqual(self.settings.save_calls, 1)

        self.clipboard.apply_max_history.assert_called_once_with(100)

    def test_save_notifies_shortcut_change(self):
        self.window._set_temp("shortcut", "<Ctrl><Shift>x")

        self.window._on_save_clicked(None)

        self.shortcut_callback.assert_called_once_with(
            "<Ctrl><Shift>x"
        )

    # 4. Cancelar

    def test_cancel_discards_temporary_changes(self):
        original_settings = dict(self.settings.settings)

        self.window._set_temp("save_images", False)
        self.window._set_temp("max_history", 100)

        cancel_button = self._find_button(
            self.window,
            _("Cancel"),
        )

        self.assertIsNotNone(cancel_button)

        cancel_button.clicked()

        self.assertEqual(self.settings.settings, original_settings)
        self.assertEqual(self.settings.save_calls, 0)

    # 5. Atajos

    def test_shortcut_capture_starts(self):
        self.window._start_capturing_shortcut(None)

        self.assertTrue(self.window.is_capturing_shortcut)
        self.assertEqual(
            self.window.btn_shortcut.get_label(),
            _("Press a key combination..."),
        )

    def test_shortcut_capture_records_key_and_modifiers(self):
        self.window._start_capturing_shortcut(None)

        event = SimpleNamespace(
            keyval=Gdk.KEY_v,
            state=(
                Gdk.ModifierType.CONTROL_MASK
                | Gdk.ModifierType.MOD1_MASK
            ),
        )

        result = self.window._on_key_press_event(
            self.window,
            event,
        )

        self.assertTrue(result)
        self.assertEqual(
            self.window.temp_settings["shortcut"],
            "<Ctrl><Alt>v",
        )
        self.assertFalse(self.window.is_capturing_shortcut)

    def test_escape_cancels_shortcut_capture(self):
        original_shortcut = self.window.temp_settings["shortcut"]

        self.window._start_capturing_shortcut(None)

        event = SimpleNamespace(
            keyval=Gdk.KEY_Escape,
            state=Gdk.ModifierType(0),
        )

        result = self.window._on_key_press_event(
            self.window,
            event,
        )

        self.assertTrue(result)
        self.assertFalse(self.window.is_capturing_shortcut)
        self.assertEqual(
            self.window.temp_settings["shortcut"],
            original_shortcut,
        )

    def test_isolated_modifier_does_not_set_shortcut(self):
        original_shortcut = self.window.temp_settings["shortcut"]

        self.window._start_capturing_shortcut(None)

        event = SimpleNamespace(
            keyval=Gdk.KEY_Control_L,
            state=Gdk.ModifierType.CONTROL_MASK,
        )

        self.window._on_key_press_event(self.window, event)

        self.assertTrue(self.window.is_capturing_shortcut)
        self.assertEqual(
            self.window.temp_settings["shortcut"],
            original_shortcut,
        )

    # 6. Modo de historial

    def test_selecting_temporary_mode_updates_temporary_settings(self):
        self.window.radio_temporary.set_active(True)

        self.assertEqual(
            self.window.temp_settings["history_mode"],
            "temporary",
        )

    def test_selecting_persistent_mode_updates_temporary_settings(self):
        self.window.radio_temporary.set_active(True)
        self.window.radio_persistent.set_active(True)

        self.assertEqual(
            self.window.temp_settings["history_mode"],
            "persistent",
        )

    def test_switching_from_persistent_to_temporary_deletes_history(self):
        self.window._confirm_history_mode_change = Mock(return_value=True)
        self.window._delete_persistent_history = Mock()

        self.window.radio_temporary.set_active(True)
        self.window._on_save_clicked(None)

        self.window._delete_persistent_history.assert_called_once()

    def test_switching_from_temporary_to_persistent_does_not_delete_history(self):
        self.settings = FakeSettingsManager({
            "history_mode": "temporary"
        })

        self.window.destroy()

        self.window = PreferencesWindow(
            self.settings,
            self.clipboard,
        )

        self.window._confirm_history_mode_change = Mock(return_value=True)
        self.window._delete_persistent_history = Mock()

        self.window.radio_persistent.set_active(True)
        self.window._on_save_clicked(None)

        self.window._delete_persistent_history.assert_not_called()

    def test_cancelled_history_mode_change_does_not_save(self):
        self.window._confirm_history_mode_change = Mock(return_value=False)

        self.window.radio_temporary.set_active(True)
        self.window._on_save_clicked(None)

        self.assertEqual(
            self.settings.get("history_mode"),
            "persistent",
        )
        self.assertEqual(self.settings.save_calls, 0)
        self.assertTrue(self.window.radio_persistent.get_active())


if __name__ == "__main__":
    unittest.main()
