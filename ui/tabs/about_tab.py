# -*- coding: utf-8 -*-
"""
Lumina Studio - About Tab
Extracted from layout.py for modularity.
"""

import gradio as gr

from utils import Stats
from ..image_helpers import _format_bytes

ABOUT_CONTENT = """## 🌟 Lumina Studio v1.6.7

**多材料3D打印色彩系统**

让FDM打印也能拥有精准的色彩还原

---

### 📖 使用流程

1. **生成校准板** → 打印1024色校准网格
2. **提取颜色** → 拍照并提取打印机实际色彩
3. **转换图像** → 将图片转为多层3D模型

---

### 🎨 色彩模式定位点顺序

| 模式 | 左上 | 右上 | 右下 | 左下 |
|------|------|------|------|------|
| **RYBW** | ⬜ 白色 | 🟥 红色 | 🟦 蓝色 | 🟨 黄色 |
| **CMYW** | ⬜ 白色 | 🔵 青色 | 🟣 品红 | 🟨 黄色 |

---

### 🔬 技术原理

- **Beer-Lambert 光学混色**
- **KD-Tree 色彩匹配**
- **RLE 几何生成**
- **K-Means 色彩量化**

---

### 📝 v1.6.7 更新日志

#### 🐛 Bug 修复
- 修复 6色 RYBWGK 用户 3MF 文件中 AMS 耐材颜色分配错误的问题（原来固定使用 CMYWGK 预览色，现改为从 LUT 纯色标定条目自动推导）
- 修复全屏预览左上角新增「✕ 返回」按钮，方便退出全屏

---

### 📝 v1.5.8 更新日志

#### 🧹 代码清理
- 移除融合LUT功能（简化用户体验）
- 保留BW黑白模式功能
- 清理.npz文件格式支持

---

### 📝 v1.5.7 更新日志

#### 🔧 8色模式叠色效果修复
- **核心修复**：修复8色模式图像转换时堆叠顺序错误导致的叠色效果不正确
- **数据一致性**：确保8色模式ref_stacks格式与4色、6色保持一致 [顶...底]
- **观赏面修复**：修复观赏面(Z=0)和背面颠倒的问题

#### 🎨 完整8色图像转换支持
- **UI增强**：图像转换TAB新增8色模式支持
- **自动检测**：8色LUT自动检测(2600-2800色范围)
- **完整工作流**：校准板生成 → 颜色提取 → 图像转换

#### 🐳 Docker支持
- **容器化部署**：添加Dockerfile支持
- **简化安装**：无需手动配置系统依赖
- **跨平台**：统一的部署体验

---

### 📝 v1.5.5 更新日志 (历史)

#### 🎨 8色校准版算法优化
- **算法升级**：8色校准版采用与6色一致的智能筛选算法
- **黑色优化**：Black TD从0.2mm调整至0.6mm，实现自然筛选
- **质量提升**：移除强制黑色约束，改用RGB距离>8的贪心算法
- **数据修复**：修正材料ID映射，确保与config.py完全一致
- **统计修正**：修复黑色统计代码，使用正确的材料ID

---

### 📝 v1.5.4 更新日志 (历史)

#### 🐛 矢量模式改进
- 改进矢量模式的布尔运算逻辑
- 优化SVG颜色顺序处理
- 添加微Z偏移以保持细节独立性
- 增强小特征保护机制

---

### 📝 v1.5.0 更新日志

#### 🎨 代码标准化
- **注释统一为英文**：所有代码注释翻译为英文，提升国际化协作能力
- **文档规范化**：统一使用 Google-style docstrings
- **代码清理**：移除冗余注释，保留关键算法说明

---

### 📝 v1.4.1 更新日志

#### 🚀 建模模式整合
- **高保真模式取代矢量和版画模式**：统一为两种模式（高保真/像素艺术）
- **语言切换功能**：点击右上角按钮即可切换中英文界面

#### 📝 v1.4 更新日志

#### 🚀 核心功能

- ✅ **高保真模式** - RLE算法，无缝拼接，水密模型（10 px/mm）
- ✅ **像素艺术模式** - 经典方块美学，像素艺术风格

#### 🔧 架构重构

- 合并Vector和Woodblock为统一的High-Fidelity模式
- RLE（Run-Length Encoding）几何生成引擎
- 零间隙、完美边缘对齐（shrink=0.0）
- 性能优化：支持100k+面片即时生成

#### 🎨 色彩量化架构

- K-Means聚类（8-256色可调，默认64色）
- "先聚类，后匹配"（速度提升1000×）
- 双边滤波 + 中值滤波（消除碎片化区域）

---

### 🚧 开发路线图

- [✅] 4色基础模式
- [✅] 两种建模模式（高保真/像素艺术）
- [✅] RLE几何引擎
- [✅] 钥匙扣挂孔
- [🚧] 漫画模式（Ben-Day dots模拟）
- [ ] 6色扩展模式
- [ ] 8色专业模式

---

### 📄 许可证

**GNU GPL v3.0** 开源协议

GPL 协议允许并鼓励商业使用。我们特别支持大家通过劳动获取收益，你无需获得额外授权即可：

使用本软件生成模型或辅助生产；

销售物理打印成品（如挂件、浮雕、3D 打印件等）；

在夜市、市集、展会或个人网店销售。

---

### 🙏 致谢

特别感谢：
- **HueForge** - 在FDM打印中开创光学混色技术
- **AutoForge** - 让多色工作流民主化
- **3D打印社区** - 持续创新

---

<div style="text-align:center; color:#888; margin-top:20px;">
    Made with ❤️ by Lumina Studio Contributors<br>
    v1.6.7 | 2026
</div>
"""


def create_about_tab_content() -> dict:
    """Build About tab content. Returns component dict."""
    components = {}

    # Settings section
    components['md_settings_title'] = gr.Markdown('## ⚙️ 设置')
    cache_size = Stats.get_cache_size()
    cache_size_str = _format_bytes(cache_size)
    components['md_cache_size'] = gr.Markdown(
        f'📦 缓存大小: {cache_size_str}'
    )
    with gr.Row():
        components['btn_clear_cache'] = gr.Button(
            '🗑️ 清空缓存',
            variant="secondary",
            size="sm"
        )
        components['btn_reset_counters'] = gr.Button(
            '🔢 使用计数归零',
            variant="secondary",
            size="sm"
        )

    output_size = Stats.get_output_size()
    output_size_str = _format_bytes(output_size)
    components['md_output_size'] = gr.Markdown(
        f'📦 输出大小: {output_size_str}'
    )
    components['btn_clear_output'] = gr.Button(
        '🗑️ 清空输出',
        variant="secondary",
        size="sm"
    )

    components['md_settings_status'] = gr.Markdown("")

    # About page content
    components['md_about_content'] = gr.Markdown(ABOUT_CONTENT)

    return components
