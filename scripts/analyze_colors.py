import numpy as np
import os
import sys

# Bootstrap: ensure project root is on sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ==========================================
# 紧急修复: 给 colormath 库打补丁
# ==========================================
setattr(np, "asscalar", lambda a: a.item())

# 补丁打完后再引入 colormath
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color
from colormath.color_diff import delta_e_cie2000
import itertools
import os

from config import ColorSystem, PrinterConfig
from core.utils.logger import get_logger

logger = get_logger("ANALYZE_COLORS")

# ================= 配置区域 =================

# 打印参数 (统一使用 config.py 的配置)
LAYER_HEIGHT = PrinterConfig.LAYER_HEIGHT  # 层高
LAYERS = PrinterConfig.COLOR_LAYERS         # 混色层数
BACKING_COLOR = np.array([255, 255, 255])   # 底板颜色 (白色)

# 耗材定义 (统一使用 config.py 的 EIGHT_COLOR 注册表)
FILAMENTS = ColorSystem.EIGHT_COLOR['filaments']

# RGB距离阈值 (和6色算法一致)
RGB_DISTANCE_THRESHOLD = 8

# ===========================================

def calculate_alpha(td_value, layer_height):
    """计算单层透明度 (和6色算法一致)"""
    blending_distance = td_value / 10.0
    if blending_distance <= 0: return 1.0
    alpha = layer_height / blending_distance
    return min(max(alpha, 0.0), 1.0)

def mix_colors(stack):
    """
    颜色混合模拟 (和6色算法一致)
    stack: [底层 ... 顶层]
    """
    current_rgb = BACKING_COLOR.astype(float)
    for fid in stack:
        fil = FILAMENTS[fid]
        f_rgb = np.array(fil["rgb"])
        f_alpha = calculate_alpha(fil["td"], LAYER_HEIGHT)
        current_rgb = f_rgb * f_alpha + current_rgb * (1.0 - f_alpha)
    return current_rgb.astype(np.uint8)

