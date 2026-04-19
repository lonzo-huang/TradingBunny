# PDE 策略实时监控系统 — 完整指导文档

## 一、系统概述

本系统为 Polymarket PDE 交易策略提供 **毫秒级实时监控**，采用双后端推流架构，刷新频率 100–500ms，与现有 Prometheus/Grafana 5秒级监控并行运行，互不干扰。

### 架构

```
NautilusTrader Strategy
      ↓  (push, 线程安全)
 CompositeLivePusher
      ├─→ LiveStreamServer (WebSocket broadcast, port 8765)
      │      ↓
      │    浏览器实时仪表盘 (HTML, port 8766)
      │
      └─→ GrafanaLivePusher (HTTP POST → Grafana Live API)
             ↓
           Grafana Live Dashboard (port 3000)
```

- **Prometheus** 继续做 5 秒级别的长期监控和告警
- **WebSocket 实时链路** 做 tick 级别（100–200ms）的即时监控（HTML 仪表盘）
- **Grafana Live 链路** 做 200ms 级别的即时监控（原生 Grafana 面板）
- 三条链路完全独立，互不影响
- **推荐使用 Grafana Live**：原生面板渲染、内置告警、无需维护 HTML

---

## 二、文件清单

| 文件 | 作用 |
|------|------|
| `utils/composite_pusher.py` | 统一推送接口，扇出到所有后端 |
| `utils/live_stream_server.py` | WebSocket 推流服务器 + HTTP 仪表盘服务器 |
| `utils/grafana_live_pusher.py` | Grafana Live HTTP 推流器 |
| `strategies/polymarket_pde_strategy.py` | 策略主文件，已集成所有推流调用 |
| `monitoring/live-dashboard.html` | HTML 实时仪表盘（14 面板，暗色 HFT 风格） |
| `monitoring/pde-live-dashboard.json` | Grafana Live 仪表盘 JSON 模型 |

---

## 三、启动方式

### 前置条件

```bash
pip install websockets
```

### 启动 Grafana（启用 Live）

```bash
cd monitoring
docker-compose up -d
```

docker-compose 已配置 `GF_LIVE_ALLOWED_CHANNEL_PREFIXES=stream/pde/`，允许策略向 `stream/pde/*` 频道推送数据。

Grafana Live 推送认证通过以下环境变量配置（策略进程侧）：

- `GRAFANA_URL`（默认 `http://localhost:3000`）
- `GRAFANA_API_TOKEN`（推荐，若设置则优先使用 Bearer Token）
- `GRAFANA_USER`（默认 `admin`，未设置 token 时使用）
- `GRAFANA_PASSWORD`（默认 `admin`，未设置 token 时使用）

### 启动策略

正常启动策略即可，双后端推流会自动启动：

```bash
python live/run_polymarket_pde.py
```

启动后控制台会打印：

```
📡 Live pusher started (WebSocket + Grafana Live)
📡 Live stream WebSocket server started on ws://0.0.0.0:8765
🖥️  Live dashboard HTTP server started on http://0.0.0.0:8766
```

### 打开 Grafana Live 仪表盘（推荐）

浏览器访问：

```
http://localhost:3000
```

登录后选择 **"PDE Strategy — Live (Sub-Second)"** 仪表盘。面板会自动订阅 Grafana Live 频道，无需手动刷新。

### 打开 HTML 仪表盘（备选）

```
http://localhost:8766/live-dashboard.html
```

HTML 仪表盘通过 WebSocket 连接，左上角连接状态指示灯变绿表示已连接。

---

## 四、14 面板详细说明

仪表盘分为 4 大区域，共 14 个面板，完全对应原始需求。

### ① 实时价格区（BTC + Polymarket）

#### 面板 1：Binance BTC 实时价格

- **数据源**：WebSocket `btc_tick`
- **刷新**：100–200ms（每个 tick 即时推送）
- **显示内容**：
  - 实时 BTC 价格（大号字体，橙色）
  - ΔUSD（相对本局起点的价格偏移）
  - Move（相对 anchor 的 bps 跳变幅度）
  - 1 分钟窗口价格曲线（sparkline）

