# -*- coding: utf-8 -*-
"""
Lumina Studio - LUT Merge Tab
Self-contained module for LUT merging: UI and event bindings.
"""

import gradio as gr
from core.i18n import I18n
from utils import LUTManager
from ..callbacks import (
    on_merge_primary_select,
    on_merge_secondary_change,
    on_merge_execute,
)


# ═══════════════════════════════════════════════════════════════
# Tab UI Builder
# ═══════════════════════════════════════════════════════════════

def create_merge_tab_content(lang: str, lang_state=None) -> dict:
    """Build LUT Merge tab UI and events. Returns component dict.

    Layout: Primary LUT dropdown (single) + Secondary LUTs dropdown (multi-select)
    Primary must be 6-Color or 8-Color. Secondary options are filtered based on primary mode.
    """
    components = {}

    components['md_merge_title'] = gr.Markdown(I18n.get('merge_title', lang))
    components['md_merge_desc'] = gr.Markdown(I18n.get('merge_desc', lang))

    with gr.Row():
        with gr.Column():
            components['dd_merge_primary'] = gr.Dropdown(
                choices=LUTManager.get_lut_choices(),
                label=I18n.get('merge_lut_primary_label', lang),
                interactive=True,
            )
            components['md_merge_mode_primary'] = gr.Markdown(
                I18n.get('merge_primary_hint', lang)
            )
        with gr.Column():
            components['dd_merge_secondary'] = gr.Dropdown(
                choices=[],
                label=I18n.get('merge_lut_secondary_label', lang),
                multiselect=True,
                interactive=True,
            )
            components['md_merge_secondary_info'] = gr.Markdown(
                I18n.get('merge_secondary_none', lang)
            )

    components['slider_dedup_threshold'] = gr.Slider(
        minimum=0, maximum=20, value=3, step=0.5,
        label=I18n.get('merge_dedup_label', lang),
        info=I18n.get('merge_dedup_info', lang),
    )

    components['btn_merge'] = gr.Button(
        I18n.get('merge_btn', lang),
        variant="primary",
    )

    components['md_merge_status'] = gr.Markdown(I18n.get('merge_status_ready', lang))

    # Event bindings
    components['dd_merge_primary'].change(
        fn=on_merge_primary_select,
        inputs=[components['dd_merge_primary'], lang_state],
        outputs=[
            components['md_merge_mode_primary'],
            components['dd_merge_secondary'],
        ],
    )
    components['dd_merge_secondary'].change(
        fn=on_merge_secondary_change,
        inputs=[components['dd_merge_secondary'], lang_state],
        outputs=[components['md_merge_secondary_info']],
    )
    components['btn_merge'].click(
        fn=on_merge_execute,
        inputs=[
            components['dd_merge_primary'],
            components['dd_merge_secondary'],
            components['slider_dedup_threshold'],
            lang_state,
        ],
        outputs=[
            components['md_merge_status'],
            components['dd_merge_primary'],
            components['dd_merge_secondary'],
        ],
    )

    return components
