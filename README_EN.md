<p align="center">
  <img src="logo.png" width="128" alt="Lumina Studio Logo">
</p>

<h1 align="center">Lumina Studio</h1>

<p align="center">
  Physics-Based Multi-Material FDM Color System
</p>

<p align="center">
  <a href="https://github.com/MOVIBALE/Lumina-Layers/stargazers">
    <img src="https://img.shields.io/github/stars/MOVIBALE/Lumina-Layers?style=social" alt="Stars">
  </a>
  &nbsp;
  <a href="https://github.com/MOVIBALE/Lumina-Layers/releases/latest">
    <img src="https://img.shields.io/github/v/release/MOVIBALE/Lumina-Layers?label=Latest%20Release&amp;include_prereleases" alt="Release">
  </a>
  &nbsp;
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-GPL%20v3.0-blue.svg" alt="License">
  </a>
</p>

<p align="center">
  <a href="README.md">📖 中文文档 / Chinese Version</a>
</p>

---

<p align="center">
  <a href="https://github.com/MOVIBALE/Lumina-Layers"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github" alt="GitHub"></a>
  <a href="https://discord.gg/57whRe3C8G"><img src="https://img.shields.io/badge/Discord-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://b23.tv/CCxxiKC"><img src="https://img.shields.io/badge/Bilibili-00A1D6?style=flat-square&logo=bilibili&logoColor=white" alt="Bilibili"></a>
  <a href="https://qm.qq.com/q/vocxOMTnj2"><img src="https://img.shields.io/badge/QQ%20Group-1065401448-EB1923?style=flat-square&logo=tencentqq&logoColor=white" alt="QQ Group"></a>
</p>

---

## Project Status

**Current Version**: v1.6.8 | **License**: GNU GPL v3.0 | **Nature**: Non-profit open-source community project

[View Full Changelog →](CHANGELOG.md)

---

## Inspiration & Technical Statement

### Acknowledgements to Pioneers

- **HueForge** - First tool to introduce optical color mixing to the FDM community
- **AutoForge** - Automated color matching workflow
- **CMYK Printing Theory** - Layer-by-layer transmission adaptation of subtractive color model

### Technical Differentiation

Traditional tools rely on theoretical calculations (TD1/TD0 transmission values), but these parameters fail easily due to filament brands, printer models, and environmental factors.

**Lumina Studio employs an exhaustive search approach**: Print 1024-color physical calibration board → Photograph and extract actual RGB data → Build LUT → Nearest-neighbor matching.

### Prior Art Declaration

FDM multilayer overlay principles were publicly disclosed by HueForge et al. (2022-2023) and constitute **prior art**. This technology has entered the public domain and is generally **not patentable**.

This project maintains an open-source, collaborative, non-profit position. No bundled sales or paid features. Sponsorship does not constitute commercial binding or influence technical decisions.

**Special thanks to the HueForge team for their support of open source!**

---

Lumina Studio v1.5.4 integrates three major modules into a unified interface:

### 📐 Module 1: Calibration Generator

Generates precision calibration boards to physically test filament mixing.

- **Multiple Color Systems**: 4-Color (CMYW/RYBW, 1024 colors), 6-Color (1296 colors), 8-Color (2738 colors), BW Mode (32 grayscale levels)
- **Smart Calibration Workflow**: Single-board full permutation (4/6-Color), two-page merge (8-Color)
- **Face-Down Optimization**: Viewing surface prints directly on build plate for smooth finish
- **Solid Backing**: Automatically generates opaque backing for color consistency and structural rigidity

### 🎨 Module 2: Color Extractor

Digitizes the physical reality of your printer.

- **Computer Vision**: Perspective warp + lens distortion correction for automatic grid alignment
- **Multi-Mode Support**: 4-Color/6-Color/8-Color/BW modes
- **Mode-Aware Alignment**: Corner markers follow correct color sequence based on selected mode
- **Digital Twin**: Extracts RGB values from prints and generates .npy LUT files
- **Human-in-the-Loop**: Interactive probe tools for manual verification/correction

### 💎 Module 3: Image Converter

Converts images into printable 3D models using calibrated data.

- **KD-Tree Color Matching**: Maps image pixels to actual printable colors in your LUT
- **Live 3D Preview**: Interactive WebGL preview with true matched colors
- **Keychain Loop Generator**: Automatically adds functional hanging loops with smart color detection
- **Structure Options**: Double-sided (keychain) or Single-sided (relief) modes
- **Smart Background Removal**: Automatic transparency detection with adjustable tolerance
- **Correct 3MF Naming**: Objects named by color for easy slicer identification

---

## Changelog

For detailed version history, see [CHANGELOG.md](CHANGELOG.md) / [CHANGELOG_CN.md](CHANGELOG_CN.md).

---

## Development Roadmap

| Phase | Status | Target |
|-------|--------|--------|
| Phase 1: Foundation | ✅ Complete | Pixel Art & Photographic Graphics |
| Phase 2: Manga Mode | ✅ Complete | Manga panels, Ink drawings, High-contrast illustrations |
| Phase 3: Dynamic Palette Engine | ✅ Complete | Adaptive color systems |
| Phase 4: Extended Color Modes | ✅ Complete | Professional multi-material printing (6/8-Color) |
| Perler Bead Mode | 🚧 In Progress | - |

---

## Installation

### Clone the repository

```bash
git clone https://github.com/MOVIBALE/Lumina-Layers.git
cd Lumina-Layers
```

