# 设计文档：补齐论文关键缺失

## 目标

补齐论文模板（论文模板.docx）要求的全部缺失内容，使论文结构完整、实验数据真实可复现。

## 缺失清单与方案

### P0: Abstract + Author + Affiliation + Keywords

| 缺失 | 方案 | 文件 |
|------|------|------|
| Abstract | 中文摘要（~250 词）+ 英文摘要（~200 词）| `paper/sections/00-abstract.tex` |
| Author | 补充 `\author{姓名}` | `paper/main.tex` |
| Affiliation | 补充 `\affiliation{学校/院系}` | `paper/main.tex` |
| Keywords | 中文 5 个 + 英文 5 个 | `00-abstract.tex` |

**中文关键词**: 桌面智能体；意图识别；YOLOv8；LangGraph；角色扮演
**英文关键词**: Desktop Agent; Intent Recognition; YOLOv8; LangGraph; Roleplay

**摘要结构**:
- 背景(1句): LLM Agent 发展 + 桌面场景需求
- 问题(1句): 缺乏分层架构、意图识别单一、视觉薄弱
- 方法(3句): 三层架构 + 关键词组合门控 + YOLOv8 视觉 + LangGraph 工作流
- 实验(1句): 400 条测试集，F1=XX，延迟 XXms
- 结论(1句): 原型验证可行

### P1: Dataset + Metrics + Settings

#### §4.1 Dataset and Evaluation Protocol

**测试集构造**:
- 总量: 400 条中文输入
- 来源: 200 条手工构造 + 200 条从系统部署日志提取
- 分布: chat 160 (40%) / coding 190 (48%) / unknown 50 (12.5%)
- JSON 格式: `{"id": int, "text": str, "label": str, "source": "manual"|"log"}`

**标注协议**:
- 标注规则写入 `paper/data/labeling_guideline.md`
- 规则: 含编程动词+技术名词/文件路径/代码结构 → coding; 纯自然语言无编程信号 → chat; 空/噪声/无法判断 → unknown
- 日志数据标签来源: `detect_intent()` 输出，**论文中声明存在循环验证风险**

**评估指标**:
- Accuracy: $\text{Acc} = \frac{\text{correct}}{\text{total}}$
- Weighted F1: $\text{F1}_{\text{weighted}} = \sum_{c} w_c \cdot \text{F1}(c)$，其中 $w_c = N_c / N$
- Latency（路由层）: `detect_intent()` 入口到 `RoutingDecision` 返回，time.perf_counter()
- Latency（端到端）: 用户输入到角色输出，含 LLM 调用

**实验环境**:
- 硬件: 用户本机（Windows 11）
- Python: 3.11
- LLM: 通过 `settings.llm_base_url` 配置的 OpenAI 兼容 API，temperature=0
- 可复现性: random.seed(42)，LLM 响应记录到 `paper/data/llm_responses.json`

#### §4.2 Baselines

| 基线 | 定义 | 与 Ours 的差异 |
|------|------|----------------|
| B1: Rule-Only | 任一编程关键词子串命中 → coding | 不区分语义类别，召回高但精度低 |
| B2: LLM-ZeroShot | 直接调 LLM（temperature=0）做 3 分类 | 纯 LLM，延迟高 |
| B3: Keyword-Score≥1 | $\|$matched\_categories$\|$ ≥ 1 → coding | 去掉组合门控的共现要求 |
| Ours | $\|$matched\_categories$\|$ ≥ 2 → coding | 组合门控 |

B1 vs B3 区别: B1 是单个关键词子串匹配（如"写"出现在"写字"中也触发），B3 是单个语义类别命中（需命中该类别至少一个关键词）。B3 比 B1 更精确。

LLM-ZeroShot 使用与参数抽取相同的 LLM，延迟取 5 次中位数。

#### §4.3 Main Results

**主结果表**: 5 方法 × (Precision / Recall / F1 / Accuracy / Latency)

**Per-class F1 表**: chat / coding / unknown 各类 F1，unknown 样本量小（50条），指标仅供参考。

#### §4.4 Ablation Study（三维度）

**维度 1: 意图分类消融**（400 条测试集，Accuracy/F1/Latency）

| 配置 | 说明 |
|------|------|
| Full (Ours) | 组合门控 |
| w/o Gate | = B3 Keyword-Score≥1，数据复用 |

**维度 2: 端到端任务消融**（20 个 coding 任务，任务成功率/参数抽取准确率）

| 配置 | 说明 |
|------|------|
| Full | 组合门控 + LLM 抽取 |
| Rule-Only Extraction | 组合门控 + 规则抽取（去掉 LLM） |

**维度 3: 视觉消融**（定性案例对比，§4.5 Case Study 中展示）

对比有/无视觉上下文时角色回复的情境相关性。

### 文件产出

| 文件 | 内容 |
|------|------|
| `paper/sections/00-abstract.tex` | 中英文摘要 + 关键词 |
| `paper/main.tex` | 补充 Author + Affiliation + \input{sections/00-abstract} |
| `paper/data/test_set.json` | 400 条测试集 |
| `paper/data/labeling_guideline.md` | 标注规则 |
| `paper/data/llm_responses.json` | LLM API 响应记录 |
| `paper/scripts/run_experiments.py` | 实验运行脚本（含 4 baseline + 2 ablation） |
| `paper/scripts/generate_result_figures.py` | 结果可视化（混淆矩阵/F1-Latency 散点/消融柱状图） |
| `paper/sections/04-experiments.tex` | 重构为 9 个子节 |

### §4 重构后的完整结构

```
§4 Experiments
├── §4.1 Dataset and Evaluation Protocol
│   ├── 测试集统计表（按来源分层）
│   ├── 评估指标定义（公式）
│   └── 实验环境描述
├── §4.2 Baselines
│   └── 4 种方法定义表
├── §4.3 Main Results
│   ├── 主结果表（Precision/Recall/F1/Accuracy/Latency）
│   ├── Per-class F1 表
│   └── 混淆矩阵图 + F1-Latency 散点图
├── §4.4 Ablation Study
│   ├── 意图分类消融表
│   ├── 端到端任务消融表
│   └── 消融柱状图
├── §4.5 Visualization Study（保留原 §4.3 YOLOv8 检测图）
├── §4.6 Error Analysis（保留原 §4.5）
└── §4.7 Case Study（保留原 §4.4 + 视觉消融案例）
```
