大物实验报告生成器 v2.0
==================================

这是一个自动化生成物理实验报告的工具，支持 AI 数据处理、自动画图和 PDF 报告生成。

### 🚀 快速开始

1. **双击运行 `run.bat`**
   - 脚本会自动检查环境、安装依赖并启动程序
   - 启动后浏览器会自动打开 http://localhost:5000

2. **配置 API**
   - 点击界面左下角的 "⚙️ API 设置"
   - **API URL**: 输入服务商提供的地址 (例如: `https://api.openai.com/v1/chat/completions`)
   - **API Key**: 输入你的密钥 (`sk-...`)
   - **模型**: 输入想使用的模型名称 (默认 `gpt-4o`，建议使用支持视觉的模型以便识别图片)

3. **开始使用**
   - 填写实验信息
   - 上传数据记录表照片（必须）和实验指导书 PDF（推荐）
   - 点击生成报告

### 📦 系统要求

1. **Python**
   - 需要安装 Python 3.8 或更高版本
   - 确保安装时勾选了 "Add Python to PATH"

2. **XeLaTeX (生成 PDF 必需)**
   - 推荐安装 [MiKTeX](https://miktex.org/download) 或 [TeX Live](https://www.tug.org/texlive/)
   - 如果未安装，仍然可以生成 LaTeX 源码，但无法预览 PDF

### 📂 主要文件说明

- `run.bat`: 一键启动脚本
- `app.py`: 主程序代码
- `requirements.txt`: 依赖列表
- `latex_template/`: 包含 LaTeX 模板和字体文件
- `output/`: 生成的报告和历史记录保存在这里
- `uploads/`: 上传的临时文件
- `config.py`: 配置文件

### ⚠️ 常见问题

Q: 启动时提示 "未检测到 Python"？
A: 请去 python.org 下载并安装 Python，记得勾选 "Add to PATH"。

Q: 报告生成时提示 "编译失败"？
A: 请确保已安装 MiKTeX 或 TeX Live，并且 `xelatex` 命令可以在命令行中使用。

Q: 生成图表中文乱码？
A: 项目已内置中文字体，如果仍有问题，请检查 logs。
