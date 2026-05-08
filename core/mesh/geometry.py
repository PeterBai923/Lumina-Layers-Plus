"""
Lumina Studio - Geometry Utilities
Geometry utilities module - Pure functional geometry calculation tools
"""

import numpy as np
import trimesh
from core.utils.logger import get_logger

logger = get_logger("MESH")

# Standard cube face indices (12 triangles for 8 vertices)
CUBE_FACES = [
    [0, 2, 1], [0, 3, 2],
    [4, 5, 6], [4, 6, 7],
    [0, 1, 5], [0, 5, 4],
    [1, 2, 6], [1, 6, 5],
    [2, 3, 7], [2, 7, 6],
    [3, 0, 4], [3, 4, 7],
]
CUBE_FACES_NP = np.array(CUBE_FACES, dtype=np.int64)

# Standard cube vertices template (unit cube, 8 vertices)
CUBE_VERTICES_TEMPLATE = np.array([
    [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
    [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]
], dtype=np.float64)


def fill_box_vertices_batch(vertices, start_idx, x0, x1, y0, y1, z0, z1):
    """
    Fill box vertices in batch (vectorized implementation)
    批量填充立方体顶点（向量化实现）

    Args:
        vertices: Preallocated vertex array (N*8, 3). (预分配的顶点数组)
        start_idx: Starting box index. (起始立方体索引)
        x0, x1, y0, y1: Box corner coordinates as (n,) arrays. (立方体角坐标数组)
        z0, z1: Z-axis range (scalar or array). (Z 轴范围)

    Note:
        Modifies vertices in-place by filling batch[start_idx * 8 : (start_idx + n) * 8].
    """
    n = len(x0)
    batch = np.empty((n, 8, 3), dtype=np.float64)
    batch[:] = CUBE_VERTICES_TEMPLATE

    # Bottom face vertices (z=z0)
    batch[:, 0, 0] = x0
    batch[:, 0, 1] = y0
    batch[:, 0, 2] = z0
    batch[:, 1, 0] = x1
    batch[:, 1, 1] = y0
    batch[:, 1, 2] = z0
    batch[:, 2, 0] = x1
    batch[:, 2, 1] = y1
    batch[:, 2, 2] = z0
    batch[:, 3, 0] = x0
    batch[:, 3, 1] = y1
    batch[:, 3, 2] = z0

    # Top face vertices (z=z1)
    batch[:, 4, 0] = x0
    batch[:, 4, 1] = y0
    batch[:, 4, 2] = z1
    batch[:, 5, 0] = x1
    batch[:, 5, 1] = y0
    batch[:, 5, 2] = z1
    batch[:, 6, 0] = x1
    batch[:, 6, 1] = y1
    batch[:, 6, 2] = z1
    batch[:, 7, 0] = x0
    batch[:, 7, 1] = y1
    batch[:, 7, 2] = z1

    vertices[start_idx * 8 : (start_idx + n) * 8] = batch.reshape(-1, 3)


def fill_box_faces_batch(faces, start_idx, n_boxes, vertex_offset=0):
    """
    Fill box faces in batch (vectorized implementation)
    批量填充面索引（向量化实现）

    Args:
        faces: Preallocated face array (N*12, 3). (预分配的面数组)
        start_idx: Starting box index. (起始立方体索引)
        n_boxes: Number of boxes to fill. (立方体数量)
        vertex_offset: Vertex index offset. (顶点索引偏移量)

    Note:
        Modifies faces in-place by filling faces[start_idx * 12 : (start_idx + n_boxes) * 12].
    """
    offsets = (np.arange(n_boxes, dtype=np.int64) * 8 + vertex_offset).reshape(-1, 1, 1)
    batch_faces = CUBE_FACES_NP.reshape(1, 12, 3) + offsets
    faces[start_idx * 12 : (start_idx + n_boxes) * 12] = batch_faces.reshape(-1, 3)


def create_keychain_loop(width_mm, length_mm, hole_dia_mm, thickness_mm, 
                         attach_x_mm, attach_y_mm):
    """
    Create keychain loop mesh
    
    This is a pure function that generates a rectangle + semicircle loop geometry with hole
    
    Args:
        width_mm: Loop width (millimeters)
        length_mm: Loop length (millimeters)
        hole_dia_mm: Hole diameter (millimeters)
        thickness_mm: Loop thickness (millimeters)
        attach_x_mm: Attachment point X coordinate (millimeters)
        attach_y_mm: Attachment point Y coordinate (millimeters)
    
    Returns:
        trimesh.Trimesh: Loop mesh object
    """
    logger.info("Creating keychain loop: w=%s, l=%s, hole=%s, thick=%s, pos=(%s, %s)", width_mm, length_mm, hole_dia_mm, thickness_mm, attach_x_mm, attach_y_mm)
    
    # Calculate geometric parameters
    half_w = width_mm / 2
    circle_radius = half_w
    hole_radius = min(hole_dia_mm / 2, circle_radius * 0.8)
    rect_height = max(0.2, length_mm - circle_radius)
    circle_center_y = rect_height
    
    # Generate outer contour points
    n_arc = 32
    outer_pts = []
    
    # Rectangle bottom
    outer_pts.append((-half_w, 0))
    outer_pts.append((half_w, 0))
    outer_pts.append((half_w, rect_height))
    
    # Semicircle top
    for i in range(1, n_arc):
        angle = np.pi * i / n_arc
        x = circle_radius * np.cos(angle)
        y = circle_center_y + circle_radius * np.sin(angle)
        outer_pts.append((x, y))
    
    # Rectangle left side
    outer_pts.append((-half_w, rect_height))
    
    outer_pts = np.array(outer_pts)
    n_outer = len(outer_pts)
    
    # Generate hole points
    n_hole = 32
    hole_pts = []
    for i in range(n_hole):
        angle = 2 * np.pi * i / n_hole
        x = hole_radius * np.cos(angle)
        y = circle_center_y + hole_radius * np.sin(angle)
        hole_pts.append((x, y))
    hole_pts = np.array(hole_pts)
    n_hole_pts = len(hole_pts)
    
    # Build 3D vertices
    vertices = []
    faces = []
    
    # Bottom face outer contour
    for pt in outer_pts:
        vertices.append([pt[0], pt[1], 0])
    
    # Bottom face hole
    for pt in hole_pts:
        vertices.append([pt[0], pt[1], 0])
    
    # Top face outer contour
    for pt in outer_pts:
        vertices.append([pt[0], pt[1], thickness_mm])
    
    # Top face hole
    for pt in hole_pts:
        vertices.append([pt[0], pt[1], thickness_mm])
    
    # Index definitions
    bottom_outer_start = 0
    bottom_hole_start = n_outer
    top_outer_start = n_outer + n_hole_pts
    top_hole_start = n_outer + n_hole_pts + n_outer
    
    # Outer contour side faces
    for i in range(n_outer):
        i_next = (i + 1) % n_outer
        bi = bottom_outer_start + i
        bi_next = bottom_outer_start + i_next
        ti = top_outer_start + i
        ti_next = top_outer_start + i_next
        faces.append([bi, bi_next, ti_next])
        faces.append([bi, ti_next, ti])
    
    # Hole side faces
    for i in range(n_hole_pts):
        i_next = (i + 1) % n_hole_pts
        bi = bottom_hole_start + i
        bi_next = bottom_hole_start + i_next
        ti = top_hole_start + i
        ti_next = top_hole_start + i_next
        faces.append([bi, ti, ti_next])
        faces.append([bi, ti_next, bi_next])
    
    # Connect outer contour and hole (top and bottom faces)
    vertices_arr = np.array(vertices)
    
    bottom_outer_idx = list(range(bottom_outer_start, bottom_outer_start + n_outer))
    bottom_hole_idx = list(range(bottom_hole_start, bottom_hole_start + n_hole_pts))
    bottom_faces = _connect_rings(bottom_outer_idx, bottom_hole_idx, vertices_arr, is_top=False)
    faces.extend(bottom_faces)
    
    top_outer_idx = list(range(top_outer_start, top_outer_start + n_outer))
    top_hole_idx = list(range(top_hole_start, top_hole_start + n_hole_pts))
    top_faces = _connect_rings(top_outer_idx, top_hole_idx, vertices_arr, is_top=True)
    faces.extend(top_faces)
    
    # Apply position offset
    vertices_arr = np.array(vertices)
    vertices_arr[:, 0] += attach_x_mm
    vertices_arr[:, 1] += attach_y_mm
    
    # Create mesh
    mesh = trimesh.Trimesh(vertices=vertices_arr, faces=np.array(faces))
    mesh.fix_normals()
    
    logger.info("Loop mesh created: %d vertices, %d faces", len(mesh.vertices), len(mesh.faces))
    
    return mesh


def _connect_rings(outer_indices, hole_indices, vertices_arr, is_top=True):
    """
    Helper function to connect outer ring and inner ring
    Uses greedy algorithm to generate triangular faces
    
    Args:
        outer_indices: Outer ring vertex index list
        hole_indices: Inner ring vertex index list
        vertices_arr: Vertex array
        is_top: Whether it's the top face
    
    Returns:
        list: Face index list
    """
    ring_faces = []
    n_o = len(outer_indices)
    n_h = len(hole_indices)
    
    oi = 0  # Outer ring pointer
    hi = 0  # Inner ring pointer
    
    def get_2d(idx):
        """Get 2D coordinates of vertex"""
        return np.array([vertices_arr[idx][0], vertices_arr[idx][1]])
    
    total_steps = n_o + n_h
    for _ in range(total_steps):
        o_curr = outer_indices[oi % n_o]
        o_next = outer_indices[(oi + 1) % n_o]
        h_curr = hole_indices[hi % n_h]
        h_next = hole_indices[(hi + 1) % n_h]
        
        # Calculate distance to decide connection direction
        dist_o = np.linalg.norm(get_2d(o_next) - get_2d(h_curr))
        dist_h = np.linalg.norm(get_2d(o_curr) - get_2d(h_next))
        
        if oi >= n_o:
            # Outer ring complete, only connect inner ring
            if is_top:
                ring_faces.append([o_curr, h_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, h_next])
            hi += 1
        elif hi >= n_h:
            # Inner ring complete, only connect outer ring
            if is_top:
                ring_faces.append([o_curr, o_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, o_next])
            oi += 1
        elif dist_o < dist_h:
            # Connect next point of outer ring
            if is_top:
                ring_faces.append([o_curr, o_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, o_next])
            oi += 1
        else:
            # Connect next point of inner ring
            if is_top:
                ring_faces.append([o_curr, h_next, h_curr])
            else:
                ring_faces.append([o_curr, h_curr, h_next])
            hi += 1
    
    return ring_faces
