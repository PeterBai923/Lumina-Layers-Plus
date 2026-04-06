# -*- coding: utf-8 -*-
"""
Lumina Studio - Advanced Settings Tab
Extracted from layout.py for modularity.
"""

import gradio as gr

from ..settings import _load_user_settings


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
