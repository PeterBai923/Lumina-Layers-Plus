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
    ) -> np.ndarray:
        """
        Quantize pixels using GPU K-Means.

        Args:
            pixels: Input pixels array (N, 3), dtype float32
            k: Number of clusters
            max_iter: Maximum iterations per run
            tol: Convergence tolerance
            n_init: Number of initialization runs
            seed: Random seed for reproducibility

        Returns:
            np.ndarray: Cluster centers (k, 3), dtype float32
        """
        if not isinstance(pixels, np.ndarray):
            raise TypeError("pixels must be numpy array")
        if pixels.ndim != 2 or pixels.shape[1] != 3:
            raise ValueError("pixels must have shape (N, 3)")
        if not isinstance(k, int) or k <= 0:
            raise ValueError("k must be positive integer")
        if k > pixels.shape[0]:
            raise ValueError("k cannot exceed number of pixels")

        return self.gpu_kmeans.fit(
            pixels, k, max_iter=max_iter, tol=tol, n_init=n_init, seed=seed
        )

    def is_gpu_active(self) -> bool:
        return True
