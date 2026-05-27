from __future__ import annotations

import os
from pathlib import Path
from typing import List, Sequence

import pandas as pd

from model import StoreModel
from store_layout import LAYOUT_NAMES


def run_single_simulation(
    layout: str,
    shoppers: int,
    steps: int,
    seed: int | None,
    promotion_level: float,
    num_cashiers: int = 3,
    output_dir: str | Path = "results",
    make_plots: bool = True,
    days: int = 1,
    opening_hour: float = 9.0,
    closing_hour: float = 21.0,
) -> dict:
    if days <= 0:
        raise ValueError("days must be positive.")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if days > 1:
        return run_multi_day_simulation(
            layout=layout,
            shoppers=shoppers,
            steps=steps,
            seed=seed,
            promotion_level=promotion_level,
            num_cashiers=num_cashiers,
            output_dir=output_path,
            make_plots=make_plots,
            days=days,
            opening_hour=opening_hour,
            closing_hour=closing_hour,
        )

    model = StoreModel(
        layout_name=layout,
        num_shoppers=shoppers,
        num_cashiers=num_cashiers,
        max_steps=steps,
        promotion_level=promotion_level,
        opening_hour=opening_hour,
        closing_hour=closing_hour,
        seed=seed,
    )
    model.run_model()

    summary = model.summary()
    summary["days_simulated"] = days
    summary["seed"] = seed
    summary_df = pd.DataFrame([summary])
    file_stem = f"{layout}_{shoppers}_{num_cashiers}cashiers_seed{seed}"
    summary_file = output_path / f"summary_{file_stem}.csv"
    summary_df.to_csv(summary_file, index=False)

    model_df = model.datacollector.get_model_vars_dataframe()
    model_file = output_path / f"timeseries_{file_stem}.csv"
    model_df.to_csv(model_file, index=False)

    shopper_lists_df = pd.DataFrame(model.shopper_list_summary())
    shopper_lists_file = output_path / f"shopping_lists_{file_stem}.csv"
    shopper_lists_df.to_csv(shopper_lists_file, index=False)

    item_rates_df = pd.DataFrame(model.shopping_list_item_summary())
    item_rates_file = output_path / f"shopping_list_items_{file_stem}.csv"
    item_rates_df.to_csv(item_rates_file, index=False)

    category_df = pd.DataFrame(model.category_summary())
    category_file = output_path / f"category_sales_{file_stem}.csv"
    category_df.to_csv(category_file, index=False)

    shopper_type_df = pd.DataFrame(model.shopper_type_summary())
    shopper_type_file = output_path / f"shopper_types_{file_stem}.csv"
    shopper_type_df.to_csv(shopper_type_file, index=False)

    if make_plots:
        plot_timeseries(model_df, output_path / f"timeseries_{file_stem}.png")
        plot_heatmap(model, output_path / f"heatmap_{file_stem}.png")
        plot_behavior_timeseries(
            model_df,
            output_path / f"behavior_{file_stem}.png",
        )
        plot_purchase_mix(
            summary,
            output_path / f"purchase_mix_{file_stem}.png",
        )
        plot_category_performance(
            category_df,
            output_path / f"category_performance_{file_stem}.png",
        )
        plot_shopper_type_performance(
            shopper_type_df,
            output_path / f"shopper_type_performance_{file_stem}.png",
        )

    summary["summary_file"] = str(summary_file)
    summary["timeseries_file"] = str(model_file)
    summary["shopping_lists_file"] = str(shopper_lists_file)
    summary["shopping_list_items_file"] = str(item_rates_file)
    summary["category_sales_file"] = str(category_file)
    summary["shopper_types_file"] = str(shopper_type_file)
    return summary


