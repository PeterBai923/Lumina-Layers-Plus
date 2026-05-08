"""
Lumina Studio - Preview Package

Provides preview rendering and interaction functionality for the image-to-3D conversion pipeline.

Modules:
    render: Functions for rendering 2D/3D previews, generating GLB files
    interaction: Functions for handling user interactions with previews
"""

from core.preview.render import (
    # Constants
    FIXED_BED_WIDTH_MM,
    FIXED_BED_HEIGHT_MM,
    FIXED_BED_LABEL,
    # Rendering functions
    render_preview,
    generate_empty_bed_glb,
    generate_realtime_glb,
    generate_highlight_preview,
    clear_highlight_preview,
    generate_lut_grid_html,
    generate_lut_card_grid_html,
    # Internal functions (exposed for advanced use)
    _create_bed_mesh,
    _create_preview_mesh,
    _get_or_create_grid_template,
    _draw_loop_on_canvas,
    _resolve_highlight_mask,
)

from core.preview.interaction import (
    # Interaction functions
    on_preview_click,
    on_preview_click_select_color,
    update_preview_with_loop,
    on_remove_loop,
    update_preview_with_replacements,
    # Internal functions (exposed for advanced use)
    _compute_connected_region_mask_4n,
    _build_selection_meta,
    _ensure_quantized_image_in_cache,
    _resolve_click_selection_hexes,
)

__all__ = [
    # Constants
    'FIXED_BED_WIDTH_MM',
    'FIXED_BED_HEIGHT_MM',
    'FIXED_BED_LABEL',
    # Rendering functions
    'render_preview',
    'generate_empty_bed_glb',
    'generate_realtime_glb',
    'generate_highlight_preview',
    'clear_highlight_preview',
    'generate_lut_grid_html',
    'generate_lut_card_grid_html',
    # Internal rendering functions
    '_create_bed_mesh',
    '_create_preview_mesh',
    '_get_or_create_grid_template',
    '_draw_loop_on_canvas',
    '_resolve_highlight_mask',
    # Interaction functions
    'on_preview_click',
    'on_preview_click_select_color',
    'update_preview_with_loop',
    'on_remove_loop',
    'update_preview_with_replacements',
    # Internal interaction functions
    '_compute_connected_region_mask_4n',
    '_build_selection_meta',
    '_ensure_quantized_image_in_cache',
    '_resolve_click_selection_hexes',
]
