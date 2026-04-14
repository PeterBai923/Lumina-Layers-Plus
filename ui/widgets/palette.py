"""
Lumina Studio - Color Palette Extension
Non-invasive color palette functionality extension for the converter tab.

This module provides enhanced color palette display without modifying core files.
Text and percentage are displayed BELOW the color swatches for better readability.
Click handlers are defined globally in crop_extension.py to survive Gradio re-renders.
"""

from typing import List


def build_hue_filter_bar_html(lang: str = "zh") -> str:
    """Build the hue filter button bar HTML (shared by swatch, card, and palette grids)."""
    hue_labels = [
        ("all", "全部", "#666"),
        ("red", "红色", "#e53935"),
        ("orange", "橙色", "#fb8c00"),
        ("yellow", "黄色", "#fdd835"),
        ("green", "绿色", "#43a047"),
        ("cyan", "青色", "#00acc1"),
        ("blue", "蓝色", "#1e88e5"),
        ("purple", "紫色", "#8e24aa"),
        ("neutral", "灰色", "#9e9e9e"),
        ("fav", "收藏", "#ffc107"),
    ]
    parts = [
        '<div id="lut-hue-filter-bar" class="flex-center gap-xs" style="flex-wrap:wrap; margin-bottom:8px;">'
    ]
    for hue_key, hue_label, hue_color in hue_labels:
        active_class = " active" if hue_key == "all" else ""
        if hue_key == "all":
            dot = ""
        elif hue_key == "neutral":
            dot = f'<span class="hue-dot" style="background:{hue_color};border:1px solid #666;"></span>'
        elif hue_key == "fav":
            dot = '<span style="font-size:8px;margin-right:1px;vertical-align:middle;">⭐</span>'
        else:
            dot = f'<span class="hue-dot" style="background:{hue_color};"></span>'
        parts.append(
            f'<button class="lut-hue-btn{active_class}" data-hue="{hue_key}" '
            f"onclick=\"window.lutHueDispatch && window.lutHueDispatch('{hue_key}', this)\""
            f">{dot}{hue_label}</button>"
        )
    parts.append("</div>")
    return "".join(parts)


def build_search_bar_html(lang: str = "zh") -> str:
    """Build the search input bar HTML (shared by swatch and card grids)."""
    search_placeholder = "搜索十六进制颜色..."
    search_clear = "清除"
    return f"""<div class="flex-center gap-md" style="margin-bottom:8px;">
        <span style="font-size:12px; color:#666;">🔍</span>
        <input type="text" id="lut-color-search" class="lut-search-input" placeholder="{search_placeholder}"
               oninput="window.lutSearchDispatch && window.lutSearchDispatch(this.value)" />
        <button class="btn-chip" onclick="document.getElementById('lut-color-search').value=''; window.lutSearchDispatch && window.lutSearchDispatch('');">{search_clear}</button>
    </div>"""


def dedupe_auto_pairs(pairs):
    """按 (quantized_hex, matched_hex) 去重，保留首次出现顺序。"""
    seen = set()
    out = []
    for p in pairs or []:
        q = (p.get("quantized_hex") or "").lower()
        m = (p.get("matched_hex") or "").lower()
        k = (q, m)
        if not q or not m or k in seen:
            continue
        seen.add(k)
        out.append({"quantized_hex": q, "matched_hex": m})
    return out


