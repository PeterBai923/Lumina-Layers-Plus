"""Lumina Studio configuration: paths, printer/smart config, and legacy i18n data."""

import os
import sys
from enum import Enum

# Handle PyInstaller bundled resources
if getattr(sys, 'frozen', False):
    # Running as compiled executable - use current working directory
    _BASE_DIR = os.getcwd()
else:
    # Running as script
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(_BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_asset_path(relative_path: str) -> str:
    """Resolve asset file path for both script and PyInstaller frozen modes.
    解析资源文件路径，兼容脚本运行和 PyInstaller 打包模式。

    Args:
        relative_path (str): Relative path under assets/, e.g. 'smart_8color_stacks.npy'.
                             (assets/ 下的相对路径)

    Returns:
        str: Absolute path to the asset file. (资源文件的绝对路径)

    Raises:
        FileNotFoundError: If the asset file cannot be found. (找不到资源文件时抛出)
    """
    candidates = []
    asset_rel = os.path.join("assets", relative_path)

    if getattr(sys, 'frozen', False):
        # PyInstaller bundled: check _MEIPASS first, then CWD
        candidates.append(os.path.join(sys._MEIPASS, asset_rel))
        candidates.append(os.path.join(os.getcwd(), asset_rel))
    else:
        # Script mode: check project root, then parent dir
        candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), asset_rel))
        candidates.append(os.path.join(os.getcwd(), asset_rel))
        candidates.append(os.path.join("..", asset_rel))

    for path in candidates:
        if os.path.exists(path):
            return path

    raise FileNotFoundError(
        f"Asset not found: {relative_path}\n"
        f"Searched: {candidates}"
    )


class PrinterConfig:
    """Physical printer parameters (layer height, nozzle, backing)."""
    LAYER_HEIGHT: float = 0.08
    NOZZLE_WIDTH: float = 0.42
    COLOR_LAYERS: int = 5
    BACKING_MM: float = 1.6
    SHRINK_OFFSET: float = 0.02


class SmartConfig:
    """Configuration for the Smart 1296 (36x36) System."""
    GRID_DIM: int = 36
    TOTAL_BLOCKS: int = 1296
    
    DEFAULT_BLOCK_SIZE: float = 5.0  # mm (Face Down mode)
    DEFAULT_GAP: float = 0.8  # mm

    FILAMENTS = {
        0: {"name": "White",   "hex": "#FFFFFF", "rgb": [255, 255, 255], "td": 5.0},
        1: {"name": "Cyan",    "hex": "#0086D6", "rgb": [0, 134, 214],   "td": 3.5},
        2: {"name": "Magenta", "hex": "#EC008C", "rgb": [236, 0, 140],   "td": 3.0},
        3: {"name": "Green",   "hex": "#00AE42", "rgb": [0, 174, 66],    "td": 2.0},
        4: {"name": "Yellow",  "hex": "#F4EE2A", "rgb": [244, 238, 42],  "td": 6.0},
        5: {"name": "Black",   "hex": "#000000", "rgb": [0, 0, 0],       "td": 0.6},
    }

class ModelingMode(str, Enum):
    """建模模式枚举"""
    HIGH_FIDELITY = "high-fidelity"  # 高保真模式
    PIXEL = "pixel"  # 像素模式
    VECTOR = "vector"
    
    def get_display_name(self) -> str:
        """获取模式的显示名称"""
        display_names = {
            ModelingMode.HIGH_FIDELITY: "High-Fidelity",
            ModelingMode.PIXEL: "Pixel Art",
            ModelingMode.VECTOR: "Vector"
        }
        return display_names.get(self, self.value)


