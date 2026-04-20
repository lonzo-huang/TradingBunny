"""Polymarket PDE Strategy - Modular Implementation.

Combines all mixins into the main strategy class.
"""

from __future__ import annotations

import os
import sys
import math
import uuid
import json
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
        self.log.info("[START] PDE Strategy (Modular) starting...")
        self.log.info(f"   Base slug: {self.config.market_base_slug}")
        self.log.info(f"   Interval: {self.config.market_interval_minutes}min")

        if getattr(self.config, 'persistence_enabled', False):
            try:
                from utils.pde_persistence import PDEPersistenceStore

                db_path = str(getattr(self.config, 'persistence_db_path', 'data/pde/pde_runs.sqlite3'))
                run_tag = getattr(self.config, 'order_id_tag', 'pde')
                now_utc = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                self.persistence_run_id = f"pde_{run_tag}_{now_utc}_{uuid.uuid4().hex[:8]}"
                self.persistence_store = PDEPersistenceStore(db_path)
                self.persistence_store.start_run(
                    run_id=self.persistence_run_id,
                    mode='live_node',
                    strategy='PolymarketPDEStrategy',
                    metadata={
                        'market_base_slug': self.config.market_base_slug,
                        'interval_minutes': self.config.market_interval_minutes,
                        'phase_a_start_sec': getattr(self.config, 'phase_a_start_sec', 0.0),
                        'phase_a_end_sec': getattr(self.config, 'phase_a_end_sec', 240.0),
                        'threshold_phase_b_usd': self.config.phase_b_momentum_threshold_usd,
                    },
                )
                self.log.info(
                    f"[PERSIST] Persistence enabled db={db_path} run_id={self.persistence_run_id}"
                )
            except Exception as e:
                self.persistence_store = None
                self.persistence_run_id = ""
                self.log.warning(f"[WARN] Persistence init failed: {e}")
        
        # Setup metrics
        self._setup_prometheus_metrics()
        
        # Load flip stats
        self.flip_stats = self._load_flip_stats_from_file()
        self._schedule_flip_stats_refresh()
        
        # Subscribe to BTC feed
        if self.config.btc_price_source == "mid":
            self.subscribe_quote_ticks(self.btc_instrument_id)
            self.log.info("[SERVER] Subscribed BTC quote ticks (mid mode)")
        else:
            self.subscribe_trade_ticks(self.btc_instrument_id)
            self.log.info("[SERVER] Subscribed BTC trade ticks")
        
        # Initialize market subscription
        self._subscribe_current_market()
        self._schedule_next_provider_refresh()
        
        # Create rollover timer (1s interval for precise prewarm + rollover)
        self.clock.set_timer(
            name="pde_rollover_check",
            interval=timedelta(seconds=1),
            callback=self._on_rollover_timer,
        )
        self.log.info("[TIMER] Rollover timer started (1s interval)")
        
        # Start live server
        try:
            from utils.live_stream_server import LiveStreamServer
            self.live_server = LiveStreamServer(host="0.0.0.0", port=8765)
            self.live_server.set_param_update_handler(self._apply_runtime_params)
            self.live_server.start()
            self.log.info("[OK] Live stream server started on :8765")
            
            # Push initial phase state so dashboard shows Round immediately
            if self.current_market_slug:
                self.live_server.push_phase_state(
                    phase='A', remaining=self.config.market_interval_minutes * 60,
                    a_trades=0, b_trades=0, tail_done=False,
                    btc_round=self.current_market_slug
                )
        except Exception as e:
            self.log.warning(f"[WARN] Live server failed to start: {e}")

        self._load_runtime_params_file()
    
    def on_stop(self) -> None:
        """Strategy shutdown."""
        if getattr(self, 'persistence_store', None):
            try:
                self.persistence_store.finish_run(
                    run_id=self.persistence_run_id,
                    summary={
                        'round_pnl': self.round_pnl,
                        'total_pnl': self.total_pnl,
                        'a_trades': self.A_trades,
                        'b_trades': self.B_trades,
                    },
                )
                self.persistence_store.close()
                self.log.info(f"[PERSIST] Persistence closed run_id={self.persistence_run_id}")
            except Exception as e:
                self.log.warning(f"[WARN] Persistence close failed: {e}")

        if hasattr(self, 'live_server') and self.live_server:
            self.live_server.stop()
            self.log.info("[OK] Live server stopped")
        
        # Unsubscribe all
        if self.instrument:
            self.unsubscribe_quote_ticks(self.instrument.id)
        if self.down_instrument:
            self.unsubscribe_quote_ticks(self.down_instrument.id)
        self.unsubscribe_trade_ticks(self.btc_instrument_id)
        self.log.info("[STOP] PDE Strategy stopped")
    
    def on_reset(self) -> None:
        """Reset strategy state."""
        self.instrument = None
        self.down_instrument = None
        self.start_price = {'up': None, 'down': None}
        self.ev_ema = {'up': None, 'down': None}
        self._phase_a_signal_state = {'up': 'neutral', 'down': 'neutral'}
        self._last_signal_eval_ts = {'up': 0.0, 'down': 0.0}
        self.start_ts = None
        self.current_market_slug = None
        self._rollover_in_progress = False
        self._rollover_retry_count = 0
        self.round_pnl = 0.0
        self.A_trades = 0
        self.B_trades = 0
        self.tail_trade_done = False
        self._p_t = {'up': 0.5, 'down': 0.5}  # Reset p(t) probabilities
        self._btc_prev_price = None

    def _runtime_params_path(self) -> str:
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'pde_runtime_overrides.json')

    def _load_runtime_params_file(self) -> None:
        path = self._runtime_params_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                params = json.load(f)
            if isinstance(params, dict) and params:
                result = self._apply_runtime_params(params)
                self.log.info(f"[CONFIG] Runtime params loaded: applied={list(result.get('applied', {}).keys())}")
        except Exception as e:
            self.log.warning(f"[WARN] Failed loading runtime params file: {e}")

    def _apply_runtime_params(self, params: dict) -> dict:
        """Apply mutable runtime params to current strategy config.

        Returns a dict: {"applied": {...}, "rejected": {...}}.
        """
        allowed_casts = {
            'ev_threshold_A': float,
            'ev_entry_hysteresis': float,
            'ev_deadband': float,
            'phase_b_momentum_threshold_usd': float,
            'take_profit_pct': float,
            'stop_loss_pct': float,
            'spread_tolerance': float,
            'max_A_trades': int,
            'per_trade_usd': float,
            'signal_eval_interval_sec': float,
            'entry_retry_cooldown_sec': float,
            'close_retry_interval_sec': float,
        }
        applied: dict = {}
        rejected: dict = {}

        for key, val in (params or {}).items():
            caster = allowed_casts.get(key)
            if caster is None:
                rejected[key] = 'not_runtime_mutable'
                continue
            if not hasattr(self.config, key):
                rejected[key] = 'config_missing'
                continue
            try:
                cast_val = caster(val)
                setattr(self.config, key, cast_val)
                applied[key] = cast_val
            except Exception as e:
                rejected[key] = f'cast_error:{e}'

        if applied:
            self.log.info(f"[CONFIG] Runtime params updated: {applied}")
        if rejected:
            self.log.warning(f"[WARN] Runtime params rejected: {rejected}")

        return {'applied': applied, 'rejected': rejected}
    
    def _process_tick_for_strategy(self, tick, is_up: bool) -> None:
        """Main tick processing - combines signal and execution logic."""
        token_key = 'up' if is_up else 'down'
        inst = self.instrument if is_up else self.down_instrument
        
        # Get mid price
        bid = float(tick.bid_price)
        ask = float(tick.ask_price)
        if ask <= 0 or bid <= 0:
            return
        spread_pct = (ask - bid) / ask
        if spread_pct > self.config.spread_tolerance:
            self.log.debug(f"[TRADE] Skip {token_key}: spread too wide {spread_pct:.4f} > {self.config.spread_tolerance:.4f}")
            return
        mid = (bid + ask) / 2.0

        # Keep live position mark-to-market updates responsive on every tick
        if self.positions[token_key].get('open'):
            self._push_live_position_mark(token_key, mid)
        
        # Update price history
        self._update_price_history(token_key, mid)
        
        # Calculate timing
        if self.start_ts is None:
            return

        now_ts = self.clock.timestamp()
        last_eval_ts = self._last_signal_eval_ts.get(token_key, 0.0)
        if now_ts - last_eval_ts < self.config.signal_eval_interval_sec:
            return
        self._last_signal_eval_ts[token_key] = now_ts

        elapsed = now_ts - self.start_ts
        remaining = self.config.market_interval_minutes * 60 - elapsed
        
        # Determine phase using configurable time window
        phase_a_start = getattr(self.config, 'phase_a_start_sec', 0.0)
        phase_a_end = getattr(self.config, 'phase_a_end_sec', 240.0)
        in_phase_a = phase_a_start <= elapsed < phase_a_end
        phase = 'A' if in_phase_a else 'B'
        
        # Calculate delta vs BTC
        if self.btc_start_price and self.btc_start_price > 0:
            delta_pct = (self.btc_price - self.btc_start_price) / self.btc_start_price
        else:
            delta_pct = 0.0
        
        # Calculate BTC tick-to-tick change for p(t) update
        if self._btc_prev_price and self._btc_prev_price > 0:
            delta_btc_pct = (self.btc_price - self._btc_prev_price) / self._btc_prev_price
        else:
            delta_btc_pct = 0.0
        self._btc_prev_price = self.btc_price
        
        # Calculate volatility
        sigma = self._calculate_sigma(token_key)
        
        # Calculate EV
        ev, p_flip, tail_cond = self._calculate_ev(
            token_key, mid, sigma, delta_pct, remaining, in_phase_a, delta_btc_pct
        )
        
        # Phase B: Trend-Reinforcement with time-weighted score
        # trend_score = |ΔP| × w(t), where w(t) = (t - 240) / 60
        phase_b_start = 240.0  # Phase B always starts at 240s
        phase_b_end = 300.0    # Phase B always ends at 300s
        
        # Time weight: linear from 0 (at 240s) to 1 (at 300s)
        if elapsed >= phase_b_start:
            time_weight = min(1.0, (elapsed - phase_b_start) / (phase_b_end - phase_b_start))
        else:
            time_weight = 0.0
        
        # Absolute deviation from BTC start price
        if self.btc_start_price and self.btc_start_price > 0:
            delta_p = self.btc_price - self.btc_start_price  # Can be positive or negative
            delta_p_pct = delta_p / self.btc_start_price
        else:
            delta_p = 0.0
            delta_p_pct = 0.0
        
        # Trend strength score: |ΔP| × w(t)
        trend_score = abs(delta_p_pct) * time_weight
        
        # Threshold check
        threshold_usd = float(getattr(self.config, 'phase_b_momentum_threshold_usd', 30.0))
        btc_price_for_th = self.btc_price or self.btc_start_price or 85000
        threshold_pct = threshold_usd / max(btc_price_for_th, 1)
        
        phase_b_target = 'up' if delta_p > 0 else 'down' if delta_p < 0 else 'flat'
        if trend_score < threshold_pct:
            phase_b_target = 'none'

        if (not in_phase_a) and (self.config.debug_raw_data or self.config.debug_ws):
            delta_usd = delta_pct * (self.btc_price or self.btc_start_price or 85000)
            self.log.info(
                f"[PHASE_B_DEBUG] token={token_key} delta_usd={delta_usd:+.1f} "
                f"trend_score={trend_score:.6f} time_weight={time_weight:.3f} "
                f"ev={ev:.4f} tail_cond={tail_cond} "
                f"th=${threshold_usd:.0f} target={phase_b_target}"
            )

        # Push to dashboard with new metrics
        # Phase A: p(t) internal probability, q(t) market price
        p_t = getattr(self, '_p_t', {}).get(token_key, 0.5)
        q_t = mid  # Market price as q(t)
        ev_alpha = getattr(self.config, 'ev_alpha', 0.001)
        
        self._push_ev(
            token=token_key,
            phase=phase,
            ev=ev,
            p_up=0.5 + delta_pct,
            sigma=sigma,
            p_flip=p_flip if in_phase_a else 0.0,
            remaining=remaining,
            tau=remaining,
            delta_pct=delta_pct,
            delta_usd=delta_pct,
            # Phase A new metrics
            p_t=p_t,
            q_t=q_t,
            ev_alpha=ev_alpha,
            # Phase B new metrics
            time_weight=time_weight if not in_phase_a else 0.0,
            trend_score=trend_score if not in_phase_a else 0.0,
            delta_p=delta_p if not in_phase_a else 0.0,
            delta_p_pct=delta_p_pct if not in_phase_a else 0.0,
            target=phase_b_target,
            momentum_threshold=threshold_usd,
            tail_done=self.tail_trade_done,
            tail_condition=tail_cond,
            # Phase window info
            phase_a_start=phase_a_start,
            phase_a_end=phase_a_end,
            elapsed=elapsed
        )
        
        # Trading logic
        pos = self.positions[token_key]
        self.log.debug(f"[TRADE] {token_key} phase={phase} ev={ev:.4f} threshold={self.config.min_edge_threshold} delta_pct={delta_pct:.4f} pos_open={pos['open']}")

        # Always evaluate exits first for already-open positions, regardless of phase signal state.
        if pos.get('open'):
            if self._maybe_exit_position(token_key, mid, bid, ask, ev, phase):
                return

        def _has_other_open_or_pending(tk: str) -> bool:
            for k, p in self.positions.items():
                if k == tk:
                    continue
                if p.get('open') or p.get('pending_open'):
                    return True
            return False

        if in_phase_a:
            # Phase A: momentum entry
            phase_a_threshold = self.config.ev_threshold_A
            entry_threshold = phase_a_threshold + self.config.ev_entry_hysteresis
            exit_threshold = max(0.0, phase_a_threshold - self.config.ev_entry_hysteresis)

            prev_state = self._phase_a_signal_state.get(token_key, 'neutral')
            state = prev_state
            if prev_state == 'neutral':
                if ev > entry_threshold:
                    state = 'bullish'
                elif ev < -entry_threshold:
                    state = 'bearish'
            elif prev_state == 'bullish':
                if ev < exit_threshold:
                    state = 'neutral'
            elif prev_state == 'bearish':
                if ev > -exit_threshold:
                    state = 'neutral'
            self._phase_a_signal_state[token_key] = state

            # Phase A: EV arbitrage - bidirectional trading
            # EV > entry_threshold -> Buy (market underpricing)
            # EV < -entry_threshold -> Sell (market overpricing)
            if ev > entry_threshold:
                signal_side = 'buy'
            elif ev < -entry_threshold:
                signal_side = 'sell'
            else:
                signal_side = None
            
            if signal_side and prev_state == 'neutral':
                if pos.get('open') or pos.get('pending_open'):
                    return
                if _has_other_open_or_pending(token_key):
                    self.log.debug(f"[TRADE] Skip {token_key} Phase A entry: other token has open/pending position")
                    return
                if self.A_trades >= self.config.max_A_trades:
                    return
                last_ts = self._last_entry_attempt_ts.get(token_key, 0.0)
                if now_ts - last_ts < self.config.entry_retry_cooldown_sec:
                    return

                # ④ Token price range filter: avoid thin books at extremes
                pa_min_price = float(getattr(self.config, 'phase_a_min_token_price', 0.30))
                pa_max_price = float(getattr(self.config, 'phase_a_max_token_price', 0.70))
                if not (pa_min_price <= mid <= pa_max_price):
                    self.log.debug(
                        f"[TRADE] Skip {token_key} Phase A: price {mid:.4f} outside [{pa_min_price}, {pa_max_price}]"
                    )
                    return

                # ⑤ BTC momentum minimum filter: skip entries when BTC is flat
                btc_momentum_min = float(getattr(self.config, 'phase_a_min_btc_delta', 0.0003))
                if abs(delta_pct) < btc_momentum_min:
                    self.log.debug(
                        f"[TRADE] Skip {token_key} Phase A: |delta_pct| {abs(delta_pct):.6f} < {btc_momentum_min}"
                    )
                    return

                # ⑥ Direction alignment filter: only trade with BTC trend
                if signal_side == 'buy' and delta_pct < 0:
                    self.log.debug(f"[TRADE] Skip {token_key} Phase A BUY: BTC trending down (delta={delta_pct:.6f})")
                    return
                if signal_side == 'sell' and delta_pct > 0:
                    self.log.debug(f"[TRADE] Skip {token_key} Phase A SELL: BTC trending up (delta={delta_pct:.6f})")
                    return

                self._last_entry_attempt_ts[token_key] = now_ts
                self.log.info(
                    f"[TRADE] Phase A {signal_side.upper()} signal: {token_key} ev={ev:.4f} "
                    f"threshold=±{entry_threshold:.4f} mid={mid:.4f} delta={delta_pct:.6f}"
                )
                self.log.info(f"[TRADE] Attempting {token_key} {signal_side} @ {mid:.4f}")
                result = self._enter_position(token_key, signal_side, mid, self.config.per_trade_usd / mid, phase)
                if result:
                    self.log.info(f"[TRADE] Entry result: {result}")
                else:
                    self.log.warning(
                        f"[TRADE] Entry result: False reason={getattr(self, '_last_entry_reject_reason', 'unknown')}"
                    )
            else:
                self.log.debug(
                    f"[TRADE] Phase A: state={state} ev={ev:.4f} entry={entry_threshold:.4f} exit={exit_threshold:.4f}, no entry"
                )
        else:
            if pos['open'] and pos.get('phase') == 'A':
                self.log.info(f"[TRADE] Phase A timeout close: {token_key} (now in Phase B)")
                trigger = self._trigger_price_for_exit(pos, bid, ask, mid)
                if self._close_position(token_key, trigger, f"phase_a_timeout_{token_key}"):
                    self.log.info(f"[TRADE] Phase A position closed in Phase B: {token_key}")
                else:
                    self.log.warning(f"[TRADE] Phase A timeout close failed: {token_key}")
                return

            # Phase B: momentum continuation based on trend_score
            self.log.debug(f"[TRADE] Phase B: trend_score={trend_score:.6f} threshold={threshold_pct:.6f} target={phase_b_target}")
            if phase_b_target != 'none' and not self.tail_trade_done:
                trend_match = (
                    (token_key == 'up' and delta_pct > 0) or
                    (token_key == 'down' and delta_pct < 0)
                )
                if trend_match:
                    if pos.get('open') or pos.get('pending_open'):
                        return
                    if _has_other_open_or_pending(token_key):
                        self.log.debug(f"[TRADE] Skip {token_key} Phase B entry: other token has open/pending position")
                        return
                    self.log.info(
                        f"[TRADE] Phase B momentum lock: {token_key} "
                        f"| delta={delta_pct:.4f} | trend_score={trend_score:.6f}"
                    )
                    result = self._enter_position(token_key, 'buy', mid, self.config.per_trade_usd / mid, phase)
                    if result:
                        self.tail_trade_done = True
                        self.log.info("[TRADE] Phase B momentum entry success")

        # Push phase state periodically (every 3 seconds)
        if not hasattr(self, '_last_phase_push_ts') or now_ts - self._last_phase_push_ts >= 3.0:
            self._last_phase_push_ts = now_ts
            self._push_phase_state(
                phase, remaining,
                phase_a_start=phase_a_start,
                phase_a_end=phase_a_end,
                elapsed=elapsed
            )
    
    def check_rollover(self) -> None:
        """Check and handle market rollover."""
        new_slug = self._get_current_slug()
        if new_slug == self.current_market_slug:
            self._pending_rollover_slug = None
            return

        now_ts = self.clock.timestamp()
        if self._pending_rollover_slug != new_slug:
            self._pending_rollover_slug = new_slug
            self._last_rollover_block_log_ts = 0.0

        # Phase B: binary settlement before closing (state still valid here)
        self._settle_phase_b_positions_at_rollover()

        # Close remaining positions (must succeed before state reset)
        if not self._close_all_open_positions():
            if now_ts - self._last_rollover_block_log_ts >= 5.0:
                self._last_rollover_block_log_ts = now_ts
                self.log.warning(" Rollover blocked: still have open positions, will retry close on next timer")
            return

        self._pending_rollover_slug = None
        self.rounds_counter.inc()
        self.log.info(f" Rollover: {self.current_market_slug} -> {new_slug}")

        # Push rollover event only when rollover is actually executed
        self._push_rollover(self.current_market_slug or '', new_slug)
        
        # Reset state
        self.start_ts = self._calculate_round_start_ts()
        self.start_price = {'up': None, 'down': None}
        self.ev_ema = {'up': None, 'down': None}
        self._phase_a_signal_state = {'up': 'neutral', 'down': 'neutral'}
        self._last_signal_eval_ts = {'up': 0.0, 'down': 0.0}
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
        self._last_post_rollover_retry_ts = self._post_rollover_switch_ts
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
                self.log.info("[OK] Post-rollover market data resumed")
            elif (
                self._post_rollover_retry_count < self._post_rollover_retry_max
                and (now_ts - self._last_post_rollover_retry_ts) >= self._post_rollover_retry_interval_sec
            ):
                self._post_rollover_retry_count += 1
                self._last_post_rollover_retry_ts = now_ts
                self.log.warning(
                    f"[RETRY] Post-rollover subscribe retry "
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
                f"[WARN] No quote tick for {now_ts - self.last_quote_tick_ts:.0f}s - "
                f"forcing resubscribe (attempt {self._resubscribe_attempts}/3)"
            )
            self._force_resubscribe()
            return
        
        # Check rollover
        self.check_rollover()
        
        # Periodic maintenance
        self._check_flip_stats_refresh()
        self._update_metrics()
