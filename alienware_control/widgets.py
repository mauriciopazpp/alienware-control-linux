"""Cairo-drawn widgets: dial gauge, disk ring, colour wheel and the laptop illustration."""
import colorsys
import math

import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Adw, GLib, Gtk, Pango, PangoCairo  # noqa: E402

import fx  # noqa: E402
import theme  # noqa: E402

FONT = "Inter, Cantarell, Noto Sans, Sans"


def text(cr, s, x, y, size, weight="Bold", color=(1, 1, 1, 1), align="center"):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription.from_string(f"{FONT} {weight} {size}"))
    layout.set_text(s, -1)
    w, h = layout.get_pixel_size()
    dx = {"center": w / 2, "left": 0, "right": w}[align]
    cr.set_source_rgba(*color)
    cr.move_to(x - dx, y - h / 2)
    PangoCairo.show_layout(cr, layout)


def rgba(c, a):
    return (c[0], c[1], c[2], a)


def rounded(cr, x, y, w, h, r):
    r = min(r, w / 2, h / 2)
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


class Animated:
    """Number that eases towards its target value."""

    def __init__(self, widget, on_change):
        self.value = 0.0
        self.anim = None
        self.widget = widget
        self.on_change = on_change

    def go(self, target):
        if self.anim:
            self.anim.pause()
        start = self.value
        target_cb = Adw.CallbackAnimationTarget.new(self._set)
        self.anim = Adw.TimedAnimation.new(self.widget, start, target, 700, target_cb)
        self.anim.set_easing(Adw.Easing.EASE_OUT_CUBIC)
        self.anim.play()

    def _set(self, v):
        self.value = v
        self.on_change()


# ---------- dial gauge (car dashboard style) ----------

class Gauge(Gtk.DrawingArea):
    START, SWEEP = math.radians(135), math.radians(270)

    def __init__(self, label, unit, maximum, warn=None, crit=None, size=150):
        super().__init__()
        self.label, self.unit, self.maximum = label, unit, maximum
        self.warn, self.crit = warn, crit
        self.display = "—"
        self.status = ""
        self.anim = Animated(self, self.queue_draw)
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self.draw)

    def set(self, value, display, status=""):
        self.display, self.status = display, status
        if value is None:
            self.anim.go(0)
        else:
            self.anim.go(max(0.0, min(1.0, value / self.maximum)))
        self.queue_draw()

    def level_color(self, pal, frac):
        v = frac * self.maximum
        if self.crit is not None and v >= self.crit:
            return pal["crit"]
        if self.warn is not None and v >= self.warn:
            return pal["warn"]
        return pal["accent"]

    def draw(self, area, cr, w, h):
        pal = theme.palette(self)
        cx, cy = w / 2, h / 2 + 6
        r = min(w, h) / 2 - 12
        cr.set_line_cap(cairo.LINE_CAP_ROUND)

        cr.set_line_width(11)
        cr.set_source_rgba(*rgba(pal["fg"], 0.08))
        cr.arc(cx, cy, r, self.START, self.START + self.SWEEP)
        cr.stroke()

        # tick marks
        cr.set_line_width(1.5)
        for i in range(11):
            a = self.START + self.SWEEP * i / 10
            inner = r - 14 if i % 5 == 0 else r - 10
            cr.set_source_rgba(*rgba(pal["fg"], 0.22 if i % 5 == 0 else 0.10))
            cr.move_to(cx + math.cos(a) * inner, cy + math.sin(a) * inner)
            cr.line_to(cx + math.cos(a) * (r - 7), cy + math.sin(a) * (r - 7))
            cr.stroke()

        frac = self.anim.value
        if frac > 0.002:
            color = self.level_color(pal, frac)
            end = self.START + self.SWEEP * frac
            for width, alpha in ((22, 0.10), (16, 0.16)):  # glow
                cr.set_line_width(width)
                cr.set_source_rgba(*rgba(color, alpha))
                cr.arc(cx, cy, r, self.START, end)
                cr.stroke()
            cr.set_line_width(11)
            cr.set_source_rgba(*color)
            cr.arc(cx, cy, r, self.START, end)
            cr.stroke()
            cr.set_source_rgba(*rgba(pal["fg"], 0.95))
            cr.arc(cx + math.cos(end) * r, cy + math.sin(end) * r, 3.2, 0, 2 * math.pi)
            cr.fill()

        text(cr, self.display, cx, cy - 6, 22, "Bold", pal["fg"])
        text(cr, self.unit, cx, cy + 20, 9, "Medium", rgba(pal["fg"], 0.6))
        text(cr, self.label, cx, h - 12, 10, "Bold", pal["fg"])


