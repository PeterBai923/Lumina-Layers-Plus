# -*- coding: utf-8 -*-
"""
Lumina Studio - UI Layout (Refactored with i18n)
UI layout definition - Refactored version with language switching support
"""

import gradio as gr

from core.i18n import I18n
from utils import Stats
from core.converter import generate_realtime_glb, render_preview

from .styles import CUSTOM_CSS
from .callbacks import on_lut_select
from .settings import _save_user_setting
from .assets import HEADER_CSS, LUT_GRID_CSS
from .image_helpers import _preview_update, _format_bytes
from .i18n_helpers import (
    _get_header_html,
    _get_stats_html,
    _get_footer_html,
    _get_all_component_updates,
    _get_component_list,
)

# Supported image file types for Gradio upload components.
# Centralized list so that adding a new format only requires one change.
SUPPORTED_IMAGE_FILE_TYPES: list[str] = [
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".webp",
    ".heic",
    ".heif",
]

# Runtime-injected i18n keys (avoids editing core/i18n.py).
if hasattr(I18n, "TEXTS"):
    I18n.TEXTS.update(
        {
            "conv_advanced": {"zh": "🛠️ 高级设置", "en": "🛠️ Advanced Settings"},
            "conv_stop": {"zh": "🛑 停止生成", "en": "🛑 Stop Generation"},
            "conv_batch_mode": {"zh": "📦 批量模式", "en": "📦 Batch Mode"},
            "conv_batch_mode_info": {
                "zh": "一次生成多个模型 (参数共享)",
                "en": "Generate multiple models (Shared Settings)",
            },
            "conv_batch_input": {
                "zh": "📤 批量上传图片",
                "en": "📤 Batch Upload Images",
            },
            "conv_lut_status": {
                "zh": "💡 拖放.npy文件自动添加",
                "en": "💡 Drop .npy file to load",
            },
        }
    )

from .tabs.converter_tab import (
    create_converter_tab_content,
    _update_lut_grid,
    _detect_and_enforce_structure,
)
from .tabs.advanced_tab import create_advanced_tab_content
from .tabs.about_tab import create_about_tab_content


