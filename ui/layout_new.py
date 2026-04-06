# -*- coding: utf-8 -*-
"""
Lumina Studio - UI Layout (Refactored with i18n)
UI layout definition - Refactored version with language switching support
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
    generate_preview_cached,
    generate_realtime_glb,
    generate_empty_bed_glb,
    render_preview,
    update_preview_with_loop,
    on_remove_loop,
    generate_final_model,
    on_preview_click_select_color,
    generate_lut_grid_html,
    generate_lut_card_grid_html,
    detect_lut_color_mode,
    detect_image_type,
    generate_auto_height_map,
    _build_dual_recommendations,
    _resolve_click_selection_hexes,
    get_lut_color_choices,
)
from core.heightmap_loader import HeightmapLoader
from .styles import CUSTOM_CSS
from .callbacks import (
    on_lut_select,
    on_lut_upload_save,
    on_apply_color_replacement,
    on_clear_color_replacements,
    on_undo_color_replacement,
    on_preview_generated_update_palette,
    on_delete_selected_user_replacement,
    on_highlight_color_change,
    on_clear_highlight,
    on_merge_preview,
    on_merge_apply,
    on_merge_revert,
)
from .settings import (
    load_last_lut_setting, save_last_lut_setting,
    _load_user_settings, _save_user_setting,
    save_color_mode, save_modeling_mode,
    resolve_height_mode, CONFIG_FILE,
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
    _get_image_size, calc_height_from_width,
    calc_width_from_height, init_dims,
    _scale_preview_image, _preview_update,
)
from .i18n_helpers import (
    _get_header_html, _get_stats_html, _get_footer_html,
    _get_all_component_updates, _get_component_list,
)
from .helpers import _format_bytes

# Supported image file types for Gradio upload components.
# Centralized list so that adding a new format only requires one change.
SUPPORTED_IMAGE_FILE_TYPES: list[str] = [
    ".jpg", ".jpeg", ".png", ".bmp",
    ".gif", ".webp", ".heic", ".heif",
]

# Runtime-injected i18n keys (avoids editing core/i18n.py).
if hasattr(I18n, 'TEXTS'):
    I18n.TEXTS.update({
        'conv_advanced': {'zh': '🛠️ 高级设置', 'en': '🛠️ Advanced Settings'},
        'conv_stop':     {'zh': '🛑 停止生成', 'en': '🛑 Stop Generation'},
        'conv_batch_mode':      {'zh': '📦 批量模式', 'en': '📦 Batch Mode'},
        'conv_batch_mode_info': {'zh': '一次生成多个模型 (参数共享)', 'en': 'Generate multiple models (Shared Settings)'},
        'conv_batch_input':     {'zh': '📤 批量上传图片', 'en': '📤 Batch Upload Images'},
        'conv_lut_status': {'zh': '💡 拖放.npy文件自动添加', 'en': '💡 Drop .npy file to load'},
    })

from .converter_tab import (
    create_converter_tab_content,
    process_batch_generation,
    _update_lut_grid,
    _detect_and_enforce_structure,
)



def create_app():
    """Build the Gradio app (tabs, i18n, events) and return the Blocks instance."""
    with gr.Blocks(title="Lumina Studio") as app:
        # Inject CSS styles via HTML component (for Gradio 4.20.0 compatibility)
        from ui.styles import CUSTOM_CSS
        gr.HTML(f"<style>{CUSTOM_CSS + HEADER_CSS + LUT_GRID_CSS}</style>")
        
        lang_state = gr.State(value="zh")
        theme_state = gr.State(value=False)  # False=light, True=dark

        # Header + Stats merged into one row
        with gr.Row(elem_classes=["header-row"], equal_height=True):
            with gr.Column(scale=6):
                app_title_html = gr.HTML(
                    value=f"<h1>✨ Lumina Studio</h1><p>{I18n.get('app_subtitle', 'zh')}</p>",
                    elem_id="app-header"
                )
            with gr.Column(scale=4):
                stats = Stats.get_all()
                stats_html = gr.HTML(
                    value=_get_stats_html("zh", stats),
                    elem_classes=["stats-bar-inline"]
                )
            with gr.Column(scale=1, min_width=140, elem_classes=["header-controls"]):
                lang_btn = gr.Button(
                    value="🌐 English",
                    size="sm",
                    elem_id="lang-btn"
                )
                theme_btn = gr.Button(
                    value=I18n.get('theme_toggle_night', "zh"),
                    size="sm",
                    elem_id="theme-btn"
                )
        
        # Global scripts for crop modal - using a different approach for Gradio 4.20.0
        # Store script in a hidden element and execute it
        gr.HTML("""
