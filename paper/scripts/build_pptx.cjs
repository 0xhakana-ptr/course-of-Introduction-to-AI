const pptxgen = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.3" x 7.5"
pres.author = "Ye Yu";
pres.title = "面向桌面场景的多模态分层智能体";

// ── Palette: Teal Trust ──
const C = {
  dark:    "0B1D33",  // dark navy (title bg)
  primary: "028090",  // teal
  sea:     "00A896",  // seafoam
  mint:    "02C39A",  // mint accent
  white:   "FFFFFF",
  offwhite:"F7FAFA",
  text:    "1A1A2E",
  muted:   "5A6B7A",
  lightBg: "F0F6F4",
  cardBg:  "E8F4F0",
  red:     "C0392B",
};

const FONT_H = "Georgia";
const FONT_B = "Calibri";
const FIG = path.join(__dirname, "..", "figures");

function imgSize(name, maxW, maxH) {
  // Read PNG header to get dimensions
  const buf = fs.readFileSync(path.join(FIG, name));
  const w = buf.readUInt32BE(16);
  const h = buf.readUInt32BE(20);
  const scale = Math.min(maxW / w, maxH / h);
  return { w: Math.round(w * scale * 100) / 100, h: Math.round(h * scale * 100) / 100 };
}

function figPath(name) { return path.join(FIG, name).replace(/\\/g, "/"); }

// ══════════════════════════════════════════════════════════════
// SLIDE 1: TITLE — dark bg, centered title
// ══════════════════════════════════════════════════════════════
let s1 = pres.addSlide();
s1.background = { color: C.dark };
// Large title
s1.addText("面向桌面场景的多模态分层智能体", {
  x: 0.8, y: 1.8, w: 11.7, h: 1.5,
  fontSize: 40, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
s1.addText("意图识别、视觉感知与工作流编排", {
  x: 0.8, y: 3.3, w: 11.7, h: 0.8,
  fontSize: 22, fontFace: FONT_B, color: C.mint, align: "left", margin: 0
});
// Thin mint line
s1.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 4.4, w: 2.5, h: 0.04, fill: { color: C.mint } });
// Author
s1.addText("叶宇", {
  x: 0.8, y: 4.8, w: 5, h: 0.6,
  fontSize: 20, fontFace: FONT_B, color: C.white, align: "left", margin: 0
});
s1.addText("Introduction to Artificial Intelligence · Final Project", {
  x: 0.8, y: 5.4, w: 8, h: 0.5,
  fontSize: 13, fontFace: FONT_B, color: C.muted, align: "left", margin: 0
});
// Teal decorative block on right
s1.addShape(pres.shapes.RECTANGLE, { x: 11.5, y: 0, w: 1.833, h: 7.5, fill: { color: C.primary, transparency: 30 } });
s1.addShape(pres.shapes.RECTANGLE, { x: 12.3, y: 0, w: 1.033, h: 7.5, fill: { color: C.sea, transparency: 50 } });
s1.addNotes("论文报告开场。标题：面向桌面场景的多模态分层智能体。作者：叶宇。");

