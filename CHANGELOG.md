# Changelog

## [Unreleased]

### Added
- Preferences → System and Shortcut has a "Tray menu width" setting: Normal (340 px, as before), Wide (440 px) or Extra wide (560 px). An invalid width in `config.json` falls back to Normal without resetting the other settings.

### Changed
- The quick menu list is a bit shorter: it can use up to 40% of the screen height (about 10 one-line items on a 1200 px screen) instead of half of it.
- Text previews in the quick menu wrap to the menu width and show at most three lines; the expand button appears only when there is more to show. File names use the full width before they are shortened.

### Fixed
- Long lines in quick menu previews are no longer broken in the middle of words.
- The quick menu is centred on the panel icon using its real width.

## [1.3.4] - 2026-11-03

### Added
- Ignored applications: copies made in listed applications are never recorded. The list is pre-filled with common password managers and can be edited in Preferences.
- A pause button in the quick menu and the main window turns history recording off and on. While paused, the main window shows a notice with a Resume button.
- The welcome wizard asks whether to check for updates at startup; the README documents what the update check sends.

### Changed
- The Debian package is now built from the standard `debian/` directory with `dpkg-buildpackage`; `build_deb.sh` is a thin wrapper and checks that `_version.py` matches `debian/changelog`.
- The package is now maintained by Akos Keresztes; update checks, the About dialog and the README point to `xsak/cinnamon-clipboard`.
- "Clear history" moved from the quick menu and the main window to Preferences → History and Privacy, and now asks for confirmation (Cancel is the default).
- The quick menu shows more items: the list can use up to half of the screen height (about 12 items on a 1200 px screen) instead of at most 460 px (7 items).
- Preferences shows the history mode as a single row with a Persistent | Temporary switch; the selected mode is described below the title.
- The update checker recognizes beta and release-candidate versions in both `1.3.4-beta1` and `1.3.4~beta1` form.
- The launcher and the autostart entry now share a single `.desktop` file, which also adds the Hungarian launcher name.
- RPM packaging was removed; Linux Mint is the supported target.

### Fixed
- The clipboard history database, its folder and saved images are now readable only by the current user.
- Copying files from the history no longer freezes the application or drops paste requests while waiting for the X server.
- "Paste on select" now pastes only into the window that was active when the quick menu opened. If focus does not return to it, the item is just copied.
- Deleted history items are always overwritten in the database file, whatever SQLite build is used.
- Images saved by older versions and the configuration folder are now readable only by the current user.
- Private folders are no longer changed through a symbolic link.
- The release workflow pins `actions/checkout` to a commit and no longer keeps the token in the checkout.
- Switching from temporary to persistent history no longer deletes the history.
- With "Focus first item when opening menu" turned off, the quick menu still keeps the first item selected, so Enter picks it.
- The quick menu shows a translated placeholder for images that cannot be displayed.
- All new text is translated into every supported language.

## [1.3.3] - 2026-11-01

### Added
- Automatically build and attach the Debian package to published GitHub Releases.

### Changed
- Updated the Hungarian translation.

## [1.3.2] - 2026-10-31

### Added
- Added info buttons to explain persistent and temporary history modes without cluttering the Preferences window.

### Fixed
- Fixed the history-mode info popovers so their descriptions are visible and readable.
- Correctly recognize release-candidate versions when checking for updates.

## [1.3.1] - 2026-10-30

### Fixed
- Updated and synchronized translations across all supported languages.

### Supported languages
English, Spanish, Italian, Brazilian Portuguese, French, German, Russian, Japanese, and Hungarian.