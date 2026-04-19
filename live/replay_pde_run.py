"""Replay persisted PDE market_data events in timestamp order.

This is a lightweight replay utility for debugging strategy behavior over historical
captured ticks before running a full Nautilus backtest.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass


@dataclass
class ReplayEvent:
    ts_ns: int
    source: str
    instrument_id: str
    bid: float | None
    ask: float | None
    last: float | None
    mid: float | None
    volume: float | None
    extra_json: str


def load_market_data(csv_path: str) -> list[ReplayEvent]:
    events: list[ReplayEvent] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            events.append(
                ReplayEvent(
                    ts_ns=int(row.get("ts_ns") or 0),
                    source=row.get("source") or "",
                    instrument_id=row.get("instrument_id") or "",
                    bid=_to_float(row.get("bid")),
                    ask=_to_float(row.get("ask")),
                    last=_to_float(row.get("last")),
                    mid=_to_float(row.get("mid")),
                    volume=_to_float(row.get("volume")),
                    extra_json=row.get("extra_json") or "{}",
                )
            )
    events.sort(key=lambda x: x.ts_ns)
    return events


def _to_float(v: str | None) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def replay(events: list[ReplayEvent], speed: float = 1.0, max_events: int | None = None) -> None:
    if not events:
        print("No events to replay.")
        return

    print(f"▶ Replay start: {len(events)} events | speed={speed}x")

    prev_ts = events[0].ts_ns
    processed = 0

    for ev in events:
        if max_events is not None and processed >= max_events:
            break

        if processed > 0:
            dt_sec = max(0.0, (ev.ts_ns - prev_ts) / 1_000_000_000)
            sleep_for = dt_sec / max(speed, 0.01)
            if sleep_for > 0:
                time.sleep(min(sleep_for, 1.0))

        extra = {}
        try:
            extra = json.loads(ev.extra_json or "{}")
        except Exception:
            extra = {"raw": ev.extra_json}

        print(
            f"[{ev.ts_ns}] {ev.source:<10} {ev.instrument_id:<42} "
            f"bid={ev.bid} ask={ev.ask} last={ev.last} mid={ev.mid} vol={ev.volume} extra={extra}"
        )

        prev_ts = ev.ts_ns
        processed += 1

    print(f"✅ Replay done: {processed} events")


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay persisted PDE market_data CSV")
    parser.add_argument(
        "--csv",
        default=os.path.join("data", "pde", "exports", "market_data.csv"),
        help="Path to market_data.csv",
    )
    parser.add_argument("--speed", type=float, default=20.0, help="Replay speed multiplier")
    parser.add_argument("--max-events", type=int, default=None, help="Stop after N events")
    args = parser.parse_args()

    events = load_market_data(args.csv)
    replay(events, speed=args.speed, max_events=args.max_events)


if __name__ == "__main__":
    main()
