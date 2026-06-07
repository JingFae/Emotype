from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
import seaborn as sns


OUTPUT_DIR = Path(__file__).resolve().parent / "assets"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOKENS = {
    "surface": "#FCFCFD",
    "panel": "#FFFFFF",
    "ink": "#1F2430",
    "muted": "#6F768A",
    "grid": "#E6E8F0",
    "axis": "#D7DBE7",
}

COLORS = {
    "blue": {"base": "#A3BEFA", "dark": "#2E4780"},
    "gold": {"base": "#FFE15B", "dark": "#736422"},
    "orange": {"base": "#F0986E", "dark": "#804126"},
}


def add_chart_header(fig, ax, title, subtitle):
    title = textwrap.fill(title, width=72, break_long_words=False)
    subtitle = textwrap.fill(subtitle, width=105, break_long_words=False)
    ax.set_title("")
    fig.subplots_adjust(top=0.76, left=0.12, right=0.96, bottom=0.18)
    left = ax.get_position().x0
    fig.text(
        left,
        0.97,
        title,
        ha="left",
        va="top",
        fontsize=15,
        fontweight="semibold",
        color=TOKENS["ink"],
    )
    fig.text(
        left,
        0.89,
        subtitle,
        ha="left",
        va="top",
        fontsize=9.5,
        color=TOKENS["muted"],
    )


sns.set_theme(
    style="whitegrid",
    rc={
        "figure.facecolor": TOKENS["surface"],
        "savefig.facecolor": TOKENS["surface"],
        "axes.facecolor": TOKENS["panel"],
        "axes.edgecolor": TOKENS["axis"],
        "axes.labelcolor": TOKENS["ink"],
        "grid.color": TOKENS["grid"],
        "grid.linewidth": 0.8,
        "font.family": "sans-serif",
        "font.sans-serif": ["Aptos", "Inter", "Segoe UI", "DejaVu Sans", "Arial"],
    },
)

tasks = ["Emotion understanding", "Emotion reasoning", "Emotion-guided generation"]
gains = [6.15, 3.54, 3.96]
fills = [COLORS["blue"]["base"], COLORS["gold"]["base"], COLORS["orange"]["base"]]
edges = [COLORS["blue"]["dark"], COLORS["gold"]["dark"], COLORS["orange"]["dark"]]

fig, ax = plt.subplots(figsize=(9.6, 4.9), dpi=160)
bars = ax.bar(tasks, gains, color=fills, edgecolor=edges, linewidth=1.0, width=0.62)

for bar, value in zip(bars, gains):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        value + 0.16,
        f"+{value:.2f} pp",
        ha="center",
        va="bottom",
        fontsize=10,
        fontweight="semibold",
        color=TOKENS["ink"],
    )

ax.set_ylabel("Average improvement (percentage points)")
ax.set_ylim(0, 7.1)
ax.yaxis.grid(True)
ax.xaxis.grid(False)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.tick_params(axis="x", labelsize=9)
ax.tick_params(axis="y", labelsize=8, colors=TOKENS["muted"])

add_chart_header(
    fig,
    ax,
    "GAT improves all three affective image tasks",
    "Average gains reported in the accepted AICA-Bench paper; the largest improvement is in emotion understanding.",
)

output_path = OUTPUT_DIR / "gat_task_gains.png"
fig.savefig(output_path, bbox_inches="tight", facecolor=TOKENS["surface"])
plt.close(fig)
print(output_path)
