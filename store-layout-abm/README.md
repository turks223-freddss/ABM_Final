# Store Layout ABM

Mesa-based agent simulation for the grocery-store layout project described in the PDF. The model compares how layout design affects shopper movement, shopping-list completion, congestion, impulse buying, revenue, and profit.

## What Is Modeled

- Shopper profiles: mission-driven shoppers, bargain hunters, impulse buyers, loyal shoppers, and browsers.
- Store layouts: efficiency-focused grid, exposure-focused loop, and exploration-focused free-flow.
- Static products: shelf location, category, price, margin, visibility, promotion status, shopping-list appearance percentage, and whether the item is essential.
- Dynamic processes: time-of-day shopper traffic, unique shopper lists, aisle movement, item search, product exposure, live patience levels, tile crowding, early abandonment, planned purchases, impulse purchases, unlisted purchases, congestion delays, and checkout waiting.
- Output metrics: completion time, shopping-list completion, abandonment rate and reason, satisfaction, checkout queues, basket value, category profit, shopper-type behavior, layout score, traffic heatmaps, planned purchases, impulse purchases, unlisted purchases, profit from unlisted purchases, abandoned-list items, lost sales from abandonment, revenue, and profit.

The default store catalogue is shelf-driven. Each shelf coordinate creates one product, so adding more shelf cells automatically increases the number of products instead of leaving capped or empty shelves. Product templates repeat with numbered names when a category has more shelf cells than unique product templates.

Shelves are modeled separately from walkable aisle tiles. The live map colors shelf blocks by product category, while shoppers move only through aisle/service tiles. The default model grid is now 24x24. Shelf placement is intentionally defined with editable coordinate arrays in `store_layout.py`, for example `produce: [(2, 13), (3, 13), ...]`.

Product placement also uses those category coordinate arrays. Edit the arrays in `store_layout.py` to move shelves around by hand, for example `produce: [(2, 13), (3, 13), ...]`; the product count will follow the number of shelf cells present.

Each cashier has three dedicated queue tiles directly before the register. These queue tiles are marked `Q` in the live map and are reserved for shoppers who have completed their shopping list and are moving to checkout. Cashiers are separated by checkout impulse shelves stocked with small items such as gum, mints, chocolate, magazines, and batteries.

## Time-Of-Day Traffic

By default, each simulation day represents a store open from 9:00 AM to 9:00 PM. The `--shoppers` value is the total daily shopper population, and each time window sets the target share of shoppers allowed to be active in the store:

- 9:00 AM-10:00 AM: 5%
- 10:00 AM-11:00 AM: 35%
- 11:00 AM-3:00 PM: 15%
- 3:00 PM-5:00 PM: 35%
- 5:00 PM-9:00 PM: 10%

The default command-line and live-dashboard population is 400 shoppers so the compact grid stays responsive. A full-size supermarket benchmark is closer to 2,225 in-store transactions per day, derived from FMI's 2024 average weekly supermarket sales and in-store sales per transaction. You can enter any positive whole number in the live dashboard's daily shopper population field, or pass any positive value to `--shoppers` on the command line.

The live dashboard and timeseries CSV include store time, traffic period, target traffic share, active shoppers, and target active shoppers. If a peak ends while shoppers are still inside, those shoppers continue naturally and new admissions pause until active shoppers fall below the current target.

In the live dashboard, hover over shopper, product, cashier, and queue tiles for quick details. Click a shopper to track their basket, shopping list, patience, state, and movement stats. Click a product shelf to inspect item details, or click a cashier/queue lane to inspect queue length and randomized cashier checkout speed.

Patience is tracked in approximate minutes. Purchases are counted as revenue only after checkout completes; if shoppers abandon before payment, the basket is counted as lost revenue/profit instead.

Two shoppers can share a tile without penalty. When three or four shoppers occupy the same tile, they lose patience from crowding. A tile will not accept a fifth shopper, so blocked shoppers wait, lose patience, and add to the tile-capacity metrics.

## Setup

From PowerShell:

