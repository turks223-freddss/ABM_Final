# Store Layout ABM

Mesa-based agent simulation for a grocery-store layout project. The model compares how layout design affects shopper movement, shopping-list completion, congestion, checkout behavior, abandonment, and planned versus unplanned purchasing.

## What Is Modeled

- Shopper profiles: mission-driven shoppers, bargain hunters, impulse buyers, loyal shoppers, and browsers.
- Store layouts: efficiency-focused grid, exposure-focused loop, and exploration-focused free-flow.
- Static products: shelf location, category, price, visibility, promotion status, sale discount, shopping-list appearance percentage, and whether the item is essential. The default catalogue is Philippine-informed, with staples such as rice, cooking oil, instant noodles, condiments, vegetables, pork/chicken/fish, pandesal or loaf bread, snacks, laundry items, and toiletries.
- Dynamic processes: time-of-day shopper traffic, active-shopper admission control, shopper lists that can naturally repeat, aisle movement, item search, product exposure, live patience levels, tile crowding, early checkout, trip abandonment, checkout waiting, planned purchases, and unplanned purchases.
- Live output metrics: completed and not completed shopping lists, planned versus unplanned purchases, completed and abandoned trips by shopper type, checkout queues, congestion, patience, abandonment reason, and layout score.

The model still keeps price, revenue, and profit fields internally for older CSV exports and analysis scripts, but the live dashboard focuses on non-financial behavioral outcomes.

## Environment Behavior

The store is a 24x24 Mesa `MultiGrid`. Coordinates use `(x, y)` positions with `(0, 0)` at the bottom-left. Shoppers can move only through passable aisle, entrance, queue, and cashier tiles. Shelf cells, wall cells, checkout separators, and the outer border block normal movement.

The environment supports three layout types:

- `grid`: a structured baseline with more shelf coordinates and clear aisle access.
- `loop`: a directed circulation layout with a reference loop path that encourages shoppers to circulate around the store.
- `free_flow`: a less rigid layout with separated islands, open spaces, and manually editable shelf blocks.

Shelf placement is controlled by the `SHELF_COORDINATES` dictionary in `store_layout.py`. Each shelf coordinate creates one product, so a layout with more shelf cells has more products. Product templates repeat with numbered names when a category has more shelf cells than unique templates. This is why the grid layout can hold more products, while the loop and free-flow layouts can be designed with fewer product positions.

Manual wall tiles can be added in `WALL_COORDINATES` in `store_layout.py`. This wall layer is applied only to the `loop` and `free_flow` layouts so the grid baseline stays unchanged. Wall cells block shopper movement, appear as `W` in the live dashboard, and override shelf coordinates if a wall and shelf are placed on the same tile.

Product categories are assigned by shelf coordinates. The default categories are produce, bakery, dairy, meat, pantry, beverages, snacks, frozen, household, personal care, and checkout. Checkout products are small impulse items such as gum, mints, chocolate, candy packs, and batteries.

The front service area contains entrances, cashier tiles, queue lanes, and checkout separators. Each cashier has three dedicated queue tiles marked `Q`. Checkout separator cells span from the cashier row down to the end of the queue line and are treated as checkout product/display cells, which separates cashier lanes while still creating checkout exposure.

Products have category, price, visibility, sale status, discount, essential status, and list probability. Promotions are assigned either by `promotion_level` or by an exact `sale_item_count`. Sale discounts use the model's default internal range. Products in hot zones and checkout shelves receive higher visibility.

The environment tracks tile crowding. Two shoppers can share a tile without penalty. Three or four shoppers on a tile create same-tile crowding costs. A tile will not accept a fifth shopper, so blocked shoppers wait, lose patience, and increment the tile-capacity block metric.

Movement uses layout pathing first, then a crowd-aware movement filter. Shoppers prefer empty neighboring tiles. They only step onto an occupied tile when no usable empty neighbor is available. Queue tiles and cashier tiles are reserved for shoppers who are heading to checkout.

## Time-Of-Day Traffic

By default, each simulation day represents a store open from 9:00 AM to 9:00 PM. The `--shoppers` value is the total daily shopper population, and each time window sets the target share of shoppers allowed to be active in the store. The default profile is based on the research note in `../research-docs/store_layout_research_background.tex`, which found the strongest Philippine support for a 2:00 PM-7:00 PM grocery peak window:

- 9:00 AM-11:00 AM: 10%
- 11:00 AM-2:00 PM: 20%
- 2:00 PM-5:00 PM: 35%
- 5:00 PM-7:00 PM: 25%
- 7:00 PM: remaining 10% final scheduled shopper arrivals

The default command-line and live-dashboard population is 400 shoppers so the compact grid stays responsive. A full-size supermarket benchmark is closer to 2,225 in-store transactions per day, derived from FMI's 2024 average weekly supermarket sales and in-store sales per transaction. You can enter any positive whole number in the live dashboard's daily shopper population field, or pass any positive value to `--shoppers` on the command line.

The live dashboard and timeseries CSV include store time, traffic period, target traffic share, active shoppers, and target active shoppers. If a peak ends while shoppers are still inside, those shoppers continue naturally and new admissions pause until active shoppers fall below the current target.

In the live dashboard, hover over shopper, product, cashier, and queue tiles for quick details. Click a shopper to track their basket, shopping list, patience, state, and movement stats. Click a product shelf to inspect item details, or click a cashier/queue lane to inspect queue length and randomized cashier checkout speed.

At 7:00 PM, no new shoppers are scheduled to arrive. At 8:30 PM, all active shoppers stop searching for remaining list items and start moving toward checkout. The simulation clock reaches closing at 9:00 PM, but the model keeps stepping until shoppers have cleared checkout or otherwise completed their trip.

