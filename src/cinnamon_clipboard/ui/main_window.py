import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")

from gi.repository import Gtk, Pango

from ..i18n import _

class MainWindow(Gtk.Window):
    """Main clipboard history management window."""

    def __init__(self, clipboard_manager):
        super().__init__(title=_("Cinnamon Clipboard"))

        self.clipboard_manager = clipboard_manager
        self.current_filter_type = "ALL"  # ALL, text, image, files

        self.set_default_size(680, 520)
        self.set_position(Gtk.WindowPosition.CENTER)

        # Subscribe to receive notifications when the clipboard changes
        self.clipboard_manager.add_history_listener(self.refresh_list)
        self.connect("destroy", self._on_destroy)

        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        self.add(main_box)

        # 1. Top bar: search and filters
        top_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text(_("Search history..."))
        self.search_entry.connect("search-changed", self._on_search_changed)
        top_box.pack_start(self.search_entry, True, True, 0)

        # Category filter buttons
        filter_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        filter_box.set_valign(Gtk.Align.CENTER)
        
        btn_all = Gtk.RadioButton.new_with_label(None, _("All"))
        btn_all.connect("toggled", self._on_filter_changed, "ALL")
        filter_box.pack_start(btn_all, False, False, 0)

        btn_text = Gtk.RadioButton.new_with_label_from_widget(btn_all, _("Text"))
        btn_text.connect("toggled", self._on_filter_changed, "text")
        filter_box.pack_start(btn_text, False, False, 0)

        btn_img = Gtk.RadioButton.new_with_label_from_widget(btn_all, _("Images"))
        btn_img.connect("toggled", self._on_filter_changed, "image")
        filter_box.pack_start(btn_img, False, False, 0)

        btn_files = Gtk.RadioButton.new_with_label_from_widget(btn_all, _("Files"))
        btn_files.connect("toggled", self._on_filter_changed, "files")
        filter_box.pack_start(btn_files, False, False, 0)

        top_box.pack_end(filter_box, False, False, 0)
        main_box.pack_start(top_box, False, False, 0)

        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Status bar shown only while history recording is paused
        self.paused_bar = Gtk.InfoBar()
        self.paused_bar.set_message_type(Gtk.MessageType.WARNING)
        self.paused_bar.add_button(_("Resume"), Gtk.ResponseType.ACCEPT)
        self.paused_bar.connect("response", lambda _bar, _response: self._set_paused(False))
        paused_label = Gtk.Label(label=_("History recording is paused."), xalign=0)
        self.paused_bar.get_content_area().pack_start(paused_label, True, True, 0)
        paused_label.show()
        # Kept out of show_all(); _sync_pause_state() decides whether it is visible.
        self.paused_bar.set_no_show_all(True)
        main_box.pack_start(self.paused_bar, False, False, 0)

        # 2. Scrollable list area
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scrolled.set_shadow_type(Gtk.ShadowType.IN)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self.scrolled.add(self.list_box)

        main_box.pack_start(self.scrolled, True, True, 0)

        # 3. Bottom bar: general actions
        main_box.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)


        btn_about = Gtk.Button.new_from_icon_name("help-about-symbolic", Gtk.IconSize.BUTTON)
        btn_about.set_tooltip_text(_("About"))
        btn_about.connect("clicked", self._open_about)
        bottom_box.pack_end(btn_about, False, False, 0)

        btn_pref = Gtk.Button.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.BUTTON)
        btn_pref.set_tooltip_text(_("Preferences"))
        btn_pref.connect("clicked", self._open_preferences)
        bottom_box.pack_end(btn_pref, False, False, 0)

        self.btn_pause = Gtk.ToggleButton()
        self.btn_pause.set_image(
            Gtk.Image.new_from_icon_name("media-playback-pause-symbolic", Gtk.IconSize.BUTTON)
        )
        self._pause_handler_id = self.btn_pause.connect(
            "toggled", lambda button: self._set_paused(button.get_active())
        )
        bottom_box.pack_end(self.btn_pause, False, False, 0)

        btn_quit = Gtk.Button(label=_("Quit"))
        btn_quit.set_tooltip_text(_("Close Cinnamon Clipboard"))
        btn_quit.connect("clicked", self._on_quit_clicked)
        bottom_box.pack_end(btn_quit, False, False, 0)

        main_box.pack_start(bottom_box, False, False, 0)



        # Load initial data
        self.refresh_list()

    def _open_about(self, btn):
        app = self.get_application()
        if app:
            app.open_about(parent=self)

    def _open_preferences(self, btn):
        app = self.get_application()
        if app:
            app.open_preferences(parent=self)

    def _set_paused(self, paused):
        self.clipboard_manager.set_history_paused(paused)
        self._sync_pause_state()

    def _sync_pause_state(self):
        """Show whether history recording is paused (the "Record clipboard history" setting)."""
        paused = not self.clipboard_manager.settings.get("enable_history")
        self.btn_pause.handler_block(self._pause_handler_id)
        self.btn_pause.set_active(paused)
        self.btn_pause.handler_unblock(self._pause_handler_id)
        if paused:
            self.btn_pause.set_tooltip_text(_("History recording is paused. Click to resume."))
        else:
            self.btn_pause.set_tooltip_text(_("Pause history recording"))
        self.paused_bar.set_visible(paused)

    def _on_destroy(self, widget):
        """Remove the subscription when the window is closed."""
        self.clipboard_manager.remove_history_listener(self.refresh_list)

    def refresh_list(self):
        """Redraw the list applying the category filter and search text."""
        self._sync_pause_state()
        for child in self.list_box.get_children():
            self.list_box.remove(child)

        query = self.search_entry.get_text().strip().lower()
        history = self.clipboard_manager.history
        visible_count = 0

        if not history:
            self.list_box.add(
                self._create_status_row(
                    "edit-clear-symbolic",
                    _("Clipboard history is empty"),
                )
            )
            self.list_box.show_all()
            return

        for item in history:
            item_type = item.get("type")

            # Filter by type
            if self.current_filter_type != "ALL" and item_type != self.current_filter_type:
                continue

            # Filter by text / search
            if query:
                preview = str(item.get("preview", "")).lower()
                data_str = str(item.get("data", "")).lower()
                if query not in preview and query not in data_str:
                    continue

            row_widget = self._create_row_widget(item)
            self.list_box.add(row_widget)
            visible_count += 1

        if visible_count == 0:
            self.list_box.add(
                self._create_status_row(
                    "system-search-symbolic",
                    _("No results found"),
                )
            )

        self.list_box.show_all()

    def _create_status_row(self, icon_name, text):
        list_row = Gtk.ListBoxRow()
        list_row.set_selectable(False)
        list_row.set_activatable(False)

        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
        )
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)
        box.set_margin_top(24)
        box.set_margin_bottom(24)

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DIALOG)
        icon.set_valign(Gtk.Align.CENTER)
        box.pack_start(icon, False, False, 0)

        label = Gtk.Label(label=text, xalign=0)
        label.get_style_context().add_class("dim-label")
        box.pack_start(label, False, False, 0)

        list_row.add(box)
        return list_row

    def _create_row_widget(self, item):
        """Build the row for a history item."""
        list_row = Gtk.ListBoxRow()
        
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(8)
        box.set_margin_bottom(8)

        item_type = item.get("type")

        # 1. Icon or thumbnail
        if item_type == "image":
            if item.get("pixbuf"):
                scaled = self.clipboard_manager._scale_pixbuf(item["pixbuf"], target_size=80)
                img = Gtk.Image.new_from_pixbuf(scaled)
                img.set_valign(Gtk.Align.CENTER)
                box.pack_start(img, False, False, 0)
            else:
                lbl_type = Gtk.Label(label=_("[Image]"))
                lbl_type.set_valign(Gtk.Align.CENTER)
                box.pack_start(lbl_type, False, False, 0)

            info_label = Gtk.Label(label=item.get("preview", _("Image")), xalign=0)
            info_label.set_valign(Gtk.Align.CENTER)
            box.pack_start(info_label, True, True, 0)

        elif item_type == "files":
            icon = Gtk.Image.new_from_icon_name("folder-documents-symbolic", Gtk.IconSize.BUTTON)
            icon.set_valign(Gtk.Align.CENTER)
            box.pack_start(icon, False, False, 0)

            info_label = Gtk.Label(label=item.get("preview", _("Files")), xalign=0)
            info_label.set_valign(Gtk.Align.CENTER)
            info_label.set_ellipsize(3)  # EllipsizeMode.END
            box.pack_start(info_label, True, True, 0)

        else:  # text
            icon = Gtk.Image.new_from_icon_name("edit-paste-symbolic", Gtk.IconSize.BUTTON)
            icon.set_valign(Gtk.Align.START)
            full_text = item.get("data", "").strip()

            raw_lines = full_text.splitlines()
            preview_lines = []
            for line in raw_lines:
                if len(line) > 70:
                    chunks = [
                        line[i:i + 70]
                        for i in range(0, len(line), 70)
                    ]
                    preview_lines.extend(chunks)
                else:
                    preview_lines.append(line)

                if len(preview_lines) >= 3:
                    break

            preview_lines = preview_lines[:3]
            preview_text = "\n".join(preview_lines)
            needs_expand = len(raw_lines) > 3 or len(full_text) > 210

            if needs_expand:
                preview_text = preview_text.rstrip() + "..."

            info_label = Gtk.Label(label=preview_text, xalign=0)
            info_label.set_valign(Gtk.Align.START)
            info_label.set_line_wrap(True)
            info_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            info_label.set_max_width_chars(50)

            text_box = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=6,
            )
            text_box.set_hexpand(True)
            text_box.pack_start(icon, False, False, 0)
            text_box.pack_start(info_label, True, True, 0)

            if needs_expand:
                expand_button = Gtk.Button.new_from_icon_name(
                    "pan-down-symbolic",
                    Gtk.IconSize.BUTTON,
                )
                expand_button.set_relief(Gtk.ReliefStyle.NONE)
                expand_button.set_valign(Gtk.Align.START)
                expand_button.set_can_focus(False)
                expand_button.set_tooltip_text(_("Show full content"))
                expand_button.expanded = False
                expand_button.connect(
                    "clicked",
                    self._toggle_text_expand,
                    info_label,
                    full_text,
                    preview_text,
                )
                text_box.pack_end(expand_button, False, False, 0)

            box.pack_start(text_box, True, True, 0)

        # 2. Action buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_box.set_valign(Gtk.Align.START)

        # Pin button (view-pin-symbolic)
        is_pinned = item.get("pinned", False)
        btn_pin = Gtk.Button.new_from_icon_name("view-pin-symbolic", Gtk.IconSize.BUTTON)
        btn_pin.set_relief(Gtk.ReliefStyle.NONE)
        
        if not is_pinned:
            btn_pin.set_opacity(0.30)  # Translucent / gray when not pinned
        else:
            btn_pin.set_opacity(1.0)   # Bright / full white when pinned

        btn_pin.set_tooltip_text(_("Unpin") if is_pinned else _("Pin to top"))
        btn_pin.connect("clicked", lambda b, i_id=item["id"]: self._on_toggle_pin(i_id))
        btn_box.pack_start(btn_pin, False, False, 0)

        btn_copy = Gtk.Button.new_from_icon_name("edit-copy-symbolic", Gtk.IconSize.BUTTON)
        btn_copy.set_relief(Gtk.ReliefStyle.NONE)
        btn_copy.set_tooltip_text(_("Copy to clipboard"))
        btn_copy.connect("clicked", lambda b, i=item: self._on_copy_item(i))
        btn_box.pack_start(btn_copy, False, False, 0)

        btn_delete = Gtk.Button.new_from_icon_name("user-trash-symbolic", Gtk.IconSize.BUTTON)
        btn_delete.set_relief(Gtk.ReliefStyle.NONE)
        btn_delete.set_tooltip_text(_("Delete"))
        btn_delete.connect("clicked", lambda b, i_id=item["id"]: self._on_delete_item(i_id))
        btn_box.pack_start(btn_delete, False, False, 0)

        box.pack_end(btn_box, False, False, 0)

        list_row.add(box)
        return list_row

    def _toggle_text_expand(self, button, label, full_text, preview_text):
        """Expand or collapse a long text preview in the main window."""
        if not getattr(button, "expanded", False):
            button.expanded = True
            label.set_text(full_text)
            button.set_image(
                Gtk.Image.new_from_icon_name(
                    "pan-up-symbolic",
                    Gtk.IconSize.BUTTON,
                )
            )
            button.set_tooltip_text(_("Collapse content"))
        else:
            button.expanded = False
            label.set_text(preview_text)
            button.set_image(
                Gtk.Image.new_from_icon_name(
                    "pan-down-symbolic",
                    Gtk.IconSize.BUTTON,
                )
            )
            button.set_tooltip_text(_("Show full content"))

    def _on_search_changed(self, entry):
        self.refresh_list()

    def _on_filter_changed(self, button, filter_type):
        if button.get_active():
            self.current_filter_type = filter_type
            self.refresh_list()

    def _on_toggle_pin(self, item_id):
        self.clipboard_manager.toggle_pin_item(item_id)

    def _on_copy_item(self, item):
        """Copy an item and scroll the history back to the top."""
        self.clipboard_manager.copy_item_to_system(item)

        vadjustment = self.scrolled.get_vadjustment()
        vadjustment.set_value(vadjustment.get_lower())

    def _on_delete_item(self, item_id):
        self.clipboard_manager.remove_item(item_id)

    def _on_quit_clicked(self, btn):
        app = self.get_application()
        if app:
            app.quit_app()