# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Tab Image/LUT/Mode Event Bindings
Extracted from converter_tab.py (original lines 1039-1593).
Binds all image upload, LUT selection, crop modal, color detection,
modeling mode, and preview button event handlers.
"""

import re
import xml.etree.ElementTree as ET

import gradio as gr

from config import ModelingMode
from core.image_preprocessor import ImagePreprocessor
from core.converter import detect_image_type
from ...callbacks import on_lut_select, on_lut_upload_save, on_preview_generated_update_palette
from ...settings import (
    _load_user_settings, _save_user_setting,
    save_last_lut_setting, save_color_mode, save_modeling_mode,
)
from ...image_helpers import init_dims, calc_height_from_width, calc_width_from_height
from .helpers import (
    generate_preview_cached_with_fit,
    _update_lut_grid,
    _detect_and_enforce_structure,
)


def bind_image_events(components, states):
    """Bind all image/LUT/mode event handlers.

    Args:
        components: Dict of Gradio UI components keyed by name.
        states: Dict of Gradio state components keyed by name.
    """

    # ==================== Batch mode toggle ====================
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

    # ==================== Crop checkbox preference ====================
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

    # ==================== SVG dimension parser ====================
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

    # ==================== Image upload handler ====================
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
            # Render the SVG to a temp PNG for display in gr.Image, while keeping the
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
        outputs=[states['preprocess_img_width'], states['preprocess_img_height'], states['preprocess_processed_path'], states['preprocess_dimensions_html'], components['image_conv_image_label']]
    ).then(
        fn=None,
        inputs=None,
        outputs=None,
        js=open_crop_modal_js
    )

    # ==================== Use original image (no crop) ====================
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

    states['use_original_btn'].click(
        use_original_image_simple,
        inputs=[states['preprocess_processed_path'], states['preprocess_img_width'], states['preprocess_img_height'], states['crop_data_json']],
        outputs=[components['image_conv_image_label']]
    )

    # ==================== Confirm crop image ====================
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

    states['confirm_crop_btn'].click(
        confirm_crop_image_simple,
        inputs=[states['preprocess_processed_path'], states['crop_data_json']],
        outputs=[components['image_conv_image_label']]
    )

    # ==================== Auto Color Detection Button ====================
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
                    msg = '💡 色彩细节已设置为 <b>' + recommended + '</b>（最大安全值: ' + maxSafe + '）';
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
    # ==================== END Auto Color Detection ====================

    # ==================== LUT dropdown change ====================
    components['dropdown_conv_lut_dropdown'].change(
            on_lut_select,
            inputs=[components['dropdown_conv_lut_dropdown']],
            outputs=[states['conv_lut_path'], components['md_conv_lut_status']]
    ).then(
            fn=save_last_lut_setting,
            inputs=[components['dropdown_conv_lut_dropdown']],
            outputs=None
    ).then(
            fn=_update_lut_grid,
            inputs=[states['conv_lut_path'], states['conv_palette_mode']],
            outputs=[components['conv_lut_grid_view']]
    ).then(
            fn=_detect_and_enforce_structure,
            inputs=[states['conv_lut_path']],
            outputs=[components['radio_conv_color_mode'], components['radio_conv_structure'], components['checkbox_conv_relief_mode']]
    )

    # ==================== LUT file upload ====================
    states['conv_lut_upload'].upload(
            on_lut_upload_save,
            inputs=[states['conv_lut_upload']],
            outputs=[components['dropdown_conv_lut_dropdown'], components['md_conv_lut_status']]
    ).then(
            fn=lambda: gr.update(),
            outputs=[components['dropdown_conv_lut_dropdown']]
    ).then(
            fn=lambda lut_file: _detect_and_enforce_structure(lut_file.name if lut_file else None),
            inputs=[states['conv_lut_upload']],
            outputs=[components['radio_conv_color_mode'], components['radio_conv_structure'], components['checkbox_conv_relief_mode']]
    )

    # ==================== Image change → init dims + detect type ====================
    components['image_conv_image_label'].change(
            fn=init_dims,
            inputs=[components['image_conv_image_label']],
            outputs=[components['slider_conv_width'], states['conv_target_height_mm']]
    ).then(
            # 自动检测图像类型并切换建模模式
            # 使用 preprocess_processed_path 而非 image_conv_image_label，
            # 因为 SVG 上传后 image_conv_image_label 存的是 PNG 缩略图，
            # 只有 preprocess_processed_path 保留原始 SVG 路径。
            fn=detect_image_type,
            inputs=[states['preprocess_processed_path']],
            outputs=[components['radio_conv_modeling_mode']]
    ).then(
            # 清空已生成的 3MF 文件，强制下次点击切片按钮时重新生成
            fn=lambda: None,
            inputs=None,
            outputs=[components['file_conv_download_file']]
    )

    # ==================== Width / Height linkage ====================
    components['slider_conv_width'].input(
            fn=calc_height_from_width,
            inputs=[components['slider_conv_width'], components['image_conv_image_label']],
            outputs=[states['conv_target_height_mm']]
    )
    states['conv_target_height_mm'].input(
            fn=calc_width_from_height,
            inputs=[states['conv_target_height_mm'], components['image_conv_image_label']],
            outputs=[components['slider_conv_width']]
    )

    # ==================== Modeling mode change ====================
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

    # ==================== Color mode change ====================
    # Save color mode when changed
    components['radio_conv_color_mode'].change(
        fn=save_color_mode,
        inputs=[components['radio_conv_color_mode']],
        outputs=None
    )

    # ==================== Persist additional settings ====================
    # Structure mode
    components['radio_conv_structure'].change(
        fn=lambda v: _save_user_setting("last_structure", v),
        inputs=[components['radio_conv_structure']],
        outputs=None
    )

    # Width / Height / Thickness
    for _comp_key, _setting_key in [
        ('slider_conv_width', 'last_width'),
        ('slider_conv_height', 'last_height'),
        ('slider_conv_thickness', 'last_thickness'),
    ]:
        components[_comp_key].change(
            fn=lambda v, k=_setting_key: _save_user_setting(k, v),
            inputs=[components[_comp_key]],
            outputs=None
        )

    # Advanced settings
    components['slider_conv_quantize_colors'].change(
        fn=lambda v: _save_user_setting("last_quantize_colors", v),
        inputs=[components['slider_conv_quantize_colors']],
        outputs=None
    )
    components['slider_conv_tolerance'].change(
        fn=lambda v: _save_user_setting("last_tolerance", v),
        inputs=[components['slider_conv_tolerance']],
        outputs=None
    )
    components['checkbox_conv_auto_bg'].change(
        fn=lambda v: _save_user_setting("last_auto_bg", v),
        inputs=[components['checkbox_conv_auto_bg']],
        outputs=None
    )
    components['checkbox_conv_cleanup'].change(
        fn=lambda v: _save_user_setting("last_cleanup", v),
        inputs=[components['checkbox_conv_cleanup']],
        outputs=None
    )
    components['checkbox_conv_separate_backing'].change(
        fn=lambda v: _save_user_setting("last_separate_backing", v),
        inputs=[components['checkbox_conv_separate_backing']],
        outputs=None
    )
    components['slider_conv_hue_weight'].change(
        fn=lambda v: _save_user_setting("last_hue_weight", v),
        inputs=[components['slider_conv_hue_weight']],
        outputs=None
    )

    # Outline settings
    components['checkbox_conv_outline_enable'].change(
        fn=lambda v: _save_user_setting("last_outline_enable", v),
        inputs=[components['checkbox_conv_outline_enable']],
        outputs=None
    )
    components['slider_conv_outline_width'].change(
        fn=lambda v: _save_user_setting("last_outline_width", v),
        inputs=[components['slider_conv_outline_width']],
        outputs=None
    )

    # Cloisonné settings
    components['checkbox_conv_cloisonne_enable'].change(
        fn=lambda v: _save_user_setting("last_cloisonne_enable", v),
        inputs=[components['checkbox_conv_cloisonne_enable']],
        outputs=None
    )
    components['slider_conv_wire_width'].change(
        fn=lambda v: _save_user_setting("last_wire_width", v),
        inputs=[components['slider_conv_wire_width']],
        outputs=None
    )
    components['slider_conv_wire_height'].change(
        fn=lambda v: _save_user_setting("last_wire_height", v),
        inputs=[components['slider_conv_wire_height']],
        outputs=None
    )

    # Coating settings
    components['checkbox_conv_coating_enable'].change(
        fn=lambda v: _save_user_setting("last_coating_enable", v),
        inputs=[components['checkbox_conv_coating_enable']],
        outputs=None
    )
    components['slider_conv_coating_height'].change(
        fn=lambda v: _save_user_setting("last_coating_height", v),
        inputs=[components['slider_conv_coating_height']],
        outputs=None
    )

    def _on_color_mode_update_structure(color_mode):
        """5-Color Extended requires single-sided face-up (max 4 materials per Z layer).
        Also disables 2.5D relief mode which is incompatible with 5-Color Extended.
        """
        if color_mode and "5-Color Extended" in color_mode:
            return gr.update(
                value='single',
                interactive=False,
            ), gr.update(value=False, interactive=False)
        return gr.update(interactive=True), gr.update(interactive=True)

    components['radio_conv_color_mode'].change(
        fn=_on_color_mode_update_structure,
        inputs=[components['radio_conv_color_mode']],
        outputs=[components['radio_conv_structure'], components['checkbox_conv_relief_mode']],
    )

    # ==================== Preview button click ====================
    preview_event = components['btn_conv_preview_btn'].click(
            generate_preview_cached_with_fit,
            inputs=[
                components['image_conv_image_label'],
                states['conv_lut_path'],
                components['slider_conv_width'],
                components['checkbox_conv_auto_bg'],
                components['slider_conv_tolerance'],
                components['radio_conv_color_mode'],
                components['radio_conv_modeling_mode'],
                components['slider_conv_quantize_colors'],
                components['checkbox_conv_cleanup'],
                states['theme_state'],
                states['preprocess_processed_path'],
                components['slider_conv_hue_weight'],
                components['radio_conv_structure'],
            ],
            outputs=[states['conv_preview'], states['conv_preview_cache'], components['textbox_conv_status'], states['conv_3d_preview']]
    ).then(
            on_preview_generated_update_palette,
            inputs=[states['conv_preview_cache']],
            outputs=[states['conv_palette_html'], states['conv_selected_color']]
    ).then(
            fn=lambda: (None, None),
            inputs=[],
            outputs=[states['conv_selected_user_row_id'], states['conv_selected_auto_row_id']]
    )

    states['preview_event'] = preview_event
    return preview_event
