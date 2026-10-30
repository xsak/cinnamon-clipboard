import gi
import logging

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")

from gi.repository import Gtk, Gdk, GLib

logger = logging.getLogger(__name__)

from ..i18n import _
from ..update_checker import check_for_updates
from ..installation import PACKAGE_MANAGED


class PreferencesWindow(Gtk.Window):
    """Cinnamon Clipboard configuration/preferences window."""

    def __init__(
        self,
        settings_manager,
        clipboard_manager,
        on_shortcut_changed_callback=None,
        app=None,
    ):
        super().__init__(title=_("Preferences"))

        self.set_wmclass("cinnamon-clipboard", "CinnamonClipboard")
        
        self.settings = settings_manager
        self.clipboard_manager = clipboard_manager
        self.on_shortcut_changed_callback = on_shortcut_changed_callback
        self.app = app

        self.set_default_size(600, 550)
        self.set_resizable(True)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)

        # Load temporary values (to apply only if the user clicks "Save")
        self.temp_settings = {
            "enable_history": self.settings.get("enable_history"),
            "history_mode": self.settings.get("history_mode") or "persistent",
            "max_history": self.settings.get("max_history"),
            "save_images": self.settings.get("save_images"),
            "save_files": self.settings.get("save_files"),
            "autostart": self.settings.get("autostart"),
            "focus_first_item": self.settings.get("focus_first_item"),
            "paste_on_select": self.settings.get("paste_on_select"),
            "shortcut": self.settings.get("shortcut"),
            "check_updates": self.settings.get("check_updates"),
        }

        self.is_capturing_shortcut = False

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        main_box.set_margin_top(16)
        main_box.set_margin_bottom(16)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        self.add(main_box)

        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
            list.settings-list row.settings-row {
                border: 1px solid @borders;
                border-radius: 6px;
                margin-top: 3px;
                margin-bottom: 3px;
            }
            list.settings-list row.settings-row:hover {
                background-color: @theme_bg_color;
                background-image: linear-gradient(
                    alpha(@theme_selected_bg_color, 0.10),
                    alpha(@theme_selected_bg_color, 0.10)
                );
            }
        """)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        notebook = Gtk.Notebook()
        notebook.set_scrollable(True)
        main_box.pack_start(notebook, True, True, 0)

        # --- SECTION 1: HISTORY AND PRIVACY ---
        grid_history = Gtk.Grid()
        grid_history.set_column_spacing(24)
        grid_history.set_row_spacing(14)
        grid_history.set_hexpand(True)
        grid_history.set_margin_start(10)
        grid_history.set_margin_end(10)
        grid_history.set_margin_top(8)
        grid_history.set_margin_bottom(8)

        scrolled_history = Gtk.ScrolledWindow()
        scrolled_history.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        scrolled_history.set_hexpand(True)
        scrolled_history.set_vexpand(True)
        scrolled_history.add(grid_history)
        notebook.append_page(scrolled_history, Gtk.Label(label=_("History and Privacy")))

        grid = grid_history
        row = 0

        self.switch_enable = Gtk.Switch()
        self.switch_enable.set_halign(Gtk.Align.END)
        self.switch_enable.set_active(self.temp_settings["enable_history"])
        self.switch_enable.connect(
            "state-set",
            lambda s, state: self._set_temp("enable_history", state)
        )
        enable_row = self._create_settings_row(
            _("Record clipboard history"),
            _("When disabled, new clipboard items won't be recorded."),
            self.switch_enable,
        )
        enable_list = self._create_settings_list(enable_row)
        enable_list.connect(
            "row-activated",
            lambda _list, _row: self.switch_enable.set_active(
                not self.switch_enable.get_active()
            ),
        )
        grid.attach(enable_list, 0, row, 2, 1)
        row += 1

        # History storage mode
        lbl_mode = Gtk.Label(xalign=0)
        history_mode_label = _("History mode")
        lbl_mode.set_markup(
            f"<b>{GLib.markup_escape_text(history_mode_label)}</b>"
        )
        lbl_mode.set_margin_start(18)
        lbl_mode.set_halign(Gtk.Align.START)
        grid.attach(lbl_mode, 0, row, 2, 1)
        row += 1

        self.radio_persistent = Gtk.RadioButton.new_with_label(
            None, _("Persistent history")
        )
        self.radio_persistent.set_halign(Gtk.Align.START)
        self.radio_persistent.set_margin_start(36)

        self.radio_temporary = Gtk.RadioButton.new_with_label_from_widget(
            self.radio_persistent, _("Temporary history")
        )
        self.radio_temporary.set_halign(Gtk.Align.START)
        self.radio_temporary.set_margin_start(36)

        current_mode = self.temp_settings.get("history_mode") or "persistent"
        self.radio_persistent.set_active(current_mode == "persistent")
        self.radio_temporary.set_active(current_mode == "temporary")

        self.radio_persistent.connect(
            "toggled",
            lambda b: b.get_active() and self._set_temp(
                "history_mode", "persistent"
            )
        )
        self.radio_temporary.connect(
            "toggled",
            lambda b: b.get_active() and self._set_temp(
                "history_mode", "temporary"
            )
        )
        lbl_persistent_desc = _(
                "The history is stored in an SQLite database on disk, "
                "along with images. Items are preserved when closing "
                "the application or restarting the PC."
        )
        lbl_temporary_desc = _(
                "The history is kept in RAM and is lost when closing "
                "the application or shutting down or restarting the PC. "
                "No persistent copy of the history is saved to disk."
        )
        self.radio_persistent.set_label("")
        self.radio_temporary.set_label("")

        persistent_row = self._create_settings_row(
            _("Persistent history"),
            lbl_persistent_desc,
            self.radio_persistent,
        )
        temporary_row = self._create_settings_row(
            _("Temporary history"),
            lbl_temporary_desc,
            self.radio_temporary,
        )
        mode_list = self._create_settings_list(
            persistent_row,
            temporary_row,
        )
        mode_list.connect(
            "row-activated",
            self._on_history_mode_row_activated,
        )
        grid.attach(mode_list, 0, row, 2, 1)
        row += 1

        current_limit = self.temp_settings["max_history"]
        self.combo_history_limit = Gtk.ComboBoxText()
        self.combo_history_limit.set_halign(Gtk.Align.END)
        for limit in (10, 25, 50, 75, 100):
            self.combo_history_limit.append(str(limit), str(limit))
        if current_limit not in (10, 25, 50, 75, 100):
            current_limit = 50
        self.combo_history_limit.set_active_id(str(current_limit))
        self.combo_history_limit.connect(
            "changed",
            self._on_history_limit_changed,
        )
        limit_row = self._create_settings_row(
            _("History limit"),
            _("Applies only to unpinned items."),
            self.combo_history_limit,
            _("Choose one of: 10, 25, 50, 75, or 100 items."),
        )
        limit_list = self._create_settings_list(limit_row)
        grid.attach(limit_list, 0, row, 2, 1)
        row += 1

        # --- SECTION 2: CONTENT CAPTURE ---
        grid_capture = Gtk.Grid()
        grid_capture.set_column_spacing(24)
        grid_capture.set_row_spacing(14)
        grid_capture.set_hexpand(True)
        grid_capture.set_margin_start(10)
        grid_capture.set_margin_end(10)
        grid_capture.set_margin_top(8)
        grid_capture.set_margin_bottom(8)

        scrolled_capture = Gtk.ScrolledWindow()
        scrolled_capture.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        scrolled_capture.set_hexpand(True)
        scrolled_capture.set_vexpand(True)
        scrolled_capture.add(grid_capture)
        notebook.append_page(scrolled_capture, Gtk.Label(label=_("Content Capture")))

        grid = grid_capture
        row = 0

        self.switch_images = Gtk.Switch()
        self.switch_images.set_halign(Gtk.Align.END)
        self.switch_images.set_active(self.temp_settings["save_images"])
        self.switch_images.connect(
            "state-set",
            lambda s, state: self._set_temp("save_images", state)
        )
        images_row = self._create_switch_row(
            _("Capture images"),
            _("Save images copied to the clipboard."),
            self.switch_images,
        )

        self.switch_files = Gtk.Switch()
        self.switch_files.set_halign(Gtk.Align.END)
        self.switch_files.set_active(self.temp_settings["save_files"])
        self.switch_files.connect(
            "state-set",
            lambda s, state: self._set_temp("save_files", state)
        )
        files_row = self._create_switch_row(
            _("Capture files and folders"),
            _("Keep file and folder clipboard entries."),
            self.switch_files,
        )
        capture_list = self._create_settings_list(images_row, files_row)
        capture_list.connect(
            "row-activated",
            self._on_capture_row_activated,
        )
        grid.attach(capture_list, 0, row, 1, 1)
        row += 1

        # --- SECTION 3: SYSTEM AND SHORTCUT ---
        grid_system = Gtk.Grid()
        grid_system.set_column_spacing(24)
        grid_system.set_row_spacing(14)
        grid_system.set_hexpand(True)
        grid_system.set_margin_start(10)
        grid_system.set_margin_end(10)
        grid_system.set_margin_top(8)
        grid_system.set_margin_bottom(8)

        scrolled_system = Gtk.ScrolledWindow()
        scrolled_system.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        scrolled_system.set_hexpand(True)
        scrolled_system.set_vexpand(True)
        scrolled_system.add(grid_system)
        notebook.append_page(scrolled_system, Gtk.Label(label=_("System and Shortcut")))

        grid = grid_system
        row = 0

        self.switch_autostart = Gtk.Switch()
        self.switch_autostart.set_halign(Gtk.Align.END)
        self.switch_autostart.set_active(self.temp_settings["autostart"])
        self.switch_autostart.connect(
            "state-set",
            lambda s, state: self._set_temp("autostart", state)
        )
        autostart_row = self._create_switch_row(
            _("Start with session"),
            _("Launch Cinnamon Clipboard when you log in."),
            self.switch_autostart,
        )

        self.btn_shortcut = Gtk.Button(
            label=self._format_shortcut_label(
                self.temp_settings["shortcut"]
            )
        )
        self.btn_shortcut.set_halign(Gtk.Align.END)
        self.btn_shortcut.connect(
            "clicked", self._start_capturing_shortcut
        )
        shortcut_row = self._create_settings_row(
            _("Tray menu shortcut"),
            _("Press the button to record a new key combination."),
            self.btn_shortcut,
        )

        self.switch_focus_first = Gtk.Switch()
        self.switch_focus_first.set_halign(Gtk.Align.END)
        self.switch_focus_first.set_active(
            self.temp_settings["focus_first_item"]
        )
        self.switch_focus_first.connect(
            "state-set",
            lambda s, state: self._set_temp("focus_first_item", state)
        )
        focus_row = self._create_switch_row(
            _("Focus first item when opening menu"),
            _("Move keyboard focus to the first item when the tray menu opens."),
            self.switch_focus_first,
        )

        self.switch_paste_select = Gtk.Switch()
        self.switch_paste_select.set_halign(Gtk.Align.END)
        self.switch_paste_select.set_active(
            self.temp_settings["paste_on_select"]
        )
        self.switch_paste_select.connect(
            "state-set",
            lambda s, state: self._set_temp("paste_on_select", state)
        )
        paste_row = self._create_switch_row(
            _("Paste automatically when selecting an item"),
            _("Automatically paste the selected item into the active application."),
            self.switch_paste_select,
        )

        system_list = self._create_settings_list(
            autostart_row,
            shortcut_row,
            focus_row,
            paste_row,
        )
        system_list.connect("row-activated", self._on_system_row_activated)
        grid.attach(system_list, 0, row, 1, 1)
        row += 1

        # --- SECTION 4: UPDATES ---
        grid_updates = Gtk.Grid()
        grid_updates.set_column_spacing(24)
        grid_updates.set_row_spacing(14)
        grid_updates.set_hexpand(True)
        grid_updates.set_margin_start(10)
        grid_updates.set_margin_end(10)
        grid_updates.set_margin_top(8)
        grid_updates.set_margin_bottom(8)

        scrolled_updates = Gtk.ScrolledWindow()
        scrolled_updates.set_policy(
            Gtk.PolicyType.NEVER,
            Gtk.PolicyType.AUTOMATIC,
        )
        scrolled_updates.set_hexpand(True)
        scrolled_updates.set_vexpand(True)
        scrolled_updates.add(grid_updates)
        if not PACKAGE_MANAGED:
            notebook.append_page(
                scrolled_updates,
                Gtk.Label(label=_("Updates")),
            )

        grid = grid_updates
        row = 0

        self.switch_check_updates = Gtk.Switch()
        self.switch_check_updates.set_halign(Gtk.Align.END)
        self.switch_check_updates.set_active(
            self.temp_settings["check_updates"]
        )
        self.switch_check_updates.connect(
            "state-set",
            lambda switch, state: self._set_temp("check_updates", state),
        )

        self.btn_check_updates = Gtk.Button(
            label=_("Check for updates now")
        )
        self.btn_check_updates.connect(
            "clicked",
            self._on_check_updates_clicked,
        )

        self.lbl_update_status = Gtk.Label(xalign=0)
        self.lbl_update_status.set_line_wrap(True)
        self.lbl_update_status.set_margin_start(18)
        self.lbl_update_status.set_margin_end(18)
        self.lbl_update_status.set_halign(Gtk.Align.START)
        self.lbl_update_status.get_style_context().add_class("dim-label")
        updates_row = self._create_switch_row(
            _("Check for updates at startup"),
            _("Check for a new Cinnamon Clipboard release at startup."),
            self.switch_check_updates,
        )
        check_row = self._create_settings_row(
            _("Check for updates now"),
            None,
            self.btn_check_updates,
        )
        updates_list = self._create_settings_list(updates_row, check_row)
        updates_list.connect("row-activated", self._on_updates_row_activated)
        grid.attach(updates_list, 0, row, 1, 1)
        row += 1
        grid.attach(self.lbl_update_status, 0, row, 1, 1)
        row += 1

        if PACKAGE_MANAGED:
            self.switch_check_updates.set_sensitive(False)
            self.btn_check_updates.set_sensitive(False)
            self.lbl_update_status.set_text(
                _("Updates are managed by APT.")
            )


        # LOWER ACTION BAR (CANCEL / SAVE)
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bottom_box.set_halign(Gtk.Align.END)

        btn_cancel = Gtk.Button(label=_("Cancel"))
        btn_cancel.connect("clicked", lambda b: self.destroy())
        bottom_box.pack_start(btn_cancel, False, False, 0)

        btn_save = Gtk.Button(label=_("Save"))
        btn_save.get_style_context().add_class("suggested-action")
        btn_save.connect("clicked", self._on_save_clicked)
        bottom_box.pack_start(btn_save, False, False, 0)

        main_box.pack_start(bottom_box, False, False, 0)

        self.connect("key-press-event", self._on_key_press_event)

    def _create_settings_list(self, *rows):
        list_box = Gtk.ListBox()
        list_box.get_style_context().add_class("settings-list")
        list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        list_box.set_activate_on_single_click(True)
        list_box.set_hexpand(True)
        for row in rows:
            list_box.add(row)
        return list_box

    def _create_settings_row(self, title, subtitle=None, control=None, tooltip=None):
        row = Gtk.ListBoxRow()
        row.set_activatable(True)
        row.get_style_context().add_class("settings-row")

        outer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        outer.set_margin_start(12)
        outer.set_margin_end(12)
        outer.set_margin_top(8)
        outer.set_margin_bottom(8)

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)

        title_label = Gtk.Label(label=title, xalign=0)
        title_label.set_halign(Gtk.Align.START)
        title_label.set_selectable(False)
        text_box.pack_start(title_label, False, False, 0)

        if subtitle:
            subtitle_label = Gtk.Label(label=subtitle, xalign=0)
            subtitle_label.set_halign(Gtk.Align.START)
            subtitle_label.set_line_wrap(True)
            subtitle_label.set_max_width_chars(55)
            subtitle_label.get_style_context().add_class("dim-label")
            text_box.pack_start(subtitle_label, False, False, 0)

        outer.pack_start(text_box, True, True, 0)
        if control is not None:
            control.set_halign(Gtk.Align.END)
            outer.pack_end(control, False, False, 0)

        if tooltip:
            row.set_tooltip_text(tooltip)

        row.add(outer)
        return row

    def _create_switch_row(self, title, subtitle, switch, tooltip=None):
        row = self._create_settings_row(title, subtitle, switch, tooltip)
        return row

    def _on_history_mode_row_activated(self, list_box, row):
        if list_box.get_row_at_index(0) == row:
            self.radio_persistent.set_active(True)
        elif list_box.get_row_at_index(1) == row:
            self.radio_temporary.set_active(True)

    def _on_capture_row_activated(self, list_box, row):
        if list_box.get_row_at_index(0) == row:
            self.switch_images.set_active(not self.switch_images.get_active())
        elif list_box.get_row_at_index(1) == row:
            self.switch_files.set_active(not self.switch_files.get_active())

    def _on_system_row_activated(self, list_box, row):
        if list_box.get_row_at_index(0) == row:
            self.switch_autostart.set_active(not self.switch_autostart.get_active())
        elif list_box.get_row_at_index(1) == row:
            self.btn_shortcut.clicked()
        elif list_box.get_row_at_index(2) == row:
            self.switch_focus_first.set_active(
                not self.switch_focus_first.get_active()
            )
        elif list_box.get_row_at_index(3) == row:
            self.switch_paste_select.set_active(
                not self.switch_paste_select.get_active()
            )

    def _on_updates_row_activated(self, list_box, row):
        if list_box.get_row_at_index(0) == row:
            if self.switch_check_updates.get_sensitive():
                self.switch_check_updates.set_active(
                    not self.switch_check_updates.get_active()
                )
        elif list_box.get_row_at_index(1) == row:
            self.btn_check_updates.clicked()

    def _set_temp(self, key, value):
        self.temp_settings[key] = value
        return False

    def _on_history_limit_changed(self, combo):
        active_id = combo.get_active_id()
        if active_id:
            self._set_temp("max_history", int(active_id))

    def _on_check_updates_clicked(self, button):
        if self.app is None:
            self.lbl_update_status.set_text(
                _("Unable to check for updates.")
            )
            return

        self.btn_check_updates.set_sensitive(False)
        self.lbl_update_status.set_text(_("Checking for updates..."))

        check_for_updates(
            self.app,
            callback=self._on_manual_update_result,
            notify_if_new=False,
        )

    def _on_manual_update_result(self, status, release):
        self.btn_check_updates.set_sensitive(True)

        if status == "current":
            self.lbl_update_status.set_text(
                _("Cinnamon Clipboard is up to date.")
            )
            return

        if status == "error":
            self.lbl_update_status.set_text(
                _("Unable to check for updates.")
            )
            return

        self.lbl_update_status.set_text(
            _("A new version is available.")
        )

        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.NONE,
            text=_("A new version of Cinnamon Clipboard is available."),
        )

        dialog.format_secondary_text(
            _("Version %(version)s is available.")
            % {"version": release["version"]}
        )

        changelog = release.get("body", "").strip()
        if changelog:
            dialog.get_message_area().pack_start(
                Gtk.Label(label=changelog, xalign=0),
                False,
                False,
                8,
            )
            dialog.get_message_area().show_all()

        dialog.add_button(_("Later"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("View release"), Gtk.ResponseType.ACCEPT)

        response = dialog.run()
        dialog.destroy()

        if response == Gtk.ResponseType.ACCEPT:
            import webbrowser
            webbrowser.open(release["url"])

    def _format_shortcut_label(self, shortcut_str):
        if not shortcut_str:
            return _("Click to assign")
        return shortcut_str.replace("<Super>", "Super + ").replace("<Ctrl>", "Ctrl + ").replace("<Alt>", "Alt + ").replace("<Shift>", "Shift + ")

    def _start_capturing_shortcut(self, btn):
        self.is_capturing_shortcut = True
        self.btn_shortcut.set_label(_("Press a key combination..."))

    def _on_key_press_event(self, widget, event):
        if not self.is_capturing_shortcut:
            return False

        keyval = event.keyval
        state = event.state

        # Ignore isolated modifier key presses
        if keyval in (Gdk.KEY_Control_L, Gdk.KEY_Control_R,
                      Gdk.KEY_Shift_L, Gdk.KEY_Shift_R,
                      Gdk.KEY_Alt_L, Gdk.KEY_Alt_R,
                      Gdk.KEY_Super_L, Gdk.KEY_Super_R):
            return True

        # Esc to cancel capture
        if keyval == Gdk.KEY_Escape:
            self.is_capturing_shortcut = False
            self.btn_shortcut.set_label(self._format_shortcut_label(self.temp_settings["shortcut"]))
            return True

        modifiers = []
        if state & Gdk.ModifierType.SUPER_MASK or state & Gdk.ModifierType.MOD4_MASK:
            modifiers.append("<Super>")
        if state & Gdk.ModifierType.CONTROL_MASK:
            modifiers.append("<Ctrl>")
        if state & Gdk.ModifierType.MOD1_MASK:
            modifiers.append("<Alt>")
        if state & Gdk.ModifierType.SHIFT_MASK:
            modifiers.append("<Shift>")

        key_name = Gdk.keyval_name(keyval)
        if key_name:
            key_str = key_name.lower()
            shortcut_code = "".join(modifiers) + key_str
            self.temp_settings["shortcut"] = shortcut_code
            self.btn_shortcut.set_label(self._format_shortcut_label(shortcut_code))

        self.is_capturing_shortcut = False
        return True

    def _confirm_history_mode_change(self, old_mode, new_mode):
        if old_mode == "persistent" and new_mode == "temporary":
            title = _("Switch to temporary history?")
            explanation = _(
                "The saved clipboard history database and its images "
                "will be permanently deleted. The application will restart "
                "with an empty history stored only in memory."
            )
            message_type = Gtk.MessageType.WARNING
            continue_label = _("Delete history and switch")
        else:
            title = _("Switch to persistent history?")
            explanation = _(
                "The temporary history will be lost when the application "
                "restarts. Persistent history will start empty."
            )
            message_type = Gtk.MessageType.QUESTION
            continue_label = _("Restart and switch")

        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=message_type,
            buttons=Gtk.ButtonsType.NONE,
            text=title,
        )
        dialog.format_secondary_text(explanation)
        dialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(continue_label, Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)

        response = dialog.run()
        dialog.destroy()

        return response == Gtk.ResponseType.OK

    def _delete_persistent_history(self):
        """Remove persistent history using ClipboardManager's implementation."""
        self.clipboard_manager._clean_persistent_storage()

    def _show_history_delete_error(self, error):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=_("Could not delete the saved history"),
        )
        dialog.format_secondary_text(
            _(
                "The history mode has not been changed. "
                "Check the file permissions and try again."
            )
            + "\n\n"
            + str(error)
        )
        dialog.run()
        dialog.destroy()


    def _show_settings_save_error(self):
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=_("Could not save preferences"),
        )
        dialog.format_secondary_text(
            _(
                "The preferences could not be saved. "
                "Check the file permissions and try again."
            )
        )
        dialog.run()
        dialog.destroy()


    def _on_save_clicked(self, btn):
        old_settings = dict(self.settings.settings)
        old_mode = old_settings.get("history_mode") or "persistent"
        new_mode = self.temp_settings.get("history_mode") or "persistent"
        mode_changed = old_mode != new_mode
        old_autostart = old_settings.get("autostart", False)
        new_autostart = self.temp_settings["autostart"]
        autostart_snapshot = None

        if mode_changed:
            if not self._confirm_history_mode_change(old_mode, new_mode):
                self.temp_settings["history_mode"] = old_mode
                self.radio_persistent.set_active(old_mode == "persistent")
                self.radio_temporary.set_active(old_mode == "temporary")
                return

        if new_autostart != old_autostart:
            try:
                autostart_snapshot = (
                    self.settings.snapshot_autostart_file()
                )
            except OSError:
                logger.exception("Could not inspect autostart file")
                self._show_settings_save_error()
                return

            if not self.settings.set_autostart(new_autostart):
                self.settings.settings["autostart"] = old_autostart
                self.settings.restore_autostart_file(autostart_snapshot)
                self._show_settings_save_error()
                return

        self.settings.settings.update(self.temp_settings)
        if not self.settings.save():
            self.settings.settings.clear()
            self.settings.settings.update(old_settings)
            config_restored = self.settings.save()

            autostart_restored = True
            if autostart_snapshot is not None:
                autostart_restored = (
                    self.settings.restore_autostart_file(
                        autostart_snapshot
                    )
                )

            if not config_restored or not autostart_restored:
                logger.critical(
                    "Could not fully restore preferences after save failure"
                )

            self._show_settings_save_error()
            return

        if mode_changed:
            try:
                self._delete_persistent_history()
            except OSError as error:
                self.settings.settings.clear()
                self.settings.settings.update(old_settings)
                self.settings.save()

                if autostart_snapshot is not None:
                    self.settings.restore_autostart_file(
                        autostart_snapshot
                    )

                self.temp_settings["history_mode"] = old_mode
                self.radio_persistent.set_active(old_mode == "persistent")
                self.radio_temporary.set_active(old_mode == "temporary")
                self._show_history_delete_error(error)
                return

        self.clipboard_manager.apply_max_history(
            self.temp_settings["max_history"]
        )

        if self.on_shortcut_changed_callback:
            self.on_shortcut_changed_callback(
                self.temp_settings["shortcut"]
            )

        self.destroy()

        if mode_changed and self.app is not None:
            self.app.restart_app()
