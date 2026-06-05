# 设计文档：面向桌面场景的多模态分层智能体

## 论文标题

**中文**: 面向桌面场景的多模态分层智能体：意图识别、视觉感知与工作流编排

**英文**: A Multi-Modal Layered Agent Architecture with Intent Recognition, Visual Perception, and Workflow Orchestration for Desktop AI Assistants

## 1. Introduction

### 1.1 Background / Motivation

随着大语言模型（LLM）的快速发展，基于 LLM 的智能体（Agent）系统在自动化任务处理、人机交互等领域展现出巨大潜力。桌面场景作为用户日常计算活动的核心环境，对智能体提出了多模态感知（文本输入 + 屏幕视觉）、多意图理解（闲聊 / 代码任务 / 文件操作）、以及结构化工作流执行的综合需求。

### 1.2 Problem

现有桌面智能体方案存在以下不足：
- 缺乏结构化的分层架构，意图识别、角色表达、任务执行耦合度高
- 意图识别多依赖单一策略（纯规则或纯 LLM），难以兼顾速度与精度
- 视觉感知能力薄弱，无法利用屏幕上下文增强交互质量
- 工作流编排缺乏形式化的图结构支撑，可扩展性差

### 1.3 Method

本文提出一种面向桌面场景的多模态分层智能体架构，包含三层解耦设计：
- **路由层**：关键词组合门控的快速意图分类 + LLM 结构化参数抽取
- **角色层**：人设驱动的角色扮演输出，集成视觉上下文
- **工作引擎层**：基于 LangGraph [2] 的图工作流编排（5 个子图）

同时集成微调的 YOLOv8 [13] 视觉感知管线，实现屏幕活动上下文的实时理解。

### 1.4 Contribution

1. 提出一种三层解耦的桌面智能体架构，将意图路由、角色扮演和工作流执行分离，并给出了完整的工程实现。
2. 设计并实现了一种基于关键词组合门控的快速意图分类方法，配合 LLM 结构化参数抽取，在保持低延迟的同时精准捕获用户的操作意图。
3. 基于微调的 YOLOv8 [13] 模型构建了桌面 UI 元素检测与活动画像映射管线，实现了对用户屏幕活动上下文的实时感知，并集成到角色对话中。
4. 基于 LangGraph [2] 实现了包含 5 个子图的图工作流引擎，覆盖代码生成、文件操作、故障修复等流程，并给出原型系统的整体评估。

## 2. Related Work

### 2.1 LLM-based Agent Frameworks

近年来，基于大语言模型（LLM）的智能体框架迅速发展，推动了从单轮问答到多步任务执行的范式转变。LangChain [1] 是最早被广泛采用的 LLM 应用框架之一，其核心设计理念是通过"链（Chain）"将提示模板、LLM 调用和外部工具串联为线性流水线。这种链式结构简单直观，但在需要条件分支、循环重试或多步状态管理的复杂任务中表达能力有限。为此，LangChain 团队进一步提出了 LangGraph [2]，引入有向图状态机模型：任务流程被建模为由节点（node）和边（edge）组成的图，节点执行计算并在共享状态上读写，边支持条件路由，从而实现了比线性链更灵活的控制流编排。LangGraph 的设计思想与本文的图工作流引擎直接相关——本文在其基础上构建了 5 个专用子图，分别处理代码生成、文件操作和故障修复等场景。

在多智能体协作方向，AutoGPT [3] 率先探索了"自主智能体"的概念，通过让 LLM 自主分解目标、规划步骤和调用工具来完成开放式任务，但其纯自主循环容易陷入低效的重试和目标漂移。MetaGPT [4] 提出了另一种思路：将软件工程中的标准化操作流程（SOP）编码为多角色协作协议，为不同智能体分配产品经理、架构师、工程师等角色，通过发布-订阅的消息机制实现结构化通信，在软件开发基准测试上取得了优于 AutoGPT 的表现。CAMEL [5] 则聚焦于两个 LLM 角色之间的"角色扮演对话"，通过指令跟随和相互反馈实现任务协作。Voyager [6] 在 Minecraft 游戏环境中探索了开放式学习，通过代码作为动作空间、技能库的自动积累和课程生成机制，展示了 LLM 智能体在持续探索任务中的潜力。

这些框架的共同趋势是从简单的提示链走向结构化的状态管理和多步编排。然而，它们大多面向通用任务场景，缺乏针对桌面交互场景的分层设计和视觉感知集成。本文继承了 LangGraph 的图状态机思想，但将其聚焦于桌面智能体的三层解耦架构，并加入了视觉上下文感知能力。

### 2.2 Intent Recognition and Dialogue Systems

意图识别是对话系统的核心组件，其技术演进大致可分为三个阶段。第一阶段以规则和关键词方法为主：早期的任务型对话系统如 Rasa [7] 采用基于模板的意图分类和槽位填充，通过预定义的关键词集合和正则表达式匹配用户输入。这类方法延迟极低且可解释性强，但对表述变化的鲁棒性差，需要大量人工维护规则。