# ---------- disk usage ring ----------

class DiskRing(Gtk.DrawingArea):
    def __init__(self, size=96):
        super().__init__()
        self.frac = None
        self.anim = Animated(self, self.queue_draw)
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self.draw)

    def set(self, frac):
        self.frac = frac
        self.anim.go(frac or 0)

    def draw(self, area, cr, w, h):
        pal = theme.palette(self)
        cx, cy, r = w / 2, h / 2, min(w, h) / 2 - 8
        cr.set_line_width(9)
        cr.set_source_rgba(*rgba(pal["fg"], 0.08))
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()
        if self.frac is not None:
            color = pal["crit"] if self.frac >= 0.9 else pal["warn"] if self.frac >= 0.8 else pal["accent"]
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.set_source_rgba(*color)
            cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * max(self.anim.value, 0.001))
            cr.stroke()
            text(cr, f"{round(self.frac * 100)}%", cx, cy, 15, "Bold", pal["fg"])
        else:
            text(cr, "—", cx, cy, 15, "Bold", rgba(pal["fg"], 0.6))


# ---------- colour wheel ----------

class ColorWheel(Gtk.DrawingArea):
    """Hue on the angle, saturation on the radius. Brightness is set elsewhere (slider)."""

    def __init__(self, on_change, size=220):
        super().__init__()
        self.h, self.s, self.v = 0.53, 0.78, 1.0
        self.on_change = on_change
        self.cache = None
        self.set_content_width(size)
        self.set_content_height(size)
        self.set_draw_func(self.draw)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._begin)
        drag.connect("drag-update", self._update)
        self.add_controller(drag)
        self._origin = (0, 0)

    def set_hsv(self, h, s, v):
        self.h, self.s, self.v = h, s, v
        self.queue_draw()

    def rgb(self):
        return tuple(int(round(c * 255)) for c in colorsys.hsv_to_rgb(self.h, self.s, self.v))

    def _pick(self, x, y):
        w, h = self.get_width(), self.get_height()
        r = min(w, h) / 2 - 8
        dx, dy = x - w / 2, y - h / 2
        self.h = (math.degrees(math.atan2(dx, -dy)) % 360) / 360
        self.s = min(1.0, math.hypot(dx, dy) / r)
        self.queue_draw()
        self.on_change()

    def _begin(self, gesture, x, y):
        self._origin = (x, y)
        self._pick(x, y)

    def _update(self, gesture, ox, oy):
        self._pick(self._origin[0] + ox, self._origin[1] + oy)

    def _wheel_surface(self, size):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        cr = cairo.Context(surf)
        c = r = size / 2
        steps = 360
        for i in range(steps):
            a0 = math.radians(i - 0.6) - math.pi / 2
            a1 = math.radians(i + 1.6) - math.pi / 2
            cr.move_to(c, c)
            cr.arc(c, c, r, a0, a1)
            cr.close_path()
            cr.set_source_rgb(*colorsys.hsv_to_rgb(i / steps, 1, 1))
            cr.fill()
        white = cairo.RadialGradient(c, c, 0, c, c, r)
        white.add_color_stop_rgba(0, 1, 1, 1, 1)
        white.add_color_stop_rgba(1, 1, 1, 1, 0)
        cr.set_source(white)
        cr.arc(c, c, r, 0, 2 * math.pi)
        cr.fill()
        return surf

    def draw(self, area, cr, w, h):
        pal = theme.palette(self)
        size = int(min(w, h) - 16)
        if size <= 0:
            return
        if not self.cache or self.cache[0] != size:
            self.cache = (size, self._wheel_surface(size))
        ox, oy = (w - size) / 2, (h - size) / 2
        cr.set_source_rgba(*rgba(pal["fg"], 0.06))
        cr.arc(w / 2, h / 2, size / 2 + 7, 0, 2 * math.pi)
        cr.fill()
        cr.save()
        cr.arc(w / 2, h / 2, size / 2, 0, 2 * math.pi)
        cr.clip()
        cr.set_source_surface(self.cache[1], ox, oy)
        cr.paint()
        cr.set_source_rgba(0, 0, 0, 1 - self.v)
        cr.paint()
        cr.restore()
        r = size / 2
        mx = w / 2 + math.sin(self.h * 2 * math.pi) * self.s * r
        my = h / 2 - math.cos(self.h * 2 * math.pi) * self.s * r
        red, green, blue = colorsys.hsv_to_rgb(self.h, self.s, self.v)
        cr.arc(mx, my, 12, 0, 2 * math.pi)
        cr.set_source_rgba(0, 0, 0, 0.45)
        cr.set_line_width(5)
        cr.stroke_preserve()
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(3)
        cr.stroke_preserve()
        cr.set_source_rgb(red, green, blue)
        cr.fill()


