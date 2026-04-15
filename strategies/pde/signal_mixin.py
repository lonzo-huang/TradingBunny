"""Signal generation mixin: EV calculation, flip stats, price analysis."""

from __future__ import annotations

import math
import json
import os
import threading
from typing import Any


class PDESignalMixin:
    """Handles signal generation, EV calculation, and flip probability analysis."""
    
    # Required from base
    config: Any
    log: Any
    clock: Any
    flip_probs: dict
    flip_stats: dict
    btc_price: float | None
    btc_start_price: float | None
    _flip_stats_refresh_thread: Any | None
    _next_flip_stats_refresh_ts: float
    price_history: dict

    def _smooth_phase_a_ev(self, token_key: str, ev_raw: float) -> float:
        """Smooth Phase A EV with EMA and clamp tiny noise around zero."""
        alpha = max(0.0, min(1.0, float(getattr(self.config, 'ev_ema_alpha', 0.25))))
        deadband = max(0.0, float(getattr(self.config, 'ev_deadband', 0.0)))

        prev = self.ev_ema.get(token_key)
        if prev is None:
            ev_smoothed = ev_raw
        else:
            ev_smoothed = prev + alpha * (ev_raw - prev)
        self.ev_ema[token_key] = ev_smoothed
        return 0.0 if abs(ev_smoothed) < deadband else ev_smoothed
    
    def _load_flip_stats_from_file(self) -> dict:
        """Load flip probability lookup table from JSON."""
        try:
            flip_stats_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'config', 'flip_stats.json'
            )
            with open(flip_stats_path, 'r') as f:
                data = json.load(f)

            # Support both schemas:
            # - legacy: {"probs": {...}}
            # - current: {"data": {...}}
            buckets = data.get('probs') or data.get('data') or {}
            self.flip_probs = buckets

            self.log.info(f"📊 Loaded flip stats: {len(buckets)} buckets")
            return data
        except Exception as e:
            self.log.error(f"❌ Failed to load flip stats: {e}")
            return {}
    
    def _schedule_flip_stats_refresh(self) -> None:
        """Schedule next flip stats refresh."""
        interval_min = self.config.flip_stats_refresh_minutes
        if interval_min <= 0:
            return
        
        self._next_flip_stats_refresh_ts = self.clock.timestamp() + interval_min * 60
        self.log.info(f"📅 Scheduled flip stats refresh in {interval_min}min")
    
    def _check_flip_stats_refresh(self) -> None:
        """Check if it's time to refresh flip stats."""
        if self.config.flip_stats_refresh_minutes <= 0:
            return
        if self.clock.timestamp() < self._next_flip_stats_refresh_ts:
            return
        if self._flip_stats_refresh_thread and self._flip_stats_refresh_thread.is_alive():
            return
        
        self._flip_stats_refresh_thread = threading.Thread(
            target=self._refresh_flip_stats_worker, daemon=True
        )
        self._flip_stats_refresh_thread.start()
        self._schedule_flip_stats_refresh()
    
    def _refresh_flip_stats_worker(self) -> None:
        """Background thread: fetch Binance data and compute flip probs."""
        try:
            from utils.flip_stats_engine import generate_flip_stats, flip_probs_to_lookup
            
            lookback = self.config.flip_stats_lookback
            stats, probs = generate_flip_stats(lookback=lookback)
            
            self.flip_stats = stats
            self.flip_probs = flip_probs_to_lookup(probs)
            
            self.log.info(f"✅ Refreshed flip stats: {len(self.flip_probs)} buckets")
        except Exception as e:
            self.log.error(f"❌ Flip stats refresh failed: {e}")
    
    def _calculate_ev(self, token_key: str, current_price: float, 
                     sigma: float, delta_pct: float, remaining_sec: float,
                     in_phase_a: bool) -> tuple[float, float, bool]:
        """Calculate expected value for a position.
        
        Returns: (ev, p_flip, tail_condition)
        """
        # Base probability from delta
        p_up = 0.5 + delta_pct if token_key == 'up' else 0.5 - delta_pct
        p_up = max(0.05, min(0.95, p_up))  # Clamp to reasonable range
        
        # Get flip probability
        p_flip = 0.0
        if self.flip_probs:
            bucket = self._get_flip_bucket(delta_pct, sigma)
            p_flip = self.flip_probs.get(bucket, 0.0)
        
        # Calculate EV
        if in_phase_a:
            # Phase A: momentum following
            ev_raw = self._ev_phase_a(p_up, current_price)
            ev = self._smooth_phase_a_ev(token_key, ev_raw)
            return ev, p_flip, False
        else:
            # Phase B: trend continuation
            ev, tail_cond = self._ev_phase_b(
                p_up, p_flip, current_price, sigma, delta_pct, remaining_sec
            )
            return ev, p_flip, tail_cond
    
    def _get_flip_bucket(self, delta_pct: float, sigma: float) -> str:
        """Determine flip probability bucket based on delta and volatility."""
        z_score = delta_pct / max(sigma, 0.001)
        if abs(z_score) < 0.5:
            return "low"
        elif abs(z_score) < 1.0:
            return "medium"
        else:
            return "high"
    
    def _ev_phase_a(self, p_up: float, price: float) -> float:
        """Phase A EV for BUYing this token.

        `p_up` here is already token-specific probability from `_calculate_ev`:
        - up token   -> p_up = P(up)
        - down token -> p_up = P(down)

        Binary token expected value per share when buying is:
            EV = P(win) - price
        """
        return p_up - price
    
    def _ev_phase_b(
        self,
        p_up: float,
        p_flip: float,
        price: float,
        sigma: float,
        delta_pct: float,
        remaining_sec: float,
    ) -> tuple[float, bool]:
        """Phase B EV: momentum continuation with time/volatility scaling.

        Args:
            delta_pct: Price change as decimal (e.g., 0.005 for 0.5%)
        """
        # Get threshold in USD and compute price offset ratio
        threshold_usd = float(getattr(self.config, 'phase_b_momentum_threshold_usd', 30.0))
        # Convert USD threshold to percentage based on current BTC price
        btc_price = getattr(self, 'btc_price', 0) or getattr(self, 'btc_start_price', 0) or 85000
        momentum_threshold_pct = threshold_usd / max(btc_price, 1) if btc_price > 0 else 0.005
        if abs(delta_pct) < momentum_threshold_pct:
            return 0.0, False

        remaining = max(0.0, float(remaining_sec))
        vol_time_scaled = max(0.0, float(sigma)) * math.sqrt(remaining / 300.0)
        z_score = abs(delta_pct) / max(vol_time_scaled, 1e-4)

        # Smoothly map z-score to continuation probability in [0.5, 0.95].
        p_cont = min(0.95, 0.5 + 0.45 * (1.0 - 1.0 / (1.0 + z_score)))
        ev = p_cont - price
        tail_condition = ev > 0.01
        return ev, tail_condition
    
    def _update_price_history(self, token_key: str, price: float) -> None:
        """Update price history for volatility calculation."""
        if self.price_history[token_key] is None:
            from collections import deque
            self.price_history[token_key] = deque(maxlen=100)
        
        self.price_history[token_key].append({
            'price': price,
            'ts': self.clock.timestamp()
        })
    
    def _calculate_sigma(self, token_key: str) -> float:
        """Calculate realized volatility from price history."""
        hist = self.price_history[token_key]
        if hist is None or len(hist) < 10:
            return 0.01  # Default 1% vol

        prices = [h['price'] for h in hist if h['price'] > 0]
        if len(prices) < 2:
            return 0.01

        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                   for i in range(1, len(prices)) if prices[i-1] > 0]

        if len(returns) < 2:
            return 0.01

        import statistics
        return statistics.stdev(returns)
