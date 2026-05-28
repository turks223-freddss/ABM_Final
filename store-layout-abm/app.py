from __future__ import annotations

import asyncio
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
MPL_CONFIG_DIR = PROJECT_DIR / "results" / ".matplotlib"
MPL_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CONFIG_DIR))

import solara
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Patch, Rectangle
from mesa.visualization import make_plot_component
import mesa.visualization.solara_viz as mesa_solara_viz
from mesa.visualization.utils import force_update, update_counter

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


SHOPPER_DOT_POSITIONS = {
    1: ((50, 50),),
    2: ((38, 50), (62, 50)),
    3: ((50, 34), (36, 64), (64, 64)),
    4: ((35, 35), (65, 35), (35, 65), (65, 65)),
}


def css_cell_style(
    background: str,
    color: str = "#111827",
    border: str = "#d1d5db",
    selected: bool = False,
    selected_shopper: bool = False,
) -> str:
    if selected_shopper:
        outline = "3px solid #f59e0b"
        outline_offset = "-3px"
        box_shadow = "0 0 0 2px #fff7ed, 0 0 12px rgba(245,158,11,0.85)"
    elif selected:
        outline = "2px solid #111827"
        outline_offset = "-2px"
        box_shadow = "none"
    else:
        outline = "0 solid transparent"
        outline_offset = "-2px"
        box_shadow = "none"
    return (
        "width:22px; min-width:22px; height:22px; min-height:22px; "
        "padding:0; margin:0; border-radius:2px; "
        f"border:1px solid {border}; background:{background}; color:{color}; "
        "font-size:9px; line-height:1; text-transform:none; "
        f"outline:{outline}; outline-offset:{outline_offset}; box-shadow:{box_shadow};"
    )


def shopper_circle_background(background: str, customers, selected_shopper_id: int | None = None) -> str:
    if not customers:
        return background

    selected_customers = [
        customer for customer in customers if customer.uid == selected_shopper_id
    ]
    if selected_customers:
        visible_customers = [
            selected_customers[0],
            *[customer for customer in customers if customer.uid != selected_shopper_id],
        ][:4]
    else:
        visible_customers = customers[:4]
    dot_positions = SHOPPER_DOT_POSITIONS[len(visible_customers)]
    dot_layers = [
        (
            f"radial-gradient(circle at {x}% {y}%, "
            f"{SHOPPER_COLORS[customer.shopper_type]} 0 "
            f"{'4.4px' if customer.uid == selected_shopper_id else '3.5px'}, "
            f"#ffffff {'4.6px 5.8px' if customer.uid == selected_shopper_id else '3.7px 4.8px'}, "
            f"{'#facc15 6px 7.4px, #111827 7.6px 8.2px, ' if customer.uid == selected_shopper_id else ''}"
            f"transparent {'8.4px' if customer.uid == selected_shopper_id else '5px'})"
        )
        for customer, (x, y) in zip(visible_customers, dot_positions)
    ]
    return ", ".join([*dot_layers, background])


def item_tooltip(item) -> str:
    promo = "yes" if item.promotion else "no"
    discount = f"{item.discount_percent:.1f}%" if item.promotion else "0.0%"
    return (
        f"{item.name}\n"
        f"Category: {item.category}\n"
        f"Price: ${item.sale_price:.2f}\n"
        f"List chance: {item.list_probability_percent:.1f}%\n"
        f"Promotion: {promo}\n"
        f"Discount: {discount}\n"
        f"Visibility: {item.visibility:.2f}"
    )


