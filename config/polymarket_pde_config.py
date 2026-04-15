# config/polymarket_pde_config.py
"""
Configuration for Polymarket PDE Strategy (Dual-Phase Engine)
Reuses the same data client and execution client as the original strategy,
but swaps in the PDE strategy class.
"""
import os
import json
import urllib.request
import urllib.parse
from decimal import Decimal
from datetime import datetime, timezone

from nautilus_trader.config import (
    TradingNodeConfig,
    CacheConfig,
    DatabaseConfig,
    LoggingConfig,
)
from nautilus_trader.trading.config import ImportableStrategyConfig
from nautilus_trader.live.risk_engine import LiveRiskEngineConfig
from nautilus_trader.live.execution_engine import LiveExecEngineConfig
from nautilus_trader.adapters.polymarket.config import PolymarketDataClientConfig, PolymarketExecClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.common.config import InstrumentProviderConfig
from nautilus_trader.adapters.polymarket.providers import PolymarketInstrumentProviderConfig
from nautilus_trader.adapters.binance.config import BinanceDataClientConfig
from nautilus_trader.adapters.binance.common.enums import BinanceAccountType

from config.polymarket_config import resolve_current_token_id


def configure_pde_node(execution_mode: str = "sandbox") -> TradingNodeConfig:
    """
    Polymarket PDE Strategy node configuration.
    Same data/exec clients as original, but uses PDE strategy.
    """

    # ── Resolve current market token ID ──
    token_id = resolve_current_token_id("btc-updown-5m", interval_minutes=5)
    load_ids = [token_id] if token_id else []
    if not load_ids:
        print("⚠️  Warning: no token ID resolved")

    # ── A1. Binance data client (public market data, no API key needed) ──
    binance_data_cfg = BinanceDataClientConfig(
        api_key=os.getenv("BINANCE_API_KEY"),       # optional, improves rate limits
        api_secret=os.getenv("BINANCE_API_SECRET"),  # optional
        account_type=BinanceAccountType.SPOT,
        instrument_provider=InstrumentProviderConfig(
            load_all=False,
            load_ids=frozenset(["BTCUSDT.BINANCE"]),
        ),
    )
    print("📋 Binance data client configured (BTCUSDT spot)")

    # ── A2. Polymarket data client ──
    polymarket_data_cfg = PolymarketDataClientConfig(
        private_key=os.getenv("POLYMARKET_PK"),
        funder=os.getenv("POLYMARKET_FUNDER"),
        api_key=os.getenv("POLYMARKET_API_KEY"),
        api_secret=os.getenv("POLYMARKET_API_SECRET"),
        passphrase=os.getenv("POLYMARKET_API_PASSPHRASE"),
        drop_quotes_missing_side=False,
        instrument_config=PolymarketInstrumentProviderConfig(
            event_slug_builder="utils.slug_builder:build_btc_updown_slugs",
        ),
    )

    # ── B. Sandbox exec client ──
    sandbox_exec_cfg = SandboxExecutionClientConfig(
        venue="POLYMARKET",
        account_type="MARGIN",
        starting_balances=["1000000 USDC", "1000000 USDC.e"],
        book_type="L2_MBP",  # L2 depth for realistic sandbox fills
    )

    # ── C. Polymarket exec client (live) ──
    polymarket_exec_cfg = PolymarketExecClientConfig(
        private_key=os.getenv("POLYMARKET_PK"),
        funder=os.getenv("POLYMARKET_FUNDER"),
        api_key=os.getenv("POLYMARKET_API_KEY"),
        api_secret=os.getenv("POLYMARKET_API_SECRET"),
        passphrase=os.getenv("POLYMARKET_API_PASSPHRASE"),
    )

    # ── D. Select exec client by mode ──
    exec_clients = {}
    reconciliation = True

    if execution_mode == "sandbox":
        exec_clients["SANDBOX"] = sandbox_exec_cfg
        reconciliation = False
        print("📋 PDE Execution mode: SANDBOX (paper trading)")
    elif execution_mode == "live":
        exec_clients["POLYMARKET"] = polymarket_exec_cfg
        print("📋 PDE Execution mode: POLYMARKET (live trading)")
    elif execution_mode == "both":
        exec_clients["SANDBOX"] = sandbox_exec_cfg
        exec_clients["POLYMARKET"] = polymarket_exec_cfg
        reconciliation = False
        print("📋 PDE Execution mode: BOTH (sandbox + live)")
    else:
        raise ValueError(f"Invalid execution_mode: {execution_mode}")

    return TradingNodeConfig(
        trader_id=os.getenv("NAUTILUS_TRADER_ID", "POLYMARKET-001"),

        data_clients={
            "POLYMARKET": polymarket_data_cfg,
            "BINANCE": binance_data_cfg,
        },

        exec_clients=exec_clients,

        exec_engine=LiveExecEngineConfig(
            reconciliation=reconciliation,
        ),

        cache=CacheConfig(
            database=DatabaseConfig(
                type="redis",
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                timeout=2,
            ),
            encoding="msgpack",
            tick_capacity=20_000,
        ),

        logging=LoggingConfig(
            log_level=os.getenv("NAUTILUS_LOG_LEVEL", "DEBUG"),
            log_directory="./logs",
            log_colors=True,
        ),

        risk_engine=LiveRiskEngineConfig(
            bypass=False,
        ),

        strategies=[
            # Use new modular strategy
            ImportableStrategyConfig(
                strategy_path="strategies.pde.main:PolymarketPDEStrategy",
                config_path="strategies.pde.main:PolymarketPDEStrategyConfig",
                config={
                    "market_base_slug": "btc-updown-5m",
                    "market_interval_minutes": 5,
                    "trade_amount_usd": 100.0,
                    "auto_rollover": True,
                    "ev_threshold_A": 0.05,
                    "ev_entry_hysteresis": 0.01,
                    "ev_ema_alpha": 0.25,
                    "ev_deadband": 0.005,
                    "spread_tolerance": 0.03,
                    "signal_eval_interval_sec": 0.5,
                    "close_retry_interval_sec": 3.0,
                    "max_A_trades": 6,
                    "phase_b_momentum_threshold_usd": 30.0,  # $30 USD absolute price offset (bidirectional)
                    "take_profit_pct": 0.30,
                    "stop_loss_pct": 0.20,
                    "delta_tail_min": 5.0,
                    "tail_return": 0.10,
                    "ev_threshold_tail": 0.0,
                    "btc_jump_threshold_bps": 5.0,
                    "jump_staleness_sec": 10.0,
                    "max_slippage_pct": 0.10,
                    "volatility_window": 60,
                    "flip_stats_path": "config/flip_stats.json",
                    "flip_stats_lookback": 200,
                    "flip_stats_refresh_minutes": 60,
                    "debug_raw_data": True,
                    "order_id_tag": "002",
                },
            ),
        ],
    )