<div id="crop-scripts-loader" style="display:none;">
<textarea id="crop-script-content" style="display:none;">
window.cropper = null;
window.originalImageData = null;

function hideCropHelperComponents() {
    ['crop-data-json', 'use-original-hidden-btn', 'confirm-crop-hidden-btn'].forEach(function(id) {
        var el = document.getElementById(id);
        if (el) {
            el.style.cssText = 'position:absolute!important;left:-9999px!important;top:-9999px!important;width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;visibility:hidden!important;';
        }
    });
}
document.addEventListener('DOMContentLoaded', function() { setTimeout(hideCropHelperComponents, 500); });
setInterval(hideCropHelperComponents, 2000);

window.updateCropDataJson = function(x, y, w, h) {
    var jsonData = JSON.stringify({x: x, y: y, w: w, h: h});
    var container = document.getElementById('crop-data-json');
    if (!container) {
        console.error('crop-data-json element not found');
        return;
    }
    var textarea = container.querySelector('textarea');
    if (textarea) {
        textarea.value = jsonData;
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
        textarea.dispatchEvent(new Event('change', { bubbles: true }));
        console.log('Updated crop data JSON:', jsonData);
    } else {
        console.error('textarea not found in crop-data-json');
    }
};

window.clickGradioButton = function(elemId) {
    var elem = document.getElementById(elemId);
    if (!elem) {
        console.error('clickGradioButton: element not found:', elemId);
        return;
    }
    var btn = elem.querySelector('button') || elem;
    if (btn && btn.tagName === 'BUTTON') {
        btn.click();
        console.log('Clicked button:', elemId);
    } else {
        console.error('Button element not found for:', elemId);
    }
};

window.openCropModal = function(imageSrc, width, height) {
    console.log('openCropModal called:', imageSrc ? imageSrc.substring(0, 50) + '...' : 'null', width, height);
    window.originalImageData = { src: imageSrc, width: width, height: height };
    
    var origSizeEl = document.getElementById('crop-original-size');
    if (origSizeEl) {
        var prefix = origSizeEl.dataset.prefix || 'Size';
        origSizeEl.textContent = prefix + ': ' + width + ' × ' + height + ' px';
    }
    
    var img = document.getElementById('crop-image');
    if (!img) { console.error('crop-image element not found'); return; }
    img.src = imageSrc;
    
    var overlay = document.getElementById('crop-modal-overlay');
    if (overlay) overlay.style.display = 'flex';
    
    img.onload = function() {
        if (window.cropper) window.cropper.destroy();
        window.cropper = new Cropper(img, {
            viewMode: 1, dragMode: 'crop', autoCropArea: 1, responsive: true,
            crop: function(event) {
                var data = event.detail;
                var cropX = document.getElementById('crop-x');
                var cropY = document.getElementById('crop-y');
                var cropW = document.getElementById('crop-width');
                var cropH = document.getElementById('crop-height');
                var selSize = document.getElementById('crop-selection-size');
                if (cropX) cropX.value = Math.round(data.x);
                if (cropY) cropY.value = Math.round(data.y);
                if (cropW) cropW.value = Math.round(data.width);
                if (cropH) cropH.value = Math.round(data.height);
                if (selSize) {
                    var prefix = selSize.dataset.prefix || 'Selection';
                    selSize.textContent = prefix + ': ' + Math.round(data.width) + ' × ' + Math.round(data.height) + ' px';
                }
            }
        });
    };
};

