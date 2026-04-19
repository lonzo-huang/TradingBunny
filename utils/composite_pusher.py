# utils/composite_pusher.py
"""
Composite Live Pusher — fans out real-time pushes to multiple backends.

Backends:
  1. LiveStreamServer  (WebSocket → browser HTML dashboard, port 8765)
  2. GrafanaLivePusher (HTTP POST → Grafana Live channels)

Both backends share the same push method signatures, so this wrapper
simply delegates every call to all active backends.
"""

import logging
from typing import Any

from utils.live_stream_server import LiveStreamServer
from utils.grafana_live_pusher import GrafanaLivePusher

logger = logging.getLogger(__name__)


class CompositeLivePusher:
    """Delegates real-time push calls to all registered backends.

    Usage:
        pusher = CompositeLivePusher()
        pusher.add(LiveStreamServer())
        pusher.add(GrafanaLivePusher(grafana_url="http://localhost:3000"))
        pusher.start()

        pusher.push_btc_tick(price=71000, delta_usd=50, move_bps=3.2)
        # → calls both LiveStreamServer.push_btc_tick and GrafanaLivePusher.push_btc_tick
    """

    def __init__(self):
        self._backends: list = []

    def add(self, backend) -> None:
        """Register a push backend (must have push_xxx methods)."""
        self._backends.append(backend)

    def start(self) -> None:
        for b in self._backends:
            try:
                b.start()
            except Exception as e:
                logger.warning("Failed to start backend %s: %s", type(b).__name__, e)

    def stop(self) -> None:
        for b in self._backends:
            try:
                b.stop()
            except Exception as e:
                logger.warning("Failed to stop backend %s: %s", type(b).__name__, e)

    # ── Push methods (same signatures as LiveStreamServer / GrafanaLivePusher) ──

    def push_btc_tick(self, **kw) -> None:
        self._fan("push_btc_tick", kw)

    def push_poly_tick(self, **kw) -> None:
        self._fan("push_poly_tick", kw)

    def push_ev(self, **kw) -> None:
        self._fan("push_ev", kw)

    def push_phase_state(self, **kw) -> None:
        self._fan("push_phase_state", kw)

    def push_position(self, **kw) -> None:
        self._fan("push_position", kw)

    def push_latency(self, **kw) -> None:
        self._fan("push_latency", kw)

    def push_jump(self, **kw) -> None:
        self._fan("push_jump", kw)

    def push_trade(self, **kw) -> None:
        self._fan("push_trade", kw)

    def push_safety(self, **kw) -> None:
        self._fan("push_safety", kw)

    def push_depth(self, **kw) -> None:
        self._fan("push_depth", kw)

    def push_pnl_summary(self, **kw) -> None:
        self._fan("push_pnl_summary", kw)

    def push_rollover(self, **kw) -> None:
        self._fan("push_rollover", kw)

    def push_anomaly(self, **kw) -> None:
        self._fan("push_anomaly", kw)

    # ── Internal ────────────────────────────────────────────────────────

    def _fan(self, method_name: str, kwargs: dict[str, Any]) -> None:
        for b in self._backends:
            try:
                getattr(b, method_name)(**kwargs)
            except Exception as e:
                # Silently ignore — one backend failing shouldn't block the other
                pass
