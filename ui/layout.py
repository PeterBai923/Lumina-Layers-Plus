# -*- coding: utf-8 -*-
"""
Lumina Studio - UI Layout
UI layout definition
"""

import gradio as gr

from utils import Stats
from core.converter import generate_realtime_glb, render_preview

from .styles import CUSTOM_CSS
from .callbacks import on_lut_select
from .settings import _save_user_setting
from .image_helpers import _preview_update, _format_bytes
from .i18n_helpers import (
    _get_header_html,
    _get_stats_html,
    _get_footer_html,
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

from .tabs.converter import (
    create_converter_tab_content,
    _update_lut_grid,
    _detect_and_enforce_structure,
)
from .tabs.advanced_tab import create_advanced_tab_content
from .tabs.about_tab import create_about_tab_content


def create_app():
    """Build the Gradio app (tabs, events) and return the Blocks instance."""
    with gr.Blocks(title="Lumina Studio") as app:
        # Inject CSS styles via HTML component (for Gradio 4.20.0 compatibility)
        gr.HTML(f"<style>{CUSTOM_CSS}</style>")

        theme_state = gr.State(value=False)  # False=light, True=dark

        # Header + Stats merged into one row
        with gr.Row(elem_classes=["header-row"], equal_height=True):
            with gr.Column(scale=6):
                app_title_html = gr.HTML(
                    value=_get_header_html(),
                    elem_id="app-header",
                )
            with gr.Column(scale=4):
                stats = Stats.get_all()
                stats_html = gr.HTML(
                    value=_get_stats_html(stats),
                    elem_classes=["stats-bar-inline"],
                )
            with gr.Column(scale=1, min_width=140, elem_classes=["header-controls"]):
                theme_btn = gr.Button(
                    value='🌙 夜间模式',
                    size="sm",
                    elem_id="theme-btn",
                )

        # Crop modal scripts are loaded via head parameter in main.py (CROP_MODAL_JS)

        tab_components = {}
        with gr.Tabs() as tabs:
            components = {}

            # Converter tab
            with gr.TabItem(label='💎 图像转换', id=0) as tab_conv:
                conv_components = create_converter_tab_content(
                    theme_state
                )
                components.update(conv_components)
            tab_components["tab_converter"] = tab_conv

            with gr.TabItem(label='📐 校准板生成', id=1) as tab_cal:
                from .tabs.calibration_tab import create_calibration_tab_content

                cal_components = create_calibration_tab_content()
                components.update(cal_components)
            tab_components["tab_calibration"] = tab_cal

            with gr.TabItem(label='🎨 颜色提取', id=2) as tab_ext:
                from .tabs.extractor_tab import create_extractor_tab_content

                ext_components = create_extractor_tab_content()
                components.update(ext_components)
            tab_components["tab_extractor"] = tab_ext

            with gr.TabItem(label="🔬 高级 | Advanced", id=3) as tab_advanced:
                advanced_components = create_advanced_tab_content()
                components.update(advanced_components)
            tab_components["tab_advanced"] = tab_advanced

            with gr.TabItem(label='🔀 色卡合并', id=4) as tab_merge:
                from .tabs.merge_tab import create_merge_tab_content

                merge_components = create_merge_tab_content()
                components.update(merge_components)
            tab_components["tab_merge"] = tab_merge

            with gr.TabItem(label="🎨 配色查询 | Color Query", id=5) as tab_5color:
                from ui.tabs.colorquery_tab import create_5color_tab_v2

                create_5color_tab_v2()
            tab_components["tab_5color"] = tab_5color

            with gr.TabItem(label='ℹ️ 关于', id=6) as tab_about:
                about_components = create_about_tab_content()
                components.update(about_components)
            tab_components["tab_about"] = tab_about

        footer_html = gr.HTML(value=_get_footer_html(), elem_id="footer")

        def _on_theme_toggle(current_is_dark, cache):
            """Toggle theme state and re-render preview with new bed colors."""
            new_is_dark = not current_is_dark
            label = '☀️ 日间模式' if new_is_dark else '🌙 夜间模式'

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
            inputs=[theme_state, components["_conv_preview_cache"]],
            outputs=[
                theme_state,
                theme_btn,
                components["_conv_preview"],
                components["_conv_3d_preview"],
            ],
        )

        def init_theme(request: gr.Request):
            theme = None
            try:
                if request is not None:
                    theme = request.query_params.get("__theme")
            except Exception:
                theme = None

            is_dark = theme == "dark"
            label = '☀️ 日间模式' if is_dark else '🌙 夜间模式'
            return is_dark, gr.update(value=label)

        app.load(fn=init_theme, inputs=None, outputs=[theme_state, theme_btn])

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
        def on_clear_cache():
            cache_size_before = Stats.get_cache_size()
            _, _ = Stats.clear_cache()
            cache_size_after = Stats.get_cache_size()
            freed_size = max(cache_size_before - cache_size_after, 0)

            status_msg = f'✅ 缓存已清空，释放了 {_format_bytes(freed_size)} 空间'
            new_cache_size = f'📦 缓存大小: {_format_bytes(cache_size_after)}'
            return status_msg, new_cache_size

        def on_clear_output():
            output_size_before = Stats.get_output_size()
            _, _ = Stats.clear_output()
            output_size_after = Stats.get_output_size()
            freed_size = max(output_size_before - output_size_after, 0)

            status_msg = f'✅ 输出已清空，释放了 {_format_bytes(freed_size)} 空间'
            new_output_size = f'📦 输出大小: {_format_bytes(output_size_after)}'
            return status_msg, new_output_size

        def on_reset_counters():
            Stats.reset_all()
            new_stats = Stats.get_all()

            status_msg = '✅ 计数器已归零：校准板: {} | 颜色提取: {} | 模型转换: {}'.format(
                new_stats.get("calibrations", 0),
                new_stats.get("extractions", 0),
                new_stats.get("conversions", 0),
            )
            return status_msg, _get_stats_html(new_stats)

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
            inputs=[],
            outputs=[components["md_settings_status"], components["md_cache_size"]],
        )

        components["btn_clear_output"].click(
            fn=on_clear_output,
            inputs=[],
            outputs=[components["md_settings_status"], components["md_output_size"]],
        )

        components["btn_reset_counters"].click(
            fn=on_reset_counters,
            inputs=[],
            outputs=[components["md_settings_status"], stats_html],
        )

        def update_stats_bar():
            stats = Stats.get_all()
            return _get_stats_html(stats)

        if "cal_event" in components:
            components["cal_event"].then(
                fn=update_stats_bar, inputs=[], outputs=[stats_html]
            )

        if "ext_event" in components:
            components["ext_event"].then(
                fn=update_stats_bar, inputs=[], outputs=[stats_html]
            )

        if "conv_event" in components:
            components["conv_event"].then(
                fn=update_stats_bar, inputs=[], outputs=[stats_html]
            )

        # Palette mode switch (Advanced tab)
        if "radio_palette_mode" in components:

            def on_palette_mode_change(mode, lut_path):
                _save_user_setting("palette_mode", mode)
                return mode, _update_lut_grid(lut_path, mode)

            components["radio_palette_mode"].change(
                fn=on_palette_mode_change,
                inputs=[
                    components["radio_palette_mode"],
                    components["state_conv_lut_path"],
                ],
                outputs=[
                    components["state_conv_palette_mode"],
                    components["conv_lut_grid_view"],
                ],
            )

    return app