# ---------- laptop illustration ----------

KEY_ROWS = [
    (0.55, [1] * 16),
    (1, [1] * 13 + [2]),
    (1, [1.5] + [1] * 12 + [1.5]),
    (1, [1.75] + [1] * 10 + [2.25]),
    (1, [2.25] + [1] * 10 + [2.75]),
    (1, [1.25, 1, 1.25, 1.25, 6.25, 1.25, 1.25, 1, 1, 1]),
]


# Light ids under each key of the drawing (see keymap.py). The drawing is a generic laptop,
# so a few real keys share one drawn key.
KEY_IDS = [
    [[120 + i] for i in range(16)],
    [[20 + i] for i in range(13)] + [[35, 139]],
    [[40]] + [[42 + i] for i in range(12)] + [[54, 136]],
    [[61]] + [[62 + i] for i in range(10)] + [[72, 73, 138]],
    [[81, 82]] + [[83 + i] for i in range(10)] + [[94, 114, 137]],
    [[100], [101], [103], [104], [105, 106, 107, 108, 110], [111], [109], [112], [141], [142, 143]],
]


def lerp(a, b, t):
    return a + (b - a) * t


def quad_point(q, u, v):
    """Point (u, v) in 0..1 inside quad q = (top-left, top-right, bottom-right, bottom-left)."""
    tl, tr, br, bl = q
    top = (lerp(tl[0], tr[0], u), lerp(tl[1], tr[1], u))
    bot = (lerp(bl[0], br[0], u), lerp(bl[1], br[1], u))
    return lerp(top[0], bot[0], v), lerp(top[1], bot[1], v)


def quad_path(cr, pts):
    cr.move_to(*pts[0])
    for p in pts[1:]:
        cr.line_to(*p)
    cr.close_path()


