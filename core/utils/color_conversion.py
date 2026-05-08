import numpy as np
import torch
from typing import Union

TORCH_AVAILABLE = True


def rgb_to_lab(rgb_tensor: torch.Tensor) -> torch.Tensor:
    """
    Convert RGB to LAB color space (GPU only).

    Args:
        rgb_tensor: RGB tensor (N, 3) or (H, W, 3), range [0, 255]

    Returns:
        torch.Tensor: LAB tensor, range L:[0,255], a:[0,255], b:[0,255]
    """
    if not rgb_tensor.is_cuda:
        raise ValueError("Input must be a CUDA tensor")

    # Ensure input is in correct range
    rgb = rgb_tensor.clamp(0, 255) / 255.0  # Normalize to [0, 1]

    # Step 1: RGB → linear RGB (remove gamma correction)
    mask = rgb > 0.04045
    linear_rgb = torch.where(
        mask,
        ((rgb + 0.055) / 1.055) ** 2.4,
        rgb / 12.92
    )

    # Step 2: Linear RGB → XYZ (D65 illuminant)
    if linear_rgb.ndim == 2:
        xyz = torch.stack([
            linear_rgb[:, 0] * 0.4124564 + linear_rgb[:, 1] * 0.3575761 + linear_rgb[:, 2] * 0.1804375,
            linear_rgb[:, 0] * 0.2126729 + linear_rgb[:, 1] * 0.7151522 + linear_rgb[:, 2] * 0.0721750,
            linear_rgb[:, 0] * 0.0193339 + linear_rgb[:, 1] * 0.1191920 + linear_rgb[:, 2] * 0.9503041,
        ], dim=1)
    else:
        xyz = torch.stack([
            linear_rgb[..., 0] * 0.4124564 + linear_rgb[..., 1] * 0.3575761 + linear_rgb[..., 2] * 0.1804375,
            linear_rgb[..., 0] * 0.2126729 + linear_rgb[..., 1] * 0.7151522 + linear_rgb[..., 2] * 0.0721750,
            linear_rgb[..., 0] * 0.0193339 + linear_rgb[..., 1] * 0.1191920 + linear_rgb[..., 2] * 0.9503041,
        ], dim=-1)

    # Step 3: XYZ → LAB (D65 reference white: X=0.95047, Y=1.0, Z=1.08883)
    xyz_norm = xyz / torch.tensor([0.95047, 1.0, 1.08883], device=xyz.device, dtype=xyz.dtype)

    # Apply f function
    threshold = 0.008856
    mask = xyz_norm > threshold
    f_xyz = torch.where(
        mask,
        xyz_norm ** (1.0 / 3.0),
        7.787 * xyz_norm + 16.0 / 116.0
    )

    # Calculate LAB values
    if f_xyz.ndim == 2:
        L = 116.0 * f_xyz[:, 1] - 16.0
        a = 500.0 * (f_xyz[:, 0] - f_xyz[:, 1])
        b = 200.0 * (f_xyz[:, 1] - f_xyz[:, 2])
    else:
        L = 116.0 * f_xyz[..., 1] - 16.0
        a = 500.0 * (f_xyz[..., 0] - f_xyz[..., 1])
        b = 200.0 * (f_xyz[..., 1] - f_xyz[..., 2])

    # Scale to OpenCV's 0-255 range
    L = L * 255.0 / 100.0
    a = a + 128.0
    b = b + 128.0

    # Stack LAB channels
    if xyz.ndim == 2:
        lab = torch.stack([L, a, b], dim=1)
    else:
        lab = torch.stack([L, a, b], dim=-1)

    return lab.clamp(0, 255)


def lab_to_rgb(lab_tensor: torch.Tensor) -> torch.Tensor:
    """
    Convert LAB to RGB color space (GPU only).

    Args:
        lab_tensor: LAB tensor (N, 3) or (H, W, 3), range L:[0,255], a:[0,255], b:[0,255]

    Returns:
        torch.Tensor: RGB tensor, range [0, 255]
    """
    if not lab_tensor.is_cuda:
        raise ValueError("Input must be a CUDA tensor")

    # Normalize LAB from OpenCV's 0-255 range
    if lab_tensor.ndim == 2:
        L = lab_tensor[:, 0] * 100.0 / 255.0
        a = lab_tensor[:, 1] - 128.0
        b = lab_tensor[:, 2] - 128.0
    else:
        L = lab_tensor[..., 0] * 100.0 / 255.0
        a = lab_tensor[..., 1] - 128.0
        b = lab_tensor[..., 2] - 128.0

    # Calculate f(Y), f(X), f(Z)
    f_y = (L + 16.0) / 116.0
    f_x = a / 500.0 + f_y
    f_z = f_y - b / 200.0

    # Stack f values
    if lab_tensor.ndim == 2:
        f_xyz = torch.stack([f_x, f_y, f_z], dim=1)
    else:
        f_xyz = torch.stack([f_x, f_y, f_z], dim=-1)

    # Inverse f function
    threshold = 0.206893
    mask = f_xyz > threshold
    xyz_norm = torch.where(
        mask,
        f_xyz ** 3,
        (f_xyz - 16.0 / 116.0) / 7.787
    )

    # Scale by reference white (D65)
    ref_white = torch.tensor([0.95047, 1.0, 1.08883], device=lab_tensor.device, dtype=lab_tensor.dtype)
    xyz = xyz_norm * ref_white

    # XYZ → linear RGB
    if xyz.ndim == 2:
        linear_rgb = torch.stack([
            xyz[:, 0] * 3.2404542 + xyz[:, 1] * (-1.5371385) + xyz[:, 2] * (-0.4985314),
            xyz[:, 0] * (-0.9692660) + xyz[:, 1] * 1.8760108 + xyz[:, 2] * 0.0415560,
            xyz[:, 0] * 0.0556434 + xyz[:, 1] * (-0.2040259) + xyz[:, 2] * 1.0572252,
        ], dim=1)
    else:
        linear_rgb = torch.stack([
            xyz[..., 0] * 3.2404542 + xyz[..., 1] * (-1.5371385) + xyz[..., 2] * (-0.4985314),
            xyz[..., 0] * (-0.9692660) + xyz[..., 1] * 1.8760108 + xyz[..., 2] * 0.0415560,
            xyz[..., 0] * 0.0556434 + xyz[..., 1] * (-0.2040259) + xyz[..., 2] * 1.0572252,
        ], dim=-1)

    # Clamp linear RGB to [0, 1]
    linear_rgb = linear_rgb.clamp(0, 1)

    # Apply gamma correction (sRGB)
    threshold = 0.0031308
    mask = linear_rgb > threshold
    rgb = torch.where(
        mask,
        1.055 * (linear_rgb ** (1.0 / 2.4)) - 0.055,
        12.92 * linear_rgb
    )

    # Scale to [0, 255]
    return (rgb * 255.0).clamp(0, 255)