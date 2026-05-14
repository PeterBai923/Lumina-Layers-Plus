# Lumina Studio

基于物理校准的多材料FDM色彩系统

> **重构说明**: 本项目基于 [Lumina-Layers V1](https://github.com/lumina-layer-studio/Lumina-Layers) 进行模块化重构和性能优化。

[查看完整更新日志 →](CHANGELOG_CN.md)

---

## 更新日志

### v1.7.0 (2026-05-14)

- **新功能**: 变量层高变换、K-Means 种子配置、统一日志模块
- **性能优化**: 多模块 GPU 加速、向量化网格生成、增强聚类空间特征
- **重构**: 模块化架构重组（color/image/lut/mesh/preview/utils）、CUDA 支持集成
- **精简**: 移除掐丝珐琅、透明镀层、分段 GLB 预览等功能

### v1.6.8 (2026-05-06)

- **新功能**: 背板层高独立设置、设置自动保存
- **性能优化**: 网格模板缓存机制
- **修复**: 结构模式大小写判断、单面预览镜像显示
- **重构**: UI 组件 HTML 化、模块拆分、移除国际化模块

### v1.6.7 (2026-03-29)

- **关键修复**: 6色 RYBWGK LUT 的 3MF 文件 AMS 耗材颜色分配错误
- **改进**: 3MF 预览颜色现从 LUT 自身纯色标定条目推导，适用于任意品牌耗材

完整版本历史请查看 [CHANGELOG_CN.md](CHANGELOG_CN.md) / [CHANGELOG.md](CHANGELOG.md)。

---

## 安装

### 克隆仓库

```bash
git clone https://github.com/MOVIBALE/Lumina-Layers.git
cd Lumina-Layers
```

### 选项 1：Docker (推荐)

```bash
# 构建镜像
docker build -t lumina-layers .

# 运行容器
docker run -p 7860:7860 lumina-layers
```

在浏览器中打开 `http://localhost:7860`。

### 选项 2：本地安装

```bash
pip install -r requirements.txt
```

---

## 使用指南

### 快速启动

```bash
python main.py
```

---

### 步骤1：生成校准板

1. 打开**📐 校准板**标签
2. 选择色彩模式（4色 RYBW/CMYW、6色、8色、黑白）
3. 调整色块大小（默认：5mm）和间隙（默认：0.82mm）
4. 点击**生成**并下载`.3mf`文件

**打印设置**: 层高 0.08mm（色彩层），耗材槽位匹配所选模式。

| 模式     | 总颜色数 | 耗材槽位                                     |
| -------- | -------- | -------------------------------------------- |
| 4色 RYBW | 1024     | 白色、红色、黄色、蓝色                       |
| 4色 CMYW | 1024     | 白色、青色、品红、黄色                       |
| 6色      | 1296     | 白色、青色、品红、黄色、柠檬绿、黑色         |
| 8色      | 2738     | 白色、青色、品红、黄色、柠檬绿、黑色（+2种） |
| 黑白     | 32       | 黑色、白色                                   |

---

### 步骤2：提取颜色

1. 打印校准板并拍照（面朝上，均匀光照）
2. 打开**🎨 颜色提取器**标签，选择与校准板相同的色彩模式
3. 上传照片，按顺序点击四个角落色块：

| 模式     | 左上角  | 右上角 | 右下角 | 左下角 |
| -------- | ------- | ------ | ------ | ------ |
| 4色 RYBW | ⬜ 白色 | 红色   | 蓝色   | 黄色   |
| 4色 CMYW | ⬜ 白色 | 青色   | 品红   | 黄色   |
| 6色      | ⬜ 白色 | 青色   | 品红   | 黄色   |
| 8色      | ⬜ 白色 | 黄色   | 黑色   | 青色   |
| 黑白     | ⬜ 白色 | 黑色   | 黑色   | 黑色   |

4. 调整校正滑块，点击**提取**
5. **仅8色模式**：提取第1页 → 手动修正 → 提取第2页 → 合并为最终LUT
6. 下载`.npy` LUT文件

---

### 步骤3：转换图像

1. 打开**💎 图像转换器**标签
2. 上传`.npy` LUT文件和图像，选择与LUT相同的色彩模式
3. **选择建模模式**：
    - **高保真（平滑）** - 推荐用于标志、照片、肖像
    - **像素艺术（方块）** - 推荐用于像素艺术和8bit风格
4. 调整**色彩细节**滑块（8-256色，默认64）
5. 点击**👁️ 生成预览**查看结果
6. （可选）添加钥匙扣挂孔：点击2D预览图位置 → 勾选"启用挂孔" → 调整尺寸
7. 选择结构类型（双面/单面），点击**🚀 生成3MF**
8. 在交互式3D查看器中预览，下载`.3mf`文件

---

## 致谢

感谢 **HueForge**、**AutoForge** 开创 FDM 光学混色技术。

Lumina Studio 采用"穷举法"路线：打印物理校准板 → 拍照提取真实 RGB 数据 → 建立 LUT → 最近邻匹配，避免了传统工具依赖理论参数的问题。

本项目以开源、非盈利定位持续开发，支持个人创作者通过劳动获取收益。

感谢以下开源项目：
- **[ChromaStack](https://github.com/borealis-zhe/ChromaStack)** - 多色层叠模型生成器
- **[LD_ColorLayering](https://github.com/Luban-Daddy/LD_ColorLayering)** - H5网页应用，支持多种颜色模式
- **[ChromaPrint3D](https://github.com/Neroued/ChromaPrint3D)** - 支持Bambu Studio预设自动写入

---

## 贡献者

<a href="https://github.com/MOVIBALE/Lumina-Layers/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=MOVIBALE/Lumina-Layers" />
</a>

由所有贡献者精心制作！

---

⭐ 如果觉得有用，请给个Star！