class LaptopView(Gtk.DrawingArea):
    """Front (keyboard, power button) and back (lid logo) of a laptop, with an animated flip."""

    W, H = 600, 500

    def __init__(self, on_select):
        super().__init__()
        base = {"effect": "static", "color": (0, 160, 255), "color2": (138, 60, 255), "speed": "normal"}
        self.zones = {z: dict(base) for z in ("keyboard", "power", "logo", "rear")}
        self.selected = "keyboard"
        self.paint = False      # paint mode: keys show `painted` and can be clicked or dragged over
        self.painted = {}       # light id -> (r, g, b)
        self.on_paint = None    # callback(list of light ids)
        self.key_quads = []
        self._last_painted = None
        self._drag_origin = (0, 0)
        self.flip = 0.0  # 0 = front, 1 = back
        self.seconds = 0.0
        self._last_frame = 0
        self.on_select = on_select
        self.regions = {}
        self.anim = None
        self.tick_id = None
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_content_width(520)
        self.set_content_height(440)
        self.set_draw_func(self.draw)
        click = Gtk.GestureClick()
        click.connect("released", self._click)
        self.add_controller(click)
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._drag_begin)
        drag.connect("drag-update", self._drag_update)
        self.add_controller(drag)

    @property
    def showing_back(self):
        return self.flip >= 0.5

    def rotate(self, to_back=None):
        target = (0.0 if self.showing_back else 1.0) if to_back is None else (1.0 if to_back else 0.0)
        if abs(target - self.flip) < 1e-3:
            return
        if self.anim:
            self.anim.pause()
        cb = Adw.CallbackAnimationTarget.new(self._set_flip)
        self.anim = Adw.TimedAnimation.new(self, self.flip, target, 900, cb)
        self.anim.set_easing(Adw.Easing.EASE_IN_OUT_CUBIC)
        self.anim.play()

    def _set_flip(self, v):
        self.flip = v
        self.queue_draw()

    def set_state(self, zones):
        """zones: {zone: {"effect", "color", "color2", "speed"}}, colours already dimmed."""
        for zone, st in zones.items():
            self.zones[zone] = {"effect": st["effect"], "color": tuple(st["color"]),
                                "color2": tuple(st["color2"]), "speed": st["speed"]}
        animated = any(st["effect"] != "static" for st in self.zones.values())
        if animated and self.tick_id is None:
            self.tick_id = self.add_tick_callback(self._tick)
        elif not animated and self.tick_id is not None:
            self.remove_tick_callback(self.tick_id)
            self.tick_id = None
        self.queue_draw()

    def _tick(self, widget, clock):
        now = clock.get_frame_time()
        if now - self._last_frame >= 40000:  # about 25 fps is plenty, and keeps the CPU cool
            self._last_frame = now
            self.seconds = now / 1e6
            self.queue_draw()
        return True

    def _transform(self, w, h):
        s = min(w / self.W, h / self.H)
        return s, (w - self.W * s) / 2, (h - self.H * s) / 2

    def _to_drawing(self, x, y):
        s, ox, oy = self._transform(self.get_width(), self.get_height())
        sx = abs(math.cos(math.pi * self.flip)) or 1e-3
        mx = (x - ox) / s
        return self.W / 2 + (mx - self.W / 2) / sx, (y - oy) / s

    def _key_at(self, mx, my):
        for pts, ids in self.key_quads:
            inside = True
            for i in range(4):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % 4]
                if (x1 - x0) * (my - y0) - (y1 - y0) * (mx - x0) < 0:
                    inside = False
                    break
            if inside:
                return ids
        return None

    def _paint_at(self, x, y):
        if not (self.paint and self.on_paint) or self.showing_back:
            return
        ids = self._key_at(*self._to_drawing(x, y))
        if ids and ids is not self._last_painted:
            self._last_painted = ids
            self.on_paint(ids)

    def _drag_begin(self, gesture, x, y):
        self._drag_origin = (x, y)
        self._last_painted = None
        self._paint_at(x, y)

    def _drag_update(self, gesture, dx, dy):
        self._paint_at(self._drag_origin[0] + dx, self._drag_origin[1] + dy)

    def _click(self, gesture, n, x, y):
        mx, my = self._to_drawing(x, y)
        if self.paint and not self.showing_back and self._key_at(mx, my):
            return  # painting, not selecting
        for zone, (x0, y0, x1, y1) in self.regions.items():
            if x0 <= mx <= x1 and y0 <= my <= y1:
                self.on_select(zone)
                return

    def draw(self, area, cr, w, h):
        pal = theme.palette(self)
        s, ox, oy = self._transform(w, h)
        cr.translate(ox, oy)
        cr.scale(s, s)

        # background glow
        g = cairo.RadialGradient(self.W / 2, self.H * 0.55, 0, self.W / 2, self.H * 0.55, self.W * 0.6)
        g.add_color_stop_rgba(0, *rgba(pal["glow"], 0.9))
        g.add_color_stop_rgba(1, *rgba(pal["glow"], 0))
        cr.set_source(g)
        cr.paint()

        sx = math.cos(math.pi * self.flip)
        cr.save()
        cr.translate(self.W / 2, 0)
        cr.scale(max(abs(sx), 0.002), 1)
        cr.translate(-self.W / 2, 0)
        self.regions = {}
        if self.showing_back:
            self._draw_back(cr, pal)
        else:
            self._draw_front(cr, pal)
        cr.restore()
        # shading while flipping
        if 0.02 < self.flip < 0.98:
            cr.set_source_rgba(0, 0, 0, 0.35 * (1 - abs(sx)))
            cr.rectangle(self.W / 2 - self.W / 2 * abs(sx), 0, self.W * abs(sx), self.H)
            cr.fill()

    def _light(self, zone, u=0.5):
        """(r, g, b, intensity): hue at full strength plus how bright it is right now."""
        st = self.zones[zone]
        rgb = fx.sample(zone, st["effect"], st["color"], st["color2"], self.seconds, st["speed"], u)
        peak = max(rgb)
        if peak < 1:
            return (0.0, 0.0, 0.0, 0.0)
        return (rgb[0] / peak, rgb[1] / peak, rgb[2] / peak, peak / 255)

    def _outline(self, cr, pal, x0, y0, x1, y1, radius):
        cr.save()
        cr.set_dash([6, 5])
        cr.set_line_width(2)
        cr.set_source_rgba(*rgba(pal["accent"], 0.9))
        rounded(cr, x0 - 7, y0 - 7, x1 - x0 + 14, y1 - y0 + 14, radius)
        cr.stroke()
        cr.restore()

    def _draw_front(self, cr, pal):
        body = theme.mix(pal["bg"], pal["fg"], 0.07)
        deck = theme.mix(pal["bg"], pal["fg"], 0.10)
        line = rgba(pal["fg"], 0.14)

        # screen
        cr.set_source_rgba(0, 0, 0, 0.35)
        rounded(cr, 72, 34, 456, 270, 16)
        cr.fill()
        cr.set_source_rgba(*body)
        rounded(cr, 65, 20, 470, 280, 16)
        cr.fill_preserve()
        cr.set_source_rgba(*line)
        cr.set_line_width(1.2)
        cr.stroke()
        disp = cairo.LinearGradient(80, 34, 520, 280)
        disp.add_color_stop_rgb(0, 0.10, 0.15, 0.22)
        disp.add_color_stop_rgb(0.55, 0.05, 0.07, 0.11)
        disp.add_color_stop_rgb(1, 0.07, 0.10, 0.15)
        rounded(cr, 80, 34, 440, 250, 6)
        cr.set_source(disp)
        cr.fill()
        cr.save()
        rounded(cr, 80, 34, 440, 250, 6)
        cr.clip()
        cr.set_source_rgba(1, 1, 1, 0.035)
        quad_path(cr, [(150, 34), (300, 34), (170, 284), (20, 284)])
        cr.fill()
        cr.restore()

        # hinge and base (in perspective)
        cr.set_source_rgba(*theme.mix(pal["bg"], pal["fg"], 0.13))
        rounded(cr, 52, 298, 496, 10, 3)
        cr.fill()
        base = [(52, 306), (548, 306), (584, 470), (16, 470)]
        cr.set_source_rgba(0, 0, 0, 0.35)
        quad_path(cr, [(p[0], p[1] + 10) for p in base])
        cr.fill()
        grad = cairo.LinearGradient(0, 306, 0, 470)
        grad.add_color_stop_rgba(0, *deck)
        grad.add_color_stop_rgba(1, *body)
        quad_path(cr, base)
        cr.set_source(grad)
        cr.fill_preserve()
        cr.set_source_rgba(*line)
        cr.stroke()

        # keyboard
        kq = [(96, 330), (504, 330), (522, 418), (78, 418)]
        kst = self.zones["keyboard"]
        lit = max(kst["color"]) > 4 or self.paint
        light = self._light("keyboard")
        self.key_quads = []
        total_h = sum(r[0] for r in KEY_ROWS)
        gap_u, gap_v = 0.006, 0.035
        v = 0.0
        for ri, (row_h, keys) in enumerate(KEY_ROWS):
            vh = row_h / total_h
            total_w = sum(keys)
            u = 0.0
            for ki, kw in enumerate(keys):
                uw = kw / total_w
                kl = self._light("keyboard", u + uw / 2) if lit else light
                if self.paint:
                    rgb = self.painted.get(KEY_IDS[ri][ki][0], (0, 0, 0))
                    peak = max(rgb)
                    kl = (rgb[0] / peak, rgb[1] / peak, rgb[2] / peak, 0.25 + 0.75 * peak / 255) if peak > 3 \
                        else (0.5, 0.5, 0.5, 0.12)
                pts = [quad_point(kq, u + gap_u, v + gap_v), quad_point(kq, u + uw - gap_u, v + gap_v),
                       quad_point(kq, u + uw - gap_u, v + vh - gap_v), quad_point(kq, u + gap_u, v + vh - gap_v)]
                self.key_quads.append((pts, KEY_IDS[ri][ki]))
                quad_path(cr, pts)
                cr.set_source_rgba(*theme.mix(pal["bg"], (0, 0, 0, 1), 0.3))
                cr.fill_preserve()
                if lit:
                    cr.set_source_rgba(kl[0], kl[1], kl[2], 0.22 * kl[3])
                    cr.fill_preserve()
                    cr.set_source_rgba(kl[0], kl[1], kl[2], 0.95 * kl[3])
                else:
                    cr.set_source_rgba(*line)
                cr.set_line_width(1.1)
                cr.stroke()
                u += uw
            v += vh
        if lit and not self.paint:  # glow under the keys
            glow = cairo.RadialGradient(300, 374, 10, 300, 374, 260)
            glow.add_color_stop_rgba(0, light[0], light[1], light[2], 0.16 * light[3])
            glow.add_color_stop_rgba(1, light[0], light[1], light[2], 0)
            cr.set_source(glow)
            quad_path(cr, base)
            cr.fill()
        self.regions["keyboard"] = (78, 326, 522, 420)
        if self.selected == "keyboard":
            self._outline(cr, pal, 78, 326, 522, 420, 10)

        # power button
        p = self._light("power")
        rounded(cr, 476, 313, 32, 10, 5)
        cr.set_source_rgba(*theme.mix(pal["bg"], (0, 0, 0, 1), 0.3))
        cr.fill_preserve()
        cr.set_source_rgba(p[0], p[1], p[2], 0.35 * p[3])
        cr.fill_preserve()
        cr.set_source_rgba(p[0], p[1], p[2], p[3])
        cr.set_line_width(1.6)
        cr.stroke()
        halo = cairo.RadialGradient(492, 318, 2, 492, 318, 30)
        halo.add_color_stop_rgba(0, p[0], p[1], p[2], 0.45 * p[3])
        halo.add_color_stop_rgba(1, p[0], p[1], p[2], 0)
        cr.set_source(halo)
        cr.arc(492, 318, 30, 0, 2 * math.pi)
        cr.fill()
        self.regions["power"] = (466, 306, 518, 328)
        if self.selected == "power":
            self._outline(cr, pal, 470, 310, 514, 326, 8)

        # touchpad
        quad_path(cr, [(232, 428), (368, 428), (374, 460), (226, 460)])
        cr.set_source_rgba(*rgba(pal["fg"], 0.04))
        cr.fill_preserve()
        cr.set_source_rgba(*line)
        cr.stroke()

    def _draw_back(self, cr, pal):
        body = theme.mix(pal["bg"], pal["fg"], 0.08)
        deep = theme.mix(pal["bg"], pal["fg"], 0.04)
        line = rgba(pal["fg"], 0.14)

        cr.set_source_rgba(0, 0, 0, 0.35)
        rounded(cr, 72, 44, 456, 320, 18)
        cr.fill()
        lid = cairo.LinearGradient(65, 30, 535, 350)
        lid.add_color_stop_rgba(0, *body)
        lid.add_color_stop_rgba(1, *deep)
        rounded(cr, 65, 30, 470, 320, 18)
        cr.set_source(lid)
        cr.fill_preserve()
        cr.set_source_rgba(*line)
        cr.set_line_width(1.2)
        cr.stroke()
        rounded(cr, 80, 45, 440, 290, 12)
        cr.set_source_rgba(*rgba(pal["fg"], 0.05))
        cr.stroke()

        # generic emblem (hexagonal shield) lit with the logo colour
        lr, lg, lb, lk = self._light("logo")
        cx, cy = 300, 190
        glow = cairo.RadialGradient(cx, cy, 5, cx, cy, 120)
        glow.add_color_stop_rgba(0, lr, lg, lb, 0.40 * lk)
        glow.add_color_stop_rgba(1, lr, lg, lb, 0)
        cr.set_source(glow)
        cr.arc(cx, cy, 120, 0, 2 * math.pi)
        cr.fill()

        def hexa(size, drop):
            return [(cx, cy - size), (cx + size * 0.84, cy - size * 0.5), (cx + size * 0.84, cy + size * 0.45),
                    (cx, cy + size + drop), (cx - size * 0.84, cy + size * 0.45), (cx - size * 0.84, cy - size * 0.5)]

        for width, alpha in ((9, 0.18), (5, 0.35)):
            quad_path(cr, hexa(42, 6))
            cr.set_source_rgba(lr, lg, lb, alpha * lk)
            cr.set_line_width(width)
            cr.stroke()
        quad_path(cr, hexa(42, 6))
        cr.set_source_rgba(lr, lg, lb, 0.12 + 0.88 * lk)
        cr.set_line_width(3)
        cr.stroke()
        quad_path(cr, hexa(22, 4))
        cr.set_source_rgba(lr, lg, lb, 0.9 * lk)
        cr.fill()
        self.regions["logo"] = (cx - 50, cy - 52, cx + 50, cy + 56)
        if self.selected == "logo":
            self._outline(cr, pal, cx - 44, cy - 46, cx + 44, cy + 52, 14)

        # base edge with air vents
        rounded(cr, 40, 348, 520, 28, 10)
        cr.set_source_rgba(*theme.mix(pal["bg"], pal["fg"], 0.06))
        cr.fill_preserve()
        cr.set_source_rgba(*line)
        cr.stroke()
        for i in range(20):
            rounded(cr, 116 + i * 19, 356, 13, 10, 2)
            cr.set_source_rgba(0, 0, 0, 0.55)
            cr.fill()

        # rear light: a strip along the back edge, two halves that blend in the middle
        segments = 24
        for i in range(segments):
            rr, rg, rb, rk = self._light("rear", (i + 0.5) / segments)
            x = 70 + 460 * i / segments
            if rk > 0.02:
                halo = cairo.LinearGradient(0, 376, 0, 420)
                halo.add_color_stop_rgba(0, rr, rg, rb, 0.45 * rk)
                halo.add_color_stop_rgba(1, rr, rg, rb, 0)
                cr.set_source(halo)
                cr.rectangle(x, 376, 460 / segments + 0.6, 44)
                cr.fill()
            cr.set_source_rgba(rr, rg, rb, 0.10 + 0.90 * rk)
            cr.rectangle(x, 377, 460 / segments + 0.6, 6)
            cr.fill()
        self.regions["rear"] = (40, 346, 560, 400)
        if self.selected == "rear":
            self._outline(cr, pal, 46, 350, 554, 386, 10)


