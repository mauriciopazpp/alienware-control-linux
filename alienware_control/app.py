#!/usr/bin/env python3
"""Alienware Control: dashboard, lighting and power settings for Alienware laptops on Linux.

Runs on any distribution with GTK 4 + libadwaita. Hardware-specific parts (lighting,
BIOS settings) are only enabled when the matching hardware is detected.
"""
import colorsys
import json
import os
import shutil
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

import awelc  # noqa: E402
import awkbd  # noqa: E402
import diskwatch  # noqa: E402
import fx  # noqa: E402
import i18n  # noqa: E402
import keymap  # noqa: E402
import lights  # noqa: E402
import sensors  # noqa: E402
import theme  # noqa: E402
from i18n import _  # noqa: E402
from widgets import (ColorWheel, DiskRing, EffectPreview, Gauge, LaptopView,  # noqa: E402
                     SceneSwatch, rounded)

VERSION = "0.4.1"
APP_ID = "io.github.alienware_control.AlienwareControl"


def _helper(name):
    """Root helpers live in /usr/libexec (.deb package) or /usr/local/libexec (install.sh)."""
    for d in ("/usr/libexec", "/usr/local/libexec"):
        path = os.path.join(d, name)
        if os.path.exists(path):
            return path
    return os.path.join("/usr/local/libexec", name)


READ_HELPER = _helper("alienware-control-read")
WRITE_HELPER = _helper("alienware-control-write")
SYSMAN = "/sys/class/firmware-attributes/dell-wmi-sysman"
AUTOSTART_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "autostart")

THERMAL = [
    ("Quiet", "Quiet", "Less noise, limited power"),
    ("Balanced", "Balanced", "Recommended default"),
    ("Performance", "Performance", "Strong fans, for gaming"),
    ("Battery", "Battery", "Saves power on battery"),
]
CHARGE = [
    ("PrimAcUse", "Mostly plugged in", "Caps the charge level"),
    ("Adaptive", "Adaptive", "The BIOS decides"),
    ("Standard", "Standard", "Full charge"),
    ("Express", "Express", "Fast, wears the battery"),
    ("Custom", "Custom", "You pick the range"),
]
PROFILES = [
    ("power-saver", "Power saver", "Low clocks, cooler and quieter"),
    ("balanced", "Balanced", "Boosts only when needed"),
    ("performance", "Performance", "High clocks, more heat and fan noise"),
]
PRESETS = [
    ("Cyan", (62, 232, 255)), ("Violet", (138, 92, 255)), ("Red", (255, 0, 0)),
    ("Orange", (255, 110, 0)), ("Green", (0, 255, 90)), ("Pink", (255, 60, 200)),
    ("Blue", (0, 80, 255)), ("Cool white", (200, 225, 255)),
]
CYAN, VIOLET, WHITE = (62, 232, 255), (138, 92, 255), (200, 225, 255)
# name, {light: (effect, colour, colour 2)}, brightness
SCENES = [
    ("Neon", {"keyboard": ("wave", CYAN, VIOLET), "power": ("static", (0, 255, 0), (255, 170, 0)),
              "logo": ("duo", CYAN, VIOLET), "rear": ("swap", CYAN, VIOLET)}, 100),
    ("Ember", {"keyboard": ("breathing", (255, 90, 0), (255, 0, 0)), "power": ("static", (255, 40, 0), (255, 0, 0)),
               "logo": ("fire", (255, 90, 0), (255, 0, 0)), "rear": ("fire", (255, 90, 0), (255, 0, 0))}, 100),
    ("Aurora", {"keyboard": ("mix", (0, 255, 140), (130, 80, 255)), "power": ("static", (0, 255, 0), (255, 170, 0)),
                "logo": ("aurora", (0, 255, 140), (130, 80, 255)), "rear": ("swap", (0, 255, 140), (130, 80, 255))}, 100),
    ("Rainbow", {"keyboard": ("wave", (255, 60, 200), CYAN), "power": ("signal", (255, 0, 0), (0, 255, 0)),
                 "logo": ("spectrum", (255, 60, 200), CYAN), "rear": ("rainbow_wave", (255, 60, 200), CYAN)}, 100),
    ("Ocean", {"keyboard": ("nightrider", (0, 120, 255), CYAN), "power": ("static", (0, 255, 0), (255, 170, 0)),
               "logo": ("ocean", (0, 120, 255), CYAN), "rear": ("tide", (0, 160, 255), CYAN)}, 100),
    ("Focus", {z: ("static", WHITE, WHITE) for z in lights.ZONES}, 40),
    ("Lights off", {z: ("static", (60, 60, 60), (60, 60, 60)) for z in lights.ZONES}, 0),
]
SPEED_NAMES = [("slow", "Slow"), ("normal", "Normal"), ("fast", "Fast")]
FS_NAMES = {"ntfs": "Windows", "vfat": "EFI (boot)", "ext4": "Linux", "btrfs": "Linux",
            "xfs": "Linux", "f2fs": "Linux", "exfat": "exFAT"}


def label(text, *classes, xalign=0, wrap=False):
    lb = Gtk.Label(label=text, xalign=xalign, wrap=wrap)
    for c in classes:
        lb.add_css_class(c)
    return lb


def card(title=None, subtitle=None):
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    box.add_css_class("awc-card")
    if title:
        head = Gtk.Box(spacing=8)
        head.append(label(_(title), "awc-title"))
        if subtitle:
            sub = label(_(subtitle), "awc-muted", "awc-small", xalign=1)
            sub.set_hexpand(True)
            head.append(sub)
        box.append(head)
    return box


def set_autostart(name, enabled, args):
    """Create or remove ~/.config/autostart/<name>.desktop running one of our scripts."""
    path = os.path.join(AUTOSTART_DIR, f"{name}.desktop")
    if not enabled:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return
    os.makedirs(AUTOSTART_DIR, exist_ok=True)
    cmd = " ".join(_desktop_quote(a) for a in [sys.executable, *args])
    with open(path, "w") as f:
        f.write("[Desktop Entry]\nType=Application\n"
                f"Name=Alienware Control ({name})\nExec={cmd}\n"
                "NoDisplay=true\nX-GNOME-Autostart-Delay=5\n")


def _desktop_quote(arg):
    """Quote one Exec= argument as the Desktop Entry spec requires."""
    if arg and all(c.isalnum() or c in "/._-+=:," for c in arg):
        return arg
    escaped = "".join("\\" + c if c in '"`$\\' else c for c in arg)
    return '"' + escaped.replace("%", "%%") + '"'


def sync_lights_autostart(enabled):
    """Re-apply lighting at login, but only once the user has saved some colours."""
    set_autostart("alienware-control-lights", enabled and lights.has_saved(),
                  [os.path.join(HERE, "lights.py"), "apply"])


