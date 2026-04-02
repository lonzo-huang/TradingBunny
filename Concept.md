基于获取的所有文档内容，我现在为您生成完整的 Concepts 目录汇总 Markdown 文件：

```markdown
# Nautilus Trader Concepts 概念指南汇总

> **文档版本**: develop 分支 (2026年3月)  
> **适用对象**: 量化开发者、策略研究员、系统架构师  
> **用途**: AI 工具编程参考文档

---

## 目录

1. [概述 (Overview)](#1-概述-overview)
2. [架构 (Architecture)](#2-架构-architecture)
3. [Actors](#3-actors)
4. [策略 (Strategies)](#4-策略-strategies)
5. [金融工具 (Instruments)](#5-金融工具-instruments)
6. [值类型 (Value Types)](#6-值类型-value-types)
7. [数据 (Data)](#7-数据-data)
8. [事件 (Events)](#8-事件-events)
9. [期权 (Options)](#9-期权-options)
10. [Greeks](#10-greeks)
11. [自定义数据 (Custom Data)](#11-自定义数据-custom-data)
12. [订单簿 (Order Book)](#12-订单簿-order-book)
13. [执行 (Execution)](#13-执行-execution)
14. [订单 (Orders)](#14-订单-orders)
15. [持仓 (Positions)](#15-持仓-positions)
16. [缓存 (Cache)](#16-缓存-cache)
17. [消息总线 (Message Bus)](#17-消息总线-message-bus)
18. [投资组合 (Portfolio)](#18-投资组合-portfolio)
19. [报告 (Reports)](#19-报告-reports)
20. [日志 (Logging)](#20-日志-logging)
21. [回测 (Backtesting)](#21-回测-backtesting)
22. [可视化 (Visualization)](#22-可视化-visualization)
23. [配置 (Configuration)](#23-配置-configuration)
24. [实盘交易 (Live Trading)](#24-实盘交易-live-trading)
25. [适配器 (Adapters)](#25-适配器-adapters)
26. [Rust 开发](#26-rust-开发)

---

## 1. 概述 (Overview)

### 1.1 平台介绍

NautilusTrader 是一个开源、生产级、Rust 原生引擎的多资产、多交易所量化交易系统。

**核心特性**:
- **高性能**: Rust 核心 + Tokio 异步网络
- **高可靠**: Rust 类型/线程安全，可选 Redis 状态持久化
- **跨平台**: Linux/macOS/Windows 支持，Docker 部署
- **模块化**: 适配器架构，可集成任何 REST API 或 WebSocket 数据源
- **回测/实盘一致**: 同一套策略代码可直接从研究部署到生产
- **AI 友好**: 足够快的引擎支持强化学习/进化策略训练

### 1.2 使用场景

| 场景 | 描述 | 组件 |
|------|------|------|
| Backtest | 历史数据回测 | `BacktestEngine` / `BacktestNode` |
| Sandbox | 实时数据 + 虚拟执行 | `SandboxAdapter` |
| Live | 实盘/模拟账户交易 | `TradingNode` |

### 1.3 时间戳规范

- **精度**: 纳秒级 (9 位小数)
- **时区**: UTC
- **格式**: ISO 8601 (RFC 3339)
- **示例**: `2024-01-05T15:30:45.123456789Z`

### 1.4 数据类型

**市场数据类型**:
- `OrderBookDelta` (L1/L2/L3)
- `QuoteTick`, `TradeTick`, `Bar`
- `Instrument`, `InstrumentStatus`, `InstrumentClose`

**Bar 聚合类型**:
- 时间聚合: MILLISECOND, SECOND, MINUTE, HOUR, DAY, WEEK, MONTH, YEAR
- 其他聚合: TICK, VOLUME, VALUE, RENKO, TICK_IMBALANCE, VOLUME_IMBALANCE 等

### 1.5 账户类型

| 类型 | 描述 |
|------|------|
| Cash | 单币种/多币种现金账户 |
| Margin | 单币种/多币种保证金账户 |
| Betting | 单币种博彩账户 |

### 1.6 订单类型

- MARKET, LIMIT, STOP_MARKET, STOP_LIMIT
- MARKET_TO_LIMIT, MARKET_IF_TOUCHED, LIMIT_IF_TOUCHED
- TRAILING_STOP_MARKET, TRAILING_STOP_LIMIT

### 1.7 值类型精度模式

**高精度模式 (128-bit, 默认)**:
| 类型 | 原始类型 | 最大精度 | 最小值 | 最大值 |
|------|---------|---------|--------|--------|
| Price | i128 | 16 | -17,014,118,346,046 | 17,014,118,346,046 |
| Money | i128 | 16 | -17,014,118,346,046 | 17,014,118,346,046 |
| Quantity | u128 | 16 | 0 | 34,028,236,692,093 |

**标准精度模式 (64-bit)**:
| 类型 | 原始类型 | 最大精度 | 最小值 | 最大值 |
|------|---------|---------|--------|--------|
| Price | i64 | 9 | -9,223,372,036 | 9,223,372,036 |
| Money | i64 | 9 | -9,223,372,036 | 9,223,372,036 |
| Quantity | u64 | 9 | 0 | 18,446,744,073 |

---

## 2. 架构 (Architecture)

### 2.1 设计原则

**故障快速失败 (Fail-Fast)**:
- 算术溢出/下立即触发 panic
- 反序列化时拒绝 NaN/Infinity/超范围值
- 类型转换失败立即报错
- 目标：防止静默数据损坏

**崩溃恢复设计 (Crash-Only)**:
- 启动和崩溃恢复共享同一代码路径
- 关键状态外部持久化 (可选 Redis)
- 快速重启，最小化停机时间
- 操作幂等，可安全重试

### 2.2 核心组件

| 组件 | 功能 |
|------|------|
| `NautilusKernel` | 中央编排组件，管理所有系统组件 |
| `MessageBus` | 组件间通信骨干，支持发布/订阅、请求/响应 |
| `Cache` | 高性能内存存储，存储订单、持仓、市场数据 |
| `DataEngine` | 处理和路由市场数据 |
| `ExecutionEngine` | 管理订单生命周期和执行 |
| `RiskEngine` | 交易前风险检查和验证 |

### 2.3 数据流：QuoteTick 的生命周期

```
Adapter → MPSC Channel → DataEngine → Cache → MessageBus → Strategy
```

**步骤**:
1. Adapter 接收原始 WebSocket 数据，解析为 `QuoteTick`
2. 通过 MPSC 通道发送 `DataEvent`
3. DataEngine 处理事件，调用 `handle_quote`
4. Cache 存储 quote (`cache.add_quote`)
5. MessageBus 发布到主题
6. Strategy 的 `on_quote_tick` 处理器触发

### 2.4 执行流：订单的生命周期

```
Strategy → RiskEngine → ExecutionEngine → ExecutionClient → Venue
Venue → ExecutionClient → ExecutionEngine → Strategy
```

**步骤**:
1. Strategy 调用 `submit_order` 创建命令
2. RiskEngine 执行交易前风险检查
3. ExecutionEngine 路由到 ExecutionClient
4. ExecutionClient 通过 REST/WebSocket 提交到交易所
5. 事件 (Accepted/Filled/Canceled) 流回 Strategy

### 2.5 组件状态机

**稳定状态**:
- `PRE_INITIALIZED`: 实例化但未就绪
- `READY`: 已配置，可启动
- `RUNNING`: 正常运行
- `STOPPED`: 已停止
- `DEGRADED`: 降级状态
- `FAULTED`: 故障关闭
- `DISPOSED`: 已释放资源

**过渡状态**: STARTING, STOPPING, RESUMING, RESETTING, DISPOSING, DEGRADING, FAULTING

### 2.6 线程模型

- **单线程核心**: MessageBus 分发、策略逻辑、风险检查、Cache 读写
- **后台服务**: 网络 I/O、持久化、适配器操作使用独立线程/异步运行时
- **跨线程通信**: 通过通道将事件传递到单线程核心

### 2.7 代码结构

```
crates/              # Rust 实现
├── core/            # 基础原语
├── model/           # 领域模型
├── common/          # 通用组件
├── system/          # 系统内核
├── trading/         # 交易组件
├── data/            # 数据引擎
├── execution/       # 执行引擎
├── portfolio/       # 投资组合
├── risk/            # 风险管理
├── persistence/     # 持久化
├── live/            # 实盘节点
├── backtest/        # 回测节点
└── adapters/        # 交易所适配器

nautilus_trader/     # Python/Cython 绑定
```

---

## 3. Actors

### 3.1 概述

`Actor` 是接收数据、处理事件、管理状态的基础组件。`Strategy` 继承自 Actor，添加订单管理能力。

**核心能力**:
- 数据订阅和请求 (市场数据、自定义数据)
- 事件处理和发布
- 定时器和警报
- Cache 和 Portfolio 访问
- 日志记录

### 3.2 生命周期状态机

```
[*] → PRE_INITIALIZED → READY → STARTING → RUNNING
                                      ↓
RUNNING → STOPPING → STOPPED → RUNNING (resume)
RUNNING → DEGRADING → DEGRADED → RUNNING (resume)
RUNNING → FAULTING → FAULTED
RUNNING → DISPOSED → [*]
```

**生命周期方法**:
| 方法 | 调用时机 |
|------|---------|
| `on_start()` | Actor 启动时 (订阅数据) |
| `on_stop()` | Actor 停止时 (清理资源) |
| `on_resume()` | 从停止状态恢复 |
| `on_reset()` | 重置指标和内部状态 |
| `on_degrade()` | 进入降级状态 |
| `on_fault()` | 遇到故障 |
| `on_dispose()` | 最终清理 |

### 3.3 定时器和警报

```python
def on_start(self) -> None:
    # 设置周期性定时器 (每 5 秒触发)
    self.clock.set_timer(
        "my_timer",
        timedelta(seconds=5),
        callback=self._on_timer,
    )
    
    # 设置一次性警报
    self.clock.set_time_alert(
        "my_alert",
        self.clock.utc_now() + timedelta(minutes=1),
        callback=self._on_alert,
    )

def on_stop(self) -> None:
    # 取消定时器防止资源泄漏
    self.clock.cancel_timer("my_timer")
