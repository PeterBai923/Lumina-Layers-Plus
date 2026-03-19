"""
孤立像素清理 re-export 模块（Isolated Pixel Cleanup）

从 core/isolated_pixel_cleanup.py re-export cleanup_isolated_pixels。
不复制代码，仅做导入转发。

Re-export cleanup_isolated_pixels from core/isolated_pixel_cleanup.py.
"""

from core.isolated_pixel_cleanup import cleanup_isolated_pixels

__all__ = ['cleanup_isolated_pixels']
