# -*- coding: utf-8 -*-
"""
Lumina Studio - Calibration Tab
Self-contained module for calibration board generation: UI, callbacks, and helpers.
"""

import gradio as gr
from core.i18n import I18n
from core.calibration import (
    generate_calibration_board,
    generate_smart_board,
    generate_8color_batch_zip,
)


# ═══════════════════════════════════════════════════════════════
# Callbacks
# ═══════════════════════════════════════════════════════════════

def generate_board_wrapper(color_mode, block_size, gap, backing):
    """Wrapper function to call appropriate generator based on mode"""
    if color_mode == "8-Color Max":
        return generate_8color_batch_zip()
    if color_mode == "5-Color Extended (Dual Page)":
        from core.calibration import generate_5color_extended_batch_zip
        return generate_5color_extended_batch_zip(block_size, gap)
    if "5-Color Extended" in color_mode:
        from core.calibration import generate_5color_extended_board
        return generate_5color_extended_board(block_size, gap)
    if "6-Color" in color_mode:
        # Call Smart 1296 generator
        return generate_smart_board(block_size, gap)
    if color_mode == "BW (Black & White)":
        # Call BW generator (exact match to avoid matching RYBW)
        from core.calibration import generate_bw_calibration_board
        return generate_bw_calibration_board(block_size, gap, backing)
    else:
        # Call traditional 4-color generator (unified for all 4-color modes)
        # Default to RYBW palette
        return generate_calibration_board("RYBW", block_size, gap, backing)


# ═══════════════════════════════════════════════════════════════
# Tab UI Builder
# ═══════════════════════════════════════════════════════════════

def create_calibration_tab_content(lang: str) -> dict:
    """Build calibration board tab UI and events. Returns component dict."""
    components = {}

    with gr.Row():
        with gr.Column(scale=1):
            components['md_cal_params'] = gr.Markdown(I18n.get('cal_params', lang))

            components['radio_cal_color_mode'] = gr.Radio(
                choices=[
                    ("BW (Black & White)", "BW (Black & White)"),
                    ("4-Color (1024 colors)", "4-Color"),
                    ("5-Color Extended (Dual Page)", "5-Color Extended (Dual Page)"),
                    ("6-Color (Smart 1296)", "6-Color (Smart 1296)"),
                    ("8-Color Max", "8-Color Max")
                ],
                value="4-Color",
                label=I18n.get('cal_color_mode', lang)
            )

            components['slider_cal_block_size'] = gr.Slider(
                3, 10, 5, step=1,
                label=I18n.get('cal_block_size', lang)
            )

            components['slider_cal_gap'] = gr.Slider(
                0.4, 2.0, 0.82, step=0.02,
                label=I18n.get('cal_gap', lang)
            )

            components['dropdown_cal_backing'] = gr.Dropdown(
                choices=["White", "Cyan", "Magenta", "Yellow", "Red", "Blue"],
                value="White",
                label=I18n.get('cal_backing', lang)
            )

            components['btn_cal_generate_btn'] = gr.Button(
                I18n.get('cal_generate_btn', lang),
                variant="primary",
                elem_classes=["primary-btn"]
            )

            components['textbox_cal_status'] = gr.Textbox(
                label=I18n.get('cal_status', lang),
                interactive=False
            )

        with gr.Column(scale=1):
            components['md_cal_preview'] = gr.Markdown(I18n.get('cal_preview', lang))

            cal_preview = gr.Image(
                label="Calibration Preview",
                show_label=False
            )

            components['file_cal_download'] = gr.File(
                label=I18n.get('cal_download', lang)
            )

    # Event binding
    cal_event = components['btn_cal_generate_btn'].click(
            generate_board_wrapper,
            inputs=[
                components['radio_cal_color_mode'],
                components['slider_cal_block_size'],
                components['slider_cal_gap'],
                components['dropdown_cal_backing']
            ],
            outputs=[
                components['file_cal_download'],
                cal_preview,
                components['textbox_cal_status']
            ]
    )

    components['cal_event'] = cal_event

    return components
