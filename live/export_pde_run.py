"""Export a persisted PDE run from SQLite into CSV files."""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from typing import Iterable

TABLES: tuple[str, ...] = (
    "runs",
    "orders",
    "fills",
    "positions",
    "pnl",
    "market_data",
    "account_states",
)


def _latest_run_id(conn: sqlite3.Connection) -> str | None:
    row = conn.execute(
        "SELECT run_id FROM runs ORDER BY started_at_ns DESC LIMIT 1"
    ).fetchone()
    return row[0] if row else None


def _rows_for_table(conn: sqlite3.Connection, table: str, run_id: str) -> tuple[list[str], Iterable[sqlite3.Row]]:
    if table == "runs":
        query = "SELECT * FROM runs WHERE run_id = ?"
    else:
        query = f"SELECT * FROM {table} WHERE run_id = ? ORDER BY ts_ns"  # nosec B608

    cursor = conn.execute(query, (run_id,))
    cols = [d[0] for d in cursor.description]
    return cols, cursor.fetchall()


def export_run(db_path: str, run_id: str | None, output_dir: str) -> str:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        selected_run_id = run_id or _latest_run_id(conn)
        if not selected_run_id:
            raise RuntimeError("No run found in database")

        out_dir = os.path.join(output_dir, selected_run_id)
        os.makedirs(out_dir, exist_ok=True)

        for table in TABLES:
            cols, rows = _rows_for_table(conn, table, selected_run_id)
            out_path = os.path.join(out_dir, f"{table}.csv")
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                for row in rows:
                    writer.writerow([row[c] for c in cols])
            print(f"✅ Exported {table}: {len(rows)} rows -> {out_path}")

            latest_path = os.path.join(output_dir, f"{table}.csv")
            with open(latest_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                for row in rows:
                    writer.writerow([row[c] for c in cols])

        return selected_run_id
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export PDE persistence run to CSV")
    parser.add_argument("--db", default="data/pde/pde_runs.sqlite3", help="SQLite DB path")
    parser.add_argument("--run-id", default=None, help="Run ID to export (default: latest)")
    parser.add_argument("--out", default="data/pde/exports", help="Output directory")
    args = parser.parse_args()

    run_id = export_run(db_path=args.db, run_id=args.run_id, output_dir=args.out)
    print(f"\n🎯 Export complete for run_id={run_id}")


if __name__ == "__main__":
    main()
