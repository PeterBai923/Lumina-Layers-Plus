"""
Performance benchmarks for GPU pipeline.

Measures speedup across different image sizes and configurations.
"""

import sys
import os
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import numpy as np
import cv2
import torch
from core.gpu_pipeline import GPUPipeline


def generate_test_image(size):
    """Generate test image with given size."""
    h, w = size
    return np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)


def generate_mock_lut(n_colors=500):
    """Generate mock LUT for testing."""
    lut_rgb = np.random.randint(0, 256, (n_colors, 3), dtype=np.uint8)

    lut_lab = []
    for rgb in lut_rgb:
        bgr = cv2.cvtColor(rgb.reshape(1, 1, 3), cv2.COLOR_RGB2BGR)
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab).astype(np.float64)
        lut_lab.append(lab.flatten())
    lut_lab = np.array(lut_lab)

    return lut_rgb, lut_lab


def benchmark_pipeline(image_size, quantize_colors, use_gpu, lut_rgb, lut_lab, n_runs=3):
    """Benchmark pipeline performance."""
    # Generate test image
    image = generate_test_image(image_size)

    # Initialize pipeline
    pipeline = GPUPipeline(use_gpu=use_gpu)

    # Warmup run
    pipeline.process_preview(
        image, quantize_colors, lut_rgb, lut_lab,
        blur_kernel=0, smooth_sigma=0.0
    )

    # Benchmark runs
    times = []
    for _ in range(n_runs):
        start = time.time()
        matched_rgb, material_matrix, debug_data = pipeline.process_preview(
            image, quantize_colors, lut_rgb, lut_lab,
            blur_kernel=0, smooth_sigma=0.0
        )
        elapsed = time.time() - start
        times.append(elapsed)

    avg_time = np.mean(times)
    std_time = np.std(times)

    return avg_time, std_time, debug_data


def run_benchmarks():
    """Run comprehensive benchmarks."""
    print("=" * 80)
    print("GPU Pipeline Performance Benchmarks")
    print("=" * 80)

    # Check GPU availability
    if torch.cuda.is_available():
        print(f"\n[OK] GPU available: {torch.cuda.get_device_name()}")
        print(f"   Memory: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.1f} GB")
    else:
        print("\n[WARN] GPU not available, running CPU-only benchmarks")

    # Generate LUT
    lut_rgb, lut_lab = generate_mock_lut(n_colors=500)

    # Test configurations
    test_configs = [
        # (size, quantize_colors, description)
        ((500, 500), 16, "250K pixels (500×500)"),
        ((1000, 1000), 16, "1M pixels (1000×1000)"),
        ((1500, 1500), 16, "2.25M pixels (1500×1500)"),
        ((2000, 2000), 16, "4M pixels (2000×2000)"),
    ]

    results = []

    print("\n" + "=" * 80)
    print("Running benchmarks...")
    print("=" * 80)

    for size, quantize_colors, description in test_configs:
        h, w = size
        total_pixels = h * w

        print(f"\n[INFO] Testing: {description}")
        print(f"   Image size: {w}x{h} ({total_pixels:,} pixels)")
        print(f"   Quantize colors: {quantize_colors}")

        # CPU benchmark
        print(f"\n   [TIME] CPU benchmark...")
        time_cpu, std_cpu, debug_cpu = benchmark_pipeline(
            size, quantize_colors, use_gpu=False, lut_rgb=lut_rgb, lut_lab=lut_lab
        )
        print(f"      Time: {time_cpu:.2f}s (+/-{std_cpu:.2f}s)")

        # GPU benchmark (if available)
        if torch.cuda.is_available():
            print(f"   [TIME] GPU benchmark...")
            time_gpu, std_gpu, debug_gpu = benchmark_pipeline(
                size, quantize_colors, use_gpu=True, lut_rgb=lut_rgb, lut_lab=lut_lab
            )
            speedup = time_cpu / time_gpu
            print(f"      Time: {time_gpu:.2f}s (+/-{std_gpu:.2f}s)")
            print(f"      [FAST] Speedup: {speedup:.1f}x")

            result = {
                'description': description,
                'size': size,
                'total_pixels': total_pixels,
                'quantize_colors': quantize_colors,
                'time_cpu': time_cpu,
                'std_cpu': std_cpu,
                'time_gpu': time_gpu,
                'std_gpu': std_gpu,
                'speedup': speedup,
                'debug_cpu': debug_cpu,
                'debug_gpu': debug_gpu
            }
        else:
            result = {
                'description': description,
                'size': size,
                'total_pixels': total_pixels,
                'quantize_colors': quantize_colors,
                'time_cpu': time_cpu,
                'std_cpu': std_cpu,
                'time_gpu': None,
                'std_gpu': None,
                'speedup': None,
                'debug_cpu': debug_cpu,
                'debug_gpu': None
            }

        results.append(result)

    # Print summary
    print("\n" + "=" * 80)
    print("Benchmark Summary")
    print("=" * 80)

    print("\n| Size | Pixels | CPU Time | GPU Time | Speedup |")
    print("|------|--------|----------|----------|---------|")
    for result in results:
        if result['speedup']:
            print(f"| {result['size'][0]}×{result['size'][1]} | {result['total_pixels']:,} | "
                  f"{result['time_cpu']:.2f}s | {result['time_gpu']:.2f}s | {result['speedup']:.1f}x |")
        else:
            print(f"| {result['size'][0]}×{result['size'][1]} | {result['total_pixels']:,} | "
                  f"{result['time_cpu']:.2f}s | N/A | N/A |")

    # Print detailed timing breakdown
    if torch.cuda.is_available():
        print("\n" + "=" * 80)
        print("Detailed Timing Breakdown (GPU)")
        print("=" * 80)

        for result in results:
            if result['debug_gpu']:
                print(f"\n{result['description']}:")
                timings = result['debug_gpu']['timings']
                for stage, t in timings.items():
                    if stage != 'total':
                        print(f"  {stage:20s}: {t:.3f}s")

    # Calculate average speedup
    if torch.cuda.is_available():
        speedups = [r['speedup'] for r in results if r['speedup']]
        avg_speedup = np.mean(speedups)
        print(f"\n[OK] Average speedup: {avg_speedup:.1f}x")

        # Check if speedup meets expectations
        large_image_speedup = [r['speedup'] for r in results if r['total_pixels'] >= 1_000_000]
        if large_image_speedup:
            avg_large_speedup = np.mean(large_image_speedup)
            print(f"[OK] Large image speedup (>=1M pixels): {avg_large_speedup:.1f}x")

            if avg_large_speedup >= 10:
                print("   [EXCELLENT] Speedup exceeds 10x target.")
            elif avg_large_speedup >= 5:
                print("   [GOOD] Speedup meets minimum 5x target.")
            else:
                print("   [WARN] Speedup below expected. May need optimization.")

    print("\n" + "=" * 80)
    print("Benchmarks complete!")
    print("=" * 80)


if __name__ == '__main__':
    run_benchmarks()