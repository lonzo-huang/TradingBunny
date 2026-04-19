# Nautilus Trader Developer Guide 开发者指南汇总

> **文档版本**: develop 分支 (2026 年 3 月)  
> **适用对象**: 核心开发者、贡献者、系统架构师  
> **用途**: AI 工具编程参考文档

---

## 目录

1. [开发环境设置 (Development Setup)](#1-开发环境设置-development-setup)
2. [项目结构 (Project Structure)](#2-项目结构-project-structure)
3. [代码规范 (Code Standards)](#3-代码规范-code-standards)
4. [测试指南 (Testing Guide)](#4-测试指南-testing-guide)
5. [构建流程 (Build Process)](#5-构建流程-build-process)
6. [贡献指南 (Contribution Guide)](#6-贡献指南-contribution-guide)
7. [Rust 开发 (Rust Development)](#7-rust 开发-rust-development)
8. [Python 开发 (Python Development)](#8-python 开发-python-development)
9. [PyO3 绑定 (PyO3 Bindings)](#9-pyo3 绑定-pyo3-bindings)
10. [调试技巧 (Debugging Tips)](#10-调试技巧-debugging-tips)
11. [性能优化 (Performance Optimization)](#11-性能优化-performance-optimization)
12. [发布流程 (Release Process)](#12-发布流程-release-process)
13. [常见问题 (FAQ)](#13-常见问题-faq)

---

## 1. 开发环境设置 (Development Setup)

### 1.1 系统要求

| 组件 | 最低版本 | 推荐版本 |
|------|---------|---------|
| Python | 3.12 | 3.13 |
| Rust | 1.75 | 1.80+ |
| Cargo | 1.75 | 1.80+ |
| Git | 2.30 | 2.40+ |
| Ubuntu | 22.04 | 24.04 |
| macOS | 15.0 (ARM64) | 15.0+ (ARM64) |
| Windows | Server 2022 | Server 2022+ |

### 1.2 安装依赖

**Ubuntu/Debian**:
```bash
# 系统依赖
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    python3-venv \
    cargo \
    rustc \
    git \
    curl

# 安装 Rust (推荐方式)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# 验证安装
rustc --version
cargo --version
python3 --version
```

**macOS (ARM64)**:
```bash
# 使用 Homebrew
brew install python@3.12 rust git openssl

# 设置 OpenSSL 路径 (M1/M2)
export OPENSSL_DIR=$(brew --prefix openssl)
export LIBRARY_PATH=$LIBRARY_PATH:$(brew --prefix openssl)/lib
export CPATH=$CPATH:$(brew --prefix openssl)/include
```

**Windows**:
```powershell
# 安装 Rust
winget install Rustlang.Rust.GNU

# 安装 Python
winget install Python.Python.3.12

# 安装 Visual Studio Build Tools
winget install Microsoft.VisualStudio.2022.BuildTools

# 验证安装
rustc --version
python --version
```

### 1.3 克隆项目

```bash
# 克隆仓库
git clone --branch develop --depth 1 https://github.com/nautechsystems/nautilus_trader.git
cd nautilus_trader

# 安装 uv 包管理器 (推荐)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 创建虚拟环境并安装依赖
uv sync --all-extras

# 或传统方式
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows
pip install -e ".[all,dev]"
```

### 1.4 IDE 配置

**VS Code 设置** (`settings.json`):
```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "rust-analyzer.checkOnSave.command": "clippy",
    "rust-analyzer.cargo.allFeatures": true
}
```

**推荐扩展**:
- Python (Microsoft)
- Ruff (Charlie Marsh)
- Rust Analyzer (rust-lang)
- Black Formatter (Microsoft)
- GitLens (GitKraken)

### 1.5 预提交钩子

```bash
# 安装 pre-commit
pip install pre-commit

# 安装钩子
pre-commit install

# 验证钩子
pre-commit run --all-files

# 更新钩子
pre-commit autoupdate
```

**.pre-commit-config.yaml**:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
        args: ['--maxkb=1000']

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-all
          - pytest

  - repo: local
    hooks:
      - id: cargo-check
        name: cargo check
        entry: cargo check --all-targets
        language: system
        pass_filenames: false
        files: \.rs$
```

---

## 2. 项目结构 (Project Structure)

### 2.1 目录结构

```
nautilus_trader/
├── .github/                    # GitHub 配置
│   ├── workflows/              # CI/CD 工作流
│   ├── ISSUE_TEMPLATE/         # Issue 模板
│   └── PULL_REQUEST_TEMPLATE/  # PR 模板
│
├── crates/                     # Rust 代码 (核心)
│   ├── core/                   # 核心原语
│   ├── model/                  # 领域模型
│   ├── common/                 # 通用组件
│   ├── system/                 # 系统内核
│   ├── trading/                # 交易组件
│   ├── data/                   # 数据引擎
│   ├── execution/              # 执行引擎
│   ├── portfolio/              # 投资组合
│   ├── risk/                   # 风险管理
│   ├── persistence/            # 持久化
│   ├── live/                   # 实盘节点
│   ├── backtest/               # 回测节点
│   └── adapters/               # 交易所适配器
│
├── nautilus_trader/            # Python/Cython 绑定
│   ├── account/                # 账户管理
│   ├── adapters/               # Python 适配器
│   ├── analysis/               # 分析工具
│   ├── backtest/               # 回测模块
│   ├── cache/                  # 缓存模块
│   ├── common/                 # 通用模块
│   ├── config/                 # 配置模块
│   ├── data/                   # 数据模块
│   ├── execution/              # 执行模块
│   ├── indicators/             # 技术指标
│   ├── live/                   # 实盘模块
│   ├── model/                  # 模型模块
│   ├── persistence/            # 持久化模块
│   ├── portfolio/              # 投资组合模块
│   ├── risk/                   # 风险模块
│   ├── system/                 # 系统模块
│   ├── trading/                # 交易模块
│   └── examples/               # 示例代码
│
├── docs/                       # 文档
│   ├── getting_started/        # 入门指南
│   ├── concepts/               # 核心概念
│   ├── tutorials/              # 教程
│   ├── how_to/                 # 操作指南
│   ├── developer_guide/        # 开发者指南
│   ├── api_reference/          # API 参考
│   └── integrations/           # 集成文档
│
├── tests/                      # 测试
│   ├── unit_tests/             # 单元测试
│   ├── integration_tests/      # 集成测试
│   ├── acceptance_tests/       # 验收测试
│   └── fixtures/               # 测试固件
│
├── examples/                   # 完整示例
│   ├── strategies/             # 策略示例
│   ├── backtest/               # 回测示例
│   └── live/                   # 实盘示例
│
├── scripts/                    # 工具脚本
│   ├── build/                  # 构建脚本
│   ├── release/                # 发布脚本
│   └── tools/                  # 开发工具
│
├── pyproject.toml              # Python 项目配置
├── Cargo.toml                  # Rust 项目配置
├── Cargo.lock                  # Rust 依赖锁定
├── requirements.txt            # Python 依赖
├── .pre-commit-config.yaml     # 预提交配置
├── .gitignore                  # Git 忽略文件
└── README.md                   # 项目说明
```

### 2.2 Rust Crate 结构

```
crates/nautilus_core/
├── Cargo.toml              # Crate 配置
├── src/
│   ├── lib.rs              # 库入口
│   ├── uuid.rs             # UUID 实现
│   ├── datetime.rs         # 日期时间
│   ├── identifiers.rs      # 标识符
│   └── message.rs          # 消息系统
├── tests/                  # 集成测试
│   └── integration_test.rs
└── benches/                # 性能基准测试
    └── benchmark.rs
```

### 2.3 Python 模块结构

```
nautilus_trader/core/
├── __init__.py             # 模块入口
├── data.pyx                # Cython 数据类
├── message.pyx             # Cython 消息类
├── datetime.pxd            # Cython 头文件
├── datetime.pyx            # Cython 实现
└── rust/                   # Rust 绑定
    ├── __init__.py
    └── nautilus_pyo3.py    # PyO3 导入
```

### 2.4 关键文件说明

| 文件 | 用途 |
|------|------|
| `pyproject.toml` | Python 项目配置、依赖、构建系统 |
| `Cargo.toml` | Rust 工作空间配置 |
| `build.py` | Cython 构建脚本 |
| `justfile` | Just 命令定义 (类似 Makefile) |
| `.github/workflows/ci.yml` | CI/CD 流水线配置 |
| `tests/conftest.py` | pytest 共享固件 |

---

## 3. 代码规范 (Code Standards)

### 3.1 Python 代码规范

**命名约定**:
```python
# 类名：PascalCase
class MyStrategy(Strategy):
    pass

# 函数/方法：snake_case
def calculate_ema(period: int) -> EMA:
    pass

# 常量：UPPER_SNAKE_CASE
MAX_POSITION_SIZE = 1000
DEFAULT_TIMEOUT_MS = 5000

# 私有属性：前缀下划线
self._internal_state = None

# 受保护属性：前缀双下划线
self.__private_attr = None
```

**类型注解**:
```python
from typing import Optional, List, Dict, Any
from decimal import Decimal
from nautilus_trader.model.objects import Price, Quantity

# 函数签名必须带类型注解
def calculate_pnl(
    entry_price: Price,
    exit_price: Price,
    quantity: Quantity,
    multiplier: Decimal = Decimal("1"),
) -> Decimal:
    """计算盈亏"""
    return (exit_price - entry_price) * quantity * multiplier

# 可选类型
def get_order(order_id: Optional[str] = None) -> Optional[Order]:
    pass

# 集合类型
def get_instruments() -> List[Instrument]:
    pass

def get_config() -> Dict[str, Any]:
    pass
```

**文档字符串**:
```python
def submit_order(
    self,
    order: Order,
    position_id: Optional[PositionId] = None,
) -> None:
    """
    提交订单到执行引擎。

    Parameters
    ----------
    order : Order
        要提交的订单对象。
    position_id : PositionId, optional
        可选的持仓 ID (用于 OMS 对冲模式)。

    Raises
    ------
    ValueError
        如果订单参数无效。
    RuntimeError
        如果执行引擎未运行。

    Examples
    --------
    >>> order = order_factory.market(...)
    >>> strategy.submit_order(order)
    """
    pass
```

**代码风格检查**:
```bash
# 使用 Ruff 检查
ruff check nautilus_trader/

# 自动修复
ruff check --fix nautilus_trader/

# 格式化代码
ruff format nautilus_trader/

# 类型检查
mypy nautilus_trader/ --strict
```

### 3.2 Rust 代码规范

**命名约定**:
```rust
// 结构体/枚举：PascalCase
pub struct OrderBook {
    // 字段：snake_case
    pub bids: PriceLevel,
    pub asks: PriceLevel,
}

// 函数/方法：snake_case
pub fn calculate_midpoint(bids: &PriceLevel, asks: &PriceLevel) -> Price {
    // 局部变量：snake_case
    let best_bid = bids.best_price();
    let best_ask = asks.best_price();
    (best_bid + best_ask) / 2
}

// 常量：SCREAMING_SNAKE_CASE
pub const MAX_ORDER_SIZE: u64 = 1_000_000;
pub const DEFAULT_TIMEOUT_MS: u64 = 5_000;

// 特质：PascalCase
pub trait DataHandler {
    fn handle_data(&self, data: &Data);
}
```

**错误处理**:
```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum TradingError {
    #[error("Invalid order: {0}")]
    InvalidOrder(String),
    
    #[error("Insufficient balance: required={required}, available={available}")]
    InsufficientBalance { required: Money, available: Money },
    
    #[error("Connection failed: {0}")]
    ConnectionFailed(#[from] std::io::Error),
}

pub type Result<T> = std::result::Result<T, TradingError>;

// 使用 Result
fn submit_order(order: &Order) -> Result<OrderId> {
    if order.quantity <= Quantity::zero() {
        return Err(TradingError::InvalidOrder("Quantity must be positive".into()));
    }
    Ok(order.id())
}
```

**文档注释**:
```rust
/// 订单簿管理器
/// 
/// 负责维护和管理限价订单簿的状态，支持 L1/L2/L3 深度。
/// 
/// # Examples
/// 
/// ```
/// let mut book = OrderBook::new(instrument_id, BookType::L2_MBP);
/// book.apply_delta(delta);
/// let midpoint = book.midpoint().unwrap();
/// ```
/// 
/// # Errors
/// 
/// 如果订单簿状态不一致，返回 `IntegrityError`。
pub struct OrderBook {
    /// 工具标识符
    pub instrument_id: InstrumentId,
    /// 订单簿类型
    pub book_type: BookType,
    /// 买单侧
    bids: PriceLevel,
    /// 卖单侧
    asks: PriceLevel,
}
```

**代码风格检查**:
```bash
# 格式化代码
cargo fmt --all

# 检查代码
cargo clippy --all-targets -- -D warnings

# 运行测试
cargo test --all

# 基准测试
cargo bench
```

### 3.3 Git 提交规范

**提交消息格式**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型 (type)**:
| 类型 | 描述 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档更新 |
| `style` | 代码格式 (不影响功能) |
| `refactor` | 代码重构 |
| `perf` | 性能优化 |
| `test` | 测试相关 |
| `chore` | 构建/工具/配置 |

**示例**:
```bash
# 新功能
git commit -m "feat(adapter): add Bybit options support"

# Bug 修复
git commit -m "fix(execution): resolve order duplicate issue"

# 文档更新
git commit -m "docs(concepts): update position lifecycle diagram"

# 重构
git commit -m "refactor(core): simplify timestamp handling"

# 完整提交消息
git commit -m "feat(strategy): add trailing stop support

- Implement TrailingStopMarket order type
- Implement TrailingStopLimit order type
- Add simulation logic for trailing stops
- Update documentation

Closes #1234"
```

### 3.4 分支管理

**分支命名**:
```bash
# 功能分支
feature/add-new-adapter
feature/improve-performance

# 修复分支
fix/order-duplicate-issue
fix/memory-leak

# 文档分支
docs/update-api-reference
docs/add-tutorial

# 发布分支
release/1.200.0
release/1.201.0-rc1
```

**工作流**:
```bash
# 创建功能分支
git checkout develop
git pull origin develop
git checkout -b feature/my-feature

# 开发完成后
git push origin feature/my-feature

# 创建 Pull Request
# 等待 CI 通过和代码审查

# 合并到 develop
git checkout develop
git pull origin develop
git merge --no-ff feature/my-feature
git push origin develop

# 删除功能分支
git branch -d feature/my-feature
git push origin --delete feature/my-feature
```

---

## 4. 测试指南 (Testing Guide)

### 4.1 测试类型

| 类型 | 位置 | 用途 | 运行命令 |
|------|------|------|---------|
| 单元测试 | `tests/unit_tests/` | 测试单个函数/类 | `pytest tests/unit_tests/` |
| 集成测试 | `tests/integration_tests/` | 测试组件交互 | `pytest tests/integration_tests/` |
| 验收测试 | `tests/acceptance_tests/` | 测试完整流程 | `pytest tests/acceptance_tests/` |
| Rust 测试 | `crates/*/tests/` | Rust 代码测试 | `cargo test` |
| 基准测试 | `crates/*/benches/` | 性能基准 | `cargo bench` |

### 4.2 单元测试模板

**Python 单元测试**:
```python
# tests/unit_tests/test_strategy.py
import pytest
from decimal import Decimal
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide

from nautilus_trader.examples.strategies.ema_cross import EMACross, EMACrossConfig

@pytest.fixture
def backtest_engine():
    """创建回测引擎固件"""
    config = BacktestEngineConfig(
        trader_id="TESTER-001",
        run_analysis=False,
    )
    engine = BacktestEngine(config=config)
    yield engine
    engine.dispose()

@pytest.fixture
def strategy_config():
    """策略配置固件"""
    return EMACrossConfig(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
        bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR-LAST-INTERNAL"),
        fast_ema_period=10,
        slow_ema_period=20,
        trade_size=Decimal("0.1"),
        order_id_tag="001",
    )

def test_strategy_initialization(strategy_config):
    """测试策略初始化"""
    strategy = EMACross(config=strategy_config)
    
    assert strategy is not None
    assert strategy.config.fast_ema_period == 10
    assert strategy.config.slow_ema_period == 20
    assert strategy.instrument is None

def test_strategy_on_start(strategy_config, backtest_engine):
    """测试策略启动"""
    strategy = EMACross(config=strategy_config)
    backtest_engine.add_strategy(strategy)
    
    # 添加工具
    instrument = make_test_instrument()
    backtest_engine.add_instrument(instrument)
    
    strategy.on_start()
    
    assert strategy.instrument is not None
    assert strategy.fast_ema is not None
    assert strategy.slow_ema is not None

def test_strategy_on_bar(strategy_config, backtest_engine):
    """测试 K 线处理"""
    strategy = EMACross(config=strategy_config)
    backtest_engine.add_strategy(strategy)
    backtest_engine.add_instrument(make_test_instrument())
    strategy.on_start()
    
    # 创建测试 K 线
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
    
    # 处理足够 K 线使指标预热
    for i in range(25):
        strategy.on_bar(bar)
    
    assert strategy.fast_ema.value > 0
    assert strategy.slow_ema.value > 0

@pytest.mark.parametrize(
    "fast_period,slow_period,expected_signal",
    [
        (10, 20, "BUY"),
        (20, 10, "SELL"),
        (10, 10, None),  # 相同周期无信号
    ],
)
def test_ema_cross_signals(fast_period, slow_period, expected_signal):
    """参数化测试 EMA 交叉信号"""
    config = EMACrossConfig(
        instrument_id=InstrumentId.from_str("BTCUSDT.BINANCE"),
        bar_type=BarType.from_str("BTCUSDT.BINANCE-1-HOUR"),
        fast_ema_period=fast_period,
        slow_ema_period=slow_period,
        trade_size=Decimal("0.1"),
        order_id_tag="001",
    )
    
    strategy = EMACross(config=config)
    # 测试逻辑...
```

**Rust 单元测试**:
```rust
// crates/nautilus_model/tests/order_book_test.rs
use nautilus_model::order_book::OrderBook;
use nautilus_model::data::OrderBookDelta;
use nautilus_model::identifiers::InstrumentId;

#[test]
fn test_order_book_creation() {
    let instrument_id = InstrumentId::from_str("BTCUSDT.BINANCE").unwrap();
    let book = OrderBook::new(instrument_id, BookType::L2_MBP);
    
    assert_eq!(book.instrument_id(), instrument_id);
    assert_eq!(book.book_type(), BookType::L2_MBP);
    assert_eq!(book.bids().len(), 0);
    assert_eq!(book.asks().len(), 0);
}

#[test]
fn test_order_book_apply_delta() {
    let instrument_id = InstrumentId::from_str("BTCUSDT.BINANCE").unwrap();
    let mut book = OrderBook::new(instrument_id, BookType::L2_MBP);
    
    let delta = OrderBookDelta::new(
        instrument_id,
        BookAction::ADD,
        Order::new(Price::from_str("50000.00").unwrap(), Quantity::from_str("1.0").unwrap()),
        1630000000000000000,
        1630000000000000000,
    );
    
    book.apply_delta(&delta).unwrap();
    
    assert_eq!(book.bids().len(), 1);
    assert_eq!(book.best_bid_price(), Some(Price::from_str("50000.00").unwrap()));
}

#[test]
#[should_panic(expected = "Invalid price")]
fn test_order_book_invalid_delta() {
    let instrument_id = InstrumentId::from_str("BTCUSDT.BINANCE").unwrap();
    let mut book = OrderBook::new(instrument_id, BookType::L2_MBP);
    
    // 创建无效 delta (负价格)
    let delta = OrderBookDelta::new(
        instrument_id,
        BookAction::ADD,
        Order::new(Price::from_str("-1.00").unwrap(), Quantity::from_str("1.0").unwrap()),
        1630000000000000000,
        1630000000000000000,
    );
    
    book.apply_delta(&delta).unwrap();
}

#[tokio::test]
async fn test_order_book_async_operations() {
    // 异步测试
    let instrument_id = InstrumentId::from_str("BTCUSDT.BINANCE").unwrap();
    let mut book = OrderBook::new(instrument_id, BookType::L2_MBP);
    
    // 异步操作...
}
```

### 4.3 集成测试模板

```python
# tests/integration_tests/test_backtest_integration.py
import pytest
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.backtest.config import (
    BacktestRunConfig,
    BacktestEngineConfig,
    BacktestVenueConfig,
)
from nautilus_trader.config import CacheConfig, LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType

@pytest.fixture
def backtest_config():
    """回测配置固件"""
    return BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id="INTEGRATION-001",
            run_analysis=True,
            cache=CacheConfig(tick_capacity=10_000),
            logging=LoggingConfig(log_level="WARNING"),
        ),
        venues=[
            BacktestVenueConfig(
                name="BINANCE",
                oms_type=OmsType.NETTING,
                account_type=AccountType.MARGIN,
                base_currency="USDT",
                starting_balances=[Money(1_000_000, "USDT")],
            ),
        ],
        data=[
            DataConfig(
                catalog_path="./tests/fixtures/catalog",
                instrument_id="BTCUSDT.BINANCE",
                bar_type="1-HOUR",
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

def test_backtest_runs_successfully(backtest_config):
    """测试回测成功运行"""
    node = BacktestNode(configs=[backtest_config])
    results = node.run()
    
    assert len(results) > 0
    assert results[0].performance is not None
    assert results[0].performance.total_return is not None

def test_backtest_generates_reports(backtest_config, tmp_path):
    """测试回测生成报告"""
    node = BacktestNode(configs=[backtest_config])
    results = node.run()
    
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    
    results[0].save_reports(report_dir)
    
    assert (report_dir / "performance.html").exists()
    assert (report_dir / "positions.parquet").exists()
    assert (report_dir / "orders.parquet").exists()

@pytest.mark.slow
def test_full_backtest_with_analysis(backtest_config):
    """完整回测带分析 (慢测试)"""
    node = BacktestNode(configs=[backtest_config])
    results = node.run()
    
    performance = results[0].performance
    
    # 验证关键指标
    assert performance.total_return > -1.0  # 不会亏损超过 100%
    assert performance.max_drawdown >= 0
    assert performance.total_trades >= 0
```

### 4.4 测试覆盖率

```bash
# 运行测试并生成覆盖率报告
pytest tests/ --cov=nautilus_trader --cov-report=html --cov-report=term

# 查看覆盖率摘要
coverage report

# 生成 HTML 报告
coverage html

# 打开报告
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows

# 覆盖率目标 (在 pyproject.toml 中配置)
[tool.coverage.run]
source = ["nautilus_trader"]
omit = ["*/tests/*", "*/__init__.py"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "if TYPE_CHECKING:",
]
show_missing = true
precision = 2
fail_under = 80  # 最低覆盖率要求
```

### 4.5 测试最佳实践

**固件管理**:
```python
# tests/conftest.py
import pytest
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.identifiers import InstrumentId, Symbol

@pytest.fixture(scope="session")
def test_instrument():
    """会话级测试工具固件"""
    return CurrencyPair(
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

@pytest.fixture
def mock_clock():
    """模拟时钟"""
    return TestClock()

@pytest.fixture
def mock_msgbus():
    """模拟消息总线"""
    return MessageBus(trader_id=TraderId("TESTER-001"))
```

**模拟对象**:
```python
from unittest.mock import Mock, AsyncMock, patch, MagicMock

def test_with_mock():
    """使用模拟对象测试"""
    mock_client = Mock()
    mock_client.fetch.return_value = {"data": "test"}
    
    result = my_function(mock_client)
    
    mock_client.fetch.assert_called_once()
    assert result == "expected"

@pytest.mark.asyncio
async def test_with_async_mock():
    """使用异步模拟对象"""
    mock_client = AsyncMock()
    mock_client.fetch.return_value = {"data": "test"}
    
    result = await my_async_function(mock_client)
    
    mock_client.fetch.assert_awaited_once()
```

**参数化测试**:
```python
@pytest.mark.parametrize(
    "input_value,expected",
    [
        (100, "100"),
        (100.50, "100.50"),
        (Decimal("100.50"), "100.50"),
    ],
)
def test_format_value(input_value, expected):
    """参数化测试"""
    assert format_value(input_value) == expected
```

**标记测试**:
```python
@pytest.mark.unit
def test_unit():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.slow
def test_slow():
    pass

@pytest.mark.skip(reason="Not implemented yet")
def test_skipped():
    pass

@pytest.mark.skipif(sys.platform == "win32", reason="Not supported on Windows")
def test_platform_specific():
    pass

# 运行特定标记的测试
pytest -m "unit"
pytest -m "integration"
pytest -m "not slow"
```

---

## 5. 构建流程 (Build Process)

### 5.1 构建系统概述

Nautilus Trader 使用混合构建系统:
- **Rust**: Cargo (原生性能核心)
- **Python**: setuptools + Cython + PyO3 (绑定层)
- **打包**: maturin (Rust-Python 混合包)

### 5.2 本地构建

**完整构建**:
```bash
# 清理之前的构建
cargo clean
rm -rf build/ dist/ *.egg-info

# 安装 Rust 依赖
cargo fetch

# 构建 Rust 库
cargo build --release

# 构建 Python 包
python build.py

# 或一步完成
just build

# 开发模式构建 (更快)
just build-dev
```

**Just 命令** (`justfile`):
```just
# 构建命令
build:
    cargo build --release
    python build.py

build-dev:
    cargo build
    python build.py --debug

# 测试命令
test:
    cargo test --all
    pytest tests/unit_tests/

test-integration:
    pytest tests/integration_tests/

# 代码质量
lint:
    cargo clippy --all-targets -- -D warnings
    ruff check nautilus_trader/
    mypy nautilus_trader/ --strict

format:
    cargo fmt --all
    ruff format nautilus_trader/

# 清理
clean:
    cargo clean
    rm -rf build/ dist/ *.egg-info .pytest_cache/
```

### 5.3 Cython 构建

**build.py**:
```python
#!/usr/bin/env python3
"""Nautilus Trader Cython 构建脚本"""

import os
import sys
from setuptools import setup, Extension
from Cython.Build import cythonize
from setuptools_rust import RustExtension

# 编译选项
compile_args = ["-O3"]
link_args = []

if sys.platform == "darwin":
    compile_args.extend(["-std=c++17"])
    link_args.extend(["-stdlib=libc++"])

# Cython 扩展
extensions = [
    Extension(
        "nautilus_trader.core.datetime",
        sources=["nautilus_trader/core/datetime.pyx"],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
    ),
    Extension(
        "nautilus_trader.core.uuid",
        sources=["nautilus_trader/core/uuid.pyx"],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
    ),
    # ... 更多扩展
]

# Rust 扩展
rust_extensions = [
    RustExtension(
        "nautilus_trader.core.nautilus_pyo3",
        path="crates/pyo3/Cargo.toml",
        binding="pyo3",
        debug=False,
    ),
]

setup(
    name="nautilus_trader",
    ext_modules=cythonize(extensions, language_level=3),
    rust_extensions=rust_extensions,
    zip_safe=False,
)
```

### 5.4 平台特定构建

**Linux**:
```bash
# Ubuntu/Debian
sudo apt-get install -y build-essential libssl-dev python3-dev
just build

# 许多 Linux 构建 (用于发布)
just build-manylinux
```

**macOS**:
```bash
# ARM64 (M1/M2)
export OPENSSL_DIR=$(brew --prefix openssl)
export MACOSX_DEPLOYMENT_TARGET=15.0
just build

# Intel
export MACOSX_DEPLOYMENT_TARGET=12.0
just build
```

**Windows**:
```powershell
# 需要 Visual Studio Build Tools
# 设置环境变量
$env:OPENSSL_DIR = "C:\OpenSSL"
$env:LIB = "C:\OpenSSL\lib;$env:LIB"
$env:INCLUDE = "C:\OpenSSL\include;$env:INCLUDE"

# 构建
just build

# 注意：Windows 仅支持 64 位标准精度
```

### 5.5 Docker 构建

**开发容器**:
```dockerfile
FROM ghcr.io/nautechsystems/jupyterlab:nightly

WORKDIR /app

# 复制源代码
COPY . .

# 安装依赖
RUN pip install -e ".[all,dev]"

# 构建 Rust 扩展
RUN cargo build --release

# 设置入口点
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888"]
```

**构建命令**:
```bash
# 构建开发镜像
docker build -t nautilus-trader:dev -f Dockerfile.dev .

# 运行开发容器
docker run -it --rm \
    -v $(pwd):/app \
    -p 8888:8888 \
    nautilus-trader:dev
```

### 5.6 构建问题排查

**常见问题**:

| 问题 | 解决方案 |
|------|---------|
| Rust 编译失败 | `rustup update`, `cargo clean` |
| Cython 编译失败 | 检查 Python 头文件，`pip install --upgrade cython` |
| OpenSSL 链接错误 | 设置 `OPENSSL_DIR` 环境变量 |
| macOS 架构错误 | 确认使用 ARM64 Python 和 Rust |
| Windows MSVC 错误 | 安装 Visual Studio Build Tools |

**调试构建**:
```bash
# 详细输出
just build --verbose

# 仅 Rust
cargo build --release --verbose

# 仅 Python
python build.py --verbose

# 清理后重新构建
just clean && just build
```

---

## 6. 贡献指南 (Contribution Guide)

### 6.1 贡献流程

```
1. Fork 仓库
        ↓
2. 创建功能分支
        ↓
3. 开发功能
        ↓
4. 编写测试
        ↓
5. 提交代码
        ↓
6. 创建 Pull Request
        ↓
7. 代码审查
        ↓
8. CI 检查通过
        ↓
9. 合并到 develop
```

### 6.2 提交 Pull Request

**PR 模板**:
```markdown
## 描述
简要描述此 PR 的更改内容。

## 相关 Issue
Closes #1234

## 更改类型
- [ ] 新功能 (feat)
- [ ] Bug 修复 (fix)
- [ ] 文档更新 (docs)
- [ ] 代码重构 (refactor)
- [ ] 性能优化 (perf)
- [ ] 测试更新 (test)
- [ ] 其他 (chore)

## 测试
- [ ] 已添加单元测试
- [ ] 已添加集成测试
- [ ] 所有测试通过
- [ ] 代码覆盖率满足要求

## 检查清单
- [ ] 代码符合项目规范
- [ ] 已更新文档
- [ ] 已更新 CHANGELOG
- [ ] 无破坏性变更 (或已标记)
```

### 6.3 代码审查标准

**审查要点**:
| 类别 | 检查项 |
|------|--------|
| 功能 | 功能是否正确实现？边界情况是否处理？ |
| 性能 | 是否有性能问题？内存泄漏？ |
| 安全 | 是否有安全漏洞？输入验证？ |
| 测试 | 测试是否充分？覆盖率是否达标？ |
| 文档 | 文档是否更新？注释是否清晰？ |
| 规范 | 是否符合代码规范？命名是否一致？ |

### 6.4 贡献者协议

**重要条款**:
- 贡献代码即同意 MIT 许可证
- 保证代码为原创或有权贡献
- 同意代码可能被修改和重新分发
- 不提供任何担保

---

## 7. Rust 开发 (Rust Development)

### 7.1 Rust 项目结构

```
crates/
├── nautilus_core/        # 核心原语
├── nautilus_model/       # 领域模型
├── nautilus_common/      # 通用组件
├── nautilus_system/      # 系统内核
├── nautilus_trading/     # 交易组件
├── nautilus_data/        # 数据引擎
├── nautilus_execution/   # 执行引擎
├── nautilus_portfolio/   # 投资组合
├── nautilus_risk/        # 风险管理
├── nautilus_persistence/ # 持久化
├── nautilus_live/        # 实盘节点
├── nautilus_backtest/    # 回测节点
└── adapters/             # 交易所适配器
```

### 7.2 Cargo 工作空间

**根 Cargo.toml**:
```toml
[workspace]
resolver = "2"
members = [
    "crates/core",
    "crates/model",
    "crates/common",
    "crates/system",
    "crates/trading",
    "crates/data",
    "crates/execution",
    "crates/portfolio",
    "crates/risk",
    "crates/persistence",
    "crates/live",
    "crates/backtest",
    "crates/adapters/*",
    "crates/pyo3",
]

[workspace.package]
version = "1.200.0"
edition = "2021"
license = "MIT"

[workspace.dependencies]
tokio = { version = "1.35", features = ["full"] }
serde = { version = "1.0", features = ["derive"] }
thiserror = "1.0"
```

### 7.3 编写 Rust 组件

**示例：自定义指标**:
```rust
use nautilus_model::data::bar::Bar;
use nautilus_model::objects::Price;

/// 指数移动平均线指标
pub struct EMA {
    period: usize,
    multiplier: f64,
    value: Option<f64>,
    count: usize,
}

impl EMA {
    pub fn new(period: usize) -> Self {
        Self {
            period,
            multiplier: 2.0 / (period as f64 + 1.0),
            value: None,
            count: 0,
        }
    }

    pub fn handle_bar(&mut self, bar: &Bar) {
        let close_price = f64::from(bar.close());
        
        match self.value {
            None => {
                // 第一个值使用收盘价
                self.value = Some(close_price);
            }
            Some(prev_value) => {
                // EMA = (close * multiplier) + (prev_ema * (1 - multiplier))
                let new_value = (close_price * self.multiplier) 
                    + (prev_value * (1.0 - self.multiplier));
                self.value = Some(new_value);
            }
        }
        
        self.count += 1;
    }

    pub fn value(&self) -> Option<Price> {
        self.value.map(|v| Price::from(v))
    }

    pub fn is_initialized(&self) -> bool {
        self.count >= self.period
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ema_calculation() {
        let mut ema = EMA::new(10);
        
        // 处理 10 根 K 线
        for i in 0..10 {
            let bar = create_test_bar(100.0 + i as f64);
            ema.handle_bar(&bar);
        }
        
        assert!(ema.is_initialized());
        assert!(ema.value().is_some());
    }
}
```

### 7.4 Rust 性能优化

**优化技巧**:
```rust
// 1. 使用迭代器而非循环
let sum: i64 = prices.iter().sum();

// 2. 避免不必要的克隆
fn process_data(data: &Data) -> Result { ... }

// 3. 使用 Cow 避免复制
use std::borrow::Cow;
fn get_name(item: &Item) -> Cow<str> { ... }

// 4. 预分配容量
let mut vec = Vec::with_capacity(1000);

// 5. 使用 rayon 并行处理
use rayon::prelude::*;
let results: Vec<_> = data.par_iter().map(process).collect();

// 6. 使用对象池
use object_pool::Pool;
static POOL: Pool<Vec<u8>> = Pool::new(100, || Vec::with_capacity(1024));
```

---

## 8. Python 开发 (Python Development)

### 8.1 Python 模块结构

```
nautilus_trader/
├── __init__.py
├── account/
│   ├── __init__.py
│   └── accounts.py
├── adapters/
│   ├── __init__.py
│   └── binance/
├── analysis/
│   ├── __init__.py
│   ├── performance.py
│   └── plotter.py
├── backtest/
│   ├── __init__.py
│   ├── engine.py
│   └── node.py
├── cache/
│   ├── __init__.py
│   └── cache.py
├── common/
│   ├── __init__.py
│   ├── actors.py
│   └── components.py
├── config/
│   ├── __init__.py
│   └── config.py
├── data/
│   ├── __init__.py
│   ├── client.py
│   └── engine.py
├── execution/
│   ├── __init__.py
│   ├── client.py
│   └── engine.py
├── indicators/
│   ├── __init__.py
│   └── ema.py
├── live/
│   ├── __init__.py
│   └── node.py
├── model/
│   ├── __init__.py
│   ├── data.py
│   ├── instruments.py
│   ├── orders.py
│   └── position.py
├── persistence/
│   ├── __init__.py
│   └── catalog.py
├── portfolio/
│   ├── __init__.py
│   └── portfolio.py
├── risk/
│   ├── __init__.py
│   └── engine.py
├── system/
│   ├── __init__.py
│   ├── cache.py
│   └── msgbus.py
├── trading/
│   ├── __init__.py
│   └── strategy.py
└── examples/
    ├── strategies/
    ├── backtest/
    └── live/
```

### 8.2 编写策略

**策略模板**:
```python
from decimal import Decimal
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.indicators import EMA

class MyStrategyConfig(StrategyConfig):
    """策略配置"""
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    fast_ema_period: int = 10
    slow_ema_period: int = 20

class MyStrategy(Strategy):
    """自定义策略"""
    
    def __init__(self, config: MyStrategyConfig) -> None:
        super().__init__(config)
        self.instrument: Instrument | None = None
        self.fast_ema: EMA | None = None
        self.slow_ema: EMA | None = None
        self.position: Position | None = None
        self.bar_count: int = 0
    
    def on_start(self) -> None:
        """策略启动"""
        self.instrument = self.cache.instrument(self.config.instrument_id)
        
        if self.instrument is None:
            self.log.error("Instrument not found")
            return
        
        # 初始化指标
        self.fast_ema = EMA(self.config.fast_ema_period)
        self.slow_ema = EMA(self.config.slow_ema_period)
        
        # 订阅数据
        self.subscribe_bars(self.config.bar_type)
        
        self.log.info(f"Strategy started: {self.instrument.id}")
    
    def on_stop(self) -> None:
        """策略停止"""
        self.cancel_all_orders()
        self.log.info("Strategy stopped")
    
    def on_bar(self, bar: Bar) -> None:
        """K 线处理"""
        self.bar_count += 1
        
        # 更新指标
        if self.fast_ema and self.slow_ema:
            self.fast_ema.handle_bar(bar)
            self.slow_ema.handle_bar(bar)
        
        # 等待指标预热
        if self.bar_count < self.config.slow_ema_period:
            return
        
        # 交易逻辑
        if self.fast_ema and self.slow_ema:
            fast_value = self.fast_ema.value
            slow_value = self.slow_ema.value
            
            if fast_value and slow_value:
                if fast_value > slow_value and not self.position:
                    self._enter_long()
                elif fast_value < slow_value and self.position:
                    self._exit_position()
    
    def _enter_long(self) -> None:
        """做多入场"""
        if self.instrument is None:
            return
        
        order = self.order_factory.market(
            instrument_id=self.instrument.id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
        )
        self.submit_order(order)
    
    def _exit_position(self) -> None:
        """平仓出场"""
        self.cancel_all_orders()
        # 实现平仓逻辑
```

### 8.3 编写自定义指标

```python
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
        """处理 K 线"""
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
        """计算 RSI"""
        avg_gain = sum(self.gains[-self.period:]) / self.period
        avg_loss = sum(self.losses[-self.period:]) / self.period
        
        if avg_loss == 0:
            self.value = 100.0
        else:
            rs = avg_gain / avg_loss
            self.value = 100 - (100 / (1 + rs))
        
        self._updated = True
    
    def reset(self) -> None:
        """重置指标"""
        super().reset()
        self.gains.clear()
        self.losses.clear()
        self.value = None
```

### 8.4 编写自定义数据类

```python
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

---

## 9. PyO3 绑定 (PyO3 Bindings)

### 9.1 PyO3 项目结构

```
crates/pyo3/
├── Cargo.toml
└── src/
    ├── lib.rs
    ├── datetime.rs
    ├── identifiers.rs
    ├── model.rs
    └── trading.rs
```

### 9.2 编写 PyO3 绑定

**Cargo.toml**:
```toml
[package]
name = "nautilus_pyo3"
version = "1.200.0"
edition = "2021"

[lib]
name = "nautilus_pyo3"
crate-type = ["cdylib"]

[dependencies]
pyo3 = { version = "0.20", features = ["extension-module"] }
nautilus_core = { path = "../core" }
nautilus_model = { path = "../model" }
```

**lib.rs**:
```rust
use pyo3::prelude::*;
use nautilus_core::datetime::unix_nanos_to_iso8601;
use nautilus_model::identifiers::InstrumentId;

/// Nautilus PyO3 模块
#[pymodule]
fn nautilus_pyo3(_py: Python, m: &PyModule) -> PyResult<()> {
    // 添加函数
    m.add_function(wrap_pyfunction!(unix_nanos_to_iso8601, m)?)?;
    
    // 添加类
    m.add_class::<PyInstrumentId>()?;
    
    // 添加子模块
    let datetime_module = PyModule::new(_py, "datetime")?;
    datetime_module.add_function(wrap_pyfunction!(unix_nanos_to_iso8601, datetime_module)?)?;
    m.add_submodule(datetime_module)?;
    
    Ok(())
}

/// Python 包装的 InstrumentId
#[pyclass(name = "InstrumentId")]
pub struct PyInstrumentId {
    inner: InstrumentId,
}

#[pymethods]
impl PyInstrumentId {
    #[new]
    #[pyo3(signature = (value))]
    fn new(value: &str) -> PyResult<Self> {
        let inner = InstrumentId::from_str(value)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))?;
        Ok(Self { inner })
    }
    
    #[getter]
    fn value(&self) -> String {
        self.inner.to_string()
    }
    
    fn __str__(&self) -> String {
        self.inner.to_string()
    }
    
    fn __repr__(&self) -> String {
        format!("InstrumentId('{}')", self.inner)
    }
}
```

### 9.3 使用 PyO3 绑定

```python
from nautilus_trader.core.nautilus_pyo3 import InstrumentId, unix_nanos_to_iso8601

# 使用 Rust 实现的类
instrument_id = InstrumentId("BTCUSDT.BINANCE")
print(instrument_id.value)  # 调用 Rust getter

# 使用 Rust 实现的函数
iso_str = unix_nanos_to_iso8601(1630000000000000000)
print(iso_str)  # 2021-08-26T12:26:40.000000000Z
```

---

## 10. 调试技巧 (Debugging Tips)

### 10.1 Python 调试

**使用 pdb**:
```python
import pdb

def my_function():
    pdb.set_trace()  # 设置断点
    # ... 代码

# 运行
python -m pdb my_script.py

# 常用命令
# n - 下一行
# s - 进入函数
# c - 继续执行
# q - 退出
# p var - 打印变量
# l - 显示代码
```

**使用 IPython**:
```python
from IPython import embed

def my_function():
    embed()  # 进入交互式 shell
    # ... 代码
```

**日志调试**:
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def my_function():
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
```

### 10.2 Rust 调试

**使用 println!**:
```rust
fn my_function(x: i32) {
    println!("x = {}", x);
    dbg!(x);  // 更详细的调试输出
}
```

**使用 Rust 调试器**:
```bash
# 构建调试版本
cargo build

# 使用 lldb
lldb target/debug/my_program
(lldb) breakpoint set --name my_function
(lldb) run
(lldb) print x

# 使用 gdb
gdb target/debug/my_program
(gdb) break my_function
(gdb) run
(gdb) print x
```

### 10.3 性能分析

**Python 性能分析**:
```bash
# 使用 cProfile
python -m cProfile -o profile.stats my_script.py

# 查看结果
python -m pstats profile.stats
# 或直接使用可视化工具
snakeviz profile.stats

# 使用 line_profiler
kernprof -l -v my_script.py
```

**Rust 性能分析**:
```bash
# 使用 cargo flamegraph
cargo install flamegraph
cargo flamegraph --bin my_program

# 使用 perf (Linux)
perf record -g ./target/release/my_program
perf report

# 使用 Instruments (macOS)
cargo build --release
open -a Instruments ./target/release/my_program
```

### 10.4 内存分析

**Python 内存**:
```python
import tracemalloc

tracemalloc.start()

# ... 代码 ...

current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.2f} MB")
print(f"Peak: {peak / 1024 / 1024:.2f} MB")

tracemalloc.stop()
```

**Rust 内存**:
```bash
# 使用 valgrind
valgrind --leak-check=full ./target/release/my_program

# 使用 AddressSanitizer
RUSTFLAGS="-Z sanitizer=address" cargo run
```

---

## 11. 性能优化 (Performance Optimization)

### 11.1 Python 优化

**优化技巧**:
```python
# 1. 使用局部变量
def process(items):
    append = items.append  # 缓存方法引用
    for i in range(1000):
        append(i)

# 2. 使用生成器而非列表
def get_data():
    for i in range(1000000):
        yield i  # 而非 return [i for i in ...]

# 3. 使用 NumPy 进行数值计算
import numpy as np
prices = np.array(price_list)
returns = np.diff(prices) / prices[:-1]

# 4. 使用 Cython 优化热点
# 在.pyx 文件中
def cython_function(double[:] data):
    cdef int i
    cdef double sum = 0
    for i in range(len(data)):
        sum += data[i]
    return sum

# 5. 使用 multiprocessing
from multiprocessing import Pool
with Pool() as p:
    results = p.map(process_function, data_list)
```

### 11.2 Rust 优化

**优化技巧**:
```rust
// 1. 使用迭代器
let sum: i64 = data.iter().sum();

// 2. 避免不必要的分配
fn process(data: &[u8]) -> Result<Vec<u8>> {
    let mut output = Vec::with_capacity(data.len());
    // ...
    Ok(output)
}

// 3. 使用并行处理
use rayon::prelude::*;
let results: Vec<_> = data.par_iter().map(process).collect();

// 4. 使用小字符串优化
use smallvec::SmallVec;
let items: SmallVec<[Item; 4]> = SmallVec::new();

// 5. 使用对象池
use object_pool::Pool;
static POOL: Pool<Vec<u8>> = Pool::new(100, || Vec::with_capacity(1024));
```

### 11.3 基准测试

**Rust 基准测试**:
```rust
// crates/core/benches/benchmark.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use nautilus_core::datetime::unix_nanos_to_iso8601;

fn bench_datetime_conversion(c: &mut Criterion) {
    c.bench_function("datetime_conversion", |b| {
        b.iter(|| {
            unix_nanos_to_iso8601(black_box(1630000000000000000))
        })
    });
}

criterion_group!(benches, bench_datetime_conversion);
criterion_main!(benches);
```

**运行基准测试**:
```bash
cargo bench
```

---

## 12. 发布流程 (Release Process)

### 12.1 版本管理

**版本号格式**: `MAJOR.MINOR.PATCH`
- **MAJOR**: 破坏性变更
- **MINOR**: 向后兼容的新功能
- **PATCH**: 向后兼容的 Bug 修复

### 12.2 发布步骤

```bash
# 1. 更新版本号
# 编辑 pyproject.toml 和 Cargo.toml

# 2. 更新 CHANGELOG
# 添加新版本的更改记录

# 3. 运行所有测试
just test
just test-integration

# 4. 构建发布包
just build-release

# 5. 发布到 PyPI
just publish-pypi

# 6. 创建 Git 标签
git tag -a v1.200.0 -m "Release v1.200.0"
git push origin v1.200.0

# 7. 创建 GitHub Release
# 在 GitHub 上创建 Release 并上传构建产物
```

### 12.3 CI/CD 流水线

```yaml
# .github/workflows/release.yml
name: Release

on:
  release:
    types: [published]

jobs:
  publish-pypi:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Build and publish
        run: |
          pip install build twine
          python -m build
          twine upload dist/*
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
```

---

## 13. 常见问题 (FAQ)

### 13.1 构建问题

**Q: Rust 编译失败？**
```bash
A: 尝试以下命令：
   rustup update
   cargo clean
   cargo build --release
```

**Q: Cython 编译失败？**
```bash
A: 检查 Python 头文件：
   pip install --upgrade cython setuptools
   python build.py --verbose
```

**Q: macOS 架构错误？**
```bash
A: 确认使用 ARM64:
   arch -arm64 python3 --version
   rustup target add aarch64-apple-darwin
```

### 13.2 测试问题

**Q: 测试失败？**
```bash
A: 查看详细输出：
   pytest tests/ -v --tb=long
   cargo test --all --verbose
```

**Q: 覆盖率不达标？**
```bash
A: 添加缺失的测试：
   coverage html
   # 查看 htmlcov/index.html 找出未覆盖的代码
```

### 13.3 性能问题

**Q: 回测速度慢？**
```bash
A: 优化建议：
   - 使用 Bar 而非 Tick 数据
   - 减少策略数量
   - 禁用不必要的分析
   - 使用 Rust 实现的指标
```

**Q: 内存使用过高？**
```bash
A: 检查内存泄漏：
   - Python: tracemalloc
   - Rust: valgrind
   - 减少缓存容量配置
```

---

## 附录 A: 快速参考

### A.1 常用命令

```bash
# 开发
just build-dev      # 开发构建
just test           # 运行测试
just lint           # 代码检查
just format         # 格式化代码

# 发布
just build-release  # 发布构建
just publish-pypi   # 发布到 PyPI

# 清理
just clean          # 清理构建产物
```

### A.2 资源链接

| 资源 | 链接 |
|------|------|
| 官方文档 | https://nautilustrader.io/docs/ |
| Developer Guide | https://nautilustrader.io/docs/nightly/developer_guide/ |
| GitHub | https://github.com/nautechsystems/nautilus_trader |
| Rust 文档 | https://doc.rust-lang.org/ |
| PyO3 文档 | https://pyo3.rs/ |
| 社区讨论 | https://github.com/nautechsystems/nautilus_trader/discussions |

---

> **文档版本**: develop 分支 (2026 年 3 月)  
> **最后更新**: 2026-04-13  
> **维护者**: Nautilus Trader 社区

---