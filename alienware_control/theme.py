"""Themes and settings for Alienware Control.

- gtk:    follows the system GTK theme. Loads the theme's libadwaita.css when it has
          one, otherwise only the @define-color lines of its GTK 4 CSS. With neither,
          plain libadwaita is used, which follows the system light/dark preference.
- neon:   midnight blue with cyan and violet.
- amoled: pure black with cyan highlights.
"""
import os
import re
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

from i18n import _  # noqa: E402

from config import CONFIG, CONFIG_DIR, DEFAULT_CONFIG, THEME_NAMES, load_config, save_config  # noqa: E402,F401

PALETTES = {
    "neon": {
        "window_bg_color": "#0B0E14", "window_fg_color": "#E8EDF4",
        "view_bg_color": "#0B0E14", "view_fg_color": "#E8EDF4",
        "headerbar_bg_color": "#0D1118", "headerbar_fg_color": "#E8EDF4",
        "headerbar_border_color": "#1A2030", "headerbar_backdrop_color": "#0D1118",
        "card_bg_color": "#10151F", "card_fg_color": "#E8EDF4",
        "popover_bg_color": "#121722", "popover_fg_color": "#E8EDF4",
        "dialog_bg_color": "#10151F", "dialog_fg_color": "#E8EDF4",
        "accent_bg_color": "#3EE8FF", "accent_fg_color": "#0B0E14", "accent_color": "#3EE8FF",
        "awc_glow": "#121A28",
    },
    "amoled": {
        "window_bg_color": "#000000", "window_fg_color": "#F2F2F2",
        "view_bg_color": "#000000", "view_fg_color": "#F2F2F2",
        "headerbar_bg_color": "#000000", "headerbar_fg_color": "#F2F2F2",
        "headerbar_border_color": "#1A1A1A", "headerbar_backdrop_color": "#000000",
        "card_bg_color": "#0A0A0A", "card_fg_color": "#F2F2F2",
        "popover_bg_color": "#111111", "popover_fg_color": "#F2F2F2",
        "dialog_bg_color": "#0A0A0A", "dialog_fg_color": "#F2F2F2",
        "accent_bg_color": "#3EE8FF", "accent_fg_color": "#000000", "accent_color": "#3EE8FF",
        "awc_glow": "#06161A",
    },
}

APP_CSS = """
.awc-card { background-color: @card_bg_color; color: @card_fg_color;
            border: 1px solid alpha(currentColor, 0.08); border-radius: 18px; padding: 18px; }
.awc-inner { background-color: alpha(currentColor, 0.03); border: 1px solid alpha(currentColor, 0.08);
             border-radius: 14px; padding: 14px; }
.awc-title { font-weight: 700; font-size: 18px; }
.awc-big { font-weight: 700; font-size: 34px; }
.awc-muted { opacity: 0.68; }
.awc-small { font-size: 12px; }
.awc-pill { border-radius: 999px; padding: 4px 12px; font-weight: 600; font-size: 13px; }
.awc-pill.ok { background-color: alpha(@accent_color, 0.14); color: @accent_color; }
.awc-pill.warn { background-color: alpha(#F5B04A, 0.14); color: #F5B04A; }
.awc-pill.crit { background-color: alpha(#FF5C6C, 0.14); color: #FF5C6C; }
.awc-pill.none { background-color: alpha(currentColor, 0.08); }
.awc-opt { border-radius: 14px; padding: 14px; min-height: 64px;
           background-color: alpha(currentColor, 0.03); border: 1px solid alpha(currentColor, 0.08); }
.awc-opt:hover { background-color: alpha(currentColor, 0.06); }
.awc-opt:checked { background-color: alpha(@accent_color, 0.10); border-color: @accent_color;
                   box-shadow: inset 0 0 0 1px @accent_color; color: inherit; }
.awc-opt-title { font-weight: 700; font-size: 15px; }
.awc-seg { background-color: alpha(currentColor, 0.05); border-radius: 12px; padding: 4px; }
.awc-seg > button { border-radius: 9px; min-height: 36px; padding: 0 14px; background: none; box-shadow: none; }
.awc-seg > button:checked { background-color: alpha(currentColor, 0.12); }
.awc-swatch { min-width: 30px; min-height: 30px; border-radius: 999px; padding: 0;
              border: 2px solid alpha(currentColor, 0.15); }
.awc-swatch:hover { border-color: alpha(currentColor, 0.5); }
.awc-rotate { border-radius: 999px; min-height: 46px; padding: 0 22px; font-weight: 600; }
"""


# ----- system theme -----

