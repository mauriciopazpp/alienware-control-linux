"""Sensor readings straight from /sys and /proc: no root, no extra dependencies.

Works on any Linux: tries the common drivers (Intel coretemp, AMD k10temp/zenpower,
Dell dell_smm/dell_ddv, amdgpu, nvme) and returns None for anything missing.
"""
import json
import os
import subprocess

HWMON = "/sys/class/hwmon"


def read(path, default=None):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return default


def read_int(path):
    value = read(path)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def hwmon_by_name():
    found = {}
    if not os.path.isdir(HWMON):
        return found
    for h in sorted(os.listdir(HWMON)):
        path = os.path.join(HWMON, h)
        found.setdefault(read(os.path.join(path, "name"), ""), []).append(path)
    return found


def _labeled_temp(path, wanted):
    """First tempN_input whose label is in `wanted` (any label when wanted is None), in °C."""
    for i in range(1, 40):
        label = read(os.path.join(path, f"temp{i}_label"))
        value = read_int(os.path.join(path, f"temp{i}_input"))
        if value is None:
            continue
        if wanted is None or (label and label in wanted):
            return value / 1000
    return None


def cpu_temp(hw):
    for name, labels in (("coretemp", ("Package id 0",)), ("k10temp", ("Tctl", "Tdie")),
                         ("zenpower", ("Tdie", "Tctl")), ("cpu_thermal", None)):
        for path in hw.get(name, []):
            t = _labeled_temp(path, labels) or _labeled_temp(path, None)
            if t is not None:
                return t
    return None


def gpu_temp(hw):
    """Discrete GPU temperature without waking the GPU up (never calls nvidia-smi)."""
    for path in hw.get("dell_ddv", []):
        t = _labeled_temp(path, ("Video",))
        if t is not None:
            return t
    for name in ("amdgpu", "nouveau"):
        for path in hw.get(name, []):
            t = _labeled_temp(path, ("edge", "junction")) or _labeled_temp(path, None)
            if t is not None:
                return t
    return None


def nvidia_awake():
    """True/False for an NVIDIA GPU's runtime power state; None when there is no NVIDIA GPU."""
    base = "/sys/bus/pci/devices"
    if not os.path.isdir(base):
        return None
    for dev in os.listdir(base):
        p = os.path.join(base, dev)
        if read(os.path.join(p, "vendor")) == "0x10de" and (read(os.path.join(p, "class")) or "").startswith("0x03"):
            return read(os.path.join(p, "power", "runtime_status")) == "active"
    return None


def nvme_temps(hw):
    temps = {}
    for path in hw.get("nvme", []):
        dev = os.path.realpath(os.path.join(path, "device"))
        ctrl = os.path.basename(dev)
        try:
            name = next((n for n in sorted(os.listdir(dev)) if n.startswith(ctrl + "n")), ctrl)
        except OSError:
            name = ctrl
        t = _labeled_temp(path, ("Composite",)) or _labeled_temp(path, None)
        if t is not None:
            temps[name] = t
    return temps


def fans(hw):
    """List of (label, rpm, max_rpm)."""
    result = []
    for name in ("dell_smm", "thinkpad", "asus", "applesmc", "nct6775", "it87"):
        for path in hw.get(name, []):
            for i in range(1, 9):
                rpm = read_int(os.path.join(path, f"fan{i}_input"))
                if rpm is None:
                    continue
                label = read(os.path.join(path, f"fan{i}_label"))
                if not label:
                    label = {1: "CPU", 2: "GPU"}.get(i, str(i)) if name == "dell_smm" else str(i)
                if "fan" not in label.lower():
                    label = f"{label} fan"
                top = read_int(os.path.join(path, f"fan{i}_max")) or 5000
                result.append((label, rpm, max(top, rpm, 1)))
        if result:
            break
    return result


class CpuUsage:
    def __init__(self):
        self.last = None

    def sample(self):
        line = read("/proc/stat", "").splitlines()[0:1]
        if not line:
            return None
        parts = [int(x) for x in line[0].split()[1:]]
        idle, total = parts[3] + (parts[4] if len(parts) > 4 else 0), sum(parts)
        last, self.last = self.last, (idle, total)
        if not last or total == last[1]:
            return None
        return max(0.0, min(100.0, 100 * (1 - (idle - last[0]) / (total - last[1]))))


