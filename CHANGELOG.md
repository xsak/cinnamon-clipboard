# Changelog

## [Unreleased]

### Changed
- The Debian package is now built from the standard `debian/` directory with `dpkg-buildpackage`; `build_deb.sh` is a thin wrapper and checks that `_version.py` matches `debian/changelog`.
- The package is now maintained by Akos Keresztes; update checks, the About dialog and the README point to `xsak/cinnamon-clipboard`.
- The update checker recognizes beta and release-candidate versions in both `1.3.4-beta1` and `1.3.4~beta1` form.
- The launcher and the autostart entry now share a single `.desktop` file, which also adds the Hungarian launcher name.
- RPM packaging was removed; Linux Mint is the supported target.

### Fixed
- The clipboard history database, its folder and saved images are now readable only by the current user.
- Copying files from the history no longer freezes the application or drops paste requests while waiting for the X server.

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