def run_multi_day_simulation(
    layout: str,
    shoppers: int,
    steps: int,
    seed: int | None,
    promotion_level: float,
    num_cashiers: int,
    output_dir: str | Path,
    make_plots: bool,
    days: int,
    opening_hour: float = 9.0,
    closing_hour: float = 21.0,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    daily_records: List[dict] = []
    timeseries_frames: List[pd.DataFrame] = []
    shopper_list_frames: List[pd.DataFrame] = []
    item_rate_frames: List[pd.DataFrame] = []
    category_frames: List[pd.DataFrame] = []
    shopper_type_frames: List[pd.DataFrame] = []
    heatmaps = []
    reference_model: StoreModel | None = None

    for day in range(1, days + 1):
        day_seed = None if seed is None else seed + day - 1
        model = StoreModel(
            layout_name=layout,
            num_shoppers=shoppers,
            num_cashiers=num_cashiers,
            max_steps=steps,
            promotion_level=promotion_level,
            opening_hour=opening_hour,
            closing_hour=closing_hour,
            seed=day_seed,
        )
        model.run_model()
        reference_model = reference_model or model

        record = model.summary()
        record["day"] = day
        record["seed"] = day_seed
        daily_records.append(record)

        model_df = model.datacollector.get_model_vars_dataframe()
        model_df.insert(0, "day", day)
        model_df.insert(1, "seed", day_seed)
        timeseries_frames.append(model_df)

        shopper_lists_df = pd.DataFrame(model.shopper_list_summary())
        shopper_lists_df.insert(0, "day", day)
        shopper_lists_df.insert(1, "seed", day_seed)
        shopper_list_frames.append(shopper_lists_df)

        item_rates_df = pd.DataFrame(model.shopping_list_item_summary())
        item_rates_df.insert(0, "day", day)
        item_rates_df.insert(1, "seed", day_seed)
        item_rate_frames.append(item_rates_df)

        category_df = pd.DataFrame(model.category_summary())
        category_df.insert(0, "day", day)
        category_df.insert(1, "seed", day_seed)
        category_frames.append(category_df)

        shopper_type_df = pd.DataFrame(model.shopper_type_summary())
        shopper_type_df.insert(0, "day", day)
        shopper_type_df.insert(1, "seed", day_seed)
        shopper_type_frames.append(shopper_type_df)
        heatmaps.append(model.traffic_heatmap())

    file_stem = f"{layout}_{shoppers}_{days}days_{num_cashiers}cashiers_seed{seed}"
    daily_summary_df = pd.DataFrame(daily_records)
    daily_summary_file = output_path / f"daily_summary_{file_stem}.csv"
    daily_summary_df.to_csv(daily_summary_file, index=False)

    summary = summarize_daily_records(daily_summary_df)
    summary["layout"] = layout
    summary["shoppers"] = shoppers
    summary["days_simulated"] = days
    summary["seed"] = seed

    summary_df = pd.DataFrame([summary])
    summary_file = output_path / f"summary_{file_stem}.csv"
    summary_df.to_csv(summary_file, index=False)

    timeseries_df = pd.concat(timeseries_frames, ignore_index=True)
    timeseries_file = output_path / f"timeseries_{file_stem}.csv"
    timeseries_df.to_csv(timeseries_file, index=False)

    shopper_lists_df = pd.concat(shopper_list_frames, ignore_index=True)
    shopper_lists_file = output_path / f"shopping_lists_{file_stem}.csv"
    shopper_lists_df.to_csv(shopper_lists_file, index=False)

    item_rates_df = pd.concat(item_rate_frames, ignore_index=True)
    item_rates_file = output_path / f"shopping_list_items_{file_stem}.csv"
    item_rates_df.to_csv(item_rates_file, index=False)

    category_df = pd.concat(category_frames, ignore_index=True)
    category_file = output_path / f"category_sales_{file_stem}.csv"
    category_df.to_csv(category_file, index=False)

    shopper_type_df = pd.concat(shopper_type_frames, ignore_index=True)
    shopper_type_file = output_path / f"shopper_types_{file_stem}.csv"
    shopper_type_df.to_csv(shopper_type_file, index=False)

    if make_plots and reference_model is not None:
        plot_timeseries(timeseries_df, output_path / f"timeseries_{file_stem}.png")
        average_heatmap = sum(heatmaps) / len(heatmaps)
        plot_heatmap_data(
            average_heatmap,
            output_path / f"heatmap_{file_stem}.png",
            title=f"Average traffic heatmap: {layout} over {days} days",
            entrance=reference_model.layout.entrance_positions,
            checkout=reference_model.layout.checkout_positions,
        )
        plot_behavior_timeseries(timeseries_df, output_path / f"behavior_{file_stem}.png")
        plot_purchase_mix(summary, output_path / f"purchase_mix_{file_stem}.png")
        plot_category_performance(
            category_df,
            output_path / f"category_performance_{file_stem}.png",
        )
        plot_shopper_type_performance(
            shopper_type_df,
            output_path / f"shopper_type_performance_{file_stem}.png",
        )

    summary["summary_file"] = str(summary_file)
    summary["daily_summary_file"] = str(daily_summary_file)
    summary["timeseries_file"] = str(timeseries_file)
    summary["shopping_lists_file"] = str(shopper_lists_file)
    summary["shopping_list_items_file"] = str(item_rates_file)
    summary["category_sales_file"] = str(category_file)
    summary["shopper_types_file"] = str(shopper_type_file)
    return summary


def summarize_daily_records(daily_summary_df: pd.DataFrame) -> dict:
    excluded_columns = {"day", "seed"}
    numeric_columns = [
        column
        for column in daily_summary_df.select_dtypes(include="number").columns
        if column not in excluded_columns
    ]
    summary = {
        column: round(float(daily_summary_df[column].mean()), 3)
        for column in numeric_columns
    }

    total_columns = [
        "planned_purchases",
        "impulse_purchases",
        "unlisted_purchases",
        "abandoned_shoppers",
        "abandoned_list_items",
        "abandoned_due_to_time",
        "abandoned_due_to_traffic",
        "abandoned_due_to_congestion",
        "abandoned_due_to_checkout",
        "lost_revenue_from_abandonment",
        "lost_profit_from_abandonment",
        "revenue",
        "profit",
        "revenue_from_planned",
        "revenue_from_impulse",
        "revenue_from_unlisted",
        "profit_from_unlisted",
    ]
    for column in total_columns:
        if column in daily_summary_df:
            summary[f"total_{column}"] = round(float(daily_summary_df[column].sum()), 3)
    return summary


def run_experiment(
    layouts: Sequence[str] = LAYOUT_NAMES,
    shopper_counts: Sequence[int] = (20, 50, 80),
    runs: int = 5,
    steps: int = 250,
    promotion_level: float = 0.25,
    num_cashiers: int = 3,
    output_dir: str | Path = "results",
    make_plots: bool = True,
    seed: int | None = 42,
    opening_hour: float = 9.0,
    closing_hour: float = 21.0,
) -> pd.DataFrame:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    records: List[dict] = []
    category_frames: List[pd.DataFrame] = []
    shopper_type_frames: List[pd.DataFrame] = []
    for layout in layouts:
        for shoppers in shopper_counts:
            for run in range(runs):
                run_seed = None if seed is None else seed + run + shoppers * 100 + len(layout)
                model = StoreModel(
                    layout_name=layout,
                    num_shoppers=shoppers,
                    num_cashiers=num_cashiers,
                    max_steps=steps,
                    promotion_level=promotion_level,
                    opening_hour=opening_hour,
                    closing_hour=closing_hour,
                    seed=run_seed,
                )
                model.run_model()
                record = model.summary()
                record["run"] = run + 1
                record["seed"] = run_seed
                records.append(record)

                category_df = pd.DataFrame(model.category_summary())
                category_df.insert(0, "layout", layout)
                category_df.insert(1, "shoppers", shoppers)
                category_df.insert(2, "run", run + 1)
                category_df.insert(3, "seed", run_seed)
                category_frames.append(category_df)

                shopper_type_df = pd.DataFrame(model.shopper_type_summary())
                shopper_type_df.insert(0, "layout", layout)
                shopper_type_df.insert(1, "shoppers", shoppers)
                shopper_type_df.insert(2, "run", run + 1)
                shopper_type_df.insert(3, "seed", run_seed)
                shopper_type_frames.append(shopper_type_df)

                if make_plots and run == 0:
                    plot_heatmap(model, output_path / f"heatmap_{layout}_{shoppers}.png")

    results = pd.DataFrame(records)
    raw_file = output_path / "experiment_results.csv"
    results.to_csv(raw_file, index=False)

    aggregate = aggregate_results(results)
    aggregate_file = output_path / "experiment_summary_by_layout.csv"
    aggregate.to_csv(aggregate_file, index=False)

    category_results = pd.concat(category_frames, ignore_index=True)
    category_file = output_path / "experiment_category_sales.csv"
    category_results.to_csv(category_file, index=False)
    category_aggregate = aggregate_grouped_numeric(
        category_results,
        ["layout", "shoppers", "category"],
    )
    category_aggregate_file = output_path / "experiment_category_sales_by_layout.csv"
    category_aggregate.to_csv(category_aggregate_file, index=False)

    shopper_type_results = pd.concat(shopper_type_frames, ignore_index=True)
    shopper_type_file = output_path / "experiment_shopper_types.csv"
    shopper_type_results.to_csv(shopper_type_file, index=False)
    shopper_type_aggregate = aggregate_grouped_numeric(
        shopper_type_results,
        ["layout", "shoppers", "shopper_type", "profile_name"],
    )
    shopper_type_aggregate_file = output_path / "experiment_shopper_types_by_layout.csv"
    shopper_type_aggregate.to_csv(shopper_type_aggregate_file, index=False)

    if make_plots:
        plot_layout_comparison(aggregate, output_path / "layout_comparison.png")
        plot_profit_abandonment_scatter(
            aggregate,
            output_path / "profit_vs_abandonment.png",
        )
        plot_layout_scorecard(aggregate, output_path / "layout_scorecard.png")
        plot_experiment_category_profit(
            category_aggregate,
            output_path / "category_profit_by_layout.png",
        )
        plot_experiment_shopper_type_abandonment(
            shopper_type_aggregate,
            output_path / "shopper_type_abandonment.png",
        )

    return results


def aggregate_results(results: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "arrived_shoppers",
        "waiting_shoppers",
        "target_active_shoppers",
        "active_shopper_share",
        "completion_rate",
        "abandonment_rate",
        "abandoned_due_to_time",
        "abandoned_due_to_traffic",
        "abandoned_due_to_congestion",
        "abandoned_due_to_checkout",
        "avg_completion_time",
        "avg_completion_minutes",
        "avg_planned_completion",
        "avg_satisfaction",
        "avg_checkout_wait",
        "max_checkout_wait",
        "longest_checkout_queue",
        "avg_impulse_per_customer",
        "avg_unlisted_per_customer",
        "unlisted_purchases",
        "abandoned_shoppers",
        "abandoned_list_items",
        "lost_revenue_from_abandonment",
        "lost_profit_from_abandonment",
        "avg_basket_value",
        "avg_basket_profit",
        "avg_items_per_shopper",
        "revenue",
        "profit",
        "profit_from_unlisted",
        "avg_revenue_per_customer",
        "avg_profit_per_customer",
        "avg_congestion_delay",
        "avg_patience_remaining",
        "avg_patience_lost_to_congestion",
        "layout_score",
    ]
    numeric_columns = [column for column in numeric_columns if column in results.columns]
    return (
        results.groupby(["layout", "shoppers"], as_index=False)[numeric_columns]
        .mean()
        .round(3)
    )


def aggregate_grouped_numeric(df: pd.DataFrame, group_columns: Sequence[str]) -> pd.DataFrame:
    excluded_columns = set(group_columns) | {"run", "seed"}
    numeric_columns = [
        column
        for column in df.select_dtypes(include="number").columns
        if column not in excluded_columns
    ]
    return df.groupby(list(group_columns), as_index=False)[numeric_columns].mean().round(3)


def plot_timeseries(model_df: pd.DataFrame, path: Path) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    if "day" in model_df.columns:
        shopper_columns = ["revenue", "profit", "active_shoppers"]
        if "abandoned_shoppers" in model_df.columns:
            shopper_columns.append("abandoned_shoppers")
        plot_df = model_df.groupby("step", as_index=False)[
            shopper_columns
        ].mean()
        title = "Average store performance over simulated days"
    else:
        plot_df = model_df
        title = "Store performance over time"

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(plot_df["step"], plot_df["revenue"], label="Revenue", color="#2563eb")
    ax1.plot(plot_df["step"], plot_df["profit"], label="Profit", color="#16a34a")
    ax1.set_xlabel("Simulation step")
    ax1.set_ylabel("Dollars")

    ax2 = ax1.twinx()
    ax2.plot(
        plot_df["step"],
        plot_df["active_shoppers"],
        label="Active shoppers",
        color="#dc2626",
        linestyle="--",
    )
    if "abandoned_shoppers" in plot_df.columns:
        ax2.plot(
            plot_df["step"],
            plot_df["abandoned_shoppers"],
            label="Abandoned shoppers",
            color="#7c2d12",
            linestyle=":",
        )
    ax2.set_ylabel("Shoppers")

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="best")
    ax1.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_behavior_timeseries(model_df: pd.DataFrame, path: Path) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    columns = [
        "active_shoppers",
        "target_active_shoppers",
        "abandoned_shoppers",
        "checkout_queue",
        "avg_patience_remaining",
        "avg_congestion_delay",
    ]
    available_columns = [column for column in columns if column in model_df.columns]
    if "day" in model_df.columns:
        plot_df = model_df.groupby("step", as_index=False)[available_columns].mean()
        title = "Average shopper behavior over simulated days"
    else:
        plot_df = model_df
        title = "Shopper behavior over time"

    fig, ax1 = plt.subplots(figsize=(9, 5))
    if "active_shoppers" in plot_df:
        ax1.plot(plot_df["step"], plot_df["active_shoppers"], label="Active", color="#2563eb")
    if "target_active_shoppers" in plot_df:
        ax1.plot(
            plot_df["step"],
            plot_df["target_active_shoppers"],
            label="Target active",
            color="#ec4899",
            linestyle="--",
        )
    if "abandoned_shoppers" in plot_df:
        ax1.plot(plot_df["step"], plot_df["abandoned_shoppers"], label="Abandoned", color="#dc2626")
    if "checkout_queue" in plot_df:
        ax1.plot(plot_df["step"], plot_df["checkout_queue"], label="Checkout queue", color="#7c3aed")
    ax1.set_xlabel("Simulation step")
    ax1.set_ylabel("Shoppers")

    ax2 = ax1.twinx()
    if "avg_patience_remaining" in plot_df:
        ax2.plot(
            plot_df["step"],
            plot_df["avg_patience_remaining"],
            label="Avg. patience",
            color="#16a34a",
            linestyle="--",
        )
    if "avg_congestion_delay" in plot_df:
        ax2.plot(
            plot_df["step"],
            plot_df["avg_congestion_delay"],
            label="Avg. congestion delay",
            color="#f97316",
            linestyle=":",
        )
    ax2.set_ylabel("Steps")

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="best")
    ax1.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_purchase_mix(summary: dict, path: Path) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    count_metrics = {
        "Planned": summary.get("planned_purchases", 0),
        "Impulse": summary.get("impulse_purchases", 0),
        "Unlisted": summary.get("unlisted_purchases", 0),
        "Abandoned list": summary.get("abandoned_list_items", 0),
    }
    profit_metrics = {
        "Total profit": summary.get("profit", 0),
        "Unlisted profit": summary.get("profit_from_unlisted", 0),
        "Lost profit": summary.get("lost_profit_from_abandonment", 0),
    }

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].bar(count_metrics.keys(), count_metrics.values(), color=["#2563eb", "#f97316", "#dc2626", "#64748b"])
    axes[0].set_title("Purchase and abandonment counts")
    axes[0].set_ylabel("Items")
    axes[0].tick_params(axis="x", rotation=20)

    axes[1].bar(profit_metrics.keys(), profit_metrics.values(), color=["#16a34a", "#0f766e", "#b91c1c"])
    axes[1].set_title("Profit impact")
    axes[1].set_ylabel("Dollars")
    axes[1].tick_params(axis="x", rotation=20)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def average_numeric_by(df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    numeric_columns = df.select_dtypes(include="number").columns.tolist()
    numeric_columns = [
        column
        for column in numeric_columns
        if column not in {"day", "run", "seed"}
    ]
    return df.groupby(group_column, as_index=False)[numeric_columns].mean()


def plot_category_performance(category_df: pd.DataFrame, path: Path) -> None:
    if category_df.empty:
        return

    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    plot_df = average_numeric_by(category_df, "category")
    plot_df = plot_df.sort_values("profit", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].barh(plot_df["category"], plot_df["revenue"], color="#2563eb", label="Revenue")
    axes[0].barh(plot_df["category"], plot_df["profit"], color="#16a34a", label="Profit")
    axes[0].set_title("Revenue and profit by category")
    axes[0].set_xlabel("Dollars")
    axes[0].legend(loc="best")

    axes[1].barh(
        plot_df["category"],
        plot_df["lost_profit_from_abandonment"],
        color="#dc2626",
    )
    axes[1].set_title("Lost profit from abandoned list items")
    axes[1].set_xlabel("Dollars")

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_shopper_type_performance(shopper_type_df: pd.DataFrame, path: Path) -> None:
    if shopper_type_df.empty:
        return

    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    plot_df = average_numeric_by(shopper_type_df, "shopper_type")
    plot_df = plot_df.sort_values("avg_basket_profit", ascending=False)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].bar(plot_df["shopper_type"], plot_df["avg_basket_profit"], color="#16a34a")
    axes[0].set_title("Avg. basket profit by shopper type")
    axes[0].set_ylabel("Dollars")
    axes[0].tick_params(axis="x", rotation=25)

    axes[1].bar(plot_df["shopper_type"], plot_df["abandonment_rate"], color="#dc2626")
    axes[1].set_title("Abandonment rate by shopper type")
    axes[1].set_ylabel("Rate")
    axes[1].tick_params(axis="x", rotation=25)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_heatmap(model: StoreModel, path: Path) -> None:
    plot_heatmap_data(
        model.traffic_heatmap(),
        path,
        title=f"Traffic heatmap: {model.layout_name}",
        entrance=model.layout.entrance_positions,
        checkout=model.layout.checkout_positions,
    )


