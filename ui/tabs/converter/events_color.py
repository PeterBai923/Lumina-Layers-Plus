# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Color Event Bindings
Binds all color replacement / merge / selection event handlers for the converter tab.
"""

import gradio as gr

from core.i18n import I18n
from core.converter import (
    on_preview_click_select_color,
    _build_dual_recommendations, _resolve_click_selection_hexes,
    get_lut_color_choices,
)
from ...callbacks import (
    on_highlight_color_change, on_clear_highlight,
    on_apply_color_replacement, on_clear_color_replacements,
    on_undo_color_replacement, on_delete_selected_user_replacement,
    on_merge_preview, on_merge_apply, on_merge_revert,
)
from ...image_helpers import _preview_update


def bind_color_events(components, states, lang_state, theme_state, lang):
    """Bind all color replacement / merge / selection event handlers.

    Args:
        components: dict of Gradio UI components keyed by name.
        states: dict of Gradio State components keyed by name.
        lang_state: Gradio State for current language code.
        theme_state: Gradio State for dark/light theme flag.
        lang: Initial language code string ('zh' or 'en').
    """

    # ------------------------------------------------------------------
    # Hidden textbox receives highlight color from JavaScript click (triggers preview highlight)
    # Use button click instead of textbox change for more reliable triggering
    # ------------------------------------------------------------------
    def on_highlight_color_change_with_fit(highlight_hex, cache, loop_pos, add_loop,
                                           loop_width, loop_length, loop_hole, loop_angle):
        display, status = on_highlight_color_change(
            highlight_hex, cache, loop_pos, add_loop,
            loop_width, loop_length, loop_hole, loop_angle
        )
        return _preview_update(display), status

    states['conv_highlight_trigger_btn'].click(
        on_highlight_color_change_with_fit,
        inputs=[
            states['conv_highlight_color_hidden'], states['conv_preview_cache'], states['conv_loop_pos'],
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'], components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'], components['slider_conv_loop_angle']
        ],
        outputs=[states['conv_preview'], components['textbox_conv_status']]
    )

    # ------------------------------------------------------------------
    # LUT color swatch click event (JS -> Hidden Textbox -> Python)
    # ------------------------------------------------------------------
    def on_lut_color_click(hex_color):
        return hex_color, hex_color

    def build_palette_html_with_selection(cache, replacement_regions,
                                          selected_user_row_id, selected_auto_row_id,
                                          lang_state_val):
        from ui.widgets.palette import generate_palette_html

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

    states['conv_lut_color_trigger_btn'].click(
        fn=on_lut_color_click,
        inputs=[states['conv_lut_color_selected_hidden']],
        outputs=[states['conv_replacement_color_state'], components['color_conv_palette_replace_label']]
    )

    states['conv_palette_row_select_trigger_btn'].click(
        fn=on_palette_row_select,
        inputs=[
            states['conv_palette_row_select_hidden'],
            states['conv_selected_user_row_id'],
            states['conv_selected_auto_row_id'],
            states['conv_preview_cache'],
        ],
        outputs=[
            states['conv_selected_user_row_id'],
            states['conv_selected_auto_row_id'],
            states['conv_preview_cache'],
        ]
    ).then(
        fn=build_palette_html_with_selection,
        inputs=[
            states['conv_preview_cache'], states['conv_replacement_regions'],
            states['conv_selected_user_row_id'], states['conv_selected_auto_row_id'], lang_state
        ],
        outputs=[states['conv_palette_html']]
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

    states['conv_palette_delete_trigger_btn'].click(
        fn=on_delete_selected_user_replacement_regions_only,
        inputs=[
            states['conv_preview_cache'], states['conv_replacement_regions'], states['conv_replacement_history'],
            states['conv_selected_user_row_id'],
            states['conv_loop_pos'], components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'], components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            states['conv_preview'], states['conv_preview_cache'], states['conv_palette_html'],
            states['conv_replacement_regions'], states['conv_replacement_history'],
            components['textbox_conv_status'], states['conv_selected_user_row_id']
        ]
    ).then(
        fn=lambda: None,
        inputs=[],
        outputs=[states['conv_selected_auto_row_id']]
    )

    # ------------------------------------------------------------------
    # Color picker nearest match via KDTree (以色找色)
    # ------------------------------------------------------------------
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

            print(f"[COLOR_PICKER] {picker_hex} -> nearest LUT: {nearest_hex} (dist={dist[0]:.1f})")

            # Return JS call to scroll to the matched swatch + update replacement display
            gr.Info(f"\u2705 \u6700\u63a5\u8fd1: {nearest_hex} (\u8ddd\u79bb: {dist[0]:.1f})")
            return nearest_hex, nearest_hex
        except Exception as e:
            print(f"[COLOR_PICKER] Error: {e}")
            return gr.update(), gr.update()

    components['btn_conv_picker_search'].click(
        fn=on_color_picker_find_nearest,
        inputs=[components['color_conv_picker_search'], states['conv_lut_path']],
        outputs=[states['conv_replacement_color_state'], components['color_conv_palette_replace_label']]
    ).then(
        fn=None,
        inputs=[states['conv_replacement_color_state']],
        outputs=[],
        js="(hex) => { if (hex) { setTimeout(() => window.lutScrollToColor && window.lutScrollToColor(hex), 200); } }"
    )

    # ------------------------------------------------------------------
    # Color replacement: Apply replacement
    # ------------------------------------------------------------------
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

    components['btn_conv_palette_apply_btn'].click(
        on_apply_color_replacement_with_fit,
        inputs=[
            states['conv_preview_cache'], states['conv_selected_color'], states['conv_replacement_color_state'],
            states['conv_replacement_regions'], states['conv_replacement_history'], states['conv_loop_pos'],
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'], components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            states['conv_preview'], states['conv_preview_cache'], states['conv_palette_html'],
            states['conv_replacement_regions'], states['conv_replacement_history'],
            components['textbox_conv_status']
        ]
    ).then(
        fn=lambda: (None, None),
        inputs=[],
        outputs=[states['conv_selected_user_row_id'], states['conv_selected_auto_row_id']]
    )

    # ------------------------------------------------------------------
    # Color replacement: Undo last replacement
    # ------------------------------------------------------------------
    def on_undo_color_replacement_with_fit(cache, replacement_regions, replacement_history,
                                           loop_pos, add_loop, loop_width, loop_length,
                                           loop_hole, loop_angle, lang_state_val):
        display, updated_cache, palette_html, new_regions, new_history, status = on_undo_color_replacement(
            cache, replacement_regions, replacement_history,
            loop_pos, add_loop, loop_width, loop_length,
            loop_hole, loop_angle, lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, new_regions, new_history, status

    components['btn_conv_palette_undo_btn'].click(
        on_undo_color_replacement_with_fit,
        inputs=[
            states['conv_preview_cache'], states['conv_replacement_regions'], states['conv_replacement_history'],
            states['conv_loop_pos'], components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'], components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            states['conv_preview'], states['conv_preview_cache'], states['conv_palette_html'],
            states['conv_replacement_regions'], states['conv_replacement_history'],
            components['textbox_conv_status']
        ]
    ).then(
        fn=lambda: (None, None),
        inputs=[],
        outputs=[states['conv_selected_user_row_id'], states['conv_selected_auto_row_id']]
    )

    # ------------------------------------------------------------------
    # Color replacement: Clear all replacements
    # ------------------------------------------------------------------
    def on_clear_color_replacements_with_fit(cache, replacement_regions, replacement_history,
                                             loop_pos, add_loop, loop_width, loop_length,
                                             loop_hole, loop_angle, lang_state_val):
        display, updated_cache, palette_html, new_regions, new_history, status = on_clear_color_replacements(
            cache, replacement_regions, replacement_history,
            loop_pos, add_loop, loop_width, loop_length,
            loop_hole, loop_angle, lang_state_val
        )
        return _preview_update(display), updated_cache, palette_html, new_regions, new_history, status

    components['btn_conv_palette_clear_btn'].click(
        on_clear_color_replacements_with_fit,
        inputs=[
            states['conv_preview_cache'], states['conv_replacement_regions'], states['conv_replacement_history'],
            states['conv_loop_pos'], components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'], components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'], components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            states['conv_preview'], states['conv_preview_cache'], states['conv_palette_html'],
            states['conv_replacement_regions'], states['conv_replacement_history'],
            components['textbox_conv_status']
        ]
    )

    # ------------------------------------------------------------------
    # Free Color (自由色) Event Handlers
    # ------------------------------------------------------------------
    def _render_free_color_html(free_set):
        if not free_set:
            return ""
        parts = ["<div style='display:flex; flex-wrap:wrap; gap:6px; padding:4px; align-items:center;'>",
                 "<span style='font-size:11px; color:#666;'>\U0001f3af 自由色:</span>"]
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
            msg = f"\u21a9\ufe0f 已取消自由色: {hex_c}"
        else:
            new_set.add(hex_c)
            msg = f"\U0001f3af 已标记为自由色: {hex_c} (生成时将作为独立对象)"
        return new_set, _render_free_color_html(new_set), msg

    def on_clear_free_colors(free_set):
        return set(), "", "[OK] 已清除所有自由色标记"

    components['btn_conv_free_color'].click(
        on_mark_free_color,
        inputs=[states['conv_selected_color'], states['conv_free_color_set']],
        outputs=[states['conv_free_color_set'], states['conv_free_color_html'], components['textbox_conv_status']]
    )
    components['btn_conv_free_color_clear'].click(
        on_clear_free_colors,
        inputs=[states['conv_free_color_set']],
        outputs=[states['conv_free_color_set'], states['conv_free_color_html'], components['textbox_conv_status']]
    )

    # ------------------------------------------------------------------
    # Color Merging Event Handlers
    # ------------------------------------------------------------------

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
            states['conv_preview_cache'],
            components['checkbox_conv_merge_enable'],
            components['slider_conv_merge_threshold'],
            components['slider_conv_merge_max_distance'],
            states['conv_loop_pos'],
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            states['conv_preview'],
            states['conv_preview_cache'],
            states['conv_palette_html'],
            states['conv_merge_map'],
            states['conv_merge_stats'],
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
            states['conv_preview_cache'],
            states['conv_merge_map'],
            states['conv_merge_stats'],
            states['conv_loop_pos'],
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            states['conv_preview'],
            states['conv_preview_cache'],
            states['conv_palette_html'],
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
            states['conv_preview_cache'],
            states['conv_loop_pos'],
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle'],
            lang_state
        ],
        outputs=[
            states['conv_preview'],
            states['conv_preview_cache'],
            states['conv_palette_html'],
            states['conv_merge_map'],
            states['conv_merge_stats'],
            components['md_conv_merge_status']
        ]
    )

    # ------------------------------------------------------------------
    # Preview image click -> sync to UI (color selection + dual recommendations)
    # ------------------------------------------------------------------
    def on_preview_click_sync_ui(cache, evt: gr.SelectData, lut_path):
        from ui.widgets.palette import generate_dual_recommendations_html, build_selected_dual_color_html

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

    # ------------------------------------------------------------------
    # Relief mode: update slider when color is selected
    # ------------------------------------------------------------------
    def on_color_selected_for_relief(hex_color, enable_relief, height_map, base_thickness, cache):
        """When user clicks a color in preview, update relief slider.

        Args:
            hex_color (str | None): Quantized hex from click selection.
            enable_relief (bool): Whether relief mode is enabled.
            height_map (dict): Color-to-height mapping keyed by matched hex.
            base_thickness (float): Base thickness fallback in mm.
            cache (dict | None): Preview cache containing selected_matched_hex.

        Returns:
            tuple: (slider update, relief_selected_color, selected_color).
        """
        if not enable_relief or not hex_color:
            return gr.update(visible=False), hex_color, hex_color

        # Use matched hex (same key space as color_height_map) for lookup
        matched_hex = (cache or {}).get('selected_matched_hex', hex_color) if cache else hex_color
        current_height = height_map.get(matched_hex, base_thickness)

        # Store matched_hex in conv_relief_selected_color so slider edits
        # write back with the correct key
        return gr.update(visible=True, value=current_height), matched_hex, hex_color

    # Store function reference for events_relief to use
    states['fn_on_color_selected_for_relief'] = on_color_selected_for_relief

    # ------------------------------------------------------------------
    # conv_preview.select() handler with relief sync .then() chain
    # ------------------------------------------------------------------
    states['conv_preview'].select(
        fn=on_preview_click_sync_ui,
        inputs=[states['conv_preview_cache'], states['conv_lut_path']],
        outputs=[
            states['conv_preview'],
            states['conv_selected_display'],
            states['conv_selected_color'],
            states['conv_dual_recommend_html'],
            components['textbox_conv_status']
        ]
    ).then(
        # Also update relief slider when clicking preview image
        fn=on_color_selected_for_relief,
        inputs=[
            states['conv_selected_color'],
            components['checkbox_conv_relief_mode'],
            states['conv_color_height_map'],
            components['slider_conv_thickness'],
            states['conv_preview_cache']
        ],
        outputs=[
            components['slider_conv_relief_height'],
            states['conv_relief_selected_color'],
            states['conv_selected_color']
        ]
    )
