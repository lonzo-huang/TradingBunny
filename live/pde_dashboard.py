"""PDE SQLite Database Web Dashboard

Simple Flask-based web interface for viewing PDE strategy trading data.

Usage:
    python live/pde_dashboard.py --db data/pde/pde_runs.sqlite3
    
Then open http://localhost:5000 in your browser.
"""

import argparse
import sqlite3
import json
from datetime import datetime
from typing import Any
from pathlib import Path

from flask import Flask, render_template_string, g

app = Flask(__name__)
app.config['PROPAGATE_EXCEPTIONS'] = True
DB_PATH: str = "data/pde/pde_runs.sqlite3"


@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all exceptions and return detailed error page."""
    import traceback
    error_msg = f"""
    <h1>500 Internal Server Error</h1>
    <pre>{traceback.format_exc()}</pre>
    """
    return error_msg, 500


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception: Any) -> None:
    """Close database connection."""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def query_db(query: str, args: tuple = (), one: bool = False) -> list | dict | None:
    """Execute query and return results."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    if one:
        return rv[0] if rv else None
    return rv


# HTML Templates
BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>PDE Trading Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            line-height: 1.6;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 20px;
            margin-bottom: 20px;
        }
        h1 { color: #58a6ff; font-size: 24px; }
        h2 { color: #79c0ff; font-size: 18px; margin: 20px 0 10px; }
        .nav {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .nav a {
            background: #21262d;
            color: #c9d1d9;
            padding: 8px 16px;
            text-decoration: none;
            border-radius: 6px;
            border: 1px solid #30363d;
            transition: all 0.2s;
        }
        .nav a:hover, .nav a.active {
            background: #58a6ff;
            color: #0d1117;
        }
        .card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-box {
            background: #21262d;
            padding: 15px;
            border-radius: 6px;
            border-left: 3px solid #58a6ff;
        }
        .stat-label { font-size: 12px; color: #8b949e; text-transform: uppercase; }
        .stat-value { font-size: 20px; font-weight: 600; margin-top: 5px; }
        .positive { color: #3fb950; }
        .negative { color: #f85149; }
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        th, td {
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }
        th {
            background: #21262d;
            color: #79c0ff;
            font-weight: 500;
            position: sticky;
            top: 0;
        }
        tr:hover { background: #1c2128; }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 500;
        }
        .badge-a { background: #1f6feb; color: white; }
        .badge-b { background: #8957e5; color: white; }
        .badge-up { background: #238636; color: white; }
        .badge-down { background: #da3633; color: white; }
        .badge-filled { background: #3fb950; color: white; }
        .badge-submitted { background: #d29922; color: black; }
        pre {
            background: #0d1117;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 11px;
            max-height: 200px;
        }
        .run-selector {
            margin-bottom: 20px;
        }
        select {
            background: #21262d;
            color: #c9d1d9;
            border: 1px solid #30363d;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 14px;
        }
        .chart-container {
            height: 300px;
            margin-top: 20px;
        }
        .empty-state {
            text-align: center;
            padding: 40px;
            color: #8b949e;
        }
        a { color: #58a6ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <header>
        <div class="container">
            <h1>[PDE] Trading Dashboard</h1>
            <div class="nav">
                <a href="/" class="{% if active_page == 'runs' %}active{% endif %}">Runs</a>
                {% if run_id %}
                <a href="/run/{{ run_id }}" class="{% if active_page == 'overview' %}active{% endif %}">Overview</a>
                <a href="/run/{{ run_id }}/orders" class="{% if active_page == 'orders' %}active{% endif %}">Orders</a>
                <a href="/run/{{ run_id }}/fills" class="{% if active_page == 'fills' %}active{% endif %}">Fills</a>
                <a href="/run/{{ run_id }}/positions" class="{% if active_page == 'positions' %}active{% endif %}">Positions</a>
                <a href="/run/{{ run_id }}/pnl" class="{% if active_page == 'pnl' %}active{% endif %}">PnL</a>
                {% endif %}
            </div>
        </div>
    </header>
    <div class="container">
        {{ content | safe }}
    </div>
</body>
</html>
"""


def format_ts(ts_iso: str | None) -> str:
    """Format timestamp for display."""
    if not ts_iso:
        return "-"
    try:
        dt = datetime.fromisoformat(ts_iso.replace('Z', '+00:00'))
        return dt.strftime('%H:%M:%S')
    except:
        return ts_iso[:19]


def format_number(n: float | None, decimals: int = 2) -> str:
    """Format number for display."""
    if n is None:
        return "-"
    return f"{n:.{decimals}f}"


@app.route("/")
def index() -> str:
    """List all runs."""
    runs = query_db("""
        SELECT run_id, started_at, finished_at, mode, strategy,
               (SELECT COUNT(*) FROM orders WHERE orders.run_id = runs.run_id) as order_count,
               (SELECT COUNT(*) FROM fills WHERE fills.run_id = runs.run_id) as fill_count,
               (SELECT COUNT(*) FROM positions WHERE positions.run_id = runs.run_id) as position_count
        FROM runs
        ORDER BY started_at DESC
    """)
    
    content = """
        <h2>Trading Runs</h2>
        <div class="card">
            <table>
                <tr>
                    <th>Run ID</th>
                    <th>Started</th>
                    <th>Status</th>
                    <th>Mode</th>
                    <th>Orders</th>
                    <th>Fills</th>
                    <th>Positions</th>
                    <th>Actions</th>
                </tr>
    """
    
    for run in runs:
        status = "Finished" if run['finished_at'] else "Running"
        status_badge = f'<span class="badge badge-filled">{status}</span>' if status == "Finished" else f'<span class="badge badge-submitted">{status}</span>'
        
        content += f"""
                <tr>
                    <td><code>{run['run_id'][:50]}...</code></td>
                    <td>{format_ts(run['started_at'])}</td>
                    <td>{status_badge}</td>
                    <td>{run['mode']}</td>
                    <td>{run['order_count']}</td>
                    <td>{run['fill_count']}</td>
                    <td>{run['position_count']}</td>
                    <td><a href="/run/{run['run_id']}">View Details →</a></td>
                </tr>
        """
    
    content += "</table></div>"
    
    return render_template_string(BASE_TEMPLATE, content=content, active_page="runs", run_id=None)


@app.route("/run/<run_id>")
def run_overview(run_id: str) -> str:
    """Show run overview."""
    run = query_db("SELECT * FROM runs WHERE run_id = ?", (run_id,), one=True)
    if not run:
        return render_template_string(BASE_TEMPLATE, content="<div class='card'><h2>Run not found</h2></div>", active_page="overview", run_id=None)
    
    # Get summary stats
    orders = query_db("SELECT COUNT(*) as cnt, side FROM orders WHERE run_id = ? GROUP BY side", (run_id,))
    fills = query_db("SELECT COUNT(*) as cnt, SUM(quantity) as qty, SUM(quantity * price) as notional FROM fills WHERE run_id = ?", (run_id,), one=True)
    
    # Get PnL by phase
    pnl_data = query_db("""
        SELECT phase, 
               SUM(realized_pnl) as realized,
               SUM(unrealized_pnl) as unrealized
        FROM pnl 
        WHERE run_id = ? AND event_type = 'position_closed'
        GROUP BY phase
    """, (run_id,))
    
    content = f"""
        <h2>Run Overview: <code>{run_id[:40]}...</code></h2>
        
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">Started</div>
                <div class="stat-value">{format_ts(run['started_at'])}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Status</div>
                <div class="stat-value">{'Finished' if run['finished_at'] else 'Running'}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Mode</div>
                <div class="stat-value">{run['mode']}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Total Orders</div>
                <div class="stat-value">{sum(o['cnt'] for o in orders) if orders else 0}</div>
            </div>
        </div>
        
        <h3>PnL by Phase</h3>
        <div class="card">
            <table>
                <tr>
                    <th>Phase</th>
                    <th>Realized PnL</th>
                    <th>Unrealized PnL</th>
                    <th>Total</th>
                </tr>
    """
    
    total_pnl = 0
    for pnl in pnl_data:
        phase_total = (pnl['realized'] or 0) + (pnl['unrealized'] or 0)
        total_pnl += phase_total
        phase_class = "positive" if phase_total >= 0 else "negative"
        content += f"""
                <tr>
                    <td><span class="badge badge-{pnl['phase'].lower()}">Phase {pnl['phase']}</span></td>
                    <td class="{'positive' if (pnl['realized'] or 0) >= 0 else 'negative'}">{format_number(pnl['realized'])}</td>
                    <td class="{'positive' if (pnl['unrealized'] or 0) >= 0 else 'negative'}">{format_number(pnl['unrealized'])}</td>
                    <td class="{phase_class}">{format_number(phase_total)}</td>
                </tr>
        """
    
    content += f"""
            </table>
            <div style="margin-top: 20px; text-align: right; font-size: 18px;">
                <strong>Total PnL: <span class="{'positive' if total_pnl >= 0 else 'negative'}">{format_number(total_pnl)} USDC</span></strong>
            </div>
        </div>
        
        <h3>Metadata</h3>
        <div class="card">
            <pre>{json.dumps(json.loads(run['metadata'] or '{}'), indent=2)}</pre>
        </div>
    """
    
    return render_template_string(BASE_TEMPLATE, content=content, active_page="overview", run_id=run_id)


@app.route("/run/<run_id>/orders")
def run_orders(run_id: str) -> str:
    """Show orders for a run."""
    orders = query_db("""
        SELECT * FROM orders 
        WHERE run_id = ? 
        ORDER BY ts_iso DESC 
        LIMIT 100
    """, (run_id,))
    
    content = f"""
        <h2>Orders</h2>
        <div class="card">
            <table>
                <tr>
                    <th>Time</th>
                    <th>Type</th>
                    <th>Side</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Status</th>
                    <th>Client Order ID</th>
                </tr>
    """
    
    for order in orders:
        status_class = "badge-filled" if order['status'] == 'FILLED' else "badge-submitted"
        content += f"""
                <tr>
                    <td>{format_ts(order['ts_iso'])}</td>
                    <td>{order['event_type']}</td>
                    <td><span class="badge badge-{order['side'].lower() if order['side'] else 'a'}">{order['side']}</span></td>
                    <td>{format_number(order['quantity'])}</td>
                    <td>{format_number(order['price'])}</td>
                    <td><span class="badge {status_class}">{order['status']}</span></td>
                    <td><code>{order['client_order_id'][:30] if order['client_order_id'] else '-'}</code></td>
                </tr>
        """
    
    content += "</table></div>"
    
    return render_template_string(BASE_TEMPLATE, content=content, active_page="orders", run_id=run_id)


@app.route("/run/<run_id>/fills")
def run_fills(run_id: str) -> str:
    """Show fills for a run."""
    fills = query_db("""
        SELECT fills.*, orders.side as order_side
        FROM fills 
        LEFT JOIN orders ON fills.client_order_id = orders.client_order_id AND fills.run_id = orders.run_id
        WHERE fills.run_id = ? 
        ORDER BY fills.ts_iso DESC 
        LIMIT 100
    """, (run_id,))
    
    content = f"""
        <h2>Fills</h2>
        <div class="card">
            <table>
                <tr>
                    <th>Time</th>
                    <th>Side</th>
                    <th>Quantity</th>
                    <th>Price</th>
                    <th>Fee</th>
                    <th>Notional</th>
                    <th>Trade ID</th>
                </tr>
    """
    
    total_notional = 0
    for fill in fills:
        notional = (fill['quantity'] or 0) * (fill['price'] or 0)
        total_notional += notional
        side = fill['order_side'] or 'BUY'
        content += f"""
                <tr>
                    <td>{format_ts(fill['ts_iso'])}</td>
                    <td><span class="badge badge-{side.lower()}">{side}</span></td>
                    <td>{format_number(fill['quantity'])}</td>
                    <td>{format_number(fill['price'])}</td>
                    <td>{format_number(fill['fee'])}</td>
                    <td>{format_number(notional)}</td>
                    <td><code>{fill['trade_id'][:20] if fill['trade_id'] else '-'}</code></td>
                </tr>
        """
    
    content += f"""
            </table>
            <div style="margin-top: 20px; text-align: right;">
                <strong>Total Notional: {format_number(total_notional)} USDC</strong>
            </div>
        </div>
    """
    
    return render_template_string(BASE_TEMPLATE, content=content, active_page="fills", run_id=run_id)


@app.route("/run/<run_id>/positions")
def run_positions(run_id: str) -> str:
    """Show positions for a run."""
    positions = query_db("""
        SELECT * FROM positions 
        WHERE run_id = ? 
        ORDER BY ts_iso DESC 
        LIMIT 100
    """, (run_id,))
    
    content = f"""
        <h2>Positions</h2>
        <div class="card">
            <table>
                <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Token</th>
                    <th>Phase</th>
                    <th>Size</th>
                    <th>Avg Price</th>
                    <th>Realized PnL</th>
                    <th>Unrealized PnL</th>
                </tr>
    """
    
    for pos in positions:
        realized_class = "positive" if (pos['realized_pnl'] or 0) >= 0 else "negative"
        unrealized_class = "positive" if (pos['unrealized_pnl'] or 0) >= 0 else "negative"
        content += f"""
                <tr>
                    <td>{format_ts(pos['ts_iso'])}</td>
                    <td>{pos['event_type']}</td>
                    <td><span class="badge badge-{pos['token']}">{pos['token'].upper()}</span></td>
                    <td><span class="badge badge-{pos['phase'].lower()}">Phase {pos['phase']}</span></td>
                    <td>{format_number(pos['position_size'])}</td>
                    <td>{format_number(pos['avg_price'])}</td>
                    <td class="{realized_class}">{format_number(pos['realized_pnl'])}</td>
                    <td class="{unrealized_class}">{format_number(pos['unrealized_pnl'])}</td>
                </tr>
        """
    
    content += "</table></div>"
    
    return render_template_string(BASE_TEMPLATE, content=content, active_page="positions", run_id=run_id)


@app.route("/run/<run_id>/pnl")
def run_pnl(run_id: str) -> str:
    """Show PnL chart for a run."""
    pnl_data = query_db("""
        SELECT ts_iso, phase, realized_pnl, unrealized_pnl, total_pnl
        FROM pnl 
        WHERE run_id = ?
        ORDER BY ts_iso ASC
    """, (run_id,))
    
    # Prepare data for chart
    timestamps = []
    realized = []
    unrealized = []
    total = []
    
    for row in pnl_data:
        timestamps.append(format_ts(row['ts_iso']))
        realized.append(row['realized_pnl'] or 0)
        unrealized.append(row['unrealized_pnl'] or 0)
        total.append(row['total_pnl'] or 0)
    
    chart_data = {
        'labels': timestamps,
        'realized': realized,
        'unrealized': unrealized,
        'total': total
    }
    
    content = f"""
        <h2>PnL Over Time</h2>
        
        <div class="card">
            <canvas id="pnlChart" class="chart-container"></canvas>
        </div>
        
        <h3>Raw Data</h3>
        <div class="card">
            <table>
                <tr>
                    <th>Time</th>
                    <th>Phase</th>
                    <th>Realized</th>
                    <th>Unrealized</th>
                    <th>Total</th>
                </tr>
    """
    
    for row in pnl_data[-50:]:  # Show last 50 entries
        total_val = (row['realized_pnl'] or 0) + (row['unrealized_pnl'] or 0)
        content += f"""
                <tr>
                    <td>{format_ts(row['ts_iso'])}</td>
                    <td><span class="badge badge-{row['phase'].lower()}">Phase {row['phase']}</span></td>
                    <td class="{'positive' if (row['realized_pnl'] or 0) >= 0 else 'negative'}">{format_number(row['realized_pnl'])}</td>
                    <td class="{'positive' if (row['unrealized_pnl'] or 0) >= 0 else 'negative'}">{format_number(row['unrealized_pnl'])}</td>
                    <td class="{'positive' if total_val >= 0 else 'negative'}">{format_number(total_val)}</td>
                </tr>
        """
    
    content += f"""
            </table>
        </div>
        
        <script>
            const ctx = document.getElementById('pnlChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {chart_data['labels']},
                    datasets: [
                        {{
                            label: 'Realized PnL',
                            data: {chart_data['realized']},
                            borderColor: '#3fb950',
                            backgroundColor: 'rgba(63, 185, 80, 0.1)',
                            fill: true
                        }},
                        {{
                            label: 'Unrealized PnL',
                            data: {chart_data['unrealized']},
                            borderColor: '#d29922',
                            backgroundColor: 'rgba(210, 153, 34, 0.1)',
                            fill: true
                        }},
                        {{
                            label: 'Total PnL',
                            data: {chart_data['total']},
                            borderColor: '#58a6ff',
                            backgroundColor: 'rgba(88, 166, 255, 0.1)',
                            fill: true
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            labels: {{ color: '#c9d1d9' }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            ticks: {{ color: '#8b949e' }},
                            grid: {{ color: '#30363d' }}
                        }},
                        y: {{
                            ticks: {{ color: '#8b949e' }},
                            grid: {{ color: '#30363d' }}
                        }}
                    }}
                }}
            }});
        </script>
    """
    
    return render_template_string(BASE_TEMPLATE, content=content, active_page="pnl", run_id=run_id)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="PDE Trading Dashboard")
    parser.add_argument("--db", default="data/pde/pde_runs.sqlite3", help="Path to SQLite database")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()
    
    global DB_PATH
    DB_PATH = args.db
    
    print(f"[START] PDE Dashboard starting")
    print(f"[DB] Database: {DB_PATH}")
    print(f"[URL] http://{args.host}:{args.port}")
    print()
    print("Press Ctrl+C to stop")
    
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
