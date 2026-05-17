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
    parser.add_argument("--shoppers", type=int, default=40)
    parser.add_argument("--steps", type=int, default=250)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--promotion-level", type=float, default=0.25)
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
        default=5,
        help="Number of repetitions per scenario when using --experiment.",
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
    args = build_parser().parse_args()
    results_dir = Path(args.results_dir)
    make_plots = not args.no_plots

    if args.experiment:
        results = run_experiment(
            layouts=parse_layouts(args.layouts),
            shopper_counts=parse_int_list(args.densities),
            runs=args.runs,
            steps=args.steps,
            promotion_level=args.promotion_level,
            output_dir=results_dir,
            make_plots=make_plots,
            seed=args.seed,
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
        output_dir=results_dir,
        make_plots=make_plots,
    )
    printable = {key: value for key, value in summary.items() if not key.endswith("_file")}
    print("\nSingle simulation complete:\n")
    for key, value in printable.items():
        print(f"{key}: {value}")
    print(f"\nSaved results to: {results_dir.resolve()}")


if __name__ == "__main__":
    main()
