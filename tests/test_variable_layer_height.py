"""
Unit tests for variable layer height transform functionality.

Tests the _apply_variable_layer_height_transform function that fixes
the backing thickness calculation bug where backing layers were incorrectly
scaled using optical layer height (0.08mm) instead of backing layer height (0.2mm).
"""

import pytest
import numpy as np
import trimesh
from core.converter import _apply_variable_layer_height_transform
from config import PrinterConfig


def test_single_sided_mode():
    """测试单面模式: 光学层在底部,背板在顶部"""
    # 创建测试mesh (Z范围0-12,共13层)
    mesh = trimesh.creation.box(extents=[10, 10, 13])
    mesh.vertices[:, 2] = np.clip(mesh.vertices[:, 2], 0, 12)

    backing_metadata = {
        'backing_z_range': (5, 12),  # 背板Z=5-12
    }

    _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale=1.0)

    # 验证总高度
    # 光学层(0-4): 5层 × 0.08mm = 0.4mm
    # 背板层(5-12): 8层 × 0.2mm = 1.6mm
    # 总高度: 2.0mm
    expected_height = 0.4 + 1.6
    assert np.max(mesh.vertices[:, 2]) == pytest.approx(expected_height, abs=0.01)

    # 验证光学层高度
    optical_vertices = mesh.vertices[mesh.vertices[:, 2] < 0.4]
    assert len(optical_vertices) > 0
    assert np.max(optical_vertices[:, 2]) == pytest.approx(0.4, abs=0.01)

    # 验证背板层高度
    backing_vertices = mesh.vertices[mesh.vertices[:, 2] >= 0.4]
    assert len(backing_vertices) > 0
    assert np.max(backing_vertices[:, 2]) == pytest.approx(2.0, abs=0.01)


def test_backing_thickness_0_8mm():
    """测试用户报告的具体问题: 0.8mm背板厚度"""
    # 创建测试mesh
    # 5光学层 + 4背板层 = 9层总高度
    mesh = trimesh.creation.box(extents=[10, 10, 9])
    mesh.vertices[:, 2] = np.clip(mesh.vertices[:, 2], 0, 8)

    backing_metadata = {
        'backing_z_range': (5, 8),  # 4层背板
    }

    _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale=1.0)

    # 验证背板厚度
    # 光学层: 5层 × 0.08mm = 0.4mm
    # 背板层: 4层 × 0.2mm = 0.8mm (用户期望)
    # 总高度: 1.2mm
    z_coords = mesh.vertices[:, 2]

    # 光学层顶点 (Z < 0.4mm)
    optical_vertices = z_coords[z_coords < 0.4]
    assert len(optical_vertices) > 0
    assert np.max(optical_vertices) == pytest.approx(0.4, abs=0.01)

    # 背板层顶点 (Z >= 0.4mm)
    backing_vertices = z_coords[z_coords >= 0.4]
    assert len(backing_vertices) > 0

    # 背板厚度 = max - min
    expected_backing_thickness = 0.8  # mm
    actual_backing_thickness = np.max(backing_vertices) - np.min(backing_vertices)

    assert actual_backing_thickness == pytest.approx(expected_backing_thickness, abs=0.01)

    # 验证总高度
    expected_total_height = 1.2  # mm
    assert np.max(z_coords) == pytest.approx(expected_total_height, abs=0.01)


def test_double_sided_mode():
    """测试双面模式: 光学层-背板-光学层"""
    mesh = trimesh.creation.box(extents=[10, 10, 18])  # Z: 0-17
    mesh.vertices[:, 2] = np.clip(mesh.vertices[:, 2], 0, 17)

    backing_metadata = {
        'backing_z_range': (5, 12),  # 背板Z=5-12
    }

    _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale=1.0)

    # 底部光学层: 5层 × 0.08 = 0.4mm
    # 背板层: 8层 × 0.2 = 1.6mm
    # 顶部光学层: 5层 × 0.08 = 0.4mm
    # 总高度: 2.4mm
    expected_height = 0.4 + 1.6 + 0.4
    assert np.max(mesh.vertices[:, 2]) == pytest.approx(expected_height, abs=0.01)

    # 验证三段结构
    z_coords = mesh.vertices[:, 2]

    # 底部光学层 (0-0.4mm)
    bottom_optical = z_coords[z_coords < 0.4]
    assert len(bottom_optical) > 0
    assert np.max(bottom_optical) == pytest.approx(0.4, abs=0.01)

    # 背板层 (0.4-2.0mm)
    backing = z_coords[(z_coords >= 0.4) & (z_coords < 2.0)]
    assert len(backing) > 0
    assert np.max(backing) == pytest.approx(2.0, abs=0.01)

    # 顶部光学层 (2.0-2.4mm)
    top_optical = z_coords[z_coords >= 2.0]
    assert len(top_optical) > 0
    assert np.max(top_optical) == pytest.approx(2.4, abs=0.01)