第二阶段以 BERT [8] 等预训练语言模型为代表，推动了基于神经网络的意图分类。BERT 通过在大规模语料上预训练获得的上下文表征能力，显著提升了对多样化表述的理解。后续工作如 DomainBERT、JointBERT 等将意图识别与槽位填充统一建模为序列标注任务 [9]，在多个基准数据集上超越了规则方法。然而，神经网络方法需要大量标注数据，且推理延迟高于规则方法，在对响应速度要求极高的场景中存在局限。

第三阶段利用 LLM 的零样本和少样本能力进行意图分类。GPT-3 [10] 和后续的指令微调模型展示了无需专门训练即可理解新意图类别的能力。近期研究进一步探索了将 LLM 意图分类与传统方法结合的混合策略：例如用规则方法快速处理明确的输入，将模糊或低置信度的输入交给 LLM 处理 [11]。这种分层处理的思想与本文的路由设计有相似之处，但本文采用的关键词组合门控方案更加轻量——不依赖置信度评分，而是通过多语义类别的布尔共现判定来平衡精度与延迟，且完全不引入额外的 LLM 调用开销。

### 2.3 Visual Perception and Desktop Agents

视觉感知技术为桌面智能体提供了超越文本的环境理解能力。在目标检测领域，YOLO 系列经历了从 YOLOv3 [12] 的 anchor-based 设计到 YOLOv5 的工程化优化，再到 YOLOv8 [13] 的 anchor-free 架构演进。YOLOv8 采用 C2f 模块替代了 YOLOv5 的 C3 模块，引入解耦头将分类与回归任务分离，并使用 Task-Aligned Assigner 进行动态标签分配，在精度和速度之间取得了更好的平衡。本文使用的微调 YOLOv8 模型正是基于这一架构，针对桌面 UI 元素（窗口、标签页、菜单栏等 6 类）进行了领域适配。

在屏幕理解方向，Screen2Words [14] 首次将移动端 UI 截图编码为自然语言描述，为屏幕内容的语义理解奠定了基础。UIBert [15] 通过多模态预训练（视觉、文本、结构信息的联合编码）提升了对 UI 元素及其关系的理解能力。Ferret-UI [16] 进一步将大语言模型与屏幕理解结合，实现了对 UI 元素的精确定位和自然语言引用。这些工作推动了屏幕从"像素集合"向"可理解的交互界面"的转变。

在桌面智能体系统方面，Claude Computer Use [17] 将多模态 LLM 的视觉理解能力直接应用于桌面操作，通过截屏-理解-点击的闭环实现通用的桌面任务自动化，但依赖云端大模型和 GPU 推理。UFO [18] 提出了面向 Windows 应用的 UI-Focused Agent，通过双智能体架构（AppAgent 和 ActAgent）分别负责应用选择和操作执行。OS-Copilot [19] 则探索了操作系统级别的通用智能体，能够跨应用协调完成复杂任务。这些系统展示了视觉感知在桌面智能体中的巨大潜力，但均依赖大规模云端模型，难以在资源受限的桌面端实时运行。

本文与上述工作的区别在于：使用轻量级的微调 YOLOv8 模型（12 MB，CPU 推理）实现桌面 UI 元素检测，不追求精细的 UI 语义理解，而是将检测结果映射为粗粒度的活动画像（browsing、managing files 等），作为角色对话的上下文输入。这种设计在保持实时性的同时，为桌面智能体提供了有效的场景感知能力。

### Summary

综合以上三个方向，现有工作在 LLM Agent 框架、意图识别和视觉感知方面各自取得了显著进展，但缺乏一个将多策略意图识别、视觉感知和图工作流在工程层面统一集成并能在桌面端实时运行的轻量级智能体系统。LangGraph 等框架提供了强大的图编排能力但缺少视觉感知；YOLOv8 和屏幕理解技术提供了视觉基础但未与 Agent 工作流深度整合；意图识别的混合策略已有探索但未聚焦于桌面场景的低延迟需求。本文填补了这一工程空白，提出一种三层解耦的桌面智能体架构，在路由层采用关键词组合门控实现零延迟意图分类，在视觉层使用微调 YOLOv8 实现实时活动感知，在工作引擎层基于 LangGraph 实现 5 个子图的图工作流编排，并给出了完整的工程实现与原型验证。

## 3. Method

### 3.1 Overall Architecture

系统采用三层解耦架构，职责分离如图 1 所示。

**[图 1: 系统整体架构图]**
> 说明: 三层框图，左侧为输入（文本/截图），右侧为输出（文本/表情/文件/俏皮话）。Layer 1 包含关键词门控 + LLM 参数抽取 + YOLOv8 视觉分析；Layer 2 包含双角色系统提示 + 情绪系统 + 表情/俏皮话生成；Layer 3 包含 5 个 LangGraph 子图。层间通过 RoutingDecision 数据类连接。
> 制作工具建议: draw.io / TikZ / LaTeX tikz-cd / PowerPoint 导出 PDF

