"""
Core utilities package for shared functionality.

This package provides unified implementations of commonly used operations
to eliminate code duplication across the codebase.

Modules:
    color_conversion: RGB↔LAB color space conversions (GPU)
    color_encoding: Color encoding and lookup table utilities
    gpu_device: GPU device management and batch size calculation
    stats: Usage statistics
    lut_manager: LUT preset management
    bambu_3mf_writer: BambuStudio-compatible 3MF export
    color_recipe_logger: Color recipe report generation
"""

from .color_conversion import (
    rgb_to_lab,
    lab_to_rgb,
)

from .color_encoding import (
    encode_rgb_colors,
    build_color_lut,
    lookup_colors,
)

from .gpu_device import GPUDeviceManager

from .lut_detection import (
    SIZE_TO_COLOR_COUNT,
    SIZE_TO_MODE_NAME,
    MODE_TO_COLOR_COUNT,
    detect_color_count_by_size,
    detect_mode_by_size,
)

from .stats import Stats
from .lut_manager import LUTManager

__all__ = [
    # Color conversion
    "rgb_to_lab",
    "lab_to_rgb",
    # Color encoding
    "encode_rgb_colors",
    "build_color_lut",
    "lookup_colors",
    # GPU device management
    "GPUDeviceManager",
    # LUT detection
    "SIZE_TO_COLOR_COUNT",
    "SIZE_TO_MODE_NAME",
    "MODE_TO_COLOR_COUNT",
    "detect_color_count_by_size",
    "detect_mode_by_size",
    # Stats
    "Stats",
    # LUT manager
    "LUTManager",
]