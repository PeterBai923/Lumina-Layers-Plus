# -*- coding: utf-8 -*-
"""
Lumina Studio - LUT Merge Tab
Self-contained module for LUT merging: UI and event bindings.
"""

import gradio as gr
from utils import LUTManager
from ..callbacks import (
    on_merge_primary_select,
    on_merge_secondary_change,
    on_merge_execute,
)


# ═══════════════════════════════════════════════════════════════
# Tab UI Builder
# ═══════════════════════════════════════════════════════════════

def create_merge_tab_content() -> dict:
    """Build LUT Merge tab UI and events. Returns component dict."""
    components = {}

    components['md_merge_title'] = gr.Markdown('### 🔀 色卡合并')
    components['md_merge_desc'] = gr.Markdown('将不同色彩模式的LUT色卡合并为一个，获得更丰富的色彩。')

    with gr.Row():
        with gr.Column():
            components['dd_merge_primary'] = gr.Dropdown(
                choices=LUTManager.get_lut_choices(),
                label='🎯 主色卡（6色或8色）',
                interactive=True,
            )
            components['md_merge_mode_primary'] = gr.Markdown(
                '💡 请先选择一个6色或8色的主色卡'
            )
        with gr.Column():
            components['dd_merge_secondary'] = gr.Dropdown(
                choices=[],
                label='➕ 副色卡（可多选）',
                multiselect=True,
                interactive=True,
            )
            components['md_merge_secondary_info'] = gr.Markdown(
                '未选择副色卡'
            )

    components['slider_dedup_threshold'] = gr.Slider(
        minimum=0, maximum=20, value=3, step=0.5,
        label='Delta-E 去重阈值',
        info='值越大去除的相近色越多，0=仅精确去重',
    )

    components['btn_merge'] = gr.Button(
        '🔀 执行合并',
        variant="primary",
    )

    components['md_merge_status'] = gr.Markdown('💡 选择两个LUT后点击合并')

    # Event bindings
    components['dd_merge_primary'].change(
        fn=on_merge_primary_select,
        inputs=[components['dd_merge_primary']],
        outputs=[
            components['md_merge_mode_primary'],
            components['dd_merge_secondary'],
        ],
    )
    components['dd_merge_secondary'].change(
        fn=on_merge_secondary_change,
        inputs=[components['dd_merge_secondary']],
        outputs=[components['md_merge_secondary_info']],
    )
    components['btn_merge'].click(
        fn=on_merge_execute,
        inputs=[
            components['dd_merge_primary'],
            components['dd_merge_secondary'],
            components['slider_dedup_threshold'],
        ],
        outputs=[
            components['md_merge_status'],
            components['dd_merge_primary'],
            components['dd_merge_secondary'],
        ],
    )

    return components
