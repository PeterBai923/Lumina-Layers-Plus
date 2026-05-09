"""
Lumina Studio - Image Converter Coordinator (Refactored)

Coordinates modules to complete image-to-3D model conversion.
This module serves as the main orchestrator, delegating specific tasks
to specialized submodules.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import deque
import numpy as np
import cv2
import trimesh
from PIL import Image, ImageDraw
import gradio as gr
from typing import List, Dict, Tuple, Optional

from config import PrinterConfig, ColorSystem, ModelingMode, OUTPUT_DIR, EXTENDED_PRINT_SETTINGS
from core.utils import Stats
from core.utils.bambu_3mf_writer import export_scene_with_bambu_metadata

from core.image.processor import LuminaImageProcessor
from core.mesh.generators import get_mesher
from core.mesh.geometry import create_keychain_loop, CUBE_FACES, CUBE_FACES_NP
from core.mesh.heightmap import HeightmapLoader
from core.naming import generate_model_filename, generate_preview_filename
from core.color.formats import rgb_to_hex, hex_to_rgb
from core.preview.render import (
    FIXED_BED_WIDTH_MM, FIXED_BED_HEIGHT_MM,
    render_preview, generate_highlight_preview, clear_highlight_preview,
    generate_lut_grid_html, generate_lut_card_grid_html,
    _create_preview_mesh, _create_bed_mesh
)
from core.preview.interaction import (
    on_preview_click, on_preview_click_select_color,
    update_preview_with_loop, on_remove_loop,
    update_preview_with_replacements,
    _compute_connected_region_mask_4n, _ensure_quantized_image_in_cache
)

from core.utils.logger import get_logger

logger = get_logger("CONVERTER")

# ========== LUT Color Extraction Functions ==========

def extract_lut_available_colors(lut_path: str) -> List[dict]:
    """
    Extract all available colors from a LUT file.

    This function loads a LUT file (.npy) and extracts all unique colors
    that the printer can produce. These colors can be used as replacement
    options in the color replacement feature.

    Args:
        lut_path: Path to the LUT file (.npy)

    Returns:
        List of dicts, each containing:
        - 'color': (R, G, B) tuple
        - 'hex': '#RRGGBB' string

        Returns empty list if LUT cannot be loaded.
    """
    if not lut_path:
        return []

    try:
        # Handle .npz (merged LUT) format
        if lut_path.endswith('.npz'):
            data = np.load(lut_path)
            measured_colors = data['rgb']
            logger.debug("Loading merged LUT (.npz) with %s colors", len(measured_colors))
        else:
            # Standard .npy format
            lut_grid = np.load(lut_path)
            measured_colors = lut_grid.reshape(-1, 3)
            logger.debug("Loading standard LUT (.npy) with %s colors", len(measured_colors))

        # Get unique colors
        unique_colors = np.unique(measured_colors, axis=0)

        # Build color list
        colors = []
        for color in unique_colors:
            r, g, b = int(color[0]), int(color[1]), int(color[2])
            colors.append({
                'color': (r, g, b),
                'hex': f'#{r:02x}{g:02x}{b:02x}'
            })

        # Sort by brightness (dark to light) for better UX
        colors.sort(key=lambda x: sum(x['color']))

        logger.debug("Extracted %s unique colors from LUT", len(colors))
        return colors

    except Exception as e:
        logger.debug("Error extracting colors from LUT: %s", e)
        return []


def get_lut_color_choices(lut_path: str) -> List[tuple]:
    """
    Get LUT colors formatted for Gradio Dropdown.

    Args:
        lut_path: Path to the LUT .npy file

    Returns:
        List of (display_label, hex_value) tuples for Dropdown choices.
        Display label includes a colored square emoji approximation.
    """
    colors = extract_lut_available_colors(lut_path)

    if not colors:
        return []

    choices = []
    for entry in colors:
        hex_color = entry['hex']
        r, g, b = entry['color']
        # Create a display label with RGB values
        label = f"■ {hex_color} (R:{r} G:{g} B:{b})"
        choices.append((label, hex_color))

    return choices


def generate_lut_color_dropdown_html(lut_path: str, selected_color: str = None, used_colors: set = None) -> str:
    """
    Generate HTML for displaying LUT available colors as a clickable visual grid.

    Colors are grouped into two sections:
    1. Colors used in current image (if any)
    2. Other available colors

    This provides a visual preview of all available colors from the LUT,
    allowing users to click directly to select a replacement color.

    Args:
        lut_path: Path to the LUT .npy file
        selected_color: Currently selected replacement color hex
        used_colors: Set of hex colors currently used in the image (for grouping)

    Returns:
        HTML string showing available colors as a clickable grid
    """
    from ui.widgets.palette import generate_lut_color_grid_html
    colors = extract_lut_available_colors(lut_path)
    # Delegate HTML generation to palette widget (non-invasive)
    return generate_lut_color_grid_html(colors, selected_color, used_colors)


# ========== Helper Functions for Color Processing ==========

def _recommend_lut_colors_by_rgb(base_rgb, lut_colors, top_k=10):
    """按 RGB 欧氏距离推荐 LUT 颜色，返回前 top_k 项。"""
    if not lut_colors:
        return []

    normalized = []
    for c in lut_colors:
        if isinstance(c, dict):
            color = c.get("color")
            hex_color = c.get("hex")
            if color is None and isinstance(hex_color, str) and len(hex_color.strip().lstrip('#')) == 6:
                h = hex_color.strip().lstrip('#')
                color = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
            if color is not None and isinstance(hex_color, str):
                normalized.append({"color": tuple(int(v) for v in color), "hex": hex_color.lower()})
            continue

        if isinstance(c, (tuple, list)) and len(c) >= 2 and isinstance(c[1], str):
            h = c[1].strip().lstrip('#')
            if len(h) != 6:
                continue
            normalized.append({
                "color": (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)),
                "hex": f"#{h.lower()}"
            })

    if not normalized:
        return []

    arr = np.array([c["color"] for c in normalized], dtype=np.float64)
    b = np.array(base_rgb, dtype=np.float64)
    dist = np.sqrt(np.sum((arr - b) ** 2, axis=1))
    idx = np.argsort(dist)[:top_k]
    return [normalized[i] for i in idx]


def _build_dual_recommendations(q_rgb, m_rgb, lut_colors, top_k=10):
    """构建双基准推荐：按量化色与按原配准色。"""
    return {
        "by_quantized": _recommend_lut_colors_by_rgb(q_rgb, lut_colors, top_k=top_k),
        "by_matched": _recommend_lut_colors_by_rgb(m_rgb, lut_colors, top_k=top_k),
    }


def _normalize_color_replacements_input(color_replacements):
    """兼容 dict / replacement_regions(list) 两种替换输入，统一为 {hex: hex}。"""
    if not color_replacements:
        return {}

    if isinstance(color_replacements, dict):
        out = {}
        for src, dst in color_replacements.items():
            if not isinstance(src, str) or not isinstance(dst, str):
                continue
            s = src.strip().lower()
            d = dst.strip().lower()
            if s and d:
                out[s] = d
        return out

    if isinstance(color_replacements, list):
        out = {}
        for item in color_replacements:
            if not isinstance(item, dict):
                continue
            src = (item.get('matched') or item.get('matched_hex')
                   or item.get('source') or item.get('quantized')
                   or item.get('quantized_hex') or '').strip().lower()
            dst = (item.get('replacement') or item.get('replacement_hex') or '').strip().lower()
            if src and dst:
                out[src] = dst
        return out

    return {}


def _apply_region_replacement(image_rgb, region_mask, replacement_rgb):
    """仅在 region_mask 覆盖区域应用替换色。"""
    out = image_rgb.copy()
    out[region_mask] = np.array(replacement_rgb, dtype=np.uint8)
    return out


def _apply_regions_to_raster_outputs(matched_rgb, material_matrix, mask_solid,
                                     replacement_regions, lut_index_resolver, ref_stacks):
    """按 regions 顺序覆盖 raster 输出（matched_rgb + material_matrix）。"""
    out_rgb = matched_rgb.copy()
    out_mat = material_matrix.copy()

    for item in (replacement_regions or []):
        region_mask = item.get('mask')
        replacement_hex = item.get('replacement')
        if region_mask is None or not replacement_hex:
            continue

        effective_mask = region_mask & mask_solid
        if not np.any(effective_mask):
            continue

        replacement_rgb = hex_to_rgb(replacement_hex)
        out_rgb[effective_mask] = np.array(replacement_rgb, dtype=np.uint8)

        lut_idx = int(lut_index_resolver(replacement_rgb))
        out_mat[effective_mask] = ref_stacks[lut_idx]

    return out_rgb, out_mat


# ========== Color Palette Functions ==========

def extract_color_palette(preview_cache: dict) -> List[dict]:
    """
    Extract unique colors from preview cache.

    Args:
        preview_cache: Cache data from generate_preview_cached containing:
            - matched_rgb: (H, W, 3) uint8 array of matched colors
            - mask_solid: (H, W) bool array indicating solid pixels

    Returns:
        List of dicts sorted by pixel count (descending), each containing:
        - 'color': (R, G, B) tuple
        - 'hex': '#RRGGBB' string
        - 'count': pixel count
        - 'percentage': percentage of total solid pixels (0.0-100.0)
    """
    if preview_cache is None:
        return []

    matched_rgb = preview_cache.get('matched_rgb')
    mask_solid = preview_cache.get('mask_solid')

    if matched_rgb is None or mask_solid is None:
        return []

    # Ensure uint8 type for correct encoding
    if matched_rgb.dtype != np.uint8:
        matched_rgb = matched_rgb.astype(np.uint8)

    # Get only solid pixels
    solid_pixels = matched_rgb[mask_solid]

    if len(solid_pixels) == 0:
        return []

    total_solid = len(solid_pixels)

    # Optimized: Use counting sort instead of np.unique (O(n) vs O(n log n))
    #
    # Performance trade-off:
    # - Time complexity: O(n) vs O(n log n)
    # - Memory overhead: Fixed ~16.8MB for bincount array
    # - Best for: Large images with many pixels
    # - Limitation: May be slower for small images due to memory allocation
    #
    # RGB encoding: R*65536 + G*256 + B ensures unique mapping

    # Encode RGB as single integer
    codes = (solid_pixels[:, 0].astype(np.int32) * 65536 +
             solid_pixels[:, 1].astype(np.int32) * 256 +
             solid_pixels[:, 2].astype(np.int32))

    # Count occurrences (O(n) complexity)
    counts = np.bincount(codes)

    # Extract non-zero colors
    unique_codes = np.where(counts > 0)[0]
    color_counts = counts[unique_codes]

    # Decode back to RGB with validation
    r_values = unique_codes // 65536
    g_values = (unique_codes // 256) % 256
    b_values = unique_codes % 256

    # Validate RGB range (should never fail if encoding is correct)
    assert r_values.max() <= 255, "R channel overflow detected"
    assert g_values.max() <= 255, "G channel overflow detected"
    assert b_values.max() <= 255, "B channel overflow detected"

    r = r_values.astype(np.uint8)
    g = g_values.astype(np.uint8)
    b = b_values.astype(np.uint8)

    # Build palette entries
    palette = []
    for i in range(len(unique_codes)):
        palette.append({
            'color': (int(r[i]), int(g[i]), int(b[i])),
            'hex': f'#{r[i]:02x}{g[i]:02x}{b[i]:02x}',
            'count': int(color_counts[i]),
            'percentage': round(color_counts[i] / total_solid * 100, 2)
        })

    # Sort by count descending
    palette.sort(key=lambda x: x['count'], reverse=True)

    return palette


# ========== Debug Helper Functions ==========

def _save_debug_preview(debug_data, material_matrix, mask_solid, image_path, mode_name, num_materials=4):
    """
    Save high-fidelity mode debug preview image.

    Shows the K-Means quantized image, which is the actual input the vectorizer receives.
    Optionally draws contours to show shape recognition results.

    Args:
        debug_data: Debug data dictionary
        material_matrix: Material matrix
        mask_solid: Solid mask
        image_path: Original image path
        mode_name: Mode name
        num_materials: Number of materials (4 or 6), default 4
    """
    quantized_image = debug_data['quantized_image']
    num_colors = debug_data['num_colors']

    logger.debug("Saving %s debug preview...", mode_name)
    logger.debug("Quantized to %s colors", num_colors)

    debug_img = quantized_image.copy()

    # Draw contours to show how the vectorizer interprets shapes
    try:
        contour_overlay = debug_img.copy()

        for mat_id in range(num_materials):
            mat_mask = np.zeros(material_matrix.shape[:2], dtype=np.uint8)
            for layer in range(material_matrix.shape[2]):
                mat_mask = np.logical_or(mat_mask, material_matrix[:, :, layer] == mat_id)

            mat_mask = np.logical_and(mat_mask, mask_solid).astype(np.uint8) * 255

            if not np.any(mat_mask):
                continue

            contours, _ = cv2.findContours(
                mat_mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
            )

            cv2.drawContours(contour_overlay, contours, -1, (0, 0, 0), 1)

        debug_img = contour_overlay
        logger.debug("Contours drawn on preview")

    except Exception as e:
        logger.debug("Warning: Could not draw contours: %s", e)

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    debug_path = os.path.join(OUTPUT_DIR, f"{base_name}_{mode_name}_Debug.png")

    debug_pil = Image.fromarray(debug_img, mode='RGB')
    debug_pil.save(debug_path, 'PNG')

    logger.debug("Saved: %s", debug_path)
    logger.debug("This is the EXACT image the vectorizer sees before meshing")


# ========== LUT Slot Color Derivation ==========

def _get_actual_lut_slot_colors(processor) -> dict:
    """Derive the actual measured color for each slot from the LUT's pure-color entries.

    For a 6-Color Smart-1296 LUT, the pure-color stack for slot *i* is the entry
    where all 5 layers equal *i* (top-to-bottom convention: ``(i, i, i, i, i)``).
    The corresponding ``lut_rgb`` value is the physical color actually measured
    from the calibration board for that slot.

    This is used to override the hard-coded ``ColorSystem.SIX_COLOR`` preview
    colours (CMYWGK) with the real filament colours so BambuStudio's AMS panel
    shows the correct colour and the user loads the right filament in each slot.

    Args:
        processor: A ``LuminaImageProcessor`` instance whose ``ref_stacks`` and
                   ``lut_rgb`` attributes have already been populated.

    Returns:
        ``{slot_id: (r, g, b)}`` for every slot whose pure-colour entry is found.
        Returns an empty dict if the data is unavailable or the stack depth < 5.
    """
    try:
        ref_stacks = np.asarray(processor.ref_stacks)
        lut_rgb    = np.asarray(processor.lut_rgb)
    except (AttributeError, TypeError):
        return {}

    if ref_stacks.ndim != 2 or ref_stacks.shape[1] < 5 or len(lut_rgb) == 0:
        return {}

    num_slots = int(ref_stacks.max()) + 1
    slot_colors: dict = {}
    for slot_id in range(num_slots):
        pure_mask = np.all(ref_stacks == slot_id, axis=1)
        if np.any(pure_mask):
            idx = int(np.argmax(pure_mask))
            rgb = lut_rgb[idx]
            slot_colors[slot_id] = (int(rgb[0]), int(rgb[1]), int(rgb[2]))

    return slot_colors


# ========== Voxel Matrix Building Functions ==========

def _build_voxel_matrix(material_matrix, mask_solid, spacer_thick, structure_mode, backing_color_id=0):
    """
    Build complete voxel matrix with backing layer marked using special material_id.

    Args:
        material_matrix: (H, W, N) material matrix (N optical layers)
        mask_solid: (H, W) solid pixel mask
        spacer_thick: backing thickness (mm)
        structure_mode: "双面" or "单面" (Double-sided or Single-sided)
        backing_color_id: backing material ID (0-7), default is 0 (White)

    Returns:
        tuple: (full_matrix, backing_metadata)
            - full_matrix: (Z, H, W) voxel matrix
            - backing_metadata: dict with keys:
                - 'backing_color_id': int
                - 'backing_z_range': tuple (start_z, end_z)
    """
    if material_matrix.ndim != 3:
        raise ValueError(f"material_matrix must be 3D (H, W, N), got shape={material_matrix.shape}")
    target_h, target_w, optical_layers = material_matrix.shape
    mask_transparent = ~mask_solid

    bottom_voxels = np.transpose(material_matrix, (2, 0, 1))

    spacer_layers = max(1, int(round(spacer_thick / PrinterConfig.BACKING_LAYER_HEIGHT)))

    if "双面" in structure_mode or "double" in structure_mode.lower():
        top_voxels = np.transpose(material_matrix[..., ::-1], (2, 0, 1))
        total_layers = optical_layers + spacer_layers + optical_layers
        full_matrix = np.full((total_layers, target_h, target_w), -1, dtype=int)

        full_matrix[0:optical_layers] = bottom_voxels

        # Use backing_color_id parameter to mark backing layer
        spacer = np.full((target_h, target_w), -1, dtype=int)
        spacer[~mask_transparent] = backing_color_id
        for z in range(optical_layers, optical_layers + spacer_layers):
            full_matrix[z] = spacer

        full_matrix[optical_layers + spacer_layers:] = top_voxels

        backing_z_range = (optical_layers, optical_layers + spacer_layers - 1)
    else:
        total_layers = optical_layers + spacer_layers
        full_matrix = np.full((total_layers, target_h, target_w), -1, dtype=int)

        full_matrix[0:optical_layers] = bottom_voxels

        # Use backing_color_id parameter to mark backing layer
        spacer = np.full((target_h, target_w), -1, dtype=int)
        spacer[~mask_transparent] = backing_color_id
        for z in range(optical_layers, total_layers):
            full_matrix[z] = spacer

        backing_z_range = (optical_layers, total_layers - 1)

    backing_metadata = {
        'backing_color_id': backing_color_id,
        'backing_z_range': backing_z_range
    }

    return full_matrix, backing_metadata


def _build_voxel_matrix_faceup(material_matrix, mask_solid, spacer_thick, backing_color_id=0):
    """
    Face up voxel matrix for 5-Color Extended mode.

    Orientation: backing at the bottom (print-bed side), viewing surface at the
    top.  The model is printed right-side-up — no post-print flipping required.

    material_matrix convention (top-to-bottom):
        index 0 = viewing surface (outermost)
        index N-1 = near backing (innermost)

    For base 1024 stacks, index 0 = -1 (air padding) so their viewing surface
    sits 1 Z below the extended stacks, keeping each Z ≤ 4 materials.

    Layer structure (bottom → top, Z ascending):
        Z = 0 .. spacer-1  : Solid backing (backing_color_id)
        Z = spacer .. +5   : Optical layers (reversed: index N-1 → lowest Z,
                             index 0 → highest Z)
        -1 values stay as air in the voxel matrix.
    """
    target_h, target_w, optical_layers = material_matrix.shape
    spacer_layers = max(1, int(round(spacer_thick / PrinterConfig.BACKING_LAYER_HEIGHT)))
    total_layers = spacer_layers + optical_layers
    full_matrix = np.full((total_layers, target_h, target_w), -1, dtype=int)

    # Backing: solid block at the bottom
    spacer = np.where(mask_solid, backing_color_id, -1).astype(int)
    full_matrix[:spacer_layers] = spacer[np.newaxis, :, :]

    # Optical: reversed order so index 0 (viewing surface) → highest Z
    for i in range(optical_layers):
        layer = material_matrix[:, :, optical_layers - 1 - i]
        z = spacer_layers + i
        full_matrix[z] = np.where(mask_solid, layer, -1)

    backing_z_range = (0, spacer_layers - 1)
    return full_matrix, {
        'backing_color_id': backing_color_id,
        'backing_z_range': backing_z_range,
    }


def _build_relief_voxel_matrix(matched_rgb, material_matrix, mask_solid, color_height_map,
                               default_height, structure_mode, backing_color_id, pixel_scale,
                               height_matrix=None):
    """
    Build 2.5D relief voxel matrix with per-color or per-pixel variable heights (GPU accelerated).

    Supports two modes:
    1. Color height map mode (default): heights assigned by color
    2. Heightmap mode: heights from external grayscale heightmap (per-pixel)

    Physical Model:
    - Each color region has its own target height (Target_Z)
    - Bottom layers (base): Z=0 to Z=(Target_Z - 0.4mm) - filled with backing_color_id
    - Top layers (optical): Z=(Target_Z - 0.4mm) to Z=Target_Z - filled with material layers

    Args:
        matched_rgb: (H, W, 3) RGB color array after K-Means matching
        material_matrix: (H, W, 5) material matrix for optical layers
        mask_solid: (H, W) boolean mask of solid pixels
        color_height_map: dict mapping hex colors to heights in mm
        default_height: default height in mm for colors not in map
        structure_mode: "Double-sided" or "Single-sided"
        backing_color_id: backing material ID (0-7)
        pixel_scale: mm per pixel
        height_matrix: optional (H, W) float32 per-pixel height matrix from heightmap

    Returns:
        tuple: (full_matrix, backing_metadata)
    """
    import torch
    from core.utils.gpu_device import GPUDeviceManager

    device = GPUDeviceManager().get_device()
    target_h, target_w = material_matrix.shape[:2]

    # Constants
    OPTICAL_LAYERS = 5
    OPTICAL_THICKNESS_MM = OPTICAL_LAYERS * PrinterConfig.LAYER_HEIGHT
    LAYER_HEIGHT = PrinterConfig.LAYER_HEIGHT

    logger.info("Relief: Building 2.5D relief voxel matrix (GPU)...")
    logger.info("Relief: Optical layer thickness: %smm (%s layers)", OPTICAL_THICKNESS_MM, OPTICAL_LAYERS)

    # Convert inputs to GPU tensors
    mask_tensor = torch.from_numpy(mask_solid).to(device)
    mat_tensor = torch.from_numpy(material_matrix).to(device)

    # Step 1: Build per-pixel height matrix (GPU)
    if height_matrix is not None:
        # Heightmap mode: use provided per-pixel height matrix
        logger.info("Relief: 使用高度图模式（逐像素高度）")
        pixel_heights = torch.from_numpy(height_matrix).to(device).float()
        # Clamp: pixel height < optical thickness → set to optical thickness
        pixel_heights = torch.where(
            mask_tensor & (pixel_heights < OPTICAL_THICKNESS_MM),
            torch.full_like(pixel_heights, OPTICAL_THICKNESS_MM),
            pixel_heights
        )
    elif color_height_map:
        # Color height map mode: vectorized color matching (GPU)
        matched_tensor = torch.from_numpy(matched_rgb).to(device).float()

        # Build color-to-height lookup tensors
        colors = []
        heights = []
        for hex_color, height in color_height_map.items():
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            colors.append([r, g, b])
            heights.append(height)

        color_tensor = torch.tensor(colors, device=device, dtype=torch.float32)
        height_tensor = torch.tensor(heights, device=device, dtype=torch.float32)

        # Batch distance calculation
        flat_rgb = matched_tensor.reshape(-1, 3)
        distances = torch.cdist(flat_rgb, color_tensor)
        nearest_idx = distances.argmin(dim=1)
        nearest_heights = height_tensor[nearest_idx].reshape(target_h, target_w)

        # Apply only for exact matches
        exact_match = (distances.min(dim=1).values == 0).reshape(target_h, target_w)
        pixel_heights = torch.where(
            mask_tensor & exact_match,
            nearest_heights,
            torch.full((target_h, target_w), default_height, device=device, dtype=torch.float32)
        )
    else:
        pixel_heights = torch.full((target_h, target_w), default_height, device=device, dtype=torch.float32)

    # Step 2: Calculate max height to determine total Z layers
    if mask_tensor.any():
        max_height_mm = pixel_heights[mask_tensor].max().item()
    else:
        max_height_mm = default_height
    max_z_layers = max(OPTICAL_LAYERS + 1, int(np.ceil(max_height_mm / LAYER_HEIGHT)))

    logger.info("Relief: Max height: %.2fmm (%s layers)", max_height_mm, max_z_layers)
    if mask_tensor.any():
        logger.info("Relief: Height range: %.2fmm - %.2fmm", pixel_heights[mask_tensor].min().item(), max_height_mm)

    # Step 3: Initialize voxel matrix (GPU)
    full_matrix = torch.full((max_z_layers, target_h, target_w), -1, device=device, dtype=torch.int32)

    # Step 4: Fill voxel matrix (vectorized GPU)
    z_layers = torch.ceil(pixel_heights / LAYER_HEIGHT).long()
    z_layers = z_layers.clamp(min=OPTICAL_LAYERS, max=max_z_layers)
    optical_start_z = z_layers - OPTICAL_LAYERS

    # Fill backing layers
    for z in range(max_z_layers):
        backing_mask = mask_tensor & (z < optical_start_z)
        full_matrix[z][backing_mask] = backing_color_id

    # Fill optical layers
    solid_y, solid_x = torch.where(mask_tensor)
    if solid_y.numel() > 0:
        for layer_idx in range(OPTICAL_LAYERS):
            z_positions = optical_start_z[solid_y, solid_x] + layer_idx
            valid_z = z_positions < max_z_layers
            z_valid = z_positions[valid_z]
            y_valid = solid_y[valid_z]
            x_valid = solid_x[valid_z]
            mat_ids = mat_tensor[y_valid, x_valid, OPTICAL_LAYERS - 1 - layer_idx].long()
            full_matrix[z_valid, y_valid, x_valid] = mat_ids

    # Step 5: Relief mode is always single-sided (观赏面朝上)
    backing_z_range = (0, max_z_layers - OPTICAL_LAYERS - 1)

    backing_metadata = {
        'backing_color_id': backing_color_id,
        'backing_z_range': backing_z_range,
        'is_relief': True,
        'max_height_mm': max_height_mm
    }

    logger.info("Relief: Relief voxel matrix built: %s", full_matrix.shape)
    logger.info("Relief: Backing range: Z=%s to Z=%s", backing_z_range[0], backing_z_range[1])
    logger.info("Relief: Mode: Single-sided (viewing surface on top)")

    return full_matrix.cpu().numpy(), backing_metadata


def _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale):
    """
    Apply transform with variable layer heights for optical and backing layers.

    For each vertex, determine which layer type it belongs to and apply the
    appropriate Z scaling:
    - Optical layers: LAYER_HEIGHT (0.08mm)
    - Backing layers: BACKING_LAYER_HEIGHT (0.2mm)

    Supports single-sided, double-sided, cloisonne, and relief modes.

    Args:
        mesh: trimesh.Trimesh object to transform
        backing_metadata: dict with 'backing_z_range' (start_z, end_z)
        pixel_scale: XY pixel scale factor (mm per voxel)

    Returns:
        Modified mesh with transformed vertices
    """
    if mesh is None or len(mesh.vertices) == 0:
        return mesh

    vertices = mesh.vertices.copy()
    backing_z_start, backing_z_end = backing_metadata['backing_z_range']

    # Extract Z coordinates (voxel layer indices)
    z_voxel = vertices[:, 2]

    # Calculate scaled Z coordinates
    def scale_z(z):
        """Non-linear Z scaling based on layer type"""
        if z < backing_z_start:
            # Optical layers (before backing)
            return z * PrinterConfig.LAYER_HEIGHT
        elif z <= backing_z_end:
            # Backing layers
            optical_height = backing_z_start * PrinterConfig.LAYER_HEIGHT
            return optical_height + (z - backing_z_start) * PrinterConfig.BACKING_LAYER_HEIGHT
        else:
            # Optical layers (after backing, e.g., double-sided mode)
            optical_height_bottom = backing_z_start * PrinterConfig.LAYER_HEIGHT
            backing_height = (backing_z_end - backing_z_start + 1) * PrinterConfig.BACKING_LAYER_HEIGHT
            optical_height_top = (z - backing_z_end - 1) * PrinterConfig.LAYER_HEIGHT
            return optical_height_bottom + backing_height + optical_height_top

    # Vectorize Z scaling
    z_new = np.vectorize(scale_z)(z_voxel)

    # Apply XY scaling
    vertices[:, 0] *= pixel_scale
    vertices[:, 1] *= pixel_scale
    vertices[:, 2] = z_new

    mesh.vertices = vertices
    return mesh


# ========== Loop and Outline Helper Functions ==========

def _calculate_loop_info(loop_pos, loop_width, loop_length, loop_hole,
                         mask_solid, material_matrix, target_w, target_h, pixel_scale):
    """Calculate keychain loop information."""
    solid_rows = np.any(mask_solid, axis=1)
    if not np.any(solid_rows):
        return None

    click_x, click_y = loop_pos
    attach_col = int(click_x)
    attach_row = int(click_y)
    attach_col = max(0, min(target_w - 1, attach_col))
    attach_row = max(0, min(target_h - 1, attach_row))

    col_mask = mask_solid[:, attach_col]
    if np.any(col_mask):
        solid_rows_in_col = np.where(col_mask)[0]
        distances = np.abs(solid_rows_in_col - attach_row)
        nearest_idx = np.argmin(distances)
        top_row = solid_rows_in_col[nearest_idx]
    else:
        top_row = np.argmax(solid_rows)
        solid_cols_in_top = np.where(mask_solid[top_row])[0]
        if len(solid_cols_in_top) > 0:
            distances = np.abs(solid_cols_in_top - attach_col)
            nearest_idx = np.argmin(distances)
            attach_col = solid_cols_in_top[nearest_idx]
        else:
            attach_col = target_w // 2

    attach_col = max(0, min(target_w - 1, attach_col))

    loop_color_id = 0
    search_area = material_matrix[
        max(0, top_row-2):top_row+3,
        max(0, attach_col-3):attach_col+4
    ]
    search_area = search_area[search_area >= 0]
    if len(search_area) > 0:
        unique, counts = np.unique(search_area, return_counts=True)
        for mat_id in unique[np.argsort(-counts)]:
            if mat_id != 0:
                loop_color_id = int(mat_id)
                break

    return {
        'attach_x_mm': attach_col * pixel_scale,
        'attach_y_mm': (target_h - 1 - top_row) * pixel_scale,
        'width_mm': loop_width,
        'length_mm': loop_length,
        'hole_dia_mm': loop_hole,
        'color_id': loop_color_id
    }


def _draw_loop_on_preview(preview_rgba, loop_info, color_conf, pixel_scale):
    """Draw keychain loop on preview image."""
    preview_pil = Image.fromarray(preview_rgba, mode='RGBA')
    draw = ImageDraw.Draw(preview_pil)

    loop_color_rgba = tuple(color_conf['preview'][loop_info['color_id']][:3]) + (255,)

    attach_col = int(loop_info['attach_x_mm'] / pixel_scale)
    attach_row = int((preview_rgba.shape[0] - 1) - loop_info['attach_y_mm'] / pixel_scale)

    loop_w_px = int(loop_info['width_mm'] / pixel_scale)
    loop_h_px = int(loop_info['length_mm'] / pixel_scale)
    hole_r_px = int(loop_info['hole_dia_mm'] / 2 / pixel_scale)
    circle_r_px = loop_w_px // 2

    loop_bottom = attach_row
    loop_left = attach_col - loop_w_px // 2
    loop_right = attach_col + loop_w_px // 2

    rect_h_px = loop_h_px - circle_r_px
    rect_bottom = loop_bottom
    rect_top = loop_bottom - rect_h_px

    circle_center_y = rect_top
    circle_center_x = attach_col

    if rect_h_px > 0:
        draw.rectangle(
            [loop_left, rect_top, loop_right, rect_bottom],
            fill=loop_color_rgba
        )

    draw.ellipse(
        [circle_center_x - circle_r_px, circle_center_y - circle_r_px,
         circle_center_x + circle_r_px, circle_center_y + circle_r_px],
        fill=loop_color_rgba
    )

    draw.ellipse(
        [circle_center_x - hole_r_px, circle_center_y - hole_r_px,
         circle_center_x + hole_r_px, circle_center_y + hole_r_px],
        fill=(0, 0, 0, 0)
    )

    return np.array(preview_pil)


def _generate_outline_mesh(mask_solid, pixel_scale, outline_width_mm, outline_thickness_mm, target_h):
    """Generate a ring-shaped outline mesh around the outer contour of the model.

    Algorithm:
    1. Find outer contour of mask_solid using cv2.findContours
    2. Dilate the mask outward by outline_width_mm
    3. Create ring = dilated - original
    4. Extrude the ring to outline_thickness_mm height

    Args:
        mask_solid: (H, W) boolean mask of solid pixels
        pixel_scale: mm per pixel
        outline_width_mm: Width of the outline in mm
        outline_thickness_mm: Thickness (height) of the outline in mm
        target_h: Image height in pixels

    Returns:
        trimesh.Trimesh or None
    """
    # Convert outline width from mm to pixels
    outline_width_px = max(1, int(round(outline_width_mm / pixel_scale)))

    # Convert thickness from mm to layers
    outline_layers = max(1, int(round(outline_thickness_mm / PrinterConfig.LAYER_HEIGHT)))

    logger.info("Outline: Width: %smm = %spx, Thickness: %smm = %s layers", outline_width_mm, outline_width_px, outline_thickness_mm, outline_layers)

    # Pad the mask before dilation so edges touching image boundaries
    # can still expand outward. Without padding, cv2.dilate treats the border
    # as zeros and the outline ring is missing on boundary-touching sides.
    pad = outline_width_px + 1
    mask_uint8 = mask_solid.astype(np.uint8) * 255
    padded_mask = cv2.copyMakeBorder(mask_uint8, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)

    # Dilate the padded mask outward
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(padded_mask, kernel, iterations=outline_width_px)

    # Also pad the original mask for subtraction
    padded_original = cv2.copyMakeBorder(mask_uint8, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)

    # Ring = dilated minus original (in padded space, preserving outline beyond image edges)
    ring_mask = (dilated > 0) & ~(padded_original > 0)

    # Use padded dimensions for mesh generation; offset coordinates by -pad later
    h, w = ring_mask.shape
    # h_original is needed for Y-flip coordinate conversion
    h_original = mask_solid.shape[0]

    if not np.any(ring_mask):
        logger.info("Outline: Ring mask is empty, skipping")
        return None

    ring_pixel_count = np.sum(ring_mask)
    logger.info("Outline: Ring mask: %s pixels", ring_pixel_count)

    # Use greedy rectangle merging to generate optimized mesh
    # Note: h, w are padded dimensions; use pad offset for world coordinates
    processed = np.zeros_like(ring_mask, dtype=bool)
    vertices = []
    faces = []

    z_bottom = 0.0
    z_top = float(outline_layers)

    for y in range(h):
        row_valid = ring_mask[y] & ~processed[y]
        if not np.any(row_valid):
            continue

        padded = np.concatenate([[False], row_valid, [False]])
        diff = np.diff(padded.astype(np.int8))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]

        for x_start, x_end in zip(starts, ends):
            if processed[y, x_start]:
                continue

            y_end = y + 1
            while y_end < h:
                seg_mask = ring_mask[y_end, x_start:x_end]
                seg_proc = processed[y_end, x_start:x_end]
                if not (np.all(seg_mask) and not np.any(seg_proc)):
                    break
                y_end += 1

            processed[y:y_end, x_start:x_end] = True

            # Convert to world coordinates (flip Y, apply scale)
            # Subtract pad offset so coordinates align with the original (unpadded) model
            world_x0 = float(x_start - pad) * pixel_scale
            world_x1 = float(x_end - pad) * pixel_scale
            world_y0 = float(h_original - (y_end - pad)) * pixel_scale
            world_y1 = float(h_original - (y - pad)) * pixel_scale
            z_bot = 0.0
            z_tp = float(outline_layers) * PrinterConfig.LAYER_HEIGHT

            base_idx = len(vertices)
            vertices.extend([
                [world_x0, world_y0, z_bot], [world_x1, world_y0, z_bot],
                [world_x1, world_y1, z_bot], [world_x0, world_y1, z_bot],
                [world_x0, world_y0, z_tp], [world_x1, world_y0, z_tp],
                [world_x1, world_y1, z_tp], [world_x0, world_y1, z_tp]
            ])
            cube_faces = CUBE_FACES
            faces.extend([[v + base_idx for v in f] for f in cube_faces])

    if not vertices:
        return None

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())

    logger.info("Outline: Generated outline mesh: %s verts, %s faces", f"{len(mesh.vertices):,}", f"{len(mesh.faces):,}")
    return mesh


# ========== Height Map Functions ==========

def calculate_luminance(hex_color):
    """
    Calculate relative luminance of a color using standard formula.

    Formula: Y = 0.299*R + 0.587*G + 0.114*B

    Args:
        hex_color: Color in hex format (e.g., '#ff0000')

    Returns:
        float: Luminance value (0-255)
    """
    # Remove '#' if present
    hex_color = hex_color.lstrip('#')

    # Convert hex to RGB
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    # Calculate luminance using standard formula
    luminance = 0.299 * r + 0.587 * g + 0.114 * b

    return luminance


def generate_auto_height_map(color_list, mode, base_thickness, max_relief_height):
    """
    Generate automatic height mapping based on color luminance using Min-Max normalization.

    This function calculates the luminance of each color and assigns heights
    using normalization, ensuring all heights fall within [base_thickness, max_relief_height].
    This prevents height explosion when dealing with many colors.

    Algorithm:
    1. Calculate luminance Y = 0.299*R + 0.587*G + 0.114*B for each color
    2. Find Y_min and Y_max across all colors
    3. Calculate available height range: Delta_Z = max_relief_height - base_thickness
    4. For each color, calculate normalized ratio:
       - If "浅色凸起": Ratio = (Y - Y_min) / (Y_max - Y_min)
       - If "深色凸起": Ratio = 1.0 - (Y - Y_min) / (Y_max - Y_min)
    5. Final height = base_thickness + Ratio * Delta_Z
    6. Round to 0.1mm precision

    Args:
        color_list: List of hex color strings (e.g., ['#ff0000', '#00ff00'])
        mode: Sorting mode - "深色凸起" (darker higher) or "浅色凸起" (lighter higher)
        base_thickness: Base thickness in mm (minimum height)
        max_relief_height: Maximum relief height in mm (maximum height)

    Returns:
        dict: Color-to-height mapping {hex_color: height_mm}

    Example:
        >>> colors = ['#ff0000', '#00ff00', '#0000ff']
        >>> generate_auto_height_map(colors, "深色凸起", 1.2, 5.0)
        {'#00ff00': 1.2, '#ff0000': 3.1, '#0000ff': 5.0}
    """
    if not color_list:
        return {}

    # Step 1: Calculate luminance for each color
    color_luminance = []
    for color in color_list:
        luminance = calculate_luminance(color)
        color_luminance.append((color, luminance))

    # Step 2: Find min and max luminance
    luminances = [lum for _, lum in color_luminance]
    y_min = min(luminances)
    y_max = max(luminances)

    # Handle edge case: all colors have same luminance
    if y_max == y_min:
        # All colors get the same height (average of base and max)
        avg_height = (base_thickness + max_relief_height) / 2.0
        color_height_map = {color: round(avg_height, 1) for color, _ in color_luminance}
        logger.info("AutoHeight: All colors have same luminance, using average height: %.1fmm", avg_height)
        return color_height_map

    # Step 3: Calculate available height range
    delta_z = max_relief_height - base_thickness

    # Step 4 & 5: Calculate normalized heights
    color_height_map = {}
    for color, luminance in color_luminance:
        # Normalize luminance to [0, 1]
        normalized = (luminance - y_min) / (y_max - y_min)

        # Apply mode: darker higher or lighter higher
        if "深色凸起" in mode or "Darker Higher" in mode:
            # Darker colors (lower luminance) should be higher
            # Invert the ratio: 0 -> 1, 1 -> 0
            ratio = 1.0 - normalized
        else:
            # Lighter colors (higher luminance) should be higher
            # Keep the ratio as is: 0 -> 0, 1 -> 1
            ratio = normalized

        # Calculate final height (minimum 0.08mm = 1 layer height)
        height = max(0.08, base_thickness + ratio * delta_z)

        # Round to 0.1mm precision
        color_height_map[color] = round(height, 1)

    logger.info("AutoHeight: Generated normalized height map for %s colors", len(color_list))
    logger.info("AutoHeight: Mode: %s", mode)
    logger.info("AutoHeight: Luminance range: %.1f - %.1f", y_min, y_max)
    logger.info("AutoHeight: Height range: %.1fmm - %.1fmm", min(color_height_map.values()), max(color_height_map.values()))
    logger.info("AutoHeight: Total height span: %.1fmm", max(color_height_map.values()) - min(color_height_map.values()))

    return color_height_map


# ========== Main Conversion Function ==========

def convert_image_to_3d(image_path, lut_path, target_width_mm, spacer_thick,
                         structure_mode, auto_bg, bg_tol, color_mode,
                         add_loop, loop_width, loop_length, loop_hole, loop_pos,
                         modeling_mode=ModelingMode.HIGH_FIDELITY, quantize_colors=32,
                         blur_kernel=0, smooth_sigma=10,
                         color_replacements=None, replacement_regions=None, backing_color_id=0, separate_backing=False,
                         enable_relief=False, color_height_map=None,
                         height_mode: str = "color",
                         heightmap_path=None, heightmap_max_height=None,
                         enable_cleanup=True,
                         enable_outline=False, outline_width=2.0,
                         free_color_set=None,
                         hue_weight: float = 0.0,
                         progress=None):
    """
    Main conversion function: Convert image to 3D model.

    This refactored coordinator function is responsible for:
    1. Calling LuminaImageProcessor to process the image
    2. Calling get_mesher to get the mesh generator
    3. Generating meshes for each material
    4. Adding keychain loop (if needed)
    5. Exporting 3MF file

    Args:
        image_path: Path to input image
        lut_path: LUT file path (string) or Gradio File object
        target_width_mm: Target width in millimeters
        spacer_thick: Backing thickness in mm
        structure_mode: "Double-sided" or "Single-sided"
        auto_bg: Enable automatic background removal
        bg_tol: Background tolerance value
        color_mode: Color system mode (CMYW/RYBW/6-Color)
        add_loop: Enable keychain loop
        loop_width: Loop width in mm
        loop_length: Loop length in mm
        loop_hole: Loop hole diameter in mm
        loop_pos: Loop position (x, y) tuple
        modeling_mode: Modeling mode ("high-fidelity")
        quantize_colors: Number of colors for K-Means quantization
        blur_kernel: Median filter kernel size (0=disabled, recommended 0-5, default 0)
        smooth_sigma: Bilateral filter sigma value (recommended 5-20, default 10)
        color_replacements: Optional dict of color replacements {hex: hex}
                           e.g., {'#ff0000': '#00ff00'}
        backing_color_id: Backing material ID (0-7), default is 0 (White)
        separate_backing: Boolean flag to separate backing as individual object (default: False)
                         When True, backing_color_id is overridden to -2

    Returns:
        Tuple of (3mf_path, glb_path, preview_image, status_message)
    """
    def _prog(val: float, desc: str = ""):
        if progress is not None:
            progress(val, desc=desc)

    # Input validation
    if image_path is None:
        return None, None, None, "[ERROR] Please upload an image", None
    if lut_path is None:
        return None, None, None, "[WARNING] Please select or upload a .npy calibration file!", None

    # Handle LUT path (supports string path or Gradio File object)
    if isinstance(lut_path, str):
        actual_lut_path = lut_path
    elif hasattr(lut_path, 'name'):
        actual_lut_path = lut_path.name
    else:
        return None, None, None, "[ERROR] Invalid LUT file format", None

    # Handle backing separation: override backing_color_id if separate_backing is True
    # Error handling for checkbox state (Requirement 8.4)
    try:
        separate_backing = bool(separate_backing) if separate_backing is not None else False
    except Exception as e:
        logger.error("Error reading separate_backing checkbox state: %s, using default (False)", e)
        separate_backing = False

    if separate_backing:
        backing_color_id = -2
        logger.info("Backing separation enabled: backing will be a separate object (white)")
    else:
        logger.info("Backing separation disabled: backing merged with first layer (backing_color_id=%s)", backing_color_id)

    logger.info("Starting conversion...")
    logger.info("Mode: %s, Quantize: %s", modeling_mode.get_display_name(), quantize_colors)
    logger.info("Filters: blur_kernel=%s, smooth_sigma=%s", blur_kernel, smooth_sigma)
    logger.info("LUT: %s", actual_lut_path)

    # ========== Raster-based Processing ==========
    # NOTE: CMYW and RYBW share 100% of the processing pipeline.
    # Only difference is the LUT file and slot names from ColorSystem.get()
    # All K-Means, layer slicing, and mesh generation logic is unified.

    color_conf = ColorSystem.get(color_mode)
    slot_names = color_conf['slots']
    preview_colors = color_conf['preview']

    # Validate backing_color_id (allow -2 as special marker for separation)
    num_materials = len(slot_names)
    if backing_color_id != -2 and (backing_color_id < 0 or backing_color_id >= num_materials):
        logger.warning("Invalid backing_color_id=%s, using default (0)", backing_color_id)
        backing_color_id = 0

    # Step 1: Image Processing
    _prog(0.05, "图像处理与 LUT 匹配中... | Processing image...")
    # Always enable HiFi timing for better observability (zero-overhead when not printing)
    _bench_enabled = True
    _hifi_timings = {}
    _hifi_t0 = time.perf_counter()

    try:
        processor = LuminaImageProcessor(actual_lut_path, color_mode, hue_weight=hue_weight)
        processor.enable_cleanup = enable_cleanup
        result = processor.process_image(
            image_path=image_path,
            target_width_mm=target_width_mm,
            modeling_mode=modeling_mode,
            quantize_colors=quantize_colors,
            auto_bg=auto_bg,
            bg_tol=bg_tol,
            blur_kernel=blur_kernel,
            smooth_sigma=smooth_sigma
        )
        _hifi_timings['image_proc_s'] = time.perf_counter() - _hifi_t0
    except Exception as e:
        return None, None, None, f"[ERROR] Image processing failed: {e}", None

    matched_rgb = result['matched_rgb']
    material_matrix = result['material_matrix']
    mask_solid = result['mask_solid']
    target_w, target_h = result['dimensions']
    pixel_scale = result['pixel_scale']
    mode_info = result['mode_info']
    debug_data = result.get('debug_data', None)

    # Override preview_colors with actual per-slot measured colors from the LUT.
    if hasattr(processor, 'ref_stacks') and processor.ref_stacks is not None:
        actual_slot_colors = _get_actual_lut_slot_colors(processor)
        if actual_slot_colors:
            preview_colors = dict(preview_colors)  # local copy; don't mutate shared config
            for slot_id, rgb in actual_slot_colors.items():
                preview_colors[slot_id] = [rgb[0], rgb[1], rgb[2], 255]
            logger.info("LUT slot colors derived from calibration data:")
            for sid in sorted(preview_colors):
                c = preview_colors[sid]
                logger.info("  slot%s: #%02x%02x%02x", sid, c[0], c[1], c[2])

    # Apply color replacements if provided
    effective_color_replacements = _normalize_color_replacements_input(color_replacements)
    if replacement_regions:
        api_format_replacements = _normalize_color_replacements_input(replacement_regions)
        if api_format_replacements:
            effective_color_replacements.update(api_format_replacements)
            replacement_regions = [r for r in replacement_regions if r.get('mask') is not None]

    if effective_color_replacements:
        from core.color.replacement import ColorReplacementManager
        manager = ColorReplacementManager.from_dict(effective_color_replacements)
        old_rgb = matched_rgb.copy()
        matched_rgb = manager.apply_to_image(matched_rgb)
        logger.info("Applied %s color replacements", len(manager))

        for orig_hex, repl_hex in effective_color_replacements.items():
            orig_rgb_tuple = hex_to_rgb(orig_hex)
            repl_rgb_tuple = hex_to_rgb(repl_hex)
            orig_mask = np.all(old_rgb == orig_rgb_tuple, axis=-1)
            if not np.any(orig_mask):
                continue
            repl_lab = processor._rgb_to_lab(np.array([repl_rgb_tuple], dtype=np.uint8))
            _, lut_idx = processor.kdtree.query(repl_lab)
            lut_idx = lut_idx[0]
            new_stacks = processor.ref_stacks[lut_idx]
            material_matrix[orig_mask] = new_stacks
            lut_color = processor.lut_rgb[lut_idx]
            logger.info("material_matrix: %s -> LUT#%s rgb(%s,%s,%s) stacks=%s", orig_hex, lut_idx, lut_color[0], lut_color[1], lut_color[2], new_stacks)

    # Apply region replacements in-order
    if replacement_regions:
        def _resolve_lut_index_for_rgb(replacement_rgb):
            repl_lab = processor._rgb_to_lab(np.array([replacement_rgb], dtype=np.uint8))
            _, lut_idx = processor.kdtree.query(repl_lab)
            return lut_idx[0]

        matched_rgb, material_matrix = _apply_regions_to_raster_outputs(
            matched_rgb,
            material_matrix,
            mask_solid,
            replacement_regions,
            _resolve_lut_index_for_rgb,
            processor.ref_stacks,
        )

    logger.info("Image processed: %sx%s px, scale=%s mm/px", target_w, target_h, pixel_scale)

    # Step 2: Save Debug Preview (High-Fidelity mode only)
    if debug_data is not None and mode_info['mode'] == ModelingMode.HIGH_FIDELITY:
        try:
            num_materials = len(slot_names)
            _save_debug_preview(
                debug_data=debug_data,
                material_matrix=material_matrix,
                mask_solid=mask_solid,
                image_path=image_path,
                mode_name=mode_info['name'],
                num_materials=num_materials
            )
        except Exception as e:
            logger.warning("Failed to save debug preview: %s", e)

    # Step 3: Generate Preview Image
    preview_rgba = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    preview_rgba[mask_solid, :3] = matched_rgb[mask_solid]
    preview_rgba[mask_solid, 3] = 255

    # Step 4: Handle Keychain Loop
    loop_info = None
    if add_loop and loop_pos is not None:
        loop_info = _calculate_loop_info(
            loop_pos, loop_width, loop_length, loop_hole,
            mask_solid, material_matrix, target_w, target_h, pixel_scale
        )

        if loop_info:
            preview_rgba = _draw_loop_on_preview(
                preview_rgba, loop_info, color_conf, pixel_scale
            )

    preview_img = Image.fromarray(preview_rgba, mode='RGBA')

    # Step 5: Build Voxel Matrix
    try:
        # 5-Color Extended: force single-sided face-up
        if "5-Color Extended" in color_mode:
            logger.info("5-Color Extended: forcing single-sided face-up")
            structure_mode = "单面"
            if enable_relief:
                logger.info("5-Color Extended: 2.5D relief mode disabled (incompatible)")
                enable_relief = False
            full_matrix, backing_metadata = _build_voxel_matrix_faceup(
                material_matrix, mask_solid, spacer_thick, backing_color_id
            )
        # 2.5D Relief Mode Support
        heightmap_height_matrix = None
        heightmap_stats = None
        if enable_relief and height_mode == "heightmap" and heightmap_path is not None:
            logger.info("Heightmap Relief Mode: 尝试加载高度图...")
            logger.info("高度图路径: %s", heightmap_path)
            try:
                hm_max = heightmap_max_height if heightmap_max_height is not None else 5.0
                hm_result = HeightmapLoader.load_and_process(
                    heightmap_path=heightmap_path,
                    target_w=target_w,
                    target_h=target_h,
                    max_relief_height=hm_max,
                    base_thickness=spacer_thick
                )
                if hm_result['success']:
                    heightmap_height_matrix = hm_result['height_matrix']
                    heightmap_stats = hm_result['stats']
                    for w in hm_result.get('warnings', []):
                        logger.info("%s", w)
                    logger.info("高度图加载成功: %s", heightmap_height_matrix.shape)
                else:
                    logger.warning("高度图处理失败: %s，回退到 flat 模式", hm_result['error'])
            except Exception as e:
                logger.warning("高度图处理异常: %s，回退到 flat 模式", e)
        elif enable_relief and height_mode == "heightmap" and heightmap_path is None:
            logger.warning("heightmap mode selected but no heightmap provided, falling back to flat")

        if heightmap_height_matrix is not None:
            logger.info("2.5D Heightmap Relief Mode ENABLED")
            full_matrix, backing_metadata = _build_relief_voxel_matrix(
                matched_rgb=matched_rgb,
                material_matrix=material_matrix,
                mask_solid=mask_solid,
                color_height_map=color_height_map if color_height_map else {},
                default_height=spacer_thick,
                structure_mode=structure_mode,
                backing_color_id=backing_color_id,
                pixel_scale=pixel_scale,
                height_matrix=heightmap_height_matrix
            )
        elif enable_relief and height_mode == "color" and color_height_map:
            logger.info("2.5D Relief Mode ENABLED")
            logger.info("Color height map: %s", color_height_map)

            full_matrix, backing_metadata = _build_relief_voxel_matrix(
                matched_rgb=matched_rgb,
                material_matrix=material_matrix,
                mask_solid=mask_solid,
                color_height_map=color_height_map,
                default_height=spacer_thick,
                structure_mode=structure_mode,
                backing_color_id=backing_color_id,
                pixel_scale=pixel_scale
            )
        else:
            # Original flat voxel matrix
            full_matrix, backing_metadata = _build_voxel_matrix(
                material_matrix, mask_solid, spacer_thick, structure_mode, backing_color_id
            )

        total_layers = full_matrix.shape[0]
        logger.info("Voxel matrix: %s (ZxHxW)", full_matrix.shape)
        logger.info("Backing layer: z=%s, color_id=%s", backing_metadata['backing_z_range'], backing_metadata['backing_color_id'])
    except Exception as e:
        logger.error("Error marking backing layer: %s", e)
        logger.info("Falling back to original behavior (backing_color_id=0)")

        try:
            full_matrix, backing_metadata = _build_voxel_matrix(
                material_matrix, mask_solid, spacer_thick, structure_mode, backing_color_id=0
            )
            total_layers = full_matrix.shape[0]
            logger.info("Fallback successful: %s (ZxHxW)", full_matrix.shape)
        except Exception as fallback_error:
            return None, None, None, f"[ERROR] Voxel matrix generation failed: {fallback_error}", None

    # Step 6: Generate 3D Meshes
    _prog(0.30, "生成 3D 网格中... | Generating meshes...")
    _mesh_t0 = time.perf_counter() if _bench_enabled else None

    scene = trimesh.Scene()

    logger.info("Transform: XY=%smm/px, Z=variable (optical=%smm, backing=%smm)", pixel_scale, PrinterConfig.LAYER_HEIGHT, PrinterConfig.BACKING_LAYER_HEIGHT)

    mesher = get_mesher(modeling_mode)
    logger.info("Using mesher: %s", mesher.__class__.__name__)

    valid_slot_names = []
    num_materials = len(slot_names)
    logger.info("Generating meshes for %s materials...", num_materials)

    max_workers = min(4, num_materials)
    parallel_enabled = max_workers > 1 and os.getenv("LUMINA_DISABLE_PARALLEL_MESH", "0") != "1"
    mesh_results = {}
    mesh_errors = {}
    if parallel_enabled:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {
                pool.submit(mesher.generate_mesh, full_matrix, mat_id, target_h): mat_id
                for mat_id in range(num_materials)
            }
            for future in as_completed(future_map):
                mat_id = future_map[future]
                try:
                    mesh_results[mat_id] = future.result()
                except Exception as e:
                    mesh_errors[mat_id] = e
    else:
        for mat_id in range(num_materials):
            try:
                mesh_results[mat_id] = mesher.generate_mesh(full_matrix, mat_id, target_h)
            except Exception as e:
                mesh_errors[mat_id] = e

    for mat_id in range(num_materials):
        if mat_id in mesh_errors:
            e = mesh_errors[mat_id]
            logger.error("Error generating mesh for material %s (%s): %s", mat_id, slot_names[mat_id], e)
            logger.info("Continuing with other materials...")
            continue
        mesh = mesh_results.get(mat_id)
        if mesh:
            _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale)
            mesh.visual.face_colors = preview_colors[mat_id]
            name = slot_names[mat_id]
            mesh.metadata['name'] = name
            scene.add_geometry(
                mesh,
                node_name=name,
                geom_name=name
            )
            valid_slot_names.append(name)
            logger.info("Added mesh for %s", name)

    # Conditionally generate backing mesh
    if separate_backing:
        logger.info("Attempting to generate separate backing mesh (mat_id=-2)...")
        try:
            backing_mesh = mesher.generate_mesh(full_matrix, mat_id=-2, height_px=target_h)

            if backing_mesh is None or len(backing_mesh.vertices) == 0:
                logger.warning("Backing mesh is empty, skipping separate backing object")
                logger.info("Continuing with other material meshes...")
            else:
                _apply_variable_layer_height_transform(backing_mesh, backing_metadata, pixel_scale)
                backing_color = preview_colors[0]
                backing_mesh.visual.face_colors = backing_color
                backing_name = "Backing"
                backing_mesh.metadata['name'] = backing_name
                scene.add_geometry(backing_mesh, node_name=backing_name, geom_name=backing_name)
                valid_slot_names.append(backing_name)
                logger.info("Added backing mesh as separate object (white)")
                logger.info("Scene now has %s geometries", len(scene.geometry))
        except Exception as e:
            logger.exception("Error generating backing mesh: %s", e)
            logger.info("Continuing with other material meshes...")
    else:
        logger.info("Backing merged with first layer (original behavior)")

    # Free Color mesh extraction
    if free_color_set:
        _free_set = {c.lower() for c in free_color_set if c}
        if _free_set:
            logger.info("Free Color mode: %s colors marked", len(_free_set))
            for hex_c in sorted(_free_set):
                try:
                    r_fc = int(hex_c[1:3], 16)
                    g_fc = int(hex_c[3:5], 16)
                    b_fc = int(hex_c[5:7], 16)
                    color_mask = (
                        (matched_rgb[:, :, 0] == r_fc) &
                        (matched_rgb[:, :, 1] == g_fc) &
                        (matched_rgb[:, :, 2] == b_fc) &
                        mask_solid
                    )
                    if not np.any(color_mask):
                        logger.info("  %s: no pixels found, skipping", hex_c)
                        continue
                    fc_matrix = np.where(
                        np.broadcast_to(color_mask[np.newaxis, :, :], full_matrix.shape),
                        full_matrix, -1
                    )
                    fc_matrix = np.where(fc_matrix >= 0, 0, -1)
                    fc_mesh = mesher.generate_mesh(fc_matrix, 0, target_h)
                    if fc_mesh and len(fc_mesh.vertices) > 0:
                        _apply_variable_layer_height_transform(fc_mesh, backing_metadata, pixel_scale)
                        fc_mesh.visual.face_colors = [r_fc, g_fc, b_fc, 255]
                        fc_name = f"Free_{hex_c[1:]}"
                        fc_mesh.metadata['name'] = fc_name
                        scene.add_geometry(fc_mesh, node_name=fc_name, geom_name=fc_name)
                        valid_slot_names.append(fc_name)
                        logger.info("  %s -> standalone object '%s' (%s px)", hex_c, fc_name, np.sum(color_mask))
                    else:
                        logger.info("  %s: mesh empty, skipping", hex_c)
                except Exception as e:
                    logger.error("Error extracting free color %s: %s", hex_c, e)

    _hifi_timings['mesh_gen_s'] = time.perf_counter() - _mesh_t0

    # Step 7: Add Keychain Loop
    loop_added = False

    if add_loop and loop_info is not None:
        try:
            loop_thickness = total_layers * PrinterConfig.LAYER_HEIGHT
            loop_mesh = create_keychain_loop(
                width_mm=loop_info['width_mm'],
                length_mm=loop_info['length_mm'],
                hole_dia_mm=loop_info['hole_dia_mm'],
                thickness_mm=loop_thickness,
                attach_x_mm=loop_info['attach_x_mm'],
                attach_y_mm=loop_info['attach_y_mm']
            )

            if loop_mesh is not None:
                loop_mesh.visual.face_colors = preview_colors[loop_info['color_id']]
                loop_mesh.metadata['name'] = "Keychain_Loop"
                scene.add_geometry(
                    loop_mesh,
                    node_name="Keychain_Loop",
                    geom_name="Keychain_Loop"
                )
                valid_slot_names.append("Keychain_Loop")
                loop_added = True
                logger.info("Loop added successfully")
        except Exception as e:
            logger.error("Loop creation failed: %s", e)

    # Generate Outline Mesh
    outline_added = False
    if enable_outline:
        try:
            backing_z_start, backing_z_end = backing_metadata['backing_z_range']
            optical_layers_bottom = backing_z_start
            backing_layers = backing_z_end - backing_z_start + 1
            optical_layers_top = total_layers - backing_z_end - 1 if backing_z_end < total_layers - 1 else 0

            optical_height = (optical_layers_bottom + optical_layers_top) * PrinterConfig.LAYER_HEIGHT
            backing_height = backing_layers * PrinterConfig.BACKING_LAYER_HEIGHT
            outline_thickness_mm = optical_height + backing_height

            logger.info("Generating outline: width=%smm, thickness=%smm", outline_width, outline_thickness_mm)

            outline_mesh = _generate_outline_mesh(
                mask_solid=mask_solid,
                pixel_scale=pixel_scale,
                outline_width_mm=outline_width,
                outline_thickness_mm=outline_thickness_mm,
                target_h=target_h
            )

            if outline_mesh is not None:
                outline_mesh.visual.face_colors = preview_colors[0]
                outline_name = "Outline"
                outline_mesh.metadata['name'] = outline_name
                scene.add_geometry(outline_mesh, node_name=outline_name, geom_name=outline_name)
                valid_slot_names.append(outline_name)
                logger.info("Outline added as standalone '%s' object", outline_name)
                outline_added = True
            else:
                logger.warning("Outline mesh is empty, skipping")
        except Exception as e:
            logger.exception("Outline generation failed: %s", e)

    # Step 8: Export 3MF
    is_single_sided = "单面" in structure_mode or "single" in structure_mode.lower()
    is_5color = "5-Color Extended" in color_mode

    # 5-Color: Z flip for correct viewing surface orientation
    if is_5color:
        max_z = max(
            g.vertices[:, 2].max()
            for g in scene.geometry.values()
            if hasattr(g, "vertices") and len(g.vertices) > 0
        )
        z_flip = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, -1, max_z],
            [0, 0, 0, 1],
        ])
        for geom_name in list(scene.geometry.keys()):
            scene.geometry[geom_name].apply_transform(z_flip)

    # Single-sided: X-axis mirror correction
    if is_single_sided:
        model_width_mm = target_w * pixel_scale
        mirror_transform = np.array([
            [-1, 0, 0, model_width_mm],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        for geom_name in list(scene.geometry.keys()):
            scene.geometry[geom_name].apply_transform(mirror_transform)

    # 5-Color: Additional X mirror for correct left/right orientation
    if is_5color:
        model_width_mm = target_w * pixel_scale
        x_mirror_again = np.array([
            [-1, 0, 0, model_width_mm],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        for geom_name in list(scene.geometry.keys()):
            scene.geometry[geom_name].apply_transform(x_mirror_again)

    _prog(0.50, "导出 3MF 中... | Exporting 3MF...")
    _export_t0 = time.perf_counter() if _bench_enabled else None

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    out_path = os.path.join(OUTPUT_DIR, generate_model_filename(base_name, modeling_mode, color_mode))

    if len(scene.geometry) == 0:
        logger.error("No meshes generated, cannot export 3MF")
        return None, None, None, "[ERROR] Mesh generation failed: No valid meshes generated", None

    print_settings = EXTENDED_PRINT_SETTINGS

    try:
        logger.info("Exporting with BambuStudio metadata...")
        backing_z_start, backing_z_end = backing_metadata['backing_z_range']
        backing_layers_count = backing_z_end - backing_z_start + 1
        export_scene_with_bambu_metadata(
            scene=scene,
            output_path=out_path,
            slot_names=valid_slot_names,
            preview_colors=preview_colors,
            settings=print_settings,
            color_mode=color_mode,
            optical_layer_height=PrinterConfig.LAYER_HEIGHT,
            backing_layer_height=PrinterConfig.BACKING_LAYER_HEIGHT,
            optical_layers=PrinterConfig.COLOR_LAYERS,
            backing_layers=backing_layers_count
        )
        _hifi_timings['export_3mf_s'] = time.perf_counter() - _export_t0
        logger.info("3MF exported with embedded settings: %s", out_path)
    except Exception as e:
        logger.error("Error exporting 3MF: %s", e)
        return None, None, None, f"[ERROR] 3MF export failed: {e}", None

    # Generate Color Recipe Report
    color_recipe_path = None
    recipe_policy = os.getenv("LUMINA_COLOR_RECIPE_POLICY", "auto").strip().lower()
    try:
        recipe_auto_max_pixels = int(os.getenv("LUMINA_COLOR_RECIPE_AUTO_MAX_PIXELS", "1200000"))
    except Exception:
        recipe_auto_max_pixels = 1200000
    solid_pixels = int(np.count_nonzero(mask_solid))
    enable_recipe = recipe_policy == "on" or (
        recipe_policy == "auto" and solid_pixels <= recipe_auto_max_pixels
    )
    if enable_recipe:
        try:
            from core.utils.color_recipe_logger import ColorRecipeLogger

            model_filename = os.path.basename(out_path)
            color_recipe_path = ColorRecipeLogger.create_from_processor(
                processor=processor,
                output_dir=OUTPUT_DIR,
                model_filename=model_filename,
                matched_rgb=matched_rgb,
                material_matrix=material_matrix,
                mask_solid=mask_solid
            )
        except Exception as e:
            logger.warning("Failed to generate color recipe report: %s", e)
    else:
        logger.info(
            "Skipping color recipe report: policy=%s, solid_pixels=%s, auto_max=%s",
            recipe_policy, solid_pixels, recipe_auto_max_pixels
        )

    # Step 9: Generate 3D Preview
    _prog(0.90, "生成 3D 预览中... | Generating 3D preview...")
    preview_mesh = _create_preview_mesh(
        matched_rgb, mask_solid, total_layers,
        backing_color_id=backing_color_id,
        backing_z_range=backing_metadata['backing_z_range'],
        preview_colors=preview_colors
    )

    if preview_mesh:
        preview_transform = np.eye(4)
        preview_transform[0, 0] = pixel_scale
        preview_transform[1, 1] = pixel_scale
        preview_transform[2, 2] = PrinterConfig.LAYER_HEIGHT
        preview_mesh.apply_transform(preview_transform)

        if is_single_sided:
            model_width_mm = target_w * pixel_scale
            mirror_transform = np.array([
                [-1, 0, 0, model_width_mm],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ])
            preview_mesh.apply_transform(mirror_transform)

        if loop_added and loop_info:
            try:
                preview_loop = create_keychain_loop(
                    width_mm=loop_info['width_mm'],
                    length_mm=loop_info['length_mm'],
                    hole_dia_mm=loop_info['hole_dia_mm'],
                    thickness_mm=loop_thickness,
                    attach_x_mm=loop_info['attach_x_mm'],
                    attach_y_mm=loop_info['attach_y_mm']
                )
                if preview_loop:
                    loop_color = preview_colors[loop_info['color_id']]
                    preview_loop.visual.face_colors = [loop_color] * len(preview_loop.faces)
                    preview_mesh = trimesh.util.concatenate([preview_mesh, preview_loop])
            except Exception as e:
                logger.error("Preview loop failed: %s", e)

        if outline_added:
            try:
                outline_thickness_mm = total_layers * PrinterConfig.LAYER_HEIGHT
                preview_outline = _generate_outline_mesh(
                    mask_solid=mask_solid,
                    pixel_scale=pixel_scale,
                    outline_width_mm=outline_width,
                    outline_thickness_mm=outline_thickness_mm,
                    target_h=target_h
                )
                if preview_outline:
                    outline_color = preview_colors[0]
                    preview_outline.visual.face_colors = [outline_color] * len(preview_outline.faces)
                    preview_mesh = trimesh.util.concatenate([preview_mesh, preview_outline])
            except Exception as e:
                logger.error("Preview outline failed: %s", e)

    if preview_mesh:
        glb_path = os.path.join(OUTPUT_DIR, generate_preview_filename(base_name))
        preview_mesh.export(glb_path)
    else:
        glb_path = None

    # Step 10: Generate Status Message
    Stats.increment("conversions")

    if _hifi_timings:
        image_proc_s = _hifi_timings.get('image_proc_s', 0.0)
        mesh_gen_s = _hifi_timings.get('mesh_gen_s', 0.0)
        export_3mf_s = _hifi_timings.get('export_3mf_s', 0.0)
        total_s = image_proc_s + mesh_gen_s + export_3mf_s
        logger.info(
            "HiFi timings (s): image_proc=%.3f, mesh_gen=%.3f, export_3mf=%.3f, total=%.3f",
            image_proc_s, mesh_gen_s, export_3mf_s, total_s
        )

    mode_name = mode_info['mode'].get_display_name()
    msg = f"✅ Conversion complete ({mode_name})! Resolution: {target_w}×{target_h}px"

    if heightmap_stats is not None:
        msg += (f" | 📊 高度图: {heightmap_stats['min_mm']:.1f}mm ~ "
                f"{heightmap_stats['max_mm']:.1f}mm (avg {heightmap_stats['avg_mm']:.1f}mm)")

    if loop_added:
        msg += f" | Loop: {slot_names[loop_info['color_id']]}"

    total_pixels = target_w * target_h
    if glb_path and total_pixels > 500_000:
        msg += " | 3D preview simplified"

    return out_path, glb_path, preview_img, msg, color_recipe_path


# ========== Preview Generation Functions ==========

def generate_preview_cached(image_path, lut_path, target_width_mm,
                            auto_bg, bg_tol, color_mode,
                            modeling_mode: ModelingMode = ModelingMode.HIGH_FIDELITY,
                            quantize_colors: int = 64,
                            backing_color_id: int = 0,
                            enable_cleanup: bool = True,
                            is_dark: bool = True,
                            hue_weight: float = 0.0,
                            structure_mode: str = "single"):
    """
    Generate preview and cache data
    For 2D preview interface

    Args:
        image_path: Path to input image
        lut_path: LUT file path (string) or Gradio File object
        target_width_mm: Target width in millimeters
        auto_bg: Enable automatic background removal
        bg_tol: Background tolerance value
        color_mode: Color system mode (CMYW/RYBW)
        modeling_mode: Modeling mode (HIGH_FIDELITY/PIXEL_ART)
        quantize_colors: K-Means quantization color count (8-256)
        backing_color_id: Backing layer material ID (0-7), default 0 (White)

    Returns:
        tuple: (preview_image, cache_data, status_message)
    """
    if image_path is None:
        return None, None, "[ERROR] Please upload an image"
    if lut_path is None:
        return None, None, "[WARNING] Please select or upload calibration file"

    if isinstance(lut_path, str):
        actual_lut_path = lut_path
    elif hasattr(lut_path, 'name'):
        actual_lut_path = lut_path.name
    else:
        return None, None, "[ERROR] Invalid LUT file format"

    # Handle None modeling_mode with default
    if modeling_mode is None or modeling_mode == "none":
        modeling_mode = ModelingMode.HIGH_FIDELITY
        logger.warning("modeling_mode was None, using default HIGH_FIDELITY")
    else:
        modeling_mode = ModelingMode(modeling_mode)

    # Clamp quantize_colors to valid range
    quantize_colors = max(8, min(256, quantize_colors))

    color_conf = ColorSystem.get(color_mode)

    try:
        logger.info("hue_weight=%s, color_mode=%s", hue_weight, color_mode)
        processor = LuminaImageProcessor(actual_lut_path, color_mode, hue_weight=hue_weight)
        processor.enable_cleanup = enable_cleanup
        result = processor.process_image(
            image_path=image_path,
            target_width_mm=target_width_mm,
            modeling_mode=modeling_mode,
            quantize_colors=quantize_colors,
            auto_bg=auto_bg,
            bg_tol=bg_tol,
            blur_kernel=0,
            smooth_sigma=10
        )
    except Exception as e:
        return None, None, f"[ERROR] Preview generation failed: {e}"

    matched_rgb = result['matched_rgb']
    material_matrix = result['material_matrix']
    mask_solid = result['mask_solid']
    target_w, target_h = result['dimensions']

    preview_rgba = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    preview_rgba[mask_solid, :3] = matched_rgb[mask_solid]
    preview_rgba[mask_solid, 3] = 255

    cache = {
        'target_w': target_w,
        'target_h': target_h,
        'target_width_mm': target_width_mm,
        'mask_solid': mask_solid,
        'material_matrix': material_matrix,
        'matched_rgb': matched_rgb,
        'preview_rgba': preview_rgba.copy(),
        'color_conf': color_conf,
        'color_mode': color_mode,
        'quantize_colors': quantize_colors,
        'backing_color_id': backing_color_id,
        'is_dark': is_dark,
        'structure_mode': structure_mode
    }

    # 统一缓存契约：保证 quantized_image 始终可用
    cache['debug_data'] = result.get('debug_data') if isinstance(result, dict) else None
    cache['quantized_image'] = result.get('quantized_image')
    _ensure_quantized_image_in_cache(cache)

    # Extract color palette from cache
    color_palette = extract_color_palette(cache)
    cache['color_palette'] = color_palette

    display = render_preview(
        preview_rgba, None, 0, 0, 0, 0, False, color_conf,
        target_width_mm=target_width_mm, is_dark=is_dark
    )

    num_colors = len(color_palette)
    return display, cache, f"[OK] Preview ({target_w}×{target_h}px, {num_colors} colors) | Click image to place loop"


def generate_final_model(image_path, lut_path, target_width_mm, spacer_thick,
                        structure_mode, auto_bg, bg_tol, color_mode,
                        add_loop, loop_width, loop_length, loop_hole, loop_pos,
                        modeling_mode=ModelingMode.HIGH_FIDELITY, quantize_colors=64,
                        color_replacements=None, replacement_regions=None, backing_color_name="White",
                        separate_backing=False, enable_relief=False, color_height_map=None,
                        height_mode: str = "color",
                        heightmap_path=None, heightmap_max_height=None,
                        enable_cleanup=True,
                        enable_outline=False, outline_width=2.0,
                        free_color_set=None,
                        hue_weight: float = 0.0,
                        progress=None):
    """
    Wrapper function for generating final model.

    Directly calls main conversion function with smart defaults:
    - blur_kernel=0 (disable median filter, preserve details)
    - smooth_sigma=10 (gentle bilateral filter, preserve edges)

    Args:
        color_replacements: Optional dict of color replacements {hex: hex}
                           e.g., {'#ff0000': '#00ff00'}
        backing_color_name: Name of backing color (e.g., "White", "Cyan")
                           Will be converted to material ID based on color_mode
        separate_backing: Boolean flag to separate backing as individual object (default: False)
        height_mode: "color" or "heightmap", determines relief branch selection
    """
    # Convert backing color name to ID or use special marker for separate backing
    try:
        separate_backing = bool(separate_backing) if separate_backing is not None else False
    except Exception as e:
        logger.error("Error reading separate_backing parameter: %s, using default (False)", e)
        separate_backing = False

    if separate_backing:
        backing_color_id = -2  # Special marker for separate backing
        logger.info("Backing will be separated as individual object (white)")
    else:
        color_conf = ColorSystem.get(color_mode)
        backing_color_id = color_conf['map'].get(backing_color_name, 0)
        logger.info("Backing color: %s (ID=%s)", backing_color_name, backing_color_id)

    # Handle relief mode parameters
    if color_height_map is None:
        color_height_map = {}

    return convert_image_to_3d(
        image_path, lut_path, target_width_mm, spacer_thick,
        structure_mode, auto_bg, bg_tol, color_mode,
        add_loop, loop_width, loop_length, loop_hole, loop_pos,
        modeling_mode, quantize_colors,
        blur_kernel=0,
        smooth_sigma=10,
        color_replacements=color_replacements,
        replacement_regions=replacement_regions,
        backing_color_id=backing_color_id,
        separate_backing=separate_backing,
        enable_relief=enable_relief,
        color_height_map=color_height_map,
        height_mode=height_mode,
        heightmap_path=heightmap_path,
        heightmap_max_height=heightmap_max_height,
        enable_cleanup=enable_cleanup,
        enable_outline=enable_outline,
        outline_width=outline_width,
        free_color_set=free_color_set,
        hue_weight=hue_weight,
        progress=progress,
    )


# ========== Auto-detection Functions ==========

def detect_lut_color_mode(lut_path):
    """
    自动检测LUT文件的颜色模式

    Args:
        lut_path: LUT文件路径

    Returns:
        str: 颜色模式 ("BW (Black & White)", "Merged", "6-Color (Smart 1296)", "8-Color Max", etc.)
    """
    if not lut_path or not os.path.exists(lut_path):
        return None

    try:
        if lut_path.endswith('.npz'):
            data = np.load(lut_path)
            if 'rgb' in data:
                rgb = data['rgb']
                total_colors = int(rgb.reshape(-1, 3).shape[0])
                stacks = data['stacks'] if 'stacks' in data else None
                layer_count = int(stacks.shape[1]) if isinstance(stacks, np.ndarray) and stacks.ndim == 2 else None
                max_mat = int(np.max(stacks)) if isinstance(stacks, np.ndarray) and stacks.size > 0 else None
                if total_colors >= 2400 and total_colors < 2600 and layer_count == 6 and (max_mat is None or max_mat <= 4):
                    logger.info("Detected 5-Color Extended mode from .npz (%s colors)", total_colors)
                    return "5-Color Extended"
                if total_colors >= 2600 and total_colors <= 2800:
                    logger.info("Detected 8-Color mode from .npz (%s colors)", total_colors)
                    return "8-Color Max"
                if total_colors >= 1200 and total_colors < 1400:
                    logger.info("Detected 6-Color mode from .npz (%s colors)", total_colors)
                    return "6-Color (Smart 1296)"
                if total_colors >= 900 and total_colors < 1200:
                    logger.info("Detected 4-Color mode from .npz (%s colors)", total_colors)
                    return "4-Color"
                if total_colors >= 30 and total_colors <= 36:
                    logger.info("Detected 2-Color BW mode from .npz (%s colors)", total_colors)
                    return "BW (Black & White)"
            logger.info("Detected Merged LUT (.npz format)")
            return "Merged"

        # Standard .npy format
        lut_data = np.load(lut_path)

        # 确保是2D数组
        if lut_data.ndim == 1:
            if len(lut_data) % 3 == 0:
                lut_data = lut_data.reshape(-1, 3)
            else:
                logger.info("Invalid LUT format: cannot reshape to (N, 3)")
                return None

        if lut_data.ndim == 2:
            total_colors = lut_data.shape[0]
        else:
            total_colors = lut_data.shape[0] * lut_data.shape[1]

        logger.info("LUT shape: %s, total colors: %s", lut_data.shape, total_colors)

        # 2色模式：32色 (2^5 = 32), LUT is 6x6 grid = 36 entries
        if total_colors >= 30 and total_colors <= 36:
            logger.info("Detected 2-Color BW mode (32 colors)")
            return "BW (Black & White)"

        # 5-Color Extended模式：~2468色 (1024 base + 1444 extended)
        elif total_colors >= 2400 and total_colors < 2600:
            logger.info("Detected 5-Color Extended mode (%s colors)", total_colors)
            return "5-Color Extended"

        # 8色模式：2600-2800色
        elif total_colors >= 2600 and total_colors <= 2800:
            logger.info("Detected 8-Color mode (%s colors)", total_colors)
            return "8-Color Max"

        # 6色模式：1200-1400色
        elif total_colors >= 1200 and total_colors < 1400:
            logger.info("Detected 6-Color mode (%s colors)", total_colors)
            return "6-Color (Smart 1296)"

        # 4色模式：900-1200色
        elif total_colors >= 900 and total_colors < 1200:
            logger.info("Detected 4-Color mode (%s colors)", total_colors)
            return "4-Color"

        else:
            logger.info("Non-standard LUT size (%s colors), detected as Merged", total_colors)
            return "Merged"

    except Exception as e:
        logger.exception("Error detecting LUT mode: %s", e)
        return None


def detect_image_type(image_path):
    """
    Detect image type and return recommended modeling mode.
    自动检测图像类型并返回推荐的建模模式。

    Args:
        image_path (str): Image file path. (图像文件路径)

    Returns:
        gr.update: Gradio update object (no-op, always returns current mode).
    """
    import gradio as gr
    if not image_path:
        return gr.update()

    # Always return no-op update (only high-fidelity mode is supported)
    return gr.update()