# ---------- effect previews ----------

class EffectPreview(Gtk.DrawingArea):
    """A small strip that shows what an effect looks like; animates while `playing`."""

    def __init__(self, zone, key, width=104, height=30):
        super().__init__()
        self.zone, self.key = zone, key
        self.c1, self.c2, self.speed = (0, 160, 255), (138, 60, 255), "normal"
        self.seconds = 0.6
        self.timer = None
        self.set_content_width(width)
        self.set_content_height(height)
        self.set_draw_func(self.draw)
        self.connect("unmap", lambda *_: self.play(False))

    def set_colors(self, c1, c2, speed):
        self.c1, self.c2, self.speed = tuple(c1), tuple(c2), speed
        self.queue_draw()

    def play(self, on):
        if on and self.timer is None:
            self.timer = GLib.timeout_add(66, self._step)
        elif not on and self.timer is not None:
            GLib.source_remove(self.timer)
            self.timer = None

    def _step(self):
        self.seconds += 0.066
        self.queue_draw()
        return True

    def draw(self, area, cr, w, h):
        n = 12 if self.zone in ("keyboard", "rear") else 1
        gap = 2 if self.zone == "keyboard" else 0
        cr.save()
        rounded(cr, 0, 0, w, h, 8)
        cr.clip()
        cr.set_source_rgb(0.03, 0.04, 0.06)
        cr.paint()
        for i in range(n):
            r, g, b = fx.sample(self.zone, self.key, self.c1, self.c2, self.seconds, self.speed, (i + 0.5) / n)
            cr.set_source_rgb(r / 255, g / 255, b / 255)
            cr.rectangle(i * w / n + gap / 2, 0, w / n - gap + 0.6, h)
            cr.fill()
        cr.restore()


class SceneSwatch(Gtk.DrawingArea):
    """Four colour stops side by side: a scene's keyboard, power, logo and rear colours."""

    def __init__(self, colors, width=60, height=20):
        super().__init__()
        self.colors = colors
        self.set_content_width(width)
        self.set_content_height(height)
        self.set_draw_func(self.draw)

    def draw(self, area, cr, w, h):
        rounded(cr, 0, 0, w, h, h / 2)
        cr.clip()
        grad = cairo.LinearGradient(0, 0, w, 0)
        for i, (r, g, b) in enumerate(self.colors):
            grad.add_color_stop_rgb(i / max(1, len(self.colors) - 1), r / 255, g / 255, b / 255)
        cr.set_source(grad)
        cr.paint()
