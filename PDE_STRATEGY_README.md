# Polymarket PDE Strategy (Dual-Phase Engine)

## 📋 概述

**PDE Strategy** 是一个基于期望值（EV）驱动的双阶段交易策略，用于 Polymarket BTC Up/Down 5 分钟滚动市场。

### 策略架构

```
┌─────────────────────────────────────────────────────────┐
│  Phase A (0-240s): EV-Driven Arbitrage                  │
│  ├─ 布朗运动理论计算 Up 概率                              │
│  ├─ 与市场隐含概率比较                                    │
│  └─ EV > 阈值 → 下单（最多 N 次）                        │
├─────────────────────────────────────────────────────────┤
│  Phase B (240-300s): Tail Reversal Strategy             │
│  ├─ 查询历史翻转概率表                                    │
│  ├─ 偏移量足够大 + 翻转概率低                             │
│  └─ 下注当前偏移方向（仅一次）                            │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install scipy prometheus-client
```

### 2. 配置翻转概率表

编辑 `config/flip_stats.json`，根据历史数据调整概率值：

```json
{
  "data": {
    "10_20_50_100": 0.35,  // tau=10-20s, delta=50-100 → 35% 翻转概率
    ...
  }
}
```

### 3. 运行策略

```bash
python live/run_polymarket_pde.py --execution-mode sandbox
```

---

## ⚙️ 配置参数

### 策略参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `market_base_slug` | `"btc-updown-5m"` | 市场 slug 前缀 |
| `market_interval_minutes` | `5` | 市场滚动间隔 |
| `trade_size` | `100` | 每次交易金额（USDC） |
| `auto_rollover` | `True` | 自动市场滚动 |

### Phase A 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `ev_threshold_A` | `0.05` | EV 阈值（5%） |
| `max_A_trades` | `2` | 最大交易次数 |
| `volatility_window` | `60` | 波动率估计窗口（秒） |

### Phase B 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `delta_tail_min` | `150.0` | 最小偏移量触发条件 |
| `tail_return` | `0.10` | 预期回报率（10%） |
| `ev_threshold_tail` | `0.0` | 尾盘 EV 阈值 |

---

## 📊 监控指标

### Prometheus 指标（端口 8001）

**市场状态**
- `pde_delta_p` - 价格偏移量（ΔP）
- `pde_remaining_time` - 剩余时间（秒）
- `pde_strategy_state` - 当前阶段（0=Idle, 1=Phase A, 2=Phase B）

**Phase A 指标**
- `pde_p_up` - 理论 Up 概率（布朗运动）
- `pde_ev` - 期望值（按 token_type 和 side 区分）
- `pde_sigma` - 估计波动率

**Phase B 指标**
- `pde_p_flip` - 翻转概率（查表）
- `pde_ev_tail` - 尾盘期望值

**交易指标**
- `pde_trades_total` - 总交易次数（按 phase/token/side 区分）
- `pde_phase_a_trades` - Phase A 当前轮次交易数
- `pde_unrealized_pnl` - 未实现盈亏
- `pde_realized_pnl` - 已实现盈亏
- `pde_position_size` - 当前持仓

### Grafana Dashboard

导入 `monitoring/pde-dashboard.json` 查看实时监控：

```bash
http://localhost:3000/dashboard/import
```

**主要面板**：
1. **Strategy Phase** - 当前策略阶段
2. **Remaining Time** - 倒计时
3. **Delta P** - 价格偏移走势
4. **Theoretical Probability** - 理论概率曲线
5. **EV (Phase A)** - 期望值实时监控
6. **Flip Probability (Phase B)** - 翻转概率
7. **Trades Count** - 交易频率统计
8. **PnL** - 盈亏监控

---

## 🧠 策略逻辑详解

### Phase A: 布朗运动 EV 套利

**理论基础**：
```
σ_rem = σ × √(T_remaining)
z = ΔP / σ_rem
p_up = Φ(z)  // 标准正态分布累积概率
```

**交易条件**：
```python
EV_yes = p_up - market_price
EV_no = (1 - p_up) - (1 - market_price)

if EV_yes > threshold:
    BUY Up token
elif EV_no > threshold:
    SELL Up token (or BUY Down token)
```

### Phase B: 尾盘翻转概率

**查表逻辑**：
```python
p_flip = lookup_table[(tau, delta)]
EV_tail = (1 - p_flip) × return - p_flip

if EV_tail > 0 and |ΔP| > delta_min:
    BET on current offset direction
```

---

## 🔧 待完成功能

### 🔴 高优先级

1. **CEX 价格源集成**
   - 当前使用 Polymarket token 价格作为 proxy
   - 需要集成 Binance WebSocket 获取 BTC/USDT 实时价格
   - 文件位置：`strategies/polymarket_pde_strategy.py:_process_tick()`

2. **波动率估计优化**
   - 当前使用简单滚动窗口
   - 可改进为 EWMA 或 GARCH 模型

### 🟡 中优先级

3. **翻转概率表数据采集**
   - 当前使用占位符数据
   - 需要历史数据统计生成真实概率

4. **回测验证**
   - 使用历史数据验证策略有效性
   - 优化参数（EV 阈值、最大交易次数）

### 🟢 低优先级

5. **多市场支持**
   - 支持其他时间间隔（1min, 10min）
   - 支持其他标的（ETH, SOL）

---

## 📁 文件结构

```
polymarket_nt_project/
├── strategies/
│   ├── polymarket_strategy.py          # 原策略（固定阈值）
│   └── polymarket_pde_strategy.py      # PDE 策略（新）
├── config/
│   ├── polymarket_config.py
│   └── flip_stats.json                 # 翻转概率表（新）
├── monitoring/
│   ├── grafana-dashboard.json          # 原策略 Dashboard
│   ├── pde-dashboard.json              # PDE Dashboard（新）
│   ├── prometheus.yml
│   └── docker-compose.yml
└── PDE_STRATEGY_README.md              # 本文档（新）
```

---

## 🐛 故障排查

### 问题 1: Prometheus 端口冲突

**错误**: `OSError: [Errno 48] Address already in use`

**解决**: PDE 策略使用端口 8001，原策略使用 8000，确保不同时运行或修改端口。

### 问题 2: 翻转概率表未找到

**错误**: `Failed to load flip stats`

**解决**: 确保 `config/flip_stats.json` 存在且格式正确。

### 问题 3: 波动率估计为 None

**原因**: 价格历史数据不足（< 10 个点）

**解决**: 等待策略运行一段时间积累数据。

### 问题 4: No data in Grafana

**原因**: 策略未运行或 Prometheus 未抓取指标

**解决**: 
1. 确认策略正在运行
2. 访问 `http://localhost:8001/metrics` 确认指标存在
3. 检查 Prometheus targets: `http://localhost:9090/targets`

---

## 📈 性能优化建议

1. **减少日志输出**：生产环境降低日志级别
2. **批量订阅**：同时订阅 Up/Down token 减少延迟
3. **缓存优化**：缓存翻转概率查询结果
4. **异步处理**：波动率计算可异步执行

---

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📝 更新日志

### v1.0.0 (2026-04-04)
- ✅ 初始版本发布
- ✅ Phase A: 布朗运动 EV 策略
- ✅ Phase B: 尾盘翻转概率策略
- ✅ Prometheus 监控集成
- ✅ Grafana Dashboard
- ⚠️  CEX 价格源待集成

---

## 📧 联系方式

如有问题或建议，请提交 Issue 或联系开发团队。
