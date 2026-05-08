import numpy as np


def encode_rgb_colors(colors: np.ndarray) -> np.ndarray:
    return (
        colors[:, 0].astype(np.int32) * 65536 +
        colors[:, 1].astype(np.int32) * 256 +
        colors[:, 2].astype(np.int32)
    )


def build_color_lut(
    unique_colors: np.ndarray,
    unique_indices: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    unique_codes = encode_rgb_colors(unique_colors)

    sort_idx = np.argsort(unique_codes)
    sorted_codes = unique_codes[sort_idx]
    sorted_indices = unique_indices[sort_idx]

    return sorted_codes, sorted_indices


def lookup_colors(
    pixel_colors: np.ndarray,
    sorted_codes: np.ndarray,
    sorted_indices: np.ndarray
) -> np.ndarray:
    pixel_codes = encode_rgb_colors(pixel_colors)

    insert_positions = np.searchsorted(sorted_codes, pixel_codes)

    return sorted_indices[insert_positions]
