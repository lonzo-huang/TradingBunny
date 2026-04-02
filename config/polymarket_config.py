# config/polymarket_config.py
import os
import json
import urllib.request
import urllib.parse
from decimal import Decimal
from datetime import datetime, timezone

from nautilus_trader.config import (
    TradingNodeConfig,
    CacheConfig,
    DatabaseConfig,
    LoggingConfig,
)
from nautilus_trader.trading.config import ImportableStrategyConfig
from nautilus_trader.live.risk_engine import LiveRiskEngineConfig
from nautilus_trader.live.execution_engine import LiveExecEngineConfig
from nautilus_trader.adapters.polymarket.config import PolymarketDataClientConfig, PolymarketExecClientConfig
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.common.config import InstrumentProviderConfig
from nautilus_trader.adapters.polymarket.providers import PolymarketInstrumentProviderConfig



# ─────────────────────────────────────────────────────────────────────────────
#  启动前：动态解析当前 5 分钟窗口的 YES token ID
# ─────────────────────────────────────────────────────────────────────────────

def resolve_current_token_id(base_slug: str = "btc-updown-5m", interval_minutes: int = 5) -> str | None:
    """
    通过 Gamma API + CLOB API 解析当前时间窗口的 YES token ID（0x 格式）。
    在节点启动之前调用，用于预加载 Instrument。
    """
    now = datetime.now(timezone.utc)
    aligned = (now.minute // interval_minutes) * interval_minutes
    market_time = now.replace(minute=aligned, second=0, microsecond=0)
    slug = f"{base_slug}-{int(market_time.timestamp())}"
    print(f"🔍 Resolving token ID for: {slug}")

    try:
        # Step 1: Gamma API → conditionId
        params = urllib.parse.urlencode({"slug": slug, "active": "true", "limit": 1})
        req = urllib.request.Request(
            f"https://gamma-api.polymarket.com/markets?{params}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            markets = json.loads(resp.read())

        if not markets:
            print(f"❌ Gamma API: no market found for {slug}")
            return None

        condition_id = markets[0].get("conditionId") or markets[0].get("condition_id")
        if not condition_id:
            print("❌ Gamma API: no conditionId")
            return None
        print(f"   conditionId: {condition_id}")

        # Step 2: CLOB API → token_id
        req2 = urllib.request.Request(
            f"https://clob.polymarket.com/markets/{condition_id}",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req2, timeout=8) as resp2:
            clob = json.loads(resp2.read())

        tokens = clob.get("tokens", [])
        if not tokens:
            print("❌ CLOB API: no tokens")
            return None

        yes_token = next(
            (t for t in tokens if t.get("outcome", "").lower() == "yes"),
            tokens[0],
        )
        token_id = yes_token.get("token_id", "")

        # 十进制大整数 → 0x 十六进制
        if token_id and not token_id.startswith("0x"):
            token_id = hex(int(token_id))

        print(f"✅ YES token_id: {token_id}")
        return token_id

    except Exception as e:
        print(f"❌ resolve_current_token_id failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  节点配置
# ─────────────────────────────────────────────────────────────────────────────

def configure_polymarket_node(execution_mode: str = "sandbox") -> TradingNodeConfig:
    """
    Polymarket 节点配置：
    - 数据：Polymarket RTDS 公开 WebSocket（真实价格）
    - 执行：根据 execution_mode 参数选择执行客户端
      - "sandbox": Sandbox 本地虚拟撮合（假钱）
      - "live": Polymarket 实盘交易（真钱）
      - "both": 同时配置两个执行客户端
    """

    # ── 启动前解析当前市场的 token ID ────────────────────────────────────
    token_id = resolve_current_token_id("btc-updown-5m", interval_minutes=5)
    load_ids = [token_id] if token_id else []
    if not load_ids:
        print("⚠️  Warning: no token ID resolved, DataClient will start without preloaded instruments")

    # ── A. Polymarket 数据客户端 ──────────────────────────────────────────
    polymarket_data_cfg = PolymarketDataClientConfig(
        private_key=os.getenv("POLYMARKET_PK"),
        funder=os.getenv("POLYMARKET_FUNDER"),
        api_key=os.getenv("POLYMARKET_API_KEY"),
        api_secret=os.getenv("POLYMARKET_API_SECRET"),
        passphrase=os.getenv("POLYMARKET_API_PASSPHRASE"),
        drop_quotes_missing_side=False,
        instrument_config=PolymarketInstrumentProviderConfig(
            # ★ 告诉 Polymarket provider 去调用这个函数获取 slug 列表
            # 格式：模块路径:函数名
            event_slug_builder="utils.slug_builder:build_btc_updown_slugs",
        ),
    )

    # ── B. Sandbox 执行客户端 ─────────────────────────────────────────────
    sandbox_exec_cfg = SandboxExecutionClientConfig(
        venue="POLYMARKET",                 # ★ 关键修复：使用 POLYMARKET 作为 venue，与数据客户端一致
        account_type="MARGIN",              # 必须传字符串，不能传枚举
        starting_balances=["1000000 USDC"], # 必须传字符串，不能传 Money 对象
    )

    # ── C. Polymarket 执行客户端（实盘交易）──────────────────────────────────
    polymarket_exec_cfg = PolymarketExecClientConfig(
        private_key=os.getenv("POLYMARKET_PK"),
        funder=os.getenv("POLYMARKET_FUNDER"),
        api_key=os.getenv("POLYMARKET_API_KEY"),
        api_secret=os.getenv("POLYMARKET_API_SECRET"),
        passphrase=os.getenv("POLYMARKET_API_PASSPHRASE"),
    )

    # ── D. 根据 execution_mode 动态配置执行客户端 ────────────────────────
    exec_clients = {}
    reconciliation = True  # 默认开启对账
    
    if execution_mode == "sandbox":
        exec_clients["SANDBOX"] = sandbox_exec_cfg
        reconciliation = False  # Sandbox 不支持对账
        print("📋 Execution mode: SANDBOX (paper trading)")
    elif execution_mode == "live":
        exec_clients["POLYMARKET"] = polymarket_exec_cfg
        print("📋 Execution mode: POLYMARKET (live trading)")
    elif execution_mode == "both":
        exec_clients["SANDBOX"] = sandbox_exec_cfg
        exec_clients["POLYMARKET"] = polymarket_exec_cfg
        reconciliation = False  # 包含 Sandbox 时关闭对账
        print("📋 Execution mode: BOTH (sandbox + live)")
    else:
        raise ValueError(f"Invalid execution_mode: {execution_mode}. Must be 'sandbox', 'live', or 'both'")

    return TradingNodeConfig(
        trader_id=os.getenv("NAUTILUS_TRADER_ID", "POLYMARKET-001"),

        data_clients={
            "POLYMARKET": polymarket_data_cfg,
        },

        exec_clients=exec_clients,

        # ★ 根据 execution_mode 动态设置 reconciliation
        exec_engine=LiveExecEngineConfig(
            reconciliation=reconciliation,
        ),

        cache=CacheConfig(
            database=DatabaseConfig(
                type="redis",
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                timeout=2,
            ),
            encoding="msgpack",
            tick_capacity=20_000,
        ),

        logging=LoggingConfig(
            log_level=os.getenv("NAUTILUS_LOG_LEVEL", "INFO"),
            log_directory="./logs",
            log_colors=True,
        ),

        risk_engine=LiveRiskEngineConfig(
            bypass=False,
        ),

        strategies=[
            ImportableStrategyConfig(
                strategy_path="strategies.polymarket_strategy:PolymarketStrategy",
                config_path="strategies.polymarket_strategy:PolymarketStrategyConfig",
                config={
                    "market_base_slug": "btc-updown-5m",
                    "market_interval_minutes": 5,
                    "trade_size": "100",   # 字符串，NT 会自动转 Decimal
                    "auto_rollover": True,
                    "order_id_tag": "001",
                },
            ),
        ],
    )