from __future__ import annotations

import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
MPL_CONFIG_DIR = PROJECT_DIR / "results" / ".matplotlib"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import solara
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Patch, Rectangle
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
    "pantry": "#a16207",
    "beverages": "#0ea5e9",
    "snacks": "#eab308",
    "frozen": "#60a5fa",
    "household": "#64748b",
    "personal_care": "#14b8a6",
    "checkout": "#111827",
}


def css_cell_style(
    background: str,
    color: str = "#111827",
    border: str = "#d1d5db",
    selected: bool = False,
) -> str:
    outline = "2px solid #111827" if selected else "0 solid transparent"
    return (
        "width:22px; min-width:22px; height:22px; min-height:22px; "
        "padding:0; margin:0; border-radius:2px; "
        f"border:1px solid {border}; background:{background}; color:{color}; "
        "font-size:9px; line-height:1; text-transform:none; "
        f"outline:{outline}; outline-offset:-2px;"
    )


def shopper_label(customer) -> str:
    return str(customer.uid)


def item_tooltip(item) -> str:
    promo = "yes" if item.promotion else "no"
    return (
        f"{item.name}\n"
        f"Category: {item.category}\n"
        f"Price: ${item.sale_price:.2f}\n"
        f"Profit: ${item.profit:.2f}\n"
        f"List chance: {item.list_probability_percent:.1f}%\n"
        f"Promotion: {promo}\n"
        f"Visibility: {item.visibility:.2f}"
    )


def customer_tooltip(customer) -> str:
    return (
        f"Shopper {customer.uid}\n"
        f"Type: {SHOPPER_PROFILES[customer.shopper_type].name}\n"
        f"State: {customer.state}\n"
        f"Patience: {customer.patience_level:.1f}/{customer.max_patience:.0f}\n"
        f"Basket items: {len(customer.bought_item_names)}\n"
        f"Remaining list: {len(customer.remaining_items)}"
    )


def cashier_tooltip(model: StoreModel, checkout_pos) -> str:
    detail = model.cashier_detail(checkout_pos)
    return (
        f"Cashier {checkout_pos}\n"
        f"Speed: {detail['speed']}\n"
        f"Service time: {detail['service_minutes']:.2f} min/shopper\n"
        f"Queue length: {detail['queue_length']}"
    )


def items_at_cell(model: StoreModel, pos):
    return model.layout.items_by_location.get(pos, [])


def active_customers_at_cell(model: StoreModel, pos):
    return [
        customer
        for customer in model.customers
        if customer.arrived and not customer.completed and customer.pos == pos
    ]


def selection_id(kind: str, key) -> str:
    if kind == "shopper":
        return f"shopper:{key}"
    if kind == "item":
        return f"item:{key}"
    if kind == "cashier":
        x, y = key
        return f"cashier:{x},{y}"
    return "none:"


def parse_selection(value: str):
    kind, _, key = value.partition(":")
    if kind == "shopper":
        try:
            return kind, int(key)
        except ValueError:
            return "none", None
    if kind == "cashier":
        try:
            x_text, y_text = key.split(",", 1)
            return kind, (int(x_text), int(y_text))
        except ValueError:
            return "none", None
    if kind == "item" and key:
        return kind, key
    return "none", None


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
def InteractiveStoreView(model: StoreModel):
    update_counter.get()
    selected_id, set_selected_id = solara.use_state("none:")

    def select(kind, key):
        def handler():
            set_selected_id(selection_id(kind, key))

        return handler

    solara.Column(
        gap="12px",
        children=[
            StoreGrid(model, selected_id, select),
            SelectionPanel(model, selected_id),
        ],
    )


