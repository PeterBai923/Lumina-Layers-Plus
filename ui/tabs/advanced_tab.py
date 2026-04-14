# -*- coding: utf-8 -*-
"""
Lumina Studio - Advanced Settings Tab
Extracted from layout.py for modularity.
"""

import gradio as gr

from ..settings import _load_user_settings


def create_advanced_tab_content() -> dict:
    """Build Advanced tab content with independent setting groups."""
    components = {}

    # --- Group 1: Palette display mode ---
    with gr.Group():
        saved_mode = _load_user_settings().get("palette_mode", "swatch")
        components['radio_palette_mode'] = gr.Radio(
            choices=[("色块模式", "swatch"), ("色卡模式", "card")],
            value=saved_mode,
            label="调色板样式",
        )

    # --- Group 2: Unlock max size limit ---
    with gr.Group():
        components['checkbox_unlock_max_size'] = gr.Checkbox(
            label="解除最大尺寸限制",
            value=False,
            info="开启后，图像转换的宽度/高度滑块将不再限制最大值（默认上限 400mm）",
        )

    return components
