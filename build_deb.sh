#!/bin/bash
set -e

PACKAGE_NAME="cinnamon-clipboard"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/cinnamon_clipboard/_version.py)

if [[ -z "$VERSION" ]]; then
    echo "Error: could not read the version from _version.py" >&2
    exit 1
fi

ARCH="all"
BUILD_DIR="build_deb"
LOCALE_DIR="locale"
MO_FILENAME="cinnamon-clipboard.mo"
PO_FILENAME="cinnamon-clipboard.po"

echo "=== Building Debian package for $PACKAGE_NAME v$VERSION ==="

# 1. Clean previous build artifacts
rm -rf "$BUILD_DIR"
rm -f "${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

# 2. Compile all available translation catalogs
echo "[+] Compiling gettext translations..."

while IFS= read -r -d '' po_file; do
    mo_file="${po_file%.po}.mo"

    msgfmt "$po_file" -o "$mo_file"
    echo "    Compiled: $mo_file"
done < <(find "$LOCALE_DIR" -type f -name "$PO_FILENAME" -print0)

# 3. Create the package directory structure
echo "[+] Creating directory structure..."

mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/lib/python3/dist-packages/cinnamon_clipboard"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/icons/hicolor/512x512/apps"

# 4. Create DEBIAN/control
echo "[+] Generating DEBIAN/control metadata..."

cat <<EOF > "$BUILD_DIR/DEBIAN/control"
Package: $PACKAGE_NAME
Version: $VERSION
Architecture: $ARCH
Maintainer: Pablo / Vaider13 <vaider13@github.com>
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-xapp-1.0, gir1.2-keybinder-3.0, python3-setproctitle, python3-xlib
Section: utils
Priority: optional
Description: Clipboard manager for Cinnamon and Linux desktops
 Simple, lightweight, and responsive clipboard manager with GTK3, SQLite persistence,
 shortcut support, and privacy filter for password managers.
EOF

# 5. Create the executable
echo "[+] Creating executable at /usr/bin/cinnamon-clipboard..."

cat <<'EOF' > "$BUILD_DIR/usr/bin/cinnamon-clipboard"
#!/bin/sh
exec python3 -m cinnamon_clipboard.app "$@"
EOF

chmod +x "$BUILD_DIR/usr/bin/cinnamon-clipboard"

# 6. Copy the Python source code
echo "[+] Copying application source code..."

cp -a src/cinnamon_clipboard/. \
    "$BUILD_DIR/usr/lib/python3/dist-packages/cinnamon_clipboard/"

find "$BUILD_DIR/usr/lib/python3/dist-packages/cinnamon_clipboard/" \
    -type d -name __pycache__ -prune -exec rm -rf {} +

find "$BUILD_DIR/usr/lib/python3/dist-packages/cinnamon_clipboard/" \
    -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

# 7. Copy the application icon
if [ -f "data/icons/cinnamon-clipboard.png" ]; then
    echo "[+] Copying application icon..."

    cp data/icons/cinnamon-clipboard.png \
        "$BUILD_DIR/usr/share/icons/hicolor/512x512/apps/cinnamon-clipboard.png"
else
    echo "[!] Warning: application icon not found."
fi

# 8. Copy all compiled translation catalogs
echo "[+] Copying translations..."

while IFS= read -r -d '' mo_file; do
    relative_path="${mo_file#"$LOCALE_DIR"/}"
    lang="${relative_path%%/*}"
    dest="$BUILD_DIR/usr/share/locale/$lang/LC_MESSAGES"

    mkdir -p "$dest"
    cp "$mo_file" "$dest/$MO_FILENAME"

    echo "    Copied: $lang"
done < <(find "$LOCALE_DIR" -type f -name "$MO_FILENAME" -print0)

# 9. Install the .desktop launcher
echo "[+] Installing .desktop launcher..."

install -m 644 src/cinnamon_clipboard/data/cinnamon-clipboard.desktop \
    "$BUILD_DIR/usr/share/applications/cinnamon-clipboard.desktop"

# 10. Build the package
echo "[+] Building package with dpkg-deb..."

dpkg-deb \
    --build \
    --root-owner-group \
    "$BUILD_DIR" \
    "${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"

echo
echo "=== Package created successfully! ==="
echo "${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"