```

### 3.4 系统访问

| 属性 | 描述 |
|------|------|
| `self.cache` | 共享状态 (工具、订单、持仓等) |
| `self.portfolio` | 投资组合状态和计算 |
| `self.clock` | 当前时间和定时器/警报调度 |
| `self.log` | 结构化日志 |
| `self.msgbus` | 发布/订阅自定义消息 |

### 3.5 数据处理

**历史数据 vs 实时数据**:

| 操作 | 类别 | 处理器 | 用途 |
|------|------|--------|------|
| `request_*()` | 历史 | `on_historical_data()` | 初始数据加载 |
| `subscribe_*()` | 实时 | `on_*_tick()`, `on_bar()` | 实时数据处理 |

---

## 4. 策略 (Strategies)

### 4.1 概述

策略继承 `Strategy` 类，实现交易逻辑。策略拥有 Actor 的所有能力 + 订单管理。

**主要能力**:
- 历史数据请求
- 实时数据订阅
- 设置时间警报/定时器
- Cache 访问
- Portfolio 访问
- 创建和管理订单/持仓

### 4.2 策略实现

```python
from nautilus_trader.trading.strategy import Strategy

class MyStrategy(Strategy):
    def __init__(self) -> None:
        super().__init__()  # 必须调用父类初始化
    
    def on_start(self) -> None:
        # 初始化策略 (获取工具、订阅数据)
        pass
    
    def on_stop(self) -> None:
        # 清理任务 (取消订单、关闭持仓、取消订阅)
        pass
```

### 4.3 处理器 (Handlers)

**状态生命周期处理器**:
```python
def on_start(self) -> None: ...
def on_stop(self) -> None: ...
def on_resume(self) -> None: ...
def on_reset(self) -> None: ...
def on_save(self) -> dict[str, bytes]: ...  # 保存状态
def on_load(self, state: dict[str, bytes]) -> None: ...  # 加载状态
```

**数据处理器**:
```python
def on_order_book_deltas(self, deltas: OrderBookDeltas) -> None: ...
def on_quote_tick(self, tick: QuoteTick) -> None: ...
def on_trade_tick(self, tick: TradeTick) -> None: ...
def on_bar(self, bar: Bar) -> None: ...
def on_data(self, data: Data) -> None: ...  # 自定义数据
def on_signal(self, signal: Data) -> None: ...  # 信号
```

**订单事件处理器** (按顺序调用):
1. 特定处理器 (如 `on_order_filled`)
2. `on_order_event(...)` (所有订单事件)
3. `on_event(...)` (所有事件)

```python
def on_order_initialized(self, event: OrderInitialized) -> None: ...
def on_order_submitted(self, event: OrderSubmitted) -> None: ...
def on_order_accepted(self, event: OrderAccepted) -> None: ...
def on_order_filled(self, event: OrderFilled) -> None: ...
def on_order_canceled(self, event: OrderCanceled) -> None: ...
def on_order_event(self, event: OrderEvent) -> None: ...
```

**持仓事件处理器**:
```python
def on_position_opened(self, event: PositionOpened) -> None: ...
def on_position_changed(self, event: PositionChanged) -> None: ...
def on_position_closed(self, event: PositionClosed) -> None: ...
def on_position_event(self, event: PositionEvent) -> None: ...
```

### 4.4 策略配置

```python
from decimal import Decimal
from nautilus_trader.config import StrategyConfig

class MyStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    trade_size: Decimal
    order_id_tag: str

class MyStrategy(Strategy):
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        # 配置通过 self.config 访问
        # 状态变量作为直接属性
    
    def on_start(self) -> None:
        self.subscribe_bars(self.config.bar_type)
```

**配置 vs 状态变量**:
- `self.config.xxx`: 初始设置，定义策略如何工作
- `self.xxx`: 跟踪策略的自定义状态

### 4.5 交易命令

**提交订单**:
```python
from nautilus_trader.model.enums import OrderSide, TimeInForce

# 限价单
order = self.order_factory.limit(
    instrument_id=self.instrument_id,
    order_side=OrderSide.BUY,
    quantity=self.instrument.make_qty(self.trade_size),
    price=self.instrument.make_price(5000.00),
    time_in_force=TimeInForce.GTC,
)
self.submit_order(order)

# 市价单 + 执行算法
order = self.order_factory.market(
    instrument_id=self.instrument_id,
    order_side=OrderSide.BUY,
    quantity=self.instrument.make_qty(self.trade_size),
    exec_algorithm_id=ExecAlgorithmId("TWAP"),
    exec_algorithm_params={"horizon_secs": 20, "interval_secs": 2.5},
)
self.submit_order(order)
```

**取消订单**:
```python
self.cancel_order(order)           # 单个订单
self.cancel_orders([order1, ...])  # 批量订单
self.cancel_all_orders()           # 所有订单
```

**修改订单**:
```python
from nautilus_trader.model import Quantity
new_quantity = Quantity.from_int(5)
self.modify_order(order, new_quantity)
```

**市场退出**:
```python
# 优雅退出所有持仓和订单
self.market_exit()

# 配置自动退出
config = StrategyConfig(manage_stop=True)  # stop() 时先执行市场退出
```

### 4.6 多策略运行

- 每个策略实例必须有唯一的 `order_id_tag`
- 策略 ID = 类名 + `order_id_tag` (如 `MyStrategy-001`)
- 重复的策略 ID 会引发 `RuntimeError`

---

## 5. 金融工具 (Instruments)

### 5.1 工具类型

| 类型 | 描述 |
|------|------|
| `Equity` | 上市股票或 ETF |
| `CurrencyPair` | 现货外汇或加密货币对 |
| `Commodity` | 现货商品 (如黄金、石油) |
| `FuturesContract` | 可交割期货合约 |
| `FuturesSpread` | 交易所定义的多腿期货策略 |
| `CryptoFuture` | 有到期日的加密货币期货 |
| `CryptoPerpetual` | 永续期货合约 |
| `PerpetualContract` | 资产类别无关的永续掉期 |
| `OptionContract` | 交易所交易期权 (看涨/看跌) |
| `OptionSpread` | 交易所定义的多腿期权策略 |
| `CryptoOption` | 加密货币期权 |
| `BinaryOption` | 固定收益期权 |
| `Cfd` | 差价合约 |
| `BettingInstrument` | 体育/游戏市场选择 |
| `SyntheticInstrument` | 合成工具 |

### 5.2 命名规范

**InstrumentId 格式**: `{symbol}.{venue}`

示例: `ETHUSDT-PERP.BINANCE`

**要求**:
- 同一交易所内原生符号应唯一
- `{symbol}.{venue}` 组合在 Nautilus 系统中必须唯一

### 5.3 精度管理

**精度字段**:
| 字段 | 约束 | 示例 |
|------|------|------|
| `price_precision` | 订单价格、触发价格、成交价 | 2 → 50000.01 |
| `size_precision` | 订单数量、成交数量 | 5 → 1.00001 |

**增量字段**:
| 字段 | 用途 |
|------|------|
| `price_increment` | 最小有效价格变化 (tick size) |
| `size_increment` | 最小有效数量变化 |

**使用工厂方法**:
```python
instrument = self.cache.instrument(instrument_id)
price = instrument.make_price(0.90500)      # 自动舍入到正确精度
quantity = instrument.make_qty(150)         # 自动舍入到正确精度
```

### 5.4 限制

可选限制字段 (交易所依赖):
- `max_quantity` / `min_quantity`: 单笔订单最大/最小数量
- `max_notional` / `min_notional`: 单笔订单最大/最小价值
- `max_price` / `min_price`: 最大/最小有效报价

### 5.5 保证金和费用

**保证金计算**:
```python
# 初始保证金
margin_init = (notional_value / leverage * margin_init) + (notional_value / leverage * taker_fee)

# 维持保证金
margin_maint = (notional_value / leverage * margin_maint) + (notional_value / leverage * taker_fee)
```

**费用率符号约定**:
- **正费用率** = 佣金 (减少账户余额)
- **负费用率** = 返佣 (增加账户余额)

示例: maker_fee = -0.00025 (0.025% 返佣), taker_fee = 0.00075 (0.075% 佣金)

### 5.6 合成工具

**创建合成工具**:
```python
from nautilus_trader.model.instruments import SyntheticInstrument

synthetic = SyntheticInstrument(
    symbol=Symbol("BTC-ETH:BINANCE"),
    price_precision=8,
    components=[btcusdt_id, ethusdt_id],
    formula="BTCUSDT.BINANCE - ETHUSDT.BINANCE",
    ts_event=clock.timestamp_ns(),
    ts_init=clock.timestamp_ns(),
)

self.add_synthetic(synthetic)
self.subscribe_quote_ticks(synthetic.id)
```

**更新公式**:
```python
synthetic = self.cache.synthetic(synthetic_id)
synthetic.change_formula("(BTCUSDT.BINANCE + ETHUSDT.BINANCE) / 2")
self.update_synthetic(synthetic)
```

---

## 6. 值类型 (Value Types)

### 6.1 类型概述

| 类型 | 用途 | 有符号 | 货币 |
|------|------|--------|------|
| `Quantity` | 交易规模、订单数量、持仓 | 否 | - |
| `Price` | 市场价格、报价、价格水平 | 是 | - |
| `Money` | 货币金额、P&L、账户余额 | 是 | 是 |

### 6.2 不可变性

所有值类型都是**不可变**的。操作不会修改原始对象，而是创建新实例。

```python
from nautilus_trader.model.objects import Quantity

qty1 = Quantity(100, precision=0)
qty2 = Quantity(50, precision=0)
result = qty1 + qty2  # 创建新 Quantity

print(qty1)   # 100 (不变)
print(qty2)   # 50 (不变)
print(result) # 150
```

### 6.3 算术运算

**同类型二元运算**:
| 运算 | 结果类型 |
|------|---------|
| `Quantity + Quantity` | `Quantity` |
| `Quantity - Quantity` | `Quantity` |
| `Price + Price` | `Price` |
| `Price - Price` | `Price` |
| `Money + Money` | `Money` |
| `Price * Price` | `Decimal` |
| `Price / Price` | `Decimal` |

**一元运算**:
| 运算 | Price | Quantity | Money |
|------|-------|----------|-------|
| `-x` (负) | `Price` | `Decimal` | `Money` |
| `+x` (正) | `Price` | `Quantity` | `Money` |
| `abs(x)` | `Price` | `Quantity` | `Money` |
| `int(x)` | `int` | `int` | `int` |
| `float(x)` | `float` | `float` | `float` |

**混合类型运算**:
| 左操作数 | 右操作数 | 结果类型 |
|---------|---------|---------|
| 值类型 | `int` | `Decimal` |
| 值类型 | `float` | `float` |
| 值类型 | `Decimal` | `Decimal` |

### 6.4 精度处理

**精度设置**:
```python
p1 = Price(1.23, precision=2)   # 显示为 "1.23"
p2 = Price(1.230, precision=3)  # 显示为 "1.230"
p1 == p2  # True: 底层值相同
```

**算术精度**:
```python
price1 = Price(100.5, precision=1)
price2 = Price(0.125, precision=3)
result = price1 + price2
print(result.precision)  # 3 (取最大值)
```

### 6.5 类型特定约束

**Quantity**:
- 不能为负数
- 小数减大数会引发错误

**Money**:
- 加减运算要求货币匹配
- 不同货币相加会引发 `ValueError`

### 6.6 常用模式

**累加值**:
```python
total = Money(0.00, USD)
for amount in amounts:
    total = total + amount  # 重新赋值