def plot_heatmap_data(heatmap, path: Path, title: str, entrance, checkout) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.imshow(heatmap, origin="lower", cmap="YlOrRd")
    entrance_positions = _as_position_list(entrance)
    checkout_positions = _as_position_list(checkout)
    if entrance_positions:
        ax.scatter(
            [pos[0] for pos in entrance_positions],
            [pos[1] for pos in entrance_positions],
            c="white",
            s=80,
            label="Entrance",
        )
    if checkout_positions:
        ax.scatter(
            [pos[0] for pos in checkout_positions],
            [pos[1] for pos in checkout_positions],
            c="black",
            s=80,
            label="Checkout",
        )
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(loc="upper right")
    fig.colorbar(image, ax=ax, label="Visits")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _as_position_list(value) -> list[tuple[int, int]]:
    if not value:
        return []
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], int):
        return [value]
    return list(value)


def plot_layout_comparison(aggregate: pd.DataFrame, path: Path) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    metrics = [
        "profit",
        "completion_rate",
        "abandonment_rate",
        "lost_profit_from_abandonment",
        "avg_checkout_wait",
        "layout_score",
    ]
    metrics = [metric for metric in metrics if metric in aggregate.columns]
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()

    for axis, metric in zip(axes, metrics):
        for layout in aggregate["layout"].unique():
            subset = aggregate[aggregate["layout"] == layout]
            axis.plot(subset["shoppers"], subset[metric], marker="o", label=layout)
        axis.set_xlabel("Shopper count")
        axis.set_title(metric.replace("_", " ").title())
        axis.set_ylabel("Metric value")

    for axis in axes[len(metrics):]:
        axis.axis("off")

    axes[0].legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_profit_abandonment_scatter(aggregate: pd.DataFrame, path: Path) -> None:
    if not {"abandonment_rate", "profit"}.issubset(aggregate.columns):
        return

    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    for layout in aggregate["layout"].unique():
        subset = aggregate[aggregate["layout"] == layout]
        ax.scatter(
            subset["abandonment_rate"],
            subset["profit"],
            s=65,
            label=layout,
        )
        for _, row in subset.iterrows():
            ax.annotate(str(int(row["shoppers"])), (row["abandonment_rate"], row["profit"]), fontsize=8)
    ax.set_xlabel("Abandonment rate")
    ax.set_ylabel("Profit")
    ax.set_title("Profit vs. abandonment by layout and density")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_layout_scorecard(aggregate: pd.DataFrame, path: Path) -> None:
    if "layout_score" not in aggregate.columns:
        return

    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9, 5))
    for layout in aggregate["layout"].unique():
        subset = aggregate[aggregate["layout"] == layout]
        ax.plot(subset["shoppers"], subset["layout_score"], marker="o", label=layout)
    ax.set_xlabel("Shopper count")
    ax.set_ylabel("Score")
    ax.set_title("Overall layout score")
    ax.set_ylim(0, 100)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_experiment_category_profit(category_aggregate: pd.DataFrame, path: Path) -> None:
    if category_aggregate.empty or "profit" not in category_aggregate.columns:
        return

    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    plot_df = (
        category_aggregate
        .groupby(["layout", "category"], as_index=False)["profit"]
        .mean()
    )
    pivot = plot_df.pivot(index="category", columns="layout", values="profit").fillna(0)
    ax = pivot.plot(kind="bar", figsize=(10, 5), rot=25)
    ax.set_title("Average category profit by layout")
    ax.set_xlabel("Category")
    ax.set_ylabel("Profit")
    ax.legend(title="Layout")
    ax.figure.tight_layout()
    ax.figure.savefig(path, dpi=150)
    plt.close(ax.figure)


