
"""Tests for the Cinnamon Clipboard first-run welcome wizard.

Run from the project root with:
    PYTHONPATH=src python3 -m unittest discover -s src/tests -p 'test_welcome_window.py' -v
"""

import unittest
from unittest.mock import Mock, patch

from cinnamon_clipboard.ui.welcome_window import WelcomeWindow


class FakeStyleContext:
    def __init__(self):
        self.classes = set()

    def add_class(self, name):
        self.classes.add(name)

    def remove_class(self, name):
        self.classes.discard(name)


class FakeButton:
    def __init__(self):
        self.label = None
        self.sensitive = True
        self.style = FakeStyleContext()

    def set_label(self, label):
        self.label = label

    def get_style_context(self):
        return self.style

    def set_sensitive(self, sensitive):
        self.sensitive = sensitive


class FakeStack:
    def __init__(self):
        self.visible_child_name = None

    def set_visible_child_name(self, name):
        self.visible_child_name = name


class FakeSettings:
    DEFAULTS = {
        "history_mode": "persistent",
        "max_history": 50,
        "autostart": False,
    }


class WelcomeWindowBehaviorTests(unittest.TestCase):
    def make_window(self, callback=None):
        """Create an instance without running GTK window initialization."""
        if callback is None:
            callback = Mock(return_value=True)

        window = WelcomeWindow.__new__(WelcomeWindow)
        window.settings = FakeSettings()
        window.on_complete = callback
        window.current_page = 0
        window._completed = False
        window.history_mode = "persistent"
        window.max_history = 50
        window.autostart = False

        window.back_button = FakeButton()
        window.skip_button = FakeButton()
        window.next_button = FakeButton()
        window.stack = FakeStack()
        window.destroy = Mock()

        return window

    def test_finish_saves_selected_values(self):
        callback = Mock(return_value=True)
        window = self.make_window(callback)
        window.current_page = len(window.PAGE_NAMES) - 1

        window.limit_combo = Mock()
        window.limit_combo.get_active_text.return_value = "75"

        window.autostart_check = Mock()
        window.autostart_check.get_active.return_value = True

        window.history_mode = "temporary"

        window._on_next(None)

        callback.assert_called_once_with({
            "history_mode": "temporary",
            "max_history": 75,
            "autostart": True,
        })
        self.assertTrue(window._completed)
        window.destroy.assert_called_once_with()

    def test_skip_saves_default_values(self):
        callback = Mock(return_value=True)
        window = self.make_window(callback)

        window._on_skip(None)

        callback.assert_called_once_with(FakeSettings.DEFAULTS)
        self.assertTrue(window._completed)
        window.destroy.assert_called_once_with()

    def test_close_saves_default_values(self):
        callback = Mock(return_value=True)
        window = self.make_window(callback)

        result = window._on_delete(None, None)

        callback.assert_called_once_with(FakeSettings.DEFAULTS)
        self.assertTrue(window._completed)
        window.destroy.assert_called_once_with()
        self.assertTrue(result)

    def test_failed_save_keeps_window_open(self):
        callback = Mock(return_value=False)
        window = self.make_window(callback)

        with patch.object(window, "_show_error") as show_error:
            window._finish(use_defaults=True)

        show_error.assert_called_once_with()
        self.assertFalse(window._completed)
        window.destroy.assert_not_called()

    def test_exception_during_save_keeps_window_open(self):
        callback = Mock(side_effect=OSError("save failed"))
        window = self.make_window(callback)

        with patch.object(window, "_show_error") as show_error:
            window._finish(use_defaults=True)

        show_error.assert_called_once_with()
        self.assertFalse(window._completed)
        window.destroy.assert_not_called()

    def test_finish_cannot_complete_twice(self):
        callback = Mock(return_value=True)
        window = self.make_window(callback)
        window._completed = True

        window._finish(use_defaults=True)

        callback.assert_not_called()
        window.destroy.assert_not_called()

    def test_navigation_updates_page_and_finish_button(self):
        window = self.make_window()

        window._show_page(0)
        self.assertEqual(window.stack.visible_child_name, "welcome")
        self.assertFalse(window.back_button.sensitive)
        self.assertEqual(window.next_button.label, "Next")
        self.assertNotIn(
            "suggested-action",
            window.next_button.style.classes,
        )

        window._show_page(1)
        self.assertEqual(window.stack.visible_child_name, "history")
        self.assertTrue(window.back_button.sensitive)
        self.assertEqual(window.next_button.label, "Next")

        last_page = len(window.PAGE_NAMES) - 1
        window._show_page(last_page)

        self.assertEqual(window.stack.visible_child_name, "autostart")
        self.assertEqual(window.next_button.label, "Finish")
        self.assertIn(
            "suggested-action",
            window.next_button.style.classes,
        )

    def test_next_advances_to_the_next_page(self):
        window = self.make_window()
        window.current_page = 0

        with patch.object(window, "_show_page") as show_page:
            window._on_next(None)

        show_page.assert_called_once_with(1)

    def test_back_returns_to_previous_page(self):
        window = self.make_window()
        window.current_page = 2

        with patch.object(window, "_show_page") as show_page:
            window._on_back(None)

        show_page.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
