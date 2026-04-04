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
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import Venue, InstrumentId


class PolymarketPDEStrategyConfig(StrategyConfig):
    """Configuration for Polymarket PDE Strategy"""
    market_base_slug: str  # e.g., "btc-updown-5m"
    market_interval_minutes: int = 5
    trade_size: Decimal = Decimal("100")
    auto_rollover: bool = True
    
    # Phase A parameters
    ev_threshold_A: float = 0.05
    max_A_trades: int = 2
    
    # Phase B parameters
    delta_tail_min: float = 150.0  # Minimum price offset for tail strategy
    tail_return: float = 0.10  # Expected return for tail strategy
    ev_threshold_tail: float = 0.0
    
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
        
        # Round state
        self.start_price: float | None = None
        self.start_ts: int | None = None
        self.position_open: bool = False
        self.down_position_open: bool = False
        
        # Phase A state
        self.A_trades: int = 0
        
        # Phase B state
        self.tail_trade_done: bool = False
        
        # Price history for volatility estimation
        self.price_history: deque = deque(maxlen=config.volatility_window)
        self.last_rollover_check: datetime | None = None
        
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
        
        self.log.info("📊 Prometheus metrics initialized for PDE Strategy")

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def on_start(self) -> None:
        self.log.info("🚀 Starting Polymarket PDE Strategy (Dual-Phase Engine)")
        self.log.info(f"   Base slug        : {self.config.market_base_slug}")
        self.log.info(f"   Interval (min)   : {self.config.market_interval_minutes}")
        self.log.info(f"   Trade size (USDC): {self.config.trade_size}")
        self.log.info(f"   Phase A EV threshold: {self.config.ev_threshold_A}")
        self.log.info(f"   Phase A max trades: {self.config.max_A_trades}")
        self.log.info(f"   Phase B delta min: {self.config.delta_tail_min}")

        # Start Prometheus HTTP server
        try:
            start_http_server(8001)  # Use different port from existing strategy
            self.log.info("📊 Prometheus metrics server started on http://localhost:8001")
            self.log.info("   Metrics endpoint: http://localhost:8001/metrics")
        except Exception as e:
            self.log.warning(f"⚠️  Failed to start Prometheus server: {e}")

        self._subscribe_current_market()

        if self.config.auto_rollover:
            self.clock.set_timer(
                name="pde_market_rollover_check",
                interval=timedelta(minutes=1),
                callback=self._on_rollover_timer,
            )

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
            
        self.log.info("🛑 PDE Strategy stopped.")

    def on_reset(self) -> None:
        self.instrument = None
        self.down_instrument = None
        self.start_price = None
        self.start_ts = None
        self.position_open = False
        self.down_position_open = False
        self.A_trades = 0
        self.tail_trade_done = False
        self.current_market_slug = None
        self.price_history.clear()

    # ── Slug calculation ───────────────────────────────────────────────────

    def _get_current_slug(self) -> str:
        now = datetime.now(timezone.utc)
        interval = self.config.market_interval_minutes
        aligned_minute = (now.minute // interval) * interval
        market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
        return f"{self.config.market_base_slug}-{int(market_time.timestamp())}"

    # ── Market subscription ────────────────────────────────────────────────

    def _subscribe_current_market(self) -> None:
        """Subscribe to current market Up/Down tokens"""
        slug = self._get_current_slug()
        if slug == self.current_market_slug:
            return

        # Unsubscribe old instruments
        old_instruments = []
        if self.instrument and self.current_market_slug:
            old_instruments.append(self.instrument)
        if self.down_instrument and self.current_market_slug:
            old_instruments.append(self.down_instrument)
            
        for old_inst in old_instruments:
            self.log.info(f"📤 Unsubscribing: {old_inst.id}")
            self.unsubscribe_quote_ticks(old_inst.id)
            self.cancel_all_orders(instrument_id=old_inst.id)

        self.current_market_slug = slug
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

        # Subscribe to found instruments
        if up_matched:
            self.instrument = up_matched
            self.subscribe_quote_ticks(up_matched.id)
            self.log.info(f"📊 Subscribed to Up: {up_matched.id}")
        else:
            self.log.error(f"❌ No Up token found for {slug}")
            
        if down_matched:
            self.down_instrument = down_matched
            self.subscribe_quote_ticks(down_matched.id)
            self.log.info(f"📊 Subscribed to Down: {down_matched.id}")
        else:
            self.log.warning(f"⚠️  No Down token found for {slug}")

    # ── Rollover timer ─────────────────────────────────────────────────────

    def _on_rollover_timer(self, event) -> None:
        new_slug = self._get_current_slug()
        if new_slug == self.current_market_slug:
            return
            
        self.log.info(f"🔄 Rollover: {self.current_market_slug} → {new_slug}")
        
        if self.instrument:
            self.cancel_all_orders(instrument_id=self.instrument.id)
        if self.down_instrument:
            self.cancel_all_orders(instrument_id=self.down_instrument.id)
            
        # Reset round state
        self.start_price = None
        self.start_ts = None
        self.position_open = False
        self.down_position_open = False
        self.A_trades = 0
        self.tail_trade_done = False
        self.price_history.clear()
        
        self._subscribe_current_market()
        self.last_rollover_check = datetime.now(timezone.utc)

    # ── Quote tick processing ──────────────────────────────────────────────

    def on_quote_tick(self, tick: QuoteTick) -> None:
        """Process quote ticks from Up/Down tokens"""
        if self.instrument and tick.instrument_id == self.instrument.id:
            self._process_tick(tick, is_up=True)
        elif self.down_instrument and tick.instrument_id == self.down_instrument.id:
            self._process_tick(tick, is_up=False)

    def _process_tick(self, tick: QuoteTick, is_up: bool) -> None:
        """Main tick processing logic for PDE strategy"""
        
        # TODO: Get BTC price from Binance instead of Polymarket mid price
        # For now, use Polymarket token price as proxy
        price = float(tick.bid_price + tick.ask_price) / 2.0
        
        ts_sec = tick.ts_event // 1_000_000_000
        
        # Initialize round
        if self.start_price is None:
            self.start_price = price
            self.start_ts = ts_sec
            self.A_trades = 0
            self.tail_trade_done = False
            self.price_history.clear()
            self.log.info(f"🎬 Round started: start_price={self.start_price:.4f}")
            return
        
        # Update price history
        self.price_history.append(price)
        
        # Calculate round state
        t_elapsed = ts_sec - self.start_ts
        remaining = 300 - t_elapsed
        delta_p = price - self.start_price
        abs_delta = abs(delta_p)
        
        # Update metrics
        token_type = 'up' if is_up else 'down'
        self.delta_p_gauge.labels(token_type=token_type).set(delta_p)
        self.remaining_time_gauge.set(remaining)
        
        # Route to appropriate phase
        if t_elapsed < 240:
            self._execute_phase_A(tick, is_up, t_elapsed, remaining, delta_p, abs_delta)
        else:
            self._execute_phase_B(tick, is_up, remaining, delta_p, abs_delta)

    # ── Phase A: EV-driven strategy ───────────────────────────────────────

    def _execute_phase_A(self, tick: QuoteTick, is_up: bool, t_elapsed: int, 
                         remaining: float, delta_p: float, abs_delta: float) -> None:
        """Phase A (0-240s): Brownian motion EV arbitrage"""
        
        self.strategy_state_gauge.set(1)  # Phase A
        
        if self.A_trades >= self.config.max_A_trades:
            return
        
        # Estimate volatility
        sigma = self._estimate_sigma()
        if sigma is None or sigma <= 0:
            return
        
        self.sigma_gauge.set(sigma)
        
        # Calculate theoretical probability using Brownian motion
        sigma_rem = sigma * math.sqrt(remaining)
        if sigma_rem <= 0:
            return
        
        z = delta_p / sigma_rem
        p_up = norm.cdf(z)
        
        token_type = 'up' if is_up else 'down'
        self.p_up_gauge.labels(token_type=token_type).set(p_up)
        
        # Get market implied probability from Polymarket
        up_ask = float(tick.ask_price)
        
        # Calculate EV
        ev_yes = p_up - up_ask
        ev_no = (1 - p_up) - (1 - up_ask)
        
        self.ev_gauge.labels(token_type=token_type, side='yes').set(ev_yes)
        self.ev_gauge.labels(token_type=token_type, side='no').set(ev_no)
        
        # Trading logic
        if ev_yes > self.config.ev_threshold_A:
            self._open_position(tick, is_up, OrderSide.BUY, "Phase A: EV_yes > threshold")
            self.A_trades += 1
            self.phase_a_trades_gauge.set(self.A_trades)
            self.trades_counter.labels(phase='A', token_type=token_type, side='buy').inc()
            
        elif ev_no > self.config.ev_threshold_A:
            self._open_position(tick, is_up, OrderSide.SELL, "Phase A: EV_no > threshold")
            self.A_trades += 1
            self.phase_a_trades_gauge.set(self.A_trades)
            self.trades_counter.labels(phase='A', token_type=token_type, side='sell').inc()

    # ── Phase B: Tail reversal strategy ────────────────────────────────────

    def _execute_phase_B(self, tick: QuoteTick, is_up: bool, remaining: float, 
                         delta_p: float, abs_delta: float) -> None:
        """Phase B (240-300s): Tail reversal probability strategy"""
        
        self.strategy_state_gauge.set(2)  # Phase B
        
        if self.tail_trade_done:
            return
        
        if abs_delta < self.config.delta_tail_min:
            return
        
        # Query flip probability from lookup table
        p_flip = self._get_flip_prob(remaining, abs_delta)
        if p_flip is None:
            return
        
        token_type = 'up' if is_up else 'down'
        self.p_flip_gauge.labels(token_type=token_type).set(p_flip)
        
        # Calculate tail EV
        ev_tail = (1 - p_flip) * self.config.tail_return - p_flip
        self.ev_tail_gauge.labels(token_type=token_type).set(ev_tail)
        
        # Trading logic: bet on current offset direction if EV > threshold
        if ev_tail > self.config.ev_threshold_tail:
            side = OrderSide.BUY if delta_p > 0 else OrderSide.SELL
            self._open_position(tick, is_up, side, f"Phase B: EV_tail={ev_tail:.4f}, p_flip={p_flip:.4f}")
            self.tail_trade_done = True
            self.trades_counter.labels(phase='B', token_type=token_type, side=side.name.lower()).inc()

    # ── Utility functions ──────────────────────────────────────────────────

    def _estimate_sigma(self) -> float | None:
        """Estimate volatility from price history using rolling window"""
        if len(self.price_history) < 10:
            return None
        
        prices = np.array(self.price_history)
        log_returns = np.diff(np.log(prices))
        
        if len(log_returns) == 0:
            return None
        
        # Annualize to 5-minute period
        sigma = np.std(log_returns) * np.sqrt(300)
        return float(sigma)

    def _get_flip_prob(self, tau: float, abs_delta: float) -> float | None:
        """Query flip probability from lookup table"""
        for (tau_low, tau_high, delta_low, delta_high), p in self.flip_stats.items():
            if tau_low <= tau <= tau_high and delta_low <= abs_delta <= delta_high:
                return p
        return None

    def _open_position(self, tick: QuoteTick, is_up: bool, side: OrderSide, reason: str) -> None:
        """Open a position"""
        instrument = self.instrument if is_up else self.down_instrument
        if not instrument:
            self.log.warning(f"⚠️  Cannot open position: instrument not available")
            return
        
        token_type = 'up' if is_up else 'down'
        self.log.info(f"📝 {reason} | {side.name} {token_type.upper()} @ {tick.ask_price}")
        
        order = self.order_factory.market(
            instrument_id=instrument.id,
            order_side=side,
            quantity=instrument.make_qty(self.config.trade_size),
            tags=[f"PDE_{token_type.upper()}_{side.name}"],
        )
        self.submit_order(order)
        
        if is_up:
            self.position_open = True
        else:
            self.down_position_open = True
        
        self.position_entry_price_gauge.labels(token_type=token_type).set(float(tick.ask_price))

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