def generate_palette_html(
    palette: List[dict],
    replacements: dict = None,
    selected_color: str = None,
    lang: str = "zh",
    replacement_regions: list = None,
    auto_pairs: list = None,
    selected_user_row_id: str = None,
    selected_auto_row_id: str = None,
) -> str:
    """渲染已生效替换区：左用户替换列表 + 右自动配准列表（行级交互）。"""
    if not palette and not replacement_regions:
        return f'<p class="placeholder-text">{"暂无颜色，请先生成预览。"}</p>'

    replacement_regions = replacement_regions or []

    # 用户替换：仅使用 replacement_regions，最新在前（row_id 基于反转前稳定生成）
    raw_user_rows = []
    for item in replacement_regions:
        raw_user_rows.append(
            {
                "quantized": (
                    item.get("quantized") or item.get("source") or ""
                ).lower(),
                "matched": (item.get("matched") or item.get("source") or "").lower(),
                "replacement": (item.get("replacement") or "").lower(),
            }
        )
    filtered_user_rows = [
        r for r in raw_user_rows if r["quantized"] and r["replacement"]
    ]
    user_rows = []
    for idx, r in enumerate(filtered_user_rows):
        rr = dict(r)
        rr["row_id"] = (
            f"user::{rr['quantized']}|{rr['matched']}|{rr['replacement']}|{idx}"
        )
        user_rows.append(rr)
    user_rows = list(reversed(user_rows))

    # 自动配准（右栏）
    auto_rows = []
    for idx, r in enumerate(dedupe_auto_pairs(auto_pairs or [])):
        qh, mh = r["quantized_hex"], r["matched_hex"]
        auto_rows.append(
            {
                "quantized_hex": qh,
                "matched_hex": mh,
                "row_id": f"auto::{qh}|{mh}|{idx}",
            }
        )

    def _sw(hex_color):
        return (
            f"<span class='lut-color-swatch swatch-xs' data-color='{hex_color}' "
            f"style='background:{hex_color};vertical-align:middle;margin-right:6px;'></span>"
            f"<span class='text-caption'>{hex_color}</span>"
        )

    user_title = "用户替换"
    auto_title = "自动配准"
    delete_btn_text = "删除选中"
    user_empty = "暂无替换"
    auto_empty = "暂无自动配准"
    delete_disabled = " disabled" if not selected_user_row_id else ""

    html = [
        "<div id='palette-grid-container'>",
        "<div class='palette-list-card'>",
        "<div class='palette-list-header'>",
        f"<div class='section-title'>{user_title}</div>",
        f"<button id='conv-palette-delete-selected' class='palette-delete-btn'{delete_disabled}>{delete_btn_text}</button>",
        "</div>",
        "<div class='palette-list-scroll'>",
    ]

    if user_rows:
        for r in user_rows:
            item_class = (
                "palette-list-item is-selected"
                if r["row_id"] == selected_user_row_id
                else "palette-list-item"
            )
            html.append(
                f"<div class='{item_class}' data-row-type='user' data-row-id='{r['row_id']}' "
                f"data-quantized='{r['quantized']}' data-matched='{r['matched']}' data-replacement='{r['replacement']}'>"
                f"<div class='flex-center gap-lg' style='flex-wrap:wrap;'>"
                f"<div>{_sw(r['quantized'])}</div>"
                f"<div>{_sw(r['matched'])}</div>"
                f"<div>{_sw(r['replacement'])}</div>"
                "</div></div>"
            )
    else:
        html.append(f"<div class='empty-hint'>{user_empty}</div>")

    html.extend(
        [
            "</div>",
            "</div>",
            "<div class='palette-list-card'>",
            "<div class='palette-list-header'>",
            f"<div class='section-title'>{auto_title}</div>",
            "</div>",
            "<div class='palette-list-scroll'>",
        ]
    )

    if auto_rows:
        for r in auto_rows:
            qh, mh = r["quantized_hex"], r["matched_hex"]
            item_class = (
                "palette-list-item is-selected"
                if r["row_id"] == selected_auto_row_id
                else "palette-list-item"
            )
            html.append(
                f"<div class='{item_class}' data-row-type='auto' data-row-id='{r['row_id']}' "
                f"data-quantized='{qh}' data-matched='{mh}' data-replacement=''>"
                f"<div class='flex-center gap-lg' style='flex-wrap:wrap;'>"
                f"<div>{_sw(qh)}</div>"
                f"<div>{_sw(mh)}</div>"
                "</div></div>"
            )
    else:
        html.append(f"<div class='empty-hint'>{auto_empty}</div>")

    html.extend(["</div>", "</div>", "</div>"])
    return "".join(html)


def build_selected_dual_color_html(
    quantized_hex: str = None, matched_hex: str = None, lang: str = "zh"
) -> str:
    """渲染"当前选中"双颜色块：量化色 + 原配准色（含下方编码）。"""
    qh = quantized_hex.lower() if isinstance(quantized_hex, str) else "#000000"
    mh = matched_hex.lower() if isinstance(matched_hex, str) else "#000000"

    q_label = "量化色"
    m_label = "原配准色"

    def _card(label, hex_color):
        return (
            "<div class='flex-col-center gap-xs'>"
            f"<div class='text-caption'>{label}</div>"
            f"<div class='lut-color-swatch swatch-xl' style='background:{hex_color};'></div>"
            f"<div class='text-caption'>{hex_color}</div>"
            "</div>"
        )

    return (
        "<div class='flex-center gap-lg' style='align-items:flex-start;padding:4px 0;'>"
        + _card(q_label, qh)
        + _card(m_label, mh)
        + "</div>"
    )


