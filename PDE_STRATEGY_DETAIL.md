# Polymarket PDE 策略详细技术文档

> **版本**: v2.0 (2026-04-06)
> **策略文件**: `strategies/polymarket_pde_strategy.py`
> **配置文件**: `config/polymarket_pde_config.py`
> **Slug 构建**: `utils/slug_builder.py`

---

## 目录

1. [策略概览](#1-策略概览)
2. [配置参数](#2-配置参数)
3. [状态变量](#3-状态变量)
4. [生命周期](#4-生命周期)
5. [数据流与 Tick 处理](#5-数据流与-tick-处理)
6. [Phase A: EV 驱动交易](#6-phase-a-ev-驱动交易)
7. [Phase B: 尾部延续策略](#7-phase-b-尾部延续策略)
8. [仓位管理 (TP/SL)](#8-仓位管理-tpsl)
9. [市场轮转 (Rollover)](#9-市场轮转-rollover)
10. [Instrument 缓存刷新机制](#10-instrument-缓存刷新机制)
11. [WebSocket 断线恢复](#11-websocket-断线恢复)
12. [滑点与盘口深度检查](#12-滑点与盘口深度检查)
13. [波动率估算 (σ)](#13-波动率估算-σ)
14. [Prometheus 监控指标](#14-prometheus-监控指标)
15. [节点配置与部署](#15-节点配置与部署)
16. [已知限制与注意事项](#16-已知限制与注意事项)

---

## 1. 策略概览

**Polymarket PDE (Dual-Phase Engine)** 是一个针对 Polymarket BTC-UpDown-5m 二元期权市场的自动化交易策略。

### 核心思路

每 5 分钟一轮，Polymarket 会创建一个新的 BTC 涨跌市场：
- **Up token**: BTC 在本轮结束时上涨则结算为 $1，否则 $0
- **Down token**: BTC 在本轮结束时下跌则结算为 $1，否则 $0

策略利用 **Binance BTC 现货价格** 作为先行指标（速度优势），在 Polymarket 报价反应之前下注。

### 双阶段引擎

| 阶段 | 时间窗口 | 策略逻辑 |
|------|----------|----------|
| **Phase A** | 0 - 240s | 基于布朗运动理论的 EV 套利。检测 BTC 价格跳跃后，计算理论概率 vs 市场报价，EV > 阈值时买入 |
| **Phase B** | 240 - 300s | 尾部延续策略。BTC 已大幅偏移时，查询翻转概率表，在翻转概率低的方向下注延续 |

### 数据源

- **Binance BTCUSDT**: 实时 trade tick → BTC 现价、跳跃检测、波动率估算
- **Polymarket**: WebSocket quote tick + L2 order book → Up/Down token 报价、盘口深度

---

## 2. 配置参数

### 策略配置 (`PolymarketPDEStrategyConfig`)

```python
class PolymarketPDEStrategyConfig(StrategyConfig):
    market_base_slug: str           # "btc-updown-5m"
    market_interval_minutes: int    # 5 (每轮时长，分钟)
    trade_amount_usd: float         # 100.0 (每笔交易 USD 金额)
    auto_rollover: bool             # True (自动轮转到下一个市场)

    # Phase A
    ev_threshold_A: float           # 0.05 (EV 阈值，高于此值才买入)
    max_A_trades: int               # 2 (每轮最多 Phase A 交易数)
    take_profit_pct: float          # 0.30 (+30% 止盈)
    stop_loss_pct: float            # 0.20 (-20% 止损)

    # Phase B
    delta_tail_min: float           # 150.0 (最小 BTC 价格偏移，USD)
    tail_return: float              # 0.10 (遗留参数，动态计算优先)
    ev_threshold_tail: float        # 0.0 (Phase B EV 阈值)

    # 延迟监控
    btc_jump_threshold_bps: float   # 5.0 (BTC 必须变动 ≥5 bps 才触发速度优势)
    jump_staleness_sec: float       # 10.0 (跳跃必须在最近 10s 内)

    # 滑点
    max_slippage_pct: float         # 0.10 (10% 最大允许滑点)

    # 波动率
    volatility_window: int          # 60 (价格历史窗口，秒)

    # 翻转概率表
    flip_stats_path: str            # "config/flip_stats.json"
```

### 生产默认值 (polymarket_pde_config.py)

| 参数 | 值 | 说明 |
|------|-----|------|
| `trade_amount_usd` | 100 | 每笔 $100 |
| `ev_threshold_A` | 0.05 | Phase A 需 EV > 5% |
| `max_A_trades` | 2 | 每轮最多 2 笔 Phase A |
| `take_profit_pct` | 0.30 | +30% 止盈 |
| `stop_loss_pct` | 0.20 | -20% 止损 |
| `delta_tail_min` | 150.0 | Phase B 需 BTC Δ > $150 |
| `btc_jump_threshold_bps` | 5.0 | 5 bps 跳跃门槛 |
| `jump_staleness_sec` | 10.0 | 跳跃有效期 10s |
| `max_slippage_pct` | 0.10 | 10% 滑点上限 |

---

## 3. 状态变量

### 市场状态

| 变量 | 类型 | 说明 |
|------|------|------|
| `current_market_slug` | `str \| None` | 当前已提交的市场 slug（只在 instruments 找到后设置） |
| `instrument` | `Instrument \| None` | Up token instrument 对象 |
| `down_instrument` | `Instrument \| None` | Down token instrument 对象 |

### 轮次状态（每轮重置）

| 变量 | 类型 | 说明 |
|------|------|------|
| `start_price` | `dict[str, float]` | `{'up': None, 'down': None}` — 本轮 Up/Down 起始价 |
| `start_ts` | `int \| None` | 本轮开始的 Unix 时间戳（秒） |
| `A_trades` | `int` | 本轮 Phase A 已交易次数 |
| `tail_trade_done` | `bool` | 本轮 Phase B 是否已交易 |
| `positions` | `dict` | 每个 token 的仓位状态 `{'open': bool, 'entry_price': float}` |
| `price_history` | `dict[str, deque]` | Up/Down 价格历史（用于波动率估算） |

### BTC 价格状态

| 变量 | 类型 | 说明 |
|------|------|------|
| `btc_price` | `float \| None` | 最新 BTC 现价 |
| `btc_start_price` | `float \| None` | 本轮开始时的 BTC 价格 |
| `btc_anchor_price` | `float \| None` | 跳跃检测的锚点价格（每次跳跃后重置） |
| `btc_jump_ts` | `float` | 最近一次 BTC 跳跃的墙钟时间 |
| `btc_jump_direction` | `int` | 跳跃方向：+1 涨、-1 跌、0 无 |
| `btc_price_history` | `deque` | BTC tick 价格历史（最多 3000 个，用于 σ 估算） |

### 延迟监控

| 变量 | 类型 | 说明 |
|------|------|------|
| `btc_last_tick_wall_ts` | `float` | Binance 最后一个 tick 的墙钟时间 |
| `poly_last_tick_wall_ts` | `float` | Polymarket 最后一个 tick 的墙钟时间 |

### Rollover 状态

| 变量 | 类型 | 说明 |
|------|------|------|
| `_rollover_in_progress` | `bool` | True = 正在等待 instruments 加载（重试模式） |
| `_rollover_retry_count` | `int` | 重试计数（上限 30 次） |
| `_resubscribe_attempts` | `int` | WebSocket 重连尝试次数 |
| `_next_provider_refresh_ts` | `float` | 下次主动刷新 instruments 的墙钟时间 |
| `_provider_refresh_pending` | `bool` | 防止重叠刷新请求 |

---

## 4. 生命周期

### `on_start()`

1. 打印所有配置参数
2. 启动 Prometheus HTTP server（端口 8001）
3. 调用 `_subscribe_current_market()` 订阅当前 5 分钟市场
4. 订阅 Binance BTCUSDT trade tick
5. 设置 rollover 定时器（每 1 分钟检查一次）
6. 调度首次主动 Provider 刷新（1 小时后）

### `on_stop()`

1. 取消 rollover 定时器
2. 取消所有未完成订单
3. 取消订阅所有 quote tick 和 order book
4. 取消订阅 Binance BTC

### `on_reset()`

完全重置所有状态变量到初始值（包括 `btc_anchor_price = None`，因为完全重置后首个 BTC tick 会重新初始化）。

---

## 5. 数据流与 Tick 处理

### Binance BTC Trade Tick → `on_trade_tick()`

```
BTC tick 到达
  ├─ 更新 self.btc_price + Prometheus gauge
  ├─ 记录 btc_last_tick_wall_ts（延迟监控用）
  ├─ 如果 btc_anchor_price is None → 立即初始化（不依赖 start_ts）
  ├─ 如果 btc_start_price is None 且 start_ts 已设 → 记录本轮 BTC 起始价
  ├─ 跳跃检测:
  │   move_bps = (btc_price - btc_anchor_price) / btc_anchor_price × 10000
  │   如果 |move_bps| ≥ btc_jump_threshold_bps (5 bps):
  │     ├─ 记录 btc_jump_ts = 当前墙钟时间
  │     ├─ 记录 btc_jump_direction = +1 或 -1
  │     └─ 重置 btc_anchor_price = 当前价格（阶梯式锚点）
  └─ 追加到 btc_price_history（σ 估算用）
```

**关键设计**: `btc_anchor_price` 在首个 BTC tick 就初始化，不等待 Polymarket 数据。这确保跳跃检测从一开始就工作。

### Polymarket Quote Tick → `on_quote_tick()`

```
Polymarket quote tick 到达
  ├─ 更新 last_quote_tick_ts（staleness watchdog 用）
  ├─ 重置 _resubscribe_attempts = 0
  ├─ 计算延迟差: gap_ms = (btc_wall_ts - poly_wall_ts) × 1000
  └─ 路由到 _process_tick(tick, is_up=True/False)
```

### `_process_tick()` — 主处理逻辑

```
1. price = (bid + ask) / 2
2. 初始化 start_ts（首个 tick 到达时）
   └─ 同时快照 btc_start_price 和重置 btc_anchor_price
3. 初始化 start_price[token_key]（首个 tick 后 return）
4. 追加价格历史
5. 计算 t_elapsed 和 remaining
6. 检查 TP/SL
7. 如果 remaining ≤ 0 → 平仓，return
8. 计算 BTC delta:
   - delta_log = log(btc_price / btc_start_price)  → Phase A 用
   - delta_usd = btc_price - btc_start_price        → Phase B 用
9. 路由:
   - t_elapsed < 240s → _execute_phase_A()
   - t_elapsed ≥ 240s → _execute_phase_B()
```

---

## 6. Phase A: EV 驱动交易

### 入场条件（全部满足才交易）

1. **仓位检查**: 当前 token 没有未平仓仓位
2. **交易次数**: `A_trades < max_A_trades` (默认 2)
3. **速度优势门**: `btc_jump_ts` 在最近 `jump_staleness_sec` (10s) 内
4. **波动率有效**: `_estimate_sigma()` 返回非 None
5. **EV 正向**: `ev_buy > ev_threshold_A` (0.05)
6. **滑点检查**: 预估滑点 < `max_slippage_pct` (10%)

### 理论概率计算

```python
# 1. 波动率缩放到剩余时间
sigma_rem = sigma × √remaining

# 2. Z-score（delta_log 是无量纲对数收益率）
z = delta_log / sigma_rem

# 3. 理论上涨概率（标准正态 CDF）
p_up = Φ(z)
```

### EV 计算

```python
# Up token: 如果 BTC 上涨结算为 $1
ev_buy_up = p_up - market_ask_price

# Down token: 如果 BTC 下跌结算为 $1
ev_buy_down = (1 - p_up) - market_ask_price
```

### 下单

- 方向: `OrderSide.BUY`
- 数量: `trade_amount_usd / ask_price` (例: $100 / $0.50 = 200 tokens)
- 类型: 市价单 (`order_factory.market()`)

---

## 7. Phase B: 尾部延续策略

### 入场条件

1. **未交易过**: `tail_trade_done == False`
2. **BTC 偏移足够大**: `|delta_usd| ≥ delta_tail_min` (默认 $150)
3. **翻转概率可查**: `_get_flip_prob(remaining, |delta_usd|)` 返回非 None
4. **EV 正向**: `ev_tail > ev_threshold_tail` (默认 0.0)

### 翻转概率查询

从 `config/flip_stats.json` 加载的查找表，key 格式为 `tau_low_tau_high_delta_low_delta_high`。

```python
def _get_flip_prob(tau, abs_delta):
    for (tau_low, tau_high, delta_low, delta_high), p in flip_stats.items():
        if tau_low <= tau <= tau_high and delta_low <= abs_delta <= delta_high:
            return p
    return None
```

### EV 计算

```python
# 获取目标 token 的实际盘口 ask 价格
actual_ask = target_quote.ask_price

# EV = 延续概率 × $1 结算 - 成本
ev_tail = (1 - p_flip) - actual_ask
```

### 方向选择

- BTC 上涨 (`delta_usd > 0`) → BUY Up token（押注延续上涨）
- BTC 下跌 (`delta_usd < 0`) → BUY Down token（押注延续下跌）

---

## 8. 仓位管理 (TP/SL)

### 每个 tick 检查

```python
def _check_tp_sl(token_key, current_price):
    entry = positions[token_key]['entry_price']
    pnl_pct = (current_price - entry) / entry

    if pnl_pct >= +0.30:   # Take Profit
        close_position → log TP
    elif pnl_pct <= -0.20:  # Stop Loss
        close_position → log SL
```

### 平仓方式

通过 `self.close_position(position)` 调用 Nautilus 内置平仓（市价反向单）。

### 轮次结束

`remaining ≤ 0` 或 rollover 时，调用 `_close_all_open_positions()` 强制平所有仓。

### 仓位状态跟踪

本地 `self.positions[token_key]` 字典追踪 `open` 和 `entry_price`，与 Nautilus cache 中的实际 Position 对象同步。

---

## 9. 市场轮转 (Rollover)

### 定时器

`pde_market_rollover_check` — 每 1 分钟触发一次 `_on_rollover_timer()`。

### 轮转流程

```
_on_rollover_timer() 触发
  │
  ├─ 检查主动刷新 (_check_proactive_refresh)
  │
  ├─ 如果 _rollover_in_progress → 直接重试 _subscribe_current_market()
  │
  ├─ staleness watchdog 检查（>30s 无 quote tick → force resubscribe）
  │
  └─ 计算 new_slug = _get_current_slug()
     └─ 如果 new_slug ≠ current_market_slug:
        ├─ rounds_counter++
        ├─ 取消所有未完成订单
        ├─ 平仓所有持仓
        ├─ 重置轮次状态:
        │   ├─ start_price = {up: None, down: None}
        │   ├─ start_ts = None
        │   ├─ positions → 全部关闭
        │   ├─ A_trades = 0, tail_trade_done = False
        │   ├─ price_history 清空
        │   ├─ btc_start_price = None
        │   ├─ btc_anchor_price = self.btc_price (保持跳跃检测活跃)
        │   └─ btc_price_history 清空
        └─ 调用 _subscribe_current_market()
```

### Slug 计算

```python
def _get_current_slug():
    now = datetime.now(timezone.utc)
    aligned_minute = (now.minute // 5) * 5
    market_time = now.replace(minute=aligned_minute, second=0, microsecond=0)
    return f"btc-updown-5m-{int(market_time.timestamp())}"
```

### `_subscribe_current_market()` — 核心订阅逻辑

```
1. slug = _get_current_slug()
2. 如果 slug == current_market_slug → return (无需切换)

3. 首次尝试（非重试）:
   ├─ 取消订阅旧 instruments（容错）
   └─ 清空 instrument/down_instrument 引用

4. 在缓存中搜索 instruments:
   ├─ 遍历 cache.instruments(venue=POLYMARKET)
   ├─ 匹配 info.market_slug == slug
   ├─ 按 outcome 字段分配 Up/Down
   └─ fallback: 按 token_id 排序分配

5. 如果未找到 instruments:
   ├─ _rollover_in_progress = True
   ├─ retry_count++
   ├─ 调用 request_instruments(venue=POLYMARKET, callback=...)
   │   → 触发 Provider 重新调用 build_btc_updown_slugs()
   │   → callback 中立即重试 _subscribe_current_market()
   └─ retry_count > 30 → 放弃，等下一个 5 分钟窗口

6. 找到 instruments:
   ├─ 提交 current_market_slug = slug ← 关键：只在成功后提交
   ├─ 订阅 Up token: quote_ticks + order_book_deltas (L2_MBP)
   └─ 订阅 Down token: quote_ticks + order_book_deltas (L2_MBP)
```

**关键设计**: `current_market_slug` 只在 instruments 成功找到后才设置。如果未找到，slug 不提交，下次 timer tick 会计算相同的 `new_slug ≠ current_market_slug`，从而触发重试。

---

## 10. Instrument 缓存刷新机制

### 架构：双层保障

```
启动 ──→ slug_builder 加载 24 个窗口（2h 缓存）
           │
           ▼
       每 1 分钟 rollover timer
           │
           ├─ 正常: 缓存命中 → 订阅 → 交易
           │
           ├─ 缓存未命中 → 重试模式
           │   └─ request_instruments() → Provider 重新调用 slug_builder
           │     → callback 中立即重试订阅
           │
           └─ 主动刷新（半程 = 1h）
               └─ request_instruments() → 加载新的 24 窗口
                 → callback 中重新调度下一次刷新
```

### `build_btc_updown_slugs()` (slug_builder)

```python
def build_btc_updown_slugs() -> list[str]:
    now = datetime.now(timezone.utc)
    aligned_minute = (now.minute // 5) * 5
    current = now.replace(minute=aligned_minute, second=0, microsecond=0)

    slugs = []
    for i in range(24):  # 24 个窗口 = 2 小时
        window_time = current + timedelta(minutes=5 * i)
        slug = f"btc-updown-5m-{int(window_time.timestamp())}"
        slugs.append(slug)
    return slugs
```

每次 Provider 调用此函数时，基于 `datetime.now()` 生成新窗口列表 → 自然滚动向前。

### 主动刷新定时器

```python
def _schedule_next_provider_refresh():
    NUM_WINDOWS = 24
    half_coverage_sec = (24 // 2) * 5 * 60  # = 3600s = 1h
    _next_provider_refresh_ts = clock.timestamp() + half_coverage_sec

def _check_proactive_refresh():
    # 每次 rollover timer tick 检查
    if now >= _next_provider_refresh_ts:
        request_instruments(venue=POLYMARKET, callback=_on_proactive_refresh_done)

def _on_proactive_refresh_done():
    # 刷新完成 → 重新调度下一次
    _schedule_next_provider_refresh()
```

### 时间线示例

```
T=0h    启动: 加载 Window 1-24 (覆盖到 T+2h)
T=1h    半程刷新: 重新加载 Window 13-36 (覆盖到 T+3h)
T=2h    半程刷新: 重新加载 Window 25-48 (覆盖到 T+4h)
...     无限循环，缓存永远有 ≥1h 储备
```

---

## 11. WebSocket 断线恢复

### Staleness Watchdog

在 `_on_rollover_timer()` 中：
- 如果 `last_quote_tick_ts` 距今 > 30 秒且 `_resubscribe_attempts < 3`
- 调用 `_force_resubscribe()`

### `_force_resubscribe()`

```python
for inst in (instrument, down_instrument):
    unsubscribe_quote_ticks(inst.id)       # 容错
    unsubscribe_order_book_deltas(inst.id)  # 容错

# 重新订阅 → 触发新 WebSocket 连接
subscribe_quote_ticks(instrument.id)
subscribe_order_book_deltas(instrument.id, book_type=L2_MBP)
```

### Rollover 期间的取消订阅

使用 `try/except` 包裹，WebSocket 已断开时 `RuntimeError("Cannot send text")` 被捕获为非致命错误。

---

## 12. 滑点与盘口深度检查

### `_check_book_depth(instrument, qty, side, token_key)`

```python
book = cache.order_book(instrument.id)
best_ask = book.best_ask_price()
avg_px = book.get_avg_px_for_quantity(qty, side)

slippage_pct = max(0, (avg_px - best_ask) / best_ask)

# 薄盘口保护: avg_px > 2× best_ask → 跳过阈值检查
if avg_px > 2 * best_ask:
    return True, 0.0  # 照常交易

# 正常检查
if slippage_pct > max_slippage_pct (10%):
    skip trade
```

**设计原因**: Polymarket 二元期权的 L2 order book 通常很薄。对于 $100 / $0.20 = 500 token 的订单，很可能需要穿透多个价位。当 avg_px > 2× best_ask 时，说明盘口深度不足以给出有意义的滑点估计，此时应照常交易（实际成交会用可用流动性填充）。

---

## 13. 波动率估算 (σ)

### `_estimate_sigma(token_key)`

**数据源**: 严格使用 BTC 价格历史（不使用 token 价格，因为 token 价格是概率而非资产价格）。

```python
# 前置条件
if elapsed < 30s: return None           # 时间太短
if len(btc_price_history) < 50: return None  # 数据点不够

# 计算
prices = np.array(btc_price_history)
log_returns = np.diff(np.log(prices))

# 缩放到 5 分钟
avg_tick_interval = elapsed / len(log_returns)
sigma = np.std(log_returns) × √(300 / avg_tick_interval)

# 健全性检查
if sigma < 1e-6 or sigma > 1.0: return None
```

---

## 14. Prometheus 监控指标

### 端点

`http://localhost:8001/metrics`

### 指标清单

| 指标名 | 类型 | 标签 | 说明 |
|--------|------|------|------|
| `pde_delta_p` | Gauge | token_type | 价格偏移 ΔP (USD) |
| `pde_remaining_time` | Gauge | — | 本轮剩余秒数 |
| `pde_p_up` | Gauge | token_type | 理论上涨概率 |
| `pde_ev` | Gauge | token_type, side | Phase A EV |
| `pde_sigma` | Gauge | — | 估算波动率 σ |
| `pde_p_flip` | Gauge | token_type | Phase B 翻转概率 |
| `pde_ev_tail` | Gauge | token_type | Phase B EV |
| `pde_strategy_state` | Gauge | — | 0=Idle, 1=Phase A, 2=Phase B |
| `pde_trades_total` | Counter | phase, token_type, side | 交易计数（详细） |
| `pde_phase_a_trades` | Gauge | — | 本轮 Phase A 交易数 |
| `pde_unrealized_pnl` | Gauge | token_type | 未实现 PnL |
| `pde_realized_pnl` | Gauge | token_type | 已实现 PnL |
| `pde_position_size` | Gauge | token_type | 持仓大小 |
| `pde_position_entry_price` | Gauge | token_type | 入场价 |
| `pde_position_pnl_pct` | Gauge | token_type | 持仓盈亏百分比 |
| `pde_tp_sl_total` | Counter | token_type, trigger | TP/SL 触发计数 |
| `pde_phase_a_trades_cumulative` | Counter | — | Phase A 累计交易数 |
| `pde_phase_b_trades_cumulative` | Counter | — | Phase B 累计交易数 |
| `pde_rounds_total` | Counter | — | 完成轮次数 |
| `pde_btc_momentum_bps` | Gauge | — | BTC 动量 (bps) |
| `pde_latency_gap_ms` | Gauge | — | Binance vs Polymarket 延迟差 (ms) |
| `pde_phase_a_skip_total` | Counter | reason | Phase A 跳过原因 (no_jump/slippage) |
| `pde_order_slippage_pct` | Gauge | token_type | 预估滑点 |
| `pde_btc_price` | Gauge | — | BTC 实时价格 |
| `pde_btc_delta_p` | Gauge | — | BTC 本轮价格偏移 (USD) |

---

## 15. 节点配置与部署

### 数据客户端

| 客户端 | 用途 |
|--------|------|
| **BINANCE** | `BinanceDataClientConfig` — BTCUSDT spot trade tick |
| **POLYMARKET** | `PolymarketDataClientConfig` — Up/Down quote tick + L2 order book |

### 执行客户端

| 模式 | 客户端 | 说明 |
|------|--------|------|
| `sandbox` | `SandboxExecutionClientConfig` | 模拟交易，起始余额 1M USDC + 1M USDC.e，L2 order book 深度填充 |
| `live` | `PolymarketExecClientConfig` | 实盘交易 |
| `both` | 两者皆有 | 同时模拟和实盘 |

### Instrument Provider

```python
PolymarketInstrumentProviderConfig(
    event_slug_builder="utils.slug_builder:build_btc_updown_slugs",
)
```

Provider 在初始化和每次 `request_instruments` 调用时，执行 `build_btc_updown_slugs()` 获取 slug 列表，然后通过 Gamma API + CLOB API 加载对应的 instruments。

### 基础设施

| 组件 | 地址 |
|------|------|
| Redis | `localhost:6379` |
| Prometheus | `http://localhost:8001` |
| Grafana | Docker 容器，dashboard: `monitoring/pde-dashboard.json` |

### 启动命令

```bash
# Sandbox 模式
python live/run_polymarket_pde.py --mode sandbox

# 实盘模式
python live/run_polymarket_pde.py --mode live
```

### 清除 Redis（Windows 上无 redis-cli）

```python
import redis
redis.Redis('localhost', 6379).flushall()
```

---

## 16. 已知限制与注意事项

### Phase B 触发条件

- 需要 BTC 在单个 5 分钟窗口内变动 > $150 (delta_tail_min)
- 在低波动率市场中可能很少触发
- `flip_stats.json` 查找表的覆盖范围有限

### 滑点检查

- Polymarket L2 order book 通常很薄
- 大额订单 ($100 on $0.20 token = 500 tokens) 可能穿透多个价位
- 当前保护: avg_px > 2× best_ask 时跳过滑点检查
- `max_slippage_pct` 设为 10%（低于此值仍可能阻止薄盘口交易）

### BTC 跳跃检测

- `btc_anchor_price` 是阶梯式锚点（每次跳跃后重置到当前价格）
- 这意味着连续小幅变动不会触发，只有单次 ≥5 bps 的跳跃才触发
- `jump_staleness_sec = 10s` 意味着跳跃后 10 秒内未交易则作废

### Instrument 缓存

- 初始加载 24 个窗口 (2h)
- 半程（1h）主动刷新
- 如果 Polymarket API 暂时不可用，重试机制最多尝试 30 次
- 超过 30 次后放弃当前 slug，等待下一个 5 分钟窗口自然推进

### 仓位追踪

- 本地 `self.positions` 字典与 Nautilus cache 中的 Position 对象独立维护
- `on_position_closed` 事件更新 Prometheus 指标
- 如果出现不一致，rollover 时的 `_close_all_open_positions()` 会强制同步

### Rollover 期间的状态保持

- `btc_anchor_price` 保持为当前 BTC 价格（不重置为 None）
- `btc_jump_ts` 和 `btc_jump_direction` 跨轮保持（最近的跳跃对新轮次仍有参考价值）
- `btc_price` 持续更新，不受 rollover 影响

---

## 附录：文件结构

```
polymarket_nt_project/
├── config/
│   ├── polymarket_pde_config.py   # 节点配置（数据客户端、执行客户端、策略参数）
│   ├── polymarket_config.py       # 通用配置（resolve_current_token_id）
│   └── flip_stats.json            # Phase B 翻转概率查找表
├── strategies/
│   ├── polymarket_pde_strategy.py  # PDE 策略主文件（本文档的核心）
│   └── polymarket_strategy.py      # 旧版策略（参考）
├── utils/
│   ├── slug_builder.py            # build_btc_updown_slugs() — slug 生成器
│   ├── get_current_market.py      # 市场查找工具
│   └── find_current_market.py     # Gamma/CLOB API 查询工具
├── live/
│   └── run_polymarket_pde.py      # 启动脚本
├── monitoring/
│   └── pde-dashboard.json         # Grafana dashboard 定义
├── polymarket/
│   └── market_rollover.py         # 早期轮转管理器（参考）
└── requirements.txt
```
