from __future__ import annotations

import argparse
from pathlib import Path

from analysis import (
    aggregate_results,
    parse_int_list,
    parse_layouts,
    run_experiment,
    run_single_simulation,
)
from store_layout import LAYOUT_NAMES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mesa ABM for grocery store layout, shopper movement, and profit."
    )
    parser.add_argument("--layout", choices=LAYOUT_NAMES, default="grid")
    parser.add_argument(
        "--shoppers",
        type=int,
        default=400,
        help="Total daily shopper population for the simulated store day.",
    )
    parser.add_argument(
        "--cashiers",
        type=int,
        default=3,
        help="Number of cashier lanes at the entrance/checkout area.",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=720,
        help="Simulation steps across the store day. Default: 720, roughly one step per minute for 9 AM-9 PM.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of simulated days for a single simulation.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--promotion-level", type=float, default=0.25)
    parser.add_argument(
        "--opening-hour",
        type=float,
        default=9.0,
        help="Store opening hour on a 24-hour clock. Default: 9.0.",
    )
    parser.add_argument(
        "--closing-hour",
        type=float,
        default=21.0,
        help="Store closing hour on a 24-hour clock. Default: 21.0.",
    )
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--no-plots", action="store_true", help="Skip PNG chart generation.")

    parser.add_argument(
        "--experiment",
        action="store_true",
        help="Run all selected layouts across shopper-density scenarios.",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=None,
        help="Number of repetitions per scenario when using --experiment. If omitted, --days can be used as the run count.",
    )
    parser.add_argument(
        "--densities",
        default="20,50,80",
        help="Comma-separated shopper counts for --experiment.",
    )
    parser.add_argument(
        "--layouts",
        default=",".join(LAYOUT_NAMES),
        help="Comma-separated layouts for --experiment: grid,loop,free_flow.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.days <= 0:
        parser.error("--days must be positive.")
    if args.cashiers <= 0:
        parser.error("--cashiers must be positive.")
    if args.runs is not None and args.runs <= 0:
        parser.error("--runs must be positive.")
    if args.closing_hour <= args.opening_hour:
        parser.error("--closing-hour must be after --opening-hour.")

    results_dir = Path(args.results_dir)
    make_plots = not args.no_plots

    if args.experiment:
        experiment_runs = args.runs if args.runs is not None else (args.days if args.days != 1 else 5)
        results = run_experiment(
            layouts=parse_layouts(args.layouts),
            shopper_counts=parse_int_list(args.densities),
            runs=experiment_runs,
            steps=args.steps,
            promotion_level=args.promotion_level,
            num_cashiers=args.cashiers,
            output_dir=results_dir,
            make_plots=make_plots,
            seed=args.seed,
            opening_hour=args.opening_hour,
            closing_hour=args.closing_hour,
        )
        aggregate = aggregate_results(results)
        print("\nExperiment complete. Average metrics by layout and shopper count:\n")
        print(aggregate.to_string(index=False))
        print(f"\nSaved detailed results to: {results_dir.resolve()}")
        return

    summary = run_single_simulation(
        layout=args.layout,
        shoppers=args.shoppers,
        steps=args.steps,
        seed=args.seed,
        promotion_level=args.promotion_level,
        num_cashiers=args.cashiers,
        output_dir=results_dir,
        make_plots=make_plots,
        days=args.days,
        opening_hour=args.opening_hour,
        closing_hour=args.closing_hour,
    )
    printable = {key: value for key, value in summary.items() if not key.endswith("_file")}
    if args.days == 1:
        print("\nSingle simulation complete:\n")
    else:
        print(f"\nMulti-day simulation complete ({args.days} days). Daily averages:\n")
    for key, value in printable.items():
        print(f"{key}: {value}")
    print(f"\nSaved results to: {results_dir.resolve()}")


if __name__ == "__main__":
    main()
