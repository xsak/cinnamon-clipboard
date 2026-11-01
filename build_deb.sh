#!/bin/bash
# Build the Debian package from debian/ and place the .deb in the project root.
# Extra arguments are passed to dpkg-buildpackage.
set -euo pipefail

cd "$(dirname "$0")"

PACKAGE_NAME="cinnamon-clipboard"

APP_VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' src/cinnamon_clipboard/_version.py)
DEB_VERSION=$(dpkg-parsechangelog -S Version)

if [[ -z "$APP_VERSION" ]]; then
    echo "Error: could not read the version from _version.py" >&2
    exit 1
fi

# The package is native, so debian/changelog must carry the same version as the app.
if [[ "$APP_VERSION" != "$DEB_VERSION" ]]; then
    echo "Error: _version.py ($APP_VERSION) does not match debian/changelog ($DEB_VERSION)." >&2
    echo "Add a debian/changelog entry for $APP_VERSION (for example with: dch -v $APP_VERSION)." >&2
    exit 1
fi

echo "=== Building Debian package for $PACKAGE_NAME v$DEB_VERSION ==="

dpkg-buildpackage --build=binary --no-sign "$@"

# dpkg-buildpackage writes its results to the parent directory.
BASENAME="${PACKAGE_NAME}_${DEB_VERSION}"
mv "../${BASENAME}_all.deb" .
rm -f "../${BASENAME}_"*.buildinfo "../${BASENAME}_"*.changes

echo
echo "=== Package created successfully! ==="
echo "${BASENAME}_all.deb"
