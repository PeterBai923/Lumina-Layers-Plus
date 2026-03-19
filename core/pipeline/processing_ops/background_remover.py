"""
背景移除模块（Background Remover）

从 image_processing.py 的 process_image 搬入背景移除逻辑。
包含 alpha 透明度检测和自动背景颜色检测。

Background removal using alpha transparency and auto background detection.
Extracted from process_image.
"""

import numpy as np


def remove_background(alpha_arr: np.ndarray, rgb_arr: np.ndarray,
                      auto_bg: bool, bg_tol: int) -> np.ndarray:
    """背景移除（alpha 透明度 + 自动背景检测）。
    Remove background using alpha transparency and optional auto background detection.

    Args:
        alpha_arr: (H, W) uint8 alpha 通道数组
        rgb_arr: (H, W, 3) uint8 RGB 图像数组（用于自动背景检测的参考图像）
        auto_bg: 是否启用自动背景检测
        bg_tol: 背景容差值

    Returns:
        (H, W) bool 实体掩码（mask_solid），True 表示非透明像素
    """
    # CRITICAL FIX: Identify transparent pixels BEFORE color processing
    # This prevents transparent areas from being matched to LUT colors
    mask_transparent = alpha_arr < 10
    print(f"[IMAGE_PROCESSOR] Found {np.sum(mask_transparent)} transparent pixels (alpha<10)")

    # Background removal - combine alpha transparency with optional auto-bg
    if auto_bg:
        bg_color = rgb_arr[0, 0]
        diff = np.sum(np.abs(rgb_arr.astype(np.int16) - bg_color.astype(np.int16)), axis=-1)
        mask_transparent = np.logical_or(mask_transparent, diff < bg_tol)

    mask_solid = ~mask_transparent
    return mask_solid
