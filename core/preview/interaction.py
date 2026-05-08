"""
Lumina Studio - Preview Interaction Module

Provides functions for handling user interactions with the preview,
including click events, color selection, and loop placement.
"""

import numpy as np
import gradio as gr
from collections import deque
from typing import Optional, List, Dict, Tuple

from config import PrinterConfig
from core.color.formats import rgb_to_hex, hex_to_rgb
from core.preview.render import (
    FIXED_BED_WIDTH_MM, FIXED_BED_HEIGHT_MM,
    render_preview, generate_highlight_preview
)


def _compute_connected_region_mask_4n(quantized_image, mask_solid, x, y):
    """Compute 4-connected region mask for clicked pixel."""
    h, w = quantized_image.shape[:2]
    if not (0 <= x < w and 0 <= y < h) or not mask_solid[y, x]:
        return np.zeros((h, w), dtype=bool)

    target = quantized_image[y, x]
    out = np.zeros((h, w), dtype=bool)
    q = deque([(x, y)])
    out[y, x] = True

    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < w and 0 <= ny < h and not out[ny, nx]:
                if mask_solid[ny, nx] and np.array_equal(quantized_image[ny, nx], target):
                    out[ny, nx] = True
                    q.append((nx, ny))

    return out


def _build_selection_meta(q_rgb, m_rgb, scope="region"):
    """Build click selection metadata (quantized color + original matched color)."""
    return {
        "selected_quantized_hex": rgb_to_hex(q_rgb),
        "selected_matched_hex": rgb_to_hex(m_rgb),
        "selection_scope": scope,
    }


def _ensure_quantized_image_in_cache(cache):
    """Ensure quantized_image exists in preview cache, backfill if missing."""
    if cache.get("quantized_image") is not None:
        return cache

    dbg = cache.get("debug_data") or {}
    q = dbg.get("quantized_image")
    if q is None:
        q = cache["matched_rgb"].copy()

    cache["quantized_image"] = q
    return cache


def _resolve_click_selection_hexes(cache, default_hex):
    """Resolve display color and internal state color after click.

    Display color prefers original matched color, internal state color keeps quantized color,
    to be compatible with "display original image color, replace by quantized color on connected region" design.
    """
    cached_q_hex = (cache or {}).get('selected_quantized_hex')
    cached_m_hex = (cache or {}).get('selected_matched_hex')

    # Gradio update objects are dict-like; they must not propagate into hex state.
    fallback_hex = default_hex if isinstance(default_hex, str) else None
    q_hex = cached_q_hex if isinstance(cached_q_hex, str) else fallback_hex
    m_hex = cached_m_hex if isinstance(cached_m_hex, str) else q_hex
    return m_hex, q_hex


def on_preview_click(cache, loop_pos, evt: gr.SelectData):
    """Handle preview image click event."""
    if evt is None or cache is None:
        return loop_pos, False, "Invalid click - please generate preview first"

    click_x, click_y = evt.index

    target_w = cache['target_w']
    target_h = cache['target_h']
    target_width_mm = cache.get('target_width_mm')

    bed_w_mm, bed_h_mm = FIXED_BED_WIDTH_MM, FIXED_BED_HEIGHT_MM
    ppm = 1200 / max(bed_w_mm, bed_h_mm)
    margin = 0

    canvas_w = int(bed_w_mm * ppm)
    canvas_h = int(bed_h_mm * ppm)

    # Use target_width_mm from cache for accurate physical size
    # But in preview image, model already fills bed, so use same logic
    aspect_ratio = target_w / target_h if target_h > 0 and target_w > 0 else 1.0

    if aspect_ratio >= 1.0:
        # Wide image: width fills bed width
        model_w_mm = bed_w_mm
        model_h_mm = bed_w_mm / aspect_ratio
    else:
        # Tall image: height fills bed height
        model_h_mm = bed_h_mm
        model_w_mm = bed_h_mm * aspect_ratio

    new_w = max(1, int(model_w_mm * ppm))
    new_h = max(1, int(model_h_mm * ppm))

    offset_x = (canvas_w - new_w) // 2
    offset_y = (canvas_h - new_h) // 2

    # Gradio may scale the displayed image
    gradio_display_height = 600
    gradio_display_width = 900
    scale_by_height = gradio_display_height / canvas_h
    scale_by_width = gradio_display_width / canvas_w
    gradio_scale = min(1.0, scale_by_height, scale_by_width)

    canvas_click_x = click_x / gradio_scale
    canvas_click_y = click_y / gradio_scale

    # Convert from canvas coords to original image pixel coords
    # Each pixel in original image = (model_w_mm / target_w) mm
    mm_per_px = model_w_mm / target_w
    img_click_x = (canvas_click_x - offset_x) / (mm_per_px * ppm)
    img_click_y = (canvas_click_y - offset_y) / (mm_per_px * ppm)

    orig_x = max(0, min(target_w - 1, img_click_x))
    orig_y = max(0, min(target_h - 1, img_click_y))

    pos_info = f"Position: ({orig_x:.1f}, {orig_y:.1f}) px"
    return (orig_x, orig_y), True, pos_info


