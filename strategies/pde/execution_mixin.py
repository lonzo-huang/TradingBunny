"""Trade execution mixin: order management, position tracking, PnL."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from nautilus_trader.model.enums import OrderSide


class PDEExecutionMixin:
    """Handles order execution, position management, and PnL tracking."""
    
    # Required from base
    config: Any
    cache: Any
    clock: Any
    log: Any
    positions: dict
    round_pnl: float
    total_pnl: float
    cumulative_fees: float
    A_trades: int
    B_trades: int
    tail_trade_done: bool
    instrument: Any | None
    down_instrument: Any | None
    live_server: Any | None
    position_gauge: Any | None
    persistence_store: Any | None
    persistence_run_id: str

    def _event_to_dict(self, event: Any) -> dict:
        """Convert NautilusTrader event to serializable dict."""
        if isinstance(event, dict):
            return event
        result = {}
        for attr in dir(event):
            if attr.startswith('_'):
                continue
            try:
                val = getattr(event, attr)
                if callable(val):
                    continue
                # Convert NautilusTrader identifier types to string
                if hasattr(val, 'value'):
                    result[attr] = str(val.value)
                elif 'nautilus_trader.model.identifiers' in str(type(val)):
                    result[attr] = str(val)
                elif isinstance(val, (str, int, float, bool)):
                    result[attr] = val
                elif val is None:
                    result[attr] = None
                else:
                    result[attr] = str(val)
            except Exception:
                pass
        return result

    def _persist_order_event(self, event_type: str, event: Any) -> None:
        store = getattr(self, 'persistence_store', None)
        run_id = getattr(self, 'persistence_run_id', '')
        if not store or not run_id:
            self.log.warning(f"[PERSIST-WARN] Cannot persist order: store={store}, run_id={run_id}")
            return
        try:
            event_dict = self._event_to_dict(event)
            store.insert_order_event(run_id=run_id, event_type=event_type, event=event_dict)
            self.log.info(f"[PERSIST-OK] Order {event_type} persisted")
        except Exception as e:
            self.log.error(f"[PERSIST-FAIL] order event insert failed ({event_type}): {e}")

    def _persist_fill_event(self, event: Any) -> None:
        store = getattr(self, 'persistence_store', None)
        run_id = getattr(self, 'persistence_run_id', '')
        if not store or not run_id:
            self.log.warning(f"[PERSIST-WARN] Cannot persist fill: store={store}, run_id={run_id}")
            return
        try:
            event_dict = self._event_to_dict(event)
            store.insert_fill_event(run_id=run_id, event=event_dict)
            self.log.info(f"[PERSIST-OK] Fill persisted")
        except Exception as e:
            self.log.error(f"[PERSIST-FAIL] fill event insert failed: {e}")

    def _persist_position_event(
        self,
        event_type: str,
        token: str,
        phase: str,
        event: Any,
        position_size: float,
        avg_price: float,
        unrealized_pnl: float,
        realized_pnl: float,
    ) -> None:
        store = getattr(self, 'persistence_store', None)
        run_id = getattr(self, 'persistence_run_id', '')
        if not store or not run_id:
            self.log.warning(f"[PERSIST-WARN] Cannot persist position: store={store}, run_id={run_id}")
            return
        try:
            event_dict = self._event_to_dict(event)
            store.insert_position_event(
                run_id=run_id,
                event_type=event_type,
                token=token,
                phase=phase,
                event=event_dict,
                position_size=position_size,
                avg_price=avg_price,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
            )
            self.log.info(f"[PERSIST-OK] Position {event_type} persisted")
        except Exception as e:
            self.log.error(f"[PERSIST-FAIL] position event insert failed ({event_type}): {e}")

    def _persist_pnl_snapshot(
        self,
        event_type: str,
        token: str,
        phase: str,
        realized: float,
        unrealized: float,
    ) -> None:
        store = getattr(self, 'persistence_store', None)
        run_id = getattr(self, 'persistence_run_id', '')
        if not store or not run_id:
            return
        try:
            store.insert_pnl_snapshot(
                run_id=run_id,
                event_type=event_type,
                token=token,
                phase=phase,
                realized=realized,
                unrealized=unrealized,
                round_pnl=float(getattr(self, 'round_pnl', 0.0)),
                total_pnl=float(getattr(self, 'total_pnl', 0.0)),
            )
        except Exception as e:
            self.log.debug(f"[PERSIST] pnl snapshot insert failed ({event_type}): {e}")

    def _push_live_pnl_summary(self, phase: str, realized: float, unrealized: float) -> None:
        if not self.live_server:
            return

        phase_a_realized = realized if phase == 'A' else 0.0
        phase_b_realized = realized if phase == 'B' else 0.0
        phase_a_unrealized = unrealized if phase == 'A' else 0.0
        phase_b_unrealized = unrealized if phase == 'B' else 0.0

        self.live_server.push_pnl_summary(
            phase_a_realized=phase_a_realized,
            phase_b_realized=phase_b_realized,
            phase_a_unrealized=phase_a_unrealized,
            phase_b_unrealized=phase_b_unrealized,
            round_pnl=float(getattr(self, 'round_pnl', 0.0)),
            cumulative_a=float(getattr(self, 'total_pnl', 0.0)),
            cumulative_b=0.0,
        )

    def _reset_local_position(self, token_key: str) -> None:
        """Reset local token position state to flat."""
        pos = self.positions[token_key]
        pos['open'] = False
        pos['entry_price'] = 0.0
        pos['size'] = 0.0
        pos['side'] = None
        pos['phase'] = None
        pos['instrument_id'] = None
        pos['close_pending'] = False
        pos['close_requested_ts'] = 0.0
        pos['close_label'] = None
        pos['pending_open'] = False
        pos['pending_open_ts'] = 0.0

    def _has_engine_open_position(self, instrument_id: Any) -> bool:
        """Best-effort check for real open position in engine cache."""
        if not instrument_id:
            return False

        try:
            open_positions = self.cache.positions_open()
        except Exception:
            return True

        iid = str(instrument_id)
        for p in open_positions or []:
            try:
                if str(getattr(p, 'instrument_id', '')) != iid:
                    continue
                qty = float(getattr(p, 'quantity', 0.0) or 0.0)
                if qty > 0:
                    return True
            except Exception:
                if str(getattr(p, 'instrument_id', '')) == iid:
                    return True
        return False

    def on_order_accepted(self, event) -> None:
        self._persist_order_event('order_accepted', event)

    def on_order_rejected(self, event) -> None:
        self._persist_order_event('order_rejected', event)

    def on_order_canceled(self, event) -> None:
        self._persist_order_event('order_canceled', event)

    def on_order_filled(self, event) -> None:
        self._persist_order_event('order_filled', event)
        self._persist_fill_event(event)

    def on_account_state(self, event) -> None:
        store = getattr(self, 'persistence_store', None)
        run_id = getattr(self, 'persistence_run_id', '')
        if not store or not run_id:
            return
        try:
            store.insert_account_state(run_id=run_id, event=event)
        except Exception as e:
            self.log.debug(f"[PERSIST] account state insert failed: {e}")

    def on_account_state_changed(self, event) -> None:
        self.on_account_state(event)

    def _token_key_from_instrument_id(self, instrument_id: Any) -> str | None:
        """Resolve token key from instrument id using tracked position or current instruments."""
        iid = str(instrument_id)

        for token_key in ('up', 'down'):
            tracked = self.positions[token_key].get('instrument_id')
            if tracked and str(tracked) == iid:
                return token_key

        if self.instrument and str(self.instrument.id) == iid:
            return 'up'
        if self.down_instrument and str(self.down_instrument.id) == iid:
            return 'down'
        return None

    def _trigger_price_for_exit(self, pos: dict, bid: float, ask: float, fallback: float) -> float:
        """Choose realistic executable-side trigger price for exits.

        Long exits (sell) are triggered on bid; short exits (buy) on ask.
        """
        if bid > 0 and ask > 0:
            return bid if pos.get('side') == 'buy' else ask
        return fallback

    def _push_live_position_mark(self, token_key: str, mark_price: float) -> None:
        """Push mark-to-market position snapshot using mark (mid) price for display."""
        pos = self.positions[token_key]
        if not pos.get('open'):
            return

        entry = float(pos.get('entry_price', 0.0))
        size = float(pos.get('size', 0.0))
        if entry <= 0 or size <= 0:
            return

        if pos.get('side') == 'sell':
            unrealized = (entry - mark_price) * size
            pnl_pct = ((entry - mark_price) / entry) * 100.0
        else:
            unrealized = (mark_price - entry) * size
            pnl_pct = ((mark_price - entry) / entry) * 100.0

        if self.live_server:
            self.live_server.push_position(
                token=token_key,
                phase=pos.get('phase') or 'A',
                is_open=True,
                entry_price=entry,
                current_price=mark_price,
                unrealized_pnl=unrealized,
                pnl_pct=pnl_pct,
                quantity=size,
            )

    def on_position_opened(self, event) -> None:
        """Sync local state when position is opened/confirmed by engine."""
        token_key = self._token_key_from_instrument_id(event.instrument_id)
        if token_key is None:
            return

        pos = self.positions[token_key]
        pos['open'] = True
        pos['entry_price'] = float(event.avg_px_open)
        pos['size'] = float(event.quantity)
        pos['instrument_id'] = str(event.instrument_id)
        pos['close_pending'] = False
        pos['close_requested_ts'] = 0.0
        pos['close_label'] = None
        pos['pending_open'] = False
        pos['pending_open_ts'] = 0.0

        phase = pos.get('phase') or 'A'
        exposure = pos['entry_price'] * pos['size']
        self._persist_position_event(
            event_type='position_opened',
            token=token_key,
            phase=phase,
            event=event,
            position_size=pos['size'],
            avg_price=pos['entry_price'],
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )
        self._persist_pnl_snapshot(
            event_type='position_opened',
            token=token_key,
            phase=phase,
            realized=0.0,
            unrealized=0.0,
        )
        self._push_live_pnl_summary(phase=phase, realized=0.0, unrealized=0.0)
        try:
            self.position_gauge.labels(token=token_key).set(exposure)
        except Exception:
            pass

        if self.live_server:
            self.live_server.push_position(
                token=token_key,
                phase=phase,
                is_open=True,
                entry_price=pos['entry_price'],
                current_price=pos['entry_price'],
                quantity=pos['size'],
            )
            self.log.debug(
                f"[WS] push_position token={token_key} is_open=True phase={phase} qty={pos['size']:.6f} "
                f"entry={pos['entry_price']:.4f} current={pos['entry_price']:.4f}"
            )

    def on_position_changed(self, event) -> None:
        """Sync local size while position is partially closed/changed."""
        token_key = self._token_key_from_instrument_id(event.instrument_id)
        if token_key is None:
            return

        pos = self.positions[token_key]
        pos['size'] = float(event.quantity)
        phase = pos.get('phase') or 'A'
        unrealized = float(getattr(event, 'unrealized_pnl', 0.0) or 0.0)
        avg_px = float(getattr(event, 'avg_px_open', pos.get('entry_price', 0.0)) or 0.0)

        self._persist_position_event(
            event_type='position_changed',
            token=token_key,
            phase=phase,
            event=event,
            position_size=pos['size'],
            avg_price=avg_px,
            unrealized_pnl=unrealized,
            realized_pnl=0.0,
        )
        self._persist_pnl_snapshot(
            event_type='position_changed',
            token=token_key,
            phase=phase,
            realized=0.0,
            unrealized=unrealized,
        )
        self._push_live_pnl_summary(phase=phase, realized=0.0, unrealized=unrealized)

        try:
            self.position_gauge.labels(token=token_key).set(pos['entry_price'] * pos['size'])
        except Exception:
            pass

        if self.live_server:
            entry = pos.get('entry_price', 0.0)
            pnl_pct = ((avg_px - entry) / entry * 100.0) if entry > 0 else 0.0
            self.live_server.push_position(
                token=token_key,
                phase=phase,
                is_open=True,
                entry_price=entry,
                current_price=avg_px,
                unrealized_pnl=unrealized,
                pnl_pct=pnl_pct,
                quantity=pos['size'],
            )
            self.log.debug(
                f"[WS] push_position token={token_key} is_open=True phase={phase} "
                f"qty={pos['size']:.6f} entry={entry:.4f} current={avg_px:.4f} "
                f"unrealized={unrealized:.4f} pnl_pct={pnl_pct:.2f}"
            )

    def on_position_closed(self, event) -> None:
        """Mark local position closed only when engine confirms closure."""
        token_key = self._token_key_from_instrument_id(event.instrument_id)
        if token_key is None:
            self.log.warning(f"[WARN] PositionClosed for unknown instrument: {event.instrument_id}")
            return

        phase = self.positions[token_key].get('phase') or 'A'
        realized = float(event.realized_pnl)
        self.round_pnl += realized
        self.total_pnl += realized

        self._persist_position_event(
            event_type='position_closed',
            token=token_key,
            phase=phase,
            event=event,
            position_size=0.0,
            avg_price=float(getattr(event, 'avg_px_open', 0.0) or 0.0),
            unrealized_pnl=0.0,
            realized_pnl=realized,
        )
        self._persist_pnl_snapshot(
            event_type='position_closed',
            token=token_key,
            phase=phase,
            realized=realized,
            unrealized=0.0,
        )
        self._push_live_pnl_summary(phase=phase, realized=realized, unrealized=0.0)

        self._reset_local_position(token_key)

        try:
            self.position_gauge.labels(token=token_key).set(0.0)
        except Exception:
            pass

        if self.live_server:
            self.live_server.push_position(
                token=token_key,
                phase=phase,
                is_open=False,
                unrealized_pnl=0.0,
                realized_pnl=realized,
                quantity=0.0,
            )
            self.log.debug(
                f"[WS] push_position token={token_key} is_open=False phase={phase} qty=0.000000 "
                f"realized={realized:.4f}"
            )

        self.log.info(f"[OK] Close confirmed {token_key.upper()} realized_pnl={realized:.4f}")
    
    def _place_order(self, instrument: Any, side: OrderSide,
                     price: float, size: float, label: str = "") -> bool:
        """Place a market order via Strategy order_factory.

        Returns True on successful submit, False otherwise.
        """
        if instrument is None:
            self._last_entry_reject_reason = "instrument_none"
            return False

        try:
            qty = instrument.make_qty(Decimal(str(size)))
            order = self.order_factory.market(
                instrument_id=instrument.id,
                order_side=side,
                quantity=qty,
                tags=[f"PDE_{label}"],
            )
            self.submit_order(order)
            # Debug persistence
            store = getattr(self, 'persistence_store', None)
            run_id = getattr(self, 'persistence_run_id', '')
            if not store or not run_id:
                self.log.warning(f"[PERSIST-DEBUG] Cannot persist order: store={store}, run_id={run_id}")
            self._persist_order_event('order_submitted', {
                'client_order_id': getattr(order, 'client_order_id', ''),
                'venue_order_id': getattr(order, 'venue_order_id', ''),
                'instrument_id': str(instrument.id),
                'order_side': side.name,
                'quantity': size,
                'price': price,
                'status': 'SUBMITTED',
                'label': label,
                'ts_event': int(self.clock.timestamp() * 1_000_000_000),
            })
            self.log.info(f"[ORDER] {side.name} {instrument.id} qty={size:.6f} ref_px={price:.4f} (label={label})")
            return True
        except Exception as e:
            self._last_entry_reject_reason = f"submit_error:{e}"
            self.log.error(f"[ERROR] Order submit failed ({label}): {e}")
            return False
    
    def _close_position(self, token_key: str, current_price: float, label: str) -> bool:
        """Request close for one token position and mark it as pending.

        Returns True if close request is accepted/pending, False on request failure.
        """
        pos = self.positions[token_key]
        if not pos['open']:
            return True

        now_ts = self.clock.timestamp()
        retry_interval = max(0.1, float(getattr(self.config, 'close_retry_interval_sec', 3.0)))
        if pos.get('close_pending') and (now_ts - pos.get('close_requested_ts', 0.0)) < retry_interval:
            return True

        inst = self.instrument if token_key == 'up' else self.down_instrument
        if inst is None:
            self.log.warning(f"[BLOCK] Cannot close {token_key}: instrument unavailable")
            return False

        side = OrderSide.SELL if pos['side'] == 'buy' else OrderSide.BUY
        if not self._place_order(inst, side, current_price, pos['size'], label):
            self.log.warning(f"[FAIL] Close failed for {token_key} label={label}")
            return False

        pos['close_pending'] = True
        pos['close_requested_ts'] = now_ts
        pos['close_label'] = label
        
        # Persist close request immediately
        self._persist_position_event(
            event_type='position_close_requested',
            token=token_key,
            phase=pos.get('phase', 'A'),
            event={'price': current_price, 'label': label},
            position_size=pos.get('size', 0),
            avg_price=pos.get('entry_price', 0),
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )
        
        self.log.info(f"[CLOSE] Requested {token_key.upper()} @ {current_price:.4f} ({label})")
        return True

    def _close_all_open_positions(self) -> bool:
        """Close all open positions at market prices.

        Returns True only if all open positions were closed successfully.
        """
        all_closed = True
        for token_key in ('up', 'down'):
            pos = self.positions[token_key]
            if not pos['open']:
                continue

            inst = self.instrument if token_key == 'up' else self.down_instrument
            tracked_iid = pos.get('instrument_id') or (inst and str(inst.id))
            if tracked_iid and not self._has_engine_open_position(tracked_iid):
                self.log.warning(f"[CLEAR] Clearing stale local {token_key.upper()} position (not open in engine cache)")
                self._reset_local_position(token_key)
                try:
                    self.position_gauge.labels(token=token_key).set(0.0)
                except Exception:
                    pass
                if self.live_server:
                    self.live_server.push_position(
                        token=token_key,
                        phase='A',
                        is_open=False,
                        unrealized_pnl=0.0,
                        quantity=0.0,
                    )
                continue

            all_closed = False

            if inst is None:
                continue
            
            # Get current mid price
            quote = self.cache.quote_tick(inst.id)
            if quote is None:
                mid = pos['entry_price']
                self.log.warning(f"[WARN] No quote for {token_key} on rollover close, using entry_price={mid:.4f}")
            else:
                bid = float(quote.bid_price)
                ask = float(quote.ask_price)
                mid = (bid + ask) / 2
                trigger = self._trigger_price_for_exit(pos, bid, ask, mid)

            self._close_position(token_key, trigger if quote is not None else mid, f"close_{token_key}")
        
        self.log.info(f"[PNL] Round PnL: {self.round_pnl:.4f} | Total: {self.total_pnl:.4f}")
        return all_closed
    
    def _enter_position(self, token_key: str, side: str, price: float, 
                        size: float, phase: str) -> bool:
        """Enter a new position if risk limits allow."""
        now_ts = self.clock.timestamp()
        pos = self.positions[token_key]

        # Check existing position
        if pos['open']:
            self._last_entry_reject_reason = f"position_already_open:{token_key}"
            return False

        pending_cooldown = max(0.1, float(getattr(self.config, 'entry_retry_cooldown_sec', 2.0)))
        if pos.get('pending_open') and (now_ts - pos.get('pending_open_ts', 0.0)) < pending_cooldown:
            self._last_entry_reject_reason = f"entry_pending:{token_key}"
            return False
        
        # Check position limit
        total_exposure = sum(
            p['size'] * p['entry_price'] 
            for p in self.positions.values() if p['open']
        )
        new_exposure = size * price
        if total_exposure + new_exposure > self.config.max_position_usd:
            self._last_entry_reject_reason = (
                f"max_position_exceeded:{total_exposure + new_exposure:.2f}>{self.config.max_position_usd:.2f}"
            )
            self.log.warning(f"[LIMIT] Position limit exceeded: {total_exposure + new_exposure:.2f} > {self.config.max_position_usd}")
            return False
        
        inst = self.instrument if token_key == 'up' else self.down_instrument
        if inst is None:
            self._last_entry_reject_reason = f"instrument_unavailable:{token_key}"
            return False
        
        order_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL
        if not self._place_order(inst, order_side, price, size, f"enter_{token_key}_{phase}"):
            if not self._last_entry_reject_reason:
                self._last_entry_reject_reason = "place_order_failed"
            return False
        
        # Update position state - treat as immediately open for Sandbox
        self.positions[token_key].update({
            'open': True,
            'side': side,
            'entry_price': price,
            'size': size,
            'phase': phase,
            'instrument_id': str(inst.id),
            'close_pending': False,
            'close_requested_ts': 0.0,
            'close_label': None,
            'pending_open': False,
            'pending_open_ts': now_ts,
        })
        
        # Persist position opened event immediately (don't rely on callback)
        self._persist_position_event(
            event_type='position_opened',
            token=token_key,
            phase=phase,
            event={'price': price, 'size': size, 'side': side},
            position_size=size,
            avg_price=price,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )
        
        # Update trade counters
        if phase == 'A':
            self.A_trades += 1
        elif phase == 'B':
            self.B_trades += 1

        self._last_entry_reject_reason = ""
        
        self.log.info(f"[ENTER] Requested {token_key.upper()} {side} @ {price:.4f} (phase={phase})")
        return True
    
    def _maybe_exit_position(self, token_key: str, mark_price: float,
                             bid: float, ask: float, ev: float, phase: str) -> bool:
        """Evaluate exit conditions for open position."""
        pos = self.positions[token_key]
        if not pos['open']:
            return False

        self._push_live_position_mark(token_key, mark_price)

        trigger_price = self._trigger_price_for_exit(pos, bid, ask, mark_price)
        entry = float(pos.get('entry_price', 0.0))
        if entry <= 0:
            return False

        if pos.get('side') == 'sell':
            pnl_pct = (entry - trigger_price) / entry
        else:
            pnl_pct = (trigger_price - entry) / entry

        if pnl_pct >= self.config.take_profit_pct:
            if self._close_position(token_key, trigger_price, f"exit_tp_{token_key}"):
                if self.live_server:
                    self.live_server.push_trade(
                        phase=phase,
                        token=token_key,
                        side='sell' if pos.get('side') == 'buy' else 'buy',
                        price=trigger_price,
                        qty=float(pos.get('size', 0.0)),
                        reason=f"tp:{pnl_pct:+.2%}",
                    )
                self.log.info(
                    f"[PNL] TP requested {token_key.upper()} @ {trigger_price:.4f} "
                    f"(pnl={pnl_pct:+.2%}, phase={phase})"
                )
                return True
            return False

        if pnl_pct <= -self.config.stop_loss_pct:
            if self._close_position(token_key, trigger_price, f"exit_sl_{token_key}"):
                if self.live_server:
                    self.live_server.push_trade(
                        phase=phase,
                        token=token_key,
                        side='sell' if pos.get('side') == 'buy' else 'buy',
                        price=trigger_price,
                        qty=float(pos.get('size', 0.0)),
                        reason=f"sl:{pnl_pct:+.2%}",
                    )
                self.log.info(
                    f"[STOP] SL requested {token_key.upper()} @ {trigger_price:.4f} "
                    f"(pnl={pnl_pct:+.2%}, phase={phase})"
                )
                return True
            return False

        if pos.get('close_pending'):
            return False

        # For Phase B tail trades, keep TP/SL active but ignore EV-based stop exits.
        if phase == 'B' and pos.get('phase') == 'B':
            return False
        
        # Exit if EV turns negative significantly
        if ev < -0.01:  # -1% threshold
            if self._close_position(token_key, trigger_price, f"exit_ev_{token_key}"):
                self.log.info(f"💨 Exit requested {token_key.upper()} @ {trigger_price:.4f} (EV={ev:.4f})")
                return True
            return False
        
        return False
