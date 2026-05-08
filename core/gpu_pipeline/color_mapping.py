"""
GPU-accelerated color mapping.

Provides batch color matching using torch.cdist.
"""

import torch
from typing import Optional

from core.utils.gpu_device import GPUDeviceManager


def map_colors_gpu(
    query_colors: torch.Tensor,
    lut_colors: torch.Tensor,
    batch_size: Optional[int] = None,
    use_amp: bool = True,
) -> torch.Tensor:
    """
    Map query colors to nearest LUT colors using GPU batch distance calculation.

    Args:
        query_colors: Query colors tensor (N, 3), range [0, 255], float32
        lut_colors: LUT colors tensor (M, 3), range [0, 255], float32
        batch_size: Batch size for distance calculation (auto-calculated if None)
        use_amp: Use automatic mixed precision (float16) to reduce memory usage

    Returns:
        torch.Tensor: Indices of nearest LUT colors for each query color, shape (N,)
    """
    device = query_colors.device
    n_queries = query_colors.shape[0]
    n_lut = lut_colors.shape[0]

    # Auto-calculate batch size based on available GPU memory
    if batch_size is None:
        device_manager = GPUDeviceManager()
        batch_size = device_manager.get_batch_size_for_color_mapping(n_queries, n_lut)

    # Initialize result tensor
    indices = torch.empty(n_queries, dtype=torch.long, device=device)

    # Process in batches
    for start_idx in range(0, n_queries, batch_size):
        end_idx = min(start_idx + batch_size, n_queries)
        batch_queries = query_colors[start_idx:end_idx]

        # Calculate distances using torch.cdist
        if use_amp:
            with torch.autocast("cuda"):
                distances = torch.cdist(
                    batch_queries.unsqueeze(0),
                    lut_colors.unsqueeze(0),
                    p=2,
                ).squeeze(0)
        else:
            distances = torch.cdist(
                batch_queries.unsqueeze(0), lut_colors.unsqueeze(0), p=2
            ).squeeze(0)

        # Find nearest LUT color for each query
        batch_indices = torch.argmin(distances, dim=1)
        indices[start_idx:end_idx] = batch_indices

        # Clean up intermediate tensors
        del distances, batch_indices

    return indices


def batch_color_distance_gpu(
    colors1: torch.Tensor, colors2: torch.Tensor, use_amp: bool = True
) -> torch.Tensor:
    """
    Calculate pairwise distances between two color sets on GPU.

    Args:
        colors1: First color set (N, 3), range [0, 255], float32
        colors2: Second color set (M, 3), range [0, 255], float32
        use_amp: Use automatic mixed precision

    Returns:
        torch.Tensor: Distance matrix (N, M)
    """
    if use_amp:
        with torch.autocast("cuda"):
            distances = torch.cdist(
                colors1.unsqueeze(0), colors2.unsqueeze(0), p=2
            ).squeeze(0)
    else:
        distances = torch.cdist(
            colors1.unsqueeze(0), colors2.unsqueeze(0), p=2
        ).squeeze(0)

    return distances
