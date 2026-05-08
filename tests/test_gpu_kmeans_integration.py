"""
Integration test for GPU K-Means with image processing.

Tests that GPU K-Means integrates correctly with the quantization pipeline.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch
from core.gpu_kmeans import KMeansBackend


def test_quantization_pipeline():
    """Test GPU K-Means in quantization pipeline."""
    print("=" * 80)
    print("GPU K-Means Integration Test")
    print("=" * 80)
    print()

    # Check GPU availability
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    else:
        print("GPU: Not available")
        print("This test requires CUDA. Exiting.")
        return False

    print()

    # Create test image data (simulating image processing pipeline)
    print("Creating test image data...")
    size = 2000
    n_pixels = size * size

    # Create color gradient (similar to real image)
    pixels = np.zeros((n_pixels, 3), dtype=np.float32)
    for i in range(size):
        for j in range(size):
            idx = i * size + j
            pixels[idx] = [
                255 * i / size,  # Red gradient
                255 * j / size,  # Green gradient
                128  # Blue constant
            ]

    print(f"Test data size: {size}x{size} ({n_pixels:,} pixels)")
    print()

    # Test with different k values
    k_values = [8, 16, 32]

    for k in k_values:
        print(f"--- Testing k={k} ---")

        # GPU version
        backend = KMeansBackend()
        centers = backend.quantize(pixels, k=k, max_iter=50, tol=0.5, n_init=5)

        print(f"Centers shape: {centers.shape}")

        # Verify centers are valid
        assert centers.shape == (k, 3), f"Expected shape ({k}, 3), got {centers.shape}"
        assert np.all(centers >= 0) and np.all(centers <= 255), "Centers out of range"

        print("PASS: GPU K-Means completed successfully")
        print()

    return True


if __name__ == '__main__':
    success = test_quantization_pipeline()
    print()
    print("=" * 80)
    if success:
        print("Integration test PASSED")
    else:
        print("Integration test FAILED")
    print("=" * 80)