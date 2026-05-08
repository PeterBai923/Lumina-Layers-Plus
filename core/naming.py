"""Naming_Service — 统一的文件命名服务模块。

负责生成 Lumina Studio 中所有输出文件的标准化文件名，
包含时间戳和模式信息，便于用户识别和管理生成的文件。
"""

import re
from datetime import datetime
from typing import Optional, Dict

from config import ModelingMode


# 建模模式 → 文件名标识映射
MODELING_MODE_TAGS: Dict[ModelingMode, str] = {
    ModelingMode.HIGH_FIDELITY: "HiFi",
}

# 颜色模式 → 文件名标识映射
COLOR_MODE_TAGS: Dict[str, str] = {
    "4-Color": "4C",
    "4-Color (1024 colors)": "4C",
    "CMYW": "4C",
    "RYBW": "4C",
    "5-Color Extended": "5C",
    "6-Color": "6C",
    "6-Color (Smart 1296)": "6C",
    "8-Color Max": "8C",
    "8-Color": "8C",
    "BW": "BW",
    "BW (Black & White)": "BW",
    "Merged": "Merged",
}


def _get_timestamp() -> str:
    """返回当前本地时间的时间戳字符串，格式 YYYYMMDD_HHmmss。"""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _sanitize(name: str) -> str:
    """移除文件名中操作系统不允许的特殊字符，替换为下划线。"""
    forbidden = '<>:"/\\|?*'
    for ch in forbidden:
        name = name.replace(ch, "_")
    return name


# Gradio/pywebview 临时文件前缀模式: tmp{random}_ (例如 tmpq7esd8mm_photo, tmpud7d8o06_photo)
_TEMP_PREFIX_RE = re.compile(r"^tmp[a-zA-Z0-9]{4,12}_")


def _strip_temp_prefix(name: str) -> str:
    """去除 Gradio/pywebview 生成的临时文件名前缀。"""
    return _TEMP_PREFIX_RE.sub("", name)


def generate_model_filename(
    base_name: str,
    modeling_mode: ModelingMode,
    color_mode: str,
    extension: str = ".3mf",
) -> str:
    """生成标准模型文件名。

    格式: {base_name}_Lumina_{mode_tag}_{color_tag}_{timestamp}{ext}

    - base_name 为空字符串时使用默认值 "untitled"
    - modeling_mode 未知时使用 "Unknown" 作为 mode tag
    - color_mode 未知时使用 "Unknown" 作为 color tag
    """
    base = _sanitize(_strip_temp_prefix(base_name.strip())) if base_name.strip() else "untitled"
    mode_tag = MODELING_MODE_TAGS.get(modeling_mode, "Unknown")
    color_tag = COLOR_MODE_TAGS.get(color_mode, "Unknown")
    ts = _get_timestamp()
    return f"{base}_Lumina_{mode_tag}_{color_tag}_{ts}{extension}"


def generate_preview_filename(
    base_name: str,
    extension: str = ".glb",
) -> str:
    """生成预览文件名。

    格式: {base_name}_Preview_{timestamp}{ext}

    - base_name 为空字符串时使用默认值 "untitled"
    """
    base = _sanitize(_strip_temp_prefix(base_name.strip())) if base_name.strip() else "untitled"
    ts = _get_timestamp()
    return f"{base}_Preview_{ts}{extension}"


def generate_calibration_filename(
    color_mode: str,
    calibration_type: str = "Standard",
    extension: str = ".3mf",
) -> str:
    """生成校准板文件名。

    格式: Lumina_Calibration_{calibration_type}_{color_tag}_{timestamp}{ext}

    - color_mode 未知时使用 "Unknown" 作为 color tag
    """
    color_tag = COLOR_MODE_TAGS.get(color_mode, "Unknown")
    safe_type = _sanitize(calibration_type)
    ts = _get_timestamp()
    return f"Lumina_Calibration_{safe_type}_{color_tag}_{ts}{extension}"


def generate_batch_filename(
    extension: str = ".zip",
) -> str:
    """生成批量输出文件名。

    格式: Lumina_Batch_{timestamp}{ext}
    """
    ts = _get_timestamp()
    return f"Lumina_Batch_{ts}{extension}"


