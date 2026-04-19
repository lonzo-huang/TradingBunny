"""SQLite persistence for PDE live/sandbox runs."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any


class PDEPersistenceStore:
    """Durable event/tick store for PDE strategy."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def close(self) -> None:
        with self._lock:
            self._conn.commit()
            self._conn.close()

    def start_run(self, run_id: str, mode: str, strategy: str, metadata: dict[str, Any] | None = None) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO runs(run_id, mode, strategy, started_at_ns, started_at_iso, metadata_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    mode,
                    strategy,
                    int(now.timestamp() * 1_000_000_000),
                    now.isoformat(),
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            self._conn.commit()

    def finish_run(self, run_id: str, summary: dict[str, Any] | None = None) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._conn.execute(
                """
                UPDATE runs
                SET ended_at_ns = ?, ended_at_iso = ?, summary_json = ?
                WHERE run_id = ?
                """,
                (
                    int(now.timestamp() * 1_000_000_000),
                    now.isoformat(),
                    json.dumps(summary or {}, ensure_ascii=False),
                    run_id,
                ),
            )
            self._conn.commit()

    def insert_order_event(self, run_id: str, event_type: str, event: Any) -> None:
        ts_ns, ts_iso = self._extract_event_time(event)
        payload = self._to_json_dict(event)
        self._execute(
            """
            INSERT INTO orders(
                run_id, ts_ns, ts_iso, event_type,
                client_order_id, venue_order_id, instrument_id,
                side, quantity, price, status, payload_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                ts_ns,
                ts_iso,
                event_type,
                self._get(event, "client_order_id"),
                self._get(event, "venue_order_id"),
                self._get(event, "instrument_id"),
                self._get(event, "order_side"),
                self._to_float(self._get(event, "quantity")),
                self._to_float(self._get(event, "price")) or self._to_float(self._get(event, "avg_px_open")),
                self._get(event, "order_status") or self._get(event, "status"),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def insert_fill_event(self, run_id: str, event: Any) -> None:
        ts_ns, ts_iso = self._extract_event_time(event)
        payload = self._to_json_dict(event)
        self._execute(
            """
            INSERT INTO fills(
                run_id, ts_ns, ts_iso,
                client_order_id, trade_id, instrument_id,
                side, quantity, price, fee, payload_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                ts_ns,
                ts_iso,
                self._get(event, "client_order_id"),
                self._get(event, "trade_id") or self._get(event, "venue_trade_id"),
                self._get(event, "instrument_id"),
                self._to_side_str(self._get(event, "order_side") or self._get(event, "is_buy")),
                self._to_float(self._get(event, "last_qty")) or self._to_float(self._get(event, "quantity")),
                self._to_float(self._get(event, "last_px")) or self._to_float(self._get(event, "price")),
                self._to_float(self._get(event, "commission")) or self._to_float(self._get(event, "fee")),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def insert_position_event(
        self,
        run_id: str,
        event_type: str,
        token: str,
        phase: str,
        event: Any,
        position_size: float,
        avg_price: float,
        unrealized_pnl: float,
        realized_pnl: float,
        round_slug: str = "",
        entry_context: dict | None = None,
    ) -> None:
        ts_ns, ts_iso = self._extract_event_time(event)
        payload = self._to_json_dict(event)
        self._execute(
            """
            INSERT INTO positions(
                run_id, ts_ns, ts_iso, event_type,
                token, phase, instrument_id,
                position_size, avg_price, unrealized_pnl, realized_pnl,
                payload_json, round_slug, entry_context_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                ts_ns,
                ts_iso,
                event_type,
                token,
                phase,
                self._get(event, "instrument_id"),
                position_size,
                avg_price,
                unrealized_pnl,
                realized_pnl,
                json.dumps(payload, ensure_ascii=False),
                round_slug or "",
                json.dumps(entry_context or {}, ensure_ascii=False),
            ),
        )

    def insert_pnl_snapshot(
        self,
        run_id: str,
        event_type: str,
        token: str,
        phase: str,
        realized: float,
        unrealized: float,
        round_pnl: float,
        total_pnl: float,
    ) -> None:
        now = datetime.now(timezone.utc)
        self._execute(
            """
            INSERT INTO pnl(
                run_id, ts_ns, ts_iso, event_type,
                token, phase, realized_pnl, unrealized_pnl,
                round_pnl, total_pnl
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                int(now.timestamp() * 1_000_000_000),
                now.isoformat(),
                event_type,
                token,
                phase,
                realized,
                unrealized,
                round_pnl,
                total_pnl,
            ),
        )

    def insert_market_data(
        self,
        run_id: str,
        source: str,
        instrument_id: str,
        bid: float | None = None,
        ask: float | None = None,
        last: float | None = None,
        mid: float | None = None,
        volume: float | None = None,
        event_ts_ns: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if event_ts_ns is None:
            event_ts_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
        ts_iso = datetime.fromtimestamp(event_ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()

        self._execute(
            """
            INSERT INTO market_data(
                run_id, ts_ns, ts_iso, source, instrument_id,
                bid, ask, last, mid, volume, extra_json
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                event_ts_ns,
                ts_iso,
                source,
                instrument_id,
                bid,
                ask,
                last,
                mid,
                volume,
                json.dumps(extra or {}, ensure_ascii=False),
            ),
        )

    def insert_account_state(self, run_id: str, event: Any) -> None:
        ts_ns, ts_iso = self._extract_event_time(event)
        payload = self._to_json_dict(event)
        self._execute(
            """
            INSERT INTO account_states(run_id, ts_ns, ts_iso, account_id, payload_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                run_id,
                ts_ns,
                ts_iso,
                self._get(event, "account_id"),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def latest_run_id(self) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT run_id FROM runs ORDER BY started_at_ns DESC LIMIT 1"
            ).fetchone()
            return row[0] if row else None

    def _execute(self, sql: str, params: tuple[Any, ...]) -> None:
        with self._lock:
            self._conn.execute(sql, params)
            self._conn.commit()

    def _create_tables(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    mode TEXT,
                    strategy TEXT,
                    started_at_ns INTEGER,
                    started_at_iso TEXT,
                    ended_at_ns INTEGER,
                    ended_at_iso TEXT,
                    metadata_json TEXT,
                    summary_json TEXT
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts_ns INTEGER,
                    ts_iso TEXT,
                    event_type TEXT,
                    client_order_id TEXT,
                    venue_order_id TEXT,
                    instrument_id TEXT,
                    side TEXT,
                    quantity REAL,
                    price REAL,
                    status TEXT,
                    payload_json TEXT
                );

                CREATE TABLE IF NOT EXISTS fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts_ns INTEGER,
                    ts_iso TEXT,
                    client_order_id TEXT,
                    trade_id TEXT,
                    instrument_id TEXT,
                    side TEXT,
                    quantity REAL,
                    price REAL,
                    fee REAL,
                    payload_json TEXT
                );

                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts_ns INTEGER,
                    ts_iso TEXT,
                    event_type TEXT,
                    token TEXT,
                    phase TEXT,
                    instrument_id TEXT,
                    position_size REAL,
                    avg_price REAL,
                    unrealized_pnl REAL,
                    realized_pnl REAL,
                    payload_json TEXT,
                    round_slug TEXT DEFAULT '',
                    entry_context_json TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS pnl (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts_ns INTEGER,
                    ts_iso TEXT,
                    event_type TEXT,
                    token TEXT,
                    phase TEXT,
                    realized_pnl REAL,
                    unrealized_pnl REAL,
                    round_pnl REAL,
                    total_pnl REAL
                );

                CREATE TABLE IF NOT EXISTS market_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts_ns INTEGER,
                    ts_iso TEXT,
                    source TEXT,
                    instrument_id TEXT,
                    bid REAL,
                    ask REAL,
                    last REAL,
                    mid REAL,
                    volume REAL,
                    extra_json TEXT
                );

                CREATE TABLE IF NOT EXISTS account_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT,
                    ts_ns INTEGER,
                    ts_iso TEXT,
                    account_id TEXT,
                    payload_json TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_orders_run_ts ON orders(run_id, ts_ns);
                CREATE INDEX IF NOT EXISTS idx_fills_run_ts ON fills(run_id, ts_ns);
                CREATE INDEX IF NOT EXISTS idx_positions_run_ts ON positions(run_id, ts_ns);
                CREATE INDEX IF NOT EXISTS idx_pnl_run_ts ON pnl(run_id, ts_ns);
                CREATE INDEX IF NOT EXISTS idx_market_run_ts ON market_data(run_id, ts_ns);
                CREATE INDEX IF NOT EXISTS idx_account_run_ts ON account_states(run_id, ts_ns);
                """
            )
            # Migration: add new columns to existing databases
            for col, definition in [
                ("round_slug", "TEXT DEFAULT ''"),
                ("entry_context_json", "TEXT DEFAULT '{}'"),
            ]:
                try:
                    cur.execute(f"ALTER TABLE positions ADD COLUMN {col} {definition}")
                except Exception:
                    pass  # Column already exists
            self._conn.commit()

    @staticmethod
    def _to_side_str(value: Any) -> str:
        """Normalise order side to 'BUY' or 'SELL' string."""
        if value is None:
            return ""
        s = str(value).upper()
        if s in ("BUY", "1", "TRUE"):
            return "BUY"
        if s in ("SELL", "2", "FALSE"):
            return "SELL"
        return s  # e.g. already "BUY"/"SELL" string

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _get(obj: Any, attr: str) -> Any:
        if obj is None:
            return None
        if hasattr(obj, attr):
            return getattr(obj, attr)
        if isinstance(obj, dict):
            return obj.get(attr)
        return None

    def _extract_event_time(self, event: Any) -> tuple[int, str]:
        ts_ns = self._get(event, "ts_event")
        if ts_ns is None:
            ts_ns = self._get(event, "ts_init")
        if ts_ns is None:
            ts_ns = int(datetime.now(timezone.utc).timestamp() * 1_000_000_000)
        ts_ns = int(ts_ns)
        ts_iso = datetime.fromtimestamp(ts_ns / 1_000_000_000, tz=timezone.utc).isoformat()
        return ts_ns, ts_iso

    def _to_json_dict(self, event: Any) -> dict[str, Any]:
        if event is None:
            return {}
        if isinstance(event, dict):
            source = event.items()
        else:
            source = ((k, getattr(event, k)) for k in dir(event) if not k.startswith("_"))

        data: dict[str, Any] = {}
        for k, v in source:
            if callable(v):
                continue
            if isinstance(v, (str, int, float, bool)) or v is None:
                data[k] = v
            else:
                data[k] = str(v)
        return data