## Agent Behavior

Each shopper is a `CustomerAgent` with a shopper type, arrival time, shopping list, basket, patience level, checkout patience level, path history, and state. Shopper states are `waiting`, `shopping`, `checkout`, `finished`, and `abandoned`.

The default shopper types are:

| Type | Patience | Impulse probability | Familiarity | Exploration | Discount awareness | Exposure radius |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Mission-Driven | 90 | 0.012 | 0.80 | 0.03 | 0.20 | 1 |
| Bargain Hunter | 125 | 0.035 | 0.65 | 0.12 | 0.85 | 1 |
| Impulse Buyer | 115 | 0.090 | 0.45 | 0.20 | 0.45 | 2 |
| Loyal Shopper | 105 | 0.020 | 0.92 | 0.04 | 0.35 | 1 |
| Browser | 155 | 0.055 | 0.30 | 0.34 | 0.25 | 2 |

Shopping lists are generated from listable, non-checkout products. Each product has a base list probability. Mission-driven and loyal shoppers are more likely to include essential products; bargain hunters are more likely to include promoted products; impulse buyers start with smaller lists. The minimum list size is always 1 for shoppers with planned lists. Default max list sizes are 8 items for mission-driven and loyal shoppers, 7 for bargain hunters, and 6 for impulse buyers. The dashboard and CLI can override this with a maximum shopping-list size.

Browser shoppers do not receive planned shopping lists. They browse through hot zones and open aisles, buy noticed items through the unplanned-purchase logic, and only head to checkout when patience or the store cutoff pushes them there.

At each step, an arrived shopper updates patience, checks crowding, interacts with visible items, chooses a target, and moves one tile if possible. Shoppers with planned shopping lists prioritize the nearest remaining list item with direct, low-exploration routing until the list is complete. Browser shoppers have no planned list and can target unseen products, hot zones, or open aisles.

A shopper buys a planned item when it is visible and appears on the remaining shopping list. A shopper can also make an unplanned purchase after noticing a visible item. Once an item has already been viewed, shoppers are less likely to focus on it again and are more likely to continue toward unseen items, but it can still be bought when it remains in line of sight. Unplanned purchasing is more likely for snacks, checkout items, bakery, frozen goods, promoted items, high-exposure items, and shoppers with higher impulse probability. Loop layouts slightly increase impulse probability, while grid layouts slightly reduce it.

Patience is tracked in approximate minutes. Normal walking and shopping do not consume baseline patience. Nearby traffic, congestion delay, same-tile crowding, blocked movement, and checkout-line waiting can still consume patience. If a shopper still has a basket when patience reaches zero from congestion, they try to go to checkout instead of immediately abandoning.

When a shopper's remaining patience drops below the configured threshold, they stop searching for remaining list items and begin moving toward the cashier lanes. Shoppers can still abandon while waiting farther back in a checkout line if checkout patience runs out. Once a shopper reaches the front queue tile or cashier tile, they stay and complete checkout.

Checkout starts when a shopper reaches their assigned cashier tile. Each cashier has a randomized service speed. Checkout wait is estimated from the cashier queue length and service time. Purchases are recorded only after checkout finishes; shoppers who abandon before payment keep their abandoned basket and remaining list as abandoned items.

The live dashboard represents shoppers as dots so multiple shoppers on the same tile can be seen. Hover still works for shoppers, product shelves, cashiers, and queue lanes, and clicking still opens the selected object details.

## Setup

From PowerShell:

```powershell
cd "C:\Documents\4th year\ABM FInal\store-layout-abm"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If you already installed Mesa in another Python environment, activate that environment instead and run the commands below from this folder.

## Bash Commands

From Git Bash on Windows:

```bash
cd "/c/Documents/4th year/ABM FInal/store-layout-abm"
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

If you are using WSL, macOS, or Linux instead of Git Bash on Windows, `cd` to this project folder and activate the virtual environment with:

```bash
source .venv/bin/activate
```

Start the live dashboard:

```bash
python -m solara run app.py --host 127.0.0.1 --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

Run one simulation from the command line:

```bash
python main.py --layout grid --shoppers 400 --steps 720 --seed 42
```

Simulate the other layouts:

```bash
python main.py --layout loop --shoppers 400 --steps 720 --seed 42
python main.py --layout free_flow --shoppers 400 --steps 720 --seed 42
```

Run the full layout comparison experiment:

```bash
python main.py --experiment --runs 5 --densities 20,50,80 --steps 250
```

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

- `shopping_lists_<layout>_<shoppers>_seed<seed>.csv`: one row per shopper with their shopping list, patience remaining, unlisted purchases, and any abandoned list items. Some shoppers may share the same list.
- `shopping_list_items_<layout>_<shoppers>_seed<seed>.csv`: each item's configured list percentage, observed list percentage, sale status, discount, units sold, unlisted units, revenue, profit, and lost sales from abandonment.
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

Use the sidebar to change the layout, shopper count, cashier count, max shopping-list size, patience threshold, shopper-type percentages, promotion level, exact sale item count, seed, and speed. Click `Reset` after changing model parameters, then click Play.

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
python main.py --layout grid --shopping-list-size 8 --patience-threshold 0.35 --shopper-mix mission_driven=30,bargain_hunter=20,impulse_buyer=20,loyal_shopper=20,browser=10 --sale-items 25
```

## File Guide

- `main.py`: command-line entry point.
- `model.py`: Mesa model, metrics, and data collection.
- `customer_agent.py`: shopper behavior and purchase decisions.
- `store_layout.py`: store geometry, products, and pathing.
- `analysis.py`: experiment runner, CSV export, and plots.
- `results/`: generated outputs.
