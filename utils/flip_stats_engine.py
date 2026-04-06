# utils/flip_stats_engine.py
"""
Core engine for computing BTC flip probabilities from Binance historical data.

Used by:
  - utils/generate_flip_stats.py (CLI tool)
  - strategies/polymarket_pde_strategy.py (runtime dynamic refresh)
"""

import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict


# ── Constants ────────────────────────────────────────────────────────────────

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
WINDOW_SEC = 300       # 5-minute window
PHASE_B_START = 240    # Phase B begins at 240s into the window

TAU_BINS = [
    (0, 10),
    (10, 20),
    (20, 30),
    (30, 45),
    (45, 60),
]

DELTA_BINS = [
    (0, 5),
    (5, 10),
    (10, 20),
    (20, 50),
    (50, 100),
    (100, 150),
    (150, 200),
    (200, 300),
    (300, 500),
    (500, 999),
]

LOOKBACK_MAP = {
    '12h': timedelta(hours=12),
    '24h': timedelta(hours=24),
    '1d':  timedelta(days=1),
    '3d':  timedelta(days=3),
    '1w':  timedelta(weeks=1),
    '2w':  timedelta(weeks=2),
    '30d': timedelta(days=30),
}


# ── Binance API ──────────────────────────────────────────────────────────────

def fetch_klines(symbol: str, interval: str, start_ms: int, end_ms: int,
                 limit: int = 1000, verbose: bool = True) -> list:
    """Fetch klines from Binance API with pagination and rate limiting."""
    all_klines = []
    current_start = start_ms

    while current_start < end_ms:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start,
            'endTime': end_ms,
            'limit': limit,
        }
        url = f"{BINANCE_KLINES_URL}?{urllib.parse.urlencode(params)}"

        for attempt in range(3):
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                else:
                    if verbose:
                        print(f"\n  ❌ API failed after 3 attempts: {e}")
                    return all_klines

        if not data:
            break

        all_klines.extend(data)

        last_close_time = data[-1][6]
        current_start = last_close_time + 1

        if verbose:
            progress = min(100, (current_start - start_ms) / (end_ms - start_ms) * 100)
            print(f"\r  Fetching: {progress:5.1f}%  ({len(all_klines):,} candles)",
                  end="", flush=True)

        time.sleep(0.12)

        if len(data) < limit:
            break

    if verbose:
        print()
    return all_klines


# ── Price series construction ────────────────────────────────────────────────

def klines_to_prices(klines: list, interval: str) -> dict[int, float]:
    """Convert klines to {timestamp_sec: price} mapping."""
    prices = {}
    for k in klines:
        ts_sec = k[0] // 1000
        if interval == '1s':
            prices[ts_sec] = float(k[4])  # close price
        else:
            # 1m: record open at start, close at end
            prices[ts_sec] = float(k[1])       # open
            prices[ts_sec + 59] = float(k[4])  # close
    return prices


# ── Flip probability computation ─────────────────────────────────────────────

