import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

from cinnamon_clipboard.core.settings import MENU_WIDTHS, SettingsManager
from cinnamon_clipboard.ui.menu_window import (
    LIST_MAX_SCREEN_FRACTION,
    PREVIEW_LINES,
    QuickMenuWindow,
)
from cinnamon_clipboard.ui.preferences_window import PreferencesWindow


class TestSettingsAndQuickMenu(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _make_settings(self, initial_data=None):
        with patch.object(Path, "home", return_value=Path(self.temp_dir.name)):
            if initial_data is not None:
                cfg_dir = Path(self.temp_dir.name) / ".config" / "cinnamon-clipboard"
                cfg_dir.mkdir(parents=True, exist_ok=True)
                with open(cfg_dir / "config.json", "w", encoding="utf-8") as f:
                    json.dump(initial_data, f)
            return SettingsManager()

    def _make_mock_clipboard_manager(self, settings=None, history=None):
        cm = MagicMock()
        cm.settings = settings or self._make_settings()
        cm.history = history if history is not None else [
            {"id": 1, "type": "text", "data": "first entry", "preview": "first entry", "pinned": False},
            {"id": 2, "type": "text", "data": "second entry", "preview": "second entry", "pinned": False},
            {"id": 3, "type": "text", "data": "third alpha", "preview": "third alpha", "pinned": False},
        ]
        cm.copy_item_to_system.return_value = True
        return cm

    def test_settings_defaults_and_validation(self):
        settings = self._make_settings()
        self.assertTrue(settings.get("focus_first_item"))
        self.assertTrue(settings.get("paste_on_select"))
        self.assertFalse(settings.config_was_reset)

        # Valid custom values are preserved
        settings2 = self._make_settings({
            "focus_first_item": False,
            "paste_on_select": False,
        })
        self.assertFalse(settings2.get("focus_first_item"))
        self.assertFalse(settings2.get("paste_on_select"))
        self.assertFalse(settings2.config_was_reset)

        # Invalid non-boolean values trigger reset to defaults
        settings3 = self._make_settings({
            "focus_first_item": "invalid",
        })
        self.assertTrue(settings3.config_was_reset)
        self.assertTrue(settings3.get("focus_first_item"))

    def test_invalid_menu_width_keeps_other_settings(self):
        settings = self._make_settings({"menu_width": 9999, "paste_on_select": False})
        self.assertFalse(settings.config_was_reset)
        self.assertEqual(settings.get("menu_width"), MENU_WIDTHS[0])
        self.assertFalse(settings.get("paste_on_select"))

    def test_open_focuses_and_selects_first_item_by_default(self):
        cm = self._make_mock_clipboard_manager()
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        selected = menu.list_box.get_selected_row()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.item_data["id"], 1)
        self.assertEqual(menu.get_focus(), selected)
        menu.destroy()

    def test_open_focuses_search_when_focus_first_item_disabled(self):
        settings = self._make_settings({"focus_first_item": False})
        cm = self._make_mock_clipboard_manager(settings=settings)
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        selected = menu.list_box.get_selected_row()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.item_data["id"], 1)
        self.assertEqual(menu.get_focus(), menu.search_entry)
        menu.destroy()

    def test_enter_activates_first_item_and_triggers_auto_paste(self):
        cm = self._make_mock_clipboard_manager()
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        event.keyval = Gdk.KEY_Return
        event.state = Gdk.ModifierType(0)

        handled = menu._on_key_press(menu, event)
        self.assertTrue(handled)
        cm.copy_item_to_system.assert_called_once_with(cm.history[0])
        cm.paste_to_active_window.assert_called_once()
        self.assertEqual(cm.paste_to_active_window.call_args.kwargs.get("item_type"), "text")
        menu.destroy()

    def test_auto_paste_targets_window_focused_before_menu_opened(self):
        cm = self._make_mock_clipboard_manager()
        cm.get_focused_toplevel_xid.return_value = 4242
        menu = QuickMenuWindow(cm)
        menu.toggle_window()

        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        event.keyval = Gdk.KEY_Return
        event.state = Gdk.ModifierType(0)

        menu._on_key_press(menu, event)
        self.assertEqual(cm.paste_to_active_window.call_args.kwargs.get("target_xid"), 4242)
        menu.destroy()

    def test_list_height_scales_with_screen(self):
        cm = self._make_mock_clipboard_manager()
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        screen_height = Gdk.Screen.get_default().get_monitor_geometry(0).height
        self.assertEqual(
            menu.scrolled.get_max_content_height(),
            int(screen_height * LIST_MAX_SCREEN_FRACTION),
        )
        menu.destroy()

    def test_menu_width_follows_setting(self):
        settings = self._make_settings()
        cm = self._make_mock_clipboard_manager(settings=settings)
        menu = QuickMenuWindow(cm)
        # Wide first, then narrower again, as when the setting is changed later.
        for width in (MENU_WIDTHS[2], MENU_WIDTHS[1], MENU_WIDTHS[0]):
            settings.set("menu_width", width)
            menu.refresh_and_show()
            self.assertEqual(menu.get_preferred_width()[0], width)
        menu.destroy()

    def test_menu_is_centred_on_panel_icon_at_its_real_width(self):
        settings = self._make_settings({"menu_width": MENU_WIDTHS[2]})
        cm = self._make_mock_clipboard_manager(settings=settings)
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        menu.panel_position = Gtk.PositionType.BOTTOM
        menu.panel_x = 800
        menu.panel_y = 1000
        with patch.object(menu, "move") as move:
            menu._update_position()
        self.assertEqual(move.call_args.args[0], 800 - MENU_WIDTHS[2] // 2)
        menu.destroy()

    def test_long_text_preview_is_limited_and_expandable(self):
        long_text = "word " * 200
        history = [
            {"id": 1, "type": "text", "data": long_text, "preview": long_text, "pinned": False},
            {"id": 2, "type": "text", "data": "short", "preview": "short", "pinned": False},
        ]
        cm = self._make_mock_clipboard_manager(history=history)
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        def expand_buttons(row):
            return [
                child for child in row.get_child().get_children()
                if isinstance(child, Gtk.Button)
                and child.get_tooltip_text() == "Show full content"
            ]

        long_row, short_row = menu.list_box.get_children()
        self.assertEqual(len(expand_buttons(long_row)), 1)
        self.assertEqual(expand_buttons(short_row), [])

        label = next(
            child for child in long_row.get_child().get_children()[-1].get_children()
            if isinstance(child, Gtk.Label)
        )
        self.assertEqual(label.get_lines(), PREVIEW_LINES)

        expand_buttons(long_row)[0].clicked()
        self.assertEqual(label.get_lines(), -1)
        self.assertEqual(label.get_text(), long_text.strip())
        menu.destroy()

    def test_pause_button_toggles_history_recording(self):
        cm = self._make_mock_clipboard_manager()
        menu = QuickMenuWindow(cm)
        self.assertFalse(menu.btn_pause.get_active())

        menu.btn_pause.set_active(True)
        cm.set_history_paused.assert_called_with(True)

        cm.settings.set("enable_history", False)
        menu._sync_pause_button()
        self.assertTrue(menu.btn_pause.get_active())

        menu.btn_pause.set_active(False)
        cm.set_history_paused.assert_called_with(False)
        menu.destroy()

    def test_enter_copies_without_auto_paste_when_disabled(self):
        settings = self._make_settings({"paste_on_select": False})
        cm = self._make_mock_clipboard_manager(settings=settings)
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        event.keyval = Gdk.KEY_Return
        event.state = Gdk.ModifierType(0)

        handled = menu._on_key_press(menu, event)
        self.assertTrue(handled)
        cm.copy_item_to_system.assert_called_once_with(cm.history[0])
        cm.paste_to_active_window.assert_not_called()
        menu.destroy()

    def test_arrow_navigation_and_type_to_search(self):
        cm = self._make_mock_clipboard_manager()
        menu = QuickMenuWindow(cm)
        menu.refresh_and_show()

        # Press Down to select the second item
        down_event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        down_event.keyval = Gdk.KEY_Down
        down_event.state = Gdk.ModifierType(0)
        self.assertTrue(menu._on_key_press(menu, down_event))
        self.assertEqual(menu.list_box.get_selected_row().item_data["id"], 2)

        # Type 'a' while row is focused -> redirects to search_entry and selects first matching item ("third alpha")
        type_event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        type_event.keyval = Gdk.KEY_a
        type_event.state = Gdk.ModifierType(0)
        self.assertTrue(menu._on_key_press(menu, type_event))
        self.assertEqual(menu.search_entry.get_text(), "a")
        self.assertEqual(menu.list_box.get_selected_row().item_data["id"], 3)

        # Press Enter to activate filtered match
        enter_event = Gdk.Event.new(Gdk.EventType.KEY_PRESS)
        enter_event.keyval = Gdk.KEY_Return
        enter_event.state = Gdk.ModifierType(0)
        self.assertTrue(menu._on_key_press(menu, enter_event))
        cm.copy_item_to_system.assert_called_once_with(cm.history[2])
        menu.destroy()

    def test_preferences_window_saves_new_options(self):
        settings = self._make_settings()
        cm = self._make_mock_clipboard_manager(settings=settings)
        prefs = PreferencesWindow(settings, cm)

        self.assertTrue(prefs.switch_focus_first.get_active())
        self.assertTrue(prefs.switch_paste_select.get_active())

        self.assertEqual(prefs.combo_menu_width.get_active_id(), str(MENU_WIDTHS[0]))

        prefs.switch_focus_first.set_active(False)
        prefs.switch_paste_select.set_active(False)
        prefs.combo_menu_width.set_active_id(str(MENU_WIDTHS[1]))
        prefs._on_save_clicked(None)

        self.assertFalse(settings.get("focus_first_item"))
        self.assertFalse(settings.get("paste_on_select"))
        self.assertEqual(settings.get("menu_width"), MENU_WIDTHS[1])


if __name__ == "__main__":
    unittest.main()
