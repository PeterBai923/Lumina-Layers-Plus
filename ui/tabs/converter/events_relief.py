# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Tab Relief / Loop / Heightmap Event Bindings
Binds all Gradio event handlers for relief mode, loop, and heightmap features.
"""

import os

import gradio as gr
import numpy as np

from core.i18n import I18n
from core.converter import (
    update_preview_with_loop,
    on_remove_loop,
    generate_auto_height_map,
    _build_dual_recommendations,
    _resolve_click_selection_hexes,
    get_lut_color_choices,
)
from core.heightmap_loader import HeightmapLoader
from core.image_preprocessor import ImagePreprocessor
from ...callbacks import on_highlight_color_change, on_delete_selected_user_replacement
from ...image_helpers import _preview_update


def bind_relief_events(components, states, lang_state, lang):
    """Bind relief / loop / heightmap event handlers.

    Args:
        components: Dict of Gradio UI components.
        states: Dict of Gradio state components.
        lang_state: Gradio State for language (also stored in states['lang_state']).
        lang: Initial language code string.
    """

    states['lang_state'] = lang_state

    # Retrieve the on_color_selected_for_relief function stored by events_color
    on_color_selected_for_relief = states['fn_on_color_selected_for_relief']

    # ------------------------------------------------------------------
    # Nested helper functions
    # ------------------------------------------------------------------

    def update_preview_with_loop_with_fit(cache, loop_pos, add_loop,
                                          loop_width, loop_length, loop_hole, loop_angle):
        display = update_preview_with_loop(
            cache, loop_pos, add_loop,
            loop_width, loop_length, loop_hole, loop_angle
        )
        return _preview_update(display)

    # ------------------------------------------------------------------
    # Loop remove button
    # ------------------------------------------------------------------
    components['btn_conv_loop_remove'].click(
        on_remove_loop,
        outputs=[states['conv_loop_pos'], components['checkbox_conv_loop_enable'],
                 components['slider_conv_loop_angle'], components['textbox_conv_loop_info']]
    ).then(
        update_preview_with_loop_with_fit,
        inputs=[
            states['conv_preview_cache'], states['conv_loop_pos'], components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'], components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'], components['slider_conv_loop_angle']
        ],
        outputs=[states['conv_preview']]
    )

    # ------------------------------------------------------------------
    # Loop parameter sliders
    # ------------------------------------------------------------------
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
                states['conv_preview_cache'], states['conv_loop_pos'], components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'], components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'], components['slider_conv_loop_angle']
            ],
            outputs=[states['conv_preview']]
        )

    # ========== Relief / Cloisonne Mutual Exclusion ==========

    def on_relief_mode_toggle(enable_relief, selected_color, height_map, base_thickness):
        """Toggle relief mode visibility and reset state; auto-disable cloisonne.

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
        """When cloisonne is enabled, auto-disable relief mode"""
        if enable_cloisonne:
            gr.Info("⚠️ 掐丝珐琅模式与2.5D浮雕模式互斥，已自动关闭浮雕 | Cloisonné and Relief are mutually exclusive, Relief disabled")
            return gr.update(value=False), gr.update(visible=False), gr.update(visible=False)
        return gr.update(), gr.update(), gr.update()

    components['checkbox_conv_relief_mode'].change(
        on_relief_mode_toggle,
        inputs=[
            components['checkbox_conv_relief_mode'],
            states['conv_relief_selected_color'],
            states['conv_color_height_map'],
            components['slider_conv_thickness']
        ],
        outputs=[
            components['slider_conv_relief_height'],
            components['accordion_conv_auto_height'],
            components['slider_conv_auto_height_max'],
            components['row_conv_heightmap'],
            components['image_conv_heightmap_preview'],
            states['conv_color_height_map'],
            states['conv_relief_selected_color'],
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
        from ui.widgets.palette import generate_dual_recommendations_html, build_selected_dual_color_html

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
    states['conv_color_trigger_btn'].click(
        fn=on_color_trigger_sync_ui,
        inputs=[
            states['conv_color_selected_hidden'],
            states['conv_highlight_color_hidden'],
            states['conv_preview_cache'],
            states['conv_lut_path'],
            states['conv_replacement_regions'],
            states['conv_selected_user_row_id'],
            states['conv_selected_auto_row_id'],
            states['conv_loop_pos'],
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            components['checkbox_conv_relief_mode'],
            states['conv_color_height_map'],
            components['slider_conv_thickness'],
        ],
        outputs=[
            states['conv_preview'],
            states['conv_selected_display'],
            states['conv_selected_color'],
            states['conv_dual_recommend_html'],
            states['conv_preview_cache'],
            components['textbox_conv_status'],
            components['slider_conv_relief_height'],
            states['conv_relief_selected_color'],
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
            states['conv_relief_selected_color'],
            states['conv_color_height_map']
        ],
        outputs=[states['conv_color_height_map']]
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
            states['conv_preview_cache'],
            components['radio_conv_auto_height_mode'],
            components['slider_conv_auto_height_max'],
            components['slider_conv_thickness']
        ],
        outputs=[states['conv_color_height_map']]
    )
    # ========== END Relief Mode Event Handlers ==========