#### 面板 2：Polymarket Up / Down 实时价格

- **数据源**：WebSocket `poly_tick`
- **显示内容**（UP 和 DOWN 各一个面板）：
  - Mid 价格（中间价）
  - Bid（买价）
  - Ask（卖价）
  - Spread%（价差百分比）

#### 面板 3：Binance vs Polymarket 价格对比

- **数据源**：`btc_tick` + `poly_tick` 双曲线叠加
- **显示内容**：
  - BTC ΔUSD 曲线（橙色）
  - Polymarket Up implied price 曲线（绿色）
  - BTC ΔUSD 当前值
  - Poly ΔP 当前值
  - Lag 指示（来自 latency gap，绿色=有优势，红色=无优势）
- **用途**：一眼看出 Polymarket 是否滞后、滞后多少毫秒、滞后是否扩大（套利机会）

### ② 策略状态区（Phase A/B + EV + 参数）

#### 面板 4：当前 Phase 阶段

- **数据源**：WebSocket `phase_state`
- **显示内容**：
  - 当前阶段（PHASE A 绿色 / PHASE B 蓝色 / IDLE 灰色）
  - 剩余时间（秒）
  - Phase A 交易次数
  - Phase B 交易次数
  - Tail Trade 是否已执行

#### 面板 5：Phase A 参数实时显示

- **数据源**：WebSocket `ev`（phase='A'）
- **显示内容**（8 个参数）：
  - **σ**（波动率估计）
  - **Δlog**（BTC 对数收益率，dimensionless）
  - **z-score**（Δlog / σ_rem）
  - **P(UP)**（理论概率，norm.cdf(z)）
  - **EV**（买入期望值，正=绿色，负=红色）
  - **EV 阈值**（config.ev_threshold_A）
  - **Speed Advantage**（是否满足跳变优势门控，✓/✗）
  - **剩余时间**
- **附加**：EV 实时曲线（sparkline，1 分钟窗口）

#### 面板 6：Phase B 参数实时显示

- **数据源**：WebSocket `ev`（phase='B'）
- **显示内容**（8 个参数）：
  - **ΔUSD**（BTC 价格偏移，USD）
  - **τ**（剩余秒数）
  - **P(flip)**（翻转概率，查表结果）
  - **EV tail**（尾部延续期望值）
  - **Tail 条件**（ΔUSD ≥ delta_tail_min，✓/✗）
  - **Target Token**（目标代币方向）
  - **Tail Done**（是否已执行 tail trade）
  - **剩余时间**
- **附加**：EV tail 实时曲线（sparkline）

### ③ 交易执行区（持仓 + 盈利）

#### 面板 7：当前持仓（Up / Down）

- **数据源**：WebSocket `position`
- **显示内容**（UP 和 DOWN 各一个面板）：
  - 状态（Open / Closed）
  - Phase（A 或 B）
  - 数量
  - 入场价格
  - 当前价格
  - 未实现盈亏（$，绿色=盈利，红色=亏损）
  - PnL%（百分比）
  - 平仓时显示：已实现盈亏（R: xxx）

#### 面板 8：当局盈亏

- **数据源**：WebSocket `pnl_summary`
- **显示内容**：
  - Phase A 已实现 PnL
  - Phase B 已实现 PnL
  - Phase A 未实现 PnL
  - Phase B 未实现 PnL
  - 当局总 PnL（颜色随正负变化）

#### 面板 9：累积盈亏

- **数据源**：WebSocket `pnl_summary`
- **显示内容**：
  - Phase A 累积交易数
  - Phase B 累积交易数
  - 总累积（颜色随正负变化）
  - 累积 PnL 曲线（sparkline）

#### 交易日志

- **数据源**：WebSocket `trade` + `rollover`
- **显示内容**：
  - 每笔交易：Phase (A/B) + 方向 + Token + 价格 + 数量 + 时间
  - Rollover 事件：旧 slug → 新 slug + rounds 数