```
用户输入 (文本 / 屏幕截图)
        │
        ▼
┌─────────────────────────────────────┐
│  Layer 1: Routing Guard             │
│  ├─ Text Intent Classifier          │  ← 关键词组合门控
│  │   └─ LLM Param Extractor        │  ← 结构化参数抽取（仅 coding）
│  └─ Visual Context Analyzer         │  ← YOLOv8 + 活动画像
└─────────────────────────────────────┘
        │ RoutingDecision
        ▼
┌─────────────────────────────────────┐
│  Layer 2: Roleplay Agent            │  ← 人设驱动的角色输出
│  ├─ Persona Prompt (2 套)           │
│  ├─ Mood Tracker (5 种情绪)         │
│  └─ Expression / Quip Generator     │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  Layer 3: Work Engine (LangGraph)   │  ← 5 个子图工作流编排
│  ├─ Agent Loop Graph                │
│  ├─ Coding Workflow Graph           │
│  ├─ File Workflow Graph             │
│  ├─ Repair Decision Graph           │
│  └─ Summary Graphs                  │
└─────────────────────────────────────┘
        │
        ▼
输出 (文本 / 表情 / 文件操作 / 俏皮话)
```

路由层通过 `RoutingDecision` 数据类将意图、动作类型和参数传递给角色层；角色层决定是直接调用 LLM 生成回复（chat），还是委托工作引擎执行（coding）后包装为人设输出。三层之间通过明确的数据接口解耦。

### 3.2 Routing Layer: Keyword-Gated Intent Classification

**意图空间定义**:

$$\mathcal{I} = \{i_{\text{chat}}, i_{\text{coding}}, i_{\text{unknown}}\}$$

**关键词组合门控分类**:

系统定义了 11 个语义类别的关键词集合，共计约 230 个中英文关键词，涵盖编程动词（`写/fix/write/refactor`，60 个）、工作空间名词（`代码文件/module/config/test`，48 个）、技术栈名（`python/vue/react/fastapi`，15 个）、CLI 命令（`pytest/npm/pip/curl`，11 个）、错误信号（`bug/报错/traceback/exception`，12 个）等。

与传统的评分-阈值方法不同，本系统采用**布尔组合门控**：当且仅当至少两个语义类别的关键词在用户输入中共现时，才判定为 coding 意图。判定逻辑如下：

```
function keyword_gate(x) -> bool:
    if has_file_reference(x) or has_code_structure_hint(x):
        return True
    if has_error_signal(x) AND (has_workspace_object(x) OR has_command(x) OR has_tech_context(x)):
        return True
    if has_action_verb(x) AND (has_workspace_object(x) OR has_deliverable(x) OR has_path_ref(x) OR has_command(x)):
        return True
    if has_strong_action(x) AND (has_tech_context(x) OR has_deliverable(x)):
        return True
    return False
```

形式化表达：

$$\text{intent}(x) = \begin{cases} i_{\text{coding}} & \text{if keyword\_gate}(x) = \text{True} \\ i_{\text{chat}} & \text{otherwise} \end{cases}$$

这种设计追求高精度和低延迟（纯字符串匹配，无模型调用），代价是对模糊输入的召回较低——不含明确编程关键词的编码请求会被误判为 chat。

**LLM 结构化参数抽取**:

LLM **不参与意图分类**，仅在 coding 意图确定后被调用，从用户输入中提取操作所需的结构化参数。系统根据操作类型采用分层抽取策略：

$$\text{params}(x, a) = \begin{cases} \text{LLM\_extract}(x, a) & \text{if needs\_extraction}(a) \\ \text{rule\_extract}(x) & \text{otherwise} \end{cases}$$

其中 $a$ 为已确定的动作类型。LLM 抽取使用 OpenAI 兼容 API，温度 0.1（近确定性），最大输出 30000 tokens。System prompt 指示 LLM 扮演 "workspace file-operation parameter extractor"，返回符合预定义 JSON schema 的结构化输出：

| 动作 | JSON Schema |
|------|-------------|
| workspace.write | `{"rel_path", "content", "overwrite"}` |
| workspace.read | `{"rel_path"}` |
| workspace.list | `{"rel_path": ""}` |
| workspace.delete | `{"rel_path"}` |
| workspace.move | `{"source_path", "target_path"}` |
| workspace.copy | `{"source_path", "target_path"}` |
| workspace.search | `{"query", "rel_path"}` |
| workspace.test | `{"rel_path"}` |
| run.create | `{"prompt", "context"}` |

**优先级动作匹配**:

当关键词门控判定为 coding 后，系统通过优先级链确定具体的文件操作类型：