def on_preview_click_select_color(cache, evt: gr.SelectData):
    """
    Preview click event handler: pick color and highlight display
    1. Identify clicked position color
    2. Generate highlight preview for that color
    3. Return color info to UI
    """
    if cache is None:
        return None, "Not selected", None, "[ERROR] Please generate preview first"

    if evt is None or evt.index is None:
        return gr.update(), "Not selected", None, "[WARNING] Invalid click"

    display_click_x, display_click_y = evt.index

    target_w = cache.get('target_w')
    target_h = cache.get('target_h')
    target_width_mm = cache.get('target_width_mm')

    if target_w is None or target_h is None:
        return gr.update(), "Not selected", None, "[ERROR] Incomplete cache data"

    bed_w_mm, bed_h_mm = FIXED_BED_WIDTH_MM, FIXED_BED_HEIGHT_MM
    ppm = 1200 / max(bed_w_mm, bed_h_mm)
    margin = 0

    canvas_w = int(bed_w_mm * ppm)
    canvas_h = int(bed_h_mm * ppm)

    # Use target_width_mm from cache for accurate physical size
    # But in preview image, model already fills bed, so use same logic
    aspect_ratio = target_w / target_h if target_h > 0 and target_w > 0 else 1.0

    if aspect_ratio >= 1.0:
        # Wide image: width fills bed width
        model_w_mm = bed_w_mm
        model_h_mm = bed_w_mm / aspect_ratio
    else:
        # Tall image: height fills bed height
        model_h_mm = bed_h_mm
        model_w_mm = bed_h_mm * aspect_ratio

    new_w = max(1, int(model_w_mm * ppm))
    new_h = max(1, int(model_h_mm * ppm))

    offset_x = (canvas_w - new_w) // 2
    offset_y = (canvas_h - new_h) // 2

    # _scale_preview_image fits canvas into 1200x750 box
    gradio_scale = min(1.0, 1200 / canvas_w, 750 / canvas_h)

    canvas_click_x = display_click_x / gradio_scale
    canvas_click_y = display_click_y / gradio_scale

    # Convert canvas coords to original image pixel coords
    mm_per_px = model_w_mm / target_w
    img_px_x = (canvas_click_x - offset_x) / (mm_per_px * ppm)
    img_px_y = (canvas_click_y - offset_y) / (mm_per_px * ppm)

    orig_x = int(img_px_x)
    orig_y = int(img_px_y)

    matched_rgb = cache.get('original_matched_rgb', cache.get('matched_rgb'))
    quantized_image = cache.get('quantized_image')
    mask_solid = cache.get('mask_solid')

    if quantized_image is None:
        _ensure_quantized_image_in_cache(cache)
        quantized_image = cache.get('quantized_image')

    if matched_rgb is None or mask_solid is None or quantized_image is None:
        return None, "Not selected", None, "[ERROR] Invalid cache"

    h, w = matched_rgb.shape[:2]

    if not (0 <= orig_x < w and 0 <= orig_y < h):
        return gr.update(), "Not selected", None, f"[WARNING] Clicked invalid area ({orig_x}, {orig_y})"

    if not mask_solid[orig_y, orig_x]:
        return gr.update(), "Not selected", None, "[WARNING] Clicked background area"

    q_rgb = tuple(int(v) for v in quantized_image[orig_y, orig_x])
    m_rgb = tuple(int(v) for v in matched_rgb[orig_y, orig_x])

    region_mask = _compute_connected_region_mask_4n(quantized_image, mask_solid, orig_x, orig_y)
    cache['selected_region_mask'] = region_mask
    cache.update(_build_selection_meta(q_rgb, m_rgb, scope="region"))

    q_hex = cache['selected_quantized_hex']
    m_hex = cache['selected_matched_hex']

    print(f"[CLICK] Coords: ({orig_x}, {orig_y}), Quantized: {q_hex}, Matched: {m_hex}")

    display_img, status_msg = generate_highlight_preview(
        cache,
        highlight_color=q_hex,
        add_loop=False
    )

    display_text = f"Quantized {q_hex} | Original {m_hex}"
    if display_img is None:
        return gr.update(), display_text, q_hex, status_msg

    return display_img, display_text, q_hex, status_msg