### Option 1: Docker (Recommended)

```bash
# Build the image
docker build -t lumina-layers .

# Run the container
docker run -p 7860:7860 lumina-layers
```

Open your browser to `http://localhost:7860`.

### Option 2: Local Installation

```bash
pip install -r requirements.txt
```

---

## Usage Guide

### Quick Start

```bash
python main.py
```

---

### Step 1: Generate Calibration Board

1. Open the **📐 Calibration** tab
2. Select color mode (4-Color RYBW/CMYW, 6-Color, 8-Color, BW)
3. Adjust block size (default: 5mm) and gap (default: 0.82mm)
4. Click **Generate** and download the `.3mf` file(s)

**Print Settings**:

- Layer height: 0.08mm (color layers), backing can use 0.2mm
- Filament slots must match your selected mode

| Mode | Total Colors | Filament Slots |
|------|--------------|----------------|
| 4-Color RYBW | 1024 | White, Red, Yellow, Blue |
| 4-Color CMYW | 1024 | White, Cyan, Magenta, Yellow |
| 6-Color | 1296 | White, Cyan, Magenta, Yellow, Lime, Black |
| 8-Color | 2738 | White, Cyan, Magenta, Yellow, Lime, Black (+ 2 more) |
| BW | 32 | Black, White |

---

### Step 2: Extract Colors

1. Print the calibration board and photograph it (face-up, even lighting)
2. Open the **🎨 Color Extractor** tab, select the same color mode as your board
3. Upload photo, click the four corner blocks in order:

| Mode | Top-Left | Top-Right | Bottom-Right | Bottom-Left |
|------|----------|-----------|--------------|-------------|
| 4-Color RYBW | ⬜ White | Red | Blue | Yellow |
| 4-Color CMYW | ⬜ White | Cyan | Magenta | Yellow |
| 6-Color | ⬜ White | Cyan | Magenta | Yellow |
| 8-Color | ⬜ White | Yellow | Black | Cyan |
| BW | ⬜ White | Black | Black | Black |

4. Adjust correction sliders, click **Extract**
5. **For 8-Color Mode Only**: Extract Page 1 → Manual corrections → Extract Page 2 → Merge into final LUT
6. Download the `.npy` LUT file

---

### Step 3: Convert Image

1. Open the **💎 Image Converter** tab
2. Upload your `.npy` LUT file and image, select the same color mode as your LUT
3. **Choose Modeling Mode**:
   - **High-Fidelity (Smooth)** - Recommended for logos, photos, portraits
   - **Pixel Art (Blocky)** - Recommended for pixel art and 8-bit style
4. Adjust **Color Detail** slider (8-256 colors, default 64)
5. Click **👁️ Generate Preview** to see the result
6. (Optional) Add Keychain Loop: Click on 2D preview → Enable "启用挂孔" → Adjust dimensions
7. Choose structure type (Double/Single-sided), click **🚀 Generate 3MF**
8. Preview in interactive 3D viewer, download `.3mf` file

---

## Technical Stack

| Component | Technology |
|-----------|------------|
| Core Logic | Python (NumPy for voxel manipulation) |
| Geometry Engine | Trimesh (Mesh generation & Export) |
| UI Framework | Gradio 4.0+ |
| Vision Stack | OpenCV (Perspective & Color Extraction) |
| Color Matching | SciPy KDTree |
| 3D Preview | Gradio Model3D (GLB format) |

---

## How It Works

### Why Calibration Matters

Theoretical TD values assume consistent filament dye concentration, identical nozzle temperatures, and uniform layer adhesion. In reality, these vary significantly between brands/batches, printer models, and environmental conditions.

The LUT-based approach solves this by measuring actual printed colors and matching via nearest-neighbor search in RGB space.

---

## Open Ecosystem & License

### About .npy Calibration Files

All calibration presets (`.npy` files) are **completely free and open**:

- **No Vendor Lock-in**: We will never force users to specific filament brands
- **Community Collaboration**: Welcome all users, organizations, and manufacturers to submit PRs

**Open Data = Democratization of Technology**

### Core License: GNU GPL v3.0

- ✅ **Open & Free**: You are free to run, study, modify, and distribute this software
- 🔄 **Copyleft**: If you modify and distribute, you must release source code under GPL v3.0
- ❌ **No Proprietary Derivatives**: Selling closed-source versions is strictly prohibited

**Commercial Use & "Street Vendor" Support Statement**: GPL permits commercial use. We specifically support individual creators, street vendors, and small businesses to earn a living through their craft. You may freely use this software to generate models and sell physical prints without additional permission.

**Go set up your stall and make a living!**

---

## Acknowledgments

Special thanks to **HueForge** and **AutoForge** for pioneering optical color mixing in FDM printing, and to these open-source projects:

- **[ChromaStack](https://github.com/borealis-zhe/ChromaStack)** - Multi-color layer stacking model generator
- **[LD_ColorLayering](https://github.com/Luban-Daddy/LD_ColorLayering)** - H5 web app supporting multiple color modes
- **[ChromaPrint3D](https://github.com/Neroued/ChromaPrint3D)** - Bambu Studio preset auto-injection support

---

## Contributors

<a href="https://github.com/MOVIBALE/Lumina-Layers/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MOVIBALE/Lumina-Layers" />
</a>

Made with ❤️ by all our contributors!

---

⭐ Star this repo if you find it useful!
