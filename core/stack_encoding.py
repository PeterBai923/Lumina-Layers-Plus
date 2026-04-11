"""N 进制 Stack 编码工具函数。"""


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
