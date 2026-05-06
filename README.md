<p align="center">
  <img src="logo.png" width="128" alt="Lumina Studio Logo">
</p>

<h1 align="center">Lumina Studio</h1>

<p align="center">
  基于物理校准的多材料FDM色彩系统
</p>

<p align="center">
  <a href="https://github.com/MOVIBALE/Lumina-Layers/stargazers">
    <img src="https://img.shields.io/github/stars/MOVIBALE/Lumina-Layers?style=social" alt="Stars">
  </a>
  &nbsp;
  <a href="https://github.com/MOVIBALE/Lumina-Layers/releases/latest">
    <img src="https://img.shields.io/github/v/release/MOVIBALE/Lumina-Layers?label=最新版本&amp;include_prereleases" alt="Release">
  </a>
  &nbsp;
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/协议-GPL%20v3.0-blue.svg" alt="License">
  </a>
</p>

<p align="center">
  <a href="README_EN.md">📖 English Version / 英文文档</a>
</p>

---

<p align="center">
  <a href="https://github.com/MOVIBALE/Lumina-Layers"><img src="https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github" alt="GitHub"></a>
  <a href="https://discord.gg/57whRe3C8G"><img src="https://img.shields.io/badge/Discord-5865F2?style=flat-square&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://b23.tv/CCxxiKC"><img src="https://img.shields.io/badge/Bilibili-00A1D6?style=flat-square&logo=bilibili&logoColor=white" alt="Bilibili"></a>
  <a href="https://qm.qq.com/q/vocxOMTnj2"><img src="https://img.shields.io/badge/QQ群-1065401448-EB1923?style=flat-square&logo=tencentqq&logoColor=white" alt="QQ Group"></a>
</p>

---

## 项目状态

**当前版本**: v1.6.8 | **协议**: GNU GPL v3.0 | **性质**: 非营利开源社区项目

[查看完整更新日志 →](CHANGELOG_CN.md)

---

## 灵感来源与技术声明

### 致谢先驱者

- **HueForge** - 首个将光学混色引入FDM社区的工具
- **AutoForge** - 自动化色彩匹配工作流
- **CMYK印刷理论** - 经典减色模型在3D打印中的逐层透射改编

### 技术区别

传统工具依赖理论计算（如TD1/TD0透射距离值），但这些参数极易因耗材品牌、打印机型号、环境湿度等因素而失效。

**Lumina Studio采用"穷举法"路线**：打印1024色物理校准板 → 拍照提取真实RGB数据 → 建立查找表（LUT）→ 用最近邻算法匹配。

### Prior Art 声明

FDM多层叠色核心原理已于2022-2023年由HueForge等软件公开披露，属于**现有技术**。该技术原理已进入公共领域，通常**不具备专利性**。

本项目以开源、互助、非盈利性定位持续开发，不会进行捆绑销售或将功能付费化。赞助行为不构成商业绑定，不影响技术决策或开源协议。

**特别感谢HueForge团队对开源的支持和理解！**

---

Lumina Studio v1.5.4整合三大模块，统一界面：

### 📐 模块1：校准板生成器

生成精密校准板，物理测试耗材混色。

- **多种色彩系统**：4色（CMYW/RYBW，1024色）、6色（1296色）、8色（2738色）、黑白模式（32级灰度）
- **智能校准工作流**：单板全排列（4/6色）、双页合并（8色）
- **面朝下优化**：观察面直接接触打印平台，表面光滑
- **实心背板**：自动生成不透明背板，确保色彩一致性和结构强度

### 🎨 模块2：颜色提取器

数字化你打印机的物理现实。

- **计算机视觉**：透视变换+镜头畸变校正自动对齐网格
- **多模式支持**：4色/6色/8色/黑白模式
- **模式感知对齐**：角点标记遵循所选模式的正确颜色序列
- **数字孪生**：从打印品提取RGB值，生成.npy LUT文件
- **人工干预**：交互式探针工具，手动验证/修正特定色块读数

### 💎 模块3：图像转换器

使用校准数据将图像转换为可打印3D模型。

- **KD树色彩匹配**：将图像像素映射到LUT中的实际可打印颜色
- **实时3D预览**：交互式WebGL预览，显示真实匹配色彩
- **钥匙扣挂孔生成器**：自动添加功能性挂孔，智能颜色检测
- **结构选项**：双面（钥匙扣）或单面（浮雕）模式
- **智能背景移除**：自动透明度检测，可调容差
- **正确的3MF命名**：对象按颜色命名，便于切片器识别

---

## 更新日志

完整版本历史请查看 [CHANGELOG_CN.md](CHANGELOG_CN.md) / [CHANGELOG.md](CHANGELOG.md)。

---

## 开发路线图

| 阶段                    | 状态      | 目标                         |
| ----------------------- | --------- | ---------------------------- |
| 阶段1：基础架构         | ✅ 完成   | 像素艺术与照片级图形         |
| 阶段2：漫画模式         | ✅ 完成   | 漫画面板、墨画、高对比度插图 |
| 阶段3：动态调色板引擎   | ✅ 完成   | 自适应色彩系统               |
| 阶段4：扩展色彩模式     | ✅ 完成   | 专业多材料打印（6/8色）      |
| 拼豆（Perler bead）模式 | 🚧 进行中 | -                            |

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

**打印设置**：

- 层高：0.08mm（色彩层），背板可用0.2mm
- 耗材槽位必须匹配所选模式

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

## 技术栈

| 组件     | 技术                        |
| -------- | --------------------------- |
| 核心逻辑 | Python（NumPy用于体素操作） |
| 几何引擎 | Trimesh（网格生成与导出）   |
| UI框架   | Gradio 4.0+                 |
| 视觉栈   | OpenCV（透视与颜色提取）    |
| 色彩匹配 | SciPy KDTree                |
| 3D预览   | Gradio Model3D（GLB格式）   |

---

## 工作原理

### 为什么需要校准

理论TD值假设耗材染料浓度一致、喷嘴温度相同、层间粘合均匀。实际上，这些因素在不同品牌/批次、打印机型号、环境条件下存在显著差异。

基于LUT的方法通过测量实际打印颜色并在RGB空间中通过最近邻搜索匹配来解决这个问题。

---

## 生态开放与许可协议

### 关于 .npy 校准文件

所有校准预设（`.npy`文件）**完全免费开放**：

- **拒绝供应商锁定**：永远不会强迫用户使用特定耗材品牌
- **社区共建**：欢迎所有用户、组织、耗材厂商提交PR，同步校准预设

**数据开放 = 技术民主化**

### 核心协议：GNU GPL v3.0

- ✅ **开源与自由**：你可以自由地运行、研究、修改和分发本软件
- 🔄 **强传染性 (Copyleft)**：修改并分发时必须在 GPL v3.0 下公开源代码
- ❌ **禁止闭源**：严禁将本软件或其衍生作品闭源打包销售

**商业使用与"小摊主"支持声明**：本项目支持并鼓励个人创作者、小摊主及小微企业通过劳动获取收益。你可以自由地使用本软件生成模型并销售物理打印成品，无需额外授权。

---

## 致谢

特别感谢 **HueForge**、**AutoForge** 开创FDM光学混色技术，以及以下开源项目：

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
