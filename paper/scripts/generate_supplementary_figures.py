"""Generate all 8 supplementary figures for the paper.
Uses matplotlib with Chinese font support (SimHei on Windows).
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np
from pathlib import Path

# ── Chinese font setup ──
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)

# Color palette
C_BLUE = '#1565C0'
C_LIGHT_BLUE = '#E3F2FD'
C_ORANGE = '#E65100'
C_LIGHT_ORANGE = '#FFF3E0'
C_GREEN = '#2E7D32'
C_LIGHT_GREEN = '#E8F5E9'
C_RED = '#C62828'
C_LIGHT_RED = '#FFEBEE'
C_GRAY = '#616161'
C_LIGHT_GRAY = '#F5F5F5'
C_PURPLE = '#6A1B9A'
C_YELLOW = '#F9A825'


def save(fig, name):
    path = FIG_DIR / f"{name}.pdf"
    fig.savefig(path, bbox_inches='tight', dpi=300)
    fig.savefig(FIG_DIR / f"{name}.png", bbox_inches='tight', dpi=200)
    plt.close(fig)
    print(f"  Saved: {path.name}")


# ════════════════════════════════════════════════════════════════════
# Figure 4: Keyword Gate Flowchart
# ════════════════════════════════════════════════════════════════════
def fig_keyword_gate():
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis('off')

    def box(x, y, w, h, text, color=C_LIGHT_BLUE, edge=C_BLUE, fs=8):
        r = FancyBboxPatch((x - w/2, y - h/2), w, h,
                           boxstyle="round,pad=0.15", fc=color, ec=edge, lw=1.5)
        ax.add_patch(r)
        ax.text(x, y, text, ha='center', va='center', fontsize=fs, wrap=True)

    def diamond(x, y, w, h, text, color='#FFF9C4', edge=C_YELLOW, fs=7):
        pts = [(x, y+h/2), (x+w/2, y), (x, y-h/2), (x-w/2, y)]
        p = plt.Polygon(pts, fc=color, ec=edge, lw=1.5)
        ax.add_patch(p)
        ax.text(x, y, text, ha='center', va='center', fontsize=fs, wrap=True)

    def arrow(x1, y1, x2, y2, label='', color='black'):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', lw=1.5, color=color))
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx+0.15, my, label, fontsize=7, color=color, style='italic')

    # Start
    box(5, 13.3, 2.5, 0.6, '输入 x', C_LIGHT_GRAY, C_GRAY)
    arrow(5, 13.0, 5, 12.5)

    # Empty check
    diamond(5, 12.0, 3.5, 0.8, 'x 为空?', '#FFCDD2', C_RED)
    arrow(5, 11.6, 5, 11.1)
    ax.text(5.1, 11.35, '否', fontsize=7, color=C_GREEN)

    # Branch 1: file ref / code hint
    diamond(5, 10.6, 4.5, 0.8, 'has_file_ref(x)\nor has_code_hint(x)?', '#FFF9C4', C_YELLOW, 7)
    arrow(8.0, 12.0, 9.0, 11.0)
    ax.text(8.2, 11.6, '是: True\n→ coding', fontsize=7, color=C_RED)

    # Yes -> coding
    box(9.0, 10.5, 1.8, 0.5, '→ coding', C_LIGHT_GREEN, C_GREEN, 8)

    arrow(5, 10.2, 5, 9.7)
    ax.text(5.1, 9.95, '否', fontsize=7, color=C_GREEN)

    # Extract features
    box(5, 9.2, 5.5, 0.7, '提取 8 个特征标志:\nhas_action / has_strong_action / has_workspace_object\nhas_deliverable / has_path / has_command / has_issue / has_tech',
        C_LIGHT_BLUE, C_BLUE, 6)
    arrow(5, 8.85, 5, 8.4)

    # Branch 2: issue + (object|cmd|tech)
    diamond(5, 7.9, 4.5, 0.8, 'has_issue AND\n(object|cmd|tech)?', '#FFF9C4', C_YELLOW, 7)
    arrow(5, 7.5, 5, 7.0)
    ax.text(5.1, 7.25, '否', fontsize=7, color=C_GREEN)
    arrow(8.0, 7.9, 9.0, 10.5)
    ax.text(8.2, 9.5, '是: True\n→ coding', fontsize=7, color=C_RED)

    # Branch 3: action + (object|deliverable|path|cmd)
    diamond(5, 6.5, 4.8, 0.8, 'has_action AND\n(obj|deliverable|path|cmd)?', '#FFF9C4', C_YELLOW, 7)
    arrow(5, 6.1, 5, 5.6)
    ax.text(5.1, 5.85, '否', fontsize=7, color=C_GREEN)
    arrow(8.2, 6.5, 9.0, 10.0)
    ax.text(8.4, 8.5, '是: True\n→ coding', fontsize=7, color=C_RED)

    # Branch 4: strong_action + (tech|deliverable)
    diamond(5, 5.1, 4.8, 0.8, 'has_strong_action AND\n(tech|deliverable)?', '#FFF9C4', C_YELLOW, 7)
    arrow(5, 4.7, 5, 4.2)
    ax.text(5.1, 4.45, '否', fontsize=7, color=C_GREEN)
    arrow(8.2, 5.1, 9.0, 9.5)
    ax.text(8.4, 7.5, '是: True\n→ coding', fontsize=7, color=C_RED)

    # Empty -> unknown
    arrow(3.0, 12.0, 1.5, 11.0)
    ax.text(1.6, 11.6, '是', fontsize=7, color=C_RED)
    box(1.5, 10.5, 1.8, 0.5, '→ unknown', C_LIGHT_ORANGE, C_ORANGE, 8)

    # All false -> chat
    box(5, 3.5, 1.8, 0.5, '→ chat', C_LIGHT_ORANGE, C_ORANGE, 8)
    arrow(5, 4.0, 5, 3.75)

    # Title
    ax.text(5, 13.8, '关键词组合门控判定流程', ha='center', fontsize=12, fontweight='bold')

    save(fig, 'keyword_gate_flowchart')


# ════════════════════════════════════════════════════════════════════
# Figure 5: JSON Schema Tree
# ════════════════════════════════════════════════════════════════════
def fig_json_schema():
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis('off')

    def box(x, y, w, h, text, color=C_LIGHT_BLUE, edge=C_BLUE, fs=7):
        r = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                           fc=color, ec=edge, lw=1.2)
        ax.add_patch(r)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fs)

    def line(x1, y1, x2, y2):
        ax.plot([x1, x2], [y1, y2], 'k-', lw=1, alpha=0.5)

    # Root
    box(4.5, 7.2, 3, 0.5, 'LLM 参数抽取 JSON 输出', C_LIGHT_GREEN, C_GREEN, 9)

    # action level
    box(0.2, 6.0, 2.2, 0.4, 'action_type', '#E8EAF6', '#3F51B5', 8)
    box(3.0, 6.0, 2.2, 0.4, 'action_input', '#E8EAF6', '#3F51B5', 8)
    line(5, 7.2, 1.3, 6.4)
    line(5, 7.2, 4.1, 6.4)

    # action_input fields
    fields = [
        ('rel_path*', C_LIGHT_BLUE, C_BLUE),
        ('content*', C_LIGHT_BLUE, C_BLUE),
        ('overwrite', C_LIGHT_GRAY, C_GRAY),
        ('source_path*', C_LIGHT_ORANGE, C_ORANGE),
        ('target_path*', C_LIGHT_ORANGE, C_ORANGE),
        ('query*', C_LIGHT_GREEN, C_GREEN),
    ]
    for i, (name, fc, ec) in enumerate(fields):
        x = 1.5 + (i % 3) * 2.8
        y = 4.8 - (i // 3) * 1.0
        box(x, y, 2.2, 0.4, name, fc, ec, 8)
        line(4.1, 6.0, x + 1.1, y + 0.4)

    # Legend
    ax.text(0.3, 1.2, '* = 必填字段', fontsize=8, fontweight='bold')
    ax.text(0.3, 0.8, '无 * = 可选字段', fontsize=8)

    # Action type examples
    actions = [
        'workspace.write', 'workspace.read', 'workspace.list',
        'workspace.delete', 'workspace.move', 'workspace.copy',
        'workspace.search', 'workspace.test', 'run.create'
    ]
    for i, a in enumerate(actions):
        x = 0.3 + (i % 3) * 2.0
        y = 3.2 - (i // 3) * 0.5
        box(x, y, 1.8, 0.35, a, '#F3E5F5', C_PURPLE, 6)

    ax.text(6, 7.5, 'LLM 参数抽取 JSON Schema 结构', ha='center',
            fontsize=12, fontweight='bold')

    save(fig, 'json_schema_tree')


# ════════════════════════════════════════════════════════════════════
# Figure 6: YOLOv8 Pipeline Data Flow
# ════════════════════════════════════════════════════════════════════
def fig_yolo_pipeline():
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 4)
    ax.axis('off')

    steps = [
        ('截图输入', 'H×W×3', C_LIGHT_GRAY, C_GRAY),
        ('Resize +\n归一化', '640×640×3\nfloat32 [0,1]', C_LIGHT_BLUE, C_BLUE),
        ('HWC→CHW\n+ Batch', '1×3×640×640', C_LIGHT_BLUE, C_BLUE),
        ('ONNX Runtime\nCPU 推理', '12MB 模型', C_LIGHT_ORANGE, C_ORANGE),
        ('输出张量', '1×10×8400', C_LIGHT_RED, C_RED),
        ('转置 +\nArgmax', '8400×10', C_LIGHT_GREEN, C_GREEN),
        ('置信度过滤\nτ=0.4', 'N×10', C_LIGHT_GREEN, C_GREEN),
        ('检测结果\n列表', '{cls,bbox,conf}', C_LIGHT_GREEN, C_GREEN),
    ]

    for i, (label, dim, fc, ec) in enumerate(steps):
        x = 0.3 + i * 1.7
        w, h = 1.5, 2.0
        r = FancyBboxPatch((x, 1.0), w, h, boxstyle="round,pad=0.1",
                           fc=fc, ec=ec, lw=1.5)
        ax.add_patch(r)
        ax.text(x + w/2, 2.3, label, ha='center', va='center',
                fontsize=7, fontweight='bold')
        ax.text(x + w/2, 1.5, dim, ha='center', va='center',
                fontsize=6, color=C_GRAY, style='italic')
        if i < len(steps) - 1:
            ax.annotate('', xy=(x + w + 0.05, 2.0), xytext=(x + w + 0.15, 2.0),
                        arrowprops=dict(arrowstyle='->', lw=2, color=C_BLUE))

    ax.text(7, 3.5, 'YOLOv8 推理管线数据流', ha='center',
            fontsize=12, fontweight='bold')

    save(fig, 'yolo_pipeline')


# ════════════════════════════════════════════════════════════════════
# Figure 7: Activity Profile Decision Tree
# ════════════════════════════════════════════════════════════════════
def fig_activity_tree():
    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')

    def node(x, y, text, fc='#E3F2FD', ec='#1565C0', fs=7, w=2.5, h=0.6):
        r = FancyBboxPatch((x - w/2, y - h/2), w, h, boxstyle="round,pad=0.1",
                           fc=fc, ec=ec, lw=1.2)
        ax.add_patch(r)
        ax.text(x, y, text, ha='center', va='center', fontsize=fs, wrap=True)

    def edge(x1, y1, x2, y2, label='', color='black'):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', lw=1.2, color=color))
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx + 0.1, my, label, fontsize=6, color=color, style='italic')

    # Root
    node(7, 9.5, '检测结果 D', '#FFF9C4', '#F9A825', 8, 2.5, 0.6)
    edge(7, 9.2, 7, 8.7, 'D ≠ ∅')

    # Check 1: tab>=3 AND aw>=1
    node(3, 8.3, 'tab≥3\nAND activewindow≥1', '#FFF9C4', '#F9A825', 7, 2.8, 0.7)
    edge(7, 8.7, 4.4, 8.3)
    # Yes -> browsing
    node(1, 7.2, 'browsing\nneutral', '#C8E6C9', '#2E7D32', 7, 1.8, 0.5)
    edge(3, 7.95, 1.9, 7.2, '是')

    # Check 2
    node(7, 8.3, 'activewindow≥1\nAND menubar≥1', '#FFF9C4', '#F9A825', 7, 2.8, 0.7)
    edge(3, 7.95, 5.6, 8.3, '否')
    node(5.5, 7.2, 'using app\nneutral', '#C8E6C9', '#2E7D32', 7, 1.8, 0.5)
    edge(7, 7.95, 6.4, 7.2, '是')

    # Check 3
    node(11, 8.3, 'folder≥2', '#FFF9C4', '#F9A825', 7, 2.2, 0.6)
    edge(7, 7.95, 9.9, 8.3, '否')
    node(10, 7.2, 'managing\nfiles', '#C8E6C9', '#2E7D32', 7, 1.8, 0.5)
    edge(11, 8.0, 10.9, 7.2, '是')

    # Check 4
    node(3, 6.0, 'addr_bar≥1\nAND folder≥1', '#FFF9C4', '#F9A825', 7, 2.8, 0.7)
    edge(11, 7.95, 4.4, 6.0, '否')
    node(1, 5.0, 'navigating\nfiles', '#C8E6C9', '#2E7D32', 7, 1.8, 0.5)
    edge(3, 5.65, 1.9, 5.0, '是')

    # Check 5
    node(7, 6.0, 'tab≥5', '#FFF9C4', '#F9A825', 7, 2.0, 0.6)
    edge(3, 5.65, 6.0, 6.0, '否')
    node(5.5, 5.0, 'deep in\nresearch', '#C8E6C9', '#2E7D32', 7, 1.8, 0.5)
    edge(7, 5.7, 6.4, 5.0, '是')

    # Check 6
    node(11, 6.0, 'activewindow≥3', '#FFF9C4', '#F9A825', 7, 2.5, 0.6)
    edge(7, 5.7, 9.75, 6.0, '否')
    node(10, 5.0, 'multitasking\nhard', '#C8E6C9', '#2E7D32', 7, 1.8, 0.5)
    edge(11, 5.7, 10.9, 5.0, '是')

    # Fallbacks
    node(3, 3.5, '总检测≥2', '#FFE0B2', '#E65100', 7, 2.0, 0.6)
    edge(11, 5.7, 4.0, 3.5, '否')
    node(1, 2.5, 'using computer\nneutral', '#FFE0B2', '#E65100', 7, 2.2, 0.5)
    edge(3, 3.2, 2.1, 2.5, '是')

    node(7, 3.5, '总检测<2', '#FFE0B2', '#E65100', 7, 2.0, 0.6)
    edge(3, 3.2, 6.0, 3.5, '否')
    node(5.5, 2.5, 'minimal\nneutral', '#FFE0B2', '#E65100', 7, 1.8, 0.5)
    edge(7, 3.2, 6.4, 2.5, '是')

    node(11, 3.5, 'D = ∅', '#FFCDD2', '#C62828', 7, 1.8, 0.6)
    edge(7, 3.2, 10.1, 3.5, '否')
    node(10, 2.5, 'idle\nlonely', '#FFCDD2', '#C62828', 7, 1.8, 0.5)
    edge(11, 3.2, 10.9, 2.5, '是')

    ax.text(7, 10.2, '活动画像映射决策树（首次匹配策略）', ha='center',
            fontsize=12, fontweight='bold')

    save(fig, 'activity_decision_tree')


# ════════════════════════════════════════════════════════════════════
# Figure 8: LangGraph Work Engine Topology
# ════════════════════════════════════════════════════════════════════
def fig_langgraph_topology():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis('off')

    def subgraph_box(x, y, w, h, title, color, nodes):
        r = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.15",
                           fc=color, ec='black', lw=1.5, alpha=0.15)
        ax.add_patch(r)
        ax.text(x + w/2, y + h - 0.25, title, ha='center', va='center',
                fontsize=9, fontweight='bold')
        for i, (nx, ny, label) in enumerate(nodes):
            nr = FancyBboxPatch((x + nx - 0.6, y + ny - 0.2), 1.2, 0.4,
                                boxstyle="round,pad=0.05", fc='white', ec=color, lw=1)
            ax.add_patch(nr)
            ax.text(x + nx, y + ny, label, ha='center', va='center', fontsize=6)

    # Agent Loop Graph
    subgraph_box(0.2, 5.5, 4, 3, 'Agent Loop Graph', C_BLUE, [
        (0.8, 2.2, 'plan'), (2.0, 2.2, 'act'), (3.2, 2.2, 'observe'),
        (2.0, 1.4, 'decide'), (0.8, 0.6, 'finalize'), (3.2, 0.6, 'failure'),
    ])
    # Internal edges (simplified)
    ax.annotate('', xy=(1.6, 7.7), xytext=(1.4, 7.7),
                arrowprops=dict(arrowstyle='->', lw=1, color=C_BLUE))
    ax.annotate('', xy=(2.8, 7.7), xytext=(2.6, 7.7),
                arrowprops=dict(arrowstyle='->', lw=1, color=C_BLUE))

    # Coding Workflow Graph
    subgraph_box(5, 5.5, 4.5, 3, 'Coding Workflow Graph', C_ORANGE, [
        (0.7, 2.2, 'start'), (1.7, 2.2, 'PM'), (2.7, 2.2, 'coder'),
        (3.7, 2.2, 'executor'), (1.2, 0.6, 'QA'), (2.5, 0.6, 'debugger'),
        (3.7, 0.6, 'finish'),
    ])

    # File Workflow Graph
    subgraph_box(10, 5.5, 3.5, 3, 'File Workflow Graph', C_GREEN, [
        (0.7, 2.2, 'start'), (1.75, 2.2, 'executor'),
        (2.8, 2.2, 'observer'), (1.75, 0.6, 'finish'),
    ])

    # Repair Decision Graph
    subgraph_box(1, 1, 5.5, 3.5, 'Repair Decision Graph', C_RED, [
        (0.7, 2.8, 'inspect'), (1.7, 2.8, 'eligible'),
        (2.7, 2.8, 'QA'), (3.7, 2.8, 'decision'),
        (4.7, 2.8, 'feedback'), (4.7, 1.5, 'codegen'),
    ])

    # Summary Graphs
    subgraph_box(7.5, 1, 5.5, 3.5, 'Summary Graphs', C_PURPLE, [
        (1.2, 2.8, 'run_summary'), (3.0, 2.8, 'attempt_summary'),
        (1.2, 1.5, 'summary_node'), (3.0, 1.5, 'summary_node'),
        (1.2, 0.5, 'roleplay'), (3.0, 0.5, 'roleplay'),
    ])

    # Cross-graph edges
    # Agent Loop -> Coding (act_node dispatches to coding)
    ax.annotate('', xy=(5.0, 7.5), xytext=(4.2, 7.5),
                arrowprops=dict(arrowstyle='->', lw=2, color=C_ORANGE,
                                connectionstyle='arc3,rad=0'))
    ax.text(4.5, 7.7, 'run.create', fontsize=6, color=C_ORANGE, ha='center')

    # Agent Loop -> File (act_node dispatches to file)
    ax.annotate('', xy=(10.0, 7.5), xytext=(4.2, 7.0),
                arrowprops=dict(arrowstyle='->', lw=2, color=C_GREEN,
                                connectionstyle='arc3,rad=-0.2'))
    ax.text(7.5, 6.8, 'file ops', fontsize=6, color=C_GREEN, ha='center')

    # Coding -> Repair (on failure)
    ax.annotate('', xy=(3.7, 4.5), xytext=(7.2, 5.5),
                arrowprops=dict(arrowstyle='->', lw=2, color=C_RED,
                                connectionstyle='arc3,rad=0.2'))
    ax.text(5.8, 5.2, 'failure', fontsize=6, color=C_RED, ha='center')

    # All -> Summary
    ax.annotate('', xy=(8.5, 4.5), xytext=(2.2, 5.5),
                arrowprops=dict(arrowstyle='->', lw=1.5, color=C_PURPLE,
                                connectionstyle='arc3,rad=-0.1'))
    ax.text(5, 4.8, 'complete', fontsize=6, color=C_PURPLE, ha='center')

    ax.text(7, 8.8, 'LangGraph 工作引擎完整拓扑图', ha='center',
            fontsize=12, fontweight='bold')

    save(fig, 'langgraph_topology')


# ════════════════════════════════════════════════════════════════════
# Figure 9: Memory Sliding Window
# ════════════════════════════════════════════════════════════════════
def fig_memory_window():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5),
                                    gridspec_kw={'width_ratios': [1.2, 1]})

    # Left: deque visualization
    ax1.set_xlim(-1, 13)
    ax1.set_ylim(-1, 5)
    ax1.axis('off')
    ax1.set_title('滑动窗口 (deque, maxlen=12)', fontsize=10, fontweight='bold')

    # Draw 12 slots
    for i in range(12):
        color = '#C8E6C9' if i < 8 else '#FFCDD2'  # green=active, red=evicted
        r = FancyBboxPatch((i, 1.5), 0.9, 1.5, boxstyle="round,pad=0.05",
                           fc=color, ec='#424242', lw=1)
        ax1.add_patch(r)
        ax1.text(i + 0.45, 2.25, f'T{i+1}', ha='center', va='center', fontsize=7)

    # Arrows
    ax1.annotate('', xy=(12.5, 3.5), xytext=(11.5, 3.5),
                arrowprops=dict(arrowstyle='->', lw=2, color=C_GREEN))
    ax1.text(12, 3.8, '新事件\n加入', fontsize=7, color=C_GREEN, ha='center')

    ax1.annotate('', xy=(-0.5, 3.5), xytext=(0.5, 3.5),
                arrowprops=dict(arrowstyle='->', lw=2, color=C_RED))
    ax1.text(-0.3, 3.8, '旧事件\n移出', fontsize=7, color=C_RED, ha='center')

    ax1.text(6, 0.8, 'MAX_RECENT_EVENTS = 12', ha='center',
             fontsize=8, style='italic', color=C_GRAY)

    # Right: build_context() output
    ax2.axis('off')
    ax2.set_xlim(0, 10)
    ax2.set_ylim(0, 10)
    ax2.set_title('build_context() 输出示例', fontsize=10, fontweight='bold')

    code = (
        '=== 对话记忆 (Hermes) ===\n'
        '[Turn 1] OK | Intent: coding |\n'
        '  User: 写一个 hello world |\n'
        '  Result: 脚本生成并执行成功\n'
        '[Turn 2] OK | Intent: chat |\n'
        '  User: 今天天气怎么样 |\n'
        '  Result: 角色闲聊回复\n'
        '[Turn 3] OK | Intent: coding |\n'
        '  User: 搜索 TODO |\n'
        '  Result: 找到 5 个文件\n'
        '...\n'
        '[Turn 12] OK | Intent: chat |\n'
        '  User: 谢谢 |\n'
        '  Result: 不客气~\n'
        '=== 记忆结束 ==='
    )
    r = FancyBboxPatch((0.5, 0.5), 9, 9, boxstyle="round,pad=0.2",
                       fc='#263238', ec='#546E7A', lw=1.5)
    ax2.add_patch(r)
    ax2.text(1.0, 9.0, code, fontsize=7, color='#A5D6A7',
             family='monospace', va='top')

    plt.tight_layout()
    save(fig, 'memory_sliding_window')


# ════════════════════════════════════════════════════════════════════
# Figure 10: Intent Classification Performance
# ════════════════════════════════════════════════════════════════════
def fig_intent_performance():
    fig, ax = plt.subplots(figsize=(10, 5))

    categories = ['明确编码请求', '纯闲聊', '模糊输入']
    gate_true = [100, 0, 15]   # % classified as coding
    gate_false = [0, 100, 85]  # % classified as chat
    keyword_hits = [3.2, 0, 0.8]  # avg keyword categories hit

    x = np.arange(len(categories))
    w = 0.3

    bars1 = ax.bar(x - w/2, gate_true, w, label='→ coding (True)',
                   color=C_GREEN, alpha=0.8)
    bars2 = ax.bar(x + w/2, gate_false, w, label='→ chat (False)',
                   color=C_ORANGE, alpha=0.8)

    # Add keyword hit count on top
    for i, hits in enumerate(keyword_hits):
        ax.text(x[i], max(gate_true[i], gate_false[i]) + 3,
                f'avg hits: {hits}', ha='center', fontsize=8, color=C_GRAY)

    ax.set_ylabel('判定比例 (%)', fontsize=10)
    ax.set_title('关键词组合门控在三类输入上的判定结果', fontsize=12, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(categories, fontsize=10)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 115)
    ax.grid(axis='y', alpha=0.3)

    # Add value labels
    for bar in bars1:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2, h + 1,
                    f'{h:.0f}%', ha='center', fontsize=8)
    for bar in bars2:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width()/2, h + 1,
                    f'{h:.0f}%', ha='center', fontsize=8)

    plt.tight_layout()
    save(fig, 'intent_performance')


# ════════════════════════════════════════════════════════════════════
# Figure 11: Work Engine Success Rate
# ════════════════════════════════════════════════════════════════════
def fig_work_engine_success():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: Success rates
    modules = ['Coding\nGraph', 'File\nGraph', 'Repair\nGraph']
    success = [10, 9, 14]
    total = [10, 9, 14]
    rates = [s/t*100 for s, t in zip(success, total)]

    bars = ax1.bar(modules, rates, color=[C_BLUE, C_GREEN, C_RED], alpha=0.8,
                   edgecolor='black', linewidth=0.8)
    for bar, s, t in zip(bars, success, total):
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, h + 1,
                 f'{s}/{t}\n({h:.0f}%)', ha='center', fontsize=9, fontweight='bold')

    ax1.set_ylabel('成功率 (%)', fontsize=10)
    ax1.set_title('各子图执行成功率', fontsize=11, fontweight='bold')
    ax1.set_ylim(0, 115)
    ax1.grid(axis='y', alpha=0.3)

    # Right: Coding repair flow
    labels = ['首次成功', 'Repair\n修复成功']
    values = [8, 2]
    colors = [C_GREEN, C_YELLOW]

    bars2 = ax2.bar(labels, values, color=colors, alpha=0.8,
                    edgecolor='black', linewidth=0.8)
    for bar, v in zip(bars2, values):
        h = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, h + 0.2,
                 f'{v}/10', ha='center', fontsize=10, fontweight='bold')

    ax2.set_ylabel('任务数', fontsize=10)
    ax2.set_title('Coding 子图成功分布', fontsize=11, fontweight='bold')
    ax2.set_ylim(0, 12)
    ax2.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    save(fig, 'work_engine_success')


# ════════════════════════════════════════════════════════════════════
# Main
# ════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("Generating figures...")
    fig_keyword_gate()
    fig_json_schema()
    fig_yolo_pipeline()
    fig_activity_tree()
    fig_langgraph_topology()
    fig_memory_window()
    fig_intent_performance()
    fig_work_engine_success()
    print(f"All 8 figures saved to {FIG_DIR}")
