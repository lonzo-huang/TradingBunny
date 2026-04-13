"""Trade execution mixin: order management, position tracking, PnL."""

from __future__ import annotations

from typing import Any
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.objects import Price, Quantity


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
    
    def _place_order(self, instrument_id: InstrumentId, side: OrderSide, 
                     price: float, size: float, label: str = "") -> None:
        """Place a limit order with configured tolerance."""
        # Adjust price for slippage tolerance
        adjusted = price * (1 - self.config.max_slippage) if side == OrderSide.BUY else price * (1 + self.config.max_slippage)
        
        order = self.cache._order_factory.limit(
            instrument_id=instrument_id,
            side=side,
            quantity=Quantity.from_str(f"{size:.6f}"),
            price=Price.from_str(f"{adjusted:.6f}"),
            time_in_force=TimeInForce.GTC,
        )
        self.submit_order(order)
        self.log.info(f"📤 Order {side.name} @ {adjusted:.4f} (label={label})")
    
    def _close_all_open_positions(self) -> None:
        """Close all open positions at market prices."""
        for token_key in ('up', 'down'):
            pos = self.positions[token_key]
            if not pos['open']:
                continue
            
            inst = self.instrument if token_key == 'up' else self.down_instrument
            if inst is None:
                continue
            
            # Get current mid price
            quote = self.cache.quote_tick(inst.id)
            if quote is None:
                continue
            
            mid = (float(quote.bid_price) + float(quote.ask_price)) / 2
            
            # Place closing order
            side = OrderSide.SELL if pos['side'] == 'buy' else OrderSide.BUY
            self._place_order(inst.id, side, mid, pos['size'], f"close_{token_key}")
            
            # Update PnL
            entry = pos['entry_price']
            pnl = (mid - entry) * pos['size'] if pos['side'] == 'buy' else (entry - mid) * pos['size']
            self.round_pnl += pnl
            self.total_pnl += pnl
            
            # Mark as closed
            pos['open'] = False
            pos['entry_price'] = 0.0
            pos['size'] = 0.0
            pos['side'] = None
            pos['phase'] = None
        
        self.log.info(f"💰 Round PnL: {self.round_pnl:.4f} | Total: {self.total_pnl:.4f}")
    
    def _enter_position(self, token_key: str, side: str, price: float, 
                        size: float, phase: str) -> bool:
        """Enter a new position if risk limits allow."""
        # Check existing position
        if self.positions[token_key]['open']:
            return False
        
        # Check position limit
        total_exposure = sum(
            p['size'] * p['entry_price'] 
            for p in self.positions.values() if p['open']
        )
        new_exposure = size * price
        if total_exposure + new_exposure > self.config.max_position_usd:
            self.log.warning(f"⛔ Position limit exceeded: {total_exposure + new_exposure:.2f} > {self.config.max_position_usd}")
            return False
        
        inst = self.instrument if token_key == 'up' else self.down_instrument
        if inst is None:
            return False
        
        order_side = OrderSide.BUY if side == 'buy' else OrderSide.SELL
        self._place_order(inst.id, order_side, price, size, f"enter_{token_key}_{phase}")
        
        # Update position state
        self.positions[token_key].update({
            'open': True,
            'side': side,
            'entry_price': price,
            'size': size,
            'phase': phase,
        })
        
        # Update trade counters
        if phase == 'A':
            self.A_trades += 1
        elif phase == 'B':
            self.B_trades += 1
        
        self.log.info(f"🎯 Entered {token_key.upper()} {side} @ {price:.4f} (phase={phase})")
        return True
    
    def _maybe_exit_position(self, token_key: str, current_price: float, 
                             ev: float, phase: str) -> bool:
        """Evaluate exit conditions for open position."""
        pos = self.positions[token_key]
        if not pos['open']:
            return False
        
        # Exit if EV turns negative significantly
        if ev < -0.01:  # -1% threshold
            inst = self.instrument if token_key == 'up' else self.down_instrument
            if inst is None:
                return False
            
            side = OrderSide.SELL if pos['side'] == 'buy' else OrderSide.BUY
            self._place_order(inst.id, side, current_price, pos['size'], f"exit_ev_{token_key}")
            
            # Calculate PnL
            entry = pos['entry_price']
            pnl = (current_price - entry) * pos['size'] if pos['side'] == 'buy' else (entry - current_price) * pos['size']
            self.round_pnl += pnl
            self.total_pnl += pnl
            
            pos['open'] = False
            pos['entry_price'] = 0.0
            pos['size'] = 0.0
            pos['side'] = None
            pos['phase'] = None
            
            self.log.info(f"💨 Exited {token_key.upper()} @ {current_price:.4f} (EV={ev:.4f})")
            return True
        
        return False
