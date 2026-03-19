"""
双边滤波模块（Bilateral Filter）

从 image_processing.py 的 _process_high_fidelity_mode Step 1 搬入。
边缘保持平滑滤波，减少噪声同时保留边缘细节。

Bilateral filter for edge-preserving smoothing.
Extracted from _process_high_fidelity_mode Step 1.
"""

import time
import numpy as np
import cv2


def apply_bilateral_filter(rgb: np.ndarray, sigma: float, d: int = 9) -> np.ndarray:
    """双边滤波（边缘保持平滑）。
    Bilateral filter for edge-preserving smoothing.

    Args:
        rgb: (H, W, 3) uint8 RGB 图像数组
        sigma: 滤波 sigma 值（sigmaColor 和 sigmaSpace 共用），0 表示禁用
        d: 滤波直径，默认 9

    Returns:
        (H, W, 3) uint8 滤波后的 RGB 图像数组
    """
    t0 = time.time()
    if sigma > 0:
        print(f"[IMAGE_PROCESSOR] Applying bilateral filter (sigma={sigma})...")
        rgb_processed = cv2.bilateralFilter(
            rgb.astype(np.uint8),
            d=d,
            sigmaColor=sigma,
            sigmaSpace=sigma
        )
    else:
        print(f"[IMAGE_PROCESSOR] Bilateral filter disabled (sigma=0)")
        rgb_processed = rgb.astype(np.uint8)
    print(f"[IMAGE_PROCESSOR] ⏱️ Bilateral filter: {time.time() - t0:.2f}s")
    return rgb_processed
