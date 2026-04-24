# Live Trading Setup & 历史修复记录

> **最后更新**: 2026-04-24  
> **适用版本**: PDE Strategy v1.x（NautilusTrader + py_clob_client）

---

## 目录

1. [首次实盘启动清单](#1-首次实盘启动清单)
2. [关键 Bug 修复记录](#2-关键-bug-修复记录)
3. [scripts/ 工具脚本说明](#3-scripts-工具脚本说明)
4. [执行模式说明](#4-执行模式说明)
5. [常见错误 & 排查](#5-常见错误--排查)

---

## 1. 首次实盘启动清单

首次在新钱包运行实盘前，必须完成以下一次性设置：

### 1.1 环境变量（`.env`）

```env
POLYMARKET_PK=<你的 EOA 私钥>
POLYMARKET_FUNDER=<你的钱包地址>
POLYMARKET_API_KEY=<CLOB API Key>
POLYMARKET_API_SECRET=<CLOB API Secret>
POLYMARKET_API_PASSPHRASE=<CLOB API Passphrase>
```

### 1.2 链上 USDC Allowance（**必做，仅一次**）

Polymarket 的 CTF Exchange 合约必须被预先授权才能划转你钱包里的 USDC。  
这是 ERC-20 标准的 `approve()` 机制，与市场是否过期无关，授权永久有效。

**需授权的三个合约**（Polygon 主网）：

| 合约名 | 地址 |
|--------|------|
| CTF Exchange | `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E` |
| NegRisk CTF Exchange | `0xC5d563A36AE78145C45a50134d48A1215220f80a` |
| NegRisk Adapter | `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296` |

**执行授权**（会发送 3 笔链上交易，消耗极少量 MATIC）：

```powershell
$env:POLYGON_RPC_URL = "https://polygon-bor-rpc.publicnode.com"
python scripts/approve_usdc.py
```

**验证授权状态**：

```powershell
python scripts/fix_allowance.py
```

预期输出：所有合约的 `allowances` 值为 `115792...935`（即 MAX_UINT256）。

### 1.3 验证余额

脚本输出会显示 `USDC balance`，确认钱包有足够 USDC（至少 `per_trade_usd` × 5）。

---

## 2. 关键 Bug 修复记录

### Fix #1 — `ExecEngine` 自动转换 quote_quantity（`polymarket_pde_config.py`）

**问题**：NautilusTrader 的 `LiveExecEngineConfig` 默认会将 `quote_quantity=True` 的 USDC 数量自动转换为 token 数量再提交给执行客户端，导致 Polymarket 拒单：

```
OrderDenied: Polymarket market BUY orders require quote-denominated quantities
```

**修复**：在 `config/polymarket_pde_config.py` 中禁用自动转换：

```python
exec_engine=LiveExecEngineConfig(
    convert_quote_qty_to_base=False,   # ← 必须设置
    ...
)
```

---

### Fix #2 — BUY 订单必须使用 `quote_quantity=True`（`execution_mixin.py`）

**问题**：Polymarket BUY 市价单要求以 USDC（quote）计价，而非 token（base）数量。  
原始代码未传 `quote_quantity` 参数，导致拒单。

**修复**：在 `strategies/pde/execution_mixin.py` 的 `_enter_position()` 中：

```python
order = self.order_factory.market(
    instrument_id=instrument.id,
    order_side=OrderSide.BUY,
    quantity=Quantity.from_str(f"{self._config.per_trade_usd:.6f}"),
    quote_quantity=True,      # ← BUY 必须为 True
    tags=[...],
)
```

---

### Fix #3 — `on_order_denied` 状态回滚（`execution_mixin.py`）

**问题**：`OrderDenied` 事件未被处理，导致策略内部仓位状态记录了虚假入场，后续产生幽灵 PnL。

**修复**：添加 `on_order_denied` 处理器，镜像 `on_order_rejected` 的清理逻辑：

```python
def on_order_denied(self, event: OrderDenied) -> None:
    self._handle_entry_order_failure(event.client_order_id, "denied")
```

---

### Fix #4 — `py_clob_client` 价格精度违反 0.01 tick（`builder.py`）

**问题**：`py_clob_client` 内部用浮点除法计算 token 数量（`5.0 / 0.54 = 9.2592...`），导致反算出的价格不符合 0.01 tick size，API 返回：

```
OrderRejected: Price (0.5400034560221185) breaks minimum tick size rule: 0.01
```

**修复位置**：`C:\Python314\Lib\site-packages\py_clob_client\order_builder\builder.py`  
（注意：此文件在 site-packages，**不在项目 git 仓库内**，每次重装 Python 环境需重新修改）

**修复内容**（`get_market_order_amounts` BUY 分支）：

```python
# 原始代码（有浮点精度问题）
raw_maker_amt = round_down(amount, round_config.size)
raw_taker_amt = raw_maker_amt / raw_price

# 修复后（整数 token 数 + Decimal 反算 USDC）
from decimal import Decimal as _D
import math
_price_str = f"{raw_price:.{round_config.price}f}"
raw_taker_amt = math.floor(round_down(amount, round_config.size) / raw_price)
if raw_taker_amt <= 0:
    raw_taker_amt = 1
raw_maker_amt = float(_D(str(raw_taker_amt)) * _D(_price_str))
```

---

### Fix #5 — USDC Allowance 为 0（链上授权缺失）

**问题**：即使 Polymarket 账户有余额（`balance > 0`），如果从未执行过链上 `approve()`，CTF Exchange 无法划转 USDC：

```
OrderRejected: not enough balance / allowance: the allowance is not enough
→ spender: 0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E, allowance: 0
```

**修复**：运行 `scripts/approve_usdc.py`（见第 1.2 节）。

---

## 3. scripts/ 工具脚本说明

| 脚本 | 用途 | 使用频率 |
|------|------|----------|
| `scripts/approve_usdc.py` | 对 Polygon 上三个 Polymarket 合约执行链上 USDC `approve(MAX_UINT256)` | **一次性**（新环境必做） |
| `scripts/fix_allowance.py` | 通过 py_clob_client API 查询当前余额和 allowance 状态，并触发后端刷新 | 诊断用 |
| `scripts/pde_log_ui.py` | 实时日志查看 UI | 调试时使用 |
| `scripts/start_pde_with_log.ps1` | 启动策略并附带日志窗口的 PowerShell 脚本 | 日常启动 |
| `scripts/view_pde_log.ps1` | 查看历史日志文件 | 调试时使用 |

### `approve_usdc.py` 使用注意事项

- 需要 `web3` 库（已在环境中：`pip install web3`）
- 默认 RPC：`https://polygon-bor-rpc.publicnode.com`（如连不上可在 `.env` 中设 `POLYGON_RPC_URL`）
- Gas 使用动态定价（`1.5x 当前 gas price`），Polygon 当前约 125-200 gwei，每笔约 0.002 MATIC
- `POLYMARKET_PK` 必须是 `POLYMARKET_FUNDER` 地址的私钥，否则脚本会提示错误

---

## 4. 执行模式说明

启动命令：

```powershell
python live/run_polymarket_pde.py --mode sandbox   # 沙盒（默认，虚拟资金）
python live/run_polymarket_pde.py --mode live       # 实盘（真实资金）
python live/run_polymarket_pde.py --mode both       # 同时运行沙盒+实盘（两个子进程）
```

| 模式 | 数据源 | 执行客户端 | 资金 | 对账 |
|------|--------|-----------|------|------|
| `sandbox` | Polymarket WebSocket | SandboxExecClient | 虚拟 | 关闭 |
| `live` | Polymarket WebSocket | PolymarketExecClient | 真实 USDC | 开启 |
| `both` | Polymarket WebSocket | 两个客户端（独立子进程） | 各自独立 | live 开启 |

**关键配置项**（`config/polymarket_pde_config.py`）：

```python
LiveExecEngineConfig(
    convert_quote_qty_to_base=False,  # 禁止 ExecEngine 自动转换 quote 数量
)
```

---

## 5. 常见错误 & 排查

### `allowance: 0, order amount: XXXXXXX`

→ 运行 `python scripts/approve_usdc.py` 完成链上授权。

### `Price (...) breaks minimum tick size rule: 0.01`

→ 检查 `py_clob_client/order_builder/builder.py` 是否应用了 Fix #4。  
→ 文件路径：`C:\Python314\Lib\site-packages\py_clob_client\order_builder\builder.py`

### `Polymarket market BUY orders require quote-denominated quantities`

→ 检查 `execution_mixin.py` 是否设置 `quote_quantity=True`（Fix #2）。  
→ 检查 `polymarket_pde_config.py` 是否设置 `convert_quote_qty_to_base=False`（Fix #1）。

### `Cannot connect to Polygon RPC`

→ 尝试在命令行设置备用 RPC：

```powershell
$env:POLYGON_RPC_URL = "https://polygon-bor-rpc.publicnode.com"
python scripts/approve_usdc.py
```

### 订单被拒后策略一直重复下单

→ 检查 `on_order_denied` 处理器是否正确实现（Fix #3）。  
→ 查看 `[CLEAR] 入场单被拒绝` 日志是否出现，确认状态已回滚。
