# Nautilus Trader Dev Templates 开发模板汇总

> **文档版本**: develop 分支 (2026 年 3 月)  
> **适用对象**: 量化开发者、策略研究员、系统架构师  
> **用途**: AI 工具编程参考文档

---

## 目录

1. [概述 (Overview)](#1-概述-overview)
2. [策略模板 (Strategy Templates)](#2-策略模板-strategy-templates)
3. [适配器模板 (Adapter Templates)](#3-适配器模板-adapter-templates)
4. [项目结构模板 (Project Structure)](#4-项目结构模板-project-structure)
5. [配置文件模板 (Configuration Templates)](#5-配置文件模板-configuration-templates)
6. [Docker 部署模板 (Docker Templates)](#6-docker 部署模板-docker-templates)
7. [测试模板 (Testing Templates)](#7-测试模板-testing-templates)
8. [CI/CD 模板 (CI/CD Templates)](#8-cicd 模板-cicd-templates)
9. [数据管道模板 (Data Pipeline Templates)](#9-数据管道模板-data-pipeline-templates)
10. [回测模板 (Backtest Templates)](#10-回测模板-backtest-templates)
11. [实盘部署模板 (Live Deployment Templates)](#11-实盘部署模板-live-deployment-templates)
12. [监控与日志模板 (Monitoring & Logging)](#12-监控与日志模板-monitoring--logging)
13. [文档模板 (Documentation Templates)](#13-文档模板-documentation-templates)

---

## 1. 概述 (Overview)

### 1.1 模板用途

`dev_templates` 目录提供标准化的开发模板，帮助开发者快速搭建 Nautilus Trader 项目。

**主要目标**:
- 🚀 快速启动新项目
- 📐 保持代码结构一致性
- ✅ 遵循最佳实践
- 🔧 减少重复配置工作
- 📚 提供学习参考

### 1.2 模板分类

| 类别 | 模板数量 | 用途 |
|------|---------|------|
| 策略模板 | 10+ | 不同类型策略的起点 |
| 适配器模板 | 5+ | 自定义交易所集成 |
| 项目模板 | 3+ | 完整项目结构 |
| 配置模板 | 8+ | 各种场景配置 |
| 部署模板 | 4+ | Docker/K8s 部署 |
| 测试模板 | 6+ | 单元/集成测试 |

### 1.3 使用方式

```bash
# 克隆模板
git clone https://github.com/nautechsystems/nautilus_trader.git
cd nautilus_trader/dev_templates

# 复制所需模板
cp -r strategy_templates/my_strategy ~/projects/my_project/

# 或使用脚手架工具
nautilus-cli create-project --template strategy --name my_strategy
```

---

## 2. 策略模板 (Strategy Templates)

### 2.1 基础策略模板

**文件**: `strategy_templates/basic_strategy/`

```python
# basic_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

class BasicStrategyConfig(StrategyConfig):
    """基础策略配置"""
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    stop_loss_pct: Decimal = Decimal("0.02")
    take_profit_pct: Decimal = Decimal("0.04")

class BasicStrategy(Strategy):
    """基础策略模板"""
    
    def __init__(self, config: BasicStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.position = None
        self.bar_count = 0
    
    def on_start(self) -> None:
        """策略启动"""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
        self.log.info(f"Strategy started: {self.instrument.id}")
    
    def on_stop(self) -> None:
        """策略停止"""
        self.cancel_all_orders()
        self.log.info("Strategy stopped")
    
    def on_bar(self, bar: Bar) -> None:
        """K 线处理"""
        self.bar_count += 1
        
        # 示例逻辑：每 10 根 K 线交易一次
        if self.bar_count % 10 == 0 and not self.position:
            order = self.order_factory.market(
                instrument_id=self.instrument.id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.config.trade_size),
            )
            self.submit_order(order)
    
    def on_position_opened(self, event) -> None:
        """持仓开启"""
        self.position = self.cache.position(event.position_id)
        self.log.info(f"Position opened: {event.position_id}")
    
    def on_position_closed(self, event) -> None:
        """持仓关闭"""
        self.position = None
        self.log.info(f"Position closed: {event.position_id}")
```

### 2.2 EMA 交叉策略模板

**文件**: `strategy_templates/ema_cross/`

```python
# ema_cross.py
from nautilus_trader.indicators import EMA

class EMACrossConfig(StrategyConfig):
    """EMA 交叉策略配置"""
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_ema_period: int = 10
    slow_ema_period: int = 20

class EMACrossStrategy(Strategy):
    """EMA 交叉策略"""
    
    def __init__(self, config: EMACrossConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.fast_ema = None
        self.slow_ema = None
        self.position = None
        self.bar_count = 0
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        
        # 初始化 EMA 指标
        self.fast_ema = EMA(self.config.fast_ema_period)
        self.slow_ema = EMA(self.config.slow_ema_period)
        
        self.subscribe_bars(self.config.bar_type)
    
    def on_bar(self, bar: Bar) -> None:
        self.bar_count += 1
        
        # 更新指标
        self.fast_ema.handle_bar(bar)
        self.slow_ema.handle_bar(bar)
        
        # 等待指标预热
        if self.bar_count < self.config.slow_ema_period:
            return
        
        # 交易信号
        fast_value = self.fast_ema.value
        slow_value = self.slow_ema.value
        
        if fast_value > slow_value and not self.position:
            # 金叉买入
            self._enter_long()
        elif fast_value < slow_value and self.position:
            # 死叉卖出
            self._exit_position()
    
    def _enter_long(self) -> None:
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
        )
        self.submit_order(order)
    
    def _exit_position(self) -> None:
        self.cancel_all_orders()
        # 市价平仓逻辑
```

### 2.3 网格交易策略模板

**文件**: `strategy_templates/grid_trading/`

```python
# grid_trading.py
from typing import List

class GridTradingConfig(StrategyConfig):
    """网格交易策略配置"""
    instrument_id: InstrumentId
    grid_levels: int = 10
    grid_spacing_pct: Decimal = Decimal("0.01")
    order_size: Decimal
    upper_price: Decimal
    lower_price: Decimal

class GridTradingStrategy(Strategy):
    """网格交易策略"""
    
    def __init__(self, config: GridTradingConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.grid_orders: List = []
        self.grid_levels: List[Decimal] = []
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        
        # 计算网格价格
        self._calculate_grid_levels()
        
        # 订阅数据
        self.subscribe_quote_ticks(self.instrument.id)
        
        # 放置初始网格订单
        self._place_grid_orders()
    
    def _calculate_grid_levels(self) -> None:
        """计算网格价格水平"""
        price_range = self.config.upper_price - self.config.lower_price
        step = price_range / self.config.grid_levels
        
        self.grid_levels = [
            self.config.lower_price + step * i
            for i in range(self.config.grid_levels + 1)
        ]
    
    def _place_grid_orders(self) -> None:
        """放置网格订单"""
        for i, price in enumerate(self.grid_levels):
            if i < len(self.grid_levels) / 2:
                # 下方挂买单
                order = self.order_factory.limit(
                    instrument_id=self.instrument.id,
                    order_side=OrderSide.BUY,
                    quantity=self.instrument.make_qty(self.config.order_size),
                    price=self.instrument.make_price(price),
                )
                self.submit_order(order)
                self.grid_orders.append(order)
            else:
                # 上方挂卖单
                order = self.order_factory.limit(
                    instrument_id=self.instrument.id,
                    order_side=OrderSide.SELL,
                    quantity=self.instrument.make_qty(self.config.order_size),
                    price=self.instrument.make_price(price),
                )
                self.submit_order(order)
                self.grid_orders.append(order)
    
    def on_quote_tick(self, tick) -> None:
        """报价更新时重新平衡网格"""
        mid_price = (tick.bid_price + tick.ask_price) / 2
        self._rebalance_grid(mid_price)
    
    def _rebalance_grid(self, current_price: Decimal) -> None:
        """重新平衡网格订单"""
        # 取消并重新放置订单逻辑
        pass
```

### 2.4 做市商策略模板

**文件**: `strategy_templates/market_maker/`

```python
# market_maker.py
from nautilus_trader.model.data import OrderBookDelta

class MarketMakerConfig(StrategyConfig):
    """做市商策略配置"""
    instrument_id: InstrumentId
    spread_bps: Decimal = Decimal("10")  # 10 基点
    order_size: Decimal
    max_inventory: Decimal
    inventory_skew_factor: Decimal = Decimal("0.5")

class MarketMakerStrategy(Strategy):
    """做市商策略"""
    
    def __init__(self, config: MarketMakerConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.bid_order = None
        self.ask_order = None
        self.inventory = Decimal("0")
        self.mid_price = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_order_book_deltas(self.instrument.id)
        self._update_quotes()
    
    def on_order_book_deltas(self, deltas: OrderBookDeltas) -> None:
        """订单簿更新"""
        book = self.cache.order_book(self.instrument.id)
        if book:
            self.mid_price = book.midpoint()
            self._update_quotes()
    
    def _update_quotes(self) -> None:
        """更新报价"""
        if not self.mid_price:
            return
        
        # 计算买卖价格
        spread = self.mid_price * self.config.spread_bps / 10000
        bid_price = self.mid_price - spread / 2
        ask_price = self.mid_price + spread / 2
        
        # 库存偏斜调整
        inventory_skew = self.inventory * self.config.inventory_skew_factor
        bid_price -= inventory_skew
        ask_price -= inventory_skew
        
        # 取消旧订单
        if self.bid_order:
            self.cancel_order(self.bid_order)
        if self.ask_order:
            self.cancel_order(self.ask_order)
        
        # 放置新订单
        self.bid_order = self.order_factory.limit(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.order_size),
            price=self.instrument.make_price(bid_price),
            post_only=True,
        )
        self.submit_order(self.bid_order)
        
        self.ask_order = self.order_factory.limit(
            instrument_id=self.instrument.id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.config.order_size),
            price=self.instrument.make_price(ask_price),
            post_only=True,
        )
        self.submit_order(self.ask_order)
    
    def on_order_filled(self, event) -> None:
        """订单成交更新库存"""
        if event.order_side == OrderSide.BUY:
            self.inventory += event.quantity
        else:
            self.inventory -= event.quantity
```

### 2.5 统计套利策略模板

**文件**: `strategy_templates/statistical_arbitrage/`

```python
# stat_arb.py
from scipy import stats
import numpy as np

class StatArbConfig(StrategyConfig):
    """统计套利策略配置"""
    instrument_id_1: InstrumentId
    instrument_id_2: InstrumentId
    bar_type: BarType
    lookback_period: int = 60
    entry_zscore: Decimal = Decimal("2.0")
    exit_zscore: Decimal = Decimal("0.5")
    trade_size: Decimal

class StatArbStrategy(Strategy):
    """统计套利策略"""
    
    def __init__(self, config: StatArbConfig) -> None:
        super().__init__(config)
        self.instrument_1 = None
        self.instrument_2 = None
        self.price_ratio = []
        self.position = None
    
    def on_start(self) -> None:
        self.instrument_1 = self.cache.instrument(self.config.instrument_id_1)
        self.instrument_2 = self.cache.instrument(self.config.instrument_id_2)
        
        self.subscribe_bars(self.config.bar_type)
    
    def on_bar(self, bar: Bar) -> None:
        # 计算价格比率
        if bar.instrument_id == self.config.instrument_id_1:
            self.price_ratio.append(float(bar.close))
        elif bar.instrument_id == self.config.instrument_id_2:
            if len(self.price_ratio) > 0:
                self.price_ratio[-1] /= float(bar.close)
        
        # 等待足够数据
        if len(self.price_ratio) < self.config.lookback_period:
            return
        
        # 计算 Z-Score
        zscore = self._calculate_zscore()
        
        # 交易信号
        if zscore > self.config.entry_zscore and not self.position:
            self._enter_short_spread()
        elif zscore < -self.config.entry_zscore and not self.position:
            self._enter_long_spread()
        elif abs(zscore) < self.config.exit_zscore and self.position:
            self._exit_position()
    
    def _calculate_zscore(self) -> float:
        """计算 Z-Score"""
        prices = np.array(self.price_ratio[-self.config.lookback_period:])
        mean = np.mean(prices)
        std = np.std(prices)
        return (prices[-1] - mean) / std if std > 0 else 0
    
    def _enter_long_spread(self) -> None:
        """做多价差"""
        # 买入 instrument_1, 卖出 instrument_2
        pass
    
    def _enter_short_spread(self) -> None:
        """做空价差"""
        # 卖出 instrument_1, 买入 instrument_2
        pass
```

### 2.6 期权策略模板

**文件**: `strategy_templates/options/`

```python
# options_strategy.py
from nautilus_trader.model.data import OptionGreeks

class OptionsStrategyConfig(StrategyConfig):
    """期权策略配置"""
    underlying_id: InstrumentId
    option_id: InstrumentId
    target_delta: Decimal = Decimal("0.3")
    rebalance_threshold: Decimal = Decimal("0.05")

class DeltaHedgingStrategy(Strategy):
    """Delta 对冲策略"""
    
    def __init__(self, config: OptionsStrategyConfig) -> None:
        super().__init__(config)
        self.underlying = None
        self.option = None
        self.current_delta = Decimal("0")
        self.hedge_position = Decimal("0")
    
    def on_start(self) -> None:
        self.underlying = self.cache.instrument(self.config.underlying_id)
        self.option = self.cache.instrument(self.config.option_id)
        
        # 订阅期权 Greeks
        self.subscribe_option_greeks(self.config.option_id)
        self.subscribe_quote_ticks(self.config.underlying_id)
    
    def on_option_greeks(self, greeks: OptionGreeks) -> None:
        """Greeks 更新"""
        self.current_delta = Decimal(str(greeks.delta))
        self._rebalance_hedge()
    
    def _rebalance_hedge(self) -> None:
        """重新平衡对冲"""
        target_hedge = -self.current_delta  # 负 delta 对冲
        
        if abs(target_hedge - self.hedge_position) > self.config.rebalance_threshold:
            hedge_qty = target_hedge - self.hedge_position
            
            if hedge_qty > 0:
                order = self.order_factory.market(
                    instrument_id=self.underlying.id,
                    order_side=OrderSide.BUY,
                    quantity=self.underlying.make_qty(abs(hedge_qty)),
                )
            else:
                order = self.order_factory.market(
                    instrument_id=self.underlying.id,
                    order_side=OrderSide.SELL,
                    quantity=self.underlying.make_qty(abs(hedge_qty)),
                )
            
            self.submit_order(order)
            self.hedge_position = target_hedge
```

### 2.7 模板对比

| 模板 | 复杂度 | 适用场景 | 数据需求 |
|------|--------|---------|---------|
| Basic | ⭐ | 学习/测试 | Bar |
| EMA Cross | ⭐⭐ | 趋势跟踪 | Bar |
| Grid Trading | ⭐⭐⭐ | 震荡市场 | QuoteTick |
| Market Maker | ⭐⭐⭐⭐ | 做市/流动性 | OrderBook |
| Stat Arb | ⭐⭐⭐⭐ | 配对交易 | Bar (多工具) |
| Options | ⭐⭐⭐⭐⭐ | 期权对冲 | OptionGreeks |

---

## 3. 适配器模板 (Adapter Templates)

### 3.1 基础适配器模板

**文件**: `adapter_templates/basic_adapter/`

```
basic_adapter/
├── __init__.py
├── config.py
├── data_client.py
├── execution_client.py
├── http_client.py
├── websocket_client.py
├── parsing/
│   ├── __init__.py
│   ├── instruments.py
│   └── orders.py
└── tests/
    ├── __init__.py
    ├── test_data_client.py
    └── test_execution_client.py
```

### 3.2 配置类模板

**文件**: `adapter_templates/basic_adapter/config.py`

```python
from nautilus_trader.live.config import LiveConfig
from nautilus_trader.model.identifiers import InstrumentId
from pydantic import Field

class MyExchangeConfig(LiveConfig):
    """MyExchange 适配器配置"""
    
    # 认证
    api_key: str = Field(..., description="API 密钥")
    api_secret: str = Field(..., description="API 密钥", sensitive=True)
    
    # 网络
    base_url: str = Field(
        default="https://api.myexchange.com",
        description="REST API 基础 URL",
    )
    ws_url: str = Field(
        default="wss://ws.myexchange.com",
        description="WebSocket URL",
    )
    
    # 交易
    instrument_ids: list[InstrumentId] = Field(
        default_factory=list,
        description="要交易的工具 ID 列表",
    )
    
    # 高级选项
    use_testnet: bool = Field(
        default=False,
        description="是否使用测试网络",
    )
    timestamp_sync: bool = Field(
        default=True,
        description="是否启用时间戳同步",
    )
    max_retries: int = Field(
        default=3,
        description="最大重试次数",
    )
    retry_delay_ms: int = Field(
        default=1000,
        description="重试延迟 (毫秒)",
    )
```

### 3.3 数据客户端模板

**文件**: `adapter_templates/basic_adapter/data_client.py`

```python
import asyncio
import json
from typing import Optional
import websockets

from nautilus_trader.live.data_client import DataClient
from nautilus_trader.model.data import QuoteTick, TradeTick, Bar
from nautilus_trader.model.identifiers import InstrumentId, ClientId
from nautilus_trader.core.datetime import dt_to_unix_nanos

class MyExchangeDataClient(DataClient):
    """MyExchange 数据客户端"""
    
    def __init__(self, config: MyExchangeConfig):
        super().__init__(config)
        self.config = config
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self._is_connected = False
        self._subscriptions: set[InstrumentId] = set()
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected
    
    async def connect(self) -> None:
        """建立 WebSocket 连接"""
        self._log.info("Connecting to MyExchange...")
        
        try:
            self.ws = await websockets.connect(
                self.config.ws_url,
                ping_interval=30,
                ping_timeout=10,
            )
            
            # 认证
            await self._authenticate()
            
            self._is_connected = True
            self._log.info("Connected to MyExchange")
            
            # 启动消息处理器
            asyncio.create_task(self._message_handler())
            
        except Exception as e:
            self._log.error(f"Connection failed: {e}")
            raise
    
    async def disconnect(self) -> None:
        """断开连接"""
        self._log.info("Disconnecting from MyExchange...")
        
        if self.ws:
            await self.ws.close()
        
        self._is_connected = False
        self._subscriptions.clear()
        self._log.info("Disconnected from MyExchange")
    
    async def subscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        """订阅报价"""
        if not self._is_connected:
            raise RuntimeError("Client not connected")
        
        symbol = self._instrument_to_symbol(instrument_id)
        
        message = {
            "op": "subscribe",
            "channel": "quote",
            "symbol": symbol,
        }
        
        await self.ws.send(json.dumps(message))
        self._subscriptions.add(instrument_id)
        self._log.info(f"Subscribed to quotes: {instrument_id}")
    
    async def subscribe_trade_ticks(self, instrument_id: InstrumentId) -> None:
        """订阅成交"""
        if not self._is_connected:
            raise RuntimeError("Client not connected")
        
        symbol = self._instrument_to_symbol(instrument_id)
        
        message = {
            "op": "subscribe",
            "channel": "trade",
            "symbol": symbol,
        }
        
        await self.ws.send(json.dumps(message))
        self._log.info(f"Subscribed to trades: {instrument_id}")
    
    async def _authenticate(self) -> None:
        """认证"""
        # 实现认证逻辑
        pass
    
    async def _message_handler(self) -> None:
        """处理 WebSocket 消息"""
        async for message in self.ws:
            try:
                data = json.loads(message)
                await self._handle_message(data)
            except Exception as e:
                self._log.error(f"Message handling error: {e}")
    
    async def _handle_message(self, data: dict) -> None:
        """处理单条消息"""
        channel = data.get("channel")
        
        if channel == "quote":
            tick = self._parse_quote_tick(data)
            self._send_data(tick)
        elif channel == "trade":
            tick = self._parse_trade_tick(data)
            self._send_data(tick)
    
    def _parse_quote_tick(self, data: dict) -> QuoteTick:
        """解析报价 Tick"""
        instrument_id = self._symbol_to_instrument(data["symbol"])
        
        return QuoteTick(
            instrument_id=instrument_id,
            bid_price=self._parse_price(data["bid"]),
            ask_price=self._parse_price(data["ask"]),
            bid_size=self._parse_quantity(data["bid_size"]),
            ask_size=self._parse_quantity(data["ask_size"]),
            ts_event=self._parse_timestamp(data["timestamp"]),
            ts_init=self._clock.timestamp_ns(),
        )
    
    def _parse_trade_tick(self, data: dict) -> TradeTick:
        """解析成交 Tick"""
        instrument_id = self._symbol_to_instrument(data["symbol"])
        
        return TradeTick(
            instrument_id=instrument_id,
            price=self._parse_price(data["price"]),
            size=self._parse_quantity(data["size"]),
            aggressor_side=self._parse_aggressor(data["side"]),
            trade_id=data["trade_id"],
            ts_event=self._parse_timestamp(data["timestamp"]),
            ts_init=self._clock.timestamp_ns(),
        )
    
    def _instrument_to_symbol(self, instrument_id: InstrumentId) -> str:
        """工具 ID 转交易所符号"""
        return instrument_id.symbol.value
    
    def _symbol_to_instrument(self, symbol: str) -> InstrumentId:
        """交易所符号转工具 ID"""
        return InstrumentId.from_str(f"{symbol}.MYEXCHANGE")
    
    def _parse_price(self, value: str) -> 'Price':
        """解析价格"""
        from nautilus_trader.model.objects import Price
        return Price.from_str(value)
    
    def _parse_quantity(self, value: str) -> 'Quantity':
        """解析数量"""
        from nautilus_trader.model.objects import Quantity
        return Quantity.from_str(value)
    
    def _parse_timestamp(self, value: str) -> int:
        """解析时间戳"""
        from nautilus_trader.core.datetime import parse_iso8601
        return dt_to_unix_nanos(parse_iso8601(value))
    
    def _parse_aggressor(self, side: str) -> 'AggressorSide':
        """解析 aggressor 方向"""
        from nautilus_trader.model.enums import AggressorSide
        return AggressorSide.BUYER if side == "buy" else AggressorSide.SELLER
```

### 3.4 执行客户端模板

**文件**: `adapter_templates/basic_adapter/execution_client.py`

```python
from nautilus_trader.live.execution_client import ExecutionClient
from nautilus_trader.model.order import Order
from nautilus_trader.model.enums import OrderSide, OrderType, OrderStatus
from nautilus_trader.model.event import (
    OrderSubmitted,
    OrderAccepted,
    OrderRejected,
    OrderFilled,
    OrderCanceled,
)

class MyExchangeExecutionClient(ExecutionClient):
    """MyExchange 执行客户端"""
    
    def __init__(self, config: MyExchangeConfig):
        super().__init__(config)
        self.config = config
        self.http = MyExchangeHttpClient(config)
        self._is_connected = False
    
    @property
    def is_connected(self) -> bool:
        return self._is_connected
    
    async def connect(self) -> None:
        """建立连接"""
        self._log.info("Connecting to MyExchange...")
        await self.http.connect()
        self._is_connected = True
        self._log.info("Connected to MyExchange")
    
    async def disconnect(self) -> None:
        """断开连接"""
        self._log.info("Disconnecting from MyExchange...")
        await self.http.disconnect()
        self._is_connected = False
        self._log.info("Disconnected from MyExchange")
    
    async def submit_order(self, order: Order) -> None:
        """提交订单"""
        self._log.info(f"Submitting order: {order.client_order_id}")
        
        try:
            # 发送 Submitted 事件
            self._generate_order_submitted(order)
            
            # 调用交易所 API
            response = await self.http.submit_order(
                symbol=self._instrument_to_symbol(order.instrument_id),
                side=self._order_side_to_string(order.side),
                quantity=str(order.quantity),
                price=str(order.price) if order.price else None,
                order_type=self._order_type_to_string(order.type),
                client_order_id=order.client_order_id.value,
            )
            
            # 发送 Accepted 事件
            self._generate_order_accepted(order, response)
            
        except Exception as e:
            self._log.error(f"Order submission failed: {e}")
            self._generate_order_rejected(order, str(e))
    
    async def cancel_order(self, order: Order) -> None:
        """取消订单"""
        self._log.info(f"Canceling order: {order.client_order_id}")
        
        try:
            response = await self.http.cancel_order(
                order_id=order.client_order_id.value,
            )
            self._generate_order_canceled(order, response)
            
        except Exception as e:
            self._log.error(f"Order cancellation failed: {e}")
    
    async def modify_order(
        self,
        order: Order,
        quantity: 'Quantity' | None = None,
        price: 'Price' | None = None,
    ) -> None:
        """修改订单"""
        self._log.info(f"Modifying order: {order.client_order_id}")
        
        try:
            response = await self.http.modify_order(
                order_id=order.client_order_id.value,
                quantity=str(quantity) if quantity else None,
                price=str(price) if price else None,
            )
            self._generate_order_updated(order, response)
            
        except Exception as e:
            self._log.error(f"Order modification failed: {e}")
    
    def _generate_order_submitted(self, order: Order) -> None:
        """生成订单提交事件"""
        event = OrderSubmitted(
            trader_id=order.trader_id,
            strategy_id=order.strategy_id,
            account_id=self.account_id,
            client_order_id=order.client_order_id,
            ts_init=self._clock.timestamp_ns(),
        )
        self._handle_event(event)
    
    def _generate_order_accepted(self, order: Order, response: dict) -> None:
        """生成订单接受事件"""
        event = OrderAccepted(
            trader_id=order.trader_id,
            strategy_id=order.strategy_id,
            account_id=self.account_id,
            client_order_id=order.client_order_id,
            venue_order_id=response["order_id"],
            ts_init=self._clock.timestamp_ns(),
        )
        self._handle_event(event)
    
    def _generate_order_rejected(self, order: Order, reason: str) -> None:
        """生成订单拒绝事件"""
        event = OrderRejected(
            trader_id=order.trader_id,
            strategy_id=order.strategy_id,
            account_id=self.account_id,
            client_order_id=order.client_order_id,
            reason=reason,
            ts_init=self._clock.timestamp_ns(),
        )
        self._handle_event(event)
    
    def _generate_order_filled(self, order: Order, fill_data: dict) -> None:
        """生成订单成交事件"""
        from nautilus_trader.model.objects import Price, Quantity
        
        event = OrderFilled(
            trader_id=order.trader_id,
            strategy_id=order.strategy_id,
            account_id=self.account_id,
            client_order_id=order.client_order_id,
            venue_order_id=fill_data["order_id"],
            trade_id=fill_data["trade_id"],
            order_side=order.side,
            order_type=order.type,
            quantity=Quantity.from_str(fill_data["quantity"]),
            price=Price.from_str(fill_data["price"]),
            ts_init=self._clock.timestamp_ns(),
        )
        self._handle_event(event)
    
    def _generate_order_canceled(self, order: Order, response: dict) -> None:
        """生成订单取消事件"""
        event = OrderCanceled(
            trader_id=order.trader_id,
            strategy_id=order.strategy_id,
            account_id=self.account_id,
            client_order_id=order.client_order_id,
            venue_order_id=response.get("order_id"),
            ts_init=self._clock.timestamp_ns(),
        )
        self._handle_event(event)
    
    def _generate_order_updated(self, order: Order, response: dict) -> None:
        """生成订单更新事件"""
        event = OrderUpdated(
            trader_id=order.trader_id,
            strategy_id=order.strategy_id,
            account_id=self.account_id,
            client_order_id=order.client_order_id,
            venue_order_id=response.get("order_id"),
            quantity=order.quantity,
            price=order.price,
            ts_init=self._clock.timestamp_ns(),
        )
        self._handle_event(event)
    
    def _instrument_to_symbol(self, instrument_id: InstrumentId) -> str:
        return instrument_id.symbol.value
    
    def _order_side_to_string(self, side: OrderSide) -> str:
        return "buy" if side == OrderSide.BUY else "sell"
    
    def _order_type_to_string(self, order_type: OrderType) -> str:
        mapping = {
            OrderType.MARKET: "market",
            OrderType.LIMIT: "limit",
            OrderType.STOP_MARKET: "stop_market",
            OrderType.STOP_LIMIT: "stop_limit",
        }
        return mapping.get(order_type, "market")
```

### 3.5 HTTP 客户端模板

**文件**: `adapter_templates/basic_adapter/http_client.py`

```python
import aiohttp
import hashlib
import hmac
import time
from typing import Optional

class MyExchangeHttpClient:
    """MyExchange HTTP 客户端"""
    
    def __init__(self, config: MyExchangeConfig):
        self.config = config
        self.api_key = config.api_key
        self.api_secret = config.api_secret
        self.base_url = config.base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def connect(self) -> None:
        """建立 HTTP 会话"""
        self.session = aiohttp.ClientSession(
            base_url=self.base_url,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
        )
    
    async def disconnect(self) -> None:
        """关闭 HTTP 会话"""
        if self.session:
            await self.session.close()
    
    async def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: str,
        price: Optional[str] = None,
        order_type: str = "market",
        client_order_id: Optional[str] = None,
    ) -> dict:
        """提交订单"""
        endpoint = "/api/v1/orders"
        
        payload = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "type": order_type,
            "clientOrderId": client_order_id,
        }
        
        if price:
            payload["price"] = price
        
        return await self._request("POST", endpoint, data=payload)
    
    async def cancel_order(self, order_id: str) -> dict:
        """取消订单"""
        endpoint = f"/api/v1/orders/{order_id}"
        return await self._request("DELETE", endpoint)
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[str] = None,
        price: Optional[str] = None,
    ) -> dict:
        """修改订单"""
        endpoint = f"/api/v1/orders/{order_id}"
        
        payload = {}
        if quantity:
            payload["quantity"] = quantity
        if price:
            payload["price"] = price
        
        return await self._request("PUT", endpoint, data=payload)
    
    async def get_instruments(self) -> list:
        """获取工具列表"""
        endpoint = "/api/v1/instruments"
        return await self._request("GET", endpoint)
    
    async def get_account_balance(self) -> dict:
        """获取账户余额"""
        endpoint = "/api/v1/account/balance"
        return await self._request("GET", endpoint)
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> dict:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"
        
        # 添加签名
        if method in ["POST", "PUT", "DELETE"]:
            signature = self._generate_signature(method, endpoint, data)
            headers = {"X-SIGNATURE": signature}
        else:
            headers = {}
        
        async with self.session.request(
            method,
            url,
            json=data,
            headers=headers,
        ) as response:
            if response.status != 200:
                error = await response.text()
                raise Exception(f"API Error: {error}")
            
            return await response.json()
    
    def _generate_signature(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
    ) -> str:
        """生成请求签名"""
        timestamp = str(int(time.time() * 1000))
        
        message = f"{timestamp}{method}{endpoint}"
        if data:
            message += str(data)
        
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()
        
        return signature
```

---

## 4. 项目结构模板 (Project Structure)

### 4.1 标准项目结构

**文件**: `project_templates/standard/`

```
my_trading_project/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
│
├── config/
│   ├── __init__.py
│   ├── trading_config.py
│   ├── backtest_config.py
│   └── live_config.py
│
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py
│   ├── ema_cross.py
│   └── grid_trading.py
│
├── adapters/
│   ├── __init__.py
│   └── custom_exchange/
│       ├── __init__.py
│       ├── config.py
│       ├── data_client.py
│       └── execution_client.py
│
├── data/
│   ├── __init__.py
│   ├── loaders.py
│   └── processors.py
│
├── backtests/
│   ├── __init__.py
│   ├── run_backtest.py
│   └── configs/
│       └── ema_cross_config.py
│
├── live/
│   ├── __init__.py
│   ├── run_live.py
│   └── configs/
│       └── live_config.py
│
├── analysis/
│   ├── __init__.py
│   ├── performance.py
│   └── reports.py
│
├── tests/
│   ├── __init__.py
│   ├── test_strategies.py
│   ├── test_adapters.py
│   └── fixtures/
│       └── sample_data.py
│
└── scripts/
    ├── __init__.py
    ├── download_data.py
    ├── build_catalog.py
    └── deploy.py
```

### 4.2 pyproject.toml 模板

**文件**: `project_templates/standard/pyproject.toml`

```toml
[project]
name = "my-trading-project"
version = "0.1.0"
description = "My Nautilus Trader Trading Project"
readme = "README.md"
requires-python = ">=3.12"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your.email@example.com"}
]
dependencies = [
    "nautilus_trader>=1.200.0",
    "pandas>=2.0.0",
    "numpy>=1.24.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
    "mypy>=1.0.0",
]

analysis = [
    "plotly>=5.0.0",
    "matplotlib>=3.7.0",
    "seaborn>=0.12.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["strategies", "adapters", "config"]

[tool.black]
line-length = 100
target-version = ["py312"]

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
python_version = "3.12"
strict = true
```

### 4.3 环境变量模板

**文件**: `project_templates/standard/.env.example`

```bash
# Nautilus Trader 配置
NAUTILUS_TRADER_ID=TRADER-001
NAUTILUS_RUN_ID=20240105-001

# 数据库配置
NAUTILUS_DATABASE_TYPE=redis
NAUTILUS_DATABASE_HOST=localhost
NAUTILUS_DATABASE_PORT=6379
NAUTILUS_DATABASE_PASSWORD=

# 日志配置
NAUTILUS_LOG_LEVEL=INFO
NAUTILUS_LOG_DIRECTORY=./logs

# 交易所 API 密钥 (不要提交到版本控制!)
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_api_secret

BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret

# Databento API
DATABENTO_API_KEY=your_databento_api_key

# 其他配置
DATA_CATALOG_PATH=./catalog
BACKTEST_START_DATE=2024-01-01
BACKTEST_END_DATE=2024-12-31
```

### 4.4 Dockerfile 模板

**文件**: `project_templates/standard/Dockerfile`

```dockerfile
# 多阶段构建
FROM ghcr.io/nautechsystems/jupyterlab:nightly AS builder

WORKDIR /app

# 复制依赖文件
COPY pyproject.toml requirements.txt ./

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# 生产镜像
FROM python:3.12-slim

WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 从 builder 复制
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app /app

# 复制项目代码
COPY strategies/ ./strategies/
COPY config/ ./config/
COPY live/ ./live/

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV NAUTILUS_LOG_LEVEL=INFO

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import nautilus_trader" || exit 1

# 启动命令
CMD ["python", "-m", "live.run_live"]
```

### 4.5 docker-compose.yml 模板

**文件**: `project_templates/standard/docker-compose.yml`

```yaml
version: '3.8'

services:
  # Redis 数据库
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # 交易节点
  trader:
    build: .
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - NAUTILUS_DATABASE_HOST=redis
      - NAUTILUS_DATABASE_PORT=6379
      - NAUTILUS_TRADER_ID=${NAUTILUS_TRADER_ID:-TRADER-001}
    volumes:
      - ./logs:/app/logs
      - ./catalog:/app/catalog
    restart: unless-stopped

  # JupyterLab (可选)
  jupyter:
    image: ghcr.io/nautechsystems/jupyterlab:nightly
    ports:
      - "8888:8888"
    volumes:
      - .:/home/jovyan/work
      - ./catalog:/home/jovyan/work/catalog
    environment:
      - JUPYTER_TOKEN=${JUPYTER_TOKEN:-mytoken}
    command: start-notebook.sh --NotebookApp.token=${JUPYTER_TOKEN}

volumes:
  redis_data:
```

---

## 5. 配置文件模板 (Configuration Templates)

### 5.1 回测配置模板

**文件**: `config_templates/backtest_config.py`

```python
from decimal import Decimal
from nautilus_trader.backtest.config import (
    BacktestRunConfig,
    BacktestEngineConfig,
    BacktestVenueConfig,
)
from nautilus_trader.config import (
    CacheConfig,
    LoggingConfig,
    RiskEngineConfig,
)
from nautilus_trader.model.enums import AccountType, OmsType

def get_backtest_config() -> BacktestRunConfig:
    """获取回测配置"""
    
    return BacktestRunConfig(
        # 引擎配置
        engine=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            run_id="backtest-2024-001",
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
        ),
        
        # 交易所配置
        venues=[
            BacktestVenueConfig(
                name="BINANCE",
                oms_type=OmsType.NETTING,
                account_type=AccountType.MARGIN,
                base_currency="USDT",
                starting_balances=[Money(1_000_000, "USDT")],
                
                # 模拟配置
                fill_model=FillModel(
                    prob_fill_on_limit=0.5,
                    prob_fill_on_stop=0.95,
                    prob_slippage=0.1,
                ),
                
                # 费用配置
                maker_fee=0.0002,
                taker_fee=0.0005,
            ),
        ],
        
        # 数据配置
        data=[
            DataConfig(
                catalog_path="./catalog",
                instrument_id="BTCUSDT.BINANCE",
                bar_type="1-HOUR",
                start_time="2024-01-01",
                end_time="2024-12-31",
            ),
        ],
        
        # 策略配置
        strategies=[
            EMACrossConfig(
                instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"),
                fast_ema_period=10,
                slow_ema_period=20,
                trade_size=Decimal("0.1"),
                order_id_tag="001",
            ),
        ],
    )
```

### 5.2 实盘配置模板

**文件**: `config_templates/live_config.py`

```python
from decimal import Decimal
from nautilus_trader.live.config import (
    TradingNodeConfig,
    TradingEngineConfig,
)
from nautilus_trader.config import (
    CacheConfig,
    DatabaseConfig,
    LoggingConfig,
    RiskEngineConfig,
    MessageBusConfig,
)
from nautilus_trader.adapters.binance.config import BinanceLiveConfig
from nautilus_trader.model.enums import AccountType

def get_live_config() -> TradingNodeConfig:
    """获取实盘配置"""
    
    return TradingNodeConfig(
        # 基本配置
        trader_id="TRADER-001",
        run_id="live-2024-001",
        
        # 引擎配置
        engine=TradingEngineConfig(
            # 缓存配置
            cache=CacheConfig(
                database=DatabaseConfig(
                    type="redis",
                    host="localhost",
                    port=6379,
                    timeout=2,
                ),
                encoding="msgpack",
                tick_capacity=10_000,
                bar_capacity=5_000,
            ),
            
            # 消息总线配置
            message_bus=MessageBusConfig(
                database=DatabaseConfig(
                    type="redis",
                    host="localhost",
                    port=6379,
                ),
                encoding="json",
                timestamps_as_iso8601=True,
            ),
            
            # 日志配置
            logging=LoggingConfig(
                log_level="INFO",
                log_level_file="DEBUG",
                log_directory="./logs",
                log_colors=True,
            ),
            
            # 风险引擎配置
            risk_engine=RiskEngineConfig(
                bypass=False,
                max_notional_per_order=Money(100_000, "USDT"),
                max_notional_per_position=Money(500_000, "USDT"),
                max_open_orders=50,
                max_open_positions=20,
            ),
        ),
        
        # 交易所配置
        venues=[
            BinanceLiveConfig(
                api_key=os.getenv("BINANCE_API_KEY"),
                api_secret=os.getenv("BINANCE_API_SECRET"),
                instrument_ids=[
                    "BTCUSDT.BINANCE",
                    "ETHUSDT.BINANCE",
                ],
                account_type=AccountType.MARGIN,
                use_testnet=False,
            ),
        ],
        
        # 策略配置
        strategies=[
            EMACrossConfig(
                instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                bar_type=BarType.from_str("BTCUSDT.BINANCE-1-MINUTE-LAST-INTERNAL"),
                fast_ema_period=10,
                slow_ema_period=20,
                trade_size=Decimal("0.01"),
                order_id_tag="001",
            ),
        ],
    )
```

### 5.3 YAML 配置模板

**文件**: `config_templates/config.yaml`

```yaml
# Nautilus Trader 配置文件

trader_id: "TRADER-001"
run_id: "20240105-001"

# 缓存配置
cache:
  database:
    type: "redis"
    host: "localhost"
    port: 6379
  encoding: "msgpack"
  tick_capacity: 10000
  bar_capacity: 5000

# 日志配置
logging:
  log_level: "INFO"
  log_level_file: "DEBUG"
  log_directory: "./logs"
  log_colors: true
  log_filename_format: "{trader_id}-{strategy_id}-{component}.log"

# 风险引擎配置
risk_engine:
  bypass: false
  max_notional_per_order:
    amount: 100000
    currency: "USDT"
  max_notional_per_position:
    amount: 500000
    currency: "USDT"
  max_open_orders: 50
  max_open_positions: 20

# 交易所配置
venues:
  - name: "BINANCE"
    type: "binance"
    config:
      api_key: "${BINANCE_API_KEY}"
      api_secret: "${BINANCE_API_SECRET}"
      instrument_ids:
        - "BTCUSDT.BINANCE"
        - "ETHUSDT.BINANCE"
      account_type: "MARGIN"
      use_testnet: false

# 策略配置
strategies:
  - class_path: "strategies.ema_cross.EMACrossStrategy"
    config:
      instrument_id: "BTCUSDT.BINANCE"
      bar_type: "BTCUSDT.BINANCE-1-MINUTE-LAST-INTERNAL"
      fast_ema_period: 10
      slow_ema_period: 20
      trade_size: 0.01
      order_id_tag: "001"
  
  - class_path: "strategies.grid_trading.GridTradingStrategy"
    config:
      instrument_id: "ETHUSDT.BINANCE"
      grid_levels: 10
      grid_spacing_pct: 0.01
      order_size: 0.1
      upper_price: 3000
      lower_price: 2000
```

### 5.4 加载 YAML 配置

**文件**: `config_templates/load_config.py`

```python
import os
import yaml
from pathlib import Path
from nautilus_trader.config import TradingNodeConfig

def load_config(config_path: str) -> TradingNodeConfig:
    """加载 YAML 配置文件"""
    
    with open(config_path, 'r') as f:
        config_dict = yaml.safe_load(f)
    
    # 替换环境变量
    config_dict = replace_env_vars(config_dict)
    
    # 创建配置对象
    config = TradingNodeConfig(**config_dict)
    
    return config

def replace_env_vars(config: dict) -> dict:
    """替换配置中的环境变量"""
    
    if isinstance(config, dict):
        return {k: replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [replace_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        env_var = config[2:-1]
        return os.getenv(env_var, config)
    else:
        return config

# 使用示例
if __name__ == "__main__":
    config = load_config("config/config.yaml")
    node = TradingNode(config=config)
    node.run()
```

---

## 6. Docker 部署模板 (Docker Templates)

### 6.1 生产 Dockerfile

**文件**: `docker_templates/production/Dockerfile`

```dockerfile
# ============================================
# Nautilus Trader 生产部署 Dockerfile
# ============================================

# 构建阶段
FROM ghcr.io/nautechsystems/jupyterlab:nightly AS builder

WORKDIR /build

# 复制依赖文件
COPY pyproject.toml requirements.txt ./

# 安装依赖
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY strategies/ ./strategies/
COPY config/ ./config/
COPY adapters/ ./adapters/

# 安装项目
RUN pip install --no-cache-dir -e .

# 运行测试
RUN pytest tests/ -v

# ============================================
# 生产镜像
# ============================================
FROM python:3.12-slim-bookworm

# 设置标签
LABEL maintainer="your.email@example.com"
LABEL version="1.0.0"
LABEL description="Nautilus Trader Production Image"

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl-dev \
    libffi-dev \
    libzmq3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash trader
USER trader
WORKDIR /home/trader

# 从 builder 复制
COPY --from=builder --chown=trader:trader /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder --chown=trader:trader /build /home/trader/app

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV NAUTILUS_LOG_LEVEL=INFO
ENV NAUTILUS_LOG_DIRECTORY=/home/trader/logs

# 创建目录
RUN mkdir -p /home/trader/logs /home/trader/catalog

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import nautilus_trader; print('OK')" || exit 1

# 暴露端口 (Jupyter)
EXPOSE 8888

# 启动命令
ENTRYPOINT ["python", "-m", "live.run_live"]
```

### 6.2 开发 Dockerfile

**文件**: `docker_templates/development/Dockerfile`

```dockerfile
# ============================================
# Nautilus Trader 开发 Dockerfile
# ============================================

FROM ghcr.io/nautechsystems/jupyterlab:nightly

WORKDIR /home/jovyan/work

# 安装开发依赖
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# 复制项目代码
COPY . .

# 安装项目 (可编辑模式)
RUN pip install -e .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV NAUTILUS_LOG_LEVEL=DEBUG

# 默认命令
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root"]
```

### 6.3 Kubernetes 部署模板

**文件**: `docker_templates/kubernetes/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nautilus-trader
  labels:
    app: nautilus-trader
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nautilus-trader
  template:
    metadata:
      labels:
        app: nautilus-trader
    spec:
      containers:
      - name: trader
        image: your-registry/nautilus-trader:latest
        ports:
        - containerPort: 8888
        env:
        - name: NAUTILUS_TRADER_ID
          valueFrom:
            configMapKeyRef:
              name: nautilus-config
              key: trader_id
        - name: NAUTILUS_DATABASE_HOST
          value: "redis-service"
        - name: BINANCE_API_KEY
          valueFrom:
            secretKeyRef:
              name: nautilus-secrets
              key: binance_api_key
        - name: BINANCE_API_SECRET
          valueFrom:
            secretKeyRef:
              name: nautilus-secrets
              key: binance_api_secret
        volumeMounts:
        - name: logs
          mountPath: /home/trader/logs
        - name: catalog
          mountPath: /home/trader/catalog
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          exec:
            command:
            - python
            - -c
            - "import nautilus_trader"
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          exec:
            command:
            - python
            - -c
            - "import nautilus_trader"
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: logs
        persistentVolumeClaim:
          claimName: logs-pvc
      - name: catalog
        persistentVolumeClaim:
          claimName: catalog-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: nautilus-trader-service
spec:
  selector:
    app: nautilus-trader
  ports:
  - port: 8888
    targetPort: 8888
  type: ClusterIP
```

### 6.4 Docker Compose 完整模板

**文件**: `docker_templates/docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  # Redis 数据库
  redis:
    image: redis:7-alpine
    container_name: nautilus-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - nautilus-network

  # 交易节点
  trader:
    build:
      context: .
      dockerfile: Dockerfile.prod
    container_name: nautilus-trader
    depends_on:
      redis:
        condition: service_healthy
    environment:
      - NAUTILUS_DATABASE_HOST=redis
      - NAUTILUS_DATABASE_PORT=6379
      - NAUTILUS_TRADER_ID=${NAUTILUS_TRADER_ID:-TRADER-001}
      - NAUTILUS_RUN_ID=${NAUTILUS_RUN_ID:-live-001}
      - NAUTILUS_LOG_LEVEL=${NAUTILUS_LOG_LEVEL:-INFO}
    env_file:
      - .env
    volumes:
      - ./logs:/home/trader/logs
      - ./catalog:/home/trader/catalog
    restart: unless-stopped
    networks:
      - nautilus-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # JupyterLab (可选，用于分析)
  jupyter:
    image: ghcr.io/nautechsystems/jupyterlab:nightly
    container_name: nautilus-jupyter
    ports:
      - "8888:8888"
    volumes:
      - .:/home/jovyan/work
      - ./catalog:/home/jovyan/work/catalog
    environment:
      - JUPYTER_TOKEN=${JUPYTER_TOKEN:-mytoken}
    command: start-notebook.sh --NotebookApp.token=${JUPYTER_TOKEN}
    networks:
      - nautilus-network
    profiles:
      - dev

  # Prometheus 监控 (可选)
  prometheus:
    image: prom/prometheus:latest
    container_name: nautilus-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    networks:
      - nautilus-network
    profiles:
      - monitoring

  # Grafana 可视化 (可选)
  grafana:
    image: grafana/grafana:latest
    container_name: nautilus-grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
    depends_on:
      - prometheus
    networks:
      - nautilus-network
    profiles:
      - monitoring

networks:
  nautilus-network:
    driver: bridge

volumes:
  redis_data:
  prometheus_data:
  grafana_data:
```

---

## 7. 测试模板 (Testing Templates)

### 7.1 策略单元测试模板

**文件**: `test_templates/test_strategy.py`

```python
import pytest
from decimal import Decimal
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from strategies.ema_cross import EMACrossStrategy, EMACrossConfig

@pytest.fixture
def backtest_engine():
    """创建回测引擎"""
    config = BacktestEngineConfig(
        trader_id="TESTER-001",
        run_analysis=False,
    )
    engine = BacktestEngine(config=config)
    yield engine
    engine.dispose()

@pytest.fixture
def strategy_config():
    """策略配置"""
    return EMACrossConfig(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
        bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"),
        fast_ema_period=10,
        slow_ema_period=20,
        trade_size=Decimal("0.1"),
        order_id_tag="001",
    )

@pytest.fixture
def strategy(strategy_config):
    """策略实例"""
    return EMACrossStrategy(config=strategy_config)

def test_strategy_initialization(strategy):
    """测试策略初始化"""
    assert strategy is not None
    assert strategy.config.fast_ema_period == 10
    assert strategy.config.slow_ema_period == 20

def test_strategy_on_start(strategy, backtest_engine):
    """测试策略启动"""
    backtest_engine.add_strategy(strategy)
    strategy.on_start()
    
    assert strategy.instrument is not None
    assert strategy.fast_ema is not None
    assert strategy.slow_ema is not None

def test_strategy_on_bar(strategy, backtest_engine):
    """测试 K 线处理"""
    backtest_engine.add_strategy(strategy)
    strategy.on_start()
    
    # 创建模拟 K 线
    bar = Bar(
        bar_type=strategy.config.bar_type,
        open=Price.from_str("50000.00"),
        high=Price.from_str("50100.00"),
        low=Price.from_str("49900.00"),
        close=Price.from_str("50050.00"),
        volume=Quantity.from_str("100.0"),
        ts_event=1630000000000000000,
        ts_init=1630000000000000000,
    )
    
    # 处理多根 K 线使指标预热
    for i in range(25):
        strategy.on_bar(bar)
    
    # 验证指标已计算
    assert strategy.fast_ema.value > 0
    assert strategy.slow_ema.value > 0

def test_full_backtest(backtest_engine, strategy_config):
    """测试完整回测"""
    # 添加策略
    strategy = EMACrossStrategy(config=strategy_config)
    backtest_engine.add_strategy(strategy)
    
    # 添加工具
    instrument = CurrencyPair(...)
    backtest_engine.add_instrument(instrument)
    
    # 添加数据
    bars = load_test_bars()
    backtest_engine.add_data(bars)
    
    # 运行回测
    backtest_engine.run()
    
    # 验证结果
    results = backtest_engine.results()
    assert len(results) > 0
    
    # 验证报告
    report = backtest_engine.performance_report()
    assert report is not None
```

### 7.2 适配器测试模板

**文件**: `test_templates/test_adapter.py`

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from adapters.my_exchange.config import MyExchangeConfig
from adapters.my_exchange.data_client import MyExchangeDataClient
from adapters.my_exchange.execution_client import MyExchangeExecutionClient

@pytest.fixture
def adapter_config():
    """适配器配置"""
    return MyExchangeConfig(
        api_key="test_api_key",
        api_secret="test_api_secret",
        base_url="https://test-api.myexchange.com",
        ws_url="wss://test-ws.myexchange.com",
    )

@pytest.fixture
def data_client(adapter_config):
    """数据客户端"""
    return MyExchangeDataClient(config=adapter_config)

@pytest.fixture
def execution_client(adapter_config):
    """执行客户端"""
    return MyExchangeExecutionClient(config=adapter_config)

class TestDataClient:
    """数据客户端测试"""
    
    @pytest.mark.asyncio
    async def test_connect(self, data_client):
        """测试连接"""
        with patch('websockets.connect') as mock_ws:
            mock_ws.return_value = AsyncMock()
            await data_client.connect()
            assert data_client.is_connected
    
    @pytest.mark.asyncio
    async def test_disconnect(self, data_client):
        """测试断开连接"""
        data_client._is_connected = True
        data_client.ws = AsyncMock()
        
        await data_client.disconnect()
        assert not data_client.is_connected
    
    @pytest.mark.asyncio
    async def test_subscribe_quote_ticks(self, data_client):
        """测试订阅报价"""
        data_client._is_connected = True
        data_client.ws = AsyncMock()
        
        instrument_id = InstrumentId.from_str("BTCUSDT.MYEXCHANGE")
        await data_client.subscribe_quote_ticks(instrument_id)
        
        assert instrument_id in data_client._subscriptions
        data_client.ws.send.assert_called_once()

class TestExecutionClient:
    """执行客户端测试"""
    
    @pytest.mark.asyncio
    async def test_submit_order(self, execution_client):
        """测试提交订单"""
        execution_client._is_connected = True
        execution_client.http = AsyncMock()
        execution_client.http.submit_order.return_value = {"order_id": "123"}
        
        order = MarketOrder(...)
        await execution_client.submit_order(order)
        
        execution_client.http.submit_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, execution_client):
        """测试取消订单"""
        execution_client._is_connected = True
        execution_client.http = AsyncMock()
        execution_client.http.cancel_order.return_value = {"status": "canceled"}
        
        order = MarketOrder(...)
        await execution_client.cancel_order(order)
        
        execution_client.http.cancel_order.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_order_rejection(self, execution_client):
        """测试订单拒绝"""
        execution_client._is_connected = True
        execution_client.http = AsyncMock()
        execution_client.http.submit_order.side_effect = Exception("API Error")
        
        order = MarketOrder(...)
        await execution_client.submit_order(order)
        
        # 验证生成了拒绝事件
        execution_client._generate_order_rejected.assert_called_once()
```

### 7.3 集成测试模板

**文件**: `test_templates/test_integration.py`

```python
import pytest
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import BacktestRunConfig

from config.backtest_config import get_backtest_config

class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def backtest_config(self):
        """回测配置"""
        return get_backtest_config()
    
    def test_backtest_runs_successfully(self, backtest_config):
        """测试回测成功运行"""
        node = BacktestNode(configs=[backtest_config])
        results = node.run()
        
        assert len(results) > 0
        assert results[0].performance is not None
    
    def test_backtest_performance_metrics(self, backtest_config):
        """测试回测绩效指标"""
        node = BacktestNode(configs=[backtest_config])
        results = node.run()
        
        performance = results[0].performance
        
        # 验证关键指标存在
        assert hasattr(performance, 'total_return')
        assert hasattr(performance, 'sharpe_ratio')
        assert hasattr(performance, 'max_drawdown')
        
        # 验证指标范围合理
        assert performance.total_return > -1.0  # 不会亏损超过 100%
        assert performance.max_drawdown >= 0
    
    def test_backtest_generates_reports(self, backtest_config, tmp_path):
        """测试回测生成报告"""
        node = BacktestNode(configs=[backtest_config])
        results = node.run()
        
        # 验证报告文件生成
        report_dir = tmp_path / "reports"
        report_dir.mkdir()
        
        # 保存报告
        results[0].save_reports(report_dir)
        
        assert (report_dir / "performance.html").exists()
        assert (report_dir / "positions.parquet").exists()
```

### 7.4 测试配置文件

**文件**: `test_templates/pytest.ini`

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
addopts = 
    -v
    --tb=short
    --strict-markers
    -m "not slow"
filterwarnings =
    ignore::DeprecationWarning
```

### 7.5 测试覆盖率配置

**文件**: `test_templates/.coveragerc`

```ini
[run]
source = strategies,adapters,config
omit = 
    */tests/*
    */__init__.py
    */test_*.py
branch = True

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
show_missing = True
precision = 2

[html]
directory = htmlcov
```

---

## 8. CI/CD 模板 (CI/CD Templates)

### 8.1 GitHub Actions 模板

**文件**: `cicd_templates/.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  # 代码质量检查
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install black ruff mypy
      
      - name: Run Black
        run: black --check .
      
      - name: Run Ruff
        run: ruff check .
      
      - name: Run MyPy
        run: mypy strategies/ adapters/ config/

  # 单元测试
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.12', '3.13']
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install -r requirements-dev.txt
      
      - name: Run tests
        run: pytest tests/ -v --cov=strategies --cov=adapters --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  # 集成测试
  integration:
    runs-on: ubuntu-latest
    needs: [lint, test]
    
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -e .
          pip install -r requirements-dev.txt
      
      - name: Run integration tests
        run: pytest tests/ -v -m integration
        env:
          NAUTILUS_DATABASE_HOST: localhost
          NAUTILUS_DATABASE_PORT: 6379

  # Docker 构建
  docker:
    runs-on: ubuntu-latest
    needs: [lint, test]
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:latest
            ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

### 8.2 发布工作流模板

**文件**: `cicd_templates/.github/workflows/release.yml`

```yaml
name: Release

on:
  release:
    types: [published]

jobs:
  # 发布到 PyPI
  publish-pypi:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install build tools
        run: pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: twine upload dist/*

  # 发布 Docker 镜像
  publish-docker:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Get release version
        id: version
        run: echo "version=${GITHUB_REF#refs/tags/}" >> $GITHUB_OUTPUT
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: |
            ghcr.io/${{ github.repository }}:${{ steps.version.outputs.version }}
            ghcr.io/${{ github.repository }}:latest
```

### 8.3 预提交钩子模板

**文件**: `cicd_templates/.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
        language_version: python3.12

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-all
```

---

## 9. 数据管道模板 (Data Pipeline Templates)

### 9.1 数据下载模板

**文件**: `data_templates/download_data.py`

```python
import asyncio
from datetime import datetime
from pathlib import Path
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader

async def download_data(
    instrument_ids: list[str],
    start_date: str,
    end_date: str,
    output_path: str,
    api_key: str,
):
    """下载历史数据"""
    
    # 创建数据目录
    catalog_path = Path(output_path)
    catalog_path.mkdir(parents=True, exist_ok=True)
    
    # 初始化数据加载器
    loader = DatabentoDataLoader(api_key=api_key)
    
    # 创建数据目录
    catalog = ParquetDataCatalog(path=catalog_path)
    
    for instrument_id in instrument_ids:
        print(f"Downloading data for {instrument_id}...")
        
        # 下载 K 线
        bars = loader.load_bars(
            instrument_ids=[instrument_id],
            schema="ohlcv-1m",
            start=start_date,
            end=end_date,
        )
        catalog.write_bars(bars)
        print(f"  Downloaded {len(bars)} bars")
        
        # 下载成交
        trades = loader.load_trade_ticks(
            instrument_ids=[instrument_id],
            start=start_date,
            end=end_date,
        )
        catalog.write_trade_ticks(trades)
        print(f"  Downloaded {len(trades)} trades")
        
        # 下载报价
        quotes = loader.load_quote_ticks(
            instrument_ids=[instrument_id],
            start=start_date,
            end=end_date,
        )
        catalog.write_quote_ticks(quotes)
        print(f"  Downloaded {len(quotes)} quotes")
    
    print(f"Data download complete. Catalog: {catalog_path}")

if __name__ == "__main__":
    asyncio.run(
        download_data(
            instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
            start_date="2024-01-01",
            end_date="2024-12-31",
            output_path="./catalog",
            api_key="your_databento_api_key",
        )
    )
```

### 9.2 数据构建模板

**文件**: `data_templates/build_catalog.py`

```python
from pathlib import Path
import pandas as pd
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.data import Bar, QuoteTick, TradeTick
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.core.datetime import dt_to_unix_nanos

def build_catalog_from_csv(
    csv_path: str,
    instrument_id: str,
    output_path: str,
    data_type: str = "bars",
):
    """从 CSV 构建数据目录"""
    
    # 读取 CSV
    df = pd.read_csv(csv_path)
    
    # 创建数据目录
    catalog = ParquetDataCatalog(path=output_path)
    
    if data_type == "bars":
        # 转换为 Bar 对象
        bars = []
        for _, row in df.iterrows():
            bar = Bar(
                bar_type=BarType.from_str(f"{instrument_id}-1-MINUTE-LAST-INTERNAL"),
                open=Price.from_str(str(row["open"])),
                high=Price.from_str(str(row["high"])),
                low=Price.from_str(str(row["low"])),
                close=Price.from_str(str(row["close"])),
                volume=Quantity.from_str(str(row["volume"])),
                ts_event=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
                ts_init=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
            )
            bars.append(bar)
        
        catalog.write_bars(bars)
        print(f"Written {len(bars)} bars to catalog")
    
    elif data_type == "quotes":
        # 转换为 QuoteTick 对象
        quotes = []
        for _, row in df.iterrows():
            quote = QuoteTick(
                instrument_id=InstrumentId.from_str(instrument_id),
                bid_price=Price.from_str(str(row["bid"])),
                ask_price=Price.from_str(str(row["ask"])),
                bid_size=Quantity.from_str(str(row["bid_size"])),
                ask_size=Quantity.from_str(str(row["ask_size"])),
                ts_event=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
                ts_init=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
            )
            quotes.append(quote)
        
        catalog.write_quote_ticks(quotes)
        print(f"Written {len(quotes)} quotes to catalog")
    
    elif data_type == "trades":
        # 转换为 TradeTick 对象
        trades = []
        for _, row in df.iterrows():
            trade = TradeTick(
                instrument_id=InstrumentId.from_str(instrument_id),
                price=Price.from_str(str(row["price"])),
                size=Quantity.from_str(str(row["size"])),
                aggressor_side=AggressorSide.BUYER if row["side"] == "buy" else AggressorSide.SELLER,
                trade_id=row["trade_id"],
                ts_event=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
                ts_init=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
            )
            trades.append(trade)
        
        catalog.write_trade_ticks(trades)
        print(f"Written {len(trades)} trades to catalog")

if __name__ == "__main__":
    build_catalog_from_csv(
        csv_path="./data/btcusdt.csv",
        instrument_id="BTCUSDT.BINANCE",
        output_path="./catalog",
        data_type="bars",
    )
```

### 9.3 数据处理模板

**文件**: `data_templates/process_data.py`

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.data import Bar
import pandas as pd

class DataProcessor:
    """数据处理类"""
    
    def __init__(self, catalog_path: str):
        self.catalog = ParquetDataCatalog(path=catalog_path)
    
    def resample_bars(
        self,
        instrument_id: str,
        source_bar_type: str,
        target_bar_type: str,
    ) -> list[Bar]:
        """重采样 K 线"""
        
        # 加载源数据
        bars = self.catalog.bars(
            instrument_ids=[instrument_id],
            bar_types=[source_bar_type],
        )
        
        # 转换为 DataFrame
        df = pd.DataFrame([
            {
                "ts_event": bar.ts_event,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
            for bar in bars
        ])
        
        # 设置时间索引
        df["timestamp"] = pd.to_datetime(df["ts_event"])
        df = df.set_index("timestamp")
        
        # 重采样
        resampled = df.resample("1H").agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna()
        
        # 转换回 Bar 对象
        new_bars = []
        for ts, row in resampled.iterrows():
            bar = Bar(
                bar_type=BarType.from_str(target_bar_type),
                open=Price.from_str(str(row["open"])),
                high=Price.from_str(str(row["high"])),
                low=Price.from_str(str(row["low"])),
                close=Price.from_str(str(row["close"])),
                volume=Quantity.from_str(str(row["volume"])),
                ts_event=int(ts.timestamp() * 1e9),
                ts_init=int(ts.timestamp() * 1e9),
            )
            new_bars.append(bar)
        
        return new_bars
    
    def calculate_returns(
        self,
        instrument_id: str,
        bar_type: str,
    ) -> pd.Series:
        """计算收益率"""
        
        bars = self.catalog.bars(
            instrument_ids=[instrument_id],
            bar_types=[bar_type],
        )
        
        prices = [float(bar.close) for bar in bars]
        returns = pd.Series(prices).pct_change()
        
        return returns
    
    def export_to_csv(
        self,
        instrument_id: str,
        bar_type: str,
        output_path: str,
    ):
        """导出数据到 CSV"""
        
        bars = self.catalog.bars(
            instrument_ids=[instrument_id],
            bar_types=[bar_type],
        )
        
        df = pd.DataFrame([
            {
                "timestamp": pd.Timestamp(bar.ts_event),
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": float(bar.volume),
            }
            for bar in bars
        ])
        
        df.to_csv(output_path, index=False)
        print(f"Exported {len(df)} rows to {output_path}")

if __name__ == "__main__":
    processor = DataProcessor("./catalog")
    
    # 重采样 K 线
    hourly_bars = processor.resample_bars(
        instrument_id="BTCUSDT.BINANCE",
        source_bar_type="1-MINUTE",
        target_bar_type="1-HOUR",
    )
    
    # 计算收益率
    returns = processor.calculate_returns(
        instrument_id="BTCUSDT.BINANCE",
        bar_type="1-HOUR",
    )
    
    # 导出 CSV
    processor.export_to_csv(
        instrument_id="BTCUSDT.BINANCE",
        bar_type="1-HOUR",
        output_path="./output/btcusdt_hourly.csv",
    )
```

---

## 10. 回测模板 (Backtest Templates)

### 10.1 简单回测脚本

**文件**: `backtest_templates/run_backtest.py`

```python
from nautilus_trader.backtest.node import BacktestNode
from config.backtest_config import get_backtest_config

def run_backtest():
    """运行回测"""
    
    # 获取配置
    config = get_backtest_config()
    
    # 创建回测节点
    node = BacktestNode(configs=[config])
    
    # 运行回测
    results = node.run()
    
    # 打印结果
    for result in results:
        print(f"\n{'='*50}")
        print(f"Strategy: {result.strategy_id}")
        print(f"{'='*50}")
        
        performance = result.performance
        print(f"Total Return: {performance.total_return:.2%}")
        print(f"Sharpe Ratio: {performance.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {performance.max_drawdown:.2%}")
        print(f"Total Trades: {performance.total_trades}")
        print(f"Win Rate: {performance.win_rate:.2%}")
    
    # 生成报告
    node.generate_reports()
    
    return results

if __name__ == "__main__":
    results = run_backtest()
```

### 10.2 多策略回测模板

**文件**: `backtest_templates/run_multi_strategy.py`

```python
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import BacktestRunConfig

def get_multi_strategy_configs() -> list[BacktestRunConfig]:
    """获取多策略配置"""
    
    configs = []
    
    # 策略 1: EMA Cross
    configs.append(
        BacktestRunConfig(
            engine=BacktestEngineConfig(trader_id="BACKTESTER-001"),
            venues=[...],
            data=[...],
            strategies=[
                EMACrossConfig(
                    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                    bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
                    fast_ema_period=10,
                    slow_ema_period=20,
                    trade_size=Decimal("0.1"),
                    order_id_tag="001",
                ),
            ],
        ),
    )
    
    # 策略 2: Grid Trading
    configs.append(
        BacktestRunConfig(
            engine=BacktestEngineConfig(trader_id="BACKTESTER-002"),
            venues=[...],
            data=[...],
            strategies=[
                GridTradingConfig(
                    instrument_id=InstrumentId.from_str("ETHUSDT.BINANCE"),
                    grid_levels=10,
                    grid_spacing_pct=Decimal("0.01"),
                    order_size=Decimal("0.1"),
                    upper_price=Decimal("3000"),
                    lower_price=Decimal("2000"),
                    order_id_tag="002",
                ),
            ],
        ),
    )
    
    return configs

def run_multi_strategy_backtest():
    """运行多策略回测"""
    
    configs = get_multi_strategy_configs()
    node = BacktestNode(configs=configs)
    
    results = node.run()
    
    # 汇总结果
    print("\n" + "="*50)
    print("MULTI-STRATEGY BACKTEST SUMMARY")
    print("="*50)
    
    for result in results:
        print(f"\n{result.strategy_id}:")
        print(f"  Total Return: {result.performance.total_return:.2%}")
        print(f"  Sharpe Ratio: {result.performance.sharpe_ratio:.2f}")
    
    return results

if __name__ == "__main__":
    results = run_multi_strategy_backtest()
```

### 10.3 参数优化模板

**文件**: `backtest_templates/optimize_parameters.py`

```python
from itertools import product
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import BacktestRunConfig

def optimize_ema_parameters():
    """优化 EMA 参数"""
    
    # 参数网格
    fast_periods = [5, 10, 15, 20]
    slow_periods = [20, 30, 40, 50]
    
    results = []
    
    for fast, slow in product(fast_periods, slow_periods):
        if fast >= slow:
            continue
        
        print(f"Testing fast={fast}, slow={slow}...")
        
        config = BacktestRunConfig(
            engine=BacktestEngineConfig(trader_id="BACKTESTER-001"),
            venues=[...],
            data=[...],
            strategies=[
                EMACrossConfig(
                    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                    bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
                    fast_ema_period=fast,
                    slow_ema_period=slow,
                    trade_size=Decimal("0.1"),
                    order_id_tag="001",
                ),
            ],
        )
        
        node = BacktestNode(configs=[config])
        backtest_results = node.run()
        
        performance = backtest_results[0].performance
        
        results.append({
            "fast_period": fast,
            "slow_period": slow,
            "total_return": performance.total_return,
            "sharpe_ratio": performance.sharpe_ratio,
            "max_drawdown": performance.max_drawdown,
        })
    
    # 排序并显示最佳结果
    results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
    
    print("\n" + "="*50)
    print("OPTIMIZATION RESULTS (Sorted by Sharpe Ratio)")
    print("="*50)
    
    for i, r in enumerate(results[:5]):
        print(f"\n{i+1}. Fast={r['fast_period']}, Slow={r['slow_period']}")
        print(f"   Return: {r['total_return']:.2%}")
        print(f"   Sharpe: {r['sharpe_ratio']:.2f}")
        print(f"   MaxDD: {r['max_drawdown']:.2%}")
    
    return results

if __name__ == "__main__":
    optimize_ema_parameters()
```

---

## 11. 实盘部署模板 (Live Deployment Templates)

### 11.1 实盘运行脚本

**文件**: `live_templates/run_live.py`

```python
import asyncio
import signal
import sys
from nautilus_trader.live.node import TradingNode
from config.live_config import get_live_config

class TradingBot:
    """交易机器人"""
    
    def __init__(self):
        self.node = None
        self._shutdown = False
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        print(f"\nReceived signal {signum}. Shutting down...")
        self._shutdown = True
    
    async def run(self):
        """运行交易节点"""
        
        # 获取配置
        config = get_live_config()
        
        # 创建节点
        self.node = TradingNode(config=config)
        
        # 设置信号处理
        self.setup_signal_handlers()
        
        try:
            # 启动节点
            await self.node.run_async()
            
            # 等待关闭信号
            while not self._shutdown:
                await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error: {e}")
            raise
        finally:
            # 清理
            await self.stop()
    
    async def stop(self):
        """停止交易节点"""
        if self.node:
            print("Stopping trading node...")
            self.node.stop()
            self.node.dispose()
            print("Trading node stopped.")

async def main():
    """主函数"""
    bot = TradingBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### 11.2 系统服务模板 (systemd)

**文件**: `live_templates/nautilus-trader.service`

```ini
[Unit]
Description=Nautilus Trader Service
After=network.target redis.service
Wants=redis.service

[Service]
Type=simple
User=trader
Group=trader
WorkingDirectory=/home/trader/app

# 环境变量
Environment="PYTHONUNBUFFERED=1"
Environment="NAUTILUS_LOG_LEVEL=INFO"
Environment="NAUTILUS_DATABASE_HOST=localhost"
Environment="NAUTILUS_DATABASE_PORT=6379"

# 从文件加载敏感信息
EnvironmentFile=/home/trader/.env

# 执行命令
ExecStart=/usr/bin/python -m live.run_live
Restart=always
RestartSec=10

# 资源限制
LimitNOFILE=65536
MemoryMax=2G

# 日志
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nautilus-trader

[Install]
WantedBy=multi-user.target
```

**安装服务**:
```bash
# 复制服务文件
sudo cp nautilus-trader.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务
sudo systemctl enable nautilus-trader

# 启动服务
sudo systemctl start nautilus-trader

# 查看状态
sudo systemctl status nautilus-trader

# 查看日志
sudo journalctl -u nautilus-trader -f
```

### 11.3 健康检查模板

**文件**: `live_templates/health_check.py`

```python
import asyncio
import aiohttp
from datetime import datetime

class HealthChecker:
    """健康检查器"""
    
    def __init__(self, check_interval_secs: int = 60):
        self.check_interval = check_interval_secs
        self.last_check = None
        self.is_healthy = False
    
    async def check_node_health(self) -> bool:
        """检查节点健康状态"""
        
        checks = {
            "redis": await self._check_redis(),
            "strategy": await self._check_strategy(),
            "orders": await self._check_orders(),
            "positions": await self._check_positions(),
        }
        
        self.is_healthy = all(checks.values())
        self.last_check = datetime.utcnow()
        
        return self.is_healthy
    
    async def _check_redis(self) -> bool:
        """检查 Redis 连接"""
        try:
            # Redis 连接检查
            return True
        except Exception:
            return False
    
    async def _check_strategy(self) -> bool:
        """检查策略状态"""
        try:
            # 策略状态检查
            return True
        except Exception:
            return False
    
    async def _check_orders(self) -> bool:
        """检查订单状态"""
        try:
            # 订单状态检查
            return True
        except Exception:
            return False
    
    async def _check_positions(self) -> bool:
        """检查持仓状态"""
        try:
            # 持仓状态检查
            return True
        except Exception:
            return False
    
    async def run(self):
        """运行健康检查"""
        while True:
            healthy = await self.check_node_health()
            
            if healthy:
                print(f"[{datetime.utcnow()}] Health check: OK")
            else:
                print(f"[{datetime.utcnow()}] Health check: FAILED")
                # 发送警报
                await self._send_alert()
            
            await asyncio.sleep(self.check_interval)
    
    async def _send_alert(self):
        """发送警报"""
        # 实现警报逻辑 (邮件、Slack、Telegram 等)
        pass

if __name__ == "__main__":
    checker = HealthChecker()
    asyncio.run(checker.run())
```

---

## 12. 监控与日志模板 (Monitoring & Logging)

### 12.1 Prometheus 配置模板

**文件**: `monitoring_templates/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'nautilus-trader'
    static_configs:
      - targets: ['trader:8000']
    metrics_path: '/metrics'

  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

rule_files:
  - 'alerts.yml'
```

### 12.2 警报规则模板

**文件**: `monitoring_templates/alerts.yml`

```yaml
groups:
  - name: nautilus_trader_alerts
    rules:
      - alert: TraderDown
        expr: up{job="nautilus-trader"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Nautilus Trader is down"
          description: "Trader has been down for more than 5 minutes"

      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      - alert: LargeDrawdown
        expr: current_drawdown > 0.1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Large drawdown detected"
          description: "Drawdown is {{ $value | humanizePercentage }}"
```

### 12.3 Grafana 仪表板模板

**文件**: `monitoring_templates/grafana_dashboard.json`

```json
{
  "dashboard": {
    "title": "Nautilus Trader Dashboard",
    "panels": [
      {
        "title": "Equity Curve",
        "type": "graph",
        "targets": [
          {
            "expr": "portfolio_equity",
            "legendFormat": "Equity"
          }
        ]
      },
      {
        "title": "Drawdown",
        "type": "graph",
        "targets": [
          {
            "expr": "portfolio_drawdown",
            "legendFormat": "Drawdown"
          }
        ]
      },
      {
        "title": "Open Positions",
        "type": "stat",
        "targets": [
          {
            "expr": "positions_open_count",
            "legendFormat": "Open Positions"
          }
        ]
      },
      {
        "title": "Order Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(orders_submitted_total[5m])",
            "legendFormat": "Orders/min"
          }
        ]
      }
    ]
  }
}
```

### 12.4 日志配置模板

**文件**: `monitoring_templates/logging_config.py`

```python
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging(
    log_level: str = "INFO",
    log_directory: str = "./logs",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
):
    """设置日志"""
    
    # 创建日志目录
    log_path = Path(log_directory)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # 根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # 文件处理器 (轮转)
    file_handler = RotatingFileHandler(
        log_path / "nautilus_trader.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # 策略日志
    strategy_logger = logging.getLogger("strategy")
    strategy_handler = RotatingFileHandler(
        log_path / "strategy.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    strategy_handler.setFormatter(file_formatter)
    strategy_logger.addHandler(strategy_handler)
    
    # 执行日志
    exec_logger = logging.getLogger("execution")
    exec_handler = RotatingFileHandler(
        log_path / "execution.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
    )
    exec_handler.setFormatter(file_formatter)
    exec_logger.addHandler(exec_handler)
    
    return root_logger

if __name__ == "__main__":
    logger = setup_logging()
    logger.info("Logging initialized")
```

---

## 13. 文档模板 (Documentation Templates)

### 13.1 README 模板

**文件**: `docs_templates/README.md`

```markdown
# My Trading Project

[![CI](https://github.com/username/my-trading-project/actions/workflows/ci.yml/badge.svg)](https://github.com/username/my-trading-project/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

基于 Nautilus Trader 的量化交易系统。

## 功能特性

- 📊 多策略支持 (EMA Cross, Grid Trading, Market Making)
- 🔄 回测与实盘一致性
- 📈 绩效分析与可视化
- 🐳 Docker 部署支持
- 📝 完整的测试覆盖

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/username/my-trading-project.git
cd my-trading-project

# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件填入 API 密钥
```

### 运行回测

```bash
python -m backtests.run_backtest
```

### 运行实盘

```bash
python -m live.run_live
```

## 项目结构

```
my-trading-project/
├── strategies/          # 策略实现
├── adapters/           # 交易所适配器
├── config/             # 配置文件
├── backtests/          # 回测脚本
├── live/               # 实盘脚本
├── tests/              # 测试
└── docs/               # 文档
```

## 策略列表

| 策略 | 描述 | 风险等级 |
|------|------|---------|
| EMA Cross | 趋势跟踪策略 | 中 |
| Grid Trading | 网格交易策略 | 中高 |
| Market Maker | 做市商策略 | 高 |

## 配置

编辑 `config/live_config.py` 配置实盘参数。

## 监控

- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

## 贡献

欢迎提交 Issue 和 Pull Request!

## 许可证

MIT License
```

### 13.2 策略文档模板

**文件**: `docs_templates/strategy_docs.md`

```markdown
# EMA Cross Strategy

## 概述

EMA Cross 是一个基于指数移动平均线交叉的趋势跟踪策略。

## 原理

- 当快速 EMA 上穿慢速 EMA 时，产生买入信号
- 当快速 EMA 下穿慢速 EMA 时，产生卖出信号

## 参数

| 参数 | 默认值 | 描述 |
|------|--------|------|
| fast_ema_period | 10 | 快速 EMA 周期 |
| slow_ema_period | 20 | 慢速 EMA 周期 |
| trade_size | 0.1 | 交易规模 |

## 风险

- 震荡市场中可能产生频繁假信号
- 建议配合止损使用

## 回测结果

| 指标 | 值 |
|------|-----|
| 总收益率 | 25.3% |
| 夏普比率 | 1.5 |
| 最大回撤 | 12.5% |
| 胜率 | 55% |

## 使用示例

```python
config = EMACrossConfig(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
    fast_ema_period=10,
    slow_ema_period=20,
    trade_size=Decimal("0.1"),
)

strategy = EMACrossStrategy(config=config)
```
```

---

## 附录 A: 模板使用指南

### A.1 选择模板

| 需求 | 推荐模板 |
|------|---------|
| 学习 Nautilus Trader | `strategy_templates/basic_strategy` |
| 快速开始交易 | `project_templates/standard` |
| 自定义交易所 | `adapter_templates/basic_adapter` |
| 生产部署 | `docker_templates/production` |
| 参数优化 | `backtest_templates/optimize_parameters` |

### A.2 自定义模板

```bash
# 复制模板
cp -r dev_templates/strategy_templates/ema_cross ~/projects/my_strategy/

# 修改策略逻辑
cd ~/projects/my_strategy
# 编辑 ema_cross.py

# 运行测试
pytest tests/

# 运行回测
python -m backtests.run_backtest
```

---

## 附录 B: 资源链接

| 资源 | 链接 |
|------|------|
| 官方文档 | https://nautilustrader.io/docs/ |
| Dev Templates | https://github.com/nautechsystems/nautilus_trader/tree/develop/dev_templates |
| GitHub | https://github.com/nautechsystems/nautilus_trader |
| 示例项目 | https://github.com/nautechsystems/nautilus_trader/tree/develop/examples |
| 社区讨论 | https://github.com/nautechsystems/nautilus_trader/discussions |

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-03-31  
> **维护者**: Nautilus Trader 社区

---

此 Markdown 文件包含完整的 Dev Templates 目录内容汇总，可直接用于 AI 工具编程参考。如需进一步细化某个模板的使用细节，请告知！