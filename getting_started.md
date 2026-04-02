# Nautilus Trader Getting Started 入门指南汇总

> **文档版本**: develop 分支 (2026 年 3 月)  
> **适用对象**: 量化交易新手、策略研究员、开发者  
> **用途**: AI 工具编程参考文档

---

## 目录

1. [概述 (Overview)](#1-概述-overview)
2. [系统要求 (System Requirements)](#2-系统要求-system-requirements)
3. [安装指南 (Installation Guide)](#3-安装指南-installation-guide)
4. [快速入门 (Quick Start)](#4-快速入门-quick-start)
5. [第一个策略 (First Strategy)](#5-第一个策略-first-strategy)
6. [第一次回测 (First Backtest)](#6-第一次回测-first-backtest)
7. [配置说明 (Configuration)](#7-配置说明-configuration)
8. [数据准备 (Data Preparation)](#8-数据准备-data-preparation)
9. [实盘准备 (Live Trading Preparation)](#9-实盘准备-live-trading-preparation)
10. [常见问题 (FAQ)](#10-常见问题-faq)
11. [下一步学习 (Next Steps)](#11-下一步学习-next-steps)

---

## 1. 概述 (Overview)

### 1.1 Nautilus Trader 简介

**Nautilus Trader** 是一个开源、生产级、多资产、多交易所的量化交易系统。

**核心特性**:
| 特性 | 描述 |
|------|------|
| ⚡ 高性能 | Rust 核心引擎 + Tokio 异步网络，纳秒级时间精度 |
| 🔒 高可靠 | Rust 类型/线程安全，可选 Redis 状态持久化 |
| 🌐 跨平台 | Linux/macOS/Windows 支持，Docker 部署 |
| 🔌 模块化 | 适配器架构，可集成任何 REST API 或 WebSocket 数据源 |
| 🧪 回测/实盘一致 | 同一套策略代码可直接从研究部署到生产 |
| 🤖 AI 友好 | 足够快的引擎支持强化学习/进化策略训练 |

### 1.2 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    Nautilus Trader                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐      │
│  │  Strategy   │  │   Cache     │  │  Portfolio  │      │
│  │  (Python)   │  │   (Rust)    │  │   (Rust)    │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
│         │                │                │              │
│  ┌──────▼────────────────▼────────────────▼──────┐      │
│  │           MessageBus / Engine (Rust)           │      │
│  └──────┬────────────────┬────────────────┬──────┘      │
│         │                │                │              │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐      │
│  │ DataClient  │  │ ExecClient  │  │  Adapter    │      │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘      │
└─────────┼────────────────┼────────────────┼─────────────┘
          │                │                │
    ┌─────▼─────┐    ┌─────▼─────┐    ┌─────▼─────┐
    │  WebSocket │    │   REST    │    │   FIX     │
    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
          │                │                │
    ┌─────▼────────────────▼────────────────▼─────┐
    │           External Exchange / Venue          │
    └──────────────────────────────────────────────┘
```

### 1.3 使用场景

| 场景 | 描述 | 组件 |
|------|------|------|
| **Backtest** | 历史数据回测 | `BacktestEngine` / `BacktestNode` |
| **Sandbox** | 实时数据 + 虚拟执行 | `SandboxAdapter` |
| **Live** | 实盘/模拟账户交易 | `TradingNode` |

### 1.4 学习路径

```
入门 → 安装 → 快速入门 → 第一个策略 → 回测 → 实盘
  ↓
概念学习 → 数据管理 → 风险管理 → 性能优化
  ↓
高级主题 → 自定义适配器 → 系统集成 → 生产部署
```

---

## 2. 系统要求 (System Requirements)

### 2.1 硬件要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核心 | 8+ 核心 |
| 内存 | 8 GB | 16+ GB |
| 存储 | 50 GB SSD | 500 GB+ NVMe SSD |
| 网络 | 10 Mbps | 100 Mbps+ |

### 2.2 软件要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.12 | 3.13 |
| Rust | 1.75 | 1.80+ |
| Git | 2.30 | 2.40+ |
| Docker | 20.10 | 24.0+ |

### 2.3 操作系统支持

| 操作系统 | 版本 | 支持状态 |
|---------|------|---------|
| Ubuntu | 22.04+ | ✅ 完全支持 |
| Debian | 11+ | ✅ 完全支持 |
| macOS | 15.0+ (ARM64) | ✅ 完全支持 |
| Windows | Server 2022+ | ⚠️ 仅 64 位标准精度 |

### 2.4 精度模式说明

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

> ⚠️ **注意**: Windows 平台仅提供 64 位标准精度版本（因 MSVC 不支持 `__int128`）

---

## 3. 安装指南 (Installation Guide)

### 3.1 使用 pip 安装 (推荐)

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# 安装 nautilus_trader
pip install nautilus_trader

# 带可选依赖安装
pip install "nautilus_trader[docker,ib]"

# 验证安装
python -c "import nautilus_trader; print(nautilus_trader.__version__)"
```

### 3.2 使用 uv 安装 (最快)

```bash
# 安装 uv 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建项目并安装
uv init my_trading_project
cd my_trading_project
uv add nautilus_trader

# 验证安装
uv run python -c "import nautilus_trader; print(nautilus_trader.__version__)"
```

### 3.3 从源码构建

```bash
# 克隆仓库
git clone --branch develop --depth 1 https://github.com/nautechsystems/nautilus_trader.git
cd nautilus_trader

# 安装依赖
uv sync --all-extras

# 或传统方式
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev]"

# 验证构建
python -c "import nautilus_trader; print('Build successful!')"
```

### 3.4 Docker 安装

```bash
# 拉取镜像
docker pull ghcr.io/nautechsystems/jupyterlab:nightly

# 运行容器
docker run -it --rm \
    -p 8888:8888 \
    -v $(pwd):/home/jovyan/work \
    ghcr.io/nautechsystems/jupyterlab:nightly

# 访问 JupyterLab
# http://localhost:8888/?token=<token>
```

### 3.5 安装验证

```python
# test_installation.py
import nautilus_trader
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.trading.strategy import Strategy

print(f"Nautilus Trader version: {nautilus_trader.__version__}")
print("Installation successful!")

# 测试核心组件
engine = BacktestEngine()
print("BacktestEngine created successfully!")

# 测试策略基类
class TestStrategy(Strategy):
    pass

print("Strategy class imported successfully!")
```

运行测试:
```bash
python test_installation.py
```

### 3.6 安装问题排查

| 问题 | 解决方案 |
|------|---------|
| Rust 编译失败 | `rustup update`, `cargo clean` |
| Python 版本不兼容 | 使用 Python 3.12-3.13 |
| OpenSSL 链接错误 | 设置 `OPENSSL_DIR` 环境变量 |
| macOS 架构错误 | 确认使用 ARM64 Python 和 Rust |
| Windows MSVC 错误 | 安装 Visual Studio Build Tools |

---

## 4. 快速入门 (Quick Start)

### 4.1 5 分钟快速回测

**步骤 1: 创建策略文件**

```python
# strategies/ema_cross.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.indicators import EMA

class EMACrossConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    trade_size: Decimal

class EMACross(Strategy):
    def __init__(self, config: EMACrossConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.fast_ema = None
        self.slow_ema = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.fast_ema = EMA(self.config.fast_ema_period)
        self.slow_ema = EMA(self.config.slow_ema_period)
        self.subscribe_bars(self.config.bar_type)
    
    def on_bar(self, bar: Bar) -> None:
        self.fast_ema.handle_bar(bar)
        self.slow_ema.handle_bar(bar)
        
        if self.fast_ema.value > self.slow_ema.value:
            self.buy()
        elif self.fast_ema.value < self.slow_ema.value:
            self.sell()
    
    def buy(self) -> None:
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
        )
        self.submit_order(order)
    
    def sell(self) -> None:
        self.cancel_all_orders()
```

**步骤 2: 创建回测脚本**

```python
# backtests/run_backtest.py
from decimal import Decimal
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import (
    BacktestRunConfig,
    BacktestEngineConfig,
    BacktestVenueConfig,
)
from nautilus_trader.config import CacheConfig, LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model import Money
from strategies.ema_cross import EMACross, EMACrossConfig

def run_backtest():
    config = BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            run_analysis=True,
            cache=CacheConfig(tick_capacity=10_000),
            logging=LoggingConfig(log_level="INFO"),
        ),
        venues=[
            BacktestVenueConfig(
                name="BINANCE",
                oms_type=OmsType.NETTING,
                account_type=AccountType.MARGIN,
                base_currency="USDT",
                starting_balances=[Money(1_000_000, "USDT")],
                maker_fee=0.0002,
                taker_fee=0.0005,
            ),
        ],
        data=[
            DataConfig(
                catalog_path="./catalog",
                instrument_id="BTCUSDT.BINANCE",
                bar_type="1-HOUR",
                start_time="2024-01-01",
                end_time="2024-12-31",
            ),
        ],
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
    
    node = BacktestNode(configs=[config])
    results = node.run()
    
    for result in results:
        perf = result.performance
        print(f"\n{'='*50}")
        print(f"Strategy: {result.strategy_id}")
        print(f"{'='*50}")
        print(f"Total Return: {perf.total_return:.2%}")
        print(f"Sharpe Ratio: {perf.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {perf.max_drawdown:.2%}")
        print(f"Total Trades: {perf.total_trades}")
    
    return results

if __name__ == "__main__":
    run_backtest()
```

**步骤 3: 运行回测**

```bash
python backtests/run_backtest.py
```

### 4.2 使用示例项目

```bash
# 克隆示例项目
git clone https://github.com/nautechsystems/nautilus_trader.git
cd nautilus_trader/examples

# 运行示例回测
python backtest/ema_cross.py

# 运行示例实盘 (需要 API 密钥)
python live/binance_spot.py
```

### 4.3 Jupyter Notebook 快速开始

```python
# quickstart.ipynb
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.indicators import EMA

# 创建回测引擎
engine = BacktestEngine(
    config=BacktestEngineConfig(
        trader_id="BACKTESTER-001",
        run_analysis=True,
    ),
)

# 添加策略
strategy = EMACross(config=EMACrossConfig(...))
engine.add_strategy(strategy)

# 加载数据
engine.load_data(bars=bars)

# 运行回测
engine.run()

# 生成报告
engine.generate_reports()

# 查看结果
results = engine.results()
```

---

## 5. 第一个策略 (First Strategy)

### 5.1 策略基础结构

```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig

class MyStrategyConfig(StrategyConfig):
    """策略配置类"""
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal

class MyStrategy(Strategy):
    """自定义策略类"""
    
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        # 初始化状态变量
        self.instrument = None
    
    def on_start(self) -> None:
        """策略启动时调用"""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
        self.log.info(f"Strategy started: {self.instrument.id}")
    
    def on_stop(self) -> None:
        """策略停止时调用"""
        self.cancel_all_orders()
        self.log.info("Strategy stopped")
    
    def on_bar(self, bar: Bar) -> None:
        """K 线数据到达时调用"""
        # 策略逻辑
        pass
```

### 5.2 策略生命周期

```
PRE_INITIALIZED → READY → STARTING → RUNNING
                                    ↓
RUNNING → STOPPING → STOPPED → RUNNING (resume)
RUNNING → DEGRADED → RUNNING (resume)
RUNNING → FAULTED
RUNNING → DISPOSED
```

**生命周期方法**:
| 方法 | 调用时机 | 用途 |
|------|---------|------|
| `on_start()` | 策略启动时 | 订阅数据、初始化指标 |
| `on_stop()` | 策略停止时 | 取消订单、清理资源 |
| `on_resume()` | 从停止恢复 | 恢复订阅 |
| `on_reset()` | 策略重置 | 重置指标和状态 |
| `on_save()` | 保存状态 | 返回状态字典 |
| `on_load()` | 加载状态 | 恢复状态 |
| `on_dispose()` | 最终清理 | 释放资源 |

### 5.3 数据处理器

```python
class MyStrategy(Strategy):
    # 订单簿数据
    def on_order_book_deltas(self, deltas: OrderBookDeltas) -> None:
        pass
    
    def on_order_book_depth(self, depth: OrderBookDepth10) -> None:
        pass
    
    # 市场数据
    def on_quote_tick(self, tick: QuoteTick) -> None:
        pass
    
    def on_trade_tick(self, tick: TradeTick) -> None:
        pass
    
    def on_bar(self, bar: Bar) -> None:
        pass
    
    # 自定义数据
    def on_data(self,  Data) -> None:
        pass
    
    def on_signal(self, signal) -> None:
        pass
    
    # 历史数据
    def on_historical_data(self,  Data) -> None:
        pass
```

### 5.4 订单事件处理器

```python
class MyStrategy(Strategy):
    # 特定订单事件
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
    
    # 通用订单事件
    def on_order_event(self, event: OrderEvent) -> None:
        pass
```

### 5.5 持仓事件处理器

```python
class MyStrategy(Strategy):
    # 特定持仓事件
    def on_position_opened(self, event: PositionOpened) -> None:
        pass
    
    def on_position_changed(self, event: PositionChanged) -> None:
        pass
    
    def on_position_closed(self, event: PositionClosed) -> None:
        pass
    
    # 通用持仓事件
    def on_position_event(self, event: PositionEvent) -> None:
        pass
```

### 5.6 完整策略示例

```python
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide, PositionSide
from nautilus_trader.indicators import EMA, RSI

class MyFirstStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    rsi_period: int = 14
    rsi_overbought: Decimal = Decimal("70")
    rsi_oversold: Decimal = Decimal("30")

class MyFirstStrategy(Strategy):
    def __init__(self, config: MyFirstStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.fast_ema = None
        self.slow_ema = None
        self.rsi = None
        self.position = None
        self.bar_count = 0
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        
        if self.instrument is None:
            self.log.error("Instrument not found")
            return
        
        # 初始化指标
        self.fast_ema = EMA(self.config.fast_ema_period)
        self.slow_ema = EMA(self.config.slow_ema_period)
        self.rsi = RSI(self.config.rsi_period)
        
        # 订阅数据
        self.subscribe_bars(self.config.bar_type)
        
        self.log.info(f"Strategy started: {self.instrument.id}")
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("Strategy stopped")
    
    def on_bar(self, bar: Bar) -> None:
        self.bar_count += 1
        
        # 更新指标
        self.fast_ema.handle_bar(bar)
        self.slow_ema.handle_bar(bar)
        self.rsi.handle_bar(bar)
        
        # 等待指标预热
        if self.bar_count < self.config.slow_ema_period:
            return
        
        # 获取当前持仓
        self.position = self.cache.position_for_strategy(self.id)
        
        # 交易逻辑
        ema_signal = self.fast_ema.value > self.slow_ema.value
        rsi_oversold = self.rsi.value < float(self.config.rsi_oversold)
        rsi_overbought = self.rsi.value > float(self.config.rsi_overbought)
        
        if ema_signal and rsi_oversold and not self.position:
            self._enter_long()
        elif (not ema_signal or rsi_overbought) and self.position:
            self._exit_position()
    
    def _enter_long(self) -> None:
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["ENTRY"],
        )
        self.submit_order(order)
        self.log.info(f"Long entry at {order.price}")
    
    def _exit_position(self) -> None:
        self.cancel_all_orders()
        self.log.info("Exiting position")
    
    def on_position_opened(self, event: PositionOpened) -> None:
        self.log.info(f"Position opened: {event.position_id}")
    
    def on_position_closed(self, event: PositionClosed) -> None:
        self.log.info(
            f"Position closed: {event.position_id}, "
            f"PnL: {event.realized_pnl}"
        )
    
    def on_order_filled(self, event: OrderFilled) -> None:
        self.log.info(
            f"Order filled: {event.client_order_id}, "
            f"price: {event.last_px}, qty: {event.last_qty}"
        )
```

---

## 6. 第一次回测 (First Backtest)

### 6.1 回测引擎类型

| 引擎 | 用途 | 特点 |
|------|------|------|
| `BacktestEngine` | 低阶 API | 直接控制，灵活，适合学习 |
| `BacktestNode` | 高阶 API | 配置驱动，推荐生产使用 |

### 6.2 低阶 API 回测

```python
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.modules import FXRatesSimulator
from nautilus_trader.model import Money

# 1. 初始化引擎
engine = BacktestEngine(
    config=BacktestEngineConfig(
        trader_id="BACKTESTER-001",
        run_id="backtest-001",
        run_analysis=True,
    ),
)

# 2. 添加模拟模块 (可选)
engine.add_simulator_module(
    FXRatesSimulator(
        base_currency=Currency.from_str("USD"),
        rates={"EUR/USD": 1.1000},
    ),
)

# 3. 添加策略
strategy = MyFirstStrategy(config=MyFirstStrategyConfig(...))
engine.add_strategy(strategy)

# 4. 添加工具
instrument = CurrencyPair(...)
engine.add_instrument(instrument)

# 5. 加载数据
engine.load_data(
    quote_ticks=quote_ticks,
    trade_ticks=trade_ticks,
    bars=bars,
)

# 6. 运行回测
engine.run()

# 7. 生成报告
engine.generate_reports()

# 8. 获取结果
results = engine.results()

# 9. 清理
engine.dispose()
```

### 6.3 高阶 API 回测

```python
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import (
    BacktestRunConfig,
    BacktestEngineConfig,
    BacktestVenueConfig,
    DataConfig,
)

# 1. 配置回测运行
configs = [
    BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            run_analysis=True,
        ),
        venues=[
            BacktestVenueConfig(
                name="BINANCE",
                oms_type=OmsType.NETTING,
                account_type=AccountType.MARGIN,
                base_currency="USDT",
                starting_balances=[Money(1_000_000, "USDT")],
                maker_fee=0.0002,
                taker_fee=0.0005,
            ),
        ],
        data=[
            DataConfig(
                catalog_path="./catalog",
                instrument_id="BTCUSDT.BINANCE",
                bar_type="1-HOUR",
                start_time="2024-01-01",
                end_time="2024-12-31",
            ),
        ],
        strategies=[
            MyFirstStrategyConfig(
                instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
                trade_size=Decimal("0.1"),
                order_id_tag="001",
            ),
        ],
    ),
]

# 2. 创建节点
node = BacktestNode(configs=configs)

# 3. 运行回测
results = node.run()

# 4. 处理结果
for result in results:
    perf = result.performance
    print(f"Total Return: {perf.total_return:.2%}")
    print(f"Sharpe Ratio: {perf.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {perf.max_drawdown:.2%}")
```

### 6.4 回测配置选项

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
    run_id="backtest-001",
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
)
```

### 6.5 回测结果分析

```python
# 绩效指标
performance = result.performance

print(f"Total Return: {performance.total_return:.2%}")
print(f"Annualized Return: {performance.annualized_return:.2%}")
print(f"Sharpe Ratio: {performance.sharpe_ratio:.2f}")
print(f"Sortino Ratio: {performance.sortino_ratio:.2f}")
print(f"Calmar Ratio: {performance.calmar_ratio:.2f}")
print(f"Max Drawdown: {performance.max_drawdown:.2%}")
print(f"Max Drawdown Duration: {performance.max_drawdown_duration}")
print(f"Volatility: {performance.volatility:.2%}")

# 交易统计
print(f"Total Trades: {performance.total_trades}")
print(f"Winning Trades: {performance.winning_trades}")
print(f"Losing Trades: {performance.losing_trades}")
print(f"Win Rate: {performance.win_rate:.2%}")
print(f"Profit/Loss Ratio: {performance.profit_loss_ratio:.2f}")
print(f"Average Trade: {performance.average_trade:.2f}")
print(f"Average Hold Time: {performance.average_hold_time}")
```

### 6.6 生成回测报告

```python
from pathlib import Path

# 生成报告目录
report_dir = Path("./reports")
report_dir.mkdir(parents=True, exist_ok=True)

# 保存报告
for result in results:
    result.save_reports(report_dir)

# 报告文件包括:
# - performance.html (绩效报告)
# - positions.parquet (持仓记录)
# - orders.parquet (订单记录)
# - fills.parquet (成交记录)
# - account_state.parquet (账户状态)
```

---

## 7. 配置说明 (Configuration)

### 7.1 配置层次

| 层次 | 范围 | 示例 |
|------|------|------|
| `TradingNodeConfig` | 整个交易节点 | 所有交易所、策略 |
| `BacktestEngineConfig` | 回测引擎 | 回测特定设置 |
| `StrategyConfig` | 单个策略 | 策略参数 |
| `AdapterConfig` | 适配器 | 交易所连接设置 |

### 7.2 Python 配置

```python
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.adapters.binance.config import BinanceLiveConfig

config = TradingNodeConfig(
    trader_id="TRADER-001",
    run_id="20240105-001",
    
    # 缓存配置
    cache=CacheConfig(
        database=DatabaseConfig(
            type="redis",
            host="localhost",
            port=6379,
        ),
    ),
    
    # 日志配置
    logging=LoggingConfig(
        log_level="INFO",
        log_colors=True,
    ),
    
    # 交易所配置
    venues=[
        BinanceLiveConfig(
            api_key="your_api_key",
            api_secret="your_api_secret",
            instrument_ids=["BTCUSDT.BINANCE"],
        ),
    ],
    
    # 策略配置
    strategies=[
        EMACrossConfig(
            instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
            bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
            trade_size=Decimal("0.1"),
        ),
    ],
)
```

### 7.3 YAML 配置

```yaml
# config.yaml
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

venues:
  - name: "BINANCE"
    type: "binance"
    config:
      api_key: "${BINANCE_API_KEY}"
      api_secret: "${BINANCE_API_SECRET}"
      instrument_ids:
        - "BTCUSDT.BINANCE"

strategies:
  - class_path: "strategies.ema_cross.EMACross"
    config:
      instrument_id: "BTCUSDT.BINANCE"
      bar_type: "BTCUSDT.BINANCE-1-HOUR"
      fast_ema_period: 10
      slow_ema_period: 20
      trade_size: 0.1
```

### 7.4 环境变量

```bash
# .env 文件
NAUTILUS_TRADER_ID=TRADER-001
NAUTILUS_RUN_ID=20240105-001

NAUTILUS_DATABASE_TYPE=redis
NAUTILUS_DATABASE_HOST=localhost
NAUTILUS_DATABASE_PORT=6379

NAUTILUS_LOG_LEVEL=INFO
NAUTILUS_LOG_DIRECTORY=./logs

BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
```

### 7.5 加载配置

```python
import os
from pathlib import Path
from nautilus_trader.config import TradingNodeConfig

# 从 Python 文件加载
from config.live_config import get_live_config
config = get_live_config()

# 从 YAML 文件加载
import yaml
with open("config.yaml", "r") as f:
    config_dict = yaml.safe_load(f)
config = TradingNodeConfig(**config_dict)

# 从环境变量加载
config = TradingNodeConfig(
    trader_id=os.getenv("NAUTILUS_TRADER_ID"),
    run_id=os.getenv("NAUTILUS_RUN_ID"),
)
```

---

## 8. 数据准备 (Data Preparation)

### 8.1 数据来源

| 数据源 | 类型 | 费用 | 质量 |
|--------|------|------|------|
| Databento | Tick/Bar/OrderBook | 付费 | 交易所直连 |
| Tardis.dev | Tick/OrderBook | 付费 | 高质量 |
| Binance API | Tick/Bar | 免费 | 实时数据 |
| 本地 CSV | 自定义 | 免费 | 取决于来源 |

### 8.2 构建 Parquet 数据目录

```python
from pathlib import Path
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader

def build_catalog():
    # 1. 创建目录
    catalog_path = Path("./catalog")
    catalog_path.mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(path=catalog_path)
    
    # 2. 加载数据
    loader = DatabentoDataLoader(api_key="your_api_key")
    
    # 加载 K 线
    bars = loader.load_bars(
        instrument_ids=["BTCUSDT.BINANCE"],
        schema="ohlcv-1m",
        start="2024-01-01",
        end="2024-12-31",
    )
    catalog.write_bars(bars)
    
    # 加载报价
    quotes = loader.load_quote_ticks(
        instrument_ids=["BTCUSDT.BINANCE"],
        start="2024-01-01",
        end="2024-12-31",
    )
    catalog.write_quote_ticks(quotes)
    
    # 加载工具定义
    instruments = loader.load_instruments(
        instrument_ids=["BTCUSDT.BINANCE"],
    )
    catalog.write_instruments(instruments)
    
    return catalog
```

### 8.3 从 CSV 导入数据

```python
import pandas as pd
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.data import Bar
from nautilus_trader.core.datetime import dt_to_unix_nanos

def import_from_csv(csv_path: str, catalog_path: str):
    df = pd.read_csv(csv_path)
    catalog = ParquetDataCatalog(path=catalog_path)
    
    bars = []
    for _, row in df.iterrows():
        bar = Bar(
            bar_type=BarType.from_str("BTCUSDT.BINANCE-1-MINUTE"),
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
    print(f"Imported {len(bars)} bars")
```

### 8.4 查询数据目录

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog

catalog = ParquetDataCatalog(path="./catalog")

# 查询 K 线
bars = catalog.bars(
    instrument_ids=["BTCUSDT.BINANCE"],
    bar_types=["1-HOUR"],
    start="2024-01-01",
    end="2024-12-31",
)

# 查询报价
quotes = catalog.quote_ticks(
    instrument_ids=["BTCUSDT.BINANCE"],
    start="2024-01-01",
    end="2024-01-31",
)

# 查询工具
instruments = catalog.instruments(
    instrument_ids=["BTCUSDT.BINANCE"],
)
```

### 8.5 数据格式要求

**时间戳**:
- 精度：纳秒级 (9 位小数)
- 时区：UTC
- 格式：ISO 8601 (RFC 3339)
- 示例：`2024-01-05T15:30:45.123456789Z`

**价格/数量精度**:
```python
# 使用工具工厂方法确保精度正确
price = instrument.make_price(50000.00)
quantity = instrument.make_qty(0.1)

# 或手动创建
price = Price.from_str("50000.00")
quantity = Quantity.from_str("0.1")
```

---

## 9. 实盘准备 (Live Trading Preparation)

### 9.1 实盘前检查清单

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 策略回测 | ☐ | 完成充分回测验证 |
| 沙箱测试 | ☐ | 在沙箱环境测试 |
| 模拟账户 | ☐ | 在交易所模拟账户测试 |
| 风险控制 | ☐ | 配置风险限制 |
| 监控报警 | ☐ | 设置监控和报警 |
| 日志配置 | ☐ | 配置日志持久化 |
| 应急计划 | ☐ | 制定应急处理流程 |

### 9.2 配置实盘节点

```python
from nautilus_trader.live.node import TradingNode
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.config import (
    CacheConfig,
    DatabaseConfig,
    LoggingConfig,
    RiskEngineConfig,
)
from nautilus_trader.adapters.binance.config import BinanceLiveConfig

config = TradingNodeConfig(
    trader_id="TRADER-001",
    run_id="live-2024-001",
    
    # 缓存配置 (使用 Redis)
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
    
    # 交易所配置
    venues=[
        BinanceLiveConfig(
            api_key=os.getenv("BINANCE_API_KEY"),
            api_secret=os.getenv("BINANCE_API_SECRET"),
            instrument_ids=["BTCUSDT.BINANCE"],
            account_type=AccountType.MARGIN,
            use_testnet=False,
        ),
    ],
    
    # 策略配置
    strategies=[
        EMACrossConfig(
            instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
            bar_type=BarType.from_str("BTCUSDT.BINANCE-1-MINUTE"),
            trade_size=Decimal("0.01"),
            order_id_tag="001",
        ),
    ],
)

node = TradingNode(config=config)
```

### 9.3 启动实盘交易

```python
import asyncio
import signal
import sys

class TradingBot:
    def __init__(self, config):
        self.config = config
        self.node = None
        self._shutdown = False
    
    def setup_signal_handlers(self):
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print(f"\nReceived signal {signum}. Shutting down...")
        self._shutdown = True
    
    async def run(self):
        self.node = TradingNode(config=self.config)
        self.setup_signal_handlers()
        
        try:
            await self.node.run_async()
            
            while not self._shutdown:
                await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        if self.node:
            print("Stopping trading node...")
            self.node.stop()
            self.node.dispose()
            print("Trading node stopped.")

async def main():
    config = configure_live_node()
    bot = TradingBot(config)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### 9.4 使用沙箱测试

```python
from nautilus_trader.adapters.sandbox.config import SandboxLiveConfig
from nautilus_trader.adapters.sandbox.fill_model import FillModel

sandbox_config = SandboxLiveConfig(
    instrument_ids=["BTCUSDT.SANDBOX"],
    account_type=AccountType.MARGIN,
    starting_balances=[Money(1_000_000, "USDT")],
    fill_model=FillModel(
        prob_fill_on_limit=0.2,
        prob_fill_on_stop=0.9,
        prob_slippage=0.1,
        slippage_range=(0.0001, 0.001),
    ),
)

# 沙箱特点:
# - 使用真实市场数据
# - 虚拟执行 (不实际下单)
# - 可配置滑点和延迟
# - 适合策略验证
```

### 9.5 实盘部署选项

| 部署方式 | 适用场景 | 复杂度 |
|---------|---------|--------|
| 本地运行 | 开发/测试 | ⭐ |
| Docker | 生产环境 | ⭐⭐ |
| Kubernetes | 大规模部署 | ⭐⭐⭐⭐ |
| 云服务 (AWS/GCP) | 企业级 | ⭐⭐⭐ |

---

## 10. 常见问题 (FAQ)

### 10.1 安装问题

**Q: Windows 上安装失败？**
```
A: Windows 仅支持 64 位标准精度版本。
   确保使用 Python 3.12+ 和最新 pip。
   安装 Visual Studio Build Tools。
```

**Q: Rust 编译失败？**
```
A: 运行以下命令：
   rustup update
   cargo clean
   cargo build --release
```

**Q: 依赖冲突？**
```
A: 使用 uv 包管理器或创建干净的虚拟环境。
   uv sync --all-extras
```

### 10.2 回测问题

**Q: 回测结果与实盘不一致？**
```
A: 检查以下项：
   - 滑点设置
   - 佣金配置
   - 延迟模拟
   - 数据源质量
   - 风险引擎配置
```

**Q: 回测速度慢？**
```
A: 优化建议：
   - 使用 Bar 而非 Tick 数据
   - 减少策略数量
   - 禁用不必要的分析
   - 减少缓存容量
```

### 10.3 实盘问题

**Q: 连接交易所失败？**
```
A: 检查以下项：
   - API 密钥权限
   - 网络连接
   - 防火墙设置
   - 时间同步 (误差需 < 500ms)
```

**Q: 订单被拒绝？**
```
A: 检查以下项：
   - 风险引擎限制
   - 订单参数 (价格/数量精度)
   - 账户余额
   - 交易所规则
```

### 10.4 策略问题

**Q: 策略不产生交易信号？**
```
A: 检查以下项：
   - 指标是否正确初始化
   - 数据订阅是否正确
   - 条件逻辑是否正确
   - 查看日志输出
```

**Q: 策略状态丢失？**
```
A: 实现 on_save() 和 on_load() 方法：
   def on_save(self) -> dict[str, bytes]:
       return {"state": str(self.state).encode()}
   
   def on_load(self, state: dict[str, bytes]) -> None:
       self.state = int(state["state"].decode())
```

### 10.5 性能问题

**Q: 内存使用过高？**
```
A: 优化建议：
   - 减少缓存容量配置
   - 使用 Redis 外部缓存
   - 定期清理旧数据
   - 检查内存泄漏
```

**Q: CPU 使用过高？**
```
A: 优化建议：
   - 减少数据订阅
   - 优化策略逻辑
   - 使用更高效的指标
   - 考虑 Rust 实现热点代码
```

---

## 11. 下一步学习 (Next Steps)

### 11.1 学习路径

```
入门完成
    ↓
1. 深入学习 Concepts 文档
    ↓
2. 完成 Tutorials 教程
    ↓
3. 阅读 How-To 操作指南
    ↓
4. 参考 API Reference
    ↓
5. 研究 Integrations 集成
    ↓
6. 参与 Developer Guide 开发
```

### 11.2 推荐学习资源

| 资源 | 用途 | 链接 |
|------|------|------|
| Concepts | 核心概念详解 | `/docs/concepts/` |
| Tutorials | 实战教程 | `/docs/tutorials/` |
| How-To | 操作指南 | `/docs/how_to/` |
| API Reference | API 参考 | `/docs/api_reference/` |
| Integrations | 交易所集成 | `/docs/integrations/` |
| Developer Guide | 开发者指南 | `/docs/developer_guide/` |

### 11.3 社区资源

| 资源 | 用途 | 链接 |
|------|------|------|
| GitHub Issues | 问题报告 | https://github.com/nautechsystems/nautilus_trader/issues |
| GitHub Discussions | 社区讨论 | https://github.com/nautechsystems/nautilus_trader/discussions |
| 官方文档 | 完整文档 | https://nautilustrader.io/docs/ |
| PyPI | 包下载 | https://pypi.org/project/nautilus-trader/ |
| Docker Hub | 镜像 | https://ghcr.io/nautechsystems/jupyterlab:nightly |

### 11.4 进阶主题

| 主题 | 描述 | 难度 |
|------|------|------|
| 自定义指标 | 编写自定义技术指标 | ⭐⭐ |
| 执行算法 | 实现 TWAP/VWAP 等算法 | ⭐⭐⭐ |
| 自定义适配器 | 集成新交易所 | ⭐⭐⭐⭐ |
| Rust 开发 | 使用 Rust 编写策略 | ⭐⭐⭐⭐⭐ |
| 分布式部署 | Kubernetes 部署 | ⭐⭐⭐⭐⭐ |

### 11.5 最佳实践

**代码组织**:
```
my_project/
├── strategies/      # 策略代码
├── adapters/        # 自定义适配器
├── config/          # 配置文件
├── backtests/       # 回测脚本
├── live/            # 实盘脚本
├── tests/           # 测试代码
└── data/            # 数据目录
```

**版本控制**:
```bash
# 使用 Git 管理代码
git init
git add .
git commit -m "Initial commit"

# 使用分支管理功能开发
git checkout -b feature/new-strategy
```

**持续集成**:
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: pytest tests/
```

---

## 附录 A: 快速参考卡片

### A.1 常用导入

```python
# 核心
from nautilus_trader.core import UUID4, Timestamp
from nautilus_trader.core.identifiers import (
    AccountId, ClientId, InstrumentId, OrderId,
    PositionId, StrategyId, TraderId, Venue,
)

# 模型
from nautilus_trader.model import Price, Quantity, Money, Currency
from nautilus_trader.model.data import QuoteTick, TradeTick, Bar
from nautilus_trader.model.orders import MarketOrder, LimitOrder
from nautilus_trader.model.position import Position

# 交易
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig

# 回测
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.node import BacktestNode

# 实盘
from nautilus_trader.live.node import TradingNode

# 数据
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# 指标
from nautilus_trader.indicators import EMA, SMA, RSI, MACD
```

### A.2 常用命令

```bash
# 安装
pip install nautilus_trader
uv add nautilus_trader

# 回测
python -m backtests.run_backtest

# 实盘
python -m live.run_live

# 测试
pytest tests/

# 构建数据目录
python scripts/build_catalog.py

# Docker
docker-compose up -d
docker-compose logs -f
```

### A.3 关键配置参数

```python
# 策略配置
StrategyConfig:
    - instrument_id
    - bar_type
    - trade_size
    - order_id_tag

# 回测配置
BacktestEngineConfig:
    - trader_id
    - run_analysis
    - cache
    - logging

# 实盘配置
TradingNodeConfig:
    - trader_id
    - cache (Redis)
    - logging
    - risk_engine
    - venues
    - strategies
```

---

## 附录 B: 检查清单

### B.1 安装检查清单

- [ ] Python 3.12+ 已安装
- [ ] 虚拟环境已创建
- [ ] nautilus_trader 已安装
- [ ] 导入测试通过
- [ ] 示例代码可运行

### B.2 回测检查清单

- [ ] 数据目录已构建
- [ ] 策略代码已编写
- [ ] 回测配置已完成
- [ ] 回测运行成功
- [ ] 报告已生成
- [ ] 结果已分析

### B.3 实盘检查清单

- [ ] 策略已充分回测
- [ ] 沙箱测试通过
- [ ] API 密钥已配置
- [ ] 风险限制已设置
- [ ] 监控报警已配置
- [ ] 日志持久化已启用
- [ ] 应急计划已制定

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-03-31  
> **维护者**: Nautilus Trader 社区

---

此 Markdown 文件包含完整的 Getting Started 目录内容汇总，可直接用于 AI 工具编程参考。如需进一步细化某个章节的入门细节，请告知！