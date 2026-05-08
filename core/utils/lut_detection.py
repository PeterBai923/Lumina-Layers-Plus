"""
LUT 模式检测工具

统一的 LUT 颜色模式检测功能，供多个模块使用。
"""

from typing import Optional, Tuple


# 组合数量到颜色数量的映射
SIZE_TO_COLOR_COUNT = {
    32: 2,    # BW: 2^5 = 32 combinations
    1024: 4,  # 4-Color: 4^5 = 1024 combinations
    2468: 5,  # 5-Color Extended: 1024 base + 1444 extended
    1296: 6,  # 6-Color: 6^4 = 1296 combinations (or 6^5 with restrictions)
    2738: 8,  # 8-Color: 2738 combinations
}

# 组合数量到模式名称的映射
SIZE_TO_MODE_NAME = {
    32: "BW",
    1024: "4-Color",
    2468: "5-Color Extended",
    1296: "6-Color",
    2738: "8-Color",
}

# 模式名称到颜色数量的映射
MODE_TO_COLOR_COUNT = {
    "BW": 2,
    "4-Color": 4,
    "5-Color Extended": 5,
    "6-Color": 6,
    "8-Color": 8,
    "Merged": 8,  # Merged LUT 使用 8 色作为上限
}


def detect_color_count_by_size(combination_count: int) -> int:
    """
    根据组合数量检测颜色数量。

    Args:
        combination_count: LUT 中的组合总数

    Returns:
        颜色数量 (2, 4, 5, 6, 8)，未知返回 0
    """
    return SIZE_TO_COLOR_COUNT.get(combination_count, 0)


def detect_mode_by_size(combination_count: int) -> Optional[str]:
    """
    根据组合数量检测颜色模式名称。

    Args:
        combination_count: LUT 中的组合总数

    Returns:
        模式名称 ("BW", "4-Color", etc.)，未知返回 None
    """
    # 精确匹配
    if combination_count in SIZE_TO_MODE_NAME:
        return SIZE_TO_MODE_NAME[combination_count]

    # BW 容差：30-36 (某些 BW LUT 有非标准大小)
    if 30 <= combination_count <= 36:
        return "BW"

    return None
