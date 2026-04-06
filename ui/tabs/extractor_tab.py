# -*- coding: utf-8 -*-
"""
Lumina Studio - Color Extractor Tab
Self-contained module for color extraction tab: UI, callbacks, and helpers.
"""

import os
import numpy as np
import gradio as gr
from PIL import Image as PILImage

from core.i18n import I18n
from config import ColorSystem, LUT_FILE_PATH
from core.extractor import (
    rotate_image,
    draw_corner_points,
    run_extraction,
    probe_lut_cell,
    manual_fix_cell,
)


# ═══════════════════════════════════════════════════════════════
# Extractor Helpers
# ═══════════════════════════════════════════════════════════════

def _get_corner_labels(mode, page_choice=None):
    if mode is not None and "5-Color Extended" in mode and page_choice is not None and "2" in str(page_choice):
        return ["蓝色 (左上)", "红色 (右上)", "黑色 (右下)", "黄色 (左下)"], None
    conf = ColorSystem.get(mode)
    return conf['corner_labels'], conf.get('corner_labels_en', conf['corner_labels'])


def get_first_hint(mode, page_choice=None):
    labels_zh, labels_en = _get_corner_labels(mode, page_choice)
    label_zh = labels_zh[0]
    label_en = label_zh if labels_en is None else labels_en[0]
    return f"#### 👉 点击 Click: **{label_zh} / {label_en}**"


def get_next_hint(mode, pts_count, page_choice=None):
    labels_zh, labels_en = _get_corner_labels(mode, page_choice)
    if pts_count >= 4:
        return "#### [OK] Positioning complete! Ready to extract!"
    label_zh = labels_zh[pts_count]
    label_en = label_zh if labels_en is None else labels_en[pts_count]
    return f"#### 👉 点击 Click: **{label_zh} / {label_en}**"


# ═══════════════════════════════════════════════════════════════
# Extractor Callbacks
# ═══════════════════════════════════════════════════════════════

def on_extractor_upload(i, mode, page_choice=None):
    """Handle image upload"""
    hint = get_first_hint(mode, page_choice)
    return i, i, [], None, hint


def on_extractor_mode_change(img, mode, page_choice=None):
    """Handle color mode change"""
    hint = get_first_hint(mode, page_choice)
    # Show page selector and merge button for dual-page modes
    is_dual_page = "8-Color" in mode or "5-Color Extended" in mode
    return [], hint, img, gr.update(visible=is_dual_page), gr.update(visible=is_dual_page)


def on_extractor_rotate(i, mode, page_choice=None):
    """Rotate image"""
    if i is None:
        return None, None, [], get_first_hint(mode, page_choice)
    r = rotate_image(i, "Rotate Left 90°")
    return r, r, [], get_first_hint(mode, page_choice)


def on_extractor_click(img, pts, mode, page_choice, evt: gr.SelectData):
    """Set corner point by clicking image"""
    if len(pts) >= 4:
        return img, pts, "#### [OK] 定位完成 Complete!"
    n = pts + [[evt.index[0], evt.index[1]]]
    vis = draw_corner_points(img, n, mode, page_choice)
    hint = get_next_hint(mode, len(n), page_choice)
    return vis, n, hint


def on_extractor_clear(img, mode, page_choice=None):
    """Clear corner points"""
    hint = get_first_hint(mode, page_choice)
    return img, [], hint


def on_extractor_page_change(img, mode, page_choice):
    hint = get_first_hint(mode, page_choice)
    return [], hint, img


# ═══════════════════════════════════════════════════════════════
# Extraction Wrapper & Merge
# ═══════════════════════════════════════════════════════════════

