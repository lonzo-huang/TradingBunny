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
    btc_price_history: Any | None
    _flip_stats_refresh_thread: Any | None
    _next_flip_stats_refresh_ts: float
    price_history: dict
    _flip_probs_lock: threading.Lock | None = None

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
    
    def _get_flip_probs_lock(self) -> threading.Lock:
        """Get or create the flip_probs thread lock."""
        if self._flip_probs_lock is None:
            self._flip_probs_lock = threading.Lock()
        return self._flip_probs_lock

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

            # Thread-safe update
            with self._get_flip_probs_lock():
                self.flip_probs = buckets

            self.log.info(f"[STATS] Loaded flip stats: {len(buckets)} buckets")
            return data
        except Exception as e:
            self.log.error(f"[ERROR] Failed to load flip stats: {e}")
            return {}
    
    def _schedule_flip_stats_refresh(self) -> None:
        """Schedule next flip stats refresh."""
        interval_min = self.config.flip_stats_refresh_minutes
        if interval_min <= 0:
            return
        
        self._next_flip_stats_refresh_ts = self.clock.timestamp() + interval_min * 60
        self.log.info(f"[SCHED] Scheduled flip stats refresh in {interval_min}min")
    
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

            # Thread-safe update
            with self._get_flip_probs_lock():
                self.flip_stats = stats
                self.flip_probs = flip_probs_to_lookup(probs)

            self.log.info(f"[OK] Refreshed flip stats: {len(self.flip_probs)} buckets")
        except Exception as e:
            self.log.error(f"[ERROR] Flip stats refresh failed: {e}")
    
    def _update_p_t(self, token_key: str, delta_btc_pct: float) -> float:
        """Update internal probability p(t) using BTC price changes.
        
        Formula: p(t) = p(t-Δt) + α · ΔBTC
        """
        alpha = float(getattr(self.config, 'ev_alpha', 0.001))
        prev_p = getattr(self, '_p_t', {}).get(token_key, 0.5)
        
        # For 'up' token: BTC up → probability up
        # For 'down' token: BTC up → probability down
        if token_key == 'up':
            new_p = prev_p + alpha * delta_btc_pct
        else:  # 'down'
            new_p = prev_p - alpha * delta_btc_pct
        
        # Clamp to [0.05, 0.95]
        new_p = max(0.05, min(0.95, new_p))
        
        # Store updated value
        if hasattr(self, '_p_t'):
            self._p_t[token_key] = new_p
        return new_p

    def _calculate_btc_sigma(self) -> float:
        """Calculate BTC realized volatility from price history."""
        if self.btc_price_history is None or len(self.btc_price_history) < 10:
            return 0.01  # Default 1% vol

        prices = [p for p in self.btc_price_history if isinstance(p, (int, float)) and p > 0]
        if len(prices) < 2:
            return 0.01

        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                   for i in range(1, len(prices)) if prices[i-1] > 0]

        if len(returns) < 2:
            return 0.01

        import statistics
        return statistics.stdev(returns)

    def _calculate_ev(
        self,
        token_key: str,
        current_price: float,
        sigma: float,
        delta_pct: float,
        remaining_sec: float,
        in_phase_a: bool,
        delta_btc_pct: float = 0.0,
        elapsed_sec: float = 0.0,
    ) -> tuple[float, float, bool]:
        """Calculate expected value for a position.

        Returns: (ev, p_flip, tail_condition)
        """
        # Get flip probability (thread-safe)
        p_flip = 0.0
        if self.flip_probs:
            bucket = self._get_flip_bucket(delta_pct, sigma, remaining_sec)
            with self._get_flip_probs_lock():
                p_flip = self.flip_probs.get(bucket, 0.0)

        # Calculate EV
        if in_phase_a:
            # Phase A: Direction-aware momentum following based on BTC z-score
            # Calculate BTC volatility and z-score
            btc_sigma = self._calculate_btc_sigma()
            btc_z = delta_btc_pct / max(btc_sigma, 0.001)

            # Direction-aware EV: BTC up -> UP token positive EV, DOWN token negative EV
            # z-score magnitude determines confidence, sign determines direction
            if token_key == 'up':
                # UP token benefits from BTC rise
                ev_raw = min(0.95, max(-0.95, 0.5 + 0.45 * math.tanh(btc_z * 2.0))) - current_price
            else:  # 'down'
                # DOWN token benefits from BTC fall
                ev_raw = min(0.95, max(-0.95, 0.5 - 0.45 * math.tanh(btc_z * 2.0))) - current_price

            ev = self._smooth_phase_a_ev(token_key, ev_raw)
            return ev, p_flip, False
        else:
            # Phase B: momentum continuation with flip probability adjustment
            ev, tail_cond = self._ev_phase_b(
                0.5, p_flip, current_price, sigma, delta_pct, remaining_sec, elapsed_sec
            )
            return ev, p_flip, tail_cond
    
    def _get_flip_bucket(self, delta_pct: float, sigma: float, remaining_sec: float = 300.0) -> str:
        """Determine flip probability bucket based on delta, volatility, and time.

        Returns bucket key in format "{tau_low}_{tau_high}_{delta_low}_{delta_high}"
        to match flip_stats.json keys.
        """
        # Map remaining time to tau buckets (in seconds)
        if remaining_sec >= 240:
            tau_bucket = "240_300"
        elif remaining_sec >= 180:
            tau_bucket = "180_240"
        elif remaining_sec >= 120:
            tau_bucket = "120_180"
        elif remaining_sec >= 60:
            tau_bucket = "60_120"
        else:
            tau_bucket = "0_60"

        # Map delta to delta buckets (in basis points, 1bp = 0.01%)
        delta_bps = abs(delta_pct) * 10000
        if delta_bps < 5:
            delta_bucket = "0_5"
        elif delta_bps < 10:
            delta_bucket = "5_10"
        elif delta_bps < 20:
            delta_bucket = "10_20"
        elif delta_bps < 50:
            delta_bucket = "20_50"
        else:
            delta_bucket = "50_inf"

        return f"{tau_bucket}_{delta_bucket}"
    
    def _ev_phase_a(self, p_t: float, market_price: float) -> float:
        """Phase A EV: p(t) - q(t) - legacy simple form, now unused.

        The new direction-aware EV is calculated inline in _calculate_ev.
        This method is kept for backward compatibility.
        """
        return p_t - market_price
    
    def _ev_phase_b(
        self,
        p_up: float,
        p_flip: float,
        price: float,
        sigma: float,
        delta_pct: float,
        remaining_sec: float,
        elapsed_sec: float = 0.0,
    ) -> tuple[float, bool]:
        """Phase B EV: momentum continuation with time/volatility scaling and flip adjustment.

        Args:
            delta_pct: Price change as decimal (e.g. 0.005 for 0.5%)
            p_flip: Historical flip probability from stats (0-1)
            elapsed_sec: Time elapsed since round start
        """
        # Get threshold in USD and compute price offset ratio
        threshold_usd = float(getattr(self.config, 'phase_b_momentum_threshold_usd', 30.0))
        # Use reasonable BTC price fallback to avoid threshold explosion
        btc_price = getattr(self, 'btc_price', None) or getattr(self, 'btc_start_price', None)
        if btc_price is None or btc_price <= 0:
            btc_price = 85000.0  # Reasonable default BTC price
        momentum_threshold_pct = threshold_usd / btc_price

        if abs(delta_pct) < momentum_threshold_pct:
            return 0.0, False

        remaining = max(0.0, float(remaining_sec))
        vol_time_scaled = max(0.0, float(sigma)) * math.sqrt(remaining / 300.0)
        z_score = abs(delta_pct) / max(vol_time_scaled, 1e-4)

        # Smoothly map z-score to continuation probability in [0.5, 0.95].
        p_cont_z = min(0.95, 0.5 + 0.45 * (1.0 - 1.0 / (1.0 + z_score)))

        # Blend with historical flip probability: higher p_flip = more likely to reverse
        # p_cont blends momentum continuation with historical reversal probability
        if p_flip > 0:
            # If history shows high flip probability, reduce continuation confidence
            p_cont = 0.5 * p_cont_z + 0.5 * (1.0 - p_flip)
        else:
            p_cont = p_cont_z

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
