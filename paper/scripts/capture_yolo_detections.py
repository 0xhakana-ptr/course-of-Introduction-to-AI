"""Generate YOLOv8 detection visualization figures for paper Figure 2.
Creates 3 mock detection scenarios with bounding box annotations.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
from pathlib import Path

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(exist_ok=True)

# Color map for 6 UI classes
COLORS = {
    "activewindow": "#E53935",
    "address bar": "#1E88E5",
    "folder": "#43A047",
    "menubar": "#FB8C00",
    "tab": "#8E24AA",
    "window": "#00ACC1",
}

SCENARIOS = [
    {
        "title": "Case 1: Browsing (deep in research)",
        "activity": "deep in research",
        "quip": "开这么多标签，CPU 都要哭了~",
        "detections": [
            {"class_name": "tab", "bbox": [50, 20, 80, 15], "conf": 0.92},
            {"class_name": "tab", "bbox": [140, 20, 80, 15], "conf": 0.89},
            {"class_name": "tab", "bbox": [230, 20, 80, 15], "conf": 0.91},
            {"class_name": "tab", "bbox": [320, 20, 80, 15], "conf": 0.87},
            {"class_name": "tab", "bbox": [410, 20, 80, 15], "conf": 0.85},
            {"class_name": "activewindow", "bbox": [250, 200, 400, 250], "conf": 0.94},
        ],
    },
    {
        "title": "Case 2: File Management (navigating files)",
        "activity": "navigating files",
        "quip": "在整理文件嘛？需要帮忙吗~",
        "detections": [
            {"class_name": "folder", "bbox": [50, 100, 60, 60], "conf": 0.93},
            {"class_name": "folder", "bbox": [130, 100, 60, 60], "conf": 0.90},
            {"class_name": "folder", "bbox": [210, 100, 60, 60], "conf": 0.88},
            {"class_name": "address bar", "bbox": [100, 30, 350, 20], "conf": 0.91},
        ],
    },
    {
        "title": "Case 3: Idle Screen",
        "activity": "idle",
        "quip": "不理我要没电了哦...",
        "detections": [],
    },
]


def draw_scenario(scenario, save_path):
    fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    ax.set_xlim(0, 500)
    ax.set_ylim(0, 400)
    ax.set_facecolor("#2C2C2C")
    fig.patch.set_facecolor("#2C2C2C")

    for det in scenario["detections"]:
        cx, cy, w, h = det["bbox"]
        x, y = cx - w / 2, cy - h / 2
        color = COLORS.get(det["class_name"], "#FFFFFF")
        rect = patches.Rectangle((x, y), w, h, linewidth=2,
                                  edgecolor=color, facecolor="none")
        ax.add_patch(rect)
        label = f'{det["class_name"]} {det["conf"]:.2f}'
        ax.text(x, y - 5, label, fontsize=7, color=color,
                fontweight="bold", bbox=dict(boxstyle="round,pad=0.1",
                facecolor="black", alpha=0.7))

    # Activity label + quip at bottom
    ax.text(250, -30, f'Activity: {scenario["activity"]}',
            ha="center", fontsize=9, color="#FFFFFF",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="#1565C0", alpha=0.8))
    ax.text(250, -65, f'Quip: {scenario["quip"]}',
            ha="center", fontsize=8, color="#FFD54F",
            style="italic")

    ax.set_title(scenario["title"], fontsize=10, color="white", pad=10)
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#555555")

    plt.tight_layout()
    plt.savefig(save_path, dpi=200, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"Saved: {save_path}")


def main():
    for i, scenario in enumerate(SCENARIOS, 1):
        save_path = FIG_DIR / f"yolo_detection_case{i}.png"
        draw_scenario(scenario, save_path)
    print(f"All figures saved to {FIG_DIR}")


if __name__ == "__main__":
    main()
