"""
孤立像素清理模块（Isolated Pixel Cleanup）- GPU 加速版

在 LUT 颜色匹配之后、voxel matrix 构建之前，对 material_matrix 执行孤立像素检测与替换。
孤立像素是指其 5 层材料堆叠编码与所有 8 邻域像素均不同的像素点，
这些像素在打印时会产生不必要的换色操作。

核心思路：将每个像素的 5 层材料 ID 编码为单个整数（堆叠编码），
通过 PyTorch GPU 向量化操作快速检测孤立像素，然后用邻域众数替换，
同时同步更新 matched_rgb 以保持数据一致性。
"""

import numpy as np
import torch
import torch.nn.functional as F

from core.stack_encoding import encode_stacks_batch
from core.utils.gpu_device import GPUDeviceManager
from core.utils.logger import get_logger

logger = get_logger("CLEANUP")

_encode_stacks = encode_stacks_batch


def _detect_isolated(encoded: np.ndarray) -> np.ndarray:
    """
    检测孤立像素，返回 (H, W) 布尔掩码 (GPU 加速版)。

    孤立像素 = 堆叠编码与所有 8 邻域均不同。
    使用 PyTorch unfold 提取 8 邻域，向量化比较。

    Args:
        encoded: (H, W) 整数编码矩阵

    Returns:
        (H, W) 布尔掩码，True 表示孤立像素
    """
    H, W = encoded.shape

    if H <= 1 and W <= 1:
        return np.zeros((H, W), dtype=bool)

    device = GPUDeviceManager().get_device()
    t = torch.from_numpy(encoded).to(device).float()

    # Pad 并提取 3x3 邻域
    padded = F.pad(t, (1, 1, 1, 1), mode='constant', value=-1)
    neighborhoods = padded.unfold(0, 3, 1).unfold(1, 3, 1)  # (H, W, 3, 3)
    neighborhoods = neighborhoods.reshape(H, W, 9)  # 展平为 9 个邻域值

    center = neighborhoods[:, :, 4]  # 中心像素 (index 4)

    # 统计有效邻居数量和不同数量
    valid = neighborhoods != -1
    neighbor_count = valid.sum(dim=-1) - 1  # 减去中心

    # 与中心不同的邻居
    different = (neighborhoods != center.unsqueeze(-1)) & valid
    diff_count = different.sum(dim=-1)

    # 孤立 = 与所有实际邻居都不同（且至少有一个邻居）
    isolated = (diff_count == neighbor_count) & (neighbor_count > 0)

    return isolated.cpu().numpy()


def _find_neighbor_mode(encoded: np.ndarray, isolated_mask: np.ndarray) -> np.ndarray:
    """
    对每个孤立像素，找到其 8 邻域中出现次数最多的堆叠编码 (GPU 加速版)。

    使用 torch.mode 向量化众数查找。

    Args:
        encoded: (H, W) 整数编码矩阵
        isolated_mask: (H, W) 布尔掩码，True 表示孤立像素

    Returns:
        (H, W) 数组，孤立像素位置存储邻域众数编码，非孤立像素位置值为原编码
    """
    H, W = encoded.shape
    device = GPUDeviceManager().get_device()

    t = torch.from_numpy(encoded).to(device).float()
    mask = torch.from_numpy(isolated_mask).to(device)

    mode_map = t.clone()

    if not mask.any():
        return mode_map.cpu().numpy().astype(encoded.dtype)

    # Pad 并提取邻域
    padded = F.pad(t, (1, 1, 1, 1), mode='constant', value=-2)  # -2 为无效标记
    neighborhoods = padded.unfold(0, 3, 1).unfold(1, 3, 1).reshape(H, W, 9)

    # 排除中心 (index 4)，只保留 8 个邻居
    neighbor_vals = torch.cat([
        neighborhoods[:, :, :4],
        neighborhoods[:, :, 5:]
    ], dim=-1)  # (H, W, 8)

    # 找众数 (torch.mode 返回最小众数，确定性)
    modes, _ = torch.mode(neighbor_vals, dim=-1)

    # 只更新孤立像素
    mode_map[mask] = modes[mask]

    return mode_map.cpu().numpy().astype(encoded.dtype)


def cleanup_isolated_pixels(
    material_matrix: np.ndarray,
    matched_rgb: np.ndarray,
    lut_rgb: np.ndarray,
    ref_stacks: np.ndarray,
) -> tuple:
    """
    检测并替换孤立像素。

    流程：编码堆叠 → 检测孤立 → 邻域众数替换 → LUT 反查同步 RGB
    单轮清理，不修改输入数组。

    Args:
        material_matrix: (H, W, N) 材料堆叠矩阵
        matched_rgb: (H, W, 3) 匹配的 RGB 颜色
        lut_rgb: (N, 3) LUT 颜色表
        ref_stacks: (N, L) LUT 材料堆叠表

    Returns:
        (cleaned_matched_rgb, cleaned_material_matrix) - 清理后的副本
    """
    cleaned_mat = material_matrix.copy()
    cleaned_rgb = matched_rgb.copy()

    H, W = material_matrix.shape[:2]
    total_pixels = H * W

    # 步骤 1：编码堆叠
    base = int(material_matrix.max()) + 1 if material_matrix.size > 0 else 1
    encoded = _encode_stacks(material_matrix, base)

    # 步骤 2：检测孤立像素
    isolated_mask = _detect_isolated(encoded)
    isolated_count = int(np.sum(isolated_mask))

    if isolated_count == 0:
        logger.info("未检测到孤立像素，跳过清理")
        return cleaned_rgb, cleaned_mat

    # 步骤 3：找到邻域众数
    mode_map = _find_neighbor_mode(encoded, isolated_mask)

    # 步骤 4：构建 LUT 编码 → 索引 的映射，用于反查
    layer_count = ref_stacks.shape[1]
    lut_encoded = _encode_stacks(ref_stacks.reshape(1, -1, layer_count), base).flatten()
    # 编码 → LUT 索引的字典
    encode_to_lut_idx = {}
    for idx in range(len(lut_encoded)):
        enc_val = int(lut_encoded[idx])
        if enc_val not in encode_to_lut_idx:
            encode_to_lut_idx[enc_val] = idx

    # 步骤 5：替换孤立像素
    replaced_count = 0
    isolated_coords = np.argwhere(isolated_mask)

    for i, j in isolated_coords:
        new_enc = int(mode_map[i, j])
        if new_enc in encode_to_lut_idx:
            lut_idx = encode_to_lut_idx[new_enc]
            cleaned_mat[i, j] = ref_stacks[lut_idx]
            cleaned_rgb[i, j] = lut_rgb[lut_idx]
            replaced_count += 1

    # 输出统计信息
    percentage = (replaced_count / total_pixels * 100) if total_pixels > 0 else 0
    logger.info("清理完成: 检测到 %d 个孤立像素, 成功合并 %d 个, 占总像素 %.2f%% (总像素=%d)", isolated_count, replaced_count, percentage, total_pixels)

    return cleaned_rgb, cleaned_mat
