"""PDE Strategy base class with configuration and core state."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from nautilus_trader.model.data import QuoteTick, TradeTick
from nautilus_trader.trading.strategy import Strategy, StrategyConfig
from nautilus_trader.model.identifiers import Venue, InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.enums import BookType


class PolymarketPDEStrategyConfig(StrategyConfig):
    """Configuration for Polymarket PDE Strategy."""
    
    market_base_slug: str
    market_interval_minutes: int = 5
    
    # Risk & Execution
    max_position_usd: float = 500.0
    per_trade_usd: float = 100.0
    min_edge_threshold: float = 0.02
    max_slippage: float = 0.005
    spread_tolerance: float = 0.05
    
    # Phase parameters — A 和 B 时间窗口完全独立配置，互不共用
    phase_a_start_sec: float = 0.0      # Phase A 入场窗口开始（秒）
    phase_a_end_sec: float = 240.0      # Phase A 停止新建仓时间（秒），已持仓继续运行直到自身出场条件
    phase_b_start_sec: float = 240.0    # Phase B 入场窗口开始（秒），独立于 phase_a_end_sec
    ev_threshold_A: float = 0.02
    ev_entry_hysteresis: float = 0.01
    ev_ema_alpha: float = 0.25
    ev_deadband: float = 0.005
    ev_alpha: float = 0.001             # p(t) 概率更新系数: p(t) = p(t-Δt) + α·ΔBTC
    phase_a_min_btc_delta: float = 0.0003  # Phase A 最小 BTC 动量过滤（0.03%），低于此不开仓
    taker_fee_rate: float = 0.0072         # Polymarket CLOB taker fee: 0.72% of notional
    phase_a_min_token_price: float = 0.30  # Phase A token 价格下限，低于此不开仓（流动性不足）
    phase_a_max_token_price: float = 0.70  # Phase A token 价格上限，高于此不开仓（流动性不足）
    max_A_trades: int = 6
    tail_start_threshold: float = 0.1
    phase_b_momentum_threshold_usd: float = 30.0  # $30 USD absolute price offset (bidirectional)
    phase_b_max_token_price: float = 0.75        # Phase B 不入场的 token 价格上限

    # Phase B entry guards (pluggable)
    phase_b_ev_filter_enabled: bool = True       # Guard: require minimum EV to enter Phase B
    phase_b_min_ev: float = -0.05                # Minimum EV floor for Phase B entry
    phase_b_hedge_max_price: float = 1.0         # Phase B hedge only if token price below this
    phase_b_early_exit_enabled: bool = True      # Guard: exit Phase B before reserve window on SL
    phase_b_early_exit_reserve_sec: float = 5.0  # Don't early-exit in last N seconds (hold for resolution)
    phase_b_stop_loss_pct: float = 0.20          # Phase B percentage stop-loss threshold
    phase_b_abs_stop_loss_enabled: bool = True   # Guard: absolute price floor stop-loss
    phase_b_abs_stop_loss_price: float = 0.50    # Exit Phase B if token price drops below this

    take_profit_pct: float = 0.30
    stop_loss_pct: float = 0.20
    entry_retry_cooldown_sec: float = 1.0
    signal_eval_interval_sec: float = 0.5
    close_retry_interval_sec: float = 3.0
    
    # BTC monitoring
    btc_jump_threshold_bps: float = 50.0
    btc_price_source: str = "trade"  # "trade" or "mid"
    
    # Data refresh
    proactive_refresh_interval_min: float = 10.0
    flip_stats_refresh_minutes: int = 30
    flip_stats_lookback_windows: int = 96  # 96×5min=8h lookback, 0=disabled
    
    # PnL display
    pnl_display_interval_sec: float = 10.0
    
    # Phase B Hedge Guard
    phase_b_hedge_enabled: bool = False               # Enable Phase B reversal hedge
    phase_b_hedge_window_sec: float = 60.0            # Trigger only in last T seconds of round
    phase_b_hedge_delta_threshold_usd: float = 10.0   # Hedge if |delta_usd| drops below this
    phase_b_hedge_size_pct: float = 0.01              # Hedge size as fraction of Phase B notional

    # Hot-reload
    hot_config_path: str = "config/pde_runtime_config.json"
    hot_config_check_interval_sec: float = 5.0

    # Debug
    debug_raw_data: bool = False
    debug_ws: bool = False

    # Persistence
    persistence_enabled: bool = True
    persistence_db_path: str = "data/pde/pde_runs.sqlite3"
    persistence_record_market_data: bool = True
    persistence_export_dir: str = "data/pde/exports"


class PDEStrategyBase(Strategy):
    """Base class for PDE Strategy with core state initialization."""
    
    def __init__(self, config: PolymarketPDEStrategyConfig) -> None:
        super().__init__(config)
        
        # Market state
        self.current_market_slug: str | None = None
        self.instrument: Instrument | None = None
        self.down_instrument: Instrument | None = None
        self.start_price: dict[str, float | None] = {'up': None, 'down': None}
        self.start_ts: float | None = None
        self.last_rollover_check: datetime | None = None
        
        # Position state
        self.positions: dict[str, Any] = {
            'up': {
                'open': False,
                'entry_price': 0.0,
                'size': 0.0,
                'side': None,
                'phase': None,
                'instrument_id': None,
                'close_pending': False,
                'close_requested_ts': 0.0,
                'close_label': None,
                'pending_open': False,
                'pending_open_ts': 0.0,
            },
            'down': {
                'open': False,
                'entry_price': 0.0,
                'size': 0.0,
                'side': None,
                'phase': None,
                'instrument_id': None,
                'close_pending': False,
                'close_requested_ts': 0.0,
                'close_label': None,
                'pending_open': False,
                'pending_open_ts': 0.0,
            },
        }
        self.ev_ema: dict[str, float | None] = {'up': None, 'down': None}
        self._phase_a_signal_state: dict[str, str] = {'up': 'neutral', 'down': 'neutral'}
        # Phase A: internal probability p(t), starts at 0.5
        self._p_t: dict[str, float] = {'up': 0.5, 'down': 0.5}
        self._btc_prev_price: float | None = None  # 用于计算 ΔBTC
        self._last_signal_eval_ts: dict[str, float] = {'up': 0.0, 'down': 0.0}
        self._last_entry_attempt_ts: dict[str, float] = {'up': 0.0, 'down': 0.0}
        self._last_entry_reject_reason: str = ""
        self.round_pnl: float = 0.0
        self.total_pnl: float = 0.0
        self.cumulative_fees: float = 0.0
        
        # Phase tracking
        self.A_trades: int = 0
        self.B_trades: int = 0
        self.tail_trade_done: bool = False
        self.phase_a_cumulative: Any | None = None
        self.phase_b_cumulative: Any | None = None
        self._phase_b_hedge_done: dict[str, bool] = {'up': False, 'down': False}
        
        # Price history
        self.price_history: dict[str, Any] = {'up': None, 'down': None}
        self.btc_price_history: Any | None = None
        
        # BTC state
        self.btc_instrument_id = InstrumentId.from_str("BTCUSDT.BINANCE")
        self.btc_price: float | None = None
        self.btc_start_price: float | None = None
        self.btc_anchor_price: float | None = None
        self.btc_jump_ts: float = 0.0
        self.btc_jump_direction: int = 0
        
        # Flip stats
        self.flip_probs: dict = {}
        self.flip_stats: dict = {}
        self._flip_stats_refresh_thread: Any | None = None
        self._next_flip_stats_refresh_ts: float = 0.0
        
        # Timing
        self.last_quote_tick_ts: float = 0.0
        self.btc_last_tick_wall_ts: float = 0.0
        self.poly_last_tick_wall_ts: float = 0.0
        self._last_ws_push_ts: float = 0.0
        self._resubscribe_attempts: int = 0
        self._rollover_in_progress: bool = False
        self._pending_rollover_slug: str | None = None
        self._last_rollover_block_log_ts: float = 0.0
        self._rollover_retry_count: int = 0
        self._prewarm_lead_seconds: float = 10.0
        self.next_market_slug: str | None = None
        self.next_instrument: Instrument | None = None
        self.next_down_instrument: Instrument | None = None
        self._next_refresh_pending: bool = False
        self._post_rollover_subscribe_pending: bool = False
        self._post_rollover_switch_ts: float = 0.0
        self._post_rollover_retry_count: int = 0
        self._last_post_rollover_retry_ts: float = 0.0
        self._post_rollover_retry_interval_sec: float = 6.0
        self._post_rollover_retry_max: int = 10
        self._resubscribe_attempts: int = 0
        self._provider_refresh_pending: bool = False
        self._next_provider_refresh_ts: float = 0.0
        
        # Metrics
        self.rounds_counter: Any | None = None
        self.btc_price_gauge: Any | None = None
        self.btc_momentum_gauge: Any | None = None
        self.btc_delta_p_gauge: Any | None = None
        self.latency_gap_gauge: Any | None = None
        self.position_gauge: Any | None = None
        self.phase_a_trades_gauge: Any | None = None
        self.phase_b_trades_gauge: Any | None = None
        self.pnl_gauge: Any | None = None
        self.total_pnl_gauge: Any | None = None
        
        # Live streaming
        self.live_server: Any | None = None

        # Hot-reload state
        self._hot_config_mtime: float = 0.0
        self._last_hot_config_check_ts: float = 0.0

        # Persistence
        self.persistence_store: Any | None = None
        self.persistence_run_id: str = ""

        # Order tracking: client_order_id_str -> {'type': 'entry'|'close', 'token_key': str, 'phase': str}
        self._order_map: dict[str, dict] = {}
    
    def _calculate_round_start_ts(self) -> float:
        """Calculate aligned round start timestamp."""
        now = datetime.now(timezone.utc)
        interval = self.config.market_interval_minutes
        aligned_minute = (now.minute // interval) * interval
        market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
        return market_time.timestamp()
