# UCAS-PhysReportGen：Codex 实验报告 Skill

新版入口是 **实验名称 + 原始记录表照片**。在 Codex 中完成资料匹配、读图转录、数据计算、
拟合绘图、报告写作、XeLaTeX 编译和逐页检查，交付 PDF 与可复算的源码工程。

当前版本为 **Skill v0.1.0**，可从 [GitHub Releases](https://github.com/Elysium-Seeker/UCAS-PhysReportGen/releases/tag/skill-v0.1.0) 下载独立安装包。
原有 Flask 网页程序保留；旧用法见 [历史网页版本说明](docs/legacy-webapp.md)。

## 使用方式

安装后在 Codex 中说：

> 使用 $ucas-physics-report，生成光电探测实验报告。这里是记录表照片。

也可以直接说“帮我根据这些照片写国科大驻波实验报告”，让 Codex 自动选择 skill。
默认输出 PDF、LaTeX 源码、数据 JSON、计算脚本和原始照片附录。
无需另建模型后端或提供 API Key，读图和撰写由当前 Codex 完成。

首次关联你的本地资料库；姓名等信息可在明确需要复用时单独保存。
日常输入清晰时继续生成；少数数字无法识别时集中询问，并可先生成保留缺值的草稿。
草稿会明确标记，缺值不补零，不用往届报告数据补齐。

## 覆盖范围

14 类实验均有独立的范围识别、公式/单位、图表和误差处理规则：

| 类别 | 主要项目 |
|---|---|
| 粘滞与密立根油滴 | 落球粘度、温度关系、油滴电荷 |
| 电子束 | 弗兰克–赫兹、电/磁偏转、聚焦与荷质比 |
| 磁场测量 | 霍尔换向、线圈轴向分布 |
| 磁滞回线 | 动态/准静态回线、材料对比 |
| 驻波 | 弦上驻波、空气/水中声速 |
| 气垫导轨 | 弹簧振子、机械能、瞬时速度 |
| 杨氏模量 | 拉伸、光杠杆、霍尔弯曲、动态悬挂 |
| 分光仪器 | 三棱镜、光栅、光谱 |
| 光路偏振 | 马吕斯定律、光纤、M-Z 干涉 |
| 傅里叶光学 | 阿贝成像、4F、空间滤波、假彩色 |
| RLC | 串并联谐振、相频/幅频、暂态 |
| 虚拟仪器 | LabVIEW 实验说明、伏安测量 |
| 温度测量 | 热电偶、电桥、热敏电阻、热导率 |
| 光电探测 | 硅光电池六项特性 |

这是 **实验规则覆盖范围**。专用分析脚本由 Codex 依据本次照片和讲义生成，
并不表示每个子实验都有一个已经验证的固定计算器。
真实参考报告、签字照片与个人信息保留在本地库，不打包进公共 skill。
本次验证记录见 [VALIDATION.md](docs/VALIDATION.md)。

## 安装

要求 Python 3.10+；生成 PDF 需要可用的 XeLaTeX（TeX Live 或 MiKTeX），
模板使用 TeX 自带的 Fandol 中文字体。推荐从仓库安装，Windows PowerShell 示例：

~~~powershell
git clone https://github.com/Elysium-Seeker/UCAS-PhysReportGen.git
Set-Location UCAS-PhysReportGen
python -m venv .venv-skill
.\.venv-skill\Scripts\python.exe -m pip install -r skills/ucas-physics-report/requirements.txt
.\.venv-skill\Scripts\python.exe -X utf8 scripts/install_skill.py
.\.venv-skill\Scripts\python.exe -X utf8 skills/ucas-physics-report/scripts/report.py configure --library "你的参考资料库路径"
~~~

安装器复制 skill 到 CODEX_HOME/skills/ucas-physics-report，默认是 ~/.codex/skills。
更新已有安装时先保存备份。关联库和个人设置位于 CODEX_HOME/ucas-physics-report/config.json。
配置会记录当前 Python 解释器，后续使用前仍会检查环境。

也可以只下载 Release 中的 `ucas-physics-report-0.1.0.zip` 和对应 `.sha256` 校验文件。
ZIP 内只有 `ucas-physics-report/`：将此目录放到 `CODEX_HOME/skills/`（默认 `~/.codex/skills/`），
在准备使用的 Python 环境中安装该目录的 `requirements.txt`，再运行该目录下
`scripts/report.py configure --library "你的参考资料库路径"`。
更新现有安装时推荐使用上面的仓库安装器，它会自动备份旧版。

本地库沿用本项目整理后的布局：

~~~text
资料库/
  报告/01_粘滞与密立根油滴/...
  02_同学参考/...
  03_往届参考/...
  04_模板与工具/...
~~~

只有 skill 包时仍有实验规则和通用模板；完整原始讲义/参考库需在本地提供。
新版直接支持 PNG/JPEG 照片输入；其他格式先保留原件并转换阅读副本。
纯 CSV/Excel 输入的来源接口尚未扩展，不将其伪装成照片数据。

## 开发与验证

- [技能入口](skills/ucas-physics-report/SKILL.md)
- [数据接口与部分数据草稿](skills/ucas-physics-report/references/data-contract.md)
- [实验目录](skills/ucas-physics-report/references/experiments.json)
- [报告版式与证据要求](skills/ucas-physics-report/references/report-style.md)

~~~powershell
.\.venv-skill\Scripts\python.exe -X utf8 -m unittest discover -s tests_skill -v
.\.venv-skill\Scripts\python.exe -X utf8 scripts/package_skill.py
~~~

tests_skill 与历史网页程序的 tests 分开。测试包括读数来源、缺值、计算助手、
过期数据/图像、编译失败不复用旧 PDF，以及源码更改后视觉审阅失效。
[GitHub Actions](https://github.com/Elysium-Seeker/UCAS-PhysReportGen/actions/workflows/skill-checks.yml)
在 Windows 和 Linux 上运行这些检查与打包检查。
真实用户工程放在忽略目录或仓库外；不要将其加入通用发布包。

新模板参考 Shing-Ho Lin 与 Jun-Xiong Ji 的课程 LaTeX 模板表头，已注明来源。
它是本项目的轻量适配版，不代表新的课程官方认证。