window.closeCropModal = function() {
    var overlay = document.getElementById('crop-modal-overlay');
    if (overlay) overlay.style.display = 'none';
    if (window.cropper) { window.cropper.destroy(); window.cropper = null; }
};

window.updateCropperFromInputs = function() {
    if (!window.cropper) return;
    window.cropper.setData({
        x: parseInt(document.getElementById('crop-x').value) || 0,
        y: parseInt(document.getElementById('crop-y').value) || 0,
        width: parseInt(document.getElementById('crop-width').value) || 100,
        height: parseInt(document.getElementById('crop-height').value) || 100
    });
};

window.useOriginalImage = function() {
    if (!window.originalImageData) return;
    window.updateCropDataJson(0, 0, window.originalImageData.width, window.originalImageData.height);
    window.closeCropModal();
    setTimeout(function() { window.clickGradioButton('use-original-hidden-btn'); }, 100);
};

window.confirmCrop = function() {
    if (!window.cropper) return;
    var data = window.cropper.getData(true);
    console.log('confirmCrop data:', data);
    window.updateCropDataJson(Math.round(data.x), Math.round(data.y), Math.round(data.width), Math.round(data.height));
    window.closeCropModal();
    setTimeout(function() { window.clickGradioButton('confirm-crop-hidden-btn'); }, 100);
};

window.setCropRatio = function(ratio, btn) {
    if (!window.cropper) return;
    document.querySelectorAll('.crop-ratio-btn').forEach(function(b) { b.classList.remove('active'); });
    if (btn) btn.classList.add('active');
    window.cropper.setAspectRatio(ratio);
};

console.log('[CROP] Global scripts loaded, openCropModal:', typeof window.openCropModal);
</textarea>
</div>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.css">
<img src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js" onerror="
  var s1 = document.createElement('script');
  s1.src = 'https://cdnjs.cloudflare.com/ajax/libs/jquery/3.7.1/jquery.min.js';
  s1.onload = function() {
    var s2 = document.createElement('script');
    s2.src = 'https://cdnjs.cloudflare.com/ajax/libs/cropperjs/1.6.1/cropper.min.js';
    s2.onload = function() {
      var content = document.getElementById('crop-script-content');
      if (content) {
        var s3 = document.createElement('script');
        s3.textContent = content.value;
        document.head.appendChild(s3);
      }
    };
    document.head.appendChild(s2);
  };
  document.head.appendChild(s1);
