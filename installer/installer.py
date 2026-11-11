#!/usr/bin/python3
"""Graphical installer for Alienware Control.

A small GTK wizard around install.sh / uninstall.sh: it checks the computer, lets you
pick the options, then runs the script through pkexec (one password prompt) and shows
its progress. Double-click "Install" or "Uninstall" in the project folder, or run
    installer/installer.py [--uninstall]
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))       # installer/
ROOT = os.path.dirname(HERE)                              # project root
sys.path.insert(0, os.path.join(ROOT, "alienware_control"))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

import awelc  # noqa: E402
import awkbd  # noqa: E402
import i18n  # noqa: E402
import sensors  # noqa: E402
import theme  # noqa: E402
from i18n import _  # noqa: E402

INSTALLED_MARK = "/usr/local/share/alienware-control/app.py"
PACKAGE_MARK = "/usr/share/alienware-control/app.py"   # installed from the .deb package
SYSMAN = "/sys/class/firmware-attributes/dell-wmi-sysman"
CSS = """
.inst-title { font-weight: 800; font-size: 26px; }
.inst-log { font-family: monospace; font-size: 12px; }
.inst-ok { color: #2ec27e; }
.inst-warn { color: #e5a50a; }
"""


OK_ICONS = ["emblem-ok-symbolic", "object-select-symbolic", "checkbox-checked-symbolic", "emblem-default"]
WARN_ICONS = ["dialog-warning-symbolic", "emblem-important-symbolic", "dialog-warning"]


def icon(names, size=None):
    img = Gtk.Image.new_from_gicon(Gio.ThemedIcon.new_from_names(names))
    if size:
        img.set_pixel_size(size)
    return img


def adw_ok():
    return (Adw.get_major_version(), Adw.get_minor_version()) >= (1, 3)


def checks():
    """[(title, detail, ok)] describing this computer."""
    nvidia = sensors.nvidia_awake() is not None
    return [
        (_("Computer"), _(sensors.machine()), True),
        (_("GTK 4 and libadwaita 1.3+"), f"libadwaita {Adw.get_major_version()}.{Adw.get_minor_version()}", adw_ok()),
        (_("Keyboard lighting"), _("found") if awkbd.find_device() else _("not found"), awkbd.find_device() is not None),
        (_("Power button and logo lighting"), _("found") if awelc.find_device() else _("not found"),
         awelc.find_device() is not None),
        (_("BIOS settings (Dell WMI)"), _("found") if os.path.isdir(SYSMAN) else _("not found"), os.path.isdir(SYSMAN)),
        (_("Power profiles"), _("found") if shutil.which("powerprofilesctl") else _("not found"),
         shutil.which("powerprofilesctl") is not None),
        (_("Password prompt (polkit)"), _("found") if shutil.which("pkexec") else _("not found"),
         shutil.which("pkexec") is not None),
        (_("NVIDIA GPU"), _("found") if nvidia else _("not found"), nvidia),
    ]


class Installer(Adw.ApplicationWindow):
    def __init__(self, app, uninstall=False):
        super().__init__(application=app, title=_("Uninstall Alienware Control") if uninstall
                         else _("Install Alienware Control"))
        self.set_default_size(640, 620)
        self.installed = os.path.exists(INSTALLED_MARK)
        self.mode = "install"
        self.proc = None

        self.stack = Gtk.Stack(transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT, vexpand=True)
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(Adw.HeaderBar())
        root.append(self.stack)
        self.set_content(root)

        self.stack.add_named(self.page_welcome(), "welcome")
        self.stack.add_named(self.page_check(), "check")
        self.stack.add_named(self.page_options(), "options")
        self.stack.add_named(self.page_progress(), "progress")
        self.stack.add_named(self.page_done(), "done")
        self.stack.add_named(self.page_uninstall(), "uninstall")
        # AWC_INSTALLER_PAGE is a developer aid for screenshots.
        self.stack.set_visible_child_name("uninstall" if uninstall else os.environ.get("AWC_INSTALLER_PAGE", "welcome"))

    # ----- layout helpers -----

    @staticmethod
    def page(spacing=18):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing,
                      margin_top=24, margin_bottom=24, margin_start=32, margin_end=32)
        return box

    @staticmethod
    def buttons(*items):
        row = Gtk.Box(spacing=12, halign=Gtk.Align.END, valign=Gtk.Align.END, vexpand=True)
        for text, cb, style in items:
            btn = Gtk.Button(label=text)
            if style:
                btn.add_css_class(style)
            btn.add_css_class("pill")
            btn.connect("clicked", lambda _b, f=cb: f())
            row.append(btn)
        return row

    def go(self, name):
        self.stack.set_visible_child_name(name)

    # ----- pages -----

    def page_welcome(self):
        box = self.page()
        icon = Gtk.Image.new_from_file(os.path.join(ROOT, "data", "alienware-control.svg"))
        icon.set_pixel_size(112)
        icon.set_margin_top(12)
        box.append(icon)
        title = Gtk.Label(label="Alienware Control for Linux")
        title.add_css_class("inst-title")
        box.append(title)
        intro = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, label=_(
            "Temperatures, fans, disks, RGB lighting, thermal mode and battery charging "
            "for Alienware laptops on Linux."))
        box.append(intro)
        note = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, label=_(
            "Tested only on an Alienware m15 R7. On other models some features may not work."))
        note.add_css_class("dim-label")
        box.append(note)
        if os.path.exists(PACKAGE_MARK):
            box.append(Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, margin_top=8, label=_(
                "Alienware Control is installed as a system package. Update or remove it from your software "
                "center or package manager.")))
            box.append(self.buttons((_("Close"), self.close, None)))
        elif self.installed:
            box.append(Gtk.Label(label=_("Alienware Control is already installed."), margin_top=8))
            box.append(self.buttons((_("Uninstall"), self.start_uninstall, "destructive-action"),
                                    (_("Update"), lambda: self.go("check"), "suggested-action")))
        else:
            box.append(self.buttons((_("Next"), lambda: self.go("check"), "suggested-action")))
        return box

    def page_uninstall(self):
        box = self.page()
        img = icon(WARN_ICONS, 96)
        img.set_margin_top(24)
        box.append(img)
        title = Gtk.Label(label=_("Uninstall Alienware Control?"))
        title.add_css_class("inst-title")
        box.append(title)
        if self.installed:
            box.append(Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, label=_(
                "This removes the app, its helpers and permissions. Your settings in "
                "~/.config/alienware-control are kept.")))
            box.append(self.buttons((_("Cancel"), self.close, None),
                                    (_("Uninstall"), self.start_uninstall, "destructive-action")))
        else:
            box.append(Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER,
                                 label=_("Alienware Control is not installed on this computer.")))
            box.append(self.buttons((_("Close"), self.close, None)))
        return box

    def page_check(self):
        box = self.page(12)
        box.append(self.heading(_("Your computer"), _("What the installer found. Missing items only turn "
                                                         "the matching feature off.")))
        group = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        group.add_css_class("boxed-list")
        for title, detail, ok in checks():
            row = Adw.ActionRow(title=title, subtitle=detail)
            img = icon(OK_ICONS if ok else WARN_ICONS)
            img.add_css_class("inst-ok" if ok else "inst-warn")
            row.add_prefix(img)
            group.append(row)
        box.append(group)
        if not adw_ok():
            box.append(Gtk.Label(wrap=True, label=_("libadwaita 1.3 or newer is required. Update your system "
                                                     "first, then run the installer again.")))
            box.append(self.buttons((_("Back"), lambda: self.go("welcome"), None)))
        else:
            box.append(self.buttons((_("Back"), lambda: self.go("welcome"), None),
                                    (_("Next"), lambda: self.go("options"), "suggested-action")))
        return box

    def page_options(self):
        box = self.page(12)
        box.append(self.heading(_("Options"), _("You can run the installer again later to change them.")))
        group = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        group.add_css_class("boxed-list")
        row = Adw.ActionRow(title=_("Let the NVIDIA GPU sleep when idle"),
                            subtitle=_("Saves 10 to 15 W and keeps the GPU fan quiet on some laptops"))
        self.gpu_switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=sensors.nvidia_awake() is not None)
        self.gpu_switch.set_sensitive(sensors.nvidia_awake() is not None)
        row.add_suffix(self.gpu_switch)
        row.set_activatable_widget(self.gpu_switch)
        group.append(row)
        box.append(group)
        where = Gtk.Label(wrap=True, xalign=0, label=_(
            "Files go to /usr/local, plus a polkit policy and a udev rule. "
            "You will be asked for your password once."))
        where.add_css_class("dim-label")
        box.append(where)
        box.append(self.buttons((_("Back"), lambda: self.go("check"), None),
                                (_("Install"), self.start_install, "suggested-action")))
        return box

    def page_progress(self):
        box = self.page(12)
        self.progress_title = self.heading(_("Installing…"), _("Follow the password prompt if one appears."))
        box.append(self.progress_title)
        self.bar = Gtk.ProgressBar()
        box.append(self.bar)
        self.log = Gtk.TextView(editable=False, cursor_visible=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.log.add_css_class("inst-log")
        scroller = Gtk.ScrolledWindow(vexpand=True, child=self.log)
        scroller.add_css_class("card")
        box.append(scroller)
        return box

    def page_done(self):
        box = self.page()
        self.done_icon = icon(OK_ICONS, 96)
        self.done_icon.set_margin_top(24)
        box.append(self.done_icon)
        self.done_title = Gtk.Label()
        self.done_title.add_css_class("inst-title")
        box.append(self.done_title)
        self.done_text = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER)
        box.append(self.done_text)
        self.done_buttons = Gtk.Box(spacing=12, halign=Gtk.Align.END, valign=Gtk.Align.END, vexpand=True)
        box.append(self.done_buttons)
        return box

    @staticmethod
    def heading(title, subtitle):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        t = Gtk.Label(label=title, xalign=0)
        t.add_css_class("title-2")
        box.append(t)
        s = Gtk.Label(label=subtitle, xalign=0, wrap=True)
        s.add_css_class("dim-label")
        box.append(s)
        return box

    # ----- running the scripts -----

    def start_install(self):
        self.mode = "install"
        args = ["--gpu-sleep"] if self.gpu_switch.get_active() else []
        self.run_script("install.sh", args)

    def start_uninstall(self):
        self.mode = "uninstall"
        self.run_script("uninstall.sh", [])

    def run_script(self, script, args):
        self.go("progress")
        title = self.progress_title.get_first_child()
        title.set_label(_("Uninstalling…") if self.mode == "uninstall" else _("Installing…"))
        self.log.get_buffer().set_text("")
        cmd = ["pkexec", "/bin/sh", os.path.join(HERE, script), *args]
        try:
            self.proc = Gio.Subprocess.new(cmd, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        except GLib.Error as e:
            self.finish(False, e.message)
            return
        self.pulse_id = GLib.timeout_add(120, self._pulse)
        stream = Gio.DataInputStream.new(self.proc.get_stdout_pipe())
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._line, stream)
        self.proc.wait_async(None, self._exited)

    def _pulse(self):
        self.bar.pulse()
        return True

    def _line(self, stream, res, _data):
        try:
            line, _len = stream.read_line_finish_utf8(res)
        except GLib.Error:
            return
        if line is None:
            return
        buf = self.log.get_buffer()
        buf.insert(buf.get_end_iter(), line + "\n")
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self._line, stream)

    def _exited(self, proc, res):
        try:
            proc.wait_finish(res)
        except GLib.Error:
            pass
        GLib.source_remove(self.pulse_id)
        code = proc.get_exit_status()
        if code in (126, 127):
            self.finish(False, _("The password was not confirmed, so nothing was changed."))
        else:
            self.finish(code == 0, None)

    def finish(self, ok, message):
        self.bar.set_fraction(1.0 if ok else 0.0)
        for child in list(self._children(self.done_buttons)):
            self.done_buttons.remove(child)
        if ok and self.mode == "install":
            self.done_icon.set_from_gicon(Gio.ThemedIcon.new_from_names(OK_ICONS))
            self.done_title.set_label(_("All set"))
            self.done_text.set_label(_("Alienware Control is installed. You can find it in your app menu."))
            self.done_buttons.append(self._button(_("Close"), self.close, None))
            self.done_buttons.append(self._button(_("Open Alienware Control"), self.open_app, "suggested-action"))
        elif ok:
            self.done_icon.set_from_gicon(Gio.ThemedIcon.new_from_names(OK_ICONS))
            self.done_title.set_label(_("Removed"))
            self.done_text.set_label(_("Alienware Control was uninstalled. Your settings were kept."))
            self.done_buttons.append(self._button(_("Close"), self.close, "suggested-action"))
        else:
            self.done_icon.set_from_gicon(Gio.ThemedIcon.new_from_names(WARN_ICONS))
            self.done_title.set_label(_("Something went wrong"))
            self.done_text.set_label(message or _("See the details on the previous screen."))
            self.done_buttons.append(self._button(_("Show details"), lambda: self.go("progress"), None))
            self.done_buttons.append(self._button(_("Close"), self.close, None))
        self.go("done")

    @staticmethod
    def _children(box):
        child = box.get_first_child()
        while child:
            yield child
            child = child.get_next_sibling()

    @staticmethod
    def _button(text, cb, style):
        btn = Gtk.Button(label=text)
        btn.add_css_class("pill")
        if style:
            btn.add_css_class(style)
        btn.connect("clicked", lambda _b: cb())
        return btn

    def open_app(self):
        try:
            Gio.Subprocess.new(["/usr/local/bin/alienware-control"], Gio.SubprocessFlags.NONE)
        except GLib.Error:
            pass
        self.close()


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id="io.github.alienware_control.Installer",
                         flags=Gio.ApplicationFlags.NON_UNIQUE)

    def do_activate(self):
        cfg = theme.load_config()
        i18n.setup(cfg["language"])
        provider = Gtk.CssProvider()
        if hasattr(provider, "load_from_string"):
            provider.load_from_string(CSS)
        else:
            provider.load_from_data(CSS, -1)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        Installer(self, uninstall="--uninstall" in sys.argv[1:]).present()


if __name__ == "__main__":
    sys.exit(App().run([sys.argv[0]]))