@solara.component
def StoreGrid(model: StoreModel, selected_id: str, select):
    update_counter.get()
    selected_kind, selected_key = parse_selection(selected_id)

    with solara.Column(gap="8px", style="width:640px; min-width:640px; overflow-x:auto;"):
        solara.Markdown(
            f"**{model.layout_name.replace('_', ' ').title()} layout** | "
            f"{model.current_time_label} {model.current_traffic_period} | "
            f"Active {model.active_shopper_count}/{model.target_active_shopper_count} | "
            f"Products {len(model.layout.items)}"
        )
        with solara.GridFixed(
            columns=model.width,
            column_gap="1px",
            row_gap="1px",
            justify_items="center",
            align_items="center",
        ):
            for y in range(model.height - 1, -1, -1):
                for x in range(model.width):
                    pos = (x, y)
                    customers = active_customers_at_cell(model, pos)
                    items = items_at_cell(model, pos)
                    checkout_for_queue = model.layout.checkout_for_queue_cell(pos)

                    if customers:
                        customer = customers[0]
                        label = shopper_label(customer)
                        background = SHOPPER_COLORS[customer.shopper_type]
                        color = "white"
                        border = "#ffffff"
                        click_kind = "shopper"
                        click_key = customer.uid
                        tooltip = "\n\n".join(customer_tooltip(c) for c in customers)
                    elif items:
                        item = items[0]
                        label = "*" if item.promotion else "I"
                        background = CATEGORY_COLORS.get(item.category, "#94a3b8")
                        color = "#111827" if item.promotion else "white"
                        border = "#facc15" if item.promotion else "#111827"
                        click_kind = "item"
                        click_key = item.name
                        tooltip = "\n\n".join(item_tooltip(item) for item in items[:4])
                        if len(items) > 4:
                            tooltip += f"\n\n+ {len(items) - 4} more item(s)"
                    elif model.layout.is_checkout(pos):
                        label = "C"
                        background = "#fecaca"
                        color = "#7f1d1d"
                        border = "#dc2626"
                        click_kind = "cashier"
                        click_key = pos
                        tooltip = cashier_tooltip(model, pos)
                    elif checkout_for_queue is not None:
                        label = "Q"
                        background = "#fef08a"
                        color = "#1d4ed8"
                        border = "#2563eb"
                        click_kind = "cashier"
                        click_key = checkout_for_queue
                        tooltip = (
                            f"Queue lane for cashier {checkout_for_queue}\n"
                            f"Queue length: {model.checkout_queue_length_at(checkout_for_queue)}"
                        )
                    elif pos in model.layout.front_service_area_cells:
                        label = ""
                        background = "#fb923c"
                        color = "#111827"
                        border = "#ea580c"
                        click_kind = "none"
                        click_key = None
                        tooltip = "Cashier and entrance area"
                    elif pos in model.layout.checkout_queue_area_cells:
                        label = ""
                        background = "#fef08a"
                        color = "#111827"
                        border = "#eab308"
                        click_kind = "none"
                        click_key = None
                        tooltip = "Queue area"
                    elif pos in model.layout.shelf_categories:
                        category = model.layout.shelf_categories[pos]
                        label = "S"
                        background = CATEGORY_COLORS.get(category, "#94a3b8")
                        color = "white"
                        border = "#64748b"
                        click_kind = "none"
                        click_key = None
                        tooltip = f"Empty {category.replace('_', ' ')} shelf"
                    elif pos in model.layout.passable:
                        label = ""
                        background = "#f8fafc"
                        color = "#111827"
                        border = "#e5e7eb"
                        click_kind = "none"
                        click_key = None
                        tooltip = f"Aisle tile {pos}"
                    else:
                        label = ""
                        background = "#334155"
                        color = "white"
                        border = "#475569"
                        click_kind = "none"
                        click_key = None
                        tooltip = f"Wall {pos}"

                    cell_selection_id = selection_id(click_kind, click_key)
                    is_selected = click_kind != "none" and selected_id == cell_selection_id
                    if selected_kind == "cashier" and pos in model.layout.checkout_queue_cells.get(selected_key, []):
                        is_selected = True

                    with solara.Tooltip(tooltip):
                        solara.Button(
                            label=label,
                            on_click=select(click_kind, click_key),
                            text=True,
                            style=css_cell_style(
                                background,
                                color=color,
                                border=border,
                                selected=is_selected,
                            ),
                        )


