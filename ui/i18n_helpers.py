# -*- coding: utf-8 -*-
"""Lumina Studio - i18n update helpers and HTML rendering."""

import gradio as gr

from core.i18n import I18n
from utils import Stats
from config import ModelingMode
from .helpers import _format_bytes


def _get_header_html(lang: str) -> str:
    """Return header HTML (title + subtitle) for the given language."""
    return f"<h1>✨ Lumina Studio</h1><p>{I18n.get('app_subtitle', lang)}</p>"


def _get_stats_html(lang: str, stats: dict) -> str:
    """Return stats bar HTML (calibrations / extractions / conversions)."""
    return f"""
    <div class="stats-bar">
        {I18n.get('stats_total', lang)}:
        <strong>{stats.get('calibrations', 0)}</strong> {I18n.get('stats_calibrations', lang)} |
        <strong>{stats.get('extractions', 0)}</strong> {I18n.get('stats_extractions', lang)} |
        <strong>{stats.get('conversions', 0)}</strong> {I18n.get('stats_conversions', lang)}
    </div>
    """


def _get_footer_html(lang: str) -> str:
    """Return footer HTML for the given language."""
    return f"""
    <div class="footer">
        <p>{I18n.get('footer_tip', lang)}</p>
    </div>
    """


def _get_all_component_updates(lang: str, components: dict) -> list:
    """Build a list of gr.update() for all components to apply i18n.

    Skips dynamic status components (md_conv_lut_status, textbox_conv_status)
    so their runtime text is not overwritten.
    Also skips event objects (Dependency) which are not valid components.

    Args:
        lang: Target language code ('zh' or 'en').
        components: Dict of component key -> Gradio component.

    Returns:
        list: One gr.update() per component, in dict iteration order.
    """
    from gradio.blocks import Block
    updates = []
    for key, component in components.items():
        # Skip event objects (Dependency)
        if not isinstance(component, Block):
            continue

        if key == 'md_conv_lut_status' or key == 'textbox_conv_status':
            updates.append(gr.update())
            continue
        if key == 'md_settings_title':
            updates.append(gr.update(value=I18n.get('settings_title', lang)))
            continue
        if key == 'md_cache_size':
            cache_size = Stats.get_cache_size()
            updates.append(gr.update(value=I18n.get('settings_cache_size', lang).format(_format_bytes(cache_size))))
            continue
        if key == 'btn_clear_cache':
            updates.append(gr.update(value=I18n.get('settings_clear_cache', lang)))
            continue
        if key == 'md_output_size':
            output_size = Stats.get_output_size()
            updates.append(gr.update(value=I18n.get('settings_output_size', lang).format(_format_bytes(output_size))))
            continue
        if key == 'btn_clear_output':
            updates.append(gr.update(value=I18n.get('settings_clear_output', lang)))
            continue
        if key == 'btn_reset_counters':
            updates.append(gr.update(value=I18n.get('settings_reset_counters', lang)))
            continue
        if key == 'md_settings_status':
            updates.append(gr.update())
            continue
        # Merge tab: skip dynamic status
        if key == 'md_merge_status':
            updates.append(gr.update())
            continue
        if key == 'md_merge_title':
            updates.append(gr.update(value=I18n.get('merge_title', lang)))
            continue
        if key == 'md_merge_desc':
            updates.append(gr.update(value=I18n.get('merge_desc', lang)))
            continue
        if key == 'md_merge_mode_primary':
            updates.append(gr.update())  # dynamic, don't overwrite
            continue
        if key == 'md_merge_secondary_info':
            updates.append(gr.update())  # dynamic, don't overwrite
            continue
        if key == 'dd_merge_primary':
            updates.append(gr.update(label=I18n.get('merge_lut_primary_label', lang)))
            continue
        if key == 'dd_merge_secondary':
            updates.append(gr.update(label=I18n.get('merge_lut_secondary_label', lang)))
            continue
        if key == 'slider_dedup_threshold':
            updates.append(gr.update(
                label=I18n.get('merge_dedup_label', lang),
                info=I18n.get('merge_dedup_info', lang),
            ))
            continue
        if key == 'btn_merge':
            updates.append(gr.update(value=I18n.get('merge_btn', lang)))
            continue

        if key.startswith('md_'):
            updates.append(gr.update(value=I18n.get(key[3:], lang)))
        elif key.startswith('lbl_'):
            updates.append(gr.update(label=I18n.get(key[4:], lang)))
        elif key.startswith('btn_'):
            updates.append(gr.update(value=I18n.get(key[4:], lang)))
        elif key.startswith('radio_'):
            choice_key = key[6:]
            if choice_key == 'conv_color_mode' or choice_key == 'cal_color_mode' or choice_key == 'ext_color_mode':
                choices = [
                    ("BW (Black & White)", "BW (Black & White)"),
                    ("4-Color (1024 colors)", "4-Color"),
                    ("5-Color Extended (2468)", "5-Color Extended"),
                    ("6-Color (Smart 1296)", "6-Color (Smart 1296)"),
                    ("8-Color Max", "8-Color Max"),
                ]
                # Only the converter tab needs the Merged option
                if choice_key == 'conv_color_mode':
                    choices.append(("🔀 Merged", "Merged"))
                updates.append(gr.update(
                    label=I18n.get(choice_key, lang),
                    choices=choices,
                ))
            elif choice_key == 'conv_structure':
                updates.append(gr.update(
                    label=I18n.get(choice_key, lang),
                    choices=[
                        (I18n.get('conv_structure_double', lang), I18n.get('conv_structure_double', 'en')),
                        (I18n.get('conv_structure_single', lang), I18n.get('conv_structure_single', 'en'))
                    ]
                ))
            elif choice_key == 'conv_modeling_mode':
                updates.append(gr.update(
                    label=I18n.get(choice_key, lang),
                    info=I18n.get('conv_modeling_mode_info', lang),
                    choices=[
                        (I18n.get('conv_modeling_mode_hifi', lang), ModelingMode.HIGH_FIDELITY),
                        (I18n.get('conv_modeling_mode_pixel', lang), ModelingMode.PIXEL),
                        (I18n.get('conv_modeling_mode_vector', lang), ModelingMode.VECTOR)
                    ]
                ))
            else:
                # Fallback for radios without i18n mapping (e.g., ext_page)
                updates.append(gr.update())
        elif key.startswith('slider_'):
            slider_key = key[7:]
            updates.append(gr.update(label=I18n.get(slider_key, lang)))
        elif key.startswith('color_'):
            color_key = key[6:]
            updates.append(gr.update(label=I18n.get(color_key, lang)))
        elif key.startswith('checkbox_'):
            checkbox_key = key[9:]
            info_key = checkbox_key + '_info'
            if info_key in I18n.TEXTS:
                updates.append(gr.update(
                    label=I18n.get(checkbox_key, lang),
                    info=I18n.get(info_key, lang)
                ))
            else:
                updates.append(gr.update(label=I18n.get(checkbox_key, lang)))
        elif key.startswith('dropdown_'):
            dropdown_key = key[9:]
            info_key = dropdown_key + '_info'
            if info_key in I18n.TEXTS:
                updates.append(gr.update(
                    label=I18n.get(dropdown_key, lang),
                    info=I18n.get(info_key, lang)
                ))
            else:
                updates.append(gr.update(label=I18n.get(dropdown_key, lang)))
        elif key.startswith('image_'):
            image_key = key[6:]
            updates.append(gr.update(label=I18n.get(image_key, lang)))
        elif key.startswith('file_'):
            file_key = key[5:]
            updates.append(gr.update(label=I18n.get(file_key, lang)))
        elif key.startswith('textbox_'):
            textbox_key = key[8:]
            updates.append(gr.update(label=I18n.get(textbox_key, lang)))
        elif key.startswith('num_'):
            num_key = key[4:]
            updates.append(gr.update(label=I18n.get(num_key, lang)))
        elif key == 'html_crop_modal':
            from ui.crop_extension import get_crop_modal_html
            updates.append(gr.update(value=get_crop_modal_html(lang)))
        elif key.startswith('html_'):
            html_key = key[5:]
            updates.append(gr.update(value=I18n.get(html_key, lang)))
        elif key.startswith('accordion_'):
            acc_key = key[10:]
            updates.append(gr.update(label=I18n.get(acc_key, lang)))
        else:
            updates.append(gr.update())

    return updates


def _get_component_list(components: dict) -> list:
    """Return component values in dict order (for Gradio outputs).

    Filters out event objects (Dependency) which are not valid outputs.
    """
    from gradio.blocks import Block
    result = []
    for v in components.values():
        if isinstance(v, Block):
            result.append(v)
    return result
