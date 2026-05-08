"""N 进制 Stack 编码工具函数。

提供整数与 N 进制数字列表之间的双向转换，以及材料矩阵的批量编码。
"""

import numpy as np


def encode_to_base(index: int, base: int, length: int = 5) -> list[int]:
    """将整数编码为 N 进制数字列表（高位在前）。

    Args:
        index: 要编码的非负整数。
        base: 进制基数（例如 2 表示二进制，4 表示四进制）。
        length: 输出数字列表的长度，不足高位补零。

    Returns:
        list[int]: 高位在前的数字列表，长度为 length。
    """
    digits = []
    temp = index
    for _ in range(length):
        digits.append(temp % base)
        temp //= base
    return digits[::-1]


def encode_stacks_batch(material_matrix: np.ndarray, base: int) -> np.ndarray:
    """将 (H, W, N) 的材料矩阵批量编码为 (H, W) 的整数矩阵。

    编码公式: layer0 * B^(N-1) + layer1 * B^(N-2) + ... + layer(N-1)
    其中 B = base（材料 ID 的最大值 + 1）

    Args:
        material_matrix: (H, W, N) 材料堆叠矩阵
        base: 编码基数，通常为 max(material_id) + 1

    Returns:
        (H, W) 整数矩阵，dtype 为 int64
    """
    if material_matrix.ndim != 3:
        raise ValueError(f"material_matrix must be 3D (H, W, N), got shape={material_matrix.shape}")
    layer_count = material_matrix.shape[2]
    weights = np.array([base ** i for i in range(layer_count - 1, -1, -1)], dtype=np.int64)
    encoded = np.sum(material_matrix.astype(np.int64) * weights, axis=2)
    return encoded
