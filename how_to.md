# Nautilus Trader How-To 操作指南汇总

> **文档版本**: develop 分支 (2026 年 3 月)  
> **适用对象**: 量化开发者、策略研究员、系统运维人员  
> **用途**: AI 工具编程参考文档

---

## 目录

1. [策略开发 (Strategy Development)](#1-策略开发-strategy-development)
2. [数据管理 (Data Management)](#2-数据管理-data-management)
3. [回测操作 (Backtesting Operations)](#3-回测操作-backtesting-operations)
4. [实盘部署 (Live Deployment)](#4-实盘部署-live-deployment)
5. [风险管理 (Risk Management)](#5-风险管理-risk-management)
6. [订单管理 (Order Management)](#6-订单管理-order-management)
7. [持仓管理 (Position Management)](#7-持仓管理-position-management)
8. [账户管理 (Account Management)](#8-账户管理-account-management)
9. [适配器配置 (Adapter Configuration)](#9-适配器配置-adapter-configuration)
10. [性能优化 (Performance Optimization)](#10-性能优化-performance-optimization)
11. [故障排查 (Troubleshooting)](#11-故障排查-troubleshooting)
12. [监控与报警 (Monitoring & Alerting)](#12-监控与报警-monitoring--alerting)
13. [数据导出 (Data Export)](#13-数据导出-data-export)
14. [系统集成 (System Integration)](#14-系统集成-system-integration)

---

## 1. 策略开发 (Strategy Development)

### 1.1 如何创建新策略

**步骤**:

```python
# 1. 创建策略配置文件
from decimal import Decimal
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.identifiers import InstrumentId, BarType

class MyStrategyConfig(StrategyConfig):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_period: int = 10
    slow_period: int = 20

# 2. 创建策略类
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.indicators import EMA

class MyStrategy(Strategy):
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        self.instrument = None
        self.fast_ema = None
        self.slow_ema = None
    
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.fast_ema = EMA(self.config.fast_period)
        self.slow_ema = EMA(self.config.slow_period)
        self.subscribe_bars(self.config.bar_type)
    
    def on_bar(self, bar: Bar) -> None:
        self.fast_ema.handle_bar(bar)
        self.slow_ema.handle_bar(bar)
        
        if self.fast_ema.value > self.slow_ema.value:
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

# 3. 注册策略
# 在配置文件中引用
```

### 1.2 如何添加技术指标

```python
from nautilus_trader.indicators import (
    EMA, SMA, RSI, MACD, BollingerBands, ATR, STC
)

class IndicatorStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        
        # 移动平均线
        self.ema_fast = EMA(10)
        self.ema_slow = EMA(20)
        self.sma = SMA(50)
        
        # 动量指标
        self.rsi = RSI(14)
        self.macd = MACD(12, 26, 9)
        
        # 波动率指标
        self.bollinger = BollingerBands(20, 2.0)
        self.atr = ATR(14)
        
        # 趋势指标
        self.stc = STC(10, 12, 26)
    
    def on_bar(self, bar: Bar) -> None:
        # 更新所有指标
        self.ema_fast.handle_bar(bar)
        self.ema_slow.handle_bar(bar)
        self.rsi.handle_bar(bar)
        self.macd.handle_bar(bar)
        self.bollinger.handle_bar(bar)
        self.atr.handle_bar(bar)
        
        # 检查指标值
        if self.rsi.value < 30:
            self.log.info(f"RSI 超卖：{self.rsi.value:.2f}")
        
        if self.rsi.value > 70:
            self.log.info(f"RSI 超买：{self.rsi.value:.2f}")
```

### 1.3 如何实现多时间框架策略

```python
class MultiTimeframeStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        
        # 多个时间框架
        self.bar_type_1m = BarType.from_str("BTCUSDT.BINANCE-1-MINUTE")
        self.bar_type_5m = BarType.from_str("BTCUSDT.BINANCE-5-MINUTE")
        self.bar_type_1h = BarType.from_str("BTCUSDT.BINANCE-1-HOUR")
        
        # 各时间框架的指标
        self.ema_1m = EMA(10)
        self.ema_5m = EMA(20)
        self.ema_1h = EMA(50)
    
    def on_start(self) -> None:
        # 订阅多个时间框架
        self.subscribe_bars(self.bar_type_1m)
        self.subscribe_bars(self.bar_type_5m)
        self.subscribe_bars(self.bar_type_1h)
    
    def on_bar(self, bar: Bar) -> None:
        # 根据时间框架处理
        if bar.bar_type == self.bar_type_1m:
            self.ema_1m.handle_bar(bar)
            self._check_1m_signal()
        elif bar.bar_type == self.bar_type_5m:
            self.ema_5m.handle_bar(bar)
            self._check_5m_signal()
        elif bar.bar_type == self.bar_type_1h:
            self.ema_1h.handle_bar(bar)
            self._check_1h_signal()
    
    def _check_1m_signal(self) -> None:
        # 1 分钟信号逻辑
        pass
    
    def _check_5m_signal(self) -> None:
        # 5 分钟信号逻辑
        pass
    
    def _check_1h_signal(self) -> None:
        # 1 小时信号逻辑 (趋势确认)
        pass
```

### 1.4 如何实现多资产策略

```python
class MultiAssetStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        
        # 多个交易工具
        self.instruments = [
            InstrumentId.from_str("BTCUSDT.BINANCE"),
            InstrumentId.from_str("ETHUSDT.BINANCE"),
            InstrumentId.from_str("SOLUSDT.BINANCE"),
        ]
        
        self.indicators = {}
        self.positions = {}
    
    def on_start(self) -> None:
        for inst_id in self.instruments:
            instrument = self.cache.instrument(inst_id)
            self.indicators[inst_id] = EMA(20)
            self.positions[inst_id] = None
            self.subscribe_bars(
                BarType.from_str(f"{inst_id.value}-1-HOUR-LAST-INTERNAL")
            )
    
    def on_bar(self, bar: Bar) -> None:
        inst_id = bar.bar_type.instrument_id
        
        # 更新指标
        self.indicators[inst_id].handle_bar(bar)
        
        # 检查信号
        if self._should_buy(inst_id):
            self._enter_position(inst_id, OrderSide.BUY)
        elif self._should_sell(inst_id):
            self._exit_position(inst_id)
    
    def _should_buy(self, instrument_id: InstrumentId) -> bool:
        # 买入逻辑
        return True
    
    def _should_sell(self, instrument_id: InstrumentId) -> bool:
        # 卖出逻辑
        return True
```

### 1.5 如何保存和加载策略状态

```python
class StatefulStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self.trade_count = 0
        self.total_pnl = Decimal("0")
        self.last_signal = None
    
    def on_save(self) -> dict[str, bytes]:
        """保存策略状态"""
        return {
            "trade_count": str(self.trade_count).encode(),
            "total_pnl": str(self.total_pnl).encode(),
            "last_signal": (self.last_signal or "").encode(),
        }
    
    def on_load(self, state: dict[str, bytes]) -> None:
        """加载策略状态"""
        self.trade_count = int(state["trade_count"].decode())
        self.total_pnl = Decimal(state["total_pnl"].decode())
        self.last_signal = state["last_signal"].decode() or None
        self.log.info(f"Loaded state: trades={self.trade_count}, pnl={self.total_pnl}")
    
    def on_reset(self) -> None:
        """重置策略状态"""
        self.trade_count = 0
        self.total_pnl = Decimal("0")
        self.last_signal = None
```

---

## 2. 数据管理 (Data Management)

### 2.1 如何构建 Parquet 数据目录

```python
from pathlib import Path
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader

def build_catalog():
    """构建数据目录"""
    
    # 1. 创建目录
    catalog_path = Path("./catalog")
    catalog_path.mkdir(parents=True, exist_ok=True)
    catalog = ParquetDataCatalog(path=catalog_path)
    
    # 2. 加载数据
    loader = DatabentoDataLoader(api_key="your_api_key")
    
    # 加载 K 线
    bars = loader.load_bars(
        instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
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
    
    # 加载成交
    trades = loader.load_trade_ticks(
        instrument_ids=["BTCUSDT.BINANCE"],
        start="2024-01-01",
        end="2024-12-31",
    )
    catalog.write_trade_ticks(trades)
    
    # 加载工具定义
    instruments = loader.load_instruments(
        instrument_ids=["BTCUSDT.BINANCE"],
    )
    catalog.write_instruments(instruments)
    
    print(f"Catalog built at: {catalog_path}")
    return catalog
```

### 2.2 如何从 CSV 导入数据

```python
import pandas as pd
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.data import Bar, QuoteTick, TradeTick
from nautilus_trader.model.identifiers import InstrumentId, BarType
from nautilus_trader.core.datetime import dt_to_unix_nanos

def import_from_csv(csv_path: str, catalog_path: str, data_type: str = "bars"):
    """从 CSV 导入数据"""
    
    # 读取 CSV
    df = pd.read_csv(csv_path)
    
    # 创建目录
    catalog = ParquetDataCatalog(path=catalog_path)
    
    if data_type == "bars":
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
        catalog.write_bars(bars)
        print(f"Imported {len(bars)} bars")
    
    elif data_type == "quotes":
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
        print(f"Imported {len(quotes)} quotes")
    
    elif data_type == "trades":
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
        print(f"Imported {len(trades)} trades")
```

### 2.3 如何查询数据目录

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
print(f"Found {len(bars)} bars")

# 查询报价
quotes = catalog.quote_ticks(
    instrument_ids=["BTCUSDT.BINANCE"],
    start="2024-01-01",
    end="2024-01-31",
)
print(f"Found {len(quotes)} quotes")

# 查询成交
trades = catalog.trade_ticks(
    instrument_ids=["BTCUSDT.BINANCE"],
    start="2024-01-01",
    end="2024-01-31",
)
print(f"Found {len(trades)} trades")

# 查询工具
instruments = catalog.instruments(
    instrument_ids=["BTCUSDT.BINANCE"],
)
print(f"Found {len(instruments)} instruments")

# 查询自定义数据
custom_data = catalog.query(
    data_type=DataType(GreeksData),
    instrument_ids=["BTC-29DEC23-40000-C.BYBIT"],
    start="2024-01-01",
    end="2024-12-31",
)
```

### 2.4 如何清理数据目录

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog

catalog = ParquetDataCatalog(path="./catalog")

# 删除特定时间段的数据
catalog.delete_bars(
    instrument_ids=["BTCUSDT.BINANCE"],
    bar_types=["1-MINUTE"],
    start="2024-01-01",
    end="2024-01-31",
)

# 删除特定工具的所有数据
catalog.delete_data(
    instrument_ids=["ETHUSDT.BINANCE"],
)

# 删除所有数据 (谨慎使用!)
# catalog.delete_all()

# 检查目录大小
import os
def get_dir_size(path):
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total += os.path.getsize(fp)
    return total

size_gb = get_dir_size("./catalog") / 1024 / 1024 / 1024
print(f"Catalog size: {size_gb:.2f} GB")
```

### 2.5 如何重采样 K 线

```python
import pandas as pd
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.data import Bar

def resample_bars(
    catalog_path: str,
    instrument_id: str,
    source_bar_type: str,
    target_bar_type: str,
) -> list[Bar]:
    """重采样 K 线"""
    
    catalog = ParquetDataCatalog(path=catalog_path)
    
    # 加载源数据
    bars = catalog.bars(
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
    df["timestamp"] = pd.to_datetime(df["ts_event"], unit="ns")
    df = df.set_index("timestamp")
    
    # 重采样 (1 分钟 -> 1 小时)
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
    
    # 写入目录
    catalog.write_bars(new_bars)
    
    return new_bars

# 使用示例
resampled = resample_bars(
    catalog_path="./catalog",
    instrument_id="BTCUSDT.BINANCE",
    source_bar_type="1-MINUTE",
    target_bar_type="1-HOUR",
)
print(f"Created {len(resampled)} hourly bars")
```

---

## 3. 回测操作 (Backtesting Operations)

### 3.1 如何运行简单回测

```python
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

def run_simple_backtest():
    """运行简单回测"""
    
    config = BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="BACKTESTER-001",
            run_id="backtest-001",
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
    
    # 打印结果
    for result in results:
        perf = result.performance
        print(f"Total Return: {perf.total_return:.2%}")
        print(f"Sharpe Ratio: {perf.sharpe_ratio:.2f}")
        print(f"Max Drawdown: {perf.max_drawdown:.2%}")
        print(f"Total Trades: {perf.total_trades}")
    
    return results
```

### 3.2 如何运行多策略回测

```python
def run_multi_strategy_backtest():
    """运行多策略回测"""
    
    configs = []
    
    # 策略 1: EMA Cross
    configs.append(BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id="BACKTESTER-001"),
        venues=[...],
        data=[...],
        strategies=[EMACrossConfig(...)],
    ))
    
    # 策略 2: Grid Trading
    configs.append(BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id="BACKTESTER-002"),
        venues=[...],
        data=[...],
        strategies=[GridTradingConfig(...)],
    ))
    
    # 策略 3: Market Making
    configs.append(BacktestRunConfig(
        engine=BacktestEngineConfig(trader_id="BACKTESTER-003"),
        venues=[...],
        data=[...],
        strategies=[MarketMakerConfig(...)],
    ))
    
    node = BacktestNode(configs=configs)
    results = node.run()
    
    # 汇总结果
    print("\n" + "="*50)
    print("MULTI-STRATEGY SUMMARY")
    print("="*50)
    
    for result in results:
        perf = result.performance
        print(f"\n{result.strategy_id}:")
        print(f"  Return: {perf.total_return:.2%}")
        print(f"  Sharpe: {perf.sharpe_ratio:.2f}")
        print(f"  MaxDD: {perf.max_drawdown:.2%}")
    
    return results
```

### 3.3 如何优化策略参数

```python
from itertools import product
from nautilus_trader.backtest.node import BacktestNode

def optimize_parameters():
    """参数优化"""
    
    # 参数网格
    fast_periods = [5, 10, 15, 20]
    slow_periods = [20, 30, 40, 50]
    trade_sizes = [Decimal("0.05"), Decimal("0.1"), Decimal("0.2")]
    
    results = []
    
    for fast, slow, size in product(fast_periods, slow_periods, trade_sizes):
        if fast >= slow:
            continue
        
        print(f"Testing fast={fast}, slow={slow}, size={size}...")
        
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
                    trade_size=size,
                    order_id_tag="001",
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
        })
    
    # 按夏普比率排序
    results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)
    
    print("\n" + "="*50)
    print("TOP 5 PARAMETER SETS")
    print("="*50)
    
    for i, r in enumerate(results[:5]):
        print(f"\n{i+1}. Fast={r['fast_period']}, Slow={r['slow_period']}, Size={r['trade_size']}")
        print(f"   Return: {r['total_return']:.2%}")
        print(f"   Sharpe: {r['sharpe_ratio']:.2f}")
        print(f"   MaxDD: {r['max_drawdown']:.2%}")
    
    return results
```

### 3.4 如何生成回测报告

```python
from nautilus_trader.backtest.node import BacktestNode
from pathlib import Path

def generate_backtest_reports():
    """生成回测报告"""
    
    node = BacktestNode(configs=[config])
    results = node.run()
    
    # 生成报告目录
    report_dir = Path("./reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    
    for result in results:
        # 保存报告
        result.save_reports(report_dir)
        
        # 报告文件包括:
        # - performance.html (绩效报告)
        # - positions.parquet (持仓记录)
        # - orders.parquet (订单记录)
        # - fills.parquet (成交记录)
        # - account_state.parquet (账户状态)
        
        print(f"Reports saved to: {report_dir / result.strategy_id}")
    
    # 生成汇总报告
    node.generate_reports()
```

### 3.5 如何比较回测结果

```python
import pandas as pd
from nautilus_trader.backtest.node import BacktestNode

def compare_backtest_results():
    """比较多个回测结果"""
    
    configs = [
        # 配置 1
        BacktestRunConfig(..., strategies=[EMACrossConfig(fast=10, slow=20)]),
        # 配置 2
        BacktestRunConfig(..., strategies=[EMACrossConfig(fast=15, slow=30)]),
        # 配置 3
        BacktestRunConfig(..., strategies=[EMACrossConfig(fast=20, slow=40)]),
    ]
    
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
            "Avg Trade": f"{perf.average_trade:.2f}",
        })
    
    df = pd.DataFrame(comparison)
    print(df.to_string(index=False))
    
    # 保存为 CSV
    df.to_csv("./reports/comparison.csv", index=False)
    
    return df
```

---

## 4. 实盘部署 (Live Deployment)

### 4.1 如何配置实盘节点

```python
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
import os

def configure_live_node():
    """配置实盘节点"""
    
    config = TradingNodeConfig(
        trader_id="TRADER-001",
        run_id="live-2024-001",
        
        # 缓存配置
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
            EMACrossConfig(
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

### 4.2 如何启动实盘交易

```python
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
            await self.node.run_async()
            
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

### 4.3 如何使用 Docker 部署

**Dockerfile**:
```dockerfile
FROM ghcr.io/nautechsystems/jupyterlab:nightly

WORKDIR /app

# 复制项目
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY strategies/ ./strategies/
COPY config/ ./config/
COPY live/ ./live/

# 安装项目
RUN pip install -e .

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV NAUTILUS_LOG_LEVEL=INFO

# 启动命令
CMD ["python", "-m", "live.run_live"]
```

**docker-compose.yml**:
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  trader:
    build: .
    depends_on:
      - redis
    environment:
      - NAUTILUS_DATABASE_HOST=redis
      - NAUTILUS_DATABASE_PORT=6379
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_API_SECRET=${BINANCE_API_SECRET}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  redis_data:
```

**部署命令**:
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f trader

# 停止服务
docker-compose down
```

### 4.4 如何配置 systemd 服务

**服务文件** (`/etc/systemd/system/nautilus-trader.service`):
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

Environment="PYTHONUNBUFFERED=1"
Environment="NAUTILUS_LOG_LEVEL=INFO"
Environment="NAUTILUS_DATABASE_HOST=localhost"
Environment="NAUTILUS_DATABASE_PORT=6379"

EnvironmentFile=/home/trader/.env

ExecStart=/usr/bin/python -m live.run_live
Restart=always
RestartSec=10

LimitNOFILE=65536
MemoryMax=2G

StandardOutput=journal
StandardError=journal
SyslogIdentifier=nautilus-trader

[Install]
WantedBy=multi-user.target
```

**安装命令**:
```bash
# 复制服务文件
sudo cp nautilus-trader.service /etc/systemd/system/

# 重新加载
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

### 4.5 如何实现优雅关闭

```python
import asyncio
import signal

class GracefulShutdown:
    def __init__(self, node: TradingNode):
        self.node = node
        self._shutdown_requested = False
    
    def register_handlers(self):
        """注册信号处理器"""
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, self._handle_signal)
    
    def _handle_signal(self, signum, frame):
        """处理信号"""
        print(f"\nShutdown signal received ({signum})")
        self._shutdown_requested = True
    
    async def wait_for_shutdown(self):
        """等待关闭信号"""
        while not self._shutdown_requested:
            await asyncio.sleep(0.1)
    
    async def shutdown(self):
        """执行优雅关闭"""
        print("Initiating graceful shutdown...")
        
        # 1. 停止接受新订单
        self.node.stop()
        print("Stopped accepting new orders")
        
        # 2. 等待未完成订单
        await asyncio.sleep(2)
        
        # 3. 取消所有挂单
        self.node.cancel_all_orders()
        print("Canceled all open orders")
        
        # 4. 等待订单取消确认
        await asyncio.sleep(2)
        
        # 5. 释放资源
        self.node.dispose()
        print("Resources disposed")
        
        print("Shutdown complete")

async def main():
    config = configure_live_node()
    node = TradingNode(config=config)
    
    shutdown = GracefulShutdown(node)
    shutdown.register_handlers()
    
    # 启动节点
    await node.run_async()
    
    # 等待关闭信号
    await shutdown.wait_for_shutdown()
    
    # 执行关闭
    await shutdown.shutdown()
```

---

## 5. 风险管理 (Risk Management)

### 5.1 如何配置风险引擎

```python
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

### 5.2 如何实现自定义风险检查

```python
from nautilus_trader.risk.engine import RiskEngine
from nautilus_trader.model.order import Order
from nautilus_trader.model.event import OrderDenied

class CustomRiskEngine(RiskEngine):
    """自定义风险引擎"""
    
    def check_order(self, order: Order) -> None:
        """自定义订单检查"""
        
        # 调用父类检查
        super().check_order(order)
        
        # 添加自定义检查
        self._check_concentration(order)
        self._check_volatility(order)
        self._check_time_restrictions(order)
    
    def _check_concentration(self, order: Order) -> None:
        """检查持仓集中度"""
        position = self.cache.position_for_order(order.client_order_id)
        
        if position:
            portfolio_value = self.portfolio.value()
            position_value = position.value()
            concentration = position_value / portfolio_value
            
            if concentration > Decimal("0.25"):  # 单持仓不超过 25%
                raise OrderDenied(
                    trader_id=order.trader_id,
                    strategy_id=order.strategy_id,
                    account_id=self.account_id,
                    client_order_id=order.client_order_id,
                    reason="Position concentration exceeds 25%",
                )
    
    def _check_volatility(self, order: Order) -> None:
        """检查波动率限制"""
        # 实现波动率检查逻辑
        pass
    
    def _check_time_restrictions(self, order: Order) -> None:
        """检查时间限制"""
        # 实现交易时间检查逻辑
        pass
```

### 5.3 如何实现止损逻辑

```python
class StopLossStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self.stop_loss_pct = Decimal("0.02")  # 2% 止损
        self.take_profit_pct = Decimal("0.04")  # 4% 止盈
        self.entry_price = None
    
    def on_position_opened(self, event: PositionOpened) -> None:
        """持仓开启时设置止损"""
        position = self.cache.position(event.position_id)
        self.entry_price = position.avg_px_open
        
        # 计算止损和止盈价格
        if position.side == PositionSide.LONG:
            stop_price = self.entry_price * (1 - self.stop_loss_pct)
            take_profit_price = self.entry_price * (1 + self.take_profit_pct)
        else:
            stop_price = self.entry_price * (1 + self.stop_loss_pct)
            take_profit_price = self.entry_price * (1 - self.take_profit_pct)
        
        # 提交止损单
        stop_order = self.order_factory.stop_market(
            instrument_id=position.instrument_id,
            order_side=OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY,
            quantity=position.quantity,
            trigger_price=stop_price,
            reduce_only=True,
            tags=["STOP_LOSS"],
        )
        self.submit_order(stop_order)
        
        # 提交止盈单
        tp_order = self.order_factory.limit(
            instrument_id=position.instrument_id,
            order_side=OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY,
            quantity=position.quantity,
            price=take_profit_price,
            reduce_only=True,
            tags=["TAKE_PROFIT"],
        )
        self.submit_order(tp_order)
    
    def on_bar(self, bar: Bar) -> None:
        """K 线处理 - 移动止损"""
        if self.position and self.entry_price:
            # 实现追踪止损逻辑
            self._update_trailing_stop(bar)
```

### 5.4 如何实现仓位管理

```python
class PositionSizingStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self.risk_per_trade = Decimal("0.01")  # 每笔交易风险 1%
        self.max_position_pct = Decimal("0.20")  # 最大持仓 20%
    
    def calculate_position_size(self, stop_loss_distance: Decimal) -> Quantity:
        """计算仓位大小"""
        
        # 获取账户余额
        account = self.portfolio.account(venue=self.instrument.venue)
        account_value = account.value()
        
        # 计算风险金额
        risk_amount = account_value * self.risk_per_trade
        
        # 根据止损距离计算仓位
        position_value = risk_amount / stop_loss_distance
        
        # 应用最大持仓限制
        max_position_value = account_value * self.max_position_pct
        position_value = min(position_value, max_position_value)
        
        # 转换为数量
        quantity = position_value / self.instrument.make_price(float(bar.close))
        
        return self.instrument.make_qty(quantity)
    
    def on_signal(self, signal) -> None:
        """信号处理"""
        stop_loss_distance = self.calculate_stop_loss_distance()
        quantity = self.calculate_position_size(stop_loss_distance)
        
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=signal.side,
            quantity=quantity,
        )
        self.submit_order(order)
```

### 5.5 如何监控风险指标

```python
class RiskMonitor(Actor):
    def __init__(self, config: ActorConfig) -> None:
        super().__init__(config)
        self.alert_thresholds = {
            "drawdown": Decimal("0.05"),
            "concentration": Decimal("0.25"),
            "daily_loss": Money(10_000, "USDT"),
        }
    
    def on_start(self) -> None:
        # 设置定时检查
        self.clock.set_timer(
            "risk_check",
            timedelta(minutes=5),
            callback=self._check_risk,
        )
    
    def _check_risk(self) -> None:
        """检查风险指标"""
        
        # 检查回撤
        current_drawdown = self._calculate_drawdown()
        if current_drawdown > self.alert_thresholds["drawdown"]:
            self._send_alert("DRAWDOWN", f"Drawdown: {current_drawdown:.2%}")
        
        # 检查持仓集中度
        concentration = self._calculate_concentration()
        if concentration > self.alert_thresholds["concentration"]:
            self._send_alert("CONCENTRATION", f"Concentration: {concentration:.2%}")
        
        # 检查日损失
        daily_loss = self._calculate_daily_loss()
        if daily_loss > self.alert_thresholds["daily_loss"]:
            self._send_alert("DAILY_LOSS", f"Daily Loss: {daily_loss}")
    
    def _calculate_drawdown(self) -> Decimal:
        """计算当前回撤"""
        account = self.portfolio.account(venue=Venue("BINANCE"))
        peak = account.peak_value()
        current = account.value()
        return (peak - current) / peak if peak > 0 else Decimal("0")
    
    def _calculate_concentration(self) -> Decimal:
        """计算最大持仓集中度"""
        positions = self.cache.positions_open()
        if not positions:
            return Decimal("0")
        
        account_value = self.portfolio.account(venue=Venue("BINANCE")).value()
        max_position = max(p.value() for p in positions)
        return max_position / account_value
    
    def _calculate_daily_loss(self) -> Money:
        """计算日损失"""
        # 实现日损失计算逻辑
        pass
    
    def _send_alert(self, alert_type: str, message: str) -> None:
        """发送警报"""
        self.log.warning(f"[RISK ALERT] {alert_type}: {message}")
        # 可以集成邮件、Slack、Telegram 等通知
```

---

## 6. 订单管理 (Order Management)

### 6.1 如何提交订单

```python
class OrderManagementStrategy(Strategy):
    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
    
    def submit_market_order(self, side: OrderSide, quantity: Decimal) -> None:
        """提交市价单"""
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=side,
            quantity=self.instrument.make_qty(quantity),
            time_in_force=TimeInForce.IOC,
            tags=["MARKET"],
        )
        self.submit_order(order)
    
    def submit_limit_order(
        self,
        side: OrderSide,
        quantity: Decimal,
        price: Decimal,
    ) -> None:
        """提交限价单"""
        order = self.order_factory.limit(
            instrument_id=self.instrument.id,
            order_side=side,
            quantity=self.instrument.make_qty(quantity),
            price=self.instrument.make_price(price),
            time_in_force=TimeInForce.GTC,
            post_only=True,
            tags=["LIMIT"],
        )
        self.submit_order(order)
    
    def submit_stop_order(
        self,
        side: OrderSide,
        quantity: Decimal,
        trigger_price: Decimal,
    ) -> None:
        """提交止损单"""
        order = self.order_factory.stop_market(
            instrument_id=self.instrument.id,
            order_side=side,
            quantity=self.instrument.make_qty(quantity),
            trigger_price=self.instrument.make_price(trigger_price),
            trigger_type=TriggerType.LAST_PRICE,
            reduce_only=True,
            tags=["STOP"],
        )
        self.submit_order(order)
    
    def submit_bracket_order(
        self,
        side: OrderSide,
        quantity: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
        take_profit: Decimal,
    ) -> None:
        """提交括号订单"""
        orders = self.order_factory.bracket(
            instrument_id=self.instrument.id,
            order_side=side,
            quantity=self.instrument.make_qty(quantity),
            entry_type=OrderType.LIMIT,
            entry_price=self.instrument.make_price(entry_price),
            tp_type=OrderType.LIMIT,
            tp_price=self.instrument.make_price(take_profit),
            sl_type=OrderType.STOP_MARKET,
            sl_trigger_price=self.instrument.make_price(stop_loss),
            time_in_force=TimeInForce.GTC,
            tags=["BRACKET"],
        )
        self.submit_order_list(orders)
```

### 6.2 如何修改订单

```python
def modify_order_quantity(self, order: Order, new_quantity: Decimal) -> None:
    """修改订单数量"""
    new_qty = self.instrument.make_qty(new_quantity)
    self.modify_order(order, quantity=new_qty)

def modify_order_price(self, order: Order, new_price: Decimal) -> None:
    """修改订单价格"""
    new_price_obj = self.instrument.make_price(new_price)
    self.modify_order(order, price=new_price_obj)

def modify_order_both(self, order: Order, new_quantity: Decimal, new_price: Decimal) -> None:
    """同时修改数量和价格"""
    new_qty = self.instrument.make_qty(new_quantity)
    new_price_obj = self.instrument.make_price(new_price)
    self.modify_order(order, quantity=new_qty, price=new_price_obj)
```

### 6.3 如何取消订单

```python
def cancel_single_order(self, order: Order) -> None:
    """取消单个订单"""
    self.cancel_order(order)

def cancel_multiple_orders(self, orders: list[Order]) -> None:
    """取消多个订单"""
    self.cancel_orders(orders)

def cancel_all_orders(self) -> None:
    """取消所有订单"""
    self.cancel_all_orders()

def cancel_orders_by_strategy(self, strategy_id: StrategyId) -> None:
    """取消指定策略的所有订单"""
    orders = self.cache.orders(strategy_id=strategy_id)
    self.cancel_orders(orders)

def cancel_orders_by_instrument(self, instrument_id: InstrumentId) -> None:
    """取消指定工具的所有订单"""
    orders = self.cache.orders(instrument_id=instrument_id)
    self.cancel_orders(orders)

def cancel_open_orders_only(self) -> None:
    """仅取消未成交订单"""
    orders = self.cache.orders_open()
    self.cancel_orders(orders)
```

### 6.4 如何查询订单状态

```python
def query_order_status(self) -> None:
    """查询订单状态"""
    
    # 查询单个订单
    order = self.cache.order(ClientOrderId("O-123456"))
    if order:
        self.log.info(f"Order status: {order.status}")
    
    # 查询所有订单
    all_orders = self.cache.orders()
    self.log.info(f"Total orders: {len(all_orders)}")
    
    # 查询未成交订单
    open_orders = self.cache.orders_open()
    self.log.info(f"Open orders: {len(open_orders)}")
    
    # 查询已成交订单
    filled_orders = self.cache.orders_filled()
    self.log.info(f"Filled orders: {len(filled_orders)}")
    
    # 查询已取消订单
    canceled_orders = self.cache.orders_canceled()
    self.log.info(f"Canceled orders: {len(canceled_orders)}")
    
    # 按策略查询
    strategy_orders = self.cache.orders(strategy_id=self.id)
    self.log.info(f"Strategy orders: {len(strategy_orders)}")
    
    # 按工具查询
    instrument_orders = self.cache.orders(instrument_id=self.instrument.id)
    self.log.info(f"Instrument orders: {len(instrument_orders)}")
    
    # 检查订单状态
    if order:
        self.log.info(f"Is open: {self.cache.is_order_open(order.client_order_id)}")
        self.log.info(f"Is closed: {self.cache.is_order_closed(order.client_order_id)}")
        self.log.info(f"Is emulated: {self.cache.is_order_emulated(order.client_order_id)}")
```

### 6.5 如何处理订单事件

```python
class OrderEventHandler(Strategy):
    def on_order_initialized(self, event: OrderInitialized) -> None:
        """订单初始化"""
        self.log.info(f"Order initialized: {event.client_order_id}")
    
    def on_order_submitted(self, event: OrderSubmitted) -> None:
        """订单提交"""
        self.log.info(f"Order submitted: {event.client_order_id}")
    
    def on_order_accepted(self, event: OrderAccepted) -> None:
        """订单接受"""
        self.log.info(f"Order accepted: {event.client_order_id}")
    
    def on_order_rejected(self, event: OrderRejected) -> None:
        """订单拒绝"""
        self.log.error(f"Order rejected: {event.client_order_id}, reason: {event.reason}")
    
    def on_order_filled(self, event: OrderFilled) -> None:
        """订单成交"""
        self.log.info(
            f"Order filled: {event.client_order_id}, "
            f"price: {event.last_px}, qty: {event.last_qty}"
        )
    
    def on_order_canceled(self, event: OrderCanceled) -> None:
        """订单取消"""
        self.log.info(f"Order canceled: {event.client_order_id}")
    
    def on_order_updated(self, event: OrderUpdated) -> None:
        """订单更新"""
        self.log.info(f"Order updated: {event.client_order_id}")
    
    def on_order_expired(self, event: OrderExpired) -> None:
        """订单过期"""
        self.log.info(f"Order expired: {event.client_order_id}")
    
    def on_order_event(self, event: OrderEvent) -> None:
        """所有订单事件的通用处理器"""
        self.log.debug(f"Order event: {event.event_type} - {event.client_order_id}")
```

---

## 7. 持仓管理 (Position Management)

### 7.1 如何查询持仓

```python
def query_positions(self) -> None:
    """查询持仓"""
    
    # 查询单个持仓
    position = self.cache.position(PositionId("P-123456"))
    if position:
        self.log.info(f"Position: {position.id}, side: {position.side}, qty: {position.quantity}")
    
    # 查询所有持仓
    all_positions = self.cache.positions()
    self.log.info(f"Total positions: {len(all_positions)}")
    
    # 查询未平仓持仓
    open_positions = self.cache.positions_open()
    self.log.info(f"Open positions: {len(open_positions)}")
    
    # 查询已平仓持仓
    closed_positions = self.cache.positions_closed()
    self.log.info(f"Closed positions: {len(closed_positions)}")
    
    # 按工具查询
    instrument_positions = self.cache.positions(instrument_id=self.instrument.id)
    self.log.info(f"Instrument positions: {len(instrument_positions)}")
    
    # 按方向查询
    long_positions = self.cache.positions(side=PositionSide.LONG)
    short_positions = self.cache.positions(side=PositionSide.SHORT)
    self.log.info(f"Long: {len(long_positions)}, Short: {len(short_positions)}")
    
    # 检查持仓状态
    if position:
        self.log.info(f"Is open: {self.cache.is_position_open(position.id)}")
        self.log.info(f"Is closed: {self.cache.is_position_closed(position.id)}")
```

### 7.2 如何计算持仓盈亏

```python
def calculate_position_pnl(self) -> None:
    """计算持仓盈亏"""
    
    positions = self.cache.positions_open()
    
    for position in positions:
        # 已实现盈亏
        realized_pnl = position.realized_pnl
        self.log.info(f"Realized PnL: {realized_pnl}")
        
        # 已实现回报率
        realized_return = position.realized_return
        self.log.info(f"Realized Return: {realized_return:.2%}")
        
        # 未实现盈亏 (使用最后成交价)
        unrealized_pnl = position.unrealized_pnl()
        self.log.info(f"Unrealized PnL: {unrealized_pnl}")
        
        # 未实现盈亏 (使用买价 - 保守估计)
        book = self.cache.order_book(position.instrument_id)
        if book:
            unrealized_pnl_bid = position.unrealized_pnl(book.bid_price())
            self.log.info(f"Unrealized PnL (bid): {unrealized_pnl_bid}")
        
        # 总盈亏
        total_pnl = position.total_pnl()
        self.log.info(f"Total PnL: {total_pnl}")
        
        # 持仓价值
        position_value = position.value()
        self.log.info(f"Position Value: {position_value}")
```

### 7.3 如何平仓

```python
def close_position(self, position_id: PositionId) -> None:
    """平仓指定持仓"""
    position = self.cache.position(position_id)
    
    if position and position.is_open:
        # 确定平仓方向
        if position.side == PositionSide.LONG:
            side = OrderSide.SELL
        else:
            side = OrderSide.BUY
        
        # 提交市价平仓单
        order = self.order_factory.market(
            instrument_id=position.instrument_id,
            order_side=side,
            quantity=position.quantity,
            reduce_only=True,
            tags=["CLOSE"],
        )
        self.submit_order(order)

def close_all_positions(self) -> None:
    """平掉所有持仓"""
    positions = self.cache.positions_open()
    
    for position in positions:
        self.close_position(position.id)

def close_positions_by_instrument(self, instrument_id: InstrumentId) -> None:
    """平掉指定工具的所有持仓"""
    positions = self.cache.positions(instrument_id=instrument_id)
    
    for position in positions:
        if position.is_open:
            self.close_position(position.id)

def close_profitable_positions(self, min_profit_pct: Decimal = Decimal("0.01")) -> None:
    """平掉盈利超过阈值的持仓"""
    positions = self.cache.positions_open()
    
    for position in positions:
        if position.realized_return >= min_profit_pct:
            self.log.info(f"Closing profitable position: {position.id}, return: {position.realized_return:.2%}")
            self.close_position(position.id)

def close_losing_positions(self, max_loss_pct: Decimal = Decimal("-0.02")) -> None:
    """止损平仓"""
    positions = self.cache.positions_open()
    
    for position in positions:
        if position.realized_return <= max_loss_pct:
            self.log.info(f"Closing losing position: {position.id}, return: {position.realized_return:.2%}")
            self.close_position(position.id)
```

### 7.4 如何处理持仓事件

```python
class PositionEventHandler(Strategy):
    def on_position_opened(self, event: PositionOpened) -> None:
        """持仓开启"""
        self.log.info(
            f"Position opened: {event.position_id}, "
            f"side: {event.side}, qty: {event.quantity}"
        )
    
    def on_position_changed(self, event: PositionChanged) -> None:
        """持仓变更"""
        self.log.info(
            f"Position changed: {event.position_id}, "
            f"qty: {event.quantity}, pnl: {event.realized_pnl}"
        )
    
    def on_position_closed(self, event: PositionClosed) -> None:
        """持仓关闭"""
        self.log.info(
            f"Position closed: {event.position_id}, "
            f"realized_pnl: {event.realized_pnl}, "
            f"return: {event.realized_return:.2%}"
        )
    
    def on_position_event(self, event: PositionEvent) -> None:
        """所有持仓事件的通用处理器"""
        self.log.debug(f"Position event: {event.event_type} - {event.position_id}")
```

### 7.5 如何管理持仓快照

```python
def get_position_snapshots(self, instrument_id: InstrumentId) -> None:
    """获取持仓快照"""
    snapshots = self.cache.position_snapshots(instrument_id=instrument_id)
    
    for snapshot in snapshots:
        self.log.info(
            f"Snapshot: {snapshot.id}, "
            f"realized_pnl: {snapshot.realized_pnl}, "
            f"closed_at: {snapshot.ts_closed}"
        )

def calculate_total_realized_pnl(self) -> Money:
    """计算总已实现盈亏 (包括快照)"""
    total_pnl = Money(0, "USDT")
    
    # 当前持仓的已实现盈亏
    for position in self.cache.positions_open():
        total_pnl = total_pnl + position.realized_pnl
    
    # 已关闭持仓的已实现盈亏 (快照)
    for snapshot in self.cache.position_snapshots():
        total_pnl = total_pnl + snapshot.realized_pnl
    
    return total_pnl
```

---

## 8. 账户管理 (Account Management)

### 8.1 如何查询账户状态

```python
def query_account_status(self) -> None:
    """查询账户状态"""
    
    # 获取账户
    account = self.portfolio.account(venue=Venue("BINANCE"))
    
    if account:
        # 账户基本信息
        self.log.info(f"Account ID: {account.id}")
        self.log.info(f"Account Type: {account.account_type}")
        self.log.info(f"Base Currency: {account.base_currency}")
        
        # 账户状态
        self.log.info(f"Status: {account.status}")
        self.log.info(f"Is Cash Account: {account.is_cash_account()}")
        self.log.info(f"Is Margin Account: {account.is_margin_account()}")
        
        # 余额信息
        balances = account.balances()
        for currency, balance in balances.items():
            self.log.info(f"Balance {currency}: {balance}")
        
        # 可用余额
        free_balances = account.balances_free()
        for currency, balance in free_balances.items():
            self.log.info(f"Free Balance {currency}: {balance}")
        
        # 锁定余额
        locked_balances = account.balances_locked()
        for currency, balance in locked_balances.items():
            self.log.info(f"Locked Balance {currency}: {balance}")
        
        # 保证金
        margins_init = account.margins_init()
        margins_maint = account.margins_maint()
        for currency, margin in margins_init.items():
            self.log.info(f"Init Margin {currency}: {margin}")
        for currency, margin in margins_maint.items():
            self.log.info(f"Maint Margin {currency}: {margin}")
        
        # 盈亏
        unrealized_pnls = account.unrealized_pnls()
        realized_pnls = account.realized_pnls()
        for currency, pnl in unrealized_pnls.items():
            self.log.info(f"Unrealized PnL {currency}: {pnl}")
        for currency, pnl in realized_pnls.items():
            self.log.info(f"Realized PnL {currency}: {pnl}")
        
        # 风险敞口
        net_exposures = account.net_exposures()
        for currency, exposure in net_exposures.items():
            self.log.info(f"Net Exposure {currency}: {exposure}")
        
        # 统计
        self.log.info(f"Starting Balance: {account.starting_balance()}")
        self.log.info(f"Peak Value: {account.peak_value()}")
        self.log.info(f"Current Value: {account.value()}")
```

### 8.2 如何监控账户余额

```python
class AccountMonitor(Actor):
    def __init__(self, config: ActorConfig) -> None:
        super().__init__(config)
        self.alert_thresholds = {
            "min_balance": Money(10_000, "USDT"),
            "max_margin_usage": Decimal("0.80"),
        }
    
    def on_start(self) -> None:
        self.clock.set_timer(
            "balance_check",
            timedelta(minutes=1),
            callback=self._check_balance,
        )
    
    def _check_balance(self) -> None:
        """检查账户余额"""
        account = self.portfolio.account(venue=Venue("BINANCE"))
        
        if not account:
            return
        
        # 检查最低余额
        total_balance = account.value()
        if total_balance < self.alert_thresholds["min_balance"]:
            self._send_alert("LOW_BALANCE", f"Balance: {total_balance}")
        
        # 检查保证金使用率
        margins_init = account.margins_init()
        total_margin = sum(margins_init.values(), Money(0, "USDT"))
        margin_usage = total_margin / total_balance if total_balance > 0 else Decimal("0")
        
        if margin_usage > self.alert_thresholds["max_margin_usage"]:
            self._send_alert("HIGH_MARGIN", f"Margin Usage: {margin_usage:.2%}")
    
    def _send_alert(self, alert_type: str, message: str) -> None:
        """发送警报"""
        self.log.warning(f"[ACCOUNT ALERT] {alert_type}: {message}")
```

### 8.3 如何处理账户事件

```python
class AccountEventHandler(Strategy):
    def on_account(self, account: Account) -> None:
        """账户状态更新"""
        self.log.info(
            f"Account update: {account.id}, "
            f"value: {account.value()}, "
            f"free: {account.balances_free()}"
        )
```

---

## 9. 适配器配置 (Adapter Configuration)

### 9.1 如何配置 Binance 适配器

```python
from nautilus_trader.adapters.binance.config import BinanceLiveConfig, BinanceSpotConfig, BinanceFuturesConfig

# Spot 现货配置
spot_config = BinanceSpotConfig(
    api_key=os.getenv("BINANCE_API_KEY"),
    api_secret=os.getenv("BINANCE_API_SECRET"),
    instrument_ids=["BTCUSDT.BINANCE", "ETHUSDT.BINANCE"],
    account_type=AccountType.CASH,
    use_testnet=False,
)

# Futures 期货配置
futures_config = BinanceFuturesConfig(
    api_key=os.getenv("BINANCE_FUTURES_API_KEY"),
    api_secret=os.getenv("BINANCE_FUTURES_API_SECRET"),
    instrument_ids=["BTCUSDT-PERP.BINANCE"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
)
```

### 9.2 如何配置 Bybit 适配器

```python
from nautilus_trader.adapters.bybit.config import BybitLiveConfig

bybit_config = BybitLiveConfig(
    api_key=os.getenv("BYBIT_API_KEY"),
    api_secret=os.getenv("BYBIT_API_SECRET"),
    instrument_ids=["BTCUSDT.BYBIT", "ETHUSDT.BYBIT"],
    account_type=AccountType.MARGIN,
    use_testnet=False,
    demo_trading=False,
)
```

### 9.3 如何配置 Interactive Brokers 适配器

```python
from nautilus_trader.adapters.interactive_brokers.config import InteractiveBrokersConfig

ib_config = InteractiveBrokersConfig(
    ibg_host="127.0.0.1",
    ibg_port=7496,  # 7496=TWS, 4001=Gateway
    ibg_client_id=1,
    account_ids=["DU123456"],
    readonly=False,
)
```

### 9.4 如何配置沙箱适配器

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
    latency_model={
        "mean_ms": 50,
        "std_ms": 10,
    },
)
```

---

## 10. 性能优化 (Performance Optimization)

### 10.1 如何优化回测速度

```python
# 1. 使用 Bar 数据而非 Tick 数据
data_config = DataConfig(
    catalog_path="./catalog",
    bar_type="1-HOUR",  # 而非 quote_ticks 或 trade_ticks
)

# 2. 减少分析开销
engine_config = BacktestEngineConfig(
    run_analysis=False,  # 禁用绩效分析
)

# 3. 减少缓存容量
cache_config = CacheConfig(
    tick_capacity=1_000,  # 减少缓存
    bar_capacity=500,
)

# 4. 禁用日志
logging_config = LoggingConfig(
    log_level="WARNING",  # 减少日志输出
)

# 5. 使用更少的策略
# 一次只运行一个策略进行优化
```

### 10.2 如何优化内存使用

```python
# 1. 配置缓存容量
cache_config = CacheConfig(
    tick_capacity=5_000,
    bar_capacity=2_000,
)

# 2. 定期清理缓存
def cleanup_cache(self) -> None:
    # 清理旧数据
    pass

# 3. 使用 Redis 外部缓存
cache_config = CacheConfig(
    database=DatabaseConfig(
        type="redis",
        host="localhost",
        port=6379,
    ),
)

# 4. 减少数据订阅
# 只订阅必要的数据类型
self.subscribe_bars(bar_type)
# 而非同时订阅 bars + quotes + trades
```

### 10.3 如何优化策略性能

```python
# 1. 缓存计算结果
class OptimizedStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._cached_signal = None
        self._last_calculation_ts = 0
    
    def on_bar(self, bar: Bar) -> None:
        # 避免重复计算
        if bar.ts_event - self._last_calculation_ts < 60_000_000_000:  # 1 分钟
            return
        
        self._cached_signal = self._calculate_signal()
        self._last_calculation_ts = bar.ts_event

# 2. 使用局部变量
def process_bars(bars: list[Bar]) -> None:
    append = self.signals.append  # 缓存方法引用
    for bar in bars:
        append(self._process(bar))

# 3. 避免在循环中创建对象
# 不好
for bar in bars:
    price = Price.from_str(str(bar.close))

# 好
for bar in bars:
    price = bar.close  # 直接使用
```

---

## 11. 故障排查 (Troubleshooting)

### 11.1 如何诊断连接问题

```python
def diagnose_connection(self) -> None:
    """诊断连接问题"""
    
    # 1. 检查适配器状态
    for adapter in self.node.adapters:
        self.log.info(f"Adapter {adapter.id}: {adapter.state}")
    
    # 2. 检查 WebSocket 连接
    # 查看日志中的连接/断开消息
    
    # 3. 检查 API 密钥
    # 验证 API 密钥权限
    
    # 4. 检查网络
    import socket
    try:
        socket.create_connection(("api.binance.com", 443), timeout=5)
        self.log.info("Network connection OK")
    except Exception as e:
        self.log.error(f"Network connection failed: {e}")
    
    # 5. 检查时间同步
    from nautilus_trader.core.datetime import unix_nanos_to_dt
    local_time = unix_nanos_to_dt(self.clock.timestamp_ns())
    self.log.info(f"Local time: {local_time}")
```

### 11.2 如何诊断订单问题

```python
def diagnose_order_issues(self) -> None:
    """诊断订单问题"""
    
    # 1. 检查订单状态
    orders = self.cache.orders()
    for order in orders:
        self.log.info(f"Order {order.client_order_id}: {order.status}")
    
    # 2. 检查订单拒绝原因
    # 查看 OrderRejected 事件中的 reason 字段
    
    # 3. 检查风险引擎
    # 查看是否触发风险限制
    
    # 4. 检查账户余额
    account = self.portfolio.account(venue=Venue("BINANCE"))
    self.log.info(f"Available balance: {account.balances_free()}")
    
    # 5. 检查订单参数
    # 验证价格/数量精度
```

### 11.3 如何查看日志

```bash
# 查看实时日志
tail -f logs/nautilus_trader.log

# 查看错误日志
grep ERROR logs/nautilus_trader.log

# 查看特定策略日志
grep "MyStrategy" logs/nautilus_trader.log

# 查看特定时间段日志
awk '/2024-01-01/,/2024-01-02/' logs/nautilus_trader.log

# 使用 journalctl (systemd)
journalctl -u nautilus-trader -f
```

---

## 12. 监控与报警 (Monitoring & Alerting)

### 12.1 如何设置 Prometheus 监控

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'nautilus-trader'
    static_configs:
      - targets: ['trader:8000']
    metrics_path: '/metrics'
```

### 12.2 如何设置警报规则

```yaml
# alerts.yml
groups:
  - name: nautilus_trader_alerts
    rules:
      - alert: TraderDown
        expr: up{job="nautilus-trader"} == 0
        for: 5m
        annotations:
          summary: "Nautilus Trader is down"

      - alert: LargeDrawdown
        expr: current_drawdown > 0.1
        for: 1m
        annotations:
          summary: "Large drawdown detected"
```

### 12.3 如何集成 Telegram 通知

```python
import asyncio
import aiohttp

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(self, message: str) -> None:
        """发送 Telegram 消息"""
        url = f"{self.base_url}/sendMessage"
        data = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    print(f"Failed to send message: {await response.text()}")

# 使用示例
notifier = TelegramNotifier(
    bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    chat_id=os.getenv("TELEGRAM_CHAT_ID"),
)

asyncio.run(notifier.send_message("🚨 Trading Alert: Large drawdown detected!"))
```

---

## 13. 数据导出 (Data Export)

### 13.1 如何导出回测数据

```python
def export_backtest_data(results, output_dir: str) -> None:
    """导出回测数据"""
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for result in results:
        # 导出绩效报告
        result.save_reports(output_path)
        
        # 导出为 CSV
        import pandas as pd
        
        # 订单
        orders = result.orders()
        orders_df = pd.DataFrame([o.to_dict() for o in orders])
        orders_df.to_csv(output_path / f"{result.strategy_id}_orders.csv", index=False)
        
        # 成交
        fills = result.fills()
        fills_df = pd.DataFrame([f.to_dict() for f in fills])
        fills_df.to_csv(output_path / f"{result.strategy_id}_fills.csv", index=False)
        
        # 持仓
        positions = result.positions()
        positions_df = pd.DataFrame([p.to_dict() for p in positions])
        positions_df.to_csv(output_path / f"{result.strategy_id}_positions.csv", index=False)
```

### 13.2 如何导出数据到数据库

```python
import sqlite3
from datetime import datetime

def export_to_sqlite(results, db_path: str) -> None:
    """导出到 SQLite 数据库"""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 创建表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY,
            strategy_id TEXT,
            instrument_id TEXT,
            side TEXT,
            price REAL,
            quantity REAL,
            pnl REAL,
            timestamp TEXT
        )
    ''')
    
    # 插入数据
    for result in results:
        for fill in result.fills():
            cursor.execute('''
                INSERT INTO trades (strategy_id, instrument_id, side, price, quantity, pnl, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.strategy_id,
                fill.instrument_id,
                fill.order_side,
                float(fill.price),
                float(fill.quantity),
                float(fill.realized_pnl) if hasattr(fill, 'realized_pnl') else 0,
                datetime.fromtimestamp(fill.ts_event / 1e9).isoformat(),
            ))
    
    conn.commit()
    conn.close()
```

---

## 14. 系统集成 (System Integration)

### 14.1 如何集成外部信号系统

```python
class ExternalSignalStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self.signal_queue = asyncio.Queue()
    
    def on_start(self) -> None:
        # 订阅外部信号
        self.subscribe_signal("external_signal")
        
        # 启动信号处理器
        asyncio.create_task(self._process_signals())
    
    def on_signal(self, signal) -> None:
        """接收外部信号"""
        self.signal_queue.put_nowait(signal)
    
    async def _process_signals(self) -> None:
        """处理信号队列"""
        while True:
            signal = await self.signal_queue.get()
            self._execute_signal(signal)
    
    def _execute_signal(self, signal) -> None:
        """执行信号"""
        if signal.value == "BUY":
            self._buy()
        elif signal.value == "SELL":
            self._sell()
```

### 14.2 如何集成机器学习模型

```python
import joblib
from nautilus_trader.trading.strategy import Strategy

class MLStrategy(Strategy):
    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self.model = joblib.load("./models/trading_model.pkl")
        self.features = []
    
    def on_bar(self, bar: Bar) -> None:
        # 提取特征
        features = self._extract_features(bar)
        self.features.append(features)
        
        # 等待足够特征
        if len(self.features) >= 20:
            # 预测
            X = np.array(self.features[-20:])
            prediction = self.model.predict(X)
            
            # 执行交易
            if prediction > 0.7:
                self._buy()
            elif prediction < 0.3:
                self._sell()
    
    def _extract_features(self, bar: Bar) -> list[float]:
        """提取特征"""
        return [
            float(bar.open),
            float(bar.high),
            float(bar.low),
            float(bar.close),
            float(bar.volume),
        ]
```

---

## 附录 A: 快速参考

### A.1 常用命令

```bash
# 回测
python -m backtests.run_backtest

# 实盘
python -m live.run_live

# 构建数据目录
python scripts/build_catalog.py

# 查看日志
tail -f logs/nautilus_trader.log

# Docker 部署
docker-compose up -d
```

### A.2 资源链接

| 资源 | 链接 |
|------|------|
| 官方文档 | https://nautilustrader.io/docs/ |
| How-To 文档 | https://nautilustrader.io/docs/nightly/how_to/ |
| GitHub | https://github.com/nautechsystems/nautilus_trader |
| 社区讨论 | https://github.com/nautechsystems/nautilus_trader/discussions |

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-03-31  
> **维护者**: Nautilus Trader 社区

---

此 Markdown 文件包含完整的 How-To 目录内容汇总，可直接用于 AI 工具编程参考。如需进一步细化某个操作指南的细节，请告知！