" style="display:none;">
""")
        
        tab_components = {}
        with gr.Tabs() as tabs:
            components = {}

            # Converter tab
            with gr.TabItem(label=I18n.get('tab_converter', "zh"), id=0) as tab_conv:
                conv_components = create_converter_tab_content("zh", lang_state, theme_state)
                components.update(conv_components)
            tab_components['tab_converter'] = tab_conv
            
            with gr.TabItem(label=I18n.get('tab_calibration', "zh"), id=1) as tab_cal:
                from .calibration_tab import create_calibration_tab_content
                cal_components = create_calibration_tab_content("zh")
                components.update(cal_components)
            tab_components['tab_calibration'] = tab_cal
            
            with gr.TabItem(label=I18n.get('tab_extractor', "zh"), id=2) as tab_ext:
                from .extractor_tab import create_extractor_tab_content
                ext_components = create_extractor_tab_content("zh")
                components.update(ext_components)
            tab_components['tab_extractor'] = tab_ext
            
            with gr.TabItem(label="🔬 高级 | Advanced", id=3) as tab_advanced:
                advanced_components = create_advanced_tab_content("zh")
                components.update(advanced_components)
            tab_components['tab_advanced'] = tab_advanced
            
            with gr.TabItem(label=I18n.get('tab_merge', "zh"), id=4) as tab_merge:
                from .merge_tab import create_merge_tab_content
                merge_components = create_merge_tab_content("zh", lang_state)
                components.update(merge_components)
            tab_components['tab_merge'] = tab_merge
            
            with gr.TabItem(label="🎨 配色查询 | Color Query", id=5) as tab_5color:
                from ui.fivecolor_tab_v2 import create_5color_tab_v2
                create_5color_tab_v2("zh")
            tab_components['tab_5color'] = tab_5color
            
            with gr.TabItem(label=I18n.get('tab_about', "zh"), id=6) as tab_about:
                about_components = create_about_tab_content("zh")
                components.update(about_components)
            tab_components['tab_about'] = tab_about
        
        footer_html = gr.HTML(
            value=_get_footer_html("zh"),
            elem_id="footer"
        )
        
        def change_language(current_lang, is_dark):
            """Switch UI language and return updates for all i18n components."""
            new_lang = "en" if current_lang == "zh" else "zh"
            updates = []
            updates.append(gr.update(value=I18n.get('lang_btn_zh' if new_lang == "zh" else 'lang_btn_en', new_lang)))
            theme_label = I18n.get('theme_toggle_day', new_lang) if is_dark else I18n.get('theme_toggle_night', new_lang)
            updates.append(gr.update(value=theme_label))
            updates.append(gr.update(value=_get_header_html(new_lang)))
            stats = Stats.get_all()
            updates.append(gr.update(value=_get_stats_html(new_lang, stats)))
            updates.append(gr.update(label=I18n.get('tab_converter', new_lang)))
            updates.append(gr.update(label=I18n.get('tab_calibration', new_lang)))
            updates.append(gr.update(label=I18n.get('tab_extractor', new_lang)))
            updates.append(gr.update(label="🔬 高级 | Advanced" if new_lang == "zh" else "🔬 Advanced"))
            updates.append(gr.update(label=I18n.get('tab_merge', new_lang)))
            updates.append(gr.update(label=I18n.get('tab_about', new_lang)))
            updates.extend(_get_all_component_updates(new_lang, components))
            updates.append(gr.update(value=_get_footer_html(new_lang)))
            updates.append(new_lang)
            return updates

        output_list = [
            lang_btn,
            theme_btn,
            app_title_html,
            stats_html,
            tab_components['tab_converter'],
            tab_components['tab_calibration'],
            tab_components['tab_extractor'],
            tab_components['tab_advanced'],
            tab_components['tab_merge'],
            tab_components['tab_about'],
        ]
        output_list.extend(_get_component_list(components))
        output_list.extend([footer_html, lang_state])

        lang_btn.click(
            change_language,
            inputs=[lang_state, theme_state],
            outputs=output_list
        )

        def _on_theme_toggle(current_is_dark, current_lang, cache):
            """Toggle theme state and re-render preview with new bed colors."""
            new_is_dark = not current_is_dark
            label = I18n.get('theme_toggle_day', current_lang) if new_is_dark else I18n.get('theme_toggle_night', current_lang)

            # Re-render 2D preview with new theme
            new_preview = gr.update()
            if cache is not None:
                cache['is_dark'] = new_is_dark
                preview_rgba = cache.get('preview_rgba')
                if preview_rgba is not None:
                    color_conf = cache.get('color_conf')
                    display = render_preview(
                        preview_rgba, None, 0, 0, 0, 0, False, color_conf,
                        bed_label=cache.get('bed_label'),
                        target_width_mm=cache.get('target_width_mm'),
                        is_dark=new_is_dark
                    )
                    new_preview = _preview_update(display)

            # Re-render 3D preview with new bed theme
            new_glb = gr.update()
            if cache is not None:
                glb_path = generate_realtime_glb(cache)
                if glb_path:
                    new_glb = glb_path

            return new_is_dark, gr.update(value=label), new_preview, new_glb

        theme_btn.click(
            fn=None,
            inputs=None,
            outputs=None,
            js="""() => {
                const body = document.querySelector('body');
                const isDark = body.classList.contains('dark');
                if (isDark) {
                    body.classList.remove('dark');
                } else {
                    body.classList.add('dark');
                }
                // Update URL param without reload
                const url = new URL(window.location.href);
                url.searchParams.set('__theme', isDark ? 'light' : 'dark');
                window.history.replaceState({}, '', url.toString());
                return [];
            }"""
        ).then(
            fn=_on_theme_toggle,
            inputs=[theme_state, lang_state, components['_conv_preview_cache']],
            outputs=[theme_state, theme_btn, components['_conv_preview'], components['_conv_3d_preview']]
        )

        def init_theme(current_lang, request: gr.Request = None):
            theme = None
            try:
                if request is not None:
                    theme = request.query_params.get("__theme")
            except Exception:
                theme = None

            is_dark = theme == "dark"
            label = I18n.get('theme_toggle_day', current_lang) if is_dark else I18n.get('theme_toggle_night', current_lang)
            return is_dark, gr.update(value=label)

        app.load(
            fn=init_theme,
            inputs=[lang_state],
            outputs=[theme_state, theme_btn]
        )

        app.load(
            fn=on_lut_select,
            inputs=[components['dropdown_conv_lut_dropdown']],
            outputs=[components['state_conv_lut_path'], components['md_conv_lut_status']]
        ).then(
            fn=_update_lut_grid,
            inputs=[components['state_conv_lut_path'], lang_state, components['state_conv_palette_mode']],
            outputs=[components['conv_lut_grid_view']]
        ).then(
            fn=_detect_and_enforce_structure,
            inputs=[components['state_conv_lut_path']],
            outputs=[components['radio_conv_color_mode'], components['radio_conv_structure'], components['checkbox_conv_relief_mode']]
        )

        # Settings: cache clearing and counter reset
        def on_clear_cache(lang):
            cache_size_before = Stats.get_cache_size()
            _, _ = Stats.clear_cache()
            cache_size_after = Stats.get_cache_size()
            freed_size = max(cache_size_before - cache_size_after, 0)

            status_msg = I18n.get('settings_cache_cleared', lang).format(_format_bytes(freed_size))
            new_cache_size = I18n.get('settings_cache_size', lang).format(_format_bytes(cache_size_after))
            return status_msg, new_cache_size

        def on_clear_output(lang):
            output_size_before = Stats.get_output_size()
            _, _ = Stats.clear_output()
            output_size_after = Stats.get_output_size()
            freed_size = max(output_size_before - output_size_after, 0)

            status_msg = I18n.get('settings_output_cleared', lang).format(_format_bytes(freed_size))
            new_output_size = I18n.get('settings_output_size', lang).format(_format_bytes(output_size_after))
            return status_msg, new_output_size

        def on_reset_counters(lang):
            Stats.reset_all()
            new_stats = Stats.get_all()

            status_msg = I18n.get('settings_counters_reset', lang).format(
                new_stats.get('calibrations', 0),
                new_stats.get('extractions', 0),
                new_stats.get('conversions', 0)
            )
            return status_msg, _get_stats_html(lang, new_stats)

        # ========== Advanced Tab Events ==========
        def on_unlock_max_size(unlock: bool):
            """Toggle max size limit for width/height sliders."""
            new_max = 9999 if unlock else 400
            return gr.update(maximum=new_max), gr.update(maximum=new_max)

        components['checkbox_unlock_max_size'].change(
            on_unlock_max_size,
            inputs=[components['checkbox_unlock_max_size']],
            outputs=[components['slider_conv_width'], components['slider_conv_height']]
        )

        # ========== About Tab Events ==========
        components['btn_clear_cache'].click(
            fn=on_clear_cache,
            inputs=[lang_state],
            outputs=[components['md_settings_status'], components['md_cache_size']]
        )

        components['btn_clear_output'].click(
            fn=on_clear_output,
            inputs=[lang_state],
            outputs=[components['md_settings_status'], components['md_output_size']]
        )

        components['btn_reset_counters'].click(
            fn=on_reset_counters,
            inputs=[lang_state],
            outputs=[components['md_settings_status'], stats_html]
        )

        def update_stats_bar(lang):
            stats = Stats.get_all()
            return _get_stats_html(lang, stats)

        if 'cal_event' in components:
            components['cal_event'].then(
                fn=update_stats_bar,
                inputs=[lang_state],
                outputs=[stats_html]
            )

        if 'ext_event' in components:
            components['ext_event'].then(
                fn=update_stats_bar,
                inputs=[lang_state],
                outputs=[stats_html]
            )

        if 'conv_event' in components:
            components['conv_event'].then(
                fn=update_stats_bar,
                inputs=[lang_state],
                outputs=[stats_html]
            )

        # Palette mode switch (Advanced tab)
        if 'radio_palette_mode' in components:
            def on_palette_mode_change(mode, lut_path, lang):
                _save_user_setting("palette_mode", mode)
                return mode, _update_lut_grid(lut_path, lang, mode)

            components['radio_palette_mode'].change(
                fn=on_palette_mode_change,
                inputs=[components['radio_palette_mode'],
                        components['state_conv_lut_path'], lang_state],
                outputs=[components['state_conv_palette_mode'],
                         components['conv_lut_grid_view']]
            )

    return app


# ---------- Tab builders ----------




def create_advanced_tab_content(lang: str) -> dict:
    """Build Advanced tab content with independent setting groups.
    独立分组构建高级设置标签页内容。

    Args:
        lang (str): Language code, 'zh' or 'en'. (语言代码)

    Returns:
        dict: Gradio component dictionary. (组件字典)
    """
    components = {}

    # --- Group 1: Palette display mode ---
    with gr.Group():
        palette_label = "调色板样式" if lang == "zh" else "Palette Style"
        palette_swatch = "色块模式" if lang == "zh" else "Swatch Grid"
        palette_card = "色卡模式" if lang == "zh" else "Card Layout"
        saved_mode = _load_user_settings().get("palette_mode", "swatch")
        components['radio_palette_mode'] = gr.Radio(
            choices=[(palette_swatch, "swatch"), (palette_card, "card")],
            value=saved_mode,
            label=palette_label,
        )

    # --- Group 2: Unlock max size limit ---
    with gr.Group():
        unlock_label = "解除最大尺寸限制" if lang == "zh" else "Unlock Max Size Limit"
        unlock_info = "开启后，图像转换的宽度/高度滑块将不再限制最大值（默认上限 400mm）" if lang == "zh" else "When enabled, width/height sliders in Image Converter will have no upper limit (default max 400mm)"
        components['checkbox_unlock_max_size'] = gr.Checkbox(
            label=unlock_label,
            value=False,
            info=unlock_info,
        )

    return components


def create_about_tab_content(lang: str) -> dict:
    """Build About tab content from i18n. Returns component dict."""
    components = {}

    # Settings section
    components['md_settings_title'] = gr.Markdown(I18n.get('settings_title', lang))
    cache_size = Stats.get_cache_size()
    cache_size_str = _format_bytes(cache_size)
    components['md_cache_size'] = gr.Markdown(
        I18n.get('settings_cache_size', lang).format(cache_size_str)
    )
    with gr.Row():
        components['btn_clear_cache'] = gr.Button(
            I18n.get('settings_clear_cache', lang),
            variant="secondary",
            size="sm"
        )
        components['btn_reset_counters'] = gr.Button(
            I18n.get('settings_reset_counters', lang),
            variant="secondary",
            size="sm"
        )
    
    output_size = Stats.get_output_size()
    output_size_str = _format_bytes(output_size)
    components['md_output_size'] = gr.Markdown(
        I18n.get('settings_output_size', lang).format(output_size_str)
    )
    components['btn_clear_output'] = gr.Button(
        I18n.get('settings_clear_output', lang),
        variant="secondary",
        size="sm"
    )
    
    components['md_settings_status'] = gr.Markdown("")
    
    # About page content (from i18n)
    components['md_about_content'] = gr.Markdown(I18n.get('about_content', lang))
    
    return components

