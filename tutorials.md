# Nautilus Trader Tutorials 实战教程汇总

> **文档版本**: develop 分支 (2026 年 3 月)  
> **适用对象**: 量化开发者、策略研究员、学习者  
> **用途**: AI 工具编程参考文档

python live/pde_dashboard.py --db data/pde/pde_runs.sqlite3
python live/run_polymarket_pde.py --mode sandbox 2>&1

---

## 目录

1. [教程概述 (Tutorial Overview)](#1-教程概述-tutorial-overview)
2. [快速入门教程 (Quick Start Tutorial)](#2-快速入门教程-quick-start-tutorial)
3. [回测教程 (Backtesting Tutorials)](#3-回测教程-backtesting-tutorials)
4. [数据工作流教程 (Data Workflow Tutorials)](#4-数据工作流教程-data-workflow-tutorials)
5. [策略开发教程 (Strategy Development Tutorials)](#5-策略开发教程-strategy-development-tutorials)
6. [实盘交易教程 (Live Trading Tutorials)](#6-实盘交易教程-live-trading-tutorials)
7. [风险管理教程 (Risk Management Tutorials)](#7-风险管理教程-risk-management-tutorials)
8. [高级主题教程 (Advanced Topic Tutorials)](#8-高级主题教程-advanced-topic-tutorials)
9. [集成教程 (Integration Tutorials)](#9-集成教程-integration-tutorials)
10. [学习路径建议 (Learning Path Recommendations)](#10-学习路径建议-learning-path-recommendations)

---

## 1. 教程概述 (Tutorial Overview)

### 1.1 教程分类

| 类别 | 教程数量 | 难度 | 预计时间 |
|------|---------|------|---------|
| 快速入门 | 2 | ⭐ | 30 分钟 |
| 回测教程 | 5 | ⭐⭐ | 2-4 小时 |
| 数据工作流 | 4 | ⭐⭐ | 2-3 小时 |
| 策略开发 | 6 | ⭐⭐⭐ | 4-8 小时 |
| 实盘交易 | 3 | ⭐⭐⭐⭐ | 4-6 小时 |
| 风险管理 | 3 | ⭐⭐⭐ | 2-4 小时 |
| 高级主题 | 4 | ⭐⭐⭐⭐⭐ | 8-16 小时 |
| 集成教程 | 5 | ⭐⭐⭐⭐ | 4-8 小时 |

### 1.2 学习前提

**必备知识**:
- Python 编程基础 (3.12+)
- 量化交易基本概念
- 命令行操作基础

**推荐知识**:
- Rust 基础 (用于高级开发)
- Docker 基础 (用于部署)
- Redis 基础 (用于缓存)

### 1.3 教程环境设置

```bash
# 1. 创建项目目录
mkdir nautilus_tutorials
cd nautilus_tutorials

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

# 3. 安装 nautilus_trader
pip install nautilus_trader

# 4. 安装教程依赖
pip install pandas numpy plotly jupyterlab

# 5. 验证安装
python -c "import nautilus_trader; print(f'Version: {nautilus_trader.__version__}')"
```

### 1.4 教程项目结构

```
nautilus_tutorials/
├── 01_quickstart/          # 快速入门
├── 02_backtesting/         # 回测教程
├── 03_data_workflow/       # 数据工作流
├── 04_strategy_dev/        # 策略开发
├── 05_live_trading/        # 实盘交易
├── 06_risk_management/     # 风险管理
├── 07_advanced/            # 高级主题
├── 08_integrations/        # 集成教程
├── data/                   # 示例数据
├── catalog/                # Parquet 数据目录
├── logs/                   # 日志文件
└── reports/                # 回测报告
```

---

## 2. 快速入门教程 (Quick Start Tutorial)

### 2.1 教程 1:5 分钟快速回测

**目标**: 5 分钟内完成第一次回测

**步骤**:

```python
# 01_quickstart/quickstart.py
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
from nautilus_trader.indicators import EMA

# 1. 定义策略配置
from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

class QuickStartConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal

class QuickStartStrategy(Strategy):
    def __init__(self, config: QuickStartConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.ema = None
        self.bar_count = 0
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.ema = EMA(20)
        self.subscribe_bars(self.config.bar_type)
    
    def on_bar(self, bar: Bar) -> None:
        self.bar_count += 1
        self.ema.handle_bar(bar)
        
        if self.bar_count > 20:
            if self.ema.value < float(bar.close):
                self._buy()
            else:
                self._sell()
    
    def _buy(self) -> None:
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
        )
        self.submit_order(order)
    
    def _sell(self) -> None:
        self.cancel_all_orders()

# 2. 配置回测
config = BacktestRunConfig(
    engine=BacktestEngineConfig(
        trader_id="QUICKSTART-001",
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
            starting_balances=[Money(100_000, "USDT")],
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
            end_time="2024-06-30",
        ),
    ],
    strategies=[
        QuickStartConfig(
            instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
            bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"),
            trade_size=Decimal("0.01"),
            order_id_tag="001",
        ),
    ],
)

# 3. 运行回测
node = BacktestNode(configs=[config])
results = node.run()

# 4. 查看结果
for result in results:
    perf = result.performance
    print(f"\n{'='*50}")
    print(f"Strategy: {result.strategy_id}")
    print(f"{'='*50}")
    print(f"Total Return: {perf.total_return:.2%}")
    print(f"Sharpe Ratio: {perf.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {perf.max_drawdown:.2%}")
    print(f"Total Trades: {perf.total_trades}")
```

**运行命令**:
```bash
python 01_quickstart/quickstart.py
```

### 2.2 教程 2: 使用 Jupyter Notebook

**目标**: 在交互式环境中学习 Nautilus Trader

**Notebook 结构**:

```python
# 01_quickstart/quickstart.ipynb

# Cell 1: 导入库
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.indicators import EMA, RSI
import pandas as pd
import plotly.graph_objects as go

# Cell 2: 创建回测引擎
engine = BacktestEngine(
    config=BacktestEngineConfig(
        trader_id="NOTEBOOK-001",
        run_analysis=True,
    ),
)

# Cell 3: 添加策略
strategy = QuickStartStrategy(config=QuickStartConfig(...))
engine.add_strategy(strategy)

# Cell 4: 加载数据
engine.load_data(bars=bars)

# Cell 5: 运行回测
engine.run()

# Cell 6: 可视化结果
results = engine.results()
perf = results[0].performance

# 权益曲线
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=perf.equity_curve.index,
    y=perf.equity_curve.values,
    name='Equity'
))
fig.show()
```

---

## 3. 回测教程 (Backtesting Tutorials)

### 3.1 教程 3: 低阶 API 回测

**目标**: 学习使用 BacktestEngine 进行细粒度控制

**完整代码**:

```python
# 02_backtesting/low_level_backtest.py
from decimal import Decimal
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.modules import FXRatesSimulator
from nautilus_trader.model import Money, Currency
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.data import Bar, QuoteTick
from nautilus_trader.model.identifiers import InstrumentId, Symbol

# 1. 初始化引擎
engine = BacktestEngine(
    config=BacktestEngineConfig(
        trader_id="LOWLEVEL-001",
        run_id="lowlevel-001",
        run_analysis=True,
    ),
)

# 2. 添加模拟模块 (可选)
engine.add_simulator_module(
    FXRatesSimulator(
        base_currency=Currency.from_str("USD"),
        rates={"EUR/USD": 1.1000, "GBP/USD": 1.2500},
    ),
)

# 3. 添加策略
strategy = EMACrossStrategy(config=EMACrossConfig(...))
engine.add_strategy(strategy)

# 4. 添加工具
instrument = CurrencyPair(
    instrument_id=InstrumentId.from_str("BTC/USDT.BINANCE"),
    symbol=Symbol("BTC/USDT"),
    base_currency=Currency.from_str("BTC"),
    quote_currency=Currency.from_str("USDT"),
    price_precision=8,
    size_precision=8,
    price_increment=Price.from_str("0.00000001"),
    size_increment=Quantity.from_str("0.00000001"),
    ts_event=0,
    ts_init=0,
)
engine.add_instrument(instrument)

# 5. 加载数据
engine.load_data(
    bars=bars,
    quote_ticks=quotes,
    trade_ticks=trades,
)

# 6. 运行回测
engine.run()

# 7. 生成报告
engine.generate_reports()

# 8. 获取结果
results = engine.results()
report = engine.performance_report()

# 9. 清理
engine.dispose()
```

### 3.2 教程 4: 高阶 API 回测

**目标**: 学习使用 BacktestNode 进行配置驱动回测

**完整代码**:

```python
# 02_backtesting/high_level_backtest.py
from decimal import Decimal
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import (
    BacktestRunConfig,
    BacktestEngineConfig,
    BacktestVenueConfig,
    DataConfig,
)
from nautilus_trader.config import CacheConfig, LoggingConfig, RiskEngineConfig
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model import Money

# 1. 配置多个回测运行
configs = [
    # 运行 1: BTC 1 小时回测
    BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="HIGHLEVEL-001",
            run_analysis=True,
            cache=CacheConfig(tick_capacity=10_000),
            logging=LoggingConfig(log_level="INFO"),
            risk_engine=RiskEngineConfig(
                max_notional_per_order=Money(100_000, "USDT"),
            ),
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
                bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
                fast_ema_period=10,
                slow_ema_period=20,
                trade_size=Decimal("0.1"),
                order_id_tag="001",
            ),
        ],
    ),
    
    # 运行 2: ETH 1 小时回测
    BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id="HIGHLEVEL-002"),
        venues=[...],
        data=[...],
        strategies=[...],
    ),
]

# 2. 创建节点
node = BacktestNode(configs=configs)

# 3. 运行回测
results = node.run()

# 4. 处理结果
for result in results:
    perf = result.performance
    print(f"\n{result.strategy_id}:")
    print(f"  Return: {perf.total_return:.2%}")
    print(f"  Sharpe: {perf.sharpe_ratio:.2f}")
    print(f"  MaxDD: {perf.max_drawdown:.2%}")

# 5. 生成汇总报告
node.generate_reports()
```

### 3.3 教程 5: 多策略回测

**目标**: 同时回测多个策略并比较结果

**完整代码**:

```python
# 02_backtesting/multi_strategy_backtest.py
from decimal import Decimal
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import BacktestRunConfig
import pandas as pd

def run_multi_strategy_backtest():
    """运行多策略回测并比较"""
    
    configs = []
    
    # 策略 1: EMA Cross (10, 20)
    configs.append(BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id="MULTI-001"),
        venues=[...],
        data=[...],
        strategies=[EMACrossConfig(fast=10, slow=20, ...)],
    ))
    
    # 策略 2: EMA Cross (15, 30)
    configs.append(BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id="MULTI-002"),
        venues=[...],
        data=[...],
        strategies=[EMACrossConfig(fast=15, slow=30, ...)],
    ))
    
    # 策略 3: EMA Cross (20, 40)
    configs.append(BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id="MULTI-003"),
        venues=[...],
        data=[...],
        strategies=[EMACrossConfig(fast=20, slow=40, ...)],
    ))
    
    # 运行回测
    node = BacktestNode(configs=configs)
    results = node.run()
    
    # 创建比较表格
    comparison = []
    for result in results:
        perf = result.performance
        comparison.append({
            "Strategy": result.strategy_id,
            "Total Return": f"{perf.total_return:.2%}",
            "Sharpe Ratio": f"{perf.sharpe_ratio:.2f}",
            "Sortino Ratio": f"{perf.sortino_ratio:.2f}",
            "Max Drawdown": f"{perf.max_drawdown:.2%}",
            "Total Trades": perf.total_trades,
            "Win Rate": f"{perf.win_rate:.2%}",
        })
    
    df = pd.DataFrame(comparison)
    print(df.to_string(index=False))
    
    # 保存比较结果
    df.to_csv("./reports/strategy_comparison.csv", index=False)
    
    return df
```

### 3.4 教程 6: 参数优化回测

**目标**: 学习如何优化策略参数

**完整代码**:

```python
# 02_backtesting/parameter_optimization.py
from itertools import product
from decimal import Decimal
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import BacktestRunConfig

def optimize_ema_parameters():
    """优化 EMA 策略参数"""
    
    # 参数网格
    fast_periods = [5, 10, 15, 20, 25]
    slow_periods = [20, 30, 40, 50, 60]
    trade_sizes = [Decimal("0.05"), Decimal("0.1"), Decimal("0.2")]
    
    results = []
    
    for fast, slow, size in product(fast_periods, slow_periods, trade_sizes):
        if fast >= slow:
            continue
        
        print(f"Testing fast={fast}, slow={slow}, size={size}...")
        
        config = BacktestRunConfig(
            engine=BacktestEngineConfig(
                trader_id="OPTIMIZE-001",
                run_analysis=False,  # 禁用分析加速
            ),
            venues=[...],
            data=[...],
            strategies=[
                EMACrossConfig(
                    instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                    bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
                    fast_ema_period=fast,
                    slow_ema_period=slow,
                    trade_size=size,
                    order_id_tag=f"{fast:02d}{slow:02d}",
                ),
            ],
        )
        
        node = BacktestNode(configs=[config])
        backtest_results = node.run()
        
        perf = backtest_results[0].performance
        
        results.append({
            "fast_period": fast,
            "slow_period": slow,
            "trade_size": str(size),
            "total_return": perf.total_return,
            "sharpe_ratio": perf.sharpe_ratio,
            "max_drawdown": perf.max_drawdown,
            "total_trades": perf.total_trades,
            "win_rate": perf.win_rate,
        })
    
    # 按夏普比率排序
    results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
    
    # 显示前 5 名
    print("\n" + "="*70)
    print("TOP 5 PARAMETER SETS (by Sharpe Ratio)")
    print("="*70)
    
    for i, r in enumerate(results[:5]):
        print(f"\n{i+1}. Fast={r['fast_period']}, Slow={r['slow_period']}, Size={r['trade_size']}")
        print(f"   Return: {r['total_return']:.2%}")
        print(f"   Sharpe: {r['sharpe_ratio']:.2f}")
        print(f"   MaxDD: {r['max_drawdown']:.2%}")
        print(f"   Trades: {r['total_trades']}")
        print(f"   Win Rate: {r['win_rate']:.2%}")
    
    return results
```

### 3.5 教程 7: 回测结果分析

**目标**: 学习如何分析和可视化回测结果

**完整代码**:

```python
# 02_backtesting/analyze_results.py
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from nautilus_trader.backtest.node import BacktestNode

def analyze_backtest_results():
    """分析回测结果"""
    
    # 运行回测
    node = BacktestNode(configs=[config])
    results = node.run()
    result = results[0]
    perf = result.performance
    
    # 1. 打印绩效指标
    print("\n" + "="*50)
    print("PERFORMANCE METRICS")
    print("="*50)
    print(f"Total Return: {perf.total_return:.2%}")
    print(f"Annualized Return: {perf.annualized_return:.2%}")
    print(f"Sharpe Ratio: {perf.sharpe_ratio:.2f}")
    print(f"Sortino Ratio: {perf.sortino_ratio:.2f}")
    print(f"Calmar Ratio: {perf.calmar_ratio:.2f}")
    print(f"Max Drawdown: {perf.max_drawdown:.2%}")
    print(f"Max Drawdown Duration: {perf.max_drawdown_duration}")
    print(f"Volatility: {perf.volatility:.2%}")
    
    # 2. 打印交易统计
    print("\n" + "="*50)
    print("TRADING STATISTICS")
    print("="*50)
    print(f"Total Trades: {perf.total_trades}")
    print(f"Winning Trades: {perf.winning_trades}")
    print(f"Losing Trades: {perf.losing_trades}")
    print(f"Win Rate: {perf.win_rate:.2%}")
    print(f"Profit/Loss Ratio: {perf.profit_loss_ratio:.2f}")
    print(f"Average Trade: {perf.average_trade:.2f}")
    print(f"Average Hold Time: {perf.average_hold_time}")
    
    # 3. 创建可视化
    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=('Equity Curve', 'Drawdown', 'Monthly Returns', 'Trade Distribution'),
        vertical_spacing=0.08
    )
    
    # 权益曲线
    fig.add_trace(
        go.Scatter(x=perf.equity_curve.index, y=perf.equity_curve.values, name='Equity'),
        row=1, col=1
    )
    
    # 回撤
    fig.add_trace(
        go.Scatter(x=perf.drawdown_curve.index, y=perf.drawdown_curve.values, name='Drawdown', fill='tozeroy'),
        row=2, col=1
    )
    
    # 月度收益
    fig.add_trace(
        go.Bar(x=perf.monthly_returns.index, y=perf.monthly_returns.values, name='Monthly Return'),
        row=3, col=1
    )
    
    # 交易收益分布
    fig.add_trace(
        go.Histogram(x=perf.trade_returns, name='Trade Returns', nbinsx=50),
        row=4, col=1
    )
    
    fig.update_layout(height=1000, title_text="Backtest Analysis")
    fig.write_html("./reports/backtest_analysis.html")
    
    return perf
```

---

## 4. 数据工作流教程 (Data Workflow Tutorials)

### 4.1 教程 8: 构建 Parquet 数据目录

**目标**: 学习如何构建和管理 Parquet 数据目录

**完整代码**:

```python
# 03_data_workflow/build_catalog.py
from pathlib import Path
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader

def build_catalog():
    """构建 Parquet 数据目录"""
    
    # 1. 创建目录
    catalog_path = Path("./catalog")
    catalog_path.mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(path=catalog_path)
    
    # 2. 初始化数据加载器
    loader = DatabentoDataLoader(api_key="your_databento_api_key")
    
    # 3. 加载 K 线数据
    print("Loading bars...")
    bars = loader.load_bars(
        instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
        schema="ohlcv-1m",
        start="2024-01-01",
        end="2024-12-31",
    )
    catalog.write_bars(bars)
    print(f"  Written {len(bars)} bars")
    
    # 4. 加载报价数据
    print("Loading quotes...")
    quotes = loader.load_quote_ticks(
        instrument_ids=["BTCUSDT.BINANCE"],
        start="2024-01-01",
        end="2024-06-30",
    )
    catalog.write_quote_ticks(quotes)
    print(f"  Written {len(quotes)} quotes")
    
    # 5. 加载成交数据
    print("Loading trades...")
    trades = loader.load_trade_ticks(
        instrument_ids=["BTCUSDT.BINANCE"],
        start="2024-01-01",
        end="2024-06-30",
    )
    catalog.write_trade_ticks(trades)
    print(f"  Written {len(trades)} trades")
    
    # 6. 加载工具定义
    print("Loading instruments...")
    instruments = loader.load_instruments(
        instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
    )
    catalog.write_instruments(instruments)
    print(f"  Written {len(instruments)} instruments")
    
    # 7. 验证目录
    print("\n" + "="*50)
    print("CATALOG SUMMARY")
    print("="*50)
    print(f"Bars: {len(catalog.bars(instrument_ids=['BTCUSDT.BINANCE']))}")
    print(f"Quotes: {len(catalog.quote_ticks(instrument_ids=['BTCUSDT.BINANCE']))}")
    print(f"Trades: {len(catalog.trade_ticks(instrument_ids=['BTCUSDT.BINANCE']))}")
    print(f"Instruments: {len(catalog.instruments())}")
    
    return catalog
```

### 4.2 教程 9: 从 CSV 导入数据

**目标**: 学习如何从 CSV 文件导入自定义数据

**完整代码**:

```python
# 03_data_workflow/import_from_csv.py
import pandas as pd
from pathlib import Path
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.data import Bar, QuoteTick, TradeTick
from nautilus_trader.model.identifiers import InstrumentId, BarType
from nautilus_trader.core.datetime import dt_to_unix_nanos

def import_bars_from_csv(csv_path: str, catalog_path: str):
    """从 CSV 导入 K 线数据"""
    
    # 读取 CSV
    df = pd.read_csv(csv_path)
    print(f"Loaded {len(df)} rows from CSV")
    
    # 创建目录
    catalog = ParquetDataCatalog(path=catalog_path)
    
    # 转换为 Bar 对象
    bars = []
    for _, row in df.iterrows():
        bar = Bar(
            bar_type=BarType.from_str("BTCUSDT.BINANCE-1-MINUTE-LAST-INTERNAL"),
            open=Price.from_str(str(row["open"])),
            high=Price.from_str(str(row["high"])),
            low=Price.from_str(str(row["low"])),
            close=Price.from_str(str(row["close"])),
            volume=Quantity.from_str(str(row["volume"])),
            ts_event=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
            ts_init=dt_to_unix_nanos(pd.Timestamp(row["timestamp"])),
        )
        bars.append(bar)
    
    # 写入目录
    catalog.write_bars(bars)
    print(f"Written {len(bars)} bars to catalog")
    
    return bars

def import_quotes_from_csv(csv_path: str, catalog_path: str):
    """从 CSV 导入报价数据"""
    
    df = pd.read_csv(csv_path)
    catalog = ParquetDataCatalog(path=catalog_path)
    
    quotes = []
    for _, row in df.iterrows():
        quote = QuoteTick(
            instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
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
    
    return quotes

def import_trades_from_csv(csv_path: str, catalog_path: str):
    """从 CSV 导入成交数据"""
    
    df = pd.read_csv(csv_path)
    catalog = ParquetDataCatalog(path=catalog_path)
    
    trades = []
    for _, row in df.iterrows():
        trade = TradeTick(
            instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
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
    
    return trades
```

### 4.3 教程 10: 查询数据目录

**目标**: 学习如何查询和过滤数据目录

**完整代码**:

```python
# 03_data_workflow/query_catalog.py
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.core.data import DataType
import pandas as pd

def query_catalog():
    """查询数据目录"""
    
    catalog = ParquetDataCatalog(path="./catalog")
    
    # 1. 查询 K 线
    print("\n" + "="*50)
    print("BARS QUERY")
    print("="*50)
    bars = catalog.bars(
        instrument_ids=["BTCUSDT.BINANCE"],
        bar_types=["1-HOUR"],
        start="2024-01-01",
        end="2024-12-31",
    )
    print(f"Found {len(bars)} bars")
    if bars:
        print(f"First bar: {bars[0]}")
        print(f"Last bar: {bars[-1]}")
    
    # 2. 查询报价
    print("\n" + "="*50)
    print("QUOTES QUERY")
    print("="*50)
    quotes = catalog.quote_ticks(
        instrument_ids=["BTCUSDT.BINANCE"],
        start="2024-01-01",
        end="2024-01-31",
    )
    print(f"Found {len(quotes)} quotes")
    
    # 3. 查询成交
    print("\n" + "="*50)
    print("TRADES QUERY")
    print("="*50)
    trades = catalog.trade_ticks(
        instrument_ids=["BTCUSDT.BINANCE"],
        start="2024-01-01",
        end="2024-01-31",
    )
    print(f"Found {len(trades)} trades")
    
    # 4. 查询工具
    print("\n" + "="*50)
    print("INSTRUMENTS QUERY")
    print("="*50)
    instruments = catalog.instruments(
        instrument_ids=["BTCUSDT.BINANCE"],
    )
    print(f"Found {len(instruments)} instruments")
    for inst in instruments:
        print(f"  {inst.id}: precision={inst.price_precision}/{inst.size_precision}")
    
    # 5. 查询自定义数据
    print("\n" + "="*50)
    print("CUSTOM DATA QUERY")
    print("="*50)
    custom_data = catalog.query(
        data_type=DataType(GreeksData),
        instrument_ids=["BTC-29DEC23-40000-C.BYBIT"],
        start="2024-01-01",
        end="2024-12-31",
    )
    print(f"Found {len(custom_data)} custom data points")
    
    # 6. 转换为 DataFrame
    print("\n" + "="*50)
    print("DATAFRAME CONVERSION")
    print("="*50)
    df = pd.DataFrame([
        {
            "timestamp": pd.Timestamp(bar.ts_event),
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        }
        for bar in bars[:100]
    ])
    print(df.head())
    
    return catalog
```

### 4.4 教程 11: 重采样 K 线

**目标**: 学习如何将 K 线重采样到不同时间框架

**完整代码**:

```python
# 03_data_workflow/resample_bars.py
import pandas as pd
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.data import Bar
from nautilus_trader.model.identifiers import BarType

def resample_bars(
    catalog_path: str,
    instrument_id: str,
    source_bar_type: str,
    target_bar_type: str,
) -> list[Bar]:
    """重采样 K 线"""
    
    catalog = ParquetDataCatalog(path=catalog_path)
    
    # 1. 加载源数据
    print(f"Loading {source_bar_type} bars...")
    bars = catalog.bars(
        instrument_ids=[instrument_id],
        bar_types=[source_bar_type],
    )
    print(f"  Loaded {len(bars)} bars")
    
    # 2. 转换为 DataFrame
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
    
    # 3. 设置时间索引
    df["timestamp"] = pd.to_datetime(df["ts_event"], unit="ns")
    df = df.set_index("timestamp")
    
    # 4. 重采样
    print(f"Resampling to {target_bar_type}...")
    resampled = df.resample("1H").agg({
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }).dropna()
    
    # 5. 转换回 Bar 对象
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
    
    print(f"  Created {len(new_bars)} resampled bars")
    
    # 6. 写入目录
    catalog.write_bars(new_bars)
    print(f"  Written to catalog")
    
    return new_bars

# 使用示例
if __name__ == "__main__":
    resampled = resample_bars(
        catalog_path="./catalog",
        instrument_id="BTCUSDT.BINANCE",
        source_bar_type="1-MINUTE",
        target_bar_type="1-HOUR",
    )
```

---

## 5. 策略开发教程 (Strategy Development Tutorials)

### 5.1 教程 12: 创建基础策略

**目标**: 学习创建第一个完整策略

**完整代码**:

```python
# 04_strategy_dev/basic_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide, PositionSide
from nautilus_trader.indicators import EMA

class BasicStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    ema_period: int = 20

class BasicStrategy(Strategy):
    def __init__(self, config: BasicStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.ema = None
        self.position = None
        self.bar_count = 0
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.ema = EMA(self.config.ema_period)
        self.subscribe_bars(self.config.bar_type)
        self.log.info(f"Strategy started: {self.instrument.id}")
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("Strategy stopped")
    
    def on_bar(self, bar: Bar) -> None:
        self.bar_count += 1
        self.ema.handle_bar(bar)
        
        # 等待指标预热
        if self.bar_count < self.config.ema_period:
            return
        
        # 获取当前持仓
        self.position = self.cache.position_for_strategy(self.id)
        
        # 交易逻辑
        if self.ema.value < float(bar.close):
            # 价格在 EMA 上方 - 做多信号
            if not self.position or self.position.side == PositionSide.SHORT:
                self._enter_long()
        else:
            # 价格在 EMA 下方 - 做空信号
            if not self.position or self.position.side == PositionSide.LONG:
                self._enter_short()
    
    def _enter_long(self) -> None:
        self.cancel_all_orders()
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["ENTRY_LONG"],
        )
        self.submit_order(order)
        self.log.info(f"Long entry at {bar.close}")
    
    def _enter_short(self) -> None:
        self.cancel_all_orders()
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["ENTRY_SHORT"],
        )
        self.submit_order(order)
        self.log.info(f"Short entry at {bar.close}")
    
    def on_position_opened(self, event: PositionOpened) -> None:
        self.log.info(f"Position opened: {event.position_id}")
    
    def on_position_closed(self, event: PositionClosed) -> None:
        self.log.info(f"Position closed: {event.position_id}, PnL: {event.realized_pnl}")
    
    def on_order_filled(self, event: OrderFilled) -> None:
        self.log.info(f"Order filled: {event.client_order_id}, price: {event.last_px}")
```

### 5.2 教程 13: EMA 交叉策略

**目标**: 学习实现经典的 EMA 交叉策略

**完整代码**:

```python
# 04_strategy_dev/ema_cross_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide, PositionSide
from nautilus_trader.indicators import EMA

class EMACrossStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    stop_loss_pct: Decimal = Decimal("0.02")
    take_profit_pct: Decimal = Decimal("0.04")

class EMACrossStrategy(Strategy):
    def __init__(self, config: EMACrossStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.fast_ema = None
        self.slow_ema = None
        self.position = None
        self.bar_count = 0
        self.entry_price = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.fast_ema = EMA(self.config.fast_ema_period)
        self.slow_ema = EMA(self.config.slow_ema_period)
        self.subscribe_bars(self.config.bar_type)
        self.log.info(f"EMA Cross Strategy started")
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("EMA Cross Strategy stopped")
    
    def on_bar(self, bar: Bar) -> None:
        self.bar_count += 1
        
        # 更新指标
        self.fast_ema.handle_bar(bar)
        self.slow_ema.handle_bar(bar)
        
        # 等待指标预热
        if self.bar_count < self.config.slow_ema_period:
            return
        
        # 获取当前持仓
        self.position = self.cache.position_for_strategy(self.id)
        
        # 检查交叉信号
        fast_value = self.fast_ema.value
        slow_value = self.slow_ema.value
        
        if fast_value > slow_value:
            # 金叉 - 做多信号
            if not self.position or self.position.side == PositionSide.SHORT:
                self._enter_long(bar)
        elif fast_value < slow_value:
            # 死叉 - 做空信号
            if not self.position or self.position.side == PositionSide.LONG:
                self._enter_short(bar)
        
        # 检查止损/止盈
        if self.position:
            self._check_stop_loss(bar)
            self._check_take_profit(bar)
    
    def _enter_long(self, bar: Bar) -> None:
        self.cancel_all_orders()
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["EMA_CROSS_LONG"],
        )
        self.submit_order(order)
        self.entry_price = float(bar.close)
        self.log.info(f"Long entry at {bar.close}")
    
    def _enter_short(self, bar: Bar) -> None:
        self.cancel_all_orders()
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["EMA_CROSS_SHORT"],
        )
        self.submit_order(order)
        self.entry_price = float(bar.close)
        self.log.info(f"Short entry at {bar.close}")
    
    def _check_stop_loss(self, bar: Bar) -> None:
        if not self.entry_price:
            return
        
        if self.position.side == PositionSide.LONG:
            stop_price = self.entry_price * (1 - float(self.config.stop_loss_pct))
            if float(bar.close) <= stop_price:
                self._exit_position()
                self.log.info(f"Stop loss triggered at {bar.close}")
        else:
            stop_price = self.entry_price * (1 + float(self.config.stop_loss_pct))
            if float(bar.close) >= stop_price:
                self._exit_position()
                self.log.info(f"Stop loss triggered at {bar.close}")
    
    def _check_take_profit(self, bar: Bar) -> None:
        if not self.entry_price:
            return
        
        if self.position.side == PositionSide.LONG:
            tp_price = self.entry_price * (1 + float(self.config.take_profit_pct))
            if float(bar.close) >= tp_price:
                self._exit_position()
                self.log.info(f"Take profit triggered at {bar.close}")
        else:
            tp_price = self.entry_price * (1 - float(self.config.take_profit_pct))
            if float(bar.close) <= tp_price:
                self._exit_position()
                self.log.info(f"Take profit triggered at {bar.close}")
    
    def _exit_position(self) -> None:
        self.cancel_all_orders()
        if self.position and self.position.is_open:
            if self.position.side == PositionSide.LONG:
                order = self.order_factory.market(
                    instrument_id=self.instrument.id,
                    order_side=OrderSide.SELL,
                    quantity=self.position.quantity,
                    reduce_only=True,
                    tags=["EXIT"],
                )
            else:
                order = self.order_factory.market(
                    instrument_id=self.instrument.id,
                    order_side=OrderSide.BUY,
                    quantity=self.position.quantity,
                    reduce_only=True,
                    tags=["EXIT"],
                )
            self.submit_order(order)
```

### 5.3 教程 14: 网格交易策略

**目标**: 学习实现网格交易策略

**完整代码**:

```python
# 04_strategy_dev/grid_trading_strategy.py
from decimal import Decimal
from typing import List
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.orders import LimitOrder

class GridTradingStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    grid_levels: int = 10
    grid_spacing_pct: Decimal = Decimal("0.01")
    order_size: Decimal
    upper_price: Decimal
    lower_price: Decimal

class GridTradingStrategy(Strategy):
    def __init__(self, config: GridTradingStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.grid_orders: List[LimitOrder] = []
        self.grid_levels: List[Decimal] = []
        self.active_orders: dict = {}
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        
        # 计算网格价格
        self._calculate_grid_levels()
        
        # 订阅报价
        self.subscribe_quote_ticks(self.instrument.id)
        
        # 放置初始网格订单
        self._place_grid_orders()
        
        self.log.info(f"Grid Trading Strategy started with {len(self.grid_levels)} levels")
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("Grid Trading Strategy stopped")
    
    def _calculate_grid_levels(self) -> None:
        """计算网格价格水平"""
        price_range = self.config.upper_price - self.config.lower_price
        step = price_range / self.config.grid_levels
        
        self.grid_levels = [
            self.config.lower_price + step * i
            for i in range(self.config.grid_levels + 1)
        ]
        
        self.log.info(f"Grid levels: {self.grid_levels[0]} to {self.grid_levels[-1]}")
    
    def _place_grid_orders(self) -> None:
        """放置网格订单"""
        self.cancel_all_orders()
        self.grid_orders = []
        self.active_orders = {}
        
        mid_price = (self.config.upper_price + self.config.lower_price) / 2
        
        for i, price in enumerate(self.grid_levels):
            if price < mid_price:
                # 下方挂买单
                order = self.order_factory.limit(
                    instrument_id=self.instrument.id,
                    order_side=OrderSide.BUY,
                    quantity=self.instrument.make_qty(self.config.order_size),
                    price=self.instrument.make_price(price),
                    post_only=True,
                    tags=[f"GRID_BUY_{i}"],
                )
                self.submit_order(order)
                self.grid_orders.append(order)
                self.active_orders[order.client_order_id] = "BUY"
            elif price > mid_price:
                # 上方挂卖单
                order = self.order_factory.limit(
                    instrument_id=self.instrument.id,
                    order_side=OrderSide.SELL,
                    quantity=self.instrument.make_qty(self.config.order_size),
                    price=self.instrument.make_price(price),
                    post_only=True,
                    tags=[f"GRID_SELL_{i}"],
                )
                self.submit_order(order)
                self.grid_orders.append(order)
                self.active_orders[order.client_order_id] = "SELL"
        
        self.log.info(f"Placed {len(self.grid_orders)} grid orders")
    
    def on_quote_tick(self, tick: QuoteTick) -> None:
        """报价更新时重新平衡网格"""
        mid_price = (float(tick.bid_price) + float(tick.ask_price)) / 2
        self._rebalance_grid(Decimal(str(mid_price)))
    
    def _rebalance_grid(self, current_price: Decimal) -> None:
        """重新平衡网格订单"""
        # 检查是否需要重新放置订单
        # 简化版本：当价格移动超过一个网格间距时重新平衡
        grid_spacing = (self.config.upper_price - self.config.lower_price) / self.config.grid_levels
        
        # 实现重新平衡逻辑
        # ...
    
    def on_order_filled(self, event: OrderFilled) -> None:
        """订单成交时放置对立订单"""
        if event.client_order_id in self.active_orders:
            side = self.active_orders[event.client_order_id]
            
            if side == "BUY":
                # 买单成交后，在上方放置卖单
                self._place_opposite_order(event.price, "SELL")
            else:
                # 卖单成交后，在下方放置买单
                self._place_opposite_order(event.price, "BUY")
    
    def _place_opposite_order(self, fill_price: Decimal, side: str) -> None:
        """放置对立订单"""
        # 计算下一个网格价格
        grid_spacing = (self.config.upper_price - self.config.lower_price) / self.config.grid_levels
        
        if side == "SELL":
            next_price = fill_price + grid_spacing
            order_side = OrderSide.SELL
        else:
            next_price = fill_price - grid_spacing
            order_side = OrderSide.BUY
        
        # 检查价格是否在网格范围内
        if self.config.lower_price <= next_price <= self.config.upper_price:
            order = self.order_factory.limit(
                instrument_id=self.instrument.id,
                order_side=order_side,
                quantity=self.instrument.make_qty(self.config.order_size),
                price=self.instrument.make_price(next_price),
                post_only=True,
                tags=[f"GRID_FOLLOWUP_{side}"],
            )
            self.submit_order(order)
```

### 5.4 教程 15: 做市商策略

**目标**: 学习实现做市商策略

**完整代码**:

```python
# 04_strategy_dev/market_maker_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import OrderBookDelta
from nautilus_trader.model.enums import OrderSide

class MarketMakerStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    spread_bps: Decimal = Decimal("10")  # 10 基点
    order_size: Decimal
    max_inventory: Decimal
    inventory_skew_factor: Decimal = Decimal("0.5")

class MarketMakerStrategy(Strategy):
    def __init__(self, config: MarketMakerStrategyConfig) -> None:
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
        self.log.info("Market Maker Strategy started")
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("Market Maker Strategy stopped")
    
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
        spread = float(self.mid_price) * float(self.config.spread_bps) / 10000
        bid_price = float(self.mid_price) - spread / 2
        ask_price = float(self.mid_price) + spread / 2
        
        # 库存偏斜调整
        inventory_skew = float(self.inventory) * float(self.config.inventory_skew_factor)
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
            price=self.instrument.make_price(Decimal(str(bid_price))),
            post_only=True,
            tags=["MM_BID"],
        )
        self.submit_order(self.bid_order)
        
        self.ask_order = self.order_factory.limit(
            instrument_id=self.instrument.id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.config.order_size),
            price=self.instrument.make_price(Decimal(str(ask_price))),
            post_only=True,
            tags=["MM_ASK"],
        )
        self.submit_order(self.ask_order)
    
    def on_order_filled(self, event: OrderFilled) -> None:
        """订单成交更新库存"""
        if event.order_side == OrderSide.BUY:
            self.inventory += event.last_qty
        else:
            self.inventory -= event.last_qty
        
        self.log.info(f"Inventory updated: {self.inventory}")
        
        # 更新报价
        self._update_quotes()
```

### 5.5 教程 16: 多时间框架策略

**目标**: 学习实现多时间框架策略

**完整代码**:

```python
# 04_strategy_dev/multi_timeframe_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.indicators import EMA

class MultiTimeframeStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type_1m: BarType
    bar_type_5m: BarType
    bar_type_1h: BarType
    trade_size: Decimal

class MultiTimeframeStrategy(Strategy):
    def __init__(self, config: MultiTimeframeStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        
        # 各时间框架的指标
        self.ema_1m = EMA(10)
        self.ema_5m = EMA(20)
        self.ema_1h = EMA(50)
        
        # 信号状态
        self.signal_1m = None
        self.signal_5m = None
        self.signal_1h = None
        
        self.position = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        
        # 订阅多个时间框架
        self.subscribe_bars(self.config.bar_type_1m)
        self.subscribe_bars(self.config.bar_type_5m)
        self.subscribe_bars(self.config.bar_type_1h)
        
        self.log.info("Multi-Timeframe Strategy started")
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("Multi-Timeframe Strategy stopped")
    
    def on_bar(self, bar: Bar) -> None:
        # 根据时间框架处理
        if bar.bar_type == self.config.bar_type_1m:
            self.ema_1m.handle_bar(bar)
            self.signal_1m = self.ema_1m.value > float(bar.close)
            self._check_trading_signal()
        
        elif bar.bar_type == self.config.bar_type_5m:
            self.ema_5m.handle_bar(bar)
            self.signal_5m = self.ema_5m.value > float(bar.close)
            self._check_trading_signal()
        
        elif bar.bar_type == self.config.bar_type_1h:
            self.ema_1h.handle_bar(bar)
            self.signal_1h = self.ema_1h.value > float(bar.close)
            self._check_trading_signal()
    
    def _check_trading_signal(self) -> None:
        """检查交易信号"""
        # 需要所有时间框架信号
        if None in [self.signal_1m, self.signal_5m, self.signal_1h]:
            return
        
        # 获取当前持仓
        self.position = self.cache.position_for_strategy(self.id)
        
        # 多时间框架确认信号
        all_bullish = all([self.signal_1m, self.signal_5m, self.signal_1h])
        all_bearish = not any([self.signal_1m, self.signal_5m, self.signal_1h])
        
        if all_bullish and not self.position:
            self._enter_long()
        elif all_bearish and self.position:
            self._exit_position()
    
    def _enter_long(self) -> None:
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
            tags=["MTF_LONG"],
        )
        self.submit_order(order)
        self.log.info("Multi-timeframe long entry")
    
    def _exit_position(self) -> None:
        self.cancel_all_orders()
        self.log.info("Multi-timeframe exit")
```

### 5.6 教程 17: 期权策略

**目标**: 学习实现期权 Delta 对冲策略

**完整代码**:

```python
# 04_strategy_dev/options_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import OptionGreeks
from nautilus_trader.model.enums import OrderSide

class OptionsStrategyConfig(StrategyConfig):
    underlying_id: InstrumentId
    option_id: InstrumentId
    target_delta: Decimal = Decimal("0")  # Delta 中性
    rebalance_threshold: Decimal = Decimal("0.05")

class DeltaHedgingStrategy(Strategy):
    def __init__(self, config: OptionsStrategyConfig) -> None:
        super().__init__(config)
        self.underlying = None
        self.option = None
        self.current_delta = Decimal("0")
        self.hedge_position = Decimal("0")
        self.option_quantity = Decimal("0")
    
    def on_start(self) -> None:
        self.underlying = self.cache.instrument(self.config.underlying_id)
        self.option = self.cache.instrument(self.config.option_id)
        
        # 订阅期权 Greeks
        self.subscribe_option_greeks(self.config.option_id)
        self.subscribe_quote_ticks(self.config.underlying_id)
        
        self.log.info("Delta Hedging Strategy started")
    
    def on_stop(self) -> None:
        self.cancel_all_orders()
        self.log.info("Delta Hedging Strategy stopped")
    
    def on_option_greeks(self, greeks: OptionGreeks) -> None:
        """Greeks 更新"""
        self.current_delta = Decimal(str(greeks.delta))
        self._rebalance_hedge()
    
    def _rebalance_hedge(self) -> None:
        """重新平衡对冲"""
        if self.option_quantity == 0:
            return
        
        # 计算目标对冲头寸
        # 期权 Delta * 期权数量 + 标的头寸 = 目标 Delta
        target_hedge = -self.current_delta * self.option_quantity
        
        # 检查是否需要重新平衡
        if abs(target_hedge - self.hedge_position) > self.config.rebalance_threshold:
            hedge_qty = target_hedge - self.hedge_position
            
            if hedge_qty > 0:
                order = self.order_factory.market(
                    instrument_id=self.underlying.id,
                    order_side=OrderSide.BUY,
                    quantity=self.underlying.make_qty(abs(hedge_qty)),
                    tags=["DELTA_HEDGE_BUY"],
                )
            else:
                order = self.order_factory.market(
                    instrument_id=self.underlying.id,
                    order_side=OrderSide.SELL,
                    quantity=self.underlying.make_qty(abs(hedge_qty)),
                    tags=["DELTA_HEDGE_SELL"],
                )
            
            self.submit_order(order)
            self.hedge_position = target_hedge
            self.log.info(f"Delta hedge rebalanced: {hedge_qty}")
```

---

## 6. 实盘交易教程 (Live Trading Tutorials)

### 6.1 教程 18: 配置实盘节点

**目标**: 学习配置实盘交易节点

**完整代码**:

```python
# 05_live_trading/configure_live_node.py
from decimal import Decimal
from nautilus_trader.live.node import TradingNode
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.config import (
    CacheConfig,
    DatabaseConfig,
    LoggingConfig,
    RiskEngineConfig,
    MessageBusConfig,
)
from nautilus_trader.adapters.binance.config import BinanceLiveConfig
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model import Money
import os

def configure_live_node():
    """配置实盘节点"""
    
    config = TradingNodeConfig(
        trader_id="LIVE-TRADER-001",
        run_id="live-2024-001",
        
        # 缓存配置 (使用 Redis)
        cache=CacheConfig(
            database=DatabaseConfig(
                type="redis",
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
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
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
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
            EMACrossStrategyConfig(
                instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
                bar_type=BarType.from_str("BTCUSDT.BINANCE-1-MINUTE"),
                fast_ema_period=10,
                slow_ema_period=20,
                trade_size=Decimal("0.01"),
                order_id_tag="001",
            ),
        ],
    )
    
    return config
```

### 6.2 教程 19: 启动实盘交易

**目标**: 学习启动和管理实盘交易

**完整代码**:

```python
# 05_live_trading/run_live_trading.py
import asyncio
import signal
import sys
from nautilus_trader.live.node import TradingNode

class TradingBot:
    def __init__(self, config):
        self.config = config
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
        self.node = TradingNode(config=self.config)
        self.setup_signal_handlers()
        
        try:
            print("Starting trading node...")
            await self.node.run_async()
            
            print("Trading node running. Press Ctrl+C to stop...")
            while not self._shutdown:
                await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error: {e}")
            raise
        finally:
            await self.stop()
    
    async def stop(self):
        """停止交易节点"""
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

### 6.3 教程 20: 使用沙箱测试

**目标**: 学习使用沙箱环境测试策略

**完整代码**:

```python
# 05_live_trading/sandbox_testing.py
from decimal import Decimal
from nautilus_trader.live.node import TradingNode
from nautilus_trader.live.config import TradingNodeConfig
from nautilus_trader.adapters.sandbox.config import SandboxLiveConfig
from nautilus_trader.adapters.sandbox.fill_model import FillModel
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model import Money

def run_sandbox_test():
    """运行沙箱测试"""
    
    config = TradingNodeConfig(
        trader_id="SANDBOX-001",
        run_id="sandbox-test-001",
        
        # 沙箱配置
        venues=[
            SandboxLiveConfig(
                instrument_ids=["BTCUSDT.SANDBOX"],
                account_type=AccountType.MARGIN,
                starting_balances=[Money(1_000_000, "USDT")],
                
                # 填充模型配置
                fill_model=FillModel(
                    prob_fill_on_limit=0.2,    # 限价单成交概率 20%
                    prob_fill_on_stop=0.9,     # 止损单成交概率 90%
                    prob_slippage=0.1,         # 滑点概率 10%
                    slippage_range=(0.0001, 0.001),  # 滑点范围
                ),
                
                # 延迟模拟
                latency_model={
                    "mean_ms": 50,
                    "std_ms": 10,
                },
            ),
        ],
        
        # 策略配置
        strategies=[
            EMACrossStrategyConfig(
                instrument_id=InstrumentId.from_str("BTCUSDT.SANDBOX"),
                bar_type=BarType.from_str("BTCUSDT.SANDBOX-1-MINUTE"),
                trade_size=Decimal("0.01"),
                order_id_tag="001",
            ),
        ],
    )
    
    node = TradingNode(config=config)
    
    print("Starting sandbox test...")
    print("Using real market data with virtual execution")
    print("No real orders will be placed")
    
    node.run()
```

---

## 7. 风险管理教程 (Risk Management Tutorials)

### 7.1 教程 21: 配置风险引擎

**目标**: 学习配置风险引擎参数

**完整代码**:

```python
# 06_risk_management/configure_risk_engine.py
from decimal import Decimal
from nautilus_trader.config import RiskEngineConfig
from nautilus_trader.model import Money, Quantity

def configure_risk_engine():
    """配置风险引擎"""
    
    config = RiskEngineConfig(
        # 是否绕过风险检查
        bypass=False,
        
        # 订单级别限制
        max_notional_per_order=Money(100_000, "USDT"),
        max_quantity_per_order=Quantity.from_str("10.0"),
        
        # 持仓级别限制
        max_notional_per_position=Money(500_000, "USDT"),
        max_quantity_per_position=Quantity.from_str("50.0"),
        
        # 账户级别限制
        max_open_orders=50,
        max_open_positions=20,
        
        # 日交易限制
        max_daily_turnover=Money(1_000_000, "USDT"),
        max_daily_trades=100,
        
        # 损失限制
        max_daily_loss=Money(10_000, "USDT"),
        max_drawdown_pct=Decimal("0.05"),  # 5%
    )
    
    return config
```

### 7.2 教程 22: 实现止损逻辑

**目标**: 学习在策略中实现止损

**完整代码**:

```python
# 06_risk_management/stop_loss_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.enums import OrderSide, PositionSide

class StopLossStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    stop_loss_pct: Decimal = Decimal("0.02")
    take_profit_pct: Decimal = Decimal("0.04")
    trailing_stop_pct: Decimal = Decimal("0.015")

class StopLossStrategy(Strategy):
    def __init__(self, config: StopLossStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.position = None
        self.entry_price = None
        self.highest_price = None
        self.lowest_price = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
    
    def on_bar(self, bar: Bar) -> None:
        # 更新极值
        if self.position and self.position.is_open:
            if self.position.side == PositionSide.LONG:
                if self.highest_price is None or float(bar.high) > float(self.highest_price):
                    self.highest_price = bar.high
            else:
                if self.lowest_price is None or float(bar.low) < float(self.lowest_price):
                    self.lowest_price = bar.low
            
            # 检查追踪止损
            self._check_trailing_stop(bar)
    
    def on_position_opened(self, event: PositionOpened) -> None:
        self.position = self.cache.position(event.position_id)
        self.entry_price = self.position.avg_px_open
        self.highest_price = self.entry_price
        self.lowest_price = self.entry_price
        
        # 放置初始止损单
        self._place_stop_order()
    
    def _place_stop_order(self) -> None:
        """放置止损单"""
        if not self.position or not self.entry_price:
            return
        
        if self.position.side == PositionSide.LONG:
            stop_price = self.entry_price * (1 - self.config.stop_loss_pct)
            order_side = OrderSide.SELL
        else:
            stop_price = self.entry_price * (1 + self.config.stop_loss_pct)
            order_side = OrderSide.BUY
        
        order = self.order_factory.stop_market(
            instrument_id=self.position.instrument_id,
            order_side=order_side,
            quantity=self.position.quantity,
            trigger_price=stop_price,
            reduce_only=True,
            tags=["STOP_LOSS"],
        )
        self.submit_order(order)
    
    def _check_trailing_stop(self, bar: Bar) -> None:
        """检查追踪止损"""
        if not self.position or not self.entry_price:
            return
        
        trigger_price = None
        
        if self.position.side == PositionSide.LONG:
            # 多头追踪止损
            if self.highest_price:
                trigger_price = self.highest_price * (1 - self.config.trailing_stop_pct)
            if float(bar.close) <= float(trigger_price):
                self._exit_position()
        else:
            # 空头追踪止损
            if self.lowest_price:
                trigger_price = self.lowest_price * (1 + self.config.trailing_stop_pct)
            if float(bar.close) >= float(trigger_price):
                self._exit_position()
    
    def _exit_position(self) -> None:
        """平仓"""
        self.cancel_all_orders()
        if self.position and self.position.is_open:
            if self.position.side == PositionSide.LONG:
                order = self.order_factory.market(
                    instrument_id=self.position.instrument_id,
                    order_side=OrderSide.SELL,
                    quantity=self.position.quantity,
                    reduce_only=True,
                )
            else:
                order = self.order_factory.market(
                    instrument_id=self.position.instrument_id,
                    order_side=OrderSide.BUY,
                    quantity=self.position.quantity,
                    reduce_only=True,
                )
            self.submit_order(order)
```

### 7.3 教程 23: 仓位管理

**目标**: 学习实现动态仓位管理

**完整代码**:

```python
# 06_risk_management/position_sizing_strategy.py
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig

class PositionSizingStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    risk_per_trade_pct: Decimal = Decimal("0.01")  # 每笔交易风险 1%
    max_position_pct: Decimal = Decimal("0.20")    # 最大持仓 20%
    stop_loss_pct: Decimal = Decimal("0.02")

class PositionSizingStrategy(Strategy):
    def __init__(self, config: PositionSizingStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_bars(self.config.bar_type)
    
    def calculate_position_size(self, stop_loss_distance: Decimal) -> Quantity:
        """计算仓位大小"""
        
        # 获取账户余额
        account = self.portfolio.account(venue=self.instrument.venue)
        account_value = account.value()
        
        # 计算风险金额
        risk_amount = account_value * self.config.risk_per_trade_pct
        
        # 根据止损距离计算仓位
        position_value = risk_amount / stop_loss_distance
        
        # 应用最大持仓限制
        max_position_value = account_value * self.config.max_position_pct
        position_value = min(position_value, max_position_value)
        
        # 转换为数量
        quantity = position_value / float(self.instrument.make_price(1.0))
        
        return self.instrument.make_qty(quantity)
    
    def on_signal(self, signal) -> None:
        """信号处理"""
        # 计算止损距离
        stop_loss_distance = float(self.instrument.make_price(1.0)) * float(self.config.stop_loss_pct)
        
        # 计算仓位大小
        quantity = self.calculate_position_size(Decimal(str(stop_loss_distance)))
        
        # 提交订单
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=signal.side,
            quantity=quantity,
        )
        self.submit_order(order)
```

---

## 8. 高级主题教程 (Advanced Topic Tutorials)

### 8.1 教程 24: 自定义数据类

**目标**: 学习创建和使用自定义数据类型

**完整代码**:

```python
# 07_advanced/custom_data.py
from nautilus_trader.core.data import Data
from nautilus_trader.model.custom import customdataclass
from nautilus_trader.model.identifiers import InstrumentId

@customdataclass
class GreeksData(Data):
    """期权 Greeks 数据"""
    instrument_id: InstrumentId
    delta: float = 0.0
    gamma: float = 0.0
    vega: float = 0.0
    theta: float = 0.0
    rho: float = 0.0

@customdataclass
class SignalData(Data):
    """交易信号数据"""
    instrument_id: InstrumentId
    signal_type: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 - 1.0
    target_price: float = 0.0

# 使用示例
greeks = GreeksData(
    instrument_id=InstrumentId.from_str("BTC-29DEC23-40000-C.BYBIT"),
    delta=0.5,
    gamma=0.02,
    vega=0.1,
    theta=-0.05,
    rho=0.01,
    ts_event=1630000000000000000,
    ts_init=1630000000000000000,
)
```

### 8.2 教程 25: 自定义指标

**目标**: 学习创建自定义技术指标

**完整代码**:

```python
# 07_advanced/custom_indicator.py
from nautilus_trader.indicators.base import Indicator
from nautilus_trader.model.data import Bar

class RSI(Indicator):
    """相对强弱指标"""
    
    def __init__(self, period: int = 14):
        super().__init__()
        self.period = period
        self.gains: list[float] = []
        self.losses: list[float] = []
        self.value: float | None = None
    
    def handle_bar(self, bar: Bar) -> None:
        if len(self._cache) == 0:
            self._cache.append(bar.close)
            return
        
        change = float(bar.close) - float(self._cache[-1])
        self._cache.append(bar.close)
        
        if change > 0:
            self.gains.append(change)
            self.losses.append(0)
        else:
            self.gains.append(0)
            self.losses.append(abs(change))
        
        if len(self.gains) >= self.period:
            self._calculate()
    
    def _calculate(self) -> None:
        avg_gain = sum(self.gains[-self.period:]) / self.period
        avg_loss = sum(self.losses[-self.period:]) / self.period
        
        if avg_loss == 0:
            self.value = 100.0
        else:
            rs = avg_gain / avg_loss
            self.value = 100 - (100 / (1 + rs))
        
        self._updated = True
    
    def reset(self) -> None:
        super().reset()
        self.gains.clear()
        self.losses.clear()
        self.value = None

class MACD(Indicator):
    """移动平均收敛散度指标"""
    
    def __init__(self, fast_period: int = 12, slow_period: int = 26, signal_period: int = 9):
        super().__init__()
        self.fast_ema = EMA(fast_period)
        self.slow_ema = EMA(slow_period)
        self.signal_ema = EMA(signal_period)
        self.macd_line: float | None = None
        self.signal_line: float | None = None
        self.histogram: float | None = None
    
    def handle_bar(self, bar: Bar) -> None:
        self.fast_ema.handle_bar(bar)
        self.slow_ema.handle_bar(bar)
        
        if self.fast_ema.value and self.slow_ema.value:
            self.macd_line = self.fast_ema.value - self.slow_ema.value
            self.signal_ema.handle_value(self.macd_line)
            
            if self.signal_ema.value:
                self.signal_line = self.signal_ema.value
                self.histogram = self.macd_line - self.signal_line
                self._updated = True
```

### 8.3 教程 26: 执行算法

**目标**: 学习实现 TWAP 执行算法

**完整代码**:

```python
# 07_advanced/twap_algorithm.py
from nautilus_trader.execution.algorithm import ExecAlgorithm
from nautilus_trader.model.order import Order
from nautilus_trader.model.enums import OrderSide

class TWAPExecAlgorithm(ExecAlgorithm):
    """时间加权平均价格执行算法"""
    
    def __init__(self):
        super().__init__(algorithm_id=ExecAlgorithmId("TWAP"))
        self.primary_orders = {}
        self.child_orders = {}
        self.filled_qty = {}
    
    def on_order(self, order: Order) -> None:
        """主订单处理"""
        self.primary_orders[order.client_order_id] = order
        self.filled_qty[order.client_order_id] = Quantity.zero()
        
        # 计算切片参数
        total_qty = order.quantity
        num_slices = 10  # 分为 10 个切片
        slice_qty = total_qty / num_slices
        
        # 放置第一个切片
        self._spawn_slice(order, slice_qty, 0)
    
    def on_fill(self, order: Order, fill: OrderFilled) -> None:
        """成交处理"""
        if order.client_order_id in self.primary_orders:
            self.filled_qty[order.client_order_id] += fill.last_qty
            
            # 检查是否需要放置下一个切片
            primary_order = self.primary_orders[order.client_order_id]
            if self.filled_qty[order.client_order_id] < primary_order.quantity:
                # 放置下一个切片 (简化版本)
                pass
    
    def _spawn_slice(self, primary_order: Order, quantity: Quantity, slice_num: int) -> None:
        """生成切片订单"""
        child_order = self.spawn_limit(
            primary_order=primary_order,
            quantity=quantity,
            price=primary_order.price,
            tags=[f"TWAP_SLICE_{slice_num}"],
        )
        self.child_orders[child_order.client_order_id] = primary_order.client_order_id
```

### 8.4 教程 27: Rust 策略开发

**目标**: 学习使用 Rust 编写策略

**完整代码**:

```rust
// 07_advanced/rust_strategy.rs
use nautilus_trader::trading::strategy::Strategy;
use nautilus_trader::model::data::bar::Bar;
use nautilus_trader::model::enums::OrderSide;

pub struct RustEMAStrategy {
    fast_period: usize,
    slow_period: usize,
    fast_ema: EMA,
    slow_ema: EMA,
    bar_count: usize,
}

impl RustEMAStrategy {
    pub fn new(fast_period: usize, slow_period: usize) -> Self {
        Self {
            fast_period,
            slow_period,
            fast_ema: EMA::new(fast_period),
            slow_ema: EMA::new(slow_period),
            bar_count: 0,
        }
    }
}

impl Strategy for RustEMAStrategy {
    fn on_start(&mut self) {
        self.log_info("Rust EMA Strategy started");
    }
    
    fn on_bar(&mut self, bar: &Bar) {
        self.bar_count += 1;
        self.fast_ema.handle_bar(bar);
        self.slow_ema.handle_bar(bar);
        
        if self.bar_count < self.slow_period {
            return;
        }
        
        if let (Some(fast), Some(slow)) = (self.fast_ema.value(), self.slow_ema.value()) {
            if fast > slow {
                self._enter_long();
            } else if fast < slow {
                self._enter_short();
            }
        }
    }
    
    fn _enter_long(&mut self) {
        // 实现做多逻辑
    }
    
    fn _enter_short(&mut self) {
        // 实现做空逻辑
    }
}
```

---

## 9. 集成教程 (Integration Tutorials)

### 9.1 教程 28: Binance 集成

**目标**: 学习配置和使用 Binance 适配器

**完整代码**:

```python
# 08_integrations/binance_integration.py
from nautilus_trader.adapters.binance.config import BinanceLiveConfig, BinanceSpotConfig, BinanceFuturesConfig
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
```

### 9.2 教程 29: Bybit 集成

**目标**: 学习配置和使用 Bybit 适配器

**完整代码**:

```python
# 08_integrations/bybit_integration.py
from nautilus_trader.adapters.bybit.config import BybitLiveConfig

bybit_config = BybitLiveConfig(
    api_key="your_bybit_api_key",
    api_secret="your_bybit_api_secret",
    instrument_ids=["BTCUSDT.BYBIT", "ETHUSDT.BYBIT"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
    demo_trading=False,
)
```

### 9.3 教程 30: Interactive Brokers 集成

**目标**: 学习配置和使用 IB 适配器

**完整代码**:

```python
# 08_integrations/ib_integration.py
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersConfig

ib_config = InteractiveBrokersConfig(
    ibg_host="127.0.0.1",
    ibg_port=7496,  # 7496=TWS, 4001=Gateway
    ibg_client_id=1,
    account_ids=["DU123456"],
    readonly=False,
)
```

### 9.4 教程 31: Databento 数据集成

**目标**: 学习使用 Databento 数据源

**完整代码**:

```python
# 08_integrations/databento_integration.py
from nautilus_trader.adapters.databento.config import DatabentoDataConfig
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader

# 实时数据配置
data_config = DatabentoDataConfig(
    api_key="your_databento_api_key",
    instrument_ids=["ESU4.GLBX", "NQU4.GLBX"],
    schema="ohlcv-1m",
)

# 历史数据加载
loader = DatabentoDataLoader(api_key="your_databento_api_key")

bars = loader.load_bars(
    instrument_ids=["ESU4.GLBX"],
    schema="ohlcv-1m",
    start="2024-01-01",
    end="2024-12-31",
)
```

### 9.5 教程 32: 自定义适配器开发

**目标**: 学习开发自定义交易所适配器

**完整代码**:

```python
# 08_integrations/custom_adapter.py
from nautilus_trader.live.data_client import DataClient
from nautilus_trader.live.execution_client import ExecutionClient
from nautilus_trader.live.config import LiveConfig

class MyExchangeConfig(LiveConfig):
    api_key: str
    api_secret: str
    base_url: str
    ws_url: str

class MyExchangeDataClient(DataClient):
    def __init__(self, config: MyExchangeConfig):
        super().__init__(config)
        self.ws = None
    
    async def connect(self) -> None:
        self.ws = await websockets.connect(self.config.ws_url)
        await self._authenticate()
    
    async def subscribe_quote_ticks(self, instrument_id: InstrumentId) -> None:
        symbol = self._instrument_to_symbol(instrument_id)
        await self.ws.send(json.dumps({
            "op": "subscribe",
            "channel": "quote",
            "symbol": symbol,
        }))

class MyExchangeExecutionClient(ExecutionClient):
    def __init__(self, config: MyExchangeConfig):
        super().__init__(config)
        self.http = MyExchangeHttpClient(config)
    
    async def submit_order(self, order: Order) -> None:
        response = await self.http.submit_order(...)
        self._generate_order_accepted(order, response)
```

---

## 10. 学习路径建议 (Learning Path Recommendations)

### 10.1 初学者路径 (4-6 周)

| 周次 | 教程 | 目标 |
|------|------|------|
| 第 1 周 | 教程 1-2 | 快速入门，完成第一次回测 |
| 第 2 周 | 教程 3-4 | 理解高低阶 API 回测 |
| 第 3 周 | 教程 5-7 | 多策略回测和参数优化 |
| 第 4 周 | 教程 8-11 | 数据工作流管理 |
| 第 5 周 | 教程 12-13 | 创建基础策略 |
| 第 6 周 | 教程 18-20 | 实盘准备和沙箱测试 |

### 10.2 进阶路径 (8-12 周)

| 周次 | 教程 | 目标 |
|------|------|------|
| 第 1-2 周 | 教程 14-17 | 高级策略开发 |
| 第 3-4 周 | 教程 21-23 | 风险管理系统 |
| 第 5-6 周 | 教程 24-26 | 自定义组件开发 |
| 第 7-8 周 | 教程 28-32 | 交易所集成 |
| 第 9-12 周 | 教程 27 | Rust 开发和性能优化 |

### 10.3 专家路径 (12+ 周)

| 领域 | 学习内容 | 目标 |
|------|---------|------|
| 系统架构 | 深入理解核心架构 | 能够设计复杂系统 |
| 性能优化 | Rust 开发、基准测试 | 优化关键路径性能 |
| 生产部署 | Docker、K8s、监控 | 生产环境部署能力 |
| 自定义适配器 | 完整适配器开发 | 集成新交易所 |
| 贡献社区 | 提交 PR、解决问题 | 成为核心贡献者 |

### 10.4 实践项目建议

| 项目 | 难度 | 涉及教程 |
|------|------|---------|
| EMA 交叉策略回测 | ⭐ | 1-7, 12-13 |
| 网格交易机器人 | ⭐⭐ | 1-7, 14 |
| 多策略组合回测 | ⭐⭐ | 5-7, 12-17 |
| 实盘交易机器人 | ⭐⭐⭐ | 18-20, 28-30 |
| 自定义执行算法 | ⭐⭐⭐⭐ | 25-26 |
| 完整交易系统 | ⭐⭐⭐⭐⭐ | 所有教程 |

---

## 附录 A: 教程资源

### A.1 代码仓库

| 资源 | 链接 |
|------|------|
| 官方示例 | https://github.com/nautechsystems/nautilus_trader/tree/develop/examples |
| 教程代码 | https://github.com/nautechsystems/nautilus_trader/tree/develop/docs/tutorials |
| 社区策略 | https://github.com/nautechsystems/nautilus_trader/discussions |

### A.2 文档资源

| 资源 | 链接 |
|------|------|
| 官方文档 | https://nautilustrader.io/docs/ |
| Tutorials | https://nautilustrader.io/docs/nightly/tutorials/ |
| API Reference | https://nautilustrader.io/docs/nightly/api_reference/ |

### A.3 社区资源

| 资源 | 链接 |
|------|------|
| GitHub Issues | https://github.com/nautechsystems/nautilus_trader/issues |
| GitHub Discussions | https://github.com/nautechsystems/nautilus_trader/discussions |
| PyPI | https://pypi.org/project/nautilus-trader/ |

---

## 附录 B: 常见问题

### B.1 教程相关问题

**Q: 教程代码无法运行？**
```
A: 检查以下项：
   - Python 版本是否为 3.12+
   - nautilus_trader 是否正确安装
   - 依赖是否完整安装
   - 数据目录是否正确构建
```

**Q: 回测结果与预期不符？**
```
A: 检查以下项：
   - 数据质量
   - 策略逻辑
   - 手续费和滑点设置
   - 风险引擎配置
```

**Q: 实盘连接失败？**
```
A: 检查以下项：
   - API 密钥权限
   - 网络连接
   - 时间同步
   - 防火墙设置
```

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-03-31  
> **维护者**: Nautilus Trader 社区

---

此 Markdown 文件包含完整的 Tutorials 目录内容汇总，可直接用于 AI 工具编程参考。如需进一步细化某个教程的细节，请告知！