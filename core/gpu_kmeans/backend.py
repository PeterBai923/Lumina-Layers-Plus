"""
Author: Peter_Bai
Date: 2026-05-08 10:44:13
KKDY保佑代码无BUG!: 
"""
import numpy as np
from typing import Optional

from core.utils.gpu_device import GPUDeviceManager
from .kmeans_plusplus import CUDAKMeansPlusPlus


class KMeansBackend:
    """GPU-only K-Means backend using CUDA acceleration."""

    def __init__(self):
        self.device_manager = GPUDeviceManager()
        if not self.device_manager.is_cuda_available():
            raise RuntimeError("CUDA is not available. GPU is required.")
        self.gpu_kmeans = CUDAKMeansPlusPlus(self.device_manager)
        self.device = self.device_manager.get_device()

    def quantize(
        self,
        pixels: np.ndarray,
        k: int,
        max_iter: int = 100,
        tol: float = 1e-4,
        n_init: int = 10,
        seed: Optional[int] = None,
        feature_dim: int = 3,
    ) -> np.ndarray:
        """
        Quantize pixels using GPU K-Means.

        Args:
            pixels: Input pixels array (N, D), dtype float32, D >= feature_dim.
                    For spatial K-Means, D=5 with [R, G, B, x*weight, y*weight].
            k: Number of clusters
            max_iter: Maximum iterations per run
            tol: Convergence tolerance
            n_init: Number of initialization runs
            seed: Random seed for reproducibility
            feature_dim: Dimension of output features (default 3 for RGB).
                         If input has D > feature_dim, clustering uses all D dimensions
                         but only the first feature_dim dimensions are returned.

        Returns:
            np.ndarray: Cluster centers (k, feature_dim), dtype float32
        """
        if not isinstance(pixels, np.ndarray):
            raise TypeError("pixels must be numpy array")
        if pixels.ndim != 2 or pixels.shape[1] < feature_dim:
            raise ValueError(f"pixels must have shape (N, D) where D >= {feature_dim}")
        if not isinstance(k, int) or k <= 0:
            raise ValueError("k must be positive integer")
        if k > pixels.shape[0]:
            raise ValueError("k cannot exceed number of pixels")

        all_centers = self.gpu_kmeans.fit(
            pixels, k, max_iter=max_iter, tol=tol, n_init=n_init, seed=seed
        )

        return all_centers[:, :feature_dim]

    def is_gpu_active(self) -> bool:
        return True
