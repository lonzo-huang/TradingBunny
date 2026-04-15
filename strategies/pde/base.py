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
    
    # Phase parameters
    phase_a_duration_sec: float = 240.0
    ev_threshold_A: float = 0.02
    ev_entry_hysteresis: float = 0.01
    ev_ema_alpha: float = 0.25
    ev_deadband: float = 0.005
    max_A_trades: int = 6
    tail_start_threshold: float = 0.1
    phase_b_momentum_threshold_usd: float = 30.0  # $30 USD absolute price offset (bidirectional)
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
    flip_stats_lookback: int = 200
    
    # PnL display
    pnl_display_interval_sec: float = 10.0
    
    # Debug
    debug_raw_data: bool = False
    debug_ws: bool = False


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
    
    def _calculate_round_start_ts(self) -> float:
        """Calculate aligned round start timestamp."""
        now = datetime.now(timezone.utc)
        interval = self.config.market_interval_minutes
        aligned_minute = (now.minute // interval) * interval
        market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
        return market_time.timestamp()
