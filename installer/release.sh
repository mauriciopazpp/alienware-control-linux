#!/bin/sh
# Publish a GitHub release with the .deb attached.
#   installer/release.sh
# Reads VERSION from alienware_control/app.py, builds dist/alienware-control_<version>_all.deb,
# tags v<version> and creates the release with the GitHub CLI (gh).
# Bump VERSION in app.py and commit before running it for a new release.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' alienware_control/app.py)"
TAG="v$VERSION"
DEB="dist/alienware-control_${VERSION}_all.deb"

command -v gh >/dev/null 2>&1 || { echo "The GitHub CLI (gh) is needed: https://cli.github.com" >&2; exit 1; }
[ -n "$VERSION" ] || { echo "Could not read VERSION from app.py" >&2; exit 1; }
if [ -n "$(git status --porcelain)" ]; then
  echo "Commit your changes first; the release must match the code on GitHub." >&2
  exit 1
fi
git fetch -q origin
if [ "$(git rev-parse HEAD)" != "$(git rev-parse '@{u}')" ]; then
  echo "Push your commits first (git push)." >&2
  exit 1
fi
if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release $TAG already exists. Bump VERSION in alienware_control/app.py for a new one." >&2
  exit 1
fi

sh installer/build-deb.sh

NOTES="$(mktemp)"
trap 'rm -f "$NOTES"' EXIT
cat > "$NOTES" <<EOF
## Install

**Debian, Ubuntu, Linux Mint, Zorin OS, Pop!_OS:** download \`alienware-control_${VERSION}_all.deb\` below and double-click it.

**Any other distribution:** download the source code, then run \`/usr/bin/python3 installer/installer.py\`.

Needs GTK 4 and libadwaita 1.3+. Tested on an Alienware m15 R7 running Zorin OS 17.3. See the README for details and for reporting other models.
EOF

git tag -a "$TAG" -m "Alienware Control $VERSION"
git push -q origin "$TAG"
gh release create "$TAG" "$DEB" --title "Alienware Control $VERSION" --notes-file "$NOTES" --verify-tag
echo "Published: $(gh release view "$TAG" --json url --jq .url)"
