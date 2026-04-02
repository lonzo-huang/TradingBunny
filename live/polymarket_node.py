# live/polymarket_node.py
# ⚠️  此文件与 config/polymarket_config.py 功能重复。
#     run_polymarket.py 已经从 config/polymarket_config.py 导入配置，
#     建议废弃此文件，或只保留以下正确的 import 参考。

# BUG 5 修复：TradingNodeConfig 的正确 import 路径
# 错误写法：from nautilus_trader.live.config import TradingNodeConfig
# 正确写法：
from nautilus_trader.config import TradingNodeConfig        # ← 正确
from nautilus_trader.live.node import TradingNode

# 其他常用 import 参考
from nautilus_trader.config import CacheConfig, DatabaseConfig, LoggingConfig
from nautilus_trader.live.risk_engine import LiveRiskEngineConfig
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model import Money
from nautilus_trader.adapters.polymarket.config import PolymarketDataClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig