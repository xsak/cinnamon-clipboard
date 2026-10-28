import logging

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ..i18n import _

logger = logging.getLogger(__name__)


class WelcomeWindow(Gtk.Window):
    """First-run setup wizard for Cinnamon Clipboard."""

    PAGE_NAMES = ("welcome", "history", "limit", "autostart")
    HISTORY_LIMITS = (10, 25, 50, 75, 100)

    def __init__(self, settings, on_complete):
        super().__init__(title=_("Welcome to Cinnamon Clipboard"))

        self.settings = settings
        self.on_complete = on_complete
        self.current_page = 0
        self._completed = False

        defaults = self.settings.DEFAULTS
        self.history_mode = defaults.get("history_mode", "persistent")
        self.max_history = defaults.get("max_history", 50)
        self.autostart = bool(defaults.get("autostart", False))

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(560, 460)
        self.set_resizable(False)
        self.set_border_width(20)
        self.set_icon_name("cinnamon-clipboard")

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.NONE)
        self.stack.set_hexpand(True)
        self.stack.set_vexpand(True)

        self._build_welcome_page()
        self._build_history_page()
        self._build_limit_page()
        self._build_autostart_page()

        self.back_button = Gtk.Button(label=_("Back"))
        self.back_button.connect("clicked", self._on_back)

        self.skip_button = Gtk.Button(label=_("Skip"))
        self.skip_button.connect("clicked", self._on_skip)

        self.next_button = Gtk.Button(label=_("Next"))
        self.next_button.connect("clicked", self._on_next)

        navigation = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        navigation.pack_start(self.back_button, False, False, 0)
        navigation.pack_start(self.skip_button, False, False, 0)

        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        navigation.pack_start(spacer, True, True, 0)
        navigation.pack_end(self.next_button, False, False, 0)

        layout = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
        )
        layout.pack_start(self.stack, True, True, 0)
        layout.pack_end(navigation, False, False, 0)

        self.add(layout)
        self.connect("delete-event", self._on_delete)

        self._show_page(0)

    @staticmethod
    def _make_heading(text):
        label = Gtk.Label()
        escaped_text = GLib.markup_escape_text(text)
        label.set_markup(f"<big><b>{escaped_text}</b></big>")
        label.set_xalign(0.0)
        label.set_line_wrap(True)
        return label

    @staticmethod
    def _make_description(text):
        label = Gtk.Label(label=text)
        label.set_xalign(0.0)
        label.set_line_wrap(True)
        label.set_max_width_chars(65)
        return label

    def _make_page(self, title, description):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=14,
        )
        page.set_halign(Gtk.Align.FILL)
        page.set_valign(Gtk.Align.START)

        page.pack_start(
            self._make_heading(title),
            False,
            False,
            0,
        )
        page.pack_start(
            self._make_description(description),
            False,
            False,
            0,
        )

        return page

    def _build_welcome_page(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
        )
        page.set_halign(Gtk.Align.CENTER)
        page.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name(
            "cinnamon-clipboard",
            Gtk.IconSize.DIALOG,
        )
        icon.set_pixel_size(64)
        page.pack_start(icon, False, False, 0)

        title = Gtk.Label()
        escaped_title = GLib.markup_escape_text(
            _("Welcome to Cinnamon Clipboard")
        )
        title.set_markup(f"<big><b>{escaped_title}</b></big>")
        title.set_justify(Gtk.Justification.CENTER)
        title.set_line_wrap(True)
        page.pack_start(title, False, False, 0)

        description = Gtk.Label(
            label=_(
                "This quick setup will help you configure your clipboard history, "
                "choose how many items to keep, and decide whether the app starts "
                "automatically when you log in."
            )
        )
        description.set_justify(Gtk.Justification.CENTER)
        description.set_line_wrap(True)
        description.set_max_width_chars(58)
        page.pack_start(description, False, False, 0)

        note = Gtk.Label(
            label=_(
                "You can skip this setup and use the default settings."
            )
        )
        note.set_justify(Gtk.Justification.CENTER)
        note.set_line_wrap(True)
        note.get_style_context().add_class("dim-label")
        page.pack_start(note, False, False, 0)

        self.stack.add_named(page, "welcome")

    def _build_history_page(self):
        page = self._make_page(
            _("Choose your history mode"),
            _(
                "Choose whether your clipboard history should be "
                "preserved after closing the application."
            ),
        )

        self.persistent_radio = Gtk.RadioButton.new_with_label_from_widget(
            None,
            _("Persistent history"),
        )
        self.persistent_radio.connect(
            "toggled",
            self._on_history_mode_changed,
            "persistent",
        )

        persistent_description = self._make_description(
            _(
                "The history is stored in an SQLite database on disk, "
                "along with images. Items are preserved when closing "
                "the application or restarting the PC."
            )
        )
        persistent_description.set_margin_start(24)

        self.temporary_radio = Gtk.RadioButton.new_with_label_from_widget(
            self.persistent_radio,
            _("Temporary history"),
        )
        self.temporary_radio.connect(
            "toggled",
            self._on_history_mode_changed,
            "temporary",
        )

        temporary_description = self._make_description(
            _(
                "The history is kept in RAM and is lost when closing "
                "the application or shutting down or restarting the PC. "
                "No persistent copy of the history is saved to disk."
            )
        )
        temporary_description.set_margin_start(24)

        page.pack_start(self.persistent_radio, False, False, 0)
        page.pack_start(persistent_description, False, False, 0)
        page.pack_start(self.temporary_radio, False, False, 0)
        page.pack_start(temporary_description, False, False, 0)

        if self.history_mode == "temporary":
            self.temporary_radio.set_active(True)
        else:
            self.persistent_radio.set_active(True)

        self.stack.add_named(page, "history")

    def _build_limit_page(self):
        page = self._make_page(
            _("History limit"),
            _("Choose the maximum number of unpinned history items."),
        )

        self.limit_combo = Gtk.ComboBoxText()

        for limit in self.HISTORY_LIMITS:
            self.limit_combo.append_text(str(limit))

        try:
            selected_index = self.HISTORY_LIMITS.index(
                int(self.max_history)
            )
        except (ValueError, TypeError):
            selected_index = self.HISTORY_LIMITS.index(50)

        self.limit_combo.set_active(selected_index)

        limit_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        limit_row.pack_start(
            Gtk.Label(label=_("Maximum history items:")),
            False,
            False,
            0,
        )
        limit_row.pack_start(self.limit_combo, False, False, 0)

        page.pack_start(limit_row, False, False, 0)

        note = Gtk.Label(
            label=_("This limit applies only to unpinned items.")
        )
        note.set_xalign(0.0)
        note.set_line_wrap(True)
        note.get_style_context().add_class("dim-label")
        page.pack_start(note, False, False, 0)

        self.stack.add_named(page, "limit")

    def _build_autostart_page(self):
        page = self._make_page(
            _("Start automatically"),
            _(
                "Choose whether Cinnamon Clipboard should start "
                "automatically when you log in."
            ),
        )

        self.autostart_check = Gtk.CheckButton(
            label=_("Start Cinnamon Clipboard automatically on login")
        )
        self.autostart_check.set_active(self.autostart)

        page.pack_start(self.autostart_check, False, False, 0)

        self.stack.add_named(page, "autostart")

    def _on_history_mode_changed(self, button, mode):
        if button.get_active():
            self.history_mode = mode

    def _show_page(self, page_index):
        self.current_page = page_index
        self.stack.set_visible_child_name(
            self.PAGE_NAMES[page_index]
        )

        self.back_button.set_sensitive(page_index > 0)

        if page_index == len(self.PAGE_NAMES) - 1:
            self.next_button.set_label(_("Finish"))
            self.next_button.get_style_context().add_class("suggested-action")
        else:
            self.next_button.set_label(_("Next"))
            self.next_button.get_style_context().remove_class("suggested-action")

    def _on_back(self, _button):
        if self.current_page > 0:
            self._show_page(self.current_page - 1)

    def _on_next(self, _button):
        if self.current_page < len(self.PAGE_NAMES) - 1:
            self._show_page(self.current_page + 1)
            return

        self._finish(use_defaults=False)

    def _on_skip(self, _button):
        self._finish(use_defaults=True)

    def _on_delete(self, _window, _event):
        if not self._completed:
            self._finish(use_defaults=True)

        return True

    def _finish(self, use_defaults):
        if self._completed:
            return

        if use_defaults:
            values = self.settings.DEFAULTS.copy()
        else:
            values = self.settings.DEFAULTS.copy()
            values["history_mode"] = self.history_mode
            values["max_history"] = int(
                self.limit_combo.get_active_text()
            )
            values["autostart"] = self.autostart_check.get_active()

        try:
            result = self.on_complete(values)
        except Exception:
            logger.exception(
                "Failed to complete the welcome wizard"
            )
            self._show_error()
            return

        if result is False:
            self._show_error()
            return

        self._completed = True
        self.destroy()

    def _show_error(self):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=_("Unable to save settings"),
        )
        dialog.format_secondary_text(
            _(
                "Your settings could not be saved. "
                "Please try again."
            )
        )
        dialog.run()
        dialog.destroy()