#!/usr/bin/env python3
"""Lighting for the Alienware m15 R7: keyboard (Darfon); lid logo, power button and rear light (AW-ELC).

Map confirmed on hardware:
  keyboard      -> Darfon 0d62:dabc, keys 0..159
  rear light    -> AW-ELC 187c:0550, zones 0 and 1 (two halves that blend in the middle)
  power button  -> AW-ELC 187c:0550, zone 2
  lid logo      -> AW-ELC 187c:0550, zone 3
  zone 4 is the power button's status indicator (it starts blinking): never touched

Usage:  lights.py apply   (re-applies the saved colours; run at login)
"""
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awelc  # noqa: E402
import awkbd  # noqa: E402
import fx  # noqa: E402

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "alienware-control")
CONFIG = os.path.join(CONFIG_DIR, "lights.json")
LEGACY_CONFIG = os.path.join(CONFIG_DIR, "luzes.json")
KEYBOARD_KEYS = range(160)
ELC_ZONES = {"power": (2,), "logo": (3,), "rear": (0, 1)}
ZONES = ("keyboard", "power", "logo", "rear")
HW_EFFECTS = {"breathing": awkbd.EFFECT_BREATHING, "wave": awkbd.EFFECT_WAVE, "pulse": awkbd.EFFECT_PULSE,
              "mix": awkbd.EFFECT_MIX_PULSE, "nightrider": awkbd.EFFECT_NIGHT_RIDER}
LEGACY_EFFECTS = {"fixo": "static", "respirar": "breathing"}
SPEEDS = ("slow", "normal", "fast")

_BASE = {"color": [0, 160, 255], "color2": [138, 60, 255], "brightness": 100, "effect": "static", "speed": "normal"}
DEFAULTS = {zone: dict(_BASE) for zone in ZONES}


def _valid_color(value):
    return (isinstance(value, list) and len(value) == 3
            and all(isinstance(c, int) and 0 <= c <= 255 for c in value))


def load():
    """Saved lighting merged over the defaults; invalid values are ignored."""
    cfg = json.loads(json.dumps(DEFAULTS))
    for path in (CONFIG, LEGACY_CONFIG):
        try:
            with open(path) as f:
                saved = json.load(f)
            break
        except (OSError, ValueError):
            saved = None
    if not isinstance(saved, dict):
        return cfg
    for zone in ZONES:
        values = saved.get(zone)
        if not isinstance(values, dict):
            continue
        for key in ("color", "color2"):
            if _valid_color(values.get(key)):
                cfg[zone][key] = values[key]
        if isinstance(values.get("brightness"), int):
            cfg[zone]["brightness"] = max(0, min(100, values["brightness"]))
        effect = LEGACY_EFFECTS.get(values.get("effect"), values.get("effect"))
        if isinstance(effect, str) and fx.valid(zone, effect):
            cfg[zone]["effect"] = effect
        if values.get("speed") in SPEEDS:
            cfg[zone]["speed"] = values["speed"]
    return cfg


def has_saved():
    return os.path.exists(CONFIG) or os.path.exists(LEGACY_CONFIG)


def save(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG)


def led_color(zone, rgb):
    """What the LED can actually show: the m15 R7 power button has no blue channel."""
    return (rgb[0], rgb[1], 0) if zone == "power" else tuple(rgb)


def scaled(rgb, brightness):
    k = max(0, min(100, brightness)) / 100
    return tuple(int(round(c * k)) for c in rgb)


def apply_keyboard(state):
    with awkbd.Keyboard() as kbd:
        kbd.set_brightness(state["brightness"])  # must come first: it resets the controller
        rgb = tuple(state["color"])
        effect = HW_EFFECTS.get(state.get("effect"))
        tempo = awkbd.SPEED_TEMPOS.get(state.get("speed"), 0x07)
        if state.get("effect") == "kb_rainbow":  # wave + two-colour flag = rainbow wave
            kbd.set_effect(awkbd.EFFECT_WAVE, tempo, rgb, tuple(state["color2"]), colors=2)
        elif state.get("effect") == "kb_spectrum":
            kbd.set_effect(awkbd.EFFECT_SPECTRUM, tempo, rgb)
        elif state.get("effect") == "stars":
            kbd.set_effect(awkbd.EFFECT_LASER, 0x07, rgb)
        elif effect == awkbd.EFFECT_MIX_PULSE:
            kbd.set_effect(effect, tempo, rgb, tuple(state["color2"]), colors=2)
        elif effect is not None:
            kbd.set_effect(effect, tempo, rgb)
        else:
            kbd.set_effect(awkbd.EFFECT_EXIT, 0xFE, (0, 0, 0))
            kbd.set_colors([(k, rgb) for k in KEYBOARD_KEYS])


def elc_groups(cfg):
    """[(zones, actions)] for every AW-ELC light, colours already dimmed by brightness."""
    groups = []
    for name, zones in ELC_ZONES.items():
        st = cfg[name]
        lists = fx.elc_actions(st["effect"], led_color(name, scaled(st["color"], st["brightness"])),
                               led_color(name, scaled(st["color2"], st["brightness"])), st["speed"],
                               halves=len(zones), scale=st["brightness"] / 100,
                               stepped=name in fx.STEPPED_ZONES)
        if len(zones) > 1 and lists[0] == lists[1]:
            groups.append((zones, lists[0]))
        else:
            groups += [((zone,), actions) for zone, actions in zip(zones, lists)]
    return groups


def apply_elc(cfg):
    with awelc.Elc() as elc:
        elc.set_zone_actions(elc_groups(cfg))
        elc.set_brightness(100, [z for zones in ELC_ZONES.values() for z in zones])


def apply(cfg, parts=("keyboard", "elc")):
    """Apply to hardware; returns a list of human-readable errors (empty on success)."""
    errors = []
    if "keyboard" in parts:
        try:
            apply_keyboard(cfg["keyboard"])
        except (OSError, awkbd.KbdError) as e:
            errors.append(f"keyboard: {e}")
    if "elc" in parts:
        try:
            apply_elc(cfg)
        except (OSError, awelc.ElcError) as e:
            errors.append(f"power button / logo / rear: {e}")
    return errors


class Worker:
    """Applies in the background, one request at a time; queued requests collapse into the latest."""

    def __init__(self, on_done):
        self.on_done = on_done
        self.lock = threading.Lock()
        self.pending = None
        self.busy = False

    def request(self, cfg, parts):
        with self.lock:
            if self.pending:
                parts = tuple(sorted(set(self.pending[1]) | set(parts)))
            self.pending = (json.loads(json.dumps(cfg)), parts)
            if self.busy:
                return
            self.busy = True
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            with self.lock:
                if not self.pending:
                    self.busy = False
                    return
                cfg, parts = self.pending
                self.pending = None
            self.on_done(apply(cfg, parts))


def main(argv):
    if argv[:1] != ["apply"]:
        print(__doc__)
        return 1
    if not has_saved():
        return 0
    for _ in range(15):  # at login the USB devices and their permissions can take a moment
        if awkbd.find_device() or awelc.find_device():
            break
        time.sleep(1)
    parts = tuple(p for p, found in (("keyboard", awkbd.find_device()), ("elc", awelc.find_device())) if found)
    errors = apply(load(), parts)
    for e in errors:
        print(e, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
