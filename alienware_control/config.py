"""Settings file (~/.config/alienware-control/config.json).

Kept free of GTK imports so background helpers (diskwatch.py) stay small.
"""
import json
import os

from i18n import LANGUAGES

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "alienware-control")
CONFIG = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_CONFIG = {
    "theme": "gtk",
    "language": "auto",
    "interval": 2,
    "unit": "C",
    "login_lights": True,
    "disk_alert": True,
    "disk_threshold": 90,
}
THEME_NAMES = {"gtk": "GTK (system)", "neon": "Neon", "amoled": "Real Amoled"}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG) as f:
            data = json.load(f)
        if isinstance(data, dict):
            for key, default in DEFAULT_CONFIG.items():
                if key in data and type(data[key]) is type(default):
                    cfg[key] = data[key]
    except (OSError, ValueError):
        pass
    if cfg["theme"] not in THEME_NAMES:
        cfg["theme"] = "gtk"
    if cfg["language"] != "auto" and cfg["language"] not in LANGUAGES:
        cfg["language"] = "auto"
    if cfg["interval"] not in (1, 2, 5):
        cfg["interval"] = 2
    if cfg["unit"] not in ("C", "F"):
        cfg["unit"] = "C"
    cfg["disk_threshold"] = max(50, min(99, cfg["disk_threshold"]))
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG)
