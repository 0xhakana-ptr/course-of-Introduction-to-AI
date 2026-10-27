#!/usr/bin/env python3
"""Build Nature-style Chinese PPTX — v2: correct aspect ratios + specific content."""
import os, shutil
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

FIG_DIR = os.path.join(os.path.dirname(__file__), "..", "figures")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
ASSET_DIR = os.path.join(OUT_DIR, "assets", "figures")
os.makedirs(ASSET_DIR, exist_ok=True)

SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
DARK_TEXT = RGBColor(0x1A, 0x1A, 0x2E)
ACCENT = RGBColor(0x2D, 0x6A, 0x4F)
ACCENT2 = RGBColor(0x3D, 0x7E, 0xAA)
CAPTION_CLR = RGBColor(0x66, 0x66, 0x66)
SOURCE_CLR = RGBColor(0x99, 0x99, 0x99)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GREEN = RGBColor(0xE8, 0xF5, 0xE9)
RED_ACCENT = RGBColor(0xC6, 0x28, 0x28)
FONT_CN = "Microsoft YaHei"
FONT_EN = "Calibri"


def fig_size(name, max_w, max_h):
    """Return (w, h) in Inches preserving original aspect ratio."""
    path = os.path.join(FIG_DIR, name)
    img = Image.open(path)
    iw, ih = img.size
    scale = min(max_w / iw, max_h / ih)
    return Inches(iw * scale), Inches(ih * scale)


def set_bg(slide, color=None):
    if color is None:
        color = RGBColor(0xFA, 0xFA, 0xFA)
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def tb(slide, l, t, w, h, text, sz=14, bold=False, clr=DARK_TEXT,
       align=PP_ALIGN.LEFT, fn=FONT_CN, lsp=1.2):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(sz)
    p.font.bold = bold
    p.font.color.rgb = clr
    p.font.name = fn
    p.alignment = align
    p.space_after = Pt(0)
    p.line_spacing = Pt(sz * lsp)
    return box


