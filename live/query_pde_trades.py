#!/usr/bin/env python3
"""Query and display PDE trades from SQLite persistence.

Usage:
    python live/query_pde_trades.py --db data/pde/pde_runs.sqlite3
    python live/query_pde_trades.py --db data/pde/pde_runs.sqlite3 --run-id <RUN_ID>
    python live/query_pde_trades.py --db data/pde/pde_runs.sqlite3 --positions
    python live/query_pde_trades.py --db data/pde/pde_runs.sqlite3 --pnl-history
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from typing import Any


def format_ts(ns: int | None) -> str:
    if ns is None:
        return "—"
    return datetime.fromtimestamp(ns / 1_000_000_000).strftime("%H:%M:%S")


def get_latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id FROM runs ORDER BY started_at_ns DESC LIMIT 1"
    ).fetchone()
    return row["run_id"] if row else None


def show_positions(conn: sqlite3.Connection, run_id: str) -> None:
    """Show all position events."""
    rows = conn.execute(
        """
        SELECT ts_iso, event_type, token, phase, instrument_id,
               position_size, avg_price, unrealized_pnl, realized_pnl
        FROM positions
        WHERE run_id = ?
        ORDER BY ts_ns DESC
        LIMIT 20
        """,
        (run_id,),
    ).fetchall()

    if not rows:
        print("\n[EMPTY] No position records found")
        return

    print(f"\n[POSITIONS] Position Events (latest 20):")
    print("-" * 100)
    print(f"{'Time':<10} {'Event':<12} {'Token':<6} {'Phase':<6} {'Size':>10} {'Avg Px':>10} {'Unreal PnL':>12} {'Real PnL':>12}")
    print("-" * 100)
    for r in rows:
        print(f"{r['ts_iso'][11:19] if len(r['ts_iso'])>19 else r['ts_iso']:<10} "
              f"{r['event_type']:<12} {r['token']:<6} {r['phase']:<6} "
              f"{r['position_size'] or 0:>10.4f} {r['avg_price'] or 0:>10.4f} "
              f"{r['unrealized_pnl'] or 0:>+12.4f} {r['realized_pnl'] or 0:>+12.4f}")


def show_pnl_history(conn: sqlite3.Connection, run_id: str) -> None:
    """Show PnL snapshot history."""
    rows = conn.execute(
        """
        SELECT ts_iso, phase, unrealized_pnl, realized_pnl, total_pnl
        FROM pnl
        WHERE run_id = ?
        ORDER BY ts_ns DESC
        LIMIT 30
        """,
        (run_id,),
    ).fetchall()

    if not rows:
        print("\n[EMPTY] No PnL records found")
        return

    print(f"\n[PNL] PnL History (latest 30 snapshots):")
    print("-" * 80)
    print(f"{'Time':<10} {'Phase':<6} {'Unreal PnL':>15} {'Real PnL':>15} {'Total':>15}")
    print("-" * 80)
    for r in rows:
        total = r['total_pnl'] or (r['unrealized_pnl'] or 0) + (r['realized_pnl'] or 0)
        print(f"{r['ts_iso'][11:19] if len(r['ts_iso'])>19 else r['ts_iso']:<10} "
              f"{r['phase']:<6} {r['unrealized_pnl'] or 0:>+15.4f} "
              f"{r['realized_pnl'] or 0:>+15.4f} {total:>+15.4f}")


def show_orders(conn: sqlite3.Connection, run_id: str) -> None:
    """Show order events."""
    rows = conn.execute(
        """
        SELECT ts_iso, event_type, client_order_id, instrument_id, side, quantity, price, status
        FROM orders
        WHERE run_id = ?
        ORDER BY ts_ns DESC
        LIMIT 20
        """,
        (run_id,),
    ).fetchall()

    if not rows:
        print("\n[EMPTY] No order records found")
        return

    print(f"\n[ORDERS] Order Events (latest 20):")
    print("-" * 110)
    print(f"{'Time':<10} {'Event':<12} {'Order ID':<26} {'Instrument':<50} {'Side':<6} {'Qty':>10} {'Price':>10}")
    print("-" * 110)
    for r in rows:
        inst_short = r['instrument_id'][:48] if r['instrument_id'] else '—'
        print(f"{r['ts_iso'][11:19] if len(r['ts_iso'])>19 else r['ts_iso']:<10} "
              f"{r['event_type']:<12} {r['client_order_id'] or '—':<26} "
              f"{inst_short:<50} {r['side'] or '—':<6} "
              f"{r['quantity'] or 0:>10.4f} {r['price'] or 0:>10.4f}")


def show_fills(conn: sqlite3.Connection, run_id: str) -> None:
    """Show fill events."""
    rows = conn.execute(
        """
        SELECT ts_iso, client_order_id, instrument_id, side, quantity, price, fee
        FROM fills
        WHERE run_id = ?
        ORDER BY ts_ns DESC
        LIMIT 20
        """,
        (run_id,),
    ).fetchall()

    if not rows:
        print("\n[EMPTY] No fill records found")
        return

    print(f"\n[FILLS] Fill Events (latest 20):")
    print("-" * 100)
    print(f"{'Time':<10} {'Order ID':<26} {'Instrument':<40} {'Side':<6} {'Qty':>10} {'Price':>10} {'Fee':>10}")
    print("-" * 100)
    for r in rows:
        inst_short = r['instrument_id'][:38] if r['instrument_id'] else '—'
        print(f"{r['ts_iso'][11:19] if len(r['ts_iso'])>19 else r['ts_iso']:<10} "
              f"{r['client_order_id'] or '—':<26} {inst_short:<40} "
              f"{r['side'] or '—':<6} {r['quantity'] or 0:>10.4f} "
              f"{r['price'] or 0:>10.4f} {r['fee'] or 0:>10.4f}")


def show_run_summary(conn: sqlite3.Connection, run_id: str) -> None:
    """Show overall run summary."""
    # Run info
    row = conn.execute(
        "SELECT * FROM runs WHERE run_id = ?",
        (run_id,),
    ).fetchone()

    if not row:
        print(f"[ERROR] Run not found: {run_id}")
        return

    print(f"\n{'='*80}")
    print(f"[SUMMARY] Run Summary: {run_id}")
    print(f"{'='*80}")
    print(f"Started:  {row['started_at_iso']}")
    if row['ended_at_iso']:
        print(f"Ended:    {row['ended_at_iso']}")
    print(f"Mode:     {row['mode']}")
    print(f"Strategy: {row['strategy']}")

    # Metadata
    if row['metadata_json']:
        import json
        try:
            meta = json.loads(row['metadata_json'])
            print(f"\nConfig:")
            for k, v in meta.items():
                print(f"  {k}: {v}")
        except:
            pass

    # Counts
    stats = conn.execute(
        """
        SELECT 
            (SELECT COUNT(*) FROM orders WHERE run_id = ?) as orders,
            (SELECT COUNT(*) FROM fills WHERE run_id = ?) as fills,
            (SELECT COUNT(DISTINCT token) FROM positions WHERE run_id = ?) as tokens,
            (SELECT COUNT(*) FROM positions WHERE run_id = ?) as position_events,
            (SELECT COUNT(*) FROM market_data WHERE run_id = ?) as market_ticks
        """,
        (run_id, run_id, run_id, run_id, run_id),
    ).fetchone()

    print(f"\nStatistics:")
    print(f"  Orders:         {stats['orders']}")
    print(f"  Fills:          {stats['fills']}")
    print(f"  Position Events:{stats['position_events']}")
    print(f"  Tokens Traded:  {stats['tokens']}")
    print(f"  Market Ticks:   {stats['market_ticks']}")

    # PnL Summary
    pnl = conn.execute(
        """
        SELECT 
            SUM(realized_pnl) as total_realized,
            SUM(unrealized_pnl) as total_unrealized,
            COUNT(*) as snapshot_count
        FROM pnl
        WHERE run_id = ?
        """,
        (run_id,),
    ).fetchone()

    total = (pnl['total_realized'] or 0) + (pnl['total_unrealized'] or 0)
    print(f"\n[PNL] PnL Summary:")
    print(f"  Realized:   {pnl['total_realized'] or 0:+.4f}")
    print(f"  Unrealized: {pnl['total_unrealized'] or 0:+.4f}")
    print(f"  Total:      {total:+.4f}")
    print(f"  Snapshots:  {pnl['snapshot_count']}")

    # Summary from run end
    if row['summary_json']:
        import json
        try:
            summary = json.loads(row['summary_json'])
            print(f"\nFinal Summary:")
            for k, v in summary.items():
                print(f"  {k}: {v}")
        except:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Query PDE trades from SQLite")
    parser.add_argument("--db", default="data/pde/pde_runs.sqlite3", help="SQLite DB path")
    parser.add_argument("--run-id", default=None, help="Run ID (default: latest)")
    parser.add_argument("--positions", action="store_true", help="Show position events")
    parser.add_argument("--pnl-history", action="store_true", help="Show PnL history")
    parser.add_argument("--orders", action="store_true", help="Show order events")
    parser.add_argument("--fills", action="store_true", help="Show fill events")
    parser.add_argument("--all", action="store_true", help="Show all details")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    run_id = args.run_id or get_latest_run_id(conn)
    if not run_id:
        print("[ERROR] No runs found in database")
        sys.exit(1)

    # Default: show summary
    if not any([args.positions, args.pnl_history, args.orders, args.fills]):
        args.all = True

    show_run_summary(conn, run_id)

    if args.all or args.positions:
        show_positions(conn, run_id)

    if args.all or args.pnl_history:
        show_pnl_history(conn, run_id)

    if args.all or args.orders:
        show_orders(conn, run_id)

    if args.all or args.fills:
        show_fills(conn, run_id)

    conn.close()
    print(f"\n{'='*80}")
    print("[DONE] Query complete")


if __name__ == "__main__":
    main()