### ④ 系统健康区（延迟 + 跳变 + 深度）

#### 面板 10：延迟监控（Latency Gap）

- **数据源**：WebSocket `latency`
- **显示内容**：
  - Gap（ms，大号字体）
    - **绿色**：gap > 80ms（你有速度优势）
    - **黄色**：20–80ms（边缘）
    - **红色**：<20ms（不要交易）
  - BTC tick 时间戳
  - Polymarket tick 时间戳
  - 延迟历史曲线（sparkline，颜色随当前延迟变化）

#### 面板 11：Jump Detection（跳变监控）

- **数据源**：WebSocket `jump`
- **显示内容**：
  - 跳变方向（↑ UP 绿色 / ↓ DOWN 红色）
  - 跳变幅度（bps）
  - Anchor 价格
  - 最近 15 次跳变历史列表（方向 + 幅度 + 时间）

#### 面板 12：Polymarket 深度监控

- **数据源**：WebSocket `depth`
- **显示内容**：
  - UP 深度表（前 3 档：价格 / 数量 / 方向，卖=红色，买=绿色）
  - DOWN 深度表（前 3 档）
  - 预计滑点
  - 深度是否满足下单要求

#### 面板 13：策略安全阈值监控

- **数据源**：WebSocket `safety`
- **显示内容**（6 个检查项，任一不满足→红色 ✗）：
  - Speed Advantage（跳变优势）
  - Slippage OK（滑点限制）
  - Volatility OK（波动率限制）
  - Depth OK（深度限制）
  - Jump Fresh（跳变新鲜度）
  - Phase OK（阶段条件）

#### 面板 14：异常检测（自动报警）

- **数据源**：WebSocket `anomaly`
- **自动检测的异常类型**：
  - `btc_stale`：BTC tick 停止超过 10 秒
  - `poly_stale`：Polymarket tick 停止超过 10 秒
- **显示内容**：
  - 异常类型（⚠ 红色标记）
  - 详细描述
  - 时间戳

---

## 五、WebSocket 消息格式

所有消息均为 JSON，包含 `type` 字段用于路由。

### 消息类型一览

| type | 触发时机 | 关键字段 |
|------|----------|----------|
| `btc_tick` | 每次收到 BTC tick | price, delta_usd, move_bps |
| `poly_tick` | 每次收到 Polymarket quote | token, bid, ask, mid, spread_pct |
| `ev` | Phase A/B 计算 EV 时 | phase, ev, sigma, z_score, delta_log, p_up, p_flip, delta_usd, speed_advantage, ev_threshold, remaining, tail_condition |
| `phase_state` | 每次路由到 Phase A/B | phase, remaining, a_trades, b_trades, tail_done |
| `position` | 开仓/持仓变化/平仓 | token, phase, is_open, entry_price, current_price, unrealized_pnl, realized_pnl, pnl_pct, quantity |
| `latency` | 每次收到 Polymarket tick | gap_ms, btc_ts, poly_ts |
| `jump` | BTC 跳变检测触发 | direction, move_bps, jump_ts, anchor_price |
| `trade` | 执行开仓 | phase, token, side, price, qty, reason |
| `safety` | 每次路由到 Phase A/B | speed_advantage, slippage_ok, volatility_ok, depth_ok, jump_fresh, phase_ok |
| `depth` | 每次路由到 Phase A/B | token, levels[{price, qty, side}] |
| `pnl_summary` | 每次平仓后 | phase_a_realized, phase_b_realized, phase_a_unrealized, phase_b_unrealized, round_pnl, cumulative_a, cumulative_b |
| `rollover` | 市场轮换时 | old_slug, new_slug, rounds |
| `anomaly` | 检测到异常 | anomaly_type, detail |

---

## 六、策略中的推流集成点

### 生命周期

