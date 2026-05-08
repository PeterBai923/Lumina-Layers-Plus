"""
Unit tests for GPU pipeline components.

Tests individual modules:
- Color space conversion (RGB ↔ LAB)
- Downsampling
- Color mapping
"""

import pytest
import numpy as np
import cv2
import torch

from core.utils.color_conversion import rgb_to_lab, lab_to_rgb
from core.gpu_pipeline.downsampling import (
    downsample_image_gpu,
    calculate_downsample_size
)
from core.gpu_pipeline.color_mapping import map_colors_gpu


# Test fixtures
@pytest.fixture
def test_rgb_colors():
    """Generate test RGB colors."""
    return np.array([
        [255, 0, 0],    # Red
        [0, 255, 0],    # Green
        [0, 0, 255],    # Blue
        [255, 255, 0],  # Yellow
        [255, 0, 255],  # Magenta
        [0, 255, 255],  # Cyan
        [255, 255, 255],# White
        [0, 0, 0],      # Black
        [128, 128, 128] # Gray
    ], dtype=np.uint8)


@pytest.fixture
def test_image():
    """Generate test image (500x500)."""
    return np.random.randint(0, 256, (500, 500, 3), dtype=np.uint8)


@pytest.fixture
def large_test_image():
    """Generate large test image (1000x1000)."""
    return np.random.randint(0, 256, (1000, 1000, 3), dtype=np.uint8)


@pytest.fixture
def lut_colors():
    """Generate mock LUT colors."""
    return np.random.randint(0, 256, (100, 3), dtype=np.uint8)


class TestColorTransforms:
    """Test color space conversion."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_rgb_to_lab_gpu_accuracy(self, test_rgb_colors):
        """Test GPU RGB→LAB conversion matches OpenCV."""
        # Convert using GPU
        rgb_tensor = torch.from_numpy(test_rgb_colors.astype(np.float32)).cuda()
        lab_gpu = rgb_to_lab(rgb_tensor).cpu().numpy()

        # Convert using OpenCV
        bgr = cv2.cvtColor(test_rgb_colors.reshape(1, -1, 3), cv2.COLOR_RGB2BGR)
        lab_opencv = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab).astype(np.float64).reshape(-1, 3)

        # Check accuracy
        l_error = np.abs(lab_gpu[:, 0] - lab_opencv[:, 0])
        a_error = np.abs(lab_gpu[:, 1] - lab_opencv[:, 1])
        b_error = np.abs(lab_gpu[:, 2] - lab_opencv[:, 2])

        assert np.max(l_error) < 1.0, f"L channel error too large: {np.max(l_error)}"
        assert np.max(a_error) < 1.0, f"a channel error too large: {np.max(a_error)}"
        assert np.max(b_error) < 1.0, f"b channel error too large: {np.max(b_error)}"

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_lab_to_rgb_gpu_roundtrip(self, test_rgb_colors):
        """Test GPU LAB→RGB roundtrip conversion."""
        # RGB → LAB → RGB on GPU
        rgb_tensor = torch.from_numpy(test_rgb_colors.astype(np.float32)).cuda()
        lab_tensor = rgb_to_lab(rgb_tensor)
        rgb_back_tensor = lab_to_rgb(lab_tensor)
        rgb_back = rgb_back_tensor.cpu().numpy().astype(np.uint8)

        # Check accuracy (allow up to 2 levels difference)
        error = np.abs(test_rgb_colors.astype(np.float32) - rgb_back.astype(np.float32))
        assert np.max(error) < 2.0, f"Roundtrip error too large: {np.max(error)}"


class TestDownsampling:
    """Test image downsampling."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_downsample_gpu_basic(self, large_test_image):
        """Test GPU downsampling."""
        h, w = large_test_image.shape[:2]
        target_pixels = 500_000

        # Upload to GPU
        rgb_tensor = torch.from_numpy(large_test_image.astype(np.float32)).cuda()

        # Downsample
        downsampled, scale_factor = downsample_image_gpu(rgb_tensor, target_pixels)

        # Check dimensions
        new_h, new_w = downsampled.shape[:2]
        assert new_h * new_w <= target_pixels * 1.1

        # Check scale factor
        expected_scale = np.sqrt(h * w / target_pixels)
        assert abs(scale_factor - expected_scale) < 0.01

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_downsample_no_resize_needed(self, test_image):
        """Test downsampling when image is already small."""
        h, w = test_image.shape[:2]
        target_pixels = h * w * 2  # Target larger than image

        rgb_tensor = torch.from_numpy(test_image.astype(np.float32)).cuda()
        downsampled, scale_factor = downsample_image_gpu(rgb_tensor, target_pixels)

        # Should return original image
        assert scale_factor == 1.0
        assert downsampled.shape == test_image.shape

    def test_calculate_downsample_size(self):
        """Test downsample size calculation."""
        h, w = 1000, 1000
        target_pixels = 500_000

        new_h, new_w, scale = calculate_downsample_size(h, w, target_pixels)

        # Check calculations
        assert new_h * new_w <= target_pixels * 1.1
        assert scale == np.sqrt(h * w / target_pixels)


class TestColorMapping:
    """Test color mapping."""

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_map_colors_gpu_basic(self, test_rgb_colors, lut_colors):
        """Test GPU color mapping."""
        # Upload to GPU
        query_tensor = torch.from_numpy(test_rgb_colors.astype(np.float32)).cuda()
        lut_tensor = torch.from_numpy(lut_colors.astype(np.float32)).cuda()

        # Map colors
        indices_tensor = map_colors_gpu(query_tensor, lut_tensor)
        indices = indices_tensor.cpu().numpy()

        # Check results
        assert len(indices) == len(test_rgb_colors)
        assert all(0 <= idx < len(lut_colors) for idx in indices)

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_map_colors_gpu_large_batch(self):
        """Test GPU color mapping with large batch."""
        # Generate large query set
        n_queries = 100_000
        n_lut = 500

        query_colors = np.random.randint(0, 256, (n_queries, 3), dtype=np.uint8)
        lut_colors = np.random.randint(0, 256, (n_lut, 3), dtype=np.uint8)

        # Upload to GPU
        query_tensor = torch.from_numpy(query_colors.astype(np.float32)).cuda()
        lut_tensor = torch.from_numpy(lut_colors.astype(np.float32)).cuda()

        # Map colors
        indices_tensor = map_colors_gpu(query_tensor, lut_tensor)
        indices = indices_tensor.cpu().numpy()

        # Check results
        assert len(indices) == n_queries
        assert all(0 <= idx < n_lut for idx in indices)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])