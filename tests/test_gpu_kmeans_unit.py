"""
Unit tests for GPU K-Means module.

Tests correctness, consistency, and edge cases for GPU-accelerated K-Means++.
"""

import pytest
import numpy as np
import torch

from core.utils.gpu_device import GPUDeviceManager
from core.gpu_kmeans import CUDAKMeansPlusPlus, KMeansBackend


class TestGPUDeviceManager:
    """Test GPU device manager singleton."""

    def test_singleton_pattern(self):
        """Test that device manager is singleton."""
        manager1 = GPUDeviceManager()
        manager2 = GPUDeviceManager()
        assert manager1 is manager2

    def test_cuda_detection(self):
        """Test CUDA availability detection."""
        manager = GPUDeviceManager()
        # Should return boolean
        assert isinstance(manager.is_cuda_available(), bool)

    def test_device_selection(self):
        """Test device selection when CUDA available."""
        manager = GPUDeviceManager()
        if manager.is_cuda_available():
            device = manager.get_device()
            assert device.type == 'cuda'

    def test_batch_size_calculation(self):
        """Test dynamic batch size calculation."""
        manager = GPUDeviceManager()
        batch_size = manager.get_batch_size_for_distance_matrix(1_000_000, 16)
        assert batch_size >= 10_000
        assert batch_size <= 1_000_000


class TestCUDAKMeansPlusPlus:
    """Test CUDA K-Means++ algorithm."""

    @pytest.fixture
    def simple_data(self):
        """Generate simple test data."""
        # Three distinct clusters
        cluster1 = np.random.randn(100, 3) * 0.1 + [0, 0, 0]
        cluster2 = np.random.randn(100, 3) * 0.1 + [1, 1, 1]
        cluster3 = np.random.randn(100, 3) * 0.1 + [2, 2, 2]
        return np.vstack([cluster1, cluster2, cluster3]).astype(np.float32)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_kmeans_plus_plus_initialization(self, simple_data):
        """Test K-Means++ initialization produces good centers."""
        manager = GPUDeviceManager()
        kmeans = CUDAKMeansPlusPlus(manager)

        device = manager.get_device()
        X = torch.from_numpy(simple_data).to(device)

        centers = kmeans._initialize_centers_kmeans_plus_plus(X, 3)

        # Should return 3 centers
        assert centers.shape == (3, 3)

        # Centers should be on GPU
        assert centers.device.type == 'cuda'

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_fit_basic(self, simple_data):
        """Test basic fit functionality."""
        manager = GPUDeviceManager()
        kmeans = CUDAKMeansPlusPlus(manager)

        centers = kmeans.fit(simple_data, k=3, max_iter=50, n_init=5)

        # Should return 3 centers
        assert centers.shape == (3, 3)

        # Centers should be numpy array
        assert isinstance(centers, np.ndarray)

        # Centers should be close to true cluster centers (order may differ)
        true_centers = np.array([[0, 0, 0], [1, 1, 1], [2, 2, 2]])

        # Match each found center to nearest true center
        from scipy.spatial.distance import cdist
        distances_matrix = cdist(centers, true_centers)
        min_distances = distances_matrix.min(axis=1)

        # All centers should be within 0.5 of some true center
        assert np.all(min_distances < 0.5)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_batch_processing(self):
        """Test batch processing for large datasets."""
        # Large dataset to trigger batch processing
        large_data = np.random.randn(500_000, 3).astype(np.float32)

        manager = GPUDeviceManager()
        kmeans = CUDAKMeansPlusPlus(manager)

        centers = kmeans.fit(large_data, k=16, max_iter=20, n_init=3)

        assert centers.shape == (16, 3)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_reproducibility(self, simple_data):
        """Test reproducibility with fixed seed."""
        manager = GPUDeviceManager()
        kmeans = CUDAKMeansPlusPlus(manager)

        centers1 = kmeans.fit(simple_data, k=3, max_iter=50, n_init=5, seed=42)
        centers2 = kmeans.fit(simple_data, k=3, max_iter=50, n_init=5, seed=42)

        # Same seed should produce same results
        np.testing.assert_array_almost_equal(centers1, centers2, decimal=5)


class TestKMeansBackend:
    """Test unified K-Means backend."""

    @pytest.fixture
    def test_pixels(self):
        """Generate test pixel data."""
        return np.random.randn(10_000, 3).astype(np.float32) * 50 + 128

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_gpu_backend(self):
        """Test GPU backend initialization."""
        backend = KMeansBackend()
        assert backend.is_gpu_active()

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_gpu_quantization(self, test_pixels):
        """Test GPU quantization."""
        backend = KMeansBackend()

        centers = backend.quantize(test_pixels, k=16, max_iter=50, n_init=5)

        assert centers.shape == (16, 3)
        assert isinstance(centers, np.ndarray)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_single_color_image(self):
        """Test with single color (all pixels same)."""
        pixels = np.ones((1000, 3), dtype=np.float32) * 128

        backend = KMeansBackend()
        centers = backend.quantize(pixels, k=1, max_iter=10, n_init=1)

        assert centers.shape == (1, 3)
        np.testing.assert_array_almost_equal(centers[0], [128, 128, 128], decimal=1)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_small_k(self):
        """Test with small k value."""
        pixels = np.random.randn(1000, 3).astype(np.float32) * 50 + 128

        backend = KMeansBackend()
        centers = backend.quantize(pixels, k=2, max_iter=20, n_init=3)

        assert centers.shape == (2, 3)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_large_k(self):
        """Test with large k value."""
        pixels = np.random.randn(5000, 3).astype(np.float32) * 50 + 128

        backend = KMeansBackend()
        centers = backend.quantize(pixels, k=64, max_iter=20, n_init=3)

        assert centers.shape == (64, 3)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])