def generate_lut_color_grid_html(
    colors: List[dict],
    selected_color: str = None,
    used_colors: set = None,
    lang: str = "zh",
) -> str:
    """
    Generate HTML for displaying LUT available colors as a clickable visual grid.
    Text is displayed BELOW the color swatches.
    Includes hex/RGB search, hue filter buttons, and scroll-to-highlight.
    Uses event delegation for click handling.

    Args:
        colors: List of color dicts with 'color' (R,G,B) and 'hex' keys
        selected_color: Currently selected replacement color hex
        used_colors: Set of hex colors currently used in the image (for grouping)

    Returns:
        HTML string showing available colors as a clickable grid with search & filters
    """
    if not colors:
        return '<p class="placeholder-text">💡 拖放.npy文件自动添加</p>'

    used_colors = used_colors or set()
    used_colors_lower = {c.lower() for c in used_colors}

    # Separate colors into used and unused
    used_in_image = []
    not_used = []

    for entry in colors:
        hex_color = entry["hex"]
        if hex_color.lower() in used_colors_lower:
            used_in_image.append(entry)
        else:
            not_used.append(entry)

    count_text = f'🎨 当前 LUT 包含 <b>{len(colors)}</b> 种可打印颜色（点击选择）'

    html_parts = [
        f'<p class="text-caption" style="margin-bottom:8px;">{count_text}: <span id="lut-color-visible-count">{len(colors)}</span></p>',
        build_search_bar_html(lang),
        build_hue_filter_bar_html(lang),
    ]

    html_parts.append(
        '<div id="lut-color-grid-container" style="max-height:400px; overflow-y:auto; padding:4px;">'
    )

    def _classify_hue(r, g, b):
        """Classify RGB color into hue category."""
        import colorsys

        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
        h360 = h * 360
        # Neutral: low saturation or very dark/light
        if s < 0.15 or v < 0.10:
            return "neutral"
        # Hue ranges
        if h360 < 15 or h360 >= 345:
            return "red"
        elif h360 < 40:
            return "orange"
        elif h360 < 70:
            return "yellow"
        elif h360 < 160:
            return "green"
        elif h360 < 195:
            return "cyan"
        elif h360 < 260:
            return "blue"
        elif h360 < 345:
            return "purple"
        return "neutral"

    def render_color_grid(color_list, section_title=None, section_color="#666"):
        """Helper to render a section of colors with data-hue attribute."""
        parts = []
        if section_title:
            parts.append(
                f'<p class="section-title" style="color:{section_color}; margin:8px 0 4px 0;">{section_title}</p>'
            )
        parts.append(
            '<div class="flex-center gap-md" style="flex-wrap:wrap; margin-bottom:12px;">'
        )

        for entry in color_list:
            hex_color = entry["hex"]
            r, g, b = entry["color"]
            hue_cat = _classify_hue(r, g, b)

            is_selected = selected_color and hex_color.lower() == selected_color.lower()
            outline_style = (
                "outline: var(--swatch-selected-outline); outline-offset: var(--swatch-selected-offset);"
                if is_selected
                else ""
            )

            tooltip = f"点击高亮: {hex_color}"
            parts.append(
                f"""
            <div class="lut-color-swatch-container flex-col-center gap-xs" data-hue="{hue_cat}">
                <div class="lut-color-swatch swatch-lg" style="background:{hex_color}; cursor:pointer; {outline_style}" data-color="{hex_color}" title="{tooltip}"></div>
                <div class="text-caption" style="text-align:center; font-size:9px;">{hex_color}</div>
            </div>
            """
            )

        parts.append("</div>")
        return parts

    # Render used colors section (if any)
    if used_in_image:
        section_title = f"✅ 图像中使用 ({len(used_in_image)})"
        html_parts.extend(render_color_grid(used_in_image, section_title, "#4CAF50"))

    # Render unused colors section
    if not_used:
        section_title = None
        if used_in_image:
            section_title = f"其他 ({len(not_used)})"
        html_parts.extend(render_color_grid(not_used, section_title, "#888"))

    html_parts.append("</div>")

    return "".join(html_parts)


def generate_dual_recommendations_html(recommendations: dict, lang: str = "zh") -> str:
    """渲染双基准推荐区 HTML，复用 .lut-color-swatch 交互。"""
    if not recommendations:
        return ""

    by_q = recommendations.get("by_quantized", [])
    by_m = recommendations.get("by_matched", [])

    title_q = "按量化色推荐"
    title_m = "按原配准色推荐"

    def _render_group(title, items):
        parts = [
            f"<div style='margin:6px 0;'>",
            f"<div class='section-title'>{title}</div>",
            "<div class='flex-center gap-sm' style='flex-wrap:wrap;'>",
        ]
        for entry in items:
            hex_color = entry["hex"]
            parts.append(
                f"<div class='lut-color-swatch swatch-md' data-color='{hex_color}' "
                f"style='background:{hex_color};' title='{hex_color}'></div>"
            )
        parts.append("</div></div>")
        return "".join(parts)

    return (
        "<div id='dual-recommendations' class='dashed-box' style='padding:6px;margin:6px 0;'>"
        + _render_group(title_q, by_q)
        + _render_group(title_m, by_m)
        + "</div>"
    )
