---
source_pdf: AI Agent 开发框架与蓝图 - Google Docs.pdf
exported_at: 2026-05-11T17:35:25
export_method: pymupdf
total_pages: 4
---

# AI Agent 开发框架与蓝图 - Google Docs



---

## Page 1

结合你对 moeru-ai/airi 的参考，以及当前顶尖的 AI Agent 编程工具（如 Claude Code, Codex,
MetaGPT, ChatDev）的架构原理，你们的这个人工智能导论项目非常有野心，也非常契合目前大
模型应用的最前沿方向。
你实际上是在构建一个“具备高度情绪价值（二次元老婆）+ 极其硬核生产力（自动化软件公司）
的数字生命综合体”。
经过对目前开源生态和前沿技术的深度检索与拆解，我为你整理了这份面面俱到的全流程开发框
架与架构蓝图。我们将吸收各家之长，构建这个系统。
第一部分：前沿架构解析（我们向他们学什么？）
在动手前，我们需要明确各个参考标杆的核心技术护城河，并将其融入我们的框架：
1. moeru-ai/airi 的启示（表现层与数字生命形态）：
○ Web 原生底座：Airi 的核心在于大量使用 Web 技术（WebGPU, WebAudio,Web
Workers, WebSocket），这证明了用 WebGL 跑 Live2D 并配合前端生态是完全可以实
现高性能数字生命的。
○ 多模态与自主性：不仅仅是聊天，而是通过 CV（如 YOLO 结合 LLM）能看懂屏幕
（玩 Factorio、我的世界），这提醒我们，桌宠不能只有文字输入，需要有“视觉”和
“听觉”。
2. Claude Code & Codex 的启示（底层 Agent 运行机制）：
○ Sub-agent（子智能体）机制与上下文隔离：Claude Code 和 Codex 最核心的理念
是防止“上下文腐化 (Context Rot)”。如果让一个 Agent 做完所有事，它的 Context
Window 会被大量的 debug 日志、中间代码塞满，导致变傻。正确的做法是：主
Agent（你的桌宠老婆）只负责分发任务，她会在后台“Spawn（孵化）”专门的 Coder
、Tester 子智能体。子智能体在一个干净的、独立的上下文窗口里写代码，写完后只
把“总结和最终代码”返回给主 Agent。
○ Agentic Loop（智能体循环）：“收集上下文 -> 采取行动 -> 验证结果”。
3. MetaGPT & ChatDev 的启示（多智能体组织形式）：
○ SOP (Standard Operating Procedure) 驱动：MetaGPT 的核心哲学是 Code =
SOP(Team)。它不是让几个 AI 瞎聊，而是严格按照传统软件公司的流程：PM (写需求
PRD) -> Architect (写系统设计) -> Coder (写代码) -> QA (写测试)。
○ 角色扮演 (Role-Playing)：这非常适合你们的项目。你的“老婆”既是前台交互的看板
娘，也是这家“一人公司”的老板 (CEO/PM)，后台则是无数个不可见的“牛马 Agent”。
第二部分：全流程系统架构蓝图（系统怎么分层？）
根据上述理念，我们的项目应该采用前后端分离 + 微服务化的思想，分为四大层：
1. 表现层 (Frontend - "The Cyber Waifu")
这是用户直接感知到的桌面应用，负责所有的视觉、听觉和物理交互。
● 核心框架：HTML5 + TypeScript + React/Vue。


---

## Page 2

● 二次元渲染核心：Live2D Cubism Web Framework 结合 PixiJS。负责加载模型，处理口型
同步 (Lip-sync)、眨眼、鼠标视线跟随。
● 桌面端打包：
○ Electron：生态好，开发快，适合快速出 Demo。（但占用内存较大）
○ Tauri (推荐)：如果你们组有人懂一点 Rust，强烈推荐 Tauri。它的体积只有 Electron
的十分之一，内存占用极低，因为后台多智能体已经很吃性能了，前端要尽量轻量。
● 系统级交互：实现窗口透明 (Transparent Window)、无边框 (Frameless)、鼠标事件穿透
(Click-through)（点到老婆身体是抚摸，点到透明背景可以点击后面的桌面图标）。
2. 通信与调度层 (Middleware - The Bridge)
前端老婆和后台公司的沟通桥梁，必须是双向、实时的。
● 核心协议：WebSocket(绝对不能用 HTTP 短轮询，因为写代码是一个持续且不断有中间
状态输出的过程)。
● 状态映射流：后端不仅要传文字，还要传状态码。例如，后台 Coder Agent 在报错时，通
过 WebSocket 发送 {"status": "debugging", "msg": "遇到 Bug 啦..."}，前端收到后，触发
Live2D 模型的“皱眉/生气/冒汗”动画。
● 语音/视觉插件 (可选进阶)：接入 TTS（文本转语音，如 Edge-TTS 或 VITS 模型）让老婆说
话；接入屏幕捕获 API 让老婆能“看”到你的屏幕代码。
3. 业务逻辑层 (Backend - "The Agent Company")
这是项目的核心大脑，一个基于 Python 的多智能体工作流。
● 框架选择：直接使用MetaGPT进行二次开发，或者用LangGraph / AutoGen自己搭一
个有向无环图 (DAG) 的工作流。
● 角色设计方案：
○ 总控/老板 Agent (The Waifu Agent)：唯一与用户对话的 Agent。她负责理解你的自
然语言需求（“老婆，帮我写个贪吃蛇”），拆解成任务清单。
○ 架构师 Agent (Architect)：负责输出系统结构、文件目录结构树。
○ 程序员 Agent (Coder)：负责在这个目录下不断生成具体的 .py 或 .js 文件。
○ 测试员 Agent (Reviewer/QA)：负责执行代码，捕捉报错信息 (Traceback)，并把报
错丢回给 Coder 修改。
● 记忆机制：挂载一个轻量级向量数据库（如 ChromaDB 或本地的 SQLite+Faiss），让整个
团队拥有“记忆”，能读懂现有的代码库（类似于 Claude Code 的 Repository 检索）。
4. 基础设施层 (Environment - The Sandbox)
AI 生成的代码具有不确定性，绝对不能让 AI Agent 直接在你的物理机系统上裸跑 rm -rf甚至执
行危险脚本！
● 代码执行沙盒：必须使用 Docker 容器或轻量级虚拟机 (如 Firecracker)。后台 QAAgent
运行测试代码时，通过 API 把代码扔进 Docker 里跑，把 Docker 返回的 Stdout/Stderr 抓取
出来进行分析。


