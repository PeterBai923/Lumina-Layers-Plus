"""
色相感知颜色匹配器 (Hue-Aware Color Matcher)

核心思想：在 LCH 色彩空间中使用加权距离进行颜色匹配。

CIELAB 的 L*a*b* 用欧氏距离时，亮度差异容易压过色相差异，
导致浅粉色匹配到白色而不是红色系。

本模块将 CIELAB 转换到 LCH（亮度-彩度-色相）空间，
通过对三个维度分别设置权重来控制匹配行为：
  - w_L: 亮度权重（越大 → 亮度差异越不敏感 → 更倾向同色相）
  - w_C: 彩度权重（越大 → 彩度差异越不敏感）
  - w_H: 色相权重（越小 → 色相差异越敏感 → 更严格保持同色相）

对于无彩色（黑白灰），色相无意义，通过 CIEDE2000 风格的 ΔH 公式
自动处理（彩度为 0 时 ΔH=0）。

兼容项目现有的 OpenCV LAB 格式（L:0-255, a:0-255, b:0-255）。
"""

from core.utils.logger import get_logger

logger = get_logger("MATCHING")

from typing import Optional
import numpy as np
import torch

from core.utils.color_conversion import rgb_to_lab
from core.utils.gpu_device import GPUDeviceManager


