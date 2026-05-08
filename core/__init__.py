# -*- coding: utf-8 -*-
"""
Lumina Studio - Core Module (Refactored)
核心算法模块 - 重构版本
"""

# Patch numpy.asscalar for colormath compatibility (numpy >= 2.0)
import numpy as np
setattr(np, "asscalar", lambda a: a.item())

# Calibration module
from .calibration import generate_calibration_board

# Extractor module
from .extractor import (
    rotate_image,
    draw_corner_points,
    apply_auto_white_balance,
    apply_brightness_correction,
    run_extraction,
    probe_lut_cell,
    manual_fix_cell
)

# Converter module (refactored)
from .converter import (
    convert_image_to_3d,
    generate_preview_cached,
    render_preview,
    on_preview_click,
    update_preview_with_loop,
    on_remove_loop,
    generate_final_model
)

# Color subpackage
from .color import (
    ColorAnalyzer,
    ColorAnalysisResult,
    analyze_recommended_colors,
    HueAwareColorMatcher,
    ColorMerger,
    ColorReplacementManager,
    rgb_to_hex,
    hex_to_rgb,
    LUTMerger,
)

# Image subpackage
from .image import (
    LuminaImageProcessor,
    ImagePreprocessor,
    CropRegion,
    ImageInfo,
    cleanup_isolated_pixels,
)

# Mesh subpackage
from .mesh import (
    HighFidelityMesher,
    get_mesher,
    CUBE_FACES,
    CUBE_FACES_NP,
    create_keychain_loop,
    HeightmapLoader,
)

# LUT subpackage
from .lut import (
    ColorQueryResult,
    ColorCountDetector,
    StackFileManager,
    StackLUTLoader,
    ColorQueryEngine,
    get_color_name_from_rgb,
)

__all__ = [
    # Calibration
    'generate_calibration_board',

    # Extractor
    'rotate_image',
    'draw_corner_points',
    'apply_auto_white_balance',
    'apply_brightness_correction',
    'run_extraction',
    'probe_lut_cell',
    'manual_fix_cell',

    # Converter (public API)
    'convert_image_to_3d',
    'generate_preview_cached',
    'render_preview',
    'on_preview_click',
    'update_preview_with_loop',
    'on_remove_loop',
    'generate_final_model',

    # Color subpackage
    'ColorAnalyzer',
    'ColorAnalysisResult',
    'analyze_recommended_colors',
    'HueAwareColorMatcher',
    'ColorMerger',
    'ColorReplacementManager',
    'rgb_to_hex',
    'hex_to_rgb',
    'LUTMerger',

    # Image subpackage
    'LuminaImageProcessor',
    'ImagePreprocessor',
    'CropRegion',
    'ImageInfo',
    'cleanup_isolated_pixels',

    # Mesh subpackage
    'HighFidelityMesher',
    'get_mesher',
    'CUBE_FACES',
    'CUBE_FACES_NP',
    'create_keychain_loop',
    'HeightmapLoader',

    # LUT subpackage
    'ColorQueryResult',
    'ColorCountDetector',
    'StackFileManager',
    'StackLUTLoader',
    'ColorQueryEngine',
    'get_color_name_from_rgb',
]
