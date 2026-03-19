"""
core.pipeline — 图像转换管道模块包
Image conversion pipeline module package.

本包将 converter.py 和 image_processing.py 中的图像转换逻辑
拆分为独立模块，每个模块负责一个加工步骤。

Exports:
    - run_raster_pipeline: 光栅转换管道（S01-S12）
    - run_preview_pipeline: 预览管道（P01-P06）
    - Step modules: s01-s12, p01-p06
"""

# Step modules — raster pipeline
from core.pipeline import s01_input_validation
from core.pipeline import s02_image_processing
from core.pipeline import s03_color_replacement
from core.pipeline import s04_debug_preview
from core.pipeline import s05_preview_generation
from core.pipeline import s06_voxel_building
from core.pipeline import s07_mesh_generation
from core.pipeline import s08_auxiliary_meshes
from core.pipeline import s09_export_3mf
from core.pipeline import s10_color_recipe
from core.pipeline import s11_glb_preview
from core.pipeline import s12_result_assembly

# Step modules — preview pipeline
from core.pipeline import p01_preview_validation
from core.pipeline import p02_lut_metadata
from core.pipeline import p03_core_processing
from core.pipeline import p04_cache_building
from core.pipeline import p05_palette_extraction
from core.pipeline import p06_bed_rendering

# Coordinator entry points
from core.pipeline.coordinator import run_raster_pipeline, run_preview_pipeline
