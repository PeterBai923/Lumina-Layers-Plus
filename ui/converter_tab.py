# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Tab
Extracted from layout_new.py for modularity.
"""

import json
import os
import re
import shutil
import time
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import gradio as gr
import numpy as np
from PIL import Image as PILImage

from core.i18n import I18n
from config import ColorSystem, ModelingMode, BedManager
from utils import Stats, LUTManager
from core.naming import generate_batch_filename
from core.converter import (
    generate_preview_cached, generate_realtime_glb, generate_empty_bed_glb,
    render_preview, update_preview_with_loop, on_remove_loop,
    generate_final_model, on_preview_click_select_color,
    generate_lut_grid_html, generate_lut_card_grid_html,
    detect_lut_color_mode, detect_image_type, generate_auto_height_map,
    _build_dual_recommendations, _resolve_click_selection_hexes,
    get_lut_color_choices,
)
from core.heightmap_loader import HeightmapLoader

from .styles import CUSTOM_CSS
from .callbacks import (
    on_lut_select, on_lut_upload_save,
    on_apply_color_replacement, on_clear_color_replacements,
    on_undo_color_replacement, on_preview_generated_update_palette,
    on_delete_selected_user_replacement, on_highlight_color_change, on_clear_highlight,
    on_merge_preview, on_merge_apply, on_merge_revert,
)
from .settings import (
    load_last_lut_setting, save_last_lut_setting,
    _load_user_settings, _save_user_setting,
    save_color_mode, save_modeling_mode, resolve_height_mode, CONFIG_FILE,
)
from .slicer_integration import (
    detect_installed_slicers, open_in_slicer,
    _INSTALLED_SLICERS, _get_slicer_choices,
    _get_default_slicer, _slicer_css_class,
)
from .assets import (
    DEBOUNCE_JS, HEADER_CSS, LUT_GRID_CSS,
    PREVIEW_ZOOM_CSS, LUT_GRID_JS, PREVIEW_ZOOM_JS,
    FIVECOLOR_CLICK_JS,
)
from .image_helpers import (
    _get_image_size, calc_height_from_width, calc_width_from_height,
    init_dims, _scale_preview_image, _preview_update,
)
from .i18n_helpers import (
    _get_header_html, _get_stats_html, _get_footer_html,
    _get_all_component_updates, _get_component_list,
)
from .helpers import _format_bytes


# Lazy import to avoid circular dependency with layout_new.
# SUPPORTED_IMAGE_FILE_TYPES is only needed inside create_converter_tab_content.
def _get_supported_image_file_types():
    from .layout_new import SUPPORTED_IMAGE_FILE_TYPES
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
        tuple: (file_or_zip_path, model3d_value, preview_image, status_text).
    """
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
        return None, None, None, "[ERROR] 请先上传图片 / Please upload images first"

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


# ========== Advanced Tab Callbacks ==========


def _update_lut_grid(lut_path, lang, palette_mode="swatch"):
    """Wrapper that picks swatch or card grid based on palette_mode setting.
    
    For merged LUTs (.npz), always uses swatch mode since card mode
    requires stack data in a format incompatible with merged LUTs.
    """
    # Force swatch mode for merged LUTs
    if lut_path and lut_path.endswith('.npz'):
        palette_mode = "swatch"
    if palette_mode == "card":
        return generate_lut_card_grid_html(lut_path, lang)
    return generate_lut_grid_html(lut_path, lang)


def _detect_and_enforce_structure(lut_path):
    """Detect color mode from LUT, and enforce structure constraints for 5-Color Extended.

    Returns (color_mode_update, structure_update, relief_update) for three component outputs.
    """
    mode = detect_lut_color_mode(lut_path)
    if mode and "5-Color Extended" in mode:
        gr.Info("5-Color Extended 模式：自动切换为单面模式，2.5D 浮雕不可用")
        return mode, gr.update(
            value=I18n.get('conv_structure_single', 'en'),
            interactive=False,
        ), gr.update(value=False, interactive=False)
    if mode:
        return mode, gr.update(interactive=True), gr.update(interactive=True)
    return gr.update(), gr.update(interactive=True), gr.update(interactive=True)


# ---------- Tab builders ----------

