"""Lighting effects: the catalogue, a software simulation (for previews) and the
hardware action lists for the AW-ELC controller. No GTK imports.

Two kinds of hardware run them:
  * keyboard (Darfon): built-in effects, selected by a type number (see awkbd.py);
  * AW-ELC zones (power button, lid logo, rear strip): a looping list of actions per
    zone, each `(mode, duration, tempo, rgb)`. Values follow alien-lights, which was
    tested on this controller family: morph tempo 64, speeds 3500/1800/800.
Everything runs on the controllers themselves, so effects keep going with the app closed.
"""
import math
from collections import namedtuple

MODE_COLOR, MODE_PULSE, MODE_MORPH = 0, 1, 2
SPEEDS = {"slow": 3500, "normal": 1800, "fast": 800}        # duration of one step
PULSE_TEMPO = {"slow": 100, "normal": 175, "fast": 250}
MORPH_TEMPO = 64
HOLD_TEMPO = 250
BLACK = (0, 0, 0)

PALETTES = {
    "spectrum": [(255, 0, 0), (255, 220, 0), (0, 255, 0), (0, 255, 255), (0, 60, 255), (255, 0, 255)],
    "fire": [(255, 30, 0), (255, 120, 0), (255, 200, 20), (255, 70, 0)],
    "aurora": [(0, 255, 140), (0, 200, 255), (130, 80, 255), (0, 255, 200)],
    "ocean": [(0, 60, 255), (0, 200, 255), (0, 255, 190), (0, 120, 255)],
    "sunset": [(255, 60, 120), (255, 120, 0), (150, 60, 255), (255, 0, 80)],
    "signal": [(255, 0, 0), (255, 170, 0), (0, 255, 0)],
}
# The m15 R7 power button LED has no blue channel and cannot fade: morphs flicker,
# so its effects are built from colour steps ("holds") instead.
STEPPED_ZONES = ("power",)
POLICE = ((255, 0, 0), (0, 40, 255))
STRIPES = [(255, 0, 0), (0, 255, 0), (0, 60, 255), (255, 200, 0), (255, 0, 200), (0, 255, 255)]

# key, label, zones it applies to, number of user colours (0, 1 or 2), has speed
Effect = namedtuple("Effect", "key label zones colors speed")
ELC = ("power", "logo", "rear")
FADING = ("logo", "rear")
CATALOG = [
    Effect("static", "Static", ("keyboard",) + ELC, 1, False),
    Effect("breathing", "Breathing", ("keyboard",) + FADING, 1, True),
    Effect("pulse", "Pulse", ("keyboard",) + FADING, 1, True),
    Effect("blink", "Blink", ELC, 1, True),
    Effect("wave", "Wave", ("keyboard",), 1, True),
    Effect("mix", "Colour mix", ("keyboard",), 2, True),
    Effect("nightrider", "Night rider", ("keyboard",), 1, True),
    Effect("kb_rainbow", "Rainbow wave", ("keyboard",), 0, True),
    Effect("kb_spectrum", "Spectrum", ("keyboard",), 0, True),
    Effect("stars", "Stars (typing)", ("keyboard",), 1, False),
    Effect("ripple", "Ripple (typing)", ("keyboard",), 2, False),
    Effect("stripes", "Colour stripes", ("keyboard",), 0, False),
    Effect("paint", "Paint keys", ("keyboard",), 1, False),
    Effect("duo", "Colour shift", ELC, 2, True),
    Effect("signal", "Traffic light", ("power",), 0, True),
    Effect("spectrum", "Spectrum", FADING, 0, True),
    Effect("fire", "Fire", ELC, 0, True),
    Effect("aurora", "Aurora", FADING, 0, True),
    Effect("ocean", "Ocean", FADING, 0, True),
    Effect("sunset", "Sunset", FADING, 0, True),
    # rear strip only: it has two halves that blend in the middle
    Effect("split", "Two halves", ("rear",), 2, False),
    Effect("swap", "Swap", ("rear",), 2, True),
    Effect("tide", "Tide", ("rear",), 1, True),
    Effect("rainbow_wave", "Rainbow wave", ("rear",), 0, True),
    Effect("police", "Police", ("rear",), 0, True),
]
BY_KEY = {e.key: e for e in CATALOG}
TWO_HALVES = {"split", "swap", "tide", "rainbow_wave", "police"}


def effects_for(zone):
    return [e for e in CATALOG if zone in e.zones]


def valid(zone, key):
    return key in BY_KEY and zone in BY_KEY[key].zones


# ---------- software simulation (previews) ----------

def _mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _tri(t):
    """1 at t = 0, 0 at t = 1, back to 1 at t = 2."""
    return abs((t % 2) - 1)


def _palette(colors, t):
    n = len(colors)
    i = int(t) % n
    return _mix(colors[i], colors[(i + 1) % n], t % 1)


def _single(key, c1, c2, t, stepped=False):
    """Colour of one ELC zone at step-time t."""
    if key == "blink":
        return c1 if (t % 2) < 1 else BLACK
    if stepped:
        if key == "duo":
            return c1 if (t % 2) < 1 else c2
        if key in PALETTES:
            return PALETTES[key][int(t) % len(PALETTES[key])]
    if key == "breathing":
        return _mix(BLACK, c1, _tri(t))
    if key == "pulse":
        return c1 if (t % 1) < 0.45 else _mix(BLACK, c1, 0.08)
    if key == "duo":
        return _mix(c2, c1, _tri(t))
    if key in PALETTES:
        return _palette(PALETTES[key], t)
    return c1


