"""Run a PDE backtest via Nautilus BacktestNode.

This script expects historical data to be present in a Nautilus catalog.
Use persisted market_data exports as the upstream source to build that catalog.
"""

from __future__ import annotations

import argparse
import json
import os

from nautilus_trader.backtest.config import (
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    DataConfig,
)
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import CacheConfig, LoggingConfig
from nautilus_trader.model import Money
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.trading.config import ImportableStrategyConfig


def build_run_config(
    catalog_path: str,
    instrument_id: str,
    start_time: str | None,
    end_time: str | None,
    params_file: str | None,
) -> BacktestRunConfig:
    data_cfg = DataConfig(
        catalog_path=catalog_path,
        instrument_id=instrument_id,
        start_time=start_time,
        end_time=end_time,
    )

    strategy_params = {
        "market_base_slug": "btc-updown-5m",
        "market_interval_minutes": 5,
        "per_trade_usd": 100.0,
        "phase_b_momentum_threshold_usd": 30.0,
        "persistence_enabled": False,
        "debug_raw_data": False,
        "debug_ws": False,
    }

    if params_file and os.path.exists(params_file):
        try:
            with open(params_file, "r", encoding="utf-8") as f:
                runtime_params = json.load(f)
            if isinstance(runtime_params, dict):
                strategy_params.update(runtime_params)
        except Exception as e:
            print(f"⚠️ Failed loading params file {params_file}: {e}")

    strategy_cfg = ImportableStrategyConfig(
        strategy_path="strategies.pde.main:PolymarketPDEStrategy",
        config_path="strategies.pde.main:PolymarketPDEStrategyConfig",
        config=strategy_params,
    )

    return BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="PDE-BACKTEST-001",
            run_analysis=True,
            cache=CacheConfig(tick_capacity=200_000),
            logging=LoggingConfig(log_level="INFO"),
        ),
        venues=[
            BacktestVenueConfig(
                name="POLYMARKET",
                oms_type=OmsType.NETTING,
                account_type=AccountType.MARGIN,
                base_currency="USDC",
                starting_balances=[Money(1_000_000, "USDC")],
                maker_fee=0.0,
                taker_fee=0.0,
            )
        ],
        data=[data_cfg],
        strategies=[strategy_cfg],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Nautilus backtest for PDE strategy")
    parser.add_argument("--catalog", required=True, help="Path to Nautilus data catalog")
    parser.add_argument("--instrument-id", required=True, help="InstrumentId, e.g. BTCUSDT.BINANCE")
    parser.add_argument("--start", default=None, help="Start time, e.g. 2026-04-18T19:00:00Z")
    parser.add_argument("--end", default=None, help="End time, e.g. 2026-04-18T21:00:00Z")
    parser.add_argument("--params-file", default=None, help="Optional JSON params file")
    args = parser.parse_args()

    run_config = build_run_config(
        catalog_path=args.catalog,
        instrument_id=args.instrument_id,
        start_time=args.start,
        end_time=args.end,
        params_file=args.params_file,
    )

    node = BacktestNode(configs=[run_config])
    results = node.run()

    print("\n✅ Backtest completed")
    for idx, result in enumerate(results, start=1):
        perf = getattr(result, "performance", None)
        if perf is None:
            print(f"Run#{idx}: no performance object")
            continue
        total_return = getattr(perf, "total_return", None)
        sharpe = getattr(perf, "sharpe_ratio", None)
        max_dd = getattr(perf, "max_drawdown", None)
        print(
            f"Run#{idx}: total_return={total_return} | "
            f"sharpe={sharpe} | max_drawdown={max_dd}"
        )


if __name__ == "__main__":
    main()
