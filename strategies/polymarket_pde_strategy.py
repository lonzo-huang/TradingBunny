# strategies/polymarket_pde_strategy.py
"""
Polymarket PDE Strategy (Dual-Phase Engine)

Phase A (0-240s): EV-driven trading based on Brownian motion theory
Phase B (240-300s): Tail reversal probability strategy

Author: AI Assistant
Date: 2026-04-04
"""

from decimal import Decimal
from datetime import datetime, timezone, timedelta
from collections import deque
import json
import math
import os

import numpy as np
from scipy.stats import norm
from prometheus_client import Gauge, Counter, start_http_server

from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.data import QuoteTick, TradeTick
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.enums import BookType, OrderSide
from nautilus_trader.model.identifiers import Venue, InstrumentId


class PolymarketPDEStrategyConfig(StrategyConfig):
    """Configuration for Polymarket PDE Strategy"""
    market_base_slug: str  # e.g., "btc-updown-5m"
    market_interval_minutes: int = 5
    trade_amount_usd: float = 100.0  # USD amount per trade (qty = amount / price)
    auto_rollover: bool = True
    
    # Phase A parameters
    ev_threshold_A: float = 0.05
    max_A_trades: int = 2  # Max BUY entries per round in Phase A
    take_profit_pct: float = 0.30  # +30% take profit
    stop_loss_pct: float = 0.20  # -20% stop loss
    
    # Phase B parameters
    delta_tail_min: float = 150.0  # Minimum price offset for tail strategy
    tail_return: float = 0.10  # Legacy fallback (dynamic calc preferred)
    ev_threshold_tail: float = 0.0
    
    # Latency monitor parameters
    btc_jump_threshold_bps: float = 5.0  # BTC must move ≥5 bps to trigger speed advantage
    jump_staleness_sec: float = 10.0  # Jump must be within last 10s
    
    # Order book depth / slippage
    max_slippage_pct: float = 0.03  # 3% max slippage from best ask
    
    # Volatility estimation
    volatility_window: int = 60  # seconds
    
    # Flip stats config
    flip_stats_path: str = "config/flip_stats.json"


