# -*- coding: utf-8 -*-
"""
Lumina Studio - Converter Generate / Slicer / Fullscreen Event Bindings
Binds the generate button, stop button, slicer integration buttons,
fullscreen 3D toggle, and bed-size change events.
"""

import gradio as gr

from config import BedManager
from ...settings import resolve_height_mode
from ...slicer_integration import _get_slicer_choices, open_in_slicer
from core.converter import render_preview
from .helpers import process_batch_generation, generate_preview_cached_with_fit
from ...image_helpers import _preview_update


def bind_generate_events(components, states, theme_state):
    """Bind generation / slicer / fullscreen event handlers.

    Args:
        components: dict of Gradio component references.
        states: dict of Gradio State references.
        theme_state: Gradio State for theme (False=light, True=dark).
    """

    # Unpack frequently-used state refs for readability
    conv_preview = states['conv_preview']
    conv_preview_cache = states['conv_preview_cache']
    conv_loop_pos = states['conv_loop_pos']
    conv_lut_path = states['conv_lut_path']
    conv_replacement_regions = states['conv_replacement_regions']
    conv_color_height_map = states['conv_color_height_map']
    conv_free_color_set = states['conv_free_color_set']
    conv_3d_preview = states['conv_3d_preview']
    conv_3d_fullscreen = states['conv_3d_fullscreen']
    conv_2d_thumb_preview = states['conv_2d_thumb_preview']
    preprocess_processed_path = states['preprocess_processed_path']
    preview_event = states['preview_event']

    # ------------------------------------------------------------------
    # Wrapper function for 3MF generation
    # ------------------------------------------------------------------
    def generate_with_auto_preview(batch_files, is_batch, single_image, lut_path, target_width_mm,
                                   spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
                                   add_loop, loop_width, loop_length, loop_hole, loop_pos,
                                   modeling_mode, quantize_colors, color_replacements,
                                   separate_backing, enable_relief, color_height_map,
                                   heightmap_path, heightmap_max_height,
                                   enable_cleanup, enable_outline, outline_width,
                                   enable_cloisonne, wire_width_mm, wire_height_mm,
                                   free_color_set, enable_coating, coating_height_mm,
                                   radio_height_mode: str,
                                   preview_cache, theme_is_dark, processed_path=None,
                                   hue_weight: float = 0.0,
                                   progress=gr.Progress()):
        """Generate 3MF directly; preview is generated internally by convert_image_to_3d.

        Auto-preview pre-run is intentionally removed: it caused a full duplicate
        image-processing pass (4-35s) with no cache reuse, since preview_cache was
        never forwarded into process_batch_generation. Lower-level caches (O-3
        parse+clip, O-4 SVG raster) already prevent redundant work when the user
        runs preview before clicking this button.
        """
        # When SVG was uploaded, image_conv_image_label holds a PNG thumbnail while
        # preprocess_processed_path holds the original SVG. Use SVG for the converter.
        if processed_path and isinstance(processed_path, str) and processed_path.lower().endswith('.svg'):
            single_image = processed_path
        # Resolve UI radio value to backend height_mode parameter
        height_mode = resolve_height_mode(radio_height_mode)

        progress(0.0, desc="开始生成...")
        return process_batch_generation(
            batch_files, is_batch, single_image, lut_path, target_width_mm,
            spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
            add_loop, loop_width, loop_length, loop_hole, loop_pos,
            modeling_mode, quantize_colors, color_replacements,
            separate_backing, enable_relief, color_height_map,
            height_mode,
            heightmap_path, heightmap_max_height,
            enable_cleanup, enable_outline, outline_width,
            enable_cloisonne, wire_width_mm, wire_height_mm,
            free_color_set, enable_coating, coating_height_mm,
            hue_weight=float(hue_weight) if hue_weight else 0.0,
            progress=progress,
        )

    # ------------------------------------------------------------------
    # Generate button event
    # ------------------------------------------------------------------
    generate_event = components['btn_conv_generate_btn'].click(
            fn=generate_with_auto_preview,
            inputs=[
                components['file_conv_batch_input'],
                components['checkbox_conv_batch_mode'],
                components['image_conv_image_label'],
                conv_lut_path,
                components['slider_conv_width'],
                components['slider_conv_thickness'],
                components['radio_conv_structure'],
                components['checkbox_conv_auto_bg'],
                components['slider_conv_tolerance'],
                components['radio_conv_color_mode'],
                components['checkbox_conv_loop_enable'],
                components['slider_conv_loop_width'],
                components['slider_conv_loop_length'],
                components['slider_conv_loop_hole'],
                conv_loop_pos,
                components['radio_conv_modeling_mode'],
                components['slider_conv_quantize_colors'],
                conv_replacement_regions,
                components['checkbox_conv_separate_backing'],
                components['checkbox_conv_relief_mode'],
                conv_color_height_map,
                components['image_conv_heightmap'],
                components['slider_conv_auto_height_max'],
                components['checkbox_conv_cleanup'],
                components['checkbox_conv_outline_enable'],
                components['slider_conv_outline_width'],
                components['checkbox_conv_cloisonne_enable'],
                components['slider_conv_wire_width'],
                components['slider_conv_wire_height'],
                conv_free_color_set,
                components['checkbox_conv_coating_enable'],
                components['slider_conv_coating_height'],
                components['radio_conv_auto_height_mode'],
                conv_preview_cache,
                theme_state,
                preprocess_processed_path,
                components['slider_conv_hue_weight'],
            ],
            outputs=[
                components['file_conv_download_file'],
                conv_3d_preview,
                conv_preview,
                components['textbox_conv_status'],
                components['file_conv_color_recipe']
            ]
    )
    states['generate_event'] = generate_event
    components['conv_event'] = generate_event
    components['btn_conv_stop'].click(
        fn=None,
        inputs=None,
        outputs=None,
        cancels=[generate_event, preview_event]
    )
    components['state_conv_lut_path'] = conv_lut_path

    # ------------------------------------------------------------------
    # Invalidate cached 3MF when any generation parameter changes
    # ------------------------------------------------------------------
    # When user changes image, dimensions, color mode, modeling mode, or any other
    # parameter that affects the output, clear the cached 3MF file so the slicer
    # button will trigger a fresh generation instead of opening the stale model.
    _invalidate_fn = lambda: None  # Returns None to clear file component

    _param_components_change = [
        components['slider_conv_width'],
        components['slider_conv_thickness'],
        components['radio_conv_structure'],
        components['checkbox_conv_auto_bg'],
        components['slider_conv_tolerance'],
        components['radio_conv_color_mode'],
        components['radio_conv_modeling_mode'],
        components['slider_conv_quantize_colors'],
        components['checkbox_conv_loop_enable'],
        components['slider_conv_loop_width'],
        components['slider_conv_loop_length'],
        components['slider_conv_loop_hole'],
        components['checkbox_conv_separate_backing'],
        components['checkbox_conv_relief_mode'],
        components['checkbox_conv_cleanup'],
        components['checkbox_conv_outline_enable'],
        components['slider_conv_outline_width'],
        components['checkbox_conv_cloisonne_enable'],
        components['slider_conv_wire_width'],
        components['slider_conv_wire_height'],
        components['checkbox_conv_coating_enable'],
        components['slider_conv_coating_height'],
        components['slider_conv_auto_height_max'],
        components['radio_conv_auto_height_mode'],
    ]

    for comp in _param_components_change:
        comp.change(
            fn=_invalidate_fn,
            inputs=None,
            outputs=[components['file_conv_download_file']]
        )

    # ------------------------------------------------------------------
    # Slicer Integration Events
    # ------------------------------------------------------------------
    def on_open_slicer_click(slicer_id, file_obj, batch_files, is_batch, single_image, lut_path,
                            target_width_mm, spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
                            add_loop, loop_width, loop_length, loop_hole, loop_pos,
                            modeling_mode, quantize_colors, color_replacements,
                            separate_backing, enable_relief, color_height_map,
                            heightmap_path, heightmap_max_height,
                            enable_cleanup, enable_outline, outline_width,
                            enable_cloisonne, wire_width_mm, wire_height_mm,
                            free_color_set, enable_coating, coating_height_mm,
                            radio_height_mode: str,
                            preview_cache, theme_is_dark, processed_path=None,
                            hue_weight: float = 0.0):
        """Open file in slicer with auto-generation if needed."""

        # When SVG was uploaded, image_conv_image_label holds a PNG thumbnail while
        # preprocess_processed_path holds the original SVG. Use SVG for the converter.
        if processed_path and isinstance(processed_path, str) and processed_path.lower().endswith('.svg'):
            single_image = processed_path

        # Initialize color_recipe_path to avoid UnboundLocalError
        color_recipe_path = None

        # Resolve UI radio value to backend height_mode parameter
        height_mode = resolve_height_mode(radio_height_mode)

        # If no file exists, auto-generate the complete workflow
        if file_obj is None:
            print("[AUTO-SLICER] No 3MF file found, starting auto-generation workflow...")

            # Step 1: Generate preview if needed
            if preview_cache is None or not preview_cache:
                print("[AUTO-SLICER] Step 1/2: Generating preview...")
                try:
                    preview_img, cache, status, glb = generate_preview_cached_with_fit(
                        single_image, lut_path, target_width_mm, auto_bg, bg_tol,
                        color_mode, modeling_mode, quantize_colors, enable_cleanup, theme_is_dark
                    )
                    preview_cache = cache
                    print(f"[AUTO-SLICER] Preview generated: {status}")
                except Exception as e:
                    print(f"[AUTO-SLICER] Failed to generate preview: {e}")
                    return gr.update(), gr.update(), gr.update(), gr.update(), f"[ERROR] 预览生成失败: {e}"

            # Step 2: Generate 3MF model
            print("[AUTO-SLICER] Step 2/2: Generating 3MF model...")
            try:
                file_obj, glb, preview_img, status, color_recipe_path = process_batch_generation(
                    batch_files, is_batch, single_image, lut_path, target_width_mm,
                    spacer_thick, structure_mode, auto_bg, bg_tol, color_mode,
                    add_loop, loop_width, loop_length, loop_hole, loop_pos,
                    modeling_mode, quantize_colors, color_replacements,
                    separate_backing, enable_relief, color_height_map,
                    height_mode,
                    heightmap_path, heightmap_max_height,
                    enable_cleanup, enable_outline, outline_width,
                    enable_cloisonne, wire_width_mm, wire_height_mm,
                    free_color_set, enable_coating, coating_height_mm,
                    hue_weight=float(hue_weight) if hue_weight else 0.0,
                )
                print(f"[AUTO-SLICER] 3MF generated: {status}")
            except Exception as e:
                print(f"[AUTO-SLICER] Failed to generate 3MF: {e}")
                return gr.update(), gr.update(), gr.update(), gr.update(), f"[ERROR] 3MF生成失败: {e}"

        # Now open in slicer or download
        if slicer_id == "download":
            # Make file component visible so user can download
            if file_obj is not None:
                return file_obj, gr.update(visible=True), color_recipe_path, gr.update(visible=True), "📥 请点击下方文件下载"
            return None, gr.update(), gr.update(), gr.update(), "[ERROR] 没有可下载的文件"

        # Get actual file path from Gradio File object
        actual_path = None
        if file_obj is not None:
            if hasattr(file_obj, 'name'):
                actual_path = file_obj.name
            elif isinstance(file_obj, str):
                actual_path = file_obj

        if not actual_path:
            return None, gr.update(), gr.update(), gr.update(), "[ERROR] 生成失败，无法打开"

        status = open_in_slicer(actual_path, slicer_id)
        return file_obj, gr.update(), color_recipe_path, gr.update(), status

    # Bind each slicer button to the same handler with its own slicer_id
    _slicer_common_inputs = [
        # All generation parameters
        components['file_conv_batch_input'],
        components['checkbox_conv_batch_mode'],
        components['image_conv_image_label'],
        conv_lut_path,
        components['slider_conv_width'],
        components['slider_conv_thickness'],
        components['radio_conv_structure'],
        components['checkbox_conv_auto_bg'],
        components['slider_conv_tolerance'],
        components['radio_conv_color_mode'],
        components['checkbox_conv_loop_enable'],
        components['slider_conv_loop_width'],
        components['slider_conv_loop_length'],
        components['slider_conv_loop_hole'],
        conv_loop_pos,
        components['radio_conv_modeling_mode'],
        components['slider_conv_quantize_colors'],
        conv_replacement_regions,
        components['checkbox_conv_separate_backing'],
        components['checkbox_conv_relief_mode'],
        conv_color_height_map,
        components['image_conv_heightmap'],
        components['slider_conv_auto_height_max'],
        components['checkbox_conv_cleanup'],
        components['checkbox_conv_outline_enable'],
        components['slider_conv_outline_width'],
        components['checkbox_conv_cloisonne_enable'],
        components['slider_conv_wire_width'],
        components['slider_conv_wire_height'],
        conv_free_color_set,
        components['checkbox_conv_coating_enable'],
        components['slider_conv_coating_height'],
        components['radio_conv_auto_height_mode'],
        conv_preview_cache,
        theme_state,
        preprocess_processed_path,
        components['slider_conv_hue_weight'],
    ]
    _slicer_common_outputs = [
        components['file_conv_download_file'],
        components['file_conv_download_file'],
        components['file_conv_color_recipe'],
        conv_3d_preview,
        components['textbox_conv_status']
    ]

    for _label, _sid in _get_slicer_choices():
        _btn_key = f'btn_conv_slicer_{_sid}'
        _btn = components.get(_btn_key)
        if _btn is not None:
            # Create closure to capture slicer_id
            _make_fn = lambda sid=_sid: (lambda *args: on_open_slicer_click(sid, *args))
            _btn.click(
                fn=_make_fn(_sid),
                inputs=[components['file_conv_download_file']] + _slicer_common_inputs,
                outputs=_slicer_common_outputs,
            )

    # ------------------------------------------------------------------
    # Fullscreen 3D Toggle Events
    # ------------------------------------------------------------------
    components['btn_conv_3d_fullscreen'].click(
        fn=lambda glb, preview_img: (
            gr.update(visible=True),   # show fullscreen 3D
            glb,                        # load GLB into fullscreen
            gr.update(visible=True),   # show 2D thumbnail
            preview_img                 # load 2D preview into thumbnail
        ),
        inputs=[conv_3d_preview, conv_preview],
        outputs=[
            components['col_conv_3d_fullscreen'],
            conv_3d_fullscreen,
            components['col_conv_2d_thumbnail'],
            conv_2d_thumb_preview
        ]
    )

    components['btn_conv_2d_back'].click(
        fn=lambda: (gr.update(visible=False), gr.update(visible=False)),
        inputs=[],
        outputs=[components['col_conv_3d_fullscreen'], components['col_conv_2d_thumbnail']]
    )

    components['btn_conv_3d_back'].click(
        fn=lambda: (gr.update(visible=False), gr.update(visible=False)),
        inputs=[],
        outputs=[components['col_conv_3d_fullscreen'], components['col_conv_2d_thumbnail']]
    )

    # ------------------------------------------------------------------
    # Bed Size Change -> Re-render Preview
    # ------------------------------------------------------------------
    def on_bed_size_change(cache, bed_label, loop_pos, add_loop,
                           loop_width, loop_length, loop_hole, loop_angle):
        if cache is None:
            return gr.update(), cache
        preview_rgba = cache.get('preview_rgba')
        if preview_rgba is None:
            return gr.update(), cache
        # Store bed_label in cache so click handler can use it
        cache['bed_label'] = bed_label
        color_conf = cache['color_conf']
        is_dark = cache.get('is_dark', True)
        display = render_preview(
            preview_rgba,
            loop_pos if add_loop else None,
            loop_width, loop_length, loop_hole, loop_angle,
            add_loop, color_conf,
            bed_label=bed_label,
            target_width_mm=cache.get('target_width_mm'),
            is_dark=is_dark
        )
        return _preview_update(display), cache

    components['radio_conv_bed_size'].change(
        fn=on_bed_size_change,
        inputs=[
            conv_preview_cache,
            components['radio_conv_bed_size'],
            conv_loop_pos,
            components['checkbox_conv_loop_enable'],
            components['slider_conv_loop_width'],
            components['slider_conv_loop_length'],
            components['slider_conv_loop_hole'],
            components['slider_conv_loop_angle']
        ],
        outputs=[conv_preview, conv_preview_cache]
    )
