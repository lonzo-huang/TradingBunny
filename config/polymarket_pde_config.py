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
                    # ===== 市场配置 =====
                    "market_base_slug": "btc-updown-5m",    # 市场基础标识，用于匹配Polymarket事件
                    "market_interval_minutes": 5,           # 每个交易区间的时长（分钟），如5分钟
                    "per_trade_usd": 100.0,                 # 单笔交易金额（USD），每次开仓的仓位大小
                    "auto_rollover": True,                  # 是否自动切换到下一个区间，True=自动 rollover

                    # ===== Phase A EV套利参数 =====
                    "ev_threshold_A": 0.05,                 # Phase A EV阈值，|EV|>0.05才触发交易
                    "ev_entry_hysteresis": 0.01,            # EV入场滞回区间，防止频繁进出
                    "phase_a_min_btc_delta": 0.0001,        # Phase A BTC最小动量（0.03%），近零时不开仓
                    "taker_fee_rate": 0.0072,               # Polymarket CLOB taker fee: 0.72% of notional
                    "phase_a_min_token_price": 0.30,        # Phase A token价格下限，低于此不开仓
                    "phase_a_max_token_price": 0.70,        # Phase A token价格上限，高于此不开仓
                    "ev_ema_alpha": 0.25,                   # EV平滑系数，越大对新数据越敏感
                    "ev_deadband": 0.005,                   # EV死区，小于此值的波动被忽略
                    "ev_alpha": 0.001,                      # p(t)内部概率更新系数，BTC微动*p(t)更新
                    "phase_a_start_sec": 0.0,               # Phase A开始时间（秒），区间开始后的第N秒
                    "phase_a_end_sec": 240.0,               # Phase A结束时间（秒），默认240秒=4分钟

                    # ===== Phase B 趋势跟踪参数 =====
                    "phase_b_start_sec": 230.0,             # Phase B开始时间（秒），独立于phase_a_end_sec
                    "phase_b_max_token_price": 0.97,        # Phase B不入场的token价格上限（近解算无流动性）
                    "phase_b_momentum_threshold_usd": 10.0, # Phase B动量阈值（USD），BTC偏移>$10才交易
                    "take_profit_pct": 0.30,                # 止盈百分比，盈利30%时自动平仓
                    "stop_loss_pct": 0.20,                  # 止损百分比，亏损20%时自动平仓

                    # ===== Phase B Hedge Guard =====
                    "phase_b_hedge_enabled": True,           # Enable Phase B reversal hedge
                    "phase_b_hedge_window_sec": 60.0,         # Only hedge in last T seconds of round
                    "phase_b_hedge_delta_threshold_usd": 5.0, # Trigger when |delta_usd| drops below this
                    "phase_b_hedge_size_pct": 0.02,           # Hedge size as fraction of Phase B notional

                    # ===== 风控与执行参数 =====
                    "max_A_trades": 6,                      # Phase A最大交易次数，防止过度交易
                    "spread_tolerance": 0.03,               # 价差容忍度（3%），超过此价差不交易
                    "max_slippage_pct": 0.10,               # 最大滑点（10%），超过此滑点拒绝成交
                    "signal_eval_interval_sec": 0.5,        # 信号评估间隔（秒），每0.5秒检查一次
                    "close_retry_interval_sec": 3.0,        # 平仓重试间隔（秒），平仓失败3秒后重试
                    "btc_jump_threshold_bps": 5.0,          # BTC跳跃检测阈值（基点），5bps=0.05%
                    "jump_staleness_sec": 10.0,             # 跳跃检测数据过期时间（秒）

                    # ===== 波动率与统计参数 =====
                    "volatility_window": 60,                # 波动率计算窗口（秒），60秒历史数据
                    "flip_stats_path": "config/flip_stats.json",  # 翻转统计文件路径
                    "flip_stats_lookback": 200,             # 翻转统计回溯次数，最近200次
                    "flip_stats_refresh_minutes": 60,       # 翻转统计刷新间隔（分钟）

                    # ===== 调试与持久化参数 =====
                    "debug_raw_data": True,                 # 是否启用原始数据调试日志
                    "order_id_tag": "002",                  # 订单ID标签，用于区分不同策略实例
                    "persistence_enabled": True,            # 是否启用数据库持久化
                    "persistence_db_path": "data/pde/pde_runs.sqlite3",  # SQLite数据库路径
                    "persistence_record_market_data": True, # 是否记录市场数据（tick/quotes）
                    "persistence_export_dir": "data/pde/exports",      # 数据导出目录

                    # ===== 热加载 =====
                    "hot_config_path": "config/pde_runtime_config.json",  # 运行时热加载配置文件
                    "hot_config_check_interval_sec": 5.0,                 # 检查文件变更的间隔（秒）
                },
            ),
        ],
    )
