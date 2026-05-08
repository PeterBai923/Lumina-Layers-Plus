"""
Lumina Studio - Image Module

图像处理相关模块，包含主处理器、预处理和清理功能。
"""

from core.image.processor import LuminaImageProcessor
from core.image.preprocessor import ImagePreprocessor, CropRegion, ImageInfo
from core.image.cleanup import cleanup_isolated_pixels

__all__ = [
    "LuminaImageProcessor",
    "ImagePreprocessor",
    "CropRegion",
    "ImageInfo",
    "cleanup_isolated_pixels",
]
