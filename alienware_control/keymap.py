"""Key map of the Alienware m15 R7 per-key keyboard (Darfon 0d62:dabc, ABNT2 layout).

Worked out from photos of the keyboard painted by light id:
  * ids 20..119 form a grid: id = row * 20 + column, rows being the number row (1),
    QWERTY (2), home (3), bottom (4) and space (5) rows; wide keys skip columns;
  * the function row is ids 120..135 (Esc..Del), the media column 136..139 and the
    left/down/right arrows 141..143.
POS gives each light id an approximate physical position in key units, and
USAGE_TO_ID maps USB HID keyboard usages to the light under that key.
Other layouts of the same keyboard probably share the grid, with a few keys moved.
"""

POS = {}


def _put(base, pairs):
    for col, x, y in pairs:
        POS[base + col] = (x, y)


# function row (ids 120..135) and the right-hand media column
for _c in range(16):
    POS[120 + _c] = (_c * 0.97, 0.0)
POS.update({139: (15.6, 1.0), 136: (15.7, 2.0), 138: (15.8, 3.0), 137: (15.9, 4.0)})
# number row: ' 1 2 ... 0 - =  backspace
_put(20, [(c, float(c), 1.0) for c in range(13)] + [(15, 13.6, 1.0)])
# QWERTY row: tab, Q..P, accent, [, enter
_put(40, [(0, 0.3, 2.0)] + [(c, c - 0.5, 2.0) for c in range(2, 14)] + [(14, 13.8, 2.3)])
# home row: caps, A..L, C-cedilla, ~, ]
_put(60, [(1, 0.4, 3.0)] + [(c, c - 0.25, 3.0) for c in range(2, 14)])
# bottom row: left shift, \, Z..M, comma, period, ;, right shift
_put(80, [(1, 0.2, 4.0), (2, 1.25, 4.0)] + [(c, c - 0.75, 4.0) for c in range(3, 13)] + [(14, 13.2, 4.0)])
# space row: ctrl, fn, win, alt, space, altgr, menu, /, arrows
_put(100, [(0, 0.2, 5.0), (1, 1.3, 5.0), (3, 2.4, 5.0), (4, 3.5, 5.0),
           (5, 4.8, 5.0), (6, 5.8, 5.0), (7, 6.8, 5.0), (8, 7.8, 5.0), (10, 8.8, 5.0),
           (11, 10.3, 5.0), (9, 11.3, 5.0), (12, 12.4, 5.0), (14, 14.7, 4.2)])
POS.update({141: (13.7, 5.0), 142: (14.7, 5.0), 143: (15.7, 5.0)})

IDS = sorted(POS)

USAGE_TO_ID = {
    0x29: 120, 0x4A: 133, 0x4D: 134, 0x4C: 135,                      # esc, home, end, delete
    0x35: 20, 0x27: 30, 0x2D: 31, 0x2E: 32, 0x2A: 35,                # ' 0 - = backspace
    0x2B: 40, 0x2F: 52, 0x30: 53, 0x28: 54,                          # tab, accent, [, enter
    0x39: 61, 0x33: 71, 0x34: 72, 0x31: 73, 0x32: 73,                # caps, cedilla, ~, ]
    0x64: 82, 0x36: 90, 0x37: 91, 0x38: 92,                          # \ , . ;
    0x2C: 107, 0x87: 112,                                            # space, / ?
    0x52: 114, 0x50: 141, 0x51: 142, 0x4F: 143,                      # up, left, down, right
    # modifiers (usages 0xE0..0xE7)
    0xE0: 100, 0xE1: 81, 0xE2: 104, 0xE3: 103, 0xE5: 94, 0xE6: 111, 0xE7: 109,
}
USAGE_TO_ID.update({0x3A + i: 121 + i for i in range(12)})           # F1..F12
USAGE_TO_ID.update({0x1E + i: 21 + i for i in range(9)})             # 1..9
for _i, _ch in enumerate("qwertyuiop"):
    USAGE_TO_ID[4 + ord(_ch) - ord("a")] = 42 + _i
for _i, _ch in enumerate("asdfghjkl"):
    USAGE_TO_ID[4 + ord(_ch) - ord("a")] = 62 + _i
for _i, _ch in enumerate("zxcvbnm"):
    USAGE_TO_ID[4 + ord(_ch) - ord("a")] = 83 + _i

