"""
Lumina Studio - Color Replacement Manager

Manages color replacement mappings for preview and final model generation.
Supports CRUD operations on color mappings and batch application to images.
"""

from typing import Dict, Tuple, Optional, List
import numpy as np
from core.color_utils import rgb_to_hex, hex_to_rgb


class ColorReplacementManager:
    """
    Manages color replacement mappings for preview and final model generation.
    
    Color replacements allow users to swap specific colors in the preview
    with different colors before generating the final 3D model.
    """

    def __init__(self):
        """Initialize an empty color replacement manager."""
        self._replacements: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}

    def add_replacement(self, original: Tuple[int, int, int],
                       replacement: Tuple[int, int, int]) -> None:
        """
        Add or update a color replacement mapping.
        
        Args:
            original: Original RGB color tuple (R, G, B) with values 0-255
            replacement: Replacement RGB color tuple (R, G, B) with values 0-255
            
        Note:
            If original == replacement, the mapping is ignored (not added).
        """
        # Validate inputs
        original = self._validate_color(original)
        replacement = self._validate_color(replacement)
        
        # Don't add if colors are the same
        if original == replacement:
            return
        
        self._replacements[original] = replacement

    def remove_replacement(self, original: Tuple[int, int, int]) -> bool:
        """
        Remove a color replacement mapping.
        
        Args:
            original: Original RGB color tuple to remove
            
        Returns:
            True if the mapping was found and removed, False otherwise
        """
        original = self._validate_color(original)
        if original in self._replacements:
            del self._replacements[original]
            return True
        return False

    def get_replacement(self, original: Tuple[int, int, int]) -> Optional[Tuple[int, int, int]]:
        """
        Get the replacement color for an original color.
        
        Args:
            original: Original RGB color tuple
            
        Returns:
            Replacement RGB color tuple, or None if not mapped
        """
        original = self._validate_color(original)
        return self._replacements.get(original)

    def apply_to_image(self, rgb_array: np.ndarray) -> np.ndarray:
        """
        Apply all color replacements to an RGB image array.
        
        Args:
            rgb_array: NumPy array of shape (H, W, 3) with dtype uint8
            
        Returns:
            New NumPy array with replacements applied (original is not modified)
        """
        if len(self._replacements) == 0:
            return rgb_array.copy()
        
        result = rgb_array.copy()
        
        for original, replacement in self._replacements.items():
            # Create mask for pixels matching original color
            mask = np.all(rgb_array == original, axis=-1)
            result[mask] = replacement
        
        return result

    def clear(self) -> None:
        """Clear all color replacements."""
        self._replacements.clear()

    def __len__(self) -> int:
        """Return the number of color replacements."""
        return len(self._replacements)

    def __contains__(self, original: Tuple[int, int, int]) -> bool:
        """Check if a color has a replacement mapping."""
        original = self._validate_color(original)
        return original in self._replacements

    def get_all_replacements(self) -> Dict[Tuple[int, int, int], Tuple[int, int, int]]:
        """
        Get all color replacement mappings.
        
        Returns:
            Dictionary mapping original colors to replacement colors
        """
        return self._replacements.copy()

    def to_dict(self) -> Dict:
        """
        Export replacements as a JSON-serializable dictionary.
        
        Returns:
            Dictionary with string keys (hex colors) for JSON serialization
        """
        return {
            rgb_to_hex(orig): rgb_to_hex(repl)
            for orig, repl in self._replacements.items()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ColorReplacementManager':
        """
        Create a ColorReplacementManager from a serialized dictionary.

        Args:
            data: Dictionary with hex color string keys and values

        Returns:
            New ColorReplacementManager instance with loaded mappings
        """
        manager = cls()
        for orig_hex, repl_hex in data.items():
            original = hex_to_rgb(orig_hex)
            replacement = hex_to_rgb(repl_hex)
            manager.add_replacement(original, replacement)
        return manager

    @staticmethod
    def _validate_color(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
        """
        Validate and normalize a color tuple.
        
        Args:
            color: RGB color tuple
            
        Returns:
            Normalized color tuple with values clamped to 0-255
            
        Raises:
            ValueError: If color is not a valid RGB tuple
        """
        if not isinstance(color, (tuple, list)) or len(color) != 3:
            raise ValueError(f"Color must be a tuple of 3 integers, got {color}")
        
        return tuple(max(0, min(255, int(c))) for c in color)