def run_extraction_wrapper(img, points, offset_x, offset_y, zoom, barrel, wb, bright, color_mode, page_choice):
    """Wrapper for extraction: supports 8-Color and 5-Color Extended page saving."""

    run_mode = color_mode

    vis, prev, lut_path, status = run_extraction(
        img, points, offset_x, offset_y, zoom, barrel, wb, bright, run_mode, page_choice
    )

    # Handle 8-Color dual-page saving
    if "8-Color" in color_mode and lut_path:
        import sys
        # Handle both dev and frozen modes
        if getattr(sys, 'frozen', False):
            assets_dir = os.path.join(os.getcwd(), "assets")
        else:
            assets_dir = "assets"

        os.makedirs(assets_dir, exist_ok=True)
        page_idx = 1 if "1" in str(page_choice) else 2
        temp_path = os.path.join(assets_dir, f"temp_8c_page_{page_idx}.npy")
        try:
            lut = np.load(lut_path)
            np.save(temp_path, lut)
            # Return the assets path, not the original LUT_FILE_PATH
            # This ensures manual corrections are saved to the correct location
            print(f"[8-COLOR] Saved page {page_idx} to: {temp_path}")
            lut_path = temp_path
        except Exception as e:
            print(f"[8-COLOR] Error saving page {page_idx}: {e}")

    # Handle 5-Color Extended dual-page saving
    if "5-Color Extended" in color_mode and lut_path:
        import sys
        # Handle both dev and frozen modes
        if getattr(sys, 'frozen', False):
            assets_dir = os.path.join(os.getcwd(), "assets")
        else:
            assets_dir = "assets"

        os.makedirs(assets_dir, exist_ok=True)
        page_idx = 1 if "1" in str(page_choice) else 2
        temp_path = os.path.join(assets_dir, f"temp_5c_ext_page_{page_idx}.npy")
        try:
            lut = np.load(lut_path)
            np.save(temp_path, lut)
            print(f"[5C-EXT] Saved page {page_idx} to: {temp_path}")
            lut_path = temp_path
        except Exception as e:
            print(f"[5C-EXT] Error saving page {page_idx}: {e}")

    return vis, prev, lut_path, status


def merge_8color_data():
    """Concatenate two 8-color pages and save to LUT_FILE_PATH."""
    import sys
    # Handle both dev and frozen modes
    if getattr(sys, 'frozen', False):
        assets_dir = os.path.join(os.getcwd(), "assets")
    else:
        assets_dir = "assets"

    path1 = os.path.join(assets_dir, "temp_8c_page_1.npy")
    path2 = os.path.join(assets_dir, "temp_8c_page_2.npy")

    print(f"[MERGE_8COLOR] Looking for page 1: {path1}")
    print(f"[MERGE_8COLOR] Looking for page 2: {path2}")
    print(f"[MERGE_8COLOR] Page 1 exists: {os.path.exists(path1)}")
    print(f"[MERGE_8COLOR] Page 2 exists: {os.path.exists(path2)}")

    if not os.path.exists(path1) or not os.path.exists(path2):
        return None, "[ERROR] Missing temp pages. Please extract Page 1 and Page 2 first."

    try:
        lut1 = np.load(path1)
        lut2 = np.load(path2)
        print(f"[MERGE_8COLOR] Page 1 shape: {lut1.shape}")
        print(f"[MERGE_8COLOR] Page 2 shape: {lut2.shape}")

        merged = np.concatenate([lut1, lut2], axis=0)
        print(f"[MERGE_8COLOR] Merged shape: {merged.shape}")

        np.save(LUT_FILE_PATH, merged)
        print(f"[MERGE_8COLOR] Saved merged LUT to: {LUT_FILE_PATH}")

        return LUT_FILE_PATH, "[OK] 8-Color LUT merged and saved!"
    except Exception as e:
        print(f"[MERGE_8COLOR] Error: {e}")
        import traceback
        traceback.print_exc()
        return None, f"[ERROR] Merge failed: {e}"


def merge_5color_extended_data():
    """Concatenate two 5-Color Extended pages and save to LUT_FILE_PATH."""
    import sys
    # Handle both dev and frozen modes
    if getattr(sys, 'frozen', False):
        assets_dir = os.path.join(os.getcwd(), "assets")
    else:
        assets_dir = "assets"

    path1 = os.path.join(assets_dir, "temp_5c_ext_page_1.npy")
    path2 = os.path.join(assets_dir, "temp_5c_ext_page_2.npy")

    print(f"[MERGE_5C_EXT] Looking for page 1: {path1}")
    print(f"[MERGE_5C_EXT] Looking for page 2: {path2}")
    print(f"[MERGE_5C_EXT] Page 1 exists: {os.path.exists(path1)}")
    print(f"[MERGE_5C_EXT] Page 2 exists: {os.path.exists(path2)}")

    if not os.path.exists(path1) or not os.path.exists(path2):
        return None, "❌ Missing temp pages. Please extract Page 1 and Page 2 first."

    try:
        lut1 = np.load(path1)
        lut2 = np.load(path2)
        print(f"[MERGE_5C_EXT] Page 1 shape: {lut1.shape}")
        print(f"[MERGE_5C_EXT] Page 2 shape: {lut2.shape}")

        lut1_rgb = lut1.reshape(-1, 3)
        lut2_rgb = lut2.reshape(-1, 3)
        merged = np.vstack([lut1_rgb, lut2_rgb]).astype(np.uint8, copy=False)
        print(f"[MERGE_5C_EXT] Merged shape: {merged.shape}")

        np.save(LUT_FILE_PATH, merged)
        print(f"[MERGE_5C_EXT] Saved merged LUT to: {LUT_FILE_PATH}")

        return LUT_FILE_PATH, "✅ 5-Color Extended LUT merged and saved! (2468 colors)"
    except Exception as e:
        print(f"[MERGE_5C_EXT] Error: {e}")
        import traceback
        traceback.print_exc()
        return None, f"❌ Merge failed: {e}"


