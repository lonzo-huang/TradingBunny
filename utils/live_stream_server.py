# utils/live_stream_server.py
"""
Lightweight WebSocket server for real-time strategy data streaming.
Pushes tick-level data to Grafana Live / custom dashboards at 100-200ms latency.

Architecture:
  NautilusTrader Strategy → LiveStreamServer.push() → WebSocket clients (Grafana)
"""

import asyncio
import json
import time
import os
import threading
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Optional

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class LiveStreamServer:
    """Async WebSocket broadcast server for real-time strategy metrics."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: set = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server = None
        self._running = False
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._project_root = os.path.dirname(os.path.dirname(__file__))
        self._runtime_params_path = os.path.join(self._project_root, "config", "pde_runtime_overrides.json")
        self._param_update_handler = None
        self._control_lock = threading.Lock()
        self._control_status: dict[str, dict] = {
            "export": {"status": "idle", "last_exit_code": None, "last_output": ""},
            "replay": {"status": "idle", "last_exit_code": None, "last_output": ""},
            "backtest": {"status": "idle", "last_exit_code": None, "last_output": ""},
        }

    def set_param_update_handler(self, handler) -> None:
        """Register callback to apply runtime parameter updates in strategy process."""
        self._param_update_handler = handler

    async def _handler(self, websocket):
        """Handle a new WebSocket client connection."""
        self.clients.add(websocket)
        try:
            # Send initial connection confirmation
            await websocket.send(json.dumps({"type": "connected", "ts": time.time()}))
            async for _ in websocket:
                pass  # We only push, don't read
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)

    async def _broadcast_loop(self):
        """Continuously drain the message queue and broadcast to all clients."""
        while self._running:
            try:
                msg = await asyncio.wait_for(self._message_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue

            if not self.clients:
                continue

            data = json.dumps(msg, default=str)
            disconnected = set()
            for client in tuple(self.clients):
                try:
                    await client.send(data)
                except websockets.exceptions.ConnectionClosed:
                    disconnected.add(client)
                except Exception:
                    disconnected.add(client)
            self.clients -= disconnected

    async def _run_server(self):
        """Start the WebSocket server and broadcast loop."""
        self._running = True
        self._server = await websockets.serve(self._handler, self.host, self.port)
        # Run broadcast loop concurrently
        await self._broadcast_loop()

    def start(self):
        """Start the WebSocket server and HTTP dashboard in daemon threads."""
        if not HAS_WEBSOCKETS:
            print("[WARN]  websockets library not installed, live stream disabled")
            return

        def _thread_target():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._run_server())

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()
        print(f"[SERVER] Live stream WebSocket server started on ws://{self.host}:{self.port}")

        # Start HTTP server to serve the live dashboard HTML
        self._start_dashboard_http()

    def _start_dashboard_http(self):
        """Start a tiny HTTP server to serve live-dashboard.html on port 8766."""
        dashboard_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'monitoring')
        live_server = self

        class _Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=dashboard_dir, **kwargs)

            def log_message(self, format, *args):
                pass  # Suppress access logs

            def do_GET(self):
                if self.path == '/api/control/status':
                    self._send_json(200, {
                        'status': live_server._get_control_status(),
                        'runtime_params': live_server._read_runtime_params_file(),
                    })
                    return

                # Redirect root to v2 dashboard
                if self.path == '/':
                    self.send_response(302)
                    self.send_header('Location', '/live-dashboard-v2.html')
                    self.end_headers()
                    return
                super().do_GET()

            def do_POST(self):
                if not self.path.startswith('/api/control/'):
                    self._send_json(404, {'ok': False, 'error': 'unknown endpoint'})
                    return

                payload = self._read_json_body()

                if self.path == '/api/control/params':
                    params = payload.get('params', {})
                    if not isinstance(params, dict):
                        self._send_json(400, {'ok': False, 'error': 'params must be object'})
                        return
                    saved = live_server._write_runtime_params_file(params)
                    applied = {'applied': {}, 'rejected': {}}
                    if callable(live_server._param_update_handler):
                        try:
                            applied = live_server._param_update_handler(params)
                        except Exception as e:
                            applied = {'applied': {}, 'rejected': {'_handler': str(e)}}
                    self._send_json(200, {'ok': True, 'saved': saved, 'result': applied})
                    return

                if self.path == '/api/control/export':
                    db = str(payload.get('db', 'data/pde/pde_runs.sqlite3'))
                    out = str(payload.get('out', 'data/pde/exports'))
                    cmd = ['python', 'live/export_pde_run.py', '--db', db, '--out', out]
                    live_server._start_control_task('export', cmd)
                    self._send_json(200, {'ok': True, 'task': 'export'})
                    return

                if self.path == '/api/control/replay':
                    csv_path = str(payload.get('csv', 'data/pde/exports/market_data.csv'))
                    speed = str(payload.get('speed', 20))
                    cmd = ['python', 'live/replay_pde_run.py', '--csv', csv_path, '--speed', speed]
                    live_server._start_control_task('replay', cmd)
                    self._send_json(200, {'ok': True, 'task': 'replay'})
                    return

                if self.path == '/api/control/backtest':
                    catalog = str(payload.get('catalog', '')).strip()
                    instrument_id = str(payload.get('instrument_id', 'BTCUSDT.BINANCE')).strip()
                    if not catalog:
                        self._send_json(400, {'ok': False, 'error': 'catalog is required'})
                        return
                    cmd = [
                        'python', 'live/backtest_pde.py',
                        '--catalog', catalog,
                        '--instrument-id', instrument_id,
                    ]
                    start = str(payload.get('start', '')).strip()
                    end = str(payload.get('end', '')).strip()
                    params_file = str(payload.get('params_file', '')).strip()
                    if start:
                        cmd.extend(['--start', start])
                    if end:
                        cmd.extend(['--end', end])
                    if params_file:
                        cmd.extend(['--params-file', params_file])

                    live_server._start_control_task('backtest', cmd)
                    self._send_json(200, {'ok': True, 'task': 'backtest'})
                    return

                self._send_json(404, {'ok': False, 'error': 'unknown endpoint'})

            def _read_json_body(self):
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                except Exception:
                    length = 0
                if length <= 0:
                    return {}
                try:
                    raw = self.rfile.read(length)
                    return json.loads(raw.decode('utf-8'))
                except Exception:
                    return {}

            def _send_json(self, code: int, data: dict):
                payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'application/json; charset=utf-8')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        http_port = self.port + 1  # 8766
        try:
            httpd = HTTPServer((self.host, http_port), _Handler)
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            print(f"🖥️  Live dashboard HTTP server started on http://{self.host}:{http_port}")
            print(f"   Open http://localhost:{http_port}/live-dashboard-v2.html in your browser")
        except Exception as e:
            print(f"[WARN]  Failed to start dashboard HTTP server: {e}")

    def _read_runtime_params_file(self) -> dict:
        try:
            if not os.path.exists(self._runtime_params_path):
                return {}
            with open(self._runtime_params_path, 'r', encoding='utf-8') as f:
                obj = json.load(f)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}

    def _write_runtime_params_file(self, params: dict) -> bool:
        try:
            os.makedirs(os.path.dirname(self._runtime_params_path), exist_ok=True)
            current = self._read_runtime_params_file()
            current.update(params)
            with open(self._runtime_params_path, 'w', encoding='utf-8') as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def _get_control_status(self) -> dict:
        with self._control_lock:
            return json.loads(json.dumps(self._control_status))

    def _start_control_task(self, task_name: str, cmd: list[str]) -> None:
        with self._control_lock:
            state = self._control_status.get(task_name)
            if not state:
                return
            if state.get('status') == 'running':
                return
            state['status'] = 'running'
            state['last_exit_code'] = None
            state['last_output'] = 'Starting...'

        t = threading.Thread(
            target=self._run_control_task,
            args=(task_name, cmd),
            daemon=True,
        )
        t.start()

    def _run_control_task(self, task_name: str, cmd: list[str]) -> None:
        try:
            proc = subprocess.run(
                cmd,
                cwd=self._project_root,
                capture_output=True,
                text=True,
                shell=False,
            )
            output = ((proc.stdout or '') + '\n' + (proc.stderr or '')).strip()
            with self._control_lock:
                state = self._control_status.get(task_name, {})
                state['status'] = 'done' if proc.returncode == 0 else 'failed'
                state['last_exit_code'] = proc.returncode
                state['last_output'] = output[-6000:]
        except Exception as e:
            with self._control_lock:
                state = self._control_status.get(task_name, {})
                state['status'] = 'failed'
                state['last_exit_code'] = -1
                state['last_output'] = f'Exception: {e}'

    def stop(self):
        """Stop the WebSocket server."""
        self._running = False
        if self._server and self._loop:
            self._loop.call_soon_threadsafe(self._server.close)

    def push(self, message: dict):
        """Thread-safe push a message to all connected clients.

        Call this from the strategy thread — it schedules the message
        onto the async event loop's queue.
        """
        if not self._loop or not self._running:
            return
        try:
            self._loop.call_soon_threadsafe(
                self._message_queue.put_nowait, message
            )
        except asyncio.QueueFull:
            pass  # Drop oldest if queue is full (backpressure)

    # ── Convenience pushers for common message types ──────────────────

    def push_btc_tick(self, price: float, bid: float = 0, ask: float = 0,
                      delta_usd: float = 0, move_bps: float = 0):
        self.push({
            "type": "btc_tick",
            "ts": time.time(),
            "price": price,
            "bid": bid,
            "ask": ask,
            "delta_usd": delta_usd,
            "move_bps": move_bps,
        })

    def push_poly_tick(self, token: str, bid: float, ask: float,
                       mid: float = 0, spread_pct: float = 0,
                       btc_price: float = 0):
        self.push({
            "type": "poly_tick",
            "ts": time.time(),
            "token": token,
            "bid": bid,
            "ask": ask,
            "mid": mid or (bid + ask) / 2,
            "spread_pct": spread_pct,
            "btc_price": btc_price,
        })

    def push_ev(self, token: str, phase: str, ev: float, p_up: float = 0,
                sigma: float = 0, p_flip: float = 0, ev_tail: float = 0,
                z_score: float = 0, delta_log: float = 0, delta_usd: float = 0,
                speed_advantage: bool = False, ev_threshold: float = 0,
                remaining: float = 0, tail_condition: bool = False,
                p_cont: float = 0, tau: float = 0, delta_pct: float = 0,
                momentum_threshold: float = 0, target: str = "", tail_done: bool = False,
                p_t: float = 0, q_t: float = 0, ev_alpha: float = 0,
                time_weight: float = 0, trend_score: float = 0,
                delta_p: float = 0, delta_p_pct: float = 0,
                phase_a_start: float = 0, phase_a_end: float = 240,
                elapsed: float = 0):
        self.push({
            "type": "ev",
            "ts": time.time(),
            "token": token,
            "phase": phase,
            "ev": ev,
            "p_up": p_up,
            "sigma": sigma,
            "p_flip": p_flip,
            "ev_tail": ev_tail,
            "z_score": z_score,
            "delta_log": delta_log,
            "delta_usd": delta_usd,
            "speed_advantage": speed_advantage,
            "ev_threshold": ev_threshold,
            "remaining": remaining,
            "tail_condition": tail_condition,
            "p_cont": p_cont,
            "tau": tau,
            "delta_pct": delta_pct,
            "momentum_threshold": momentum_threshold,
            "target": target,
            "tail_done": tail_done,
            "p_t": p_t,
            "q_t": q_t,
            "ev_alpha": ev_alpha,
            "time_weight": time_weight,
            "trend_score": trend_score,
            "delta_p": delta_p,
            "delta_p_pct": delta_p_pct,
            "phase_a_start": phase_a_start,
            "phase_a_end": phase_a_end,
            "elapsed": elapsed,
        })

    def push_phase_state(self, phase: str, remaining: float, a_trades: int,
                         b_trades: int, tail_done: bool, btc_round: str = "",
                         phase_a_start: float = 0, phase_a_end: float = 240,
                         elapsed: float = 0):
        self.push({
            "type": "phase_state",
            "ts": time.time(),
            "phase": phase,
            "remaining": remaining,
            "a_trades": a_trades,
            "b_trades": b_trades,
            "tail_done": tail_done,
            "btc_round": btc_round,
            "phase_a_start": phase_a_start,
            "phase_a_end": phase_a_end,
            "elapsed": elapsed,
        })

    def push_position(self, token: str, phase: str, is_open: bool,
                      entry_price: float = 0, current_price: float = 0,
                      unrealized_pnl: float = 0, realized_pnl: float = 0,
                      pnl_pct: float = 0, quantity: float = 0):
        self.push({
            "type": "position",
            "ts": time.time(),
            "token": token,
            "phase": phase,
            "is_open": is_open,
            "entry_price": entry_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "pnl_pct": pnl_pct,
            "quantity": quantity,
        })

    def push_latency(self, gap_ms: float, btc_ts: float, poly_ts: float):
        self.push({
            "type": "latency",
            "ts": time.time(),
            "gap_ms": gap_ms,
            "btc_ts": btc_ts,
            "poly_ts": poly_ts,
        })

    def push_jump(self, direction: int, move_bps: float, jump_ts: float,
                  anchor_price: float):
        self.push({
            "type": "jump",
            "ts": time.time(),
            "direction": direction,
            "move_bps": move_bps,
            "jump_ts": jump_ts,
            "anchor_price": anchor_price,
        })

    def push_trade(self, phase: str, token: str, side: str, price: float,
                   qty: float, reason: str):
        self.push({
            "type": "trade",
            "ts": time.time(),
            "phase": phase,
            "token": token,
            "side": side,
            "price": price,
            "qty": qty,
            "reason": reason,
        })

    def push_safety(self, speed_advantage: bool, slippage_ok: bool,
                    volatility_ok: bool, depth_ok: bool, jump_fresh: bool,
                    phase_ok: bool):
        self.push({
            "type": "safety",
            "ts": time.time(),
            "speed_advantage": speed_advantage,
            "slippage_ok": slippage_ok,
            "volatility_ok": volatility_ok,
            "depth_ok": depth_ok,
            "jump_fresh": jump_fresh,
            "phase_ok": phase_ok,
        })

    def push_depth(self, token: str, levels: list):
        """Push order book depth for a token.
        levels: list of {price, qty, side} dicts, up to 3 levels per side."""
        self.push({
            "type": "depth",
            "ts": time.time(),
            "token": token,
            "levels": levels,
        })

    def push_pnl_summary(self, phase_a_realized: float, phase_b_realized: float,
                         phase_a_unrealized: float, phase_b_unrealized: float,
                         round_pnl: float, cumulative_a: float, cumulative_b: float):
        self.push({
            "type": "pnl_summary",
            "ts": time.time(),
            "phase_a_realized": phase_a_realized,
            "phase_b_realized": phase_b_realized,
            "phase_a_unrealized": phase_a_unrealized,
            "phase_b_unrealized": phase_b_unrealized,
            "round_pnl": round_pnl,
            "cumulative_a": cumulative_a,
            "cumulative_b": cumulative_b,
        })

    def push_rollover(self, old_slug: str, new_slug: str, rounds: int):
        self.push({
            "type": "rollover",
            "ts": time.time(),
            "old_slug": old_slug,
            "new_slug": new_slug,
            "rounds": rounds,
        })

    def push_anomaly(self, anomaly_type: str, detail: str):
        self.push({
            "type": "anomaly",
            "ts": time.time(),
            "anomaly_type": anomaly_type,
            "detail": detail,
        })
