# strategies/polymarket_strategy.py
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from prometheus_client import Gauge, Counter, start_http_server

from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import Venue


class PolymarketStrategyConfig(StrategyConfig):
    market_base_slug: str               # 如 "btc-updown-5m"
    market_interval_minutes: int = 5
    trade_size: Decimal = Decimal("100")
    auto_rollover: bool = True


class PolymarketStrategy(Strategy):
    """
    Polymarket BTC Up/Down 5 分钟滚动市场纸交易策略。

    架构：
    - 数据：Polymarket RTDS（真实价格），Instrument 由 DataClient 通过
            event_slug_builder 在启动时预加载到 Cache
    - 执行：Sandbox 本地虚拟撮合（假钱）
    - outcome 命名：Polymarket BTC Up/Down 市场用 "Up"/"Down"，不是 "Yes"/"No"
    """

    def __init__(self, config: PolymarketStrategyConfig) -> None:
        super().__init__(config)
        self.current_market_slug: str | None = None
        self.current_token_id: str | None = None
        self.instrument: Instrument | None = None
        self.down_instrument: Instrument | None = None  # 添加 Down token instrument
        self.position_open: bool = False
        self.down_position_open: bool = False  # Down token 持仓状态
        self.last_rollover_check: datetime | None = None  # 记录上次检查时间

        # 数据刷新频率监控
        self.last_up_tick_time: int | None = None
        self.last_down_tick_time: int | None = None
        self.tick_count_up: int = 0
        self.tick_count_down: int = 0
        self.last_frequency_report: datetime | None = None

        # Prometheus 指标
        self._setup_prometheus_metrics()

    def _setup_prometheus_metrics(self) -> None:
        """初始化 Prometheus 监控指标"""
        # 价格指标
        self.price_gauge = Gauge(
            'polymarket_price',
            'Current token price',
            ['token_type', 'price_type']  # token_type: up/down, price_type: bid/ask
        )

        # PNL 指标
        self.unrealized_pnl_gauge = Gauge(
            'polymarket_unrealized_pnl',
            'Unrealized PnL per position',
            ['token_type']
        )
        self.realized_pnl_gauge = Gauge(
            'polymarket_realized_pnl',
            'Realized PnL per position (can be negative)',
            ['token_type']
        )

        # 交易统计
        self.orders_counter = Counter(
            'polymarket_orders_total',
            'Total orders submitted',
            ['token_type', 'side']  # side: buy/sell
        )
        self.filled_orders_counter = Counter(
            'polymarket_filled_orders_total',
            'Total filled orders',
            ['token_type', 'side']
        )

        # 持仓指标
        self.position_size_gauge = Gauge(
            'polymarket_position_size',
            'Current position size',
            ['token_type']
        )
        self.position_entry_price_gauge = Gauge(
            'polymarket_position_entry_price',
            'Position entry price',
            ['token_type']
        )

        # 市场数据频率
        self.tick_counter = Counter(
            'polymarket_ticks_total',
            'Total quote ticks received',
            ['token_type']
        )

        # 策略状态
        self.market_slug_info = Gauge(
            'polymarket_current_market_slug',
            'Current market slug identifier',
            ['slug']
        )

        self.log.info("📊 Prometheus metrics initialized")

    # ── 生命周期 ──────────────────────────────────────────────────────────

    def on_start(self) -> None:
        self.log.info("🚀 Starting Polymarket BTC Up/Down Paper Trading")
        self.log.info(f"   Base slug        : {self.config.market_base_slug}")
        self.log.info(f"   Interval (min)   : {self.config.market_interval_minutes}")
        self.log.info(f"   Trade size (USDC): {self.config.trade_size}")

        # 启动 Prometheus HTTP 服务器 (端口 8000)
        try:
            start_http_server(8000)
            self.log.info("📊 Prometheus metrics server started on http://localhost:8000")
            self.log.info("   Metrics endpoint: http://localhost:8000/metrics")
        except Exception as e:
            self.log.warning(f"⚠️  Failed to start Prometheus server: {e}")

        self._subscribe_current_market()

        if self.config.auto_rollover:
            self.clock.set_timer(
                name="market_rollover_check",
                interval=timedelta(minutes=1),
                callback=self._on_rollover_timer,
            )

    def on_stop(self) -> None:
        self.clock.cancel_timer("market_rollover_check")
        # 取消所有订阅
        instruments_to_unsub = []
        if self.instrument:
            instruments_to_unsub.append(self.instrument.id)
        if self.down_instrument:
            instruments_to_unsub.append(self.down_instrument.id)
        
        for instrument_id in instruments_to_unsub:
            self.cancel_all_orders(instrument_id=instrument_id)
            self.unsubscribe_quote_ticks(instrument_id)
            
        self.log.info("🛑 Strategy stopped.")

    def on_reset(self) -> None:
        self.instrument = None
        self.down_instrument = None
        self.current_token_id = None
        self.position_open = False
        self.down_position_open = False
        self.current_market_slug = None
        self.last_rollover_check = None

    # ── slug 计算 ─────────────────────────────────────────────────────────

    def _get_current_slug(self) -> str:
        now = datetime.now(timezone.utc)
        interval = self.config.market_interval_minutes
        aligned_minute = (now.minute // interval) * interval
        market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
        return f"{self.config.market_base_slug}-{int(market_time.timestamp())}"

    # ── 市场订阅（从 Cache 查找）─────────────────────────────────────────

    def _subscribe_current_market(self) -> None:
        """
        从 Cache 里枚举 POLYMARKET instruments，找到当前 slug + "Up"/"Down" token 订阅。
        
        改进：同时订阅 Up 和 Down token，支持双向交易。
        """
        slug = self._get_current_slug()
        if slug == self.current_market_slug:
            return

        # 取消旧订阅
        old_instruments = []
        if self.instrument and self.current_market_slug:
            old_instruments.append(self.instrument)
        if self.down_instrument and self.current_market_slug:
            old_instruments.append(self.down_instrument)
            
        for old_inst in old_instruments:
            self.log.info(f"📤 Unsubscribing: {old_inst.id}")
            self.unsubscribe_quote_ticks(old_inst.id)
            self.cancel_all_orders(instrument_id=old_inst.id)

        self.current_market_slug = slug
        self.log.info(f"📥 Looking for market in cache: {slug}")

        all_instruments = self.cache.instruments(venue=Venue("POLYMARKET"))
        self.log.info(f"   Cache has {len(all_instruments)} POLYMARKET instruments")
        
        # 🔍 调试：打印所有可用的 instruments
        self.log.info("🔍 Available instruments in cache:")
        for i, inst in enumerate(all_instruments[:5]):  # 只显示前5个避免日志过长
            info = getattr(inst, 'info', {}) or {}
            market_slug = info.get("market_slug", "")
            outcome = info.get("outcome", "")
            self.log.info(f"   [{i}] {inst.id} | market_slug={market_slug} | outcome={outcome}")
        if len(all_instruments) > 5:
            self.log.info(f"   ... and {len(all_instruments) - 5} more instruments")

        # ── 查找 Up 和 Down token ──────────────────────────────
        up_matched = None
        down_matched = None
        
        # 先收集所有匹配当前 slug 的 instruments
        matching_instruments = []
        for inst in all_instruments:
            info = getattr(inst, 'info', {}) or {}
            market_slug = info.get("market_slug", "")
            
            if market_slug == slug:
                matching_instruments.append(inst)
        
        self.log.info(f"🔍 Found {len(matching_instruments)} instruments for slug {slug}")
        
        # 如果找到 2 个 instruments，假设第一个是 Up，第二个是 Down
        # （通常 Polymarket 的 Up/Down token 会一起加载）
        if len(matching_instruments) >= 2:
            # 尝试按 outcome 匹配
            for inst in matching_instruments:
                info = getattr(inst, 'info', {}) or {}
                outcome = info.get("outcome", "").lower()
                
                if outcome == "up" or outcome == "yes":
                    up_matched = inst
                    self.log.info(f"✅ Match by outcome (Up): {inst.id}")
                elif outcome == "down" or outcome == "no":
                    down_matched = inst
                    self.log.info(f"✅ Match by outcome (Down): {inst.id}")
            
            # 如果 outcome 匹配失败，按 token ID 排序，较小的为 Up，较大的为 Down
            if up_matched is None or down_matched is None:
                self.log.info("🔍 Outcome empty, using token ID to distinguish Up/Down...")
                
                # 获取 token ID 并排序
                instruments_with_tokens = []
                for inst in matching_instruments:
                    token_id = str(inst.id).split("-")[-1].split(".")[0] if hasattr(inst, 'id') else ""
                    try:
                        # 尝试将 token ID 转换为整数以便排序
                        token_int = int(token_id) if token_id.isdigit() else 0
                    except:
                        token_int = 0
                    instruments_with_tokens.append((token_int, inst))
                
                # 按 token ID 排序
                instruments_with_tokens.sort(key=lambda x: x[0])
                
                # 分配 Up 和 Down（排序后的第一个为 Up，第二个为 Down）
                if len(instruments_with_tokens) >= 1 and up_matched is None:
                    up_matched = instruments_with_tokens[0][1]
                    self.log.info(f"✅ Assigned as Up (lower token ID): {up_matched.id}")
                
                if len(instruments_with_tokens) >= 2 and down_matched is None:
                    down_matched = instruments_with_tokens[1][1]
                    self.log.info(f"✅ Assigned as Down (higher token ID): {down_matched.id}")
        
        # 如果只有一个匹配的 instrument，默认为 Up
        elif len(matching_instruments) == 1:
            up_matched = matching_instruments[0]
            self.log.warning(f"⚠️  Only one instrument found for {slug}, treating as Up: {up_matched.id}")
        
        # ── 备用匹配逻辑（如果上述都失败）───────────────────────────────────
        if up_matched is None or down_matched is None:
            self.log.info("🔍 Trying fallback matching...")
            for inst in all_instruments:
                info = getattr(inst, 'info', {}) or {}
                market_slug = info.get("market_slug", "")
                outcome = info.get("outcome", "").lower()
                
                if market_slug == slug:
                    if up_matched is None and outcome in ["up", "yes"]:
                        up_matched = inst
                        self.log.warning(f"⚠️  Using fallback Up: {inst.id}")
                    elif down_matched is None and outcome in ["down", "no"]:
                        down_matched = inst
                        self.log.warning(f"⚠️  Using fallback Down: {inst.id}")

        # 订阅找到的 instruments
        subscribed_any = False
        
        if up_matched:
            self.instrument = up_matched
            info = getattr(up_matched, 'info', {}) or {}
            self.log.info(
                f"📊 Subscribing to Up: {up_matched.id}\n"
                f"   outcome={info.get('outcome')} | "
                f"price={info.get('tokens', [{}])[0].get('price', '?')}"
            )
            self.subscribe_quote_ticks(up_matched.id)
            subscribed_any = True
        else:
            self.log.error(f"❌ No Up token found for {slug}")
            self.instrument = None
            
        if down_matched:
            self.down_instrument = down_matched
            info = getattr(down_matched, 'info', {}) or {}
            self.log.info(
                f"📊 Subscribing to Down: {down_matched.id}\n"
                f"   outcome={info.get('outcome')} | "
                f"price={info.get('tokens', [{}])[0].get('price', '?')}"
            )
            self.subscribe_quote_ticks(down_matched.id)
            subscribed_any = True
        else:
            self.log.warning(f"⚠️  No Down token found for {slug}")
            self.down_instrument = None
            
        if subscribed_any:
            self.current_token_id = str(up_matched.id).split(".")[0] if up_matched else str(down_matched.id).split(".")[0]
        else:
            self.log.error(f"❌ No instruments found for {slug}")
            self.log.warning("⚠️  This may be because the market slug is not pre-loaded.")
            self.log.warning("   The instrument provider only loads slugs at startup.")
            self.log.warning("   If running for >30 minutes, consider restarting to load new markets.")
            
            # 🔍 调试：显示当前时间计算
            now = datetime.now(timezone.utc)
            interval = self.config.market_interval_minutes
            aligned_minute = (now.minute // interval) * interval
            market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
            self.log.info(f"🔍 Current time: {now}")
            self.log.info(f"🔍 Aligned time: {market_time}")
            self.log.info(f"🔍 Timestamp: {int(market_time.timestamp())}")
            self.log.info(f"🔍 Expected slug: {slug}")

    # ── NT 回调：Instrument 更新 ──────────────────────────────────────────

    def on_instrument(self, instrument: Instrument) -> None:
        if instrument.id.venue.value != "POLYMARKET":
            return
        self.log.info(f"📩 Instrument update: {instrument.id}")
        if self.instrument is None:
            self._subscribe_current_market()

    # ── 定时器：市场滚动 ──────────────────────────────────────────────────

    def _on_rollover_timer(self, event) -> None:
        new_slug = self._get_current_slug()
        if new_slug == self.current_market_slug:
            return
            
        self.log.info(f"🔄 Rollover: {self.current_market_slug} → {new_slug}")
        
        # 取消所有订单并重置持仓状态
        if self.instrument:
            self.cancel_all_orders(instrument_id=self.instrument.id)
        if self.down_instrument:
            self.cancel_all_orders(instrument_id=self.down_instrument.id)
            
        self.position_open = False
        self.down_position_open = False
        
        # 重新订阅市场
        self._subscribe_current_market()
        
        # 记录检查时间
        self.last_rollover_check = datetime.now(timezone.utc)

    # ── 行情处理 ──────────────────────────────────────────────────────────

    def on_quote_tick(self, tick: QuoteTick) -> None:
        # 处理 Up token 的行情
        if self.instrument and tick.instrument_id == self.instrument.id:
            self._process_up_tick(tick)
        
        # 处理 Down token 的行情
        elif self.down_instrument and tick.instrument_id == self.down_instrument.id:
            self._process_down_tick(tick)
    
    def _process_up_tick(self, tick: QuoteTick) -> None:
        """处理 Up token 的行情数据"""
        # 更新数据刷新频率监控
        self._update_tick_frequency(tick.ts_event, is_up=True)

        up_ask = float(tick.ask_price)   # 买 Up 的成本
        up_bid = float(tick.bid_price)   # 卖 Up 所得

        # 更新 Prometheus 价格指标
        self.price_gauge.labels(token_type='up', price_type='ask').set(up_ask)
        self.price_gauge.labels(token_type='up', price_type='bid').set(up_bid)
        self.tick_counter.labels(token_type='up').inc()

        # 获取 Down token 价格（如果可用）
        down_ask = down_bid = None
        if self.down_instrument:
            # 从缓存获取最新的 Down token 价格
            down_ticks = self.cache.quote_ticks(instrument_id=self.down_instrument.id)
            if down_ticks:
                latest_down = down_ticks[-1]
                down_ask = float(latest_down.ask_price)
                down_bid = float(latest_down.bid_price)
                # 更新 Down 价格指标
                self.price_gauge.labels(token_type='down', price_type='ask').set(down_ask)
                self.price_gauge.labels(token_type='down', price_type='bid').set(down_bid)

        # 每 0.5 秒打印一次
        if tick.ts_event % 500_000_000 < 1_000_000:
            if down_ask is not None:
                self.log.info(
                    f"📊 [{self.current_market_slug}] "
                    f"Up_bid={up_bid:.3f} | Up_ask={up_ask:.3f} | "
                    f"Down_bid={down_bid:.3f} | Down_ask={down_ask:.3f} | "
                    f"spread={(up_ask - down_ask):.3f}"
                )
            else:
                self.log.info(
                    f"📊 [{self.current_market_slug}] "
                    f"Up_bid={up_bid:.3f} | Up_ask={up_ask:.3f} | "
                    f"Down: N/A"
                )

        # ── Up token 策略逻辑 ─────────────────────────────
        if not self.position_open:
            if up_ask < 0.40:  # Up 概率低于 40% 时买入
                self._open_long_up(tick)
        else:
            if up_ask > 0.60:  # Up 概率高于 60% 时卖出
                self._close_up_position(tick)
    
    def _process_down_tick(self, tick: QuoteTick) -> None:
        """处理 Down token 的行情数据"""
        # 更新数据刷新频率监控
        self._update_tick_frequency(tick.ts_event, is_up=False)

        down_ask = float(tick.ask_price)  # 买 Down 的成本
        down_bid = float(tick.bid_price)  # 卖 Down 所得

        # 更新 Prometheus 指标
        self.price_gauge.labels(token_type='down', price_type='ask').set(down_ask)
        self.price_gauge.labels(token_type='down', price_type='bid').set(down_bid)
        self.tick_counter.labels(token_type='down').inc()

        # 每 0.5 秒打印一次（仅在 Up token 不可用时）
        if tick.ts_event % 500_000_000 < 1_000_000 and not self.instrument:
            self.log.info(
                f"📊 [{self.current_market_slug}] "
                f"Down_bid={down_bid:.3f} | Down_ask={down_ask:.3f} | "
                f"Up: N/A"
            )

        # ── Down token 策略逻辑 ─────────────────────────────
        if not self.down_position_open:
            if down_ask < 0.40:  # Down 概率低于 40% 时买入
                self._open_long_down(tick)
        else:
            if down_ask > 0.60:  # Down 概率高于 60% 时卖出
                self._close_down_position(tick)
    
    def _update_tick_frequency(self, ts_event: int, is_up: bool) -> None:
        """更新数据刷新频率统计"""
        now = datetime.now(timezone.utc)
        
        if is_up:
            self.tick_count_up += 1
            if self.last_up_tick_time is not None:
                interval_ns = ts_event - self.last_up_tick_time
                interval_ms = interval_ns / 1_000_000  # 转换为毫秒
                if interval_ms > 0:  # 避免除零
                    frequency_hz = 1000 / interval_ms  # Hz = 1000ms / interval_ms
                    self.log.debug(f"🔄 Up token interval: {interval_ms:.1f}ms ({frequency_hz:.1f}Hz)")
            self.last_up_tick_time = ts_event
        else:
            self.tick_count_down += 1
            if self.last_down_tick_time is not None:
                interval_ns = ts_event - self.last_down_tick_time
                interval_ms = interval_ns / 1_000_000
                if interval_ms > 0:
                    frequency_hz = 1000 / interval_ms
                    self.log.debug(f"🔄 Down token interval: {interval_ms:.1f}ms ({frequency_hz:.1f}Hz)")
            self.last_down_tick_time = ts_event
        
        # 每 30 秒报告一次频率统计
        if self.last_frequency_report is None or (now - self.last_frequency_report) >= timedelta(seconds=30):
            self._report_tick_frequency()
            self.last_frequency_report = now
    
    def _report_tick_frequency(self) -> None:
        """报告数据刷新频率统计"""
        now = datetime.now(timezone.utc)
        
        # 计算 Up token 频率
        up_freq_str = "N/A"
        if self.last_up_tick_time is not None and self.tick_count_up > 1:
            # 使用总计数和运行时间估算平均频率
            elapsed_time = (now - self.last_frequency_report).total_seconds() if self.last_frequency_report else 30
            avg_freq = self.tick_count_up / elapsed_time if elapsed_time > 0 else 0
            up_freq_str = f"{avg_freq:.1f} ticks/sec"
        
        # 计算 Down token 频率
        down_freq_str = "N/A"
        if self.last_down_tick_time is not None and self.tick_count_down > 1:
            elapsed_time = (now - self.last_frequency_report).total_seconds() if self.last_frequency_report else 30
            avg_freq = self.tick_count_down / elapsed_time if elapsed_time > 0 else 0
            down_freq_str = f"{avg_freq:.1f} ticks/sec"
        
        self.log.info(
            f"📈 Data Frequency Report [{self.current_market_slug}]:\n"
            f"   Up token: {self.tick_count_up} ticks, {up_freq_str}\n"
            f"   Down token: {self.tick_count_down} ticks, {down_freq_str}"
        )

    # ── 下单 ──────────────────────────────────────────────────────────────

    def _open_long_up(self, tick: QuoteTick) -> None:
        self.log.info(
            f"📝 [PAPER] BUY UP @ {tick.ask_price} "
            f"| size={self.config.trade_size} USDC"
        )
        # 更新订单计数
        self.orders_counter.labels(token_type='up', side='buy').inc()
        self.position_entry_price_gauge.labels(token_type='up').set(float(tick.ask_price))

        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["PAPER_BUY_UP"],
        )
        self.submit_order(order)
        self.position_open = True
        self.position_size_gauge.labels(token_type='up').set(float(self.config.trade_size))

    def _close_up_position(self, tick: QuoteTick) -> None:
        self.log.info(f"📝 [PAPER] CLOSE UP @ {tick.ask_price} (Take Profit)")
        # 更新订单计数
        self.orders_counter.labels(token_type='up', side='sell').inc()

        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["PAPER_CLOSE_UP"],
        )
        self.submit_order(order)
        self.position_open = False
        self.position_size_gauge.labels(token_type='up').set(0)
        self.log.info("💰 [PAPER] Up position close order submitted!")
    
    def _open_long_down(self, tick: QuoteTick) -> None:
        if not self.down_instrument:
            self.log.warning("⚠️  Down instrument not available for trading")
            return

        self.log.info(
            f"📝 [PAPER] BUY DOWN @ {tick.ask_price} "
            f"| size={self.config.trade_size} USDC"
        )
        # 更新订单计数
        self.orders_counter.labels(token_type='down', side='buy').inc()
        self.position_entry_price_gauge.labels(token_type='down').set(float(tick.ask_price))

        order = self.order_factory.market(
            instrument_id=self.down_instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.down_instrument.make_qty(self.config.trade_size),
            tags=["PAPER_BUY_DOWN"],
        )
        self.submit_order(order)
        self.down_position_open = True
        self.position_size_gauge.labels(token_type='down').set(float(self.config.trade_size))
    
    def _close_down_position(self, tick: QuoteTick) -> None:
        if not self.down_instrument:
            self.log.warning("⚠️  Down instrument not available for trading")
            return

        self.log.info(f"📝 [PAPER] CLOSE DOWN @ {tick.ask_price} (Take Profit)")
        # 更新订单计数
        self.orders_counter.labels(token_type='down', side='sell').inc()

        order = self.order_factory.market(
            instrument_id=self.down_instrument.id,
            order_side=OrderSide.SELL,
            quantity=self.down_instrument.make_qty(self.config.trade_size),
            tags=["PAPER_CLOSE_DOWN"],
        )
        self.submit_order(order)
        self.down_position_open = False
        self.position_size_gauge.labels(token_type='down').set(0)
        self.log.info("💰 [PAPER] Down position close order submitted!")

    # ── 订单 / 持仓事件 ───────────────────────────────────────────────────

    def on_order_filled(self, event) -> None:
        self.log.info(
            f"✅ [SANDBOX] Filled: {event.order_side.name} "
            f"@ {event.last_px} | qty={event.last_qty} (Fake USDC)"
        )
        # 更新成交计数
        token_type = 'up' if 'UP' in str(event.instrument_id) else 'down'
        side = 'buy' if event.order_side == OrderSide.BUY else 'sell'
        self.filled_orders_counter.labels(token_type=token_type, side=side).inc()

    def on_position_opened(self, event) -> None:
        self.log.info(
            f"💼 [SANDBOX] Position opened "
            f"qty={event.quantity} avg_px={event.avg_px_open}"
        )
        # 更新持仓指标
        token_type = 'up' if self.instrument and event.instrument_id == self.instrument.id else 'down'
        self.position_size_gauge.labels(token_type=token_type).set(float(event.quantity))
        self.position_entry_price_gauge.labels(token_type=token_type).set(float(event.avg_px_open))

    def on_position_changed(self, event) -> None:
        self.log.info(
            f"🔄 [SANDBOX] Position changed "
            f"unrealized_pnl={event.unrealized_pnl}"
        )
        # 更新 PNL 指标
        token_type = 'up' if self.instrument and event.instrument_id == self.instrument.id else 'down'
        self.unrealized_pnl_gauge.labels(token_type=token_type).set(float(event.unrealized_pnl))

    def on_position_closed(self, event) -> None:
        self.log.info(
            f"💰 [SANDBOX] Position closed! "
            f"Realized PnL: {event.realized_pnl} (Fake USDC)"
        )
        # 更新 PNL 指标
        token_type = 'up' if self.instrument and event.instrument_id == self.instrument.id else 'down'
        self.realized_pnl_gauge.labels(token_type=token_type).set(float(event.realized_pnl))
        self.unrealized_pnl_gauge.labels(token_type=token_type).set(0)
        self.position_size_gauge.labels(token_type=token_type).set(0)