def sync_disk_watch(enabled):
    script = os.path.join(HERE, "diskwatch.py")
    set_autostart("alienware-control-diskwatch", enabled, [script, "run"])
    if enabled:  # start now too; a lock file keeps it to a single instance
        subprocess.Popen([sys.executable, script, "run"], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def fmt_temp(celsius, unit):
    if celsius is None:
        return "—", "°" + unit
    value = celsius * 9 / 5 + 32 if unit == "F" else celsius
    return f"{value:.0f}", "°" + unit


class OptionGroup(Gtk.Grid):
    """Large single-choice buttons (title + description)."""

    def __init__(self, options, columns, on_pick):
        super().__init__(column_spacing=10, row_spacing=10, column_homogeneous=True)
        self.on_pick = on_pick
        self.loading = False
        self.buttons = {}
        first = None
        for i, (key, title, desc) in enumerate(options):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            box.append(label(_(title), "awc-opt-title"))
            box.append(label(_(desc), "awc-muted", "awc-small", wrap=True))
            btn = Gtk.ToggleButton(child=box)
            btn.add_css_class("awc-opt")
            if first:
                btn.set_group(first)
            first = first or btn
            btn.connect("toggled", self._toggled, key)
            self.attach(btn, i % columns, i // columns, 1, 1)
            self.buttons[key] = btn

    def _toggled(self, btn, key):
        if btn.get_active() and not self.loading:
            self.on_pick(key)

    def select(self, key):
        self.loading = True
        if key in self.buttons:
            self.buttons[key].set_active(True)
        self.loading = False

    def show_only(self, keys):
        for key, btn in self.buttons.items():
            btn.set_visible(key in keys)


class Segmented(Gtk.Box):
    def __init__(self, options, on_pick):
        super().__init__(spacing=4, homogeneous=True)
        self.add_css_class("awc-seg")
        self.on_pick = on_pick
        self.loading = False
        self.buttons = {}
        first = None
        for key, text in options:
            btn = Gtk.ToggleButton(label=_(text))
            if first:
                btn.set_group(first)
            first = first or btn
            btn.connect("toggled", self._toggled, key)
            self.append(btn)
            self.buttons[key] = btn

    def _toggled(self, btn, key):
        if btn.get_active() and not self.loading:
            self.on_pick(key)

    def select(self, key):
        self.loading = True
        if key in self.buttons:
            self.buttons[key].set_active(True)
        self.loading = False


class Swatch(Gtk.DrawingArea):
    def __init__(self, rgb, w=30, h=30, radius=15):
        super().__init__()
        self.rgb, self.radius = rgb, radius
        self.set_content_width(w)
        self.set_content_height(h)
        self.set_draw_func(self.draw)

    def set_rgb(self, rgb):
        self.rgb = rgb
        self.queue_draw()

    def draw(self, area, cr, w, h):
        rounded(cr, 0, 0, w, h, self.radius)
        cr.set_source_rgb(*(c / 255 for c in self.rgb))
        cr.fill()


# ======================================================================

class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Alienware Control for Linux")
        self.app = app
        self.cfg = app.cfg
        self.set_default_size(1180, 800)
        self.set_size_request(900, 640)
        self.cpu = sensors.CpuUsage()
        self.cpu.sample()
        self.bios = None
        self.drawings = []
        self.gauges = {}
        self._loading = False
        self._turbo_loading = False
        self.timer = None

        self.toasts = Adw.ToastOverlay()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack = Adw.ViewStack()
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE))
        gear = Gtk.Button(icon_name="emblem-system-symbolic", tooltip_text=_("Settings"))
        gear.connect("clicked", lambda *_: SettingsWindow(self).present())
        header.pack_end(gear)
        root.append(header)
        self.banner = Adw.Banner()
        self.banner.connect("button-clicked", lambda *_: self.show_install_help())
        root.append(self.banner)
        root.append(self.stack)
        self.toasts.set_child(root)
        self.set_content(self.toasts)

        self.stack.add_titled_with_icon(self.build_dashboard(), "dashboard", _("Dashboard"), "speedometer-symbolic")
        self.stack.add_titled_with_icon(self.build_lights(), "lighting", _("Lighting"), "display-brightness-symbolic")
        self.stack.add_titled_with_icon(self.build_power(), "power", _("Power"), "battery-good-symbolic")
        # Developer aid: AWC_PAGE=lighting|power opens a page directly (used for screenshots).
        self.stack.set_visible_child_name(os.environ.get("AWC_PAGE", "dashboard"))

        self.refresh_sensors()
        self.refresh_disks()
        self.load_power_profile()
        self.load_bios()
        self.restart_timer()
        self.disk_timer = GLib.timeout_add_seconds(30, self._disks_tick)
        self.connect("close-request", lambda *_: self.stop_timers() or False)

    # ----- helpers -----

    def stop_timers(self):
        """Remove every GLib source this window owns (called before it goes away)."""
        for attr in ("timer", "disk_timer", "apply_source"):
            source = getattr(self, attr, None)
            if source:
                GLib.source_remove(source)
                setattr(self, attr, None)

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=4))

    def redraw(self):
        for d in self.drawings:
            d.queue_draw()

    def restart_timer(self):
        if self.timer:
            GLib.source_remove(self.timer)
        self.timer = GLib.timeout_add_seconds(int(self.cfg["interval"]), self._tick)

    def _tick(self):
        self.refresh_sensors()
        return True

    def _disks_tick(self):
        self.refresh_disks()
        return True

    @staticmethod
    def scrolled(child):
        sw = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        sw.set_child(Adw.Clamp(maximum_size=1200, tightening_threshold=900, child=child))
        return sw

    # ================= DASHBOARD =================

    def build_dashboard(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                       margin_top=22, margin_bottom=22, margin_start=22, margin_end=22)
        head = Gtk.Box()
        head.append(label(_("Right now"), "awc-title"))
        machine = label(f"{_(sensors.machine())} · {sensors.distro()}", "awc-muted", "awc-small", xalign=1)
        machine.set_hexpand(True)
        head.append(machine)
        page.append(head)

        self.gauge_box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                     max_children_per_line=6, min_children_per_line=2,
                                     column_spacing=14, row_spacing=14)
        page.append(self.gauge_box)

        bottom = Gtk.Box(spacing=14)
        disks_card = card()
        disks_card.set_hexpand(True)
        top = Gtk.Box(spacing=8)
        top.append(label(_("Disks"), "awc-title"))
        top.append(Gtk.Box(hexpand=True))
        self.disk_pill = label("", "awc-pill", "ok")
        top.append(self.disk_pill)
        disks_card.append(top)
        self.disk_box = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                                    max_children_per_line=3, min_children_per_line=2,
                                    column_spacing=12, row_spacing=12)
        disks_card.append(self.disk_box)
        bottom.append(disks_card)

        self.batt_card = card("Battery")
        self.batt_card.set_size_request(300, -1)
        self.batt_big = label("—", "awc-big")
        self.batt_card.append(self.batt_big)
        self.batt_state = label("", "awc-muted", "awc-small")
        self.batt_card.append(self.batt_state)
        hrow = Gtk.Box()
        hrow.append(label(_("Health"), "awc-small"))
        self.health_label = label("—", "awc-small", xalign=1)
        self.health_label.set_hexpand(True)
        hrow.append(self.health_label)
        self.batt_card.append(hrow)
        self.health_bar = Gtk.LevelBar(min_value=0, max_value=1)
        self.batt_card.append(self.health_bar)
        self.health_note = label("", "awc-muted", "awc-small", wrap=True)
        self.batt_card.append(self.health_note)
        bottom.append(self.batt_card)
        page.append(bottom)
        return self.scrolled(page)

    def set_gauge(self, key, title, unit, maximum, warn, crit, value, display, status_text):
        if key not in self.gauges:
            g = Gauge(title, unit, maximum, warn, crit)
            status = label("", "awc-small", "awc-muted", xalign=0.5)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.add_css_class("awc-card")
            box.append(g)
            box.append(status)
            self.gauge_box.append(box)
            self.gauges[key] = (g, status)
            self.drawings.append(g)
        g, status = self.gauges[key]
        g.unit, g.maximum, g.warn, g.crit = unit, maximum, warn, crit
        g.set(value, display)
        status.set_label(status_text)

    def refresh_sensors(self):
        hw = sensors.hwmon_by_name()
        unit = self.cfg["unit"]

        def temp_status(t, warn, crit):
            if t is None:
                return _("no reading")
            return _("hot") if t >= crit else _("warm") if t >= warn else _("normal")

        t = sensors.cpu_temp(hw)
        d, u = fmt_temp(t, unit)
        self.set_gauge("cpu", "CPU", u, 100, 70, 85, t, d, temp_status(t, 70, 85))

        g = sensors.gpu_temp(hw)
        awake = sensors.nvidia_awake()
        if g is not None or awake is not None:
            d, u = fmt_temp(g, unit)
            st = temp_status(g, 70, 85)
            if awake is not None:
                st = (_("active · ") if awake else _("sleeping · ")) + st
            self.set_gauge("gpu", "GPU", u, 100, 70, 85, g, d, st)

        load = self.cpu.sample()
        if load is not None:
            self.set_gauge("load", _("CPU load"), "%", 100, 70, 90, load, f"{load:.0f}",
                           _("busy") if load >= 70 else _("calm"))

        mem = sensors.memory()
        if mem:
            used, total = mem
            pct = used / total * 100
            self.set_gauge("mem", _("Memory"), _("of {size}").format(size=sensors.human(total)), 100, 80, 92, pct,
                           sensors.human(used).split()[0], _("tight") if pct >= 80 else _("plenty free"))

        for i, (name, rpm, top) in enumerate(sensors.fans(hw)):
            self.set_gauge(f"fan{i}", _(name), "RPM", top, top * 0.6, top * 0.85, rpm, str(rpm),
                           _("stopped") if rpm == 0 else _("spinning"))

        for name, temp in sorted(sensors.nvme_temps(hw).items()):
            d, u = fmt_temp(temp, unit)
            self.set_gauge(f"ssd-{name}", f"SSD {name}", u, 90, 60, 72, temp, d, temp_status(temp, 60, 72))

        bat = sensors.battery()
        self.batt_card.set_visible(bat is not None)
        if bat:
            status = {"Charging": _("charging"), "Discharging": _("on battery"), "Full": _("plugged in, full"),
                      "Not charging": _("plugged in, not charging")}.get(bat["status"], bat["status"] or "")
            self.batt_big.set_label(f"{bat['percent']}%" if bat["percent"] is not None else "—")
            self.batt_state.set_label(status)
            if bat["health"] is not None:
                h = bat["health"]
                self.health_label.set_label(f"{h:.0f}%")
                self.health_bar.set_value(min(1, h / 100))
                note = ""
                if bat.get("wh_full") and bat.get("wh_design"):
                    note = _("{full} of {design} Wh when new. ").format(full=f"{bat['wh_full']:.0f}", design=f"{bat['wh_design']:.0f}")
                if h < 80:
                    note += _("Worn: cap the charge level on the Power page.")
                self.health_note.set_label(note)

    def refresh_disks(self):
        child = self.disk_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.disk_box.remove(child)
            child = nxt
        self.drawings = [d for d in self.drawings if not isinstance(d, DiskRing)]
        worst = None
        for d in sensors.disks():
            for p in d["parts"]:
                frac = p["used"] / p["total"] if p["used"] is not None and p["total"] else None
                if frac is not None:
                    worst = frac if worst is None else max(worst, frac)
                self.disk_box.append(self.disk_tile(d, p, frac))
        for c in ("ok", "warn", "crit", "none"):
            self.disk_pill.remove_css_class(c)
        if worst is None:
            text, level = _("No mounted disks"), "none"
        elif worst >= 0.9:
            text, level = _("Risk: a disk is {pct}% full").format(pct=f"{worst * 100:.0f}"), "crit"
        elif worst >= 0.8:
            text, level = _("Warning: a disk is {pct}% full").format(pct=f"{worst * 100:.0f}"), "warn"
        else:
            text, level = _("No disk at risk"), "ok"
        self.disk_pill.set_label(text)
        self.disk_pill.add_css_class(level)

    def disk_tile(self, disk, part, frac):
        box = Gtk.Box(spacing=12)
        box.add_css_class("awc-inner")
        ring = DiskRing()
        ring.set(frac)
        self.drawings.append(ring)
        box.append(ring)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, valign=Gtk.Align.CENTER)
        kind = FS_NAMES.get(part["fstype"], part["fstype"] or "?")
        info.append(label(f"{kind}  {part['mount'] or ''}".strip(), "awc-opt-title"))
        info.append(label(disk["model"] or f"/dev/{disk['name']}", "awc-muted", "awc-small"))
        if frac is not None:
            free = part["total"] - part["used"]
            info.append(label(_("{used} of {total} · {free} free").format(
                used=sensors.human(part["used"]), total=sensors.human(part["total"]), free=sensors.human(free)),
                "awc-small", wrap=True))
            level = "crit" if frac >= 0.9 else "warn" if frac >= 0.8 else "ok"
            word = {"crit": _("Risk"), "warn": _("Warning"), "ok": _("OK")}[level]
        else:
            info.append(label(_("{size} · not mounted").format(size=sensors.human(part["size"])), "awc-small"))
            level, word = "none", _("No reading")
        pill = label(word, "awc-pill", level)
        pill.set_halign(Gtk.Align.START)
        info.append(pill)
        box.append(info)
        return box

    # ================= LIGHTING =================

    def build_lights(self):
        self.lcfg = lights.load()
        self.zone = "keyboard"
        self.worker = lights.Worker(lambda errs: GLib.idle_add(self._lights_done, errs))
        self.apply_source = None
        self.pending_parts = set()
        # AWC_DEMO (developer aid, used for the README recording): animate the drawing only,
        # never send anything to the lighting controllers.
        self.demo = "AWC_DEMO" in os.environ
        self.has_kbd = not self.demo and awkbd.find_device() is not None
        self.has_elc = not self.demo and awelc.find_device() is not None

        page = Gtk.Box()
        overlay = Gtk.Overlay(hexpand=True)
        self.laptop = LaptopView(self.select_zone)
        self.drawings.append(self.laptop)
        overlay.set_child(self.laptop)
        tl = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, halign=Gtk.Align.START,
                     valign=Gtk.Align.START, margin_top=20, margin_start=24)
        tl.append(label(_("VIEW"), "awc-muted", "awc-small"))
        self.view_label = label(_("Front"), "awc-title")
        tl.append(self.view_label)
        tl.append(label(_("Click a light on the drawing to edit it"), "awc-muted", "awc-small"))
        overlay.add_overlay(tl)
        self.view_box = tl
        rotate_btn = Gtk.Button(halign=Gtk.Align.CENTER, valign=Gtk.Align.END, margin_bottom=22)
        rb = Gtk.Box(spacing=10)
        rb.append(Gtk.Image.new_from_gicon(Gio.ThemedIcon.new_from_names(
            ["object-rotate-right-symbolic", "view-refresh-symbolic", "media-playlist-repeat-symbolic"])))
        self.rotate_label = Gtk.Label(label=_("Show the back"))
        rb.append(self.rotate_label)
        rotate_btn.set_child(rb)
        rotate_btn.add_css_class("awc-rotate")
        rotate_btn.connect("clicked", lambda *_: self.rotate_laptop())
        overlay.add_overlay(rotate_btn)
        # paint mode tools, right next to the drawing
        self.paint_bar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, halign=Gtk.Align.CENTER,
                                 valign=Gtk.Align.START, margin_top=14)
        self.paint_bar.add_css_class("awc-card")
        self.paint_bar.add_css_class("awc-paintbar")
        brush_row = Gtk.Box(spacing=6)
        brush_row.append(label(_("Brush"), "awc-opt-title"))
        self.brush_btn = self.brush_button()
        brush_row.append(self.brush_btn)
        for name, rgb in PRESETS:
            btn = Gtk.Button(child=Swatch(rgb, 22, 22, 11), tooltip_text=_(name))
            btn.add_css_class("awc-swatch")
            btn.add_css_class("flat")
            btn.connect("clicked", lambda _b, c=rgb: self.brush_set(c))
            brush_row.append(btn)
        self.paint_bar.append(brush_row)
        tools = Gtk.Box(spacing=6, homogeneous=True)
        self.eraser = Gtk.ToggleButton(label=_("Eraser"))
        fill = Gtk.Button(label=_("Fill all"))
        fill.connect("clicked", lambda *_: self.paint_fill(True))
        clear = Gtk.Button(label=_("Clear"))
        clear.connect("clicked", lambda *_: self.paint_fill(False))
        for w in (self.eraser, fill, clear):
            tools.append(w)
        self.paint_bar.append(tools)
        overlay.add_overlay(self.paint_bar)
        page.append(overlay)

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16, margin_top=20, margin_bottom=20,
                       margin_start=20, margin_end=20)
        side_wrap = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, child=side)
        side_wrap.set_size_request(410, -1)

        self.slot = "color"
        self.fx_buttons = {}
        self.fx_previews = []

        side.append(label(_("Scenes"), "awc-opt-title"))
        scenes = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4,
                             min_children_per_line=4, column_spacing=6, row_spacing=6, homogeneous=True)
        for name, zones, brightness in SCENES:
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            shown = [lights.scaled(zones[z][1], max(brightness, 25)) for z in lights.ZONES]
            swatch = SceneSwatch(shown)
            swatch.set_halign(Gtk.Align.CENTER)
            box.append(swatch)
            box.append(label(_(name), "awc-small", xalign=0.5))
            btn = Gtk.Button(child=box)
            btn.add_css_class("awc-fx")
            btn.connect("clicked", self.scene_clicked, zones, brightness)
            scenes.append(btn)
        side.append(scenes)

        self.zone_seg = Segmented([("keyboard", "Keyboard"), ("power", "Power button"), ("logo", "Logo"),
                                   ("rear", "Rear")],
                                  self.select_zone)
        self.zone_seg.add_css_class("awc-seg-compact")
        side.append(self.zone_seg)

        wheel_row = Gtk.Box(spacing=18)
        self.wheel = ColorWheel(self.wheel_changed, size=176)
        self.drawings.append(self.wheel)
        wheel_row.append(self.wheel)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER)
        self.big_swatch = Swatch((0, 0, 0), 110, 52, 14)
        info.append(self.big_swatch)
        self.hex_label = label("#000000", "awc-title")
        self.hex_label.set_selectable(True)
        info.append(self.hex_label)
        self.rgb_label = label("", "awc-muted", "awc-small")
        info.append(self.rgb_label)
        wheel_row.append(info)
        side.append(wheel_row)
        self.fixed_note = label(_("This effect has its own colours. Brightness still applies."),
                                "awc-muted", "awc-small", wrap=True)
        side.append(self.fixed_note)

        brow = Gtk.Box()
        brow.append(label(_("Brightness"), "awc-opt-title"))
        self.bright_label = label("", "awc-muted", xalign=1)
        self.bright_label.set_hexpand(True)
        brow.append(self.bright_label)
        side.append(brow)
        self.bright = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.bright.set_draw_value(False)
        self.bright.connect("value-changed", self.bright_changed)
        # The panel scrolls; without this, scrolling past the slider would change the brightness.
        no_scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
        no_scroll.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        no_scroll.connect("scroll", lambda *_: True)
        self.bright.add_controller(no_scroll)
        side.append(self.bright)

        side.append(label(_("Quick colours"), "awc-opt-title"))
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=8,
                           min_children_per_line=4, column_spacing=8, row_spacing=8)
        for name, rgb in PRESETS:
            btn = Gtk.Button(child=Swatch(rgb), tooltip_text=_(name))
            btn.add_css_class("awc-swatch")
            btn.add_css_class("flat")
            btn.connect("clicked", self.preset_clicked, rgb)
            flow.append(btn)
        side.append(flow)

        erow = Gtk.Box()
        erow.append(label(_("Effect"), "awc-opt-title"))
        hint = label(_("hover to preview"), "awc-muted", "awc-small", xalign=1)
        hint.set_hexpand(True)
        erow.append(hint)
        side.append(erow)
        self.effect_grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3,
                                       min_children_per_line=3, column_spacing=6, row_spacing=6,
                                       homogeneous=True)
        side.append(self.effect_grid)

        # options of the selected effect: its two colours, each with a name and its own picker
        self.color_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.color_panel.add_css_class("awc-inner")
        self.panel_title = label("", "awc-opt-title")
        self.color_panel.append(self.panel_title)
        self.panel_labels, self.panel_buttons = {}, {}
        for key in ("color", "color2"):
            row = Gtk.Box(spacing=10)
            lb = label("", "awc-small")
            lb.set_hexpand(True)
            row.append(lb)
            btn = self.color_button(key)
            row.append(btn)
            self.color_panel.append(row)
            self.panel_labels[key], self.panel_buttons[key] = lb, btn
        side.append(self.color_panel)

        # paint mode: brush tools
        self.paint_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.paint_panel.add_css_class("awc-inner")
        self.paint_panel.append(label(_("Paint keys"), "awc-opt-title"))
        hint = label(_("Pick a brush colour in the bar above the drawing, then click or drag over the keys."),
                     "awc-muted", "awc-small", wrap=True)
        hint.set_max_width_chars(42)
        self.paint_panel.append(hint)
        side.append(self.paint_panel)
        self.paint_pending = {}
        self.paint_source = None
        self.paint_lock = threading.Lock()
        self.laptop.on_paint = self.paint_keys

        self.speed_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.speed_box.append(label(_("Speed"), "awc-opt-title"))
        self.speed_seg = Segmented(SPEED_NAMES, self.speed_changed)
        self.speed_box.append(self.speed_seg)
        side.append(self.speed_box)

        all_btn = Gtk.Button(label=_("Use this colour on all lights"), margin_top=6)
        all_btn.connect("clicked", self.apply_all_clicked)
        side.append(all_btn)
        self.lights_status = label("", "awc-muted", "awc-small", wrap=True)
        side.append(self.lights_status)
        if self.demo:
            pass
        elif not (self.has_kbd or self.has_elc):
            self.lights_status.set_label(_("No Alienware lighting controller found: preview only."))
        elif not self.has_kbd:
            self.lights_status.set_label(_("Keyboard lighting controller not found on this computer."))
        elif not self.has_elc:
            self.lights_status.set_label(_("Power button / logo controller not found on this computer."))

        page.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        page.append(side_wrap)

        self.select_zone("keyboard", rotate=False)
        return page

    def rotate_laptop(self, to_back=None):
        back = (not self.laptop.showing_back) if to_back is None else to_back
        self.laptop.rotate(back)
        self.view_label.set_label(_("Back") if back else _("Front"))
        self.rotate_label.set_label(_("Show the front") if back else _("Show the back"))

    def select_zone(self, zone, rotate=True):
        self.zone = zone
        self.zone_seg.select(zone)
        self.laptop.selected = zone
        if rotate:
            back_zones = ("logo", "rear")
            if zone in back_zones and not self.laptop.showing_back:
                self.rotate_laptop(True)
            elif zone not in back_zones and self.laptop.showing_back:
                self.rotate_laptop(False)
        self.slot = "color"
        self.build_effect_grid()
        self.load_color_controls()

    # ----- effect gallery -----

    def build_effect_grid(self):
        """One tile per effect the selected light supports, each with a live preview."""
        for pv in self.fx_previews:
            pv.play(False)
        child = self.effect_grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.effect_grid.remove(child)
            child = nxt
        self.fx_buttons, self.fx_previews = {}, []
        first = None
        for effect in fx.effects_for(self.zone):
            preview = EffectPreview(self.zone, effect.key)
            preview.set_halign(Gtk.Align.CENTER)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            box.append(preview)
            box.append(label(_(effect.label), "awc-small", xalign=0.5))
            btn = Gtk.ToggleButton(child=box)
            btn.add_css_class("awc-fx")
            if first:
                btn.set_group(first)
            first = first or btn
            motion = Gtk.EventControllerMotion()
            motion.connect("enter", lambda _c, _x, _y, p=preview: p.play(True))
            motion.connect("leave", lambda _c, p=preview: p.play(False))
            btn.add_controller(motion)
            btn.connect("toggled", self.effect_toggled, effect.key)
            self.effect_grid.append(btn)
            self.fx_buttons[effect.key] = btn
            self.fx_previews.append(preview)
        self.sync_effect_controls()

    def color_button(self, key):
        """A button showing one colour; clicking it opens the system colour picker."""
        if hasattr(Gtk, "ColorDialogButton"):  # GTK 4.10+
            btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
            btn.connect("notify::rgba", lambda b, _p: self.panel_color_changed(key, b.get_rgba()))
        else:
            btn = Gtk.ColorButton()
            btn.connect("color-set", lambda b: self.panel_color_changed(key, b.get_rgba()))
        btn.set_valign(Gtk.Align.CENTER)
        return btn

    def brush_button(self):
        if hasattr(Gtk, "ColorDialogButton"):
            btn = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False))
            btn.connect("notify::rgba", lambda b, _p: self._brush_picked(b.get_rgba()))
        else:
            btn = Gtk.ColorButton()
            btn.connect("color-set", lambda b: self._brush_picked(b.get_rgba()))
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_tooltip_text(_("Brush colour"))
        return btn

    def _brush_picked(self, rgba):
        if not self._loading:
            self.brush_set([int(round(c * 255)) for c in (rgba.red, rgba.green, rgba.blue)])

    def brush_set(self, rgb):
        """Paint mode brush = the keyboard's main colour."""
        self.lcfg["keyboard"]["color"] = list(rgb)
        self.eraser.set_active(False)
        if self.zone == "keyboard":
            self.load_color_controls()
        else:
            self.sync_effect_controls()
        try:
            lights.save(self.lcfg)
        except OSError:
            pass

    def panel_color_changed(self, key, rgba):
        if self._loading:
            return
        self.lcfg[self.zone][key] = [int(round(c * 255)) for c in (rgba.red, rgba.green, rgba.blue)]
        if key == "color":
            self.load_color_controls()
        else:
            self.update_color_info()
        self.schedule_apply(self.zone)

    def sync_effect_controls(self):
        state = self.lcfg[self.zone]
        effect = fx.BY_KEY[state["effect"]]
        self._loading = True
        if effect.key in self.fx_buttons:
            self.fx_buttons[effect.key].set_active(True)
        self.speed_seg.select(state["speed"])
        for key, btn in self.panel_buttons.items():
            rgba = Gdk.RGBA()
            rgba.red, rgba.green, rgba.blue, rgba.alpha = (*(c / 255 for c in state[key]), 1.0)
            btn.set_rgba(rgba)
        self._loading = False
        self.speed_box.set_visible(effect.speed)
        painting = self.zone == "keyboard" and effect.key == "paint"
        self.paint_panel.set_visible(painting)
        self.paint_bar.set_visible(self.lcfg["keyboard"]["effect"] == "paint")
        self.view_box.set_visible(self.lcfg["keyboard"]["effect"] != "paint")
        self._loading = True
        brush = Gdk.RGBA()
        brush.red, brush.green, brush.blue, brush.alpha = (*(c / 255 for c in self.lcfg["keyboard"]["color"]), 1.0)
        self.brush_btn.set_rgba(brush)
        self._loading = False
        self.laptop.paint = self.lcfg["keyboard"]["effect"] == "paint"
        self.laptop.painted = {int(k): tuple(v) for k, v in self.lcfg["keyboard"].get("keys", {}).items()}
        self.color_panel.set_visible(effect.colors == 2)
        self.panel_title.set_label(_("{effect} options").format(effect=_(effect.label)))
        names = (("Ring colour", "Resting keys colour") if effect.key == "ripple"
                 else ("Colour 1", "Colour 2"))
        self.panel_labels["color"].set_label(_(names[0]))
        self.panel_labels["color2"].set_label(_(names[1]))
        if self.zone == "power":
            self.fixed_note.set_label(_("The power button LED has no blue: it shows red, green and their "
                                        "mixes (yellow, orange), and changes colour in steps."))
        else:
            self.fixed_note.set_label(_("This effect has its own colours. Brightness still applies."))
        self.fixed_note.set_visible(effect.colors == 0 or self.zone == "power")
        for pv in self.fx_previews:
            pv.set_colors(lights.led_color(self.zone, state["color"]),
                          lights.led_color(self.zone, state["color2"]), state["speed"])

    def effect_toggled(self, btn, key):
        if self._loading or not btn.get_active():
            return
        self.lcfg[self.zone]["effect"] = key
        if key == "ripple":
            # The ring only shows against dark keys: start with a dim version of colour 1.
            self.lcfg[self.zone]["color2"] = [int(c * 0.12) for c in self.lcfg[self.zone]["color"]]
        self.sync_effect_controls()
        self.update_color_info()
        self.schedule_apply(self.zone)

    # ----- paint mode -----

    def paint_keys(self, ids):
        """Called by the drawing while the pointer is over a key in paint mode."""
        keys = self.lcfg["keyboard"].setdefault("keys", {})
        color = None if self.eraser.get_active() else list(self.lcfg["keyboard"]["color"])
        for light in ids:
            if color is None:
                keys.pop(str(light), None)
                self.laptop.painted.pop(light, None)
            else:
                keys[str(light)] = color
                self.laptop.painted[light] = tuple(color)
            self.paint_pending[light] = tuple(color or (0, 0, 0))
        self.laptop.queue_draw()
        if self.paint_source is None:
            self.paint_source = GLib.timeout_add(70, self._paint_flush)

    def _paint_flush(self):
        self.paint_source = None
        items, self.paint_pending = list(self.paint_pending.items()), {}
        try:
            lights.save(self.lcfg)
        except OSError:
            pass
        if items and self.has_kbd:
            def send():
                with self.paint_lock:
                    errors = lights.paint_keys(items)
                if errors:
                    GLib.idle_add(self._lights_done, errors)
            threading.Thread(target=send, daemon=True).start()
        return False

    def paint_fill(self, filled):
        kb = self.lcfg["keyboard"]
        kb["keys"] = {str(i): list(kb["color"]) for i in keymap.IDS} if filled else {}
        self.sync_effect_controls()
        self.laptop.queue_draw()
        self.schedule_apply("keyboard")

    def speed_changed(self, speed):
        if self._loading:
            return
        self.lcfg[self.zone]["speed"] = speed
        self.sync_effect_controls()
        self.update_color_info()
        self.schedule_apply(self.zone)

    def scene_clicked(self, _btn, zones, brightness):
        for zone, (effect, c1, c2) in zones.items():
            effect = effect if fx.valid(zone, effect) else "static"
            self.lcfg[zone].update(effect=effect, color=list(c1), color2=list(c2),
                                   brightness=brightness, speed="normal")
        self.select_zone(self.zone, rotate=False)
        self.schedule_apply("keyboard")
        self.schedule_apply("power")

    # ----- colour controls -----

    def load_color_controls(self):
        state = self.lcfg[self.zone]
        h, sat, _v = colorsys.rgb_to_hsv(*(c / 255 for c in state[self.slot]))
        self._loading = True
        self.wheel.set_hsv(h, sat, state["brightness"] / 100)
        self.bright.set_value(state["brightness"])
        self._loading = False
        self.sync_effect_controls()
        self.update_color_info()

    def laptop_state(self):
        return {z: {"effect": st["effect"], "speed": st["speed"],
                    "color": lights.led_color(z, lights.scaled(st["color"], st["brightness"])),
                    "color2": lights.led_color(z, lights.scaled(st["color2"], st["brightness"]))}
                for z, st in self.lcfg.items()}

    def update_color_info(self):
        state = self.lcfg[self.zone]
        shown = lights.led_color(self.zone, lights.scaled(state[self.slot], state["brightness"]))
        self.big_swatch.set_rgb(shown)
        self.hex_label.set_label("#%02X%02X%02X" % shown)
        self.rgb_label.set_label("R %d  G %d  B %d" % shown)
        b = state["brightness"]
        self.bright_label.set_label(_("off") if b == 0 else f"{b}%")
        for pv in self.fx_previews:
            pv.set_colors(lights.led_color(self.zone, state["color"]),
                          lights.led_color(self.zone, state["color2"]), state["speed"])
        self.laptop.set_state(self.laptop_state())

    def wheel_changed(self):
        self.lcfg[self.zone][self.slot] = [int(round(c * 255))
                                           for c in colorsys.hsv_to_rgb(self.wheel.h, self.wheel.s, 1)]
        self.update_color_info()
        self.schedule_apply(self.zone)

    def bright_changed(self, scale):
        if self._loading:
            return
        v = int(scale.get_value())
        self.lcfg[self.zone]["brightness"] = v
        self.wheel.set_hsv(self.wheel.h, self.wheel.s, v / 100)
        self.update_color_info()
        self.schedule_apply(self.zone)

    def preset_clicked(self, _btn, rgb):
        self.lcfg[self.zone][self.slot] = list(rgb)
        if self.lcfg[self.zone]["brightness"] == 0:
            self.lcfg[self.zone]["brightness"] = 100
        self.load_color_controls()
        self.schedule_apply(self.zone)

    def apply_all_clicked(self, _btn):
        src = self.lcfg[self.zone]
        for z in lights.ZONES:
            self.lcfg[z]["color"] = list(src["color"])
            self.lcfg[z]["color2"] = list(src["color2"])
            self.lcfg[z]["brightness"] = src["brightness"]
        self.update_color_info()
        self.schedule_apply("keyboard")
        self.schedule_apply("power")

    def schedule_apply(self, zone):
        """Debounce: apply 450 ms after the last change, so dragging the wheel stays smooth."""
        self.pending_parts.add("keyboard" if zone == "keyboard" else "elc")
        if self.apply_source:
            GLib.source_remove(self.apply_source)
        self.apply_source = GLib.timeout_add(450, self._apply_now)

    def _apply_now(self):
        self.apply_source = None
        parts = tuple(p for p in self.pending_parts
                      if (p == "keyboard" and self.has_kbd) or (p == "elc" and self.has_elc))
        self.pending_parts.clear()
        try:
            lights.save(self.lcfg)
            sync_lights_autostart(self.cfg["login_lights"])
        except OSError as e:
            self.toast(_("Could not save the colours: {error}").format(error=e))
        if parts:
            self.lights_status.set_label(_("Applying…"))
            self.worker.request(self.lcfg, parts)
        return False

    def _lights_done(self, errors):
        self.lights_status.set_label(_("Error: {error}").format(error="; ".join(errors)) if errors else _("Applied to the laptop"))
        return False

    # ================= POWER =================

    def build_power(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16,
                       margin_top=22, margin_bottom=22, margin_start=22, margin_end=22)
        self.has_ppd = shutil.which("powerprofilesctl") is not None
        prof = card("Power profile", "applies instantly, no password" if self.has_ppd
                    else "power-profiles-daemon is not installed")
        self.profile_group = OptionGroup(PROFILES, 3, self.set_profile)
        self.profile_group.set_sensitive(self.has_ppd)
        prof.append(self.profile_group)
        page.append(prof)

        row = Gtk.Box(spacing=16, homogeneous=True)
        therm = card("Thermal mode", "BIOS")
        self.thermal_group = OptionGroup(THERMAL, 2, lambda k: self.write_bios(
            ["bios", "AWThermalManagement", k], _("Thermal mode saved")))
        therm.append(self.thermal_group)
        turbo = Gtk.Box(spacing=12)
        turbo.add_css_class("awc-inner")
        tcol = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
        tcol.append(label(_("Turbo Boost"), "awc-opt-title"))
        tcol.append(label(_("Turning it off runs much cooler, but the CPU is slower in bursts"),
                          "awc-muted", "awc-small", wrap=True))
        turbo.append(tcol)
        self.turbo_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.turbo_switch.connect("notify::active", self.turbo_toggled)
        turbo.append(self.turbo_switch)
        therm.append(turbo)
        row.append(therm)

        charge = card("Battery charging", "BIOS")
        self.charge_group = OptionGroup(CHARGE, 2, lambda k: self.write_bios(
            ["bios", "PrimaryBattChargeCfg", k], _("Charging mode saved")))
        charge.append(self.charge_group)
        self.custom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.custom_box.add_css_class("awc-inner")
        self.custom_box.set_visible(False)
        self.custom_spins = {}
        for attr, title in (("CustomChargeStart", "Start charging below (%)"),
                            ("CustomChargeStop", "Stop charging at (%)")):
            r = Gtk.Box(spacing=10)
            lb = label(_(title), "awc-small")
            lb.set_hexpand(True)
            r.append(lb)
            spin = Gtk.SpinButton.new_with_range(0, 100, 1)
            r.append(spin)
            btn = Gtk.Button(label=_("Apply"))
            btn.add_css_class("suggested-action")
            btn.connect("clicked", self.custom_clicked, attr, spin)
            r.append(btn)
            self.custom_box.append(r)
            self.custom_spins[attr] = spin
        charge.append(self.custom_box)
        row.append(charge)
        page.append(row)
        self.bios_cards = (therm, charge)
        return self.scrolled(page)

    def custom_clicked(self, _btn, attr, spin):
        value = int(spin.get_value())
        self.write_bios(["bios", attr, str(value)], _("Saved: {value}%").format(value=value))

    def load_power_profile(self):
        if not self.has_ppd:
            return
        try:
            cur = subprocess.run(["powerprofilesctl", "get"], capture_output=True, text=True, timeout=3).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return
        self.profile_group.select(cur)

    def set_profile(self, key):
        try:
            ok = subprocess.run(["powerprofilesctl", "set", key], capture_output=True, timeout=5).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ok = False
        if ok:
            self.toast(_("Power profile: {name}").format(name=_({k: t for k, t, _d in PROFILES}[key])))
        else:
            self.toast(_("Could not change the power profile"))
            self.load_power_profile()

    def bios_available(self):
        return os.path.exists(READ_HELPER) and os.path.exists(WRITE_HELPER) and os.path.isdir(SYSMAN)

    def load_bios(self):
        if not self.bios_available():
            for c in self.bios_cards:
                c.set_sensitive(False)
            if os.path.isdir(SYSMAN):
                self.banner.set_title(_("BIOS settings are off: run the installer once"))
                self.banner.set_button_label(_("How to install"))
                self.banner.set_revealed(True)
            return
        # Async, so a missing polkit agent or a slow prompt never freezes the window.
        try:
            proc = Gio.Subprocess.new(["pkexec", READ_HELPER],
                                      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
        except GLib.Error:
            self._bios_failed()
            return
        proc.communicate_utf8_async(None, None, self._bios_read_done)

    def _bios_failed(self):
        self.bios = None
        for c in self.bios_cards:
            c.set_sensitive(False)
        self.toast(_("Could not read the BIOS settings"))

    def _bios_read_done(self, proc, res):
        try:
            _ok, out, _err = proc.communicate_utf8_finish(res)
            bios = json.loads(out or "")
            if not isinstance(bios, dict):
                raise ValueError
        except (GLib.Error, ValueError):
            self._bios_failed()
            return
        self.bios = bios

        def attr(name):
            info = bios.get(name)
            return info if isinstance(info, dict) else {}

        self._show_bios_group(self.thermal_group, attr("AWThermalManagement"), self.bios_cards[0])
        charge = attr("PrimaryBattChargeCfg")
        self._show_bios_group(self.charge_group, charge, self.bios_cards[1])
        turbo = attr("TurboMode")
        self.turbo_switch.set_sensitive(turbo.get("value") in ("Enabled", "Disabled"))
        self._turbo_loading = True
        self.turbo_switch.set_active(turbo.get("value") == "Enabled")
        self._turbo_loading = False
        self.custom_box.set_visible(charge.get("value") == "Custom")
        for name, spin in self.custom_spins.items():
            info = attr(name)
            try:
                spin.set_range(int(info.get("min") or 0), int(info.get("max") or 100))
                spin.set_value(int(info.get("value") or 0))
            except ValueError:
                pass
        if bios.get("pending_reboot"):
            self.banner.set_title(_("BIOS setting saved. Restart the computer to apply it."))
            self.banner.set_button_label("")
            self.banner.set_revealed(True)
        else:
            self.banner.set_revealed(False)

    @staticmethod
    def _show_bios_group(group, info, card_widget):
        """Show only the options this BIOS reports; disable the card when the setting is missing."""
        value = info.get("value")
        possible = info.get("possible") or []
        card_widget.set_sensitive(value is not None)
        if possible:
            group.show_only(possible)
        group.select(value)

    def turbo_toggled(self, sw, _p):
        if self._turbo_loading or not self.bios:
            return
        value = "Enabled" if sw.get_active() else "Disabled"
        if value != self.bios["TurboMode"]["value"]:
            self.write_bios(["bios", "TurboMode", value], _("Turbo on") if value == "Enabled" else _("Turbo off"))

    def write_bios(self, args, success):
        if not self.bios:
            return
        try:
            proc = Gio.Subprocess.new(["pkexec", WRITE_HELPER, *args],
                                      Gio.SubprocessFlags.STDERR_PIPE | Gio.SubprocessFlags.STDOUT_SILENCE)
        except GLib.Error as e:
            self.toast(_("Error: {error}").format(error=e.message))
            return

        def done(p, res):
            try:
                _, _, err = p.communicate_utf8_finish(res)
            except GLib.Error:
                err = ""
            code = p.get_exit_status()
            if code == 0:
                self.toast(success)
            elif code in (126, 127):
                self.toast(_("Cancelled: password not confirmed"))
            else:
                lines = (err or "").strip().splitlines()
                self.toast(lines[-1] if lines else _("Failed"))
            self.load_bios()
        proc.communicate_utf8_async(None, None, done)

    def show_install_help(self):
        dialog = Adw.MessageDialog(transient_for=self, heading=_("Install the helpers"),
                                   body=_("Open the project folder and double-click Install "
                                          "(or run: sudo installer/install.sh).\n\nThen open Alienware Control again."))
        dialog.add_response("ok", _("OK"))
        dialog.present()


# ================= SETTINGS =================

class ThemePreview(Gtk.DrawingArea):
    def __init__(self, key, window):
        super().__init__()
        self.key, self.window = key, window
        self.set_content_width(190)
        self.set_content_height(104)
        self.set_draw_func(self.draw)

    def draw(self, area, cr, w, h):
        if self.key in theme.PALETTES:
            p = theme.PALETTES[self.key]

            def hexc(k):
                return tuple(int(p[k][i:i + 2], 16) / 255 for i in (1, 3, 5))
            bg, bar, cardc = hexc("window_bg_color"), hexc("headerbar_bg_color"), hexc("card_bg_color")
            acc, fg = hexc("accent_color"), hexc("window_fg_color")
        else:
            pal = theme.palette(self.window)
            bg, cardc, acc, fg = pal["bg"][:3], pal["card"][:3], pal["accent"][:3], pal["fg"][:3]
            bar = bg
        rounded(cr, 0, 0, w, h, 10)
        cr.set_source_rgb(*bg)
        cr.fill_preserve()
        cr.set_source_rgba(*fg, 0.15)
        cr.set_line_width(1)
        cr.stroke()
        cr.set_source_rgb(*bar)
        cr.rectangle(1, 1, w - 2, 17)
        cr.fill()
        cw = (w - 32) / 3
        for i in range(3):
            x = 8 + i * (cw + 8)
            rounded(cr, x, 26, cw, 48, 8)
            cr.set_source_rgb(*cardc)
            cr.fill_preserve()
            cr.set_source_rgba(*fg, 0.12)
            cr.stroke()
            cr.set_source_rgb(*acc)
            cr.set_line_width(4)
            cr.arc(x + cw / 2, 50, 11, 2.4, 6.4)
            cr.stroke()
            cr.set_line_width(1)
        cr.set_source_rgba(*fg, 0.25)
        rounded(cr, 8, 84, w * 0.45, 8, 4)
        cr.fill()


class SettingsWindow(Adw.PreferencesWindow):
    def __init__(self, win):
        super().__init__(transient_for=win, modal=True, title=_("Settings"), search_enabled=False)
        self.win = win
        self.cfg = win.cfg
        self.set_default_size(760, 720)
        page = Adw.PreferencesPage()
        self.add(page)

        g = Adw.PreferencesGroup(title=_("Theme"), description=_("Applies to every page of the app"))
        row = Gtk.Box(spacing=12, homogeneous=True)
        first = None
        self.previews = []
        for key, desc in (("gtk", "Follows your Linux theme"),
                          ("neon", "Midnight blue, cyan and violet"),
                          ("amoled", "Pure black, cyan highlights")):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            pv = ThemePreview(key, win)
            self.previews.append(pv)
            box.append(pv)
            box.append(label(_(theme.THEME_NAMES[key]), "awc-opt-title"))
            box.append(label(_(desc), "awc-muted", "awc-small", wrap=True))
            btn = Gtk.ToggleButton(child=box)
            btn.add_css_class("awc-opt")
            if first:
                btn.set_group(first)
            first = first or btn
            btn.set_active(self.cfg["theme"] == key)
            btn.connect("toggled", self.theme_toggled, key)
            row.append(btn)
        g.add(row)
        self.source_label = label("", "awc-muted", "awc-small", wrap=True)
        self.source_label.set_margin_top(10)
        g.add(self.source_label)
        page.add(g)
        self.update_source()

        g2 = Adw.PreferencesGroup(title=_("General"))
        login = Adw.ActionRow(title=_("Re-apply lighting at login"),
                              subtitle=_("Keyboard, power button and logo come back with your colours"))
        sw = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.cfg["login_lights"])
        sw.connect("notify::active", self.login_toggled)
        login.add_suffix(sw)
        login.set_activatable_widget(sw)
        g2.add(login)
        interval = Adw.ComboRow(title=_("Refresh the gauges every"), model=Gtk.StringList.new(["1 s", "2 s", "5 s"]))
        interval.set_selected({1: 0, 2: 1, 5: 2}[self.cfg["interval"]])
        interval.connect("notify::selected", self.interval_changed)
        g2.add(interval)
        unit = Adw.ComboRow(title=_("Temperature unit"), model=Gtk.StringList.new(["Celsius (°C)", "Fahrenheit (°F)"]))
        unit.set_selected(1 if self.cfg["unit"] == "F" else 0)
        unit.connect("notify::selected", self.unit_changed)
        g2.add(unit)
        self.lang_keys = ["auto", *i18n.LANGUAGES]
        lang = Adw.ComboRow(title=_("Language"), model=Gtk.StringList.new(
            [_("Automatic (system)"), *i18n.LANGUAGES.values()]))
        lang.set_selected(self.lang_keys.index(self.cfg["language"]))
        lang.connect("notify::selected", self.language_changed)
        g2.add(lang)
        page.add(g2)

        g3 = Adw.PreferencesGroup(
            title=_("Disk space alert"),
            description=_("When the Linux disk fills up, apps can crash or lose data, updates can fail "
                          "and the desktop may not start. Get a notification before that happens."))
        alert = Adw.ActionRow(title=_("Warn when a Linux disk is almost full"),
                              subtitle=_("Checks every 10 minutes in the background, even with the app closed"))
        alert_sw = Gtk.Switch(valign=Gtk.Align.CENTER, active=self.cfg["disk_alert"])
        alert_sw.connect("notify::active", self.alert_toggled)
        alert.add_suffix(alert_sw)
        alert.set_activatable_widget(alert_sw)
        g3.add(alert)
        self.threshold_row = Adw.ActionRow(title=_("Warn at"), subtitle=_("Percentage of the disk in use"))
        spin = Gtk.SpinButton.new_with_range(50, 99, 1)
        spin.set_valign(Gtk.Align.CENTER)
        spin.set_value(self.cfg["disk_threshold"])
        spin.connect("value-changed", self.threshold_changed)
        self.threshold_row.add_suffix(spin)
        self.threshold_row.add_suffix(label("%", "awc-muted"))
        self.threshold_row.set_sensitive(self.cfg["disk_alert"])
        g3.add(self.threshold_row)
        test = Adw.ActionRow(title=_("Send a test notification"))
        test_btn = Gtk.Button(label=_("Test"), valign=Gtk.Align.CENTER)
        test_btn.connect("clicked", self.test_notification)
        test.add_suffix(test_btn)
        g3.add(test)
        page.add(g3)

        g4 = Adw.PreferencesGroup(title=_("About"))
        g4.add(Adw.ActionRow(
            title=f"Alienware Control for Linux {VERSION}",
            subtitle=" · ".join([
                _(sensors.machine()),
                _("keyboard lighting: {state}").format(state=_("found") if win.has_kbd else _("not found")),
                _("power button/logo: {state}").format(state=_("found") if win.has_elc else _("not found"))])))
        page.add(g4)

    def save(self):
        theme.save_config(self.cfg)

    def update_source(self):
        is_gtk = self.cfg["theme"] == "gtk"
        self.source_label.set_visible(is_gtk)
        if is_gtk:
            self.source_label.set_label(_("Detected theme: {source}").format(source=self.win.app.themes.source))

    def theme_toggled(self, btn, key):
        if not btn.get_active():
            return
        self.cfg["theme"] = key
        self.save()
        self.win.app.themes.apply(key)
        self.win.redraw()
        for p in self.previews:
            p.queue_draw()
        self.update_source()

    def login_toggled(self, sw, _p):
        self.cfg["login_lights"] = sw.get_active()
        self.save()
        sync_lights_autostart(sw.get_active())

    def interval_changed(self, row, _p):
        self.cfg["interval"] = (1, 2, 5)[row.get_selected()]
        self.save()
        self.win.restart_timer()

    def unit_changed(self, row, _p):
        self.cfg["unit"] = "F" if row.get_selected() == 1 else "C"
        self.save()
        self.win.refresh_sensors()

    def language_changed(self, row, _p):
        choice = self.lang_keys[row.get_selected()]
        if choice == self.cfg["language"]:
            return
        self.cfg["language"] = choice
        self.save()
        i18n.setup(choice)
        self.close()
        GLib.idle_add(self.win.app.rebuild_window)

    def alert_toggled(self, sw, _p):
        self.cfg["disk_alert"] = sw.get_active()
        self.save()
        self.threshold_row.set_sensitive(sw.get_active())
        sync_disk_watch(sw.get_active())

    def threshold_changed(self, spin):
        self.cfg["disk_threshold"] = int(spin.get_value())
        self.save()

    def test_notification(self, _btn):
        if not diskwatch.notify(*diskwatch.message("/", self.cfg["disk_threshold"] / 100 + 0.01, 20 * 1024 ** 3)):
            self.add_toast(Adw.Toast(title=_("No notification service found in this session")))


class App(Adw.Application):
    def __init__(self):
        # AWC_PAGE (developer aid) also allows a second, independent instance for screenshots.
        flags = Gio.ApplicationFlags.NON_UNIQUE if "AWC_PAGE" in os.environ else Gio.ApplicationFlags.FLAGS_NONE
        super().__init__(application_id=APP_ID, flags=flags)
        self.cfg = theme.load_config()
        i18n.setup(self.cfg["language"])
        self.themes = None

    def do_activate(self):
        win = self.props.active_window
        if not win:
            self.themes = theme.ThemeManager()
            self.themes.apply(self.cfg["theme"])
            sync_lights_autostart(self.cfg["login_lights"])
            sync_disk_watch(self.cfg["disk_alert"])
            win = Window(self)
        win.present()

    def rebuild_window(self):
        """Recreate the main window (after a language change) on the same page."""
        old = self.props.active_window
        page = old.stack.get_visible_child_name() if old else "dashboard"
        win = Window(self)
        win.stack.set_visible_child_name(page)
        win.present()
        if old:
            old.stop_timers()
            old.destroy()
        return False


def main():
    return App().run(None)


if __name__ == "__main__":
    sys.exit(main())
