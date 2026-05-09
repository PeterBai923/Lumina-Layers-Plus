"""
Lumina Studio - Image Processing Core

Handles image loading, preprocessing, color quantization and matching.
"""

import os
import sys
import numpy as np
import cv2
from PIL import Image
from scipy.spatial import KDTree

from config import PrinterConfig, ModelingMode, ColorSystem, get_asset_path
from core.stack_encoding import encode_to_base
from core.utils.color_encoding import build_color_lut, lookup_colors
from core.utils.color_conversion import rgb_to_lab
from core.utils.gpu_device import GPUDeviceManager
from core.utils.logger import get_logger

logger = get_logger("PROCESSOR")

# HEIC/HEIF support (optional dependency)
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# SVG support (optional dependency)
try:
    from svglib.svglib import svg2rlg
    from reportlab.graphics import renderPM
    HAS_SVG = True
except ImportError:
    HAS_SVG = False
    logger.warning("[SVG] svglib/reportlab 未安装，SVG 支持已禁用")

# GPU modules (required)
from core.gpu_kmeans import KMeansBackend
from core.gpu_pipeline import GPUPipeline

_SVG_RASTER_CACHE = {}
_SVG_RASTER_CACHE_MAX = 4


class LuminaImageProcessor:
    """
    Image processor class.

    Handles LUT loading, image processing, and color matching.
    """

    @staticmethod
    def _rgb_to_lab(rgb_array: np.ndarray) -> np.ndarray:
        """Convert RGB to LAB using GPU."""
        import torch
        device = GPUDeviceManager().get_device()
        tensor = torch.from_numpy(rgb_array.astype(np.float32)).to(device)
        lab_tensor = rgb_to_lab(tensor)
        return lab_tensor.cpu().numpy()

    def __init__(self, lut_path, color_mode, hue_weight: float = 0.0):
        """
        Initialize image processor.
        
        Args:
            lut_path: LUT file path (.npy)
            color_mode: Color mode string (CMYW/RYBW/6-Color)
            hue_weight: 色相感知权重 (0.0-1.0)
                        0.0 = 纯 CIELAB 距离（默认，兼容原有行为）
                        0.3-0.5 = 平衡模式（推荐）
                        1.0 = 最强色相保护
        """
        self.lut_path = lut_path  # Store LUT path for color recipe logging
        self.color_mode = color_mode
        self.hue_weight = float(hue_weight)
        self.layer_count = ColorSystem.get(color_mode).get('layer_count', PrinterConfig.COLOR_LAYERS)
        self.lut_rgb = None
        self.lut_lab = None  # CIELAB 空间的 LUT 颜色（用于 KDTree 匹配）
        self.ref_stacks = None
        self.kdtree = None
        self.hue_matcher = None  # 色相感知匹配器（hue_weight > 0 时初始化）
        self.enable_cleanup = True
        
        self._load_lut(lut_path)
    
    def _load_svg(self, svg_path, target_width_mm, pixels_per_mm: float = 20.0):
        """
        [Final Fix] Safe Padding + Dual-Pass Transparency Detection.
        
        Method: Render twice (White BG / Black BG).
        - If pixel changes color -> It's background (Transparent) -> Remove it.
        - If pixel stays same -> It's content (Opaque) -> Keep it 100% intact.
        
        This guarantees NO internal image damage.
        
        Args:
            pixels_per_mm: Rasterization density. 20.0 for final output, 10.0 for previews.
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
                logger.info("[SVG] 缓存命中: %s @ %s px/mm", os.path.basename(svg_abs), pixels_per_mm)
                return cached.copy()
        except Exception:
            cache_key = None
        
        logger.info("[SVG] 正在栅格化: %s", svg_path)
        
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
            arr_white = np.array(pil_white.convert('RGB'))
            
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
            logger.info("[SVG] 几何裁切: %sx%s（基于边界，无损）", img_final.shape[1], img_final.shape[0])

            # 若渲染时为保证质量而放大，缩回目标像素宽度
            if render_width_px > target_width_px and target_width_px > 0:
                scale_back = target_width_px / render_width_px
                out_w = max(1, round(img_final.shape[1] * scale_back))
                out_h = max(1, round(img_final.shape[0] * scale_back))
                img_final = cv2.resize(img_final, (out_w, out_h), interpolation=cv2.INTER_AREA)
                logger.info("[SVG] 缩放至目标: %sx%s 像素", out_w, out_h)

            logger.info("[SVG] 最终分辨率: %sx%s 像素", img_final.shape[1], img_final.shape[0])
            if cache_key is not None:
                _SVG_RASTER_CACHE[cache_key] = img_final.copy()
                while len(_SVG_RASTER_CACHE) > _SVG_RASTER_CACHE_MAX:
                    _SVG_RASTER_CACHE.pop(next(iter(_SVG_RASTER_CACHE)))
            return img_final
            
        except Exception as e:
            logger.exception("[SVG] 双重渲染失败: %s", e)

            # 最后的保底：如果双重渲染失败，回退到普通渲染
            pil_img = renderPM.drawToPIL(drawing, bg=None, configPIL={'transparent': True})
            img_fallback = np.array(pil_img.convert('RGBA'))
            if cache_key is not None:
                _SVG_RASTER_CACHE[cache_key] = img_fallback.copy()
                while len(_SVG_RASTER_CACHE) > _SVG_RASTER_CACHE_MAX:
                    _SVG_RASTER_CACHE.pop(next(iter(_SVG_RASTER_CACHE)))
            return img_fallback
    
    def _load_lut(self, lut_path):
        """
        Load and validate LUT file (Supports 2-Color, 4-Color, 6-Color, 8-Color, and Merged).
        
        Automatically detects LUT type based on size:
        - .npz files: Merged LUT (contains rgb + stacks arrays)
        - 32 colors: 2-Color BW (Black & White)
        - 1024 colors: 4-Color Standard (CMYW/RYBW)
        - 1296 colors: 6-Color Smart 1296
        - 2738 colors: 8-Color Max
        - Other sizes: Merged LUT (try .npz companion file)
        """
        # 合并 LUT 支持：.npz 格式直接加载 rgb + stacks
        if lut_path.endswith('.npz'):
            try:
                data = np.load(lut_path)
                self.lut_rgb = data['rgb']
                self.ref_stacks = data['stacks']
                if isinstance(self.ref_stacks, np.ndarray) and self.ref_stacks.ndim == 2:
                    self.layer_count = int(self.ref_stacks.shape[1])
                self.lut_lab = self._rgb_to_lab(self.lut_rgb)
                self.kdtree = KDTree(self.lut_lab)
                logger.info("合并 LUT 已加载: %s 个颜色（.npz 格式，Lab KDTree）", len(self.lut_rgb))
                
                # 初始化色相感知匹配器（仅当 hue_weight > 0 时）
                if self.hue_weight > 0:
                    from core.color.matching import HueAwareColorMatcher
                    self.hue_matcher = HueAwareColorMatcher(
                        self.lut_rgb, self.lut_lab, hue_weight=self.hue_weight
                    )
                return
            except Exception as e:
                raise ValueError(f"❌ Merged LUT file corrupted: {e}")

        try:
            lut_grid = np.load(lut_path)
            measured_colors = lut_grid.reshape(-1, 3)
            total_colors = measured_colors.shape[0]
        except Exception as e:
            raise ValueError(f"❌ LUT file corrupted: {e}")
        
        valid_rgb = []
        valid_stacks = []
        
        logger.info("正在加载 LUT（%s 个点）...", total_colors)
        
        # Branch 0: 2-Color BW (32)
        if self.color_mode == "BW (Black & White)" or self.color_mode == "BW" or total_colors == 32:
            logger.info("检测到 2色黑白模式")
            
            # Generate all 32 combinations (2^5 = 32)
            for i in range(32):
                if i >= total_colors:
                    break
                
                # Rebuild 2-base stacking (0..31)
                stack = encode_to_base(i, 2)  # [顶...底] format
                
                valid_rgb.append(measured_colors[i])
                valid_stacks.append(stack)
            
            self.lut_rgb = np.array(valid_rgb)
            self.ref_stacks = np.array(valid_stacks)
            if isinstance(self.ref_stacks, np.ndarray) and self.ref_stacks.ndim == 2:
                self.layer_count = int(self.ref_stacks.shape[1])
            
            logger.info("LUT 已加载: %s 个颜色（2色黑白模式）", len(self.lut_rgb))
        
        # Branch 1: 8-Color Max (2738)
        elif "8-Color" in self.color_mode or total_colors == 2738:
            logger.info("检测到 8色最大模式")
            
            # Load pre-generated 8-color stacks
            stacks_path = get_asset_path('smart_8color_stacks.npy')
            
            smart_stacks = np.load(stacks_path).tolist()
            
            # 约定转换：smart_8color_stacks.npy 存储底到顶约定（stack[0]=背面），
            # 转换为顶到底约定（stack[0]=观赏面, stack[4]=背面），与 4 色模式统一
            smart_stacks = [tuple(reversed(s)) for s in smart_stacks]
            logger.info("堆栈已从底到顶转换为顶到底约定（与 4色模式统一）")

            if len(smart_stacks) != total_colors:
                logger.warning("警告: 堆栈数量 (%s) != LUT 数量 (%s)", len(smart_stacks), total_colors)
                min_len = min(len(smart_stacks), total_colors)
                smart_stacks = smart_stacks[:min_len]
                measured_colors = measured_colors[:min_len]
            
            self.lut_rgb = measured_colors
            self.ref_stacks = np.array(smart_stacks)
            if isinstance(self.ref_stacks, np.ndarray) and self.ref_stacks.ndim == 2:
                self.layer_count = int(self.ref_stacks.shape[1])
            
            logger.info("LUT 已加载: %s 个颜色（8色模式）", len(self.lut_rgb))
        
        # Branch 2: 6-Color Smart 1296
        elif "6-Color" in self.color_mode or total_colors == 1296:
            logger.info("检测到 6色 Smart 1296 模式")
            
            from core.calibration import get_top_1296_colors
            
            smart_stacks = get_top_1296_colors()
            # 约定转换：get_top_1296_colors() 返回底到顶约定（stack[0]=背面），
            # 转换为顶到底约定（stack[0]=观赏面, stack[4]=背面），与 4 色模式统一
            smart_stacks = [tuple(reversed(s)) for s in smart_stacks]
            logger.info("堆栈已从底到顶转换为顶到底约定（与 4色模式统一）")

            if len(smart_stacks) != total_colors:
                logger.warning("警告: 堆栈数量 (%s) != LUT 数量 (%s)", len(smart_stacks), total_colors)
                min_len = min(len(smart_stacks), total_colors)
                smart_stacks = smart_stacks[:min_len]
                measured_colors = measured_colors[:min_len]
            
            self.lut_rgb = measured_colors
            self.ref_stacks = np.array(smart_stacks)
            if isinstance(self.ref_stacks, np.ndarray) and self.ref_stacks.ndim == 2:
                self.layer_count = int(self.ref_stacks.shape[1])
            
            logger.info("LUT 已加载: %s 个颜色（6色模式）", len(self.lut_rgb))
        
        # Branch 3: 5-Color Extended (2468)
        elif "5-Color Extended" in self.color_mode or total_colors == 2468:
            logger.info("检测到 5色扩展模式（2468）")
            
            # For .npz files, load stacks directly
            if lut_path.endswith('.npz'):
                try:
                    data = np.load(lut_path)
                    stacks = data['stacks']
                    # Ensure 6-layer stacks and convert to top-to-bottom convention
                    if stacks.shape[1] == 6:
                        self.ref_stacks = np.array([tuple(reversed(s)) for s in stacks])
                        self.layer_count = int(self.ref_stacks.shape[1])
                        self.lut_rgb = measured_colors
                        logger.info("LUT 已加载: %s 个颜色（5色扩展，6层堆栈）", len(self.lut_rgb))
                        
                        # Build KD-Tree and hue matcher for early-return path
                        self.lut_lab = self._rgb_to_lab(self.lut_rgb)
                        self.kdtree = KDTree(self.lut_lab)
                        if self.hue_weight > 0:
                            from core.color.matching import HueAwareColorMatcher
                            self.hue_matcher = HueAwareColorMatcher(
                                self.lut_rgb, self.lut_lab, hue_weight=self.hue_weight
                            )
                        return
                except Exception as e:
                    logger.warning("从 .npz 加载堆栈失败: %s", e)
            
            # Fallback: generate stacks from index
            # First 1024: base 5-layer (4^5 combinations), pad to 6 layers
            # Next 1444: extended 6-layer from select_extended_1444_colors()
            ref_stacks = []
            
            # Generate base 1024 stacks (5-layer, pad with air(-1) at viewing end)
            # Air at index 0 offsets the base viewing surface by 1 Z level
            # so it doesn't share the same Z as extended viewing surfaces.
            for i in range(min(1024, total_colors)):
                stack = (-1,) + tuple(encode_to_base(i, 4))
                ref_stacks.append(stack)
            
            # Generate extended 1444 stacks using select_extended_1444_colors
            if total_colors > 1024:
                from core.calibration import select_extended_1444_colors
                base_5layer = [tuple(reversed([i//4**j%4 for j in range(5)])) for i in range(1024)]
                extended_stacks = select_extended_1444_colors(base_5layer)
                
                # Add extended stacks (already in correct 6-layer format)
                for i in range(min(len(extended_stacks), total_colors - 1024)):
                    ref_stacks.append(extended_stacks[i])
            
            self.lut_rgb = measured_colors
            self.ref_stacks = np.array(ref_stacks)
            if isinstance(self.ref_stacks, np.ndarray) and self.ref_stacks.ndim == 2:
                self.layer_count = int(self.ref_stacks.shape[1])
            
            logger.info("LUT 已加载: %s 个颜色（5色扩展）", len(self.lut_rgb))
        
        # Branch 4: Merged LUT (non-standard size or "Merged" mode)
        elif self.color_mode == "Merged" or total_colors not in (32, 1024, 1296, 2468, 2738):
            logger.info("检测到非标准 LUT 大小（%s），尝试查找伴随 .npz 文件...", total_colors)
            
            # 尝试查找同名 .npz 文件
            npz_path = lut_path.rsplit('.', 1)[0] + '.npz'
            if os.path.exists(npz_path):
                try:
                    data = np.load(npz_path)
                    self.lut_rgb = data['rgb']
                    self.ref_stacks = data['stacks']
                    if isinstance(self.ref_stacks, np.ndarray) and self.ref_stacks.ndim == 2:
                        self.layer_count = int(self.ref_stacks.shape[1])
                    self.lut_lab = self._rgb_to_lab(self.lut_rgb)
                    self.kdtree = KDTree(self.lut_lab)
                    logger.info("从伴随 .npz 加载合并 LUT: %s 个颜色（Lab KDTree）", len(self.lut_rgb))
                    
                    # 初始化色相感知匹配器（仅当 hue_weight > 0 时）
                    if self.hue_weight > 0:
                        from core.color.matching import HueAwareColorMatcher
                        self.hue_matcher = HueAwareColorMatcher(
                            self.lut_rgb, self.lut_lab, hue_weight=self.hue_weight
                        )
                    return
                except Exception as e:
                    logger.warning("加载伴随 .npz 失败: %s", e)
            
            # 无 .npz 伴随文件，使用 RGB 数据但无堆叠信息
            # 生成占位堆叠（全0）
            logger.warning("未找到伴随 .npz 文件，使用占位堆栈")
            self.lut_rgb = measured_colors
            self.ref_stacks = np.zeros((total_colors, self.layer_count), dtype=np.int32)
            
            logger.info("LUT 已加载: %s 个颜色（合并模式，占位堆栈）", len(self.lut_rgb))
        
        # Branch 5: 4-Color Standard (1024)
        else:
            logger.info("检测到 4色标准模式")
            
            # Keep original outlier filtering logic (Blue Check)
            base_blue = np.array([30, 100, 200])
            dropped = 0
            
            for i in range(1024):
                if i >= total_colors:
                    break
                
                # Rebuild 4-base stacking (0..1023)
                stack = encode_to_base(i, 4)
                
                real_rgb = measured_colors[i]
                
                # Filter outliers: close to blue but doesn't contain blue
                dist = np.linalg.norm(real_rgb - base_blue)
                if dist < 60 and 3 not in stack:  # 3 is Blue in RYBW/CMYW
                    dropped += 1
                    continue
                
                valid_rgb.append(real_rgb)
                valid_stacks.append(stack)
            
            self.lut_rgb = np.array(valid_rgb)
            self.ref_stacks = np.array(valid_stacks)
            if isinstance(self.ref_stacks, np.ndarray) and self.ref_stacks.ndim == 2:
                self.layer_count = int(self.ref_stacks.shape[1])
            
            logger.info("LUT 已加载: %s 个颜色（已过滤 %s 个异常值）", len(self.lut_rgb), dropped)
        
        # Build KD-Tree in CIELAB space for perceptually accurate color matching
        self.lut_lab = self._rgb_to_lab(self.lut_rgb)
        self.kdtree = KDTree(self.lut_lab)
        
        # 初始化色相感知匹配器（仅当 hue_weight > 0 时）
        if self.hue_weight > 0:
            from core.color.matching import HueAwareColorMatcher
            self.hue_matcher = HueAwareColorMatcher(
                self.lut_rgb, self.lut_lab, hue_weight=self.hue_weight
            )
    
    def process_image(self, image_path, target_width_mm, modeling_mode,
                     quantize_colors, auto_bg, bg_tol,
                     blur_kernel=0, smooth_sigma=10):
        """
        Main image processing method
        
        Args:
            image_path: Image file path
            target_width_mm: Target width (millimeters)
            modeling_mode: Modeling mode ("high-fidelity", "pixel")
            quantize_colors: K-Means quantization color count
            auto_bg: Whether to auto-remove background
            bg_tol: Background tolerance
            blur_kernel: Median filter kernel size (0=disabled, recommended 0-5)
            smooth_sigma: Bilateral filter sigma value (recommended 5-20)
        
        Returns:
            dict: Dictionary containing processing results
                - matched_rgb: (H, W, 3) Matched RGB array
                - material_matrix: (H, W, Layers) Material index matrix
                - mask_solid: (H, W) Solid mask
                - dimensions: (width, height) Pixel dimensions
                - pixel_scale: mm/pixel ratio
                - mode_info: Mode information dictionary
                - debug_data: Debug data (high-fidelity mode only)
        """
        logger.info("模式: 高保真")
        logger.info("滤镜设置: blur_kernel=%s, smooth_sigma=%s", blur_kernel, smooth_sigma)
        
        # ========== Image Loading Logic Branch ==========
        is_svg = image_path.lower().endswith('.svg')
        
        if is_svg:
            logger.info("检测到 SVG - 启用超高保真矢量模式")
            img_arr = self._load_svg(image_path, target_width_mm, pixels_per_mm=10.0)
            # SVG reset to PIL object to reuse subsequent logic (e.g., get dimensions)
            img = Image.fromarray(img_arr)
            
            # [CRITICAL] SVG is also a type of High-Fidelity, but it doesn't need denoising
            # Force override filter parameters, because vector graphics have no noise, no need to blur
            # 
            # [SUPER-SAMPLING STRATEGY]
            # We render at 20 px/mm (2x standard), which physically eliminates jaggies
            # through super-sampling. This is superior to blur-based anti-aliasing
            # because it preserves sharp edges while making curves smooth.
            blur_kernel = 0
            smooth_sigma = 0
            logger.info("SVG 模式: 滤镜已禁用（矢量源无噪声）")
            logger.info("20 px/mm 超采样自然消除锯齿边缘")
            
            # Recalculate target_w/h (based on rendered dimensions)
            target_w, target_h = img.size
            pixel_to_mm_scale = 0.05  # 20 px/mm (1/20) - Ultra-High-Fidelity
        else:
            # [Original Logic] Bitmap loading
            # Load image
            img = Image.open(image_path).convert('RGBA')
            
            # Check if image has transparency
            original_img = Image.open(image_path)
            has_alpha = original_img.mode in ('RGBA', 'LA') or (original_img.mode == 'P' and 'transparency' in original_img.info)

            if has_alpha:
                # Check alpha channel statistics
                if original_img.mode != 'RGBA':
                    original_img = original_img.convert('RGBA')
                alpha_data = np.array(original_img)[:, :, 3]
            
        # Calculate target resolution (always high-fidelity mode)
        PIXELS_PER_MM = 10
        target_w = int(target_width_mm * PIXELS_PER_MM)
        pixel_to_mm_scale = 1.0 / PIXELS_PER_MM  # 0.1 mm per pixel
        logger.info("高分辨率模式: %s px/mm", PIXELS_PER_MM)

        target_h = int(target_w * img.height / img.width)
        logger.info("目标: %sx%s像素 (%.1fx%.1fmm)", target_w, target_h, target_w * pixel_to_mm_scale, target_h * pixel_to_mm_scale)
        
        # ========== End of Image Loading Logic Branch ==========
        
        # ========== CRITICAL FIX: Use NEAREST for both modes ==========
        # REASON: LANCZOS anti-aliasing creates light transition pixels at edges.
        # These light pixels map to stacks with WHITE bases (Layer 1),
        # causing the mesh to "float" above the build plate.
        # 
        # SOLUTION: Use NEAREST to preserve hard edges and ensure dark pixels
        # map to solid dark stacks from Layer 1 upwards.
        logger.info("使用 NEAREST 插值（无抗锯齿）")
        img = img.resize((target_w, target_h), Image.Resampling.NEAREST)
        
        img_arr = np.array(img)
        rgb_arr = img_arr[:, :, :3]
        alpha_arr = img_arr[:, :, 3]
        
        # CRITICAL FIX: Identify transparent pixels BEFORE color processing
        # This prevents transparent areas from being matched to LUT colors
        mask_transparent_initial = alpha_arr < 10
        logger.info("发现 %s 个透明像素（alpha<10）", np.sum(mask_transparent_initial))
        
        # Color processing and matching
        debug_data = None
        matched_rgb, material_matrix, bg_reference, debug_data = self._process_high_fidelity_mode(
            rgb_arr, target_h, target_w, quantize_colors, blur_kernel, smooth_sigma
        )

        # >>> 孤立像素清理（可选后处理）<<<
        if self.enable_cleanup:
            try:
                from core.image.cleanup import cleanup_isolated_pixels
                matched_rgb, material_matrix = cleanup_isolated_pixels(
                    material_matrix, matched_rgb, self.lut_rgb, self.ref_stacks
                )
            except ImportError:
                logger.warning("未找到 isolated_pixel_cleanup 模块，跳过")
        
        # Background removal - combine alpha transparency with optional auto-bg
        mask_transparent = mask_transparent_initial.copy()
        if auto_bg:
            bg_color = bg_reference[0, 0]
            diff = np.sum(np.abs(bg_reference - bg_color), axis=-1)
            mask_transparent = np.logical_or(mask_transparent, diff < bg_tol)
        
        # Apply transparency mask to material matrix
        material_matrix[mask_transparent] = -1
        mask_solid = ~mask_transparent
        
        result = {
            'matched_rgb': matched_rgb,
            'material_matrix': material_matrix,
            'mask_solid': mask_solid,
            'dimensions': (target_w, target_h),
            'pixel_scale': pixel_to_mm_scale,
            'mode_info': {
                'mode': ModelingMode.HIGH_FIDELITY
            },
            # 统一返回契约：全路径提供 quantized_image
            'quantized_image': debug_data['quantized_image'] if debug_data is not None else rgb_arr.copy()
        }

        # Add debug data
        if debug_data is not None:
            result['debug_data'] = debug_data

        return result

    
    def _process_high_fidelity_mode(self, rgb_arr, target_h, target_w, quantize_colors,
                                    blur_kernel, smooth_sigma):
        """
        High-fidelity mode image processing
        Includes configurable filtering, K-Means quantization and color matching

        优化：
        1. K-Means++ 初始化（OpenCV 默认支持）
        2. 预缩放：在小图上做 K-Means，然后映射回原图
        3. GPU 流水线加速（如果可用）

        Args:
            rgb_arr: Input RGB array
            target_h: Target height
            target_w: Target width
            quantize_colors: K-Means color count
            blur_kernel: Median filter kernel size (0=disabled)
            smooth_sigma: Bilateral filter sigma value

        Returns:
            tuple: (matched_rgb, material_matrix, quantized_image, debug_data)
        """
        import time
        total_start = time.time()

        logger.info("开始边缘保护处理...")

        import time
        total_start = time.time()

        # GPU Pipeline: Use full GPU acceleration
        logger.info("使用 GPU 流水线加速...")
        pipeline = GPUPipeline()
        matched_rgb, material_matrix, debug_data = pipeline.process_preview(
            rgb_arr, quantize_colors, self.lut_rgb, self.lut_lab,
            self.ref_stacks, self.layer_count,
            blur_kernel, smooth_sigma, target_pixels=500_000
        )

        # Resize to target dimensions if needed
        h, w = matched_rgb.shape[:2]
        if h != target_h or w != target_w:
            matched_rgb = cv2.resize(matched_rgb, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
            material_matrix = cv2.resize(material_matrix, (target_w, target_h), interpolation=cv2.INTER_NEAREST)

        # Build quantized image from debug data
        quantized_image = debug_data.get('quantized_image', matched_rgb)

        logger.info("总处理时间: %.2fs", time.time() - total_start)

        return matched_rgb, material_matrix, quantized_image, debug_data
