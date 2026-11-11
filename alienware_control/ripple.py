#!/usr/bin/env python3
"""Ripple effect: a ring of light spreads from every key you press, like a drop in water.

The keyboard has no built-in ripple, so this small helper draws it key by key. It sleeps
until a key is pressed, animates for about a second and goes back to sleep.

Privacy: it reads key presses from the keyboard's own lighting device (the same one the
app already uses) only to know where a ripple starts. Nothing is stored or sent anywhere.

Usage:
  ripple.py run     animate while the keyboard effect is "ripple" (started by the app / at login)
  ripple.py keys    print the keys it sees for 10 seconds (to check the key map)
"""
import fcntl
import math
import os
import select
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awkbd  # noqa: E402
import keymap  # noqa: E402
import lights  # noqa: E402

SPEED = 13.0      # key widths per second
WIDTH = 1.25      # half-width of the ring, in key widths
LIFE = 1.15       # seconds a ripple lives
FRAME = 0.045
LOCK = os.path.join(os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
                    "alienware-control", "ripple.lock")


def pressed_usages(report):
    """HID usages held down in a keyboard input report (report ID 1), else None."""
    if len(report) < 9 or report[0] != 0x01:
        return None
    usages = {0xE0 + bit for bit in range(8) if report[1] >> bit & 1}
    usages.update(u for u in report[3:9] if u > 3)
    for i, byte in enumerate(report[9:37]):  # N-key rollover bitmap
        for bit in range(8):
            if byte >> bit & 1 and i * 8 + bit > 3:
                usages.add(i * 8 + bit)
    return usages


def level(distance, age):
    """Brightness 0..1 of a key at `distance` from a ripple that started `age` seconds ago."""
    if age < 0 or age > LIFE:
        return 0.0
    ring = 1.0 - abs(distance - SPEED * age) / WIDTH
    if ring <= 0:
        return 0.0
    return ring * (1.0 - age / LIFE) ** 0.6


def run():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = open(LOCK, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0  # already running

    def load():
        state = lights.load()["keyboard"]
        return state["effect"] == "ripple", tuple(state["color"]), tuple(state["color2"])

    active, fg, bg = load()
    if not active:
        return 0
    try:
        mtime = os.stat(lights.CONFIG).st_mtime
    except OSError:
        mtime = 0
    with awkbd.Keyboard() as kbd:
        kbd.pause = 0.006
        shown = {i: bg for i in keymap.IDS}
        ripples, held = [], set()
        while True:
            ready, _, _ = select.select([kbd.fd], [], [], FRAME if ripples else 2.0)
            now = time.monotonic()
            if ready:
                usages = pressed_usages(os.read(kbd.fd, 64))
                if usages is not None:
                    for usage in usages - held:
                        light = keymap.USAGE_TO_ID.get(usage)
                        if light in keymap.POS:
                            ripples.append((keymap.POS[light], now))
                    held = usages
            if not ripples:  # idle: see whether the user changed the effect or its colours
                try:
                    m = os.stat(lights.CONFIG).st_mtime
                except OSError:
                    m = mtime
                if m != mtime:
                    mtime = m
                    active, fg, bg = load()
                    if not active:
                        return 0
                    shown = {i: bg for i in keymap.IDS}
                continue
            ripples = [r for r in ripples if now - r[1] <= LIFE][-8:]
            changed = []
            for light, (x, y) in keymap.POS.items():
                k = 0.0
                for (ox, oy), born in ripples:
                    k = max(k, level(math.hypot(x - ox, (y - oy) * 1.05), now - born))
                color = tuple(int(bg[c] + (fg[c] - bg[c]) * k) for c in range(3))
                if color != shown[light]:
                    shown[light] = color
                    changed.append((light, color))
            if changed:
                kbd.update_colors(changed)


def keys():
    with awkbd.Keyboard() as kbd:
        end, held = time.monotonic() + 10, set()
        print("press some keys (10 s)...", flush=True)
        while time.monotonic() < end:
            if select.select([kbd.fd], [], [], 0.5)[0]:
                usages = pressed_usages(os.read(kbd.fd, 64))
                if usages is None:
                    continue
                for usage in sorted(usages - held):
                    print(f"usage {usage:#04x} -> light {keymap.USAGE_TO_ID.get(usage)}", flush=True)
                held = usages
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "run":
        sys.exit(run())
    if cmd == "keys":
        sys.exit(keys())
    print(__doc__)
    sys.exit(1)
