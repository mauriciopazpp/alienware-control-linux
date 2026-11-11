#!/bin/sh
# Build a .deb package for Debian, Ubuntu, Linux Mint, Zorin OS, Pop!_OS...
#   installer/build-deb.sh            ->  dist/alienware-control_<version>_all.deb
# Double-clicking the .deb opens the system's software installer.
# Needs dpkg-deb (always present on Debian-based systems). No root needed.
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"$/\1/p' "$ROOT/alienware_control/app.py")"
MAINTAINER="${MAINTAINER:-Mauricio Paz <8238958+mauriciopazpp@users.noreply.github.com>}"
HOMEPAGE="${HOMEPAGE:-https://github.com/mauriciopazpp/alienware-control-linux}"
[ -n "$VERSION" ] || { echo "could not read VERSION from app.py" >&2; exit 1; }

OUT="$ROOT/dist"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/alienware-control"

# --- files
install -d "$PKG/DEBIAN" "$PKG/usr/share/alienware-control" "$PKG/usr/bin" "$PKG/usr/libexec" \
           "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/scalable/apps" \
           "$PKG/usr/share/polkit-1/actions" "$PKG/lib/udev/rules.d" "$PKG/usr/share/doc/alienware-control"
install -m 644 "$ROOT"/alienware_control/*.py "$PKG/usr/share/alienware-control/"
cat > "$PKG/usr/bin/alienware-control" <<'EOF'
#!/bin/sh
exec /usr/bin/python3 /usr/share/alienware-control/app.py "$@"
EOF
chmod 755 "$PKG/usr/bin/alienware-control"
install -m 755 "$ROOT/helpers/alienware-control-read" "$ROOT/helpers/alienware-control-write" "$PKG/usr/libexec/"
# The package puts the helpers in /usr/libexec, so the polkit policy must point there.
sed 's#/usr/local/libexec/#/usr/libexec/#g' "$ROOT/data/io.github.alienware_control.policy" \
  > "$PKG/usr/share/polkit-1/actions/io.github.alienware_control.policy"
install -m 644 "$ROOT/data/alienware-control.desktop" \
  "$PKG/usr/share/applications/io.github.alienware_control.AlienwareControl.desktop"
install -m 644 "$ROOT/data/alienware-control.svg" "$PKG/usr/share/icons/hicolor/scalable/apps/"
install -m 644 "$ROOT/data/70-alienware-control.rules" "$PKG/lib/udev/rules.d/"
install -m 644 "$ROOT/LICENSE" "$PKG/usr/share/doc/alienware-control/copyright"
chmod 644 "$PKG/usr/share/polkit-1/actions/io.github.alienware_control.policy"

# --- metadata
SIZE="$(du -sk "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<EOF
Package: alienware-control
Version: $VERSION
Section: utils
Priority: optional
Architecture: all
Installed-Size: $SIZE
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.3), pkexec | policykit-1, udev
Recommends: power-profiles-daemon
Maintainer: $MAINTAINER
Homepage: $HOMEPAGE
Description: Alienware Control for Linux, a control panel for Alienware laptops
 Temperatures, fans, disks and battery health; RGB lighting for the keyboard,
 power button and lid logo; BIOS thermal mode, Turbo Boost and battery charging
 mode; and a low disk space alert. Tested on an Alienware m15 R7.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ] && command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules || true
  udevadm trigger --action=change --subsystem-match=hidraw || true
fi
exit 0
EOF
cat > "$PKG/DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -e
if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules || true
fi
exit 0
EOF
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/postrm"

mkdir -p "$OUT"
dpkg-deb --root-owner-group --build "$PKG" "$OUT/alienware-control_${VERSION}_all.deb"
echo "Built: $OUT/alienware-control_${VERSION}_all.deb"