def ml(slide, l, t, w, h, lines, sz=14, clr=DARK_TEXT, bold=False, lsp=1.3,
       align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(l, t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = line
        p.font.size = Pt(sz)
        p.font.bold = bold
        p.font.color.rgb = clr
        p.font.name = FONT_CN
        p.alignment = align
        p.space_after = Pt(4)
        p.line_spacing = Pt(sz * lsp)
    return box


def add_fig(slide, name, left, top, max_w, max_h, caption=None, src=None):
    w, h = fig_size(name, max_w, max_h)
    path = os.path.join(FIG_DIR, name)
    dst = os.path.join(ASSET_DIR, name)
    if os.path.exists(path) and not os.path.exists(dst):
        shutil.copy2(path, dst)
    slide.shapes.add_picture(path, left, top, w, h)
    cy = top + h
    if caption:
        tb(slide, left, cy + Inches(0.06), w, Inches(0.35), caption,
           sz=9, clr=CAPTION_CLR)
    if src:
        tb(slide, left, cy + Inches(0.28) if caption else cy + Inches(0.06),
           w, Inches(0.22), src, sz=7, clr=SOURCE_CLR, align=PP_ALIGN.RIGHT)
    return w, h


def accent_bar(s, l, t, w=Inches(0.08), h=Inches(0.6)):
    sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    sh.fill.solid()
    sh.fill.fore_color.rgb = ACCENT
    sh.line.fill.background()


def bottom_strip(s, text, sz=10):
    tb(s, Inches(0.6), Inches(6.9), Inches(12.0), Inches(0.4), text,
       sz=sz, clr=ACCENT, bold=True)


def sn(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def snum(slide, n, total=12):
    tb(slide, Inches(12.5), Inches(7.1), Inches(0.6), Inches(0.3),
       f"{n}/{total}", sz=7, clr=SOURCE_CLR, align=PP_ALIGN.RIGHT)


# ============================================================
prs = Presentation()
prs.slide_width = SLIDE_W
prs.slide_height = SLIDE_H
BL = prs.slide_layouts[6]

# ---- 1: Title ----
s = prs.slides.add_slide(BL); set_bg(s, RGBColor(0x1A, 0x1A, 0x2E))
tb(s, Inches(1.0), Inches(1.6), Inches(11.3), Inches(1.5),
   "面向桌面场景的多模态分层智能体", sz=38, bold=True, clr=WHITE)
tb(s, Inches(1.0), Inches(3.0), Inches(11.3), Inches(0.8),
   "意图识别、视觉感知与工作流编排", sz=24,
   clr=RGBColor(0xA0, 0xC4, 0xB0))
sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(4.1),
                        Inches(3.0), Pt(3))
sh.fill.solid(); sh.fill.fore_color.rgb = ACCENT; sh.line.fill.background()
tb(s, Inches(1.0), Inches(4.5), Inches(5.0), Inches(0.5),
   "叶宇", sz=18, clr=WHITE)
tb(s, Inches(1.0), Inches(5.1), Inches(8.0), Inches(0.5),
   "Introduction to Artificial Intelligence · Final Project",
   sz=12, clr=RGBColor(0x99,0x99,0x99), fn=FONT_EN)
sn(s, "报告开场。论文题目：面向桌面场景的多模态分层智能体。作者：叶宇。")
snum(s, 1)

# ---- 2: Background — specific evidence ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "桌面场景对智能体提出多模态感知、意图识别与工作流三重需求", sz=24, bold=True)
lines = [
    "  LLM 智能体生态：LangChain（链式工具编排）、AutoGPT（全自主循环）、",
    "      MetaGPT（多角色 SOP 协作）、Voyager（代码即动作空间）",
    "  桌面交互的独特挑战：文本输入 + 屏幕视觉双通道",
    "  用户意图跨度大：闲聊 / 代码编写 / 文件管理 / 系统维护",
    "  任务执行需多步骤编排：工具调用 → 条件判断 → 错误恢复",
]
ml(s, Inches(0.85), Inches(1.7), Inches(7.5), Inches(4.5), lines,
   sz=15, lsp=1.6)
# Right side: motivation numbers
tb(s, Inches(8.8), Inches(1.8), Inches(4.0), Inches(0.4),
   "关键痛点", sz=16, bold=True, clr=RED_ACCENT)
pain_points = [
    "1. 分层解耦缺失 → 模块紧耦合",
    "2. 意图识别延迟 vs 精度矛盾",
    "3. 屏幕信息未结构化利用",
    "4. 线性脚本无法表达任务依赖",
]
ml(s, Inches(8.8), Inches(2.4), Inches(4.0), Inches(3.0), pain_points,
   sz=13, clr=RGBColor(0x33,0x33,0x33), lsp=1.8)
bottom_strip(s, "核心问题：如何构建兼具多模态感知、高效意图识别与结构化工作流编排能力的桌面智能体？")
sn(s, "背景：LLM Agent 框架各自发展但缺乏桌面场景的分层设计。LangChain 编排工具但缺视觉感知；Computer Use 操控界面但依赖云端GPU；UFO/OS-Copilot 有分层但缺乏低延迟意图分类。")
snum(s, 2)

# ---- 3: Problem Statement — 4 gaps with specific detail ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "现有方案的四个结构性不足", sz=24, bold=True)
problems = [
    ("架构紧耦合", "意图/角色/执行逻辑混合 → 调整分类策略需重构整个系统"),
    ("分类策略单一", "规则方法泛化差（Rasa）；LLM 零样本分类延迟高（GPT-3）"),
    ("视觉未结构化", "屏幕原始图像直送 LLM → 无法复用 UI 结构信息"),
    ("工作流无图结构", "线性脚本/简单 if-else → 无法表达并行与复杂依赖"),
]
for i, (title, desc) in enumerate(problems):
    y = Inches(1.7) + Inches(i * 1.3)
    tb(s, Inches(0.85), y, Inches(0.5), Inches(0.5),
       f"0{i+1}", sz=26, bold=True, clr=ACCENT, fn=FONT_EN)
    tb(s, Inches(1.5), y, Inches(4.5), Inches(0.4),
       title, sz=17, bold=True)
    tb(s, Inches(1.5), y + Inches(0.42), Inches(7.0), Inches(0.5),
       desc, sz=13, clr=CAPTION_CLR)
bottom_strip(s, "本文提出三层解耦架构：路由层（关键词组合门控）+ 角色层（人设驱动）+ 工作引擎层（LangGraph 5子图）")
sn(s, "四个问题逐条展开。每个问题对应本系统的一个核心设计决策：解耦→三层架构，分类→组合门控，视觉→YOLOv8+活动画像，工作流→LangGraph图状态机。")
snum(s, 3)

# ---- 4: Architecture — figure with correct aspect ratio ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "三层解耦架构：路由层 → 角色层 → 工作引擎层", sz=24, bold=True)
add_fig(s, "architecture.png", Inches(1.2), Inches(1.5), Inches(10.8), Inches(4.2),
        caption="系统整体架构：路由层负责意图路由与视觉感知，角色层负责角色化输出，工作引擎层负责 LangGraph 图工作流编排",
        src="Source: Fig. 2, 本文")
tb(s, Inches(0.85), Inches(6.3), Inches(11.5), Inches(0.5),
   "各层通过 RoutingDecision / RoutingDecision / State 接口解耦，可独立替换与优化",
   sz=12, clr=CAPTION_CLR)
sn(s, "三层架构详解：\n路由层(Routing Guard)：关键词组合门控分类 + LLM参数抽取 → RoutingDecision对象\n角色层(Roleplay Agent)：双角色system prompt + 5状态情绪追踪 → 人设风格输出\n工作引擎层(Work Engine)：LangGraph有向图状态机 G=(V,E,S)，5个专用子图\n视觉感知：60秒周期后台轮询，YOLOv8推理 → 活动画像 → 角色俏皮话")
snum(s, 4)

# ---- 5: Keyword Gating — specific method detail ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "关键词组合门控：11类230词 × 布尔共现 = 零延迟意图分类", sz=24, bold=True)
w, h = add_fig(s, "keyword_gate_flowchart.png", Inches(0.5), Inches(1.5),
               Inches(7.0), Inches(5.5),
               caption="门控三阶段：空输入过滤 → 快速通道 → 8特征标志组合判定",
               src="Source: Fig. 3, 本文")
# Right column — specific numbers
tb(s, Inches(8.0), Inches(1.5), Inches(4.8), Inches(0.35),
   "门控设计细节", sz=15, bold=True, clr=ACCENT)
details = [
    "11 个语义类别：编程动词(60)、工作空间",
    "  名词(48)、技术栈(15)、CLI命令(11)、",
    "  错误信号(12) 等共约 230 个中英文关键词",
    "",
    "8 个布尔特征标志：",
    "  has_action / has_strong_action /",
    "  has_workspace_object / has_deliverable /",
    "  has_path / has_command / has_issue / has_tech",
    "",
    "判定规则：≥2 类别共现 → i_coding",
    "LLM 不参与分类，仅在分类后抽取参数",
    "temperature=0.1, max_tokens=30000",
]
ml(s, Inches(8.0), Inches(1.95), Inches(4.8), Inches(5.0), details,
   sz=12, clr=RGBColor(0x33,0x33,0x33), lsp=1.35)
bottom_strip(s, "决策函数: intent(x) = unknown(if blank) | coding(if gate=True) | chat(otherwise)")
sn(s, "关键词组合门控核心创新：\n- 不是单关键词匹配（B1），不是单类别命中（B3），而是要求≥2个语义类别共现\n- 空输入→unknown, 快速通道(文件引用/代码结构)→coding, 否则提取8个布尔标志\n- 优先级判定：issue+(obj|cmd|tech) → action+(obj|deliverable|path|cmd) → strong_action+(tech|deliverable)\n- 这种设计避免了\"写字\"中\"写\"的误触发（需要同时命中编程动词+工作空间名词）")
snum(s, 5)

# ---- 6: LLM Parameter Extraction + Action Matching ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "LLM 结构化参数抽取 + 优先级动作匹配", sz=24, bold=True)
# Left: JSON schema figure
w, h = add_fig(s, "json_schema_tree.png", Inches(0.5), Inches(1.5),
               Inches(6.5), Inches(4.5),
               caption="LLM 参数抽取 JSON Schema 结构：9 种动作类型及其参数字段",
               src="Source: Fig. 4, 本文")
# Right: action table
action_data = [
    ["动作", "抽取方式", "优先级"],
    ["workspace.write", "LLM", "Tier 1"],
    ["workspace.delete", "LLM", "Tier 1"],
    ["workspace.move/copy", "LLM", "Tier 1"],
    ["workspace.test/search", "LLM", "Tier 2"],
    ["workspace.read", "规则→LLM", "Tier 3"],
    ["workspace.list", "纯规则", "Tier 4"],
    ["run.create", "LLM", "Tier 2"],
]
tbl = s.shapes.add_table(len(action_data), 3,
                         Inches(7.5), Inches(1.5), Inches(5.2), Inches(3.2)).table
tbl.columns[0].width = Inches(2.2)
tbl.columns[1].width = Inches(1.5)
tbl.columns[2].width = Inches(1.5)
for r, row in enumerate(action_data):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(11)
            p.font.name = FONT_CN
            p.alignment = PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT
            if r == 0:
                p.font.bold = True; p.font.color.rgb = WHITE
            else:
                p.font.color.rgb = DARK_TEXT
        if r == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT
        elif r % 2 == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0xF0,0xF4,0xF0)
# Priority equation
tb(s, Inches(7.5), Inches(5.0), Inches(5.2), Inches(1.5),
   "优先级序列:\nWRITE ≻ DELETE ≻ MOVE ≻ COPY ≻ TEST ≻ SEARCH ≻ READ ≻ LIST\n\nTier 1: 不可逆/高风险 → 始终调用LLM\nTier 3: workspace.read → 正则优先,LLM回退",
   sz=11, clr=CAPTION_CLR, lsp=1.4)
sn(s, "LLM参数抽取设计：\n意图分类完成后，对coding意图调用LLM抽取结构化参数。\n参数抽取决策函数：params(x,a) = LLM_extract(x,a) if needs_extraction(a) else rule_extract(x)\n温度0.1确保确定性输出。9种动作类型分4个优先级层级。\n动作匹配优先级序列用于消歧：当用户输入匹配多个潜在动作时，取最高优先级。")
snum(s, 6)

# ---- 7: YOLOv8 Visual Pipeline — specific numbers ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "YOLOv8 视觉感知：12MB ONNX 模型，CPU 推理 1-2 秒", sz=24, bold=True)
w, h = add_fig(s, "yolo_pipeline.png", Inches(0.5), Inches(1.5),
               Inches(12.3), Inches(2.2),
               caption="YOLOv8 推理管线：I∈R^(H×W×3) → Resize(640) → /255 → 模型 → O∈R^(1×10×8400)",
               src="Source: Fig. 5, 本文")
# Two columns below
# Left: detection pipeline detail
tb(s, Inches(0.85), Inches(4.0), Inches(5.5), Inches(0.35),
   "检测管线技术细节", sz=14, bold=True, clr=ACCENT)
pipeline_detail = [
    "模型: 微调 YOLOv8 (ONNX, 12 MB)",
    "输出: O∈R^(1×10×8400)，10 = 4(bbox) + 6(类别)",
    "Anchor-free 解耦头：类别得分直接作为置信度",
    "6 类: activewindow / address bar / folder",
    "      menubar / tab / window",
    "置信度阈值 τ=0.4，不执行 NMS",
    "60 秒轮询周期，MD5 去重冷却 120 秒",
]
ml(s, Inches(0.85), Inches(4.4), Inches(5.5), Inches(2.8), pipeline_detail,
   sz=12, clr=RGBColor(0x33,0x33,0x33), lsp=1.4)
# Right: activity mapping
tb(s, Inches(7.0), Inches(4.0), Inches(5.5), Inches(0.35),
   "活动画像映射规则（首次匹配）", sz=14, bold=True, clr=ACCENT)
act_data = [
    ["UI 元素条件", "活动标签", "情绪"],
    ["tab≥3 + activewindow≥1", "browsing", "neutral"],
    ["activewindow≥1 + menubar≥1", "using app", "neutral"],
    ["folder≥2", "managing files", "neutral"],
    ["tab≥5", "deep in research", "focused"],
    ["activewindow≥3", "multitasking", "focused"],
    ["检测≥2 但无匹配", "using computer", "neutral"],
    ["检测<2", "minimal", "neutral"],
    ["无检测结果", "idle", "lonely"],
]
tbl = s.shapes.add_table(len(act_data), 3,
                         Inches(7.0), Inches(4.4), Inches(5.8), Inches(2.8)).table
tbl.columns[0].width = Inches(2.6)
tbl.columns[1].width = Inches(1.6)
tbl.columns[2].width = Inches(1.6)
for r, row in enumerate(act_data):
    for c, val in enumerate(row):
        cell = tbl.cell(r, c)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(10)
            p.font.name = FONT_CN
            if r == 0:
                p.font.bold = True; p.font.color.rgb = WHITE
            else:
                p.font.color.rgb = DARK_TEXT
        if r == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT
        elif r % 2 == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = RGBColor(0xF0,0xF4,0xF0)
sn(s, "YOLOv8视觉感知管线：\n输入I∈R^(H×W×3) → Resize(640,640) → 归一化 → YOLOv8 ONNX推理\n输出张量O∈R^(1×10×8400)，第二维10=4(bbox坐标)+6(类别得分)\n不执行NMS(目的为活动分析非精确定位)，直接取各类别argmax得分\n6类桌面UI元素通过置信度阈值τ=0.4过滤\n活动画像映射：首次匹配策略，6条主规则+3条回退规则")
snum(s, 7)

# ---- 8: Visual Detection Demo — 3 cases ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "视觉感知将屏幕状态转化为情境化角色对话", sz=24, bold=True)
# Three figures side by side with correct aspect ratios
fig_w_max = Inches(3.8)
fig_h_max = Inches(3.2)
gap = Inches(0.25)
sx = Inches(0.85)
fy = Inches(1.6)
w1, h1 = add_fig(s, "yolo_detection_case1.png", sx, fy, fig_w_max, fig_h_max,
                  caption="(a) tab×5, activewindow×1 → deep in research",
                  src="Source: Fig. 7a")
w2, h2 = add_fig(s, "yolo_detection_case2.png", sx + w1 + gap, fy,
                  fig_w_max, fig_h_max,
                  caption="(b) folder×3, address bar×1 → navigating files",
                  src="Source: Fig. 7b")
w3, h3 = add_fig(s, "yolo_detection_case3.png", sx + w1 + gap + w2 + gap, fy,
                  fig_w_max, fig_h_max,
                  caption="(c) 无检测结果 → idle",
                  src="Source: Fig. 7c")
# Comparison at bottom
tb(s, Inches(0.85), Inches(5.3), Inches(11.5), Inches(0.35),
   "视觉上下文对比", sz=14, bold=True, clr=ACCENT)
comp_lines = [
    "  有视觉感知: \"开这么多标签，CPU 都要哭了~\" (worried)  ← 检测到 tab×5",
    "  无视觉感知: \"嗯嗯，本机在听呢\" (neutral)              ← 通用回复",
    "  视觉感知显著提升了交互的情境相关性与桌面陪伴感",
]
ml(s, Inches(0.85), Inches(5.7), Inches(11.5), Inches(1.5), comp_lines,
   sz=13, clr=RGBColor(0x33,0x33,0x33), lsp=1.5)
sn(s, "三个典型案例展示视觉感知的核心价值：\nCase1: 5个标签页+1个活动窗口 → deep in research → 角色说\"CPU都要哭了\"\nCase2: 3个文件夹+地址栏 → navigating files → 角色主动提供帮助\nCase3: 空闲屏幕无检测 → idle → 角色求关注\"不理我要没电了\"\n视觉感知通过RoleplayAgent.emit_vision_quip()方法集成到角色对话中")
snum(s, 8)

# ---- 9: LangGraph — specific subgraph detail ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "LangGraph 图工作流：5 子图覆盖任务全生命周期", sz=24, bold=True)
w, h = add_fig(s, "langgraph_topology.png", Inches(0.8), Inches(1.5),
               Inches(11.7), Inches(3.5),
               caption="5 个子图的拓扑结构与调用关系",
               src="Source: Fig. 6, 本文")
# Subgraph details in two columns
sg_left = [
    "Agent Loop (6节点, 主控循环):",
    "  plan→act→observe→decide (最大15步)",
    "Coding Workflow (8节点):",
    "  PM→Coder(LLM Planner)→Executor→finish",
    "  失败: QA→debugger(规则修复,最大1步)→retry",
]
sg_right = [
    "File Workflow (5节点):",
    "  9种操作: read/write/list/move/copy/",
    "  delete/search/test/export_desktop",
    "Repair Decision (6节点):",
    "  inspect→eligibility→QA→decision→feedback→codegen",
    "Summary: 运行完成/单次尝试后生成LLM摘要",
]
ml(s, Inches(0.85), Inches(5.2), Inches(5.8), Inches(2.0), sg_left,
   sz=11, clr=RGBColor(0x33,0x33,0x33), lsp=1.35)
ml(s, Inches(7.0), Inches(5.2), Inches(5.8), Inches(2.0), sg_right,
   sz=11, clr=RGBColor(0x33,0x33,0x33), lsp=1.35)
# Execution environment note
tb(s, Inches(0.85), Inches(6.8), Inches(11.5), Inches(0.4),
   "执行安全: subprocess.Popen(shell=False), 阻塞shell解释器, 阻塞危险参数(rm/del/format), 路径穿越保护",
   sz=10, clr=SOURCE_CLR)
sn(s, "LangGraph图工作流详解：\n有向图状态机 G=(V,E,S)。\nAgent Loop: plan_node构建计划→act_node分发→observe_node评估→decide_continue_node检查步数上限\nCoding Workflow: coder_node使用LLM Planner生成JSON执行计划，不可用时回退规则引擎\nFile Workflow: observer_node将结果合并到上下文状态\nRepair Decision: 支持循环修复，直到成功、预算耗尽或用户取消")
snum(s, 9)

# ---- 10: Memory System ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "Hermes 风格记忆系统：滑动窗口事件存储 + 情绪追踪", sz=24, bold=True)
w, h = add_fig(s, "memory_sliding_window.png", Inches(0.5), Inches(1.5),
               Inches(7.0), Inches(4.5),
               caption="记忆滑动窗口: maxlen=12 deque, build_context() 格式化注入",
               src="Source: Fig. 7, 本文")
# Right: emotion + memory detail
tb(s, Inches(8.0), Inches(1.5), Inches(4.8), Inches(0.35),
   "记忆事件结构", sz=14, bold=True, clr=ACCENT)
mem_detail = [
    "m_t = (turn_index, timestamp,",
    "  user_input, intent, action_name,",
    "  result_summary, ok, error)",
    "",
    "存储: dict[str, deque[MemoryEvent]]",
    "窗口: MAX_RECENT_EVENTS = 12",
    "索引: session_id",
    "",
    "情绪系统 (5 状态):",
    "  happy / neutral / frustrated",
    "  tired / lonely",
    "  连续成功/失败/闲置自动流转",
    "  {mood_modifier} 注入 system prompt",
    "",
    "⚠ 记忆仅存内存，无磁盘持久化",
]
ml(s, Inches(8.0), Inches(1.95), Inches(4.8), Inches(5.0), mem_detail,
   sz=12, clr=RGBColor(0x33,0x33,0x33), lsp=1.35)
bottom_strip(s, "双角色系统: 主角色「未命名」(混沌善桌面精灵) + 聊天角色「Shion」(纯对话拟人化)")
sn(s, "记忆与情绪系统：\nHermes风格结构化记忆事件，每轮对话结束后自动记录\nbuild_context()将最近12条事件格式化为文本注入LLM上下文\n5状态情绪追踪器：根据任务执行结果自动流转\n两个角色系统提示：主角色要求JSON输出(chat_line/expression/quip/motion)，聊天角色为简化人设")
snum(s, 10)

# ---- 11: Results — specific numbers ----
s = prs.slides.add_slide(BL); set_bg(s)
accent_bar(s, Inches(0.6), Inches(0.8))
tb(s, Inches(0.85), Inches(0.7), Inches(11.0), Inches(0.6),
   "实验: 401条测试集验证组合门控安全性优先设计", sz=24, bold=True)
# Dataset table
tb(s, Inches(0.85), Inches(1.5), Inches(4.5), Inches(0.35),
   "测试集构成 (401条)", sz=13, bold=True, clr=ACCENT)
ds_data = [
    ["来源", "chat", "coding", "unknown", "合计"],
    ["手工构造", "80", "100", "20", "200"],
    ["部署日志", "81", "90", "30", "201"],
    ["合计", "161", "190", "50", "401"],
]
tbl1 = s.shapes.add_table(4, 5, Inches(0.85), Inches(1.9), Inches(5.0), Inches(1.5)).table
for r, row in enumerate(ds_data):
    for c, val in enumerate(row):
        cell = tbl1.cell(r, c)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(11); p.font.name = FONT_EN if c > 0 else FONT_CN
            p.alignment = PP_ALIGN.CENTER
            if r == 0 or r == 3:
                p.font.bold = True; p.font.color.rgb = WHITE
            else:
                p.font.color.rgb = DARK_TEXT
        if r == 0 or r == 3:
            cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT

# Results table
tb(s, Inches(6.5), Inches(1.5), Inches(6.0), Inches(0.35),
   "整体性能对比", sz=13, bold=True, clr=ACCENT)
res_data = [
    ["方法", "Precision", "Recall", "F1", "Acc", "延迟"],
    ["B1: Rule-Only", "0.558", "0.631", "0.778", "0.828", "0.003ms"],
    ["B3: Score≥1", "0.895", "0.641", "0.788", "0.835", "0.020ms"],
    ["Ours", "0.858", "0.608", "0.685", "0.701", "0.020ms"],
]
tbl2 = s.shapes.add_table(4, 6, Inches(6.5), Inches(1.9), Inches(6.2), Inches(1.5)).table
tbl2.columns[0].width = Inches(1.5)
for r, row in enumerate(res_data):
    for c, val in enumerate(row):
        cell = tbl2.cell(r, c)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(11); p.font.name = FONT_EN if c > 0 else FONT_CN
            p.alignment = PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT
            if r == 0:
                p.font.bold = True; p.font.color.rgb = WHITE
            elif r == 3:
                p.font.bold = True; p.font.color.rgb = ACCENT
            else:
                p.font.color.rgb = DARK_TEXT
        if r == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT
        elif r == 3:
            cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT_GREEN

# Per-class F1 chart
tb(s, Inches(0.85), Inches(3.8), Inches(5.5), Inches(0.35),
   "各类别 F1 值", sz=13, bold=True, clr=ACCENT)
pc_data = [
    ["方法", "F1(chat)", "F1(coding)", "F1(unknown)", "Weighted"],
    ["B1: Rule-Only", "0.817", "0.949", "0.000", "0.778"],
    ["B3: Score≥1", "0.824", "0.955", "0.039", "0.788"],
    ["Ours", "0.729", "0.721", "0.413", "0.685"],
]
tbl3 = s.shapes.add_table(4, 5, Inches(0.85), Inches(4.2), Inches(5.5), Inches(1.5)).table
for r, row in enumerate(pc_data):
    for c, val in enumerate(row):
        cell = tbl3.cell(r, c)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(11); p.font.name = FONT_EN if c > 0 else FONT_CN
            p.alignment = PP_ALIGN.CENTER if c > 0 else PP_ALIGN.LEFT
            if r == 0:
                p.font.bold = True; p.font.color.rgb = WHITE
            elif r == 3 and c == 3:
                p.font.bold = True; p.font.color.rgb = ACCENT
            else:
                p.font.color.rgb = DARK_TEXT
        if r == 0:
            cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT
        elif r == 3:
            cell.fill.solid(); cell.fill.fore_color.rgb = LIGHT_GREEN

# Key insight
tb(s, Inches(7.0), Inches(3.8), Inches(5.5), Inches(2.8),
   "关键发现:\n\n"
   "Ours F1(0.685) < B3(0.788)\n"
   "→ 190条coding中29条仅命中\n"
   "   单类别被误判为chat\n\n"
   "但 F1(unknown): 0.413 vs 0.039\n"
   "→ 提升0.374, 过滤噪声能力↑\n\n"
   "设计权衡: 安全性 > 召回率\n"
   "避免闲聊误触发代码生成",
   sz=12, clr=RGBColor(0x33,0x33,0x33), lsp=1.3)
bottom_strip(s, "端到端: 20个编码任务准确率80%(16/20), 失败案例与Rule-Only相同 → 无额外漏判")
sn(s, "实验设置：401条中文测试集(200手工+201日志)，3类意图(chat/coding/unknown)\nB1: 任一关键词子串匹配→coding, B3: ≥1类别命中→coding, Ours: ≥2类别共现→coding\n主结果：组合门控加权F1(0.685)低于基线，因为29条单类别coding被误判\n但unknown类F1=0.413远超基线(B1:0, B3:0.039)，体现安全性优先权衡\n端到端20任务测试证明明确编码请求无额外漏判")
snum(s, 11)

# ---- 12: Conclusion ----
s = prs.slides.add_slide(BL); set_bg(s, RGBColor(0x1A, 0x1A, 0x2E))
tb(s, Inches(1.0), Inches(0.6), Inches(10.0), Inches(0.6),
   "总结与贡献", sz=28, bold=True, clr=WHITE)
sh = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(1.3),
                        Inches(2.0), Pt(3))
