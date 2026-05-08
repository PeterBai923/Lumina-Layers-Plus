"""
Shared pytest fixtures and test utilities.

This module provides common fixtures used across multiple test files.
"""

from __future__ import annotations

import os
from typing import Any

import pytest


# ===========================================================================
# Test utilities
# ===========================================================================

# Save real os.path.join to avoid recursion when patching
_real_path_join = os.path.join


def make_join_redirector(assets_dir: str):
    """Create an os.path.join side_effect that redirects temp_5c files to assets_dir.

    创建一个 os.path.join side_effect，将 temp_5c 文件重定向到 assets_dir。

    Args:
        assets_dir: 目标目录路径

    Returns:
        可用作 mock side_effect 的函数

    Usage:
        with patch("api.routers.extractor.os.path.join",
                   side_effect=make_join_redirector(tmpdir)):
            ...
    """
    def _join(*args: Any) -> str:
        last = args[-1] if args else ""
        if isinstance(last, str) and "temp_5c" in last:
            return _real_path_join(assets_dir, last)
        return _real_path_join(*args)
    return _join