| 时机 | 推流调用 |
|------|----------|
| `on_start()` | `CompositeLivePusher().start()` — 启动 WebSocket + Grafana Live 双后端 |
| `on_stop()` | `CompositeLivePusher().stop()` — 停止所有后端 |

### 数据推送

| 事件处理器 | 推送内容 |
|------------|----------|
| `on_quote_tick()` (BTC) | `push_btc_tick()` + `push_latency()` |
| `on_quote_tick()` (Poly) | `push_poly_tick()` + `push_latency()` |
| `on_trade_tick()` (BTC) | `push_btc_tick()` |
| `_update_btc_metrics()` | `push_jump()` (跳变检测触发时) |
| `_process_tick()` | `push_phase_state()` + `push_safety()` + `push_anomaly()` + `push_depth()` |
| `_execute_phase_A()` | `push_ev()` (含 z_score, delta_log, speed_advantage 等详细参数) |
| `_execute_phase_B()` | `push_ev()` (含 delta_usd, p_flip, tail_condition 等详细参数) |
| `_open_position()` | `push_trade()` |
| `on_position_opened()` | `push_position()` (is_open=True) |
| `on_position_changed()` | `push_position()` (含 unrealized_pnl, pnl_pct) |
| `on_position_closed()` | `push_position()` (is_open=False, realized_pnl) + `push_pnl_summary()` |
| `_on_rollover_timer()` | `push_rollover()` |

---

## 七、端口说明

| 端口 | 协议 | 用途 |
|------|------|------|
| 8765 | WebSocket | 实时数据推流（策略→HTML仪表盘） |
| 8766 | HTTP | HTML 仪表盘文件服务 |
| 3000 | HTTP | Grafana（含 Live 仪表盘，推荐） |
| 8001 | HTTP | Prometheus metrics（原有，不变） |
| 9090 | HTTP | Prometheus Server（原有，不变） |

---

## 八、三条监控链路对比

| 链路 | 延迟 | 持久化 | 渲染 | 告警 | 适用场景 |
|------|------|--------|------|------|----------|
| Prometheus | ~5s | ✅ 长期存储 | Grafana | ✅ 内置 | 趋势分析、历史回溯 |
| WebSocket→HTML | ~100ms | ❌ | 自定义JS | ❌ | 快速调试、开发阶段 |
| Grafana Live | ~200ms | ❌ | Grafana原生 | ✅ 内置 | **生产推荐**、实时决策 |

- **Prometheus 链路**（5 秒级）：策略 → Prometheus HTTP metrics → Grafana → 长期趋势、告警
- **WebSocket 链路**（100–200ms 级）：策略 → WebSocket → 浏览器 HTML 仪表盘 → 快速调试
- **Grafana Live 链路**（200ms 级）：策略 → HTTP POST → Grafana Live → 原生面板 → **生产推荐**
- 三条链路完全独立，Prometheus 的所有指标和仪表盘保持不变
- WebSocket 和 Grafana Live 链路不持久化数据，仅做实时展示

---

## 九、故障排查

### Grafana Live 仪表盘无数据

1. 确认 Grafana 已启动：`docker-compose up -d`
2. 确认 `GF_LIVE_ALLOWED_CHANNEL_PREFIXES=stream/pde/` 已在 docker-compose 中配置
3. 检查策略日志是否有 Grafana Live push 错误
4. 在 Grafana 中检查 Live 频道：浏览 → Explore → 选择 "Grafana" 数据源 → 查询 `stream/pde/btc`
5. 确认策略运行在能访问 `http://localhost:3000` 的网络中

如果出现 `HTTP Error 401: Unauthorized`：

1. 优先使用 `GRAFANA_API_TOKEN`（避免 Basic 认证密码漂移）
2. 若使用 Basic 认证，确认 `GRAFANA_USER/GRAFANA_PASSWORD` 与 Grafana 实际账号一致
3. 若 Grafana 挂载了持久化卷（`grafana-storage`），历史密码可能覆盖 `docker-compose` 中的默认 `admin/admin`
4. 必要时重置 Grafana 密码或清理 Grafana 卷后重启

