# PDE 策略模块说明 (PDE Strategy Modules)

## 1. 模块结构

```
strategies/pde/
├── __init__.py          # 模块入口
├── base.py              # 配置和基础类
├── main.py              # 主策略类 (整合所有 mixin)
├── market_mixin.py      # 市场管理
├── execution_mixin.py   # 订单执行
├── signal_mixin.py      # 信号计算
├── data_mixin.py        # 数据流处理
└── metrics_mixin.py     # 指标监控
```

## 2. 各模块功能

| 模块 | 职责 | 关键方法 |
|------|------|----------|
| `base.py` | 策略配置、核心状态管理 | `PolymarketPDEStrategyConfig`, `PDEStrategyBase` |
| `market_mixin.py` | 市场切换、订阅管理、rollover | `_schedule_next_rollover()`, `_do_rollover()` |
| `execution_mixin.py` | 下单、持仓跟踪、PnL计算 | `submit_market_order()`, `_check_tp_sl()` |
| `signal_mixin.py` | EV计算、翻转概率、信号生成 | `_calculate_sigma()`, `_lookup_flip_prob()` |
| `data_mixin.py` | Tick处理、WebSocket推送 | `on_quote_tick()`, `_process_polymarket_tick()` |
| `metrics_mixin.py` | Prometheus指标、健康监控 | `_init_metrics()`, `update_dashboard()` |

## 3. 数据流流程

```
Polymarket WebSocket
       ↓
DataClient (nautilus_trader)
       ↓
PDEDataMixin.on_quote_tick()
       ↓
PDEDataMixin._process_polymarket_tick()
       ↓
├── WebSocket 推送 (dashboard)
├── 价格历史更新
└── _process_tick_for_strategy()
        ↓
   PDESignalMixin._calculate_ev()
   PDESignalMixin._check_phase_a_signal()
   PDESignalMixin._check_phase_b_signal()
        ↓
   PDEExecutionMixin.submit_market_order()
```

## 4. 关键修复记录

| 日期 | 问题 | 修复 | 文件 |
|------|------|------|------|
| 2026-04-13 | ZeroDivisionError | 添加价格>0检查 | `signal_mixin.py:_calculate_sigma()` |
| 2026-04-13 | 除零风险 | spread计算前检查ask>0 | `data_mixin.py:_process_polymarket_tick()` |
| 2026-04-13 | 日志刷屏 | tick日志改为5秒采样 | `data_mixin.py:on_quote_tick()` |

## 5. 调试技巧

### 查看 tick 流
```powershell
python live/run_polymarket_pde.py --mode sandbox 2>&1 | Select-String "TICK"
```

### 启用 DEBUG 日志
```powershell
$env:NAUTILUS_LOG_LEVEL="DEBUG"
python live/run_polymarket_pde.py --mode sandbox
```

### 过滤零价格 tick
```python
# data_mixin.py 中已添加
if bid <= 0 and ask <= 0:
    self.log.debug(f"Skipping tick with zero prices")
    return
```

## 6. 配置文件

### 表A：模块化 PDE 策略参数（已定义并生效）

> 默认定义在 `strategies/pde/base.py`，运行时覆盖在 `config/polymarket_pde_config.py`。

| 参数 | 当前值 | 作用说明 |
|------|--------|----------|
| `market_base_slug` | `btc-updown-5m` | 市场基础 slug，用于拼接当前轮次市场标识。 |
| `market_interval_minutes` | `5` | 每轮市场时长（分钟），影响剩余时间与 rollover 节奏。 |
| `max_position_usd` | `500.0` | 总持仓美元上限，防止累计仓位过大。 |
| `per_trade_usd` | `100.0` | 单次开仓目标名义金额，按 `qty=per_trade_usd/price` 计算数量。 |
| `min_edge_threshold` | `0.02` | 基础边际阈值（当前主要用于调试日志参考，Phase A 入场阈值由 `ev_threshold_A` 决定）。 |
| `max_slippage` | `0.005` | 预留滑点控制参数，用于约束执行价格偏离。 |
| `spread_tolerance` | `0.05` | 预留点差容忍参数，用于未来点差风控。 |
| `phase_a_duration_sec` | `240.0` | Phase A 持续秒数，超过后进入 Phase B。 |
| `ev_threshold_A` | `0.05` | Phase A 的基础 EV 入场阈值。 |
| `ev_entry_hysteresis` | `0.01` | EV 入场迟滞缓冲，实际触发阈值为 `ev_threshold_A + ev_entry_hysteresis`。 |
| `ev_ema_alpha` | `0.25` | EV 的 EMA 平滑系数（越小越平滑、越慢）。 |
| `ev_deadband` | `0.005` | EV 零附近死区，抑制小幅高频抖动。 |
| `max_A_trades` | `6` | 每轮 Phase A 最大开仓次数限制。 |
| `tail_start_threshold` | `0.1` | Phase B 尾部条件阈值（如波动率/尾部条件判定门槛）。 |
| `entry_retry_cooldown_sec` | `1.0` | 开仓失败后重试冷却时间，避免每个 tick 重复尝试。 |
| `btc_jump_threshold_bps` | `5.0` | BTC 跳变检测阈值（bps），用于速度优势判定。 |
| `btc_price_source` | `trade` | BTC 价格来源：`trade`（成交价）或 `mid`（中间价）。 |
| `proactive_refresh_interval_min` | `10.0` | 主动刷新 provider/instrument 的周期（分钟）。 |
| `flip_stats_refresh_minutes` | `60` | 翻转概率统计刷新周期（分钟）。 |
| `flip_stats_lookback` | `200` | 刷新翻转统计时的回看窗口大小。 |
| `pnl_display_interval_sec` | `10.0` | PnL 展示/打印节奏控制（秒）。 |
| `debug_raw_data` | `True` | 原始数据调试日志开关。 |
| `debug_ws` | `False` | WebSocket 调试日志开关。 |

## 7. 运行策略

### Sandbox 模式
```powershell
python live/run_polymarket_pde.py --mode sandbox
```

### Live 模式
```powershell
python live/run_polymarket_pde.py --mode live
```

## 8. 实时 Dashboard

- **WebSocket**: `ws://localhost:8765`
- **HTTP Dashboard**: `http://localhost:8766/live-dashboard-v2.html`
- **指标**: Prometheus 格式暴露于默认端口
