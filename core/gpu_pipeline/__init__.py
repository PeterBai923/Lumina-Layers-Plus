"""
GPU-accelerated pipeline module for image preview processing.

Provides complete GPU pipeline for image processing.
"""

from core.utils.color_conversion import (
    rgb_to_lab,
    lab_to_rgb,
)
from .downsampling import (
    downsample_image_gpu,
    upsample_image_gpu,
    resize_image_gpu,
    calculate_downsample_size
)
from .color_mapping import (
    map_colors_gpu,
    batch_color_distance_gpu
)
from .pipeline import GPUPipeline

__all__ = [
    # Color transforms
    'rgb_to_lab',
    'lab_to_rgb',

    # Resizing
    'downsample_image_gpu',
    'upsample_image_gpu',
    'resize_image_gpu',
    'calculate_downsample_size',

    # Color mapping
    'map_colors_gpu',
    'batch_color_distance_gpu',

    # Pipeline
    'GPUPipeline',
]