STRIPE_PALETTE = [(255, 0, 0), (0, 255, 0), (0, 60, 255), (255, 200, 0), (255, 0, 200), (0, 255, 255)]


def stripe_color(light_id):
    """Colour of a light in the "colour stripes" look: one colour per grid column."""
    return STRIPE_PALETTE[(light_id % 20) % 6]


# ---------- layouts for the drawing ----------
# Each row is a list of (width in key units, [light ids], legend). Rows are 16 units wide.

def _keys(ids, legends, width=1.0):
    return [(width, [i], legend) for i, legend in zip(ids, legends)]


_F_ROW = _keys(range(120, 136), ["Esc"] + [f"F{n}" for n in range(1, 13)] + ["Hm", "End", "Del"])
_SPACE = [105, 106, 107, 108, 110]

LAYOUTS = {
    "abnt2": [
        _F_ROW,
        _keys(range(20, 33), list("'1234567890-=")) + [(2.0, [35], "Bksp"), (1.0, [139], "Mic")],
        [(1.5, [40], "Tab")] + _keys(range(42, 52), list("QWERTYUIOP")) + _keys([52, 53], ["\u00b4", "["])
        + [(1.5, [54], "Enter"), (1.0, [136], "Mute")],
        [(1.75, [61], "Caps")] + _keys(range(62, 71), list("ASDFGHJKL")) + _keys([71, 72, 73], ["\u00c7", "~", "]"])
        + [(1.25, [54], ""), (1.0, [138], "V+")],
        [(1.25, [81], "Shift"), (1.0, [82], "\\")] + _keys(range(83, 90), list("ZXCVBNM"))
        + _keys([90, 91, 92], [",", ".", ";"]) + [(1.75, [94], "Shift"), (1.0, [114], "\u2191"), (1.0, [137], "V-")],
        [(1.5, [100], "Ctrl"), (1.0, [101], "Fn"), (1.0, [103], "Win"), (1.0, [104], "Alt"), (5.5, _SPACE, ""),
         (1.0, [111], "AltGr"), (1.0, [109], "Menu"), (1.0, [112], "/"),
         (1.0, [141], "\u2190"), (1.0, [142], "\u2193"), (1.0, [143], "\u2192")],
    ],
    # Same light grid with US legends. Not verified on a US keyboard.
    "us": [
        _F_ROW,
        _keys(range(20, 33), list("`1234567890-=")) + [(2.0, [35], "Bksp"), (1.0, [139], "Mic")],
        [(1.5, [40], "Tab")] + _keys(range(42, 52), list("QWERTYUIOP")) + _keys([52, 53], ["[", "]"])
        + [(1.5, [54], "\\"), (1.0, [136], "Mute")],
        [(1.75, [61], "Caps")] + _keys(range(62, 71), list("ASDFGHJKL")) + _keys([71, 72], [";", "'"])
        + [(2.25, [73, 54], "Enter"), (1.0, [138], "V+")],
        [(2.25, [81, 82], "Shift")] + _keys(range(83, 90), list("ZXCVBNM"))
        + _keys([90, 91, 92], [",", ".", "/"]) + [(1.75, [94], "Shift"), (1.0, [114], "\u2191"), (1.0, [137], "V-")],
        [(1.5, [100], "Ctrl"), (1.0, [101], "Fn"), (1.0, [103], "Win"), (1.0, [104], "Alt"), (6.5, _SPACE + [112], ""),
         (1.0, [111], "Alt"), (1.0, [109], "Ctrl"),
         (1.0, [141], "\u2190"), (1.0, [142], "\u2193"), (1.0, [143], "\u2192")],
    ],
}
LAYOUT_NAMES = {"abnt2": "ABNT2 (Brazil)", "us": "US (not verified)"}
ROW_HEIGHTS = [0.6, 1, 1, 1, 1, 1]


def detect_layout():
    """abnt2 when the system keyboard layout is Brazilian, else us."""
    import os
    import subprocess
    try:
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.input-sources", "sources"],
                             capture_output=True, text=True, timeout=2).stdout
        if "'br" in out:
            return "abnt2"
        if "'us" in out:
            return "us"
    except (OSError, subprocess.SubprocessError):
        pass
    return "abnt2" if os.environ.get("LANG", "").startswith("pt_BR") else "us"