// ══════════════════════════════════════════════════════════════
// SLIDE 2: BACKGROUND — problem setup with stat callout
// ══════════════════════════════════════════════════════════════
let s2 = pres.addSlide();
s2.background = { color: C.white };
// Left accent bar (motif)
s2.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s2.addText("桌面智能体需要三重能力：感知、识别、编排", {
  x: 0.6, y: 0.4, w: 12, h: 0.8,
  fontSize: 28, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
// Big stat callout on left
s2.addText("4", {
  x: 0.6, y: 1.6, w: 2.5, h: 2.0,
  fontSize: 96, fontFace: FONT_H, color: C.primary, bold: true, align: "center", margin: 0
});
s2.addText("个结构性不足", {
  x: 0.6, y: 3.4, w: 2.5, h: 0.5,
  fontSize: 14, fontFace: FONT_B, color: C.muted, align: "center", margin: 0
});
// Right column: 4 problems as icon+text rows
const problems = [
  ["架构紧耦合", "意图/角色/执行混合 → 调整策略需重构系统"],
  ["分类策略单一", "规则方法泛化差; LLM 零样本延迟高"],
  ["视觉未结构化", "屏幕原始图像直送 LLM → 无法复用 UI 信息"],
  ["工作流无图结构", "线性脚本 → 无法表达并行与复杂依赖"],
];
problems.forEach(([title, desc], i) => {
  const y = 1.6 + i * 1.35;
  // Teal circle with number
  s2.addShape(pres.shapes.OVAL, {
    x: 3.6, y: y + 0.05, w: 0.5, h: 0.5,
    fill: { color: C.primary }
  });
  s2.addText(String(i + 1), {
    x: 3.6, y: y + 0.05, w: 0.5, h: 0.5,
    fontSize: 16, fontFace: FONT_B, color: C.white, bold: true, align: "center", valign: "middle", margin: 0
  });
  s2.addText(title, {
    x: 4.3, y: y, w: 8, h: 0.45,
    fontSize: 17, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
  });
  s2.addText(desc, {
    x: 4.3, y: y + 0.45, w: 8, h: 0.4,
    fontSize: 13, fontFace: FONT_B, color: C.muted, align: "left", margin: 0
  });
});
// Bottom takeaway
s2.addText("核心问题：如何构建兼具多模态感知、高效意图识别与结构化工作流编排能力的桌面智能体？", {
  x: 0.6, y: 6.8, w: 12, h: 0.5,
  fontSize: 12, fontFace: FONT_B, color: C.primary, bold: true, align: "left", margin: 0
});
s2.addNotes("背景与问题：LLM Agent生态(LangChain/AutoGPT/MetaGPT)各自发展但缺乏桌面场景分层设计。\n桌面场景独特挑战：文本+视觉双通道，意图跨度大(闲聊/代码/文件/系统)，需多步编排。\n四个结构性不足对应本系统的四个核心设计决策。");

// ══════════════════════════════════════════════════════════════
// SLIDE 3: ARCHITECTURE — full-width figure
// ══════════════════════════════════════════════════════════════
let s3 = pres.addSlide();
s3.background = { color: C.white };
s3.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s3.addText("三层解耦架构：路由层 → 角色层 → 工作引擎层", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 26, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
const archSize = imgSize("architecture.png", 11.5, 5.5);
s3.addImage({ path: figPath("architecture.png"), x: (13.3 - archSize.w) / 2, y: 1.3, w: archSize.w, h: archSize.h });
s3.addText("Source: Fig. 2, 本文 — 系统整体架构", {
  x: 0.6, y: 7.0, w: 12, h: 0.35,
  fontSize: 9, fontFace: FONT_B, color: C.muted, align: "left", margin: 0
});
s3.addNotes("三层架构详解：\n路由层(Routing Guard)：意图分类+参数抽取，输出RoutingDecision\n角色层(Roleplay Agent)：双角色system prompt + 5状态情绪追踪\n工作引擎层(Work Engine)：LangGraph有向图 G=(V,E,S)，5个专用子图\n视觉感知60秒周期并行运行");

// ══════════════════════════════════════════════════════════════
// SLIDE 4: KEYWORD GATING — figure + detail cards
// ══════════════════════════════════════════════════════════════
let s4 = pres.addSlide();
s4.background = { color: C.white };
s4.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s4.addText("关键词组合门控：11 类 230 词 × 布尔共现 = 零延迟意图分类", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 24, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
// Figure left
const kwSize = imgSize("keyword_gate_flowchart.png", 6.5, 5.5);
s4.addImage({ path: figPath("keyword_gate_flowchart.png"), x: 0.5, y: 1.3, w: kwSize.w, h: kwSize.h });
s4.addText("Source: Fig. 3", {
  x: 0.5, y: 1.3 + kwSize.h + 0.05, w: kwSize.w, h: 0.3,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
// Right: 3 info cards with teal header
const kwCards = [
  ["11 语义类别", "编程动词(60) | 工作空间名词(48)\n技术栈(15) | CLI命令(11) | 错误信号(12)"],
  ["8 布尔标志", "has_action / has_strong_action /\nhas_workspace_object / has_deliverable /\nhas_path / has_command / has_issue / has_tech"],
  ["判定规则", "≥2 类别共现 → i_coding\n空输入 → i_unknown\n否则 → i_chat"],
];
kwCards.forEach(([title, body], i) => {
  const y = 1.3 + i * 1.85;
  s4.addShape(pres.shapes.RECTANGLE, {
    x: 7.5, y: y, w: 5.3, h: 1.65,
    fill: { color: C.lightBg }
  });
  s4.addShape(pres.shapes.RECTANGLE, {
    x: 7.5, y: y, w: 0.06, h: 1.65,
    fill: { color: C.primary }
  });
  s4.addText(title, {
    x: 7.75, y: y + 0.1, w: 4.8, h: 0.35,
    fontSize: 14, fontFace: FONT_H, color: C.primary, bold: true, align: "left", margin: 0
  });
  s4.addText(body, {
    x: 7.75, y: y + 0.5, w: 4.8, h: 1.05,
    fontSize: 11, fontFace: FONT_B, color: C.text, align: "left", margin: 0
  });
});
s4.addNotes("关键词组合门控：\n11类约230个中英文关键词，涵盖编程动词、工作空间名词、技术栈名等\n不是单关键词匹配(B1)，不是单类别命中(B3)，而是≥2个语义类别共现\n空输入过滤→unknown, 快速通道(文件引用/代码结构)→coding, 否则8标志组合\nLLM不参与分类，仅在分类后抽取参数(temperature=0.1)");

// ══════════════════════════════════════════════════════════════
// SLIDE 5: LLM PARAMETER EXTRACTION — table + figure
// ══════════════════════════════════════════════════════════════
let s5 = pres.addSlide();
s5.background = { color: C.white };
s5.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s5.addText("LLM 结构化参数抽取 + 优先级动作匹配", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 26, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
// JSON schema figure left
const jsSize = imgSize("json_schema_tree.png", 6.0, 5.0);
s5.addImage({ path: figPath("json_schema_tree.png"), x: 0.5, y: 1.3, w: jsSize.w, h: jsSize.h });
s5.addText("Source: Fig. 4", {
  x: 0.5, y: 1.3 + jsSize.h + 0.05, w: jsSize.w, h: 0.3,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
// Table right
const actionRows = [
  [{ text: "动作类型", options: { bold: true, color: C.white, fill: { color: C.primary } }},
   { text: "抽取方式", options: { bold: true, color: C.white, fill: { color: C.primary } }},
   { text: "优先级", options: { bold: true, color: C.white, fill: { color: C.primary } }}],
  ["workspace.write", "LLM", "Tier 1"],
  ["workspace.delete/move/copy", "LLM", "Tier 1"],
  ["workspace.test/search", "LLM", "Tier 2"],
  ["run.create", "LLM", "Tier 2"],
  ["workspace.read", "规则→LLM", "Tier 3"],
  ["workspace.list", "纯规则", "Tier 4"],
];
s5.addTable(actionRows, {
  x: 7.0, y: 1.3, w: 5.8,
  fontSize: 11, fontFace: FONT_B, color: C.text,
  border: { pt: 0.5, color: "D0D0D0" },
  colW: [2.8, 1.5, 1.5],
  rowH: [0.4, 0.38, 0.38, 0.38, 0.38, 0.38, 0.38],
  autoPage: false,
});
// Priority equation
s5.addText("优先级序列：WRITE ≻ DELETE ≻ MOVE ≻ COPY ≻ TEST ≻ SEARCH ≻ READ ≻ LIST", {
  x: 7.0, y: 4.5, w: 5.8, h: 0.5,
  fontSize: 11, fontFace: FONT_B, color: C.muted, align: "left", margin: 0
});
s5.addText("Tier 1 不可逆/高风险 → 始终调用LLM\nTier 3 workspace.read → 正则优先，LLM回退", {
  x: 7.0, y: 5.1, w: 5.8, h: 0.8,
  fontSize: 11, fontFace: FONT_B, color: C.muted, align: "left", margin: 0
});
s5.addNotes("LLM参数抽取：\n意图分类完成后，对coding意图调用LLM抽取结构化参数\nparams(x,a) = LLM_extract(x,a) if needs_extraction(a) else rule_extract(x)\n9种动作类型分4个优先级层级\n动作匹配优先级序列用于消歧");

// ══════════════════════════════════════════════════════════════
// SLIDE 6: YOLOv8 PIPELINE — wide figure + detail
// ══════════════════════════════════════════════════════════════
let s6 = pres.addSlide();
s6.background = { color: C.white };
s6.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s6.addText("YOLOv8 视觉感知：12 MB ONNX 模型，CPU 推理 1–2 秒", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 24, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
const yoloSize = imgSize("yolo_pipeline.png", 12.0, 2.5);
s6.addImage({ path: figPath("yolo_pipeline.png"), x: (13.3 - yoloSize.w) / 2, y: 1.2, w: yoloSize.w, h: yoloSize.h });
s6.addText("Source: Fig. 5", {
  x: 0.6, y: 1.2 + yoloSize.h + 0.02, w: 12, h: 0.3,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
// Two columns below
// Left: pipeline detail
s6.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.0, w: 6.0, h: 3.2, fill: { color: C.lightBg } });
s6.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.0, w: 6.0, h: 0.4, fill: { color: C.primary } });
s6.addText("检测管线", {
  x: 0.7, y: 4.02, w: 5.5, h: 0.36,
  fontSize: 13, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
s6.addText(
  "模型: 微调 YOLOv8 (ONNX, 12 MB)\n" +
  "输出: O∈R^(1×10×8400), 10=4(bbox)+6(类别)\n" +
  "Anchor-free 解耦头, 类别得分=置信度\n" +
  "6类: activewindow/address bar/folder\n" +
  "      menubar/tab/window\n" +
  "置信度阈值 τ=0.4, 不执行 NMS\n" +
  "60秒轮询周期, MD5去重冷却120秒", {
  x: 0.7, y: 4.5, w: 5.5, h: 2.6,
  fontSize: 11, fontFace: FONT_B, color: C.text, align: "left", margin: 0
});
// Right: activity table
s6.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 4.0, w: 6.0, h: 3.2, fill: { color: C.lightBg } });
s6.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 4.0, w: 6.0, h: 0.4, fill: { color: C.primary } });
s6.addText("活动画像映射 (首次匹配)", {
  x: 7.0, y: 4.02, w: 5.5, h: 0.36,
  fontSize: 13, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
const actRows = [
  [{ text: "UI条件", options: { bold: true, color: C.white, fill: { color: C.primary }, fontSize: 10 }},
   { text: "活动", options: { bold: true, color: C.white, fill: { color: C.primary }, fontSize: 10 }},
   { text: "情绪", options: { bold: true, color: C.white, fill: { color: C.primary }, fontSize: 10 }}],
  [{ text: "tab≥3 + activewindow≥1", options: { fontSize: 9 }}, { text: "browsing", options: { fontSize: 9 }}, { text: "neutral", options: { fontSize: 9 }}],
  [{ text: "folder≥2", options: { fontSize: 9 }}, { text: "managing files", options: { fontSize: 9 }}, { text: "neutral", options: { fontSize: 9 }}],
  [{ text: "tab≥5", options: { fontSize: 9 }}, { text: "deep in research", options: { fontSize: 9 }}, { text: "focused", options: { fontSize: 9 }}],
  [{ text: "activewindow≥3", options: { fontSize: 9 }}, { text: "multitasking", options: { fontSize: 9 }}, { text: "focused", options: { fontSize: 9 }}],
  [{ text: "无检测结果", options: { fontSize: 9 }}, { text: "idle", options: { fontSize: 9 }}, { text: "lonely", options: { fontSize: 9 }}],
];
s6.addTable(actRows, {
  x: 7.0, y: 4.5, w: 5.5,
  fontSize: 10, fontFace: FONT_B, color: C.text,
  border: { pt: 0.5, color: "D0D0D0" },
  colW: [2.5, 1.7, 1.3],
  rowH: [0.32, 0.3, 0.3, 0.3, 0.3, 0.3],
  autoPage: false,
});
s6.addNotes("YOLOv8视觉感知管线：\n输入I∈R^(H×W×3) → Resize(640,640) → 归一化 → ONNX推理\n输出O∈R^(1×10×8400)，anchor-free解耦头设计\n6类桌面UI元素，置信度阈值τ=0.4\n活动画像首次匹配策略：6条主规则+3条回退规则");

// ══════════════════════════════════════════════════════════════
// SLIDE 7: VISUAL DEMO — 3 figures side by side
// ══════════════════════════════════════════════════════════════
let s7 = pres.addSlide();
s7.background = { color: C.white };
s7.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s7.addText("视觉感知将屏幕状态转化为情境化角色对话", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 26, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
// 3 images with correct aspect ratios
const caseNames = ["yolo_detection_case1.png", "yolo_detection_case2.png", "yolo_detection_case3.png"];
const caseCaptions = ["(a) 多标签浏览 → deep in research", "(b) 文件管理 → navigating files", "(c) 空闲屏幕 → idle"];
const maxFigW = 3.8, maxFigH = 3.5;
const gap = 0.4;
const totalW = maxFigW * 3 + gap * 2;
const startX = (13.3 - totalW) / 2;
caseNames.forEach((name, i) => {
  const sz = imgSize(name, maxFigW, maxFigH);
  const x = startX + i * (maxFigW + gap);
  s7.addImage({ path: figPath(name), x: x, y: 1.3, w: sz.w, h: sz.h });
  s7.addText(caseCaptions[i], {
    x: x, y: 1.3 + sz.h + 0.08, w: maxFigW, h: 0.35,
    fontSize: 10, fontFace: FONT_B, color: C.muted, align: "center", margin: 0
  });
});
// Comparison strip
s7.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 5.3, w: 12.3, h: 1.8, fill: { color: C.lightBg } });
s7.addText("视觉上下文对比", {
  x: 0.7, y: 5.4, w: 5, h: 0.35,
  fontSize: 13, fontFace: FONT_H, color: C.primary, bold: true, align: "left", margin: 0
});
s7.addText([
  { text: "有视觉: ", options: { bold: true, color: C.text } },
  { text: "\"开这么多标签，CPU 都要哭了~\" (worried)  ← tab×5", options: { color: C.muted } },
], { x: 0.7, y: 5.85, w: 11.8, h: 0.4, fontSize: 12, fontFace: FONT_B, align: "left", margin: 0 });
s7.addText([
  { text: "无视觉: ", options: { bold: true, color: C.text } },
  { text: "\"嗯嗯，本机在听呢\" (neutral)  ← 通用回复", options: { color: C.muted } },
], { x: 0.7, y: 6.3, w: 11.8, h: 0.4, fontSize: 12, fontFace: FONT_B, align: "left", margin: 0 });
s7.addNotes("三个典型案例展示视觉感知价值：\nCase1: tab×5 → deep in research → 角色说\"CPU都要哭了\"\nCase2: folder×3 + address bar → navigating files → 角色主动帮忙\nCase3: 无检测 → idle → 角色求关注\n视觉感知通过emit_vision_quip()集成到角色对话");

// ══════════════════════════════════════════════════════════════
// SLIDE 8: LANGGRAPH — figure + subgraph details
// ══════════════════════════════════════════════════════════════
let s8 = pres.addSlide();
s8.background = { color: C.white };
s8.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s8.addText("LangGraph 图工作流：5 子图覆盖任务全生命周期", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 24, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
const lgSize = imgSize("langgraph_topology.png", 12.0, 3.5);
s8.addImage({ path: figPath("langgraph_topology.png"), x: (13.3 - lgSize.w) / 2, y: 1.2, w: lgSize.w, h: lgSize.h });
s8.addText("Source: Fig. 6", {
  x: 0.6, y: 1.2 + lgSize.h + 0.02, w: 12, h: 0.3,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
// 5 subgraph cards in a row
const sgs = [
  ["Agent Loop", "6节点\nplan→act→observe→decide\n最大15步"],
  ["Coding WF", "8节点\nPM→Coder→Executor→finish\n失败: QA→debugger→retry"],
  ["File WF", "5节点\n9种操作: read/write/list/\nmove/copy/delete/search..."],
  ["Repair", "6节点\ninspect→eligibility→QA\n→decision→repair"],
  ["Summary", "运行完成/单次尝试\n后生成LLM摘要"],
];
const cardW = 2.3, cardH = 2.2, cardGap = 0.25;
const cardsTotalW = sgs.length * cardW + (sgs.length - 1) * cardGap;
const cardsStartX = (13.3 - cardsTotalW) / 2;
sgs.forEach(([title, body], i) => {
  const x = cardsStartX + i * (cardW + cardGap);
  const y = 5.1;
  s8.addShape(pres.shapes.RECTANGLE, { x: x, y: y, w: cardW, h: cardH, fill: { color: C.lightBg } });
  s8.addShape(pres.shapes.RECTANGLE, { x: x, y: y, w: cardW, h: 0.38, fill: { color: C.primary } });
  s8.addText(title, {
    x: x + 0.1, y: y + 0.02, w: cardW - 0.2, h: 0.34,
    fontSize: 11, fontFace: FONT_H, color: C.white, bold: true, align: "center", margin: 0
  });
  s8.addText(body, {
    x: x + 0.1, y: y + 0.45, w: cardW - 0.2, h: 1.65,
    fontSize: 9, fontFace: FONT_B, color: C.text, align: "left", margin: 0
  });
});
s8.addNotes("LangGraph 有向图状态机 G=(V,E,S)：\nAgent Loop: 主控循环，最大15步\nCoding Workflow: LLM Planner生成JSON执行计划，不可用时回退规则引擎\nFile Workflow: 9种文件操作，observer_node合并结果到上下文\nRepair Decision: LLM分析失败原因并生成修复脚本\n执行安全: subprocess.Popen(shell=False), 阻塞shell解释器和危险参数");

// ══════════════════════════════════════════════════════════════
// SLIDE 9: MEMORY — figure + emotion detail
// ══════════════════════════════════════════════════════════════
let s9 = pres.addSlide();
s9.background = { color: C.white };
s9.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s9.addText("Hermes 风格记忆：滑动窗口事件 + 情绪追踪 + 双角色系统", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 22, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
const memSize = imgSize("memory_sliding_window.png", 7.0, 4.5);
s9.addImage({ path: figPath("memory_sliding_window.png"), x: 0.5, y: 1.3, w: memSize.w, h: memSize.h });
s9.addText("Source: Fig. 7", {
  x: 0.5, y: 1.3 + memSize.h + 0.05, w: memSize.w, h: 0.3,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
// Right: memory + emotion cards
s9.addShape(pres.shapes.RECTANGLE, { x: 8.0, y: 1.3, w: 4.8, h: 2.5, fill: { color: C.lightBg } });
s9.addShape(pres.shapes.RECTANGLE, { x: 8.0, y: 1.3, w: 4.8, h: 0.38, fill: { color: C.primary } });
s9.addText("记忆事件", {
  x: 8.15, y: 1.32, w: 4.5, h: 0.34,
  fontSize: 12, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
s9.addText(
  "m_t = (turn_index, timestamp, user_input,\n  intent, action_name, result_summary, ok, error)\n\n" +
  "存储: dict[str, deque[MemoryEvent]]\n窗口: MAX_RECENT_EVENTS = 12\nbuild_context() → 格式化注入 LLM 上下文", {
  x: 8.15, y: 1.8, w: 4.5, h: 1.9,
  fontSize: 10, fontFace: FONT_B, color: C.text, align: "left", margin: 0
});
// Emotion card
s9.addShape(pres.shapes.RECTANGLE, { x: 8.0, y: 4.1, w: 4.8, h: 2.2, fill: { color: C.lightBg } });
s9.addShape(pres.shapes.RECTANGLE, { x: 8.0, y: 4.1, w: 4.8, h: 0.38, fill: { color: C.sea } });
s9.addText("5 状态情绪追踪", {
  x: 8.15, y: 4.12, w: 4.5, h: 0.34,
  fontSize: 12, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
s9.addText(
  "happy / neutral / frustrated / tired / lonely\n\n" +
  "连续成功→happy, 连续失败→frustrated\n长时间闲置→lonely\n\n" +
  "{mood_modifier} 注入 system prompt\n影响 LLM 输出语气和表情选择\n\n双角色: 主角色「未命名」+ 聊天角色「Shion」", {
  x: 8.15, y: 4.6, w: 4.5, h: 1.6,
  fontSize: 10, fontFace: FONT_B, color: C.text, align: "left", margin: 0
});
s9.addNotes("记忆系统：\nHermes风格结构化事件，每轮对话结束后自动记录\n滑动窗口maxlen=12，按session_id索引\nbuild_context()将最近事件格式化注入LLM上下文\n5状态情绪追踪器根据任务结果自动流转\n两个角色系统提示：主角色要求JSON输出，聊天角色为简化人设");

// ══════════════════════════════════════════════════════════════
// SLIDE 10: RESULTS — two tables + key insight
// ══════════════════════════════════════════════════════════════
let s10 = pres.addSlide();
s10.background = { color: C.white };
s10.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s10.addText("实验：401 条测试集验证组合门控安全性优先设计", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 24, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
// Dataset stats — big number callout
s10.addText("401", {
  x: 0.6, y: 1.3, w: 2.5, h: 1.5,
  fontSize: 72, fontFace: FONT_H, color: C.primary, bold: true, align: "center", margin: 0
});
s10.addText("条中文测试用例\n200 手工构造 + 201 部署日志", {
  x: 0.6, y: 2.8, w: 2.5, h: 0.8,
  fontSize: 11, fontFace: FONT_B, color: C.muted, align: "center", margin: 0
});
// Results table
const resRows = [
  [{ text: "方法", options: { bold: true, color: C.white, fill: { color: C.primary } }},
   { text: "F1", options: { bold: true, color: C.white, fill: { color: C.primary } }},
   { text: "Acc", options: { bold: true, color: C.white, fill: { color: C.primary } }},
   { text: "延迟", options: { bold: true, color: C.white, fill: { color: C.primary } }}],
  ["B1: Rule-Only", "0.778", "0.828", "0.003ms"],
  ["B3: Score≥1", "0.788", "0.835", "0.020ms"],
  [{ text: "Ours", options: { bold: true, color: C.primary, fill: { color: C.lightBg } }},
   { text: "0.685", options: { bold: true, color: C.primary, fill: { color: C.lightBg } }},
   { text: "0.701", options: { bold: true, color: C.primary, fill: { color: C.lightBg } }},
   { text: "0.020ms", options: { bold: true, color: C.primary, fill: { color: C.lightBg } }}],
];
s10.addTable(resRows, {
  x: 3.5, y: 1.3, w: 5.0,
  fontSize: 12, fontFace: FONT_B, color: C.text,
  border: { pt: 0.5, color: "D0D0D0" },
  colW: [1.8, 1.0, 1.0, 1.2],
  rowH: [0.4, 0.38, 0.38, 0.38],
  autoPage: false,
});
// Per-class F1 table
s10.addText("各类别 F1 值", {
  x: 9.0, y: 1.1, w: 4, h: 0.4,
  fontSize: 13, fontFace: FONT_H, color: C.primary, bold: true, align: "left", margin: 0
});
const pcRows = [
  [{ text: "方法", options: { bold: true, color: C.white, fill: { color: C.primary }, fontSize: 10 }},
   { text: "chat", options: { bold: true, color: C.white, fill: { color: C.primary }, fontSize: 10 }},
   { text: "coding", options: { bold: true, color: C.white, fill: { color: C.primary }, fontSize: 10 }},
   { text: "unknown", options: { bold: true, color: C.white, fill: { color: C.primary }, fontSize: 10 }}],
  [{ text: "B1", options: { fontSize: 10 }}, "0.817", "0.949", "0.000"],
  [{ text: "B3", options: { fontSize: 10 }}, "0.824", "0.955", "0.039"],
  [{ text: "Ours", options: { bold: true, color: C.primary, fontSize: 10 }},
   "0.729", "0.721",
   { text: "0.413", options: { bold: true, color: C.primary, fontSize: 10 }}],
];
s10.addTable(pcRows, {
  x: 9.0, y: 1.5, w: 4.0,
  fontSize: 10, fontFace: FONT_B, color: C.text,
  border: { pt: 0.5, color: "D0D0D0" },
  colW: [1.0, 0.9, 0.9, 1.2],
  rowH: [0.35, 0.32, 0.32, 0.32],
  autoPage: false,
});
// Key insight card
s10.addShape(pres.shapes.RECTANGLE, { x: 3.5, y: 3.2, w: 9.3, h: 3.8, fill: { color: C.lightBg } });
s10.addShape(pres.shapes.RECTANGLE, { x: 3.5, y: 3.2, w: 0.06, h: 3.8, fill: { color: C.mint } });
s10.addText("关键发现", {
  x: 3.8, y: 3.3, w: 4, h: 0.4,
  fontSize: 15, fontFace: FONT_H, color: C.primary, bold: true, align: "left", margin: 0
});
// F1 comparison chart image
const f1Size = imgSize("fig_per_class_f1.png", 8.5, 2.8);
s10.addImage({ path: figPath("fig_per_class_f1.png"), x: 3.8, y: 3.8, w: f1Size.w, h: f1Size.h });
s10.addText("Source: Fig. 9", {
  x: 3.8, y: 3.8 + f1Size.h + 0.02, w: f1Size.w, h: 0.25,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
s10.addText(
  "Ours F1(0.685) < B3(0.788) → 190条coding中29条仅命中单类别被误判\n" +
  "但 F1(unknown): 0.413 vs 0.039 → 提升0.374，过滤噪声能力显著↑\n" +
  "设计权衡：安全性(避免误触发) > 召回率", {
  x: 3.8, y: 6.4, w: 8.8, h: 0.9,
  fontSize: 11, fontFace: FONT_B, color: C.muted, align: "left", margin: 0
});
s10.addNotes("实验结果：\n401条中文测试集，3类意图\n组合门控加权F1(0.685)低于基线，因29条单类别coding被误判\n但unknown类F1=0.413远超基线(B1:0, B3:0.039)，安全性优先\n端到端20任务测试准确率80%，与Rule-Only相同");

// ══════════════════════════════════════════════════════════════
// SLIDE 11: ABLATION — figure + insight
// ══════════════════════════════════════════════════════════════
let s11 = pres.addSlide();
s11.background = { color: C.white };
s11.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s11.addText("消融实验：组合门控核心贡献是对模糊输入的过滤能力", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 24, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
// Ablation figure
const ablSize = imgSize("fig_ablation.png", 5.8, 5.0);
s11.addImage({ path: figPath("fig_ablation.png"), x: 0.5, y: 1.3, w: ablSize.w, h: ablSize.h });
s11.addText("Source: Fig. 8a", {
  x: 0.5, y: 1.3 + ablSize.h + 0.05, w: ablSize.w, h: 0.25,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
// F1 vs Latency
const latSize = imgSize("fig_f1_vs_latency.png", 5.5, 3.0);
s11.addImage({ path: figPath("fig_f1_vs_latency.png"), x: 7.0, y: 1.3, w: latSize.w, h: latSize.h });
s11.addText("Source: Fig. 8b", {
  x: 7.0, y: 1.3 + latSize.h + 0.05, w: latSize.w, h: 0.25,
  fontSize: 8, fontFace: FONT_B, color: C.muted, align: "right", margin: 0
});
// Key findings
s11.addShape(pres.shapes.RECTANGLE, { x: 7.0, y: 4.5, w: 5.8, h: 2.6, fill: { color: C.lightBg } });
s11.addShape(pres.shapes.RECTANGLE, { x: 7.0, y: 4.5, w: 0.06, h: 2.6, fill: { color: C.mint } });
s11.addText("消融核心发现", {
  x: 7.25, y: 4.6, w: 5.3, h: 0.35,
  fontSize: 14, fontFace: FONT_H, color: C.primary, bold: true, align: "left", margin: 0
});
s11.addText(
  "去掉组合门控 (w/o Gate = B3):\n" +
  "  加权 F1: 0.685 → 0.788 ↑\n" +
  "  unknown F1: 0.413 → 0.039 ↓↓↓\n\n" +
  "端到端验证 (20个编码任务):\n" +
  "  组合门控准确率 = Rule-Only = 80%\n" +
  "  失败案例完全相同\n" +
  "  → 组合门控不在明确请求上引入额外漏判", {
  x: 7.25, y: 5.0, w: 5.3, h: 2.0,
  fontSize: 11, fontFace: FONT_B, color: C.text, align: "left", margin: 0
});
s11.addNotes("消融实验：\n去掉组合门控后F1上升但unknown类识别能力丧失\n证明组合门控的核心贡献是对模糊/噪声输入的过滤\n端到端20任务测试验证不会在明确编码请求上引入额外漏判");

// ══════════════════════════════════════════════════════════════
// SLIDE 12: LIMITATIONS + FUTURE — two columns
// ══════════════════════════════════════════════════════════════
let s12 = pres.addSlide();
s12.background = { color: C.white };
s12.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.08, h: 7.5, fill: { color: C.primary } });
s12.addText("系统局限与未来改进方向", {
  x: 0.6, y: 0.4, w: 12, h: 0.7,
  fontSize: 26, fontFace: FONT_H, color: C.text, bold: true, align: "left", margin: 0
});
// Limitations left
s12.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.4, w: 5.8, h: 4.8, fill: { color: "FDF0EF" } });
s12.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 1.4, w: 5.8, h: 0.42, fill: { color: C.red } });
s12.addText("当前局限", {
  x: 0.7, y: 1.42, w: 5.3, h: 0.38,
  fontSize: 14, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
const limits = [
  "记忆系统无持久化，服务重启即丢失",
  "视觉检测仅 6 类 UI 元素",
  "代码执行无沙箱隔离（本地子进程）",
  "情绪系统为全局单例，非 per-session",
];
limits.forEach((l, i) => {
  const y = 2.1 + i * 0.9;
  s12.addShape(pres.shapes.OVAL, {
    x: 0.8, y: y + 0.05, w: 0.35, h: 0.35,
    fill: { color: C.red }
  });
  s12.addText(String(i + 1), {
    x: 0.8, y: y + 0.05, w: 0.35, h: 0.35,
    fontSize: 12, fontFace: FONT_B, color: C.white, bold: true, align: "center", valign: "middle", margin: 0
  });
  s12.addText(l, {
    x: 1.3, y: y, w: 4.8, h: 0.45,
    fontSize: 13, fontFace: FONT_B, color: C.text, align: "left", margin: 0
  });
});
// Future right
s12.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.4, w: 6.0, h: 4.8, fill: { color: C.lightBg } });
s12.addShape(pres.shapes.RECTANGLE, { x: 6.8, y: 1.4, w: 6.0, h: 0.42, fill: { color: C.primary } });
s12.addText("未来方向", {
  x: 7.0, y: 1.42, w: 5.5, h: 0.38,
  fontSize: 14, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
const futures = [
  "三层记忆架构 + 磁盘持久化",
  "扩展 YOLOv8 至代码编辑器、终端等",
  "引入 Docker 沙箱执行环境",
  "per-session 情绪系统 + 多用户",
  "LLM 意图分类作为可选高精度路径",
];
futures.forEach((f, i) => {
  const y = 2.1 + i * 0.82;
  s12.addShape(pres.shapes.OVAL, {
    x: 7.1, y: y + 0.05, w: 0.35, h: 0.35,
    fill: { color: C.primary }
  });
  s12.addText(String(i + 1), {
    x: 7.1, y: y + 0.05, w: 0.35, h: 0.35,
    fontSize: 12, fontFace: FONT_B, color: C.white, bold: true, align: "center", valign: "middle", margin: 0
  });
  s12.addText(f, {
    x: 7.6, y: y, w: 5.0, h: 0.45,
    fontSize: 13, fontFace: FONT_B, color: C.text, align: "left", margin: 0
  });
});
// Positioning note
s12.addText("与 Computer Use 的定位差异：后者追求通用桌面操控，本系统追求轻量陪伴型定位", {
  x: 0.6, y: 6.8, w: 12, h: 0.4,
  fontSize: 11, fontFace: FONT_B, color: C.muted, align: "left", margin: 0
});
s12.addNotes("四大局限与五个未来方向。\n与Computer Use的差异：后者依赖云端GPU追求通用操控，本系统轻量可离线追求陪伴型定位。");

// ══════════════════════════════════════════════════════════════
// SLIDE 13: CONCLUSION — dark bg, summary
// ══════════════════════════════════════════════════════════════
let s13 = pres.addSlide();
s13.background = { color: C.dark };
s13.addShape(pres.shapes.RECTANGLE, { x: 11.5, y: 0, w: 1.833, h: 7.5, fill: { color: C.primary, transparency: 30 } });
s13.addShape(pres.shapes.RECTANGLE, { x: 12.3, y: 0, w: 1.033, h: 7.5, fill: { color: C.sea, transparency: 50 } });
s13.addText("总结", {
  x: 0.8, y: 0.6, w: 10, h: 0.8,
  fontSize: 32, fontFace: FONT_H, color: C.white, bold: true, align: "left", margin: 0
});
s13.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 1.5, w: 2.0, h: 0.04, fill: { color: C.mint } });
const contribs = [
  "三层解耦架构：路由层 + 角色层 + 工作引擎层",
  "关键词组合门控：11类230词，零LLM调用，延迟0.020ms",
  "  unknown类F1提升0.374（安全性优先设计权衡）",
  "YOLOv8视觉感知：12MB ONNX，6类UI元素，CPU实时",
  "LangGraph工作流：5子图覆盖代码/文件/故障修复",
  "原型验证：401条测试用例，各模块协作正常",
];
contribs.forEach((c, i) => {
  const y = 2.0 + i * 0.65;
  s13.addText(c, {
    x: 0.8, y: y, w: 10, h: 0.55,
    fontSize: i === 2 || i === 4 ? 14 : 16, fontFace: FONT_B,
    color: i === 2 ? C.mint : C.white, align: "left",
    bold: i < 2 || i === 4, margin: 0
  });
});
s13.addText("谢谢！", {
  x: 0.8, y: 6.2, w: 10, h: 0.6,
  fontSize: 24, fontFace: FONT_H, color: C.mint, bold: true, align: "left", margin: 0
});
s13.addNotes("总结五大贡献。强调工程完整性与安全性优先的设计权衡。");

// ══════════════════════════════════════════════════════════════
// SAVE
// ══════════════════════════════════════════════════════════════
const outDir = path.join(__dirname, "..", "output");
if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
const outPath = path.join(outDir, "presentation_v3.pptx");
pres.writeFile({ fileName: outPath }).then(() => {
  console.log("Saved:", outPath);
  console.log("Slides:", 13);
}).catch(err => {
  console.error("Error:", err);
});