class PolymarketPDEStrategy(Strategy):
    """
    Polymarket Dual-Phase Engine Strategy
    
    Phase A (0-240s): Brownian motion EV arbitrage
    Phase B (240-300s): Tail reversal probability trading
    """

    def __init__(self, config: PolymarketPDEStrategyConfig) -> None:
        super().__init__(config)
        
        # Market state
        self.current_market_slug: str | None = None
        self.instrument: Instrument | None = None
        self.down_instrument: Instrument | None = None
        
        # Round state (tracked per token: 'up' and 'down')
        self.start_price: dict[str, float | None] = {'up': None, 'down': None}
        self.start_ts: int | None = None
        
        # Per-token position tracking (independent TP/SL)
        self.positions: dict[str, dict] = {
            'up': {'open': False, 'entry_price': 0.0},
            'down': {'open': False, 'entry_price': 0.0},
        }
        
        # Phase A state
        self.A_trades: int = 0
        
        # Phase B state
        self.tail_trade_done: bool = False
        
        # Price history for volatility estimation (per token)
        self.price_history: dict[str, deque] = {
            'up': deque(maxlen=config.volatility_window),
            'down': deque(maxlen=config.volatility_window),
        }
        self.last_rollover_check: datetime | None = None
        self.last_quote_tick_ts: float = 0.0  # wallclock time of last quote tick
        self._resubscribe_attempts: int = 0
        self._rollover_in_progress: bool = False  # True while waiting for instruments after rollover
        self._rollover_retry_count: int = 0
        self._next_provider_refresh_ts: float = 0.0  # wall-clock time for next proactive refresh
        self._provider_refresh_pending: bool = False  # prevent overlapping refresh requests
        
        # Latency monitoring state
        self.btc_last_tick_wall_ts: float = 0.0  # wall-clock of last Binance tick
        self.poly_last_tick_wall_ts: float = 0.0  # wall-clock of last Polymarket tick
        self.btc_anchor_price: float | None = None  # reference price for jump detection
        self.btc_jump_ts: float = 0.0  # wall-clock time of last significant BTC jump
        self.btc_jump_direction: int = 0  # +1 up, -1 down, 0 none
        
        # Binance BTC price state
        self.btc_instrument_id = InstrumentId.from_str("BTCUSDT.BINANCE")
        self.btc_price: float | None = None
        self.btc_start_price: float | None = None
        self.btc_price_history: deque = deque(maxlen=3000)  # ~30-60s of Binance ticks
        
        # Load flip stats
        self.flip_stats = self._load_flip_stats()
        
        # Prometheus metrics
        self._setup_prometheus_metrics()

    def _load_flip_stats(self) -> dict:
        """Load flip probability lookup table from JSON"""
        try:
            flip_stats_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                self.config.flip_stats_path
            )
            with open(flip_stats_path, 'r') as f:
                data = json.load(f)
                
            # Convert string keys to tuple keys
            flip_stats = {}
            for key, prob in data.get('data', {}).items():
                parts = key.split('_')
                if len(parts) == 4:
                    tau_low, tau_high, delta_low, delta_high = map(int, parts)
                    flip_stats[(tau_low, tau_high, delta_low, delta_high)] = prob
            
            self.log.info(f"✅ Loaded {len(flip_stats)} flip probability entries")
            return flip_stats
            
        except Exception as e:
            self.log.error(f"❌ Failed to load flip stats: {e}")
            return {}

    def _setup_prometheus_metrics(self) -> None:
        """Initialize Prometheus monitoring metrics"""
        
        # Market state metrics
        self.delta_p_gauge = Gauge(
            'pde_delta_p',
            'Price offset from start (ΔP)',
            ['token_type']
        )
        self.remaining_time_gauge = Gauge(
            'pde_remaining_time',
            'Remaining time in current round (seconds)'
        )
        
        # Phase A metrics
        self.p_up_gauge = Gauge(
            'pde_p_up',
            'Theoretical probability of Up (Brownian motion)',
            ['token_type']
        )
        self.ev_gauge = Gauge(
            'pde_ev',
            'Expected value for Phase A',
            ['token_type', 'side']  # side: yes/no
        )
        self.sigma_gauge = Gauge(
            'pde_sigma',
            'Estimated volatility (sigma)'
        )
        
        # Phase B metrics
        self.p_flip_gauge = Gauge(
            'pde_p_flip',
            'Flip probability from lookup table',
            ['token_type']
        )
        self.ev_tail_gauge = Gauge(
            'pde_ev_tail',
            'Expected value for Phase B tail strategy',
            ['token_type']
        )
        
        # Strategy state
        self.strategy_state_gauge = Gauge(
            'pde_strategy_state',
            'Current strategy phase (0=Idle, 1=Phase A, 2=Phase B)'
        )
        
        # Trading metrics
        self.trades_counter = Counter(
            'pde_trades_total',
            'Total trades executed',
            ['phase', 'token_type', 'side']
        )
        self.phase_a_trades_gauge = Gauge(
            'pde_phase_a_trades',
            'Number of trades in Phase A for current round'
        )
        
        # PnL metrics (reuse from existing strategy)
        self.unrealized_pnl_gauge = Gauge(
            'pde_unrealized_pnl',
            'Unrealized PnL',
            ['token_type']
        )
        self.realized_pnl_gauge = Gauge(
            'pde_realized_pnl',
            'Realized PnL per position',
            ['token_type']
        )
        
        # Position metrics
        self.position_size_gauge = Gauge(
            'pde_position_size',
            'Current position size',
            ['token_type']
        )
        self.position_entry_price_gauge = Gauge(
            'pde_position_entry_price',
            'Position entry price',
            ['token_type']
        )
        
        # TP/SL metrics
        self.position_pnl_pct_gauge = Gauge(
            'pde_position_pnl_pct',
            'Current position unrealized PnL percentage',
            ['token_type']
        )
        self.tp_sl_counter = Counter(
            'pde_tp_sl_total',
            'TP/SL trigger count',
            ['token_type', 'trigger']  # trigger: 'tp', 'sl', 'expire'
        )
        
        # Cumulative trading counters (simple, no labels)
        self.phase_a_cumulative = Counter(
            'pde_phase_a_trades_cumulative',
            'Cumulative Phase A trades across all rounds'
        )
        self.phase_b_cumulative = Counter(
            'pde_phase_b_trades_cumulative',
            'Cumulative Phase B trades across all rounds'
        )
        self.rounds_counter = Counter(
            'pde_rounds_total',
            'Total rounds completed'
        )
        
        # Latency monitoring metrics
        self.btc_momentum_gauge = Gauge(
            'pde_btc_momentum_bps',
            'BTC price momentum (basis points over recent window)'
        )
        self.latency_gap_gauge = Gauge(
            'pde_latency_gap_ms',
            'Data freshness gap: Binance vs Polymarket (ms, positive = Binance fresher)'
        )
        self.phase_a_skip_counter = Counter(
            'pde_phase_a_skip_total',
            'Phase A trade skips by reason',
            ['reason']  # 'no_btc', 'no_jump', 'slippage', 'no_depth'
        )
        
        # Order book depth metrics
        self.order_slippage_gauge = Gauge(
            'pde_order_slippage_pct',
            'Estimated slippage for last order',
            ['token_type']
        )
        
        # Binance BTC price metric
        self.btc_price_gauge = Gauge(
            'pde_btc_price',
            'Real-time BTC spot price from Binance'
        )
        self.btc_delta_p_gauge = Gauge(
            'pde_btc_delta_p',
            'BTC price offset from round start (USD)'
        )
        
        self.log.info("📊 Prometheus metrics initialized for PDE Strategy")

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def on_start(self) -> None:
        self.log.info("🚀 Starting Polymarket PDE Strategy (Dual-Phase Engine)")
        self.log.info(f"   Base slug        : {self.config.market_base_slug}")
        self.log.info(f"   Interval (min)   : {self.config.market_interval_minutes}")
        self.log.info(f"   Trade amount USD : ${self.config.trade_amount_usd}")
        self.log.info(f"   Take profit      : +{self.config.take_profit_pct:.0%}")
        self.log.info(f"   Stop loss        : -{self.config.stop_loss_pct:.0%}")
        self.log.info(f"   Phase A EV threshold: {self.config.ev_threshold_A}")
        self.log.info(f"   Phase A max trades: {self.config.max_A_trades}")
        self.log.info(f"   Phase B delta min: {self.config.delta_tail_min}")
        self.log.info(f"   BTC jump threshold: {self.config.btc_jump_threshold_bps} bps")
        self.log.info(f"   Jump staleness    : {self.config.jump_staleness_sec}s")
        self.log.info(f"   Max slippage      : {self.config.max_slippage_pct:.0%}")

        # Start Prometheus HTTP server
        try:
            start_http_server(8001)  # Use different port from existing strategy
            self.log.info("📊 Prometheus metrics server started on http://localhost:8001")
            self.log.info("   Metrics endpoint: http://localhost:8001/metrics")
        except Exception as e:
            self.log.warning(f"⚠️  Failed to start Prometheus server: {e}")

        self._subscribe_current_market()
        
        # Subscribe to Binance BTCUSDT trade ticks for real-time BTC price
        self.subscribe_trade_ticks(self.btc_instrument_id)
        self.log.info(f"📈 Subscribed to Binance BTC spot: {self.btc_instrument_id}")

        if self.config.auto_rollover:
            self.clock.set_timer(
                name="pde_market_rollover_check",
                interval=timedelta(minutes=1),
                callback=self._on_rollover_timer,
            )
        
        # Schedule proactive provider refresh at halfway through cached instruments
        self._schedule_next_provider_refresh()

    def on_stop(self) -> None:
        self.clock.cancel_timer("pde_market_rollover_check")
        
        instruments_to_unsub = []
        if self.instrument:
            instruments_to_unsub.append(self.instrument.id)
        if self.down_instrument:
            instruments_to_unsub.append(self.down_instrument.id)
        
        for instrument_id in instruments_to_unsub:
            self.cancel_all_orders(instrument_id=instrument_id)
            self.unsubscribe_quote_ticks(instrument_id)
            self.unsubscribe_order_book_deltas(instrument_id)
        
        self.unsubscribe_trade_ticks(self.btc_instrument_id)
        self.log.info("🛑 PDE Strategy stopped.")

    def on_reset(self) -> None:
        self.instrument = None
        self.down_instrument = None
        self.start_price = {'up': None, 'down': None}
        self.start_ts = None
        self.positions = {
            'up': {'open': False, 'entry_price': 0.0},
            'down': {'open': False, 'entry_price': 0.0},
        }
        self.A_trades = 0
        self.tail_trade_done = False
        self.current_market_slug = None
        self.price_history['up'].clear()
        self.price_history['down'].clear()
        self.btc_price = None
        self.btc_start_price = None
        self.btc_price_history.clear()
        self.btc_anchor_price = None
        self.btc_jump_ts = 0.0
        self.btc_jump_direction = 0
        self.btc_last_tick_wall_ts = 0.0
        self.poly_last_tick_wall_ts = 0.0

    # ── Slug calculation ───────────────────────────────────────────────────

    def _get_current_slug(self) -> str:
        now = datetime.now(timezone.utc)
        interval = self.config.market_interval_minutes
        aligned_minute = (now.minute // interval) * interval
        market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
        return f"{self.config.market_base_slug}-{int(market_time.timestamp())}"

    # ── Market subscription ────────────────────────────────────────────────

    def _subscribe_current_market(self) -> None:
        """Subscribe to current market Up/Down tokens.
        
        If instruments are not found in cache, does NOT commit the slug,
        allowing _on_rollover_timer to retry on the next tick.
        """
        slug = self._get_current_slug()
        if slug == self.current_market_slug:
            return

        # Only unsubscribe old instruments on FIRST attempt (not retries)
        if not self._rollover_in_progress:
            old_instruments = []
            if self.instrument and self.current_market_slug:
                old_instruments.append(self.instrument)
            if self.down_instrument and self.current_market_slug:
                old_instruments.append(self.down_instrument)
                
            for old_inst in old_instruments:
                self.log.info(f"📤 Unsubscribing: {old_inst.id}")
                try:
                    self.unsubscribe_quote_ticks(old_inst.id)
                except Exception as e:
                    self.log.warning(f"⚠️  Unsubscribe quote ticks failed (non-fatal): {e}")
                try:
                    self.unsubscribe_order_book_deltas(old_inst.id)
                except Exception as e:
                    self.log.warning(f"⚠️  Unsubscribe order book failed (non-fatal): {e}")
                self.cancel_all_orders(instrument_id=old_inst.id)
            
            # Clear instrument refs to prevent stale trading during retry
            self.instrument = None
            self.down_instrument = None

        self.log.info(f"📥 Looking for market in cache: {slug}")

        all_instruments = self.cache.instruments(venue=Venue("POLYMARKET"))
        self.log.info(f"   Cache has {len(all_instruments)} POLYMARKET instruments")

        # Find Up and Down tokens
        up_matched = None
        down_matched = None
        
        matching_instruments = []
        for inst in all_instruments:
            info = getattr(inst, 'info', {}) or {}
            market_slug = info.get("market_slug", "")
            
            if market_slug == slug:
                matching_instruments.append(inst)
        
        self.log.info(f"🔍 Found {len(matching_instruments)} instruments for slug {slug}")
        
        if len(matching_instruments) >= 2:
            for inst in matching_instruments:
                info = getattr(inst, 'info', {}) or {}
                outcome = info.get("outcome", "").lower()
                
                if outcome == "up" or outcome == "yes":
                    up_matched = inst
                elif outcome == "down" or outcome == "no":
                    down_matched = inst
            
            if up_matched is None or down_matched is None:
                instruments_with_tokens = []
                for inst in matching_instruments:
                    token_id = str(inst.id).split("-")[-1].split(".")[0] if hasattr(inst, 'id') else ""
                    try:
                        token_int = int(token_id) if token_id.isdigit() else 0
                    except:
                        token_int = 0
                    instruments_with_tokens.append((token_int, inst))
                
                instruments_with_tokens.sort(key=lambda x: x[0])
                
                if len(instruments_with_tokens) >= 1 and up_matched is None:
                    up_matched = instruments_with_tokens[0][1]
                
                if len(instruments_with_tokens) >= 2 and down_matched is None:
                    down_matched = instruments_with_tokens[1][1]

        # ── If instruments NOT found, enter retry mode ──
        if up_matched is None:
            self._rollover_in_progress = True
            self._rollover_retry_count += 1
            if self._rollover_retry_count <= 30:  # retry for up to ~30 timer ticks
                self.log.warning(
                    f"⏳ No instruments for {slug} (retry {self._rollover_retry_count}/30). "
                    f"Requesting provider refresh..."
                )
                # Trigger InstrumentProvider to re-call build_btc_updown_slugs()
                # with current time, loading fresh instruments into cache
                try:
                    self.request_instruments(
                        venue=Venue("POLYMARKET"),
                        callback=self._on_instruments_refreshed,
                    )
                except Exception as e:
                    self.log.warning(f"request_instruments failed (non-fatal): {e}")
            else:
                self.log.error(
                    f"❌ Gave up finding instruments for {slug} after {self._rollover_retry_count} retries. "
                    f"Waiting for next 5-min window."
                )
                # Give up on this slug — will naturally advance to next window
                self._rollover_in_progress = False
                self._rollover_retry_count = 0
            return

        # ── Instruments found — commit slug and subscribe ──
        self.current_market_slug = slug
        self._rollover_in_progress = False
        self._rollover_retry_count = 0

        self.instrument = up_matched
        self.subscribe_quote_ticks(up_matched.id)
        self.subscribe_order_book_deltas(up_matched.id, book_type=BookType.L2_MBP)
        self.log.info(f"📊 Subscribed to Up: {up_matched.id}")
            
        if down_matched:
            self.down_instrument = down_matched
            self.subscribe_quote_ticks(down_matched.id)
            self.subscribe_order_book_deltas(down_matched.id, book_type=BookType.L2_MBP)
            self.log.info(f"📊 Subscribed to Down: {down_matched.id}")
        else:
            self.log.warning(f"⚠️  No Down token found for {slug}")

    def _on_instruments_refreshed(self, request_id) -> None:
        """Callback after request_instruments completes — retry subscription immediately"""
        all_instruments = self.cache.instruments(venue=Venue("POLYMARKET"))
        self.log.info(
            f"🔄 Provider refresh complete: {len(all_instruments)} instruments in cache. "
            f"Retrying subscription..."
        )
        self._subscribe_current_market()

    # ── Proactive provider refresh ────────────────────────────────────────

    def _schedule_next_provider_refresh(self) -> None:
        """Schedule the next proactive provider refresh at halfway through cached windows.
        
        slug_builder generates NUM_WINDOWS windows (e.g. 24 × 5min = 2h).
        We refresh at the halfway mark (e.g. 12 × 5min = 1h) so the cache
        always has >= 1h of upcoming instruments.
        """
        NUM_WINDOWS = 24  # 与 slug_builder 保持一致
        interval_min = self.config.market_interval_minutes
        half_coverage_sec = (NUM_WINDOWS // 2) * interval_min * 60  # 12 × 5 × 60 = 3600s = 1h
        self._next_provider_refresh_ts = self.clock.timestamp() + half_coverage_sec
        self._provider_refresh_pending = False
        self.log.info(
            f"📅 Next proactive instrument refresh in {half_coverage_sec // 60} min "
            f"(cache covers {NUM_WINDOWS * interval_min} min)"
        )

    def _check_proactive_refresh(self) -> None:
        """Check if it's time for a proactive provider refresh."""
        if self._provider_refresh_pending:
            return  # already waiting for a refresh callback
        if self._next_provider_refresh_ts <= 0:
            return
        now_ts = self.clock.timestamp()
        if now_ts < self._next_provider_refresh_ts:
            return
        
        self._provider_refresh_pending = True
        self.log.info("🔄 Proactive provider refresh: reloading instruments for next cycle...")
        try:
            self.request_instruments(
                venue=Venue("POLYMARKET"),
                callback=self._on_proactive_refresh_done,
            )
        except Exception as e:
            self.log.warning(f"Proactive refresh failed: {e}")
            self._provider_refresh_pending = False
            # Retry on next timer tick
            self._next_provider_refresh_ts = now_ts + 60

    def _on_proactive_refresh_done(self, request_id) -> None:
        """Callback after proactive refresh completes — reschedule next one."""
        all_instruments = self.cache.instruments(venue=Venue("POLYMARKET"))
        self.log.info(
            f"✅ Proactive refresh complete: {len(all_instruments)} instruments in cache."
        )
        self._schedule_next_provider_refresh()

    # ── Rollover timer ─────────────────────────────────────────────────────

    def _on_rollover_timer(self, event) -> None:
        # ── Proactive provider refresh: keep cache fresh for long-running ──
        self._check_proactive_refresh()

        # ── If rollover is in progress (waiting for instruments), just retry ──
        if self._rollover_in_progress:
            self._subscribe_current_market()
            return

        # ── Staleness watchdog: detect WS drop and force resubscribe ──
        now_ts = self.clock.timestamp()
        if (self.last_quote_tick_ts > 0
                and (now_ts - self.last_quote_tick_ts) > 30
                and self._resubscribe_attempts < 3):
            self._resubscribe_attempts += 1
            self.log.warning(
                f"⚠️  No quote tick for {now_ts - self.last_quote_tick_ts:.0f}s — "
                f"forcing resubscribe (attempt {self._resubscribe_attempts}/3)"
            )
            self._force_resubscribe()
            return

        new_slug = self._get_current_slug()
        if new_slug == self.current_market_slug:
            return
            
        self.rounds_counter.inc()
        self.log.info(
            f"🔄 Rollover: {self.current_market_slug} → {new_slug} | "
            f"累积: A={self.phase_a_cumulative._value.get()}, "
            f"B={self.phase_b_cumulative._value.get()}, "
            f"rounds={self.rounds_counter._value.get()}"
        )
        
        # 1. Cancel pending orders
        if self.instrument:
            self.cancel_all_orders(instrument_id=self.instrument.id)
        if self.down_instrument:
            self.cancel_all_orders(instrument_id=self.down_instrument.id)
        
        # 2. Close all open positions (realize PnL)
        self._close_all_open_positions()
            
        # Reset round state
        self.start_price = {'up': None, 'down': None}
        self.start_ts = None
        self.positions = {
            'up': {'open': False, 'entry_price': 0.0},
            'down': {'open': False, 'entry_price': 0.0},
        }
        self.A_trades = 0
        self.tail_trade_done = False
        self.price_history['up'].clear()
        self.price_history['down'].clear()
        self.btc_start_price = None
        self.btc_anchor_price = self.btc_price  # Keep anchor at current BTC price for jump detection
        # Keep btc_jump_ts/direction — recent jumps carry over to new round
        self.btc_price_history.clear()
        
        self._subscribe_current_market()
        self.last_rollover_check = datetime.now(timezone.utc)
        self.last_quote_tick_ts = self.clock.timestamp()  # give new WS time to connect
        self._resubscribe_attempts = 0

    def _force_resubscribe(self) -> None:
        """Force unsubscribe + resubscribe to recover from WS disconnect"""
        for inst in (self.instrument, self.down_instrument):
            if inst is None:
                continue
            try:
                self.unsubscribe_quote_ticks(inst.id)
            except Exception:
                pass
            try:
                self.unsubscribe_order_book_deltas(inst.id)
            except Exception:
                pass

        # Re-subscribe (will trigger new WS connection)
        if self.instrument:
            self.subscribe_quote_ticks(self.instrument.id)
            self.subscribe_order_book_deltas(self.instrument.id, book_type=BookType.L2_MBP)
            self.log.info(f"🔄 Resubscribed Up: {self.instrument.id}")
        if self.down_instrument:
            self.subscribe_quote_ticks(self.down_instrument.id)
            self.subscribe_order_book_deltas(self.down_instrument.id, book_type=BookType.L2_MBP)
            self.log.info(f"🔄 Resubscribed Down: {self.down_instrument.id}")

    # ── Binance BTC trade tick processing ────────────────────────────────

    def on_trade_tick(self, tick: TradeTick) -> None:
        """Process trade ticks from Binance BTCUSDT"""
        if tick.instrument_id != self.btc_instrument_id:
            return
        
        self.btc_price = float(tick.price)
        self.btc_price_gauge.set(self.btc_price)
        self.btc_last_tick_wall_ts = self.clock.timestamp()
        
        # Initialize BTC anchor for jump detection — always, even before round starts
        if self.btc_anchor_price is None:
            self.btc_anchor_price = self.btc_price
        
        # Initialize BTC start price for the round
        if self.btc_start_price is None and self.start_ts is not None:
            self.btc_start_price = self.btc_price
            self.log.info(f"📈 BTC start_price={self.btc_start_price:.2f}")
        
        # ── Jump detection ──
        if self.btc_anchor_price is not None and self.btc_anchor_price > 0:
            move_bps = (self.btc_price - self.btc_anchor_price) / self.btc_anchor_price * 10000
            self.btc_momentum_gauge.set(move_bps)
            if abs(move_bps) >= self.config.btc_jump_threshold_bps:
                self.btc_jump_ts = self.btc_last_tick_wall_ts
                self.btc_jump_direction = 1 if move_bps > 0 else -1
                self.btc_anchor_price = self.btc_price  # reset anchor to new level
        
        # Update BTC price history for sigma estimation
        self.btc_price_history.append(self.btc_price)
        
        # Update BTC delta_p metric
        if self.btc_start_price is not None:
            btc_delta = self.btc_price - self.btc_start_price
            self.btc_delta_p_gauge.set(btc_delta)

    # ── Quote tick processing ──────────────────────────────────────────────

    def on_quote_tick(self, tick: QuoteTick) -> None:
        """Process quote ticks from Up/Down tokens"""
        self.last_quote_tick_ts = self.clock.timestamp()
        self.poly_last_tick_wall_ts = self.last_quote_tick_ts
        self._resubscribe_attempts = 0  # reset on any live tick
        
        # Track latency gap: positive = Binance data is fresher (speed advantage)
        if self.btc_last_tick_wall_ts > 0:
            gap_ms = (self.btc_last_tick_wall_ts - self.poly_last_tick_wall_ts) * 1000
            self.latency_gap_gauge.set(gap_ms)
        if self.instrument and tick.instrument_id == self.instrument.id:
            self._process_tick(tick, is_up=True)
        elif self.down_instrument and tick.instrument_id == self.down_instrument.id:
            self._process_tick(tick, is_up=False)

    def _process_tick(self, tick: QuoteTick, is_up: bool) -> None:
        """Main tick processing logic for PDE strategy"""
        
        price = float(tick.bid_price + tick.ask_price) / 2.0
        token_key = 'up' if is_up else 'down'
        
        ts_sec = tick.ts_event // 1_000_000_000
        
        # Initialize round timestamp
        if self.start_ts is None:
            self.start_ts = ts_sec
            self.A_trades = 0
            self.tail_trade_done = False
            self.price_history['up'].clear()
            self.price_history['down'].clear()
            self.btc_start_price = self.btc_price  # Snapshot BTC price at round start
            self.btc_anchor_price = self.btc_price  # Reset jump anchor for new round
            self.btc_price_history.clear()
            self.log.info(f"🎬 Round started: ts={self.start_ts}, btc={self.btc_start_price}")
        
        # Initialize start_price per token
        if self.start_price[token_key] is None:
            self.start_price[token_key] = price
            self.log.info(f"🎬 {token_key.upper()} start_price={price:.4f}")
            return
        
        # Update price history per token
        self.price_history[token_key].append(price)
        
        # Calculate round state
        t_elapsed = ts_sec - self.start_ts
        remaining = 300 - t_elapsed
        
        # ── Always check TP/SL on existing position for this token ──
        self._check_tp_sl(token_key, price)
        
        # Guard: round expired → close all positions, stop processing
        if remaining <= 0:
            self._close_all_open_positions()
            return
        
        # Compute two delta metrics (strictly from BTC price — no token fallback)
        #   delta_log: dimensionless log-return for Phase A z-score calculation
        #   delta_usd: USD price offset for Phase B flip probability lookup
        if self.btc_price is None or self.btc_start_price is None or self.btc_start_price <= 0:
            return  # Cannot trade without BTC reference price
        
        delta_log = math.log(self.btc_price / self.btc_start_price)
        delta_usd = self.btc_price - self.btc_start_price
        
        # Update metrics
        token_type = 'up' if is_up else 'down'
        self.delta_p_gauge.labels(token_type=token_type).set(delta_usd)
        self.remaining_time_gauge.set(remaining)
        
        # Route to appropriate phase
        if t_elapsed < 240:
            self._execute_phase_A(tick, is_up, t_elapsed, remaining, delta_log, abs(delta_log))
        else:
            self._execute_phase_B(tick, is_up, remaining, delta_usd, abs(delta_usd))

    # ── Phase A: EV-driven strategy ───────────────────────────────────────

    def _execute_phase_A(self, tick: QuoteTick, is_up: bool, t_elapsed: int, 
                         remaining: float, delta_log: float, abs_delta_log: float) -> None:
        """Phase A (0-240s): Brownian motion EV arbitrage
        
        Requires a recent BTC price jump (speed advantage gate) before trading.
        
        Args:
            delta_log: dimensionless log-return of BTC price since round start
            abs_delta_log: absolute value of delta_log
        """
        
        self.strategy_state_gauge.set(1)  # Phase A
        
        token_key = 'up' if is_up else 'down'
        
        # Skip entry logic if this token already has an open position (wait for TP/SL)
        if self.positions[token_key]['open']:
            return
        
        # Skip if max buy entries reached for this round
        if self.A_trades >= self.config.max_A_trades:
            return
        
        # ── Speed advantage gate: require recent BTC jump ──
        now_ts = self.clock.timestamp()
        jump_age = now_ts - self.btc_jump_ts
        if self.btc_jump_ts == 0 or jump_age > self.config.jump_staleness_sec:
            self.phase_a_skip_counter.labels(reason='no_jump').inc()
            return
        
        # Estimate volatility
        sigma = self._estimate_sigma(token_key)
        if sigma is None or sigma <= 0:
            return
        
        self.sigma_gauge.set(sigma)
        
        # Calculate theoretical probability using Brownian motion
        # Both delta_log and sigma are in log-return space (dimensionless)
        sigma_rem = sigma * math.sqrt(remaining)
        if sigma_rem <= 0:
            return
        
        z = delta_log / sigma_rem
        p_up = norm.cdf(z)
        
        token_type = token_key
        self.p_up_gauge.labels(token_type=token_type).set(p_up)
        
        # Get market implied probability from current token
        market_ask = float(tick.ask_price)
        
        # Calculate EV for buying THIS token
        # Up token:   ev = P(BTC up) - up_price    (token pays if BTC up)
        # Down token: ev = P(BTC down) - down_price (token pays if BTC down)
        if is_up:
            ev_buy = p_up - market_ask
        else:
            ev_buy = (1 - p_up) - market_ask
        
        self.ev_gauge.labels(token_type=token_type, side='buy').set(ev_buy)
        
        # Trading logic: buy this token if EV is positive enough
        if ev_buy > self.config.ev_threshold_A:
            self._open_position(is_up, OrderSide.BUY,
                                f"Phase A: EV={ev_buy:.4f} > threshold, BUY {token_type.upper()} @ mkt={market_ask:.4f}")
            self.A_trades += 1
            self.phase_a_trades_gauge.set(self.A_trades)
            self.trades_counter.labels(phase='A', token_type=token_type, side='buy').inc()
            self.phase_a_cumulative.inc()

    # ── Phase B: Tail continuation strategy ─────────────────────────────────

    def _execute_phase_B(self, tick: QuoteTick, is_up: bool, remaining: float, 
                         delta_usd: float, abs_delta_usd: float) -> None:
        """Phase B (240-300s): Tail continuation strategy
        
        When flip probability is low (price unlikely to reverse),
        bet on continuation in the current direction.
        
        Args:
            delta_usd: USD price offset for flip probability lookup
            abs_delta_usd: absolute value of delta_usd
        """
        
        self.strategy_state_gauge.set(2)  # Phase B
        
        if self.tail_trade_done:
            return
        
        if abs_delta_usd < self.config.delta_tail_min:
            return
        
        # Query flip probability from lookup table (USD-based)
        p_flip = self._get_flip_prob(remaining, abs_delta_usd)
        if p_flip is None:
            return
        
        token_type = 'up' if is_up else 'down'
        self.p_flip_gauge.labels(token_type=token_type).set(p_flip)
        
        # Determine target token and get its actual ask price
        if delta_usd > 0:
            target_is_up = True
            target_inst = self.instrument
        else:
            target_is_up = False
            target_inst = self.down_instrument
        
        if target_inst is None:
            return
        
        target_quote = self.cache.quote_tick(target_inst.id)
        if target_quote is None or float(target_quote.ask_price) <= 0:
            return
        
        actual_ask = float(target_quote.ask_price)
        
        # Dynamic EV: prob of continuation × payout - cost
        # If continuation (prob = 1-p_flip): token settles at $1, profit = $1 - ask
        # If flip (prob = p_flip): token settles at $0, loss = ask
        # EV per token = (1-p_flip) × 1 - ask = (1-p_flip) - ask
        ev_tail = (1 - p_flip) - actual_ask
        
        target_type = 'up' if target_is_up else 'down'
        self.ev_tail_gauge.labels(token_type=target_type).set(ev_tail)
        
        # Trading logic: bet on continuation — BTC up → BUY Up token, BTC down → BUY Down token
        if ev_tail > self.config.ev_threshold_tail:
            self._open_position(target_is_up, OrderSide.BUY,
                                f"Phase B continuation: BUY {target_type.upper()}, "
                                f"EV={ev_tail:.4f}, p_flip={p_flip:.4f}, ask={actual_ask:.4f}")
            self.tail_trade_done = True
            self.trades_counter.labels(phase='B', token_type=target_type, side='buy').inc()
            self.phase_b_cumulative.inc()

    # ── Position management ────────────────────────────────────────────────

    def _check_tp_sl(self, token_key: str, current_price: float) -> None:
        """Check take-profit / stop-loss for a token's open position"""
        pos = self.positions[token_key]
        if not pos['open'] or pos['entry_price'] <= 0:
            return
        
        entry = pos['entry_price']
        pnl_pct = (current_price - entry) / entry
        
        # Update live PnL percentage metric
        self.position_pnl_pct_gauge.labels(token_type=token_key).set(pnl_pct)
        
        if pnl_pct >= self.config.take_profit_pct:
            self._close_token_position(
                token_key,
                f"TP hit: {pnl_pct:+.1%} (entry={entry:.4f}, now={current_price:.4f})")
            self.tp_sl_counter.labels(token_type=token_key, trigger='tp').inc()
        elif pnl_pct <= -self.config.stop_loss_pct:
            self._close_token_position(
                token_key,
                f"SL hit: {pnl_pct:+.1%} (entry={entry:.4f}, now={current_price:.4f})")
            self.tp_sl_counter.labels(token_type=token_key, trigger='sl').inc()

    def _close_token_position(self, token_key: str, reason: str) -> None:
        """Close a single token's position via cache lookup"""
        instrument = self.instrument if token_key == 'up' else self.down_instrument
        if instrument is None:
            return
        
        positions = self.cache.positions(venue=Venue("POLYMARKET"))
        for position in positions:
            if position.instrument_id == instrument.id and position.is_open:
                self.log.info(f"📤 Closing {token_key.upper()}: {reason}")
                self.close_position(position)
                break
        
        # Reset local tracking (on_position_closed will update metrics)
        self.positions[token_key]['open'] = False
        self.positions[token_key]['entry_price'] = 0.0

    def _close_all_open_positions(self) -> None:
        """Close all open positions (used at round end and rollover)"""
        for token_key in ('up', 'down'):
            if self.positions[token_key]['open']:
                self._close_token_position(token_key, "Round ended / Rollover")
                self.tp_sl_counter.labels(token_type=token_key, trigger='expire').inc()
                self.position_pnl_pct_gauge.labels(token_type=token_key).set(0)

    # ── Utility functions ──────────────────────────────────────────────────

    def _estimate_sigma(self, token_key: str) -> float | None:
        """Estimate volatility strictly from BTC price history (no token fallback)"""
        if self.start_ts is None:
            return None
        
        # Require minimum elapsed time to avoid noisy sigma from sub-second tick bursts
        now_sec = self.clock.timestamp()
        elapsed = now_sec - self.start_ts
        if elapsed < 30:
            return None  # Not enough time for meaningful volatility estimate
        
        MIN_POINTS = 50  # Need enough data points for statistical significance
        
        # Strictly use BTC price history — token prices are probabilities, not asset prices
        if len(self.btc_price_history) < MIN_POINTS:
            return None
        prices = np.array(self.btc_price_history)
        
        # Filter out zero/negative prices to avoid log issues
        prices = prices[prices > 0]
        if len(prices) < MIN_POINTS:
            return None
        
        log_returns = np.diff(np.log(prices))
        
        if len(log_returns) == 0:
            return None
        
        # Scale to 5-minute period using actual elapsed time
        # Each log_return covers (elapsed / N_returns) seconds on average
        n_returns = len(log_returns)
        avg_tick_interval = elapsed / n_returns  # seconds per tick
        if avg_tick_interval <= 0:
            return None
        sigma = np.std(log_returns) * np.sqrt(300 / avg_tick_interval)
        
        # Sanity check: reject extreme sigma values
        if sigma < 1e-6 or sigma > 1.0:
            return None
        
        return float(sigma)

    def _get_flip_prob(self, tau: float, abs_delta: float) -> float | None:
        """Query flip probability from lookup table"""
        for (tau_low, tau_high, delta_low, delta_high), p in self.flip_stats.items():
            if tau_low <= tau <= tau_high and delta_low <= abs_delta <= delta_high:
                return p
        return None

    def _check_book_depth(self, instrument, qty: float, side: OrderSide, token_key: str) -> tuple[bool, float]:
        """Check order book depth and estimate slippage.
        
        Returns:
            (ok_to_trade, slippage_pct) — slippage_pct is relative to best ask
        """
        try:
            book = self.cache.order_book(instrument.id)
            if book is None:
                return True, 0.0  # No book data available, proceed optimistically
            
            best_ask = book.best_ask_price()
            if best_ask is None or float(best_ask) <= 0:
                return True, 0.0
            
            avg_px = book.get_avg_px_for_quantity(
                instrument.make_qty(Decimal(str(qty))), side
            )
            if avg_px <= 0:
                return True, 0.0
            
            best_ask_f = float(best_ask)
            slippage_pct = max(0.0, (avg_px - best_ask_f) / best_ask_f)
            self.order_slippage_gauge.labels(token_type=token_key).set(slippage_pct)
            
            # If avg_px is wildly above best_ask (>2x), book is too thin for
            # meaningful slippage estimate — proceed with trade at best available
            if avg_px > 2 * best_ask_f:
                self.log.debug(
                    f"Book thin for {token_key}: avg_px={avg_px:.4f} vs best={best_ask_f:.4f}, "
                    f"qty={qty:.0f} — proceeding anyway"
                )
                return True, 0.0
            
            return True, slippage_pct
            
        except Exception as e:
            self.log.debug(f"Book depth check error (non-fatal): {e}")
            return True, 0.0

    def _open_position(self, is_up: bool, side: OrderSide, reason: str) -> None:
        """Open a position: qty = trade_amount_usd / ask_price"""
        instrument = self.instrument if is_up else self.down_instrument
        if not instrument:
            self.log.warning(f"⚠️  Cannot open position: instrument not available")
            return
        
        token_key = 'up' if is_up else 'down'
        
        # Get latest quote from cache for the TARGET instrument
        quote = self.cache.quote_tick(instrument.id)
        if not quote or float(quote.ask_price) <= 0:
            self.log.warning(f"⚠️  No valid quote for {token_key.upper()}")
            return
        
        entry_price = float(quote.ask_price)
        
        # Calculate quantity from USD amount
        qty = self.config.trade_amount_usd / entry_price
        
        # ── Order book depth / slippage check ──
        ok, slippage = self._check_book_depth(instrument, qty, side, token_key)
        if slippage > self.config.max_slippage_pct:
            self.log.warning(
                f"⚠️  Skipping {token_key.upper()}: slippage {slippage:.2%} > max {self.config.max_slippage_pct:.2%}"
            )
            self.phase_a_skip_counter.labels(reason='slippage').inc()
            return
        
        slippage_str = f", slip={slippage:.2%}" if slippage > 0 else ""
        self.log.info(f"📝 {reason} | BUY {token_key.upper()} @ {entry_price:.4f}, qty={qty:.2f} (${self.config.trade_amount_usd}{slippage_str})")
        
        order = self.order_factory.market(
            instrument_id=instrument.id,
            order_side=side,
            quantity=instrument.make_qty(Decimal(str(qty))),
            tags=[f"PDE_{token_key.upper()}_{side.name}"],
        )
        self.submit_order(order)
        
        # Track position state
        self.positions[token_key]['open'] = True
        self.positions[token_key]['entry_price'] = entry_price
        
        self.position_entry_price_gauge.labels(token_type=token_key).set(entry_price)

    # ── Event handlers ─────────────────────────────────────────────────────

    def on_order_filled(self, event) -> None:
        self.log.info(f"✅ Filled: {event.order_side.name} @ {event.last_px} | qty={event.last_qty}")

    def on_position_opened(self, event) -> None:
        token_type = 'up' if self.instrument and event.instrument_id == self.instrument.id else 'down'
        self.position_size_gauge.labels(token_type=token_type).set(float(event.quantity))
        self.log.info(f"💼 Position opened: {token_type} qty={event.quantity}")

    def on_position_changed(self, event) -> None:
        token_type = 'up' if self.instrument and event.instrument_id == self.instrument.id else 'down'
        self.unrealized_pnl_gauge.labels(token_type=token_type).set(float(event.unrealized_pnl))

    def on_position_closed(self, event) -> None:
        token_type = 'up' if self.instrument and event.instrument_id == self.instrument.id else 'down'
        self.realized_pnl_gauge.labels(token_type=token_type).set(float(event.realized_pnl))
        self.unrealized_pnl_gauge.labels(token_type=token_type).set(0)
        self.position_size_gauge.labels(token_type=token_type).set(0)
        self.log.info(f"💰 Position closed: {token_type} realized_pnl={event.realized_pnl}")