### HTML 仪表盘连接不上

1. 确认策略已启动且控制台打印了 `📡 Live pusher started`
2. 确认 `websockets` 库已安装：`pip install websockets`
3. 确认端口 8765/8766 未被占用
4. 浏览器访问 `http://localhost:8766/live-dashboard.html`

### 数据不更新

1. **Grafana Live**：检查面板数据源是否为内置 "Grafana" 数据源，频道是否为 `stream/pde/xxx`
2. **HTML 仪表盘**：检查左上角连接状态灯是否为绿色
3. 确认策略正在接收 tick 数据（检查策略日志）

### 面板显示 "—"

- 表示尚未收到对应类型的消息，策略需要先收到相关 tick 才会推送数据

---

## 十、Grafana Live 频道说明

策略通过 HTTP POST 推送数据到 Grafana Live，接口路径为 `/api/live/push/{stream_id}`（本项目使用 `stream_id=pde`，频道映射为 `stream/pde/{measurement}`）。

| 频道 | 推送内容 | 关键字段 |
|------|----------|----------|
| `stream/pde/btc` | BTC 价格 | price, delta_usd, move_bps |
| `stream/pde/poly` | Polymarket 报价 | token, bid, ask, mid, spread_pct |
| `stream/pde/ev` | EV + Phase 参数 | phase, ev, sigma, z_score, delta_log, p_up, p_flip, delta_usd, speed_advantage |
| `stream/pde/phase` | 当前阶段 | phase, remaining, a_trades, b_trades, tail_done |
| `stream/pde/position` | 持仓状态 | token, phase, is_open, entry_price, current_price, unrealized_pnl, realized_pnl, pnl_pct |
| `stream/pde/latency` | 延迟 | gap_ms, btc_ts, poly_ts |
| `stream/pde/jump` | 跳变检测 | direction, move_bps, jump_ts, anchor_price |
| `stream/pde/pnl` | 盈亏 | phase_a_realized, phase_b_realized, round_pnl, cumulative_a, cumulative_b |
| `stream/pde/safety` | 安全阈值 | speed_advantage, slippage_ok, volatility_ok, depth_ok, jump_fresh, phase_ok |
| `stream/pde/depth` | 订单簿深度 | token, l0_price, l0_qty, l0_side, ... |
| `stream/pde/anomaly` | 异常检测 | anomaly_type, detail |

---

## 十一、扩展指南

### 添加新的推送数据类型

1. 在 `utils/live_stream_server.py` 中添加新的 `push_xxx()` 方法
2. 在 `utils/grafana_live_pusher.py` 中添加对应的 `push_xxx()` 方法（同签名 + `**kw`）
3. 在 `utils/composite_pusher.py` 中添加新的 `push_xxx()` 委托方法
4. 在策略对应事件处理器中调用 `self.live_server.push_xxx()`
5. 在 `monitoring/live-dashboard.html` 的 `handleMessage()` 中添加新的 `case`
6. 在 `monitoring/pde-live-dashboard.json` 中添加新的 Grafana 面板

### 只使用 Grafana Live（禁用 HTML 仪表盘）

在策略 `on_start()` 中只添加 GrafanaLivePusher：

```python
self.live_server = CompositeLivePusher()
self.live_server.add(GrafanaLivePusher(grafana_url="http://localhost:3000", auth=("admin", "admin")))
# 或者使用 API Token:
# self.live_server.add(GrafanaLivePusher(grafana_url="http://localhost:3000", api_token="<token>"))
self.live_server.start()
```

### 连接第三方 WebSocket 客户端

任何 WebSocket 客户端都可以连接 `ws://<host>:8765`，接收 JSON 流：

```python
import asyncio, websockets

async def listen():
    async with websockets.connect("ws://localhost:8765") as ws:
        async for msg in ws:
            data = json.loads(msg)
            print(data["type"], data.get("price", ""))

asyncio.run(listen())
```