class HueAwareColorMatcher:
    """LCH 加权距离颜色匹配器"""

    # 预设配置
    # w_L 越大 → 亮度差异越不敏感（允许跨亮度匹配同色相）
    # w_H 越小 → 色相差异越敏感（更严格保持同色相）
    PRESETS = {
        # 纯 CIELAB 距离（等同于原始 KDTree 行为）
        "classic": {"w_L": 1.0, "w_C": 1.0, "w_H": 1.0},
        # 轻度色相保护（≈hw=0.3）
        "mild": {"w_L": 1.0, "w_C": 1.0, "w_H": 0.44},
        # 平衡模式（≈hw=0.5）：推荐默认值
        "balanced": {"w_L": 1.0, "w_C": 1.0, "w_H": 0.26},
        # 强色相保护（≈hw=1.0）
        "strong": {"w_L": 1.0, "w_C": 1.0, "w_H": 0.15},
    }

    def __init__(
        self,
        lut_rgb: np.ndarray,
        lut_lab: np.ndarray,
        hue_weight: float = 0.0,
        preset: Optional[str] = None,
        w_L: Optional[float] = None,
        w_C: Optional[float] = None,
        w_H: Optional[float] = None,
    ):
        """
        初始化匹配器。

        参数:
            lut_rgb: LUT 的 RGB 数组 (N, 3), uint8
            lut_lab: LUT 的 CIELAB 数组 (N, 3), float (OpenCV 格式)
            hue_weight: 简化参数 (0.0-1.0)，自动映射到 w_L/w_H
                        0.0 = 纯 CIELAB，1.0 = 最强色相保护
            preset: 预设名称 ('classic', 'mild', 'balanced', 'strong')
            w_L, w_C, w_H: 手动指定权重（优先级最高）
        """
        self.lut_rgb = np.asarray(lut_rgb, dtype=np.uint8)
        self.lut_lab = np.asarray(lut_lab, dtype=np.float64)
        self.n_colors = len(lut_rgb)

        # 预计算 LUT 的 LCH（基于 OpenCV LAB 格式）
        self.lut_lch = self._lab_to_lch(self.lut_lab)

        # 解析权重参数
        self._resolve_weights(hue_weight, preset, w_L, w_C, w_H)

        logger.info(
            "初始化: %d 色, w_L=%.2f, w_C=%.2f, w_H=%.2f",
            self.n_colors, self.w_L, self.w_C, self.w_H,
        )

    def _resolve_weights(self, hue_weight, preset, w_L, w_C, w_H):
        """解析权重参数，优先级：手动 > 预设 > hue_weight 映射"""
        if w_L is not None and w_C is not None and w_H is not None:
            self.w_L = w_L
            self.w_C = w_C
            self.w_H = w_H
        elif preset and preset in self.PRESETS:
            p = self.PRESETS[preset]
            self.w_L = p["w_L"]
            self.w_C = p["w_C"]
            self.w_H = p["w_H"]
        else:
            # hue_weight 0.0-1.0 映射到权重
            # 核心策略：w_L 保持 1.0 不变，只通过降低 w_H 放大色相惩罚。
            # 使用指数曲线而非线性映射，让滑块一旦拉起就快速进入强保护区间，
            # 避免中间值"犹豫"导致色块（部分颜色匹配同色系、部分不匹配）。
            #
            # 映射: w_H = 0.15 + 0.85 * (1 - hw)^3
            #   hw=0.0 → w_H=1.0   (纯 CIELAB)
            #   hw=0.3 → w_H=0.44  (已有明显保护)
            #   hw=0.5 → w_H=0.26  (强保护)
            #   hw=0.7 → w_H=0.17  (接近最强)
            #   hw=1.0 → w_H=0.15  (最强)
            hw = np.clip(hue_weight, 0.0, 1.0)
            self.w_L = 1.0
            self.w_C = 1.0
            self.w_H = 0.15 + 0.85 * (1.0 - hw) ** 3  # 指数曲线，快速下降

    @staticmethod
    def _lab_to_lch(lab: np.ndarray) -> np.ndarray:
        """
        OpenCV LAB → LCH 转换。

        OpenCV LAB 格式: L:0-255, a:0-255(128=0), b:0-255(128=0)

        L = L (保持 OpenCV 范围)
        C = sqrt((a-128)² + (b-128)²)  彩度
        H = atan2(b-128, a-128)        色相角 (度, 0-360)
        """
        L = lab[..., 0]
        a = lab[..., 1] - 128.0
        b = lab[..., 2] - 128.0
        C = np.sqrt(a**2 + b**2)
        H = np.degrees(np.arctan2(b, a)) % 360
        return np.stack([L, C, H], axis=-1)

    @staticmethod
    def _delta_hue(h1_deg, h2_deg, c1, c2):
        """
        计算色相差 ΔH（改进的 CIEDE2000 风格）。

        ΔH = 2 * min(C1, C2) * sin(Δh / 2)

        使用 min(C1, C2) 而非 sqrt(C1*C2)，确保：
        1. 任一颜色彩度低 → ΔH 很小（低彩度色相不可靠）
        2. 只有双方都是高彩度时，色相差异才有显著影响
        3. 正确处理色相角的环形特性（350° 和 10° 差 20°，不是 340°）
        """
        dh = h2_deg - h1_deg
        # 环形处理：确保 dh 在 [-180, 180]
        dh = (dh + 180) % 360 - 180
        dh_rad = np.radians(dh)
        return 2.0 * np.minimum(c1, c2) * np.sin(dh_rad / 2.0)

    def _weighted_distance(self, input_lch, candidate_lch):
        """
        计算 LCH 加权距离。

        input_lch: (3,) 单个颜色
        candidate_lch: (K, 3) K 个候选

        返回: (K,) 距离数组
        """
        dL = (candidate_lch[:, 0] - input_lch[0]) / self.w_L
        dC = (candidate_lch[:, 1] - input_lch[1]) / self.w_C
        dH = (
            self._delta_hue(
                input_lch[2], candidate_lch[:, 2], input_lch[1], candidate_lch[:, 1]
            )
            / self.w_H
        )

        return np.sqrt(dL**2 + dC**2 + dH**2)

    def match_colors_batch(self, input_rgb: np.ndarray, k: int = 16) -> np.ndarray:
        """
        批量颜色匹配 (纯 GPU 实现)。

        参数:
            input_rgb: (N, 3) uint8 RGB 数组
            k: 忽略（保留参数兼容性）

        返回:
            (N,) int 数组，每个输入颜色在 LUT 中的最佳匹配索引
        """
        device = GPUDeviceManager().get_device()

        # 转换输入为 GPU tensor
        if isinstance(input_rgb, np.ndarray):
            input_tensor = torch.from_numpy(input_rgb.astype(np.float32)).to(device)
        else:
            input_tensor = input_rgb.float().to(device)

        # 转换 LUT LCH 为 GPU tensor
        lut_lch_tensor = torch.from_numpy(self.lut_lch).to(device).float()

        # RGB -> LAB -> LCH (GPU)
        input_lab = rgb_to_lab(input_tensor)

        # LAB -> LCH 转换 (GPU)
        L = input_lab[:, 0]
        a = input_lab[:, 1] - 128
        b = input_lab[:, 2] - 128
        C = torch.sqrt(a**2 + b**2)
        H = torch.rad2deg(torch.atan2(b, a)) % 360
        input_lch = torch.stack([L, C, H], dim=-1)

        # 批量 LCH 加权距离计算 (N, M)
        # dL = (input_L - lut_L) / w_L
        dL = (input_lch[:, 0:1] - lut_lch_tensor[:, 0:1].T) / self.w_L

        # dC = (input_C - lut_C) / w_C
        dC = (input_lch[:, 1:2] - lut_lch_tensor[:, 1:2].T) / self.w_C

        # dH: 色相差（环形处理）
        # ΔH = 2 * min(C1, C2) * sin(Δh / 2)
        dh = (lut_lch_tensor[:, 2] - input_lch[:, 2:3].T + 180) % 360 - 180
        min_C = torch.minimum(C.unsqueeze(1), lut_lch_tensor[:, 1].unsqueeze(0))
        dH = 2 * min_C * torch.sin(torch.deg2rad(dh) / 2) / self.w_H

        # 总距离
        distances = torch.sqrt(dL**2 + dC**2 + dH**2)

        # 返回最小距离的索引
        return distances.argmin(dim=1).cpu().numpy()
