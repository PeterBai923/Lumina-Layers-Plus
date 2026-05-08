"""
Performance benchmark for GPU K-Means acceleration.

Compares GPU vs CPU performance across different image sizes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import numpy as np
import cv2
import torch
from core.gpu_kmeans import KMeansBackend


def benchmark_kmeans(n_pixels, k, max_iter=50, n_init=5, seed=42):
    """
    Benchmark K-Means performance for given parameters.

    Args:
        n_pixels: Number of pixels
        k: Number of clusters
        max_iter: Maximum iterations
        n_init: Number of initializations
        seed: Random seed

    Returns:
        dict: Performance metrics
    """
    # Generate random pixel data
    pixels = np.random.randn(n_pixels, 3).astype(np.float32) * 50 + 128

    results = {}

    # CPU benchmark
    backend_cpu = KMeansBackend(use_gpu=False)
    t0 = time.time()
    centers_cpu = backend_cpu.quantize(pixels, k, max_iter=max_iter, n_init=n_init)
    cpu_time = time.time() - t0

    results['cpu_time'] = cpu_time
    results['cpu_centers'] = centers_cpu

    # GPU benchmark (if available)
    if torch.cuda.is_available():
        backend_gpu = KMeansBackend(use_gpu=True)
        t0 = time.time()
        centers_gpu = backend_gpu.quantize(pixels, k, max_iter=max_iter, n_init=n_init, seed=seed)
        gpu_time = time.time() - t0

        results['gpu_time'] = gpu_time
        results['gpu_centers'] = centers_gpu
        results['speedup'] = cpu_time / gpu_time

        # Compute inertia for both
        from scipy.spatial import KDTree
        tree_cpu = KDTree(centers_cpu)
        tree_gpu = KDTree(centers_gpu)

        distances_cpu, _ = tree_cpu.query(pixels)
        distances_gpu, _ = tree_gpu.query(pixels)

        results['inertia_cpu'] = np.sum(distances_cpu ** 2)
        results['inertia_gpu'] = np.sum(distances_gpu ** 2)
        results['inertia_diff'] = abs(results['inertia_cpu'] - results['inertia_gpu'])

    return results


def run_benchmarks():
    """Run comprehensive benchmarks across different sizes."""
    print("=" * 80)
    print("GPU K-Means Performance Benchmark")
    print("=" * 80)
    print()

    if not torch.cuda.is_available():
        print("WARNING: CUDA not available. Running CPU-only benchmark.")
    else:
        print(f"OK: CUDA available: {torch.cuda.get_device_name(0)}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    print()

    # Test configurations
    configs = [
        {'name': 'Small (100K pixels)', 'n_pixels': 100_000, 'k': 16},
        {'name': 'Medium (500K pixels)', 'n_pixels': 500_000, 'k': 16},
        {'name': 'Large (1M pixels)', 'n_pixels': 1_000_000, 'k': 16},
        {'name': 'Very Large (2M pixels)', 'n_pixels': 2_000_000, 'k': 16},
        {'name': 'Huge (5M pixels)', 'n_pixels': 5_000_000, 'k': 16},
    ]

    results_table = []

    for config in configs:
        print(f"\n--- {config['name']} (k={config['k']}) ---")

        result = benchmark_kmeans(
            n_pixels=config['n_pixels'],
            k=config['k'],
            max_iter=50,
            n_init=5
        )

        print(f"CPU time: {result['cpu_time']:.2f}s")

        if 'gpu_time' in result:
            print(f"GPU time: {result['gpu_time']:.2f}s")
            print(f"Speedup:  {result['speedup']:.1f}x")
            print(f"Inertia diff: {result['inertia_diff']:.1f}")

            results_table.append({
                'name': config['name'],
                'n_pixels': config['n_pixels'],
                'cpu_time': result['cpu_time'],
                'gpu_time': result['gpu_time'],
                'speedup': result['speedup']
            })
        else:
            results_table.append({
                'name': config['name'],
                'n_pixels': config['n_pixels'],
                'cpu_time': result['cpu_time'],
                'gpu_time': None,
                'speedup': None
            })

    # Print summary table
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"{'Image Size':<25} {'Pixels':>12} {'CPU (s)':>10} {'GPU (s)':>10} {'Speedup':>10}")
    print("-" * 80)

    for row in results_table:
        if row['gpu_time']:
            print(f"{row['name']:<25} {row['n_pixels']:>12,} {row['cpu_time']:>10.2f} "
                  f"{row['gpu_time']:>10.2f} {row['speedup']:>9.1f}x")
        else:
            print(f"{row['name']:<25} {row['n_pixels']:>12,} {row['cpu_time']:>10.2f} "
                  f"{'N/A':>10} {'N/A':>10}")

    print("=" * 80)

    # Save results to file
    with open('benchmark_results.txt', 'w') as f:
        f.write("GPU K-Means Performance Benchmark Results\n")
        f.write("=" * 80 + "\n\n")

        if torch.cuda.is_available():
            f.write(f"GPU: {torch.cuda.get_device_name(0)}\n")
            f.write(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB\n\n")

        f.write(f"{'Image Size':<25} {'Pixels':>12} {'CPU (s)':>10} {'GPU (s)':>10} {'Speedup':>10}\n")
        f.write("-" * 80 + "\n")

        for row in results_table:
            if row['gpu_time']:
                f.write(f"{row['name']:<25} {row['n_pixels']:>12,} {row['cpu_time']:>10.2f} "
                       f"{row['gpu_time']:>10.2f} {row['speedup']:>9.1f}x\n")
            else:
                f.write(f"{row['name']:<25} {row['n_pixels']:>12,} {row['cpu_time']:>10.2f} "
                       f"{'N/A':>10} {'N/A':>10}\n")

        f.write("=" * 80 + "\n")

    print("\nOK: Results saved to benchmark_results.txt")


if __name__ == '__main__':
    run_benchmarks()