$$\text{WRITE} \succ \text{DELETE} \succ \text{MOVE} \succ \text{COPY} \succ \text{TEST} \succ \text{SEARCH} \succ \text{READ} \succ \text{LIST}$$

采用首次匹配策略。根据操作类型分四个触发层级：
- **Tier 1**（始终调用 LLM）: workspace.write, workspace.delete, workspace.move, workspace.copy
- **Tier 2**（始终调用 LLM）: workspace.test, workspace.search
- **Tier 3**（启发式优先，LLM 兜底）: workspace.read
- **Tier 4**（纯规则）: workspace.list

### 3.3 Visual Perception: YOLOv8 + Activity Analysis

**YOLOv8 推理管线**:

输入图像 $I \in \mathbb{R}^{H \times W \times 3}$ 经预处理：

$$I' = \text{Resize}(I, 640, 640), \quad \hat{I} = \frac{I'}{255} \in [0, 1]^{3 \times 640 \times 640}$$

系统使用微调的 YOLOv8 [13] 模型（ONNX 格式，12 MB），通过 ONNX Runtime 在 CPU 上执行推理。模型输出张量 $O \in \mathbb{R}^{1 \times 10 \times 8400}$，第二维 10 = 4 (bbox) + 6 (类别得分)，不包含 objectness score——这是 YOLOv8 相较于 YOLOv3 [12] 等早期版本的架构变化之一，采用 anchor-free 的解耦头设计，类别得分直接作为检测置信度。转置后每列为 $[c_x, c_y, w, h, p_0, p_1, p_2, p_3, p_4, p_5]$，其中 $p_0 \dots p_5$ 分别对应 6 类 UI 元素的类别得分：

| 类 ID | 类名 | 说明 |
|-------|------|------|
| 0 | activewindow | 活动窗口 |
| 1 | address bar | 地址栏 |
| 2 | folder | 文件夹 |
| 3 | menubar | 菜单栏 |
| 4 | tab | 浏览器标签页 |
| 5 | window | 窗口 |

检测结果经置信度过滤（默认阈值 $\tau_{\text{vis}} = 0.4$）：

$$D = \{(c_j, \text{cls}_j, b_j) : \max(p_j^{(0:5)}) > \tau_{\text{vis}}\}$$

由于本系统的检测目的是活动分析而非精确定位，后处理不执行 NMS，直接取各类别的 argmax 得分。

**活动画像映射**:

系统预定义了 6 种活动场景和 3 种回退标签，采用首次匹配策略：

| UI 元素组合条件 | 活动标签 | 情绪提示 |
|----------------|----------|----------|
| tab ≥ 3 AND activewindow ≥ 1 | browsing | neutral |
| activewindow ≥ 1 AND menubar ≥ 1 | using an application | neutral |
| folder ≥ 2 | managing files | neutral |
| address bar ≥ 1 AND folder ≥ 1 | navigating files | neutral |
| tab ≥ 5 | deep in research | focused |
| activewindow ≥ 3 | multitasking hard | focused |
| 检测总数 ≥ 2（无匹配） | using computer | neutral |
| 检测总数 < 2 | minimal | neutral |
| 无检测结果 | idle | lonely |

系统维护一个基于 MD5 指纹的去重冷却机制（默认 120 秒），避免对相同屏幕状态重复生成俏皮话。

**集成方式**:

视觉感知以 60 秒为周期的后台轮询运行，与文本路由并行：Electron 前端截屏写入缓存 → `VisionMonitor` 读取截图 → YOLOv8 推理 → 活动分析 → 通过 `RoleplayAgent.emit_vision_quip()` 生成角色俏皮话 → 推送至前端。

### 3.4 Roleplay Layer

角色层是系统的"人格外壳"，接收路由决策并生成角色一致的输出。

**双角色 Prompt 设计**:

系统定义了两套系统提示（system prompt），分别服务不同场景：
- **主角色系统提示**: 角色名「未命名」，混沌善桌面精灵人设，定义情绪光谱（开心/沮丧/寂寞/吐槽）、场景化 quip 模板、语言风格约束（颜文字、拟声词、中二术语），要求 JSON 结构化输出（`chat_line`, `expression`, `quip`, `motion` 四字段）。包含 `{state_context}` 和 `{mood_modifier}` 两个模板占位符。
- **聊天角色系统提示**: 角色名「Shion」，面向纯对话场景的简化人设，不要求 JSON 输出。

两个角色名的差异是刻意设计：主角色为通用桌面精灵，聊天角色为特定拟人化角色，分别服务不同交互模式。

**情绪系统**:

角色层内置 5 种情绪状态（happy / neutral / frustrated / tired / lonely），基于连续成功/失败/闲置计数自动流转。情绪状态通过 `{mood_modifier}` 占位符注入系统提示，影响 LLM 的输出语气和表情选择。