def plot_experiment_shopper_type_abandonment(
    shopper_type_aggregate: pd.DataFrame,
    path: Path,
) -> None:
    if shopper_type_aggregate.empty or "abandonment_rate" not in shopper_type_aggregate.columns:
        return

    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    plot_df = (
        shopper_type_aggregate
        .groupby(["layout", "shopper_type"], as_index=False)["abandonment_rate"]
        .mean()
    )
    pivot = plot_df.pivot(index="shopper_type", columns="layout", values="abandonment_rate").fillna(0)
    ax = pivot.plot(kind="bar", figsize=(10, 5), rot=25)
    ax.set_title("Average abandonment rate by shopper type")
    ax.set_xlabel("Shopper type")
    ax.set_ylabel("Abandonment rate")
    ax.legend(title="Layout")
    ax.figure.tight_layout()
    ax.figure.savefig(path, dpi=150)
    plt.close(ax.figure)


def parse_int_list(value: str) -> List[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_layouts(value: str) -> List[str]:
    layouts = [part.strip() for part in value.split(",") if part.strip()]
    invalid = [layout for layout in layouts if layout not in LAYOUT_NAMES]
    if invalid:
        raise ValueError(f"Invalid layout(s): {invalid}. Choose from {LAYOUT_NAMES}.")
    return layouts


def prepare_matplotlib(output_dir: Path) -> None:
    config_dir = output_dir / ".matplotlib"
    config_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(config_dir.resolve()))
