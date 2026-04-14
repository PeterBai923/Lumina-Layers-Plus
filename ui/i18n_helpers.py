# -*- coding: utf-8 -*-
"""Lumina Studio - HTML rendering helpers (header, stats, footer)."""


def _get_header_html() -> str:
    """Return header HTML (title + subtitle)."""
    return "<h1>✨ Lumina Studio</h1><p>多材料3D打印色彩系统 | v1.6.7</p>"


def _get_stats_html(stats: dict) -> str:
    """Return stats bar HTML (calibrations / extractions / conversions)."""
    return f"""
    <div class="stats-bar">
        📊 累计生成:
        <strong>{stats.get('calibrations', 0)}</strong> 校准板 |
        <strong>{stats.get('extractions', 0)}</strong> 颜色提取 |
        <strong>{stats.get('conversions', 0)}</strong> 模型转换
    </div>
    """


def _get_footer_html() -> str:
    """Return footer HTML."""
    return """
    <div class="footer">
        <p>💡 提示: 使用高质量的PLA/PETG basic材料可获得最佳效果</p>
    </div>
    """
