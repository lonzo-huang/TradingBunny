"""Data streaming mixin: WebSocket push, tick processing, dashboard updates."""

from __future__ import annotations

from typing import Any
from nautilus_trader.model.data import QuoteTick, TradeTick
from nautilus_trader.model.enums import BookType


class PDEDataMixin:
    """Handles WebSocket streaming and tick processing."""
    
    # Required from base
    config: Any
    log: Any
    clock: Any
    live_server: Any | None
    btc_instrument_id: Any
    btc_price: float | None
    btc_start_price: float | None
    btc_anchor_price: float | None
    btc_last_tick_wall_ts: float
    btc_jump_ts: float
    btc_jump_direction: int
    btc_momentum_gauge: Any | None
    btc_delta_p_gauge: Any | None
    btc_price_history: Any | None
    poly_last_tick_wall_ts: float
    latency_gap_gauge: Any | None
    start_ts: float | None
    instrument: Any | None
    down_instrument: Any | None
    _post_rollover_subscribe_pending: bool
    _resubscribe_attempts: int
    last_quote_tick_ts: float
    _last_ws_push_ts: float
    _last_tick_log_ts: float = 0.0  # For throttling tick logs

    def _persist_market_tick(
        self,
        source: str,
        instrument_id: Any,
        bid: float | None = None,
        ask: float | None = None,
        last: float | None = None,
        mid: float | None = None,
        volume: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not getattr(self.config, 'persistence_enabled', False):
            return
        if not getattr(self.config, 'persistence_record_market_data', True):
            return
        store = getattr(self, 'persistence_store', None)
        run_id = getattr(self, 'persistence_run_id', '')
        if not store or not run_id:
            return

        try:
            event_ts_ns = int(self.clock.timestamp() * 1_000_000_000)
            store.insert_market_data(
                run_id=run_id,
                source=source,
                instrument_id=str(instrument_id),
                bid=bid,
                ask=ask,
                last=last,
                mid=mid,
                volume=volume,
                event_ts_ns=event_ts_ns,
                extra=extra,
            )
        except Exception as e:
            self.log.debug(f"[PERSIST] market tick insert failed: {e}")

    def on_quote_tick(self, tick: QuoteTick) -> None:
        """Process quote ticks from Binance BTC and Polymarket tokens."""
        token_str = str(tick.instrument_id)
        is_poly = "POLYMARKET" in token_str

        # Log Polymarket ticks at DEBUG level, throttled to every 5 seconds
        if is_poly:
            now_ts = self.clock.timestamp()
            if now_ts - self._last_tick_log_ts >= 5.0:
                bid = float(tick.bid_price) if tick.bid_price else 0
                ask = float(tick.ask_price) if tick.ask_price else 0
                self.log.debug(f"[TICK] Polymarket tick (5s sample): {token_str[:50]}... bid={bid:.4f} ask={ask:.4f}")
                self._last_tick_log_ts = now_ts

        # Handle BTC mid price mode
        if tick.instrument_id == self.btc_instrument_id and self.config.btc_price_source == "mid":
            self._process_btc_quote_tick(tick)
            return

        # Check if tick matches current market instruments
        is_active_up = bool(self.instrument and tick.instrument_id == self.instrument.id)
        is_active_down = bool(self.down_instrument and tick.instrument_id == self.down_instrument.id)
        
        if not is_active_up and not is_active_down:
            return
        
        # Post-rollover subscription success indicator
        if self._post_rollover_subscribe_pending:
            self._post_rollover_subscribe_pending = False
            self._post_rollover_retry_count = 0
            self.log.info("[OK] First tick received after rollover, subscription confirmed")
        
        # Process Polymarket tick
        self._process_polymarket_tick(tick, is_active_up)
    
    def _process_btc_quote_tick(self, tick: QuoteTick) -> None:
        """Process BTC quote tick for mid-price mode."""
        bid = float(tick.bid_price)
        ask = float(tick.ask_price)
        
        if bid > 0 and ask > 0:
            self.btc_price = (bid + ask) / 2.0
        elif ask > 0:
            self.btc_price = ask
        elif bid > 0:
            self.btc_price = bid
        else:
            return

        self._persist_market_tick(
            source='btc_quote',
            instrument_id=tick.instrument_id,
            bid=bid,
            ask=ask,
            mid=self.btc_price,
        )
        
        self._update_btc_metrics_and_push(bid, ask)
    
    def on_trade_tick(self, tick: TradeTick) -> None:
        """Process trade ticks from Binance BTC (trade price mode)."""
        if tick.instrument_id != self.btc_instrument_id:
            return
        
        self.btc_price = float(tick.price)
        self._persist_market_tick(
            source='btc_trade',
            instrument_id=tick.instrument_id,
            last=float(tick.price),
            volume=float(getattr(tick, 'size', 0.0) or 0.0),
            mid=self.btc_price,
        )
        self._update_btc_metrics_and_push(
            bid=float(tick.price) * 0.9995,
            ask=float(tick.price) * 1.0005
        )
    
    def _process_polymarket_tick(self, tick: QuoteTick, is_active_up: bool) -> None:
        """Process and push Polymarket token tick."""
        self.last_quote_tick_ts = self.clock.timestamp()
        self.poly_last_tick_wall_ts = self.last_quote_tick_ts
        self._resubscribe_attempts = 0
        
        token_type = "up" if is_active_up else "down"
        bid = float(tick.bid_price) if tick.bid_price else 0.0
        ask = float(tick.ask_price) if tick.ask_price else 0.0

        # Guard against zero prices
        if bid <= 0 and ask <= 0:
            self.log.debug(f"[_process_polymarket_tick] Skipping tick with zero prices: bid={bid}, ask={ask}")
            return

        mid = (bid + ask) / 2.0 if bid > 0 and ask > 0 else (bid if bid > 0 else ask)
        spread_pct = ((ask - bid) / ask * 100) if ask > 0 else 0

        self._persist_market_tick(
            source='poly_quote',
            instrument_id=tick.instrument_id,
            bid=bid,
            ask=ask,
            mid=mid,
            extra={'token_type': token_type, 'spread_pct': spread_pct},
        )
        
        # Throttle WebSocket pushes to ~100ms
        now_ts = self.clock.timestamp()
        if now_ts - self._last_ws_push_ts > 0.1:
            self._push_market_data(token_type, bid, ask, mid, spread_pct)
            self._last_ws_push_ts = now_ts
        
        # Continue with strategy logic
        if is_active_up:
            self._process_tick_for_strategy(tick, is_up=True)
        else:
            self._process_tick_for_strategy(tick, is_up=False)
    
    def _push_market_data(self, token: str, bid: float, ask: float, 
                          mid: float, spread_pct: float) -> None:
        """Push tick data to WebSocket dashboard."""
        if not hasattr(self, 'live_server') or self.live_server is None:
            return
        
        # Calculate latency gap
        gap_ms = 0.0
        if self.btc_last_tick_wall_ts > 0:
            gap_ms = (self.btc_last_tick_wall_ts - self.poly_last_tick_wall_ts) * 1000
            self.latency_gap_gauge.set(gap_ms)
        
        self.live_server.push_poly_tick(
            token=token, bid=bid, ask=ask, mid=mid, spread_pct=spread_pct,
            btc_price=self.btc_price or 0,
        )
        self.live_server.push_latency(
            gap_ms=gap_ms,
            btc_ts=self.btc_last_tick_wall_ts,
            poly_ts=self.poly_last_tick_wall_ts
        )
    
    def _update_btc_metrics_and_push(self, bid: float, ask: float) -> None:
        """Update BTC metrics and push to dashboard."""
        self.btc_last_tick_wall_ts = self.clock.timestamp()

        # Update gauges
        if hasattr(self, 'btc_price_gauge'):
            self.btc_price_gauge.set(self.btc_price)

        # 策略中途启动时（start_ts 已知但 btc_start_price 为 None）：用首个 BTC tick 做参考价
        # 这使得 delta_pct 从"0"开始追踪，避免 Phase B 永远无信号
        if self.btc_start_price is None and self.btc_price is not None:
            self.btc_start_price = self.btc_price
            self.log.info(
                f"[BTC] btc_start_price 初始化（中途启动）= {self.btc_start_price:.2f}，"
                f"delta 将从此价格起算"
            )

        # Initialize anchor
        if self.btc_anchor_price is None:
            self.btc_anchor_price = self.btc_price
        
        # Jump detection
        if self.btc_anchor_price and self.btc_anchor_price > 0:
            move_bps = (self.btc_price - self.btc_anchor_price) / self.btc_anchor_price * 10000
            if hasattr(self, 'btc_momentum_gauge'):
                self.btc_momentum_gauge.set(move_bps)
            
            if abs(move_bps) >= self.config.btc_jump_threshold_bps:
                self.btc_jump_ts = self.btc_last_tick_wall_ts
                self.btc_jump_direction = 1 if move_bps > 0 else -1
                self.btc_anchor_price = self.btc_price
                
                if hasattr(self, 'live_server') and self.live_server:
                    self.live_server.push_jump(
                        direction=self.btc_jump_direction,
                        move_bps=move_bps,
                        jump_ts=self.btc_jump_ts,
                        anchor_price=self.btc_anchor_price
                    )
                    self.log.info(f"[START] BTC Jump: {move_bps:.0f} bps")
        
        # Push BTC tick
        if hasattr(self, 'live_server') and self.live_server:
            delta_usd = self.btc_price - (self.btc_start_price or self.btc_price)
            move_bps = (self.btc_price - (self.btc_anchor_price or self.btc_price)) / max(self.btc_anchor_price, 1) * 10000
            
            self.live_server.push_btc_tick(
                price=self.btc_price,
                bid=bid,
                ask=ask,
                delta_usd=delta_usd,
                move_bps=move_bps
            )
    
    def _process_tick_for_strategy(self, tick: QuoteTick, is_up: bool) -> None:
        """Process tick for trading logic (implemented in signal/execution mixins)."""
        # This is a hook for subclasses/mixins to implement
        pass
    
    def _push_phase_state(
        self, phase: str, remaining: float,
        phase_a_start: float = 0.0,
        phase_a_end: float = 240.0,
        elapsed: float = 0.0
    ) -> None:
        """Push current phase state to dashboard."""
        if not hasattr(self, 'live_server') or self.live_server is None:
            return

        self.live_server.push_phase_state(
            phase=phase,
            remaining=remaining,
            a_trades=getattr(self, 'A_trades', 0),
            b_trades=getattr(self, 'B_trades', 0),
            tail_done=getattr(self, 'tail_trade_done', False),
            btc_round=self.current_market_slug or "",
            phase_a_start=phase_a_start,
            phase_a_end=phase_a_end,
            elapsed=elapsed
        )
    
    def _push_ev(self, token: str, phase: str, ev: float, **kwargs) -> None:
        """Push EV calculation to dashboard."""
        if not hasattr(self, 'live_server') or self.live_server is None:
            return
        
        self.live_server.push_ev(token=token, phase=phase, ev=ev, **kwargs)
    
    def _push_rollover(self, old_slug: str, new_slug: str) -> None:
        """Push rollover event to dashboard."""
        if not hasattr(self, 'live_server') or self.live_server is None:
            return
        
        self.live_server.push_rollover(
            old_slug=old_slug,
            new_slug=new_slug,
            rounds=getattr(self, 'rounds_counter', None) and self.rounds_counter._value.get() or 0
        )
        self.log.info(f"[SERVER] Pushed rollover event: {old_slug} -> {new_slug}")
