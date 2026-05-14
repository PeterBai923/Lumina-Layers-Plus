# Lumina Studio

Physics-Based Multi-Material FDM Color System

> **Fork Note**: This project is a refactored and optimized version of the [original Lumina-Layers](https://github.com/lumina-layer-studio/Lumina-Layers).

[View Full Changelog →](CHANGELOG.md)

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

## Acknowledgments

Special thanks to **HueForge** and **AutoForge** for pioneering optical color mixing in FDM printing.

**Lumina Studio employs an exhaustive search approach**: Print 1024-color physical calibration board → Photograph and extract actual RGB data → Build LUT → Nearest-neighbor matching.

Thanks to these open-source projects:
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
