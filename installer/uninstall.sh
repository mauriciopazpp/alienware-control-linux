#!/bin/sh
# Alienware Control uninstaller: sudo installer/uninstall.sh
# Your settings in ~/.config/alienware-control are kept; delete that folder to remove them too.
set -eu

PREFIX=/usr/local
APP_ID=io.github.alienware_control.AlienwareControl

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run with sudo: sudo installer/uninstall.sh" >&2
  exit 1
fi

pkill -f "$PREFIX/share/alienware-control/diskwatch.py" 2>/dev/null || true
rm -rf "$PREFIX/share/alienware-control"
rm -f "$PREFIX/bin/alienware-control" \
      "$PREFIX/share/applications/$APP_ID.desktop" \
      "$PREFIX/share/icons/hicolor/scalable/apps/alienware-control.svg" \
      "$PREFIX/libexec/alienware-control-read" \
      "$PREFIX/libexec/alienware-control-write" \
      /usr/share/polkit-1/actions/io.github.alienware_control.policy \
      /etc/udev/rules.d/70-alienware-control.rules \
      /etc/udev/rules.d/81-alienware-control-gpu-sleep.rules
command -v udevadm >/dev/null 2>&1 && udevadm control --reload-rules || true

# Login entries live in each user's home; remove the two we created (fixed names only).
getent passwd | cut -d: -f6 | sort -u | while IFS= read -r home; do
  [ -d "$home/.config/autostart" ] || continue
  rm -f "$home/.config/autostart/alienware-control-lights.desktop" \
        "$home/.config/autostart/alienware-control-diskwatch.desktop"
done

echo "Alienware Control removed. Settings kept in ~/.config/alienware-control."
