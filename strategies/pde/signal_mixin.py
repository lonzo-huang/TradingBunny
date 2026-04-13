"""Signal generation mixin: EV calculation, flip stats, price analysis."""

from __future__ import annotations

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
    
    def _load_flip_stats_from_file(self) -> dict:
        """Load flip probability lookup table from JSON."""
        try:
            flip_stats_path = os.path.join(
                os.path.dirname(__file__), '..', '..', 'config', 'flip_stats.json'
            )
            with open(flip_stats_path, 'r') as f:
                data = json.load(f)
            self.log.info(f"📊 Loaded flip stats: {len(data.get('probs', {}))} buckets")
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
            ev = self._ev_phase_a(p_up, current_price)
            return ev, p_flip, False
        else:
            # Phase B: tail reversal
            ev, tail_cond = self._ev_phase_b(p_up, p_flip, current_price, sigma)
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
        """Phase A EV: simple momentum."""
        # Assume 1.0 payoff if correct
        return (p_up - 0.5) * 1.0  # Simplified
    
    def _ev_phase_b(self, p_up: float, p_flip: float, price: float, sigma: float) -> tuple[float, bool]:
        """Phase B EV: tail reversal with flip probability."""
        tail_threshold = self.config.tail_start_threshold
        is_tail = sigma > tail_threshold
        
        if not is_tail:
            return 0.0, False
        
        # Tail reversal expected value
        ev_reversal = (p_flip - 0.5) * 1.0
        tail_condition = p_flip > 0.6  # High confidence threshold
        
        return ev_reversal, tail_condition
    
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
