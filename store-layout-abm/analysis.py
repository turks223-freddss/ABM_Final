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
    output_dir: str | Path = "results",
    make_plots: bool = True,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    model = StoreModel(
        layout_name=layout,
        num_shoppers=shoppers,
        max_steps=steps,
        promotion_level=promotion_level,
        seed=seed,
    )
    model.run_model()

    summary = model.summary()
    summary["seed"] = seed
    summary_df = pd.DataFrame([summary])
    summary_file = output_path / f"summary_{layout}_{shoppers}_seed{seed}.csv"
    summary_df.to_csv(summary_file, index=False)

    model_df = model.datacollector.get_model_vars_dataframe()
    model_file = output_path / f"timeseries_{layout}_{shoppers}_seed{seed}.csv"
    model_df.to_csv(model_file, index=False)

    if make_plots:
        plot_timeseries(model_df, output_path / f"timeseries_{layout}_{shoppers}_seed{seed}.png")
        plot_heatmap(model, output_path / f"heatmap_{layout}_{shoppers}_seed{seed}.png")

    summary["summary_file"] = str(summary_file)
    summary["timeseries_file"] = str(model_file)
    return summary


def run_experiment(
    layouts: Sequence[str] = LAYOUT_NAMES,
    shopper_counts: Sequence[int] = (20, 50, 80),
    runs: int = 5,
    steps: int = 250,
    promotion_level: float = 0.25,
    output_dir: str | Path = "results",
    make_plots: bool = True,
    seed: int | None = 42,
) -> pd.DataFrame:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    records: List[dict] = []
    for layout in layouts:
        for shoppers in shopper_counts:
            for run in range(runs):
                run_seed = None if seed is None else seed + run + shoppers * 100 + len(layout)
                model = StoreModel(
                    layout_name=layout,
                    num_shoppers=shoppers,
                    max_steps=steps,
                    promotion_level=promotion_level,
                    seed=run_seed,
                )
                model.run_model()
                record = model.summary()
                record["run"] = run + 1
                record["seed"] = run_seed
                records.append(record)

                if make_plots and run == 0:
                    plot_heatmap(model, output_path / f"heatmap_{layout}_{shoppers}.png")

    results = pd.DataFrame(records)
    raw_file = output_path / "experiment_results.csv"
    results.to_csv(raw_file, index=False)

    aggregate = aggregate_results(results)
    aggregate_file = output_path / "experiment_summary_by_layout.csv"
    aggregate.to_csv(aggregate_file, index=False)

    if make_plots:
        plot_layout_comparison(aggregate, output_path / "layout_comparison.png")

    return results


def aggregate_results(results: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = [
        "completion_rate",
        "avg_completion_time",
        "avg_planned_completion",
        "avg_satisfaction",
        "avg_impulse_per_customer",
        "revenue",
        "profit",
        "avg_revenue_per_customer",
        "avg_congestion_delay",
    ]
    return (
        results.groupby(["layout", "shoppers"], as_index=False)[numeric_columns]
        .mean()
        .round(3)
    )


def plot_timeseries(model_df: pd.DataFrame, path: Path) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.plot(model_df["step"], model_df["revenue"], label="Revenue", color="#2563eb")
    ax1.plot(model_df["step"], model_df["profit"], label="Profit", color="#16a34a")
    ax1.set_xlabel("Simulation step")
    ax1.set_ylabel("Dollars")

    ax2 = ax1.twinx()
    ax2.plot(
        model_df["step"],
        model_df["active_shoppers"],
        label="Active shoppers",
        color="#dc2626",
        linestyle="--",
    )
    ax2.set_ylabel("Active shoppers")

    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="best")
    ax1.set_title("Store performance over time")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_heatmap(model: StoreModel, path: Path) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    heatmap = model.traffic_heatmap()
    fig, ax = plt.subplots(figsize=(8, 5))
    image = ax.imshow(heatmap, origin="lower", cmap="YlOrRd")
    ax.scatter([model.layout.entrance[0]], [model.layout.entrance[1]], c="white", s=80, label="Entrance")
    ax.scatter([model.layout.checkout[0]], [model.layout.checkout[1]], c="black", s=80, label="Checkout")
    ax.set_title(f"Traffic heatmap: {model.layout_name}")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(loc="upper right")
    fig.colorbar(image, ax=ax, label="Visits")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_layout_comparison(aggregate: pd.DataFrame, path: Path) -> None:
    prepare_matplotlib(path.parent)
    import matplotlib.pyplot as plt

    metrics = ["avg_completion_time", "avg_impulse_per_customer", "profit"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    for axis, metric in zip(axes, metrics):
        for layout in aggregate["layout"].unique():
            subset = aggregate[aggregate["layout"] == layout]
            axis.plot(subset["shoppers"], subset[metric], marker="o", label=layout)
        axis.set_xlabel("Shopper count")
        axis.set_title(metric.replace("_", " ").title())
    axes[0].set_ylabel("Metric value")
    axes[-1].legend(loc="best")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


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
