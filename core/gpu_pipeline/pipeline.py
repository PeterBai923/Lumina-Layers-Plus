"""
Unified GPU pipeline for image preview processing.

Provides a complete GPU-accelerated pipeline that integrates:
- Image downsampling
- Color space conversion (RGB ↔ LAB)
- K-Means quantization
- Color mapping
"""

import torch
import torch.nn.functional as F
import numpy as np
import time
from typing import Tuple, Optional, Dict, Any

try:
    import kornia
    HAS_KORNIA = True
except ImportError:
    kornia = None
    HAS_KORNIA = False

from core.utils.logger import get_logger
from core.utils.color_conversion import rgb_to_lab, lab_to_rgb
from core.utils.gpu_device import GPUDeviceManager
from .downsampling import downsample_image_gpu, upsample_image_gpu
from .color_mapping import map_colors_gpu
from core.utils.color_encoding import build_color_lut, lookup_colors

logger = get_logger("PIPELINE")


def bilateral_filter_gpu(rgb_tensor: torch.Tensor, sigma_color: float, sigma_space: float) -> torch.Tensor:
    """
    GPU bilateral filter using kornia.

    Args:
        rgb_tensor: (H, W, 3) float tensor in range [0, 255]
        sigma_color: Color space sigma
        sigma_space: Spatial sigma

    Returns:
        Filtered tensor (H, W, 3) uint8
    """
    if not HAS_KORNIA:
        raise RuntimeError("kornia is required for GPU bilateral filter. Install with: pip install kornia")

    # (H, W, 3) -> (1, 3, H, W)
    x = rgb_tensor.permute(2, 0, 1).unsqueeze(0).float() / 255.0

    # kornia bilateral_blur: sigma_color is float, sigma_space is tuple
    filtered = kornia.filters.bilateral_blur(
        x,
        kernel_size=(9, 9),
        sigma_color=sigma_color / 255.0,  # float value
        sigma_space=(sigma_space, sigma_space)  # tuple
    )

    # Back to (H, W, 3) uint8
    return (filtered.squeeze(0).permute(1, 2, 0) * 255).clamp(0, 255).to(torch.uint8)


def median_filter_gpu(rgb_tensor: torch.Tensor, kernel_size: int) -> torch.Tensor:
    """
    GPU median filter using kornia.

    Args:
        rgb_tensor: (H, W, 3) tensor
        kernel_size: Kernel size (must be odd)

    Returns:
        Filtered tensor (H, W, 3) uint8
    """
    if not HAS_KORNIA:
        raise RuntimeError("kornia is required for GPU median filter. Install with: pip install kornia")

    # Ensure kernel size is odd
    kernel_size = kernel_size if kernel_size % 2 == 1 else kernel_size + 1

    # (H, W, 3) -> (1, 3, H, W)
    x = rgb_tensor.permute(2, 0, 1).unsqueeze(0).float()

    filtered = kornia.filters.median_blur(x, (kernel_size, kernel_size))

    # Back to (H, W, 3) uint8
    return filtered.squeeze(0).permute(1, 2, 0).to(torch.uint8)


