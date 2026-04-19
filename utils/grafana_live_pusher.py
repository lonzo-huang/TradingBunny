# utils/grafana_live_pusher.py
"""
Grafana Live Pusher — pushes real-time metrics to Grafana Live channels.

Grafana Live HTTP Push API uses **InfluxDB line protocol** format:
  /api/live/push/:streamId
  <measurement>[,<tag_key>=<tag_value>] <field_key>=<field_value> [<timestamp_ns>]

Grafana panels subscribe to channels using the built-in "Grafana" data source
with query syntax: channel = "pde/<measurement>".

Requirements:
  - Grafana >= 8.0 with live enabled
  - docker-compose must set GF_LIVE_ALLOWED_CHANNEL_PREFIXES=pde/

Channel layout (each measurement maps to a Grafana Live channel):
  pde/btc       — BTC price, delta_usd, move_bps
  pde/poly      — Polymarket up/down bid/ask/mid
  pde/ev        — EV + phase params (z_score, delta_log, etc.)
  pde/phase     — current phase, remaining, trades
  pde/position  — position state (up/down)
  pde/latency   — latency gap
  pde/jump      — BTC jump detection
  pde/pnl       — PnL summary
  pde/safety    — safety thresholds
  pde/depth     — order book depth
  pde/anomaly   — anomaly detection
"""

import logging
import threading
import time
import math
from collections import deque
from typing import Any

import urllib.request
import urllib.error

logger = logging.getLogger(__name__)

# ── Default config ──────────────────────────────────────────────────────
DEFAULT_GRAFANA_URL = "http://localhost:3000"
DEFAULT_STREAM_ID = "pde"


