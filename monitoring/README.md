# Polymarket 策略监控系统

使用 Prometheus + Grafana 实时监控交易策略的盈亏、持仓、价格等指标。

## 监控指标

| 指标名称 | 类型 | 描述 |
|---------|------|------|
| `polymarket_price` | Gauge | Token 实时价格 (bid/ask) |
| `polymarket_unrealized_pnl` | Gauge | 未实现盈亏 |
| `polymarket_realized_pnl_total` | Counter | 累计已实现盈亏 |
| `polymarket_orders_total` | Counter | 订单提交次数 |
| `polymarket_filled_orders_total` | Counter | 订单成交次数 |
| `polymarket_position_size` | Gauge | 持仓数量 |
| `polymarket_position_entry_price` | Gauge | 持仓入场价 |
| `polymarket_ticks_total` | Counter | 行情 tick 次数 |

## 快速开始

### 1. 安装依赖

```bash
pip install prometheus-client>=0.19.0
```

### 2. 启动策略

运行策略时会自动启动 Prometheus HTTP 服务器（端口 8000）：

```bash
python live/run_polymarket.py --execution-mode sandbox
```

日志中会显示：
```
📊 Prometheus metrics server started on http://localhost:8000
   Metrics endpoint: http://localhost:8000/metrics
```

### 3. 启动 Prometheus + Grafana

```bash
cd monitoring
docker-compose up -d
```

### 4. 访问监控界面

- **Grafana**: http://localhost:3000 (用户名: admin, 密码: admin)
- **Prometheus**: http://localhost:9090
- **策略指标**: http://localhost:8000/metrics

### 5. 配置 Grafana 数据源

首次使用需要手动添加 Prometheus 数据源：

1. 访问 http://localhost:3000
2. 登录: admin / admin
3. 左侧菜单 → Configuration → Data Sources
4. 点击 "Add data source"
5. 选择 "Prometheus"
6. URL 填写: `http://prometheus:9090`
7. 点击 "Save & Test"

### 6. 导入仪表板

1. 左侧菜单 → Dashboards → Import
2. 上传 `monitoring/grafana-dashboard.json`
3. 选择 Prometheus 数据源
4. 点击 Import

## 仪表板面板说明

### 第一行
- **Token Prices**: Up/Down token 的 bid/ask 价格实时走势
- **Unrealized PnL**: 当前持仓的浮动盈亏
- **Total Realized PnL**: 累计已实现盈亏
- **Position Size**: 持仓数量仪表盘

### 第二行
- **Orders Submitted**: 订单提交频率（按 token 和方向区分）
- **Order Fills**: 成交频率

### 第三行
- **Position Entry Price**: 持仓入场价变化
- **Quote Ticks Rate**: 行情数据接收频率

## 停止监控

```bash
cd monitoring
docker-compose down
```

## 故障排查

### 策略指标无法访问
- 检查策略是否正常运行
- 确认端口 8000 未被占用：`lsof -i :8000` (macOS/Linux) / `netstat -ano | findstr :8000` (Windows)
- 查看策略日志中的 Prometheus 启动信息

### Prometheus 无法抓取指标
- 确保策略运行在本地（Prometheus 使用 `host.docker.internal:8000`）
- Windows 用户需要在 Docker Desktop 设置中启用 "Use the WSL 2 based engine"
- 检查防火墙设置

### Grafana 无法连接 Prometheus
- 确认 Prometheus 容器运行：`docker ps`
- 检查 Grafana 数据源配置中的 URL 是否为 `http://prometheus:9090`

## 自定义监控

可以在 `polymarket_strategy.py` 中添加更多指标：

```python
# 添加新指标
my_custom_gauge = Gauge('my_metric_name', 'Description', ['label1'])

# 更新指标值
my_custom_gauge.labels(label1='value').set(123)
```

更多 Prometheus 客户端用法：https://github.com/prometheus/client_python