---

## Page 3

第三部分：全流程开发实战步骤（Roadmap）
为了保证课程项目能稳步落地，建议你们按照以下五个冲刺阶段 (Sprints) 来开发：
Sprint 1: MVP 最小可行性桌宠 (Week 1-2)
目标：跑通“前端 Live2D + 桌面透明窗口 + 简单的 LLM 对话”。
1. 下载开源的 Live2D 模型。
2. 用 Vite + Vue/React 搭建 Web 项目，跑通 PixiJS + Live2D，让模型动起来。
3. 引入 Electron 或 Tauri，配置 transparent: true 和 frame: false，把它变成一个桌面的透明
悬浮窗。
4. 写一个简单的 Python 后端，接通一个大模型 API（如 DeepSeek-V3 或 Kimi，便宜且好
用），通过 WebSocket 建立前后端聊天机制。
Sprint 2: 搭建后台“一人公司”架构 (Week 3-4)
目标：脱离单轮对话，实现长流程的自动化代码生成。
1. 引入 LangGraph 或 MetaGPT。
2. 编写 System Prompts，定义三个核心角色：PM（需求分析）、Coder（写代码）、QA
（运行报错反馈）。
3. 构建工作流机制 (Workflow)：
○ PM 拿到需求 -> 生成 tasks.json。
○ Coder 遍历 tasks.json -> 生成代码文本。
○ QA 拿到代码文本 -> （暂不执行）直接让 LLM 审查语法。
Sprint 3: 赋予 Agent 物理世界的双手 (Week 5)
目标：让 Agent 能够真正读写本地文件和执行终端命令。
1. 工具调用 (Tool Calling)：为 Agent 编写 Python 函数工具，例如 read_file(path)，
write_file(path, content)，run_command(cmd)。
2. 配置 Docker 沙盒，确保 run_command 是在一个安全的环境里执行的。
3. 跑通闭环：让系统尝试写一个简单的计算器脚本，保存到硬盘，执行，报错，自我修复，
最后输出成功。
Sprint 4: 灵魂注入与前后端联动 (Week 6)
目标：将干瘪的后台状态转化为二次元老婆的生动演绎。
1. 定义状态机：在后端的 Agent 工作流中埋点。
○ 开始写代码 -> 触发 "status": "coding"。
○ 遇到报错、重试超过 3 次 -> 触发 "status": "frustrated"。
○ 顺利完成并测试通过 -> 触发 "status": "happy"。
2. 前端响应：前端 WebSocket 监听到状态变更，调用 Live2D 框架的 setExpression或
startMotion API。
○ “Coding”时，老婆头上出现进度条，手部敲击键盘。


---

## Page 4

○ “Frustrated”时，老婆嘟嘴、叹气。
Sprint 5: 润色与高级功能（加分项）
1. 语音模块 (Voice)：接入 VITS 语音合成，让桌宠可以用特定的萝莉/御姐音向你汇报开发进
度。
2. 记忆系统 (Memory)：让她记住你之前叫她写过的项目，下次可以说“在这基础之上加个新
功能”。
第四部分：避坑指南（关键提醒）
1. 不要试图让一个 Prompt 解决所有问题：
○ 灾难做法：“你是一个全能程序员老婆，请帮我写个网站，包含前后端，并且不要报
错。” —— 这样模型绝对会幻觉、写出一半中断。
○ 正确做法（Claude Code 核心机理）：主 Agent 必须学会任务拆解。每次只让
Coder Agent 生成一个模块，并且让 QA Agent 验证。
2. Electron 鼠标穿透的玄学：
○ 在 Windows 下，setIgnoreMouseEvents API 有时会有 bug，导致整个区域都点不中
或者都穿透。你们需要精确计算 Live2D 角色像素的 Alpha 通道透明度，只有在
Alpha=0（完全透明）的地方才允许鼠标穿透到底层桌面。
3. 输出流的解析 (Parsing)：
○ Coder Agent 输出的往往不仅是代码，还有前言后语（"Here is the code... python ...
Hope this helps!"）。必须写一个强壮的正则表达式或利用模型的 JSON 强制输出模式
(JSON Mode)，精准提取出纯代码，否则写到文件里全会报语法错误。
你们的这个项目不仅涵盖了前端图形学 (Live2D)、跨平台客户端开发 (Electron/Tauri)，更深度
融合了最前沿的 LLM Multi-Agent 架构和系统安全 (Sandbox)，如果能够做出来，绝对会是极为
出色的高分大作业，甚至可以直接开源在 GitHub 上冲击几千个 Star。祝你们开发顺利！需要深
入讨论某一个模块（比如 LangGraph 怎么搭，或者 Live2D 怎么导）随时告诉我。