def create_app():
    """Build the Gradio app (tabs, i18n, events) and return the Blocks instance."""
    with gr.Blocks(title="Lumina Studio") as app:
        # Inject CSS styles via HTML component (for Gradio 4.20.0 compatibility)
        gr.HTML(f"<style>{CUSTOM_CSS + HEADER_CSS + LUT_GRID_CSS}</style>")

        lang_state = gr.State(value="zh")
        theme_state = gr.State(value=False)  # False=light, True=dark

        # Header + Stats merged into one row
        with gr.Row(elem_classes=["header-row"], equal_height=True):
            with gr.Column(scale=6):
                app_title_html = gr.HTML(
                    value=f"<h1>✨ Lumina Studio</h1><p>{I18n.get('app_subtitle', 'zh')}</p>",
                    elem_id="app-header",
                )
            with gr.Column(scale=4):
                stats = Stats.get_all()
                stats_html = gr.HTML(
                    value=_get_stats_html("zh", stats),
                    elem_classes=["stats-bar-inline"],
                )
            with gr.Column(scale=1, min_width=140, elem_classes=["header-controls"]):
                lang_btn = gr.Button(value="🌐 English", size="sm", elem_id="lang-btn")
                theme_btn = gr.Button(
                    value=I18n.get("theme_toggle_night", "zh"),
                    size="sm",
                    elem_id="theme-btn",
                )

        # Crop modal scripts are loaded via head parameter in main.py (CROP_MODAL_JS)

        tab_components = {}
        with gr.Tabs() as tabs:
            components = {}

            # Converter tab
            with gr.TabItem(label=I18n.get("tab_converter", "zh"), id=0) as tab_conv:
                conv_components = create_converter_tab_content(
                    "zh", lang_state, theme_state
                )
                components.update(conv_components)
            tab_components["tab_converter"] = tab_conv

            with gr.TabItem(label=I18n.get("tab_calibration", "zh"), id=1) as tab_cal:
                from .tabs.calibration_tab import create_calibration_tab_content

                cal_components = create_calibration_tab_content("zh")
                components.update(cal_components)
            tab_components["tab_calibration"] = tab_cal

            with gr.TabItem(label=I18n.get("tab_extractor", "zh"), id=2) as tab_ext:
                from .tabs.extractor_tab import create_extractor_tab_content

                ext_components = create_extractor_tab_content("zh")
                components.update(ext_components)
            tab_components["tab_extractor"] = tab_ext

            with gr.TabItem(label="🔬 高级 | Advanced", id=3) as tab_advanced:
                advanced_components = create_advanced_tab_content("zh")
                components.update(advanced_components)
            tab_components["tab_advanced"] = tab_advanced

            with gr.TabItem(label=I18n.get("tab_merge", "zh"), id=4) as tab_merge:
                from .tabs.merge_tab import create_merge_tab_content

                merge_components = create_merge_tab_content("zh", lang_state)
                components.update(merge_components)
            tab_components["tab_merge"] = tab_merge

            with gr.TabItem(label="🎨 配色查询 | Color Query", id=5) as tab_5color:
                from ui.tabs.colorquery_tab import create_5color_tab_v2

                create_5color_tab_v2("zh")
            tab_components["tab_5color"] = tab_5color

            with gr.TabItem(label=I18n.get("tab_about", "zh"), id=6) as tab_about:
                about_components = create_about_tab_content("zh")
                components.update(about_components)
            tab_components["tab_about"] = tab_about

        footer_html = gr.HTML(value=_get_footer_html("zh"), elem_id="footer")

        def change_language(current_lang, is_dark):
            """Switch UI language and return updates for all i18n components."""
            new_lang = "en" if current_lang == "zh" else "zh"
            updates = []
            updates.append(
                gr.update(
                    value=I18n.get(
                        "lang_btn_zh" if new_lang == "zh" else "lang_btn_en", new_lang
                    )
                )
            )
            theme_label = (
                I18n.get("theme_toggle_day", new_lang)
                if is_dark
                else I18n.get("theme_toggle_night", new_lang)
            )
            updates.append(gr.update(value=theme_label))
            updates.append(gr.update(value=_get_header_html(new_lang)))
            stats = Stats.get_all()
            updates.append(gr.update(value=_get_stats_html(new_lang, stats)))
            updates.append(gr.update(label=I18n.get("tab_converter", new_lang)))
            updates.append(gr.update(label=I18n.get("tab_calibration", new_lang)))
            updates.append(gr.update(label=I18n.get("tab_extractor", new_lang)))
            updates.append(
                gr.update(
                    label="🔬 高级 | Advanced" if new_lang == "zh" else "🔬 Advanced"
                )
            )
            updates.append(gr.update(label=I18n.get("tab_merge", new_lang)))
            updates.append(gr.update(label=I18n.get("tab_about", new_lang)))
            updates.extend(_get_all_component_updates(new_lang, components))
            updates.append(gr.update(value=_get_footer_html(new_lang)))
            updates.append(new_lang)
            return updates

        output_list = [
            lang_btn,
            theme_btn,
            app_title_html,
            stats_html,
            tab_components["tab_converter"],
            tab_components["tab_calibration"],
            tab_components["tab_extractor"],
            tab_components["tab_advanced"],
            tab_components["tab_merge"],
            tab_components["tab_about"],
        ]
        output_list.extend(_get_component_list(components))
        output_list.extend([footer_html, lang_state])

        lang_btn.click(
            change_language, inputs=[lang_state, theme_state], outputs=output_list
        )

        def _on_theme_toggle(current_is_dark, current_lang, cache):
            """Toggle theme state and re-render preview with new bed colors."""
            new_is_dark = not current_is_dark
            label = (
                I18n.get("theme_toggle_day", current_lang)
                if new_is_dark
                else I18n.get("theme_toggle_night", current_lang)
            )

            # Re-render 2D preview with new theme
            new_preview = gr.update()
            if cache is not None:
                cache["is_dark"] = new_is_dark
                preview_rgba = cache.get("preview_rgba")
                if preview_rgba is not None:
                    color_conf = cache.get("color_conf")
                    display = render_preview(
                        preview_rgba,
                        None,
                        0,
                        0,
                        0,
                        0,
                        False,
                        color_conf,
                        bed_label=cache.get("bed_label"),
                        target_width_mm=cache.get("target_width_mm"),
                        is_dark=new_is_dark,
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
            }""",
        ).then(
            fn=_on_theme_toggle,
            inputs=[theme_state, lang_state, components["_conv_preview_cache"]],
            outputs=[
                theme_state,
                theme_btn,
                components["_conv_preview"],
                components["_conv_3d_preview"],
            ],
        )

        def init_theme(current_lang, request: gr.Request):
            theme = None
            try:
                if request is not None:
                    theme = request.query_params.get("__theme")
            except Exception:
                theme = None

            is_dark = theme == "dark"
            label = (
                I18n.get("theme_toggle_day", current_lang)
                if is_dark
                else I18n.get("theme_toggle_night", current_lang)
            )
            return is_dark, gr.update(value=label)

        app.load(fn=init_theme, inputs=[lang_state], outputs=[theme_state, theme_btn])

        app.load(
            fn=on_lut_select,
            inputs=[components["dropdown_conv_lut_dropdown"]],
            outputs=[
                components["state_conv_lut_path"],
                components["md_conv_lut_status"],
            ],
        ).then(
            fn=_update_lut_grid,
            inputs=[
                components["state_conv_lut_path"],
                lang_state,
                components["state_conv_palette_mode"],
            ],
            outputs=[components["conv_lut_grid_view"]],
        ).then(
            fn=_detect_and_enforce_structure,
            inputs=[components["state_conv_lut_path"]],
            outputs=[
                components["radio_conv_color_mode"],
                components["radio_conv_structure"],
                components["checkbox_conv_relief_mode"],
            ],
        )

        # Settings: cache clearing and counter reset
        def on_clear_cache(lang):
            cache_size_before = Stats.get_cache_size()
            _, _ = Stats.clear_cache()
            cache_size_after = Stats.get_cache_size()
            freed_size = max(cache_size_before - cache_size_after, 0)

            status_msg = I18n.get("settings_cache_cleared", lang).format(
                _format_bytes(freed_size)
            )
            new_cache_size = I18n.get("settings_cache_size", lang).format(
                _format_bytes(cache_size_after)
            )
            return status_msg, new_cache_size

        def on_clear_output(lang):
            output_size_before = Stats.get_output_size()
            _, _ = Stats.clear_output()
            output_size_after = Stats.get_output_size()
            freed_size = max(output_size_before - output_size_after, 0)

            status_msg = I18n.get("settings_output_cleared", lang).format(
                _format_bytes(freed_size)
            )
            new_output_size = I18n.get("settings_output_size", lang).format(
                _format_bytes(output_size_after)
            )
            return status_msg, new_output_size

        def on_reset_counters(lang):
            Stats.reset_all()
            new_stats = Stats.get_all()

            status_msg = I18n.get("settings_counters_reset", lang).format(
                new_stats.get("calibrations", 0),
                new_stats.get("extractions", 0),
                new_stats.get("conversions", 0),
            )
            return status_msg, _get_stats_html(lang, new_stats)

        # ========== Advanced Tab Events ==========
        def on_unlock_max_size(unlock: bool):
            """Toggle max size limit for width/height sliders."""
            new_max = 9999 if unlock else 400
            return gr.update(maximum=new_max), gr.update(maximum=new_max)

        components["checkbox_unlock_max_size"].change(
            on_unlock_max_size,
            inputs=[components["checkbox_unlock_max_size"]],
            outputs=[components["slider_conv_width"], components["slider_conv_height"]],
        )

        # ========== About Tab Events ==========
        components["btn_clear_cache"].click(
            fn=on_clear_cache,
            inputs=[lang_state],
            outputs=[components["md_settings_status"], components["md_cache_size"]],
        )

        components["btn_clear_output"].click(
            fn=on_clear_output,
            inputs=[lang_state],
            outputs=[components["md_settings_status"], components["md_output_size"]],
        )

        components["btn_reset_counters"].click(
            fn=on_reset_counters,
            inputs=[lang_state],
            outputs=[components["md_settings_status"], stats_html],
        )

        def update_stats_bar(lang):
            stats = Stats.get_all()
            return _get_stats_html(lang, stats)

        if "cal_event" in components:
            components["cal_event"].then(
                fn=update_stats_bar, inputs=[lang_state], outputs=[stats_html]
            )

        if "ext_event" in components:
            components["ext_event"].then(
                fn=update_stats_bar, inputs=[lang_state], outputs=[stats_html]
            )

        if "conv_event" in components:
            components["conv_event"].then(
                fn=update_stats_bar, inputs=[lang_state], outputs=[stats_html]
            )

        # Palette mode switch (Advanced tab)
        if "radio_palette_mode" in components:

            def on_palette_mode_change(mode, lut_path, lang):
                _save_user_setting("palette_mode", mode)
                return mode, _update_lut_grid(lut_path, lang, mode)

            components["radio_palette_mode"].change(
                fn=on_palette_mode_change,
                inputs=[
                    components["radio_palette_mode"],
                    components["state_conv_lut_path"],
                    lang_state,
                ],
                outputs=[
                    components["state_conv_palette_mode"],
                    components["conv_lut_grid_view"],
                ],
            )

    return app
