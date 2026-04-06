# -*- coding: utf-8 -*-
"""Lumina Studio - User settings persistence."""

import json
import os

from config import ModelingMode

CONFIG_FILE = "user_settings.json"


def load_last_lut_setting():
    """Load the last selected LUT name from the user settings file.

    Returns:
        str | None: LUT name if found, else None.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("last_lut", None)
        except Exception as e:
            print(f"Failed to load settings: {e}")
    return None


def save_last_lut_setting(lut_name):
    """Persist the current LUT selection to the user settings file.

    Args:
        lut_name: Display name of the selected LUT (or None to clear).
    """
    data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            pass

    data["last_lut"] = lut_name

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save settings: {e}")


def _load_user_settings():
    """Load all user settings from the settings file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_user_setting(key, value):
    """Save a single key-value pair to the user settings file."""
    data = _load_user_settings()
    data[key] = value
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save setting {key}: {e}")


def save_color_mode(color_mode):
    """Persist the selected color mode."""
    _save_user_setting("last_color_mode", color_mode)


def save_modeling_mode(modeling_mode):
    """Persist the selected modeling mode."""
    val = modeling_mode.value if hasattr(modeling_mode, 'value') else str(modeling_mode)
    _save_user_setting("last_modeling_mode", val)


def resolve_height_mode(radio_value: str) -> str:
    """Map the UI radio selection to the backend ``height_mode`` parameter.

    Args:
        radio_value: Current value of the height-mode radio button
                     (e.g. "深色凸起", "浅色凸起", "根据高度图").

    Returns:
        ``"heightmap"`` when the user selected heightmap mode,
        ``"color"`` for all colour-based modes.
    """
    if radio_value == "根据高度图":
        return "heightmap"
    return "color"