sh.fill.solid(); sh.fill.fore_color.rgb = ACCENT; sh.line.fill.background()

contribs = [
    "1. 三层解耦架构：路由层 + 角色层 + 工作引擎层，通过数据接口解耦，各层独立迭代",
    "2. 关键词组合门控：11类230词布尔共现，零LLM调用，路由延迟0.020ms，",
    "     unknown类F1提升0.374（安全性优先设计权衡）",
    "3. YOLOv8视觉感知：12MB ONNX模型CPU推理，6类UI元素检测，",
    "     6种活动画像映射，60秒轮询周期",
    "4. LangGraph工作流：5子图有向图状态机，覆盖代码生成/文件操作/故障修复",
    "5. 原型验证：401条测试用例，各模块协作正常，具备实际应用价值",
]
ml(s, Inches(1.0), Inches(1.8), Inches(11.0), Inches(4.0), contribs,
   sz=16, clr=WHITE, lsp=1.6)

tb(s, Inches(1.0), Inches(5.8), Inches(11.0), Inches(0.8),
   "局限: 记忆无持久化 / 仅6类UI检测 / 无沙箱执行 / 情绪系统非per-session",
   sz=13, clr=RGBColor(0x88,0xAA,0x99))
tb(s, Inches(1.0), Inches(6.5), Inches(11.0), Inches(0.5),
   "谢谢！", sz=26, bold=True, clr=RGBColor(0xA0,0xC4,0xB0))
sn(s, "总结五大贡献，强调工程完整性。四条局限作为诚实表述。")
snum(s, 12)

# Save
output_path = os.path.join(OUT_DIR, "final_presentation_cn.pptx")
prs.save(output_path)
print(f"Saved: {output_path}")
print(f"Slides: {len(prs.slides)}")
