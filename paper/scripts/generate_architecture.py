"""
Generate the 3-layer architecture diagram for the paper.
Produces both PDF and PNG outputs in paper/figures/.

Run: python paper/scripts/generate_architecture.py
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Use a Chinese-capable font available on Windows
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Noto Sans SC', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_DIR = "paper/figures"
OUTPUT_NAME = "architecture"

# Figure dimensions (inches) – sized for a two-column ~0.85\textwidth figure
FIG_W, FIG_H = 10, 13

# Colour palette
C_INPUT  = "#4A4A4A"   # dark grey for input/output labels
C_LAYER1 = "#3B82F6"   # blue
C_LAYER1_SUB = "#93C5FD"
C_LAYER2 = "#F59E0B"   # orange / amber
C_LAYER2_SUB = "#FCD34D"
C_LAYER3 = "#10B981"   # green / emerald
C_LAYER3_SUB = "#6EE7B7"
C_ARROW  = "#374151"   # dark slate for inter-layer arrows
C_BG     = "#FFFFFF"

# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def rounded_box(ax, xy, w, h, label, color, fontsize=11, fontcolor="white", alpha=1.0, radius=0.02):
    """Draw a rounded rectangle with centred label."""
    x, y = xy
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0,rounding_size={radius}",
        facecolor=color, edgecolor="white", linewidth=1.2, alpha=alpha,
        transform=ax.transData, zorder=2,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, label,
            ha="center", va="center", fontsize=fontsize,
            fontweight="bold", color=fontcolor, zorder=3)
    return box


def layer_box(ax, xy, w, h, color, alpha=0.18):
    """Draw a large semi-transparent layer background."""
    x, y = xy
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0,rounding_size=0.03",
        facecolor=color, edgecolor=color, linewidth=2, alpha=alpha,
        transform=ax.transData, zorder=0,
    )
    ax.add_patch(box)
    return box


def arrow(ax, start, end, color=C_ARROW, style="->", lw=2.0, label=None, label_side="right"):
    """Draw an arrow from start to end with optional label."""
    ax.annotate(
        "",
        xy=end, xytext=start,
        arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                        connectionstyle="arc3,rad=0"),
        zorder=5,
    )
    if label is not None:
        mx = (start[0] + end[0]) / 2
        my = (start[1] + end[1]) / 2
        offset_x = 0.35 if label_side == "right" else -0.35
        ax.text(mx + offset_x, my, label,
                ha="left" if label_side == "right" else "right",
                va="center", fontsize=10, color=color,
                fontweight="bold", zorder=6)


# ---------------------------------------------------------------------------
# Main figure
# ---------------------------------------------------------------------------

def draw():
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(-0.5, 9.5)
    ax.set_ylim(-1.5, 14.5)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(C_BG)

    # ---- Input --------------------------------------------------------
    ax.text(4.5, 13.8, "用户输入 (文本 / 桌面截图)", ha="center", va="center",
            fontsize=13, fontweight="bold", color=C_INPUT)
    arrow(ax, (4.5, 13.5), (4.5, 12.55), color=C_INPUT, lw=2.5)

    # ==================================================================
    # Layer 1 – Routing Guard (blue)
    # ==================================================================
    layer_box(ax, (0.3, 8.8), 8.4, 3.5, C_LAYER1)
    ax.text(4.5, 12.05, "Layer 1: 路由层 (Routing Guard)",
            ha="center", va="center", fontsize=13, fontweight="bold", color=C_LAYER1)

    # Sub-modules
    rounded_box(ax, (0.7, 10.4), 3.4, 1.6, "文本意图分类器\n(Keyword Gate + LLM Extract)",
                C_LAYER1_SUB, fontsize=10, fontcolor="#1E3A5F")
    rounded_box(ax, (4.9, 10.4), 3.4, 1.6, "视觉上下文分析器\n(YOLOv8 UI Detection)",
                C_LAYER1_SUB, fontsize=10, fontcolor="#1E3A5F")

    # Output data object
    rounded_box(ax, (2.5, 9.1), 4.0, 0.9, "RoutingDecision (意图 / 动作 / 参数)",
                C_LAYER1, fontsize=10, fontcolor="white")

    # ==================================================================
    # Layer 2 – Roleplay Agent (orange)
    # ==================================================================
    layer_box(ax, (0.3, 4.5), 8.4, 3.5, C_LAYER2)
    ax.text(4.5, 7.75, "Layer 2: 角色层 (Roleplay Agent)",
            ha="center", va="center", fontsize=13, fontweight="bold", color=C_LAYER2)

    rounded_box(ax, (0.7, 6.1), 2.4, 1.2, "角色系统提示\n(System Prompt)",
                C_LAYER2_SUB, fontsize=10, fontcolor="#7C4A00")
    rounded_box(ax, (3.5, 6.1), 2.4, 1.2, "情绪追踪器\n(5-State FSM)",
                C_LAYER2_SUB, fontsize=10, fontcolor="#7C4A00")
    rounded_box(ax, (6.3, 6.1), 2.4, 1.2, "人格化输出\n(Persona Reply)",
                C_LAYER2_SUB, fontsize=10, fontcolor="#7C4A00")

    # Sub-label for delegation
    rounded_box(ax, (2.5, 4.8), 4.0, 0.9, "委托工作引擎 → 包装为人设风格输出",
                C_LAYER2, fontsize=10, fontcolor="white")

    # ==================================================================
    # Layer 3 – Work Engine (green)
    # ==================================================================
    layer_box(ax, (0.3, 0.2), 8.4, 3.6, C_LAYER3)
    ax.text(4.5, 3.55, "Layer 3: 工作引擎 (Work Engine / LangGraph)",
            ha="center", va="center", fontsize=13, fontweight="bold", color=C_LAYER3)

    # 5 subgraphs
    sg_labels = ["代码生成", "文件操作", "故障修复", "摘要生成", "其他任务"]
    sg_x = [0.6, 2.3, 4.0, 5.7, 7.4]
    for i, (lbl, x) in enumerate(zip(sg_labels, sg_x)):
        rounded_box(ax, (x, 1.7), 1.4, 1.4, f"子图 {i+1}\n{lbl}",
                    C_LAYER3_SUB, fontsize=9, fontcolor="#064E3B", radius=0.015)

    # Action Registry
    rounded_box(ax, (2.5, 0.5), 4.0, 0.9, "动作注册表 (Action Registry)",
                C_LAYER3, fontsize=10, fontcolor="white")

    # ==================================================================
    # Inter-layer arrows
    # ==================================================================
    arrow(ax, (4.5, 9.0), (4.5, 8.0), color=C_ARROW, lw=2.2,
          label="RoutingDecision", label_side="right")
    arrow(ax, (4.5, 4.5), (4.5, 3.8), color=C_ARROW, lw=2.2,
          label="任务委托", label_side="right")
    arrow(ax, (4.5, 1.6), (4.5, 0.8), color=C_ARROW, lw=2.2,
          label="动作执行", label_side="right")

    # ---- Output -------------------------------------------------------
    arrow(ax, (4.5, 0.5), (4.5, -0.3), color=C_INPUT, lw=2.5)
    ax.text(4.5, -0.8, "角色化响应输出", ha="center", va="center",
            fontsize=13, fontweight="bold", color=C_INPUT)

    # ---- Save ----------------------------------------------------------
    fig.tight_layout(pad=0.5)
    import os
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_path = os.path.join(OUTPUT_DIR, f"{OUTPUT_NAME}.pdf")
    png_path = os.path.join(OUTPUT_DIR, f"{OUTPUT_NAME}.png")

    fig.savefig(pdf_path, format="pdf", bbox_inches="tight", dpi=300)
    fig.savefig(png_path, format="png", bbox_inches="tight", dpi=300)
    plt.close(fig)
    print(f"Saved: {pdf_path}")
    print(f"Saved: {png_path}")


if __name__ == "__main__":
    draw()