class GPUPipeline:
    """GPU-only pipeline for image preview processing."""

    def __init__(self):
        self.device_manager = GPUDeviceManager()
        if not self.device_manager.is_cuda_available():
            raise RuntimeError("CUDA is not available. GPU is required.")
        self.device = self.device_manager.get_device()
        logger.info("GPU acceleration enabled: %s", torch.cuda.get_device_name())

    def process_preview(
        self,
        rgb_arr: np.ndarray,
        quantize_colors: int,
        lut_rgb: np.ndarray,
        lut_lab: np.ndarray,
        ref_stacks: np.ndarray,
        layer_count: int,
        blur_kernel: int = 0,
        smooth_sigma: float = 0.0,
        target_pixels: int = 500_000,
    ) -> Tuple[np.ndarray, np.ndarray, Optional[Dict[str, Any]]]:
        """
        Process image preview on GPU.

        Args:
            rgb_arr: Input RGB array (H, W, 3), dtype uint8
            quantize_colors: Number of K-Means clusters
            lut_rgb: LUT RGB colors (M, 3), dtype uint8
            lut_lab: LUT LAB colors (M, 3), dtype float64
            ref_stacks: Reference stacks array (M, layer_count), dtype uint8
            layer_count: Number of layers
            blur_kernel: Median filter kernel size (0=disabled)
            smooth_sigma: Bilateral filter sigma (0=disabled)
            target_pixels: Target pixel count for downsampling

        Returns:
            tuple: (matched_rgb, material_matrix, debug_data)
        """
        total_start = time.time()
        debug_data = {"timings": {}, "gpu_used": True}

        h, w = rgb_arr.shape[:2]
        total_pixels = h * w

        # Step 1: Upload to GPU
        t0 = time.time()
        rgb_tensor = torch.from_numpy(rgb_arr.astype(np.float32)).to(self.device)
        debug_data["timings"]["upload"] = time.time() - t0

        # Step 2: Downsample (if needed)
        t0 = time.time()
        if total_pixels > target_pixels:
            rgb_small, scale_factor = downsample_image_gpu(rgb_tensor, target_pixels)
            logger.info("Downsampled: %s×%s → %s×%s (scale=%.2f)", w, h, rgb_small.shape[1], rgb_small.shape[0], scale_factor)
        else:
            rgb_small = rgb_tensor
            scale_factor = 1.0
        debug_data["timings"]["downsample"] = time.time() - t0

        # Step 3: Bilateral and median filters (GPU)
        t0 = time.time()
        if smooth_sigma > 0:
            rgb_small = bilateral_filter_gpu(rgb_small, smooth_sigma, smooth_sigma)

        if blur_kernel > 0:
            rgb_small = median_filter_gpu(rgb_small, blur_kernel)

        debug_data["timings"]["filtering"] = time.time() - t0

        # Step 4: K-Means quantization
        t0 = time.time()
        rgb_small_cpu = rgb_small.cpu().numpy()
        # Ensure correct shape (H, W, 3)
        if rgb_small_cpu.ndim == 2:
            rgb_small_cpu = np.stack([rgb_small_cpu] * 3, axis=-1)
        pixels = rgb_small_cpu.reshape(-1, 3).astype(np.float32)

        from core.gpu_kmeans import KMeansBackend
        backend = KMeansBackend()
        centers = backend.quantize(pixels, k=quantize_colors, max_iter=50, tol=0.5, n_init=5)

        debug_data["timings"]["kmeans"] = time.time() - t0

        # Step 5: Map centers to full image (GPU)
        t0 = time.time()
        centers_tensor = torch.from_numpy(centers).to(self.device)
        pixels_tensor = rgb_small.reshape(-1, 3).float().to(self.device)

        # Find nearest center for each pixel
        pixel_indices = map_colors_gpu(pixels_tensor, centers_tensor, use_amp=True)

        # Quantized image
        quantized = centers[pixel_indices.cpu().numpy()].reshape(rgb_small_cpu.shape)
        debug_data["timings"]["quantize_mapping"] = time.time() - t0

        # Step 6: Post-quantization cleanup (GPU)
        t0 = time.time()
        quantized_tensor = torch.from_numpy(quantized).to(self.device)
        quantized_tensor = median_filter_gpu(quantized_tensor, 3)
        quantized = quantized_tensor.cpu().numpy()
        debug_data["timings"]["cleanup"] = time.time() - t0

        # Step 7: Find unique colors and map to LUT
        t0 = time.time()
        unique_colors = np.unique(quantized.reshape(-1, 3), axis=0)
        logger.info("Found %s unique colors", len(unique_colors))

        # Convert unique colors to LAB (GPU)
        unique_tensor = torch.from_numpy(unique_colors.astype(np.float32)).to(self.device)
        unique_lab_tensor = rgb_to_lab(unique_tensor)
        unique_lab = unique_lab_tensor.cpu().numpy()

        # Map to LUT (GPU)
        lut_lab_tensor = torch.from_numpy(lut_lab.astype(np.float32)).to(self.device)
        unique_indices_tensor = map_colors_gpu(unique_lab_tensor, lut_lab_tensor, use_amp=True)
        unique_indices = unique_indices_tensor.cpu().numpy()

        debug_data["timings"]["lut_mapping"] = time.time() - t0

        # Step 8: Build color lookup table and apply to full image
        t0 = time.time()
        sorted_codes, sorted_lut_indices = build_color_lut(unique_colors, unique_indices)

        flat_quantized = quantized.reshape(-1, 3)
        lut_indices = lookup_colors(flat_quantized, sorted_codes, sorted_lut_indices)

        matched_rgb = lut_rgb[lut_indices].reshape(quantized.shape)
        material_matrix = ref_stacks[lut_indices].reshape(
            quantized.shape[0], quantized.shape[1], layer_count
        )

        # Resize back to original dimensions if downsampling was applied (GPU)
        if scale_factor > 1.0:
            t_resize = time.time()
            original_h, original_w = h, w

            # GPU upsample for matched_rgb
            matched_tensor = torch.from_numpy(matched_rgb.astype(np.float32)).to(self.device)
            matched_tensor = upsample_image_gpu(matched_tensor, original_h, original_w, mode='nearest')
            matched_rgb = matched_tensor.cpu().numpy().astype(np.uint8)

            # GPU upsample for material_matrix (per channel)
            material_resized = np.zeros(
                (original_h, original_w, layer_count), dtype=material_matrix.dtype
            )
            for c in range(layer_count):
                channel_tensor = torch.from_numpy(
                    material_matrix[:, :, c].astype(np.float32)
                ).to(self.device)
                channel_tensor = upsample_image_gpu(channel_tensor, original_h, original_w, mode='nearest')
                material_resized[:, :, c] = channel_tensor.cpu().numpy().astype(material_matrix.dtype)
            material_matrix = material_resized

            # GPU upsample for quantized
            quantized_tensor = torch.from_numpy(quantized.astype(np.float32)).to(self.device)
            quantized_tensor = upsample_image_gpu(quantized_tensor, original_h, original_w, mode='nearest')
            quantized = quantized_tensor.cpu().numpy().astype(np.uint8)

            debug_data["timings"]["upscale"] = time.time() - t_resize

        debug_data["timings"]["final_mapping"] = time.time() - t0
        debug_data["quantized_image"] = quantized.copy()

        total_time = time.time() - total_start
        debug_data["timings"]["total"] = total_time

        logger.info("Total GPU processing complete: %.2fs", total_time)

        return matched_rgb, material_matrix, debug_data

    def is_gpu_active(self) -> bool:
        return True

    def get_device_info(self) -> Dict[str, Any]:
        return self.device_manager.get_device_info()