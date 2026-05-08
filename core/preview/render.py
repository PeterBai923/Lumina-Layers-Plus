"""
Lumina Studio - Preview Rendering Module

Provides functions for rendering 2D/3D previews, generating GLB files,
and creating visual representations of the print bed and model.
"""

import os
import threading
import colorsys
import math
import numpy as np
import cv2
import trimesh
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, List, Dict, Tuple

from config import PrinterConfig, PREVIEW_SCALE, OUTPUT_DIR
from core.mesh.geometry import CUBE_FACES
from core.color.formats import rgb_to_hex, hex_to_rgb

# Fixed bed size constants
FIXED_BED_WIDTH_MM = 256
FIXED_BED_HEIGHT_MM = 256
FIXED_BED_LABEL = "256x256 mm"

# Grid template cache for performance optimization
#
# Cache Strategy:
# - Key: (theme, bed_width_mm, bed_height_mm)
# - Value: PIL Image with grid lines
# - Invalidation: Never (assumes fixed bed size in current version)
#
# Thread Safety: Uses double-checked locking pattern
#
# Performance Impact:
# - Avoids ~66 draw.line() calls per preview
# - Critical for high-frequency preview updates (slider dragging)
_GRID_TEMPLATE_CACHE = {}
_CACHE_LOCK = threading.Lock()


def _get_or_create_grid_template(is_dark: bool, bed_w_mm: int, bed_h_mm: int):
    """
    Get or create grid template for performance optimization.

    Args:
        is_dark: True for dark theme, False for light theme
        bed_w_mm: Bed width in mm
        bed_h_mm: Bed height in mm

    Returns:
        PIL Image with grid lines (transparent background)

    Raises:
        ValueError: If bed dimensions are not positive
    """
    # Parameter validation
    if bed_w_mm <= 0 or bed_h_mm <= 0:
        raise ValueError(f"Bed dimensions must be positive: {bed_w_mm}x{bed_h_mm}")

    cache_key = ("dark" if is_dark else "light", bed_w_mm, bed_h_mm)

    # Double-checked locking pattern for thread safety
    if cache_key in _GRID_TEMPLATE_CACHE:
        return _GRID_TEMPLATE_CACHE[cache_key]

    with _CACHE_LOCK:
        # Check again to prevent duplicate creation
        if cache_key in _GRID_TEMPLATE_CACHE:
            return _GRID_TEMPLATE_CACHE[cache_key]

        # Create grid template on first call
        ppm = 1200 / max(bed_w_mm, bed_h_mm)
        canvas_w = int(bed_w_mm * ppm)
        canvas_h = int(bed_h_mm * ppm)

        template = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(template)

        # Theme colors
        if is_dark:
            grid_fine = (52, 52, 58, 255)
            grid_bold = (72, 72, 80, 255)
            axis_color = (90, 90, 110, 255)
        else:
            grid_fine = (225, 225, 230, 255)
            grid_bold = (180, 180, 190, 255)
            axis_color = (100, 100, 120, 255)

        # Draw grid lines
        step_10 = max(1, int(10 * ppm))
        step_50 = max(1, int(50 * ppm))

        # Draw 10mm grid lines
        for x in range(0, canvas_w, step_10):
            draw.line([(x, 0), (x, canvas_h)], fill=grid_fine, width=1)
        for y in range(0, canvas_h, step_10):
            draw.line([(0, y), (canvas_w, y)], fill=grid_fine, width=1)

        # Draw 50mm grid lines
        for x in range(0, canvas_w, step_50):
            draw.line([(x, 0), (x, canvas_h)], fill=grid_bold, width=2)
        for y in range(0, canvas_h, step_50):
            draw.line([(0, y), (canvas_w, y)], fill=grid_bold, width=2)

        # Draw axes
        draw.line([(0, canvas_h), (canvas_w, canvas_h)], fill=axis_color, width=2)
        draw.line([(0, 0), (0, canvas_h)], fill=axis_color, width=2)

        # Cache template
        _GRID_TEMPLATE_CACHE[cache_key] = template
        return template