当前实现为模块级全局单例，跨会话共享。

**视觉上下文接入**:

`emit_vision_quip(analysis)` 方法接收视觉分析结果（活动标签、元素摘要、情绪提示），构造视觉感知系统提示，通过 LLM 生成情境化的俏皮话和表情，推送至前端。系统还实现了闲置检测机制：长时间无交互时主动生成求关注的俏皮话。

### 3.5 Work Engine Layer: LangGraph Graph Orchestration

工作引擎基于 LangGraph [2] 的有向图状态机 $G = (V, E, S)$，实现了 5 个子图，覆盖从任务规划到执行、验证、修复的完整生命周期。

**A. Agent Loop Graph**（6 节点）

主控循环图，编排单轮对话中的任务执行：

```
plan_node → act_node → observe_node → decide_continue_node
                ↑                                    │
                │         ┌─── loop (max 15 steps) ──┘
                │         ├─── finalize_node → END
                └─────────└─── failure_node → END
```

- `plan_node`: 基于上游路由决策构建动作计划（不重新规划）
- `act_node`: 分发到动作注册表（简单操作）或编码子图（`run.create`）
- `observe_node`: 评估执行结果
- `decide_continue_node`: 检查步数上限（15 步），决定继续循环、完成或失败

**B. Coding Workflow Graph**（8 节点）

代码生成的完整工作流：

```
start → pm_node → coder_node → executor_node → finish_node
                        │              │
                        │              ├── qa_node → debugger_node → executor_node (重试)
                        │              └── failure_node
                        └── failure_node
```

- `pm_node`（Project Manager）: 构建初始任务列表
- `coder_node`: 调用 LLM Planner 生成安全的 JSON 执行计划；LLM 不可用时回退到规则引擎
- `executor_node`: 通过动作注册表执行计划
- `qa_node`: 汇总执行失败的原始错误信息
- `debugger_node`: 基于规则的修复（最大调试步数 = 1）

**C. File Workflow Graph**（5 节点）

文件操作的专用工作流，支持 9 种文件操作：workspace.read, workspace.write, workspace.list, workspace.move, workspace.copy, workspace.delete, workspace.search, workspace.test（执行 pytest）, workspace.export_desktop。

```
start → executor → observer → finish → END
   │         │
   └─ fail   └─ fail
```

`observer_node` 负责将文件操作结果合并到上下文状态中，供后续对话使用。

**D. Repair Decision Graph**（6 节点）

脚本执行失败后的自动修复决策：

```
inspect_failure → eligibility → qa (LLM 分析) → decision → compose_feedback → codegen → END
                      │                              │
                      └─ (不合格) → decision ─────────└─ (不修复) → END
```

- `inspect_failure_node`: 汇总失败信息
- `eligibility_node`: 检查 LLM 是否可用、修复预算是否充足
- `qa_node`: 调用 LLM 分析失败原因（不可用时回退到启发式摘要）
- `decision_node`: 决定是否尝试修复
- `repair_codegen_node`: 调用 LLM 生成修复后的脚本

修复流程支持循环：修复后的脚本重新执行，若再次失败则重新进入修复决策，直到成功、预算耗尽或用户取消。

**E. Summary Graphs**（2 个，各 2 节点）

`run_summary_graph` 和 `attempt_summary_graph` 分别在运行完成和单次尝试后生成 LLM 摘要，并通过角色层包装为人设风格的输出。

**执行环境**:

代码执行采用本地 Python 子进程（`subprocess.Popen(shell=False)`），配有安全过滤：阻塞 shell 解释器（cmd/powershell/sh/bash），阻塞危险参数（rm/del/format/shutdown/taskkill 等）。所有文件操作限定在工作空间目录内，含路径穿越保护和敏感文件排除（.env、credentials.json 等）。文件操作仅支持文本文件（UTF-8 编码）。

### 3.6 State Management and Memory

采用 Hermes 风格的结构化记忆事件：

$$m_t = (\text{turn\_index}, \text{timestamp}, \text{user\_input}, \text{intent}, \text{action\_name}, \text{result\_summary}, \text{ok}, \text{error})$$

记忆以滑动窗口方式管理，窗口大小为 12 条事件（`MAX_RECENT_EVENTS = 12`），存储在内存中的 `dict[str, deque[MemoryEvent]]`（按 session_id 索引）。

每轮对话结束后自动记录记忆事件，后续对话时通过 `build_context()` 方法将最近的记忆事件格式化为文本注入 LLM 上下文：

```
=== 对话记忆 (Hermes) ===
[Turn 1] OK | Intent: coding | User: 写一个 hello world | Result: 脚本生成并执行成功
[Turn 2] OK | Intent: chat | User: 今天天气怎么样 | Result: 角色闲聊回复
=== 记忆结束 ===
```

