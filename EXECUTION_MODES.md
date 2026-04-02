# 使用示例

## 执行客户端配置

现在 `configure_polymarket_node()` 函数支持三种执行模式：

### 1. Sandbox 模式（纸交易，默认）
```bash
python live/run_polymarket.py
# 或
python live/run_polymarket.py --mode sandbox
```

### 2. Live 模式（实盘交易）
```bash
python live/run_polymarket.py --mode live
```

### 3. Both 模式（同时配置 Sandbox 和 Live）
```bash
python live/run_polymarket.py --mode both
```

## 配置说明

- **sandbox**: 使用 Sandbox 执行客户端，虚拟资金，关闭对账
- **live**: 使用 Polymarket 执行客户端，真实资金，开启对账
- **both**: 同时配置两个执行客户端，包含 Sandbox 时关闭对账

## 环境变量

确保 `.env` 文件包含以下变量：

```env
POLYMARKET_PK=your_private_key
POLYMARKET_FUNDER=your_funder_address
POLYMARKET_API_KEY=your_api_key
POLYMARKET_API_SECRET=your_api_secret
POLYMARKET_API_PASSPHRASE=your_passphrase
```

## 代码中使用

```python
from config.polymarket_config import configure_polymarket_node

# Sandbox 模式
config = configure_polymarket_node()  # 默认
# 或
config = configure_polymarket_node(execution_mode="sandbox")

# Live 模式
config = configure_polymarket_node(execution_mode="live")

# Both 模式
config = configure_polymarket_node(execution_mode="both")
```
