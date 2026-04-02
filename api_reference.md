# Nautilus Trader API Reference 汇总

> **文档版本**: develop 分支 (2026 年 3 月)  
> **适用对象**: 量化开发者、策略研究员、系统架构师  
> **用途**: AI 工具编程参考文档

---

## 目录

1. [核心模块 (Core)](#1-核心模块-core)
2. [模型模块 (Model)](#2-模型模块-model)
3. [交易模块 (Trading)](#3-交易模块-trading)
4. [数据模块 (Data)](#4-数据模块-data)
5. [执行模块 (Execution)](#5-执行模块-execution)
6. [投资组合模块 (Portfolio)](#6-投资组合模块-portfolio)
7. [风险模块 (Risk)](#7-风险模块-risk)
8. [回测模块 (Backtest)](#8-回测模块-backtest)
9. [实盘模块 (Live)](#9-实盘模块-live)
10. [持久化模块 (Persistence)](#10-持久化模块-persistence)
11. [分析模块 (Analysis)](#11-分析模块-analysis)
12. [配置模块 (Config)](#12-配置模块-config)
13. [适配器模块 (Adapters)](#13-适配器模块-adapters)
14. [序列化模块 (Serialization)](#14-序列化模块-serialization)

---

## 1. 核心模块 (Core)

### 1.1 概述

`nautilus_trader.core` 提供基础原语和工具，是所有其他模块的依赖。

### 1.2 主要类

| 类 | 用途 | 示例 |
|------|------|------|
| `UUID4` | 生成 UUID v4 | `UUID4()` |
| `Timestamp` | 纳秒级时间戳 | `Timestamp(1630000000000000000)` |
| `Duration` | 时间间隔 | `Duration(60_000_000_000)` |
| `Sequence` | 序列号管理 | `Sequence(0)` |

### 1.3 时间工具

```python
from nautilus_trader.core.datetime import (
    dt_to_unix_nanos,
    unix_nanos_to_dt,
    format_iso8601,
    parse_iso8601,
)

# 日期时间转换
nanos = dt_to_unix_nanos(datetime(2024, 1, 1, 12, 0, 0))
dt = unix_nanos_to_dt(nanos)

# ISO 8601 格式化
iso_str = format_iso8601(nanos)
nanos = parse_iso8601(iso_str)
```

### 1.4 标识符

```python
from nautilus_trader.core.identifiers import (
    AccountId,
    ClientId,
    InstrumentId,
    OrderId,
    PositionId,
    StrategyId,
    TraderId,
    Venue,
)

# 创建标识符
account_id = AccountId("BINANCE-123456")
client_id = ClientId("BINANCE")
instrument_id = InstrumentId.from_str("BTCUSDT.BINANCE")
order_id = OrderId("O-123456")
position_id = PositionId("P-123456")
strategy_id = StrategyId("MyStrategy-001")
trader_id = TraderId("TRADER-001")
venue = Venue("BINANCE")
```

### 1.5 消息总线

```python
from nautilus_trader.core.message import MessageBus

# 发布/订阅
msgbus = MessageBus(trader_id=trader_id)
msgbus.subscribe(topic="my_topic", handler=my_handler)
msgbus.publish(topic="my_topic", message=my_message)

# 请求/响应
response = msgbus.request(
    topic="my_topic",
    request=my_request,
    timeout_ms=5000,
)
```

### 1.6 数据结构

```python
from nautilus_trader.core.data import Data
from nautilus_trader.core.message import Event, Command

# 自定义数据类
class MyData(Data):
    def __init__(self, value: float, ts_event: int, ts_init: int):
        self.value = value
        self._ts_event = ts_event
        self._ts_init = ts_init
    
    @property
    def ts_event(self) -> int:
        return self._ts_event
    
    @property
    def ts_init(self) -> int:
        return self._ts_init
```

---

## 2. 模型模块 (Model)

### 2.1 概述

`nautilus_trader.model` 定义所有领域模型，包括订单、持仓、市场数据等。

### 2.2 金融工具 (Instruments)

```python
from nautilus_trader.model.instruments import (
    CurrencyPair,
    Equity,
    FuturesContract,
    OptionContract,
    CryptoPerpetual,
    SyntheticInstrument,
)

# 货币对
instrument = CurrencyPair(
    instrument_id=InstrumentId.from_str("BTC/USDT.BINANCE"),
    symbol=Symbol("BTC/USDT"),
    base_currency=Currency.from_str("BTC"),
    quote_currency=Currency.from_str("USDT"),
    settlement_currency=Currency.from_str("USDT"),
    price_precision=8,
    size_precision=8,
    price_increment=Price.from_str("0.00000001"),
    size_increment=Quantity.from_str("0.00000001"),
    multiplier=Quantity.from_int(1),
    lot_size=Quantity.from_str("0.00001000"),
    max_quantity=Quantity.from_str("9000"),
    min_quantity=Quantity.from_str("0.00001000"),
    max_notional=Money(10_000_000, "USDT"),
    min_notional=Money(10, "USDT"),
    max_price=Price.from_str("1000000"),
    min_price=Price.from_str("0.01"),
    ts_event=0,
    ts_init=0,
)

# 期货合约
instrument = FuturesContract(
    instrument_id=InstrumentId.from_str("ESU4.GLBX"),
    symbol=Symbol("ESU4"),
    asset_class=AssetClass.INDEX,
    underlying="ES",
    currency=Currency.from_str("USD"),
    price_precision=2,
    size_precision=0,
    price_increment=Price.from_str("0.25"),
    size_increment=Quantity.from_int(1),
    multiplier=Quantity.from_int(50),
    lot_size=Quantity.from_int(1),
    max_quantity=Quantity.from_int(1000),
    min_quantity=Quantity.from_int(1),
    max_notional=None,
    min_notional=Money(1000, "USD"),
    max_price=None,
    min_price=None,
    expiration_date=pd.Timestamp("2024-09-20"),
    ts_event=0,
    ts_init=0,
)

# 期权合约
instrument = OptionContract(
    instrument_id=InstrumentId.from_str("AAPL240920C175.GLBX"),
    symbol=Symbol("AAPL240920C175"),
    asset_class=AssetClass.EQUITY,
    underlying="AAPL",
    currency=Currency.from_str("USD"),
    price_precision=2,
    size_precision=0,
    price_increment=Price.from_str("0.01"),
    size_increment=Quantity.from_int(1),
    multiplier=Quantity.from_int(100),
    lot_size=Quantity.from_int(1),
    expiration_date=pd.Timestamp("2024-09-20"),
    strike_price=Price.from_str("175.00"),
    option_kind=OptionKind.CALL,
    ts_event=0,
    ts_init=0,
)

# 永续合约
instrument = CryptoPerpetual(
    instrument_id=InstrumentId.from_str("BTCUSDT-PERP.BINANCE"),
    symbol=Symbol("BTCUSDT-PERP"),
    base_currency=Currency.from_str("BTC"),
    quote_currency=Currency.from_str("USDT"),
    settlement_currency=Currency.from_str("USDT"),
    price_precision=2,
    size_precision=5,
    price_increment=Price.from_str("0.01"),
    size_increment=Quantity.from_str("0.00001"),
    multiplier=Quantity.from_int(1),
    lot_size=Quantity.from_str("0.00001"),
    max_quantity=Quantity.from_str("1000"),
    min_quantity=Quantity.from_str("0.00001"),
    max_notional=Money(10_000_000, "USDT"),
    min_notional=Money(10, "USDT"),
    max_price=Price.from_str("1000000"),
    min_price=Price.from_str("0.01"),
    ts_event=0,
    ts_init=0,
)
```

### 2.3 订单 (Orders)

```python
from nautilus_trader.model.orders import (
    MarketOrder,
    LimitOrder,
    StopMarketOrder,
    StopLimitOrder,
    MarketIfTouchedOrder,
    LimitIfTouchedOrder,
    TrailingStopMarketOrder,
    TrailingStopLimitOrder,
)
from nautilus_trader.model.enums import OrderSide, TimeInForce, TriggerType

# 市价单
order = MarketOrder(
    trader_id=TraderId("TRADER-001"),
    strategy_id=StrategyId("MyStrategy-001"),
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    client_order_id=ClientOrderId("O-123456"),
    order_side=OrderSide.BUY,
    quantity=Quantity.from_str("0.1"),
    time_in_force=TimeInForce.GTC,
    reduce_only=False,
    quote_quantity=False,
    tags=["ENTRY"],
    ts_init=0,
)

# 限价单
order = LimitOrder(
    trader_id=TraderId("TRADER-001"),
    strategy_id=StrategyId("MyStrategy-001"),
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    client_order_id=ClientOrderId("O-123456"),
    order_side=OrderSide.BUY,
    quantity=Quantity.from_str("0.1"),
    price=Price.from_str("50000.00"),
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    post_only=True,
    reduce_only=False,
    display_qty=None,
    tags=["ENTRY"],
    ts_init=0,
)

# 止损市价单
order = StopMarketOrder(
    trader_id=TraderId("TRADER-001"),
    strategy_id=StrategyId("MyStrategy-001"),
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    client_order_id=ClientOrderId("O-123456"),
    order_side=OrderSide.SELL,
    quantity=Quantity.from_str("0.1"),
    trigger_price=Price.from_str("49000.00"),
    trigger_type=TriggerType.LAST_PRICE,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    reduce_only=False,
    tags=["STOP_LOSS"],
    ts_init=0,
)

# 止损限价单
order = StopLimitOrder(
    trader_id=TraderId("TRADER-001"),
    strategy_id=StrategyId("MyStrategy-001"),
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    client_order_id=ClientOrderId("O-123456"),
    order_side=OrderSide.SELL,
    quantity=Quantity.from_str("0.1"),
    price=Price.from_str("48900.00"),
    trigger_price=Price.from_str("49000.00"),
    trigger_type=TriggerType.LAST_PRICE,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    post_only=True,
    reduce_only=False,
    tags=["STOP_LOSS"],
    ts_init=0,
)

# 追踪止损市价单
order = TrailingStopMarketOrder(
    trader_id=TraderId("TRADER-001"),
    strategy_id=StrategyId("MyStrategy-001"),
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    client_order_id=ClientOrderId("O-123456"),
    order_side=OrderSide.SELL,
    quantity=Quantity.from_str("0.1"),
    trigger_type=TriggerType.LAST_PRICE,
    trailing_offset=Decimal("100"),
    trailing_offset_type=TrailingOffsetType.PRICE,
    activation_price=Price.from_str("50000.00"),
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    reduce_only=True,
    tags=["TRAILING_STOP"],
    ts_init=0,
)
```

### 2.4 持仓 (Positions)

```python
from nautilus_trader.model.position import Position
from nautilus_trader.model.enums import PositionSide

# 查询持仓属性
position: Position

# 标识符
position.id  # PositionId
position.instrument_id  # InstrumentId
position.account_id  # AccountId
position.trader_id  # TraderId
position.strategy_id  # StrategyId
position.opening_order_id  # ClientOrderId
position.closing_order_id  # Optional[ClientOrderId]

# 状态
position.side  # PositionSide (LONG/SHORT/FLAT)
position.entry  # OrderSide (BUY/SELL)
position.quantity  # Quantity
position.signed_qty  # Decimal
position.peak_qty  # Quantity
position.is_open  # bool
position.is_closed  # bool

# 价格
position.avg_px_open  # Optional[Price]
position.avg_px_close  # Optional[Price]

# PnL
position.realized_pnl  # Money
position.realized_return  # Decimal
position.unrealized_pnl(last_price: Price) -> Money
position.total_pnl(current_price: Price) -> Money

# 时间
position.ts_init  # int
position.ts_opened  # int
position.ts_last  # int
position.ts_closed  # Optional[int]
position.duration_ns  # Optional[int]
```

### 2.5 市场数据 (Market Data)

```python
from nautilus_trader.model.data import (
    QuoteTick,
    TradeTick,
    Bar,
    OrderBookDelta,
    OrderBookDeltas,
    OrderBookDepth10,
    InstrumentStatus,
    InstrumentClose,
)

# 报价 Tick
tick = QuoteTick(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    bid_price=Price.from_str("49999.00"),
    ask_price=Price.from_str("50001.00"),
    bid_size=Quantity.from_str("1.5"),
    ask_size=Quantity.from_str("2.0"),
    ts_event=1630000000000000000,
    ts_init=1630000000000000000,
)

# 成交 Tick
tick = TradeTick(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    price=Price.from_str("50000.00"),
    size=Quantity.from_str("0.5"),
    aggressor_side=AggressorSide.BUYER,
    trade_id=TradeId("123456"),
    ts_event=1630000000000000000,
    ts_init=1630000000000000000,
)

# K 线
bar = Bar(
    bar_type=BarType.from_str("BTCUSDT.BINANCE-1-MINUTE-LAST-INTERNAL"),
    open=Price.from_str("49900.00"),
    high=Price.from_str("50100.00"),
    low=Price.from_str("49800.00"),
    close=Price.from_str("50000.00"),
    volume=Quantity.from_str("100.5"),
    ts_event=1630000000000000000,
    ts_init=1630000000000000000,
)

# 订单簿增量
delta = OrderBookDelta(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    action=BookAction.UPDATE,
    order=OrderBookOrder(
        price=Price.from_str("50000.00"),
        size=Quantity.from_str("10.0"),
        order_id=123456,
    ),
    ts_event=1630000000000000000,
    ts_init=1630000000000000000,
)

# 订单簿深度快照
depth = OrderBookDepth10(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    bids=OrderBookSide(
        price_levels=[
            PriceLevel(price=Price.from_str("49999.00"), orders=[...]),
            # ... 最多 10 档
        ],
    ),
    asks=OrderBookSide(
        price_levels=[
            PriceLevel(price=Price.from_str("50001.00"), orders=[...]),
            # ... 最多 10 档
        ],
    ),
    ts_event=1630000000000000000,
    ts_init=1630000000000000000,
)
```

### 2.6 账户 (Accounts)

```python
from nautilus_trader.model.account import Account
from nautilus_trader.model.enums import AccountType

# 账户属性
account: Account

# 标识符
account.id  # AccountId
account.account_type  # AccountType (CASH/MARGIN/BETTING)
account.base_currency  # Optional[Currency]

# 状态
account.status  # AccountStatus
account.is_cash_account()  # bool
account.is_margin_account()  # bool

# 余额
account.balances()  # dict[Currency, AccountBalance]
account.balances_locked()  # dict[Currency, Money]
account.balances_free()  # dict[Currency, Money]

# 保证金
account.margins_init()  # dict[Currency, Money]
account.margins_maint()  # dict[Currency, Money]

# PnL
account.unrealized_pnls()  # dict[Currency, Money]
account.realized_pnls()  # dict[Currency, Money]

# 风险敞口
account.net_exposures()  # dict[Currency, Money]

# 统计
account.starting_balance()  # Money
account.peak_value()  # Money
account.value()  # Money
```

### 2.7 事件 (Events)

```python
from nautilus_trader.model.event import (
    OrderInitialized,
    OrderSubmitted,
    OrderAccepted,
    OrderRejected,
    OrderFilled,
    OrderCanceled,
    OrderUpdated,
    OrderExpired,
    PositionOpened,
    PositionChanged,
    PositionClosed,
    AccountState,
)

# 订单事件属性
event: OrderEvent

event.client_order_id  # ClientOrderId
event.order_type  # OrderType
event.order_side  # OrderSide
event.quantity  # Quantity
event.price  # Optional[Price]
event.trigger_price  # Optional[Price]
event.ts_event  # int
event.ts_init  # int

# 持仓事件属性
event: PositionEvent

event.position_id  # PositionId
event.instrument_id  # InstrumentId
event.strategy_id  # StrategyId
event.quantity  # Quantity
event.avg_px  # Price
event.ts_event  # int
event.ts_init  # int
```

### 2.8 值类型 (Value Types)

```python
from nautilus_trader.model.objects import Price, Quantity, Money

# Price
price = Price(100.50, precision=2)
price = Price.from_str("100.50")
price = Price.from_int(10050, precision=2)
price.as_decimal()  # Decimal
price.as_str()  # str
price.precision  # int

# Quantity
quantity = Quantity(100, precision=0)
quantity = Quantity.from_str("100.5")
quantity = Quantity.from_int(100, precision=0)
quantity.as_decimal()  # Decimal
quantity.as_str()  # str
quantity.precision  # int

# Money
money = Money(1000.50, "USD")
money = Money.from_str("1000.50 USD")
money.currency  # Currency
money.as_decimal()  # Decimal
money.as_str()  # str

# 算术运算
result = price1 + price2  # Price
result = quantity1 + quantity2  # Quantity
result = money1 + money2  # Money (同货币)
```

---

## 3. 交易模块 (Trading)

### 3.1 概述

`nautilus_trader.trading` 提供策略和执行相关的核心组件。

### 3.2 策略 (Strategy)

```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig

class MyStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    trade_size: Decimal

class MyStrategy(Strategy):
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.bar_count = 0
    
    # ========== 生命周期 ==========
    def on_start(self) -> None:
        """策略启动时调用"""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
    
    def on_stop(self) -> None:
        """策略停止时调用"""
        self.cancel_all_orders()
    
    def on_resume(self) -> None:
        """策略从停止状态恢复时调用"""
        pass
    
    def on_reset(self) -> None:
        """策略重置时调用"""
        self.bar_count = 0
    
    def on_save(self) -> dict[str, bytes]:
        """保存策略状态"""
        return {"bar_count": str(self.bar_count).encode()}
    
    def on_load(self, state: dict[str, bytes]) -> None:
        """加载策略状态"""
        self.bar_count = int(state["bar_count"].decode())
    
    def on_dispose(self) -> None:
        """策略最终清理时调用"""
        pass
    
    # ========== 数据处理器 ==========
    def on_order_book_deltas(self, deltas: OrderBookDeltas) -> None:
        """订单簿增量更新"""
        pass
    
    def on_order_book_depth(self, depth: OrderBookDepth10) -> None:
        """订单簿深度快照"""
        pass
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """报价 Tick"""
        pass
    
    def on_trade_tick(self, tick: TradeTick) -> None:
        """成交 Tick"""
        pass
    
    def on_bar(self, bar: Bar) -> None:
        """K 线"""
        self.bar_count += 1
    
    def on_data(self,  Data) -> None:
        """自定义数据"""
        pass
    
    def on_signal(self, signal) -> None:
        """信号"""
        pass
    
    def on_historical_data(self,  Data) -> None:
        """历史数据请求响应"""
        pass
    
    # ========== 订单事件处理器 ==========
    def on_order_initialized(self, event: OrderInitialized) -> None:
        pass
    
    def on_order_submitted(self, event: OrderSubmitted) -> None:
        pass
    
    def on_order_accepted(self, event: OrderAccepted) -> None:
        pass
    
    def on_order_rejected(self, event: OrderRejected) -> None:
        pass
    
    def on_order_filled(self, event: OrderFilled) -> None:
        pass
    
    def on_order_canceled(self, event: OrderCanceled) -> None:
        pass
    
    def on_order_updated(self, event: OrderUpdated) -> None:
        pass
    
    def on_order_expired(self, event: OrderExpired) -> None:
        pass
    
    def on_order_event(self, event: OrderEvent) -> None:
        """所有订单事件的通用处理器"""
        pass
    
    # ========== 持仓事件处理器 ==========
    def on_position_opened(self, event: PositionOpened) -> None:
        pass
    
    def on_position_changed(self, event: PositionChanged) -> None:
        pass
    
    def on_position_closed(self, event: PositionClosed) -> None:
        pass
    
    def on_position_event(self, event: PositionEvent) -> None:
        """所有持仓事件的通用处理器"""
        pass
    
    # ========== 账户事件处理器 ==========
    def on_account(self, account: Account) -> None:
        """账户状态更新"""
        pass
    
    # ========== 时间事件处理器 ==========
    def on_event(self, event: Event) -> None:
        """所有事件的通用处理器"""
        pass
```

### 3.3 订单工厂 (OrderFactory)

```python
from nautilus_trader.trading.strategy import Strategy

# 在策略中访问
order_factory = self.order_factory

# 市价单
order = order_factory.market(
    instrument_id=instrument_id,
    order_side=OrderSide.BUY,
    quantity=quantity,
    time_in_force=TimeInForce.GTC,
    reduce_only=False,
    quote_quantity=False,
    tags=["ENTRY"],
)

# 限价单
order = order_factory.limit(
    instrument_id=instrument_id,
    order_side=OrderSide.BUY,
    quantity=quantity,
    price=price,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    post_only=True,
    reduce_only=False,
    display_qty=None,
    tags=["ENTRY"],
)

# 止损市价单
order = order_factory.stop_market(
    instrument_id=instrument_id,
    order_side=OrderSide.SELL,
    quantity=quantity,
    trigger_price=trigger_price,
    trigger_type=TriggerType.LAST_PRICE,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    reduce_only=False,
    tags=["STOP_LOSS"],
)

# 止损限价单
order = order_factory.stop_limit(
    instrument_id=instrument_id,
    order_side=OrderSide.SELL,
    quantity=quantity,
    price=price,
    trigger_price=trigger_price,
    trigger_type=TriggerType.LAST_PRICE,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    post_only=True,
    reduce_only=False,
    tags=["STOP_LOSS"],
)

# 市价触及单
order = order_factory.market_if_touched(
    instrument_id=instrument_id,
    order_side=OrderSide.BUY,
    quantity=quantity,
    trigger_price=trigger_price,
    trigger_type=TriggerType.LAST_PRICE,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    reduce_only=False,
    tags=["ENTRY"],
)

# 限价触及单
order = order_factory.limit_if_touched(
    instrument_id=instrument_id,
    order_side=OrderSide.BUY,
    quantity=quantity,
    price=price,
    trigger_price=trigger_price,
    trigger_type=TriggerType.LAST_PRICE,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    post_only=True,
    reduce_only=False,
    tags=["ENTRY"],
)

# 追踪止损市价单
order = order_factory.trailing_stop_market(
    instrument_id=instrument_id,
    order_side=OrderSide.SELL,
    quantity=quantity,
    trigger_type=TriggerType.LAST_PRICE,
    trailing_offset=Decimal("100"),
    trailing_offset_type=TrailingOffsetType.PRICE,
    activation_price=activation_price,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    reduce_only=True,
    tags=["TRAILING_STOP"],
)

# 追踪止损限价单
order = order_factory.trailing_stop_limit(
    instrument_id=instrument_id,
    order_side=OrderSide.SELL,
    quantity=quantity,
    price=price,
    trigger_type=TriggerType.LAST_PRICE,
    trailing_offset=Decimal("100"),
    trailing_offset_type=TrailingOffsetType.PRICE,
    activation_price=activation_price,
    time_in_force=TimeInForce.GTC,
    expire_time=None,
    post_only=True,
    reduce_only=True,
    tags=["TRAILING_STOP"],
)

# 括号订单 (入场 + 止盈 + 止损)
bracket_orders = order_factory.bracket(
    instrument_id=instrument_id,
    order_side=OrderSide.BUY,
    quantity=quantity,
    entry_type=OrderType.LIMIT,
    entry_price=entry_price,
    tp_type=OrderType.LIMIT,
    tp_price=tp_price,
    sl_type=OrderType.STOP_MARKET,
    sl_trigger_price=sl_trigger_price,
    time_in_force=TimeInForce.GTC,
    tags=["BRACKET"],
)
```

### 3.4 订单列表 (OrderList)

```python
from nautilus_trader.model.orderlist import OrderList
from nautilus_trader.model.enums import OrderListType

# OCO (One-Cancels-Other)
order_list = OrderList(
    order_list_id=OrderListId("OL-123"),
    orders=[order1, order2],
    order_list_type=OrderListType.OCO,
)

# OTO (One-Triggers-Other)
order_list = OrderList(
    order_list_id=OrderListId("OL-123"),
    orders=[parent_order, child_order],
    order_list_type=OrderListType.OTO,
)

# OUO (One-Updates-Other)
order_list = OrderList(
    order_list_id=OrderListId("OL-123"),
    orders=[order1, order2],
    order_list_type=OrderListType.OUO,
)
```

### 3.5 执行算法 (ExecAlgorithm)

```python
from nautilus_trader.execution.algorithm import ExecAlgorithm

class TWAPExecAlgorithm(ExecAlgorithm):
    def __init__(self):
        super().__init__(algorithm_id=ExecAlgorithmId("TWAP"))
    
    def on_order(self, order: Order) -> None:
        """主订单处理"""
        pass
    
    def on_fill(self, order: Order, fill: OrderFilled) -> None:
        """成交处理"""
        pass
    
    def spawn_market(
        self,
        primary_order: Order,
        quantity: Quantity,
        tags: list[str] | None = None,
    ) -> MarketOrder:
        """生成市价子订单"""
        pass
    
    def spawn_limit(
        self,
        primary_order: Order,
        quantity: Quantity,
        price: Price,
        tags: list[str] | None = None,
    ) -> LimitOrder:
        """生成限价子订单"""
        pass
```

---

## 4. 数据模块 (Data)

### 4.1 概述

`nautilus_trader.data` 处理市场数据的请求、订阅和处理。

### 4.2 数据类型

```python
from nautilus_trader.model.data import (
    QuoteTick,
    TradeTick,
    Bar,
    OrderBookDelta,
    OrderBookDeltas,
    OrderBookDepth10,
    InstrumentStatus,
    InstrumentClose,
)
from nautilus_trader.core.data import Data

# 所有数据类型都继承自 Data 基类
# 必须实现 ts_event 和 ts_init 属性
```

### 4.3 数据请求

```python
from nautilus_trader.trading.strategy import Strategy

# 请求历史数据
def on_start(self) -> None:
    # 请求 K 线
    self.request_bars(
        bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-EXTERNAL"),
    )
    
    # 请求报价 Tick
    self.request_quote_ticks(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    )
    
    # 请求成交 Tick
    self.request_trade_ticks(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    )
    
    # 请求订单簿
    self.request_order_book_deltas(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    )
    
    # 请求工具定义
    self.request_instrument(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    )

# 处理历史数据
def on_historical_data(self,  Data) -> None:
    if isinstance(data, Bar):
        # 处理 K 线
        pass
    elif isinstance(data, QuoteTick):
        # 处理报价
        pass
```

### 4.4 数据订阅

```python
from nautilus_trader.trading.strategy import Strategy

# 订阅实时数据
def on_start(self) -> None:
    # 订阅 K 线
    self.subscribe_bars(
        bar_type=BarType.from_str("BTCUSDT.BINANCE-1-MINUTE-LAST-INTERNAL"),
    )
    
    # 订阅报价 Tick
    self.subscribe_quote_ticks(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    )
    
    # 订阅成交 Tick
    self.subscribe_trade_ticks(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    )
    
    # 订阅订单簿增量
    self.subscribe_order_book_deltas(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    )
    
    # 订阅订单簿深度
    self.subscribe_order_book_depth(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
        depth=10,
    )
    
    # 订阅订单簿定时快照
    self.subscribe_order_book_at_interval(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
        interval_ms=1000,
    )

# 取消订阅
def on_stop(self) -> None:
    self.unsubscribe_bars(bar_type)
    self.unsubscribe_quote_ticks(instrument_id)
    self.unsubscribe_trade_ticks(instrument_id)
    self.unsubscribe_order_book_deltas(instrument_id)
```

### 4.5 自定义数据

```python
from nautilus_trader.core.data import Data
from nautilus_trader.model.custom import customdataclass

# 使用装饰器定义自定义数据类
@customdataclass
class GreeksData(Data):
    instrument_id: InstrumentId = InstrumentId.from_str("ES.GLBX")
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0

# 发布自定义数据
self.publish_data(
    data_type=DataType(GreeksData, metadata={"category": 1}),
    data=GreeksData(...),
)

# 订阅自定义数据
self.subscribe_data(
    data_type=DataType(GreeksData, metadata={"category": 1}),
    client_id=ClientId("MY_ADAPTER"),
)

# 处理自定义数据
def on_data(self,  Data) -> None:
    if isinstance(data, GreeksData):
        self.log.info(f"Delta: {data.delta}")
```

### 4.6 信号

```python
# 发布信号
self.publish_signal(
    name="NEW_HIGHEST_PRICE",
    value="NEW_HIGHEST_PRICE",
    ts_event=bar.ts_event,
)

# 订阅信号
self.subscribe_signal("NEW_HIGHEST_PRICE")

# 处理信号
def on_signal(self, signal) -> None:
    if signal.value == "NEW_HIGHEST_PRICE":
        self.log.info("New highest price reached")
```

### 4.7 Bar 类型

```python
from nautilus_trader.model.bar import BarType, BarSpecification, PriceType

# 完整 BarType 格式
# {instrument_id}-{interval}-{aggregation}-{price_type}-{source}
bar_type = BarType.from_str("BTCUSDT.BINANCE-1-MINUTE-LAST-INTERNAL")

# 组成部分
bar_type.instrument_id  # InstrumentId
bar_type.specification  # BarSpecification
bar_type.specification.interval  # int (分钟)
bar_type.specification.aggregation  # AggregationType
bar_type.specification.price_type  # PriceType
bar_type.specification.source  # BarSource

# 创建 BarType
bar_type = BarType(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    specification=BarSpecification(
        step=1,
        aggregation=AggregationType.TIME,
        price_type=PriceType.LAST,
    ),
    source=BarSource.INTERNAL,
)

# 聚合类型
# TIME, TICK, VOLUME, VALUE, RENKO, 
# TICK_IMBALANCE, VOLUME_IMBALANCE, VALUE_IMBALANCE

# 价格类型
# BID, ASK, MID, LAST, MARK, INDEX
```

---

## 5. 执行模块 (Execution)

### 5.1 概述

`nautilus_trader.execution` 管理订单生命周期和执行。

### 5.2 订单提交

```python
from nautilus_trader.trading.strategy import Strategy

# 提交单个订单
self.submit_order(order)

# 提交订单列表
self.submit_order_list(order_list)

# 批量提交订单
self.submit_orders([order1, order2, order3])
```

### 5.3 订单修改

```python
# 修改订单数量
self.modify_order(
    order=order,
    quantity=Quantity.from_str("0.2"),
)

# 修改订单价格 (限价单)
self.modify_order(
    order=order,
    price=Price.from_str("51000.00"),
)

# 修改订单数量和价格
self.modify_order(
    order=order,
    quantity=Quantity.from_str("0.2"),
    price=Price.from_str("51000.00"),
)
```

### 5.4 订单取消

```python
# 取消单个订单
self.cancel_order(order)

# 取消多个订单
self.cancel_orders([order1, order2, order3])

# 取消所有订单
self.cancel_all_orders()

# 取消指定策略的所有订单
self.cancel_all_orders(strategy_id=strategy_id)

# 取消指定工具的所有订单
self.cancel_all_orders(instrument_id=instrument_id)
```

### 5.5 订单查询

```python
from nautilus_trader.trading.strategy import Strategy

# 通过 Cache 查询
order = self.cache.order(client_order_id)
orders = self.cache.orders()
orders_open = self.cache.orders_open()
orders_closed = self.cache.orders_closed()
orders_emulated = self.cache.orders_emulated()

# 过滤查询
orders = self.cache.orders(
    instrument_id=instrument_id,
    strategy_id=strategy_id,
    venue=venue,
)

# 状态检查
exists = self.cache.order_exists(client_order_id)
is_open = self.cache.is_order_open(client_order_id)
is_closed = self.cache.is_order_closed(client_order_id)
is_emulated = self.cache.is_order_emulated(client_order_id)
```

### 5.6 执行引擎配置

```python
from nautilus_trader.config import BacktestExecEngineConfig, LiveExecEngineConfig

# 回测执行引擎配置
config = BacktestExecEngineConfig(
    allow_overfills=False,  # 是否允许超量成交
)

# 实盘执行引擎配置
config = LiveExecEngineConfig(
    allow_overfills=False,
    reconciliation=True,  # 启用对账
    reconciliation_lookback_mins=1440,  # 对账回溯时间 (分钟)
)
```

### 5.7 订单模拟

```python
from nautilus_trader.model.enums import OrderType, TriggerType

# 可模拟的订单类型
# LIMIT, STOP_MARKET, STOP_LIMIT, MARKET_IF_TOUCHED,
# LIMIT_IF_TOUCHED, TRAILING_STOP_MARKET, TRAILING_STOP_LIMIT

# 模拟触发类型
# NO_TRIGGER, DEFAULT, BID_ASK, LAST_PRICE,
# DOUBLE_LAST, MARK_PRICE, INDEX_PRICE

# 查询模拟订单
emulated_orders = self.cache.orders_emulated()
is_emulated = self.cache.is_order_emulated(client_order_id)
```

---

## 6. 投资组合模块 (Portfolio)

### 6.1 概述

`nautilus_trader.portfolio` 跟踪所有持仓和风险敞口。

### 6.2 账户信息

```python
from nautilus_trader.trading.strategy import Strategy

# 获取账户
account = self.portfolio.account(venue=Venue("BINANCE"))

# 账户属性
account_id = account.id
account_type = account.account_type
base_currency = account.base_currency

# 余额
balances = account.balances()  # dict[Currency, AccountBalance]
balances_locked = account.balances_locked()  # dict[Currency, Money]
balances_free = account.balances_free()  # dict[Currency, Money]

# 保证金
margins_init = account.margins_init()  # dict[Currency, Money]
margins_maint = account.margins_maint()  # dict[Currency, Money]

# PnL
unrealized_pnls = account.unrealized_pnls()  # dict[Currency, Money]
realized_pnls = account.realized_pnls()  # dict[Currency, Money]

# 风险敞口
net_exposures = account.net_exposures()  # dict[Currency, Money]

# 统计
starting_balance = account.starting_balance()  # Money
peak_value = account.peak_value()  # Money
current_value = account.value()  # Money
```

### 6.3 持仓信息

```python
# 获取持仓
position = self.cache.position(position_id)
all_positions = self.cache.positions()
open_positions = self.cache.positions_open()
closed_positions = self.cache.positions_closed()

# 过滤查询
positions = self.cache.positions(
    instrument_id=instrument_id,
    strategy_id=strategy_id,
    venue=venue,
    side=PositionSide.LONG,
)

# 持仓属性
position.id  # PositionId
position.instrument_id  # InstrumentId
position.side  # PositionSide
position.quantity  # Quantity
position.avg_px_open  # Price
position.realized_pnl  # Money
position.unrealized_pnl(last_price)  # Money
position.total_pnl(current_price)  # Money

# 组合级查询
net_exposure = self.portfolio.net_exposure(instrument_id)
net_position = self.portfolio.net_position(instrument_id)
is_net_long = self.portfolio.is_net_long(instrument_id)
is_net_short = self.portfolio.is_net_short(instrument_id)
is_flat = self.portfolio.is_flat(instrument_id)
is_completely_flat = self.portfolio.is_completely_flat()
```

### 6.4 PnL 计算

```python
# 持仓级 PnL
position.realized_pnl  # 已实现 PnL
position.realized_return  # 已实现回报率
position.unrealized_pnl(last_price)  # 未实现 PnL
position.total_pnl(current_price)  # 总 PnL

# 账户级 PnL
account.realized_pnls()  # dict[Currency, Money]
account.unrealized_pnls()  # dict[Currency, Money]

# 组合级 PnL
portfolio.total_realized_pnl(venue)  # Money
portfolio.total_unrealized_pnl(venue)  # Money
```

---

## 7. 风险模块 (Risk)

### 7.1 概述

`nautilus_trader.risk` 提供交易前风险检查。

### 7.2 风险引擎配置

```python
from nautilus_trader.config import RiskEngineConfig

config = RiskEngineConfig(
    bypass=False,  # 是否绕过风险检查
    max_notional_per_order=Money(1_000_000, "USD"),  # 单笔订单最大名义价值
    max_notional_per_position=Money(5_000_000, "USD"),  # 单持仓最大名义价值
    max_quantity_per_order=Quantity.from_str("1000"),  # 单笔订单最大数量
    max_open_orders=100,  # 最大未平订单数
    max_open_positions=50,  # 最大未平持仓数
)
```

### 7.3 风险检查

```python
# 交易前检查项
# - 价格精度正确
# - 价格为正 (期权除外)
# - 数量精度正确
# - 低于最大名义价值
# - 在最大/最小数量范围内
# - reduce_only 订单仅减少持仓
# - 最大未平订单数
# - 最大未平持仓数

# 交易状态
# ACTIVE: 正常操作
# HALTED: 不处理订单命令
# REDUCING: 仅处理取消或减少持仓的命令
```

### 7.4 风险控制

```python
from nautilus_trader.trading.strategy import Strategy

# 检查账户状态
account = self.portfolio.account(venue)
if account.status != AccountStatus.ACTIVE:
    self.log.warning("Account not active")

# 检查持仓限制
open_positions = len(self.cache.positions_open())
if open_positions >= self.config.max_positions:
    self.log.warning("Max positions reached")

# 检查订单限制
open_orders = len(self.cache.orders_open())
if open_orders >= self.config.max_orders:
    self.log.warning("Max orders reached")
```

---

## 8. 回测模块 (Backtest)

### 8.1 概述

`nautilus_trader.backtest` 提供历史数据回测功能。

### 8.2 回测引擎 (低阶 API)

```python
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.modules import FXRatesSimulator

# 初始化引擎
engine = BacktestEngine(
    config=BacktestEngineConfig(
        trader_id="BACKTESTER-001",
        run_analysis=True,
    ),
)

# 添加模拟模块
engine.add_simulator_module(
    FXRatesSimulator(
        base_currency=Currency.from_str("USD"),
        rates={"EUR/USD": 1.1000},
    ),
)

# 添加策略
engine.add_strategy(
    strategy=MyStrategy(config),
)

# 加载数据
engine.load_data(
    quote_ticks=quote_ticks,
    trade_ticks=trade_ticks,
    bars=bars,
    instruments=[instrument],
)

# 运行回测
engine.run()

# 生成报告
engine.generate_reports()

# 获取结果
results = engine.results()

# 清理
engine.dispose()
```

### 8.3 回测节点 (高阶 API)

```python
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import (
    BacktestRunConfig,
    BacktestEngineConfig,
    DataConfig,
)

# 配置回测运行
configs = [
    BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            run_analysis=True,
        ),
        data=[
            DataConfig(
                catalog_path="./catalog",
                instrument_id="BTCUSDT.BINANCE",
                bar_type="1-HOUR",
            ),
        ],
        venues=[
            BacktestVenueConfig(
                name="BINANCE",
                oms_type="NETTING",
                account_type="MARGIN",
                base_currency="USDT",
                starting_balances=[Money(1_000_000, "USDT")],
            ),
        ],
        strategies=[
            EMACrossConfig(
                instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"),
                fast_ema_period=10,
                slow_ema_period=20,
                trade_size=Decimal("0.1"),
            ),
        ],
    ),
]

# 创建节点
node = BacktestNode(configs=configs)

# 运行回测
results = node.run()

# 处理结果
for result in results:
    print(f"Strategy: {result.strategy_id}")
    print(f"Total Return: {result.performance.total_return}")
```

### 8.4 数据目录

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# 创建目录
catalog = ParquetDataCatalog(path="./catalog")

# 查询数据
bars = catalog.bars(
    instrument_ids=["BTCUSDT.BINANCE"],
    bar_types=["1-HOUR"],
    start="2024-01-01",
    end="2024-12-31",
)

quotes = catalog.quote_ticks(
    instrument_ids=["BTCUSDT.BINANCE"],
    start="2024-01-01",
    end="2024-12-31",
)

trades = catalog.trade_ticks(
    instrument_ids=["BTCUSDT.BINANCE"],
    start="2024-01-01",
    end="2024-12-31",
)

# 写入数据
catalog.write_bars(bars)
catalog.write_quote_ticks(quotes)
catalog.write_trade_ticks(trades)
```

### 8.5 回测配置

```python
from nautilus_trader.config import (
    BacktestEngineConfig,
    CacheConfig,
    LoggingConfig,
    RiskEngineConfig,
)

config = BacktestEngineConfig(
    # 基本配置
    trader_id="BACKTESTER-001",
    run_id="20240105-001",
    run_analysis=True,
    
    # 缓存配置
    cache=CacheConfig(
        tick_capacity=10_000,
        bar_capacity=5_000,
    ),
    
    # 日志配置
    logging=LoggingConfig(
        log_level="INFO",
        log_colors=True,
    ),
    
    # 风险引擎配置
    risk_engine=RiskEngineConfig(
        bypass=False,
        max_notional_per_order=Money(1_000_000, "USD"),
    ),
    
    # 执行引擎配置
    exec_engine=BacktestExecEngineConfig(
        allow_overfills=False,
    ),
)
```

---

## 9. 实盘模块 (Live)

### 9.1 概述

`nautilus_trader.live` 提供实盘交易功能。

### 9.2 交易节点

```python
from nautilus_trader.live.node import TradingNode
from nautilus_trader.live.config import TradingNodeConfig

# 创建配置
config = TradingNodeConfig(
    trader_id="TRADER-001",
    run_id="20240105-001",
    
    # 交易所配置
    venues=[
        BinanceLiveConfig(
            api_key="your_api_key",
            api_secret="your_api_secret",
            account_type="SPOT",
            use_testnet=False,
        ),
    ],
    
    # 策略配置
    strategies=[
        EMACrossConfig(
            instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
            bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"),
            trade_size=Decimal("0.1"),
        ),
    ],
)

# 创建节点
node = TradingNode(config=config)

# 启动节点
node.run()  # 阻塞运行
# 或
await node.run_async()  # 异步运行
```

### 9.3 节点生命周期

```python
# 启动
node.start()

# 停止
node.stop()

# 暂停
node.pause()

# 恢复
node.resume()

# 重置
node.reset()

# 清理
node.dispose()

# 检查状态
print(f"Node state: {node.state}")
```

### 9.4 适配器配置

```python
from nautilus_trader.adapters.binance.config import BinanceLiveConfig
from nautilus_trader.adapters.bybit.config import BybitLiveConfig
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersConfig

# Binance
config = BinanceLiveConfig(
    instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
    api_key="your_api_key",
    api_secret="your_api_secret",
    account_type="SPOT",  # 或 FUTURES
    use_testnet=False,
)

# Bybit
config = BybitLiveConfig(
    instrument_ids=["BTCUSDT.BYBIT"],
    api_key="your_api_key",
    api_secret="your_api_secret",
    account_type="UNIFIED",
    testnet=False,
)

# Interactive Brokers
config = InteractiveBrokersConfig(
    ibg_host="127.0.0.1",
    ibg_port=7496,
    ibg_client_id=1,
    account_ids=["DU123456"],
)
```

### 9.5 沙箱模式

```python
from nautilus_trader.adapters.sandbox.config import SandboxLiveConfig

config = SandboxLiveConfig(
    instrument_ids=["BTCUSDT.SANDBOX"],
    account_type="MARGIN",
    starting_balances=[Money(1_000_000, "USD")],
    fill_model=FillModel(
        prob_fill_on_limit=0.2,
        prob_fill_on_stop=0.9,
        prob_slippage=0.1,
    ),
)

# 沙箱特点:
# - 实时市场数据
# - 虚拟执行 (不实际下单)
# - 可配置滑点和延迟
# - 适合策略验证
```

---

## 10. 持久化模块 (Persistence)

### 10.1 概述

`nautilus_trader.persistence` 提供数据存储和检索功能。

### 10.2 Parquet 数据目录

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# 创建目录
catalog = ParquetDataCatalog(path="./catalog")

# 写入数据
catalog.write_bars(bars)
catalog.write_quote_ticks(quotes)
catalog.write_trade_ticks(trades)
catalog.write_order_book_deltas(deltas)
catalog.write_instruments([instrument])

# 查询数据
bars = catalog.bars(
    instrument_ids=["BTCUSDT.BINANCE"],
    bar_types=["1-HOUR"],
    start="2024-01-01",
    end="2024-12-31",
)

quotes = catalog.quote_ticks(
    instrument_ids=["BTCUSDT.BINANCE"],
    start="2024-01-01",
    end="2024-12-31",
)

instruments = catalog.instruments(
    instrument_ids=["BTCUSDT.BINANCE"],
)

# 删除数据
catalog.delete_bars(
    instrument_ids=["BTCUSDT.BINANCE"],
    bar_types=["1-HOUR"],
    start="2024-01-01",
    end="2024-01-31",
)
```

### 10.3 数据库配置

```python
from nautilus_trader.config import DatabaseConfig

# Redis 配置
config = DatabaseConfig(
    type="redis",
    host="localhost",
    port=6379,
    password=None,
    db=0,
    timeout=2,
)

# 配置选项
# type: "redis" | "memory"
# host: 数据库主机
# port: 数据库端口
# password: 数据库密码
# db: 数据库编号
# timeout: 连接超时 (秒)
```

### 10.4 数据序列化

```python
from nautilus_trader.serialization.base import register_serializable_type
from nautilus_trader.serialization.arrow.serializer import register_arrow

# 注册基本序列化
register_serializable_type(
    data_type=GreeksData,
    to_dict_func=GreeksData.to_dict,
    from_dict_func=GreeksData.from_dict,
)

# 注册 Arrow 序列化 (用于 Parquet)
register_arrow(
    data_type=GreeksData,
    schema_func=GreeksData.schema,
    to_catalog_func=GreeksData.to_catalog,
    from_catalog_func=GreeksData.from_catalog,
)
```

---

## 11. 分析模块 (Analysis)

### 11.1 概述

`nautilus_trader.analysis` 提供绩效分析和可视化工具。

### 11.2 绩效分析

```python
from nautilus_trader.analysis.performance import PortfolioAnalyzer

# 创建分析器
analyzer = PortfolioAnalyzer()

# 添加结果
analyzer.add_result(result)

# 计算指标
total_return = analyzer.total_return()
annualized_return = analyzer.annualized_return()
sharpe_ratio = analyzer.sharpe_ratio()
sortino_ratio = analyzer.sortino_ratio()
calmar_ratio = analyzer.calmar_ratio()
max_drawdown = analyzer.max_drawdown()
max_drawdown_duration = analyzer.max_drawdown_duration()
volatility = analyzer.volatility()

# 交易统计
total_trades = analyzer.total_trades()
win_rate = analyzer.win_rate()
profit_loss_ratio = analyzer.profit_loss_ratio()
average_hold_time = analyzer.average_hold_time()
```

### 11.3 可视化

```python
from nautilus_trader.analysis.plotter import Plotter

plotter = Plotter()

# 权益曲线
plotter.plot_equity_curve(
    portfolio_analyzer=analyzer,
    save_path="./equity_curve.html",
)

# 回撤图
plotter.plot_drawdowns(
    portfolio_analyzer=analyzer,
    save_path="./drawdowns.html",
)

# 月度收益热力图
plotter.plot_monthly_returns(
    portfolio_analyzer=analyzer,
    save_path="./monthly_returns.html",
)

# 持仓时长分布
plotter.plot_position_duration(
    portfolio_analyzer=analyzer,
    save_path="./position_duration.html",
)

# 完整 Tearsheet
plotter.plot_tearsheet(
    portfolio_analyzer=analyzer,
    save_path="./tearsheet.html",
    title="My Strategy Performance",
)
```

### 11.4 Greeks 计算

```python
from nautilus_trader.analysis.greeks import GreeksCalculator

calculator = GreeksCalculator()

# 计算单个期权的 Greeks
greeks = calculator.calculate(
    option_type="call",
    underlying_price=100.0,
    strike_price=105.0,
    time_to_expiry=0.25,
    volatility=0.20,
    risk_free_rate=0.05,
)

# 投资组合聚合
portfolio_greeks = calculator.aggregate_portfolio_greeks(
    positions=positions,
    underlying_prices=price_map,
)
```

---

## 12. 配置模块 (Config)

### 12.1 概述

`nautilus_trader.config` 提供所有组件的配置类。

### 12.2 配置层次

```python
from nautilus_trader.config import (
    TradingNodeConfig,
    BacktestEngineConfig,
    StrategyConfig,
    CacheConfig,
    LoggingConfig,
    RiskEngineConfig,
    DatabaseConfig,
    MessageBusConfig,
)

# 顶层配置
config = TradingNodeConfig(
    trader_id="TRADER-001",
    run_id="20240105-001",
    
    # 子配置
    cache=CacheConfig(...),
    logging=LoggingConfig(...),
    risk_engine=RiskEngineConfig(...),
    database=DatabaseConfig(...),
    message_bus=MessageBusConfig(...),
    
    # 交易所配置
    venues=[BinanceLiveConfig(...)],
    
    # 策略配置
    strategies=[EMACrossConfig(...)],
)
```

### 12.3 策略配置

```python
from nautilus_trader.config import StrategyConfig
from pydantic import Field

class MyStrategyConfig(StrategyConfig):
    """策略配置类"""
    
    instrument_id: InstrumentId = Field(
        description="交易工具 ID",
    )
    bar_type: BarType = Field(
        description="K 线类型",
    )
    fast_ema_period: int = Field(
        default=10,
        description="快速 EMA 周期",
    )
    slow_ema_period: int = Field(
        default=20,
        description="慢速 EMA 周期",
    )
    trade_size: Decimal = Field(
        description="交易规模",
    )
    order_id_tag: str = Field(
        default="001",
        description="订单 ID 标签",
    )
```

### 12.4 环境变量

```bash
# 数据库配置
NAUTILUS_DATABASE_TYPE=redis
NAUTILUS_DATABASE_HOST=localhost
NAUTILUS_DATABASE_PORT=6379

# 日志配置
NAUTILUS_LOG_LEVEL=INFO
NAUTILUS_LOG_DIRECTORY=./logs

# 交易配置
NAUTILUS_TRADER_ID=TRADER-001
NAUTILUS_RUN_ID=20240105-001
```

### 12.5 YAML 配置

```yaml
trader_id: "TRADER-001"
run_id: "20240105-001"

cache:
  database:
    type: "redis"
    host: "localhost"
    port: 6379

logging:
  log_level: "INFO"
  log_colors: true

strategies:
  - class_path: "my_strategies.ema_cross.EMACross"
    config:
      instrument_id: "BTCUSDT.BINANCE"
      bar_type: "BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"
      fast_ema_period: 10
      slow_ema_period: 20
      trade_size: 0.1
```

---

## 13. 适配器模块 (Adapters)

### 13.1 概述

`nautilus_trader.adapters` 提供交易所和数据源集成。

### 13.2 支持的交易所

| 交易所 | 配置类 | 状态 |
|--------|--------|------|
| Binance | `BinanceLiveConfig` | ✅ 生产 |
| Bybit | `BybitLiveConfig` | ✅ 生产 |
| Interactive Brokers | `InteractiveBrokersConfig` | ✅ 生产 |
| Databento | `DatabentoDataConfig` | ✅ 生产 |
| Betfair | `BetfairLiveConfig` | ✅ 生产 |
| OKX | `OKXLiveConfig` | 🧪 测试 |
| Kraken | `KrakenLiveConfig` | 🧪 测试 |

### 13.3 适配器接口

```python
from nautilus_trader.live.data_client import DataClient
from nautilus_trader.live.execution_client import ExecutionClient

# 数据客户端接口
class DataClient:
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def subscribe_quote_ticks(self, instrument_id: InstrumentId) -> None: ...
    async def subscribe_trade_ticks(self, instrument_id: InstrumentId) -> None: ...
    async def subscribe_bars(self, bar_type: BarType) -> None: ...
    async def subscribe_order_book_deltas(self, instrument_id: InstrumentId) -> None: ...

# 执行客户端接口
class ExecutionClient:
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def submit_order(self, order: Order) -> None: ...
    async def cancel_order(self, order: Order) -> None: ...
    async def modify_order(self, order: Order, quantity: Quantity, price: Price | None = None) -> None: ...
```

### 13.4 编写自定义适配器

```python
from nautilus_trader.live.execution_client import ExecutionClient
from nautilus_trader.live.config import LiveConfig

class MyConfig(LiveConfig):
    api_key: str
    api_secret: str
    base_url: str

class MyExecutionClient(ExecutionClient):
    def __init__(self, config: MyConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.base_url = config.base_url
    
    async def connect(self) -> None:
        # 建立连接
        self._connect()
        self._log.info("Connected")
    
    async def disconnect(self) -> None:
        # 断开连接
        self._disconnect()
        self._log.info("Disconnected")
    
    async def submit_order(self, order: Order) -> None:
        # 提交订单到交易所
        response = await self._http_client.post(
            url=f"{self.base_url}/orders",
            data=self._build_order_payload(order),
        )
        self._handle_order_response(response, order)
    
    async def cancel_order(self, order: Order) -> None:
        # 取消订单
        response = await self._http_client.delete(
            url=f"{self.base_url}/orders/{order.client_order_id.value}",
        )
        self._handle_cancel_response(response, order)
```

---

## 14. 序列化模块 (Serialization)

### 14.1 概述

`nautilus_trader.serialization` 提供数据序列化功能。

### 14.2 序列化格式

| 格式 | 用途 | 模块 |
|------|------|------|
| MessagePack | 默认二进制格式 | `msgspec.msgpack` |
| JSON | 人类可读格式 | `json` |
| Apache Arrow | Parquet 存储 | `pyarrow` |

### 14.3 注册序列化

```python
from nautilus_trader.serialization.base import register_serializable_type
from nautilus_trader.serialization.arrow.serializer import register_arrow

# 自定义数据类
@customdataclass
class MyData(Data):
    value: float
    
    @classmethod
    def to_dict(cls, obj):
        return {"value": obj.value}
    
    @classmethod
    def from_dict(cls, data):
        return MyData(value=data["value"])
    
    @classmethod
    def schema(cls):
        import pyarrow as pa
        return pa.schema([
            pa.field("value", pa.float64()),
        ])
    
    @classmethod
    def to_catalog(cls,  list[MyData]) -> pa.Table:
        import pyarrow as pa
        return pa.table({
            "value": [d.value for d in data],
        })
    
    @classmethod
    def from_catalog(cls, table: pa.Table) -> list[MyData]:
        return [MyData(value=row["value"]) for row in table.to_pylist()]

# 注册基本序列化
register_serializable_type(
    data_type=MyData,
    to_dict_func=MyData.to_dict,
    from_dict_func=MyData.from_dict,
)

# 注册 Arrow 序列化
register_arrow(
    data_type=MyData,
    schema_func=MyData.schema,
    to_catalog_func=MyData.to_catalog,
    from_catalog_func=MyData.from_catalog,
)
```

### 14.4 序列化使用

```python
from nautilus_trader.serialization.base import serialize, deserialize

# 序列化
data_bytes = serialize(my_data)

# 反序列化
my_data = deserialize(data_bytes, type(my_data))

# 批量序列化
data_bytes_list = [serialize(d) for d in data_list]

# 批量反序列化
data_list = [deserialize(b, MyData) for b in data_bytes_list]
```

---

## 附录 A: 常用导入

```python
# 核心
from nautilus_trader.core import UUID4, Timestamp
from nautilus_trader.core.datetime import dt_to_unix_nanos, unix_nanos_to_dt
from nautilus_trader.core.identifiers import (
    AccountId, ClientId, InstrumentId, OrderId,
    PositionId, StrategyId, TraderId, Venue,
)

# 模型
from nautilus_trader.model import (
    Price, Quantity, Money, Currency,
    OrderSide, PositionSide, OrderType, TimeInForce,
)
from nautilus_trader.model.data import QuoteTick, TradeTick, Bar
from nautilus_trader.model.orders import MarketOrder, LimitOrder
from nautilus_trader.model.position import Position
from nautilus_trader.model.account import Account

# 交易
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig

# 数据
from nautilus_trader.model.bar import BarType, BarSpecification
from nautilus_trader.core.data import Data

# 执行
from nautilus_trader.model.enums import TriggerType, TrailingOffsetType

# 回测
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.node import BacktestNode

# 实盘
from nautilus_trader.live.node import TradingNode

# 持久化
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# 分析
from nautilus_trader.analysis.performance import PortfolioAnalyzer
from nautilus_trader.analysis.plotter import Plotter
```

---

## 附录 B: 快速参考

### B.1 策略生命周期

```
PRE_INITIALIZED → READY → STARTING → RUNNING
                                    ↓
RUNNING → STOPPING → STOPPED → RUNNING (resume)
RUNNING → DEGRADED → RUNNING (resume)
RUNNING → FAULTED
RUNNING → DISPOSED
```

### B.2 订单生命周期

```
Initialized → Submitted → Accepted → Filled/Canceled
              ↓           ↓
            Denied     Rejected
              ↓           ↓
            Emulated   Expired
              ↓
            Released
```

### B.3 持仓生命周期

```
OPENED → CHANGED → CLOSED
         ↓
       (多次变更)
```

### B.4 常用枚举

```python
# OrderSide
OrderSide.BUY, OrderSide.SELL

# PositionSide
PositionSide.LONG, PositionSide.SHORT, PositionSide.FLAT

# OrderType
OrderType.MARKET, OrderType.LIMIT, OrderType.STOP_MARKET,
OrderType.STOP_LIMIT, OrderType.TRAILING_STOP_MARKET,
OrderType.TRAILING_STOP_LIMIT

# TimeInForce
TimeInForce.GTC, TimeInForce.IOC, TimeInForce.FOK,
TimeInForce.GTD, TimeInForce.DAY, TimeInForce.AT_THE_OPEN,
TimeInForce.AT_THE_CLOSE

# AccountType
AccountType.CASH, AccountType.MARGIN, AccountType.BETTING

# OrderStatus
OrderStatus.INITIALIZED, OrderStatus.SUBMITTED,
OrderStatus.ACCEPTED, OrderStatus.REJECTED,
OrderStatus.FILLED, OrderStatus.CANCELED,
OrderStatus.EXPIRED, OrderStatus.TRIGGERED
```

---

## 附录 C: 资源链接

| 资源 | 链接 |
|------|------|
| 官方文档 | https://nautilustrader.io/docs/ |
| API Reference | https://nautilustrader.io/docs/nightly/api_reference/ |
| GitHub | https://github.com/nautechsystems/nautilus_trader |
| PyPI | https://pypi.org/project/nautilus-trader/ |
| 社区讨论 | https://github.com/nautechsystems/nautilus_trader/discussions |

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-03-31  
> **维护者**: Nautilus Trader 社区

---

此 Markdown 文件包含完整的 API Reference 目录内容汇总，可直接用于 AI 工具编程参考。如需进一步细化某个章节，请告知！