@solara.component
def SelectionPanel(model: StoreModel, selected_id: str):
    update_counter.get()
    kind, key = parse_selection(selected_id)

    with solara.Column(gap="8px", style="min-width:300px; max-width:380px;"):
        solara.Markdown("### Selected Status")
        if kind == "shopper":
            customer = next((c for c in model.customers if c.uid == key), None)
            if customer is None:
                solara.Markdown("Shopper no longer exists in this run.")
                return
            basket = ", ".join(customer.bought_item_names) or "Empty"
            shopping_list = ", ".join(customer.shopping_list) or "None"
            remaining = ", ".join(customer.remaining_items) or "Complete"
            solara.Markdown(
                f"""
| Field | Value |
| --- | --- |
| Shopper | {customer.uid} |
| Type | {SHOPPER_PROFILES[customer.shopper_type].name} |
| State | {customer.state} |
| Position | {customer.pos} |
| Patience | {customer.patience_level:.1f} / {customer.max_patience:.0f} |
| Checkout patience | {customer.checkout_patience_level:.1f} |
| Time spent | {customer.time_spent} steps |
| Checkout wait | {customer.checkout_wait} steps |
| Congestion delay | {customer.congestion_delay} steps |
| Basket value | ${customer.basket_value:.2f} |
| Basket profit | ${customer.basket_profit:.2f} |
| Basket | {basket} |
| Shopping list | {shopping_list} |
| Remaining list | {remaining} |
"""
            )
        elif kind == "item":
            item = model.layout.items_by_name.get(key)
            if item is None:
                solara.Markdown("Item no longer exists in this run.")
                return
            solara.Markdown(
                f"""
| Field | Value |
| --- | --- |
| Item | {item.name} |
| Category | {item.category} |
| Position | {item.location} |
| Price | ${item.sale_price:.2f} |
| Profit | ${item.profit:.2f} |
| Margin | {item.margin:.0%} |
| List chance | {item.list_probability_percent:.1f}% |
| Promotion | {"Yes" if item.promotion else "No"} |
| Visibility | {item.visibility:.2f} |
| High exposure | {"Yes" if item.high_exposure else "No"} |
"""
            )
        elif kind == "cashier":
            detail = model.cashier_detail(key)
            nearby_checkout_items = [
                item.name
                for item in model.layout.nearby_items(key, radius=2)
                if item.category == "checkout"
            ]
            solara.Markdown(
                f"""
| Field | Value |
| --- | --- |
| Cashier position | {detail["position"]} |
| Speed | {detail["speed"]} |
| Service time | {detail["service_minutes"]:.2f} min/shopper |
| Queue length | {detail["queue_length"]} |
| Queue cells | {", ".join(str(cell) for cell in detail["queue_cells"])} |
| Nearby checkout items | {", ".join(nearby_checkout_items) or "None"} |
"""
            )
        else:
            solara.Markdown(
                "Click a shopper, item shelf, cashier, or queue lane to inspect it. "
                "Hover over products and cashiers for quick details."
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
            if (x, y) in model.layout.front_service_area_cells:
                draw_cell(ax, x, y, "#fb923c", edge="#ea580c")
            elif (x, y) in model.layout.checkout_queue_area_cells:
                draw_cell(ax, x, y, "#fef08a", edge="#eab308")
            elif (x, y) in model.layout.passable:
                draw_cell(ax, x, y, "#f8fafc")
            elif (x, y) in model.layout.shelf_categories:
                category = model.layout.shelf_categories[(x, y)]
                draw_cell(
                    ax,
                    x,
                    y,
                    CATEGORY_COLORS.get(category, "#94a3b8"),
                    alpha=0.42,
                    edge="#64748b",
                )
            else:
                draw_cell(ax, x, y, "#334155", edge="#475569")

    for x, y in model.layout.hot_zones:
        draw_cell(ax, x, y, "#fde68a", alpha=0.62, edge="#f59e0b")

    for x, y in model.layout.all_checkout_queue_cells:
        draw_cell(ax, x, y, "#fef08a", edge="#2563eb")
        ax.text(x, y, "Q", ha="center", va="center", fontsize=7, weight="bold", color="#1d4ed8")

    for entrance_x, entrance_y in model.layout.entrance_positions:
        draw_cell(ax, entrance_x, entrance_y, "#bbf7d0", edge="#16a34a")
        ax.text(entrance_x, entrance_y, "E", ha="center", va="center", fontsize=8, weight="bold")
    for checkout_x, checkout_y in model.layout.checkout_positions:
        draw_cell(ax, checkout_x, checkout_y, "#fecaca", edge="#dc2626")
        ax.text(checkout_x, checkout_y, "C", ha="center", va="center", fontsize=8, weight="bold")

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

    ax.text(
        0.01,
        0.99,
        f"{len(model.layout.items)} products",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color="#334155",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.9},
    )

    active_customers = [
        customer
        for customer in model.customers
        if customer.arrived and not customer.completed
    ]
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
        f"{model.current_time_label} {model.current_traffic_period} | "
        f"Active {model.active_shopper_count}/{model.target_active_shopper_count} | "
        f"Profit ${model.total_profit:.2f}",
        fontsize=12,
        pad=10,
    )
    ax.set_xticks([])
    ax.set_yticks([])

    shopper_legend_handles = [
        Circle((0, 0), radius=0.2, facecolor=color, edgecolor="white", label=SHOPPER_PROFILES[key].name)
        for key, color in SHOPPER_COLORS.items()
    ]
    category_legend_handles = [
        Patch(facecolor=color, edgecolor="#64748b", alpha=0.42, label=category.replace("_", " ").title())
        for category, color in CATEGORY_COLORS.items()
        if category != "checkout"
    ]
    first_legend = ax.legend(
        handles=shopper_legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.02),
        ncol=3,
        frameon=False,
        fontsize=8,
    )
    ax.add_artist(first_legend)
    ax.legend(
        handles=category_legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=5,
        frameon=False,
        fontsize=7,
    )
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[
            update_counter.value,
            model.layout_name,
            model.num_cashiers,
            model.num_shoppers,
            model.step_count,
        ],
    )