def update_preview_with_loop(cache, loop_pos, add_loop,
                            loop_width, loop_length, loop_hole, loop_angle):
    """Update preview image with keychain loop."""
    if cache is None:
        return None

    preview_rgba = cache['preview_rgba'].copy()
    color_conf = cache['color_conf']
    target_width_mm = cache.get('target_width_mm')
    is_dark = cache.get('is_dark', True)

    display = render_preview(
        preview_rgba,
        loop_pos if add_loop else None,
        loop_width, loop_length, loop_hole, loop_angle,
        add_loop, color_conf,
        target_width_mm=target_width_mm, is_dark=is_dark
    )
    return display


def on_remove_loop():
    """Remove keychain loop."""
    return None, False, 0, "Loop removed"


def update_preview_with_replacements(cache, replacement_regions=None,
                                     loop_pos=None, add_loop=False,
                                     loop_width=4, loop_length=8,
                                     loop_hole=2.5, loop_angle=0,
                                     lang: str = "zh",
                                     merge_map: dict = None):
    """
    Update preview image with color replacements and optional color merging applied.

    This function applies color replacements to the cached preview data
    without re-processing the entire image. It's designed for fast
    interactive updates when users change color mappings.

    Args:
        cache: Preview cache from generate_preview_cached
        replacement_regions: List of replacement region dicts with 'mask' and 'replacement' keys
        loop_pos: Optional loop position tuple (x, y)
        add_loop: Whether to show keychain loop
        loop_width: Loop width in mm
        loop_length: Loop length in mm
        loop_hole: Loop hole diameter in mm
        loop_angle: Loop rotation angle in degrees
        lang: Language code
        merge_map: Optional dict mapping source hex to target hex colors for merging
                  (applied before color_replacements)

    Returns:
        tuple: (display_image, updated_cache, palette_html)
    """
    if cache is None:
        return None, None, ""

    # Get original matched_rgb (use stored original if available)
    original_rgb = cache.get('original_matched_rgb', cache['matched_rgb'])
    mask_solid = cache['mask_solid']
    color_conf = cache['color_conf']
    backing_color_id = cache.get('backing_color_id', 0)  # Handle old cache versions
    target_h, target_w = original_rgb.shape[:2]

    # Start with original RGB
    matched_rgb = original_rgb.copy()

    # Apply merge map first (if provided)
    if merge_map:
        from core.color.merger import ColorMerger
        from core.image.processor import LuminaImageProcessor

        merger = ColorMerger(LuminaImageProcessor._rgb_to_lab)
        matched_rgb = merger.apply_color_merging(matched_rgb, merge_map)

    # Apply region replacements in-order (later items override earlier items)
    for item in (replacement_regions or []):
        region_mask = item.get('mask')
        replacement_hex = item.get('replacement')
        if region_mask is None or not replacement_hex:
            continue
        replacement_rgb = hex_to_rgb(replacement_hex)
        effective_mask = region_mask & mask_solid
        if np.any(effective_mask):
            matched_rgb[effective_mask] = np.array(replacement_rgb, dtype=np.uint8)

    # Build new preview RGBA
    preview_rgba = np.zeros((target_h, target_w, 4), dtype=np.uint8)
    preview_rgba[mask_solid, :3] = matched_rgb[mask_solid]
    preview_rgba[mask_solid, 3] = 255

    # Update cache with new data
    updated_cache = cache.copy()
    updated_cache['matched_rgb'] = matched_rgb
    updated_cache['preview_rgba'] = preview_rgba.copy()
    updated_cache['backing_color_id'] = backing_color_id  # Preserve backing color ID

    # Store original if not already stored
    if 'original_matched_rgb' not in updated_cache:
        updated_cache['original_matched_rgb'] = original_rgb

    # Re-extract palette with new colors
    from core.converter import extract_color_palette
    color_palette = extract_color_palette(updated_cache)
    updated_cache['color_palette'] = color_palette

    # Render display with loop if enabled
    display = render_preview(
        preview_rgba,
        loop_pos if add_loop else None,
        loop_width, loop_length, loop_hole, loop_angle,
        add_loop, color_conf,
        target_width_mm=cache.get('target_width_mm'),
        is_dark=cache.get('is_dark', True)
    )

    # Build auto pairs (quantized -> matched) for right table display
    auto_pairs = []
    q_img = updated_cache.get('quantized_image')
    if q_img is not None:
        h, w = matched_rgb.shape[:2]
        for y in range(h):
            for x in range(w):
                if not mask_solid[y, x]:
                    continue
                qh = rgb_to_hex(q_img[y, x])
                mh = rgb_to_hex(matched_rgb[y, x])
                auto_pairs.append({"quantized_hex": qh, "matched_hex": mh})

    # Generate palette HTML for display
    from ui.widgets.palette import generate_palette_html
    palette_html = generate_palette_html(
        color_palette,
        replacements={},
        lang=lang,
        replacement_regions=replacement_regions or [],
        auto_pairs=auto_pairs,
    )

    return display, updated_cache, palette_html
