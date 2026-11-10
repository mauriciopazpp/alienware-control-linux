#!/bin/sh
# Alienware Control installer.
#   sudo installer/install.sh              install the app, BIOS helpers and lighting permissions
#   sudo installer/install.sh --gpu-sleep  also let the NVIDIA GPU sleep when idle (see README)
# Everything goes under /usr/local (plus the polkit policy and a udev rule).
# Undo with: sudo installer/uninstall.sh
set -eu

PREFIX=/usr/local
SHARE="$PREFIX/share/alienware-control"
LIBEXEC="$PREFIX/libexec"
APP_ID=io.github.alienware_control.AlienwareControl
SRC="$(cd "$(dirname "$0")/.." && pwd)"   # project root (this script lives in installer/)
GPU_SLEEP=0

for arg in "$@"; do
  case "$arg" in
    --gpu-sleep) GPU_SLEEP=1 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo installer/install.sh" >&2
  exit 1
fi

ok() { echo "  [ok] $*"; }

if command -v dpkg-query >/dev/null 2>&1 && dpkg-query -W -f='${Status}' alienware-control 2>/dev/null | grep -q "ok installed"; then
  echo "Alienware Control is already installed as a .deb package. Update or remove it with your" >&2
  echo "package manager instead (sudo apt remove alienware-control) to avoid mixing the two." >&2
  exit 1
fi

echo "Checking dependencies"
DEPCHECK='
import gi, cairo
gi.require_version("Gtk", "4.0"); gi.require_version("Adw", "1"); gi.require_version("PangoCairo", "1.0")
gi.require_foreign("cairo")
from gi.repository import Gtk, Adw, PangoCairo
assert (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 3), "libadwaita 1.3+ needed"
'
if ! /usr/bin/python3 -c "$DEPCHECK" 2>/dev/null; then
  cat >&2 <<'EOF'
  Missing or too old: GTK 4, libadwaita 1.3+, pycairo or the GObject cairo bindings.
  Install them and run this again:
    Debian/Ubuntu/Mint/Zorin/Pop!_OS:  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
    Fedora:                            sudo dnf install python3-gobject python3-cairo gtk4 libadwaita
    Arch/Manjaro/EndeavourOS:          sudo pacman -S python-gobject python-cairo gtk4 libadwaita
    openSUSE:                          sudo zypper install python3-gobject python3-gobject-cairo typelib-1_0-Gtk-4_0 typelib-1_0-Adw-1
EOF
  exit 1
fi
ok "Python 3, GTK 4, libadwaita 1.3+ and cairo found"
# Image-based distros (Silverblue, Kinoite...) have a read-only /usr: stop before installing anything.
mkdir -p /usr/share/polkit-1/actions 2>/dev/null || true
if ! touch /usr/share/polkit-1/actions/.alienware-control-probe 2>/dev/null; then
  echo "  /usr/share is read-only on this system (image-based distro?). Nothing was installed." >&2
  exit 1
fi
rm -f /usr/share/polkit-1/actions/.alienware-control-probe
command -v pkexec >/dev/null 2>&1 && ok "polkit found" || echo "  [warn] pkexec not found: BIOS settings will not work (install polkit)"

echo "Installing the app to $SHARE"
install -d -m 755 "$SHARE"
install -m 644 "$SRC"/alienware_control/*.py "$SHARE"/
install -d -m 755 "$PREFIX/bin"
cat > "$PREFIX/bin/alienware-control" <<EOF
#!/bin/sh
# Always use the system Python: it is the one with the GTK bindings.
exec /usr/bin/python3 $SHARE/app.py "\$@"
EOF
chmod 755 "$PREFIX/bin/alienware-control"
install -D -m 644 "$SRC/data/alienware-control.svg" "$PREFIX/share/icons/hicolor/scalable/apps/alienware-control.svg"
install -D -m 644 "$SRC/data/alienware-control.desktop" "$PREFIX/share/applications/$APP_ID.desktop"
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -q -t "$PREFIX/share/icons/hicolor" || true
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database -q "$PREFIX/share/applications" || true
ok "app, launcher (alienware-control) and menu entry"

echo "Installing the BIOS helpers"
install -d -m 755 "$LIBEXEC"
install -o root -g root -m 755 "$SRC/helpers/alienware-control-read" "$LIBEXEC/"
install -o root -g root -m 755 "$SRC/helpers/alienware-control-write" "$LIBEXEC/"
install -D -o root -g root -m 644 "$SRC/data/io.github.alienware_control.policy" \
  /usr/share/polkit-1/actions/io.github.alienware_control.policy
ok "helpers in $LIBEXEC and polkit policy"

echo "Allowing the logged-in user to control the lights"
install -D -m 644 "$SRC/data/70-alienware-control.rules" /etc/udev/rules.d/70-alienware-control.rules
if [ "$GPU_SLEEP" -eq 1 ]; then
  install -D -m 644 "$SRC/data/81-alienware-control-gpu-sleep.rules" /etc/udev/rules.d/81-alienware-control-gpu-sleep.rules
  ok "NVIDIA GPU sleep rule"
fi
if command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload-rules
  udevadm trigger --action=change --subsystem-match=hidraw
  [ "$GPU_SLEEP" -eq 1 ] && udevadm trigger --action=add --subsystem-match=pci --attr-match=vendor=0x10de || true
fi
ok "udev rules"

echo
echo "Done. Open \"Alienware Control\" from your app menu, or run: alienware-control"
