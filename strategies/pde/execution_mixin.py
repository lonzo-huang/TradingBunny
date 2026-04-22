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

        def _convert_value(val: Any) -> Any:
            """Recursively convert a single value to serializable format."""
            if val is None:
                return None
            if isinstance(val, (str, int, float, bool)):
                return val
            if isinstance(val, (list, tuple)):
                return [_convert_value(v) for v in val]
            if isinstance(val, dict):
                return {k: _convert_value(v) for k, v in val.items()}
            # Convert NautilusTrader identifier types to string
            if hasattr(val, 'value'):
                return str(val.value)
            if 'nautilus_trader.model.identifiers' in str(type(val)):
                return str(val)
            # Catch-all: convert to string
            return str(val)

        if isinstance(event, dict):
            # Recursively process dict values
            return {k: _convert_value(v) for k, v in event.items()}

        result = {}
        for attr in dir(event):
            if attr.startswith('_'):
                continue
            try:
                val = getattr(event, attr)
                if callable(val):
                    continue
                result[attr] = _convert_value(val)
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
        round_slug: str = "",
        entry_context: dict | None = None,
        fee: float = 0.0,
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
                round_slug=round_slug,
                entry_context=entry_context,
                fee=fee,
            )
            self.log.info(f"[PERSIST-OK] Position {event_type} persisted")
        except Exception as e:
            self.log.error(f"[PERSIST-FAIL] position event insert failed ({event_type}): {e}")

    def _calc_taker_fee(self, size: float, price: float) -> float:
        """Polymarket taker fee: rate × notional (shares × price = USDC value)."""
        rate = float(getattr(self.config, 'taker_fee_rate', 0.0072))
        notional = size * price
        return round(notional * rate, 8) if notional > 0 else 0.0

    def _persist_pnl_snapshot(
        self,
        event_type: str,
        token: str,
        phase: str,
        realized: float,
        unrealized: float,
        fee: float = 0.0,
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
                fee=fee,
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

        # 用 _order_map 定位这笔订单属于哪个 token / 哪种操作，并做相应清理
        rejected_id = str(getattr(event, 'client_order_id', ''))
        order_info = self._order_map.pop(rejected_id, None)
        if not order_info:
            return

        token_key = order_info.get('token_key')
        if not token_key or token_key not in self.positions:
            return

        pos = self.positions[token_key]

        if order_info.get('type') == 'entry':
            # 入场单被拒 → 清除乐观设置的本地持仓，回滚计数器
            if pos.get('open') and pos.get('entry_order_id') == rejected_id:
                phase = pos.get('phase') or order_info.get('phase', 'A')
                self.log.warning(
                    f"[CLEAR] 入场单被拒绝 (id={rejected_id})，清除本地 {token_key.upper()} 仓位"
                )
                # 回滚交易计数
                if phase == 'A' and self.A_trades > 0:
                    self.A_trades -= 1
                elif phase == 'B':
                    if self.B_trades > 0:
                        self.B_trades -= 1
                    # Phase B 仅尝试一次，失败后允许重试（重置标志）
                    self.tail_trade_done = False
                elif phase == 'B_HEDGE':
                    # Hedge order rejected: allow retry by resetting hedge-done flag
                    hedge_done = getattr(self, '_phase_b_hedge_done', {})
                    hedge_done[token_key] = False
                # 重置仓位
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
                        quantity=0.0,
                    )

        elif order_info.get('type') == 'close':
            # 平仓单被拒 → 清除 close_pending，允许下一 tick 再次尝试
            self.log.warning(
                f"[WARN] 平仓单被拒绝 (id={rejected_id})，重置 {token_key.upper()} close_pending"
            )
            pos['close_pending'] = False
            pos['close_requested_ts'] = 0.0

    def on_order_canceled(self, event) -> None:
        self._persist_order_event('order_canceled', event)
        canceled_id = str(getattr(event, 'client_order_id', ''))
        self._order_map.pop(canceled_id, None)

    def on_order_filled(self, event) -> None:
        self._persist_order_event('order_filled', event)
        self._persist_fill_event(event)
        # 成交后从跟踪 map 移除，避免内存持续增长
        filled_id = str(getattr(event, 'client_order_id', ''))
        self._order_map.pop(filled_id, None)

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
        round_slug = getattr(self, 'current_market_slug', '') or ''

        # 计算入场 taker fee 并从 PnL 中扣除
        entry_fee = self._calc_taker_fee(pos['size'], pos['entry_price'])
        pos['entry_fee'] = entry_fee
        self.round_pnl -= entry_fee
        self.total_pnl -= entry_fee
        self.cumulative_fees += entry_fee

        self._persist_position_event(
            event_type='position_opened',
            token=token_key,
            phase=phase,
            event=event,
            position_size=pos['size'],
            avg_price=pos['entry_price'],
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            round_slug=round_slug,
            fee=entry_fee,
        )
        self._persist_pnl_snapshot(
            event_type='position_opened',
            token=token_key,
            phase=phase,
            realized=0.0,
            unrealized=0.0,
            fee=entry_fee,
        )
        self._push_live_pnl_summary(phase=phase, realized=0.0, unrealized=0.0)
        if entry_fee > 0:
            self.log.info(f"[FEE] Entry fee {token_key.upper()} {entry_fee:.4f} USDC (size={pos['size']:.2f} price={pos['entry_price']:.4f})")
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
        round_slug = getattr(self, 'current_market_slug', '') or ''

        self._persist_position_event(
            event_type='position_changed',
            token=token_key,
            phase=phase,
            event=event,
            position_size=pos['size'],
            avg_price=avg_px,
            unrealized_pnl=unrealized,
            realized_pnl=0.0,
            round_slug=round_slug,
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

        pos = self.positions[token_key]
        phase = pos.get('phase') or 'A'
        gross_realized = float(event.realized_pnl)
        round_slug = getattr(self, 'current_market_slug', '') or ''

        # 计算出场 taker fee（基于实际出场均价）
        exit_price = float(getattr(event, 'avg_px_close', 0.0) or 0.0)
        exit_size = float(pos.get('size', 0.0)) or float(getattr(event, 'quantity', 0.0) or 0.0)
        exit_fee = self._calc_taker_fee(exit_size, exit_price) if exit_price > 0 else 0.0
        entry_fee = float(pos.get('entry_fee', 0.0))
        total_fee = entry_fee + exit_fee

        net_realized = gross_realized - exit_fee
        self.round_pnl += net_realized
        self.total_pnl += net_realized
        self.cumulative_fees += exit_fee

        if exit_fee > 0:
            self.log.info(f"[FEE] Exit fee {token_key.upper()} {exit_fee:.4f} USDC | gross={gross_realized:.4f} net={net_realized:.4f}")

        self._persist_position_event(
            event_type='position_closed',
            token=token_key,
            phase=phase,
            event=event,
            position_size=0.0,
            avg_price=float(getattr(event, 'avg_px_open', 0.0) or 0.0),
            unrealized_pnl=0.0,
            realized_pnl=net_realized,
            round_slug=round_slug,
            fee=total_fee,
        )
        self._persist_pnl_snapshot(
            event_type='position_closed',
            token=token_key,
            phase=phase,
            realized=net_realized,
            unrealized=0.0,
            fee=total_fee,
        )
        self._push_live_pnl_summary(phase=phase, realized=net_realized, unrealized=0.0)

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
                realized_pnl=net_realized,
                quantity=0.0,
            )
            self.log.debug(
                f"[WS] push_position token={token_key} is_open=False phase={phase} qty=0.000000 "
                f"net_realized={net_realized:.4f}"
            )

        self.log.info(f"[OK] Close confirmed {token_key.upper()} gross={gross_realized:.4f} fee={total_fee:.6f} net={net_realized:.4f}")
    
    def _place_order(self, instrument: Any, side: OrderSide,
                     price: float, size: float, label: str = "") -> tuple[bool, str]:
        """Place a market order via Strategy order_factory.

        Returns (success, client_order_id_str).
        client_order_id_str is empty string on failure.
        """
        if instrument is None:
            self._last_entry_reject_reason = "instrument_none"
            return False, ""

        try:
            qty = instrument.make_qty(Decimal(str(size)))
            order = self.order_factory.market(
                instrument_id=instrument.id,
                order_side=side,
                quantity=qty,
                tags=[f"PDE_{label}"],
            )
            self.submit_order(order)
            order_id = str(getattr(order, 'client_order_id', ''))
            # Debug persistence
            store = getattr(self, 'persistence_store', None)
            run_id = getattr(self, 'persistence_run_id', '')
            if not store or not run_id:
                self.log.warning(f"[PERSIST-DEBUG] Cannot persist order: store={store}, run_id={run_id}")
            self._persist_order_event('order_submitted', {
                'client_order_id': order_id,
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
            return True, order_id
        except Exception as e:
            self._last_entry_reject_reason = f"submit_error:{e}"
            self.log.error(f"[ERROR] Order submit failed ({label}): {e}")
            return False, ""
    
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
        ok, order_id = self._place_order(inst, side, current_price, pos['size'], label)
        if not ok:
            self.log.warning(f"[FAIL] Close failed for {token_key} label={label}")
            return False

        # Track close order so on_order_rejected can clear close_pending correctly
        if order_id:
            self._order_map[order_id] = {'type': 'close', 'token_key': token_key}

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

    def _settle_phase_b_positions_at_rollover(self) -> None:
        """Settle open Phase B positions at round end using binary token resolution PnL.

        Polymarket binary tokens resolve to $1.00 (correct direction) or $0.00 (wrong
        direction). Settlement is determined by whether BTC is above/below the round
        start price, not by market order fill — which is unreliable at rollover time.

        Must be called BEFORE positions dict is reset (i.e., before check_rollover resets state).
        """
        btc_now = float(self.btc_price or 0.0)
        btc_start = float(self.btc_start_price or btc_now)
        btc_went_up = btc_now >= btc_start

        for token_key in ('up', 'down'):
            pos = self.positions[token_key]
            if not pos.get('open') or pos.get('phase') not in ('B', 'B_HEDGE'):
                continue

            entry_price = float(pos.get('entry_price', 0.0))
            size = float(pos.get('size', 0.0))
            if size <= 0 or entry_price <= 0:
                continue

            # UP token wins when BTC ends UP; DOWN token wins when BTC ends DOWN
            wins = btc_went_up if token_key == 'up' else not btc_went_up
            resolution_price = 1.0 if wins else 0.0
            realized_pnl = (resolution_price - entry_price) * size

            self.round_pnl += realized_pnl
            self.total_pnl += realized_pnl

            round_slug = getattr(self, 'current_market_slug', '') or ''
            direction_str = "UP" if btc_went_up else "DOWN"
            outcome_str = "WIN" if wins else "LOSE"

            self.log.info(
                f"[PHASE_B_SETTLE] {token_key.upper()} {outcome_str} | "
                f"BTC {direction_str} ({btc_start:.2f}→{btc_now:.2f}) | "
                f"entry={entry_price:.4f} resolution={resolution_price:.1f} "
                f"size={size:.2f} pnl={realized_pnl:+.4f}"
            )

            # Phase B exit fee = 0，因为 resolution_price=1.0 或 0.0 时 p*(1-p)=0
            # 只记录入场时已扣除的 entry_fee
            entry_fee = float(pos.get('entry_fee', 0.0))

            pos_phase = pos.get('phase', 'B')  # 'B' or 'B_HEDGE'
            self._persist_position_event(
                event_type='position_closed',
                token=token_key,
                phase=pos_phase,
                event={
                    'settlement_type': 'phase_b_resolution',
                    'btc_went_up': btc_went_up,
                    'btc_start': btc_start,
                    'btc_end': btc_now,
                    'wins': wins,
                    'resolution_price': resolution_price,
                },
                position_size=0.0,
                avg_price=entry_price,
                unrealized_pnl=0.0,
                realized_pnl=realized_pnl,
                round_slug=round_slug,
                fee=entry_fee,
            )
            self._persist_pnl_snapshot(
                event_type='phase_b_settled',
                token=token_key,
                phase=pos_phase,
                realized=realized_pnl,
                unrealized=0.0,
                fee=entry_fee,
            )
            self._push_live_pnl_summary(phase='B', realized=realized_pnl, unrealized=0.0)

            try:
                self.position_gauge.labels(token=token_key).set(0.0)
            except Exception:
                pass

            if self.live_server:
                self.live_server.push_position(
                    token=token_key,
                    phase='B',
                    is_open=False,
                    unrealized_pnl=0.0,
                    realized_pnl=realized_pnl,
                    quantity=0.0,
                )

            self._reset_local_position(token_key)

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
                        size: float, phase: str,
                        ev: float = 0.0, delta_pct: float = 0.0,
                        btc_price: float = 0.0) -> bool:
        """Enter a new position if risk limits allow."""
        now_ts = self.clock.timestamp()

        # Extra guard: prevent duplicate entries within same tick
        last_entry = getattr(self, '_last_entry_ts', {})
        if last_entry.get(token_key) == now_ts:
            self.log.warning(f"[DUPLICATE] Entry for {token_key} already attempted this tick")
            return False
        last_entry[token_key] = now_ts
        self._last_entry_ts = last_entry
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
        ok, order_id = self._place_order(inst, order_side, price, size, f"enter_{token_key}_{phase}")
        if not ok:
            if not self._last_entry_reject_reason:
                self._last_entry_reject_reason = "place_order_failed"
            return False

        # Track entry order so on_order_rejected can clean up local state
        if order_id:
            self._order_map[order_id] = {'type': 'entry', 'token_key': token_key, 'phase': phase}

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
            'entry_order_id': order_id,
        })
        
        # Persist entry request with full decision context (not a duplicate of on_position_opened)
        round_slug = getattr(self, 'current_market_slug', '') or ''
        self._persist_position_event(
            event_type='position_requested',
            token=token_key,
            phase=phase,
            event={'price': price, 'size': size, 'side': side,
                   'label': f'enter_{token_key}_{phase}'},
            position_size=size,
            avg_price=price,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
            round_slug=round_slug,
            entry_context={
                'ev': round(ev, 6),
                'delta_pct': round(delta_pct, 6),
                'btc_price': round(btc_price, 2),
                'label': f'enter_{token_key}_{phase}',
                'round_slug': round_slug,
            },
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

        # Phase B / B_HEDGE: hold to binary resolution unless phase_b_sl_tp_enabled=True
        if pos.get('phase') in ('B', 'B_HEDGE'):
            if not getattr(self.config, 'phase_b_sl_tp_enabled', False):
                return False

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

        # EV-based exit: 方向相关
        # 多头（buy）：EV 变负说明资产不再被低估 → 退出
        # 空头（sell）：EV 变正说明资产不再被高估 → 退出
        side = pos.get('side')
        ev_exit = (side == 'buy' and ev < -0.01) or (side == 'sell' and ev > 0.01)
        if ev_exit:
            if self._close_position(token_key, trigger_price, f"exit_ev_{token_key}"):
                self.log.info(
                    f"[EXIT] EV反转退出 {token_key.upper()} side={side} ev={ev:.4f} "
                    f"@ {trigger_price:.4f}"
                )
                return True
            return False
        
        return False