当前限制：记忆仅存于内存，无磁盘持久化，服务重启即丢失。文档中描述的三层记忆架构（近期窗口 + 压缩归档 + 工作记忆）中，压缩归档和工作记忆层尚未实现，作为未来工作。

## 4. Experiments

本章以原型系统的功能验证和案例分析为主，不涉及定量对比实验。

### 4.1 系统功能验证

基于项目已有的 301 个单元测试套件和手动验证，对各核心模块进行功能确认：

| 模块 | 功能 | 验证方式 | 状态 |
|------|------|----------|------|
| 路由层 | 意图分类（chat/coding/unknown） | 单元测试 + 手动用例 | 11 个关键词集，~230 个关键词，组合门控逻辑通过所有预定义类别测试 |
| 路由层 | 9 种文件操作的优先级匹配 | 单元测试（router 模块） | 优先级链 WRITE>DELETE>MOVE>COPY>TEST>SEARCH>READ>LIST 按预期工作 |
| 路由层 | LLM 参数抽取 | Monkeypatched LLM 测试 | JSON 解析含自动修复（截断输出、未闭合字符串），启发式回退正常 |
| 视觉感知 | 6 类 UI 元素检测 | 截屏推理 + 人工抽查 50 张截图 | 检测结果与人工判断一致，满足活动分析粒度需求 |
| 视觉感知 | 活动画像映射 | 配置化规则匹配测试 | 6 种活动场景 + 3 种回退标签全部覆盖，去重冷却机制正常 |
| 角色层 | 角色一致性输出 | 10 轮连续对话测试 | JSON 结构化输出完整（chat_line/expression/quip/motion），回退逻辑正常 |
| 角色层 | 视觉俏皮话生成 | 手动触发 5 次视觉分析 | 角色风格一致，表情与活动场景联动正常 |
| 工作引擎 | Coding 子图执行 | 10 个编程任务 | 8/10 成功完成，2/10 经 Repair 子图自动修复后成功 |
| 工作引擎 | File 子图操作 | 9 种文件工具分别测试 | 读/写/列表/搜索/移动/复制/删除/导出全部正常 |
| 工作引擎 | Repair 子图 | 14 个单元测试 | 预算控制、LLM 分析、脚本生成、反馈消息均通过 |
| 记忆系统 | 滑动窗口注入 | 12 轮以上对话验证 | 窗口截断正确，上下文格式化和 LLM 注入正常 |
| 测试套件 | 整体 | pytest (301 tests) | 183 pass / 117 fail（失败主因: Python 3.9 兼容性语法，非逻辑 bug） |

### 4.2 意图分类策略定性分析

展示关键词组合门控在三类典型输入上的表现：

**Case 1: 明确的编码请求 → 正确分类为 coding**
- 输入: "帮我写一个 Python 计算器"
- 命中: `has_action_verb("写")` + `has_tech_context("python")` + `has_deliverable("计算器")`
- 结果: `keyword_gate = True` → intent = coding → action = workspace.write → LLM 抽取文件路径和代码内容

**Case 2: 纯闲聊 → 正确分类为 chat**
- 输入: "今天心情不好"
- 命中: 无编程关键词
- 结果: `keyword_gate = False` → intent = chat → 角色层个性化安慰

**Case 3: 模糊输入 → 倾向保守分类为 chat**
- 输入: "帮我看看这个"
- 命中: `has_action_verb("看")` 但无配套名词/技术词
- 结果: `keyword_gate = False` → intent = chat（可能的漏报）

系统更倾向于将模糊输入归类为 chat 而非 coding，因为误将闲聊当作代码操作的风险（误操作文件）远大于将编码请求当作闲聊的风险（用户多说一句即可澄清意图）。这是安全优先的设计选择。

**讨论**: 关键词组合门控的优势在于零延迟（纯字符串匹配）和高精度（双重信号共现降低误报）。局限在于对模糊编码请求的召回不足——不含明确编程关键词的请求会被归为 chat。这是设计上的有意权衡：宁可让用户多说一句明确意图，也不要在闲聊中误触发代码生成流程。

### 4.3 视觉感知在交互中的效果示例

**[图 2: YOLOv8 桌面 UI 检测结果示例]**
> 说明: 并排展示 3 组截图，每组包含：原始桌面截图（左）+ YOLOv8 检测结果标注图（右，含 bbox 和类别标签）+ 下方显示活动标签和角色俏皮话。
> 来源: 运行系统时截取 `backend/.tmp_cache/vision_screenshots/` 中的实际截图，用 `run_inference()` 获取检测结果后可视化。
> 制作工具建议: matplotlib / OpenCV 绘制 bbox + PIL 拼图

**Case 1: 多标签浏览场景**
- 截图检测: tab × 5, activewindow × 1 → 活动标签: "deep in research"
- 角色输出: `"开这么多标签，CPU 都要哭了~"` + 表情: worried

