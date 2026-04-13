"""Polymarket PDE Strategy - Modular Implementation.

Combines all mixins into the main strategy class.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.identifiers import InstrumentId, Venue

from strategies.pde.base import PDEStrategyBase, PolymarketPDEStrategyConfig
from strategies.pde.market_mixin import PDEMarketMixin
from strategies.pde.execution_mixin import PDEExecutionMixin
from strategies.pde.signal_mixin import PDESignalMixin
from strategies.pde.data_mixin import PDEDataMixin
from strategies.pde.metrics_mixin import PDEMetricsMixin


class PolymarketPDEStrategy(
    PDEStrategyBase,
    PDEMarketMixin,
    PDEExecutionMixin,
    PDESignalMixin,
    PDEDataMixin,
    PDEMetricsMixin,
    Strategy
):
    """
    Polymarket Dual-Phase Engine Strategy (Modular Version).
    
    Phase A (0-240s): Momentum following with speed advantage
    Phase B (240-300s): Tail reversal probability trading
    
    Functional modules:
    - PDEMarketMixin: Market rollover, subscription, instrument management
    - PDEExecutionMixin: Order placement, position tracking, PnL
    - PDESignalMixin: EV calculation, flip stats, signal generation
    - PDEDataMixin: WebSocket streaming, tick processing, dashboard updates
    - PDEMetricsMixin: Prometheus metrics, health monitoring
    """
    
    def __init__(self, config: PolymarketPDEStrategyConfig) -> None:
        super().__init__(config)
        
        # Initialize collections
        from collections import deque
        self.price_history['up'] = deque(maxlen=100)
        self.price_history['down'] = deque(maxlen=100)
        self.btc_price_history = deque(maxlen=100)
    
    def on_start(self) -> None:
        """Strategy startup."""
        self.log.info("🚀 PDE Strategy (Modular) starting...")
        self.log.info(f"   Base slug: {self.config.market_base_slug}")
        self.log.info(f"   Interval: {self.config.market_interval_minutes}min")
        
        # Setup metrics
        self._setup_prometheus_metrics()
        
        # Load flip stats
        self.flip_stats = self._load_flip_stats_from_file()
        self._schedule_flip_stats_refresh()
        
        # Subscribe to BTC feed
        if self.config.btc_price_source == "mid":
            self.subscribe_quote_ticks(self.btc_instrument_id)
            self.log.info("📡 Subscribed BTC quote ticks (mid mode)")
        else:
            self.subscribe_trade_ticks(self.btc_instrument_id)
            self.log.info("📡 Subscribed BTC trade ticks")
        
        # Initialize market subscription
        self._subscribe_current_market()
        self._schedule_next_provider_refresh()
        
        # Create rollover timer (1s interval for precise prewarm + rollover)
        self.clock.set_timer(
            name="pde_rollover_check",
            interval=timedelta(seconds=1),
            callback=self._on_rollover_timer,
        )
        self.log.info("⏰ Rollover timer started (1s interval)")
        
        # Start live server
        try:
            from utils.live_stream_server import LiveStreamServer
            self.live_server = LiveStreamServer(host="0.0.0.0", port=8765)
            self.live_server.start()
            self.log.info("📡 Live stream server started on :8765")
            
            # Push initial phase state so dashboard shows Round immediately
            if self.current_market_slug:
                self.live_server.push_phase_state(
                    phase='A', remaining=self.config.market_interval_minutes * 60,
                    a_trades=0, b_trades=0, tail_done=False,
                    btc_round=self.current_market_slug
                )
        except Exception as e:
            self.log.warning(f"⚠️ Live server failed to start: {e}")
    
    def on_stop(self) -> None:
        """Strategy shutdown."""
        if hasattr(self, 'live_server') and self.live_server:
            self.live_server.stop()
            self.log.info("📡 Live server stopped")
        
        # Unsubscribe all
        if self.instrument:
            self.unsubscribe_quote_ticks(self.instrument.id)
        if self.down_instrument:
            self.unsubscribe_quote_ticks(self.down_instrument.id)
        self.unsubscribe_trade_ticks(self.btc_instrument_id)
        self.log.info("🛑 PDE Strategy stopped")
    
    def on_reset(self) -> None:
        """Reset strategy state."""
        self.instrument = None
        self.down_instrument = None
        self.start_price = {'up': None, 'down': None}
        self.start_ts = None
        self.current_market_slug = None
        self._rollover_in_progress = False
        self._rollover_retry_count = 0
        self.round_pnl = 0.0
        self.A_trades = 0
        self.B_trades = 0
        self.tail_trade_done = False
    
    def _process_tick_for_strategy(self, tick, is_up: bool) -> None:
        """Main tick processing - combines signal and execution logic."""
        token_key = 'up' if is_up else 'down'
        inst = self.instrument if is_up else self.down_instrument
        
        # Get mid price
        bid = float(tick.bid_price)
        ask = float(tick.ask_price)
        mid = (bid + ask) / 2.0
        
        # Update price history
        self._update_price_history(token_key, mid)
        
        # Calculate timing
        if self.start_ts is None:
            return
        
        elapsed = self.clock.timestamp() - self.start_ts
        remaining = self.config.market_interval_minutes * 60 - elapsed
        
        # Determine phase
        in_phase_a = elapsed < self.config.phase_a_duration_sec
        phase = 'A' if in_phase_a else 'B'
        
        # Calculate delta vs BTC
        if self.btc_start_price and self.btc_start_price > 0:
            delta_pct = (self.btc_price - self.btc_start_price) / self.btc_start_price
        else:
            delta_pct = 0.0
        
        # Calculate volatility
        sigma = self._calculate_sigma(token_key)
        
        # Calculate EV
        ev, p_flip, tail_cond = self._calculate_ev(
            token_key, mid, sigma, delta_pct, remaining, in_phase_a
        )
        
        # Push to dashboard
        self._push_ev(
            token=token_key,
            phase=phase,
            ev=ev,
            p_up=0.5 + delta_pct,
            sigma=sigma,
            p_flip=p_flip,
            remaining=remaining,
            tail_condition=tail_cond
        )
        
        # Trading logic
        if in_phase_a:
            # Phase A: momentum entry
            if ev > self.config.min_edge_threshold:
                self._maybe_exit_position(token_key, mid, ev, phase)
                self._enter_position(token_key, 'buy' if delta_pct > 0 else 'sell', 
                                     mid, self.config.per_trade_usd / mid, phase)
        else:
            # Phase B: tail reversal
            if tail_cond and not self.tail_trade_done:
                self._enter_position(token_key, 'buy' if delta_pct < 0 else 'sell',
                                     mid, self.config.per_trade_usd / mid, phase)
                self.tail_trade_done = True
            
            # Exit if EV turns negative
            self._maybe_exit_position(token_key, mid, ev, phase)
        
        # Push phase state periodically (every 3 seconds)
        now_ts = self.clock.timestamp()
        if not hasattr(self, '_last_phase_push_ts') or now_ts - self._last_phase_push_ts >= 3.0:
            self._last_phase_push_ts = now_ts
            self._push_phase_state(phase, remaining)
    
    def check_rollover(self) -> None:
        """Check and handle market rollover."""
        new_slug = self._get_current_slug()
        if new_slug == self.current_market_slug:
            return
        
        self.rounds_counter.inc()
        self.log.info(f"🔄 Rollover: {self.current_market_slug} -> {new_slug}")
        
        # Push rollover event
        self._push_rollover(self.current_market_slug or '', new_slug)
        
        # Close positions
        self._close_all_open_positions()
        
        # Reset state
        self.start_ts = self._calculate_round_start_ts()
        self.start_price = {'up': None, 'down': None}
        self.round_pnl = 0.0
        self.A_trades = 0
        self.B_trades = 0
        self.tail_trade_done = False
        self.btc_start_price = self.btc_price
        
        for token_key in ('up', 'down'):
            self.positions[token_key] = {
                'open': False, 'entry_price': 0.0, 'size': 0.0,
                'side': None, 'phase': None
            }
        
        # Activate new market
        if not self._activate_prewarmed_market(new_slug):
            self._subscribe_current_market()
        
        self.last_rollover_check = datetime.now(timezone.utc)
        self._post_rollover_subscribe_pending = True
        self._post_rollover_switch_ts = self.clock.timestamp()
        self._post_rollover_retry_count = 0
        self._resubscribe_attempts = 0
    
    def _on_rollover_timer(self, event) -> None:
        """1-second rollover timer: prewarm, rollover, staleness watchdog."""
        now_ts = self.clock.timestamp()
        _, next_boundary_ts = self._get_round_boundaries(now_ts)
        seconds_to_roll = next_boundary_ts - now_ts
        
        # Prewarm next market 10s before boundary
        if 0 < seconds_to_roll <= self._prewarm_lead_seconds:
            self._prewarm_next_market()
        
        # Post-rollover subscription verification
        if self._post_rollover_subscribe_pending:
            if (self.last_quote_tick_ts >= self._post_rollover_switch_ts
                    and (now_ts - self.last_quote_tick_ts) <= 5):
                self._post_rollover_subscribe_pending = False
                self._post_rollover_retry_count = 0
                self.log.info("✅ Post-rollover market data resumed")
            elif (
                self._post_rollover_retry_count < self._post_rollover_retry_max
                and (now_ts - self._last_post_rollover_retry_ts) >= self._post_rollover_retry_interval_sec
            ):
                self._post_rollover_retry_count += 1
                self._last_post_rollover_retry_ts = now_ts
                self.log.warning(
                    f"🔁 Post-rollover subscribe retry "
                    f"{self._post_rollover_retry_count}/{self._post_rollover_retry_max}"
                )
                self._force_resubscribe()
        
        # If rollover in progress (waiting for instruments), retry
        if self._rollover_in_progress:
            self._subscribe_current_market()
            return
        
        # Staleness watchdog: detect WS drop
        if (self.last_quote_tick_ts > 0
                and (now_ts - self.last_quote_tick_ts) > 90
                and self._resubscribe_attempts < 3):
            self._resubscribe_attempts += 1
            self.log.warning(
                f"⚠️  No quote tick for {now_ts - self.last_quote_tick_ts:.0f}s — "
                f"forcing resubscribe (attempt {self._resubscribe_attempts}/3)"
            )
            self._force_resubscribe()
            return
        
        # Check rollover
        self.check_rollover()
        
        # Periodic maintenance
        self._check_flip_stats_refresh()
        self._update_metrics()