def _create_bed_mesh(bed_w_mm: int, bed_h_mm: int, is_dark: bool = True):
    """Create a rounded-corner print bed mesh with UV-mapped texture.
    创建圆角打印热床网格，带 UV 贴图纹理。

    The geometry outline matches the texture's rounded rectangle so that
    no sharp-corner artifacts remain visible in the 3D preview.
    几何轮廓与纹理的圆角矩形一致，避免 3D 预览中出现直角残留。

    Args:
        bed_w_mm (int): Bed width in mm. (热床宽度 mm)
        bed_h_mm (int): Bed height in mm. (热床高度 mm)
        is_dark (bool): Use dark PEI theme. (使用深色 PEI 主题)

    Returns:
        trimesh.Trimesh: Textured bed mesh, or None on error. (带纹理的热床网格)
    """
    try:
        from PIL import Image as PILImage, ImageDraw as PILDraw
        from mapbox_earcut import triangulate_float64

        tex_scale = 4  # pixels per mm
        tex_w = int(bed_w_mm * tex_scale)
        tex_h = int(bed_h_mm * tex_scale)
        corner_r = int(8 * tex_scale)
        margin = max(2, corner_r // 4)

        # Corner radius in world mm (matches texture margin/radius ratio)
        r_mm = margin / tex_scale + corner_r / tex_scale

        if is_dark:
            base_color = (58, 58, 66)
            fine_color = (42, 42, 48)
            bold_color = (90, 90, 100)
            border_color = (45, 45, 52)
        else:
            base_color = (242, 242, 245)
            fine_color = (225, 225, 230)
            bold_color = (180, 180, 190)
            border_color = (195, 195, 205)

        # --- Texture (fill entire image with base_color, no edge_color needed) ---
        img = PILImage.new("RGB", (tex_w, tex_h), base_color)
        draw = PILDraw.Draw(img)

        step_10 = int(10 * tex_scale)
        for x in range(0, tex_w, step_10):
            draw.line([(x, 0), (x, tex_h)], fill=fine_color, width=1)
        for y in range(0, tex_h, step_10):
            draw.line([(0, y), (tex_w, y)], fill=fine_color, width=1)

        step_50 = int(50 * tex_scale)
        for x in range(0, tex_w, step_50):
            draw.line([(x, 0), (x, tex_h)], fill=bold_color, width=3)
        for y in range(0, tex_h, step_50):
            draw.line([(0, y), (tex_w, y)], fill=bold_color, width=3)

        draw.rounded_rectangle(
            [margin, margin, tex_w - margin, tex_h - margin],
            radius=corner_r,
            outline=border_color,
            width=3,
        )

        # --- Rounded-rectangle geometry outline (world coords, mm) ---
        arc_segs = 16
        angles = np.linspace(0, np.pi / 2, arc_segs + 1)
        cos_a = np.cos(angles)
        sin_a = np.sin(angles)

        outline_pts = []
        # Bottom-left corner (origin side)
        for i in range(arc_segs + 1):
            outline_pts.append([r_mm - r_mm * cos_a[i], r_mm - r_mm * sin_a[i]])
        # Bottom-right corner
        for i in range(arc_segs + 1):
            outline_pts.append(
                [bed_w_mm - r_mm + r_mm * sin_a[i], r_mm - r_mm * cos_a[i]]
            )
        # Top-right corner
        for i in range(arc_segs + 1):
            outline_pts.append(
                [bed_w_mm - r_mm + r_mm * cos_a[i], bed_h_mm - r_mm + r_mm * sin_a[i]]
            )
        # Top-left corner
        for i in range(arc_segs + 1):
            outline_pts.append(
                [r_mm - r_mm * sin_a[i], bed_h_mm - r_mm + r_mm * cos_a[i]]
            )

        outline_pts = np.array(outline_pts, dtype=np.float64)

        # Triangulate the rounded-rect polygon via mapbox-earcut
        rings = np.array([len(outline_pts)], dtype=np.int32)
        tri_flat = triangulate_float64(outline_pts, rings)
        tri_indices = np.array(tri_flat, dtype=np.int64).reshape(-1, 3)

        # Build 3D vertices (Z=0) and UV coords
        n_pts = len(outline_pts)
        verts_3d = np.zeros((n_pts, 3), dtype=np.float64)
        verts_3d[:, 0] = outline_pts[:, 0]
        verts_3d[:, 1] = outline_pts[:, 1]

        uv = np.zeros((n_pts, 2), dtype=np.float64)
        uv[:, 0] = outline_pts[:, 0] / bed_w_mm
        uv[:, 1] = 1.0 - outline_pts[:, 1] / bed_h_mm

        from trimesh.visual.material import SimpleMaterial
        from trimesh.visual import TextureVisuals

        mesh = trimesh.Trimesh(vertices=verts_3d, faces=tri_indices, process=False)
        mesh.visual = TextureVisuals(uv=uv, material=SimpleMaterial(image=img))

        theme_name = "dark" if is_dark else "light"
        print(
            f"[BED] Created {theme_name} {bed_w_mm}x{bed_h_mm}mm rounded bed ({n_pts} verts)"
        )
        return mesh

    except Exception as e:
        print(f"[BED] Failed to create bed mesh: {e}")
        import traceback

        traceback.print_exc()
        return None


def _create_preview_mesh(
    matched_rgb,
    mask_solid,
    total_layers,
    backing_color_id=0,
    backing_z_range=None,
    preview_colors=None,
):
    """Create simplified 3D preview mesh for browser display.
    为浏览器显示创建简化的 3D 预览网格。

    Args:
        matched_rgb (np.ndarray): RGB color array of shape (H, W, 3). (RGB 颜色数组)
        mask_solid (np.ndarray): Boolean mask of solid pixels of shape (H, W). (实心像素布尔掩码)
        total_layers (int): Total number of Z layers. (Z 轴总层数)
        backing_color_id (int): Backing material ID (0-7), default is 0 (White). (底板材料 ID)
        backing_z_range (tuple): Tuple of (start_z, end_z) for backing layer, or None. (底板 Z 范围)
        preview_colors (list): List of preview colors for materials. (材料预览颜色列表)

    Returns:
        trimesh.Trimesh: Simplified preview mesh, downsampled for large models. (简化预览网格，大模型会降采样)
    """
    height, width = matched_rgb.shape[:2]
    total_pixels = width * height

    TARGET_PIXELS = 300_000

    scale_factor = int(np.sqrt(total_pixels / TARGET_PIXELS))
    scale_factor = max(2, min(scale_factor, 16))

    print(
        f"[PREVIEW] Downsampling by {scale_factor}x ({total_pixels:,} -> ~{TARGET_PIXELS:,} pixels)"
    )

    import torch
    from core.gpu_pipeline import downsample_image_gpu

    device = torch.device("cuda")

    # GPU downsample matched_rgb
    rgb_tensor = torch.from_numpy(matched_rgb.astype(np.float32)).to(device)
    rgb_small, _ = downsample_image_gpu(rgb_tensor, TARGET_PIXELS, mode="area")
    matched_rgb = rgb_small.cpu().numpy().astype(np.uint8)

    # GPU downsample mask_solid
    mask_tensor = torch.from_numpy(mask_solid.astype(np.float32)).to(device)
    mask_small, _ = downsample_image_gpu(mask_tensor, TARGET_PIXELS, mode="nearest")
    mask_solid = mask_small.cpu().numpy().astype(bool)

    height, width = matched_rgb.shape[:2]
    shrink = 0.05 * scale_factor

    vertices = []
    faces = []
    face_colors = []

    for y in range(height):
        for x in range(width):
            if not mask_solid[y, x]:
                continue

            rgb = matched_rgb[y, x]
            rgba = [int(rgb[0]), int(rgb[1]), int(rgb[2]), 255]

            world_y = height - 1 - y
            x0, x1 = x + shrink, x + 1 - shrink
            y0, y1 = world_y + shrink, world_y + 1 - shrink

            # Determine Z range for this pixel
            # If backing_z_range is provided, split the model into backing and non-backing layers
            if backing_z_range is not None and preview_colors is not None:
                backing_start, backing_end = backing_z_range

                # Create backing layer box
                z0_backing = backing_start
                z1_backing = backing_end + 1

                base_idx = len(vertices)
                vertices.extend(
                    [
                        [x0, y0, z0_backing],
                        [x1, y0, z0_backing],
                        [x1, y1, z0_backing],
                        [x0, y1, z0_backing],
                        [x0, y0, z1_backing],
                        [x1, y0, z1_backing],
                        [x1, y1, z1_backing],
                        [x0, y1, z1_backing],
                    ]
                )

                # Apply backing color
                # When backing_color_id=-2 (separate backing), use white color (material_id=0)
                actual_backing_color_id = (
                    0 if backing_color_id == -2 else backing_color_id
                )
                backing_rgba = [
                    int(preview_colors[actual_backing_color_id][0]),
                    int(preview_colors[actual_backing_color_id][1]),
                    int(preview_colors[actual_backing_color_id][2]),
                    255,
                ]

                cube_faces = CUBE_FACES

                for f in cube_faces:
                    faces.append([v + base_idx for v in f])
                    face_colors.append(backing_rgba)

                # Create non-backing layers (if any exist)
                # Bottom layers (0 to backing_start)
                if backing_start > 0:
                    z0_bottom = 0
                    z1_bottom = backing_start

                    base_idx = len(vertices)
                    vertices.extend(
                        [
                            [x0, y0, z0_bottom],
                            [x1, y0, z0_bottom],
                            [x1, y1, z0_bottom],
                            [x0, y1, z0_bottom],
                            [x0, y0, z1_bottom],
                            [x1, y0, z1_bottom],
                            [x1, y1, z1_bottom],
                            [x0, y1, z1_bottom],
                        ]
                    )

                    for f in cube_faces:
                        faces.append([v + base_idx for v in f])
                        face_colors.append(rgba)

                # Top layers (backing_end+1 to total_layers)
                if backing_end + 1 < total_layers:
                    z0_top = backing_end + 1
                    z1_top = total_layers

                    base_idx = len(vertices)
                    vertices.extend(
                        [
                            [x0, y0, z0_top],
                            [x1, y0, z0_top],
                            [x1, y1, z0_top],
                            [x0, y1, z0_top],
                            [x0, y0, z1_top],
                            [x1, y0, z1_top],
                            [x1, y1, z1_top],
                            [x0, y1, z1_top],
                        ]
                    )

                    for f in cube_faces:
                        faces.append([v + base_idx for v in f])
                        face_colors.append(rgba)
            else:
                # Original behavior: single box from 0 to total_layers
                z0, z1 = 0, total_layers

                base_idx = len(vertices)
                vertices.extend(
                    [
                        [x0, y0, z0],
                        [x1, y0, z0],
                        [x1, y1, z0],
                        [x0, y1, z0],
                        [x0, y0, z1],
                        [x1, y0, z1],
                        [x1, y1, z1],
                        [x0, y1, z1],
                    ]
                )

                cube_faces = CUBE_FACES

                for f in cube_faces:
                    faces.append([v + base_idx for v in f])
                    face_colors.append(rgba)

    if not vertices:
        return None

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
    mesh.visual.face_colors = np.array(face_colors, dtype=np.uint8)

    print(
        f"[PREVIEW] Generated: {len(mesh.vertices):,} vertices, {len(mesh.faces):,} faces"
    )

    return mesh


def generate_empty_bed_glb(bed_w: int = None, bed_h: int = None, is_dark: bool = False):
    """Generate a GLB file containing only the print bed (no model).
    生成仅包含打印热床的 GLB 文件（无模型）。

    Args:
        bed_w (int): Bed width in mm. Defaults to fixed 256mm. (热床宽度 mm)
        bed_h (int): Bed height in mm. Defaults to fixed 256mm. (热床高度 mm)
        is_dark (bool): Use dark PEI theme. (使用深色 PEI 主题)

    Returns:
        str: Path to GLB file, or None on failure. (GLB 文件路径，失败返回 None)
    """
    try:
        if bed_w is None or bed_h is None:
            bed_w, bed_h = FIXED_BED_WIDTH_MM, FIXED_BED_HEIGHT_MM
        bed_mesh = _create_bed_mesh(bed_w, bed_h, is_dark=is_dark)
        if bed_mesh is None:
            return None
        glb_scene = trimesh.Scene()
        glb_scene.add_geometry(bed_mesh, node_name="bed")
        glb_path = os.path.join(OUTPUT_DIR, f"empty_bed_{bed_w}x{bed_h}.glb")
        glb_scene.export(glb_path)
        return glb_path
    except Exception as e:
        print(f"[EMPTY_BED] Failed: {e}")
        return None


def generate_realtime_glb(cache):
    """Generate a lightweight GLB preview from cached preview data.

    Called during preview stage so the 3D thumbnail updates immediately
    without waiting for the full 3MF export.

    Args:
        cache: Preview cache dict from generate_preview_cached

    Returns:
        str: Path to GLB file, or None on failure
    """
    if cache is None:
        return None

    matched_rgb = cache.get("matched_rgb")
    mask_solid = cache.get("mask_solid")
    target_w = cache.get("target_w")
    target_h = cache.get("target_h")
    target_width_mm = cache.get("target_width_mm")
    color_conf = cache.get("color_conf")
    structure_mode = cache.get("structure_mode", "single")

    if matched_rgb is None or mask_solid is None:
        return None

    try:
        # Use a fixed thin height (5 color layers + backing = 25 voxel layers)
        total_layers = 25
        preview_colors = color_conf.get("preview") if color_conf else None

        preview_mesh = _create_preview_mesh(
            matched_rgb,
            mask_solid,
            total_layers,
            backing_color_id=cache.get("backing_color_id", 0),
            preview_colors=preview_colors,
        )

        if preview_mesh is None:
            print("[REALTIME_GLB] Preview mesh is None (model too large?)")
            return None

        # Scale from pixel/voxel coords to mm
        # _create_preview_mesh may downsample internally, so we must compute
        # pixel_scale from the mesh's actual bounding box width, not target_w.
        mesh_width = preview_mesh.bounds[1][0] - preview_mesh.bounds[0][0]
        pixel_scale = target_width_mm / mesh_width if mesh_width > 0 else 0.42
        transform = np.eye(4)
        transform[0, 0] = pixel_scale
        transform[1, 1] = pixel_scale
        transform[2, 2] = PrinterConfig.LAYER_HEIGHT
        preview_mesh.apply_transform(transform)

        # Single-sided mode: X-axis mirror correction (consistent with 3MF export)
        is_single_sided = (
            "single" in structure_mode or "single" in structure_mode.lower()
        )
        if is_single_sided:
            model_width_mm = target_width_mm
            mirror_transform = np.array(
                [[-1, 0, 0, model_width_mm], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
            )
            preview_mesh.apply_transform(mirror_transform)

        # Export model-only GLB (bed platform is rendered by frontend)
        # Note: origin/main adds bed platform in Python for Gradio UI;
        # the FastAPI+React frontend renders bed in Three.js instead.
        glb_path = os.path.join(OUTPUT_DIR, "realtime_preview.glb")
        preview_mesh.export(glb_path)
        print(f"[REALTIME_GLB] Exported: {glb_path}")
        return glb_path

    except Exception as e:
        print(f"[REALTIME_GLB] Failed: {e}")
        return None


def render_preview(
    preview_rgba,
    loop_pos,
    loop_width,
    loop_length,
    loop_hole,
    loop_angle,
    loop_enabled,
    color_conf,
    target_width_mm=None,
    is_dark=True,
):
    """Render preview with physical bed grid and optional keychain loop.

    Args:
        target_width_mm: Physical width of the model in mm. If None, estimates from pixels.
        is_dark: True for dark PEI theme, False for light marble theme.
    """
    bed_w_mm, bed_h_mm = FIXED_BED_WIDTH_MM, FIXED_BED_HEIGHT_MM
    ppm = 1200 / max(bed_w_mm, bed_h_mm)

    canvas_w = int(bed_w_mm * ppm)
    canvas_h = int(bed_h_mm * ppm)
    margin = 0  # Remove margin, let print bed grid fill entire canvas

    total_w = canvas_w
    total_h = canvas_h

    # Theme colors
    if is_dark:
        canvas_bg = (38, 38, 44, 255)
        bed_bg = (58, 58, 66, 255)
        border_color = (45, 45, 52, 255)
        label_color = (140, 140, 170, 255)
    else:
        canvas_bg = (215, 215, 220, 255)
        bed_bg = (242, 242, 245, 255)
        border_color = (195, 195, 205, 255)
        label_color = (80, 80, 100, 255)

    canvas = Image.new("RGBA", (total_w, total_h), canvas_bg)
    draw = ImageDraw.Draw(canvas)

    # Rounded bed area
    corner_r = 0  # Remove rounded corners, use square corners to fill canvas
    draw.rounded_rectangle(
        [0, 0, total_w - 1, total_h - 1], radius=corner_r, fill=bed_bg
    )

    # Optimized: Use cached grid template
    grid_template = _get_or_create_grid_template(is_dark, bed_w_mm, bed_h_mm)
    canvas.paste(grid_template, (0, 0), mask=grid_template)

    # Rounded border on top of grid
    draw.rounded_rectangle(
        [0, 0, total_w - 1, total_h - 1], radius=corner_r, outline=border_color, width=2
    )

    # labels (mm)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for mm in range(0, bed_w_mm + 1, 50):
        px = int(mm * ppm)
        if px < total_w and font:
            draw.text((px - 5, total_h - 15), f"{mm}", fill=label_color, font=font)

    for mm in range(0, bed_h_mm + 1, 50):
        px = total_h - int(mm * ppm)
        if px >= 0 and font:
            draw.text((5, px - 5), f"{mm}", fill=label_color, font=font)

    # --- paste model centred on bed ---
    if preview_rgba is not None:
        h, w = preview_rgba.shape[:2]

        # Auto-fill print bed: calculate model size to fill bed
        # Keep aspect ratio, let the long edge equal corresponding bed edge
        aspect_ratio = w / h if h > 0 and w > 0 else 1.0

        if aspect_ratio >= 1.0:
            # Wide image: width fills bed width
            model_w_mm = bed_w_mm
            model_h_mm = bed_w_mm / aspect_ratio
        else:
            # Tall image: height fills bed height
            model_h_mm = bed_h_mm
            model_w_mm = bed_h_mm * aspect_ratio

        new_w = max(1, int(model_w_mm * ppm))
        new_h = max(1, int(model_h_mm * ppm))

        pil_img = Image.fromarray(preview_rgba, mode="RGBA")
        pil_img = pil_img.resize((new_w, new_h), Image.Resampling.NEAREST)

        offset_x = (total_w - new_w) // 2
        offset_y = (total_h - new_h) // 2
        canvas.paste(pil_img, (offset_x, offset_y), pil_img)

        # --- loop overlay ---
        if loop_enabled and loop_pos is not None:
            mm_per_px = model_w_mm / w if w > 0 else PrinterConfig.NOZZLE_WIDTH
            canvas = _draw_loop_on_canvas(
                canvas,
                loop_pos,
                loop_width,
                loop_length,
                loop_hole,
                loop_angle,
                color_conf,
                margin,
                ppm=ppm,
                img_offset=(offset_x, offset_y),
                mm_per_px=mm_per_px,
            )

    return np.array(canvas)


def _draw_loop_on_canvas(
    pil_img,
    loop_pos,
    loop_width,
    loop_length,
    loop_hole,
    loop_angle,
    color_conf,
    margin,
    ppm=None,
    img_offset=None,
    mm_per_px=None,
):
    """Draw keychain loop marker on canvas.

    Args:
        ppm: pixels-per-mm (new bed system). Falls back to legacy PREVIEW_SCALE.
        img_offset: (x, y) pixel offset where the model image was pasted.
        mm_per_px: mm per original image pixel. Falls back to NOZZLE_WIDTH.
    """
    if ppm is None:
        ppm = PREVIEW_SCALE / PrinterConfig.NOZZLE_WIDTH
    if img_offset is None:
        img_offset = (margin, 0)
    if mm_per_px is None:
        mm_per_px = PrinterConfig.NOZZLE_WIDTH

    loop_w_px = int(loop_width * ppm)
    loop_h_px = int(loop_length * ppm)
    hole_r_px = int(loop_hole / 2 * ppm)
    circle_r_px = loop_w_px // 2

    # loop_pos is in original image pixel coords
    cx = img_offset[0] + int(loop_pos[0] * mm_per_px * ppm)
    cy = img_offset[1] + int(loop_pos[1] * mm_per_px * ppm)

    loop_size = max(loop_w_px, loop_h_px) * 2 + 20
    loop_layer = Image.new("RGBA", (loop_size, loop_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(loop_layer)

    lc = loop_size // 2
    rect_h = max(1, loop_h_px - circle_r_px)

    loop_color = (220, 60, 60, 200)
    outline_color = (255, 255, 255, 255)

    draw.rectangle(
        [lc - loop_w_px // 2, lc, lc + loop_w_px // 2, lc + rect_h],
        fill=loop_color,
        outline=outline_color,
        width=2,
    )

    draw.ellipse(
        [lc - circle_r_px, lc - circle_r_px, lc + circle_r_px, lc + circle_r_px],
        fill=loop_color,
        outline=outline_color,
        width=2,
    )

    draw.ellipse(
        [lc - hole_r_px, lc - hole_r_px, lc + hole_r_px, lc + hole_r_px],
        fill=(0, 0, 0, 0),
    )

    if loop_angle != 0:
        loop_layer = loop_layer.rotate(
            -loop_angle, center=(lc, lc), expand=False, resample=Image.BICUBIC
        )

    paste_x = cx - lc
    paste_y = cy - lc - rect_h // 2
    pil_img.paste(loop_layer, (paste_x, paste_y), loop_layer)

    return pil_img


def _resolve_highlight_mask(color_match, mask_solid, region_mask=None, scope="global"):
    """Determine highlight mask based on selection scope: region first, otherwise global same color."""
    if scope == "region" and region_mask is not None:
        return region_mask & mask_solid
    return color_match & mask_solid


def generate_highlight_preview(
    cache,
    highlight_color: str,
    loop_pos=None,
    add_loop=False,
    loop_width=4,
    loop_length=8,
    loop_hole=2.5,
    loop_angle=0,
):
    """
    Generate preview image with a specific color highlighted.

    This function creates a preview where the selected color is shown normally
    while all other colors are dimmed/grayed out, making it easy to see
    where a specific color is used in the image.

    Args:
        cache: Preview cache from generate_preview_cached
        highlight_color: Hex color to highlight (e.g., '#ff0000')
        loop_pos: Optional loop position tuple (x, y)
        add_loop: Whether to show keychain loop
        loop_width: Loop width in mm
        loop_length: Loop length in mm
        loop_hole: Loop hole diameter in mm
        loop_angle: Loop rotation angle in degrees

    Returns:
        tuple: (display_image, status_message)
    """
    if cache is None:
        return None, "[ERROR] Please generate preview first"

    if not highlight_color:
        # No highlight - return normal preview
        preview_rgba = cache.get("preview_rgba")
        if preview_rgba is None:
            return None, "[ERROR] Invalid cache"

        color_conf = cache["color_conf"]
        display = render_preview(
            preview_rgba,
            loop_pos if add_loop else None,
            loop_width,
            loop_length,
            loop_hole,
            loop_angle,
            add_loop,
            color_conf,
            target_width_mm=cache.get("target_width_mm"),
            is_dark=cache.get("is_dark", True),
        )
        return display, "[OK] Preview restored"

    # Parse highlight color
    highlight_hex = highlight_color.strip().lower()
    if not highlight_hex.startswith("#"):
        highlight_hex = "#" + highlight_hex

    # Convert hex to RGB
    try:
        r = int(highlight_hex[1:3], 16)
        g = int(highlight_hex[3:5], 16)
        b = int(highlight_hex[5:7], 16)
        highlight_rgb = np.array([r, g, b], dtype=np.uint8)
    except (ValueError, IndexError):
        return None, f"[ERROR] Invalid color: {highlight_color}"

    # Get data from cache
    matched_rgb = cache.get("matched_rgb")
    mask_solid = cache.get("mask_solid")
    color_conf = cache.get("color_conf")

    if matched_rgb is None or mask_solid is None:
        return None, "[ERROR] Incomplete cache"

    target_h, target_w = matched_rgb.shape[:2]

    # Create highlight mask - pixels matching the highlight color
    color_match = np.all(matched_rgb == highlight_rgb, axis=2)

    scope = cache.get("selection_scope", "global")
    region_mask = cache.get("selected_region_mask")
    highlight_mask = _resolve_highlight_mask(
        color_match,
        mask_solid,
        region_mask=region_mask,
        scope=scope,
    )

    # Count highlighted pixels
    highlight_count = np.sum(highlight_mask)
    total_solid = np.sum(mask_solid)

    if highlight_count == 0:
        return None, f"[WARNING] Color not found: {highlight_hex}"

    highlight_percentage = round(highlight_count / total_solid * 100, 2)

    # Create highlighted preview
    # Option 1: Dim non-highlighted areas (grayscale + reduced opacity)
    preview_rgba = np.zeros((target_h, target_w, 4), dtype=np.uint8)

    # For non-highlighted solid pixels: convert to grayscale and dim
    non_highlight_mask = mask_solid & ~highlight_mask
    if np.any(non_highlight_mask):
        # Convert to grayscale
        gray_values = np.mean(matched_rgb[non_highlight_mask], axis=1).astype(np.uint8)
        # Apply dimming (mix with darker gray)
        dimmed_gray = (gray_values * 0.4 + 80).astype(np.uint8)
        preview_rgba[non_highlight_mask, 0] = dimmed_gray
        preview_rgba[non_highlight_mask, 1] = dimmed_gray
        preview_rgba[non_highlight_mask, 2] = dimmed_gray
        preview_rgba[non_highlight_mask, 3] = 180

    # For highlighted pixels: show original color with full opacity
    preview_rgba[highlight_mask, :3] = matched_rgb[highlight_mask]
    preview_rgba[highlight_mask, 3] = 255

    # Add a subtle colored border/glow effect around highlighted regions
    # by dilating the highlight mask and drawing a border
    try:
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(highlight_mask.astype(np.uint8), kernel, iterations=2)
        border_mask = (dilated > 0) & ~highlight_mask & mask_solid

        # Draw border in a contrasting color (cyan for visibility)
        if np.any(border_mask):
            preview_rgba[border_mask, 0] = 0
            preview_rgba[border_mask, 1] = 255
            preview_rgba[border_mask, 2] = 255
            preview_rgba[border_mask, 3] = 200
    except Exception as e:
        print(f"[HIGHLIGHT] Border effect skipped: {e}")

    # Render display
    display = render_preview(
        preview_rgba,
        loop_pos if add_loop else None,
        loop_width,
        loop_length,
        loop_hole,
        loop_angle,
        add_loop,
        color_conf,
        target_width_mm=cache.get("target_width_mm"),
        is_dark=cache.get("is_dark", True),
    )

    return (
        display,
        f"Highlight {highlight_hex} ({highlight_percentage}%, {highlight_count:,} pixels)",
    )


def clear_highlight_preview(
    cache,
    loop_pos=None,
    add_loop=False,
    loop_width=4,
    loop_length=8,
    loop_hole=2.5,
    loop_angle=0,
):
    """
    Clear highlight and restore normal preview.

    Args:
        cache: Preview cache from generate_preview_cached
        loop_pos: Optional loop position tuple (x, y)
        add_loop: Whether to show keychain loop
        loop_width: Loop width in mm
        loop_length: Loop length in mm
        loop_hole: Loop hole diameter in mm
        loop_angle: Loop rotation angle in degrees

    Returns:
        tuple: (display_image, status_message)
    """
    print(
        f"[CLEAR_HIGHLIGHT] Called with cache={cache is not None}, loop_pos={loop_pos}, add_loop={add_loop}"
    )

    if cache is None:
        print("[CLEAR_HIGHLIGHT] Cache is None!")
        return None, "[ERROR] Please generate preview first"

    preview_rgba = cache.get("preview_rgba")
    if preview_rgba is None:
        print("[CLEAR_HIGHLIGHT] preview_rgba is None!")
        return None, "[ERROR] Invalid cache"

    print(f"[CLEAR_HIGHLIGHT] preview_rgba shape: {preview_rgba.shape}")

    color_conf = cache["color_conf"]
    display = render_preview(
        preview_rgba,
        loop_pos if add_loop else None,
        loop_width,
        loop_length,
        loop_hole,
        loop_angle,
        add_loop,
        color_conf,
        target_width_mm=cache.get("target_width_mm"),
        is_dark=cache.get("is_dark", True),
    )

    print(
        f"[CLEAR_HIGHLIGHT] display shape: {display.shape if display is not None else None}"
    )

    return display, "[OK] Preview restored"


def generate_lut_grid_html(lut_path):
    """
    Generate LUT available colors HTML grid (with hue filter + smart search)
    """
    from core.converter import extract_lut_available_colors

    colors = extract_lut_available_colors(lut_path)

    if not colors:
        return f"<div style='color:orange'>LUT file invalid or empty</div>"

    count = len(colors)

    def _classify_hue(r, g, b):
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
        h360 = h * 360
        if s < 0.15 or v < 0.10:
            return "neutral"
        if h360 < 15 or h360 >= 345:
            return "red"
        elif h360 < 40:
            return "orange"
        elif h360 < 70:
            return "yellow"
        elif h360 < 160:
            return "green"
        elif h360 < 195:
            return "cyan"
        elif h360 < 260:
            return "blue"
        elif h360 < 345:
            return "purple"
        return "neutral"

    from ui.widgets.palette import build_search_bar_html, build_hue_filter_bar_html

    # Derive LUT key for favorites persistence
    _lut_key = os.path.splitext(os.path.basename(lut_path))[0] if lut_path else ""

    html = f"""
    <div class="lut-grid-container">
        <div style="margin-bottom: 8px; font-size: 12px; color: #666;">
            Current LUT contains <b>{count}</b> printable colors (click to select): <span id="lut-color-visible-count">{count}</span>
        </div>
        {build_search_bar_html('zh')}
        {build_hue_filter_bar_html('zh')}
        <div id="lut-color-grid-container" data-lut-key="{_lut_key}" style="
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            max-height: 300px;
            overflow-y: auto;
            padding: 5px;
            border: 1px solid #eee;
            border-radius: 8px;
            background: #f9f9f9;">
    """

    for entry in colors:
        hex_val = entry["hex"]
        r, g, b = entry["color"]
        rgb_val = f"R:{r} G:{g} B:{b}"
        hue_cat = _classify_hue(r, g, b)

        html += f"""
        <div class="lut-color-swatch-container" data-hue="{hue_cat}" style="display:flex;">
        <div class="lut-swatch lut-color-swatch"
             data-color="{hex_val}"
             style="background-color: {hex_val}; width:24px; height:24px; cursor:pointer; border:1px solid #ddd; border-radius:3px;"
             title="{hex_val} ({rgb_val})">
        </div>
        </div>
        """

    html += "</div></div>"
    return html


def generate_lut_card_grid_html(lut_path):
    """
    Generate a calibration-card-style (color card) HTML grid for the LUT.

    Colors are displayed in their original LUT order arranged in a square grid,
    matching the physical calibration board layout.  For 8-color LUTs the two
    halves are shown side-by-side horizontally.

    Includes search bar (highlight-in-place, no hiding) and hue filter
    (dims non-matching swatches instead of hiding to preserve grid layout).

    Each swatch is clickable (same data-color / class as the swatch grid) so
    the existing event-delegation click handler picks it up automatically.
    """
    if not lut_path:
        return "<div style='color:orange'>LUT file invalid or empty</div>"

    try:
        lut_grid = np.load(lut_path)
        measured_colors = lut_grid.reshape(-1, 3)
    except Exception as e:
        return f"<div style='color:orange'>LUT load failed: {e}</div>"

    total = len(measured_colors)

    def _classify_hue(r, g, b):
        rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
        h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
        h360 = h * 360
        if s < 0.15 or v < 0.10:
            return "neutral"
        if h360 < 15 or h360 >= 345:
            return "red"
        elif h360 < 40:
            return "orange"
        elif h360 < 70:
            return "yellow"
        elif h360 < 160:
            return "green"
        elif h360 < 195:
            return "cyan"
        elif h360 < 260:
            return "blue"
        elif h360 < 345:
            return "purple"
        return "neutral"

    if total == 2738:
        half = total // 2
        remainder = total - half
        dim1 = int(math.ceil(math.sqrt(half)))
        dim2 = int(math.ceil(math.sqrt(remainder)))
        grids = [
            (measured_colors[:half], dim1, "Card A"),
            (measured_colors[half:], dim2, "Card B"),
        ]
    else:
        dim = int(math.ceil(math.sqrt(total)))
        label = f"{total} Color Card"
        grids = [(measured_colors, dim, label)]

    cell = 18
    gap = 1

    from ui.widgets.palette import build_search_bar_html, build_hue_filter_bar_html

    html_parts = [
        f'<div style="margin-bottom:8px; font-size:12px; color:#666;">Current LUT contains <b>{total}</b> printable colors (click to select): <span id="lut-color-visible-count">{total}</span></div>',
        build_search_bar_html("zh"),
        build_hue_filter_bar_html("zh"),
    ]

    # Derive LUT key for favorites persistence
    _lut_key = os.path.splitext(os.path.basename(lut_path))[0] if lut_path else ""

    # Grid
    html_parts.append(
        f"<div id='lut-color-grid-container' data-lut-key='{_lut_key}' style='display:flex; gap:12px; align-items:flex-start; "
        "overflow-x:auto; padding:4px;'>"
    )

    for colors_arr, dim, title in grids:
        html_parts.append(
            f"<div style='flex-shrink:0;'>"
            f"<div style='font-size:11px; color:#666; margin-bottom:4px;'>{title} ({len(colors_arr)})</div>"
            f"<div style='display:grid; grid-template-columns:repeat({dim}, {cell}px); gap:{gap}px; "
            f"border:1px solid #eee; border-radius:6px; padding:4px; background:#f9f9f9;'>"
        )
        for c in colors_arr:
            r, g, b = int(c[0]), int(c[1]), int(c[2])
            hex_val = f"#{r:02x}{g:02x}{b:02x}"
            hue_cat = _classify_hue(r, g, b)
            html_parts.append(
                f"<div class='lut-swatch lut-color-swatch' data-color='{hex_val}' data-hue='{hue_cat}' "
                f"style='width:{cell}px;height:{cell}px;background:{hex_val};"
                f"cursor:pointer;border-radius:2px;' "
                f"title='{hex_val} (R:{r} G:{g} B:{b})'></div>"
            )
        html_parts.append("</div></div>")

    html_parts.append("</div>")
    return "".join(html_parts)
