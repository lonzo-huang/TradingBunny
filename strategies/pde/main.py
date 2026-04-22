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
        self._order_map = {}  # 清除跨 round 孤儿订单记录

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
            # Phase A
            'ev_threshold_A': float,
            'ev_entry_hysteresis': float,
            'ev_deadband': float,
            'phase_a_start_sec': float,
            'phase_a_end_sec': float,
            'phase_a_min_btc_delta': float,
            'taker_fee_rate': float,
            'phase_a_min_token_price': float,
            'phase_a_max_token_price': float,
            # Phase B entry guards
            'phase_b_start_sec': float,
            'phase_b_momentum_threshold_usd': float,
            'phase_b_max_token_price': float,
            'phase_b_ev_filter_enabled': bool,
            'phase_b_min_ev': float,
            # Phase B exit guards
            'phase_b_early_exit_enabled': bool,
            'phase_b_early_exit_reserve_sec': float,
            'phase_b_stop_loss_pct': float,
            'phase_b_abs_stop_loss_enabled': bool,
            'phase_b_abs_stop_loss_price': float,
            # Phase B hedge guard
            'phase_b_hedge_enabled': bool,
            'phase_b_hedge_window_sec': float,
            'phase_b_hedge_delta_threshold_usd': float,
            'phase_b_hedge_size_pct': float,
            'phase_b_hedge_max_price': float,
            # General risk
            'take_profit_pct': float,
            'stop_loss_pct': float,
            'spread_tolerance': float,
            'max_A_trades': int,
            'per_trade_usd': float,
            'signal_eval_interval_sec': float,
            'entry_retry_cooldown_sec': float,
            'close_retry_interval_sec': float,
            # Flip stats
            'flip_stats_lookback_windows': int,
            'flip_stats_refresh_minutes': int,
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
            token_key, mid, sigma, delta_pct, remaining, in_phase_a, delta_btc_pct, elapsed
        )
        
        # Phase B: Trend-Reinforcement with time-weighted score
        # trend_score = |ΔP| × w(t), where w(t) ramps from 0 to 1 across the Phase B window
        phase_b_start = getattr(self.config, 'phase_b_start_sec', 240.0)
        in_phase_b = elapsed >= phase_b_start
        phase_b_end = self.config.market_interval_minutes * 60  # Phase B ends at round end

        # Time weight: linear from 0 (at phase_b_start) to 1 (at round end)
        if in_phase_b:
            time_weight = min(1.0, (elapsed - phase_b_start) / max(phase_b_end - phase_b_start, 1.0))
        else:
            time_weight = 0.0
        
        # Absolute deviation from BTC start price
        if self.btc_start_price and self.btc_start_price > 0:
            delta_p = self.btc_price - self.btc_start_price  # Can be positive or negative
            delta_p_pct = delta_p / self.btc_start_price
        else:
            delta_p = 0.0
            delta_p_pct = 0.0
        
        # Trend strength score: |ΔP| × w(t) — for logging/sizing only, NOT for entry gate
        trend_score = abs(delta_p_pct) * time_weight

        # Threshold check: direct USD comparison (no time_weight scaling)
        # time_weight was previously included here, making Phase B impossible to trigger
        # early in the window (time_weight≈0 → effective threshold ≈ ∞)
        threshold_usd = float(getattr(self.config, 'phase_b_momentum_threshold_usd', 30.0))
        btc_price_for_th = self.btc_price or self.btc_start_price
        if btc_price_for_th is None or btc_price_for_th <= 0:
            btc_price_for_th = 85000.0  # Reasonable default BTC price
        threshold_pct = threshold_usd / btc_price_for_th

        phase_b_target = 'up' if delta_p > 0 else 'down' if delta_p < 0 else 'flat'
        if abs(delta_p_pct) < threshold_pct:
            phase_b_target = 'none'

        if in_phase_b and (self.config.debug_raw_data or self.config.debug_ws):
            self.log.info(
                f"[PHASE_B_DEBUG] token={token_key} delta_usd={delta_p:+.1f} "
                f"th=${threshold_usd:.0f} time_weight={time_weight:.3f} "
                f"trend_score={trend_score:.6f} ev={ev:.4f} target={phase_b_target}"
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
            if self._maybe_exit_position(token_key, mid, bid, ask, ev, phase, remaining=remaining):
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

                # token 价格区间过滤：仅在流动性合理的中间区间交易
                pa_min_price = getattr(self.config, 'phase_a_min_token_price', 0.30)
                pa_max_price = getattr(self.config, 'phase_a_max_token_price', 0.70)
                if not (pa_min_price <= mid <= pa_max_price):
                    self.log.debug(
                        f"[SKIP] Phase A {token_key}: price={mid:.4f} 超出区间 "
                        f"[{pa_min_price:.2f}, {pa_max_price:.2f}]，跳过"
                    )
                    return

                # ④ BTC 动量过滤：BTC 方向不明时 EV 信号是噪声，不开仓
                btc_momentum_min = getattr(self.config, 'phase_a_min_btc_delta', 0.0003)
                if abs(delta_pct) < btc_momentum_min:
                    self.log.debug(
                        f"[SKIP] Phase A {token_key}: BTC delta={delta_pct:.5f} < min={btc_momentum_min:.5f}，无方向性"
                    )
                    return

                # ⑤ 顺势过滤：只做与 BTC 方向一致的 EV 信号，不逆势交易
                if signal_side == 'buy' and delta_pct < 0:
                    self.log.debug(
                        f"[SKIP] Phase A {token_key}: EV看多但BTC在跌 delta={delta_pct:.5f}，跳过逆势"
                    )
                    return
                if signal_side == 'sell' and delta_pct > 0:
                    self.log.debug(
                        f"[SKIP] Phase A {token_key}: EV看空但BTC在涨 delta={delta_pct:.5f}，跳过逆势"
                    )
                    return

                self._last_entry_attempt_ts[token_key] = now_ts
                self.log.info(
                    f"[TRADE] Phase A {signal_side.upper()} signal: {token_key} ev={ev:.4f} "
                    f"threshold=±{entry_threshold:.4f} btc_delta={delta_pct:+.5f}"
                )
                self.log.info(f"[TRADE] Attempting {token_key} {signal_side} @ {mid:.4f}")
                result = self._enter_position(
                    token_key, signal_side, mid, self.config.per_trade_usd / mid, phase,
                    ev=ev, delta_pct=delta_pct, btc_price=self.btc_price or 0.0,
                )
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

        if in_phase_b:
            # Phase B: momentum continuation based on trend_score
            # Completely independent from Phase A — no shared state, no conflict checks
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

                    # ── Guard 1: token 价格过于极端（≥ max_token_price）──
                    phase_b_max_price = float(getattr(self.config, 'phase_b_max_token_price', 0.75))
                    if mid >= phase_b_max_price:
                        self.log.info(
                            f"[SKIP] Phase B {token_key}: price={mid:.4f} ≥ max={phase_b_max_price:.4f}"
                        )
                        return

                    # ── Guard 2: EV 过滤（可关闭）──
                    if getattr(self.config, 'phase_b_ev_filter_enabled', True):
                        min_ev = float(getattr(self.config, 'phase_b_min_ev', -0.05))
                        if ev < min_ev:
                            self.log.info(
                                f"[SKIP] Phase B {token_key}: ev={ev:.4f} < min_ev={min_ev:.4f}，EV不足跳过"
                            )
                            return

                    self.log.info(
                        f"[TRADE] Phase B momentum lock: {token_key} "
                        f"| delta={delta_pct:.4f} | trend_score={trend_score:.6f}"
                        f" | ev={ev:.4f} | price={mid:.4f}"
                    )
                    result = self._enter_position(
                        token_key, 'buy', mid, self.config.per_trade_usd / mid, phase,
                        ev=ev, delta_pct=delta_pct, btc_price=self.btc_price or 0.0,
                    )
                    if result:
                        self.tail_trade_done = True
                        self.log.info("[TRADE] Phase B momentum entry success")

        # Phase B Hedge Guard check (runs every signal eval tick when in Phase B)
        if in_phase_b:
            delta_usd_abs = delta_p  # already computed above
            self._check_phase_b_hedge(token_key, elapsed, remaining, delta_usd_abs)

        # Push phase state periodically (every 3 seconds)
        if not hasattr(self, '_last_phase_push_ts') or now_ts - self._last_phase_push_ts >= 3.0:
            self._last_phase_push_ts = now_ts
            self._push_phase_state(
                phase, remaining,
                phase_a_start=phase_a_start,
                phase_a_end=phase_a_end,
                elapsed=elapsed
            )

    def _check_phase_b_hedge(
        self,
        token_key: str,
        elapsed: float,
        remaining: float,
        delta_usd: float,
    ) -> None:
        """Phase B Hedge Guard: open a small counter-position when momentum reverses.

        Fires once per round per Phase B position when all conditions are met:
        - phase_b_hedge_enabled is True
        - A Phase B position is open on token_key
        - We are in the final phase_b_hedge_window_sec seconds of the round
        - |delta_usd| has fallen below phase_b_hedge_delta_threshold_usd
        """
        if not getattr(self.config, 'phase_b_hedge_enabled', False):
            return

        pos = self.positions.get(token_key, {})
        if not pos.get('open') or pos.get('phase') != 'B':
            return

        if self._phase_b_hedge_done.get(token_key, False):
            return

        hedge_window = float(getattr(self.config, 'phase_b_hedge_window_sec', 60.0))
        if remaining > hedge_window:
            return

        hedge_threshold = float(getattr(self.config, 'phase_b_hedge_delta_threshold_usd', 10.0))
        pos_side = pos.get('side')

        # Trigger when BTC momentum has weakened (delta now inside ±threshold zone)
        if pos_side == 'buy':
            should_hedge = delta_usd < hedge_threshold
        else:
            should_hedge = delta_usd > -hedge_threshold

        if not should_hedge:
            return

        # Mark done immediately to prevent re-entry on subsequent ticks
        self._phase_b_hedge_done[token_key] = True

        opposite_key = 'down' if token_key == 'up' else 'up'
        opp_pos = self.positions.get(opposite_key, {})
        if opp_pos.get('open') or opp_pos.get('pending_open'):
            self.log.info(
                f"[HEDGE] Skip hedge {token_key}→{opposite_key}: "
                f"opposite already occupied"
            )
            return

        opposite_instrument = self.down_instrument if opposite_key == 'down' else self.instrument
        if opposite_instrument is None:
            self.log.warning(f"[HEDGE] No instrument for {opposite_key}, cannot hedge")
            return

        try:
            opp_quote = self.cache.quote_tick(opposite_instrument.id)
            if opp_quote is None:
                self.log.warning(f"[HEDGE] No quote for {opposite_key}, cannot hedge")
                return
            opp_bid = float(opp_quote.bid_price)
            opp_ask = float(opp_quote.ask_price)
            opp_mid = (opp_bid + opp_ask) / 2.0
        except Exception as exc:
            self.log.warning(f"[HEDGE] Quote fetch failed for {opposite_key}: {exc}")
            return

        if opp_mid <= 0:
            return

        pos_notional = float(pos.get('entry_price', 0.0)) * float(pos.get('size', 0.0))
        hedge_pct = float(getattr(self.config, 'phase_b_hedge_size_pct', 0.01))
        hedge_usd = pos_notional * hedge_pct
        hedge_size = hedge_usd / opp_mid

        self.log.info(
            f"[HEDGE] Phase B Hedge Guard: {token_key}({pos_side})→hedge {opposite_key} "
            f"delta_usd={delta_usd:+.2f} remaining={remaining:.1f}s "
            f"pos_notional={pos_notional:.2f} hedge_usd={hedge_usd:.2f} "
            f"hedge_pct={hedge_pct*100:.1f}% price={opp_mid:.4f}"
        )

        result = self._enter_position(
            opposite_key, 'buy', opp_mid, hedge_size, 'B_HEDGE',
            ev=0.0,
            delta_pct=delta_usd / max(self.btc_price or 85000.0, 1.0),
            btc_price=self.btc_price or 0.0,
        )
        if result:
            self.log.info(f"[HEDGE] Hedge entry submitted: {opposite_key} @ {opp_mid:.4f}")
        else:
            self.log.warning(f"[HEDGE] Hedge entry failed for {opposite_key}")

    def check_rollover(self) -> None:
        """Check and handle market rollover.

        Per real Polymarket rules: positions are force-closed at round end.
        We attempt orderly close first, but proceed with rollover regardless.
        """
        new_slug = self._get_current_slug()
        if new_slug == self.current_market_slug:
            self._pending_rollover_slug = None
            return

        now_ts = self.clock.timestamp()
        if self._pending_rollover_slug != new_slug:
            self._pending_rollover_slug = new_slug
            self._last_rollover_block_log_ts = 0.0

        # Phase B: settle with binary resolution PnL before any state reset
        self._settle_phase_b_positions_at_rollover()

        # Attempt to close remaining (Phase A) positions
        close_attempted = self._close_all_open_positions()
        if not close_attempted:
            # Log warning but don't block rollover - real Polymarket force-closes at expiry
            if now_ts - self._last_rollover_block_log_ts >= 5.0:
                self._last_rollover_block_log_ts = now_ts
                self.log.warning("[ROLLOVER] Position close failed, proceeding with force-close semantics per Polymarket rules")

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
        self._order_map = {}  # 清除飞行中订单记录，避免跨 round 误判
        self._phase_b_hedge_done = {'up': False, 'down': False}

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

        # Force-close Phase A positions when approaching round end (< 5 seconds remaining)
        # Phase B positions are intentionally held to rollover (no TP/SL), closed by check_rollover
        if seconds_to_roll < 5.0:
            phase_a_positions = [
                k for k in ('up', 'down')
                if self.positions[k].get('open') and self.positions[k].get('phase') == 'A'
            ]
            if phase_a_positions:
                self.log.info(f"[FORCE_CLOSE] Round ending in {seconds_to_roll:.1f}s, force-closing Phase A positions: {phase_a_positions}")
                for token_key in phase_a_positions:
                    pos = self.positions[token_key]
                    inst = self.instrument if token_key == 'up' else self.down_instrument
                    if inst:
                        quote = self.cache.quote_tick(inst.id)
                        if quote:
                            bid = float(quote.bid_price)
                            ask = float(quote.ask_price)
                            mid = (bid + ask) / 2
                            trigger = self._trigger_price_for_exit(pos, bid, ask, mid)
                            self._close_position(token_key, trigger, f"force_close_phase_a_{token_key}")

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
        self._check_hot_config(now_ts)

    # ── Hot-reload ──────────────────────────────────────────────────────────

    # Parameters that can be safely updated at runtime without restart.
    # Structural params (instrument slugs, db paths, venue names) are excluded.
    _HOT_RELOAD_PARAMS: frozenset = frozenset({
        # Phase A
        "ev_threshold_A", "ev_entry_hysteresis", "ev_ema_alpha", "ev_deadband", "ev_alpha",
        "phase_a_start_sec", "phase_a_end_sec",
        "phase_a_min_token_price", "phase_a_max_token_price", "phase_a_min_btc_delta",
        "max_A_trades",
        # Phase B entry guards
        "phase_b_start_sec", "phase_b_momentum_threshold_usd", "phase_b_max_token_price",
        "phase_b_ev_filter_enabled", "phase_b_min_ev",
        # Phase B exit guards
        "phase_b_early_exit_enabled", "phase_b_early_exit_reserve_sec",
        "phase_b_stop_loss_pct", "phase_b_abs_stop_loss_enabled", "phase_b_abs_stop_loss_price",
        # Phase B hedge guard
        "phase_b_hedge_enabled", "phase_b_hedge_window_sec",
        "phase_b_hedge_delta_threshold_usd", "phase_b_hedge_size_pct", "phase_b_hedge_max_price",
        # Risk / execution
        "take_profit_pct", "stop_loss_pct",
        "taker_fee_rate", "spread_tolerance",
        "signal_eval_interval_sec", "close_retry_interval_sec",
        "entry_retry_cooldown_sec",
        # BTC
        "btc_jump_threshold_bps",
        # Trade size
        "per_trade_usd",
        # Flip stats
        "flip_stats_lookback_windows", "flip_stats_refresh_minutes",
        # Debug
        "debug_raw_data", "debug_ws",
        # Hot-reload interval itself
        "hot_config_check_interval_sec",
    })

    def _check_hot_config(self, now_ts: float) -> None:
        """Reload runtime config from JSON file if it has been modified."""
        interval = float(getattr(self.config, 'hot_config_check_interval_sec', 5.0))
        if now_ts - self._last_hot_config_check_ts < interval:
            return
        self._last_hot_config_check_ts = now_ts

        path = getattr(self.config, 'hot_config_path', '')
        if not path:
            return

        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return

        if mtime <= self._hot_config_mtime:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                new_values: dict = json.load(f)
        except Exception as exc:
            self.log.warning(f"[HOT-CONFIG] Failed to parse {path}: {exc}")
            return

        self._hot_config_mtime = mtime
        changed: list[str] = []

        for key, new_val in new_values.items():
            if key.startswith('_'):  # ignore comment/metadata fields
                continue
            if key not in self._HOT_RELOAD_PARAMS:
                self.log.warning(f"[HOT-CONFIG] Skipping unsafe/unknown param: {key!r}")
                continue
            old_val = getattr(self.config, key, None)
            if old_val == new_val:
                continue
            try:
                # Cast to original type to avoid type drift
                if isinstance(old_val, bool):
                    new_val = bool(new_val)
                elif isinstance(old_val, int):
                    new_val = int(new_val)
                elif isinstance(old_val, float):
                    new_val = float(new_val)
                object.__setattr__(self.config, key, new_val)
                changed.append(f"{key}: {old_val!r} → {new_val!r}")
            except Exception as exc:
                self.log.warning(f"[HOT-CONFIG] Failed to update {key!r}: {exc}")

        if changed:
            self.log.info(
                f"[HOT-CONFIG] Reloaded {len(changed)} param(s) from {path}:\n"
                + "\n".join(f"  {c}" for c in changed)
            )
