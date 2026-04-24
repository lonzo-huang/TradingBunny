"""
诊断并修复 Polymarket USDC allowance 问题。
用 py_clob_client 的 get_balance_allowance + update_balance_allowance。

Usage:
    python scripts/fix_allowance.py
"""
import os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
from py_clob_client.constants import POLYGON

pk      = os.getenv("POLYMARKET_PK")
funder  = os.getenv("POLYMARKET_FUNDER")
api_key = os.getenv("POLYMARKET_API_KEY")
api_sec = os.getenv("POLYMARKET_API_SECRET")
api_pass= os.getenv("POLYMARKET_API_PASSPHRASE")

if not all([pk, api_key, api_sec, api_pass]):
    print("[ERROR] 缺少 .env 配置项 (PK/API_KEY/API_SECRET/API_PASSPHRASE)")
    sys.exit(1)

from py_clob_client.clob_types import ApiCreds
creds = ApiCreds(api_key=api_key, api_secret=api_sec, api_passphrase=api_pass)

client = ClobClient(
    host="https://clob.polymarket.com",
    chain_id=POLYGON,
    key=pk,
    creds=creds,
    signature_type=0,   # EOA
    funder=funder,
)

print(f"[INFO] Funder : {funder}")
print(f"[INFO] Signer : {client.get_address()}")

# ── Step 1: 查询当前余额和 allowance ──
print("\n[STEP 1] 查询 COLLATERAL (USDC) 余额和 allowance ...")
try:
    result = client.get_balance_allowance(
        params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    )
    print(f"[INFO] get_balance_allowance 结果: {result}")
except Exception as e:
    print(f"[WARN] get_balance_allowance 失败: {e}")

# ── Step 2: 触发 update_balance_allowance (让 Polymarket 后端重新读取链上状态) ──
print("\n[STEP 2] 触发 update_balance_allowance (COLLATERAL) ...")
try:
    result2 = client.update_balance_allowance(
        params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
    )
    print(f"[INFO] update_balance_allowance 结果: {result2}")
except Exception as e:
    print(f"[WARN] update_balance_allowance 失败: {e}")

print("\n[DONE] 完成。如果 allowance 仍为 0，需要在 Polymarket 网站重新存款或手动执行链上 approve。")
print("       网站操作路径: polymarket.com → 右上角头像 → Deposit → 存入 USDC")
print("       存款流程会自动触发 approve 交易。")