def create_converter_tab_content(lang: str, lang_state=None, theme_state=None) -> dict:
    """Build converter tab UI and events. Returns component dict for i18n.

    Args:
        lang: Initial language code ('zh' or 'en').
        lang_state: Gradio State for language.
        theme_state: Gradio State for theme (False=light, True=dark).

    Returns:
        dict: Mapping from component key to Gradio component (and state refs).
    """
    components = {}
    if lang_state is None:
        lang_state = gr.State(value=lang)
    conv_loop_pos = gr.State(None)
    conv_preview_cache = gr.State(None)

    with gr.Row():
        with gr.Column(scale=1, min_width=320, elem_classes=["left-sidebar"]):
            components['md_conv_input_section'] = gr.Markdown(I18n.get('conv_input_section', lang))

            saved_lut = load_last_lut_setting()
            current_choices = LUTManager.get_lut_choices()
            default_lut_value = saved_lut if saved_lut in current_choices else None

            # Load saved preferences
            _user_prefs = _load_user_settings()
            saved_color_mode = _user_prefs.get("last_color_mode", "4-Color")
            saved_modeling_mode_str = _user_prefs.get("last_modeling_mode", ModelingMode.HIGH_FIDELITY.value)
            try:
                saved_modeling_mode = ModelingMode(saved_modeling_mode_str)
            except (ValueError, KeyError):
                saved_modeling_mode = ModelingMode.HIGH_FIDELITY

            with gr.Row():
                components['dropdown_conv_lut_dropdown'] = gr.Dropdown(
                    choices=current_choices,
                    label="校准数据 (.npy) / Calibration Data",
                    value=default_lut_value,
                    interactive=True,
                    scale=2
                )
                conv_lut_upload = gr.File(
                    label="",
                    show_label=False,
                    file_types=['.npy'],
                    height=84,
                    min_width=100,
                    scale=1,
                    elem_classes=["tall-upload"]
                )
            
            components['md_conv_lut_status'] = gr.Markdown(
                value=I18n.get('conv_lut_status_default', lang),
                visible=True,
                elem_classes=["lut-status"]
            )
            conv_lut_path = gr.State(None)
            conv_palette_mode = gr.State(value=_load_user_settings().get("palette_mode", "swatch"))
            components['state_conv_palette_mode'] = conv_palette_mode

            with gr.Row():
                components['checkbox_conv_batch_mode'] = gr.Checkbox(
                    label=I18n.get('conv_batch_mode', lang),
                    value=False,
                    info=I18n.get('conv_batch_mode_info', lang)
                )
            
            # ========== Image Crop Extension (Non-invasive) ==========
            # Hidden state for preprocessing
            preprocess_img_width = gr.State(0)
            preprocess_img_height = gr.State(0)
            preprocess_processed_path = gr.State(None)
            
            # Crop data states (used by JavaScript via hidden inputs)
            crop_data_state = gr.State({"x": 0, "y": 0, "w": 100, "h": 100})
            
            # Hidden textbox for JavaScript to pass crop data to Python (use CSS to hide)
            crop_data_json = gr.Textbox(
                value='{"x":0,"y":0,"w":100,"h":100,"autoColor":true}',
                elem_id="crop-data-json",
                visible=True,
                elem_classes=["hidden-crop-component"]
            )
            
            # Hidden buttons for JavaScript to trigger Python callbacks (use CSS to hide)
            use_original_btn = gr.Button("use_original", elem_id="use-original-hidden-btn", elem_classes=["hidden-crop-component"])
            confirm_crop_btn = gr.Button("confirm_crop", elem_id="confirm-crop-hidden-btn", elem_classes=["hidden-crop-component"])
            
            # Cropper.js Modal HTML (JS is loaded via head parameter in main.py)
            from ui.crop_extension import get_crop_modal_html
            cropper_modal_html = gr.HTML(
                get_crop_modal_html(lang),
                elem_classes=["crop-modal-container"]
            )
            components['html_crop_modal'] = cropper_modal_html
            
            # Hidden HTML element to store dimensions for JavaScript
            preprocess_dimensions_html = gr.HTML(
                value='<div id="preprocess-dimensions-data" data-width="0" data-height="0" style="display:none;"></div>',
                visible=True,
                elem_classes=["hidden-crop-component"]
            )
            # ========== END Image Crop Extension ==========
            
            components['image_conv_image_label'] = gr.Image(
                label=I18n.get('conv_image_label', lang),
                type="filepath",
                image_mode=None,  # Auto-detect mode to support both JPEG and PNG
                height=400,
                visible=True,
                elem_id="conv-image-input",
            )
            components['file_conv_batch_input'] = gr.File(
                label=I18n.get('conv_batch_input', lang),
                file_count="multiple",
                file_types=_get_supported_image_file_types(),
                visible=False
            )
            components['md_conv_params_section'] = gr.Markdown(I18n.get('conv_params_section', lang))

            with gr.Row(elem_classes=["compact-row"]):
                components['slider_conv_width'] = gr.Slider(
                    minimum=10, maximum=400, value=60, step=1,
                    label=I18n.get('conv_width', lang),
                    interactive=True
                )
                components['slider_conv_height'] = gr.Slider(
                    minimum=10, maximum=400, value=60, step=1,
                    label=I18n.get('conv_height', lang),
                    interactive=True
                )
                components['slider_conv_thickness'] = gr.Slider(
                    0.2, 3.5, 1.2, step=0.08,
                    label=I18n.get('conv_thickness', lang)
                )
            
            
            # Bed size selector removed from sidebar — now overlaid on preview
            
            # ========== 2.5D Relief Mode Controls ==========
            components['checkbox_conv_relief_mode'] = gr.Checkbox(
                label="开启 2.5D 浮雕模式 | Enable Relief Mode",
                value=False,
                info="为不同颜色设置独立的Z轴高度，保留顶部5层光学叠色（强制单面，观赏面朝上）"
            )
            
            # Relief height slider (only visible when relief mode is enabled and a color is selected)
            components['slider_conv_relief_height'] = gr.Slider(
                minimum=0.08,
                maximum=20.0,
                value=1.2,
                step=0.1,
                label="当前选中颜色的独立高度 | Selected Color Z-Height (mm)",
                visible=False,
                info="调整当前选中颜色的总高度（包含光学层）"
            )
            
            # Max relief height slider - extracted outside Accordion so it remains visible
            # when heightmap mode hides the Accordion (shared by both auto-height and heightmap modes)
            components['slider_conv_auto_height_max'] = gr.Slider(
                minimum=0.08,
                maximum=15.0,
                value=2.4,
                step=0.08,
                label="最大浮雕高度 | Max Relief Height (mm)",
                info="所有颜色的最大高度（相对于底板）",
                visible=False
            )
            
            # Auto Height Generator (only visible when relief mode is enabled)
            with gr.Accordion(label="⚡ 高度生成器 | Height Generator", open=True, visible=False) as conv_auto_height_accordion:
                components['radio_conv_auto_height_mode'] = gr.Radio(
                    choices=[
                        ("深色凸起 | Darker Higher", "深色凸起"),
                        ("浅色凸起 | Lighter Higher", "浅色凸起"),
                        ("根据高度图 | Use Heightmap", "根据高度图")
                    ],
                    value="深色凸起",
                    label="排列规则 | Sorting Rule",
                    info="选择高度分配方式：按颜色明度或使用自定义高度图"
                )
                
                components['btn_conv_auto_height_apply'] = gr.Button(
                    "✨ 一键生成高度 | Apply Auto Heights",
                    variant="primary"
                )
                
                # ========== Heightmap Upload Components (inside accordion) ==========
                with gr.Row(visible=False) as conv_heightmap_row:
                    components['image_conv_heightmap'] = gr.Image(
                        type="filepath",
                        label="上传高度图 | Upload Heightmap (PNG/JPG/BMP/HEIC)",
                        visible=True,
                        height=200,
                        sources=["upload"],
                        interactive=True,
                    )
                    components['image_conv_heightmap_preview'] = gr.Image(
                        label="高度图预览 | Heightmap Preview",
                        visible=False,
                        interactive=False,
                        height=200
                    )
                components['row_conv_heightmap'] = conv_heightmap_row
                # ========== END Heightmap Upload Components ==========
            
            components['accordion_conv_auto_height'] = conv_auto_height_accordion
            
            # State to store per-color height mapping: {hex_color: height_mm}
            conv_color_height_map = gr.State({})
            
            # State to track currently selected color for height adjustment
            conv_relief_selected_color = gr.State(None)
            # ========== END 2.5D Relief Mode Controls ==========
            
            conv_target_height_mm = components['slider_conv_height']

            with gr.Row(elem_classes=["compact-row"]):
                components['radio_conv_color_mode'] = gr.Radio(
                    choices=[
                        ("BW (Black & White)", "BW (Black & White)"),
                        ("4-Color (1024 colors)", "4-Color"),
                        ("5-Color Extended (2468)", "5-Color Extended"),
                        ("6-Color (Smart 1296)", "6-Color (Smart 1296)"),
                        ("8-Color Max", "8-Color Max"),
                        ("🔀 Merged", "Merged"),
                    ],
                    value=saved_color_mode,
                    label=I18n.get('conv_color_mode', lang),
                    interactive=False,
                    visible=False,
                )
                
                components['radio_conv_structure'] = gr.Radio(
                    choices=[
                        (I18n.get('conv_structure_double', lang), I18n.get('conv_structure_double', 'en')),
                        (I18n.get('conv_structure_single', lang), I18n.get('conv_structure_single', 'en'))
                    ],
                    value=I18n.get('conv_structure_double', 'en'),
                    label=I18n.get('conv_structure', lang)
                )

            with gr.Row(elem_classes=["compact-row"]):
                components['radio_conv_modeling_mode'] = gr.Radio(
                    choices=[
                        (I18n.get('conv_modeling_mode_hifi', lang), ModelingMode.HIGH_FIDELITY),
                        (I18n.get('conv_modeling_mode_pixel', lang), ModelingMode.PIXEL),
                        (I18n.get('conv_modeling_mode_vector', lang), ModelingMode.VECTOR)
                    ],
                    value=saved_modeling_mode,
                    label=I18n.get('conv_modeling_mode', lang),
                    info=I18n.get('conv_modeling_mode_info', lang),
                    elem_classes=["vertical-radio"],
                    scale=2
                )
                
            with gr.Accordion(label=I18n.get('conv_advanced', lang), open=False) as conv_advanced_acc:
                components['accordion_conv_advanced'] = conv_advanced_acc
                with gr.Row():
                    components['slider_conv_quantize_colors'] = gr.Slider(
                        minimum=8, maximum=256, step=8, value=48,
                        label=I18n.get('conv_quantize_colors', lang),
                        info=I18n.get('conv_quantize_info', lang)
                    )
                with gr.Row():
                    components['btn_conv_auto_color'] = gr.Button(
                        I18n.get('conv_auto_color_btn', lang),
                        variant="secondary",
                        size="sm"
                    )
                with gr.Row():
                    components['slider_conv_tolerance'] = gr.Slider(
                        0, 150, 40,
                        label=I18n.get('conv_tolerance', lang),
                        info=I18n.get('conv_tolerance_info', lang)
                    )
                with gr.Row():
                    components['checkbox_conv_auto_bg'] = gr.Checkbox(
                        label=I18n.get('conv_auto_bg', lang),
                        value=False,
                        info=I18n.get('conv_auto_bg_info', lang)
                    )
                with gr.Row():
                    components['checkbox_conv_cleanup'] = gr.Checkbox(
                        label="孤立像素清理 | Isolated Pixel Cleanup",
                        value=True,
                        info="清理 LUT 匹配后的孤立像素，提升打印成功率"
                    )
                with gr.Row():
                    components['checkbox_conv_separate_backing'] = gr.Checkbox(
                        label="底板单独一个对象 | Separate Backing",
                        value=False,
                        info="勾选后，底板将作为独立对象导出到3MF文件"
                    )
                with gr.Row():
                    components['slider_conv_hue_weight'] = gr.Slider(
                        minimum=0.0, maximum=1.0, step=0.1, value=0.0,
                        label="🎨 色相保护 | Hue Protection",
                        info="0=纯色差匹配(默认), 0.3=明显保护, 0.5=强保护(推荐), 1.0=最强。避免浅色匹配到错误色系"
                    )
            
            # Crop interface toggle - outside Accordion for immediate DOM availability
            with gr.Row():
                # Load saved crop modal preference
                saved_enable_crop = _load_user_settings().get("enable_crop_modal", True)
                print(f"[CROP_SETTING] Loading crop modal preference: {saved_enable_crop}")
                components['checkbox_conv_enable_crop'] = gr.Checkbox(
                    label="🖼️ 启用裁剪界面 | Enable Crop Interface",
                    value=saved_enable_crop,
                    info="上传图片时显示裁剪界面 | Show crop interface when uploading images",
                    elem_id="conv-enable-crop-checkbox"
                )
            
            gr.Markdown("---")
            
        with gr.Column(scale=4, elem_classes=["workspace-area"]):
            with gr.Row():
                with gr.Column(scale=3):
                    components['md_conv_preview_section'] = gr.Markdown(
                        I18n.get('conv_preview_section', lang)
                    )

                    # Bed size dropdown overlaid on preview top-right
                    with gr.Row(elem_id="conv-bed-size-overlay"):
                        components['radio_conv_bed_size'] = gr.Dropdown(
                            choices=[b[0] for b in BedManager.BEDS],
                            value=BedManager.DEFAULT_BED,
                            label=None,
                            show_label=False,
                            container=False,
                            min_width=140,
                            elem_id="conv-bed-size-dropdown"
                        )

                    conv_preview = gr.Image(
                        label="",
                        type="numpy",
                        value=render_preview(None, None, 0, 0, 0, 0, False, None, is_dark=False),
                        height=750,
                        interactive=False,
                        show_label=False,
                        elem_id="conv-preview"
                    )
                    
                    # ========== Color Palette & Replacement ==========
                    with gr.Accordion(I18n.get('conv_palette', lang), open=False) as conv_palette_acc:
                        components['accordion_conv_palette'] = conv_palette_acc
                        # 状态变量
                        conv_selected_color = gr.State(None)  # 原图中被点击的颜色
                        conv_replacement_regions = gr.State([])  # 区域替换列表
                        conv_replacement_history = gr.State([])
                        conv_replacement_color_state = gr.State(None)  # 最终确定的 LUT 颜色
                        conv_selected_user_row_id = gr.State(None)
                        conv_selected_auto_row_id = gr.State(None)
                        conv_free_color_set = gr.State(set())  # 自由色集合

                        # 隐藏的交互组件
                        conv_color_selected_hidden = gr.Textbox(
                            value="",
                            visible=True,
                            interactive=True,
                            elem_id="conv-color-selected-hidden",
                            elem_classes=["hidden-textbox-trigger"],
                            label="",
                            show_label=False,
                            container=False
                        )
                        conv_highlight_color_hidden = gr.Textbox(
                            value="",
                            visible=True,
                            interactive=True,
                            elem_id="conv-highlight-color-hidden",
                            elem_classes=["hidden-textbox-trigger"],
                            label="",
                            show_label=False,
                            container=False
                        )
                        conv_highlight_trigger_btn = gr.Button(
                            "trigger_highlight",
                            visible=True,
                            elem_id="conv-highlight-trigger-btn",
                            elem_classes=["hidden-textbox-trigger"]
                        )
                        conv_color_trigger_btn = gr.Button(
                            "trigger_color",
                            visible=True,
                            elem_id="conv-color-trigger-btn",
                            elem_classes=["hidden-textbox-trigger"]
                        )

                        # LUT 选色隐藏组件（与 JS 绑定）
                        conv_lut_color_selected_hidden = gr.Textbox(
                            value="",
                            visible=True,
                            interactive=True,
                            elem_id="conv-lut-color-selected-hidden",
                            elem_classes=["hidden-textbox-trigger"],
                            label="",
                            show_label=False,
                            container=False
                        )
                        conv_lut_color_trigger_btn = gr.Button(
                            "trigger_lut_color",
                            elem_id="conv-lut-color-trigger-btn",
                            elem_classes=["hidden-textbox-trigger"],
                            visible=True
                        )
                        conv_palette_row_select_hidden = gr.Textbox(
                            value="",
                            visible=True,
                            interactive=True,
                            elem_id="conv-palette-row-select-hidden",
                            elem_classes=["hidden-textbox-trigger"],
                            label="",
                            show_label=False,
                            container=False
                        )
                        conv_palette_row_select_trigger_btn = gr.Button(
                            "trigger_palette_row_select",
                            visible=True,
                            elem_id="conv-palette-row-select-trigger-btn",
                            elem_classes=["hidden-textbox-trigger"]
                        )
                        conv_palette_delete_trigger_btn = gr.Button(
                            "trigger_palette_delete",
                            visible=True,
                            elem_id="conv-palette-delete-trigger-btn",
                            elem_classes=["hidden-textbox-trigger"]
                        )

                        # --- 新 UI 布局 ---
                        from ui.palette_extension import build_selected_dual_color_html

                        with gr.Row():
                            # 左侧：当前选中的原图颜色
                            with gr.Column(scale=1):
                                components['md_conv_palette_step1'] = gr.Markdown(
                                    I18n.get('conv_palette_step1', lang)
                                )
                                conv_selected_display = gr.HTML(
                                    value=build_selected_dual_color_html("#000000", "#000000", lang=lang),
                                    label=I18n.get('conv_palette_selected_label', lang),
                                    show_label=True
                                )
                                components['color_conv_palette_selected_label'] = conv_selected_display

                            # 右侧：LUT 真实色盘
                            with gr.Column(scale=2):
                                components['md_conv_palette_step2'] = gr.Markdown(
                                    I18n.get('conv_palette_step2', lang)
                                )

                                # 以色找色 ColorPicker
                                with gr.Row():
                                    conv_color_picker_search = gr.ColorPicker(
                                        label=I18n.get('lut_grid_picker_label', lang),
                                        value="#ff0000",
                                        interactive=True,
                                        info=I18n.get('lut_grid_picker_hint', lang)
                                    )
                                    conv_color_picker_btn = gr.Button(
                                        I18n.get('lut_grid_picker_btn', lang),
                                        variant="secondary",
                                        size="sm"
                                    )
                                components['color_conv_picker_search'] = conv_color_picker_search
                                components['btn_conv_picker_search'] = conv_color_picker_btn


                                conv_dual_recommend_html = gr.HTML(
                                    value="",
                                    label="",
                                    show_label=False
                                )

                                # LUT 网格 HTML
                                conv_lut_grid_view = gr.HTML(
                                    value=f"<div style='color:#888; padding:10px;'>{I18n.get('conv_palette_lut_loading', lang)}</div>",
                                    label="",
                                    show_label=False
                                )
                                components['conv_lut_grid_view'] = conv_lut_grid_view

                                # 显示用户选中的替换色
                                conv_replacement_display = gr.ColorPicker(
                                    label=I18n.get('conv_palette_replace_label', lang),
                                    interactive=False
                                )
                                components['color_conv_palette_replace_label'] = conv_replacement_display

                        # 操作按钮区
                        with gr.Row():
                            conv_apply_replacement = gr.Button(I18n.get('conv_palette_apply_btn', lang), variant="primary")
                            conv_undo_replacement = gr.Button(I18n.get('conv_palette_undo_btn', lang))
                            conv_clear_replacements = gr.Button(I18n.get('conv_palette_clear_btn', lang))
                            components['btn_conv_palette_apply_btn'] = conv_apply_replacement
                            components['btn_conv_palette_undo_btn'] = conv_undo_replacement
                            components['btn_conv_palette_clear_btn'] = conv_clear_replacements

                        # 自由色功能
                        with gr.Row():
                            conv_free_color_btn = gr.Button(
                                I18n.get('conv_free_color_btn', lang),
                                variant="secondary", size="sm"
                            )
                            conv_free_color_clear_btn = gr.Button(
                                I18n.get('conv_free_color_clear_btn', lang),
                                size="sm"
                            )
                            components['btn_conv_free_color'] = conv_free_color_btn
                            components['btn_conv_free_color_clear'] = conv_free_color_clear_btn
                        conv_free_color_html = gr.HTML(
                            value="",
                            show_label=False
                        )
                        components['html_conv_free_color_list'] = conv_free_color_html

                        # 调色板预览 HTML (保持原有逻辑，用于显示已替换列表)
                        components['md_conv_palette_replacements_label'] = gr.Markdown(
                            I18n.get('conv_palette_replacements_label', lang)
                        )
                        conv_palette_html = gr.HTML(
                            value=f"<p style='color:#888;'>{I18n.get('conv_palette_replacements_placeholder', lang)}</p>",
                            label="",
                            show_label=False
                        )
                    # ========== END Color Palette ==========
                    
                    # ========== Color Merging ==========
                    with gr.Accordion(I18n.get('merge_accordion_title', lang), open=False) as conv_merge_acc:
                        components['accordion_conv_merge'] = conv_merge_acc
                        
                        # 状态变量
                        conv_merge_map = gr.State({})  # 合并映射表
                        conv_merge_stats = gr.State({})  # 合并统计信息
                        
                        # 启用/禁用复选框
                        conv_merge_enable = gr.Checkbox(
                            label=I18n.get('merge_enable_label', lang),
                            value=True,  # 默认启用以便测试
                            info=I18n.get('merge_enable_info', lang)
                        )
                        components['checkbox_conv_merge_enable'] = conv_merge_enable
                        
                        # 参数滑块
                        with gr.Row():
                            conv_merge_threshold = gr.Slider(
                                minimum=0.1,
                                maximum=5.0,
                                value=0.5,
                                step=0.1,
                                label=I18n.get('merge_threshold_label', lang),
                                info=I18n.get('merge_threshold_info', lang)
                            )
                            components['slider_conv_merge_threshold'] = conv_merge_threshold
                            
                            conv_merge_max_distance = gr.Slider(
                                minimum=5,
                                maximum=50,
                                value=20,
                                step=1,
                                label=I18n.get('merge_max_distance_label', lang),
                                info=I18n.get('merge_max_distance_info', lang)
                            )
                            components['slider_conv_merge_max_distance'] = conv_merge_max_distance
                        
                        # 操作按钮
                        with gr.Row():
                            conv_merge_preview_btn = gr.Button(
                                I18n.get('merge_preview_btn', lang),
                                variant="primary"
                            )
                            conv_merge_apply_btn = gr.Button(
                                I18n.get('merge_apply_btn', lang),
                                variant="secondary"
                            )
                            conv_merge_revert_btn = gr.Button(
                                I18n.get('merge_revert_btn', lang)
                            )
                            components['btn_conv_merge_preview'] = conv_merge_preview_btn
                            components['btn_conv_merge_apply'] = conv_merge_apply_btn
                            components['btn_conv_merge_revert'] = conv_merge_revert_btn
                        
                        # 状态显示
                        conv_merge_status = gr.Markdown(
                            value=I18n.get('merge_status_empty', lang)
                        )
                        components['md_conv_merge_status'] = conv_merge_status
                    # ========== END Color Merging ==========
                    
                    with gr.Group(visible=False):
                        components['md_conv_loop_section'] = gr.Markdown(
                            I18n.get('conv_loop_section', lang)
                        )
                            
                        with gr.Row():
                            components['checkbox_conv_loop_enable'] = gr.Checkbox(
                                label=I18n.get('conv_loop_enable', lang),
                                value=False
                            )
                            components['btn_conv_loop_remove'] = gr.Button(
                                I18n.get('conv_loop_remove', lang),
                                size="sm"
                            )
                            
                        with gr.Row():
                            components['slider_conv_loop_width'] = gr.Slider(
                                2, 10, 4, step=0.5,
                                label=I18n.get('conv_loop_width', lang)
                            )
                            components['slider_conv_loop_length'] = gr.Slider(
                                4, 15, 8, step=0.5,
                                label=I18n.get('conv_loop_length', lang)
                            )
                            components['slider_conv_loop_hole'] = gr.Slider(
                                1, 5, 2.5, step=0.25,
                                label=I18n.get('conv_loop_hole', lang)
                            )
                            
                        with gr.Row():
                            components['slider_conv_loop_angle'] = gr.Slider(
                                -180, 180, 0, step=5,
                                label=I18n.get('conv_loop_angle', lang)
                            )
                            components['textbox_conv_loop_info'] = gr.Textbox(
                                label=I18n.get('conv_loop_info', lang),
                                interactive=False,
                                scale=2
                            )
                    # ========== Outline Settings (moved to right column) ==========

                    components['textbox_conv_status'] = gr.Textbox(
                        label=I18n.get('conv_status', lang),
                        lines=3,
                        interactive=False,
                        max_lines=10,
                        show_label=True
                    )
                with gr.Column(scale=1):
                    # ========== Outline Settings ==========
                    components['md_conv_outline_section'] = gr.Markdown(
                        I18n.get('conv_outline_section', lang)
                    )
                    with gr.Row():
                        components['checkbox_conv_outline_enable'] = gr.Checkbox(
                            label=I18n.get('conv_outline_enable', lang),
                            value=False
                        )
                    components['slider_conv_outline_width'] = gr.Slider(
                        0.5, 10, 2, step=0.5,
                        label=I18n.get('conv_outline_width', lang)
                    )
                    # ========== END Outline Settings ==========

                    # ========== Cloisonné Settings ==========
                    components['md_conv_cloisonne_section'] = gr.Markdown(
                        I18n.get('conv_cloisonne_section', lang)
                    )
                    with gr.Row():
                        components['checkbox_conv_cloisonne_enable'] = gr.Checkbox(
                            label=I18n.get('conv_cloisonne_enable', lang),
                            value=False
                        )
                    components['slider_conv_wire_width'] = gr.Slider(
                        0.2, 1.2, 0.4, step=0.1,
                        label=I18n.get('conv_cloisonne_wire_width', lang)
                    )
                    components['slider_conv_wire_height'] = gr.Slider(
                        0.04, 1.0, 0.4, step=0.04,
                        label=I18n.get('conv_cloisonne_wire_height', lang)
                    )
                    # ========== END Cloisonné Settings ==========

                    # ========== Coating Settings ==========
                    components['md_conv_coating_section'] = gr.Markdown(
                        I18n.get('conv_coating_section', lang)
                    )
                    with gr.Row():
                        components['checkbox_conv_coating_enable'] = gr.Checkbox(
                            label=I18n.get('conv_coating_enable', lang),
                            value=False
                        )
                    components['slider_conv_coating_height'] = gr.Slider(
                        0.08, 0.16, 0.08, step=0.08,
                        label=I18n.get('conv_coating_height', lang)
                    )
                    # ========== END Coating Settings ==========

                    # Action buttons (preview + generate)
                    with gr.Row(elem_classes=["action-buttons"]):
                        components['btn_conv_preview_btn'] = gr.Button(
                            I18n.get('conv_preview_btn', lang),
                            variant="secondary",
                            size="lg"
                        )
                        components['btn_conv_generate_btn'] = gr.Button(
                            I18n.get('conv_generate_btn', lang),
                            variant="primary",
                            size="lg"
                        )

                    # Individual slicer buttons (one per installed slicer + download)
                    slicer_choices = _get_slicer_choices(lang)
                    default_slicer = _get_default_slicer()

                    with gr.Row(elem_id="conv-slicer-split-btn"):
                        for label, sid in slicer_choices:
                            css_cls = _slicer_css_class(sid)
                            btn_key = f'btn_conv_slicer_{sid}'
                            components[btn_key] = gr.Button(
                                value=label,
                                variant="primary" if sid == default_slicer else "secondary",
                                size="lg",
                                elem_classes=[css_cls],
                                scale=1,
                            )
                    # Hidden state for dropdown compatibility (kept as hidden)
                    components['dropdown_conv_slicer'] = gr.Dropdown(
                        choices=slicer_choices,
                        value=default_slicer,
                        label="",
                        show_label=False,
                        elem_id="conv-slicer-dropdown",
                        visible=False
                    )

                    # Hidden file component for download fallback
                    _show_file = (default_slicer == "download")
                    components['file_conv_download_file'] = gr.File(
                        label=I18n.get('conv_download_file', lang),
                        visible=_show_file
                    )
                    
                    # Color recipe log download
                    components['file_conv_color_recipe'] = gr.File(
                        label="颜色配方日志 / Color Recipe Log",
                        visible=_show_file
                    )
                    
                    components['btn_conv_stop'] = gr.Button(
                        value=I18n.get('conv_stop', lang),
                        variant="stop",
                        size="lg"
                    )

        # ========== Floating 3D Thumbnail (bottom-right corner) ==========
        with gr.Column(elem_id="conv-3d-thumbnail-container", visible=True) as conv_3d_thumb_col:
            conv_3d_preview = gr.Model3D(
                value=generate_empty_bed_glb(),
                label="3D",
                clear_color=[0.15, 0.15, 0.18, 1.0],
                height=180,
                elem_id="conv-3d-thumbnail"
            )
            components['btn_conv_3d_fullscreen'] = gr.Button(
                "⛶",
                variant="secondary",
                size="sm",
                elem_id="conv-3d-fullscreen-btn"
            )
        components['col_conv_3d_thumbnail'] = conv_3d_thumb_col

        # ========== Fullscreen 3D Preview Overlay ==========
        with gr.Column(visible=False, elem_id="conv-3d-fullscreen-container") as conv_3d_fullscreen_col:
            components['btn_conv_3d_back'] = gr.Button(
                "✕ 返回",
                variant="secondary",
                size="sm",
                elem_id="conv-3d-back-btn"
            )
            conv_3d_fullscreen = gr.Model3D(
                label="3D Fullscreen",
                clear_color=[0.12, 0.12, 0.15, 1.0],
                height=900,
                elem_id="conv-3d-fullscreen"
            )
        components['col_conv_3d_fullscreen'] = conv_3d_fullscreen_col

        # ========== 2D Thumbnail in fullscreen 3D mode (bottom-right) ==========
        with gr.Column(visible=False, elem_id="conv-2d-thumbnail-container") as conv_2d_thumb_col:
            conv_2d_thumb_preview = gr.Image(
                label="2D",
                type="numpy",
                interactive=False,
                height=160,
                elem_id="conv-2d-thumbnail"
            )
            components['btn_conv_2d_back'] = gr.Button(
                "⛶",
                variant="secondary",
                size="sm",
                elem_id="conv-2d-back-btn"
            )
        components['col_conv_2d_thumbnail'] = conv_2d_thumb_col
    
    # Event binding
    def toggle_batch_mode(is_batch):
        return [
            gr.update(visible=not is_batch),
            gr.update(visible=is_batch)
        ]

    components['checkbox_conv_batch_mode'].change(
        fn=toggle_batch_mode,
        inputs=[components['checkbox_conv_batch_mode']],
        outputs=[components['image_conv_image_label'], components['file_conv_batch_input']]
    )

    # Save crop modal preference when checkbox changes
    def on_crop_checkbox_change(enable_crop):
        print(f"[CROP_SETTING] Saving crop modal preference: {enable_crop}")
        _save_user_setting("enable_crop_modal", enable_crop)
        # Verify it was saved
        saved_value = _load_user_settings().get("enable_crop_modal")
        print(f"[CROP_SETTING] Verified saved value: {saved_value}")
        return None
    
    components['checkbox_conv_enable_crop'].change(
        fn=on_crop_checkbox_change,
        inputs=[components['checkbox_conv_enable_crop']],
        outputs=None
    )

    # ========== Image Crop Extension Events (Non-invasive) ==========
    from core.image_preprocessor import ImagePreprocessor
    
    def _parse_svg_dimensions(svg_path):
        """Parse SVG width/height with viewBox fallback."""
        try:
            root = ET.parse(svg_path).getroot()
        except Exception:
            return 0, 0

        def _parse_len(raw):
            if not raw:
                return None
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)", str(raw))
            if not m:
                return None
            try:
                return int(float(m.group(1)))
            except Exception:
                return None

        w = _parse_len(root.get("width"))
        h = _parse_len(root.get("height"))

        if w and h and w > 0 and h > 0:
            return w, h

        view_box = root.get("viewBox") or root.get("viewbox")
        if view_box:
            try:
                parts = [float(v) for v in re.split(r"[,\s]+", view_box.strip()) if v]
                if len(parts) == 4:
                    vb_w = int(abs(parts[2]))
                    vb_h = int(abs(parts[3]))
                    if vb_w > 0 and vb_h > 0:
                        return vb_w, vb_h
            except Exception:
                pass

        return 0, 0

    def on_image_upload_process_with_html(image_path):
        """When image is uploaded, process and prepare for crop modal (不分析颜色).
        For HEIC/HEIF files, returns the converted PNG path back to the Image
        component so the browser can render it (browsers cannot display HEIC).
        """
        if image_path is None:
            return (
                0, 0, None,
                '<div id="preprocess-dimensions-data" data-width="0" data-height="0" data-is-svg="0" style="display:none;"></div>',
                None,
            )
        
        try:
            # SVG: Gradio's gr.Image stores SVG as base64 data-URL internally, but the
            # base64 decode fails on subsequent events (binascii.Error: Incorrect padding).
            # Fix: render the SVG to a temp PNG for display in gr.Image, while keeping the
            # original SVG path in preprocess_processed_path for the vector converter.
            if isinstance(image_path, str) and image_path.lower().endswith(".svg"):
                width, height = _parse_svg_dimensions(image_path)
                dimensions_html = (
                    f'<div id="preprocess-dimensions-data" data-width="{width}" '
                    f'data-height="{height}" data-is-svg="1" style="display:none;"></div>'
                )
                # Try to render SVG → PNG so gr.Image gets a safe raster file
                display_path = gr.update()
                try:
                    from svglib.svglib import svg2rlg
                    from reportlab.graphics import renderPM
                    import tempfile, os as _os
                    drawing = svg2rlg(image_path)
                    if drawing is not None:
                        tmp_png = tempfile.NamedTemporaryFile(
                            suffix=".png", delete=False,
                            dir=_os.path.dirname(image_path)
                        )
                        tmp_png.close()
                        renderPM.drawToFile(drawing, tmp_png.name, fmt="PNG")
                        display_path = tmp_png.name
                        print(f"[SVG_UPLOAD] Rendered SVG preview → {tmp_png.name}")
                except Exception as render_err:
                    print(f"[SVG_UPLOAD] Could not render SVG preview: {render_err}")
                # preprocess_processed_path keeps the original SVG for the converter;
                # image_conv_image_label gets the PNG (or unchanged) to avoid base64 errors.
                return (width, height, image_path, dimensions_html, display_path)

            info = ImagePreprocessor.process_upload(image_path)
            # 不在这里分析颜色，等用户确认裁剪后再分析
            dimensions_html = (
                f'<div id="preprocess-dimensions-data" data-width="{info.width}" '
                f'data-height="{info.height}" data-is-svg="0" style="display:none;"></div>'
            )
            # If the image was converted (e.g. HEIC→PNG), feed the PNG back to
            # the Image component so the browser can actually render it.
            display_path = info.processed_path if info.was_converted else gr.update()
            return (info.width, info.height, info.processed_path, dimensions_html, display_path)
        except Exception as e:
            print(f"Image upload error: {e}")
            return (0, 0, None, '<div id="preprocess-dimensions-data" data-width="0" data-height="0" data-is-svg="0" style="display:none;"></div>', gr.update())
    
    # JavaScript to open crop modal (不传递颜色推荐，弹窗中不显示)
    # Check if crop modal is enabled before opening
    open_crop_modal_js = """
    () => {
        console.log('[CROP] Trigger fired, checking if crop modal is enabled...');
        
        // Wait for checkbox to be available and check its state
        function checkCropEnabled() {
            // Try multiple selectors to find the checkbox
            let cropCheckbox = document.querySelector('#conv-enable-crop-checkbox input[type="checkbox"]');
            
            if (!cropCheckbox) {
                // Fallback 1: Search by label text (supports both languages)
                const labels = Array.from(document.querySelectorAll('label'));
                const cropLabel = labels.find(l => 
                    l.textContent.includes('启用裁剪界面') || 
                    l.textContent.includes('Enable Crop Interface') ||
                    l.textContent.includes('🖼️')
                );
                if (cropLabel) {
                    cropCheckbox = cropLabel.querySelector('input[type="checkbox"]');
                }
            }
            
            if (!cropCheckbox) {
                // Fallback 2: Search all checkboxes near "裁剪" text
                const allCheckboxes = document.querySelectorAll('input[type="checkbox"]');
                for (let cb of allCheckboxes) {
                    const parent = cb.closest('.wrap') || cb.closest('label') || cb.parentElement;
                    if (parent && (parent.textContent.includes('裁剪') || parent.textContent.includes('Crop'))) {
                        cropCheckbox = cb;
                        break;
                    }
                }
            }
            
            if (!cropCheckbox) {
                console.warn('[CROP] Checkbox not found yet, will retry...');
                return null; // Not found yet
            }
            
            const isCropEnabled = cropCheckbox.checked;
            console.log('[CROP] ✓ Crop checkbox found! Enabled:', isCropEnabled);
            return isCropEnabled;
        }
        
        // Retry mechanism to wait for checkbox to be available
        function waitForCheckboxAndDecide(retries = 10, delay = 300) {
            const enabled = checkCropEnabled();
            
            if (enabled === null && retries > 0) {
                // Checkbox not found yet, retry
                console.log('[CROP] Retrying checkbox check... (' + retries + ' attempts left)');
                setTimeout(() => waitForCheckboxAndDecide(retries - 1, delay), delay);
                return;
            }
            
            if (enabled === false) {
                console.log('[CROP] ✗ Crop modal disabled by user, skipping...');
                return;
            }
            
            // Checkbox is enabled or not found after all retries (default to enabled)
            if (enabled === null) {
                console.warn('[CROP] ⚠ Checkbox not found after retries, defaulting to enabled');
            } else {
                console.log('[CROP] ✓ Crop modal enabled, proceeding...');
            }
            
            // Proceed to open crop modal
            openCropModalIfReady();
        }
        
        function openCropModalIfReady() {
            console.log('[CROP] Checking for openCropModal function:', typeof window.openCropModal);
            const dimElement = document.querySelector('#preprocess-dimensions-data');
            console.log('[CROP] dimElement found:', !!dimElement);
            if (dimElement) {
                const isSvgUpload = dimElement.dataset.isSvg === '1';
                if (isSvgUpload) {
                    console.log('[CROP] SVG upload detected, skipping crop modal.');
                    return;
                }
                const width = parseInt(dimElement.dataset.width) || 0;
                const height = parseInt(dimElement.dataset.height) || 0;
                console.log('[CROP] Dimensions:', width, 'x', height);
                if (width > 0 && height > 0) {
                    const imgContainer = document.querySelector('#conv-image-input');
                    console.log('[CROP] imgContainer found:', !!imgContainer);
                    if (imgContainer) {
                        const img = imgContainer.querySelector('img');
                        console.log('[CROP] img found:', !!img, 'src:', img ? img.src.substring(0, 50) : 'none');
                        if (img && img.src && typeof window.openCropModal === 'function') {
                            console.log('[CROP] Calling openCropModal...');
                            window.openCropModal(img.src, width, height, 0, 0);
                        } else {
                            console.error('[CROP] Cannot open modal - missing requirements');
                        }
                    }
                }
            }
        }
        
        // Start the check with retry mechanism
        waitForCheckboxAndDecide();
    }
    """
    
    components['image_conv_image_label'].upload(
        on_image_upload_process_with_html,
        inputs=[components['image_conv_image_label']],
        outputs=[preprocess_img_width, preprocess_img_height, preprocess_processed_path, preprocess_dimensions_html, components['image_conv_image_label']]
    ).then(
        fn=None,
        inputs=None,
        outputs=None,
        js=open_crop_modal_js
    )
    
    def use_original_image_simple(processed_path, w, h, crop_json):
        """Use original image without cropping"""
        print(f"[DEBUG] use_original_image_simple called: {processed_path}")
        if processed_path is None:
            return None
        try:
            if isinstance(processed_path, str) and processed_path.lower().endswith(".svg"):
                return processed_path
            result_path = ImagePreprocessor.convert_to_png(processed_path)
            return result_path
        except Exception as e:
            print(f"Use original error: {e}")
            return None
    
    use_original_btn.click(
        use_original_image_simple,
        inputs=[preprocess_processed_path, preprocess_img_width, preprocess_img_height, crop_data_json],
        outputs=[components['image_conv_image_label']]
    )
    
    def confirm_crop_image_simple(processed_path, crop_json):
        """Crop image with specified region"""
        print(f"[DEBUG] confirm_crop_image_simple called: {processed_path}, {crop_json}")
        if processed_path is None:
            return None
        try:
            if isinstance(processed_path, str) and processed_path.lower().endswith(".svg"):
                print("[DEBUG] SVG uploaded, skipping raster crop and keeping original path")
                return processed_path
            import json
            data = json.loads(crop_json) if crop_json else {"x": 0, "y": 0, "w": 100, "h": 100}
            x = int(data.get("x", 0))
            y = int(data.get("y", 0))
            w = int(data.get("w", 100))
            h = int(data.get("h", 100))
            
            result_path = ImagePreprocessor.crop_image(processed_path, x, y, w, h)
            return result_path
        except Exception as e:
            print(f"Crop error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    confirm_crop_btn.click(
        confirm_crop_image_simple,
        inputs=[preprocess_processed_path, crop_data_json],
        outputs=[components['image_conv_image_label']]
    )
    
    # ========== Auto Color Detection Button ==========
    # 用于触发 toast 的隐藏 HTML 组件
    color_toast_trigger = gr.HTML(value="", visible=True, elem_classes=["hidden-crop-component"])
    
    # JavaScript to show color recommendation toast
    show_toast_js = """
    () => {
        setTimeout(() => {
            const trigger = document.querySelector('#color-rec-trigger');
            if (trigger) {
                const recommended = parseInt(trigger.dataset.recommended) || 0;
                const maxSafe = parseInt(trigger.dataset.maxsafe) || 0;
                if (recommended > 0 && typeof window.showColorRecommendationToast === 'function') {
                    const lang = document.documentElement.lang || 'zh';
                    let msg;
                    if (lang === 'en') {
                        msg = '💡 Color detail set to <b>' + recommended + '</b> (max safe: ' + maxSafe + ')';
                    } else {
                        msg = '💡 色彩细节已设置为 <b>' + recommended + '</b>（最大安全值: ' + maxSafe + '）';
                    }
                    window.showColorRecommendationToast(msg);
                }
                trigger.remove();
            }
        }, 100);
    }
    """
    
    def auto_detect_colors(image_path, target_width_mm):
        """自动检测推荐的色彩细节值"""
        if image_path is None:
            return gr.update(), ""
        try:
            import time
            print(f"[AutoColor] 开始分析: {image_path}, 目标宽度: {target_width_mm}mm")
            color_analysis = ImagePreprocessor.analyze_recommended_colors(image_path, target_width_mm)
            recommended = color_analysis.get('recommended', 24)
            max_safe = color_analysis.get('max_safe', 32)
            print(f"[AutoColor] 分析完成: recommended={recommended}, max_safe={max_safe}")
            # 添加时间戳确保每次返回值不同，触发 .then() 中的 JavaScript
            timestamp = int(time.time() * 1000)
            toast_html = f'<div id="color-rec-trigger" data-recommended="{recommended}" data-maxsafe="{max_safe}" data-ts="{timestamp}" style="display:none;"></div>'
            return gr.update(value=recommended), toast_html
        except Exception as e:
            print(f"[AutoColor] 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return gr.update(), ""
    
    components['btn_conv_auto_color'].click(
        auto_detect_colors,
        inputs=[components['image_conv_image_label'], components['slider_conv_width']],
        outputs=[components['slider_conv_quantize_colors'], color_toast_trigger]
    ).then(
        fn=None,
        inputs=None,
        outputs=None,
        js=show_toast_js
    )
    # ========== END Image Crop Extension Events ==========

    components['dropdown_conv_lut_dropdown'].change(
            on_lut_select,
            inputs=[components['dropdown_conv_lut_dropdown']],
            outputs=[conv_lut_path, components['md_conv_lut_status']]
    ).then(
            fn=save_last_lut_setting,
            inputs=[components['dropdown_conv_lut_dropdown']],
            outputs=None
    ).then(
            fn=_update_lut_grid,
            inputs=[conv_lut_path, lang_state, conv_palette_mode],
            outputs=[conv_lut_grid_view]
    ).then(
            fn=_detect_and_enforce_structure,
            inputs=[conv_lut_path],
            outputs=[components['radio_conv_color_mode'], components['radio_conv_structure'], components['checkbox_conv_relief_mode']]
    )


    


    conv_lut_upload.upload(
            on_lut_upload_save,
            inputs=[conv_lut_upload],
            outputs=[components['dropdown_conv_lut_dropdown'], components['md_conv_lut_status']]
    ).then(
            fn=lambda: gr.update(),
            outputs=[components['dropdown_conv_lut_dropdown']]
    ).then(
            fn=lambda lut_file: _detect_and_enforce_structure(lut_file.name if lut_file else None),
            inputs=[conv_lut_upload],
            outputs=[components['radio_conv_color_mode'], components['radio_conv_structure'], components['checkbox_conv_relief_mode']]
    )
    
    components['image_conv_image_label'].change(
            fn=init_dims,
            inputs=[components['image_conv_image_label']],
            outputs=[components['slider_conv_width'], conv_target_height_mm]
    ).then(
            # 自动检测图像类型并切换建模模式
            # 使用 preprocess_processed_path 而非 image_conv_image_label，
            # 因为 SVG 上传后 image_conv_image_label 存的是 PNG 缩略图，
            # 只有 preprocess_processed_path 保留原始 SVG 路径。
            fn=detect_image_type,
            inputs=[preprocess_processed_path],
            outputs=[components['radio_conv_modeling_mode']]
    ).then(
            # 清空已生成的 3MF 文件，强制下次点击切片按钮时重新生成
            fn=lambda: None,
            inputs=None,
            outputs=[components['file_conv_download_file']]
    )
    components['slider_conv_width'].input(
            fn=calc_height_from_width,
            inputs=[components['slider_conv_width'], components['image_conv_image_label']],
            outputs=[conv_target_height_mm]
    )
    conv_target_height_mm.input(
            fn=calc_width_from_height,
            inputs=[conv_target_height_mm, components['image_conv_image_label']],
            outputs=[components['slider_conv_width']]
    )
    def generate_preview_cached_with_fit(image_path, lut_path, target_width_mm,
                                         auto_bg, bg_tol, color_mode,
                                         modeling_mode, quantize_colors, enable_cleanup,
                                         is_dark_theme=False, processed_path=None,
                                         hue_weight=0.0):
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
            hue_weight=float(hue_weight) if hue_weight else 0.0
        )
        # Generate realtime 3D preview GLB
        glb_path = generate_realtime_glb(cache) if cache is not None else None
        return _preview_update(display), cache, status, glb_path

    # 建模模式切换：统一处理可用参数提示与禁用逻辑
    def on_modeling_mode_change_controls(mode):
        is_pixel = mode == ModelingMode.PIXEL
        is_vector = mode == ModelingMode.VECTOR

        # Cleanup: Pixel 模式禁用，其它模式可用
        if is_pixel:
            cleanup_update = gr.update(
                interactive=False,
                value=False,
                info="像素模式下不支持孤立像素清理 | Not available in Pixel Art mode",
            )
        else:
            cleanup_update = gr.update(
                interactive=True,
                info="清理 LUT 匹配后的孤立像素，提升打印成功率",
            )

        # Outline / Cloisonné: 当前仅在 Raster 路径生效，Vector 模式禁用并提示
        if is_vector:
            outline_checkbox_update = gr.update(
                interactive=False,
                value=False,
                info="Vector(SVG) 模式暂不支持描边；该选项仅在 Raster 路径生效",
            )
            outline_width_update = gr.update(
                interactive=False,
                info="Vector(SVG) 模式下已禁用",
            )
            cloisonne_checkbox_update = gr.update(
                interactive=False,
                value=False,
                info="Vector(SVG) 模式暂不支持掐丝珐琅；该选项仅在 Raster 路径生效",
            )
            wire_width_update = gr.update(
                interactive=False,
                info="Vector(SVG) 模式下已禁用",
            )
            wire_height_update = gr.update(
                interactive=False,
                info="Vector(SVG) 模式下已禁用",
            )
        else:
            outline_checkbox_update = gr.update(
                interactive=True,
                info="描边仅在生成阶段生效",
            )
            outline_width_update = gr.update(
                interactive=True,
                info=None,
            )
            cloisonne_checkbox_update = gr.update(
                interactive=True,
                info="掐丝珐琅仅在生成阶段生效（与 2.5D 浮雕互斥）",
            )
            wire_width_update = gr.update(
                interactive=True,
                info=None,
            )
            wire_height_update = gr.update(
                interactive=True,
                info=None,
            )

        return (
            cleanup_update,
            outline_checkbox_update,
            outline_width_update,
            cloisonne_checkbox_update,
            wire_width_update,
            wire_height_update,
        )

    components['radio_conv_modeling_mode'].change(
        on_modeling_mode_change_controls,
        inputs=[components['radio_conv_modeling_mode']],
        outputs=[
            components['checkbox_conv_cleanup'],
            components['checkbox_conv_outline_enable'],
            components['slider_conv_outline_width'],
            components['checkbox_conv_cloisonne_enable'],
            components['slider_conv_wire_width'],
            components['slider_conv_wire_height'],
        ]
    ).then(
        fn=save_modeling_mode,
        inputs=[components['radio_conv_modeling_mode']],
        outputs=None
    )

    # Save color mode when changed
    components['radio_conv_color_mode'].change(
        fn=save_color_mode,
        inputs=[components['radio_conv_color_mode']],
        outputs=None
    )

    def _on_color_mode_update_structure(color_mode):
        """5-Color Extended requires single-sided face-up (max 4 materials per Z layer).
        Also disables 2.5D relief mode which is incompatible with 5-Color Extended.
        """
        if color_mode and "5-Color Extended" in color_mode:
            return gr.update(
                value=I18n.get('conv_structure_single', 'en'),
                interactive=False,
            ), gr.update(value=False, interactive=False)
        return gr.update(interactive=True), gr.update(interactive=True)

    components['radio_conv_color_mode'].change(
        fn=_on_color_mode_update_structure,
        inputs=[components['radio_conv_color_mode']],
        outputs=[components['radio_conv_structure'], components['checkbox_conv_relief_mode']],
    )

    preview_event = components['btn_conv_preview_btn'].click(
            generate_preview_cached_with_fit,
            inputs=[
                components['image_conv_image_label'],
                conv_lut_path,
                components['slider_conv_width'],
                components['checkbox_conv_auto_bg'],
                components['slider_conv_tolerance'],
                components['radio_conv_color_mode'],
                components['radio_conv_modeling_mode'],
                components['slider_conv_quantize_colors'],
                components['checkbox_conv_cleanup'],
                theme_state,
                preprocess_processed_path,
                components['slider_conv_hue_weight'],
            ],
            outputs=[conv_preview, conv_preview_cache, components['textbox_conv_status'], conv_3d_preview]
    ).then(
            on_preview_generated_update_palette,
            inputs=[conv_preview_cache, lang_state],
            outputs=[conv_palette_html, conv_selected_color]
    ).then(
            fn=lambda: (None, None),
            inputs=[],
            outputs=[conv_selected_user_row_id, conv_selected_auto_row_id]
    )

    # Hidden textbox receives highlight color from JavaScript click (triggers preview highlight)
    # Use button click instead of textbox change for more reliable triggering
    def on_highlight_color_change_with_fit(highlight_hex, cache, loop_pos, add_loop,
                                           loop_width, loop_length, loop_hole, loop_angle):
        display, status = on_highlight_color_change(
            highlight_hex, cache, loop_pos, add_loop,
            loop_width, loop_length, loop_hole, loop_angle
        )
        return _preview_update(display), status

    conv_highlight_trigger_btn.click(
            on_highlight_color_change_with_fit,
            inputs=[
                conv_highlight_color_hidden, conv_preview_cache, conv_loop_pos,
                components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'], components['slider_conv_loop_angle']
            ],
            outputs=[conv_preview, components['textbox_conv_status']]
    )

    # [新增] 处理 LUT 色块点击事件 (JS -> Hidden Textbox -> Python)
    def on_lut_color_click(hex_color):
        return hex_color, hex_color

    def build_palette_html_with_selection(cache, replacement_regions,
                                          selected_user_row_id, selected_auto_row_id,
                                          lang_state_val):
        from ui.palette_extension import generate_palette_html

        if cache is None:
            placeholder = I18n.get('conv_palette_replacements_placeholder', lang_state_val)
            return f"<p style='color:#888;'>{placeholder}</p>"

        palette = cache.get('color_palette', [])
        auto_pairs = []
        q_img = cache.get('quantized_image')
        m_img = cache.get('matched_rgb')
        mask = cache.get('mask_solid')
        if q_img is not None and m_img is not None and mask is not None:
            h, w = m_img.shape[:2]
            for y in range(h):
                for x in range(w):
                    if not mask[y, x]:
                        continue
                    qh = f"#{int(q_img[y,x,0]):02x}{int(q_img[y,x,1]):02x}{int(q_img[y,x,2]):02x}"
                    mh = f"#{int(m_img[y,x,0]):02x}{int(m_img[y,x,1]):02x}{int(m_img[y,x,2]):02x}"
                    auto_pairs.append({"quantized_hex": qh, "matched_hex": mh})

        return generate_palette_html(
            palette,
            replacements={},
            selected_color=None,
            lang=lang_state_val,
            replacement_regions=replacement_regions or [],
            auto_pairs=auto_pairs,
            selected_user_row_id=selected_user_row_id,
            selected_auto_row_id=selected_auto_row_id,
        )

    def on_palette_row_select(row_id, selected_user_row_id, selected_auto_row_id, cache):
        row_id = (row_id or '').strip()

        new_cache = cache.copy() if isinstance(cache, dict) else cache
        if isinstance(new_cache, dict):
            new_cache['selection_scope'] = 'global'
            new_cache['selected_region_mask'] = None

        if not row_id:
            return selected_user_row_id, selected_auto_row_id, new_cache
        if row_id.startswith('user::'):
            return row_id, None, new_cache
        if row_id.startswith('auto::'):
            return None, row_id, new_cache
        return selected_user_row_id, selected_auto_row_id, new_cache

    conv_lut_color_trigger_btn.click(
            fn=on_lut_color_click,
            inputs=[conv_lut_color_selected_hidden],
            outputs=[conv_replacement_color_state, conv_replacement_display]
    )

    conv_palette_row_select_trigger_btn.click(
            fn=on_palette_row_select,
            inputs=[conv_palette_row_select_hidden, conv_selected_user_row_id, conv_selected_auto_row_id, conv_preview_cache],
            outputs=[conv_selected_user_row_id, conv_selected_auto_row_id, conv_preview_cache]
    ).then(
            fn=build_palette_html_with_selection,
            inputs=[
                conv_preview_cache, conv_replacement_regions,
                conv_selected_user_row_id, conv_selected_auto_row_id, lang_state
            ],
            outputs=[conv_palette_html]
    )

    def on_delete_selected_user_replacement_regions_only(
        cache, replacement_regions, replacement_history,
        selected_user_row_id,
        loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
        lang_state_val
    ):
        display, updated_cache, palette_html, new_regions, new_history, status, selected_user = on_delete_selected_user_replacement(
            cache, replacement_regions, replacement_history,
            selected_user_row_id,
            loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
            lang_state_val
        )
        return display, updated_cache, palette_html, new_regions, new_history, status, selected_user

    conv_palette_delete_trigger_btn.click(
            fn=on_delete_selected_user_replacement_regions_only,
            inputs=[
                conv_preview_cache, conv_replacement_regions, conv_replacement_history,
                conv_selected_user_row_id,
                conv_loop_pos, components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
                lang_state
            ],
            outputs=[
                conv_preview, conv_preview_cache, conv_palette_html,
                conv_replacement_regions, conv_replacement_history,
                components['textbox_conv_status'], conv_selected_user_row_id
            ]
    ).then(
            fn=lambda: None,
            inputs=[],
            outputs=[conv_selected_auto_row_id]
    )

    # 以色找色: ColorPicker nearest match via KDTree
    def on_color_picker_find_nearest(picker_hex, lut_path):
        """Find the nearest LUT color to the picked color using KDTree."""
        if not picker_hex or not lut_path:
            return gr.update(), gr.update()
        try:
            from core.converter import extract_lut_available_colors
            from core.image_processing import LuminaImageProcessor
            import numpy as np
            from scipy.spatial import KDTree

            colors = extract_lut_available_colors(lut_path)
            if not colors:
                return gr.update(), gr.update()

            # Build KDTree from LUT colors
            rgb_array = np.array([c['color'] for c in colors], dtype=np.float64)
            tree = KDTree(rgb_array)

            # Parse picker hex
            h = picker_hex.lstrip('#')
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

            dist, idx = tree.query([[r, g, b]])
            nearest = colors[idx[0]]
            nearest_hex = nearest['hex']

            print(f"[COLOR_PICKER] {picker_hex} → nearest LUT: {nearest_hex} (dist={dist[0]:.1f})")

            # Return JS call to scroll to the matched swatch + update replacement display
            gr.Info(f"✅ 最接近: {nearest_hex} (距离: {dist[0]:.1f})")
            return nearest_hex, nearest_hex
        except Exception as e:
            print(f"[COLOR_PICKER] Error: {e}")
            return gr.update(), gr.update()

    components['btn_conv_picker_search'].click(
        fn=on_color_picker_find_nearest,
        inputs=[components['color_conv_picker_search'], conv_lut_path],
        outputs=[conv_replacement_color_state, conv_replacement_display]
    ).then(
        fn=None,
        inputs=[conv_replacement_color_state],
        outputs=[],
        js="(hex) => { if (hex) { setTimeout(() => window.lutScrollToColor && window.lutScrollToColor(hex), 200); } }"
    )
    
    # Color replacement: Apply replacement
    def on_apply_color_replacement_with_fit(cache, selected_color, replacement_color,
                                            replacement_regions, replacement_history,
                                            loop_pos, add_loop, loop_width, loop_length,
                                            loop_hole, loop_angle, lang_state_val):
        display, updated_cache, palette_html, new_regions, new_history, status = on_apply_color_replacement(
            cache, selected_color, replacement_color,
            replacement_regions, replacement_history,
            loop_pos, add_loop, loop_width, loop_length,
            loop_hole, loop_angle, lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, new_regions, new_history, status

    conv_apply_replacement.click(
            on_apply_color_replacement_with_fit,
            inputs=[
                conv_preview_cache, conv_selected_color, conv_replacement_color_state,
                conv_replacement_regions, conv_replacement_history, conv_loop_pos, components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
                lang_state
            ],
            outputs=[conv_preview, conv_preview_cache, conv_palette_html, conv_replacement_regions, conv_replacement_history, components['textbox_conv_status']]
    ).then(
            fn=lambda: (None, None),
            inputs=[],
            outputs=[conv_selected_user_row_id, conv_selected_auto_row_id]
    )

    
    # Color replacement: Undo last replacement
    def on_undo_color_replacement_with_fit(cache, replacement_regions, replacement_history,
                                           loop_pos, add_loop, loop_width, loop_length,
                                           loop_hole, loop_angle, lang_state_val):
        display, updated_cache, palette_html, new_regions, new_history, status = on_undo_color_replacement(
            cache, replacement_regions, replacement_history,
            loop_pos, add_loop, loop_width, loop_length,
            loop_hole, loop_angle, lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, new_regions, new_history, status

    conv_undo_replacement.click(
            on_undo_color_replacement_with_fit,
            inputs=[
                conv_preview_cache, conv_replacement_regions, conv_replacement_history,
                conv_loop_pos, components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
                lang_state
            ],
            outputs=[conv_preview, conv_preview_cache, conv_palette_html, conv_replacement_regions, conv_replacement_history, components['textbox_conv_status']]
    ).then(
            fn=lambda: (None, None),
            inputs=[],
            outputs=[conv_selected_user_row_id, conv_selected_auto_row_id]
    )

    
    # Color replacement: Clear all replacements
    def on_clear_color_replacements_with_fit(cache, replacement_regions, replacement_history,
                                             loop_pos, add_loop, loop_width, loop_length,
                                             loop_hole, loop_angle, lang_state_val):
        display, updated_cache, palette_html, new_regions, new_history, status = on_clear_color_replacements(
            cache, replacement_regions, replacement_history,
            loop_pos, add_loop, loop_width, loop_length,
            loop_hole, loop_angle, lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, new_regions, new_history, status

    conv_clear_replacements.click(
            on_clear_color_replacements_with_fit,
            inputs=[
                conv_preview_cache, conv_replacement_regions, conv_replacement_history,
                conv_loop_pos, components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
                lang_state
            ],
            outputs=[conv_preview, conv_preview_cache, conv_palette_html, conv_replacement_regions, conv_replacement_history, components['textbox_conv_status']]
    )


    # ========== Free Color (自由色) Event Handlers ==========
    def _render_free_color_html(free_set):
        if not free_set:
            return ""
        parts = ["<div style='display:flex; flex-wrap:wrap; gap:6px; padding:4px; align-items:center;'>",
                 "<span style='font-size:11px; color:#666;'>🎯 自由色:</span>"]
        for hex_c in sorted(free_set):
            parts.append(
                f"<div style='width:24px;height:24px;background:{hex_c};border:2px solid #ff6b6b;"
                f"border-radius:4px;' title='{hex_c}'></div>"
            )
        parts.append("</div>")
        return "".join(parts)

    def on_mark_free_color(selected_color, free_set):
        if not selected_color:
            return free_set, gr.update(), "[ERROR] 请先点击预览图选择一个颜色"
        new_set = set(free_set) if free_set else set()
        hex_c = selected_color.lower()
        if hex_c in new_set:
            new_set.discard(hex_c)
            msg = f"↩️ 已取消自由色: {hex_c}"
        else:
            new_set.add(hex_c)
            msg = f"🎯 已标记为自由色: {hex_c} (生成时将作为独立对象)"
        return new_set, _render_free_color_html(new_set), msg

    def on_clear_free_colors(free_set):
        return set(), "", "[OK] 已清除所有自由色标记"

    conv_free_color_btn.click(
        on_mark_free_color,
        inputs=[conv_selected_color, conv_free_color_set],
        outputs=[conv_free_color_set, conv_free_color_html, components['textbox_conv_status']]
    )
    conv_free_color_clear_btn.click(
        on_clear_free_colors,
        inputs=[conv_free_color_set],
        outputs=[conv_free_color_set, conv_free_color_html, components['textbox_conv_status']]
    )
    # ========== END Free Color ==========

    # ========== Color Merging Event Handlers ==========
    
    # Preview merge effect
    def on_merge_preview_with_fit(cache, merge_enable, merge_threshold, merge_max_distance,
                                  loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
                                  lang_state_val):
        display, updated_cache, palette_html, merge_map, merge_stats, status = on_merge_preview(
            cache, merge_enable, merge_threshold, merge_max_distance,
            loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
            lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, merge_map, merge_stats, status

    components['btn_conv_merge_preview'].click(
        on_merge_preview_with_fit,
        inputs=[
            conv_preview_cache,
            components['checkbox_conv_merge_enable'],
            components['slider_conv_merge_threshold'],
            components['slider_conv_merge_max_distance'],
            conv_loop_pos,
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            conv_preview,
            conv_preview_cache,
            conv_palette_html,
            conv_merge_map,
            conv_merge_stats,
            components['md_conv_merge_status']
        ]
    )

    # Apply merge
    def on_merge_apply_with_fit(cache, merge_map, merge_stats,
                                loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
                                lang_state_val):
        display, updated_cache, palette_html, status = on_merge_apply(
            cache, merge_map, merge_stats,
            loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
            lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, status

    components['btn_conv_merge_apply'].click(
        on_merge_apply_with_fit,
        inputs=[
            conv_preview_cache,
            conv_merge_map,
            conv_merge_stats,
            conv_loop_pos,
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            conv_preview,
            conv_preview_cache,
            conv_palette_html,
            components['md_conv_merge_status']
        ]
    )

    # Revert merge
    def on_merge_revert_with_fit(cache, loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
                                 lang_state_val):
        display, updated_cache, palette_html, empty_map, empty_stats, status = on_merge_revert(
            cache, loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
            lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, empty_map, empty_stats, status

    components['btn_conv_merge_revert'].click(
        on_merge_revert_with_fit,
        inputs=[
            conv_preview_cache,
            conv_loop_pos,
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            conv_preview,
            conv_preview_cache,
            conv_palette_html,
            conv_merge_map,
            conv_merge_stats,
            components['md_conv_merge_status']
        ]
    )
    
    # ========== END Color Merging ==========

    # [修改] 预览图点击事件同步到 UI
    def on_preview_click_sync_ui(cache, evt: gr.SelectData, lut_path):
        from ui.palette_extension import generate_dual_recommendations_html, build_selected_dual_color_html

        img, display_text, hex_val, msg = on_preview_click_select_color(cache, evt)
        if hex_val is None or not isinstance(hex_val, str):
            return _preview_update(img), gr.update(), gr.update(), gr.update(), msg

        rec_html = ""
        try:
            if lut_path and cache is not None:
                q_hex = cache.get('selected_quantized_hex')
                m_hex = cache.get('selected_matched_hex')
                if q_hex and m_hex:
                    lut_colors = get_lut_color_choices(lut_path)
                    rec = _build_dual_recommendations(
                        tuple(int(q_hex[i:i+2], 16) for i in (1, 3, 5)),
                        tuple(int(m_hex[i:i+2], 16) for i in (1, 3, 5)),
                        lut_colors,
                        top_k=10
                    )
                    rec_html = generate_dual_recommendations_html(rec, lang=lang)
        except Exception as e:
            print(f"[DUAL_RECOMMEND] Failed: {e}")

        display_hex, state_hex = _resolve_click_selection_hexes(cache, hex_val)
        selected_html = build_selected_dual_color_html(state_hex, display_hex, lang=lang)
        return _preview_update(img), selected_html, state_hex, rec_html, msg

    # Relief mode: update slider when color is selected
    def on_color_selected_for_relief(hex_color, enable_relief, height_map, base_thickness, cache):
        """When user clicks a color in preview, update relief slider.
        用户点击预览图选色后，更新浮雕高度 slider。

        Args:
            hex_color (str | None): Quantized hex from click selection. (点击选中的量化色 hex)
            enable_relief (bool): Whether relief mode is enabled. (浮雕模式是否开启)
            height_map (dict): Color-to-height mapping keyed by matched hex. (matched hex 为 key 的颜色高度映射)
            base_thickness (float): Base thickness fallback in mm. (底板厚度回退值，单位 mm)
            cache (dict | None): Preview cache containing selected_matched_hex. (预览缓存，包含 selected_matched_hex)

        Returns:
            tuple: (slider update, relief_selected_color, selected_color). (slider 更新, 浮雕选中色, 选中色)
        """
        if not enable_relief or not hex_color:
            return gr.update(visible=False), hex_color, hex_color

        # Use matched hex (same key space as color_height_map) for lookup
        matched_hex = (cache or {}).get('selected_matched_hex', hex_color) if cache else hex_color
        current_height = height_map.get(matched_hex, base_thickness)

        # Store matched_hex in conv_relief_selected_color so slider edits
        # write back with the correct key
        return gr.update(visible=True, value=current_height), matched_hex, hex_color

    conv_preview.select(
            fn=on_preview_click_sync_ui,
            inputs=[conv_preview_cache, conv_lut_path],
            outputs=[
                conv_preview,
                conv_selected_display,
                conv_selected_color,
                conv_dual_recommend_html,
                components['textbox_conv_status']
            ]
    ).then(
        # Also update relief slider when clicking preview image
        fn=on_color_selected_for_relief,
        inputs=[
            conv_selected_color,
            components['checkbox_conv_relief_mode'],
            conv_color_height_map,
            components['slider_conv_thickness'],
            conv_preview_cache
        ],
        outputs=[
            components['slider_conv_relief_height'],
            conv_relief_selected_color,
            conv_selected_color
        ]
    )
    def update_preview_with_loop_with_fit(cache, loop_pos, add_loop,
                                          loop_width, loop_length, loop_hole, loop_angle):
        display = update_preview_with_loop(
            cache, loop_pos, add_loop,
            loop_width, loop_length, loop_hole, loop_angle
        )
        return _preview_update(display)

    components['btn_conv_loop_remove'].click(
            on_remove_loop,
            outputs=[conv_loop_pos, components['checkbox_conv_loop_enable'], 
                    components['slider_conv_loop_angle'], components['textbox_conv_loop_info']]
    ).then(
            update_preview_with_loop_with_fit,
            inputs=[
                conv_preview_cache, conv_loop_pos, components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'], components['slider_conv_loop_angle']
            ],
            outputs=[conv_preview]
    )
    loop_params = [
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle']
    ]
    for param in loop_params:
            param.change(
                update_preview_with_loop_with_fit,
                inputs=[
                    conv_preview_cache, conv_loop_pos, components['checkbox_conv_loop_enable'],
                    components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                    components['slider_conv_loop_hole'], components['slider_conv_loop_angle']
                ],
                outputs=[conv_preview]
            )
    # ========== Relief / Cloisonné Mutual Exclusion ==========
    def on_relief_mode_toggle(enable_relief, selected_color, height_map, base_thickness):
        """Toggle relief mode visibility and reset state; auto-disable cloisonné.
        
        Returns updates for:
        - slider_conv_relief_height
        - accordion_conv_auto_height
        - slider_conv_auto_height_max
        - row_conv_heightmap
        - image_conv_heightmap_preview
        - conv_color_height_map
        - conv_relief_selected_color
        - radio_conv_auto_height_mode (reset to default)
        - checkbox_conv_cloisonne_enable (auto-disable)
        - image_conv_heightmap (clear on disable)
        """
        if not enable_relief:
            # 关闭浮雕模式 - 隐藏所有浮雕相关控件，清除 heightmap 残留值
            return (
                gr.update(visible=False),   # slider_conv_relief_height
                gr.update(visible=False),   # accordion_conv_auto_height
                gr.update(visible=False),   # slider_conv_auto_height_max
                gr.update(visible=False),   # row_conv_heightmap
                gr.update(visible=False),   # image_conv_heightmap_preview
                {},                         # conv_color_height_map
                None,                       # conv_relief_selected_color
                gr.update(value="深色凸起"), # radio_conv_auto_height_mode reset
                gr.update(),                # checkbox_conv_cloisonne_enable (no change)
                gr.update(value=None),      # image_conv_heightmap（清除）
            )
        else:
            # 开启浮雕模式 - 默认「深色凸起」，隐藏高度图上传区，自动关闭掐丝珐琅
            gr.Info("⚠️ 2.5D浮雕模式与掐丝珐琅模式互斥，已自动关闭掐丝珐琅 | Relief and Cloisonné are mutually exclusive, Cloisonné disabled")
            if selected_color:
                current_height = height_map.get(selected_color, base_thickness)
                return (
                    gr.update(visible=True, value=current_height),  # slider_conv_relief_height
                    gr.update(visible=True),    # accordion_conv_auto_height
                    gr.update(visible=True),    # slider_conv_auto_height_max
                    gr.update(visible=False),   # row_conv_heightmap (hidden for luminance mode)
                    gr.update(visible=False),   # image_conv_heightmap_preview
                    height_map,                 # conv_color_height_map
                    selected_color,             # conv_relief_selected_color
                    gr.update(value="深色凸起"), # radio_conv_auto_height_mode reset
                    gr.update(value=False),     # checkbox_conv_cloisonne_enable (disable)
                    gr.update(),                # image_conv_heightmap（不变）
                )
            else:
                return (
                    gr.update(visible=False),   # slider_conv_relief_height
                    gr.update(visible=True),    # accordion_conv_auto_height
                    gr.update(visible=True),    # slider_conv_auto_height_max
                    gr.update(visible=False),   # row_conv_heightmap (hidden for luminance mode)
                    gr.update(visible=False),   # image_conv_heightmap_preview
                    height_map,                 # conv_color_height_map
                    selected_color,             # conv_relief_selected_color
                    gr.update(value="深色凸起"), # radio_conv_auto_height_mode reset
                    gr.update(value=False),     # checkbox_conv_cloisonne_enable (disable)
                    gr.update(),                # image_conv_heightmap（不变）
                )

    def on_cloisonne_mode_toggle(enable_cloisonne):
        """When cloisonné is enabled, auto-disable relief mode"""
        if enable_cloisonne:
            gr.Info("⚠️ 掐丝珐琅模式与2.5D浮雕模式互斥，已自动关闭浮雕 | Cloisonné and Relief are mutually exclusive, Relief disabled")
            return gr.update(value=False), gr.update(visible=False), gr.update(visible=False)
        return gr.update(), gr.update(), gr.update()

    components['checkbox_conv_relief_mode'].change(
        on_relief_mode_toggle,
        inputs=[
            components['checkbox_conv_relief_mode'],
            conv_relief_selected_color,
            conv_color_height_map,
            components['slider_conv_thickness']
        ],
        outputs=[
            components['slider_conv_relief_height'],
            components['accordion_conv_auto_height'],
            components['slider_conv_auto_height_max'],
            components['row_conv_heightmap'],
            components['image_conv_heightmap_preview'],
            conv_color_height_map,
            conv_relief_selected_color,
            components['radio_conv_auto_height_mode'],
            components['checkbox_conv_cloisonne_enable'],
            components['image_conv_heightmap'],
        ]
    )

    components['checkbox_conv_cloisonne_enable'].change(
        on_cloisonne_mode_toggle,
        inputs=[components['checkbox_conv_cloisonne_enable']],
        outputs=[
            components['checkbox_conv_relief_mode'],
            components['slider_conv_relief_height'],
            components['accordion_conv_auto_height']
        ]
    )

    # ========== Sorting Rule Radio Change Handler ==========
    def on_height_mode_change(mode: str):
        """切换排列规则时，控制高度图上传区和一键生成按钮的显隐，并清除残留值。"""
        if mode == "根据高度图":
            return (
                gr.update(visible=True),    # row_conv_heightmap - 显示高度图上传区
                gr.update(visible=False),   # btn_conv_auto_height_apply - 隐藏一键生成按钮
                gr.update(visible=False),   # image_conv_heightmap_preview
                gr.update(),                # image_conv_heightmap（不变）
            )
        else:
            return (
                gr.update(visible=False),   # row_conv_heightmap - 隐藏高度图上传区
                gr.update(visible=True),    # btn_conv_auto_height_apply - 显示一键生成按钮
                gr.update(visible=False),   # image_conv_heightmap_preview
                gr.update(value=None),      # image_conv_heightmap（清除）
            )
    
    components['radio_conv_auto_height_mode'].change(
        on_height_mode_change,
        inputs=[components['radio_conv_auto_height_mode']],
        outputs=[
            components['row_conv_heightmap'],
            components['btn_conv_auto_height_apply'],
            components['image_conv_heightmap_preview'],
            components['image_conv_heightmap'],
        ]
    )

    # ========== Heightmap Upload/Clear Handlers ==========
    def on_heightmap_upload(heightmap_path):
        """高度图上传回调 - 验证并显示预览。
        For HEIC/HEIF files, converts to PNG and returns the converted path
        back to the component so the browser can render it.
        """
        if not heightmap_path:
            return on_heightmap_clear()

        # Convert HEIC/HEIF to PNG so the browser can display it
        display_update = gr.update()
        if isinstance(heightmap_path, str):
            ext = os.path.splitext(heightmap_path)[1].lower()
            if ext in ('.heic', '.heif'):
                try:
                    converted = ImagePreprocessor.convert_to_png(heightmap_path)
                    heightmap_path = converted
                    display_update = converted
                except Exception as e:
                    print(f"[HEIC] Heightmap conversion failed: {e}")

        result = HeightmapLoader.load_and_validate(heightmap_path)
        
        if result['success']:
            status_parts = ["✅ 高度图加载成功"]
            if result['original_size']:
                w, h = result['original_size']
                status_parts.append(f"尺寸: {w}x{h}")
            for warn in result['warnings']:
                status_parts.append(warn)
            status_msg = " | ".join(status_parts)
            return (
                gr.update(visible=True, value=result['thumbnail']),
                status_msg,
                display_update,
            )
        else:
            return (
                gr.update(visible=False),
                result['error'],
                display_update,
            )
    
    def on_heightmap_clear():
        """高度图移除回调 - 清除预览。"""
        return (
            gr.update(visible=False, value=None),
            "",
            gr.update(),
        )
    
    components['image_conv_heightmap'].change(
        on_heightmap_upload,
        inputs=[components['image_conv_heightmap']],
        outputs=[
            components['image_conv_heightmap_preview'],
            components['textbox_conv_status'],
            components['image_conv_heightmap'],
        ]
    )
    # ========== END Heightmap Upload/Clear Handlers ==========
    
    def on_color_trigger_sync_ui(selected_hex, highlight_hex, cache, lut_path,
                                 replacement_regions, selected_user_row_id, selected_auto_row_id,
                                 loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle,
                                 enable_relief, height_map, base_thickness):
        from ui.palette_extension import generate_dual_recommendations_html, build_selected_dual_color_html

        if not selected_hex:
            return gr.update(), gr.update(), gr.update(), gr.update(), cache, gr.update(), gr.update(), gr.update()

        q_hex = selected_hex.strip().lower()
        m_hex = (highlight_hex or selected_hex).strip().lower()

        new_cache = cache.copy() if isinstance(cache, dict) else {}
        new_cache['selection_scope'] = 'global'
        new_cache['selected_region_mask'] = None
        new_cache['selected_quantized_hex'] = q_hex
        new_cache['selected_matched_hex'] = m_hex

        if (selected_user_row_id or '').startswith('user::') and replacement_regions:
            rows = []
            for item in replacement_regions or []:
                qv = (item.get('quantized') or item.get('source') or '').lower()
                mv = (item.get('matched') or item.get('source') or '').lower()
                rv = (item.get('replacement') or '').lower()
                if not qv or not rv:
                    continue
                rows.append({'quantized': qv, 'matched': mv, 'replacement': rv, 'mask': item.get('mask')})

            indexed = []
            for idx, row in enumerate(rows):
                rr = dict(row)
                rr['row_id'] = f"user::{rr['quantized']}|{rr['matched']}|{rr['replacement']}|{idx}"
                indexed.append(rr)

            hit = next((r for r in indexed if r.get('row_id') == selected_user_row_id), None)
            mask = hit.get('mask') if isinstance(hit, dict) else None
            if mask is not None:
                new_cache['selection_scope'] = 'region'
                new_cache['selected_region_mask'] = mask

        display, _ = on_highlight_color_change(
            m_hex, new_cache, loop_pos, add_loop, loop_width, loop_length, loop_hole, loop_angle
        )

        rec_html = ""
        try:
            if lut_path and q_hex and m_hex:
                lut_colors = get_lut_color_choices(lut_path)
                rec = _build_dual_recommendations(
                    tuple(int(q_hex[i:i+2], 16) for i in (1, 3, 5)),
                    tuple(int(m_hex[i:i+2], 16) for i in (1, 3, 5)),
                    lut_colors,
                    top_k=10
                )
                rec_html = generate_dual_recommendations_html(rec, lang=lang)
        except Exception as e:
            print(f"[DUAL_RECOMMEND] Failed: {e}")

        display_hex, state_hex = _resolve_click_selection_hexes(new_cache, q_hex)
        selected_html = build_selected_dual_color_html(state_hex, display_hex, lang=lang)
        relief_slider, relief_selected_color, _ = on_color_selected_for_relief(
            state_hex, enable_relief, height_map, base_thickness, new_cache
        )
        return _preview_update(display), selected_html, state_hex, rec_html, new_cache, gr.update(), relief_slider, relief_selected_color

    # Hook into existing color selection event (when user clicks palette swatch or uses color trigger button)
    conv_color_trigger_btn.click(
        fn=on_color_trigger_sync_ui,
        inputs=[
            conv_color_selected_hidden,
            conv_highlight_color_hidden,
            conv_preview_cache,
            conv_lut_path,
            conv_replacement_regions,
            conv_selected_user_row_id,
            conv_selected_auto_row_id,
            conv_loop_pos,
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            components['checkbox_conv_relief_mode'],
            conv_color_height_map,
            components['slider_conv_thickness'],
        ],
        outputs=[
            conv_preview,
            conv_selected_display,
            conv_selected_color,
            conv_dual_recommend_html,
            conv_preview_cache,
            components['textbox_conv_status'],
            components['slider_conv_relief_height'],
            conv_relief_selected_color,
        ]
    )
    
    def on_relief_height_change(new_height, selected_color, height_map):
        """Update height map when slider changes"""
        if selected_color:
            height_map[selected_color] = new_height
            print(f"[Relief] Updated {selected_color} -> {new_height}mm")
        return height_map
    
    components['slider_conv_relief_height'].change(
        on_relief_height_change,
        inputs=[
            components['slider_conv_relief_height'],
            conv_relief_selected_color,
            conv_color_height_map
        ],
        outputs=[conv_color_height_map]
    )
    
    # Auto Height Generator Event Handler
    def on_auto_height_apply(cache, mode, max_relief_height, base_thickness):
        """Generate automatic height mapping based on color luminance using normalization.
        Skip if mode is '根据高度图' (heightmap mode uses uploaded image instead).
        """
        if mode == "根据高度图":
            gr.Info("ℹ️ 当前为高度图模式，请上传高度图后直接点击生成按钮 | Heightmap mode: upload a heightmap and click Generate")
            return gr.update()
        if cache is None:
            gr.Warning("⚠️ 请先生成预览图 | Please generate preview first")
            return {}
        
        # Extract unique colors from the preview cache
        # cache structure: {'preview': img_array, 'matched_rgb': rgb_array, ...}
        if 'matched_rgb' not in cache:
            gr.Warning("⚠️ 预览数据不完整 | Preview data incomplete")
            return {}
        
        matched_rgb = cache['matched_rgb']
        
        # Extract unique colors using mask_solid for background detection
        # instead of hardcoded (0,0,0) skip
        mask_solid: np.ndarray | None = cache.get('mask_solid')
        unique_colors: set[str] = set()
        
        if mask_solid is not None:
            # Vectorized: select only solid (non-background) pixels
            solid_pixels = matched_rgb[mask_solid]  # shape: (N, 3)
            if solid_pixels.size > 0:
                unique_rgb = np.unique(solid_pixels, axis=0)
                for r, g, b in unique_rgb:
                    unique_colors.add(f'#{r:02x}{g:02x}{b:02x}')
        else:
            # Fallback: no mask_solid available, collect all colors (no black skip)
            h, w = matched_rgb.shape[:2]
            flat_pixels = matched_rgb.reshape(-1, 3)
            unique_rgb = np.unique(flat_pixels, axis=0)
            for r, g, b in unique_rgb:
                unique_colors.add(f'#{r:02x}{g:02x}{b:02x}')
        
        if not unique_colors:
            gr.Warning("⚠️ 未找到有效颜色 | No valid colors found")
            return {}
        
        color_list = list(unique_colors)
        
        # Generate height map using the normalized algorithm
        new_height_map = generate_auto_height_map(color_list, mode, base_thickness, max_relief_height)
        
        gr.Info(f"✅ 已根据颜色明度自动生成 {len(new_height_map)} 个颜色的归一化高度！您可以继续点击单个颜色进行微调。")
        
        return new_height_map
    
    components['btn_conv_auto_height_apply'].click(
        on_auto_height_apply,
        inputs=[
            conv_preview_cache,
            components['radio_conv_auto_height_mode'],
            components['slider_conv_auto_height_max'],
            components['slider_conv_thickness']
        ],
        outputs=[conv_color_height_map]
    )
    # ========== END Relief Mode Event Handlers ==========
    
    # Wrapper function for 3MF generation
    def generate_with_auto_preview(batch_files, is_batch, single_image, lut_path, target_width_mm,
                                   spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
                                   add_loop, loop_width, loop_length, loop_hole, loop_pos,
                                   modeling_mode, quantize_colors, color_replacements,
                                   separate_backing, enable_relief, color_height_map,
                                   heightmap_path, heightmap_max_height,
                                   enable_cleanup, enable_outline, outline_width,
                                   enable_cloisonne, wire_width_mm, wire_height_mm,
                                   free_color_set, enable_coating, coating_height_mm,
                                   radio_height_mode: str,
                                   preview_cache, theme_is_dark, processed_path=None,
                                   hue_weight: float = 0.0,
                                   progress=gr.Progress()):
        """Generate 3MF directly; preview is generated internally by convert_image_to_3d.
        
        Auto-preview pre-run is intentionally removed: it caused a full duplicate
        image-processing pass (4-35s) with no cache reuse, since preview_cache was
        never forwarded into process_batch_generation. Lower-level caches (O-3
        parse+clip, O-4 SVG raster) already prevent redundant work when the user
        runs preview before clicking this button.
        """
        # When SVG was uploaded, image_conv_image_label holds a PNG thumbnail while
        # preprocess_processed_path holds the original SVG. Use SVG for the converter.
        if processed_path and isinstance(processed_path, str) and processed_path.lower().endswith('.svg'):
            single_image = processed_path
        # Resolve UI radio value to backend height_mode parameter
        height_mode = resolve_height_mode(radio_height_mode)

        progress(0.0, desc="开始生成... | Starting...")
        return process_batch_generation(
            batch_files, is_batch, single_image, lut_path, target_width_mm,
            spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
            add_loop, loop_width, loop_length, loop_hole, loop_pos,
            modeling_mode, quantize_colors, color_replacements,
            separate_backing, enable_relief, color_height_map,
            height_mode,
            heightmap_path, heightmap_max_height,
            enable_cleanup, enable_outline, outline_width,
            enable_cloisonne, wire_width_mm, wire_height_mm,
            free_color_set, enable_coating, coating_height_mm,
            hue_weight=float(hue_weight) if hue_weight else 0.0,
            progress=progress,
        )
    
    generate_event = components['btn_conv_generate_btn'].click(
            fn=generate_with_auto_preview,
            inputs=[
                components['file_conv_batch_input'],
                components['checkbox_conv_batch_mode'],
                components['image_conv_image_label'],
                conv_lut_path,
                components['slider_conv_width'],
                components['slider_conv_thickness'],
                components['radio_conv_structure'],
                components['checkbox_conv_auto_bg'],
                components['slider_conv_tolerance'],
                components['radio_conv_color_mode'],
                components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'],
                components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'],
                conv_loop_pos,
                components['radio_conv_modeling_mode'],
                components['slider_conv_quantize_colors'],
                conv_replacement_regions,
                components['checkbox_conv_separate_backing'],
                components['checkbox_conv_relief_mode'],
                conv_color_height_map,
                components['image_conv_heightmap'],
                components['slider_conv_auto_height_max'],
                components['checkbox_conv_cleanup'],
                components['checkbox_conv_outline_enable'],
                components['slider_conv_outline_width'],
                components['checkbox_conv_cloisonne_enable'],
                components['slider_conv_wire_width'],
                components['slider_conv_wire_height'],
                conv_free_color_set,
                components['checkbox_conv_coating_enable'],
                components['slider_conv_coating_height'],
                components['radio_conv_auto_height_mode'],
                conv_preview_cache,
                theme_state,
                preprocess_processed_path,
                components['slider_conv_hue_weight'],
            ],
            outputs=[
                components['file_conv_download_file'],
                conv_3d_preview,
                conv_preview,
                components['textbox_conv_status'],
                components['file_conv_color_recipe']
            ]
    )
    components['conv_event'] = generate_event
    components['btn_conv_stop'].click(
        fn=None,
        inputs=None,
        outputs=None,
        cancels=[generate_event, preview_event]
    )
    components['state_conv_lut_path'] = conv_lut_path

    # ========== Slicer Integration Events ==========
    # Each slicer button binds directly to on_open_slicer_click with its slicer_id

    # ========== Invalidate cached 3MF when any generation parameter changes ==========
    # When user changes image, dimensions, color mode, modeling mode, or any other
    # parameter that affects the output, clear the cached 3MF file so the slicer
    # button will trigger a fresh generation instead of opening the stale model.
    _invalidate_fn = lambda: None  # Returns None to clear file component

    _param_components_change = [
        components['slider_conv_width'],
        components['slider_conv_thickness'],
        components['radio_conv_structure'],
        components['checkbox_conv_auto_bg'],
        components['slider_conv_tolerance'],
        components['radio_conv_color_mode'],
        components['radio_conv_modeling_mode'],
        components['slider_conv_quantize_colors'],
        components['checkbox_conv_loop_enable'],
        components['slider_conv_loop_width'],
        components['slider_conv_loop_length'],
        components['slider_conv_loop_hole'],
        components['checkbox_conv_separate_backing'],
        components['checkbox_conv_relief_mode'],
        components['checkbox_conv_cleanup'],
        components['checkbox_conv_outline_enable'],
        components['slider_conv_outline_width'],
        components['checkbox_conv_cloisonne_enable'],
        components['slider_conv_wire_width'],
        components['slider_conv_wire_height'],
        components['checkbox_conv_coating_enable'],
        components['slider_conv_coating_height'],
        components['slider_conv_auto_height_max'],
        components['radio_conv_auto_height_mode'],
    ]

    for comp in _param_components_change:
        comp.change(
            fn=_invalidate_fn,
            inputs=None,
            outputs=[components['file_conv_download_file']]
        )

    def on_open_slicer_click(slicer_id, file_obj, batch_files, is_batch, single_image, lut_path,
                            target_width_mm, spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
                            add_loop, loop_width, loop_length, loop_hole, loop_pos,
                            modeling_mode, quantize_colors, color_replacements,
                            separate_backing, enable_relief, color_height_map,
                            heightmap_path, heightmap_max_height,
                            enable_cleanup, enable_outline, outline_width,
                            enable_cloisonne, wire_width_mm, wire_height_mm,
                            free_color_set, enable_coating, coating_height_mm,
                            radio_height_mode: str,
                            preview_cache, theme_is_dark, processed_path=None,
                            hue_weight: float = 0.0):
        """Open file in slicer with auto-generation if needed."""
        
        # When SVG was uploaded, image_conv_image_label holds a PNG thumbnail while
        # preprocess_processed_path holds the original SVG. Use SVG for the converter.
        if processed_path and isinstance(processed_path, str) and processed_path.lower().endswith('.svg'):
            single_image = processed_path

        # Initialize color_recipe_path to avoid UnboundLocalError
        color_recipe_path = None
        
        # Resolve UI radio value to backend height_mode parameter
        height_mode = resolve_height_mode(radio_height_mode)
        
        # If no file exists, auto-generate the complete workflow
        if file_obj is None:
            print("[AUTO-SLICER] No 3MF file found, starting auto-generation workflow...")
            
            # Step 1: Generate preview if needed
            if preview_cache is None or not preview_cache:
                print("[AUTO-SLICER] Step 1/2: Generating preview...")
                try:
                    preview_img, cache, status, glb = generate_preview_cached_with_fit(
                        single_image, lut_path, target_width_mm, auto_bg, bg_tol,
                        color_mode, modeling_mode, quantize_colors, enable_cleanup, theme_is_dark
                    )
                    preview_cache = cache
                    print(f"[AUTO-SLICER] Preview generated: {status}")
                except Exception as e:
                    print(f"[AUTO-SLICER] Failed to generate preview: {e}")
                    return gr.update(), gr.update(), gr.update(), gr.update(), f"[ERROR] 预览生成失败: {e}"
            
            # Step 2: Generate 3MF model
            print("[AUTO-SLICER] Step 2/2: Generating 3MF model...")
            try:
                file_obj, glb, preview_img, status, color_recipe_path = process_batch_generation(
                    batch_files, is_batch, single_image, lut_path, target_width_mm,
                    spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
                    add_loop, loop_width, loop_length, loop_hole, loop_pos,
                    modeling_mode, quantize_colors, color_replacements,
                    separate_backing, enable_relief, color_height_map,
                    height_mode,
                    heightmap_path, heightmap_max_height,
                    enable_cleanup, enable_outline, outline_width,
                    enable_cloisonne, wire_width_mm, wire_height_mm,
                    free_color_set, enable_coating, coating_height_mm,
                    hue_weight=float(hue_weight) if hue_weight else 0.0,
                )
                print(f"[AUTO-SLICER] 3MF generated: {status}")
            except Exception as e:
                print(f"[AUTO-SLICER] Failed to generate 3MF: {e}")
                return gr.update(), gr.update(), gr.update(), gr.update(), f"[ERROR] 3MF生成失败: {e}"
        
        # Now open in slicer or download
        if slicer_id == "download":
            # Make file component visible so user can download
            if file_obj is not None:
                return file_obj, gr.update(visible=True), color_recipe_path, gr.update(visible=True), "📥 请点击下方文件下载"
            return None, gr.update(), gr.update(), gr.update(), "[ERROR] 没有可下载的文件"
        
        # Get actual file path from Gradio File object
        actual_path = None
        if file_obj is not None:
            if hasattr(file_obj, 'name'):
                actual_path = file_obj.name
            elif isinstance(file_obj, str):
                actual_path = file_obj
        
        if not actual_path:
            return None, gr.update(), gr.update(), gr.update(), "[ERROR] 生成失败，无法打开"
        
        status = open_in_slicer(actual_path, slicer_id)
        return file_obj, gr.update(), color_recipe_path, gr.update(), status

    # Bind each slicer button to the same handler with its own slicer_id
    _slicer_common_inputs = [
        # All generation parameters
        components['file_conv_batch_input'],
        components['checkbox_conv_batch_mode'],
        components['image_conv_image_label'],
        conv_lut_path,
        components['slider_conv_width'],
        components['slider_conv_thickness'],
        components['radio_conv_structure'],
        components['checkbox_conv_auto_bg'],
        components['slider_conv_tolerance'],
        components['radio_conv_color_mode'],
        components['checkbox_conv_loop_enable'],
        components['slider_conv_loop_width'],
        components['slider_conv_loop_length'],
        components['slider_conv_loop_hole'],
        conv_loop_pos,
        components['radio_conv_modeling_mode'],
        components['slider_conv_quantize_colors'],
        conv_replacement_regions,
        components['checkbox_conv_separate_backing'],
        components['checkbox_conv_relief_mode'],
        conv_color_height_map,
        components['image_conv_heightmap'],
        components['slider_conv_auto_height_max'],
        components['checkbox_conv_cleanup'],
        components['checkbox_conv_outline_enable'],
        components['slider_conv_outline_width'],
        components['checkbox_conv_cloisonne_enable'],
        components['slider_conv_wire_width'],
        components['slider_conv_wire_height'],
        conv_free_color_set,
        components['checkbox_conv_coating_enable'],
        components['slider_conv_coating_height'],
        components['radio_conv_auto_height_mode'],
        conv_preview_cache,
        theme_state,
        preprocess_processed_path,
        components['slider_conv_hue_weight'],
    ]
    _slicer_common_outputs = [
        components['file_conv_download_file'],
        components['file_conv_download_file'],
        components['file_conv_color_recipe'],
        conv_3d_preview,
        components['textbox_conv_status']
    ]

    for _label, _sid in _get_slicer_choices(lang):
        _btn_key = f'btn_conv_slicer_{_sid}'
        _btn = components.get(_btn_key)
        if _btn is not None:
            # Create closure to capture slicer_id
            _make_fn = lambda sid=_sid: (lambda *args: on_open_slicer_click(sid, *args))
            _btn.click(
                fn=_make_fn(_sid),
                inputs=[components['file_conv_download_file']] + _slicer_common_inputs,
                outputs=_slicer_common_outputs,
            )

    # ========== Fullscreen 3D Toggle Events ==========
    components['btn_conv_3d_fullscreen'].click(
        fn=lambda glb, preview_img: (
            gr.update(visible=True),   # show fullscreen 3D
            glb,                        # load GLB into fullscreen
            gr.update(visible=True),   # show 2D thumbnail
            preview_img                 # load 2D preview into thumbnail
        ),
        inputs=[conv_3d_preview, conv_preview],
        outputs=[
            components['col_conv_3d_fullscreen'],
            conv_3d_fullscreen,
            components['col_conv_2d_thumbnail'],
            conv_2d_thumb_preview
        ]
    )

    components['btn_conv_2d_back'].click(
        fn=lambda: (gr.update(visible=False), gr.update(visible=False)),
        inputs=[],
        outputs=[components['col_conv_3d_fullscreen'], components['col_conv_2d_thumbnail']]
    )

    components['btn_conv_3d_back'].click(
        fn=lambda: (gr.update(visible=False), gr.update(visible=False)),
        inputs=[],
        outputs=[components['col_conv_3d_fullscreen'], components['col_conv_2d_thumbnail']]
    )

    # ========== Bed Size Change → Re-render Preview ==========
    def on_bed_size_change(cache, bed_label, loop_pos, add_loop,
                           loop_width, loop_length, loop_hole, loop_angle):
        if cache is None:
            return gr.update(), cache
        preview_rgba = cache.get('preview_rgba')
        if preview_rgba is None:
            return gr.update(), cache
        # Store bed_label in cache so click handler can use it
        cache['bed_label'] = bed_label
        color_conf = cache['color_conf']
        is_dark = cache.get('is_dark', True)
        display = render_preview(
            preview_rgba,
            loop_pos if add_loop else None,
            loop_width, loop_length, loop_hole, loop_angle,
            add_loop, color_conf,
            bed_label=bed_label,
            target_width_mm=cache.get('target_width_mm'),
            is_dark=is_dark
        )
        return _preview_update(display), cache

    components['radio_conv_bed_size'].change(
        fn=on_bed_size_change,
        inputs=[
            conv_preview_cache,
            components['radio_conv_bed_size'],
            conv_loop_pos,
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle']
        ],
        outputs=[conv_preview, conv_preview_cache]
    )

    # Expose internal state refs for theme toggle in create_app
    components['_conv_preview'] = conv_preview
    components['_conv_preview_cache'] = conv_preview_cache
    components['_conv_3d_preview'] = conv_3d_preview

    return components

