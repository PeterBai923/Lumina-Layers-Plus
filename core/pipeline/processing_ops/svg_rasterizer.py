"""
SVG 双通道光栅化模块（SVG Rasterizer）

从 image_processing.py 的 _load_svg 方法搬入。
使用白底/黑底差分法检测透明度，保证内容零损伤。

SVG dual-pass rasterization using white/black background differencing.
Extracted from LuminaImageProcessor._load_svg.
"""

import os
import numpy as np
import cv2

# SVG support (optional dependency)
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    HAS_SVG = True
except ImportError:
    HAS_SVG = False

_SVG_RASTER_CACHE = {}
_SVG_RASTER_CACHE_MAX = 4


def rasterize_svg(svg_path: str, target_width_mm: float,
                  pixels_per_mm: float = 20.0) -> np.ndarray:
    """SVG 双通道光栅化。
    Safe Padding + Dual-Pass Transparency Detection.

    Method: Render twice (White BG / Black BG).
    - If pixel changes color -> It's background (Transparent) -> Remove it.
    - If pixel stays same -> It's content (Opaque) -> Keep it 100% intact.

    This guarantees NO internal image damage.

    Args:
        svg_path: SVG 文件路径
        target_width_mm: 目标宽度（毫米）
        pixels_per_mm: 光栅化密度，20.0 用于最终输出，10.0 用于预览

    Returns:
        (H, W, 4) uint8 RGBA numpy 数组
    """
    if not HAS_SVG:
        raise ImportError("Please install 'svglib' and 'reportlab'.")

    cache_key = None
    try:
        svg_abs = os.path.abspath(svg_path)
        svg_mtime = os.path.getmtime(svg_abs)
        cache_key = (svg_abs, round(float(target_width_mm), 4), round(float(pixels_per_mm), 2), svg_mtime)
        cached = _SVG_RASTER_CACHE.get(cache_key)
        if cached is not None:
            print(f"[SVG] Cache hit: {os.path.basename(svg_abs)} @ {pixels_per_mm}px/mm")
            return cached.copy()
    except Exception:
        cache_key = None

    print(f"[SVG] Rasterizing: {svg_path}")

    # 1. 读取 SVG
    drawing = svg2rlg(svg_path)

    # --- 步骤 A: 用几何边界确定内容区域 ---
    # getBounds() 返回 SVG 几何坐标系下的内容边界，不依赖像素透明度检测，
    # 在任何分辨率下都完全可靠，彻底消除因抗锯齿导致的内容被裁切问题。
    x1, y1, x2, y2 = drawing.getBounds()
    raw_w = x2 - x1
    raw_h = y2 - y1

    # 平移至原点，仅保留 2px 的固定安全边距（不再使用百分比浮动边距）
    BORDER_PX_PRE = 4  # 渲染前在画布上留的固定余量（坐标单位）
    drawing.translate(-x1, -y1)
    drawing.width  = raw_w
    drawing.height = raw_h

    # 2. 缩放到目标像素宽度（强制最低渲染质量保证 Dual-Pass 效果）
    target_width_px = int(target_width_mm * pixels_per_mm)
    MIN_QUALITY_PX  = 800
    render_width_px = max(target_width_px, MIN_QUALITY_PX)

    if raw_w > 0:
        scale_factor = render_width_px / raw_w
    else:
        scale_factor = 1.0

    drawing.scale(scale_factor, scale_factor)
    render_w = max(1, int(raw_w  * scale_factor))
    render_h = max(1, int(raw_h  * scale_factor))
    drawing.width  = render_w
    drawing.height = render_h

    # ================== 【终极方案】双重渲染差分法 ==================
    try:
        # Pass 1: 白底渲染 (0xFFFFFF)
        # 强制不使用透明通道，完全模拟打印在白纸上的效果
        pil_white = renderPM.drawToPIL(drawing, bg=0xFFFFFF, configPIL={'transparent': False})
        arr_white = np.array(pil_white.convert('RGB'))  # 丢弃 Alpha，只看颜色

        # Pass 2: 黑底渲染 (0x000000)
        # 强制不使用透明通道，完全模拟打印在黑纸上的效果
        pil_black = renderPM.drawToPIL(drawing, bg=0x000000, configPIL={'transparent': False})
        arr_black = np.array(pil_black.convert('RGB'))

        # 计算差异 (Difference)
        # diff = |白底图 - 黑底图|
        # 如果像素是实心的，它挡住了背景，所以在白底和黑底上颜色一样 -> diff 为 0
        # 如果像素是透明的，它透出了背景，所以在白底是白，黑底是黑 -> diff 很大
        diff = np.abs(arr_white.astype(int) - arr_black.astype(int))
        diff_sum = np.sum(diff, axis=2)

        # 生成 Alpha 掩膜（严格阈值，保证下游色彩精度）
        alpha_mask = np.where(diff_sum < 10, 255, 0).astype(np.uint8)

        # 合成最终图像
        r, g, b = cv2.split(arr_white)
        img_final = cv2.merge([r, g, b, alpha_mask])

        # ── 几何裁切（替代原 Dual-Pass Crop 像素检测）──────────────────
        # 渲染画布已对齐到内容原点，直接取 render_w × render_h 即为完整内容。
        # 仅在数组边界内添加 2px 固定留白，避免抗锯齿边缘被截断。
        BORDER = 2
        h_arr, w_arr = img_final.shape[:2]
        x_start = max(0, -BORDER)
        y_start = max(0, -BORDER)
        x_end   = min(w_arr, render_w + BORDER)
        y_end   = min(h_arr, render_h + BORDER)
        img_final = img_final[y_start:y_end, x_start:x_end]
        print(f"[SVG] Geometry Crop: {img_final.shape[1]}x{img_final.shape[0]} (bounds-based, lossless)")

        # 若渲染时为保证质量而放大，缩回目标像素宽度
        if render_width_px > target_width_px and target_width_px > 0:
            scale_back = target_width_px / render_width_px
            out_w = max(1, round(img_final.shape[1] * scale_back))
            out_h = max(1, round(img_final.shape[0] * scale_back))
            img_final = cv2.resize(img_final, (out_w, out_h), interpolation=cv2.INTER_AREA)
            print(f"[SVG] Scaled to target: {out_w}x{out_h} px")

        print(f"[SVG] Final resolution: {img_final.shape[1]}x{img_final.shape[0]} px")
        if cache_key is not None:
            _SVG_RASTER_CACHE[cache_key] = img_final.copy()
            while len(_SVG_RASTER_CACHE) > _SVG_RASTER_CACHE_MAX:
                _SVG_RASTER_CACHE.pop(next(iter(_SVG_RASTER_CACHE)))
        return img_final

    except Exception as e:
        print(f"[SVG] Dual-Pass failed: {e}")
        import traceback
        traceback.print_exc()

        # 最后的保底：如果双重渲染失败，回退到普通渲染
        pil_img = renderPM.drawToPIL(drawing, bg=None, configPIL={'transparent': True})
        img_fallback = np.array(pil_img.convert('RGBA'))
        if cache_key is not None:
            _SVG_RASTER_CACHE[cache_key] = img_fallback.copy()
            while len(_SVG_RASTER_CACHE) > _SVG_RASTER_CACHE_MAX:
                _SVG_RASTER_CACHE.pop(next(iter(_SVG_RASTER_CACHE)))
        return img_fallback
