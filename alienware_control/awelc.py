"""Alienware AW-ELC lighting controller (USB 187c:0550): power button, lid logo, etc.

33-byte HID reports, no report ID (so hidraw writes are prefixed with 0x00).
Protocol cross-checked against alien-lights, alienfx-tools and alienrgb.

Safety:
  * only the volatile animation slot (0xFFFF) is used; nothing is saved to the
    controller, so a reboot restores the default lighting;
  * 0xFF (erase flash) and sub-commands 2/6/7 (save / set default / set startup)
    are never sent: `send()` refuses anything outside an allow-list;
  * packets are paced, because bursts can hang the controller.

On the Alienware m15 R7: zones 0-1 = rear light, zone 2 = power button, zone 3 = lid logo,
zone 4 = power button status indicator (blinks; left alone).
"""
import errno
import fcntl
import os
import select
import time

VENDOR, PRODUCT = "0000187C", "00000550"
PAYLOAD = 33
PAUSE = 0.07

QUERY, ANIM, SELECT, ACTION, DIM = 0x20, 0x21, 0x23, 0x24, 0x26
ANIM_START, ANIM_FINISH_PLAY = 0x0001, 0x0003
SAFE_COMMANDS = {QUERY, ANIM, SELECT, ACTION, DIM}
SAFE_ANIM_SUBS = {ANIM_START, ANIM_FINISH_PLAY}


class ElcError(Exception):
    pass


def find_device():
    base = "/sys/class/hidraw"
    if not os.path.isdir(base):
        return None
    for name in sorted(os.listdir(base)):
        try:
            with open(os.path.join(base, name, "device", "uevent")) as f:
                uevent = f.read().upper()
        except OSError:
            continue
        if f"HID_ID=0003:{VENDOR}:{PRODUCT}" in uevent:
            return "/dev/" + name
    return None


def _hidiocginput(size):
    return (3 << 30) | (size << 16) | (ord("H") << 8) | 0x0A


class Elc:
    def __init__(self, path=None):
        self.path = path or find_device()
        if not self.path:
            raise ElcError("AW-ELC lighting controller (187c:0550) not found")
        try:
            self.fd = os.open(self.path, os.O_RDWR | os.O_NONBLOCK)
        except PermissionError:
            raise ElcError(f"no permission on {self.path}: run the installer") from None

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _drain(self):
        while True:
            try:
                os.read(self.fd, 64)
            except OSError:  # BlockingIOError included: nothing left to read
                return

    def send(self, payload, expect=2, wait=PAUSE):
        """Send one report and return the controller's echo (or None if it stayed silent)."""
        payload = bytes(payload)
        if payload[0] != 0x03 or payload[1] not in SAFE_COMMANDS or len(payload) > PAYLOAD:
            raise ElcError("refusing to send a command outside the allow-list")
        if payload[1] == ANIM and (len(payload) < 6 or (payload[2] << 8 | payload[3]) not in SAFE_ANIM_SUBS
                                   or payload[4:6] != b"\xff\xff"):
            raise ElcError("refusing an animation command outside the allow-list or the volatile slot")
        self._drain()
        os.write(self.fd, b"\x00" + payload.ljust(PAYLOAD, b"\x00"))
        time.sleep(wait)
        resp = self._read()
        if resp is not None and resp[:expect] != payload[:expect]:
            raise ElcError(f"unexpected reply: {resp[:8].hex(' ')}")
        return resp

    def _read(self):
        ready, _, _ = select.select([self.fd], [], [], 0.3)
        if ready:
            try:
                data = os.read(self.fd, 64)
                return data[1:] if len(data) == PAYLOAD + 1 else data
            except OSError:
                pass
        # Some firmwares only answer a GET_REPORT.
        for report_id in (0x00, 0x01):
            buf = bytearray(PAYLOAD + 1)
            buf[0] = report_id
            try:
                fcntl.ioctl(self.fd, _hidiocginput(len(buf)), buf, True)
            except OSError as e:
                if e.errno in (errno.EINVAL, errno.EIO, errno.EPIPE, errno.ENOTTY, errno.ETIMEDOUT):
                    continue
                raise
            return bytes(buf[1:])
        return None

    def info(self):
        fw = self.send([0x03, QUERY, 0x00])
        plat = self.send([0x03, QUERY, 0x02])
        out = {"device": self.path}
        if fw:
            out["firmware"] = f"{fw[3]}.{fw[4]}.{fw[5]}"
        if plat:
            out["platform"] = f"0x{(plat[3] << 8) | plat[4]:04x}"
            out["zones"] = plat[5]
        return out

    def set_zone_colors(self, items):
        """items: [(zone, (r, g, b)), ...], one colour per zone, in a single animation."""
        self.send([0x03, ANIM, 0x00, 0x01, 0xFF, 0xFF, 0x00, 0x00], expect=4)
        for zone, (r, g, b) in items:
            self.send([0x03, SELECT, 0x01, 0x00, 0x01, zone])
            # static action: mode 0, duration 1, tempo 2, colour
            self.send([0x03, ACTION, 0x00, 0x00, 0x01, 0x00, 0x02, r, g, b])
        self.send([0x03, ANIM, 0x00, 0x03, 0xFF, 0xFF, 0x00, 0x00], expect=4, wait=1.0)

    def set_zone_actions(self, groups):
        """groups: [(zones, actions)], actions = [(mode, duration, tempo, (r, g, b)), ...].

        Each group loops through its own actions (mode 0 colour, 1 pulse, 2 morph), all
        inside one volatile animation, so the groups start together and stay in step.
        """
        for zones, actions in groups:
            if not zones or not 1 <= len(actions) <= 12:
                raise ElcError("bad animation: needs zones and 1 to 12 actions")
            for mode, duration, tempo, rgb in actions:
                if mode not in (0, 1, 2) or not 1 <= duration <= 0xFFFF or not 1 <= tempo <= 0xFFFF:
                    raise ElcError("bad animation action")
                if len(rgb) != 3 or any(not 0 <= c <= 255 for c in rgb):
                    raise ElcError("bad animation colour")
        self.send([0x03, ANIM, 0x00, 0x01, 0xFF, 0xFF, 0x00, 0x00], expect=4)
        for zones, actions in groups:
            zones = list(zones)
            self.send([0x03, SELECT, 0x01, len(zones) >> 8, len(zones) & 0xFF, *zones])
            for i in range(0, len(actions), 3):  # at most 3 actions per report
                payload = [0x03, ACTION]
                for mode, duration, tempo, (r, g, b) in actions[i:i + 3]:
                    payload += [mode, duration >> 8, duration & 0xFF, tempo >> 8, tempo & 0xFF, r, g, b]
                self.send(payload)
        self.send([0x03, ANIM, 0x00, 0x03, 0xFF, 0xFF, 0x00, 0x00], expect=4, wait=1.0)

    def set_brightness(self, percent, zones):
        dim = 100 - max(0, min(100, int(percent)))
        for i in range(0, len(zones), 28):
            chunk = list(zones[i:i + 28])
            self.send([0x03, DIM, dim, len(chunk) >> 8, len(chunk) & 0xFF, *chunk], expect=3)