def _halves(key, c1, c2, t):
    if key == "split":
        return c1, c2
    if key == "swap":
        return _mix(c2, c1, _tri(t)), _mix(c2, c1, _tri(t + 1))
    if key == "tide":
        return _mix(BLACK, c1, _tri(t)), _mix(BLACK, c1, _tri(t + 1))
    if key == "rainbow_wave":
        pal = PALETTES["spectrum"]
        return _palette(pal, t), _palette(pal, t + len(pal) / 2)
    if key == "police":
        on = (t % 2) < 1
        return (POLICE[0] if on else BLACK), (BLACK if on else POLICE[1])
    c = _single(key, c1, c2, t)
    return c, c


def sample(zone, key, c1, c2, seconds, speed="normal", u=0.5):
    """Simulated colour (r, g, b in 0..255) at position u (0 = left, 1 = right)."""
    t = seconds * 1000.0 / SPEEDS.get(speed, SPEEDS["normal"])
    if zone == "keyboard":
        if key == "wave":
            k = 0.10 + 0.90 * max(0.0, math.cos(2 * math.pi * (u - t * 0.9))) ** 3
            return _mix(BLACK, c1, k)
        if key == "nightrider":
            pos = _tri(t * 1.2 + 1)
            return _mix(BLACK, c1, 0.06 + 0.94 * math.exp(-((u - pos) / 0.09) ** 2))
        if key == "mix":
            return _mix(c2, c1, _tri(t))
        if key == "kb_rainbow":
            pal = PALETTES["spectrum"]
            return _palette(pal, (u * 1.5 - t * 0.9) % 1 * len(pal))
        if key == "kb_spectrum":
            pal = PALETTES["spectrum"]
            return _palette(pal, t * 0.8 + int(u * 12) * 1.7)
        if key == "ripple":  # colour 1 = the ring, colour 2 = the resting keys
            age = (t * 1.4) % 1.6
            ring = max(0.0, 1.0 - abs(abs(u - 0.5) - age * 0.5) / 0.09) if age < 1.1 else 0.0
            return _mix(c2, c1, ring * (1 - age / 1.1) ** 0.6 if age < 1.1 else 0.0)
        if key == "stripes":
            return STRIPES[int(u * 12) % len(STRIPES)]
        if key == "paint":  # a few painted keys on a dark keyboard
            return c1 if int(u * 12) in (2, 3, 4, 7, 9) else _mix(BLACK, c1, 0.06)
        if key == "stars":  # a few keys twinkle, as if someone were typing
            cell = int(u * 12)
            beat = int(t * 3)
            lit = (cell * 7 + beat * 5) % 11 < 2
            return _mix(BLACK, c1, 1.0 if lit else 0.05)
        return _single(key, c1, c2, t)
    if zone == "rear":
        a, b = _halves(key, c1, c2, t)
        blend = min(1.0, max(0.0, (u - 0.36) / 0.28))
        blend = blend * blend * (3 - 2 * blend)
        return _mix(a, b, blend)
    return _single(key, c1, c2, t, stepped=zone in STEPPED_ZONES)


# ---------- AW-ELC action lists ----------

def _morph(colors, d):
    return [(MODE_MORPH, d, MORPH_TEMPO, tuple(c)) for c in colors]


def _hold(colors, d):
    return [(MODE_COLOR, d, HOLD_TEMPO, tuple(c)) for c in colors]


def _one(key, c1, c2, speed, stepped=False):
    d = SPEEDS.get(speed, SPEEDS["normal"])
    if key == "blink":
        return _hold([c1, BLACK], d)
    if stepped:
        if key == "duo":
            return _hold([c1, c2], d)
        if key in PALETTES:
            return _hold(PALETTES[key], d)
    if key == "breathing":
        return _morph([c1, BLACK], d)
    if key == "pulse":
        return [(MODE_PULSE, d, PULSE_TEMPO.get(speed, 175), tuple(c1))]
    if key == "duo":
        return _morph([c1, c2], d)
    if key in PALETTES:
        return _morph(PALETTES[key], d)
    return [(MODE_COLOR, 1, 2, tuple(c1))]  # static, as tested


def elc_actions(key, c1, c2, speed, halves=1, scale=1.0, stepped=False):
    """Action lists for a zone group: one list per half (rear strip) or a single list.

    `scale` (0..1) dims fixed palettes the same way brightness dims the user colours.
    """
    def dim(actions):
        return [(m, d, t, tuple(int(round(x * scale)) for x in c)) for m, d, t, c in actions]

    d = SPEEDS.get(speed, SPEEDS["normal"])
    fixed = key in PALETTES or key in ("rainbow_wave", "police")
    if halves == 2 and key in TWO_HALVES:
        if key == "split":
            a, b = _one("static", c1, c2, speed), _one("static", c2, c1, speed)
        elif key == "swap":
            a, b = _morph([c1, c2], d), _morph([c2, c1], d)
        elif key == "tide":
            a, b = _morph([c1, BLACK], d), _morph([BLACK, c1], d)
        elif key == "rainbow_wave":
            pal = PALETTES["spectrum"]
            a, b = _morph(pal, d), _morph(pal[3:] + pal[:3], d)
        else:  # police
            step = max(250, d // 4)
            a, b = _hold([POLICE[0], BLACK], step), _hold([BLACK, POLICE[1]], step)
        return [dim(a), dim(b)] if fixed else [a, b]
    one = _one(key, c1, c2, speed, stepped)
    one = dim(one) if fixed else one
    return [one] * halves