# ═══════════════════════════════════════════════════════════════
# Reference Image Generator
# ═══════════════════════════════════════════════════════════════

def get_extractor_reference_image(mode_str, page_choice="Page 1"):
    """Load or generate reference image for color extractor (disk-cached).

    Uses assets/ with filenames ref_bw_standard.png, ref_cmyw_standard.png,
    ref_rybw_standard.png, ref_5color_ext_page1.png, ref_5color_ext_page2.png,
    ref_6color_smart.png, or ref_8color_smart.png.
    Generates via calibration board logic if missing.

    Args:
        mode_str: Color mode label (e.g. "BW", "CMYW", "RYBW", "6-Color", "8-Color").

    Returns:
        PIL.Image.Image | None: Reference image or None on error.
    """
    import sys

    # Handle both dev and frozen modes
    if getattr(sys, 'frozen', False):
        # In frozen mode, check both _MEIPASS (bundled) and cwd (user data)
        cache_dir = os.path.join(os.getcwd(), "assets")
        bundled_assets = os.path.join(sys._MEIPASS, "assets")
    else:
        cache_dir = "assets"
        bundled_assets = None

    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir, exist_ok=True)

    # Determine filename and generation mode based on color system
    gen_page_idx = 0
    if "8-Color" in mode_str:
        filename = "ref_8color_smart.png"
        gen_mode = "8-Color"
    elif "5-Color Extended" in mode_str:
        is_page2 = page_choice is not None and "2" in str(page_choice)
        filename = "ref_5color_ext_page2.png" if is_page2 else "ref_5color_ext_page1.png"
        gen_mode = "5-Color Extended"
        gen_page_idx = 1 if is_page2 else 0
    elif "6-Color" in mode_str or "1296" in mode_str:
        filename = "ref_6color_smart.png"
        gen_mode = "6-Color"
    elif "4-Color" in mode_str:
        # Unified 4-Color mode defaults to RYBW
        filename = "ref_rybw_standard.png"
        gen_mode = "RYBW"
    elif "CMYW" in mode_str:
        filename = "ref_cmyw_standard.png"
        gen_mode = "CMYW"
    elif "RYBW" in mode_str:
        filename = "ref_rybw_standard.png"
        gen_mode = "RYBW"
    elif mode_str == "BW (Black & White)" or mode_str == "BW":
        filename = "ref_bw_standard.png"
        gen_mode = "BW"
    else:
        # Default to RYBW
        filename = "ref_rybw_standard.png"
        gen_mode = "RYBW"

    filepath = os.path.join(cache_dir, filename)

    # In frozen mode, also check bundled assets
    if bundled_assets:
        bundled_filepath = os.path.join(bundled_assets, filename)
        if os.path.exists(bundled_filepath):
            try:
                print(f"[UI] Loading reference from bundle: {bundled_filepath}")
                return PILImage.open(bundled_filepath)
            except Exception as e:
                print(f"Error loading bundled asset: {e}")

    if os.path.exists(filepath):
        try:
            print(f"[UI] Loading reference from cache: {filepath}")
            return PILImage.open(filepath)
        except Exception as e:
            print(f"Error loading cache, regenerating: {e}")

    print(f"[UI] Generating new reference for {gen_mode}...")
    try:
        block_size = 10
        gap = 0
        backing = "White"

        if gen_mode == "8-Color":
            from core.calibration import generate_8color_board
            _, img, _ = generate_8color_board(0)  # Page 1
        elif gen_mode == "5-Color Extended":
            from core.calibration import generate_5color_extended_board
            _, img, _ = generate_5color_extended_board(block_size, gap, page_index=gen_page_idx)
        elif gen_mode == "6-Color":
            from core.calibration import generate_smart_board
            _, img, _ = generate_smart_board(block_size, gap)
        elif gen_mode == "BW":
            from core.calibration import generate_bw_calibration_board
            _, img, _ = generate_bw_calibration_board(block_size, gap, backing)
        else:
            from core.calibration import generate_calibration_board
            _, img, _ = generate_calibration_board(gen_mode, block_size, gap, backing)

        if img:
            if not isinstance(img, PILImage.Image):
                img = PILImage.fromarray(img.astype('uint8'), 'RGB')

            img.save(filepath)
            print(f"[UI] Cached reference saved to {filepath}")

        return img

    except Exception as e:
        print(f"Error generating reference: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# Tab UI Builder (main entry point)
# ═══════════════════════════════════════════════════════════════

def create_extractor_tab_content(lang: str) -> dict:
    """Build color extractor tab UI and events. Returns component dict."""
    components = {}
    ext_state_img = gr.State(None)
    ext_state_pts = gr.State([])
    ext_curr_coord = gr.State(None)
    default_mode = "4-Color"
    ref_img = get_extractor_reference_image(default_mode)

    with gr.Row():
        with gr.Column(scale=1):
            components['md_ext_upload_section'] = gr.Markdown(
                I18n.get('ext_upload_section', lang)
            )

            components['radio_ext_color_mode'] = gr.Radio(
                choices=[
                    ("BW (Black & White)", "BW (Black & White)"),
                    ("4-Color (1024 colors)", "4-Color"),
                    ("5-Color Extended (2468)", "5-Color Extended"),
                    ("6-Color (Smart 1296)", "6-Color (Smart 1296)"),
                    ("8-Color Max", "8-Color Max")
                ],
                value="4-Color",
                label=I18n.get('ext_color_mode', lang)
            )

            # Page selection for dual-page modes (8-Color and 5-Color Extended)
            components['radio_ext_page'] = gr.Radio(
                choices=["Page 1", "Page 2"],
                value="Page 1",
                label="Page Selection",
                visible=False
            )

            ext_img_in = gr.Image(
                label=I18n.get('ext_photo', lang),
                type="numpy",
                interactive=True,
            )

            with gr.Row():
                components['btn_ext_rotate_btn'] = gr.Button(
                    I18n.get('ext_rotate_btn', lang)
                )
                components['btn_ext_reset_btn'] = gr.Button(
                    I18n.get('ext_reset_btn', lang)
                )

            components['md_ext_correction_section'] = gr.Markdown(
                I18n.get('ext_correction_section', lang)
            )

            with gr.Row():
                components['checkbox_ext_wb'] = gr.Checkbox(
                    label=I18n.get('ext_wb', lang),
                    value=False
                )
                components['checkbox_ext_vignette'] = gr.Checkbox(
                    label=I18n.get('ext_vignette', lang),
                    value=False
                )

            components['slider_ext_zoom'] = gr.Slider(
                0.8, 1.2, 1.0, step=0.005,
                label=I18n.get('ext_zoom', lang)
            )

            components['slider_ext_distortion'] = gr.Slider(
                -0.2, 0.2, 0.0, step=0.01,
                label=I18n.get('ext_distortion', lang)
            )

            components['slider_ext_offset_x'] = gr.Slider(
                -30, 30, 0, step=1,
                label=I18n.get('ext_offset_x', lang)
            )

            components['slider_ext_offset_y'] = gr.Slider(
                -30, 30, 0, step=1,
                label=I18n.get('ext_offset_y', lang)
            )

            # Page selection moved above, controlled by color mode

            components['btn_ext_extract_btn'] = gr.Button(
                I18n.get('ext_extract_btn', lang),
                variant="primary",
                elem_classes=["primary-btn"]
            )

            components['btn_ext_merge_btn'] = gr.Button(
                "Merge Dual Pages",
                visible=False  # Hidden by default, shown when dual-page mode selected
            )

            components['textbox_ext_status'] = gr.Textbox(
                label=I18n.get('ext_status', lang),
                interactive=False
            )

        with gr.Column(scale=1):
            ext_hint = gr.Markdown(I18n.get('ext_hint_white', lang))

            ext_work_img = gr.Image(
                label=I18n.get('ext_marked', lang),
                show_label=False,
                interactive=True
            )

            with gr.Row():
                with gr.Column():
                    components['md_ext_sampling'] = gr.Markdown(
                        I18n.get('ext_sampling', lang)
                    )
                    ext_warp_view = gr.Image(show_label=False)

                with gr.Column():
                    components['md_ext_reference'] = gr.Markdown(
                        I18n.get('ext_reference', lang)
                    )
                    ext_ref_view = gr.Image(
                        show_label=False,
                        value=ref_img,
                        interactive=False
                    )

            with gr.Row():
                with gr.Column():
                    components['md_ext_result'] = gr.Markdown(
                        I18n.get('ext_result', lang)
                    )
                    ext_lut_view = gr.Image(
                        show_label=False,
                        interactive=True
                    )

                with gr.Column():
                    components['md_ext_manual_fix'] = gr.Markdown(
                        I18n.get('ext_manual_fix', lang)
                    )
                    ext_probe_html = gr.HTML(I18n.get('ext_click_cell', lang))

                    ext_picker = gr.ColorPicker(
                        label=I18n.get('ext_override', lang),
                        value="#FF0000"
                    )

                    components['btn_ext_apply_btn'] = gr.Button(
                        I18n.get('ext_apply_btn', lang)
                    )

                    components['file_ext_download_npy'] = gr.File(
                        label=I18n.get('ext_download_npy', lang)
                    )

    ext_img_in.upload(
            on_extractor_upload,
            [ext_img_in, components['radio_ext_color_mode'], components['radio_ext_page']],
            [ext_state_img, ext_work_img, ext_state_pts, ext_curr_coord, ext_hint]
    )

    components['radio_ext_color_mode'].change(
            on_extractor_mode_change,
            [ext_state_img, components['radio_ext_color_mode'], components['radio_ext_page']],
            [ext_state_pts, ext_hint, ext_work_img, components['radio_ext_page'], components['btn_ext_merge_btn']]
    )

    components['radio_ext_color_mode'].change(
        fn=get_extractor_reference_image,
        inputs=[components['radio_ext_color_mode'], components['radio_ext_page']],
        outputs=[ext_ref_view]
    )

    components['btn_ext_rotate_btn'].click(
            on_extractor_rotate,
            [ext_state_img, components['radio_ext_color_mode'], components['radio_ext_page']],
            [ext_state_img, ext_work_img, ext_state_pts, ext_hint]
    )

    ext_work_img.select(
            on_extractor_click,
            [ext_state_img, ext_state_pts, components['radio_ext_color_mode'], components['radio_ext_page']],
            [ext_work_img, ext_state_pts, ext_hint]
    )

    components['btn_ext_reset_btn'].click(
            on_extractor_clear,
            [ext_state_img, components['radio_ext_color_mode'], components['radio_ext_page']],
            [ext_work_img, ext_state_pts, ext_hint]
    )

    components['radio_ext_page'].change(
            on_extractor_page_change,
            [ext_state_img, components['radio_ext_color_mode'], components['radio_ext_page']],
            [ext_state_pts, ext_hint, ext_work_img]
    ).then(
        fn=get_extractor_reference_image,
        inputs=[components['radio_ext_color_mode'], components['radio_ext_page']],
        outputs=[ext_ref_view]
    )

    extract_inputs = [
            ext_state_img, ext_state_pts,
            components['slider_ext_offset_x'], components['slider_ext_offset_y'],
            components['slider_ext_zoom'], components['slider_ext_distortion'],
            components['checkbox_ext_wb'], components['checkbox_ext_vignette'],
            components['radio_ext_color_mode'],
            components['radio_ext_page']
    ]
    extract_outputs = [
            ext_warp_view, ext_lut_view,
            components['file_ext_download_npy'], components['textbox_ext_status']
    ]

    ext_event = components['btn_ext_extract_btn'].click(run_extraction_wrapper, extract_inputs, extract_outputs)
    components['ext_event'] = ext_event

    # Dynamic merge button handler based on color mode
    def merge_dual_pages_wrapper(color_mode):
        """Route to correct merge function based on color mode."""
        if "5-Color Extended" in color_mode:
            return merge_5color_extended_data()
        else:
            return merge_8color_data()

    components['btn_ext_merge_btn'].click(
            merge_dual_pages_wrapper,
            inputs=[components['radio_ext_color_mode']],
            outputs=[components['file_ext_download_npy'], components['textbox_ext_status']]
    )

    for s in [components['slider_ext_offset_x'], components['slider_ext_offset_y'],
                  components['slider_ext_zoom'], components['slider_ext_distortion']]:
            s.release(run_extraction_wrapper, extract_inputs, extract_outputs)

    ext_lut_view.select(
            probe_lut_cell,
            [components['file_ext_download_npy']],
            [ext_probe_html, ext_picker, ext_curr_coord]
    )
    components['btn_ext_apply_btn'].click(
            manual_fix_cell,
            [ext_curr_coord, ext_picker, components['file_ext_download_npy']],
            [ext_lut_view, components['textbox_ext_status']]
    )

    return components