def customer_tooltip(customer) -> str:
    return (
        f"Shopper {customer.uid}\n"
        f"Type: {SHOPPER_PROFILES[customer.shopper_type].name}\n"
        f"State: {customer.state}\n"
        f"Heading checkout: {'yes' if getattr(customer, 'should_head_to_checkout', False) else 'no'}\n"
        f"Patience: {customer.patience_level:.1f}/{customer.max_patience:.0f} "
        f"({customer.patience_ratio:.0%})\n"
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


def legend_swatch(color: str, border: str = "#64748b", shape: str = "square") -> str:
    radius = "999px" if shape == "circle" else "2px"
    return (
        "<span style='display:inline-block; width:0.85em; height:0.85em; "
        f"border-radius:{radius}; background:{color}; border:1px solid {border}; "
        "vertical-align:-0.08em; margin-right:0.35em;'></span>"
    )


def legend_item(label: str, color: str, border: str = "#64748b", shape: str = "square") -> str:
    return f"{legend_swatch(color, border=border, shape=shape)}{label}"


@solara.component
def InteractiveStoreView(model: StoreModel):
    selected_id, set_selected_id = solara.use_state("none:")
    show_live_metrics, set_show_live_metrics = solara.use_state(False)

    def select(kind, key):
        def handler():
            set_selected_id(selection_id(kind, key))

        return handler

    solara.Row(
        gap="16px",
        style="align-items:flex-start; width:100%; overflow-x:auto; flex-wrap:nowrap;",
        children=[
            StoreGrid(model, selected_id, select),
            PageZeroStatusPanel(model, selected_id, show_live_metrics, set_show_live_metrics),
        ],
    )


@solara.component
def PageZeroStatusPanel(model: StoreModel, selected_id: str, show_live_metrics: bool, set_show_live_metrics):
    with solara.Column(
        gap="8px",
        style=(
            "width:360px; min-width:320px; max-width:420px; "
            "flex:0 0 360px; max-height:72vh; overflow:auto;"
        ),
    ):
        solara.Switch(
            label="Show Live Metrics",
            value=show_live_metrics,
            on_value=set_show_live_metrics,
        )
        if show_live_metrics:
            LiveMetrics(model)
        else:
            SelectionPanel(model, selected_id)


@solara.component
def StoreGrid(model: StoreModel, selected_id: str, select):
    update_counter.get()
    selected_kind, selected_key = parse_selection(selected_id)
    selected_shopper_id = selected_key if selected_kind == "shopper" else None

    with solara.Column(gap="8px", style="width:640px; min-width:640px; flex:0 0 640px;"):
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

                    if items:
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
                    elif pos in model.layout.wall_cells:
                        label = "W"
                        background = "#111827"
                        color = "white"
                        border = "#020617"
                        click_kind = "none"
                        click_key = None
                        tooltip = f"Manual wall {pos}"
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

                    if customers:
                        customer = customers[0]
                        label = ""
                        selected_shopper_on_tile = any(
                            c.uid == selected_shopper_id for c in customers
                        )
                        background = shopper_circle_background(
                            background,
                            customers,
                            selected_shopper_id,
                        )
                        click_kind = "shopper"
                        click_key = customer.uid
                        tooltip = (
                            f"{len(customers)} shopper(s) on this tile\n\n"
                            + "\n\n".join(customer_tooltip(c) for c in customers)
                        )
                    else:
                        selected_shopper_on_tile = False

                    cell_selection_id = selection_id(click_kind, click_key)
                    is_selected = click_kind != "none" and selected_id == cell_selection_id
                    if selected_shopper_on_tile:
                        is_selected = True
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
                                selected_shopper=selected_shopper_on_tile,
                            ),
                        )
        StoreLegend()