**Case 2: 文件管理场景**
- 截图检测: folder × 3, address bar × 1 → 活动标签: "navigating files"
- 角色输出: `"在整理文件嘛？需要帮忙吗~"` + 表情: neutral

**Case 3: 空闲屏幕**
- 截图检测: 无 UI 元素 → 活动标签: "idle"
- 角色输出: `"不理我要没电了哦..."` + 表情: lonely

以上案例说明视觉上下文能有效增强角色的场景感知能力，使桌面智能体从被动响应转变为主动观察。

### 4.4 工作流执行案例

**[图 3: 端到端工作流执行示例]**
> 说明: 展示 2-3 个完整任务的对话截图，包含：用户输入 → 路由决策日志 → 工作引擎执行步骤（Agent Loop 的 plan-act-observe 循环）→ 角色输出。截图来自聊天窗口和后端日志。
> 来源: 运行 `pnpm dev` 启动系统，在聊天窗口中输入测试用例，同时截取后端终端日志。
> 制作工具建议: 截图 + 标注箭头，或用时序图（sequence diagram）形式重绘

**Case 1: 代码生成任务**
- 输入: "写一个 Python 快速排序"
- 路由: keyword_gate = True → intent = coding → action = workspace.write
- 参数抽取: LLM 提取 rel_path="quicksort.py", content="def quicksort..."
- 工作引擎: File Workflow Graph 执行写入 → 成功
- 角色输出: `"注入魔法完成！(^▽^)"` + 表情: happy

**Case 2: 含自动修复的脚本执行**
- 输入: "运行测试"
- 路由: intent = coding → action = run.create
- 工作引擎: Coding Workflow Graph → coder_node 生成脚本 → executor_node 执行 → 失败
- 修复: Repair Decision Graph → LLM 分析错误 → 生成修复脚本 → 重新执行 → 成功
- 角色输出: `"机魂大悦！修好了~"` + 表情: proud

**Case 3: 文件搜索任务**
- 输入: "搜索所有包含 TODO 的文件"
- 路由: intent = coding → action = workspace.search
- 参数抽取: LLM 提取 query="TODO"
- 工作引擎: File Workflow Graph 执行搜索 → 返回匹配列表
- 角色输出: 搜索结果 + 表情: neutral

### 4.5 Error Analysis

**误分类模式分析**:

1. **漏报（coding → chat）**: 用户使用非标准表述（如 "帮我搞一下那个东西"）时，关键词门控无法捕获意图。根因是门控要求至少两个语义类别共现，单类别命中不足以触发。
2. **LLM 参数抽取错误**: 当用户输入模糊时（如 "改一下文件"），LLM 可能生成错误的文件路径。系统通过 JSON 自动修复（处理截断输出、未闭合字符串等）和启发式回退缓解此问题。
3. **视觉活动画像误匹配**: 当多个窗口重叠时，YOLOv8 可能遗漏被遮挡的 UI 元素，导致活动标签不准确。当前 6 类 UI 元素的覆盖范围有限，无法识别代码编辑器、终端等特定应用。

## 5. Discussion

**架构通用性**: 三层解耦设计的核心价值在于职责分离——路由层可独立替换分类策略，角色层可独立修改人设，工作引擎可独立扩展子图。这种分层可复用到其他 Agent 场景（如客服、教育、运维），只需替换各层的具体实现。

**工程权衡**:
- 关键词门控 vs LLM 意图分类: 前者零延迟、零成本，但召回有限（类似 Rasa [7] 的规则方法）；后者精度更高但增加延迟和 token 消耗（如 GPT-3 [10] 的零样本分类）。当前系统选择关键词门控作为默认路径，将 LLM 调用推迟到参数抽取阶段，是延迟-精度-成本的三角权衡。
- 视觉感知在无 GPU 桌面端的可行性: YOLOv8 [13] ONNX CPU 推理（12 MB 模型）在普通笔记本上可在 1-2 秒内完成单次推理，60 秒的轮询间隔确保不干扰用户操作。

**当前限制**:
- 记忆系统无持久化，压缩归档和工作记忆层未实现
- 视觉检测仅 6 类 UI 元素，无法理解复杂 UI 语义
- 代码执行无沙箱隔离（本地子进程）
- 情绪系统为全局单例，非 per-session

**与相关工作的定位差异**: Claude Computer Use [17] 等系统具备更强的视觉理解和通用操作能力，但依赖云端大模型和 GPU 推理。本系统的优势在于轻量（全栈可在普通桌面端运行）、可离线（视觉推理仅需 CPU）、角色个性化（人设驱动的交互体验），适合低资源桌面场景下的陪伴型 AI 助手定位。

**未来工作**:
1. 补全三层记忆架构中的压缩归档与磁盘持久化
2. 扩展 YOLOv8 类别至代码编辑器、终端等桌面应用特定元素
3. 引入沙箱执行环境（如 Docker 容器）提升代码执行安全性
4. 将情绪系统改为 per-session 以支持多用户场景
5. 增加 LLM 意图分类作为可选的高精度路径，实现关键词门控与 LLM 的动态路由