class GrafanaLivePusher:
    """Pushes real-time metrics to Grafana Live via InfluxDB line protocol.

    Thread-safe: all push methods can be called from any thread.
    Uses a background queue + batch sender to minimise HTTP overhead.
    """

    def __init__(
        self,
        grafana_url: str = DEFAULT_GRAFANA_URL,
        stream_id: str = DEFAULT_STREAM_ID,
        auth: tuple | None = None,  # (user, password) for basic auth
        api_token: str | None = None,  # Bearer token for Grafana API
        batch_interval: float = 0.05,  # seconds between flushes (50ms for low latency)
        max_queue: int = 2000,
    ):
        self._base_url = grafana_url.rstrip("/")
        self._stream_id = stream_id
        self._auth = auth  # ("admin", "admin") by default
        self._batch_interval = batch_interval
        self._queue: deque = deque(maxlen=max_queue)
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._flush_event = threading.Event()  # signal immediate flush
        self._error_count = 0
        self._success_count = 0
        self._auth_mode = "none"
        self._seen_401 = False
        self._auth_header: str | None = None
        self._api_token = api_token
        if api_token:
            self._auth_mode = "token"
            self._auth_header = f"Bearer {api_token}"
        elif auth:
            import base64
            cred = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            self._auth_mode = "basic"
            self._auth_header = f"Basic {cred}"

    # ── Lifecycle ────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()
        logger.info(
            "[SERVER] Grafana Live pusher started (url=%s, stream=%s, auth=%s)",
            self._base_url,
            self._stream_id,
            self._auth_mode,
        )

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        # Final flush
        self._flush_batch()
        logger.info("[SERVER] Grafana Live pusher stopped (sent=%d, errors=%d)", self._success_count, self._error_count)

    # ── Internal push ────────────────────────────────────────────────────

    def _enqueue(self, measurement: str, tags: dict[str, str],
                 fields: dict[str, Any], ts_ns: int | None = None) -> None:
        """Add a line-protocol frame to the send queue and signal flush."""
        if ts_ns is None:
            ts_ns = int(time.time() * 1e9)
        with self._lock:
            self._queue.append((measurement, tags, fields, ts_ns))
        self._flush_event.set()  # wake flush thread immediately

    def _flush_loop(self) -> None:
        while self._running:
            # Wait for either: flush signal (new data) or batch timeout
            self._flush_event.wait(timeout=self._batch_interval)
            self._flush_event.clear()
            self._flush_batch()

    def _flush_batch(self) -> None:
        """Send all queued frames as a single InfluxDB line protocol batch."""
        if not self._queue:
            return
        # Drain queue — keep all data points (each with unique timestamp)
        # Use (measurement, timestamp) as key to prevent exact duplicate timestamps
        # but preserve different data points
        items_to_send: list[tuple] = []
        seen: set[tuple[str, int]] = set()
        with self._lock:
            while self._queue:
                item = self._queue.popleft()
                meas, tags, fields, ts_ns = item
                key = (meas, ts_ns)
                if key not in seen:
                    seen.add(key)
                    items_to_send.append(item)

        lines = []
        for meas, tags, fields, ts_ns in items_to_send:
            line = self._format_line(meas, tags, fields, ts_ns)
            if line:
                lines.append(line)

        if lines:
            self._post("\n".join(lines))

    @staticmethod
    def _escape_tag_value(val: str) -> str:
        """Escape special chars in tag values for InfluxDB line protocol."""
        return val.replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")

    @staticmethod
    def _format_field_value(val: Any) -> str:
        """Format a field value for InfluxDB line protocol."""
        if isinstance(val, bool):
            return "true" if val else "false"
        if isinstance(val, int):
            return f"{val}i"
        if isinstance(val, float):
            return f"{val}"
        # String field values must be quoted
        return f'"{val}"'

    def _format_line(self, measurement: str, tags: dict[str, str],
                     fields: dict[str, Any], ts_ns: int) -> str:
        """Build a single InfluxDB line protocol line."""
        if not fields:
            return ""

        # measurement,tag1=val1,tag2=val2 field1=v1,field2=v2 timestamp_ns
        tag_parts = []
        for k, v in tags.items():
            tag_parts.append(f"{k}={self._escape_tag_value(str(v))}")
        tag_str = "," + ",".join(tag_parts) if tag_parts else ""

        field_parts = []
        for k, v in fields.items():
            if v is None:
                continue
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                continue
            field_parts.append(f"{k}={self._format_field_value(v)}")
        if not field_parts:
            return ""
        field_str = ",".join(field_parts)

        return f"{measurement}{tag_str} {field_str} {ts_ns}"

    def _post(self, line_protocol_data: str) -> None:
        url = f"{self._base_url}/api/live/push/{self._stream_id}"
        data = line_protocol_data.encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "text/plain")
        if self._auth_header:
            req.add_header("Authorization", self._auth_header)
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status in (200, 204):
                    self._success_count += 1
                else:
                    self._error_count += 1
                    logger.warning("Grafana Live push returned %d", resp.status)
        except urllib.error.HTTPError as e:
            self._error_count += 1
            if e.code == 401 and not self._seen_401:
                self._seen_401 = True
                logger.error(
                    "Grafana Live push unauthorized (401). "
                    "Check Grafana credentials/token (mode=%s, url=%s). "
                    "If Grafana uses a persisted volume, admin password may not be 'admin'.",
                    self._auth_mode,
                    self._base_url,
                )
            elif self._error_count <= 3 or self._error_count % 100 == 0:
                logger.warning("Grafana Live push HTTP error %s: %s", e.code, e)
        except urllib.error.URLError as e:
            self._error_count += 1
            if self._error_count <= 3 or self._error_count % 100 == 0:
                logger.warning("Grafana Live push failed: %s", e)
        except Exception as e:
            self._error_count += 1
            if self._error_count <= 3:
                logger.warning("Grafana Live push error: %s", e)

    # ── Helper: current timestamp in nanoseconds ─────────────────────────

    @staticmethod
    def _now_ns() -> int:
        return int(time.time() * 1e9)

    # ── Public push helpers ──────────────────────────────────────────────

    def push_btc_tick(self, price: float, delta_usd: float = 0,
                      move_bps: float = 0, **kw) -> None:
        # Only send price field to Grafana Live to avoid display issues
        # delta_usd and move_bps are available in WebSocket but not needed here
        self._enqueue("btc", {}, {
            "price": price,
        })

    def push_poly_tick(self, token: str, bid: float, ask: float,
                       mid: float, spread_pct: float = 0, **kw) -> None:
        self._enqueue("poly", {"token": token}, {
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread_pct": spread_pct,
        })

    def push_ev(self, token: str, phase: str, ev: float, p_up: float = 0,
                sigma: float = 0, p_flip: float = 0, ev_tail: float = 0,
                z_score: float = 0, delta_log: float = 0, delta_usd: float = 0,
                speed_advantage: bool = False, ev_threshold: float = 0,
                remaining: float = 0, tail_condition: bool = False, **kw) -> None:
        self._enqueue("ev", {"token": token, "phase": phase}, {
            "ev": ev,
            "p_up": p_up,
            "sigma": sigma,
            "p_flip": p_flip,
            "ev_tail": ev_tail,
            "z_score": z_score,
            "delta_log": delta_log,
            "delta_usd": delta_usd,
            "speed_advantage": 1 if speed_advantage else 0,
            "ev_threshold": ev_threshold,
            "remaining": remaining,
            "tail_condition": 1 if tail_condition else 0,
        })

    def push_phase_state(self, phase: str, remaining: float,
                         a_trades: int, b_trades: int,
                         tail_done: bool = False, **kw) -> None:
        self._enqueue("phase", {"phase": phase}, {
            "remaining": remaining,
            "a_trades": a_trades,
            "b_trades": b_trades,
            "tail_done": 1 if tail_done else 0,
        })

    def push_position(self, token: str, phase: str, is_open: bool,
                      entry_price: float = 0, current_price: float = 0,
                      unrealized_pnl: float = 0, realized_pnl: float = 0,
                      pnl_pct: float = 0, quantity: float = 0, **kw) -> None:
        self._enqueue("position", {"token": token, "phase": phase}, {
            "is_open": 1 if is_open else 0,
            "entry_price": entry_price,
            "current_price": current_price,
            "unrealized_pnl": unrealized_pnl,
            "realized_pnl": realized_pnl,
            "pnl_pct": pnl_pct,
            "quantity": quantity,
        })

    def push_latency(self, gap_ms: float, btc_ts: float = 0,
                     poly_ts: float = 0, **kw) -> None:
        self._enqueue("latency", {}, {
            "gap_ms": gap_ms,
            "btc_ts": btc_ts,
            "poly_ts": poly_ts,
        })

    def push_jump(self, direction: int, move_bps: float,
                  jump_ts: float = 0, anchor_price: float = 0, **kw) -> None:
        self._enqueue("jump", {"direction": str(direction)}, {
            "move_bps": move_bps,
            "jump_ts": jump_ts,
            "anchor_price": anchor_price,
        })

    def push_trade(self, phase: str, token: str, side: str,
                   price: float, qty: float, reason: str = "", **kw) -> None:
        self._enqueue("trade", {"phase": phase, "token": token, "side": side}, {
            "price": price,
            "qty": qty,
            "reason": reason,
        })

    def push_safety(self, speed_advantage: bool, slippage_ok: bool,
                    volatility_ok: bool, depth_ok: bool,
                    jump_fresh: bool, phase_ok: bool, **kw) -> None:
        self._enqueue("safety", {}, {
            "speed_advantage": 1 if speed_advantage else 0,
            "slippage_ok": 1 if slippage_ok else 0,
            "volatility_ok": 1 if volatility_ok else 0,
            "depth_ok": 1 if depth_ok else 0,
            "jump_fresh": 1 if jump_fresh else 0,
            "phase_ok": 1 if phase_ok else 0,
        })

    def push_depth(self, token: str, levels: list[dict], **kw) -> None:
        fields: dict[str, Any] = {}
        for i, lvl in enumerate(levels[:6]):
            prefix = f"l{i}_"
            fields[prefix + "price"] = float(lvl.get("price", 0))
            fields[prefix + "qty"] = float(lvl.get("qty", 0))
            fields[prefix + "side"] = str(lvl.get("side", ""))
        self._enqueue("depth", {"token": token}, fields)

    def push_pnl_summary(self, phase_a_realized: float = 0,
                         phase_b_realized: float = 0,
                         phase_a_unrealized: float = 0,
                         phase_b_unrealized: float = 0,
                         round_pnl: float = 0,
                         cumulative_a: float = 0,
                         cumulative_b: float = 0, **kw) -> None:
        self._enqueue("pnl", {}, {
            "phase_a_realized": phase_a_realized,
            "phase_b_realized": phase_b_realized,
            "phase_a_unrealized": phase_a_unrealized,
            "phase_b_unrealized": phase_b_unrealized,
            "round_pnl": round_pnl,
            "cumulative_a": cumulative_a,
            "cumulative_b": cumulative_b,
        })

    def push_rollover(self, old_slug: str, new_slug: str,
                      rounds: int = 0, **kw) -> None:
        self._enqueue("phase", {"event": "rollover"}, {
            "old_slug": old_slug,
            "new_slug": new_slug,
            "rounds": rounds,
        })

    def push_anomaly(self, anomaly_type: str, detail: str = "", **kw) -> None:
        self._enqueue("anomaly", {"anomaly_type": anomaly_type}, {
            "detail": detail,
        })
