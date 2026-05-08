"""
GPU-accelerated image resizing.

Provides efficient image downscaling and upscaling using PyTorch interpolation.
"""

import torch
from typing import Tuple


def downsample_image_gpu(
    image_tensor: torch.Tensor,
    target_pixels: int = 500_000,
    mode: str = 'area'
) -> Tuple[torch.Tensor, float]:
    """
    Downsample image on GPU to target pixel count.

    Args:
        image_tensor: Image tensor (H, W, 3) or (H, W), range [0, 255], float32
        target_pixels: Target total pixel count (default: 500K)
        mode: Interpolation mode ('area', 'bilinear', 'nearest')
              - 'area': Area interpolation (best for downsampling, preserves colors)
              - 'bilinear': Bilinear interpolation (fast, may blur)
              - 'nearest': Nearest neighbor (fast, preserves edges)

    Returns:
        tuple: (downsampled_tensor, scale_factor)
    """
    # Get original dimensions
    if image_tensor.ndim == 3:
        h, w, c = image_tensor.shape
    else:
        h, w = image_tensor.shape
        c = None

    total_pixels = h * w

    # Check if downsampling is needed
    if total_pixels <= target_pixels:
        return image_tensor, 1.0

    # Calculate scale factor
    scale_factor = (total_pixels / target_pixels) ** 0.5

    # Calculate new dimensions
    new_h = int(h / scale_factor)
    new_w = int(w / scale_factor)

    # Ensure minimum size
    new_h = max(new_h, 1)
    new_w = max(new_w, 1)

    # Convert to (1, C, H, W) format for PyTorch interpolation
    if image_tensor.ndim == 3:
        # (H, W, 3) → (1, 3, H, W)
        tensor_4d = image_tensor.permute(2, 0, 1).unsqueeze(0)
    else:
        # (H, W) → (1, 1, H, W)
        tensor_4d = image_tensor.unsqueeze(0).unsqueeze(0)

    # Interpolate - only bilinear/bicubic/trilinear support align_corners
    kwargs = {'size': (new_h, new_w), 'mode': mode}
    if mode in ('linear', 'bilinear', 'bicubic', 'trilinear'):
        kwargs['align_corners'] = False
    downsampled = torch.nn.functional.interpolate(tensor_4d, **kwargs)

    # Convert back to (H, W, C) format
    if image_tensor.ndim == 3:
        downsampled = downsampled.squeeze(0).permute(1, 2, 0)
    else:
        downsampled = downsampled.squeeze(0).squeeze(0)

    return downsampled, scale_factor


def calculate_downsample_size(
    original_h: int,
    original_w: int,
    target_pixels: int
) -> Tuple[int, int, float]:
    """
    Calculate downsampled dimensions for target pixel count.

    Args:
        original_h: Original height
        original_w: Original width
        target_pixels: Target total pixel count

    Returns:
        tuple: (new_h, new_w, scale_factor)
    """
    total_pixels = original_h * original_w

    if total_pixels <= target_pixels:
        return original_h, original_w, 1.0

    scale_factor = (total_pixels / target_pixels) ** 0.5
    new_h = max(int(original_h / scale_factor), 1)
    new_w = max(int(original_w / scale_factor), 1)

    return new_h, new_w, scale_factor


def upsample_image_gpu(
    image_tensor: torch.Tensor,
    target_h: int,
    target_w: int,
    mode: str = 'nearest'
) -> torch.Tensor:
    """
    Upsample image on GPU to target dimensions.

    Args:
        image_tensor: Image tensor (H, W, 3) or (H, W), range [0, 255], float32
        target_h: Target height
        target_w: Target width
        mode: Interpolation mode ('nearest', 'bilinear', 'area')
              - 'nearest': Nearest neighbor (preserves edges, no interpolation)
              - 'bilinear': Bilinear interpolation (smooth, may blur)
              - 'area': Area interpolation (good for both up/down)

    Returns:
        Upsampled tensor with shape (target_h, target_w, C) or (target_h, target_w)
    """
    # Convert to (1, C, H, W) format for PyTorch interpolation
    if image_tensor.ndim == 3:
        # (H, W, 3) → (1, 3, H, W)
        tensor_4d = image_tensor.permute(2, 0, 1).unsqueeze(0)
    else:
        # (H, W) → (1, 1, H, W)
        tensor_4d = image_tensor.unsqueeze(0).unsqueeze(0)

    # Interpolate
    upsampled = torch.nn.functional.interpolate(
        tensor_4d,
        size=(target_h, target_w),
        mode=mode,
    )

    # Convert back to (H, W, C) format
    if image_tensor.ndim == 3:
        upsampled = upsampled.squeeze(0).permute(1, 2, 0)
    else:
        upsampled = upsampled.squeeze(0).squeeze(0)

    return upsampled


def resize_image_gpu(
    image_tensor: torch.Tensor,
    target_h: int = None,
    target_w: int = None,
    target_pixels: int = None,
    mode: str = 'area'
) -> Tuple[torch.Tensor, float]:
    """
    Resize image on GPU - unified function for both up and down sampling.

    Args:
        image_tensor: Image tensor (H, W, 3) or (H, W), range [0, 255], float32
        target_h: Target height (optional, used with target_w)
        target_w: Target width (optional, used with target_h)
        target_pixels: Target total pixel count (optional, auto-calculates dimensions)
        mode: Interpolation mode ('area', 'bilinear', 'nearest')

    Returns:
        tuple: (resized_tensor, scale_factor)
    """
    # Get original dimensions
    if image_tensor.ndim == 3:
        h, w, _ = image_tensor.shape
    else:
        h, w = image_tensor.shape

    # Calculate target dimensions
    if target_h is not None and target_w is not None:
        new_h, new_w = target_h, target_w
    elif target_pixels is not None:
        total_pixels = h * w
        if total_pixels <= target_pixels:
            return image_tensor, 1.0
        scale_factor = (total_pixels / target_pixels) ** 0.5
        new_h = max(int(h / scale_factor), 1)
        new_w = max(int(w / scale_factor), 1)
    else:
        raise ValueError("Either (target_h, target_w) or target_pixels must be provided")

    # Calculate scale factor
    scale_factor = max(h / new_h, w / new_w)

    # Convert to (1, C, H, W) format
    if image_tensor.ndim == 3:
        tensor_4d = image_tensor.permute(2, 0, 1).unsqueeze(0)
    else:
        tensor_4d = image_tensor.unsqueeze(0).unsqueeze(0)

    # Interpolate - only bilinear/bicubic/trilinear support align_corners
    kwargs = {'size': (new_h, new_w), 'mode': mode}
    if mode in ('linear', 'bilinear', 'bicubic', 'trilinear'):
        kwargs['align_corners'] = False
    resized = torch.nn.functional.interpolate(tensor_4d, **kwargs)

    # Convert back
    if image_tensor.ndim == 3:
        resized = resized.squeeze(0).permute(1, 2, 0)
    else:
        resized = resized.squeeze(0).squeeze(0)

    return resized, scale_factor