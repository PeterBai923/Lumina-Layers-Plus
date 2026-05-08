"""
Lumina Studio - Color Module

颜色处理相关模块，包含分析、匹配、合并、替换等功能。
"""

from core.color.analyzer import ColorAnalyzer, ColorAnalysisResult, analyze_recommended_colors
from core.color.matching import HueAwareColorMatcher
from core.color.merger import ColorMerger
from core.color.replacement import ColorReplacementManager
from core.color.formats import rgb_to_hex, hex_to_rgb
from core.color.lut import LUTMerger

__all__ = [
    "ColorAnalyzer",
    "ColorAnalysisResult",
    "analyze_recommended_colors",
    "HueAwareColorMatcher",
    "ColorMerger",
    "ColorReplacementManager",
    "rgb_to_hex",
    "hex_to_rgb",
    "LUTMerger",
]
