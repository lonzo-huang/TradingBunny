"""分析未成交订单原因

Usage:
    python live/analyze_unfilled_orders.py <run_id>

Example:
    python live/analyze_unfilled_orders.py pde_002_20260419_114908_df38cd5a
"""

import argparse
import sqlite3
from pathlib import Path


def analyze_orders(db_path: str, run_id: str) -> None:
    """Analyze unfilled orders for a run."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"订单分析 - Run ID: {run_id}")
    print(f"{'='*60}")
    
    # 1. 总体统计
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'FILLED' THEN 1 ELSE 0 END) as filled,
            SUM(CASE WHEN status = 'REJECTED' THEN 1 ELSE 0 END) as rejected,
            SUM(CASE WHEN status = 'CANCELED' THEN 1 ELSE 0 END) as canceled,
            SUM(CASE WHEN status IN ('INITIALIZED', 'SUBMITTED', 'ACCEPTED') THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status IS NULL OR status NOT IN ('FILLED', 'REJECTED', 'CANCELED', 'INITIALIZED', 'SUBMITTED', 'ACCEPTED') THEN 1 ELSE 0 END) as other
        FROM orders WHERE run_id = ?
    """, (run_id,))
    row = cur.fetchone()
    
    print(f"\n[订单状态分布]")
    print(f"  Total Orders:    {row['total']}")
    print(f"  Filled:          {row['filled']} ({row['filled']/row['total']*100:.1f}%)")
    print(f"  Rejected:        {row['rejected']} ({row['rejected']/row['total']*100:.1f}%)")
    print(f"  Canceled:        {row['canceled']} ({row['canceled']/row['total']*100:.1f}%)")
    print(f"  Pending:         {row['pending']} ({row['pending']/row['total']*100:.1f}%)")
    print(f"  Other/Unknown:   {row['other']} ({row['other']/row['total']*100:.1f}%)")
    
    # 2. 按事件类型统计
    cur.execute("""
        SELECT event_type, status, COUNT(*) as cnt
        FROM orders 
        WHERE run_id = ?
        GROUP BY event_type, status
        ORDER BY event_type, cnt DESC
    """, (run_id,))
    
    print(f"\n[按事件类型和状态统计]")
    print(f"  {'Event Type':<20} {'Status':<12} {'Count':>8}")
    print(f"  {'-'*42}")
    for row in cur.fetchall():
        print(f"  {row['event_type']:<20} {row['status'] or 'NULL':<12} {row['cnt']:>8}")
    
    # 3. 查看具体的未成交订单
    cur.execute("""
        SELECT ts_iso, event_type, side, status, client_order_id, payload_json
        FROM orders 
        WHERE run_id = ? AND status != 'FILLED'
        ORDER BY ts_iso DESC
        LIMIT 20
    """, (run_id,))
    
    print(f"\n[最近的未成交订单 (Top 20)]")
    print(f"  {'Time':<12} {'Event':<15} {'Side':<6} {'Status':<12} {'Order ID'}")
    print(f"  {'-'*80}")
    for row in cur.fetchall():
        ts = row['ts_iso'][:19] if row['ts_iso'] else 'N/A'
        oid = row['client_order_id'][:30] if row['client_order_id'] else 'N/A'
        print(f"  {ts:<12} {row['event_type']:<15} {row['side'] or '-':<6} {row['status'] or 'NULL':<12} {oid}")
    
    # 4. 查看 fills 详情
    cur.execute("""
        SELECT COUNT(*) as fill_count, SUM(quantity) as total_qty, AVG(price) as avg_price
        FROM fills 
        WHERE run_id = ?
    """, (run_id,))
    row = cur.fetchone()
    
    print(f"\n[成交统计]")
    print(f"  Fill Records:    {row['fill_count']}")
    print(f"  Total Qty:       {row['total_qty']:.4f}")
    print(f"  Avg Price:       {row['avg_price']:.4f}")
    
    conn.close()
    print(f"\n{'='*60}")
    print("分析完成")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Analyze unfilled orders")
    parser.add_argument("run_id", help="Run ID to analyze")
    parser.add_argument("--db", default="data/pde/pde_runs.sqlite3", help="Database path")
    args = parser.parse_args()
    
    analyze_orders(args.db, args.run_id)


if __name__ == "__main__":
    main()