def rgb_to_lab(rgb):
    """RGB转Lab (用于可选的色差分析)"""
    rgb_obj = sRGBColor(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
    return convert_color(rgb_obj, LabColor)

def main():
    COLOR_COUNT = 8
    TARGET_COUNT = 2738  # 37x37×2 = 2738

    logger.info("=" * 60)
    logger.info("8色智能筛选算法 (仿6色优雅版)")
    logger.info("=" * 60)
    logger.info("开始模拟 %s色 %s层 全排列 (%s 种组合)...", COLOR_COUNT, LAYERS, COLOR_COUNT ** LAYERS)
    logger.info("RGB距离阈值: %s (和6色算法一致)", RGB_DISTANCE_THRESHOLD)
    logger.info("目标数量: %s 个颜色", TARGET_COUNT)
    logger.info("黑色TD: %smm (和6色一致，自然筛选)", FILAMENTS[4]["td"])
    logger.info("")

    # ==================== 阶段1: 模拟所有组合 ====================
    logger.info("[阶段1] 模拟所有颜色组合...")
    candidates = []

    for stack in itertools.product(range(COLOR_COUNT), repeat=LAYERS):
        final_rgb = mix_colors(stack)

        # 转换到Lab用于可选分析
        lab = rgb_to_lab(final_rgb)

        candidates.append({
            "stack": stack,
            "rgb": final_rgb,
            "lab": lab
        })

    logger.info("模拟完成: %s 个组合", len(candidates))
    logger.info("")

    # ==================== 阶段2: 智能筛选 (仿6色算法) ====================
    logger.info("[阶段2] 智能筛选 (贪心算法 + RGB距离)")

    selected = []

    # Step 1: 预选种子颜色 (8个纯色)
    logger.info("  预选种子颜色 (8个纯色)...")
    for i in range(COLOR_COUNT):
        stack = (i,) * LAYERS
        for c in candidates:
            if c['stack'] == stack:
                selected.append(c)
                logger.info("     种子 %s: %s - RGB%s", i, FILAMENTS[i]['name'], tuple(c['rgb']))
                break

    logger.info("  种子颜色: %s 个", len(selected))
    logger.info("")

    # Step 2: 高质量筛选 (RGB距离 > 8)
    logger.info("  高质量筛选 (RGB距离 > %s)...", RGB_DISTANCE_THRESHOLD)
    round1_start = len(selected)

    for c in candidates:
        if len(selected) >= TARGET_COUNT:
            break

        # 跳过已选中的
        if any(c['stack'] == s['stack'] for s in selected):
            continue

        # 检查RGB距离
        is_distinct = True
        for s in selected:
            rgb_dist = np.linalg.norm(c['rgb'].astype(int) - s['rgb'].astype(int))
            if rgb_dist < RGB_DISTANCE_THRESHOLD:
                is_distinct = False
                break

        if is_distinct:
            selected.append(c)

        # 进度显示
        if len(selected) % 500 == 0:
            logger.info("     进度: %s/%s", len(selected), TARGET_COUNT)

    round1_count = len(selected) - round1_start
    logger.info("  高质量筛选: 新增 %s 个颜色", round1_count)
    logger.info("")

    # Step 3: 填充剩余 (降低阈值)
    if len(selected) < TARGET_COUNT:
        logger.info("  填充剩余 %s 个位置...", TARGET_COUNT - len(selected))
        for c in candidates:
            if len(selected) >= TARGET_COUNT:
                break
            if any(c['stack'] == s['stack'] for s in selected):
                continue
            selected.append(c)

        logger.info("  填充完成: 总计 %s 个颜色", len(selected))

    logger.info("")
    logger.info("=" * 60)
    logger.info("筛选完成!")
    logger.info("   总组合数: %s", len(candidates))
    logger.info("   最终选择: %s", len(selected))
    logger.info("   筛选率: %.2f%%", len(selected) / len(candidates) * 100)
    logger.info("=" * 60)
    logger.info("")

    # ==================== 阶段3: 保存结果 ====================
    output_dir = os.path.join(_PROJECT_ROOT, "assets")

    logger.info("保存到 '%s/'...", output_dir)

    # 确保数量正确
    final_selection = selected[:TARGET_COUNT]

    # 如果不足，用白色填充
    if len(final_selection) < TARGET_COUNT:
        logger.warning("不足 %s 个，用白色填充...", TARGET_COUNT)
        dummy_stack = (0,) * LAYERS  # 白色
        while len(final_selection) < TARGET_COUNT:
            final_selection.append({"stack": dummy_stack})

    stacks_data = [item["stack"] for item in final_selection]
    stacks_array = np.array(stacks_data, dtype=np.uint8)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    save_path = os.path.join(output_dir, "smart_8color_stacks.npy")
    np.save(save_path, stacks_array)

    logger.info("已保存到 '%s'", save_path)
    logger.info("   数组形状: %s", stacks_array.shape)
    logger.info("   数据类型: %s", stacks_array.dtype)
    logger.info("")

    # ==================== 统计分析 ====================
    logger.info("=" * 60)
    logger.info("统计分析")
    logger.info("=" * 60)

    # 统计黑色使用情况 (修正：黑色现在的 ID 是 4)
    BLACK_ID = 4
    black_count = sum(1 for s in final_selection if BLACK_ID in s['stack'])
    black_surface = sum(1 for s in final_selection if s['stack'][4] == BLACK_ID)

    logger.info("黑色使用统计 (ID=%s):", BLACK_ID)
    logger.info("  包含黑色的组合: %s/%s (%.1f%%)", black_count, len(final_selection), black_count / len(final_selection) * 100)
    logger.info("  表面层是黑色: %s/%s (%.1f%%)", black_surface, len(final_selection), black_surface / len(final_selection) * 100)
    logger.info("")

    # RGB分布统计
    all_rgb = np.array([s['rgb'] for s in final_selection])
    logger.info("RGB分布:")
    logger.info("  R: min=%s, max=%s, avg=%.1f", all_rgb[:, 0].min(), all_rgb[:, 0].max(), all_rgb[:, 0].mean())
    logger.info("  G: min=%s, max=%s, avg=%.1f", all_rgb[:, 1].min(), all_rgb[:, 1].max(), all_rgb[:, 1].mean())
    logger.info("  B: min=%s, max=%s, avg=%.1f", all_rgb[:, 2].min(), all_rgb[:, 2].max(), all_rgb[:, 2].mean())
    logger.info("")

    logger.info("完成！")
    logger.info("=" * 60)

if __name__ == "__main__":
    main()
