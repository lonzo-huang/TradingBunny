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
                <a href="/run/{{ run_id }}/trades" class="{% if active_page == 'trades' %}active{% endif %}">Trades</a>
                <a href="/run/{{ run_id }}/rounds" class="{% if active_page == 'rounds' %}active{% endif %}">Rounds</a>
                <a href="/run/{{ run_id }}/pnl" class="{% if active_page == 'pnl' %}active{% endif %}">PnL</a>
                <a href="/run/{{ run_id }}/exit_stats" class="{% if active_page == 'exit_stats' %}active{% endif %}">Exit Stats</a>
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


EXIT_REASON_LABELS = {
    'exit_ev_up': 'EV信号反转',
    'exit_ev_down': 'EV信号反转',
    'exit_tp_up': '止盈',
    'exit_tp_down': '止盈',
    'exit_sl_up': '止损',
    'exit_sl_down': '止损',
    'close_up': '轮次强平',
    'close_down': '轮次强平',
}


def human_exit_reason(label: str | None) -> str:
    """Map internal label to human-readable Chinese reason."""
    if not label:
        return 'N/A'
    if label in EXIT_REASON_LABELS:
        return EXIT_REASON_LABELS[label]
    if label.startswith('phase_a_timeout'):
        return 'Phase A超时'
    return label


def extract_exit_reason_label(close_req_payload: str | None) -> str | None:
    """Extract raw label string from position_close_requested payload."""
    if not close_req_payload:
        return None
    try:
        data = json.loads(close_req_payload)
        label = data.get('label')
        if label:
            return str(label)
        payload = data.get('payload') if isinstance(data.get('payload'), dict) else None
        if payload and payload.get('label'):
            return str(payload['label'])
    except Exception:
        pass
    return None


def parse_close_payload(close_payload_json: str | None) -> dict:
    """Parse position_closed payload and return dict with avg_px_open, avg_px_close, duration_ns."""
    result = {'avg_px_open': None, 'avg_px_close': None, 'duration_ns': None, 'realized_pnl_str': None}
    if not close_payload_json:
        return result
    try:
        data = json.loads(close_payload_json)
        result['avg_px_open'] = data.get('avg_px_open')
        result['avg_px_close'] = data.get('avg_px_close')
        result['duration_ns'] = data.get('duration_ns')
        result['realized_pnl_str'] = data.get('realized_pnl')
    except Exception:
        pass
    return result


def parse_entry_context(entry_context_json: str | None) -> dict:
    """Parse entry_context_json and return dict with ev, delta_pct, btc_price, label."""
    result = {'ev': None, 'delta_pct': None, 'btc_price': None, 'label': None}
    if not entry_context_json:
        return result
    try:
        data = json.loads(entry_context_json)
        result['ev'] = data.get('ev')
        result['delta_pct'] = data.get('delta_pct')
        result['btc_price'] = data.get('btc_price')
        result['label'] = data.get('label')
    except Exception:
        pass
    return result


def fills_side_label(side) -> str:
    """Map numeric fills.side to string."""
    if side == 1 or side == '1':
        return 'BUY'
    if side == 2 or side == '2':
        return 'SELL'
    return str(side) if side is not None else '-'


