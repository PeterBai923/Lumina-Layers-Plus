# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Tab Left Sidebar
UI construction for the left sidebar (original lines 260-557).
"""

import gradio as gr

from config import ModelingMode
from utils import LUTManager
from core.i18n import I18n
from ...settings import (
    load_last_lut_setting, _load_user_settings,
)
from .helpers import _get_supported_image_file_types


def build_left_sidebar(lang, components, states):
    """Build left sidebar UI components.

    Populates both ``components`` and ``states`` dicts with Gradio references.
    """
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
            states['conv_lut_upload'] = conv_lut_upload

        components['md_conv_lut_status'] = gr.Markdown(
            value=I18n.get('conv_lut_status_default', lang),
            visible=True,
            elem_classes=["lut-status"]
        )

        conv_lut_path = gr.State(None)
        states['conv_lut_path'] = conv_lut_path

        conv_palette_mode = gr.State(value=_load_user_settings().get("palette_mode", "swatch"))
        states['conv_palette_mode'] = conv_palette_mode
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
        states['preprocess_img_width'] = preprocess_img_width
        states['preprocess_img_height'] = preprocess_img_height
        states['preprocess_processed_path'] = preprocess_processed_path

        # Crop data states (used by JavaScript via hidden inputs)
        crop_data_state = gr.State({"x": 0, "y": 0, "w": 100, "h": 100})
        states['crop_data_state'] = crop_data_state

        # Hidden textbox for JavaScript to pass crop data to Python (use CSS to hide)
        crop_data_json = gr.Textbox(
            value='{"x":0,"y":0,"w":100,"h":100,"autoColor":true}',
            elem_id="crop-data-json",
            visible=True,
            elem_classes=["hidden-crop-component"]
        )
        states['crop_data_json'] = crop_data_json

        # Hidden buttons for JavaScript to trigger Python callbacks (use CSS to hide)
        use_original_btn = gr.Button("use_original", elem_id="use-original-hidden-btn", elem_classes=["hidden-crop-component"])
        confirm_crop_btn = gr.Button("confirm_crop", elem_id="confirm-crop-hidden-btn", elem_classes=["hidden-crop-component"])
        states['use_original_btn'] = use_original_btn
        states['confirm_crop_btn'] = confirm_crop_btn

        # Cropper.js Modal HTML (JS is loaded via head parameter in main.py)
        from ui.widgets.crop_modal import get_crop_modal_html
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
        states['preprocess_dimensions_html'] = preprocess_dimensions_html
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
        states['conv_color_height_map'] = conv_color_height_map

        # State to track currently selected color for height adjustment
        conv_relief_selected_color = gr.State(None)
        states['conv_relief_selected_color'] = conv_relief_selected_color
        # ========== END 2.5D Relief Mode Controls ==========

        conv_target_height_mm = components['slider_conv_height']
        states['conv_target_height_mm'] = conv_target_height_mm

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
