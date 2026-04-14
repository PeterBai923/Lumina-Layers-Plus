# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Tab Package
Assembles the converter tab UI and event bindings from modular sub-files.
"""

import gradio as gr

from .helpers import _update_lut_grid, _detect_and_enforce_structure
from .sidebar import build_left_sidebar
from .workspace import build_right_workspace
from .events_image import bind_image_events
from .events_color import bind_color_events
from .events_relief import bind_relief_events
from .events_generate import bind_generate_events


def create_converter_tab_content(theme_state=None) -> dict:
    """Build converter tab UI and events. Returns component dict.

    Args:
        theme_state: Gradio State for theme (False=light, True=dark).

    Returns:
        dict: Mapping from component key to Gradio component (and state refs).
    """
    components = {}
    states = {}

    # Create top-level shared states
    states['conv_loop_pos'] = gr.State(None)
    states['conv_preview_cache'] = gr.State(None)
    states['theme_state'] = theme_state

    with gr.Row():
        build_left_sidebar(components, states)
        build_right_workspace(components, states)

    # Bind events
    bind_image_events(components, states)
    bind_color_events(components, states, theme_state)
    bind_relief_events(components, states)
    bind_generate_events(components, states, theme_state)

    # Expose internal state refs for theme toggle in create_app
    components['_conv_preview'] = states['conv_preview']
    components['_conv_preview_cache'] = states['conv_preview_cache']
    components['_conv_3d_preview'] = states['conv_3d_preview']

    return components
