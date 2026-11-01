try:
    import setproctitle

    setproctitle.setproctitle("cinnamon-clipboard")
except ImportError:
    pass

import gi

import logging

logger = logging.getLogger(__name__)

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("Keybinder", "3.0")
    from gi.repository import Keybinder
    KEYBINDER_AVAILABLE = True
except Exception:
    KEYBINDER_AVAILABLE = False

from gi.repository import GLib, Gtk, Gio

from .i18n import _
from ._version import __version__
from .update_checker import REPOSITORY_URL, check_for_updates
from .installation import PACKAGE_MANAGED
from pathlib import Path

from .core.settings import SettingsManager
from .ui.welcome_window import WelcomeWindow

from .ui.about_window import AboutWindow
from .ui.preferences_window import PreferencesWindow
from .core.clipboard import ClipboardManager
from .ui.main_window import MainWindow
from .ui.menu_window import QuickMenuWindow
from .ui.tray import TrayIcon


class ClipboardApp(Gtk.Application):
    """Main Cinnamon Clipboard application in GTK3."""

    def __init__(self):
        super().__init__(
            application_id="com.github.vaider13.CinnamonClipboard"
        )
        self.clipboard_manager = None
        self.tray_icon = None
        self.main_window = None
        self.quick_menu = None
        self.current_shortcut = None
        self._keybinder_initialized = False
        self._automatic_update_check_started = False
        self.preferences_window = None
        self.about_window = None
        self.welcome_window = None
        self.welcome_settings = None
        self._welcome_completed = False
        self._application_held = False

    def open_main_window(self):
        """Open the main window or bring it to the front."""
        if self.main_window is None:
            self.main_window = MainWindow(self.clipboard_manager)
            self.main_window.set_application(self)
            self.main_window.set_wmclass(
                "cinnamon-clipboard", "CinnamonClipboard"
            )
            self.main_window.connect("destroy", self._on_main_window_destroyed)

        self.main_window.show_all()
        self.main_window.present()

    def open_about(self, parent=None):
        """Open the About dialog or bring the existing one to the front."""
        if self.about_window is None:
            self.about_window = AboutWindow(parent=parent)
            self.about_window.set_application(self)
            self.about_window.connect(
                "destroy", self._on_about_window_destroyed
            )

        if parent is not None:
            self.about_window.set_transient_for(parent)

        self.about_window.show_all()
        self.about_window.present()


    def _on_about_window_destroyed(self, widget):
        self.about_window = None

    def open_preferences(self, parent=None):
        """Open the preferences window or bring the existing one to the front."""
        if self.preferences_window is None:
            self.preferences_window = PreferencesWindow(
                self.clipboard_manager.settings,
                self.clipboard_manager,
                on_shortcut_changed_callback=self.update_global_shortcut,
                app=self,
            )
            self.preferences_window.set_application(self)
            self.preferences_window.connect(
                "destroy", self._on_preferences_window_destroyed
            )

        if parent is not None:
            self.preferences_window.set_transient_for(parent)

        self.preferences_window.show_all()
        self.preferences_window.present()

    def _on_preferences_window_destroyed(self, widget):
        self.preferences_window = None

    def _on_main_window_destroyed(self, widget):
        self.main_window = None

    def quit_app(self):
        """Fully close the application and release the service."""
        for window in (
            self.about_window,
            self.preferences_window,
            self.quick_menu,
            self.main_window,
        ):
            if window is not None:
                window.destroy()

        self.release()
        self.quit()

    def restart_app(self):
        """Restart the current process using the same Python environment."""
        import os
        import sys

        command = [
            sys.executable,
            "-m",
            "cinnamon_clipboard.app",
            *sys.argv[1:],
        ]

        try:
            os.execv(sys.executable, command)
        except OSError:
            logger.exception("Failed to restart Cinnamon Clipboard")
            self.quit_app()

    def update_global_shortcut(self, shortcut_str):
        """Update the registered global shortcut when the user changes it in preferences."""
        self._setup_global_shortcut(shortcut_str)

    def _setup_global_shortcut(self, shortcut_str):
        """Register or update the global keyboard shortcut with Keybinder safely."""
        if not KEYBINDER_AVAILABLE:
            logger.warning("gir1.2-keybinder-3.0 is not installed. Global shortcut disabled.")
            return

        if not self._keybinder_initialized:
            try:
                Keybinder.init()
                Keybinder.set_use_cooked_accelerators(False)
                self._keybinder_initialized = True
            except Exception as e:
                logger.error("Failed to initialize Keybinder: %s", e)
                return

        # Avoid re-registering if it is exactly the same combination
        if self.current_shortcut == shortcut_str and shortcut_str is not None:
            return

        # Unbind the previous shortcut safely
        if self.current_shortcut:
            try:
                Keybinder.unbind(self.current_shortcut)
            except Exception:
                pass
            self.current_shortcut = None

        if not shortcut_str:
            return

        try:
            success = Keybinder.bind(shortcut_str, self._on_shortcut_triggered, None)
            if success:
                self.current_shortcut = shortcut_str
                logger.info(
                    "Global shortcut registered successfully: %s",
                    shortcut_str,
                )
            else:
                logger.warning(
                    "Failed to register global shortcut: %s",
                    shortcut_str,
                )
        except Exception as e:
            logger.error("Failed to bind shortcut %s: %s", shortcut_str, e)

    def _on_shortcut_triggered(self, keystring, user_data):
        """Callback executed when the global key combination is pressed."""
        logger.debug("Global shortcut triggered: %s", keystring)
        if self.quick_menu:
            GLib.idle_add(self.quick_menu.toggle_window)

    def do_startup(self):
        Gtk.Application.do_startup(self)

        action = Gio.SimpleAction.new(
            "view-release",
            GLib.VariantType.new("s"),
        )
        action.connect("activate", self._on_view_release)
        self.add_action(action)

    def _on_view_release(self, action, parameter):
        import webbrowser

        url = parameter.get_string()
        if url.startswith(REPOSITORY_URL):
            webbrowser.open(url)

    def do_activate(self):
        # Keep the process alive in the background
        if not self._application_held:
            self.hold()
            self._application_held = True


        # Show the welcome wizard on first run, before creating ClipboardManager.
        if self.clipboard_manager is None and not self._welcome_completed:
            config_path = (
                Path.home()
                / ".config"
                / "cinnamon-clipboard"
                / "config.json"
            )

            if not config_path.exists():
                if self.welcome_window is None:
                    self.welcome_settings = SettingsManager()
                    self.welcome_window = WelcomeWindow(
                        settings=self.welcome_settings,
                        on_complete=self._on_welcome_complete,
                        app=self,
                    )
                    self.welcome_window.show_all()
                return

        
        # Initialize the clipboard manager after the application is active.
        if self.clipboard_manager is None:
            try:
                self.clipboard_manager = ClipboardManager()
            except RuntimeError:
                logger.exception("Failed to initialize the clipboard manager")

                notification = Gio.Notification.new(
                    _("Temporary history could not be started")
                )
                notification.set_body(
                    _(
                        "The saved clipboard history could not be deleted. "
                        "Check file permissions and restart the application."
                    )
                )
                notification.set_icon(
                    Gio.ThemedIcon.new("cinnamon-clipboard")
                )
                self.send_notification(None, notification)

                self.release()
                self.quit()
                return

        # Show a warning if the configuration was restored automatically
        if self.clipboard_manager.settings.config_was_reset:
            dialog = Gtk.MessageDialog(
                parent=None,
                flags=0,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=_("Configuration restored"),
            )
            dialog.format_secondary_text(
                _("The configuration file contained invalid data and was reset to the default "
                  "values.")
            )
            dialog.run()
            dialog.destroy()

            self.clipboard_manager.settings.config_was_reset = False

        # 1. Tray dropdown menu
        if self.quick_menu is None:
            self.quick_menu = QuickMenuWindow(
                clipboard_manager=self.clipboard_manager,
            )
            self.quick_menu.set_application(self)

        # 2. Initialize the system tray icon if it does not exist
        if self.tray_icon is None:
            self.tray_icon = TrayIcon(
                app=self,
                clipboard_manager=self.clipboard_manager,
                menu_window=self.quick_menu,
            )

        # 3. Register the global keyboard shortcut from the configuration
        shortcut = self.clipboard_manager.settings.get("shortcut")
        self._setup_global_shortcut(shortcut)

        # 4. Start monitoring the clipboard only once
        if not getattr(self, "_clipboard_monitoring_started", False):
            self.clipboard_manager.connect_to_changes()
            self._clipboard_monitoring_started = True
        if (
            not PACKAGE_MANAGED
            and self.clipboard_manager.settings.get("check_updates")
            and not self._automatic_update_check_started
        ):
            self._automatic_update_check_started = True
            check_for_updates(self)


    def _on_welcome_complete(self, values):
        settings = self.welcome_settings

        if settings is None:
            logger.error("Welcome wizard settings are not available")
            return False

        selected_autostart = bool(values.get("autostart", False))

        # Save the selected preferences without enabling autostart yet.
        values_to_save = values.copy()
        values_to_save["autostart"] = False

        previous_settings = settings.settings.copy()
        settings.settings.update(values_to_save)

        if not settings.save():
            settings.settings = previous_settings
            logger.error("Failed to save welcome wizard settings")
            return False

        # Configure autostart only after the other settings are saved.
        try:
            autostart_result = settings.set_autostart(selected_autostart)
        except Exception:
            logger.exception("Failed to configure application autostart")
            autostart_result = False

        if autostart_result is False:
            settings.settings["autostart"] = False

            if not settings.save():
                logger.error("Failed to save the disabled autostart setting")

            dialog = Gtk.MessageDialog(
                parent=self.welcome_window,
                flags=Gtk.DialogFlags.MODAL,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.OK,
                text=_("Automatic startup could not be configured"),
            )
            dialog.format_secondary_text(
                _(
                    "Your other settings were saved. "
                    "Cinnamon Clipboard will continue without automatic startup."
                )
            )
            dialog.run()
            dialog.destroy()

        self._welcome_completed = True

        # Release the window reference before normal activation continues.
        self.welcome_window = None
        self.welcome_settings = None

        # Activate the application normally, using the existing do_activate().
        self.do_activate()

        return True


def main():
    import argparse

    parser = argparse.ArgumentParser(prog="cinnamon-clipboard")
    parser.add_argument(
        "--version",
        action="version",
        version=f"Cinnamon Clipboard {__version__}",
    )
    parser.parse_args()

    app = ClipboardApp()
    return app.run(None)


if __name__ == "__main__":
    main()