def _gsetting(schema, key):
    try:
        out = subprocess.run(["gsettings", "get", schema, key], capture_output=True, text=True, timeout=2).stdout
        return out.strip().strip("'") or None
    except (OSError, subprocess.SubprocessError):
        return None


def system_theme_name():
    settings = Gtk.Settings.get_default()
    fallback = settings.get_property("gtk-theme-name") if settings else None
    return _gsetting("org.gnome.desktop.interface", "gtk-theme") or fallback


def prefers_dark():
    return _gsetting("org.gnome.desktop.interface", "color-scheme") == "prefer-dark"


def find_theme_dir(name):
    if not name or "/" in name:
        return None
    data_home = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    dirs = [os.path.expanduser("~/.themes"), os.path.join(data_home, "themes")]
    dirs += [os.path.join(d, "themes") for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if d]
    for d in dirs:
        path = os.path.join(d, name)
        if os.path.isdir(path):
            return path
    return None


def system_theme_css():
    """(css, description) with the active GTK theme's colours, or (None, reason)."""
    name = system_theme_name()
    tdir = find_theme_dir(name)
    if not tdir:
        return None, _("theme {name} not found").format(name=name or "?")
    adw = os.path.join(tdir, "libadwaita.css")
    if os.path.isfile(adw):
        try:
            with open(adw) as f:
                return f.read(), f"{name} (libadwaita.css)"
        except OSError:
            pass
    for fname in (("gtk-dark.css", "gtk.css") if prefers_dark() else ("gtk.css",)):
        try:
            with open(os.path.join(tdir, "gtk-4.0", fname)) as f:
                text = f.read()
        except OSError:
            continue
        colors = re.findall(r"@define-color\s+[\w-]+\s+[^;]+;", text)
        if colors:
            return "\n".join(colors), _("{name} (GTK 4 colours)").format(name=name)
    return None, _("{name} has no GTK 4 support").format(name=name)


class ThemeManager:
    def __init__(self):
        self.display = Gdk.Display.get_default()
        self.app_provider = Gtk.CssProvider()
        _load(self.app_provider, APP_CSS)
        Gtk.StyleContext.add_provider_for_display(self.display, self.app_provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.theme_provider = None
        self.source = ""

    def apply(self, theme):
        if self.theme_provider:
            Gtk.StyleContext.remove_provider_for_display(self.display, self.theme_provider)
            self.theme_provider = None
        style = Adw.StyleManager.get_default()
        if theme in PALETTES:
            style.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            css = "\n".join(f"@define-color {k} {v};" for k, v in PALETTES[theme].items())
            # Some system themes paint the window background directly; force the chosen colours.
            css += ("\nwindow.background, .background { background-color: @window_bg_color; color: @window_fg_color; }"
                    "\nheaderbar { background-color: @headerbar_bg_color; color: @headerbar_fg_color; }")
            self.source = _(THEME_NAMES[theme])
        else:
            style.set_color_scheme(Adw.ColorScheme.DEFAULT)
            css, self.source = system_theme_css()
            if css is None:
                self.source = _("system default ({reason})").format(reason=self.source)
        if css:
            self.theme_provider = Gtk.CssProvider()
            _load(self.theme_provider, css)
            Gtk.StyleContext.add_provider_for_display(self.display, self.theme_provider,
                                                      Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)


def _load(provider, css):
    if hasattr(provider, "load_from_string"):  # GTK 4.12+
        provider.load_from_string(css)
    else:
        provider.load_from_data(css, -1)


# ----- colours for Cairo drawings -----

def palette(widget):
    """Current theme colours as (r, g, b, a) tuples."""
    ctx = widget.get_style_context()

    def look(name, fallback):
        found, color = ctx.lookup_color(name)
        c = color if found else _rgba(fallback)
        return (c.red, c.green, c.blue, c.alpha)

    fg = widget.get_color() if hasattr(widget, "get_color") else _rgba("#ffffff")
    return {
        "fg": (fg.red, fg.green, fg.blue, 1.0),
        "bg": look("window_bg_color", "#000000"),
        "card": look("card_bg_color", "#111111"),
        "accent": look("accent_color", "#3584e4"),
        "glow": look("awc_glow", "#000000"),
        "warn": (0.96, 0.69, 0.29, 1),
        "crit": (1.0, 0.36, 0.42, 1),
    }


def _rgba(text):
    c = Gdk.RGBA()
    c.parse(text)
    return c


def mix(a, b, t):
    return tuple(a[i] * (1 - t) + b[i] * t for i in range(3)) + (1.0,)
