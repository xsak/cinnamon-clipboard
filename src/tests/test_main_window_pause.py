import unittest
from unittest.mock import Mock

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from cinnamon_clipboard.core.clipboard import ClipboardManager
from cinnamon_clipboard.ui.main_window import MainWindow


class FakeSettings:
    def __init__(self, enable_history=True):
        self.values = {"enable_history": enable_history}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value
        return True


class FakeClipboardManager:
    def __init__(self, enable_history=True):
        self.settings = FakeSettings(enable_history)
        self.history = []
        self.add_history_listener = Mock()
        self.remove_history_listener = Mock()

    def set_history_paused(self, paused):
        self.settings.set("enable_history", not paused)
        return True


class TestMainWindowPause(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        initialized, _ = Gtk.init_check(None)
        if not initialized:
            raise unittest.SkipTest("GTK display unavailable.")

    def make_window(self, enable_history=True):
        window = MainWindow(FakeClipboardManager(enable_history))
        window.show_all()
        self.addCleanup(window.destroy)
        return window

    def test_not_paused_hides_status_bar(self):
        window = self.make_window()
        self.assertFalse(window.btn_pause.get_active())
        self.assertFalse(window.paused_bar.get_visible())

    def test_paused_on_open_shows_status_bar(self):
        window = self.make_window(enable_history=False)
        self.assertTrue(window.btn_pause.get_active())
        self.assertTrue(window.paused_bar.get_visible())

    def test_pause_button_pauses_and_shows_status_bar(self):
        window = self.make_window()
        window.btn_pause.set_active(True)
        self.assertFalse(window.clipboard_manager.settings.get("enable_history"))
        self.assertTrue(window.paused_bar.get_visible())

    def test_resume_button_in_status_bar_resumes(self):
        window = self.make_window(enable_history=False)
        window.paused_bar.response(Gtk.ResponseType.ACCEPT)
        self.assertTrue(window.clipboard_manager.settings.get("enable_history"))
        self.assertFalse(window.btn_pause.get_active())
        self.assertFalse(window.paused_bar.get_visible())

    def test_refresh_picks_up_pause_from_another_window(self):
        window = self.make_window()
        window.clipboard_manager.settings.set("enable_history", False)
        window.refresh_list()
        self.assertTrue(window.btn_pause.get_active())
        self.assertTrue(window.paused_bar.get_visible())


class TestSetHistoryPaused(unittest.TestCase):
    def make_manager(self, save_ok=True):
        manager = ClipboardManager.__new__(ClipboardManager)
        manager.settings = FakeSettings()
        if not save_ok:
            manager.settings.set = Mock(return_value=False)
        manager._notify_history_changed = Mock()
        return manager

    def test_pause_saves_setting_and_notifies_windows(self):
        manager = self.make_manager()
        self.assertTrue(manager.set_history_paused(True))
        self.assertTrue(manager.is_history_paused())
        manager._notify_history_changed.assert_called_once_with()

    def test_failed_save_does_not_notify(self):
        manager = self.make_manager(save_ok=False)
        self.assertFalse(manager.set_history_paused(True))
        manager._notify_history_changed.assert_not_called()


if __name__ == "__main__":
    unittest.main()