@solara.component
def StoreLegend():
    shopper_items = " &nbsp; ".join(
        legend_item(SHOPPER_PROFILES[key].name, color, border="#ffffff", shape="circle")
        for key, color in SHOPPER_COLORS.items()
    )
    category_items = " &nbsp; ".join(
        legend_item(category.replace("_", " ").title(), color)
        for category, color in CATEGORY_COLORS.items()
    )
    solara.Markdown(
        f"""
**Shopper types:** {shopper_items}

**Item categories:** {category_items}

**Other:** {legend_item("Sale item", "#facc15", border="#78350f")} {legend_item("Cashier", "#fecaca", border="#dc2626")} {legend_item("Queue", "#fef08a", border="#2563eb")} {legend_item("Wall", "#111827", border="#020617")}
"""
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
            planned_completion = (
                f"{customer.planned_completion_rate:.0%}"
                if customer.shopping_list
                else "No planned list"
            )
            solara.Markdown(
                f"""
| Field | Value |
| --- | --- |
| Shopper | {customer.uid} |
| Type | {SHOPPER_PROFILES[customer.shopper_type].name} |
| State | {customer.state} |
| Position | {customer.pos} |
| Heading checkout | {"Yes" if getattr(customer, "should_head_to_checkout", False) else "No"} |
| Patience | {customer.patience_level:.1f} / {customer.max_patience:.0f} ({customer.patience_ratio:.0%}) |
| Checkout patience | {customer.checkout_patience_level:.1f} |
| Time spent | {customer.time_spent} steps |
| Checkout wait | {customer.checkout_wait} steps |
| Congestion delay | {customer.congestion_delay} steps |
| Shopping-list completion | {planned_completion} |
| Planned purchases | {len(customer.planned_purchases)} |
| Unplanned purchases | {len(customer.impulse_purchases)} |
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
| List chance | {item.list_probability_percent:.1f}% |
| Promotion | {"Yes" if item.promotion else "No"} |
| Discount | {item.discount_percent:.1f}% |
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
| Speed mode | Fixed |
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
            elif (x, y) in model.layout.wall_cells:
                draw_cell(ax, x, y, "#111827", edge="#020617")
                ax.text(x, y, "W", ha="center", va="center", fontsize=7, weight="bold", color="white")
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

    for x, y in model.layout.hot_zones - model.layout.wall_cells:
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
        f"Completed lists {model.completed_shopping_list_count}/{model.num_shoppers}",
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
    completed_lists = (
        f'{summary["completed_shopping_lists"]} / {summary["shoppers_with_shopping_lists"]}'
        if summary["shoppers_with_shopping_lists"]
        else "No planned lists"
    )
    solara.Markdown(
        f"""
### Live Metrics

| Metric | Value |
| --- | ---: |
| Store time | {summary["current_store_time"]} |
| Last shopper arrival | {summary["last_arrival_time"]} |
| Checkout cutoff | {summary["checkout_cutoff_time"]} |
| Checkout cutoff active | {"Yes" if summary["checkout_cutoff_active"] else "No"} |
| Traffic period | {summary["traffic_period"]} |
| Target traffic share | {summary["traffic_share"]:.0%} |
| Target active shoppers | {summary["target_active_shoppers"]} |
| Cashiers | {summary["cashiers"]} |
| Cashier speed | {summary["cashier_service_mode"].title()} ({summary["fixed_cashier_service_minutes"]:.1f} min/shopper) |
| Sale items | {summary["sale_items"]} |
| Avg. sale discount | {summary["avg_sale_discount_percentage"]:.1f}% |
| Shopping list max setting | {summary["shopping_list_max_setting"] or "Profile default"} |
| Patience threshold | {summary["patience_threshold_percentage"]:.0f}% |
| Browser time limit | {summary["browser_time_limit_minutes"]:.0f} minutes |
| Finished shoppers | {summary["finished_shoppers"]} / {summary["shoppers"]} |
| Heading to checkout | {summary["checkout_bound_shoppers"]} |
| Abandoned shoppers | {summary["abandoned_shoppers"]} / {summary["shoppers"]} |
| Shoppers with shopping lists | {summary["shoppers_with_shopping_lists"]} / {summary["shoppers"]} |
| Completed shopping lists | {completed_lists} |
| Not completed shopping lists | {summary["incomplete_shopping_lists"]} |
| Items not found | {summary["items_not_found"]} |
| Abandoned: time | {summary["abandoned_due_to_time"]} |
| Abandoned: traffic | {summary["abandoned_due_to_traffic"]} |
| Abandoned: congestion | {summary["abandoned_due_to_congestion"]} |
| Abandoned: checkout | {summary["abandoned_due_to_checkout"]} |
| Crowded tiles | {summary["crowded_tiles"]} |
| Tile capacity blocks | {summary["tile_capacity_blocks"]} |
| Blocked congestion frequency | {summary["congestion_block_frequency"]} / step |
| Waiting to arrive | {summary["waiting_shoppers"]} |
| Unique shopping lists | {summary["unique_shopping_lists"]} / {summary["shoppers"]} |
| Trip completion rate | {summary["completion_rate"]:.0%} |
| Avg. shopping-list completion | {summary["avg_planned_completion"]:.0%} |
| Abandonment rate | {summary["abandonment_rate"]:.0%} |
| Layout score | {summary["layout_score"]} / 100 |
| Avg. completion time | {summary["avg_completion_minutes"]} minutes |
| Avg. checkout wait | {summary["avg_checkout_wait"]} minutes |
| Longest checkout queue | {summary["longest_checkout_queue"]} shoppers |
| Avg. patience remaining | {summary["avg_patience_remaining"]} minutes |
| Avg. patience drop | {summary["avg_patience_drop"]} minutes |
| Avg. items per shopper | {summary["avg_items_per_shopper"]} |
| Planned purchases | {summary["planned_purchases"]} |
| Unplanned purchases | {summary["unplanned_purchases"]} |
| Abandoned list items | {summary["abandoned_list_items"]} |
| Avg. congestion delay | {summary["avg_congestion_delay"]} steps |
| Avg. patience lost to congestion | {summary["avg_patience_lost_to_congestion"]} minutes |
| Tile crowding patience loss | {summary["tile_crowding_patience_loss"]} minutes |
"""
    )


def label_bars(ax, bars) -> None:
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height:.0f}",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )


@solara.component
def ShoppingListCompletionFigure(model: StoreModel):
    update_counter.get()
    completed = model.completed_shopping_list_count
    incomplete = model.incomplete_shopping_list_count

    fig = Figure(figsize=(5.8, 3.4), dpi=110)
    ax = fig.subplots()
    bars = ax.bar(
        ["Completed list", "Not completed"],
        [completed, incomplete],
        color=["#16a34a", "#94a3b8"],
    )
    ax.set_title("Shopping-list completion")
    ax.set_ylabel("Shoppers")
    ax.set_ylim(0, max(1, model.num_shoppers) * 1.12)
    label_bars(ax, bars)
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[
            model.step_count,
            completed,
            incomplete,
        ],
    )


@solara.component
def PlannedVsUnplannedFigure(model: StoreModel):
    update_counter.get()
    planned = model.planned_purchase_count
    unplanned = model.unplanned_purchase_count

    fig = Figure(figsize=(5.8, 3.4), dpi=110)
    ax = fig.subplots()
    bars = ax.bar(
        ["Planned", "Unplanned"],
        [planned, unplanned],
        color=["#2563eb", "#f97316"],
    )
    ax.set_title("Planned vs. unplanned purchases")
    ax.set_ylabel("Purchased items")
    ax.set_ylim(0, max(1, planned, unplanned) * 1.18)
    label_bars(ax, bars)
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[
            model.step_count,
            planned,
            unplanned,
        ],
    )


@solara.component
def ShopperTypeOutcomeFigure(model: StoreModel):
    update_counter.get()
    rows = model.shopper_type_summary()
    labels = [row["profile_name"] for row in rows]
    finished = [row["finished_shoppers"] for row in rows]
    abandoned = [row["abandoned_shoppers"] for row in rows]
    x_positions = list(range(len(labels)))
    width = 0.38

    fig = Figure(figsize=(8.2, 3.8), dpi=110)
    ax = fig.subplots()
    finished_bars = ax.bar(
        [x - width / 2 for x in x_positions],
        finished,
        width,
        label="Completed trip",
        color="#16a34a",
    )
    abandoned_bars = ax.bar(
        [x + width / 2 for x in x_positions],
        abandoned,
        width,
        label="Abandoned trip",
        color="#dc2626",
    )
    ax.set_title("Trip outcome by shopper type")
    ax.set_ylabel("Shoppers")
    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, max(1, *(finished + abandoned)) * 1.18)
    ax.legend(frameon=False, fontsize=8)
    label_bars(ax, finished_bars)
    label_bars(ax, abandoned_bars)
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[
            model.step_count,
            model.finished_shopper_count,
            model.abandoned_shopper_count,
        ],
    )


@solara.component
def CongestionPatienceFigure(model: StoreModel):
    update_counter.get()
    model_df = model.datacollector.get_model_vars_dataframe()

    fig = Figure(figsize=(8.2, 3.8), dpi=110)
    ax1 = fig.subplots()
    ax2 = ax1.twinx()

    if model_df.empty:
        steps = [model.step_count]
        blocked = [model.tile_capacity_blocks]
        blocked_frequency = [model.congestion_block_frequency]
        patience_remaining = [model.avg_patience_remaining]
        patience_drop = [model.avg_patience_drop]
    else:
        def column_values(name: str):
            return model_df[name].tolist() if name in model_df else []

        steps = model_df["step"].tolist()
        blocked = column_values("tile_capacity_blocks")
        blocked_frequency = column_values("congestion_block_frequency")
        patience_remaining = column_values("avg_patience_remaining")
        patience_drop = column_values("avg_patience_drop")

    if blocked:
        ax1.plot(steps, blocked, color="#b91c1c", label="Blocked moves")
    if blocked_frequency:
        ax1.plot(
            steps,
            blocked_frequency,
            color="#78350f",
            linestyle="--",
            label="Blocked frequency",
        )
    if patience_remaining:
        ax2.plot(
            steps,
            patience_remaining,
            color="#16a34a",
            linestyle="-",
            label="Avg. patience remaining",
        )
    if patience_drop:
        ax2.plot(
            steps,
            patience_drop,
            color="#0f766e",
            linestyle=":",
            label="Avg. patience drop",
        )

    ax1.set_title("Blocked congestion and patience over time")
    ax1.set_xlabel("Simulation step")
    ax1.set_ylabel("Blocked moves / frequency")
    ax2.set_ylabel("Minutes")
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="best", fontsize=8, frameon=False)
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[
            model.step_count,
            model.tile_capacity_blocks,
            round(model.avg_patience_drop, 2),
        ],
    )


@solara.component
def ShopperTypeUnplannedFigure(model: StoreModel):
    update_counter.get()
    rows = model.shopper_type_summary()
    labels = [row["profile_name"] for row in rows]
    values = [row["unplanned_purchases"] for row in rows]
    x_positions = list(range(len(labels)))

    fig = Figure(figsize=(8.2, 3.8), dpi=110)
    ax = fig.subplots()
    bars = ax.bar(x_positions, values, color=[SHOPPER_COLORS[row["shopper_type"]] for row in rows])
    ax.set_title("Unplanned purchases by shopper type")
    ax.set_ylabel("Items")
    ax.set_xticks(list(range(len(labels))))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, max(1, *values) * 1.18)
    label_bars(ax, bars)
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[model.step_count, model.unplanned_purchase_count],
    )


@solara.component
def ShopperTypeCompletionTimeFigure(model: StoreModel):
    update_counter.get()
    rows = model.shopper_type_summary()
    labels = [row["profile_name"] for row in rows]
    values = [row["avg_completion_minutes"] for row in rows]
    x_positions = list(range(len(labels)))

    fig = Figure(figsize=(8.2, 3.8), dpi=110)
    ax = fig.subplots()
    bars = ax.bar(x_positions, values, color=[SHOPPER_COLORS[row["shopper_type"]] for row in rows])
    ax.set_title("Average completion time by shopper type")
    ax.set_ylabel("Minutes")
    ax.set_xticks(list(range(len(labels))))
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylim(0, max(1, *values) * 1.18)
    label_bars(ax, bars)
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[model.step_count, round(model.avg_completion_minutes, 2)],
    )


@solara.component
def StoreTrafficHeatmapFigure(model: StoreModel):
    update_counter.get()
    heatmap = model.traffic_heatmap()
    max_visits = max(1, int(heatmap.max()))

    fig = Figure(figsize=(8.8, 6.2), dpi=110)
    ax = fig.subplots()
    image = ax.imshow(
        heatmap,
        origin="lower",
        cmap="YlOrRd",
        vmin=0,
        vmax=max_visits,
        alpha=0.88,
    )

    for x in range(model.width):
        for y in range(model.height):
            ax.add_patch(
                Rectangle(
                    (x - 0.5, y - 0.5),
                    1,
                    1,
                    facecolor="none",
                    edgecolor="#cbd5e1",
                    linewidth=0.22,
                    alpha=0.5,
                )
            )

    for x, y in model.layout.wall_cells:
        ax.add_patch(
            Rectangle(
                (x - 0.5, y - 0.5),
                1,
                1,
                facecolor="#111827",
                edgecolor="#020617",
                linewidth=0.45,
                alpha=0.92,
            )
        )

    for pos, category in model.layout.shelf_categories.items():
        if pos in model.layout.wall_cells:
            continue
        x, y = pos
        ax.add_patch(
            Rectangle(
                (x - 0.5, y - 0.5),
                1,
                1,
                facecolor=CATEGORY_COLORS.get(category, "#94a3b8"),
                edgecolor="#111827",
                linewidth=0.35,
                alpha=0.26,
            )
        )

    for x, y in model.layout.all_checkout_queue_cells:
        ax.text(x, y, "Q", ha="center", va="center", fontsize=6.5, weight="bold", color="#1d4ed8")

    for x, y in model.layout.entrance_positions:
        ax.scatter([x], [y], c="#bbf7d0", s=95, marker="s", edgecolors="#16a34a", linewidths=0.8, zorder=4)
        ax.text(x, y, "E", ha="center", va="center", fontsize=8, weight="bold", zorder=5)

    for x, y in model.layout.checkout_positions:
        ax.scatter([x], [y], c="#fecaca", s=95, marker="s", edgecolors="#dc2626", linewidths=0.8, zorder=4)
        ax.text(x, y, "C", ha="center", va="center", fontsize=8, weight="bold", zorder=5)

    ax.set_title(
        f"Store traffic heatmap: {model.layout_name.replace('_', ' ').title()}",
        fontsize=12,
        pad=10,
    )
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_xlim(-0.5, model.width - 0.5)
    ax.set_ylim(-0.5, model.height - 0.5)
    ax.set_aspect("equal")
    fig.colorbar(image, ax=ax, label="Tile visits", shrink=0.78)
    fig.tight_layout()
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[
            model.step_count,
            model.layout_name,
            model.num_shoppers,
            model.num_cashiers,
        ],
    )


@solara.component
def ShopperTypeHeatmapFigure(model: StoreModel):
    update_counter.get()
    heatmaps = model.traffic_heatmap_by_shopper_type()
    max_visits = max(int(heatmap.max()) for heatmap in heatmaps.values()) if heatmaps else 1
    max_visits = max(1, max_visits)

    fig = Figure(figsize=(9.2, 6.2), dpi=110)
    axes = fig.subplots(2, 3)
    flat_axes = axes.flatten()
    image = None

    for axis, (shopper_type, profile) in zip(flat_axes, SHOPPER_PROFILES.items()):
        heatmap = heatmaps[shopper_type]
        image = axis.imshow(heatmap, origin="lower", cmap="YlOrRd", vmin=0, vmax=max_visits)
        if model.layout.entrance_positions:
            axis.scatter(
                [pos[0] for pos in model.layout.entrance_positions],
                [pos[1] for pos in model.layout.entrance_positions],
                c="white",
                s=18,
                edgecolors="#111827",
                linewidths=0.4,
            )
        if model.layout.checkout_positions:
            axis.scatter(
                [pos[0] for pos in model.layout.checkout_positions],
                [pos[1] for pos in model.layout.checkout_positions],
                c="#111827",
                s=18,
            )
        axis.set_title(profile.name, fontsize=9)
        axis.set_xticks([])
        axis.set_yticks([])

    for axis in flat_axes[len(SHOPPER_PROFILES):]:
        axis.axis("off")
    if image is not None:
        fig.colorbar(image, ax=flat_axes.tolist(), label="Tile visits", shrink=0.72)
    fig.suptitle("Tile heatmap by shopper type", fontsize=12)
    solara.FigureMatplotlib(
        fig,
        format="png",
        bbox_inches="tight",
        dependencies=[model.step_count, model.layout_name, model.num_shoppers],
    )


@solara.component
def ResponsiveModelController(
    model,
    renderer=None,
    *,
    model_parameters=None,
    play_interval=100,
    render_interval=1,
    use_threads=False,
):
    playing = solara.use_reactive(False)
    running = solara.use_reactive(True)
    error_message = solara.use_reactive(None)

    if model_parameters is None:
        model_parameters = {}
    model_parameters = solara.use_reactive(model_parameters)

    def safe_play_interval_seconds() -> float:
        return max(0.25, float(play_interval.value) / 1000)

    def safe_render_steps() -> int:
        return max(1, int(render_interval.value))

    def advance_model() -> None:
        for _ in range(safe_render_steps()):
            if not running.value:
                break
            model.value.step()
            running.value = model.value.running
            if not running.value:
                playing.value = False
                break

    async def play_loop():
        if not playing.value:
            return
        try:
            while playing.value and running.value:
                await asyncio.sleep(safe_play_interval_seconds())
                if not playing.value or not running.value:
                    break
                advance_model()
                force_update()
        except Exception as exc:
            playing.value = False
            error_message.value = f"error in play: {exc}"

    solara.lab.use_task(
        play_loop,
        dependencies=[playing.value, running.value],
        prefer_threaded=False,
        raise_error=False,
    )

    def do_step():
        if playing.value or not running.value:
            return
        try:
            advance_model()
            force_update()
        except Exception as exc:
            error_message.value = f"error in step: {exc}"

    def do_reset():
        try:
            error_message.value = None
            playing.value = False
            running.value = True
            kwargs = mesa_solara_viz._build_model_init_kwargs(
                model.value,
                model_parameters.value,
                add_scenario_when_empty=True,
                require_model_accepts_scenario=True,
            )
            model.value = type(model.value)(**kwargs)
            if renderer is not None:
                renderer.value = mesa_solara_viz.copy_renderer(renderer.value, model.value)
            force_update()
        except Exception as exc:
            error_message.value = f"error in reset: {exc}"

    def do_play_pause():
        if running.value:
            playing.value = not playing.value

    with solara.Row(justify="space-between"):
        solara.Button(label="Reset", color="primary", on_click=do_reset)
        solara.Button(
            label="Pause" if playing.value else "Play",
            color="primary",
            on_click=do_play_pause,
            disabled=not running.value,
        )
        solara.Button(
            label="Step",
            color="primary",
            on_click=do_step,
            disabled=playing.value or not running.value,
        )

    if error_message.value:
        solara.Error(label=error_message.value)


mesa_solara_viz.ModelController = ResponsiveModelController


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
    "shopping_list_size": {
        "type": "InputText",
        "value": "",
        "label": "Max shopping list items",
    },
    "patience_threshold": {
        "type": "SliderFloat",
        "value": 0.40,
        "label": "Patience threshold",
        "min": 0.20,
        "max": 0.50,
        "step": 0.05,
    },
    "promotion_level": {
        "type": "SliderFloat",
        "value": 0.25,
        "label": "Promotion level (blank sale count)",
        "min": 0.0,
        "max": 0.8,
        "step": 0.05,
    },
    "sale_item_count": {
        "type": "InputText",
        "value": "",
        "label": "Exact sale item count",
    },
    "mission_driven_percent": {
        "type": "SliderFloat",
        "value": 28.0,
        "label": "Mission-driven %",
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
    },
    "bargain_hunter_percent": {
        "type": "SliderFloat",
        "value": 22.0,
        "label": "Bargain hunter %",
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
    },
    "impulse_buyer_percent": {
        "type": "SliderFloat",
        "value": 18.0,
        "label": "Impulse buyer %",
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
    },
    "loyal_shopper_percent": {
        "type": "SliderFloat",
        "value": 20.0,
        "label": "Loyal shopper %",
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
    },
    "browser_percent": {
        "type": "SliderFloat",
        "value": 12.0,
        "label": "Browser %",
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
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

page = mesa_solara_viz.SolaraViz(
    model,
    components=[
        (InteractiveStoreView, 0),
        (ShoppingListCompletionFigure, 1),
        (PlannedVsUnplannedFigure, 1),
        (CongestionPatienceFigure, 1),
        (ShopperTypeOutcomeFigure, 2),
        (ShopperTypeUnplannedFigure, 2),
        (ShopperTypeCompletionTimeFigure, 2),
        (StoreTrafficHeatmapFigure, 3),
        (ShopperTypeHeatmapFigure, 3),
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
                "unplanned_purchases": "tab:orange",
            },
            page=2,
        ),
        make_plot_component(
            {
                "items_not_found": "tab:gray",
                "tile_capacity_blocks": "tab:red",
                "avg_patience_drop": "tab:green",
            },
            page=3,
        ),
    ],
    model_params=model_params,
    name="Store Layout ABM Live Simulation",
    play_interval=500,
    render_interval=1,
)
page
