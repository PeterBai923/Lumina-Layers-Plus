# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Tab Right Workspace
UI construction for the right workspace (original lines 559-1037).
"""

import gradio as gr

from config import BedManager
from core.i18n import I18n
from core.converter import render_preview, generate_empty_bed_glb
from ...slicer_integration import _get_slicer_choices, _get_default_slicer, _slicer_css_class


def build_right_workspace(lang, components, states):
    """Build right workspace UI components.

    Populates both ``components`` and ``states`` dicts with Gradio references.
    """
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
                states['conv_preview'] = conv_preview

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
                    states['conv_selected_color'] = conv_selected_color
                    states['conv_replacement_regions'] = conv_replacement_regions
                    states['conv_replacement_history'] = conv_replacement_history
                    states['conv_replacement_color_state'] = conv_replacement_color_state
                    states['conv_selected_user_row_id'] = conv_selected_user_row_id
                    states['conv_selected_auto_row_id'] = conv_selected_auto_row_id
                    states['conv_free_color_set'] = conv_free_color_set

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
                    states['conv_color_selected_hidden'] = conv_color_selected_hidden
                    states['conv_highlight_color_hidden'] = conv_highlight_color_hidden
                    states['conv_highlight_trigger_btn'] = conv_highlight_trigger_btn
                    states['conv_color_trigger_btn'] = conv_color_trigger_btn

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
                    states['conv_lut_color_selected_hidden'] = conv_lut_color_selected_hidden
                    states['conv_lut_color_trigger_btn'] = conv_lut_color_trigger_btn
                    states['conv_palette_row_select_hidden'] = conv_palette_row_select_hidden
                    states['conv_palette_row_select_trigger_btn'] = conv_palette_row_select_trigger_btn
                    states['conv_palette_delete_trigger_btn'] = conv_palette_delete_trigger_btn

                    # --- 新 UI 布局 ---
                    from ui.widgets.palette import build_selected_dual_color_html

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
                            states['conv_selected_display'] = conv_selected_display

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
                            states['conv_dual_recommend_html'] = conv_dual_recommend_html

                            # LUT 网格 HTML
                            conv_lut_grid_view = gr.HTML(
                                value=f'<div class="placeholder-text" style="padding:10px;">{I18n.get("conv_palette_lut_loading", lang)}</div>',
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
                    states['conv_free_color_html'] = conv_free_color_html

                    # 调色板预览 HTML (保持原有逻辑，用于显示已替换列表)
                    components['md_conv_palette_replacements_label'] = gr.Markdown(
                        I18n.get('conv_palette_replacements_label', lang)
                    )
                    conv_palette_html = gr.HTML(
                        value=f'<p class="placeholder-text">{I18n.get("conv_palette_replacements_placeholder", lang)}</p>',
                        label="",
                        show_label=False
                    )
                    states['conv_palette_html'] = conv_palette_html
                # ========== END Color Palette ==========

                # ========== Color Merging ==========
                with gr.Accordion(I18n.get('merge_accordion_title', lang), open=False) as conv_merge_acc:
                    components['accordion_conv_merge'] = conv_merge_acc

                    # 状态变量
                    conv_merge_map = gr.State({})  # 合并映射表
                    conv_merge_stats = gr.State({})  # 合并统计信息
                    states['conv_merge_map'] = conv_merge_map
                    states['conv_merge_stats'] = conv_merge_stats

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
    states['conv_3d_preview'] = conv_3d_preview

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
    states['conv_3d_fullscreen'] = conv_3d_fullscreen

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
    states['conv_2d_thumb_preview'] = conv_2d_thumb_preview