def memory():
    info = {}
    for line in read("/proc/meminfo", "").splitlines():
        key, _, rest = line.partition(":")
        try:
            info[key] = int(rest.split()[0]) * 1024
        except (IndexError, ValueError):
            pass
    total, avail = info.get("MemTotal"), info.get("MemAvailable")
    if not total or avail is None:
        return None
    return total - avail, total


def battery():
    base = "/sys/class/power_supply"
    if not os.path.isdir(base):
        return None
    for name in sorted(os.listdir(base)):
        p = os.path.join(base, name)
        if read(os.path.join(p, "type")) != "Battery":
            continue
        full = read_int(os.path.join(p, "charge_full")) or read_int(os.path.join(p, "energy_full"))
        design = read_int(os.path.join(p, "charge_full_design")) or read_int(os.path.join(p, "energy_full_design"))
        energy_full = read_int(os.path.join(p, "energy_full"))
        energy_design = read_int(os.path.join(p, "energy_full_design"))
        return {
            "percent": read_int(os.path.join(p, "capacity")),
            "status": read(os.path.join(p, "status")),
            "health": full / design * 100 if full and design else None,
            "wh_full": energy_full / 1e6 if energy_full else None,
            "wh_design": energy_design / 1e6 if energy_design else None,
        }
    return None


def _udev_props(dev):
    try:
        out = subprocess.run(["udevadm", "info", "-q", "property", "-n", dev],
                             capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    return dict(line.split("=", 1) for line in out.splitlines() if "=" in line)


def _lsblk():
    """lsblk tree as JSON. MOUNTPOINTS needs util-linux 2.37+; older versions only have MOUNTPOINT."""
    for column in ("MOUNTPOINTS", "MOUNTPOINT"):
        try:
            out = subprocess.run(["lsblk", "-J", "-b", "-o", f"NAME,SIZE,TYPE,MODEL,FSTYPE,{column}"],
                                 capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                return json.loads(out.stdout).get("blockdevices", [])
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return []


def _mounts(node):
    mounts = node.get("mountpoints") or [node.get("mountpoint")]
    return [m for m in mounts if m and not m.startswith("/snap/") and m != "[SWAP]"]


def _volumes(node, top_level):
    """Every node under a disk that matters: mounted ones at any depth (partitions, LUKS, LVM,
    RAID) plus unmounted partitions of 1 GB or more."""
    found = []
    mounts = _mounts(node)
    size = int(node.get("size") or 0)
    if mounts or (not top_level and node.get("type") == "part" and size >= 1024 ** 3 and not node.get("children")):
        found.append(node)
    for child in node.get("children") or []:
        found += _volumes(child, False)
    return found


def disks():
    """Physical disks with their relevant volumes, including ones inside LUKS/LVM/RAID."""
    result = []
    for d in _lsblk():
        if d.get("type") != "disk":
            continue
        parts = []
        for p in _volumes(d, True):
            mounts = _mounts(p)
            fstype = p.get("fstype") or _udev_props("/dev/" + p["name"]).get("ID_FS_TYPE", "")
            info = {"name": p["name"], "size": int(p.get("size") or 0), "mount": mounts[0] if mounts else None,
                    "fstype": fstype, "used": None, "total": None}
            if info["mount"]:
                try:
                    st = os.statvfs(info["mount"])
                    used = (st.f_blocks - st.f_bfree) * st.f_frsize
                    info["used"], info["total"] = used, used + st.f_bavail * st.f_frsize
                except OSError:
                    pass
            parts.append(info)
        if parts:
            result.append({"name": d["name"], "size": int(d.get("size") or 0),
                           "model": (d.get("model") or "").strip(), "parts": parts})
    return result


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            text = f"{n:.0f} {unit}" if unit in ("B", "KB", "MB") or n >= 100 else f"{n:.1f} {unit}"
            return text
        n /= 1024


def machine():
    vendor = read("/sys/class/dmi/id/sys_vendor", "")
    product = read("/sys/class/dmi/id/product_name", "")
    if vendor and product.lower().startswith(vendor.lower()):
        return product
    return f"{vendor} {product}".strip() or "Computer"


def distro():
    for line in read("/etc/os-release", "").splitlines():
        if line.startswith("PRETTY_NAME="):
            return line.split("=", 1)[1].strip('"')
    return "Linux"