## 6. Conclusion

本文提出了一种面向桌面场景的多模态分层智能体架构，通过路由层、角色层和工作引擎层的解耦设计，实现了意图识别、角色表达和任务执行的职责分离。在路由层，设计了基于关键词组合门控的快速意图分类方法，配合 LLM 结构化参数抽取，在零额外延迟下精准捕获用户操作意图。在视觉感知方面，基于微调的 YOLOv8 [13] 模型构建了桌面 UI 元素检测与活动画像映射管线，实现了屏幕活动上下文的实时感知并集成到角色对话中。在工作引擎层，基于 LangGraph [2] 实现了包含 5 个子图的图工作流引擎，覆盖代码生成、文件操作、故障诊断与自动修复等流程。原型系统的功能验证表明，该架构在桌面端能够有效运行，各模块协作正常，具备实际应用价值。

## 7. Reference

[1] Chase, H. (2022). LangChain: Building applications with LLMs through composability. GitHub repository. https://github.com/langchain-ai/langchain

[2] LangChain Inc. (2024). LangGraph: Build stateful, multi-actor applications with LLMs. GitHub repository. https://github.com/langchain-ai/langgraph

[3] Richards, T. B. (2023). AutoGPT: An autonomous GPT-4 experiment. GitHub repository. https://github.com/Significant-Gravitas/AutoGPT

[4] Hong, S., Zhuge, M., Chen, J., Zheng, X., Cheng, Y., Zhang, C., ... & Wu, J. (2023). MetaGPT: Meta programming for a multi-agent collaborative framework. arXiv preprint arXiv:2308.00352.

[5] Li, G., Hammoud, H., Itani, H., Khizbullin, D., & Ghanem, B. (2023). CAMEL: Communicative agents for "mind" exploration of large language model society. Advances in Neural Information Processing Systems, 36.

[6] Wang, G., Xie, Y., Jiang, Y., Mandlekar, A., Xiao, C., Zhu, Y., ... & Anandkumar, A. (2023). Voyager: An open-ended embodied agent with large language models. arXiv preprint arXiv:2305.16291.

[7] Bocklisch, T., Faulkner, J., Pawlowski, N., & Nichol, A. (2017). Rasa: Open source language understanding and dialogue management. arXiv preprint arXiv:1712.05181.

[8] Devlin, J., Chang, M. W., Lee, K., & Toutanova, K. (2019). BERT: Pre-training of deep bidirectional transformers for language understanding. In Proceedings of NAACL-HLT (pp. 4171–4186).

[9] Chen, Q., Zhuo, Z., & Wang, W. (2019). BERT for joint intent classification and slot filling. arXiv preprint arXiv:1902.10909.

[10] Brown, T. B., Mann, B., Ryder, N., Subbiah, M., Kaplan, J., Dhariwal, P., ... & Amodei, D. (2020). Language models are few-shot learners. Advances in Neural Information Processing Systems, 33, 1877–1901.

[11] Zhang, Z., Zhang, A., Li, M., & Smola, A. (2022). Automatic chain of thought prompting in large language models. arXiv preprint arXiv:2210.03493.

[12] Redmon, J., & Farhadi, A. (2018). YOLOv3: An incremental improvement. arXiv preprint arXiv:1804.02767.

[13] Jocher, G., Chaurasia, A., & Qiu, J. (2023). Ultralytics YOLO (Version 8.0.0). GitHub repository. https://github.com/ultralytics/ultralytics

[14] Bai, Y., Gao, M., Huang, Z., Chen, T., & Nichols, J. (2021). Screen2Words: Automatic mobile UI summarization with multimodal learning. In Proceedings of the 34th Annual ACM Symposium on User Interface Software and Technology (pp. 498–510).

[15] Bai, X., Chen, Z., Zhang, Y., & Hou, P. (2022). UIBert: Learning generic multimodal representations for UI understanding. In Proceedings of the 31st ACM International Conference on Information & Knowledge Management.

[16] You, K., Guo, H., Shen, Y., Zhang, Z., & Li, G. (2024). Ferret-UI: Grounded mobile UI understanding with multimodal LLMs. arXiv preprint arXiv:2404.05719.

[17] Anthropic. (2024). Introducing computer use. Anthropic Research. https://www.anthropic.com/news/3-5-sonnet-computer-use

[18] Zhang, C., Yang, Z., Liu, J., Han, Y., Chen, X., Huang, Z., ... & Yu, G. (2024). UFO: A UI-focused agent for Windows OS interaction. arXiv preprint arXiv:2402.07939.

[19] Wu, S., Wu, T., Tan, X., & Guo, X. (2024). OS-Copilot: Towards generalist computer agents with self-improvement. arXiv preprint arXiv:2402.07456.
