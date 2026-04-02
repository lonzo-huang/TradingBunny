# Nautilus Trader Integrations 集成指南汇总

> **文档版本**: develop 分支 (2026 年 3 月)  
> **适用对象**: 量化开发者、策略研究员、系统架构师  
> **用途**: AI 工具编程参考文档

---

## 目录

1. [概述 (Overview)](#1-概述-overview)
2. [Binance 集成](#2-binance-集成)
3. [Bybit 集成](#3-bybit 集成)
4. [Interactive Brokers 集成](#4-interactive-brokers 集成)
5. [Databento 集成](#5-databento 集成)
6. [Betfair 集成](#6-betfair 集成)
7. [OKX 集成](#7-okx 集成)
8. [Kraken 集成](#8-kraken 集成)
9. [BitMEX 集成](#9-bitmex 集成)
10. [dYdX 集成](#10-dydx 集成)
11. [Hyperliquid 集成](#11-hyperliquid 集成)
12. [Polymarket 集成](#12-polymarket 集成)
13. [区块链适配器](#13-区块链适配器)
14. [沙箱适配器](#14-沙箱适配器)
15. [通用数据适配器](#15-通用数据适配器)
16. [适配器开发指南](#16-适配器开发指南)

---

## 1. 概述 (Overview)

### 1.1 集成架构

Nautilus Trader 使用**适配器模式**连接外部交易所和数据源。

```
┌─────────────────────────────────────────────────────────┐
│                    Nautilus Trader                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  Strategy   │  │   Cache     │  │  Portfolio  │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
│         │                │                │              │
│  ┌──────▼────────────────▼────────────────▼──────┐      │
│  │              MessageBus / Engine               │      │
│  └──────┬────────────────┬────────────────┬──────┘      │
│         │                │                │              │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐      │
│  │ DataClient  │  │ ExecClient  │  │  Adapter    │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
└─────────┼────────────────┼────────────────┼─────────────┘
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │  WebSocket │    │   REST    │    │   FIX     │
    │   Stream   │    │    API    │    │  Protocol │
    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
          │                │                │
    ┌─────▼────────────────▼────────────────▼─────┐
    │           External Exchange / Venue          │
    └──────────────────────────────────────────────┘
```

### 1.2 适配器类型

| 类型 | 功能 | 接口 |
|------|------|------|
| `DataClient` | 市场数据订阅 | WebSocket/REST |
| `ExecutionClient` | 订单执行 | REST/WebSocket/FIX |
| `DataExecutionClient` | 数据 + 执行 | 组合接口 |

### 1.3 集成状态

| 状态 | 描述 | 建议用途 |
|------|------|---------|
| ✅ 生产 | 完整测试，生产环境可用 | 实盘交易 |
| 🧪 测试 | 基本功能测试中 | 模拟/小额实盘 |
| 📝 开发 | 开发中，功能不完整 | 仅开发测试 |
| ⚠️ 弃用 | 已弃用，将移除 | 迁移到其他适配器 |

### 1.4 通用配置模式

```python
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.adapters.XXX.config import XXXLiveConfig

config = TradingNodeConfig(
    trader_id="TRADER-001",
    
    venues=[
        XXXLiveConfig(
            # 认证凭据
            api_key="your_api_key",
            api_secret="your_api_secret",
            
            # 网络配置
            base_url="https://api.xxx.com",
            ws_url="wss://ws.xxx.com",
            
            # 交易配置
            instrument_ids=["BTCUSDT.XXX"],
            account_type="MARGIN",
            
            # 高级选项
            use_testnet=False,
            timestamp_sync=True,
        ),
    ],
    
    strategies=[...],
)
```

---

## 2. Binance 集成

### 2.1 概述

**状态**: ✅ 生产  
**支持市场**: Spot, USDⓈ-M Futures, COIN-M Futures  
**认证**: API Key + Secret

### 2.2 配置

```python
from nautilus_trader.adapters.binance.config import (
    BinanceLiveConfig,
    BinanceSpotConfig,
    BinanceFuturesConfig,
)
from nautilus_trader.model.enums import AccountType

# Spot 现货配置
spot_config = BinanceSpotConfig(
    api_key="your_spot_api_key",
    api_secret="your_spot_api_secret",
    instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
    account_type=AccountType.CASH,
    use_testnet=False,
)

# Futures 期货配置
futures_config = BinanceFuturesConfig(
    api_key="your_futures_api_key",
    api_secret="your_futures_api_secret",
    instrument_ids=["BTCUSDT-PERP.BINANCE"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
)

# 完整节点配置
from nautilus_trader.config import TradingNodeConfig

config = TradingNodeConfig(
    trader_id="BINANCE-TRADER-001",
    venues=[spot_config, futures_config],
    strategies=[...],
)
```

### 2.3 支持的数据类型

| 数据类型 | Spot | Futures | 订阅方法 |
|---------|------|---------|---------|
| `QuoteTick` | ✅ | ✅ | `subscribe_quote_ticks()` |
| `TradeTick` | ✅ | ✅ | `subscribe_trade_ticks()` |
| `Bar` (K 线) | ✅ | ✅ | `subscribe_bars()` |
| `OrderBookDelta` (L2) | ✅ | ✅ | `subscribe_order_book_deltas()` |
| `OrderBookDepth10` | ✅ | ✅ | `subscribe_order_book_depth()` |
| `Instrument` | ✅ | ✅ | `request_instrument()` |
| `InstrumentStatus` | ✅ | ✅ | 自动推送 |

### 2.4 支持的订单类型

| 订单类型 | Spot | Futures | 说明 |
|---------|------|---------|------|
| `MARKET` | ✅ | ✅ | 市价单 |
| `LIMIT` | ✅ | ✅ | 限价单 |
| `STOP_MARKET` | ✅ | ✅ | 止损市价单 |
| `STOP_LIMIT` | ✅ | ✅ | 止损限价单 |
| `TAKE_PROFIT_MARKET` | ✅ | ✅ | 止盈市价单 |
| `TAKE_PROFIT_LIMIT` | ✅ | ✅ | 止盈限价单 |
| `TRAILING_STOP_MARKET` | ❌ | ✅ | 追踪止损 (仅期货) |

### 2.5 时间有效期 (TimeInForce)

| TIF | Spot | Futures | 说明 |
|-----|------|---------|------|
| `GTC` | ✅ | ✅ | 取消前有效 |
| `IOC` | ✅ | ✅ | 立即成交或取消 |
| `FOK` | ✅ | ✅ | 全部成交或取消 |
| `GTD` | ✅ | ✅ | 指定时间前有效 |
| `POST_ONLY` | ✅ | ✅ | 仅做市 |

### 2.6 特殊功能

**账户模式**:
```python
# Spot 账户模式
# - CASH: 现金账户 (默认)

# Futures 账户模式
# - MARGIN: 保证金账户
# - 支持双向持仓 (Hedging Mode)
# - 支持交叉/逐仓保证金
```

**杠杆配置**:
```python
from nautilus_trader.adapters.binance.http.client import BinanceHttpClient

client = BinanceHttpClient(api_key, api_secret)

# 设置杠杆
await client.set_leverage(
    symbol="BTCUSDT",
    leverage=10,  # 1-125
)

# 更改保证金模式
await client.set_margin_mode(
    symbol="BTCUSDT",
    margin_mode="CROSSED",  # 或 "ISOLATED"
)
```

### 2.7 使用示例

```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

class BinanceEMAStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal

class BinanceEMAStrategy(Strategy):
    def __init__(self, config: BinanceEMAStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
        self.log.info(f"Strategy started for {self.instrument.id}")
    
    def on_bar(self, bar: Bar) -> None:
        # 策略逻辑
        if self.should_buy(bar):
            order = self.order_factory.market(
                instrument_id=self.instrument.id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.config.trade_size),
            )
            self.submit_order(order)
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("Strategy stopped")
```

### 2.8 注意事项

| 项目 | 说明 |
|------|------|
| **API 限流** | Spot: 1200 权重/分钟，Futures: 2400 权重/分钟 |
| **最小订单** | Spot: 通常 10 USDT，Futures: 通常 5 USDT |
| **时间同步** | 建议启用 NTP 时间同步，误差需 < 500ms |
| **测试网络** | 使用 `use_testnet=True` 进行沙箱测试 |
| **API 权限** | 确保 API Key 有交易和读取权限 |

---

## 3. Bybit 集成

### 3.1 概述

**状态**: ✅ 生产  
**支持市场**: Spot, Linear Perpetual, Inverse Perpetual, Options  
**认证**: API Key + Secret

### 3.2 配置

```python
from nautilus_trader.adapters.bybit.config import BybitLiveConfig
from nautilus_trader.model.enums import AccountType

config = BybitLiveConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    instrument_ids=[
        "BTCUSDT.BYBIT",      # Linear Perp
        "ETHUSDT.BYBIT",      # Linear Perp
        "BTCUSD.BYBIT",       # Inverse Perp
    ],
    account_type=AccountType.MARGIN,
    use_testnet=False,
    demo_trading=False,
)
```

### 3.3 支持的数据类型

| 数据类型 | Spot | Linear | Inverse | Options |
|---------|------|--------|---------|---------|
| `QuoteTick` | ✅ | ✅ | ✅ | ✅ |
| `TradeTick` | ✅ | ✅ | ✅ | ✅ |
| `Bar` | ✅ | ✅ | ✅ | ✅ |
| `OrderBookDelta` | ✅ | ✅ | ✅ | ✅ |
| `OrderBookDepth10` | ✅ | ✅ | ✅ | ✅ |
| `OptionGreeks` | ❌ | ❌ | ❌ | ✅ |

### 3.4 支持的订单类型

| 订单类型 | 支持 | 说明 |
|---------|------|------|
| `MARKET` | ✅ | 市价单 |
| `LIMIT` | ✅ | 限价单 |
| `STOP_MARKET` | ✅ | 止损市价单 |
| `STOP_LIMIT` | ✅ | 止损限价单 |
| `TRAILING_STOP` | ✅ | 追踪止损 |
| `TAKE_PROFIT` | ✅ | 止盈单 |

### 3.5 统一交易账户 (UTA)

Bybit 支持统一交易账户，允许跨资产保证金：

```python
from nautilus_trader.adapters.bybit.http.client import BybitHttpClient

client = BybitHttpClient(api_key, api_secret)

# 升级 UTA
await client.upgrade_to_uta()

# 设置持仓模式
await client.set_position_mode(
    category="linear",
    mode="BothSide",  # 或 "MergedSingle"
)
```

### 3.6 期权 Greeks 订阅

```python
from nautilus_trader.core.nautilus_pyo3 import OptionSeriesId, StrikeRange

# 订阅期权链
series_id = OptionSeriesId("BTC-29DEC23-40000-C.BYBIT")
strike_range = StrikeRange.atm_relative(strikes_above=5, strikes_below=5)

self.subscribe_option_chain(
    series_id=series_id,
    strike_range=strike_range,
    snapshot_interval_ms=1000,
)

def on_option_chain(self, chain) -> None:
    for strike in chain.strikes():
        call = chain.get_call(strike)
        if call and call.greeks:
            self.log.info(f"Call Delta: {call.greeks.delta:.4f}")
```

### 3.7 注意事项

| 项目 | 说明 |
|------|------|
| **API 限流** | 120 请求/秒 (现货), 100 请求/秒 (衍生品) |
| **测试网络** | `use_testnet=True` 或 `demo_trading=True` |
| **期权到期** | 期权合约在到期日自动结算 |
| **资金费率** | 永续合约每 8 小时结算一次 |

---

## 4. Interactive Brokers 集成

### 4.1 概述

**状态**: ✅ 生产  
**支持市场**: 股票、ETF、期货、期权、外汇、债券  
**认证**: TWS/Gateway 客户端连接

### 4.2 配置

```python
from nautilus_trader.adapters.interactive_brokers.config import (
    InteractiveBrokersConfig,
    InteractiveBrokersDataConfig,
)

config = InteractiveBrokersConfig(
    # TWS/Gateway 连接
    ibg_host="127.0.0.1",
    ibg_port=7496,  # 7496=TWS, 4001=Gateway
    ibg_client_id=1,
    
    # 账户配置
    account_ids=["DU123456"],  # 模拟账户或真实账户
    
    # 可选配置
    readonly=False,
    deallocation_timeout_secs=300,
)
```

### 4.3 连接要求

**TWS/Gateway 设置**:
```
1. 启用 API 连接
   Settings → API → Settings
   ☑ Enable ActiveX and Socket Clients
   
2. 设置端口
   Socket port: 7496 (TWS) / 4001 (Gateway)
   
3. 设置客户端 ID
   Trusted IPs: 127.0.0.1
   
4. 重启 TWS/Gateway
```

### 4.4 支持的数据类型

| 数据类型 | 支持 | 说明 |
|---------|------|------|
| `QuoteTick` | ✅ | 报价数据 |
| `TradeTick` | ✅ | 成交数据 |
| `Bar` | ✅ | K 线数据 |
| `OrderBookDelta` | ❌ | IB 不提供完整订单簿 |
| `Instrument` | ✅ | 合约定义 |

### 4.5 支持的订单类型

| 订单类型 | 支持 | IB 订单类型 |
|---------|------|------------|
| `MARKET` | ✅ | MKT |
| `LIMIT` | ✅ | LMT |
| `STOP_MARKET` | ✅ | STP |
| `STOP_LIMIT` | ✅ | STP LMT |
| `LIMIT_IF_TOUCHED` | ✅ | LIT |
| `MARKET_IF_TOUCHED` | ✅ | MIT |
| `TRAILING_STOP` | ✅ | TRAIL |

### 4.6 合约规格

```python
from nautilus_trader.adapters.interactive_brokers.parsing.contract import (
    make_ib_contract,
)

# 股票
contract = make_ib_contract(
    symbol="AAPL",
    sec_type="STK",
    exchange="SMART",
    currency="USD",
)

# 期货
contract = make_ib_contract(
    symbol="ES",
    sec_type="FUT",
    exchange="GLOBEX",
    currency="USD",
    expiry="202409",
)

# 期权
contract = make_ib_contract(
    symbol="AAPL",
    sec_type="OPT",
    exchange="SMART",
    currency="USD",
    expiry="20240920",
    strike=175.0,
    right="C",  # C=Call, P=Put
)

# 外汇
contract = make_ib_contract(
    symbol="EUR",
    sec_type="CASH",
    exchange="IDEALPRO",
    currency="USD",
)
```

### 4.7 使用示例

```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.data import Bar

class IBStrategy(Strategy):
    def on_start(self) -> None:
        # 请求合约定义
        self.request_instrument(
            instrument_id=InstrumentId.from_str("AAPL.NASDAQ"),
        )
        
        # 订阅实时数据
        self.subscribe_quote_ticks(
            instrument_id=InstrumentId.from_str("AAPL.NASDAQ"),
        )
        
        # 订阅 K 线
        self.subscribe_bars(
            bar_type=BarType.from_str("AAPL.NASDAQ-1-MINUTE-LAST-EXTERNAL"),
        )
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        self.log.info(f"Bid: {tick.bid_price}, Ask: {tick.ask_price}")
    
    def on_bar(self, bar: Bar) -> None:
        # 策略逻辑
        pass
```

### 4.8 注意事项

| 项目 | 说明 |
|------|------|
| **TWS 版本** | 需要 TWS 976+ 或 IB Gateway |
| **市场数据** | 需要订阅相应的市场数据套餐 |
| **交易时间** | 遵循交易所交易时间 |
| **账户类型** | 支持现金和保证金账户 |
| **连接稳定性** | 建议配置自动重连 |

---

## 5. Databento 集成

### 5.1 概述

**状态**: ✅ 生产  
**类型**: 数据提供商 (仅数据，无执行)  
**认证**: API Key

### 5.2 配置

```python
from nautilus_trader.adapters.databento.config import DatabentoDataConfig

config = DatabentoDataConfig(
    api_key="your_databento_api_key",
    
    # 数据订阅
    instrument_ids=["ESU4.GLBX", "NQ U4.GLBX"],
    
    # 数据类型
    schema="ohlcv-1m",  # 或其他 schema
    
    # 可选配置
    use_gzip=True,
    buffer_size=1000,
)
```

### 5.3 支持的 Schema

| Schema | 描述 | 数据类型 |
|--------|------|---------|
| `ohlcv-1m` | 1 分钟 K 线 | `Bar` |
| `ohlcv-1s` | 1 秒 K 线 | `Bar` |
| `trades` | 成交数据 | `TradeTick` |
| `quotes` | 报价数据 | `QuoteTick` |
| `mbp-1` | 最优买卖价 | `QuoteTick` |
| `mbp-10` | 10 档深度 | `OrderBookDepth10` |
| `mbo` | 逐笔订单簿 | `OrderBookDelta` |

### 5.4 历史数据加载

```python
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader

loader = DatabentoDataLoader(api_key="your_api_key")

# 加载历史 K 线
bars = loader.load_bars(
    instrument_ids=["ESU4.GLBX"],
    schema="ohlcv-1m",
    start="2024-01-01",
    end="2024-12-31",
)

# 加载历史成交
trades = loader.load_trade_ticks(
    instrument_ids=["ESU4.GLBX"],
    start="2024-01-01",
    end="2024-01-31",
)

# 加载历史订单簿
deltas = loader.load_order_book_deltas(
    instrument_ids=["ESU4.GLBX"],
    schema="mbo",
    start="2024-01-01",
    end="2024-01-02",
)
```

### 5.5 实时数据订阅

```python
from nautilus_trader.trading.strategy import Strategy

class DatabentoStrategy(Strategy):
    def on_start(self) -> None:
        # 订阅实时数据
        self.subscribe_bars(
            bar_type=BarType.from_str("ESU4.GLBX-1-MINUTE-OHLCV-EXTERNAL"),
        )
        
        self.subscribe_trade_ticks(
            instrument_id=InstrumentId.from_str("ESU4.GLBX"),
        )
    
    def on_bar(self, bar: Bar) -> None:
        # 处理 K 线
        pass
    
    def on_trade_tick(self, tick: TradeTick) -> None:
        # 处理成交
        pass
```

### 5.6 成本优化

```python
# 使用压缩减少带宽
config = DatabentoDataConfig(
    api_key="your_api_key",
    use_gzip=True,  # 启用 gzip 压缩
)

# 批量订阅减少请求
instrument_ids = ["ESU4.GLBX", "NQU4.GLBX", "YM U4.GLBX"]
config = DatabentoDataConfig(
    api_key="your_api_key",
    instrument_ids=instrument_ids,
)

# 使用本地缓存
from nautilus_trader.persistence.catalog import ParquetDataCatalog

catalog = ParquetDataCatalog("./catalog")
# 先查询本地，再请求远程
data = catalog.bars(...)
if not data:
    data = loader.load_bars(...)
    catalog.write_bars(data)
```

### 5.7 注意事项

| 项目 | 说明 |
|------|------|
| **API 费用** | 按数据使用量计费 |
| **延迟** | 实时数据延迟 < 100ms |
| **历史深度** | 提供多年历史数据 |
| **数据质量** | 交易所直连，高质量数据 |

---

## 6. Betfair 集成

### 6.1 概述

**状态**: ✅ 生产  
**类型**: 博彩交易所  
**认证**: App Key + Session Token

### 6.2 配置

```python
from nautilus_trader.adapters.betfair.config import BetfairLiveConfig

config = BetfairLiveConfig(
    username="your_username",
    password="your_password",
    app_key="your_app_key",
    cert_dir="/path/to/certs",  # SSL 证书目录
    
    # 市场过滤
    market_filter={
        "sport": "horse_racing",
        "country_codes": ["GB"],
    },
    
    # 可选配置
    account_type=AccountType.BETTING,
)
```

### 6.3 支持的数据类型

| 数据类型 | 支持 | 说明 |
|---------|------|------|
| `QuoteTick` | ✅ | 买卖价格 |
| `TradeTick` | ✅ | 成交数据 |
| `Instrument` | ✅ | 市场定义 |
| `InstrumentStatus` | ✅ | 市场状态 |

### 6.4 支持的订单类型

| 订单类型 | 支持 | 说明 |
|---------|------|------|
| `LIMIT` | ✅ | 限价单 |
| `LIMIT_ON_CLOSE` | ✅ | 收盘限价 |
| `MARKET_ON_CLOSE` | ✅ | 收盘市价 |

### 6.5 市场订阅

```python
from nautilus_trader.trading.strategy import Strategy

class BetfairStrategy(Strategy):
    def on_start(self) -> None:
        # 订阅市场数据
        self.subscribe_quote_ticks(
            instrument_id=InstrumentId.from_str("1.234567.BETFAIR"),
        )
        
        # 请求市场定义
        self.request_instrument(
            instrument_id=InstrumentId.from_str("1.234567.BETFAIR"),
        )
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        # Betfair 报价
        # bid_price = 背投价格 (LAY)
        # ask_price = 支持价格 (BACK)
        self.log.info(f"BACK: {tick.ask_price}, LAY: {tick.bid_price}")
```

### 6.6 二元市场特殊处理

Betfair 市场是二元市场 (YES/NO 价格和为 1.0):

```python
# 获取对立市场
yes_instrument = self.cache.instrument(InstrumentId.from_str("1.234567.BETFAIR"))
no_instrument = self.cache.instrument(InstrumentId.from_str("1.234568.BETFAIR"))

# 计算隐含概率
yes_prob = 1.0 / float(yes_instrument.ask_price)
no_prob = 1.0 / float(no_instrument.ask_price)
overround = yes_prob + no_prob  # 通常 > 1.0
```

### 6.7 注意事项

| 项目 | 说明 |
|------|------|
| **证书** | 需要 SSL 证书进行 API 认证 |
| **佣金** | 赢取金额收取佣金 (通常 2-5%) |
| **市场状态** | 市场可能暂停或关闭 |
| **最小投注** | 通常 £2 最小投注 |

---

## 7. OKX 集成

### 7.1 概述

**状态**: 🧪 测试  
**支持市场**: Spot, Futures, Perpetual, Options  
**认证**: API Key + Secret + Passphrase

### 7.2 配置

```python
from nautilus_trader.adapters.okx.config import OKXLiveConfig

config = OKXLiveConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    passphrase="your_passphrase",  # OKX 特有
    
    instrument_ids=["BTC-USDT.OKX"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
)
```

### 7.3 支持的数据类型

| 数据类型 | Spot | Futures | Perpetual | Options |
|---------|------|---------|-----------|---------|
| `QuoteTick` | ✅ | ✅ | ✅ | ✅ |
| `TradeTick` | ✅ | ✅ | ✅ | ✅ |
| `Bar` | ✅ | ✅ | ✅ | ✅ |
| `OrderBookDelta` | ✅ | ✅ | ✅ | ✅ |
| `OptionGreeks` | ❌ | ❌ | ❌ | 🟡 |

### 7.4 支持的订单类型

| 订单类型 | 支持 | 说明 |
|---------|------|------|
| `MARKET` | ✅ | 市价单 |
| `LIMIT` | ✅ | 限价单 |
| `STOP_MARKET` | ✅ | 止损市价单 |
| `STOP_LIMIT` | ✅ | 止损限价单 |
| `TRAILING_STOP` | 🟡 | 部分支持 |

### 7.5 注意事项

| 项目 | 说明 |
|------|------|
| **Passphrase** | OKX 需要额外的 passphrase 参数 |
| **API 限流** | 20 请求/2 秒 (普通), 60 请求/2 秒 (VIP) |
| **测试网络** | `use_testnet=True` 使用模拟交易 |
| **状态** | 测试中，生产使用需谨慎 |

---

## 8. Kraken 集成

### 8.1 概述

**状态**: 🧪 测试  
**支持市场**: Spot, Futures  
**认证**: API Key + Secret

### 8.2 配置

```python
from nautilus_trader.adapters.kraken.config import KrakenLiveConfig

config = KrakenLiveConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    
    instrument_ids=["XBT/USD.KRAKEN"],
    account_type=AccountType.CASH,
    use_testnet=False,
)
```

### 8.3 支持的数据类型

| 数据类型 | Spot | Futures |
|---------|------|---------|
| `QuoteTick` | ✅ | ✅ |
| `TradeTick` | ✅ | ✅ |
| `Bar` | ✅ | ✅ |
| `OrderBookDelta` | ✅ | 🟡 |

### 8.4 注意事项

| 项目 | 说明 |
|------|------|
| **API 限流** | 15 请求/秒 (普通), 更高需 VIP |
| **符号格式** | 使用 XBT 而非 BTC |
| **状态** | 测试中，功能可能不完整 |

---

## 9. BitMEX 集成

### 9.1 概述

**状态**: 🧪 测试  
**支持市场**: Perpetual, Futures, Options  
**认证**: API Key + Secret

### 9.2 配置

```python
from nautilus_trader.adapters.bitmex.config import BitmexLiveConfig

config = BitmexLiveConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    
    instrument_ids=["XBTUSD.BITMEX"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
)
```

### 9.3 特殊功能

**反向合约**:
- BitMEX 使用反向合约 (以 BTC 计价)
- PnL 计算与正向合约不同

**保险基金**:
- 强平损失进入保险基金
- 保险基金不足时可能社会化为负收益

### 9.4 注意事项

| 项目 | 说明 |
|------|------|
| **反向合约** | PnL = 合约数 × (1/入场价 - 1/出场价) |
| **强平机制** | 保险基金 + 社会化管理 |
| **状态** | 测试中 |

---

## 10. dYdX 集成

### 10.1 概述

**状态**: 🧪 测试  
**类型**: 去中心化交易所 (DEX)  
**认证**: Ethereum 钱包签名

### 10.2 配置

```python
from nautilus_trader.adapters.dydx.config import DydxLiveConfig

config = DydxLiveConfig(
    wallet_address="0x...",
    private_key="your_private_key",  # 安全存储!
    
    instrument_ids=["ETH-USD.DYDX"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
)
```

### 10.3 特殊功能

**链上结算**:
- 订单在链上结算
- 需要支付 Gas 费用

**非托管**:
- 资金保留在用户钱包
- 无需 KYC (某些司法管辖区)

### 10.4 注意事项

| 项目 | 说明 |
|------|------|
| **Gas 费用** | 每笔交易需支付 Gas |
| **延迟** | 链上确认需要时间 |
| **状态** | 测试中 |

---

## 11. Hyperliquid 集成

### 11.1 概述

**状态**: 🧪 测试  
**类型**: 去中心化永续合约交易所  
**认证**: Ethereum 钱包签名

### 11.2 配置

```python
from nautilus_trader.adapters.hyperliquid.config import HyperliquidLiveConfig

config = HyperliquidLiveConfig(
    wallet_address="0x...",
    private_key="your_private_key",
    
    instrument_ids=["BTC-USD.HYPERLIQUID"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
)
```

### 11.3 注意事项

| 项目 | 说明 |
|------|------|
| **L1 区块链** | Hyperliquid 自有 L1 |
| **Gas 费用** | 极低或无 Gas 费用 |
| **状态** | 测试中 |

---

## 12. Polymarket 集成

### 12.1 概述

**状态**: 🧪 测试  
**类型**: 去中心化预测市场  
**认证**: Ethereum 钱包签名

### 12.2 配置

```python
from nautilus_trader.adapters.polymarket.config import PolymarketLiveConfig

config = PolymarketLiveConfig(
    wallet_address="0x...",
    private_key="your_private_key",
    
    # 市场过滤
    market_filter={
        "category": "politics",
    },
)
```

### 12.3 二元市场处理

```python
# Polymarket 是二元市场 (YES/NO)
# YES 价格 + NO 价格 ≈ 1.00

# 获取对立市场
yes_market = self.cache.instrument(InstrumentId.from_str("0x123.POLYMARKET"))
no_market = self.cache.instrument(InstrumentId.from_str("0x124.POLYMARKET"))

# 计算隐含概率
yes_prob = float(yes_market.ask_price)
no_prob = float(no_market.ask_price)
```

### 12.4 注意事项

| 项目 | 说明 |
|------|------|
| **二元市场** | 结果只有 YES 或 NO |
| **结算** | 事件结束后自动结算 |
| **状态** | 测试中 |

---

## 13. 区块链适配器

### 13.1 概述

通用区块链适配器支持连接各种区块链网络。

### 13.2 配置

```python
from nautilus_trader.adapters.blockchain.config import BlockchainAdapterConfig

config = BlockchainAdapterConfig(
    network="ethereum",  # 或 polygon, arbitrum, etc.
    rpc_url="https://mainnet.infura.io/v3/your_key",
    wallet_address="0x...",
    private_key="your_private_key",
)
```

### 13.3 支持的链

| 链 | 支持 | 说明 |
|----|------|------|
| Ethereum | ✅ | 主网 + 测试网 |
| Polygon | ✅ | Layer 2 |
| Arbitrum | ✅ | Layer 2 |
| Optimism | ✅ | Layer 2 |
| BSC | 🟡 | Binance Smart Chain |

### 13.4 智能合约交互

```python
from nautilus_trader.adapters.blockchain.client import BlockchainClient

client = BlockchainClient(config)

# 调用合约
result = await client.call_contract(
    contract_address="0x...",
    function="balanceOf",
    args=[wallet_address],
)

# 发送交易
tx_hash = await client.send_transaction(
    to="0x...",
    value=Decimal("1.0"),
    data=contract_call_data,
)
```

---

## 14. 沙箱适配器

### 14.1 概述

沙箱适配器用于策略测试，无需真实资金。

### 14.2 配置

```python
from nautilus_trader.adapters.sandbox.config import SandboxLiveConfig
from nautilus_trader.adapters.sandbox.fill_model import FillModel

config = SandboxLiveConfig(
    instrument_ids=["BTCUSDT.SANDBOX"],
    account_type=AccountType.MARGIN,
    starting_balances=[Money(1_000_000, "USDT")],
    
    # 填充模型配置
    fill_model=FillModel(
        prob_fill_on_limit=0.2,    # 限价单成交概率
        prob_fill_on_stop=0.9,     # 止损单成交概率
        prob_slippage=0.1,         # 滑点概率
        slippage_range=(0.0001, 0.001),  # 滑点范围
    ),
    
    # 延迟模拟
    latency_model={
        "mean_ms": 50,
        "std_ms": 10,
    },
)
```

### 14.3 使用场景

| 场景 | 说明 |
|------|------|
| **策略验证** | 在实盘前验证策略逻辑 |
| **压力测试** | 测试极端市场条件 |
| **延迟测试** | 模拟网络延迟影响 |
| **教学演示** | 无需真实资金的教学环境 |

### 14.4 注意事项

| 项目 | 说明 |
|------|------|
| **数据源** | 使用真实市场数据 |
| **执行** | 虚拟执行，不实际下单 |
| **配置** | 可调整成交概率和滑点 |

---

## 15. 通用数据适配器

### 15.1 概述

通用数据适配器支持从各种数据源加载历史数据。

### 15.2 CSV 数据加载

```python
from nautilus_trader.adapters.generic.data import CSVDataLoader

loader = CSVDataLoader(
    data_dir="./data",
    timestamp_column="timestamp",
    price_column="price",
    volume_column="volume",
)

# 加载数据
bars = loader.load_bars(
    instrument_id=InstrumentId.from_str("BTCUSDT.CUSTOM"),
    bar_type=BarType.from_str("BTCUSDT.CUSTOM-1-MINUTE"),
)
```

### 15.3 自定义数据源

```python
from nautilus_trader.live.data_client import DataClient
from nautilus_trader.model.data import QuoteTick

class CustomDataClient(DataClient):
    def __init__(self, config: CustomDataConfig):
        super().__init__(config)
        self.data_source = config.data_source
    
    async def connect(self) -> None:
        # 建立数据源连接
        pass
    
    async def subscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        # 订阅报价
        async for tick in self.data_source.stream(instrument_id):
            self._handle_quote_tick(tick)
    
    def _handle_quote_tick(self, tick: QuoteTick) -> None:
        # 处理并发送 tick
        self._send_data(tick)
```

---

## 16. 适配器开发指南

### 16.1 适配器结构

```
adapters/
└── my_exchange/
    ├── __init__.py
    ├── config.py          # 配置类
    ├── data_client.py     # 数据客户端
    ├── execution_client.py # 执行客户端
    ├── http_client.py     # HTTP 客户端
    ├── websocket_client.py # WebSocket 客户端
    ├── parsing/           # 数据解析
    │   ├── instruments.py
    │   └── orders.py
    └── tests/             # 测试
```

### 16.2 配置类

```python
from nautilus_trader.live.config import LiveConfig
from pydantic import Field

class MyExchangeConfig(LiveConfig):
    """MyExchange 适配器配置"""
    
    api_key: str = Field(..., description="API 密钥")
    api_secret: str = Field(..., description="API 密钥")
    base_url: str = Field(default="https://api.myexchange.com")
    ws_url: str = Field(default="wss://ws.myexchange.com")
    instrument_ids: list[InstrumentId] = Field(default_factory=list)
    use_testnet: bool = Field(default=False)
```

### 16.3 数据客户端

```python
from nautilus_trader.live.data_client import DataClient
from nautilus_trader.model.data import QuoteTick, TradeTick

class MyExchangeDataClient(DataClient):
    def __init__(self, config: MyExchangeConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.ws = None
    
    async def connect(self) -> None:
        """建立 WebSocket 连接"""
        self.ws = await websockets.connect(self.config.ws_url)
        await self._authenticate()
        self._log.info("Connected")
    
    async def disconnect(self) -> None:
        """断开连接"""
        if self.ws:
            await self.ws.close()
        self._log.info("Disconnected")
    
    async def subscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        """订阅报价"""
        symbol = self._instrument_id_to_symbol(instrument_id)
        await self.ws.send(json.dumps({
            "op": "subscribe",
            "channel": "quote",
            "symbol": symbol,
        }))
    
    async def _message_handler(self, message: str) -> None:
        """处理 WebSocket 消息"""
        data = json.loads(message)
        
        if data.get("channel") == "quote":
            tick = self._parse_quote_tick(data)
            self._send_data(tick)
    
    def _parse_quote_tick(self, data: dict) -> QuoteTick:
        """解析报价 Tick"""
        return QuoteTick(
            instrument_id=self._symbol_to_instrument_id(data["symbol"]),
            bid_price=Price.from_str(data["bid"]),
            ask_price=Price.from_str(data["ask"]),
            bid_size=Quantity.from_str(data["bid_size"]),
            ask_size=Quantity.from_str(data["ask_size"]),
            ts_event=dt_to_unix_nanos(parse_iso8601(data["timestamp"])),
            ts_init=self._clock.timestamp_ns(),
        )
```

### 16.4 执行客户端

```python
from nautilus_trader.live.execution_client import ExecutionClient
from nautilus_trader.model.order import Order
from nautilus_trader.model.event import OrderFilled

class MyExchangeExecutionClient(ExecutionClient):
    def __init__(self, config: MyExchangeConfig):
        super().__init__(config)
        self.http = MyExchangeHttpClient(config)
    
    async def connect(self) -> None:
        """建立连接"""
        await self.http.connect()
        self._log.info("Connected")
    
    async def disconnect(self) -> None:
        """断开连接"""
        await self.http.disconnect()
        self._log.info("Disconnected")
    
    async def submit_order(self, order: Order) -> None:
        """提交订单"""
        try:
            response = await self.http.submit_order(
                symbol=self._instrument_id_to_symbol(order.instrument_id),
                side=order.side,
                quantity=str(order.quantity),
                price=str(order.price) if order.price else None,
                order_type=self._order_type_to_string(order.order_type),
            )
            
            # 发送 Accepted 事件
            self._handle_order_accepted(order, response)
            
        except Exception as e:
            # 发送 Rejected 事件
            self._handle_order_rejected(order, str(e))
    
    async def cancel_order(self, order: Order) -> None:
        """取消订单"""
        response = await self.http.cancel_order(
            order_id=order.client_order_id.value,
        )
        self._handle_order_canceled(order, response)
    
    async def modify_order(
        self,
        order: Order,
        quantity: Quantity | None = None,
        price: Price | None = None,
    ) -> None:
        """修改订单"""
        response = await self.http.modify_order(
            order_id=order.client_order_id.value,
            quantity=str(quantity) if quantity else None,
            price=str(price) if price else None,
        )
        self._handle_order_updated(order, response)
```

### 16.5 工具解析

```python
from nautilus_trader.model.instruments import CurrencyPair

def parse_instrument(data: dict) -> CurrencyPair:
    """解析交易所工具定义"""
    return CurrencyPair(
        instrument_id=InstrumentId.from_str(f"{data['symbol']}.MYEXCHANGE"),
        symbol=Symbol(data["symbol"]),
        base_currency=Currency.from_str(data["base_asset"]),
        quote_currency=Currency.from_str(data["quote_asset"]),
        settlement_currency=Currency.from_str(data["settle_asset"]),
        price_precision=data["price_precision"],
        size_precision=data["size_precision"],
        price_increment=Price.from_str(data["tick_size"]),
        size_increment=Quantity.from_str(data["step_size"]),
        multiplier=Quantity.from_int(1),
        lot_size=Quantity.from_str(data["min_qty"]),
        max_quantity=Quantity.from_str(data["max_qty"]),
        min_quantity=Quantity.from_str(data["min_qty"]),
        max_notional=Money(data["max_notional"], data["quote_asset"]),
        min_notional=Money(data["min_notional"], data["quote_asset"]),
        ts_event=0,
        ts_init=0,
    )
```

### 16.6 测试

```python
import pytest
from nautilus_trader.adapters.my_exchange.data_client import MyExchangeDataClient

@pytest.fixture
def config():
    return MyExchangeConfig(
        api_key="test_key",
        api_secret="test_secret",
    )

@pytest.fixture
def data_client(config):
    return MyExchangeDataClient(config)

@pytest.mark.asyncio
async def test_connect(data_client):
    await data_client.connect()
    assert data_client.is_connected

@pytest.mark.asyncio
async def test_subscribe(data_client):
    await data_client.connect()
    await data_client.subscribe_quote_ticks(
        InstrumentId.from_str("BTCUSDT.MYEXCHANGE"),
    )
    # 验证订阅成功
```

### 16.7 注册适配器

```python
# adapters/__init__.py
from nautilus_trader.adapters.my_exchange.config import MyExchangeConfig
from nautilus_trader.adapters.my_exchange.data_client import MyExchangeDataClient
from nautilus_trader.adapters.my_exchange.execution_client import MyExchangeExecutionClient

__all__ = [
    "MyExchangeConfig",
    "MyExchangeDataClient",
    "MyExchangeExecutionClient",
]

# 在节点配置中使用
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.adapters.my_exchange import MyExchangeConfig

config = TradingNodeConfig(
    trader_id="TRADER-001",
    venues=[
        MyExchangeConfig(
            api_key="...",
            api_secret="...",
            instrument_ids=["BTCUSDT.MYEXCHANGE"],
        ),
    ],
    strategies=[...],
)
```

---

## 附录 A: 集成状态总览

| 交易所/数据源 | 数据 | 执行 | 状态 | 文档 |
|--------------|------|------|------|------|
| Binance | ✅ | ✅ | 生产 | [链接](#2-binance-集成) |
| Bybit | ✅ | ✅ | 生产 | [链接](#3-bybit 集成) |
| Interactive Brokers | ✅ | ✅ | 生产 | [链接](#4-interactive-brokers 集成) |
| Databento | ✅ | ❌ | 生产 | [链接](#5-databento 集成) |
| Betfair | ✅ | ✅ | 生产 | [链接](#6-betfair 集成) |
| OKX | ✅ | ✅ | 测试 | [链接](#7-okx 集成) |
| Kraken | ✅ | ✅ | 测试 | [链接](#8-kraken 集成) |
| BitMEX | ✅ | ✅ | 测试 | [链接](#9-bitmex 集成) |
| dYdX | ✅ | ✅ | 测试 | [链接](#10-dydx 集成) |
| Hyperliquid | ✅ | ✅ | 测试 | [链接](#11-hyperliquid 集成) |
| Polymarket | ✅ | ✅ | 测试 | [链接](#12-polymarket 集成) |
| Sandbox | ✅ | ✅ (虚拟) | 生产 | [链接](#14-沙箱适配器) |

---

## 附录 B: 认证方式对比

| 交易所 | 认证方式 | 特殊要求 |
|--------|---------|---------|
| Binance | API Key + Secret | IP 白名单推荐 |
| Bybit | API Key + Secret | - |
| Interactive Brokers | TWS/Gateway 连接 | 需运行 TWS |
| Databento | API Key | - |
| Betfair | App Key + Session + Certs | SSL 证书 |
| OKX | API Key + Secret + Passphrase | Passphrase 必填 |
| Kraken | API Key + Secret | - |
| dYdX | Wallet Signature | Ethereum 钱包 |
| Hyperliquid | Wallet Signature | Ethereum 钱包 |
| Polymarket | Wallet Signature | Ethereum 钱包 |

---

## 附录 C: 资源链接

| 资源 | 链接 |
|------|------|
| 官方文档 | https://nautilustrader.io/docs/ |
| Integrations 文档 | https://nautilustrader.io/docs/nightly/integrations/ |
| GitHub | https://github.com/nautechsystems/nautilus_trader |
| 适配器示例 | https://github.com/nautechsystems/nautilus_trader/tree/develop/nautilus_trader/adapters |
| 社区讨论 | https://github.com/nautechsystems/nautilus_trader/discussions |

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-03-31  
> **维护者**: Nautilus Trader 社区

---

此 Markdown 文件包含完整的 Integrations 目录内容汇总，可直接用于 AI 工具编程参考。如需进一步细化某个交易所的集成细节，请告知！