"""Generate experiment result figures."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

def load_results():
    with open(DATA_DIR / "experiment_results.json", encoding="utf-8") as f:
        return json.load(f)

def plot_f1_vs_latency():
    results = load_results()
    order = ["Rule-Only", "Keyword-Score>=1", "Ours"]
    colors = ['#E74C3C', '#3498DB', '#27AE60']
    labels_zh = ['Rule-Only\n(B1)', 'Keyword-Score≥1\n(B3)', 'Ours\n(组合门控)']

    fig, ax = plt.subplots(figsize=(7, 5))
    for i, name in enumerate(order):
        if name in results:
            f1 = results[name]["weighted_f1"]
            lat = results[name]["avg_latency_ms"]
            ax.scatter(lat, f1, s=200, c=colors[i], edgecolors='black',
                      linewidth=1.5, zorder=5, label=labels_zh[i])
            ax.annotate(labels_zh[i], (lat, f1), textcoords="offset points",
                       xytext=(0, 18), ha='center', fontsize=9, fontweight='bold')

    ax.set_xlabel("Latency (ms)", fontsize=12)
    ax.set_ylabel("Weighted F1-Score", fontsize=12)
    ax.set_title("F1-Score vs. Inference Latency", fontsize=13, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-0.005, 0.04)
    ax.set_ylim(0.60, 0.85)
    ax.legend(loc='lower right', fontsize=9)
    fig.savefig(FIG_DIR / "fig_f1_vs_latency.png", dpi=200, bbox_inches='tight')
    plt.close()
    print("[OK] fig_f1_vs_latency.png")

def plot_ablation():
    results = load_results()
    variants = []
    f1_values = []
    if "Ours" in results:
        variants.append("Full System\n(组合门控)")
        f1_values.append(results["Ours"]["weighted_f1"])
    if "Keyword-Score>=1" in results:
        variants.append("w/o Gate\n(=B3)")
        f1_values.append(results["Keyword-Score>=1"]["weighted_f1"])
    if "Rule-Only" in results:
        variants.append("Rule-Only\n(=B1)")
        f1_values.append(results["Rule-Only"]["weighted_f1"])

    colors = ['#27AE60', '#F39C12', '#E74C3C']
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.barh(variants, f1_values, color=colors[:len(variants)],
                   edgecolor='black', linewidth=0.8, height=0.5)
    for bar, val in zip(bars, f1_values):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2,
               f'{val:.3f}', va='center', fontsize=12, fontweight='bold')
    ax.set_xlabel("Weighted F1-Score", fontsize=12)
    ax.set_title("Ablation Study: Intent Classification", fontsize=13, fontweight='bold')
    ax.set_xlim(0, 1.0)
    ax.grid(axis='x', alpha=0.3)
    ax.invert_yaxis()
    fig.savefig(FIG_DIR / "fig_ablation.png", dpi=200, bbox_inches='tight')
    plt.close()
    print("[OK] fig_ablation.png")

def plot_per_class_f1():
    results = load_results()
    methods = ["Rule-Only", "Keyword-Score>=1", "Ours"]
    classes = ["chat", "coding", "unknown"]
    x = np.arange(len(classes))
    width = 0.25
    colors = ['#E74C3C', '#3498DB', '#27AE60']

    fig, ax = plt.subplots(figsize=(8, 5))
    for i, name in enumerate(methods):
        if name in results:
            f1s = [results[name]["per_class"][c]["f1"] for c in classes]
            bars = ax.bar(x + i*width, f1s, width, label=name, color=colors[i],
                         edgecolor='black', linewidth=0.5)
            for bar, val in zip(bars, f1s):
                if val > 0.01:
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                           f'{val:.2f}', ha='center', fontsize=8, fontweight='bold')

    ax.set_ylabel("F1-Score", fontsize=12)
    ax.set_title("Per-Class F1-Score Comparison", fontsize=13, fontweight='bold')
    ax.set_xticks(x + width)
    ax.set_xticklabels(classes, fontsize=11)
    ax.legend(fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.grid(axis='y', alpha=0.3)
    fig.savefig(FIG_DIR / "fig_per_class_f1.png", dpi=200, bbox_inches='tight')
    plt.close()
    print("[OK] fig_per_class_f1.png")

if __name__ == "__main__":
    plot_f1_vs_latency()
    plot_ablation()
    plot_per_class_f1()
    print(f"\nAll figures saved to {FIG_DIR}")