```powershell
cd "C:\Documents\4th year\ABM FInal\store-layout-abm"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you already installed Mesa in another Python environment, activate that environment instead and run the commands below from this folder.

## Run One Simulation

```powershell
python main.py --layout grid --shoppers 400 --steps 720 --seed 42
```

To change the number of cashier lanes:

```powershell
python main.py --layout grid --shoppers 400 --cashiers 4 --steps 720 --seed 42
```

To change the opening hours, use 24-hour clock values:

```powershell
python main.py --layout grid --shoppers 400 --steps 720 --opening-hour 9 --closing-hour 21
```

To simulate multiple days with the same settings, set `--days`. Each day is a fresh simulation run with a new seed based on the starting seed:

```powershell
python main.py --layout grid --shoppers 400 --steps 720 --seed 42 --days 7
```

Other layout choices:

```powershell
python main.py --layout loop --shoppers 400 --steps 720 --seed 42
python main.py --layout free_flow --shoppers 400 --steps 720 --seed 42
```

Generated CSV and PNG files are saved in `results/`.

Each single simulation also writes:

- `shopping_lists_<layout>_<shoppers>_seed<seed>.csv`: one row per shopper with their unique shopping list, patience remaining, unlisted purchases, and any abandoned list items. Unlisted purchases are bought items that were not on that shopper's shopping list.
- `shopping_list_items_<layout>_<shoppers>_seed<seed>.csv`: each item's configured list percentage, observed list percentage, units sold, unlisted units, revenue, profit, and lost sales from abandonment.
- `category_sales_<layout>_<shoppers>_seed<seed>.csv`: revenue, profit, unlisted sales, and lost abandonment sales grouped by product category.
- `shopper_types_<layout>_<shoppers>_seed<seed>.csv`: completion, abandonment, basket, satisfaction, and lost-sales metrics grouped by shopper type.

Single and multi-day simulations also create richer PNG charts:

- `behavior_...png`: active shoppers, abandonment, checkout queue, patience, and congestion over time.
- `purchase_mix_...png`: planned, impulse, unlisted, abandoned-list counts, and profit impact.
- `category_performance_...png`: category revenue, profit, and lost profit.
- `shopper_type_performance_...png`: basket profit and abandonment rate by shopper profile.

Multi-day simulations write combined files with the number of days in the filename, plus a `daily_summary_...csv` showing one row per simulated day.

## Run The Live Visualization

This opens a browser dashboard with Reset, Play/Pause, and Step controls, similar to watching a NetLogo model run.

```powershell
python -m solara run app.py
```

Then open the local URL printed in the terminal, usually:

```text
http://localhost:8765
```

Use the sidebar to change the layout, shopper count, cashier count, promotion level, seed, and speed. Click `Reset` after changing model parameters, then click Play.

On Windows you can also run:

```powershell
.\run_visualization.bat
```

## Run The Full Experiment

```powershell
python main.py --experiment --runs 5 --densities 20,50,80 --steps 250
```

For experiments, `--runs` is the number of repeated days per layout and shopper-count scenario. You can also use `--days` as the run count when `--runs` is not provided:

```powershell
python main.py --experiment --days 7 --densities 20,50,80 --steps 250
```

This compares grid, loop, and free-flow layouts across low, medium, and high shopper counts. It saves:

- `results/experiment_results.csv`
- `results/experiment_summary_by_layout.csv`
- `results/experiment_category_sales.csv`
- `results/experiment_category_sales_by_layout.csv`
- `results/experiment_shopper_types.csv`
- `results/experiment_shopper_types_by_layout.csv`
- `results/layout_comparison.png`
- `results/layout_scorecard.png`
- `results/profit_vs_abandonment.png`
- `results/category_profit_by_layout.png`
- `results/shopper_type_abandonment.png`
- one traffic heatmap PNG per layout and density

## Useful Options

```powershell
python main.py --help
python main.py --experiment --layouts grid,loop --densities 30,60 --runs 10
python main.py --layout loop --promotion-level 0.40 --no-plots
```

## File Guide

- `main.py`: command-line entry point.
- `model.py`: Mesa model, metrics, and data collection.
- `customer_agent.py`: shopper behavior and purchase decisions.
- `store_layout.py`: store geometry, products, and pathing.
- `analysis.py`: experiment runner, CSV export, and plots.
- `results/`: generated outputs.
