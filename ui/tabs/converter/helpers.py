# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Tab Helpers
Pure logic helper functions extracted from converter_tab.py.
No Gradio context dependency.
"""

import os
import shutil
import time
import zipfile

import gradio as gr

from config import ModelingMode
from utils import LUTManager
from core.naming import generate_batch_filename
from core.converter import (
    generate_preview_cached, generate_realtime_glb,
    generate_lut_grid_html, generate_lut_card_grid_html,
    detect_lut_color_mode,
)

from ...image_helpers import _preview_update


# Lazy import to avoid circular dependency with layout.
def _get_supported_image_file_types():
    from ...layout import SUPPORTED_IMAGE_FILE_TYPES
    return SUPPORTED_IMAGE_FILE_TYPES


def process_batch_generation(batch_files, is_batch, single_image, lut_path, target_width_mm,
                             spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
                             add_loop, loop_width, loop_length, loop_hole, loop_pos,
                             modeling_mode, quantize_colors, replacement_regions=None,
                             separate_backing=False, enable_relief=False, color_height_map=None,
                             height_mode: str = "color",
                             heightmap_path=None, heightmap_max_height=None,
                             enable_cleanup=True,
                             enable_outline=False, outline_width=2.0,
                             enable_cloisonne=False, wire_width_mm=0.4,
                             wire_height_mm=0.4,
                             free_color_set=None,
                             enable_coating=False, coating_height_mm=0.08,
                             hue_weight: float = 0.0,
                             progress=gr.Progress()):
    """Dispatch to single-image or batch generation; batch writes a ZIP of 3MFs.

    Args:
        separate_backing: Boolean flag to separate backing as individual object (default: False)
        enable_relief: Boolean flag to enable 2.5D relief mode (default: False)
        color_height_map: Dict mapping hex colors to heights in mm (default: None)
        height_mode: "color" or "heightmap", determines relief branch selection (default: "color")
        heightmap_path: Optional path to heightmap image file (default: None)
        heightmap_max_height: Optional max height for heightmap mode in mm (default: None)

    Returns:
        tuple: (file_or_zip_path, model3d_value, preview_image, status_text, color_recipe_path).
    """
    from core.converter import generate_final_model

    # Handle None modeling_mode (use default)
    if modeling_mode is None or modeling_mode == "none":
        modeling_mode = ModelingMode.HIGH_FIDELITY
    else:
        modeling_mode = ModelingMode(modeling_mode)
    # Use default white color for backing (fixed, not user-selectable)
    backing_color_name = "White"

    # Prepare relief mode parameters
    if color_height_map is None:
        color_height_map = {}

    args = (lut_path, target_width_mm, spacer_thick, structure_mode, auto_bg, bg_tol,
            color_mode, add_loop, loop_width, loop_length, loop_hole, loop_pos,
            modeling_mode, quantize_colors, None, replacement_regions, backing_color_name,
            separate_backing, enable_relief, color_height_map,
            height_mode,
            heightmap_path, heightmap_max_height,
            enable_cleanup,
            enable_outline, outline_width,
            enable_cloisonne, wire_width_mm, wire_height_mm,
            free_color_set,
            enable_coating, coating_height_mm)

    if not is_batch:
        out_path, glb_path, preview_img, status, color_recipe_path = generate_final_model(
            image_path=single_image,
            lut_path=lut_path,
            target_width_mm=target_width_mm,
            spacer_thick=spacer_thick,
            structure_mode=structure_mode,
            auto_bg=auto_bg,
            bg_tol=bg_tol,
            progress=progress,
            color_mode=color_mode,
            add_loop=add_loop,
            loop_width=loop_width,
            loop_length=loop_length,
            loop_hole=loop_hole,
            loop_pos=loop_pos,
            modeling_mode=modeling_mode,
            quantize_colors=quantize_colors,
            replacement_regions=replacement_regions,
            backing_color_name=backing_color_name,
            separate_backing=separate_backing,
            enable_relief=enable_relief,
            color_height_map=color_height_map,
            height_mode=height_mode,
            heightmap_path=heightmap_path,
            heightmap_max_height=heightmap_max_height,
            enable_cleanup=enable_cleanup,
            enable_outline=enable_outline,
            outline_width=outline_width,
            enable_cloisonne=enable_cloisonne,
            wire_width_mm=wire_width_mm,
            wire_height_mm=wire_height_mm,
            free_color_set=free_color_set,
            enable_coating=enable_coating,
            coating_height_mm=coating_height_mm,
            hue_weight=float(hue_weight) if hue_weight else 0.0,
        )
        return out_path, glb_path, _preview_update(preview_img), status, color_recipe_path

    if not batch_files:
        return None, None, None, "[ERROR] 请先上传图片 / Please upload images first", None

    generated_files = []
    total_files = len(batch_files)
    logs = []

    output_dir = os.path.join("outputs", f"batch_{int(time.time())}")
    os.makedirs(output_dir, exist_ok=True)

    logs.append(f"🚀 开始批量处理 {total_files} 张图片...")

    for i, file_obj in enumerate(batch_files):
        path = getattr(file_obj, 'name', file_obj) if file_obj else None
        if not path or not os.path.isfile(path):
            continue
        filename = os.path.basename(path)
        progress(i / total_files, desc=f"Processing {filename}...")
        logs.append(f"[{i+1}/{total_files}] 正在生成: {filename}")

        try:
            result_3mf, _, _, _, _ = generate_final_model(path, *args, hue_weight=float(hue_weight) if hue_weight else 0.0)

            if result_3mf and os.path.exists(result_3mf):
                new_name = os.path.splitext(filename)[0] + ".3mf"
                dest_path = os.path.join(output_dir, new_name)
                shutil.copy2(result_3mf, dest_path)
                generated_files.append(dest_path)
        except Exception as e:
            logs.append(f"❌ 失败 {filename}: {str(e)}")
            print(f"Batch error on {filename}: {e}")

    if generated_files:
        zip_path = os.path.join("outputs", generate_batch_filename())
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for f in generated_files:
                zipf.write(f, os.path.basename(f))
        logs.append(f"✅ Batch done: {len(generated_files)} model(s).")
        return zip_path, None, _preview_update(None), "\n".join(logs), None
    return None, None, _preview_update(None), "[ERROR] Batch failed: no valid models.\n" + "\n".join(logs), None


def _update_lut_grid(lut_path, palette_mode="swatch"):
    """Wrapper that picks swatch or card grid based on palette_mode setting.

    For merged LUTs (.npz), always uses swatch mode since card mode
    requires stack data in a format incompatible with merged LUTs.
    """
    # Force swatch mode for merged LUTs
    if lut_path and lut_path.endswith('.npz'):
        palette_mode = "swatch"
    if palette_mode == "card":
        return generate_lut_card_grid_html(lut_path)
    return generate_lut_grid_html(lut_path)


def _detect_and_enforce_structure(lut_path):
    """Detect color mode from LUT, and enforce structure constraints for 5-Color Extended.

    Returns (color_mode_update, structure_update, relief_update) for three component outputs.
    """
    mode = detect_lut_color_mode(lut_path)
    if mode and "5-Color Extended" in mode:
        gr.Info("5-Color Extended 模式：自动切换为单面模式，2.5D 浮雕不可用")
        return mode, gr.update(
            value='Single-sided (Relief)',
            interactive=False,
        ), gr.update(value=False, interactive=False)
    if mode:
        return mode, gr.update(interactive=True), gr.update(interactive=True)
    return gr.update(), gr.update(interactive=True), gr.update(interactive=True)


def generate_preview_cached_with_fit(image_path, lut_path, target_width_mm,
                                     auto_bg, bg_tol, color_mode,
                                     modeling_mode, quantize_colors, enable_cleanup,
                                     is_dark_theme=False, processed_path=None,
                                     hue_weight=0.0, structure_mode="single"):
    """Preview generation with 3D GLB (promoted from closure to module function)."""
    # When SVG was uploaded, image_conv_image_label holds a PNG thumbnail while
    # preprocess_processed_path holds the original SVG. Use SVG for the converter.
    if processed_path and isinstance(processed_path, str) and processed_path.lower().endswith('.svg'):
        image_path = processed_path
    display, cache, status = generate_preview_cached(
        image_path, lut_path, target_width_mm,
        auto_bg, bg_tol, color_mode,
        modeling_mode, quantize_colors,
        enable_cleanup=enable_cleanup,
        is_dark=is_dark_theme,
        hue_weight=float(hue_weight) if hue_weight else 0.0,
        structure_mode=structure_mode
    )
    # Generate realtime 3D preview GLB
    glb_path = generate_realtime_glb(cache) if cache is not None else None
    return _preview_update(display), cache, status, glb_path
