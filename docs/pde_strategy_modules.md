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

### PolymarketPDEStrategyConfig 关键参数

```python
class PolymarketPDEStrategyConfig(StrategyConfig):
    market_base_slug: str           # 市场基础标识 (如 "btc-updown-5m")
    market_interval_minutes: int = 5  # 市场周期(分钟)
    
    # 风险控制
    max_position_usd: float = 500.0   # 最大持仓金额
    per_trade_usd: float = 100.0      # 单笔交易金额
    min_edge_threshold: float = 0.02  # 最小边缘优势
    max_slippage: float = 0.005       # 最大滑点
    
    # 阶段参数
    phase_a_duration_sec: float = 240.0  # Phase A 持续时间
    tail_start_threshold: float = 0.1    # 尾部交易触发阈值
    
    # BTC 监控
    btc_jump_threshold_bps: float = 50.0  # BTC跳跃检测阈值(bps)
    btc_price_source: str = "trade"         # "trade" 或 "mid"
```

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