```

**字符串解析**:
```python
qty = Quantity.from_str("100.5")
price = Price.from_str("99.95")
money = Money.from_str("1000.00 USD")
```

---

## 7. 数据 (Data)

### 7.1 内置数据类型

| 类型 | 描述 |
|------|------|
| `OrderBookDelta` | 订单簿增量 (L1/L2/L3) |
| `OrderBookDepth10` | 固定深度 10 档订单簿 |
| `QuoteTick` | 报价 tick |
| `TradeTick` | 成交 tick |
| `Bar` | K 线/柱状图 |
| `Instrument` | 工具定义 |
| `InstrumentStatus` | 工具状态 |
| `InstrumentClose` | 工具收盘价 |

### 7.2 数据请求与订阅

**请求历史数据**:
```python
def on_start(self) -> None:
    self.request_bars(BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-EXTERNAL"))
    self.request_quote_ticks(instrument_id)
    self.request_instrument(instrument_id)

def on_historical_data(self, data: Data) -> None:
    # 处理历史数据
    pass
```

**订阅实时数据**:
```python
def on_start(self) -> None:
    self.subscribe_bars(bar_type)
    self.subscribe_quote_ticks(instrument_id)
    self.subscribe_trade_ticks(instrument_id)

def on_bar(self, bar: Bar) -> None: ...
def on_quote_tick(self, tick: QuoteTick) -> None: ...
def on_trade_tick(self, tick: TradeTick) -> None: ...
```

### 7.3 数据类定义

**继承 Data 类**:
```python
from nautilus_trader.core import Data

class MyDataPoint(Data):
    def __init__(self, label: str, x: int, y: int, z: int, ts_event: int, ts_init: int):
        self.label = label
        self.x = x
        self.y = y
        self.z = z
        self._ts_event = ts_event
        self._ts_init = ts_init
    
    @property
    def ts_event(self) -> int:
        return self._ts_event
    
    @property
    def ts_init(self) -> int:
        return self._ts_init
```

**使用装饰器**:
```python
from nautilus_trader.model.custom import customdataclass

@customdataclass
class GreeksData(Data):
    instrument_id: InstrumentId = InstrumentId.from_str("ES.GLBX")
    delta: float = 0.0
```

### 7.4 发布和订阅自定义数据

```python
# 发布
self.publish_data(
    DataType(MyDataPoint, metadata={"category": 1}),
    MyDataPoint(...)
)

# 订阅
self.subscribe_data(
    data_type=DataType(MyDataPoint, metadata={"category": 1}),
    client_id=ClientId("MY_ADAPTER")
)

# 处理
def on_data(self, data: Data) -> None:
    if isinstance(data, MyDataPoint):
        # 处理自定义数据
        pass
```

### 7.5 信号数据

```python
# 发布信号
self.publish_signal("signal_name", value, ts_event)

# 订阅信号
self.subscribe_signal("signal_name")

# 处理信号
def on_signal(self, signal):
    # signal.value 包含信号值
    pass
```

---

## 8. 事件 (Events)

### 8.1 事件类别

| 类别 | 示例 | 来源 |
|------|------|------|
| Order | `OrderAccepted`, `OrderFilled`, `OrderCanceled` | `ExecutionEngine` |
| Position | `PositionOpened`, `PositionChanged` | `ExecutionEngine` |
| Account | `AccountState` | `ExecutionClient` / `Portfolio` |
| Time | `TimeEvent` | `Clock` |

### 8.2 处理器分发顺序

**订单事件**:
1. 特定处理器 (如 `on_order_filled`)
2. `on_order_event(...)`
3. `on_event(...)`

**持仓事件**:
1. 特定处理器 (如 `on_position_opened`)
2. `on_position_event(...)`
3. `on_event(...)`

**时间事件**:
- 设置回调则直接调用回调方法
- 否则传递到 `on_event(...)`

### 8.3 订单事件

| 事件 | 主要状态转换 | 处理器 |
|------|-------------|--------|
| `OrderInitialized` | (本地创建) | `on_order_initialized` |
| `OrderDenied` | Initialized → Denied | `on_order_denied` |
| `OrderEmulated` | Initialized → Emulated | `on_order_emulated` |
| `OrderReleased` | Emulated → Released | `on_order_released` |
| `OrderSubmitted` | Initialized/Released → Submitted | `on_order_submitted` |
| `OrderAccepted` | Submitted → Accepted | `on_order_accepted` |
| `OrderRejected` | Submitted → Rejected | `on_order_rejected` |
| `OrderTriggered` | Accepted → Triggered | `on_order_triggered` |
| `OrderPendingUpdate` | Accepted → PendingUpdate | `on_order_pending_update` |
| `OrderPendingCancel` | Accepted → PendingCancel | `on_order_pending_cancel` |
| `OrderUpdated` | PendingUpdate → Accepted | `on_order_updated` |
| `OrderCanceled` | PendingCancel/Accepted → Canceled | `on_order_canceled` |
| `OrderExpired` | Accepted → Expired | `on_order_expired` |
| `OrderFilled` | Accepted → Filled/PartiallyFilled | `on_order_filled` |

### 8.4 从成交到持仓的因果链

```
Venue → ExecutionEngine → Cache → Strategy
        ↓
    OrderFilled 事件
        ↓
    确定 Position ID
        ↓
    创建/更新 Position
        ↓
    PositionOpened/Changed/Closed 事件
```

**步骤**:
1. ExecutionEngine 接收 `OrderFilled` 事件
2. 应用成交到订单对象，更新 Cache
3. 确定持仓 ID (基于 OMS 类型和策略配置)
4. 三种结果:
   - 无持仓: 创建 Position，发出 `PositionOpened`
   - 持仓存在且未关闭: 更新 Position，发出 `PositionChanged`
   - 成交关闭持仓: 更新 Position，发出 `PositionClosed`

---

## 9. 期权 (Options)

### 9.1 期权工具类型

| 类型 | 字段 |
|------|------|
| `OptionContract` | `option_kind` (CALL/PUT), `expiration_utc`, `underlying`, `multiplier`, `strike_price` |
| `OptionSpread` | 最多 4 条期权腿，每条腿有权重比、行权价、期权类型 |
| `BinaryOption` | `expiration_utc`, `outcome`/`description`, 无行权价 |

### 9.2 订阅 Greeks

**单个工具 Greeks**:
```python
from nautilus_trader.model.identifiers import ClientId

client_id = ClientId("DERIBIT")
self.subscribe_option_greeks(instrument_id, client_id=client_id)

def on_option_greeks(self, greeks) -> None:
    self.log.info(
        f"{greeks.instrument_id}: "
        f"delta={greeks.delta:.4f} gamma={greeks.gamma:.6f} "
        f"vega={greeks.vega:.4f} theta={greeks.theta:.4f}"
    )
```

**期权链订阅**:
```python
from nautilus_trader.core import nautilus_pyo3

series_id = nautilus_pyo3.OptionSeriesId(...)

# 订阅 ATM 上下 5 个行权价，每 1000ms 快照
strike_range = nautilus_pyo3.StrikeRange.atm_relative(strikes_above=5, strikes_below=5)
self.subscribe_option_chain(
    series_id,
    strike_range=strike_range,
    snapshot_interval_ms=1000,
)

def on_option_chain(self, chain) -> None:
    for strike in chain.strikes():
        call = chain.get_call(strike)
        put = chain.get_put(strike)
        if call and call.greeks:
            self.log.info(f"Call {strike}: delta={call.greeks.delta:.4f}")
```

### 9.3 行权价范围过滤

| 变体 | 描述 | 示例 |
|------|------|------|
| `Fixed` | 订阅明确的行权价集合 | `StrikeRange.fixed([...])` |
| `AtmRelative` | ATM 上下 N 个行权价 | `StrikeRange.atm_relative(5, 5)` |
| `AtmPercent` | ATM 周围百分比范围内的行权价 | `StrikeRange.atm_percent(0.10)` |

### 9.4 快照模式 vs 原始模式

- **快照模式** (`snapshot_interval_ms=1000`): 报价和 Greeks 累积后定期发布
- **原始模式** (`snapshot_interval_ms=None`): 每个更新立即发布

### 9.5 OptionGreeks 数据类型

| 字段 | 类型 | 描述 |
|------|------|------|
| `instrument_id` | `InstrumentId` | 期权合约 ID |
| `delta` | `float` | 标的价格每单位变化的期权价格变化率 |
| `gamma` | `float` | 标的价格每单位变化的 delta 变化率 |
| `vega` | `float` | 隐含波动率变化 1% 的敏感度 |
| `theta` | `float` | 每日时间衰减 (dV/dt / 365.25) |
| `rho` | `float` | 利率变化的敏感度 |
| `mark_iv` | `float` | 标记隐含波动率 |
| `underlying_price` | `float` | 计算时的标的价格 |
| `open_interest` | `float` | 合约持仓量 |

### 9.6 适配器支持

| 适配器 | 单个工具 Greeks | 期权链 |
|--------|---------------|--------|
| Deribit | ✓ | ✓ |
| Bybit | ✓ | ✓ |
| OKX | ✓ | - |

---

## 10. Greeks

### 10.1 两种计算路径

**1. 交易所提供的 Greeks**:
- 通过 Rust/PyO3 `OptionGreeks` 类型
- 实时流式传输
- 来自 Deribit、Bybit、OKX 等交易所

**2. 本地计算的 Greeks**:
- `GreeksCalculator` 进行 Black-Scholes 计算
- 支持冲击情景分析
- Beta 加权和投资组合聚合

### 10.2 GreeksCalculator

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

## 11. 自定义数据 (Custom Data)

### 11.1 定义自定义数据类

**使用装饰器 (推荐)**:
```python
from nautilus_trader.model.custom import customdataclass

@customdataclass
class GreeksData(Data):
    instrument_id: InstrumentId = InstrumentId.from_str("ES.GLBX")
    delta: float = 0.0
```

**手动实现**:
```python
import msgspec
from nautilus_trader.core import Data
import pyarrow as pa

class GreeksData(Data):
    def __init__(self, instrument_id: InstrumentId, ts_event: int, ts_init: int, delta: float):
        self.instrument_id = instrument_id
        self._ts_event = ts_event
        self._ts_init = ts_init
        self.delta = delta
    
    @property
    def ts_event(self): return self._ts_event
    
    @property
    def ts_init(self): return self._ts_init
    
    def to_dict(self):
        return {
            "instrument_id": self.instrument_id.value,
            "ts_event": self._ts_event,
            "ts_init": self._ts_init,
            "delta": self.delta,
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        return GreeksData(
            InstrumentId.from_str(data["instrument_id"]),
            data["ts_event"],
            data["ts_init"],
            data["delta"]
        )
    
    def to_bytes(self):
        return msgspec.msgpack.encode(self.to_dict())
    
    @classmethod
    def from_bytes(cls, data: bytes):
        return cls.from_dict(msgspec.msgpack.decode(data))
    
    @classmethod
    def schema(cls):
        return pa.schema({
            "instrument_id": pa.string(),
            "ts_event": pa.int64(),
            "ts_init": pa.int64(),
            "delta": pa.float64(),
        })
```

### 11.2 注册序列化

```python
from nautilus_trader.serialization.base import register_serializable_type
from nautilus_trader.serialization.arrow.serializer import register_arrow

# 注册基本序列化
register_serializable_type(GreeksData, GreeksData.to_dict, GreeksData.from_dict)

# 注册 Arrow 序列化 (用于 Parquet 目录)
register_arrow(GreeksData, GreeksData.schema(), GreeksData.to_catalog, GreeksData.from_catalog)
```

### 11.3 使用 PyO3 目录

```python
from nautilus_trader.core.nautilus_pyo3 import ParquetDataCatalogV2
from nautilus_trader.core.nautilus_pyo3.model import register_custom_data_class
from nautilus_trader.model.custom import customdataclass_pyo3

@customdataclass_pyo3()
class MarketTickPython:
    symbol: str = ""
    price: float = 0.0
    volume: int = 0

# 注册 (调用一次)
register_custom_data_class(MarketTickPython)

catalog = ParquetDataCatalogV2("/path/to/catalog")
catalog.write_custom_data([MarketTickPython(1, 1, "AAPL", 150.5, 1000)])
result = catalog.query("MarketTickPython", None, None, None, None, None, True)
```

### 11.4 缓存存储

```python
def greeks_key(instrument_id: InstrumentId):
    return f"{instrument_id}_GREEKS"

def cache_greeks(self, greeks_data: GreeksData):
    self.cache.add(greeks_key(greeks_data.instrument_id), greeks_data.to_bytes())

def greeks_from_cache(self, instrument_id: InstrumentId):
    return GreeksData.from_bytes(self.cache.get(greeks_key(instrument_id)))
```

---

## 12. 订单簿 (Order Book)

### 12.1 订单簿类型

| 类型 | 描述 |
|------|------|
| `L3_MBO` | Market by order - 跟踪每个价格水平的每个订单 |
| `L2_MBP` | Market by price - 按价格水平聚合订单 |
| `L1_MBP` | Top-of-book - 仅最佳买卖价 |

### 12.2 订阅订单簿数据

```python
# L3/L2 增量更新
self.subscribe_order_book_deltas(instrument_id)

# 聚合深度快照 (最多 10 档)
self.subscribe_order_book_depth(instrument_id)

# 定时全量快照
self.subscribe_order_book_at_interval(instrument_id, interval_ms=1000)
```

**处理器**:
```python
def on_order_book_deltas(self, deltas: OrderBookDeltas) -> None: ...
def on_order_book_depth(self, depth: OrderBookDepth10) -> None: ...
def on_order_book(self, order_book: OrderBook) -> None: ...
```

### 12.3 访问订单簿

```python
# 最佳价格
best_bid = book.best_bid_price()
best_ask = book.best_ask_price()
spread = book.spread()
midpoint = book.midpoint()

# 分析
avg_px = book.get_avg_px_for_quantity(quantity, OrderSide.Buy)
qty = book.get_quantity_for_price(price, OrderSide.Buy)
fills = book.simulate_fills(&order)
```

### 12.4 完整性检查

`book_check_integrity` 验证订单簿状态:
- **L1_MBP**: 每侧不超过一个价格水平
- **L2_MBP**: 每个价格水平不超过一个订单
- **L3_MBO**: 无结构约束
- **所有类型**: 最佳买价不能超过最佳卖价 (交叉簿无效)

### 12.5 自有订单簿 (Own Order Book)

**目的**:
- 跟踪自己的工作订单，与公共簿分开
- 找到每个价格水平的真实可用流动性 (公共大小 - 自有订单)

**过滤视图**:
```python
# 从公共簿中减去自有订单，查看净可用流动性
net_bids = book.bids_filtered_as_map(Some(10), Some(&own_book), None, None, None)
net_asks = book.asks_filtered_as_map(Some(10), Some(&own_book), None, None, None)

# 完整的过滤 OrderBook，可使用所有分析方法
filtered = book.filtered_view(Some(&own_book), Some(10), None, None, None)
avg_px = filtered.get_avg_px_for_quantity(quantity, OrderSide.Buy)
```

**状态和时间过滤**:
```python
# 仅减去 ACCEPTED 状态的订单
status = Some(AHashSet::from([OrderStatus::Accepted]))
filtered = book.filtered_view(Some(&own_book), None, status, None, None)

# 仅减去至少 500ms 前接受的订单
filtered = book.filtered_view(
    Some(&own_book),
    None,
    None,
    Some(500_000_000),  # accepted_buffer_ns
    Some(clock.timestamp_ns()),
)
```

### 12.6 二元市场

对于二元/预测市场 (如 Polymarket)，YES 和 NO 两侧价格总和为 1.0:

```rust
let combined = yes_own.combined_with_opposite(&no_own).unwrap();
let filtered = book.filtered_view(Some(&combined), None, None, None, None);
```

**转换规则**:
- NO 侧价格 P 的 ask 变为 YES 侧价格 1-P 的 bid
- NO 侧价格 P 的 bid 变为 YES 侧价格 1-P 的 ask

---

## 13. 执行 (Execution)

### 13.1 执行组件

| 组件 | 功能 |
|------|------|
| `Strategy` | 创建执行命令 |
| `ExecAlgorithm` | 执行算法 (如 TWAP) |
| `OrderEmulator` | 订单模拟 |
| `RiskEngine` | 风险检查 |
| `ExecutionEngine` | 执行引擎 |
| `ExecutionClient` | 交易所客户端 |

**执行流**:
```
Strategy → OrderEmulator → ExecAlgorithm → RiskEngine → ExecutionEngine → ExecutionClient
```

### 13.2 订单管理系统 (OMS)

**OMS 类型**:
| 类型 | 描述 |
|------|------|
| `UNSPECIFIED` | 默认基于应用位置 |
| `NETTING` | 每个工具 ID 合并为单一持仓 |
| `HEDGING` | 支持每个工具 ID 多个持仓 (多头和空头) |

**策略 vs 交易所 OMS 组合**:
| 策略 OMS | 交易所 OMS | 描述 |
|---------|-----------|------|
| `NETTING` | `NETTING` | 策略使用交易所原生 OMS |
| `HEDGING` | `HEDGING` | 策略使用交易所原生 OMS |
| `NETTING` | `HEDGING` | 策略覆盖交易所 OMS，交易所跟踪多个，Nautilus 维护单一 |
| `HEDGING` | `NETTING` | 策略覆盖交易所 OMS，交易所跟踪单一，Nautilus 维护多个虚拟持仓 |

### 13.3 风险引擎

**交易前风险检查**:
- 价格精度正确
- 价格为正 (期权除外)
- 数量精度正确
- 低于最大名义价值
- 在最大/最小数量范围内
- `reduce_only` 订单仅减少持仓

**交易状态**:
| 状态 | 描述 |
|------|------|
| `ACTIVE` | 正常操作 |
| `HALTED` | 不处理订单命令直到状态改变 |
| `REDUCING` | 仅处理取消或减少持仓的命令 |

### 13.4 执行算法

**TWAP (时间加权平均价格)**:
```python
from nautilus_trader.examples.algorithms.twap import TWAPExecAlgorithm

# 注册算法
exec_algorithm = TWAPExecAlgorithm()
engine.add_exec_algorithm(exec_algorithm)

# 策略配置
config = EMACrossTWAPConfig(
    instrument_id=instrument_id,
    bar_type=bar_type,
    trade_size=Decimal("0.05"),
    twap_horizon_secs=10.0,    # 执行时间段 (秒)
    twap_interval_secs=2.5,    # 订单间隔 (秒)
)
```

**编写自定义执行算法**:
```python
from nautilus_trader.execution.algorithm import ExecAlgorithm

class MyExecAlgorithm(ExecAlgorithm):
    def on_order(self, order: Order) -> None:
        # 处理主订单
        pass
    
    def spawn_limit(self, primary_order, quantity, price):
        # 生成子订单
        pass
```

**生成订单**:
- `spawn_market(...)`: 生成市价单
- `spawn_limit(...)`: 生成限价单
- `spawn_market_to_limit(...)`: 生成市价转限价单

**子订单 ID 约定**: `{exec_spawn_id}-E{spawn_sequence}`
示例: `O-20230404-001-000-E1`

### 13.5 自有订单簿

**目的**:
- 实时监控订单在交易所公共簿中的状态
- 验证订单放置
- 防止自成交
- 支持高级订单管理策略

**生命周期**:
- 订单提交/接受时添加
- 修改时更新
- 成交/取消/拒绝/到期时移除

**安全取消查询**:
```python
# 排除 PENDING_CANCEL 状态的订单，避免重复取消
orders = cache.own_orders_open(
    instrument_id=instrument_id,
    status=[OrderStatus.Accepted, OrderStatus.PartiallyFilled],
    accepted_buffer_ns=500_000_000,  # 500ms 缓冲
)
```

### 13.6 超量成交 (Overfills)

**原因**:
- 匹配引擎竞态条件
- 最小手数限制
- DEX/AMM 机制
- 多成交原子性不保证

**配置**:
```python
from nautilus_trader.live.config import LiveExecEngineConfig

config = LiveExecEngineConfig(
    allow_overfills=True,  # 记录警告而非拒绝
)
```

**重复成交检测**:
- 通过 `trade_id` 去重
- 核心引擎路径: 4 字段检查 (trade_id, order_side, last_px, last_qty)
- 实时对账: 仅基于 `trade_id` 预过滤

---

## 14. 订单 (Orders)

### 14.1 订单参数

| 参数 | 描述 |
|------|------|
| `time_in_force` | 有效期指令 (GTC, IOC, FOK, GTD, DAY 等) |
| `post_only` | 仅做市 (不消耗流动性) |
| `reduce_only` | 仅减少持仓 |
| `display_qty` | 显示数量 (冰山单) |
| `trigger_type` | 触发类型 (LAST_PRICE, BID_ASK, MARK_PRICE 等) |
| `trailing_offset_type` | 追踪偏移类型 (PRICE, BASIS_POINTS, TICKS) |

### 14.2 订单类型示例

**市价单**:
```python
order = self.order_factory.market(
    instrument_id=InstrumentId.from_str("AUD/USD.IDEALPRO"),
    order_side=OrderSide.BUY,
    quantity=Quantity.from_int(100_000),
    time_in_force=TimeInForce.IOC,  # 可选，默认 GTC
    reduce_only=False,
    tags=["ENTRY"],
)
```

**限价单**:
```python
order = self.order_factory.limit(
    instrument_id=InstrumentId.from_str("ETHUSDT-PERP.BINANCE"),
    order_side=OrderSide.SELL,
    quantity=Quantity.from_int(20),
    price=Price.from_str("5000.00"),
    time_in_force=TimeInForce.GTC,
    post_only=True,
    reduce_only=False,
    display_qty=None,  # 冰山单显示数量
)
```

**止损市价单**:
```python
order = self.order_factory.stop_market(
    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
    order_side=OrderSide.SELL,
    quantity=Quantity.from_int(1),
    trigger_price=Price.from_int(100_000),
    trigger_type=TriggerType.LAST_PRICE,
    time_in_force=TimeInForce.GTC,
    reduce_only=False,
)
```

**止损限价单**:
```python
order = self.order_factory.stop_limit(
    instrument_id=InstrumentId.from_str("GBP/USD.CURRENEX"),
    order_side=OrderSide.BUY,
    quantity=Quantity.from_int(50_000),
    price=Price.from_str("1.30000"),
    trigger_price=Price.from_str("1.30010"),
    trigger_type=TriggerType.BID_ASK,
    time_in_force=TimeInForce.GTD,
    expire_time=pd.Timestamp("2022-06-06T12:00"),
    post_only=True,
)
```

**追踪止损市价单**:
```python
order = self.order_factory.trailing_stop_market(
    instrument_id=InstrumentId.from_str("ETHUSD-PERP.BINANCE"),
    order_side=OrderSide.SELL,
    quantity=Quantity.from_int(10),
    activation_price=Price.from_str("5000"),
    trigger_type=TriggerType.LAST_PRICE,
    trailing_offset=Decimal(100),  # 100 基点 = 1%
    trailing_offset_type=TrailingOffsetType.BASIS_POINTS,
    time_in_force=TimeInForce.GTC,
    reduce_only=True,
    tags=["TRAILING_STOP-1"],
)
```

### 14.3 高级订单

**订单列表**:
- 组合或有订单或大批量订单
- 共享 `order_list_id`

**或有类型**:
| 类型 | 描述 |
|------|------|
| `OTO` (One-Triggers-Other) | 父订单执行后自动放置子订单 |
| `OCO` (One-Cancels-Other) | 执行任一订单取消其他订单 |
| `OUO` (One-Updates-Other) | 执行一订单减少其他订单的未平数量 |

**OTO 触发模式**:
| 触发模式 | 子订单释放时机 |
|---------|---------------|
| 完全触发 | 父订单完全成交后 |
| 部分触发 | 每次部分成交时按比例释放 |

**括号订单**:
- 父订单 (入场) + 止盈限价单 + 止损市价单
- 使用 `OrderFactory` 轻松创建

### 14.4 模拟订单

**模拟触发类型**:
| 触发类型 | 描述 | 用例 |
|---------|------|------|
| `NO_TRIGGER` | 完全禁用模拟 | 使用交易所原生处理 |
| `DEFAULT` / `BID_ASK` | 使用报价触发 | 通用模拟 |
| `LAST_PRICE` | 使用最后成交价触发 | 基于实际成交触发 |
| `DOUBLE_LAST` | 使用连续两次最后成交价确认 | 额外确认 |
| `MARK_PRICE` | 使用标记价格触发 | 期货和永续合约 |
| `INDEX_PRICE` | 使用指数价格触发 | 跟踪指数的衍生品 |

**可模拟的订单类型**:
| 订单类型 | 可模拟 | 释放类型 |
|---------|--------|---------|
| `LIMIT` | ✓ | `MARKET` |
| `STOP_MARKET` | ✓ | `MARKET` |
| `STOP_LIMIT` | ✓ | `LIMIT` |
| `MARKET_IF_TOUCHED` | ✓ | `MARKET` |
| `LIMIT_IF_TOUCHED` | ✓ | `LIMIT` |
| `TRAILING_STOP_MARKET` | ✓ | `MARKET` |
| `TRAILING_STOP_LIMIT` | ✓ | `LIMIT` |

**查询模拟订单**:
```python
# 通过 Cache
emulated_orders = self.cache.orders_emulated()
is_emulated = self.cache.is_order_emulated(client_order_id)

# 直接查询
is_emulated = order.is_emulated
```

**持久化和恢复**:
- 系统崩溃或关闭时，模拟订单从配置的缓存数据库重新加载
- 保留订单状态跨系统重启

---

## 15. 持仓 (Positions)

### 15.1 持仓生命周期

**创建**:
- **NETTING OMS**: 工具首次成交时创建 (每个工具一个持仓)
- **HEDGING OMS**: 新 `position_id` 首次成交时创建 (每个工具多个持仓)

**更新**:
- 聚合买卖成交数量
- 重新计算平均入场和出场价格
- 更新峰值数量 (最大风险敞口)
- 跟踪所有关联订单 ID 和交易 ID
- 累积各币种佣金

**关闭**:
- 净数量变为零 (`FLAT`) 时关闭
- 记录平仓订单 ID
- 计算持续时间
- 计算最终已实现 PnL
- **NETTING OMS**: 重新开仓时快照已关闭状态

### 15.2 持仓调整

**基础币种佣金**:
- 现货货币对 (如 BTC/USDT) 或外汇现货
- 佣金从交易数量中扣除
- 影响 `signed_qty`

**资金调整**:
- 永续期货的定期支付
- 不影响持仓数量
- 记录 `PositionAdjusted` 事件

### 15.3 OMS 类型和持仓管理

**NETTING**:
- 每个工具 ID 一个持仓
- 所有成交贡献到同一持仓
- 持仓在 LONG/SHORT 之间翻转
- 历史快照保留已关闭持仓状态

**HEDGING**:
- 同一工具可存在多个持仓
- 每个持仓有唯一 position_id
- 持仓独立跟踪
- 无自动净额结算

**策略 vs 交易所 OMS**:
| 策略 OMS | 交易所 OMS | 行为 |
|---------|-----------|------|
| `NETTING` | `NETTING` | 策略和交易所均为单一持仓 |
| `HEDGING` | `HEDGING` | 两级均支持多个持仓 |
| `NETTING` | `HEDGING` | 交易所跟踪多个，Nautilus 维护单一 |
| `HEDGING` | `NETTING` | 交易所跟踪单一，Nautilus 维护虚拟持仓 |

### 15.4 持仓快照

**为什么重要**:
在 `NETTING` 系统中，持仓关闭后重新开仓时，持仓对象会重置。没有快照，前一周期的历史已实现 PnL 会丢失。

**工作原理**:
```python
# NETTING OMS 示例
# 周期 1: 开多
BUY 100 units at $50  # 持仓开启
SELL 100 units at $55 # 持仓关闭，PnL = $500
# 快照保留 $500 已实现 PnL

# 周期 2: 开空
SELL 50 units at $54  # 持仓重新开启 (空头)
BUY 50 units at $52   # 持仓关闭，PnL = $100
# 快照保留 $100 已实现 PnL

# 总已实现 PnL = $500 + $100 = $600 (来自快照)
```

**查询快照**:
```python
snapshots = self.cache.position_snapshots(instrument_id=instrument_id)
```

### 15.5 PnL 计算

**已实现 PnL**:
```python
# 标准工具
realized_pnl = (exit_price - entry_price) * closed_quantity * multiplier

# 反向工具 (方向感知)
# LONG: realized_pnl = closed_quantity * multiplier * (1/entry_price - 1/exit_price)
# SHORT: realized_pnl = closed_quantity * multiplier * (1/exit_price - 1/entry_price)
```

**未实现 PnL**:
```python
position.unrealized_pnl(last_price)    # 使用最后成交价
position.unrealized_pnl(bid_price)     # 多头保守估计
position.unrealized_pnl(ask_price)     # 空头保守估计
```

**总 PnL**:
```python
total_pnl = position.total_pnl(current_price)
# = realized_pnl + unrealized_pnl
```

### 15.6 持仓属性

**标识符**:
- `id`: 唯一持仓 ID
- `instrument_id`: 交易工具
- `account_id`: 持仓账户
- `trader_id`: 交易员 ID
- `strategy_id`: 管理策略
- `opening_order_id`: 开仓订单 ID
- `closing_order_id`: 平仓订单 ID

**状态**:
- `side`: 当前持仓方向 (`LONG`, `SHORT`, `FLAT`)
- `entry`: 当前开仓方向 (`Buy` 为 `LONG`, `Sell` 为 `SHORT`)
- `quantity`: 当前绝对持仓规模
- `signed_qty`: 有符号持仓规模 (正为 `LONG`, 负为 `SHORT`)
- `peak_qty`: 持仓生命周期内最大数量
- `is_open` / `is_closed`: 持仓状态

**价格和估值**:
- `avg_px_open`: 平均入场价
- `avg_px_close`: 平均出场价
- `realized_pnl`: 已实现盈亏
- `realized_return`: 已实现回报率 (小数，如 0.05 表示 5%)
- `quote_currency` / `base_currency` / `settlement_currency`

**时间戳**:
- `ts_init`: 持仓初始化时间
- `ts_opened`: 持仓开启时间
- `ts_last`: 最后更新时间
- `ts_closed`: 持仓关闭时间
- `duration_ns`: 开仓到平仓的持续时间 (纳秒)

---

## 16. 缓存 (Cache)

### 16.1 概述

`Cache` 是中央内存数据库，存储和管理所有交易相关数据。

**用途**:
1. **存储市场数据**: 订单簿、报价、成交、K 线
2. **跟踪交易数据**: 订单历史、持仓、账户信息
3. **存储自定义数据**: 用户定义的对象或数据

### 16.2 缓存工作原理

**内置类型**:
- 系统自动添加数据到 Cache
- 实盘环境中，引擎异步应用更新，可能有短暂延迟
- 报价、成交、K 线: DataEngine 先写入 Cache 再发布，处理器运行时最新值已可用
- 订单簿增量和深度快照: 直接发布，不写入 Cache

### 16.3 配置

```python
from nautilus_trader.config import CacheConfig, BacktestEngineConfig, TradingNodeConfig

# 回测配置
engine_config = BacktestEngineConfig(
    cache=CacheConfig(
        tick_capacity=10_000,    # 每个工具存储最后 10,000 个 tick
        bar_capacity=5_000,      # 每个 K 线类型存储最后 5,000 根 K 线
    ),
)

# 实盘配置
node_config = TradingNodeConfig(
    cache=CacheConfig(
        tick_capacity=10_000,
        bar_capacity=5_000,
        database=DatabaseConfig(
            type="redis",
            host="localhost",
            port=6379,
            timeout=2,
        ),
    ),
)
```

**配置选项**:
| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `database` | `DatabaseConfig` | None | 持久化数据库配置 |
| `encoding` | `str` | "msgpack" | 数据编码格式 |
| `tick_capacity` | `int` | 10,000 | 每个工具最大存储 tick 数 |
| `bar_capacity` | `int` | 10,000 | 每个 K 线类型最大存储 K 线数 |
| `drop_instruments_on_reset` | `bool` | True | 重置时清除工具 |

### 16.4 访问市场数据

**K 线访问**:
```python
bars = self.cache.bars(bar_type)                    # 所有 K 线列表
latest_bar = self.cache.bar(bar_type)               # 最新 K 线
second_last_bar = self.cache.bar(bar_type, index=1) # 倒数第二根
bar_count = self.cache.bar_count(bar_type)          # K 线数量
has_bars = self.cache.has_bars(bar_type)            # 是否有 K 线
```

**报价 tick**:
```python
quotes = self.cache.quote_ticks(instrument_id)
latest_quote = self.cache.quote_tick(instrument_id)
quote_count = self.cache.quote_tick_count(instrument_id)
has_quotes = self.cache.has_quote_ticks(instrument_id)
```

**成交 tick**:
```python
trades = self.cache.trade_ticks(instrument_id)
latest_trade = self.cache.trade_tick(instrument_id)
trade_count = self.cache.trade_tick_count(instrument_id)
has_trades = self.cache.has_trade_ticks(instrument_id)
```

**订单簿**:
```python
book = self.cache.order_book(instrument_id)
has_book = self.cache.has_order_book(instrument_id)
update_count = self.cache.book_update_count(instrument_id)
```

**价格访问**:
```python
from nautilus_trader.core.rust.model import PriceType

price = self.cache.price(
    instrument_id=instrument_id,
    price_type=PriceType.MID,  # BID, ASK, MID, LAST
)
```

### 16.5 访问交易对象

**订单**:
```python
# 基本访问
order = self.cache.order(ClientOrderId("O-123"))
orders = self.cache.orders()
orders_for_venue = self.cache.orders(venue=venue)
orders_for_strategy = self.cache.orders(strategy_id=strategy_id)

# 状态查询
open_orders = self.cache.orders_open()
closed_orders = self.cache.orders_closed()
emulated_orders = self.cache.orders_emulated()
inflight_orders = self.cache.orders_inflight()

# 状态检查
exists = self.cache.order_exists(client_order_id)
is_open = self.cache.is_order_open(client_order_id)
is_closed = self.cache.is_order_closed(client_order_id)
is_emulated = self.cache.is_order_emulated(client_order_id)

# 统计
open_count = self.cache.orders_open_count()
closed_count = self.cache.orders_closed_count()
total_count = self.cache.orders_total_count()
```

**持仓**:
```python
# 基本访问
position = self.cache.position(PositionId("P-123"))
all_positions = self.cache.positions()
open_positions = self.cache.positions_open()
closed_positions = self.cache.positions_closed()

# 过滤查询
venue_positions = self.cache.positions(venue=venue)
instrument_positions = self.cache.positions(instrument_id=instrument_id)
long_positions = self.cache.positions(side=PositionSide.LONG)

# 状态检查
exists = self.cache.position_exists(position_id)
is_open = self.cache.is_position_open(position_id)
is_closed = self.cache.is_position_closed(position_id)

# 关系查询
orders = self.cache.orders_for_position(position_id)
position = self.cache.position_for_order(client_order_id)

# 统计
open_count = self.cache.positions_open_count()
closed_count = self.cache.positions_closed_count()
total_count = self.cache.positions_total_count()
```

**账户**:
```python
account = self.cache.account(account_id)
account = self.cache.account_for_venue(venue)
account_id = self.cache.account_id(venue)
```

**工具和货币**:
```python
instrument = self.cache.instrument(instrument_id)
all_instruments = self.cache.instruments()
venue_instruments = self.cache.instruments(venue=venue)
instrument_ids = self.cache.instrument_ids()
```

### 16.6 自定义数据存储

```python
# 存储
self.cache.add(key="my_key", value=b"some binary data")

# 检索
stored_data = self.cache.get("my_key")  # 返回 bytes 或 None
```

### 16.7 Cache vs Portfolio

| 组件 | 用途 |
|------|------|
| `Cache` | 维护历史知识和当前状态，立即更新本地状态变化 |
| `Portfolio` | 聚合持仓、风险敞口和账户信息，提供当前状态无历史 |

```python
class MyStrategy(Strategy):
    def on_position_changed(self, event: PositionEvent) -> None:
        # 需要历史视角时用 Cache
        position_history = self.cache.position_snapshots(event.position_id)
        
        # 需要当前实时状态时用 Portfolio
        current_exposure = self.portfolio.net_exposure(event.instrument_id)
```

---

## 17. 消息总线 (Message Bus)

### 17.1 概述

`MessageBus` 通过消息传递实现组件间通信，创建松耦合架构。

**消息模式**:
- 点对点 (Point-to-Point)
- 发布/订阅 (Publish/Subscribe)
- 请求/响应 (Request/Response)

**消息类别**:
- 数据 (Data)
- 事件 (Events)
- 命令 (Commands)

### 17.2 消息风格对比

| 消息风格 | 用途 | 最佳用例 |
|---------|------|---------|
| `MessageBus` 发布/订阅主题 | 低级直接访问消息总线 | 自定义事件、系统级通信 |
| `Actor` 发布/订阅数据 | 结构化交易数据交换 | 交易指标、指标、需要持久化的数据 |
| `Actor` 发布/订阅信号 | 轻量级通知 | 简单警报、标志、状态更新 |

### 17.3 MessageBus 发布/订阅

```python
from nautilus_trader.core.message import Event

# 定义自定义事件
class Each10thBarEvent(Event):
    TOPIC = "each_10th_bar"
    
    def __init__(self, bar):
        self.bar = bar

# 订阅 (在 Strategy 中)
self.msgbus.subscribe(Each10thBarEvent.TOPIC, self.on_each_10th_bar)

# 发布
event = Each10thBarEvent(bar)
self.msgbus.publish(Each10thBarEvent.TOPIC, event)

# 处理器
def on_each_10th_bar(self, event: Each10thBarEvent):
    self.log.info(f"Received 10th bar: {event.bar}")
```

### 17.4 Actor 发布/订阅数据

```python
from nautilus_trader.core.data import Data
from nautilus_trader.model.custom import customdataclass

@customdataclass
class GreeksData(Data):
    delta: float
    gamma: float

# 发布数据
data = GreeksData(
    delta=0.75, 
    gamma=0.1, 
    ts_event=1_630_000_000_000_000_000, 
    ts_init=1_630_000_000_000_000_000
)
self.publish_data(GreeksData, data)

# 订阅
self.subscribe_data(GreeksData)

# 处理器
def on_data(self, data: Data):
    if isinstance(data, GreeksData):
        self.log.info(f"Delta: {data.delta}, Gamma: {data.gamma}")
```

### 17.5 Actor 发布/订阅信号

```python
import types

signals = types.SimpleNamespace()
signals.NEW_HIGHEST_PRICE = "NewHighestPriceReached"
signals.NEW_LOWEST_PRICE = "NewLowestPriceReached"

# 订阅信号
self.subscribe_signal(signals.NEW_HIGHEST_PRICE)
self.subscribe_signal(signals.NEW_LOWEST_PRICE)

# 发布信号
self.publish_signal(
    name=signals.NEW_HIGHEST_PRICE,
    value=signals.NEW_HIGHEST_PRICE,
    ts_event=bar.ts_event,
)

# 处理器
def on_signal(self, signal):
    match signal.value:
        case signals.NEW_HIGHEST_PRICE:
            self.log.info("New highest price was reached")
        case signals.NEW_LOWEST_PRICE:
            self.log.info("New lowest price was reached")
```

### 17.6 决策指南

| 用例 | 推荐方法 | 设置要求 |
|------|---------|---------|
| 自定义事件或系统级通信 | `MessageBus` + 主题发布/订阅 | 主题 + 处理器管理 |
| 结构化交易数据 | `Actor` + 数据发布/订阅 + 可选 `@customdataclass` | 新类定义继承 `Data` |
| 简单警报/通知 | `Actor` + 信号发布/订阅 | 仅信号名称 |

### 17.7 外部发布

**Redis 支持** (最低版本 6.2):
```python
from nautilus_trader.config import MessageBusConfig, DatabaseConfig

message_bus=MessageBusConfig(
    database=DatabaseConfig(),
    encoding="json",  # 或 "msgpack"
    timestamps_as_iso8601=True,
    buffer_interval_ms=100,
    autotrim_mins=30,
    use_trader_prefix=True,
    use_trader_id=True,
    use_instance_id=False,
    streams_prefix="streams",
    types_filter=[QuoteTick, TradeTick],
)
```

**配置选项**:
| 参数 | 描述 |
|------|------|
| `encoding` | JSON 或 MessagePack |
| `timestamps_as_iso8601` | 时间戳格式为 ISO 8601 字符串 |
| `buffer_interval_ms` | 批量操作缓冲间隔 |
| `autotrim_mins` | 自动修剪回溯窗口 (分钟) |
| `types_filter` | 排除外部发布的消息类型 |

### 17.8 外部流

**生产者节点配置**:
```python
message_bus=MessageBusConfig(
    database=DatabaseConfig(timeout=2),
    use_trader_id=False,
    use_trader_prefix=False,
    use_instance_id=False,
    streams_prefix="binance",  # 简单可预测的流键
    stream_per_topic=False,
    autotrim_mins=30,
),
```

**消费者节点配置**:
```python
data_engine=LiveDataEngineConfig(
    external_clients=[ClientId("BINANCE_EXT")],
),
message_bus=MessageBusConfig(
    database=DatabaseConfig(timeout=2),
    external_streams=["binance"],  # 监听外部流
),
```

---

## 18. 投资组合 (Portfolio)

### 18.1 概述

`Portfolio` 跟踪所有策略和工具的持仓，提供持仓、风险敞口和绩效的统一视图。

### 18.2 账户和持仓信息

```python
from nautilus_trader.accounting.accounts.base import Account
from nautilus_trader.model import Venue, Currency, Money, InstrumentId
import decimal

def account(self, venue: Venue) -> Account

def balances_locked(self, venue: Venue) -> dict[Currency, Money]
def margins_init(self, venue: Venue) -> dict[Currency, Money]
def margins_maint(self, venue: Venue) -> dict[Currency, Money]
def unrealized_pnls(self, venue: Venue) -> dict[Currency, Money]
def realized_pnls(self, venue: Venue) -> dict[Currency, Money]
def net_exposures(self, venue: Venue) -> dict[Currency, Money]

def unrealized_pnl(self, instrument_id: InstrumentId) -> Money
def realized_pnl(self, instrument_id: InstrumentId) -> Money
def net_exposure(self, instrument_id: InstrumentId) -> Money
def net_position(self, instrument_id: InstrumentId) -> decimal.Decimal

def is_net_long(self, instrument_id: InstrumentId) -> bool
def is_net_short(self, instrument_id: InstrumentId) -> bool
def is_flat(self, instrument_id: InstrumentId) -> bool
def is_completely_flat(self) -> bool
```

### 18.3 报告和分析

```python
# 投资组合级指标
portfolio.total_realized_pnl(venue)      # 交易所总已实现 PnL
portfolio.total_unrealized_pnl(venue)    # 交易所总未实现 PnL
portfolio.total_commissions(venue)       # 交易所总佣金

# 持仓级指标
portfolio.net_exposure(instrument_id)    # 净风险敞口
portfolio.net_position(instrument_id)    # 净持仓量
portfolio.is_net_long(instrument_id)     # 是否净多头
portfolio.is_net_short(instrument_id)    # 是否净空头
portfolio.is_flat(instrument_id)         # 是否平仓
portfolio.is_completely_flat()           # 是否完全平仓
```

### 18.4 账户状态

```python
account = self.portfolio.account(venue)

# 账户属性
account.account_id()      # 账户 ID
account.account_type()    # 账户类型 (CASH/MARGIN/BETTING)
account.base_currency()   # 基础货币
account.is_cash_account() # 是否现金账户
account.is_margin_account() # 是否保证金账户

# 余额和保证金
account.balances()        # 所有余额
account.balances_locked() # 锁定余额
account.margins_init()    # 初始保证金
account.margins_maint()   # 维持保证金

# PnL
account.unrealized_pnls() # 未实现 PnL
account.realized_pnls()   # 已实现 PnL
account.net_exposures()   # 净风险敞口

# 统计
account.starting_balance()  # 起始余额
account.peak_value()        # 峰值价值
account.value()             # 当前价值
```

---

## 19. 报告 (Reports)

### 19.1 报告类型

| 报告类型 | 描述 |
|---------|------|
| `PerformanceReport` | 策略绩效汇总 |
| `PositionReport` | 持仓历史记录 |
| `OrderReport` | 订单历史记录 |
| `TradeReport` | 成交历史记录 |
| `AccountReport` | 账户状态历史 |

### 19.2 生成报告

```python
from nautilus_trader.config import BacktestEngineConfig
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# 配置报告
config = BacktestEngineConfig(
    run_analysis=True,  # 启用绩效分析
)

# 生成报告
engine.generate_reports()

# 访问报告
performance_report = engine.performance_report()
position_report = engine.position_report()
order_report = engine.order_report()
```

### 19.3 绩效指标

**收益指标**:
- 总收益率 (Total Return)
- 年化收益率 (Annualized Return)
- 夏普比率 (Sharpe Ratio)
- 索提诺比率 (Sortino Ratio)
- 卡玛比率 (Calmar Ratio)

**风险指标**:
- 最大回撤 (Max Drawdown)
- 回撤持续时间 (Drawdown Duration)
- 波动率 (Volatility)
- VaR (Value at Risk)

**交易指标**:
- 总交易数 (Total Trades)
- 胜率 (Win Rate)
- 盈亏比 (Profit/Loss Ratio)
- 平均持仓时间 (Average Hold Time)

### 19.4 可视化

```python
from nautilus_trader.analysis import Plotter

plotter = Plotter()

# 生成 tearsheet
plotter.plot_tearsheet(
    portfolio_analyzer=analyzer,
    save_path="./tearsheet.html",
)

# 自定义图表
plotter.plot_equity_curve(analyzer)
plotter.plot_drawdowns(analyzer)
plotter.plot_monthly_returns(analyzer)
plotter.plot_position_duration(analyzer)
```

---

## 20. 日志 (Logging)

### 20.1 日志级别

| 级别 | 用途 |
|------|------|
| `CRITICAL` | 严重错误，系统无法继续 |
| `ERROR` | 错误，操作失败 |
| `WARNING` | 警告，潜在问题 |
| `INFO` | 一般信息 |
| `DEBUG` | 调试信息 |
| `TRACE` | 详细追踪 |

### 20.2 日志配置

```python
from nautilus_trader.config import LoggingConfig, BacktestEngineConfig

config = BacktestEngineConfig(
    logging=LoggingConfig(
        log_level="INFO",
        log_level_file="DEBUG",
        log_directory="./logs",
        log_colors=True,  # 彩色输出
        log_filename_format="{trader_id}-{strategy_id}-{component}.log",
    ),
)
```

### 20.3 日志使用

```python
# 策略中日志
self.log.info("Strategy started")
self.log.debug(f"Processing bar: {bar}")
self.log.warning("Low liquidity detected")
self.log.error(f"Order rejected: {order}")
self.log.critical("System fault detected")

# 带上下文日志
self.log.info(
    "Order submitted",
    detail={
        "order_id": order.client_order_id.value,
        "price": str(order.price),
        "quantity": str(order.quantity),
    },
)
```

### 20.4 日志输出

**控制台输出**:
```
2024-01-05T15:30:45.123456789Z [INFO] STRATEGY: MyStrategy-001: Strategy started
2024-01-05T15:30:46.123456789Z [DEBUG] STRATEGY: MyStrategy-001: Processing bar: BTCUSDT-1-MINUTE
```

**文件输出**:
- 按组件分离日志文件
- 支持日志轮转
- 可配置保留期限

---

## 21. 回测 (Backtesting)

### 21.1 回测引擎类型

| 引擎 | 用途 | 特点 |
|------|------|------|
| `BacktestEngine` | 低阶 API | 直接控制，灵活 |
| `BacktestNode` | 高阶 API | 配置驱动，推荐生产 |

### 21.2 低阶 API 示例

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
)

# 运行回测
engine.run()

# 生成报告
engine.generate_reports()

# 清理
engine.dispose()
```

### 21.3 高阶 API 示例

```python
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import BacktestRunConfig, BacktestEngineConfig

# 配置回测运行
configs = [
    BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            run_analysis=True,
        ),
        data=[
            # 数据配置
        ],
        venues=[
            # 交易所配置
        ],
        strategies=[
            # 策略配置
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

### 21.4 数据目录

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

# 在回测配置中使用
config = BacktestRunConfig(
    data=[
        DataConfig(
            catalog_path="./catalog",
            instrument_id="BTCUSDT.BINANCE",
            bar_type="1-HOUR",
        ),
    ],
)
```

### 21.5 模拟模块

| 模块 | 用途 |
|------|------|
| `FXRatesSimulator` | 外汇汇率模拟 |
| `InterestRateSimulator` | 利率模拟 |
| `VolatilitySimulator` | 波动率模拟 |
| `CommissionSimulator` | 佣金模拟 |

### 21.6 回测配置选项

```python
config = BacktestEngineConfig(
    # 基本配置
    trader_id="BACKTESTER-001",
    run_analysis=True,
    
    # 缓存配置
    cache=CacheConfig(
        tick_capacity=10_000,
        bar_capacity=5_000,
    ),
    
    # 日志配置
    logging=LoggingConfig(
        log_level="INFO",
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

## 22. 可视化 (Visualization)

### 22.1 交互式图表

```python
from nautilus_trader.analysis import Plotter

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
```

### 22.2 Tearsheet

```python
# 生成完整 tearsheet
plotter.plot_tearsheet(
    portfolio_analyzer=analyzer,
    save_path="./tearsheet.html",
    title="My Strategy Performance",
)
```

**Tearsheet 包含**:
- 权益曲线
- 回撤分析
- 月度收益
- 收益分布
- 持仓统计
- 交易指标

### 22.3 自定义图表

```python
import plotly.graph_objects as go

# 创建自定义图表
fig = go.Figure()

# 添加 K 线
fig.add_trace(go.Candlestick(
    x=bars_df.index,
    open=bars_df.open,
    high=bars_df.high,
    low=bars_df.low,
    close=bars_df.close,
))

# 添加成交标记
fig.add_trace(go.Scatter(
    x=fills_df.index,
    y=fills_df.price,
    mode='markers',
    name='Fills',
))

fig.show()
```

---

## 23. 配置 (Configuration)

### 23.1 配置层次

| 层次 | 范围 | 示例 |
|------|------|------|
| `TradingNodeConfig` | 整个交易节点 | 所有交易所、策略 |
| `BacktestEngineConfig` | 回测引擎 | 回测特定设置 |
| `StrategyConfig` | 单个策略 | 策略参数 |
| `AdapterConfig` | 适配器 | 交易所连接设置 |

### 23.2 配置文件格式

**YAML 配置**:
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
      bar_type: "1-HOUR"
      fast_ema_period: 10
      slow_ema_period: 20
      trade_size: 0.1
```

**Python 配置**:
```python
from nautilus_trader.config import TradingNodeConfig

config = TradingNodeConfig(
    trader_id="TRADER-001",
    run_id="20240105-001",
    
    cache=CacheConfig(
        database=DatabaseConfig(
            type="redis",
            host="localhost",
            port=6379,
        ),
    ),
    
    logging=LoggingConfig(
        log_level="INFO",
        log_colors=True,
    ),
    
    strategies=[
        EMACrossConfig(
            instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
            bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"),
            fast_ema_period=10,
            slow_ema_period=20,
            trade_size=Decimal("0.1"),
        ),
    ],
)
```

### 23.3 环境变量

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

### 23.4 配置验证

```python
from nautilus_trader.config import TradingNodeConfig

# 配置会自动验证
try:
    config = TradingNodeConfig(**config_dict)
    # 配置有效
except ValueError as e:
    # 配置无效
    print(f"Invalid config: {e}")
```

---

## 24. 实盘交易 (Live Trading)

### 24.1 交易节点

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

### 24.2 节点生命周期

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
```

### 24.3 状态监控

```python
# 检查节点状态
print(f"Node state: {node.state}")

# 检查策略状态
for strategy in node.strategies:
    print(f"Strategy {strategy.id}: {strategy.state}")

# 检查适配器状态
for adapter in node.adapters:
    print(f"Adapter {adapter.id}: {adapter.state}")
```

### 24.4 热重载配置

```python
# 运行时更新配置
node.update_config(new_config)

# 重新加载策略
node.reload_strategies()

# 重新加载适配器
node.reload_adapters()
```

### 24.5 优雅关闭

```python
import signal
import sys

def signal_handler(sig, frame):
    print("Shutting down gracefully...")
    node.stop()
    node.dispose()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

---

## 25. 适配器 (Adapters)

### 25.1 适配器类型

| 类型 | 功能 |
|------|------|
| `DataClient` | 市场数据订阅 |
| `ExecutionClient` | 订单执行 |
| `DataExecutionClient` | 数据 + 执行 |

### 25.2 支持的交易所

| 交易所 | 数据类型 | 执行类型 | 状态 |
|--------|---------|---------|------|
| Binance | Quote/Trade/Bar/OrderBook | Market/Limit/Stop | ✅ 生产 |
| Bybit | Quote/Trade/Bar/OrderBook | Market/Limit/Stop | ✅ 生产 |
| Interactive Brokers | Quote/Trade/Bar | Market/Limit | ✅ 生产 |
| Databento | Quote/Trade/Bar | - | ✅ 生产 |
| Betfair | Quote/Trade | Market/Limit | ✅ 生产 |
| OKX | Quote/Trade/Bar/OrderBook | Market/Limit | 🧪 测试 |
| Kraken | Quote/Trade/Bar | Market/Limit | 🧪 测试 |

### 25.3 适配器配置

```python
from nautilus_trader.adapters.binance.config import BinanceLiveConfig

config = BinanceLiveConfig(
    instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
    api_key="your_api_key",
    api_secret="your_api_secret",
    account_type="SPOT",  # 或 FUTURES
    use_testnet=False,
)
```

### 25.4 编写自定义适配器

```python
from nautilus_trader.live.execution_client import ExecutionClient

class MyExecutionClient(ExecutionClient):
    def __init__(self, config: MyConfig):
        super().__init__(config)
        # 初始化连接
    
    async def connect(self) -> None:
        # 建立连接
        pass
    
    async def disconnect(self) -> None:
        # 断开连接
        pass
    
    async def submit_order(self, order: Order) -> None:
        # 提交订单到交易所
        pass
    
    async def cancel_order(self, order: Order) -> None:
        # 取消订单
        pass
    
    async def modify_order(self, order: Order, quantity: Quantity) -> None:
        # 修改订单
        pass
```

### 25.5 适配器生命周期

```
PRE_INITIALIZED → READY → STARTING → RUNNING
                                    ↓
RUNNING → STOPPING → STOPPED → RUNNING (resume)
RUNNING → DEGRADED → RUNNING (resume)
RUNNING → FAULTED
RUNNING → DISPOSED
```

### 25.6 沙箱模式

```python
from nautilus_trader.adapters.sandbox.config import SandboxLiveConfig

config = SandboxLiveConfig(
    instrument_ids=["BTCUSDT.SANDBOX"],
    account_type="MARGIN",
    starting_balances=[Money(1_000_000, "USD")],
)

# 沙箱特点:
# - 实时市场数据
# - 虚拟执行 (不实际下单)
# - 可配置滑点和延迟
# - 适合策略验证
```

---

## 26. Rust 开发

### 26.1 项目结构

```
crates/
├── core/           # 核心原语 (时间、UUID 等)
├── model/          # 领域模型 (订单、持仓等)
├── common/         # 通用组件 (配置、日志等)
├── system/         # 系统内核 (消息总线、缓存等)
├── trading/        # 交易组件 (策略、执行等)
├── data/           # 数据引擎
├── execution/      # 执行引擎
├── portfolio/      # 投资组合
├── risk/           # 风险管理
├── persistence/    # 持久化
├── live/           # 实盘节点
├── backtest/       # 回测节点
└── adapters/       # 交易所适配器
```

### 26.2 编写 Rust Actor

```rust
use nautilus_trader::trading::strategy::Strategy;
use nautilus_trader::model::data::bar::Bar;

pub struct MyRustStrategy {
    // 策略状态
}

impl Strategy for MyRustStrategy {
    fn on_start(&mut self) {
        // 初始化
    }
    
    fn on_bar(&mut self, bar: &Bar) {
        // 处理 K 线
    }
    
    fn on_stop(&mut self) {
        // 清理
    }
}
```

### 26.3 PyO3 绑定

```rust
use pyo3::prelude::*;
use nautilus_trader::model::data::bar::Bar;

#[pyclass]
pub struct MyRustActor {
    // 状态
}

#[pymethods]
impl MyRustActor {
    #[new]
    fn new() -> Self {
        MyRustActor { /* 初始化 */ }
    }
    
    fn on_bar(&mut self, bar: &Bar) {
        // 处理 K 线
    }
}
```

### 26.4 构建和测试

```bash
# 构建所有 crates
cargo build --release

# 运行测试
cargo test

# 运行特定测试
cargo test --package nautilus_core --lib

# 检查代码
cargo clippy

# 格式化代码
cargo fmt
```

### 26.5 性能优化

| 优化技术 | 描述 |
|---------|------|
| 零拷贝序列化 | 避免不必要的数据复制 |
| 对象池 | 重用对象减少分配 |
| 批量处理 | 减少系统调用 |
| 异步 I/O | Tokio 运行时 |
| SIMD 指令 | 向量化计算 |

---

## 附录 A: 常用代码片段

### A.1 策略模板

```python
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

class MyStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal

class MyStrategy(Strategy):
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.bar_count = 0
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
    
    def on_bar(self, bar: Bar) -> None:
        self.bar_count += 1
        # 策略逻辑
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
```

### A.2 数据加载

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog

catalog = ParquetDataCatalog("./catalog")

# 加载 K 线
bars = catalog.bars(
    instrument_ids=["BTCUSDT.BINANCE"],
    bar_types=["1-HOUR"],
    start="2024-01-01",
    end="2024-12-31",
)

# 加载报价
quotes = catalog.quote_ticks(
    instrument_ids=["BTCUSDT.BINANCE"],
    start="2024-01-01",
    end="2024-12-31",
)
```

### A.3 订单工厂

```python
# 市价单
order = self.order_factory.market(
    instrument_id=self.instrument.id,
    order_side=OrderSide.BUY,
    quantity=self.instrument.make_qty(1.0),
)

# 限价单
order = self.order_factory.limit(
    instrument_id=self.instrument.id,
    order_side=OrderSide.BUY,
    quantity=self.instrument.make_qty(1.0),
    price=self.instrument.make_price(50000.0),
)

# 止损单
order = self.order_factory.stop_market(
    instrument_id=self.instrument.id,
    order_side=OrderSide.SELL,
    quantity=self.instrument.make_qty(1.0),
    trigger_price=self.instrument.make_price(49000.0),
)
```

---

## 附录 B: 常见问题 (FAQ)

### B.1 安装问题

**Q: Windows 上安装失败？**
A: Windows 仅支持 64 位标准精度版本。确保使用 Python 3.12+ 和最新 pip。

**Q: 依赖冲突？**
A: 使用 `uv` 包管理器或创建干净的虚拟环境。

### B.2 回测问题

**Q: 回测结果与实盘不一致？**
A: 检查滑点、佣金、延迟设置。确保使用相同的数据源。

**Q: 回测速度慢？**
A: 减少数据量、使用 Bar 而非 Tick、禁用不必要的分析。

### B.3 实盘问题

**Q: 连接交易所失败？**
A: 检查 API 密钥、网络、防火墙设置。

**Q: 订单被拒绝？**
A: 检查风险引擎设置、订单参数、账户余额。

---

## 附录 C: 资源链接

| 资源 | 链接 |
|------|------|
| 官方文档 | https://nautilustrader.io/docs/ |
| GitHub | https://github.com/nautechsystems/nautilus_trader |
| PyPI | https://pypi.org/project/nautilus-trader/ |
| Docker | https://ghcr.io/nautechsystems/jupyterlab:nightly |
| 社区讨论 | https://github.com/nautechsystems/nautilus_trader/discussions |

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-03-31  
> **维护者**: Nautilus Trader 社区

---

此 Markdown 文件可直接用于 AI 工具编程参考，包含完整的 Concepts 目录内容汇总。如需进一步细化某个章节，请告知！