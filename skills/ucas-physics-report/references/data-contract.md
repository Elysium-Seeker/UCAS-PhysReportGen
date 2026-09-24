# 数据与计算结果接口

适用脚本：scripts/report.py、scripts/build.py；示例中的数据仅展示格式。
init 会生成 inputs.json、data.json、sources.json，并复制 physics.py/reportlib.py。
在工程中写 analyze.py 和 content.tex，其余 generated 文件由 build.py 创建。
工程文件可留在用户指定位置，资料库中的原始报告不改写。

## data.json

{
  "schema_version": 1,
  "experiment_id": "photovoltaic",
  "experiment_title": "光电探测：硅光电池特性",
  "metadata": {
    "student_name": "本次学生", "student_id": "本次学号",
    "group": "1-07", "seat": "2", "date": "2026-01-12",
    "teacher": "本次教师", "room": "本次地点"
  },
  "requirements": {"preview_required": true},
  "constants": {
    "r_sample": {"value": 10, "unit": "ohm", "source": "photos/photo-001.jpg 表1"}
  },
  "tables": [{
    "id": "dark",
    "title": "无光照伏安特性原始数据",
    "columns": [
      {"key": "u1", "label": "U1", "unit": "V"},
      {"key": "u2", "label": "U2", "unit": "mV"}
    ],
    "rows": [{
      "values": {"u1": 4.0, "u2": 4.0},
      "raw": {"u1": "4.0", "u2": "4.0"},
      "source": {"image": "photos/photo-001.jpg", "table": "表1", "row": "右列第1行"}
    }]
  }],
  "observations": [],
  "issues": []
}

- number 为默认列类型；纯文字列用 "kind": "text"；无量纲的 unit 用空字符串。
- raw 可选，保留末尾零；同一行所有列都要有 values。
- 续表的每一行指向其实际图片；不得只给整张表一个模糊来源。
- 常数既可以来自图片，也可来自指明名称、页码的指导书；不要复制参考报告中的仪器实测常数。
- 坐标单位按照片记录，在 analyze.py 中显式转换，必要时同时输出 SI 值与报告显示值。
- 未知数值写 null，另建 issue；默认校验阻止计算。显式部分数据模式允许保留缺项继续做清晰部分。
- 无数量表的定性实验可只写 observations：
  {"id":"filter-horizontal","text":"照片中实际可见的现象","source":{"image":"photos/photo-002.jpg","region":"右侧成像屏"}}
- issues 元素：
  {"id":"u2-r4","status":"unresolved","blocking":true,"description":"表2第4行 U2 看不清，候选..."}
  已解决时保留 status="resolved" 和 resolution 说明。缺附件等非计算阻塞可用 blocking=false。
- 学号是字符串。metadata.date 必须为真实 ISO 日期，不能默认使用生成报告当天。

## analyze.py 与 results.json

from pathlib import Path
from physics import load_data, columns, linear_fit, configure_plots, save_results
data = load_data(".")
# 这里根据对应 recipe 做本次计算。禁止另建一份硬编码测量数组。
# quantities/tables/figures 都由该计算结果生成。
save_results(".",
    quantities=[{
        "id":"slope", "label":"拟合斜率", "value":1.23, "uncertainty":0.04,
        "digits":3, "unit":"mA/V",
        "method":"带截距普通最小二乘；此处仅为接口示例",
        "inputs":["table:iv"]
    }],
    tables=[],
    figures=[],
    notes=["拟合范围、被排除点及其理由写在这里"]
)

save_results 自动记录 data.json、analyze.py、随工程复制的计算助手和每张图的 SHA256；
不要手改哈希来掩盖旧结果。输入若为 numpy 数值，输出前转为 Python float/int/list。
quantities 的 id 可用于 \Result{slope}；uncertainty 可用于 \ResultUncertainty{slope}。
数字与单位分离，在正文使用一致单位，不能将 mA 的数值写成 A。

派生 tables 结构同原始表，但不要求 source；id 不得与原始表重复。
每个 table/figure 都要被 content.tex 的 \input 显式引用，避免漏项。
例如：
{
  "id":"iv",
  "path":"figures/iv.png",
  "caption":"暗伏安特性；点为实测，线为声明区间内的拟合",
  "table_ids":["dark"]
}
图片路径须位于工程目录内。原始照片留给附录；结果图使用真实数据作图。
定性图可使用 observation_ids 关联 data.json 中的现象条目，table_ids 可为空；
path 可指向 inputs.json 中的真实照片。图表至少有一种有效来源关联。

计算辅助函数：
- columns(data, id)：返回列名到列表的字典。
- linear_fit(x,y)：至少3点、带截距的无权OLS，返回 slope/intercept、标准误、R²和残差。
  不适用于横纵坐标均有明显不确定度、已知不等方差或强非线性；另用合适拟合方法。
- mean_uncertainty(values,instrument_limit=...)：均值与均值标准不确定度 u_A；
  instrument_limit 为已知矩形分布半宽，u_B=limit/sqrt(3)，不是默认把分辨率当半宽。
  n=1 时 u_A 未知；未提供仪器界限时 u_B/u_c 为 None。
- propagate(gradient,covariance)：一阶协方差传播，要求对称半正定矩阵。
- angular_difference(a,b)：角度制最短带符号角差，处理跨 0°。
- configure_plots()：Agg 绘图及系统中文字体选择，返回 pyplot。
  无中文字体时明确选择可用字体/英文坐标，不交付方框字。

## 部分数据草稿

本模式用于少数数字未能辨认，但其余数据足以进行独立分析的情况。
load_data(".", allow_incomplete=True) 允许 null，columns 仍原样返回，绝不自动补值或删行。
分析代码按明确条件选择完整行，notes 列出具体表/行、排除理由以及哪些结果无法计算；
样本不足或缺关键仪器参数的量仍不计算。
save_results(..., allow_incomplete=True, notes=[...]) 将 data_policy 记为 partial，notes 不得为空。
运行 report.py analyze "工程目录" --allow-incomplete；然后 build.py compile 可生成标记草稿。
原始电子表保留缺值为破折号，正文明确其含义及对本次分析范围的影响。
status 的 complete 始终为 false，不能通过 review 把部分分析标为完整。
用户补充数据后，清除 unresolved 状态并解释更改，恢复默认完整模式重算、重编译。

## 正文例子

\section{实验结果与数据处理}
\input{generated/tables/dark.tex}
\input{generated/tables/dark_processed.tex}
\input{generated/figures/iv.tex}
拟合斜率为 $\Result{slope}\pm\ResultUncertainty{slope}$ mA/V。

完整正文仍需实际实验对应的目的、仪器、原理、过程、讨论、思考题与总结。
只写原理或只有数据表不算完整报告。并非每项实验都要求数值不确定度，按指导书处理。
