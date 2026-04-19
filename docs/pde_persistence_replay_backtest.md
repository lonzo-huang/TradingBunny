# PDE Persistence, Replay, Backtest

This project now includes a full persistence pipeline for PDE strategy runs.

## 1) Persist live/sandbox run data

When running `live/run_polymarket_pde.py`, the strategy writes data to:

- `data/pde/pde_runs.sqlite3`

Captured datasets:

- `runs`
- `orders`
- `fills`
- `positions`
- `pnl`
- `market_data`
- `account_states`

Persistence is configured in `config/polymarket_pde_config.py` via:

- `persistence_enabled`
- `persistence_db_path`
- `persistence_record_market_data`
- `persistence_export_dir`

## 2) Export a run to CSV

Export latest run:

```powershell
python live/export_pde_run.py --db data/pde/pde_runs.sqlite3 --out data/pde/exports
```

Export a specific run:

```powershell
python live/export_pde_run.py --db data/pde/pde_runs.sqlite3 --run-id <RUN_ID> --out data/pde/exports
```

Outputs:

- Per-run folder: `data/pde/exports/<RUN_ID>/*.csv`
- Latest snapshot: `data/pde/exports/*.csv`

## 3) Replay market data

Replay from latest exported market data:

```powershell
python live/replay_pde_run.py --csv data/pde/exports/market_data.csv --speed 20
```

Useful flags:

- `--speed` replay speed multiplier
- `--max-events` limit replay event count

## 4) Backtest entry (Nautilus BacktestNode)

Run backtest using a Nautilus data catalog:

```powershell
python live/backtest_pde.py --catalog <CATALOG_PATH> --instrument-id BTCUSDT.BINANCE --start 2026-04-18T19:00:00Z --end 2026-04-18T21:00:00Z
```

Notes:

- This script is a production-ready entrypoint scaffold.
- It expects your historical data to already exist in a Nautilus catalog.
- Use exported `market_data.csv` as an upstream source to build/ingest catalog data.

## 5) Why this fixes "trade exists but no PnL visible"

- Position lifecycle events now write PnL snapshots (`pnl` table).
- Dashboard now receives `pnl_summary` pushes during position open/change/close.
- You can audit each close via `positions` + `pnl` + `fills` tables.
