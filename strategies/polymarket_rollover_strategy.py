# strategies/polymarket_rollover_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide
from polymarket.market_rollover import MarketRolloverManager

class PolymarketRolloverStrategyConfig(StrategyConfig):
    market_base_slug: str = "btc-updown-5m"
    market_interval_minutes: int = 5
    trade_size: Decimal = Decimal("100")
    confidence_threshold: Decimal = Decimal("0.6")

class PolymarketRolloverStrategy(Strategy):
    """支持自动市场轮转的 Polymarket 策略"""
    
    def __init__(self, config: PolymarketRolloverStrategyConfig) -> None:
        super().__init__(config)
        self.rollover_manager = None
        self.current_instrument_id = None
        self.last_signal = None
    
    def on_start(self) -> None:
        # 初始化轮转管理器
        self.rollover_manager = MarketRolloverManager(
            base_slug=self.config.market_base_slug,
            interval_minutes=self.config.market_interval_minutes,
        )
        
        # 异步连接
        asyncio.create_task(self._initialize())
        
        self.log.info("Polymarket Rollover Strategy started")
    
    async def _initialize(self) -> None:
        """异步初始化"""
        await self.rollover_manager.connect()
        
        # 获取当前市场
        instrument_id_str = self.rollover_manager.get_current_instrument_id()
        if instrument_id_str:
            self.current_instrument_id = InstrumentId.from_str(instrument_id_str)
            self.subscribe_quote_ticks(self.current_instrument_id)
            self.log.info(f"Subscribed to: {self.current_instrument_id}")
        
        # 设置轮转检查定时器
        self.clock.set_timer(
            "rollover_check",
            timedelta(minutes=1),
            callback=self._check_rollover,
        )
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        if self.rollover_manager:
            asyncio.create_task(self.rollover_manager.disconnect())
        self.log.info("Polymarket Rollover Strategy stopped")
    
    def _check_rollover(self) -> None:
        """检查市场轮转"""
        if self.rollover_manager.should_rollover():
            self.log.info("Market rollover detected")
            asyncio.create_task(self._handle_rollover())
    
    async def _handle_rollover(self) -> None:
        """处理市场轮转"""
        # 1. 取消所有当前市场订单
        self.cancel_all_orders()
        
        # 2. 等待轮转完成
        await self.rollover_manager.rollover()
        
        # 3. 取消旧市场订阅
        if self.current_instrument_id:
            self.unsubscribe_quote_ticks(self.current_instrument_id)
        
        # 4. 订阅新市场
        new_instrument_id_str = self.rollover_manager.get_current_instrument_id()
        if new_instrument_id_str:
            self.current_instrument_id = InstrumentId.from_str(new_instrument_id_str)
            self.subscribe_quote_ticks(self.current_instrument_id)
            self.log.info(f"Switched to new market: {self.current_instrument_id}")
        
        # 5. 重置策略状态
        self.last_signal = None
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """处理报价"""
        if not self.current_instrument_id or tick.instrument_id != self.current_instrument_id:
            return
        
        # 计算 YES/NO 价格
        yes_price = float(tick.ask_price)  # YES 价格
        no_price = 1.0 - yes_price  # NO 价格 (二元市场)
        
        # 交易信号
        if yes_price > float(self.config.confidence_threshold):
            signal = "YES"
        elif yes_price < (1.0 - float(self.config.confidence_threshold)):
            signal = "NO"
        else:
            signal = None
        
        # 执行交易
        if signal and signal != self.last_signal:
            self._execute_trade(signal, tick)
            self.last_signal = signal
    
    def _execute_trade(self, signal: str, tick: QuoteTick) -> None:
        """执行交易"""
        if signal == "YES":
            order = self.order_factory.market(
                instrument_id=self.current_instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.config.trade_size),
                tags=["POLYMARKET_YES"],
            )
        else:  # NO
            order = self.order_factory.market(
                instrument_id=self.current_instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.config.trade_size),
                tags=["POLYMARKET_NO"],
            )
        
        self.submit_order(order)
        self.log.info(f"Executed {signal} trade at {tick.ask_price}")