# Store Layout ABM

Mesa-based agent simulation for the grocery-store layout project described in the PDF. The model compares how layout design affects shopper movement, shopping-list completion, congestion, impulse buying, revenue, and profit.

## What Is Modeled

- Shopper profiles: mission-driven shoppers, bargain hunters, impulse buyers, loyal shoppers, and browsers.
- Store layouts: efficiency-focused grid, exposure-focused loop, and exploration-focused free-flow.
- Static products: item location, category, price, margin, visibility, promotion status, and whether the item is essential.
- Dynamic processes: movement, item search, product exposure, planned purchases, impulse purchases, congestion delays, and checkout waiting.
- Output metrics: completion time, shopping-list completion, satisfaction, traffic heatmaps, planned and impulse purchases, revenue, and profit.

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
python main.py --layout grid --shoppers 40 --steps 250 --seed 42
```

Other layout choices:

```powershell
python main.py --layout loop --shoppers 40 --steps 250 --seed 42
python main.py --layout free_flow --shoppers 40 --steps 250 --seed 42
```

Generated CSV and PNG files are saved in `results/`.

## Run The Live Visualization

This opens a browser dashboard with Reset, Play/Pause, and Step controls, similar to watching a NetLogo model run.

```powershell
python -m solara run app.py
```

Then open the local URL printed in the terminal, usually:

```text
http://localhost:8765
```

Use the sidebar to change the layout, shopper count, promotion level, seed, and speed. Click `Reset` after changing model parameters, then click Play.

On Windows you can also run:

```powershell
.\run_visualization.bat
```

## Run The Full Experiment

```powershell
python main.py --experiment --runs 5 --densities 20,50,80 --steps 250
```

This compares grid, loop, and free-flow layouts across low, medium, and high shopper counts. It saves:

- `results/experiment_results.csv`
- `results/experiment_summary_by_layout.csv`
- `results/layout_comparison.png`
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
