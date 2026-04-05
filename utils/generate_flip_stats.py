#!/usr/bin/env python3
"""
Generate flip_stats.json from Binance BTC historical data.

Computes the empirical probability that BTC price "flips" direction in the
final 60 seconds of a 5-minute window, binned by (tau, delta):
  - tau: remaining seconds until window end
  - delta: absolute USD offset from window start price

Usage:
    python utils/generate_flip_stats.py --lookback 24h
    python utils/generate_flip_stats.py --lookback 1w
    python utils/generate_flip_stats.py --lookback 30d --interval 1m
    python utils/generate_flip_stats.py --lookback 24h --output config/flip_stats.json

Lookback options: 12h, 24h, 3d, 1w, 2w, 30d
Interval options: auto (default), 1s, 1m
  - auto: 1s for ≤3d, 1m for >3d
  - 1s gives second-level resolution (slower fetch for long periods)
  - 1m gives minute-level resolution (faster but coarser tau bins)
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import os


# ── Constants ────────────────────────────────────────────────────────────────

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
WINDOW_SEC = 300       # 5-minute window
PHASE_B_START = 240    # Phase B begins at 240s into the window

# tau bins: remaining seconds in window (Phase B = last 60s)
TAU_BINS = [
    (0, 10),
    (10, 20),
    (20, 30),
    (30, 45),
    (45, 60),
]

# delta bins: absolute BTC price offset (USD) from window start
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
                 limit: int = 1000) -> list:
    """Fetch klines from Binance API with pagination and rate limiting."""
    all_klines = []
    current_start = start_ms
    request_count = 0

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
                    print(f"\n  ❌ API failed after 3 attempts: {e}")
                    return all_klines

        if not data:
            break

        all_klines.extend(data)
        request_count += 1

        # Move start to after last candle
        last_close_time = data[-1][6]  # Close time in ms
        current_start = last_close_time + 1

        # Progress
        progress = min(100, (current_start - start_ms) / (end_ms - start_ms) * 100)
        elapsed_str = f"{len(all_klines):,}" if interval == '1s' else f"{len(all_klines):,}"
        print(f"\r  Fetching: {progress:5.1f}%  ({elapsed_str} candles, {request_count} requests)",
              end="", flush=True)

        # Rate limit: ~8 req/s to stay safely under 1200 weight/min
        time.sleep(0.12)

        if len(data) < limit:
            break

    print()
    return all_klines


# ── Price series construction ────────────────────────────────────────────────

def klines_to_prices_1s(klines: list) -> dict[int, float]:
    """Convert 1s klines to {timestamp_sec: close_price}"""
    prices = {}
    for k in klines:
        ts_sec = k[0] // 1000
        prices[ts_sec] = float(k[4])  # close price
    return prices


def klines_to_prices_1m(klines: list) -> dict[int, float]:
    """Convert 1m klines to {timestamp_sec: price} using OHLC interpolation.

    For each 1m candle, we record:
      - open  at candle start
      - close at candle start + 59 (or start + 30 as midpoint proxy)
    This gives ~2 data points per minute for Phase B sampling.
    """
    prices = {}
    for k in klines:
        ts_sec = k[0] // 1000
        open_px = float(k[1])
        close_px = float(k[4])
        # Record open at start, close at end of minute
        prices[ts_sec] = open_px
        prices[ts_sec + 59] = close_px
    return prices


# ── Flip probability computation ─────────────────────────────────────────────

def compute_flip_stats(prices: dict[int, float], resolution: int,
                       min_samples: int = 5) -> tuple[dict, dict, int]:
    """
    Compute flip probabilities from price time series.

    For each aligned 5-minute window:
      p_start = price at window start
      p_end   = price at window end (t=300)
      For each sample point t in Phase B (t=240..299):
        tau   = 300 - t  (seconds remaining)
        delta = |price(t) - p_start|  (USD)
        flipped = sign(price(t) - p_start) ≠ sign(p_end - p_start)
      Bin by (tau, delta) and accumulate.

    Returns:
        (flip_probs, sample_counts, n_valid_windows)
    """
    sorted_ts = sorted(prices.keys())
    if not sorted_ts:
        return {}, {}, 0

    first_ts = sorted_ts[0]
    last_ts = sorted_ts[-1]

    # Align to 5-minute boundaries
    window_start = (first_ts // WINDOW_SEC) * WINDOW_SEC

    # Accumulate stats per bucket
    bucket_flips = defaultdict(int)
    bucket_total = defaultdict(int)
    valid_windows = 0
    total_windows = 0

    while window_start + WINDOW_SEC <= last_ts:
        window_end = window_start + WINDOW_SEC
        total_windows += 1

        # Find start price (search within first few seconds)
        p_start = _find_price(prices, window_start, max_search=resolution + 1)

        # Find end price (search around window end)
        p_end = _find_price(prices, window_end, max_search=resolution + 1)

        if p_start is None or p_end is None:
            window_start += WINDOW_SEC
            continue

        valid_windows += 1
        end_direction = _sign(p_end - p_start)

        # Sample Phase B period at available resolution
        for t_offset in range(PHASE_B_START, WINDOW_SEC, resolution):
            t_abs = window_start + t_offset
            p_t = _find_price(prices, t_abs, max_search=max(2, resolution))

            if p_t is None:
                continue

            tau = WINDOW_SEC - t_offset  # remaining seconds
            delta_usd = abs(p_t - p_start)
            direction_at_t = _sign(p_t - p_start)

            if direction_at_t == 0:
                continue  # No movement, can't determine direction

            flipped = (direction_at_t != end_direction) and (end_direction != 0)

            # Find matching (tau, delta) bin
            tau_bin = _find_bin(tau, TAU_BINS)
            delta_bin = _find_bin(delta_usd, DELTA_BINS)

            if tau_bin and delta_bin:
                key = f"{tau_bin[0]}_{tau_bin[1]}_{delta_bin[0]}_{delta_bin[1]}"
                bucket_total[key] += 1
                if flipped:
                    bucket_flips[key] += 1

        window_start += WINDOW_SEC

    if total_windows > 0:
        print(f"  Analyzed {valid_windows}/{total_windows} windows "
              f"({valid_windows/total_windows:.0%} valid)")

    # Convert to probabilities
    flip_probs = {}
    sample_counts = {}
    for key in sorted(bucket_total.keys()):
        n = bucket_total[key]
        if n >= min_samples:
            flip_probs[key] = round(bucket_flips[key] / n, 4)
            sample_counts[key] = n

    return flip_probs, sample_counts, valid_windows


def _find_price(prices: dict, ts: int, max_search: int = 2) -> float | None:
    """Find price at or near timestamp ts."""
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


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate flip_stats.json from Binance BTC historical data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python utils/generate_flip_stats.py --lookback 24h
  python utils/generate_flip_stats.py --lookback 1w --interval 1m
  python utils/generate_flip_stats.py --lookback 30d --min-samples 10
        """
    )
    parser.add_argument('--lookback', type=str, default='24h',
                        choices=list(LOOKBACK_MAP.keys()),
                        help='Lookback period (default: 24h)')
    parser.add_argument('--interval', type=str, default='auto',
                        choices=['auto', '1s', '1m'],
                        help='Kline interval: auto=1s for ≤3d else 1m (default: auto)')
    parser.add_argument('--symbol', type=str, default='BTCUSDT',
                        help='Binance symbol (default: BTCUSDT)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output path (default: config/flip_stats.json)')
    parser.add_argument('--min-samples', type=int, default=5,
                        help='Minimum samples per bucket to include (default: 5)')
    args = parser.parse_args()

    lookback = LOOKBACK_MAP[args.lookback]

    # Determine kline interval
    if args.interval == 'auto':
        interval = '1s' if lookback <= timedelta(days=3) else '1m'
    else:
        interval = args.interval

    resolution = 1 if interval == '1s' else 60

    print(f"{'='*60}")
    print(f"  Flip Stats Generator")
    print(f"{'='*60}")
    print(f"  Symbol      : {args.symbol}")
    print(f"  Lookback    : {args.lookback} ({lookback})")
    print(f"  Interval    : {interval} ({'second-level' if interval == '1s' else 'minute-level'} resolution)")
    print(f"  Min samples : {args.min_samples}")
    print()

    # Time range
    now = datetime.now(timezone.utc)
    start_time = now - lookback
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    n_expected = int(lookback.total_seconds()) if interval == '1s' else int(lookback.total_seconds() / 60)
    n_requests = max(1, n_expected // 1000)
    est_time = n_requests * 0.15
    print(f"  Time range  : {start_time.strftime('%Y-%m-%d %H:%M')} → {now.strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"  Est. candles: ~{n_expected:,}")
    print(f"  Est. time   : ~{est_time:.0f}s ({n_requests} API requests)")
    print()

    # ── Fetch data ──
    print("🔄 Fetching klines from Binance...")
    t0 = time.time()
    klines = fetch_klines(args.symbol, interval, start_ms, end_ms)
    fetch_time = time.time() - t0
    print(f"  Got {len(klines):,} klines in {fetch_time:.1f}s")

    if not klines:
        print("❌ No data fetched. Check network or try a shorter lookback.")
        sys.exit(1)

    # ── Build price series ──
    if interval == '1s':
        prices = klines_to_prices_1s(klines)
    else:
        prices = klines_to_prices_1m(klines)

    print(f"  Price series: {len(prices):,} data points")
    print()

    # ── Compute flip stats ──
    print("📈 Computing flip probabilities...")
    flip_data, sample_counts, n_windows = compute_flip_stats(
        prices, resolution, args.min_samples
    )

    if not flip_data:
        print("❌ No flip data generated. Try a longer lookback or lower --min-samples.")
        sys.exit(1)

    # ── Build output JSON ──
    output = {
        "description": (
            f"Flip probability lookup table — empirical P(price reverses direction) "
            f"in the last 60s of a 5-min BTC window"
        ),
        "generated_at": now.isoformat(),
        "symbol": args.symbol,
        "lookback": args.lookback,
        "kline_interval": interval,
        "n_windows_analyzed": n_windows,
        "n_klines": len(klines),
        "min_samples_per_bucket": args.min_samples,
        "tau_bins_sec": TAU_BINS,
        "delta_bins_usd": DELTA_BINS,
        "format": "Key: tau_low_tau_high_delta_low_delta_high → Value: flip_probability",
        "data": flip_data,
        "sample_counts": sample_counts,
    }

    # ── Write file ──
    if args.output:
        output_path = args.output
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, '..', 'config', 'flip_stats.json')
        output_path = os.path.normpath(output_path)

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Written to {output_path}")
    print(f"   {len(flip_data)} buckets (≥{args.min_samples} samples each)")

    # ── Summary table ──
    print(f"\n{'='*70}")
    print(f"  {'τ (sec)':<15} {'Δ (USD)':<15} {'P(flip)':>10} {'Samples':>10}")
    print(f"  {'-'*55}")

    for key in sorted(flip_data.keys(), key=_sort_key):
        parts = key.split('_')
        tau_str = f"[{parts[0]}, {parts[1]}]"
        delta_str = f"[${parts[2]}, ${parts[3]}]"
        prob = flip_data[key]
        n = sample_counts[key]
        bar = "█" * int(prob * 30)
        print(f"  {tau_str:<15} {delta_str:<15} {prob:>8.2%}  {n:>8,}  {bar}")

    print(f"{'='*70}")
    print(f"\n💡 To use: set delta_tail_min in config to match the smallest Δ bucket")
    print(f"   with sufficient samples. Current smallest Δ bucket with data:")

    min_delta = None
    for key in flip_data:
        parts = key.split('_')
        d_low = int(parts[2])
        if min_delta is None or d_low < min_delta:
            min_delta = d_low

    if min_delta is not None:
        print(f"   → Δ ≥ ${min_delta}  (set delta_tail_min={min_delta}.0 in config)")


def _sort_key(key: str):
    """Sort by tau_low, then delta_low."""
    parts = key.split('_')
    return (int(parts[0]), int(parts[2]))


if __name__ == '__main__':
    main()
