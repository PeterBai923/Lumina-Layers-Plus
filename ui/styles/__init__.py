"""
Lumina Studio - Unified CSS Package
Loads all CSS fragments and exports them as concatenated strings.
"""

import os

_CSS_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_css(name: str) -> str:
    """Load a CSS file from this package directory."""
    path = os.path.join(_CSS_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Ordered list of CSS fragments
_CSS_FILES = [
    "_variables.css",
    "base.css",
    "buttons.css",
    "radio.css",
    "upload.css",
    "hidden.css",
    "crop-modal.css",
    "preview.css",
    "slicer.css",
    "palette.css",
    "header.css",
    "lut-grid.css",
    "utilities.css",
    "colorquery.css",
    "crop-extension.css",
]

CUSTOM_CSS = "\n".join(_load_css(f) for f in _CSS_FILES)
