"""Market management mixin: rollover, subscription, instrument handling."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from nautilus_trader.model.identifiers import Venue, InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.enums import BookType


class PDEMarketMixin:
    """Handles market rollover, subscription management, and instrument lifecycle."""
    
    # Required attributes from base class
    current_market_slug: str | None
    instrument: Instrument | None
    down_instrument: Instrument | None
    config: Any
    cache: Any
    clock: Any
    log: Any
    next_market_slug: str | None
    next_instrument: Instrument | None
    next_down_instrument: Instrument | None
    _next_refresh_pending: bool
    _rollover_in_progress: bool
    _rollover_retry_count: int
    _prewarm_lead_seconds: float
    _post_rollover_subscribe_pending: bool
    _post_rollover_switch_ts: float
    _post_rollover_retry_count: int
    _last_post_rollover_retry_ts: float
    _post_rollover_retry_interval_sec: float
    _post_rollover_retry_max: int
    _provider_refresh_pending: bool
    _next_provider_refresh_ts: float
    start_ts: float | None
    start_price: dict
    _resubscribe_attempts: int
    last_quote_tick_ts: float
    
    def _get_current_slug(self) -> str:
        """Get current market slug based on aligned timestamp."""
        now = datetime.now(timezone.utc)
        interval = self.config.market_interval_minutes
        aligned_minute = (now.minute // interval) * interval
        market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
        return f"{self.config.market_base_slug}-{int(market_time.timestamp())}"
    
    def _get_slug_for_timestamp(self, ts_sec: int) -> str:
        """Generate slug for specific timestamp."""
        return f"{self.config.market_base_slug}-{int(ts_sec)}"
    
    def _get_round_boundaries(self, now_ts: float | None = None) -> tuple[int, int]:
        """Get current and next round start timestamps."""
        if now_ts is None:
            now_ts = self.clock.timestamp()
        interval_sec = self.config.market_interval_minutes * 60
        current_start = int(now_ts // interval_sec) * interval_sec
        next_start = current_start + interval_sec
        return current_start, next_start

    def _extract_token_id_int(self, inst: Instrument) -> int:
        """Extract numeric token id from instrument id string."""
        token_id = str(inst.id).split("-")[-1].split(".")[0]
        try:
            return int(token_id)
        except Exception:
            return 0

    def _extract_outcome_label(self, inst: Instrument) -> str:
        """Best-effort extract outcome label for one instrument."""
        info = getattr(inst, 'info', {}) or {}

        # Direct single-value fields first.
        for key in ("outcome", "token_outcome", "side", "label", "name"):
            val = str(info.get(key, "")).strip().lower()
            if val:
                return val

        # Some payloads keep outcomes under nested tokens list.
        inst_token_id = str(inst.id).split("-")[-1].split(".")[0]
        tokens = info.get("tokens")
        if isinstance(tokens, list):
            for t in tokens:
                if not isinstance(t, dict):
                    continue
                token_key = str(
                    t.get("token_id")
                    or t.get("tokenId")
                    or t.get("clob_token_id")
                    or t.get("clobTokenId")
                    or ""
                )
                if token_key and token_key != inst_token_id:
                    continue
                outcome = str(
                    t.get("outcome")
                    or t.get("name")
                    or t.get("label")
                    or ""
                ).strip().lower()
                if outcome:
                    return outcome

        return ""
    
    def _find_market_instruments_by_slug(self, slug: str) -> tuple[Instrument | None, Instrument | None]:
        """Find Up/Down instruments matching slug using instrument info."""
        all_instruments = self.cache.instruments(venue=Venue("POLYMARKET"))
        self.log.debug(f"🔍 Searching for slug '{slug}' in {len(all_instruments)} instruments")
        matching_instruments = []
        
        for inst in all_instruments:
            # Use instrument info.market_slug for matching (not ID)
            info = getattr(inst, 'info', {}) or {}
            market_slug = info.get("market_slug", "")
            if market_slug == slug:
                matching_instruments.append(inst)
                self.log.debug(f"   [OK] Found match: {inst.id} (outcome={info.get('outcome')})")
        
        if not matching_instruments:
            self.log.info(f"[ERROR] No instruments found for slug: {slug}")
            return None, None
        
        self.log.info(f"[OK] Found {len(matching_instruments)} instruments for {slug}")
        
        # Identify Up vs Down by explicit Polymarket outcome labels
        up_matched = None
        down_matched = None
        
        for inst in matching_instruments:
            outcome = self._extract_outcome_label(inst)

            if outcome in ("up", "yes"):
                up_matched = inst
            elif outcome in ("down", "no"):
                down_matched = inst

        if up_matched is None or down_matched is None:
            outcomes = [self._extract_outcome_label(inst) for inst in matching_instruments]
            instruments_with_tokens = [(self._extract_token_id_int(inst), inst) for inst in matching_instruments]
            instruments_with_tokens.sort(key=lambda x: x[0])

            # Deterministic fallback for markets where adapter omits outcome labels.
            # Keep legacy convention in this repo: lower token_id -> UP, higher token_id -> DOWN.
            if len(instruments_with_tokens) >= 2:
                up_matched = instruments_with_tokens[0][1]
                down_matched = instruments_with_tokens[-1][1]
                self.log.warning(
                    f"[WARN] Missing outcome labels for {slug}. outcomes={outcomes}. "
                    f"Fallback token_id mapping applied: UP={instruments_with_tokens[0][0]}, "
                    f"DOWN={instruments_with_tokens[-1][0]}"
                )
            else:
                self.log.warning(
                    f"[WARN] Missing outcome labels for {slug}. outcomes={outcomes}. "
                    "Insufficient instruments for fallback mapping."
                )
                return None, None

        return up_matched, down_matched
    
    def _subscribe_current_market(self) -> None:
        """Subscribe to current market Up/Down tokens."""
        slug = self._get_current_slug()
        self.log.info(f"[SERVER] Attempting to subscribe to market: {slug}")
        if slug == self.current_market_slug:
            self.log.info(f"   Already subscribed to {slug}, skipping")
            return
        
        if not self._rollover_in_progress:
            # Unsubscribe old instruments
            for old_inst in (self.instrument, self.down_instrument):
                if old_inst is None:
                    continue
                try:
                    self.unsubscribe_quote_ticks(old_inst.id)
                    self.unsubscribe_order_book_deltas(old_inst.id)
                except Exception:
                    pass
            self._rollover_in_progress = True
            self._rollover_retry_count = 0
        
        # Find instruments in cache
        up_matched, down_matched = self._find_market_instruments_by_slug(slug)
        
        if up_matched is None or down_matched is None:
            # Instruments not found, trigger refresh and retry
            self._rollover_retry_count += 1
            if self._rollover_retry_count <= 3:
                self.log.warning(
                    f"[WARN]  Instruments for {slug} not found "
                    f"(retry {self._rollover_retry_count}/3), refreshing..."
                )
                if not self._next_refresh_pending:
                    self._next_refresh_pending = True
                    self.request_instruments(Venue("POLYMARKET"))
                    self.log.info(f"[REFRESH] Requested instrument refresh for next market: {slug}")
            return
        
        # Found both instruments, commit the rollover
        old_slug = self.current_market_slug
        self.current_market_slug = slug
        self._rollover_in_progress = False
        self._rollover_retry_count = 0
        
        self.instrument = up_matched
        self.down_instrument = down_matched

        up_outcome = str((getattr(up_matched, 'info', {}) or {}).get('outcome', '')).strip().lower()
        down_outcome = str((getattr(down_matched, 'info', {}) or {}).get('outcome', '')).strip().lower()
        self.log.info(
            f"🧭 Mapping {slug}: up_id={up_matched.id} (outcome={up_outcome}) | "
            f"down_id={down_matched.id} (outcome={down_outcome})"
        )
        
        # Subscribe to new instruments
        self.subscribe_quote_ticks(up_matched.id)
        self.subscribe_order_book_deltas(up_matched.id, book_type=BookType.L2_MBP)
        
        self.subscribe_quote_ticks(down_matched.id)
        self.subscribe_order_book_deltas(down_matched.id, book_type=BookType.L2_MBP)
        
        self.log.info(
            f"[OK] Subscribed to {slug}: "
            f"up={up_matched.id}, down={down_matched.id}"
        )
        
        # Push initial phase state so dashboard shows Round immediately
        if hasattr(self, 'live_server') and self.live_server is not None:
            self.live_server.push_phase_state(
                phase='A', remaining=self.config.market_interval_minutes * 60,
                a_trades=0, b_trades=0, tail_done=False, btc_round=slug
            )
        
        # Initialize start_ts so tick processing doesn't skip phase_state push
        if not hasattr(self, 'start_ts') or self.start_ts is None:
            self.start_ts = self._calculate_round_start_ts()
            self.log.info(f"[TIME] Initialized start_ts={self.start_ts}")
        
        self._post_rollover_subscribe_pending = True
        self._post_rollover_switch_ts = self.clock.timestamp()
        self._post_rollover_retry_count = 0
        self._last_post_rollover_retry_ts = self._post_rollover_switch_ts
    
    def _prewarm_next_market(self) -> None:
        """Pre-subscribe to next market before rollover (10s lead time)."""
        _, next_start = self._get_round_boundaries()
        next_slug = self._get_slug_for_timestamp(next_start)
        
        if next_slug == self.current_market_slug or next_slug == self.next_market_slug:
            return
        
        # Find next market instruments
        up_matched, down_matched = self._find_market_instruments_by_slug(next_slug)
        
        if up_matched is None or down_matched is None:
            if not self._next_refresh_pending:
                self._next_refresh_pending = True
                self.request_instruments(Venue("POLYMARKET"))
            return
        
        # Store for activation
        self.next_market_slug = next_slug
        self.next_instrument = up_matched
        self.next_down_instrument = down_matched
        
        # Subscribe to next market's data feeds NOW so data flows before boundary
        self.subscribe_quote_ticks(up_matched.id)
        self.subscribe_order_book_deltas(up_matched.id, book_type=BookType.L2_MBP)
        self.subscribe_quote_ticks(down_matched.id)
        self.subscribe_order_book_deltas(down_matched.id, book_type=BookType.L2_MBP)
        
        self.log.info(
            f"🔥 Prewarmed next market: {next_slug} "
            f"up={up_matched.id} down={down_matched.id} (data feeds subscribed)"
        )
    
    def _activate_prewarmed_market(self, target_slug: str) -> bool:
        """Activate prewarmed market instruments and subscribe to data feeds."""
        if self.next_market_slug != target_slug or self.next_instrument is None:
            return False
        
        old_up = self.instrument
        old_down = self.down_instrument
        
        self.current_market_slug = target_slug
        self.instrument = self.next_instrument
        self.down_instrument = self.next_down_instrument
        
        self.next_market_slug = None
        self.next_instrument = None
        self.next_down_instrument = None
        self._next_refresh_pending = False
        
        # Unsubscribe old instruments
        for old_inst in (old_up, old_down):
            if old_inst is None:
                continue
            if self.instrument and old_inst.id == self.instrument.id:
                continue
            if self.down_instrument and old_inst.id == self.down_instrument.id:
                continue
            try:
                self.unsubscribe_quote_ticks(old_inst.id)
                self.unsubscribe_order_book_deltas(old_inst.id)
            except Exception:
                pass
        
        # Subscribe to new instruments' data feeds
        if self.instrument:
            self.subscribe_quote_ticks(self.instrument.id)
            self.subscribe_order_book_deltas(self.instrument.id, book_type=BookType.L2_MBP)
        if self.down_instrument:
            self.subscribe_quote_ticks(self.down_instrument.id)
            self.subscribe_order_book_deltas(self.down_instrument.id, book_type=BookType.L2_MBP)
        
        self.log.info(f"[OK] Activated prewarmed market: {target_slug} (subscribed to data feeds)")
        return True
    
    def _force_resubscribe(self) -> None:
        """Force resubscribe to recover from WebSocket disconnect."""
        # Subscribe-only retry to avoid unsubscribe errors while WS is not connected yet.
        if self.instrument:
            self.subscribe_quote_ticks(self.instrument.id)
            self.subscribe_order_book_deltas(self.instrument.id, book_type=BookType.L2_MBP)
            self.log.info(f"[REFRESH] Resubscribed Up: {self.instrument.id}")
        
        if self.down_instrument:
            self.subscribe_quote_ticks(self.down_instrument.id)
            self.subscribe_order_book_deltas(self.down_instrument.id, book_type=BookType.L2_MBP)
            self.log.info(f"[REFRESH] Resubscribed Down: {self.down_instrument.id}")
    
    def _on_instruments_refreshed(self, request_id) -> None:
        """Callback after instrument refresh completes."""
        self._next_refresh_pending = False
        self.log.info("[REFRESH] Provider refresh complete, retrying subscription...")
        self._subscribe_current_market()
    
    def _schedule_next_provider_refresh(self) -> None:
        """Schedule proactive provider refresh."""
        interval_min = getattr(self.config, 'proactive_refresh_interval_min', 10.0)
        self._next_provider_refresh_ts = self.clock.timestamp() + interval_min * 60
        self.log.info(f"[SCHED] Scheduled provider refresh in {interval_min}min")
    
    def _cleanup_expired_instruments(self) -> None:
        """Clean up expired instruments from cache."""
        all_instruments = self.cache.instruments(venue=Venue("POLYMARKET"))
        _, next_start = self._get_round_boundaries()
        next_slug = self._get_slug_for_timestamp(next_start)
        
        expired_count = 0
        for inst in all_instruments:
            inst_str = str(inst.id)
            if self.current_market_slug and self.current_market_slug in inst_str:
                continue
            if next_slug in inst_str:
                continue
            if self.next_market_slug and self.next_market_slug in inst_str:
                continue
            # Instrument is expired, remove from cache
            try:
                self.cache.remove_instrument(inst.id)
                expired_count += 1
            except Exception:
                pass
        
        if expired_count > 0:
            self.log.debug(f"🧹 Cleaned up {expired_count} expired instruments")
