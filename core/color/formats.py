"""统一的颜色格式转换工具函数。"""

import re

_RGB_RE = re.compile(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)')


def rgb_to_hex(rgb) -> str:
    """将 RGB 元组/数组转换为 #RRGGBB 字符串。"""
    r, g, b = [int(x) for x in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """将颜色字符串转换为 (R, G, B) 元组。

    支持: '#RRGGBB', 'RRGGBB', 'rgb(r,g,b)', 'rgba(r,g,b,a)'
    """
    s = hex_str.strip()
    if s.startswith('rgb'):
        m = _RGB_RE.search(s)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        raise ValueError(f"Invalid rgb format: {s}")
    s = s.lstrip('#')
    if len(s) != 6:
        raise ValueError(f"Invalid hex color: #{s}")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