def test_cloisonne_mode():
    """测试景泰蓝模式: 背板在底部,光学层在顶部"""
    mesh = trimesh.creation.box(extents=[10, 10, 13])
    mesh.vertices[:, 2] = np.clip(mesh.vertices[:, 2], 0, 12)

    backing_metadata = {
        'backing_z_range': (0, 7),  # 背板Z=0-7 (8层)
        'is_cloisonne': True
    }

    _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale=1.0)

    # 背板层: 8层 × 0.2 = 1.6mm
    # 光学层: 5层 × 0.08 = 0.4mm
    # 总高度: 2.0mm
    expected_height = 1.6 + 0.4
    assert np.max(mesh.vertices[:, 2]) == pytest.approx(expected_height, abs=0.01)

    z_coords = mesh.vertices[:, 2]

    # 背板层 (0-1.6mm)
    backing = z_coords[z_coords < 1.6]
    assert len(backing) > 0
    assert np.max(backing) == pytest.approx(1.6, abs=0.01)

    # 光学层 (1.6-2.0mm)
    optical = z_coords[z_coords >= 1.6]
    assert len(optical) > 0
    assert np.max(optical) == pytest.approx(2.0, abs=0.01)


def test_pixel_scale_xy():
    """测试XY像素缩放"""
    mesh = trimesh.creation.box(extents=[10, 10, 5])
    mesh.vertices[:, 2] = np.clip(mesh.vertices[:, 2], 0, 4)

    backing_metadata = {
        'backing_z_range': (5, 8),  # 超出mesh范围,测试边界
    }

    pixel_scale = 2.0  # 2mm per pixel
    _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale)

    # 验证XY缩放
    x_coords = mesh.vertices[:, 0]
    y_coords = mesh.vertices[:, 1]

    # 原始范围 -5到5,缩放后应为 -10到10
    assert np.max(x_coords) == pytest.approx(10.0, abs=0.01)
    assert np.min(x_coords) == pytest.approx(-10.0, abs=0.01)
    assert np.max(y_coords) == pytest.approx(10.0, abs=0.01)
    assert np.min(y_coords) == pytest.approx(-10.0, abs=0.01)


def test_empty_mesh():
    """测试空mesh处理"""
    mesh = None
    backing_metadata = {
        'backing_z_range': (5, 12),
    }

    result = _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale=1.0)
    assert result is None

    # 测试无顶点mesh
    mesh = trimesh.Trimesh()
    result = _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale=1.0)
    assert result is mesh


def test_edge_case_backing_at_top():
    """测试边界情况: 背板在最顶层"""
    mesh = trimesh.creation.box(extents=[10, 10, 10])
    mesh.vertices[:, 2] = np.clip(mesh.vertices[:, 2], 0, 9)

    backing_metadata = {
        'backing_z_range': (5, 9),  # 背板从Z=5到最顶层Z=9
    }

    _apply_variable_layer_height_transform(mesh, backing_metadata, pixel_scale=1.0)

    # 光学层: 5层 × 0.08 = 0.4mm
    # 背板层: 5层 × 0.2 = 1.0mm
    # 总高度: 1.4mm
    expected_height = 0.4 + 1.0
    assert np.max(mesh.vertices[:, 2]) == pytest.approx(expected_height, abs=0.01)


def test_backing_layer_height_constant():
    """验证背板层高常量值"""
    assert PrinterConfig.BACKING_LAYER_HEIGHT == 0.2
    assert PrinterConfig.LAYER_HEIGHT == 0.08


if __name__ == '__main__':
    pytest.main([__file__, '-v'])