@solara.component
def LiveMetrics(model: StoreModel):
    update_counter.get()
    summary = model.summary()
    solara.Markdown(
        f"""
### Live Metrics

| Metric | Value |
| --- | ---: |
| Store time | {summary["current_store_time"]} |
| Traffic period | {summary["traffic_period"]} |
| Target traffic share | {summary["traffic_share"]:.0%} |
| Target active shoppers | {summary["target_active_shoppers"]} |
| Cashiers | {summary["cashiers"]} |
| Finished shoppers | {summary["finished_shoppers"]} / {summary["shoppers"]} |
| Abandoned shoppers | {summary["abandoned_shoppers"]} / {summary["shoppers"]} |
| Crowded tiles | {summary["crowded_tiles"]} |
| Tile capacity blocks | {summary["tile_capacity_blocks"]} |
| Waiting to arrive | {summary["waiting_shoppers"]} |
| Unique shopping lists | {summary["unique_shopping_lists"]} / {summary["shoppers"]} |
| Completion rate | {summary["completion_rate"]:.0%} |
| Abandonment rate | {summary["abandonment_rate"]:.0%} |
| Layout score | {summary["layout_score"]} / 100 |
| Avg. completion time | {summary["avg_completion_minutes"]} minutes |
| Avg. checkout wait | {summary["avg_checkout_wait"]} minutes |
| Longest checkout queue | {summary["longest_checkout_queue"]} shoppers |
| Avg. patience remaining | {summary["avg_patience_remaining"]} minutes |
| Avg. basket value | ${summary["avg_basket_value"]:.2f} |
| Avg. basket profit | ${summary["avg_basket_profit"]:.2f} |
| Avg. items per shopper | {summary["avg_items_per_shopper"]} |
| Planned purchases | {summary["planned_purchases"]} |
| Impulse purchases | {summary["impulse_purchases"]} |
| Unlisted purchases | {summary["unlisted_purchases"]} |
| Profit from unlisted purchases | ${summary["profit_from_unlisted"]:.2f} |
| Abandoned list items | {summary["abandoned_list_items"]} |
| Lost profit from abandonment | ${summary["lost_profit_from_abandonment"]:.2f} |
| Revenue | ${summary["revenue"]:.2f} |
| Profit | ${summary["profit"]:.2f} |
| Avg. congestion delay | {summary["avg_congestion_delay"]} steps |
| Avg. patience lost to congestion | {summary["avg_patience_lost_to_congestion"]} minutes |
| Tile crowding patience loss | {summary["tile_crowding_patience_loss"]} minutes |
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
        "type": "InputText",
        "value": "400",
        "label": "Daily shopper population",
    },
    "num_cashiers": {
        "type": "SliderInt",
        "value": 3,
        "label": "Cashiers",
        "min": 1,
        "max": 6,
        "step": 1,
    },
    "max_steps": {
        "type": "SliderInt",
        "value": 720,
        "label": "Simulation steps (9 AM to 9 PM)",
        "min": 120,
        "max": 1440,
        "step": 60,
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
    "height": 24,
}


model = StoreModel()

page = SolaraViz(
    model,
    components=[
        (InteractiveStoreView, 0),
        (LiveMetrics, 0),
        make_plot_component({"profit": "tab:green", "revenue": "tab:blue"}, page=1),
        make_plot_component(
            {
                "active_shoppers": "tab:red",
                "target_active_shoppers": "tab:pink",
                "waiting_shoppers": "tab:gray",
                "finished_shoppers": "tab:purple",
                "abandoned_shoppers": "tab:brown",
            },
            page=1,
        ),
        make_plot_component(
            {
                "planned_purchases": "tab:blue",
                "impulse_purchases": "tab:orange",
                "unlisted_purchases": "tab:red",
                "profit_from_unlisted": "tab:green",
                "lost_profit_from_abandonment": "tab:brown",
            },
            page=2,
        ),
    ],
    model_params=model_params,
    name="Store Layout ABM Live Simulation",
    play_interval=180,
)
page
