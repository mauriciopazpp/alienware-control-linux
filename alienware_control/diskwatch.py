#!/usr/bin/env python3
"""Low disk space watcher: sends a desktop notification when a Linux filesystem gets full.

When the Linux disk fills up, apps crash or lose data, updates fail half-way and the
desktop may not even start. This watcher checks every 10 minutes and warns early.

Usage:
  diskwatch.py run     keep watching (started at login while the alert is enabled)
  diskwatch.py check   check once and print the result
  diskwatch.py test    send a sample notification

Notifications go through the standard org.freedesktop.Notifications D-Bus service,
so they work on GNOME, KDE, XFCE, Cinnamon, etc. without extra packages.
"""
import fcntl
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import i18n  # noqa: E402
import config  # noqa: E402
import sensors  # noqa: E402
from i18n import _  # noqa: E402

from gi.repository import Gio, GLib  # noqa: E402

LINUX_FS = {"ext2", "ext3", "ext4", "btrfs", "xfs", "f2fs", "jfs", "reiserfs", "bcachefs", "zfs"}
INTERVAL = 600
FIRST_CHECK = 60
REPEAT_AFTER = 24 * 3600
CRITICAL = 0.98
STATE_DIR = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")), "alienware-control")
STATE = os.path.join(STATE_DIR, "diskwatch.json")
LOCK = os.path.join(STATE_DIR, "diskwatch.lock")


def linux_filesystems():
    """[(mount, used_fraction, free_bytes)] for mounted Linux filesystems."""
    result = []
    for disk in sensors.disks():
        for p in disk["parts"]:
            if p["mount"] and p["fstype"] in LINUX_FS and p["total"]:
                result.append((p["mount"], p["used"] / p["total"], p["total"] - p["used"]))
    return result


def notify(summary, body, urgency=1):
    """Send a desktop notification; returns False when no notification service is available."""
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        bus.call_sync(
            "org.freedesktop.Notifications", "/org/freedesktop/Notifications",
            "org.freedesktop.Notifications", "Notify",
            GLib.Variant("(susssasa{sv}i)", (
                "Alienware Control", 0, "drive-harddisk-symbolic", summary, body, [],
                {"urgency": GLib.Variant("y", urgency)}, -1)),
            None, Gio.DBusCallFlags.NONE, 5000, None)
        return True
    except GLib.Error:
        return False


def message(mount, frac, free):
    pct = f"{frac * 100:.0f}"
    if mount == "/":
        summary = _("The system disk is {pct}% full").format(pct=pct)
    else:
        summary = _("The disk at {mount} is {pct}% full").format(mount=mount, pct=pct)
    body = _("Only {free} left. When the Linux disk fills up, apps can crash or lose data, updates can fail "
             "and the desktop may not start. Free some space soon (Trash, Downloads, old Docker images, "
             "package caches).").format(free=sensors.human(free))
    return summary, body


def _load_state():
    try:
        with open(STATE) as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    # Keep only well-formed entries, so a damaged file can never crash the watcher.
    return {m: e for m, e in data.items()
            if isinstance(e, dict) and isinstance(e.get("last"), (int, float)) and isinstance(e.get("critical"), bool)}


def _save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f)
    os.replace(tmp, STATE)


def check_once(threshold, state, now=None):
    """Notify about filesystems above `threshold` (0..1). Returns the list of full mounts."""
    now = now or time.time()
    full = []
    for mount, frac, free in linux_filesystems():
        entry = state.get(mount, {})
        if frac < threshold - 0.02:  # hysteresis: forget once it is clearly below again
            state.pop(mount, None)
            continue
        if frac < threshold:
            continue
        full.append(mount)
        was_critical = entry.get("critical", False)
        is_critical = frac >= CRITICAL
        due = now - entry.get("last", 0) >= REPEAT_AFTER or (is_critical and not was_critical)
        if due:
            summary, body = message(mount, frac, free)
            if notify(summary, body, urgency=2 if is_critical else 1):
                state[mount] = {"last": now, "critical": is_critical}
    return full


def run():
    os.makedirs(STATE_DIR, exist_ok=True)
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0  # another watcher is already running
    time.sleep(FIRST_CHECK)
    while True:
        cfg = config.load_config()
        if not cfg["disk_alert"]:
            return 0
        i18n.setup(cfg["language"])
        state = _load_state()
        check_once(cfg["disk_threshold"] / 100, state)
        _save_state(state)
        time.sleep(INTERVAL)


def main(argv):
    cmd = argv[0] if argv else ""
    i18n.setup(config.load_config()["language"])
    if cmd == "run":
        return run()
    if cmd == "check":
        threshold = config.load_config()["disk_threshold"]
        for mount, frac, free in linux_filesystems():
            flag = "FULL" if frac * 100 >= threshold else "ok"
            print(f"{flag:4}  {mount:20} {frac * 100:5.1f}%  {sensors.human(free)} free")
        return 0
    if cmd == "test":
        ok = notify(*message("/", 0.93, 40 * 1024 ** 3))
        print("sent" if ok else "no notification service on this session")
        return 0 if ok else 1
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
