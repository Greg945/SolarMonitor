"""
Configuration manager for SolarMonitor.
Handles persistent settings stored in config.json.
"""

import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

DEFAULT_CONFIG = {
    "ip": "192.168.178.160",
    "port": 30000,
    "interval": 5,
    "pv1_divisor": 10.0,
    "auto_start_logger": True,
    "auto_refresh": True,
    "refresh_seconds": 5,
    "location_name": "Oestrich-Winkel",
    "latitude": 50.0085,
    "longitude": 8.0199,
    "panel_names": {
      "pv1": "PV 1",
      "pv2": "PV 2",
      "pv3": "PV 3",
      "pv4": "PV 4"
    }
}


def load_config() -> dict:
    """Loads configuration from config.json, or creates it with defaults."""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        # Ensure all default keys exist
        updated = False
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
                updated = True

        if "panel_names" not in cfg or not isinstance(cfg["panel_names"], dict):
            cfg["panel_names"] = dict(DEFAULT_CONFIG["panel_names"])
            updated = True
        else:
            for p_key, p_default in DEFAULT_CONFIG["panel_names"].items():
                if p_key not in cfg["panel_names"]:
                    cfg["panel_names"][p_key] = p_default
                    updated = True

        if updated:
            save_config(cfg)

        return cfg
    except Exception as e:
        print(f"Error reading config.json: {e}. Using defaults.")
        return dict(DEFAULT_CONFIG)


def save_config(cfg: dict):
    """Saves configuration dict to config.json."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=4, ensure_ascii=False)


def get_panel_names() -> dict:
    """Returns mapping of pv1, pv2, pv3, pv4 to display names."""
    cfg = load_config()
    return cfg.get("panel_names", DEFAULT_CONFIG["panel_names"])
