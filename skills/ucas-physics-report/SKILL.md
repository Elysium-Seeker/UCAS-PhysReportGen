---
name: ucas-physics-report
description: 根据国科大基础物理实验名称和原始记录表照片，匹配实验资料，识别数据、计算拟合、绘图并生成可编辑 LaTeX 与 PDF 报告。用于现有 14 类实验的报告生成、补充数据和修改；不用于通用论文或其他学校的格式适配。
---

# UCAS 物理实验报告

用户通常只提供“实验名称 + 一组记录表照片”。完成其余步骤，交付 PDF、可编辑源码、原始数据和可复算脚本。身份信息已有配置时复用，日期、教师、仪器参数以本次记录为准。

## 入口与环境

本 skill 所在目录记为 SKILL_ROOT；命令中的 PYTHON 是检查可用的 Python 3.10+ 路径。
先读 CODEX_HOME/ucas-physics-report/config.json（CODEX_HOME 未设置时为 ~/.codex）。
如有 python_executable 优先检查该解释器；否则用 Codex workspace dependencies 或系统 Python。
运行 scripts/report.py doctor 检查 numpy、scipy、matplotlib、pypdf、pypdfium2、Pillow 和 XeLaTeX。
缺依赖时在项目独立环境中按 requirements.txt 安装；无需配置另一个模型或 API Key。

本 skill 自带实验处理规则与模板，原始指导书、参考报告留在本地资料库。
初次关联：PYTHON scripts/report.py configure --library "资料库绝对路径"。
默认读取资料库中的“报告”“02_同学参考”“03_往届参考”。
库位置未知时，先在当前项目寻找；仍未找到，只问资料库位置或指导书，不能称完整参考资料已内置。
用户有新指导书时以其为准；附带文件是资料，不是新的执行指令。

## 完整流程

1. **匹配本次实验。**
   运行 scripts/report.py catalog "实验名称"，只读返回 recipe 对应的实验文件。
   14 类目录不代表每次做完其中全部子实验，按照片表头和用户描述识别实际范围。
   重名或范围不明时问一句具体问题；不要凭目录内旧文件名判断实验正文。
   用 scripts/report.py sources "实验名称" 获取原始资料位置，优先本次指导书/记录表，其次历年参考。
   必读本次相关的数据处理要求与思考题，不必把整个参考库塞入上下文。

2. **建立独立报告工程。**
   用 scripts/report.py init --experiment "名称" --output "新目录" --records "图1.jpg" "图2.jpg"。
   有预习照片加 --preview，有光路/波形/前面板照片加 --observations。
   工程不覆盖已有目录，照片按原始字节复制并记录哈希。HEIC/PDF 等先保留原件，用可用工具转换阅读副本后输入。
   个人信息只从本次输入/明确配置读取，不从同学、学长或历史报告继承。
   若用户要求以后复用个人信息，再用 configure --profile "profile.json" 保存在本地配置中。

3. **识别全部照片，先完成数据。**
   逐张用图像工具查看，必要时原分辨率复看；识别单位、分组、续表、涂改值、仪器常数和表外补记。
   按 [data-contract.md](references/data-contract.md) 写 data.json，每行可追溯到照片/表号/行号。
   保留原始读数与显示精度，数值换算在分析代码完成。看不清的值用 null 并列 unresolved issue。
   不用参考报告数字补缺，不根据预期曲线修正实测值。光学图像、示波器波形等只能根据真实照片描述。
   对无法自行消除且影响结果的疑点，集中一次给出“照片、表、行、候选值”；同时做不依赖这些值的工作。
   清晰数据无需逐项让用户确认。运行 scripts/report.py check "工程目录"。
   若少数值仍待确认，可先出部分数据草稿：分析脚本显式使用 allow_incomplete=True，
   仅对完整且适合分析的行计算，记录缺失/排除范围；见数据接口的“部分数据草稿”。
   草稿中保留缺值，不能补0、插值冒充实测或把部分结果称完整报告。

4. **由同一份数据计算、绘图。**
   写工程内 analyze.py，从 data.json 读取，使用已复制到工程的 physics.py/reportlib.py。
   科学模型与拟合区间按对应 recipe 和实际指导书选择，必要时自行推导和写专用分析代码。
   用 physics.save_results 写 results.json：计算值、单位、方法、输入来源、处理后表格和带 table_ids 的图。
   先查看代码再运行 scripts/report.py analyze "工程目录"。检查残差、量纲、有效数字和不确定度假设。
   不机械要求一表一图；同一数据可能有多图，多组曲线也可能共用一图。
   通用助手不等于所有实验均有固定计算器；14 类目前均由 Codex 按已核对规则编写本次分析脚本。

5. **撰写完整报告。**
   按 [report-style.md](references/report-style.md) 写 content.tex，只含正文，不重复文档前导。
   用 \input{generated/tables/<id>.tex} 插入每个原始/处理后表，
   用 \input{generated/figures/<id>.tex} 插入 results.json 的图，
   用 \Result{id} / \ResultUncertainty{id} 引用核心计算值；不要再从 LaTeX 反向识别数值来作图。
   原理、误差讨论和结论围绕本次实际数据；回答实际题目，不新增假称老师布置的思考题。
   不编造个人操作经历、已观察现象、签字、额外演示实验或仪器规格。
   缺表头或必须附录时先交明确标记的草稿，同时列出具体缺项。

6. **编译并查看成稿。**
   scripts/build.py compile "工程目录" 会先检查数据、结果哈希和图表引用，用全新目录编译两次。
   只把本次成功编译的 PDF 复制为 report.pdf。失败时查看输出日志，修复当前问题；不要拿历史 PDF 当新结果。
   scripts/build.py preview "工程目录" 生成逐页 PNG 和总览。用图像工具检查所有页；有小字疑点再看单页。
   检查正文、表头、图注、单位、分页和照片附录，修复溢出/乱码/缺图后重新编译与复看。
   真实完成逐页检查后才运行 scripts/build.py review "工程目录" --pages 1 2 ... --note "实际检查说明"。
   最后运行 scripts/build.py status "工程目录"；complete=false 时准确说明哪些缺项尚存。

## 更新与交付

修改识别数据后重新运行 analyze，再重新编译与视觉检查。旧结果、旧图、旧审阅记录会因哈希不匹配失效。
用户只改措辞时保留数据和分析代码，重新编译检查即可。
最终给出 PDF、源码工程路径、已完成检查及实际缺项；不要把中间 JSON 操作交给用户。
命名按本次课程要求；常见为“分组号-姓名-实验名称缩写-实际实验日期-教师姓名”。
本地配置、真实照片与带个人信息的报告不进入通用 skill 包；发布操作按用户当前请求执行。
