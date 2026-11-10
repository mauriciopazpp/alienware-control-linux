"""Alienware per-key RGB keyboard (Darfon 0d62:*, "API v5" in alienfx-tools).

64-byte HID feature reports with report ID 0xCC.

Sequence confirmed on an Alienware m15 R7:
  brightness  -> reset (94), status (93), 83 38 9C <0..255>
  static      -> leave effect mode (80 01 FE), then per-key colours:
                 reset, 8C 02 00 [id+1 R G B]... (15 keys per report), 8C 13, 8B 01 FF
  effect      -> 80 <type> <tempo> ... colours at bytes 10..15, then 8B 01 FF
Sending per-key colours while an effect is active blanks the keyboard, so the
effect must be left first. Nothing is saved on the device; a reboot restores it.
"""
import fcntl
import os
import time

VENDOR = "00000D62"
REPORT_ID = 0xCC
LENGTH = 64

CMD_RESET = (0x94,)
CMD_STATUS = (0x93,)
CMD_COLOR = (0x8C, 0x02)
CMD_LOOP = (0x8C, 0x13)
CMD_UPDATE = (0x8B, 0x01, 0xFF)
CMD_BRIGHT = (0x83, 0x38, 0x9C)
CMD_EFFECT = (0x80, 0x02, 0x07, 0x00, 0x00, 0x01, 0x01, 0x01)
ALLOWED = {CMD_RESET, CMD_STATUS, CMD_COLOR, CMD_LOOP, CMD_UPDATE, CMD_BRIGHT, CMD_EFFECT}

# Hardware effects confirmed on an Alienware m15 R7. Types 4 (dual-colour wave) and
# 11 (laser) are documented by alienfx-tools but did nothing on this keyboard.
EFFECT_EXIT = 1        # leave hardware effect, back to per-key mode (with tempo 0xFE)
EFFECT_BREATHING = 2
EFFECT_WAVE = 3
EFFECT_PULSE = 8
EFFECT_MIX_PULSE = 9   # alternates between two colours
EFFECT_NIGHT_RIDER = 10
EFFECT_TEMPOS = {EFFECT_EXIT: {0xFE}, EFFECT_BREATHING: {0x07}, EFFECT_WAVE: {0x07},
                 EFFECT_PULSE: {0x07}, EFFECT_MIX_PULSE: {0x07}, EFFECT_NIGHT_RIDER: {0x07}}


class KbdError(Exception):
    pass


def _ioc(nr, size):
    return (3 << 30) | (size << 16) | (ord("H") << 8) | nr


HIDIOCSFEATURE = _ioc(0x06, LENGTH)
HIDIOCGFEATURE = _ioc(0x07, LENGTH)


def find_device():
    """hidraw node of a Darfon keyboard exposing usage page 0xFF89 / usage 0xCC."""
    base = "/sys/class/hidraw"
    if not os.path.isdir(base):
        return None
    for name in sorted(os.listdir(base)):
        dev = os.path.join(base, name, "device")
        try:
            with open(os.path.join(dev, "uevent")) as f:
                if f"HID_ID=0003:{VENDOR}:" not in f.read().upper():
                    continue
            with open(os.path.join(dev, "report_descriptor"), "rb") as f:
                desc = f.read()
        except OSError:
            continue
        if b"\x06\x89\xff\x09\xcc" in desc and b"\x85\xcc" in desc:
            return "/dev/" + name
    return None


class Keyboard:
    def __init__(self, path=None):
        self.path = path or find_device()
        if not self.path:
            raise KbdError("Alienware RGB keyboard (Darfon 0d62) not found")
        try:
            self.fd = os.open(self.path, os.O_RDWR)
        except PermissionError:
            raise KbdError(f"no permission on {self.path}: run the installer") from None

    def close(self):
        os.close(self.fd)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _write(self, buf):
        fcntl.ioctl(self.fd, HIDIOCSFEATURE, bytes(buf))
        time.sleep(0.02)

    def _send(self, command, extra=b"", offset=None):
        if tuple(command) not in ALLOWED:
            raise KbdError("refusing to send a command outside the allow-list")
        buf = bytearray(LENGTH)
        buf[0] = REPORT_ID
        buf[1:1 + len(command)] = bytes(command)
        if extra:
            start = offset if offset is not None else 1 + len(command)
            buf[start:start + len(extra)] = extra
        self._write(buf)

    def status(self):
        self._send(CMD_STATUS)
        buf = bytearray(LENGTH)
        buf[0] = REPORT_ID
        try:
            fcntl.ioctl(self.fd, HIDIOCGFEATURE, buf, True)
        except OSError:
            return None
        return buf[2]

    def reset(self):
        self._send(CMD_RESET)
        return self.status()

    def set_colors(self, items):
        """items: [(key_id, (r, g, b)), ...]; ids start at 0 (sent as id + 1)."""
        if any(not 0 <= key < 254 for key, _ in items):
            raise KbdError("key id out of range")
        self.reset()
        for i in range(0, len(items), 15):
            block = bytearray()
            for key, (r, g, b) in items[i:i + 15]:
                block += bytes((key + 1, r, g, b))
            self._send(CMD_COLOR, block, offset=4)
        self._send(CMD_LOOP)
        self._send(CMD_UPDATE)

    def set_effect(self, kind, tempo, rgb1, rgb2=(0, 0, 0), colors=1):
        """Whole-keyboard hardware effect: [2]=type [3]=tempo [9]=colours-1 [10..15]=RGB1, RGB2."""
        if tempo not in EFFECT_TEMPOS.get(kind, ()) or colors not in (1, 2):
            raise KbdError("refusing an effect outside the tested set")
        rgb1, rgb2 = bytes(rgb1), bytes(rgb2)  # bytes() raises for values outside 0..255
        if len(rgb1) != 3 or len(rgb2) != 3:
            raise KbdError("colours must be (r, g, b)")
        self.reset()
        buf = bytearray(LENGTH)
        buf[0] = REPORT_ID
        buf[1:1 + len(CMD_EFFECT)] = bytes(CMD_EFFECT)
        buf[2], buf[3] = kind, tempo
        buf[9] = colors - 1
        buf[10:13] = rgb1
        buf[13:16] = rgb2
        self._write(buf)
        self._send(CMD_UPDATE)

    def set_brightness(self, percent):
        value = round(max(0, min(100, int(percent))) * 255 / 100)
        self.reset()
        self._send(CMD_BRIGHT, bytes((value,)), offset=4)
