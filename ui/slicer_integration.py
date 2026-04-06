# -*- coding: utf-8 -*-
"""Lumina Studio - Slicer detection and integration."""

import os
import subprocess
import platform

if platform.system() == "Windows":
    import winreg

from .settings import _load_user_settings

# Known slicer identifiers for registry matching
_SLICER_KEYWORDS = {
    "bambu_studio":  {"match": ["bambu studio"], "name": "Bambu Studio"},
    "orca_slicer":   {"match": ["orcaslicer"],   "name": "OrcaSlicer"},
    "elegoo_slicer": {"match": ["elegooslicer", "elegoo slicer", "elegoo satellit"], "name": "ElegooSlicer"},
    "prusa_slicer":  {"match": ["prusaslicer"],  "name": "PrusaSlicer"},
    "cura":          {"match": ["ultimaker cura", "ultimaker-cura"], "name": "Ultimaker Cura"},
}


def _scan_registry_for_slicers():
    """Scan Windows registry Uninstall keys to find slicer executables.

    Returns dict: {slicer_id: {"name": display_name, "exe": exe_path}}
    Non-Windows platforms return empty dict.
    """
    if platform.system() != "Windows":
        return {}

    found = {}
    reg_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER,  r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]

    for hive, base_path in reg_paths:
        try:
            key = winreg.OpenKey(hive, base_path)
        except OSError:
            continue

        i = 0
        while True:
            try:
                subkey_name = winreg.EnumKey(key, i)
                i += 1
            except OSError:
                break

            try:
                subkey = winreg.OpenKey(key, subkey_name)
                try:
                    display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                except OSError:
                    subkey.Close()
                    continue

                # Try DisplayIcon first (most reliable for exe path)
                exe_path = None
                try:
                    icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                    # DisplayIcon can be "path.exe" or "path.exe,0"
                    # Also handle doubled paths like "F:\...\F:\...\exe"
                    icon = icon.split(",")[0].strip().strip('"')
                    # Handle doubled path: if path appears twice, take the second half
                    parts = icon.split("\\")
                    for idx in range(1, len(parts)):
                        candidate = "\\".join(parts[idx:])
                        if os.path.isfile(candidate):
                            exe_path = candidate
                            break
                    if not exe_path and os.path.isfile(icon):
                        exe_path = icon
                except OSError:
                    pass

                # Fallback: try InstallLocation
                if not exe_path:
                    try:
                        install_loc = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                        if install_loc and os.path.isdir(install_loc):
                            for f in os.listdir(install_loc):
                                if f.lower().endswith(".exe") and "unins" not in f.lower():
                                    candidate = os.path.join(install_loc, f)
                                    if os.path.isfile(candidate):
                                        exe_path = candidate
                                        break
                    except OSError:
                        pass

                subkey.Close()

                if not exe_path or not exe_path.lower().endswith(".exe"):
                    continue

                # Match against known slicers
                dn_lower = display_name.lower()
                for sid, info in _SLICER_KEYWORDS.items():
                    if sid in found:
                        continue
                    for kw in info["match"]:
                        if kw in dn_lower:
                            # Skip CUDA-related entries that match "cura"
                            if sid == "cura" and ("cuda" in dn_lower or "nvidia" in dn_lower):
                                break
                            found[sid] = {"name": display_name.strip(), "exe": exe_path}
                            break
            except OSError:
                pass

        key.Close()

    return found


def detect_installed_slicers():
    """Detect installed slicers via registry + user saved paths.

    Returns list of (id, name, exe_path).
    """
    found = []

    # 1. Registry scan
    reg_slicers = _scan_registry_for_slicers()
    for sid, info in reg_slicers.items():
        found.append((sid, info["name"], info["exe"]))
        print(f"[SLICER] Registry: {info['name']} → {info['exe']}")

    # 2. User-saved custom paths
    prefs = _load_user_settings()
    custom_slicers = prefs.get("custom_slicers", {})
    for sid, exe in custom_slicers.items():
        if os.path.isfile(exe) and sid not in [s[0] for s in found]:
            name = _SLICER_KEYWORDS.get(sid, {}).get("name", sid)
            found.append((sid, name, exe))
            print(f"[SLICER] Custom: {name} → {exe}")

    if not found:
        print("[SLICER] No slicers detected")
    return found


def open_in_slicer(file_path, slicer_id):
    """Open a 3MF file in the specified slicer."""
    if not file_path:
        return "[ERROR] 没有可打开的文件 / No file to open"

    actual_path = file_path
    if hasattr(file_path, 'name'):
        actual_path = file_path.name

    if not os.path.isfile(actual_path):
        return f"[ERROR] 文件不存在: {actual_path}"

    # Find exe from detected slicers
    for sid, name, exe in _INSTALLED_SLICERS:
        if sid == slicer_id:
            try:
                subprocess.Popen([exe, actual_path])
                return f"[OK] 已在 {name} 中打开"
            except Exception as e:
                return f"[ERROR] 启动 {name} 失败: {e}"

    return f"[ERROR] 未找到切片软件: {slicer_id}"


# Detect slicers at startup
_INSTALLED_SLICERS = detect_installed_slicers()


def _get_slicer_choices(lang="zh"):
    """Build dropdown choices: installed slicers + download option."""
    choices = []
    for sid, name, exe in _INSTALLED_SLICERS:
        label_zh = f"在 {name} 中打开"
        label_en = f"Open in {name}"
        choices.append((label_zh if lang == "zh" else label_en, sid))

    dl_label = "📥 下载 3MF" if lang == "zh" else "📥 Download 3MF"
    choices.append((dl_label, "download"))
    return choices


def _get_default_slicer():
    """Get the saved or first available slicer id."""
    prefs = _load_user_settings()
    saved = prefs.get("last_slicer", None)
    installed_ids = [s[0] for s in _INSTALLED_SLICERS]
    if saved and saved in installed_ids:
        return saved
    if installed_ids:
        return installed_ids[0]
    return "download"


def _slicer_css_class(slicer_id):
    """Map slicer_id to CSS class for button color."""
    if "bambu" in slicer_id:
        return "slicer-bambu"
    if "orca" in slicer_id:
        return "slicer-orca"
    if "elegoo" in slicer_id:
        return "slicer-elegoo"
    return "slicer-download"
