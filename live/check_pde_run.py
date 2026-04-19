"""Check and summarize a PDE run from SQLite persistence.

Usage:
    python live/check_pde_run.py --db data/pde/pde_runs.sqlite3
    python live/check_pde_run.py --db data/pde/pde_runs.sqlite3 --run-id <RUN_ID>
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime


def format_ts(ns: int | None) -> str:
    if ns is None:
        return "—"
    return datetime.fromtimestamp(ns / 1_000_000_000).strftime("%Y-%m-%d %H:%M:%S")


def summarize_run(db_path: str, run_id: str | None) -> None:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Find latest run if not specified
    if run_id is None:
        row = conn.execute(
            "SELECT run_id, mode, strategy, started_at_iso FROM runs ORDER BY started_at_ns DESC LIMIT 1"
        ).fetchone()
        if not row:
            print("❌ No runs found in database")
            sys.exit(1)
        run_id = row["run_id"]
        print(f"📊 Latest run: {run_id}  ({row['started_at_iso']})")
    else:
        row = conn.execute(
            "SELECT run_id, mode, strategy, started_at_iso FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            print(f"❌ Run not found: {run_id}")
            sys.exit(1)
        print(f"📊 Run: {run_id}  ({row['started_at_iso']})")

    # Counts
    stats = conn.execute(
        """
        SELECT 
            (SELECT COUNT(*) FROM orders WHERE run_id = ?) as orders,
            (SELECT COUNT(*) FROM fills WHERE run_id = ?) as fills,
            (SELECT COUNT(*) FROM positions WHERE run_id = ? AND event_type = 'position_closed') as positions_closed,
            (SELECT COUNT(*) FROM market_data WHERE run_id = ?) as market_ticks
        """,
        (run_id, run_id, run_id, run_id),
    ).fetchone()

    print(f"   Orders:        {stats['orders']}")
    print(f"   Fills:         {stats['fills']}")
    print(f"   Closed Pos:    {stats['positions_closed']}")
    print(f"   Market Ticks:  {stats['market_ticks']}")

    # PnL summary
    pnl_rows = conn.execute(
        """
        SELECT phase, SUM(realized_pnl) as realized, SUM(unrealized_pnl) as unrealized
        FROM pnl
        WHERE run_id = ?
        GROUP BY phase
        """,
        (run_id,),
    ).fetchall()

    print("\n💰 PnL Summary:")
    total_realized = 0.0
    total_unrealized = 0.0
    for r in pnl_rows:
        ph = r["phase"] or "?"
        real = r["realized"] or 0.0
        unreal = r["unrealized"] or 0.0
        total_realized += real
        total_unrealized += unreal
        print(f"   Phase {ph}: Realized={real:+.4f}  Unrealized={unreal:+.4f}")

    print(f"\n   Total Realized:   {total_realized:+.4f}")
    print(f"   Total Unrealized: {total_unrealized:+.4f}")

    # Last few fills
    fills = conn.execute(
        """
        SELECT ts_iso, instrument_id, side, quantity, price, fee
        FROM fills
        WHERE run_id = ?
        ORDER BY ts_ns DESC
        LIMIT 5
        """,
        (run_id,),
    ).fetchall()

    if fills:
        print("\n📝 Last 5 Fills:")
        for f in fills:
            print(
                f"   {f['ts_iso']} | {f['instrument_id']} | {f['side']} | "
                f"qty={f['quantity']} | px={f['price']} | fee={f['fee']}"
            )

    # Run summary if finished
    summary = conn.execute(
        "SELECT summary_json FROM runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    if summary and summary["summary_json"]:
        import json
        try:
            s = json.loads(summary["summary_json"])
            print("\n🏁 Run Summary (from on_stop):")
            for k, v in s.items():
                print(f"   {k}: {v}")
        except Exception:
            pass

    conn.close()
    print("\n✅ Check complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check PDE run statistics from SQLite")
    parser.add_argument("--db", default="data/pde/pde_runs.sqlite3", help="SQLite DB path")
    parser.add_argument("--run-id", default=None, help="Run ID (default: latest)")
    args = parser.parse_args()
    summarize_run(args.db, args.run_id)


if __name__ == "__main__":
    main()