@app.route("/")
def index() -> str:
    """List all runs."""
    runs = query_db("""
        SELECT run_id, started_at_iso, ended_at_iso, mode, strategy,
               (SELECT COUNT(*) FROM orders WHERE orders.run_id = runs.run_id) as order_count,
               (SELECT COUNT(*) FROM fills WHERE fills.run_id = runs.run_id) as fill_count,
               (SELECT COUNT(*) FROM positions WHERE positions.run_id = runs.run_id) as position_count,
               (
                   SELECT COALESCE(SUM(realized_pnl), 0)
                   FROM positions p2
                   WHERE p2.run_id = runs.run_id
                     AND p2.event_type = 'position_closed'
               ) as total_pnl,
               (
                   SELECT COUNT(*)
                   FROM orders o2
                   WHERE o2.run_id = runs.run_id
                     AND COALESCE(o2.status, '') NOT IN ('FILLED', 'CANCELED', 'REJECTED')
               ) as unfilled_order_count
        FROM runs
        ORDER BY started_at_ns DESC
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
                    <th>Unfilled</th>
                    <th>Positions</th>
                    <th>Total PnL</th>
                    <th>Actions</th>
                </tr>
    """

    for run in runs:
        status = "Finished" if run['ended_at_iso'] else "Running"
        status_badge = (
            f'<span class="badge badge-filled">{status}</span>'
            if status == "Finished"
            else f'<span class="badge badge-submitted">{status}</span>'
        )

        unfilled = run['unfilled_order_count'] or 0
        total_pnl = run['total_pnl'] or 0.0
        pnl_class = 'positive' if total_pnl >= 0 else 'negative'

        run_id_str = run['run_id']
        run_id_display = run_id_str[:50] + '...' if len(run_id_str) > 50 else run_id_str

        content += f"""
                <tr>
                    <td><code>{run_id_display}</code></td>
                    <td>{format_ts(run['started_at_iso'])}</td>
                    <td>{status_badge}</td>
                    <td>{run['mode']}</td>
                    <td>{run['order_count']}</td>
                    <td>{run['fill_count']}</td>
                    <td class="{'negative' if unfilled > 0 else ''}">{unfilled}</td>
                    <td>{run['position_count']}</td>
                    <td class="{pnl_class}">{format_number(total_pnl)} USDC</td>
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

    # Get PnL by phase — only from position_closed (realized), no unrealized sum
    pnl_data = query_db("""
        SELECT phase,
               SUM(realized_pnl) as realized
        FROM positions
        WHERE run_id = ? AND event_type = 'position_closed'
        GROUP BY phase
    """, (run_id,))

    # Get positions by phase
    pos_by_phase = query_db("""
        SELECT phase,
               COUNT(*) as pos_count,
               SUM(CASE WHEN event_type = 'position_requested' THEN 1 ELSE 0 END) as opened,
               SUM(CASE WHEN event_type = 'position_closed' THEN 1 ELSE 0 END) as closed
        FROM positions
        WHERE run_id = ?
        GROUP BY phase
    """, (run_id,))

    run_id_display = run_id[:40] + '...' if len(run_id) > 40 else run_id

    content = f"""
        <h2>Run Overview: <code>{run_id_display}</code></h2>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">Started</div>
                <div class="stat-value">{format_ts(run['started_at_iso'])}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Status</div>
                <div class="stat-value">{'Finished' if run['ended_at_iso'] else 'Running'}</div>
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

        <h3>Phase Statistics</h3>
        <div class="stats-grid">
            {''.join([
                f"""<div class="stat-box" style="border-left-color: {'#1f6feb' if p['phase'] == 'A' else '#8957e5'}">
                    <div class="stat-label">Phase {p['phase']} Positions</div>
                    <div class="stat-value">{p['opened']} opened / {p['closed']} closed</div>
                </div>""" for p in pos_by_phase
            ])}
        </div>

        <h3>PnL by Phase (Realized Only)</h3>
        <div class="card">
            <table>
                <tr>
                    <th>Phase</th>
                    <th>Realized PnL (Closed Trades)</th>
                </tr>
    """

    total_pnl = 0.0
    for pnl in pnl_data:
        realized = pnl['realized'] or 0.0
        total_pnl += realized
        content += f"""
                <tr>
                    <td><span class="badge badge-{pnl['phase'].lower()}">Phase {pnl['phase']}</span></td>
                    <td class="{'positive' if realized >= 0 else 'negative'}">{format_number(realized)}</td>
                </tr>
        """

    content += f"""
            </table>
            <div style="margin-top: 20px; text-align: right; font-size: 18px;">
                <strong>Total Realized PnL: <span class="{'positive' if total_pnl >= 0 else 'negative'}">{format_number(total_pnl)} USDC</span></strong>
            </div>
        </div>

        <h3>Metadata</h3>
        <div class="card">
            <pre>{json.dumps(json.loads(run['metadata_json'] or '{}'), indent=2)}</pre>
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
        side_str = order['side'] or '-'
        content += f"""
                <tr>
                    <td>{format_ts(order['ts_iso'])}</td>
                    <td>{order['event_type']}</td>
                    <td><span class="badge badge-{side_str.lower() if side_str else 'a'}">{side_str}</span></td>
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
    """Show fills with detailed trade analysis."""

    # Get fills with order details
    fills = query_db("""
        SELECT
            f.ts_iso as fill_time,
            f.client_order_id,
            f.instrument_id,
            f.side,
            f.quantity,
            f.price as fill_price,
            f.fee,
            f.trade_id,
            f.payload_json as fill_payload,
            o.ts_iso as order_time,
            o.side as order_side,
            o.payload_json as order_payload
        FROM fills f
        LEFT JOIN orders o ON o.run_id = f.run_id
            AND o.client_order_id = f.client_order_id
            AND o.event_type = 'order_submitted'
        WHERE f.run_id = ?
        ORDER BY f.ts_iso DESC
        LIMIT 200
    """, (run_id,))

    def extract_ev(payload_json):
        if not payload_json:
            return None
        try:
            data = json.loads(payload_json)
            for key in ['ev', 'ev_raw', 'ev_smoothed', 'p_t', 'p_flip']:
                if key in data and data[key] is not None:
                    return float(data[key])
            opts = data.get('options', {})
            for key in ['ev', 'p_t', 'p_flip']:
                if key in opts and opts[key] is not None:
                    return float(opts[key])
            return None
        except:
            return None

    def extract_conditions(payload_json):
        if not payload_json:
            return {}
        try:
            data = json.loads(payload_json)
            conds = {}
            for key in ['p_t', 'q_t', 'delta_btc_pct', 'sigma', 'trend_score', 'delta_p_pct', 'time_weight']:
                if key in data and data[key] is not None:
                    conds[key] = data[key]
            return conds
        except:
            return {}

    def infer_phase(order_payload, conds):
        try:
            if order_payload:
                data = json.loads(order_payload)
                phase = data.get("phase")
                if phase in ("A", "B"):
                    return phase
        except:
            pass
        if any(k in conds for k in ("trend_score", "delta_p_pct", "time_weight")):
            return "B"
        return "A"

    # Build instrument -> token map from positions table (authoritative)
    instrument_token_rows = query_db("""
        SELECT instrument_id, token, MAX(ts_ns) as last_ts
        FROM positions
        WHERE run_id = ?
          AND instrument_id IS NOT NULL
          AND token IS NOT NULL
          AND token IN ('up', 'down')
        GROUP BY instrument_id, token
        ORDER BY last_ts DESC
    """, (run_id,))
    instrument_to_token = {}
    for row in instrument_token_rows:
        iid = row['instrument_id']
        if iid and iid not in instrument_to_token:
            instrument_to_token[iid] = row['token']

    # Group by client_order_id
    groups_map = {}
    for f in fills:
        group_key = f['client_order_id'] or f['trade_id'] or f"ts:{f['fill_time']}"
        if group_key not in groups_map:
            groups_map[group_key] = []
        groups_map[group_key].append(f)

    groups = list(groups_map.values())

    content = f"""
        <h2>Fill Analysis</h2>
        <p style="color: #8b949e; font-size: 12px;">{len(fills)} fills in {len(groups)} order groups</p>

        <div class="stats-grid">
            <div class="stat-box"><div class="stat-label">Total Fills</div><div class="stat-value">{len(fills)}</div></div>
            <div class="stat-box"><div class="stat-label">Order Groups</div><div class="stat-value">{len(groups)}</div></div>
        </div>
    """

    for i, group in enumerate(groups):
        first = group[0]
        total_qty = sum(f['quantity'] or 0 for f in group)
        avg_price = sum((f['quantity'] or 0) * (f['fill_price'] or 0) for f in group) / total_qty if total_qty > 0 else 0
        total_fee = sum(f['fee'] or 0 for f in group)

        ev = extract_ev(first['order_payload'])
        conds = extract_conditions(first['order_payload'])
        phase = infer_phase(first['order_payload'], conds)
        token = instrument_to_token.get(first['instrument_id']) or 'up'

        # Map numeric side to BUY/SELL
        side_display = fills_side_label(first['side'])

        cond_html = ""
        if conds:
            cond_html = "<div style='margin-top: 8px; font-size: 11px;'><strong style='color: #8b949e;'>Entry Conditions:</strong><br>"
            for k, v in conds.items():
                cond_html += f"<span style='color: #c9d1d9;'>&nbsp;&nbsp;{k}: {v}</span><br>"
            cond_html += "</div>"

        content += f"""
        <div class="card" style="margin-bottom: 15px;">
            <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer;"
                 onclick="toggle('fg{i}')">
                <h4 style="margin: 0;">
                    Order #{i+1}
                    <span class="badge badge-{token}">{token.upper()}</span>
                    <span class="badge badge-{phase.lower()}">Phase {phase}</span>
                </h4>
                <span style="font-size: 12px; color: #8b949e;">{len(group)} fills [点击展开]</span>
            </div>

            <div style="margin-top: 10px; padding: 10px; background: #161b22; border-radius: 6px;">
                <table style="width: 100%; font-size: 12px;">
                    <tr>
                        <td style="color: #8b949e; width: 80px;">Order:</td>
                        <td>{format_ts(first['order_time'])} <code>{(first['client_order_id'] or '-')[0:18]}</code></td>
                        <td style="color: #8b949e; width: 80px;">Side:</td>
                        <td>{side_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #8b949e;">Total Qty:</td>
                        <td>{format_number(total_qty, 4)}</td>
                        <td style="color: #8b949e;">Avg Price:</td>
                        <td>{format_number(avg_price, 4)} USDC</td>
                    </tr>
                    <tr>
                        <td style="color: #8b949e;">Total Fee:</td>
                        <td>{format_number(total_fee, 4)} USDC</td>
                        <td style="color: #8b949e;">EV:</td>
                        <td>{f"{ev:.4f}" if ev else "N/A"}</td>
                    </tr>
                </table>
                {cond_html}
            </div>

            <div id="fg{i}" style="display: none; margin-top: 10px;">
                <h5 style="margin: 10px 0; color: #58a6ff; font-size: 12px;">Individual Fills:</h5>
                <table style="width: 100%; font-size: 11px;">
                    <tr style="background: #21262d;">
                        <th>Time</th><th>Side</th><th>Qty</th><th>Price</th><th>Fee</th><th>Notional</th>
                    </tr>
        """

        for f in group:
            notional = (f['quantity'] or 0) * (f['fill_price'] or 0)
            content += f"""
                    <tr>
                        <td>{format_ts(f['fill_time'])}</td>
                        <td>{fills_side_label(f['side'])}</td>
                        <td>{format_number(f['quantity'], 4)}</td>
                        <td>{format_number(f['fill_price'], 4)}</td>
                        <td>{format_number(f['fee'], 4)}</td>
                        <td>{format_number(notional, 2)}</td>
                    </tr>
            """

        content += """
                </table>
            </div>
        </div>
        """

    content += """
        <script>
            function toggle(id) {
                const el = document.getElementById(id);
                el.style.display = el.style.display === 'none' ? 'block' : 'none';
            }
        </script>
    """

    return render_template_string(BASE_TEMPLATE, content=content, active_page="fills", run_id=run_id)


@app.route("/run/<run_id>/positions")
def run_positions(run_id: str) -> str:
    """Show positions for a run - grouped by Phase A/B."""

    # Get Phase A positions
    positions_a = query_db("""
        SELECT * FROM positions
        WHERE run_id = ? AND phase = 'A'
        ORDER BY ts_iso DESC
        LIMIT 100
    """, (run_id,))

    # Get Phase B positions
    positions_b = query_db("""
        SELECT * FROM positions
        WHERE run_id = ? AND phase = 'B'
        ORDER BY ts_iso DESC
        LIMIT 100
    """, (run_id,))

    # Get Phase statistics — opened count from position_requested, closed from position_closed
    stats = query_db("""
        SELECT phase,
               COUNT(*) as total_events,
               SUM(CASE WHEN event_type = 'position_requested' THEN 1 ELSE 0 END) as opened,
               SUM(CASE WHEN event_type = 'position_closed' THEN 1 ELSE 0 END) as closed,
               SUM(CASE WHEN event_type = 'position_changed' THEN 1 ELSE 0 END) as changed,
               SUM(CASE WHEN event_type = 'position_closed' THEN realized_pnl ELSE 0 END) as total_realized,
               AVG(avg_price) as avg_entry_price
        FROM positions
        WHERE run_id = ?
        GROUP BY phase
    """, (run_id,))

    def render_position_table(positions, title):
        if not positions:
            return f"<h3>{title}</h3><p>No positions</p>"

        table = f"""
        <h3>{title}</h3>
        <div class="card">
            <table>
                <tr>
                    <th>Time</th>
                    <th>Event</th>
                    <th>Token</th>
                    <th>Size</th>
                    <th>Avg Price</th>
                    <th>Realized PnL</th>
                    <th>Unrealized PnL</th>
                </tr>
        """
        for pos in positions:
            token = pos['token'] or 'up'
            realized_class = "positive" if (pos['realized_pnl'] or 0) >= 0 else "negative"
            unrealized_class = "positive" if (pos['unrealized_pnl'] or 0) >= 0 else "negative"
            table += f"""
                <tr>
                    <td>{format_ts(pos['ts_iso'])}</td>
                    <td>{pos['event_type']}</td>
                    <td><span class="badge badge-{token}">{token.upper()}</span></td>
                    <td>{format_number(pos['position_size'])}</td>
                    <td>{format_number(pos['avg_price'])}</td>
                    <td class="{realized_class}">{format_number(pos['realized_pnl'])}</td>
                    <td class="{unrealized_class}">{format_number(pos['unrealized_pnl'])}</td>
                </tr>
            """
        table += "</table></div>"
        return table

    # Build Phase stats summary
    stats_html = """
    <div class="stats-grid">
    """
    for s in stats:
        phase_color = '#1f6feb' if s['phase'] == 'A' else '#8957e5'
        pnl_class = "positive" if (s['total_realized'] or 0) >= 0 else "negative"
        stats_html += f"""
        <div class="stat-box" style="border-left-color: {phase_color}">
            <div class="stat-label">Phase {s['phase']} Summary</div>
            <div class="stat-value">
                {s['total_events']} events<br>
                <small>{s['opened']} opened / {s['closed']} closed / {s['changed']} changed</small>
            </div>
            <div class="stat-label">Total Realized PnL</div>
            <div class="stat-value {pnl_class}">{format_number(s['total_realized'])} USDC</div>
        </div>
        """
    stats_html += "</div>"

    content = f"""
        <h2>Positions by Phase</h2>
        {stats_html}
        {render_position_table(positions_a, 'Phase A Positions (Momentum Arbitrage)')}
        {render_position_table(positions_b, 'Phase B Positions (Momentum Continuation)')}
    """

    return render_template_string(BASE_TEMPLATE, content=content, active_page="positions", run_id=run_id)


@app.route("/run/<run_id>/pnl")
def run_pnl(run_id: str) -> str:
    """Show PnL chart for a run - by Phase."""
    # Get Phase A data — total_pnl running series only
    pnl_a = query_db("""
        SELECT ts_iso, realized_pnl, total_pnl
        FROM pnl
        WHERE run_id = ? AND phase = 'A'
        ORDER BY ts_iso ASC
    """, (run_id,))

    # Get Phase B data
    pnl_b = query_db("""
        SELECT ts_iso, realized_pnl, total_pnl
        FROM pnl
        WHERE run_id = ? AND phase = 'B'
        ORDER BY ts_iso ASC
    """, (run_id,))

    # Prepare Phase A data
    ts_a = [format_ts(row['ts_iso']) for row in pnl_a]
    realized_a = [row['realized_pnl'] or 0 for row in pnl_a]
    total_a = [row['total_pnl'] or 0 for row in pnl_a]

    # Prepare Phase B data
    ts_b = [format_ts(row['ts_iso']) for row in pnl_b]
    realized_b = [row['realized_pnl'] or 0 for row in pnl_b]
    total_b = [row['total_pnl'] or 0 for row in pnl_b]

    # Summary — use only realized from position_closed
    realized_a_total = query_db("""
        SELECT COALESCE(SUM(realized_pnl), 0) as val FROM positions
        WHERE run_id = ? AND phase = 'A' AND event_type = 'position_closed'
    """, (run_id,), one=True)['val']
    realized_b_total = query_db("""
        SELECT COALESCE(SUM(realized_pnl), 0) as val FROM positions
        WHERE run_id = ? AND phase = 'B' AND event_type = 'position_closed'
    """, (run_id,), one=True)['val']

    final_a = total_a[-1] if total_a else realized_a_total
    final_b = total_b[-1] if total_b else realized_b_total

    content = f"""
        <h2>PnL by Phase</h2>

        <div class="card">
            <canvas id="pnlChartPhaseA" class="chart-container"></canvas>
        </div>

        <div class="card" style="margin-top: 20px;">
            <canvas id="pnlChartPhaseB" class="chart-container"></canvas>
        </div>

        <h3>Summary</h3>
        <div class="card">
            <table>
                <tr>
                    <th>Phase</th>
                    <th>Data Points</th>
                    <th>Total Realized (Closed Trades)</th>
                    <th>Running Total PnL (Last)</th>
                </tr>
                <tr>
                    <td><span class="badge badge-a">Phase A</span></td>
                    <td>{len(pnl_a)}</td>
                    <td class="{'positive' if realized_a_total >= 0 else 'negative'}">{format_number(realized_a_total)}</td>
                    <td class="{'positive' if final_a >= 0 else 'negative'}">{format_number(final_a)}</td>
                </tr>
                <tr>
                    <td><span class="badge badge-b">Phase B</span></td>
                    <td>{len(pnl_b)}</td>
                    <td class="{'positive' if realized_b_total >= 0 else 'negative'}">{format_number(realized_b_total)}</td>
                    <td class="{'positive' if final_b >= 0 else 'negative'}">{format_number(final_b)}</td>
                </tr>
            </table>
        </div>

        <script>
            // Phase A Chart
            const ctxA = document.getElementById('pnlChartPhaseA').getContext('2d');
            new Chart(ctxA, {{
                type: 'line',
                data: {{
                    labels: {ts_a},
                    datasets: [
                        {{
                            label: 'Phase A - Realized',
                            data: {realized_a},
                            borderColor: '#3fb950',
                            backgroundColor: 'rgba(63, 185, 80, 0.1)',
                            fill: false
                        }},
                        {{
                            label: 'Phase A - Total PnL',
                            data: {total_a},
                            borderColor: '#1f6feb',
                            backgroundColor: 'rgba(31, 111, 235, 0.1)',
                            fill: false,
                            borderWidth: 2
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Phase A PnL (Momentum Arbitrage)',
                            color: '#c9d1d9'
                        }},
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

            // Phase B Chart
            const ctxB = document.getElementById('pnlChartPhaseB').getContext('2d');
            new Chart(ctxB, {{
                type: 'line',
                data: {{
                    labels: {ts_b},
                    datasets: [
                        {{
                            label: 'Phase B - Realized',
                            data: {realized_b},
                            borderColor: '#3fb950',
                            backgroundColor: 'rgba(63, 185, 80, 0.1)',
                            fill: false
                        }},
                        {{
                            label: 'Phase B - Total PnL',
                            data: {total_b},
                            borderColor: '#8957e5',
                            backgroundColor: 'rgba(137, 87, 229, 0.1)',
                            fill: false,
                            borderWidth: 2
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        title: {{
                            display: true,
                            text: 'Phase B PnL (Momentum Continuation)',
                            color: '#c9d1d9'
                        }},
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


@app.route("/run/<run_id>/trades")
def run_trades(run_id: str) -> str:
    """Show detailed trade analysis with entry/exit conditions."""

    # Fetch all position_requested (entry) and position_closed (exit) events,
    # paired by (token, phase) using ROW_NUMBER ordering.
    req_rows = query_db("""
        SELECT
            ts_iso as entry_time,
            ts_ns as entry_ts_ns,
            token,
            phase,
            COALESCE(round_slug, 'unknown') as round_slug,
            avg_price as limit_price,
            payload_json as entry_payload,
            entry_context_json,
            ROW_NUMBER() OVER (PARTITION BY run_id, token, phase ORDER BY ts_ns) as seq_no
        FROM positions
        WHERE run_id = ?
          AND event_type = 'position_requested'
        ORDER BY ts_ns ASC
    """, (run_id,))

    cls_rows = query_db("""
        SELECT
            ts_iso as exit_time,
            ts_ns as exit_ts_ns,
            token,
            phase,
            realized_pnl,
            payload_json as close_payload,
            ROW_NUMBER() OVER (PARTITION BY run_id, token, phase ORDER BY ts_ns) as seq_no
        FROM positions
        WHERE run_id = ?
          AND event_type = 'position_closed'
        ORDER BY ts_ns ASC
    """, (run_id,))

    # Pre-fetch all position_close_requested events for Python-side matching
    close_req_rows = query_db("""
        SELECT ts_ns, token, phase, payload_json as close_req_payload
        FROM positions
        WHERE run_id = ?
          AND event_type = 'position_close_requested'
        ORDER BY ts_ns ASC
    """, (run_id,))

    # Index req by (token, phase, seq_no)
    req_index = {}
    for r in req_rows:
        key = (r['token'], r['phase'], r['seq_no'])
        req_index[key] = r

    # Index close_req by (token, phase) -> sorted list of (ts_ns, payload)
    close_req_index = {}
    for cr in close_req_rows:
        key = (cr['token'], cr['phase'])
        close_req_index.setdefault(key, []).append((cr['ts_ns'], cr['close_req_payload']))

    trades = []
    for cls in cls_rows:
        key = (cls['token'], cls['phase'], cls['seq_no'])
        req = req_index.get(key)

        # Find the most recent position_close_requested before this exit
        cr_key = (cls['token'], cls['phase'])
        close_req_list = close_req_index.get(cr_key, [])
        close_req_payload = None
        for cr_ts, cr_payload in reversed(close_req_list):
            if cr_ts <= cls['exit_ts_ns']:
                close_req_payload = cr_payload
                break

        # Parse close payload for actual fill prices
        cp = parse_close_payload(cls['close_payload'])

        # Parse entry context
        ec = parse_entry_context(req['entry_context_json'] if req else None)

        # Parse limit_price from entry_payload if avg_price is None
        limit_price = req['limit_price'] if req else None
        if limit_price is None and req and req['entry_payload']:
            try:
                ep = json.loads(req['entry_payload'])
                limit_price = ep.get('price')
            except:
                pass

        # Slippage: actual entry fill - limit price
        slippage = None
        if cp['avg_px_open'] is not None and limit_price is not None:
            try:
                slippage = float(cp['avg_px_open']) - float(limit_price)
            except:
                pass

        # Duration from close payload duration_ns, fallback to ts difference
        duration_str = "N/A"
        if cp['duration_ns'] is not None:
            try:
                duration_sec = float(cp['duration_ns']) / 1e9
                duration_str = f"{duration_sec:.1f}s"
            except:
                pass
        elif req and req['entry_time'] and cls['exit_time']:
            try:
                t1 = datetime.fromisoformat(req['entry_time'].replace('Z', '+00:00'))
                t2 = datetime.fromisoformat(cls['exit_time'].replace('Z', '+00:00'))
                duration_str = f"{(t2 - t1).total_seconds():.1f}s"
            except:
                pass

        exit_label = extract_exit_reason_label(close_req_payload)

        trades.append({
            'entry_time': req['entry_time'] if req else None,
            'entry_ts_ns': req['entry_ts_ns'] if req else None,
            'exit_time': cls['exit_time'],
            'exit_ts_ns': cls['exit_ts_ns'],
            'token': cls['token'] or 'up',
            'phase': cls['phase'] or 'A',
            'round_slug': req['round_slug'] if req else 'unknown',
            'limit_price': limit_price,
            'avg_px_open': cp['avg_px_open'],
            'avg_px_close': cp['avg_px_close'],
            'slippage': slippage,
            'duration_str': duration_str,
            'realized_pnl': cls['realized_pnl'],
            'exit_label': exit_label,
            'exit_reason_human': human_exit_reason(exit_label),
            'ev': ec['ev'],
            'delta_pct': ec['delta_pct'],
            'btc_price_entry': ec['btc_price'],
            'entry_label': ec['label'],
        })

    # Sort by exit_time descending, limit to 200
    trades = sorted(trades, key=lambda t: t['exit_time'] or '', reverse=True)[:200]

    # Summary stats
    total_pnl = sum(t['realized_pnl'] or 0 for t in trades)
    winning_trades = sum(1 for t in trades if (t['realized_pnl'] or 0) > 0)
    losing_trades = sum(1 for t in trades if (t['realized_pnl'] or 0) < 0)
    win_rate = (winning_trades / len(trades) * 100) if trades else 0.0

    content = f"""
        <h2>Trade Analysis</h2>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">Total Trades</div>
                <div class="stat-value">{len(trades)}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Winning Trades</div>
                <div class="stat-value positive">{winning_trades}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Losing Trades</div>
                <div class="stat-value negative">{losing_trades}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Win Rate</div>
                <div class="stat-value">{format_number(win_rate)}%</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Total PnL</div>
                <div class="stat-value {'positive' if total_pnl >= 0 else 'negative'}">{format_number(total_pnl)} USDC</div>
            </div>
        </div>

        <h3>Trade Details</h3>
        <div class="card" style="overflow-x: auto;">
        <table>
            <tr>
                <th>时间</th>
                <th>轮次</th>
                <th>Token</th>
                <th>阶段</th>
                <th>入场EV</th>
                <th>BTC delta</th>
                <th>BTC价格</th>
                <th>限价单</th>
                <th>实际入场均价</th>
                <th>滑点</th>
                <th>实际出场均价</th>
                <th>持仓时长</th>
                <th>出场原因</th>
                <th>盈亏</th>
            </tr>
    """

    for t in trades:
        pnl_class = "positive" if (t['realized_pnl'] or 0) >= 0 else "negative"
        phase_class = "badge-a" if t['phase'] == 'A' else "badge-b"
        token = t['token']

        ev_str = f"{t['ev']:.4f}" if t['ev'] is not None else "N/A"
        delta_str = f"{float(t['delta_pct']) * 100:.2f}%" if t['delta_pct'] is not None else "N/A"
        btc_str = format_number(t['btc_price_entry'], 0) if t['btc_price_entry'] is not None else "N/A"
        limit_str = format_number(t['limit_price'], 4) if t['limit_price'] is not None else "N/A"
        avg_open_str = format_number(t['avg_px_open'], 4) if t['avg_px_open'] is not None else "N/A"
        avg_close_str = format_number(t['avg_px_close'], 4) if t['avg_px_close'] is not None else "N/A"

        if t['slippage'] is not None:
            slip_class = "negative" if t['slippage'] > 0 else "positive"
            slip_str = f'<span class="{slip_class}">{format_number(t["slippage"], 4)}</span>'
        else:
            slip_str = "N/A"

        round_short = t['round_slug']
        if round_short and round_short != 'unknown':
            # Show last part after last '-'
            parts = round_short.rsplit('-', 2)
            round_short = '-'.join(parts[-2:]) if len(parts) >= 2 else round_short

        content += f"""
            <tr>
                <td>{format_ts(t['entry_time'])}</td>
                <td><small>{round_short}</small></td>
                <td><span class="badge badge-{token}">{token.upper()}</span></td>
                <td><span class="badge {phase_class}">Phase {t['phase']}</span></td>
                <td>{ev_str}</td>
                <td>{delta_str}</td>
                <td>{btc_str}</td>
                <td>{limit_str}</td>
                <td>{avg_open_str}</td>
                <td>{slip_str}</td>
                <td>{avg_close_str}</td>
                <td>{t['duration_str']}</td>
                <td>{t['exit_reason_human']}</td>
                <td class="{pnl_class}">{format_number(t['realized_pnl'])}</td>
            </tr>
        """

    content += "</table></div>"

    return render_template_string(BASE_TEMPLATE, content=content, active_page="trades", run_id=run_id)


@app.route("/run/<run_id>/rounds")
def run_rounds(run_id: str) -> str:
    """Show trades grouped by round_slug."""

    # Fetch all closed trades with round_slug info
    req_rows = query_db("""
        SELECT
            ts_ns as entry_ts_ns,
            ts_iso as entry_time,
            token,
            phase,
            COALESCE(round_slug, 'unknown') as round_slug,
            payload_json as entry_payload,
            entry_context_json,
            ROW_NUMBER() OVER (PARTITION BY run_id, token, phase ORDER BY ts_ns) as seq_no
        FROM positions
        WHERE run_id = ?
          AND event_type = 'position_requested'
        ORDER BY ts_ns ASC
    """, (run_id,))

    cls_rows = query_db("""
        SELECT
            ts_ns as exit_ts_ns,
            ts_iso as exit_time,
            token,
            phase,
            realized_pnl,
            payload_json as close_payload,
            ROW_NUMBER() OVER (PARTITION BY run_id, token, phase ORDER BY ts_ns) as seq_no
        FROM positions
        WHERE run_id = ?
          AND event_type = 'position_closed'
        ORDER BY ts_ns ASC
    """, (run_id,))

    # Build req index
    req_index = {}
    for r in req_rows:
        key = (r['token'], r['phase'], r['seq_no'])
        req_index[key] = r

    # Pair trades
    round_data = {}  # round_slug -> {trades, phase_a_pnl, phase_b_pnl, ...}

    for cls in cls_rows:
        key = (cls['token'], cls['phase'], cls['seq_no'])
        req = req_index.get(key)

        round_slug = req['round_slug'] if req else 'unknown'
        realized_pnl = cls['realized_pnl'] or 0.0
        phase = cls['phase'] or 'A'
        token = cls['token'] or 'up'
        cp = parse_close_payload(cls['close_payload'])

        if round_slug not in round_data:
            round_data[round_slug] = {
                'round_slug': round_slug,
                'trades': [],
                'phase_a_pnl': 0.0,
                'phase_b_pnl': 0.0,
                'total_pnl': 0.0,
                'first_entry_ts_ns': None,
                'last_exit_ts_ns': None,
            }

        rd = round_data[round_slug]
        rd['trades'].append({
            'token': token,
            'phase': phase,
            'realized_pnl': realized_pnl,
            'avg_px_open': cp['avg_px_open'],
            'avg_px_close': cp['avg_px_close'],
        })
        if phase == 'A':
            rd['phase_a_pnl'] += realized_pnl
        else:
            rd['phase_b_pnl'] += realized_pnl
        rd['total_pnl'] += realized_pnl

        entry_ts = req['entry_ts_ns'] if req else None
        if entry_ts and (rd['first_entry_ts_ns'] is None or entry_ts < rd['first_entry_ts_ns']):
            rd['first_entry_ts_ns'] = entry_ts
        if cls['exit_ts_ns'] and (rd['last_exit_ts_ns'] is None or cls['exit_ts_ns'] > rd['last_exit_ts_ns']):
            rd['last_exit_ts_ns'] = cls['exit_ts_ns']

    # Look up BTC prices for each round
    for slug, rd in round_data.items():
        btc_start = None
        btc_end = None
        if rd['first_entry_ts_ns']:
            row = query_db("""
                SELECT mid FROM market_data
                WHERE run_id = ? AND source = 'btc_trade' AND ts_ns <= ?
                ORDER BY ts_ns DESC LIMIT 1
            """, (run_id, rd['first_entry_ts_ns']), one=True)
            if row:
                btc_start = row['mid']
        if rd['last_exit_ts_ns']:
            row = query_db("""
                SELECT mid FROM market_data
                WHERE run_id = ? AND source = 'btc_trade' AND ts_ns <= ?
                ORDER BY ts_ns DESC LIMIT 1
            """, (run_id, rd['last_exit_ts_ns']), one=True)
            if row:
                btc_end = row['mid']
        rd['btc_start'] = btc_start
        rd['btc_end'] = btc_end

    # Sort rounds by slug descending
    rounds = sorted(round_data.values(), key=lambda r: r['round_slug'], reverse=True)

    total_rounds = len(rounds)
    winning_rounds = sum(1 for r in rounds if r['total_pnl'] > 0)
    grand_pnl = sum(r['total_pnl'] for r in rounds)

    content = f"""
        <h2>Rounds Summary</h2>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">Total Rounds</div>
                <div class="stat-value">{total_rounds}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Winning Rounds</div>
                <div class="stat-value positive">{winning_rounds}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Losing Rounds</div>
                <div class="stat-value negative">{total_rounds - winning_rounds}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Grand Total PnL</div>
                <div class="stat-value {'positive' if grand_pnl >= 0 else 'negative'}">{format_number(grand_pnl)} USDC</div>
            </div>
        </div>

        <div class="card" style="overflow-x: auto;">
        <table>
            <tr>
                <th>轮次</th>
                <th>BTC 入场价</th>
                <th>BTC 出场价</th>
                <th>BTC变化</th>
                <th>交易数</th>
                <th>胜/负</th>
                <th>Phase A PnL</th>
                <th>Phase B PnL</th>
                <th>轮次总PnL</th>
            </tr>
    """

    for rd in rounds:
        total_trades = len(rd['trades'])
        wins = sum(1 for t in rd['trades'] if t['realized_pnl'] > 0)
        losses = total_trades - wins
        pnl_class = "positive" if rd['total_pnl'] >= 0 else "negative"
        a_class = "positive" if rd['phase_a_pnl'] >= 0 else "negative"
        b_class = "positive" if rd['phase_b_pnl'] >= 0 else "negative"

        btc_start_str = format_number(rd['btc_start'], 0) if rd['btc_start'] else "-"
        btc_end_str = format_number(rd['btc_end'], 0) if rd['btc_end'] else "-"

        btc_delta_str = "-"
        if rd['btc_start'] and rd['btc_end']:
            btc_delta = rd['btc_end'] - rd['btc_start']
            btc_delta_class = "positive" if btc_delta >= 0 else "negative"
            btc_delta_str = f'<span class="{btc_delta_class}">{format_number(btc_delta, 0)}</span>'

        content += f"""
            <tr>
                <td><small>{rd['round_slug']}</small></td>
                <td>{btc_start_str}</td>
                <td>{btc_end_str}</td>
                <td>{btc_delta_str}</td>
                <td>{total_trades}</td>
                <td><span class="positive">{wins}</span> / <span class="negative">{losses}</span></td>
                <td class="{a_class}">{format_number(rd['phase_a_pnl'])}</td>
                <td class="{b_class}">{format_number(rd['phase_b_pnl'])}</td>
                <td class="{pnl_class}">{format_number(rd['total_pnl'])}</td>
            </tr>
        """

    content += "</table></div>"

    return render_template_string(BASE_TEMPLATE, content=content, active_page="rounds", run_id=run_id)


@app.route("/run/<run_id>/exit_stats")
def run_exit_stats(run_id: str) -> str:
    """Show exit reason statistics."""

    # Fetch all close_requested and closed events for pairing
    close_req_rows = query_db("""
        SELECT ts_ns, token, phase, payload_json as close_req_payload
        FROM positions
        WHERE run_id = ?
          AND event_type = 'position_close_requested'
        ORDER BY ts_ns ASC
    """, (run_id,))

    cls_rows = query_db("""
        SELECT ts_ns as exit_ts_ns, token, phase, realized_pnl,
               ROW_NUMBER() OVER (PARTITION BY run_id, token, phase ORDER BY ts_ns) as seq_no
        FROM positions
        WHERE run_id = ?
          AND event_type = 'position_closed'
        ORDER BY ts_ns ASC
    """, (run_id,))

    # Build close_req index by (token, phase) -> sorted list
    close_req_index = {}
    for cr in close_req_rows:
        key = (cr['token'], cr['phase'])
        close_req_index.setdefault(key, []).append((cr['ts_ns'], cr['close_req_payload']))

    # Group by exit reason
    reason_stats = {}  # raw_label -> {count, wins, total_pnl, pnl_list}

    for cls in cls_rows:
        cr_key = (cls['token'], cls['phase'])
        close_req_list = close_req_index.get(cr_key, [])
        close_req_payload = None
        for cr_ts, cr_payload in reversed(close_req_list):
            if cr_ts <= cls['exit_ts_ns']:
                close_req_payload = cr_payload
                break

        raw_label = extract_exit_reason_label(close_req_payload) or 'unknown'
        realized_pnl = cls['realized_pnl'] or 0.0

        if raw_label not in reason_stats:
            reason_stats[raw_label] = {'count': 0, 'wins': 0, 'total_pnl': 0.0, 'pnl_list': []}

        reason_stats[raw_label]['count'] += 1
        reason_stats[raw_label]['total_pnl'] += realized_pnl
        reason_stats[raw_label]['pnl_list'].append(realized_pnl)
        if realized_pnl > 0:
            reason_stats[raw_label]['wins'] += 1

    total_trades = sum(s['count'] for s in reason_stats.values())
    grand_pnl = sum(s['total_pnl'] for s in reason_stats.values())

    content = f"""
        <h2>Exit Reason Statistics</h2>

        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-label">Total Closed Trades</div>
                <div class="stat-value">{total_trades}</div>
            </div>
            <div class="stat-box">
                <div class="stat-label">Total PnL</div>
                <div class="stat-value {'positive' if grand_pnl >= 0 else 'negative'}">{format_number(grand_pnl)} USDC</div>
            </div>
        </div>

        <div class="card">
        <table>
            <tr>
                <th>出场原因 (原始)</th>
                <th>出场原因 (中文)</th>
                <th>次数</th>
                <th>胜率</th>
                <th>平均PnL</th>
                <th>总PnL</th>
            </tr>
    """

    for raw_label, stats in sorted(reason_stats.items(), key=lambda x: x[1]['total_pnl']):
        count = stats['count']
        wins = stats['wins']
        win_rate = (wins / count * 100) if count > 0 else 0.0
        avg_pnl = stats['total_pnl'] / count if count > 0 else 0.0
        total_pnl = stats['total_pnl']
        pnl_class = "positive" if total_pnl >= 0 else "negative"
        avg_class = "positive" if avg_pnl >= 0 else "negative"

        content += f"""
            <tr>
                <td><code>{raw_label}</code></td>
                <td>{human_exit_reason(raw_label)}</td>
                <td>{count}</td>
                <td>{format_number(win_rate)}%</td>
                <td class="{avg_class}">{format_number(avg_pnl)}</td>
                <td class="{pnl_class}">{format_number(total_pnl)}</td>
            </tr>
        """

    content += "</table></div>"

    return render_template_string(BASE_TEMPLATE, content=content, active_page="exit_stats", run_id=run_id)


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
