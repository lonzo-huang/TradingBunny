#!/usr/bin/env python3
"""
Generate flip_stats.json from Binance BTC historical data.

Usage:
    python utils/generate_flip_stats.py --lookback 24h
    python utils/generate_flip_stats.py --lookback 1w
    python utils/generate_flip_stats.py --lookback 30d --interval 1m

Lookback options: 12h, 24h, 3d, 1w, 2w, 30d
"""

import argparse
import json
import sys
import os
from datetime import datetime, timezone

# Ensure project root is on path for both CLI and module usage
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from utils.flip_stats_engine import (
    generate_flip_stats,
    LOOKBACK_MAP, TAU_BINS, DELTA_BINS,
)


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

    print(f"{'='*60}")
    print(f"  Flip Stats Generator")
    print(f"{'='*60}")
    print(f"  Symbol      : {args.symbol}")
    print(f"  Lookback    : {args.lookback}")
    print(f"  Interval    : {args.interval}")
    print(f"  Min samples : {args.min_samples}")
    print()

    # ── Compute via engine ──
    flip_data, sample_counts = generate_flip_stats(
        lookback=args.lookback,
        symbol=args.symbol,
        interval=args.interval,
        min_samples=args.min_samples,
        verbose=True,
    )

    if not flip_data:
        print("❌ No flip data generated. Try a longer lookback or lower --min-samples.")
        sys.exit(1)

    # ── Build output JSON ──
    now = datetime.now(timezone.utc)
    output = {
        "description": (
            f"Flip probability lookup table — empirical P(price reverses direction) "
            f"in the last 60s of a 5-min BTC window"
        ),
        "generated_at": now.isoformat(),
        "symbol": args.symbol,
        "lookback": args.lookback,
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
