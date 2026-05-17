from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
MPL_CONFIG_DIR = PROJECT_DIR / "results" / ".matplotlib"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import solara
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
from mesa.visualization import SolaraViz, make_plot_component
from mesa.visualization.utils import update_counter

from customer_agent import SHOPPER_PROFILES
from model import StoreModel
from store_layout import LAYOUT_NAMES


SHOPPER_COLORS = {
    "mission_driven": "#2563eb",
    "bargain_hunter": "#16a34a",
    "impulse_buyer": "#dc2626",
    "loyal_shopper": "#7c3aed",
    "browser": "#f97316",
}

CATEGORY_COLORS = {
    "produce": "#22c55e",
    "bakery": "#d97706",
    "dairy": "#38bdf8",
    "meat": "#ef4444",
    "snacks": "#eab308",
    "frozen": "#60a5fa",
    "household": "#64748b",
    "checkout": "#111827",
}


def draw_cell(ax, x: int, y: int, color: str, alpha: float = 1.0, edge: str = "#e5e7eb"):
    ax.add_patch(
        Rectangle(
            (x - 0.5, y - 0.5),
            1,
            1,
            facecolor=color,
            edgecolor=edge,
            linewidth=0.35,
            alpha=alpha,
        )
    )


@solara.component
def StoreMap(model: StoreModel):
    update_counter.get()

    fig = Figure(figsize=(10, 6), dpi=110)
    ax = fig.subplots()
    ax.set_xlim(-0.5, model.width - 0.5)
    ax.set_ylim(-0.5, model.height - 0.5)
    ax.set_aspect("equal")
    ax.set_facecolor("#f8fafc")

    for x in range(model.width):
        for y in range(model.height):
            if (x, y) in model.layout.passable:
                draw_cell(ax, x, y, "#f8fafc")
            else:
                draw_cell(ax, x, y, "#334155", edge="#475569")

    for x, y in model.layout.hot_zones:
        draw_cell(ax, x, y, "#fde68a", alpha=0.62, edge="#f59e0b")

    entrance_x, entrance_y = model.layout.entrance
    checkout_x, checkout_y = model.layout.checkout
    draw_cell(ax, entrance_x, entrance_y, "#bbf7d0", edge="#16a34a")
    draw_cell(ax, checkout_x, checkout_y, "#fecaca", edge="#dc2626")
    ax.text(entrance_x, entrance_y, "IN", ha="center", va="center", fontsize=8, weight="bold")
    ax.text(checkout_x, checkout_y, "PAY", ha="center", va="center", fontsize=7, weight="bold")

    for item in model.layout.items:
        x, y = item.location
        color = CATEGORY_COLORS[item.category]
        ax.scatter(
            [x],
            [y],
            marker="s",
            s=90 if item.high_exposure else 62,
            c=color,
            edgecolors="#111827",
            linewidths=0.55,
            alpha=0.88,
            zorder=3,
        )
        if item.promotion:
            ax.scatter([x + 0.23], [y + 0.23], marker="*", s=55, c="#facc15", edgecolors="#78350f", zorder=4)

    active_customers = [customer for customer in model.customers if not customer.completed]
    offsets = [
        (0.00, 0.00),
        (0.18, 0.00),
        (-0.18, 0.00),
        (0.00, 0.18),
        (0.00, -0.18),
        (0.14, 0.14),
        (-0.14, 0.14),
        (0.14, -0.14),
        (-0.14, -0.14),
    ]
    cell_counts: dict[tuple[int, int], int] = {}
    for customer in active_customers:
        count = cell_counts.get(customer.pos, 0)
        cell_counts[customer.pos] = count + 1
        dx, dy = offsets[count % len(offsets)]
        color = SHOPPER_COLORS[customer.shopper_type]
        ax.scatter(
            [customer.pos[0] + dx],
            [customer.pos[1] + dy],
            c=color,
            s=70,
            marker="o",
            edgecolors="white",
            linewidths=0.8,
            zorder=5,
        )

    ax.set_title(
        f"{model.layout_name.replace('_', ' ').title()} layout | "
        f"Step {model.step_count} | Active {model.active_shopper_count} | "
        f"Profit ${model.total_profit:.2f}",
        fontsize=12,
        pad=10,
    )
    ax.set_xticks([])
    ax.set_yticks([])

    legend_handles = [
        Circle((0, 0), radius=0.2, facecolor=color, edgecolor="white", label=SHOPPER_PROFILES[key].name)
        for key, color in SHOPPER_COLORS.items()
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncol=3,
        frameon=False,
        fontsize=8,
    )
    fig.tight_layout()
    solara.FigureMatplotlib(fig, format="png", bbox_inches="tight", dependencies=[update_counter.value])


@solara.component
def LiveMetrics(model: StoreModel):
    update_counter.get()
    summary = model.summary()
    solara.Markdown(
        f"""
### Live Metrics

| Metric | Value |
| --- | ---: |
| Finished shoppers | {summary["finished_shoppers"]} / {summary["shoppers"]} |
| Completion rate | {summary["completion_rate"]:.0%} |
| Avg. completion time | {summary["avg_completion_time"]} steps |
| Planned purchases | {summary["planned_purchases"]} |
| Impulse purchases | {summary["impulse_purchases"]} |
| Revenue | ${summary["revenue"]:.2f} |
| Profit | ${summary["profit"]:.2f} |
| Avg. congestion delay | {summary["avg_congestion_delay"]} steps |
"""
    )


model_params = {
    "layout_name": {
        "type": "Select",
        "value": "grid",
        "label": "Store layout",
        "values": list(LAYOUT_NAMES),
    },
    "num_shoppers": {
        "type": "SliderInt",
        "value": 40,
        "label": "Number of shoppers",
        "min": 5,
        "max": 120,
        "step": 5,
    },
    "max_steps": {
        "type": "SliderInt",
        "value": 250,
        "label": "Max simulation steps",
        "min": 50,
        "max": 500,
        "step": 25,
    },
    "promotion_level": {
        "type": "SliderFloat",
        "value": 0.25,
        "label": "Promotion level",
        "min": 0.0,
        "max": 0.8,
        "step": 0.05,
    },
    "seed": {
        "type": "SliderInt",
        "value": 42,
        "label": "Random seed",
        "min": 1,
        "max": 9999,
        "step": 1,
    },
    "width": 24,
    "height": 16,
}


model = StoreModel()

page = SolaraViz(
    model,
    components=[
        (StoreMap, 0),
        (LiveMetrics, 0),
        make_plot_component({"profit": "tab:green", "revenue": "tab:blue"}, page=1),
        make_plot_component({"active_shoppers": "tab:red", "finished_shoppers": "tab:purple"}, page=1),
        make_plot_component({"planned_purchases": "tab:blue", "impulse_purchases": "tab:orange"}, page=2),
    ],
    model_params=model_params,
    name="Store Layout ABM Live Simulation",
    play_interval=180,
)
page