def compute_flip_stats(prices: dict[int, float], resolution: int,
                       min_samples: int = 5,
                       verbose: bool = True) -> tuple[dict, dict, int]:
    """
    Compute flip probabilities from price time series.

    Returns:
        (flip_probs, sample_counts, n_valid_windows)
    """
    sorted_ts = sorted(prices.keys())
    if not sorted_ts:
        return {}, {}, 0

    first_ts = sorted_ts[0]
    last_ts = sorted_ts[-1]

    window_start = (first_ts // WINDOW_SEC) * WINDOW_SEC

    bucket_flips = defaultdict(int)
    bucket_total = defaultdict(int)
    valid_windows = 0
    total_windows = 0

    while window_start + WINDOW_SEC <= last_ts:
        window_end = window_start + WINDOW_SEC
        total_windows += 1

        p_start = _find_price(prices, window_start, max_search=resolution + 1)
        p_end = _find_price(prices, window_end, max_search=resolution + 1)

        if p_start is None or p_end is None:
            window_start += WINDOW_SEC
            continue

        valid_windows += 1
        end_direction = _sign(p_end - p_start)

        for t_offset in range(PHASE_B_START, WINDOW_SEC, resolution):
            t_abs = window_start + t_offset
            p_t = _find_price(prices, t_abs, max_search=max(2, resolution))

            if p_t is None:
                continue

            tau = WINDOW_SEC - t_offset
            delta_usd = abs(p_t - p_start)
            direction_at_t = _sign(p_t - p_start)

            if direction_at_t == 0:
                continue

            flipped = (direction_at_t != end_direction) and (end_direction != 0)

            tau_bin = _find_bin(tau, TAU_BINS)
            delta_bin = _find_bin(delta_usd, DELTA_BINS)

            if tau_bin and delta_bin:
                key = f"{tau_bin[0]}_{tau_bin[1]}_{delta_bin[0]}_{delta_bin[1]}"
                bucket_total[key] += 1
                if flipped:
                    bucket_flips[key] += 1

        window_start += WINDOW_SEC

    if verbose and total_windows > 0:
        print(f"  Analyzed {valid_windows}/{total_windows} windows "
              f"({valid_windows / total_windows:.0%} valid)")

    flip_probs = {}
    sample_counts = {}
    for key in sorted(bucket_total.keys()):
        n = bucket_total[key]
        if n >= min_samples:
            flip_probs[key] = round(bucket_flips[key] / n, 4)
            sample_counts[key] = n

    return flip_probs, sample_counts, valid_windows


# ── High-level API ───────────────────────────────────────────────────────────

def generate_flip_stats(lookback: str = "24h", symbol: str = "BTCUSDT",
                        interval: str = "auto", min_samples: int = 5,
                        verbose: bool = True) -> tuple[dict, dict]:
    """
    One-call API: fetch Binance data → compute flip probabilities → return dicts.

    Args:
        lookback: "12h", "24h", "3d", "1w", "2w", "30d"
        symbol: Binance symbol
        interval: "auto", "1s", "1m"
        min_samples: minimum samples per bucket
        verbose: print progress

    Returns:
        (flip_probs, sample_counts) — both are {str_key: value} dicts
        flip_probs values are probabilities [0,1]
        sample_counts values are integers
    """
    td = LOOKBACK_MAP.get(lookback)
    if td is None:
        raise ValueError(f"Unknown lookback: {lookback}. Options: {list(LOOKBACK_MAP.keys())}")

    if interval == "auto":
        interval = "1s" if td <= timedelta(days=3) else "1m"

    resolution = 1 if interval == "1s" else 60

    now = datetime.now(timezone.utc)
    start_ms = int((now - td).timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    if verbose:
        print(f"  FlipStats: {symbol} {lookback} ({interval})")

    klines = fetch_klines(symbol, interval, start_ms, end_ms, verbose=verbose)
    if not klines:
        return {}, {}

    prices = klines_to_prices(klines, interval)
    flip_probs, sample_counts, n_windows = compute_flip_stats(
        prices, resolution, min_samples, verbose
    )

    if verbose:
        print(f"  FlipStats: {len(flip_probs)} buckets from {n_windows} windows")

    return flip_probs, sample_counts


def flip_probs_to_lookup(flip_probs: dict) -> dict[tuple, float]:
    """Convert string-keyed flip_probs dict to tuple-keyed lookup table
    compatible with strategy's _get_flip_prob().
    """
    lookup = {}
    for key, prob in flip_probs.items():
        parts = key.split('_')
        if len(parts) == 4:
            tau_low, tau_high, delta_low, delta_high = map(int, parts)
            lookup[(tau_low, tau_high, delta_low, delta_high)] = prob
    return lookup


# ── Helpers ──────────────────────────────────────────────────────────────────

def _find_price(prices: dict, ts: int, max_search: int = 2) -> float | None:
    for offset in range(max_search):
        if (ts + offset) in prices:
            return prices[ts + offset]
        if offset > 0 and (ts - offset) in prices:
            return prices[ts - offset]
    return None


def _sign(x: float) -> int:
    if x > 0:
        return 1
    elif x < 0:
        return -1
    return 0


def _find_bin(value: float, bins: list[tuple[int, int]]) -> tuple[int, int] | None:
    for low, high in bins:
        if low <= value < high:
            return (low, high)
    return None
