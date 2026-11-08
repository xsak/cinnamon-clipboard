import json
import os
import tempfile
import logging
import stat
from pathlib import Path

from .database import ensure_private_dir

logger = logging.getLogger(__name__)

# Tray menu width presets in pixels: Normal, Wide, Extra wide.
MENU_WIDTHS = (340, 440, 560)

# Shared launcher entry; also installed to /usr/share/applications by the packaging.
DESKTOP_FILE = (
    Path(__file__).resolve().parent.parent / "data" / "cinnamon-clipboard.desktop"
)


class SettingsManager:
    """Handles persistence of application settings in JSON format."""

    DEFAULTS = {
        "max_history": 50,
        "autostart": False,
        "save_images": True,
        "save_files": True,
        "enable_history": True,
        "focus_first_item": True,
        "paste_on_select": True,
        "shortcut": "<Ctrl><Alt>v",
        "check_updates": True,
        "history_mode": "persistent",
        "menu_width": MENU_WIDTHS[0],
        # WM_CLASS names of applications whose copies are never recorded.
        "ignored_apps": ["keepassxc", "keepass2", "bitwarden", "1password", "enpass", "seahorse"],
    }

    def __init__(self):
        config_dir = Path.home() / ".config" / "cinnamon-clipboard"
        ensure_private_dir(config_dir)
        self.config_path = config_dir / "config.json"
        self.settings = self.DEFAULTS.copy()
        self.config_was_reset = False
        self.load()

    def load(self):
        """Load and validate the configuration, restoring default values if it is invalid."""
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, dict):
                raise ValueError("The configuration does not contain a valid JSON object.")

            valid = True

            if "max_history" in data and data["max_history"] not in (10, 25, 50, 75, 100):
                valid = False

            if "history_mode" in data and data["history_mode"] not in ("persistent", "temporary"):
                valid = False

            # A bad width only falls back to the default width; it does not
            # reset the other settings.
            if "menu_width" in data and (
                isinstance(data["menu_width"], bool)
                or data["menu_width"] not in MENU_WIDTHS
            ):
                logger.warning("Ignoring invalid menu_width: %r", data["menu_width"])
                del data["menu_width"]

            for key in (
                "autostart",
                "save_images",
                "save_files",
                "enable_history",
                "focus_first_item",
                "paste_on_select",
                "check_updates",
            ):
                if key in data and not isinstance(data[key], bool):
                    valid = False

            if "shortcut" in data and not isinstance(data["shortcut"], str):
                valid = False

            if "ignored_apps" in data and not (
                isinstance(data["ignored_apps"], list)
                and all(isinstance(name, str) for name in data["ignored_apps"])
            ):
                valid = False

            if not valid:
                raise ValueError("One or more configuration values are invalid.")

            self.settings.update(data)

        except Exception as e:

            self.settings = self.DEFAULTS.copy()
            self.config_was_reset = True
            self.save()


    def save(self):
        """Save settings atomically to the JSON file."""
        temp_path = None

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.config_path.parent,
                prefix=".config.",
                suffix=".tmp",
                delete=False,
            ) as f:
                temp_path = f.name
                json.dump(self.settings, f, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, self.config_path)
            return True

        except (OSError, TypeError, ValueError) as e:
            logger.error("Failed to save config.json: %s", e)
            return False

        finally:
            if temp_path is not None and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    logger.warning(
                        "Could not remove temporary configuration file: %s",
                        temp_path,
                    )

    @staticmethod
    def parse_app_list(text):
        """Turn a comma-separated list of WM_CLASS names into a clean, lower-case list."""
        names = []
        for name in text.split(","):
            name = name.strip().lower()
            if name and name not in names:
                names.append(name)
        return names

    def get(self, key):
        return self.settings.get(key, self.DEFAULTS.get(key))


    def set(self, key, value):
        old_value = self.settings.get(key)
        had_old_value = key in self.settings

        self.settings[key] = value

        if not self.save():
            if had_old_value:
                self.settings[key] = old_value
            else:
                self.settings.pop(key, None)

            return False

        return True

   
    
    def snapshot_autostart_file(self):
        """Capture the current autostart file state."""
        path = (
            Path.home()
            / ".config"
            / "autostart"
            / "cinnamon-clipboard.desktop"
        )

        if path.is_symlink():
            raise OSError(f"Refusing to modify symbolic link: {path}")

        if not path.exists():
            return path, False, None, None

        if not path.is_file():
            raise OSError(f"Expected a regular file: {path}")

        return (
            path,
            True,
            path.read_bytes(),
            stat.S_IMODE(path.stat().st_mode),
        )

    @staticmethod
    def restore_autostart_file(snapshot):
        """Restore the previous autostart file state."""
        path, existed, content, permissions = snapshot
        temp_path = None

        try:
            if not existed:
                if os.path.lexists(path):
                    path.unlink()
                return True

            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=".cinnamon-clipboard.",
                suffix=".tmp",
                delete=False,
            ) as f:
                temp_path = Path(f.name)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            temp_path.chmod(permissions)
            os.replace(temp_path, path)
            temp_path = None
            return True

        except OSError:
            logger.exception("Failed to restore autostart file %s", path)
            return False

        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "Could not remove temporary autostart file %s",
                        temp_path,
                    )

    def set_autostart(self, enable):
        """Update autostart file and configuration safely."""
        try:
            snapshot = self.snapshot_autostart_file()
        except OSError:
            logger.exception("Could not inspect autostart file")
            return False

        autostart_file = snapshot[0]
        existed = snapshot[1]
        temp_path = None

        try:
            if enable:
                autostart_file.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                content = (
                    DESKTOP_FILE.read_text(encoding="utf-8").rstrip("\n")
                    + "\nX-GNOME-Autostart-enabled=true\n"
                )

                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=autostart_file.parent,
                    prefix=".cinnamon-clipboard.",
                    suffix=".tmp",
                    delete=False,
                ) as f:
                    temp_path = Path(f.name)
                    f.write(content)
                    f.flush()
                    os.fsync(f.fileno())

                temp_path.chmod(
                    snapshot[3] if existed else 0o644
                )
                os.replace(temp_path, autostart_file)
                temp_path = None

            elif existed:
                autostart_file.unlink()

        except OSError:
            logger.exception("Failed to update autostart file")

            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "Could not remove temporary autostart file %s",
                        temp_path,
                    )

            if not self.restore_autostart_file(snapshot):
                logger.critical(
                    "Autostart file may be inconsistent after update failure"
                )
            return False

        if not self.set("autostart", enable):
            if not self.restore_autostart_file(snapshot):
                logger.critical(
                    "Autostart file may be inconsistent after config save failure"
                )
            return False

        return True