class ColorSystem:
    """Color model definitions for CMYW, RYBW, and 6-Color systems."""

    CMYW = {
        'name': 'CMYW',
        'slots': ["White", "Cyan", "Magenta", "Yellow"],
        'preview': {
            0: [255, 255, 255, 255],
            1: [0, 134, 214, 255],
            2: [236, 0, 140, 255],
            3: [244, 238, 42, 255]
        },
        'map': {"White": 0, "Cyan": 1, "Magenta": 2, "Yellow": 3},
        'corner_labels': ["白色 (左上)", "青色 (右上)", "品红 (右下)", "黄色 (左下)"],
        'corner_labels_en': ["White (TL)", "Cyan (TR)", "Magenta (BR)", "Yellow (BL)"]
    }

    RYBW = {
        'name': 'RYBW',
        'slots': ["White", "Red", "Yellow", "Blue"],
        'preview': {
            0: [255, 255, 255, 255],
            1: [220, 20, 60, 255],
            2: [255, 230, 0, 255],
            3: [0, 100, 240, 255]
        },
        'map': {"White": 0, "Red": 1, "Yellow": 2, "Blue": 3},
        'filaments': {
            0: {"name": "White",   "rgb": [255, 255, 255], "td": 5.0},
            1: {"name": "Red",     "rgb": [220, 20, 60],   "td": 4.0},
            2: {"name": "Yellow",  "rgb": [255, 230, 0],   "td": 6.0},
            3: {"name": "Blue",    "rgb": [0, 100, 240],   "td": 2.0},
        },
        'corner_labels': ["白色 (左上)", "红色 (右上)", "蓝色 (右下)", "黄色 (左下)"],
        'corner_labels_en': ["White (TL)", "Red (TR)", "Blue (BR)", "Yellow (BL)"]
    }

    SIX_COLOR = {
        'name': '6-Color',
        'base': 6,
        'layer_count': 5,
        'slots': ["White", "Cyan", "Magenta", "Green", "Yellow", "Black"],
        'preview': {
            0: [255, 255, 255, 255],  # White
            1: [0, 134, 214, 255],    # Cyan
            2: [236, 0, 140, 255],    # Magenta
            3: [0, 174, 66, 255],     # Green
            4: [244, 238, 42, 255],   # Yellow
            5: [0, 0, 0, 255]         # Black (纯黑 #000000)
        },
        'map': {"White": 0, "Cyan": 1, "Magenta": 2, "Green": 3, "Yellow": 4, "Black": 5},
        'corner_labels': ["白色 (左上)", "青色 (右上)", "品红 (右下)", "黄色 (左下)"],
        'corner_labels_en': ["White (TL)", "Cyan (TR)", "Magenta (BR)", "Yellow (BL)"]
    }

    EIGHT_COLOR = {
        'name': '8-Color Max',
        'slots': ['Slot 1 (White)', 'Slot 2 (Cyan)', 'Slot 3 (Magenta)', 'Slot 4 (Yellow)', 'Slot 5 (Black)', 'Slot 6 (Red)', 'Slot 7 (Deep Blue)', 'Slot 8 (Green)'],
        'preview': {
            0: [255, 255, 255, 255], 1: [0, 134, 214, 255], 2: [236, 0, 140, 255], 3: [244, 238, 42, 255],
            4: [0, 0, 0, 255], 5: [193, 46, 31, 255], 6: [10, 41, 137, 255], 7: [0, 174, 66, 255]
        },
        'map': {'White': 0, 'Cyan': 1, 'Magenta': 2, 'Yellow': 3, 'Black': 4, 'Red': 5, 'Deep Blue': 6, 'Green': 7},
        'filaments': {
            0: {"name": "White (Jade)", "rgb": [255, 255, 255], "td": 5.0},
            1: {"name": "Cyan",         "rgb": [0, 134, 214],   "td": 3.5},
            2: {"name": "Magenta",      "rgb": [236, 0, 140],   "td": 3.0},
            3: {"name": "Yellow",       "rgb": [244, 238, 42],  "td": 6.0},
            4: {"name": "Black",        "rgb": [0, 0, 0],       "td": 0.6},
            5: {"name": "Red",          "rgb": [193, 46, 31],   "td": 4.0},
            6: {"name": "Deep Blue",    "rgb": [10, 41, 137],   "td": 2.3},
            7: {"name": "Green",        "rgb": [0, 174, 66],    "td": 2.0},
        },
        'corner_labels': ['TL', 'TR', 'BR', 'BL']
    }

    BW = {
        'name': 'BW',
        'base': 2,
        'layer_count': 5,
        'slots': ["White", "Black"],
        'preview': {
            0: [255, 255, 255, 255],  # White
            1: [0, 0, 0, 255]         # Black (纯黑 #000000)
        },
        'map': {"White": 0, "Black": 1},
        'corner_labels': ["白色 (左上)", "黑色 (右上)", "黑色 (右下)", "黑色 (左下)"],
        'corner_labels_en': ["White (TL)", "Black (TR)", "Black (BR)", "Black (BL)"]
    }

    FIVE_COLOR_EXTENDED = {
        'name': '5-Color Extended',
        'base': 5,
        'layer_count': 6,
        'slots': ["White", "Red", "Yellow", "Blue", "Black"],
        'preview': {
            0: [255, 255, 255, 255],  # White
            1: [220, 20, 60, 255],    # Red
            2: [255, 230, 0, 255],    # Yellow
            3: [0, 100, 240, 255],    # Blue
            4: [20, 20, 20, 255]      # Black
        },
        'map': {"White": 0, "Red": 1, "Yellow": 2, "Blue": 3, "Black": 4},
        'filaments': {
            0: {"name": "White",   "rgb": [255, 255, 255], "td": 5.0},
            1: {"name": "Red",     "rgb": [220, 20, 60],   "td": 4.0},
            2: {"name": "Yellow",  "rgb": [255, 230, 0],   "td": 6.0},
            3: {"name": "Blue",    "rgb": [0, 100, 240],   "td": 2.0},
            4: {"name": "Black",   "rgb": [20, 20, 20],    "td": 0.6},
        },
        'corner_labels': ["白色 (左上)", "红色 (右上)", "蓝色 (右下)", "黄色 (左下)", "黑色 (外层)"],
        'corner_labels_en': ["White (TL)", "Red (TR)", "Blue (BR)", "Yellow (BL)", "Black (Outer)"]
    }

    @staticmethod
    def get(mode: str):
        """
        Get color system configuration (Unified 4-Color Backend)
        
        Args:
            mode: Color mode string (4-Color/6-Color/8-Color/BW)
        
        Returns:
            Color system configuration dict
        
        Note:
            4-Color mode defaults to RYBW palette.
            CMYW and RYBW share the same processing pipeline.
        """
        if mode is None:
            return ColorSystem.RYBW  # Default fallback
        
        # Unified 4-Color mode (defaults to RYBW)
        if mode == "4-Color" or "4-Color" in mode:
            return ColorSystem.RYBW
        
        # Check specific patterns
        if "8-Color" in mode:
            return ColorSystem.EIGHT_COLOR
        if "6-Color" in mode:
            return ColorSystem.SIX_COLOR
        
        # Merged LUT: use 8-Color config (superset of all material IDs 0-7)
        if mode == "Merged":
            return ColorSystem.EIGHT_COLOR
        
        # Legacy support for old mode strings
        if "RYBW" in mode:
            return ColorSystem.RYBW
        if "CMYW" in mode:
            return ColorSystem.CMYW
        
        # Check BW last to avoid matching RYBW
        if mode == "BW" or mode == "BW (Black & White)":
            return ColorSystem.BW
        
        # 5-Color Extended mode
        if "5-Color Extended" in mode or "5-Color (Extended)" in mode:
            return ColorSystem.FIVE_COLOR_EXTENDED
        
        return ColorSystem.RYBW  # Default fallback

# ========== Global Constants ==========

# Extractor constants
PHYSICAL_GRID_SIZE = 34
DATA_GRID_SIZE = 32
DST_SIZE = 1000
CELL_SIZE = DST_SIZE / PHYSICAL_GRID_SIZE
LUT_FILE_PATH = os.path.join(OUTPUT_DIR, "lumina_lut.npy")

# Converter constants
PREVIEW_SCALE = 2
PREVIEW_MARGIN = 30

# Default print settings (optimized for color layering)
DEFAULT_PRINT_SETTINGS = {
    'layer_height': '0.08',
    'initial_layer_height': '0.08',
    'wall_loops': '1',
    'top_shell_layers': '0',
    'bottom_shell_layers': '0',
    'sparse_infill_density': '100%',
    'sparse_infill_pattern': 'zig-zag',
}
EXTENDED_PRINT_SETTINGS = {
    **DEFAULT_PRINT_SETTINGS,
    'nozzle_temperature': ['220'] * 8,
    'bed_temperature': ['60'] * 8,
    'filament_type': ['PLA'] * 8,
    'print_speed': '100',
    'travel_speed': '150',
    'enable_support': '0',
    'brim_width': '5',
    'brim_type': 'auto_brim',
}


