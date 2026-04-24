"""
Approve USDC spending allowance for all Polymarket contracts on Polygon.
Run ONCE before starting live trading.

Usage:
    python scripts/approve_usdc.py
"""
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from web3 import Web3
from eth_account import Account

# ── Polygon RPC ──
POLYGON_RPC = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
w3 = Web3(Web3.HTTPProvider(POLYGON_RPC))

if not w3.is_connected():
    print("[ERROR] Cannot connect to Polygon RPC.")
    sys.exit(1)

print(f"[OK] Connected to Polygon (chain_id={w3.eth.chain_id})")

# ── Addresses ──
USDC_ADDRESS = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

SPENDERS = {
    "CTF Exchange":         "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
    "NegRisk CTF Exchange": "0xC5d563A36AE78145C45a50134d48A1215220f80a",
    "NegRisk Adapter":      "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
}

USDC_ABI = [
    {"inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
     "name": "approve", "outputs": [{"name": "", "type": "bool"}],
     "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
     "name": "allowance", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "account", "type": "address"}],
     "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}],
     "stateMutability": "view", "type": "function"},
]

# ── Load key ──
private_key = os.getenv("POLYMARKET_PK")
funder_addr = os.getenv("POLYMARKET_FUNDER")

if not private_key:
    print("[ERROR] POLYMARKET_PK not set in .env")
    sys.exit(1)

account = Account.from_key(private_key)
signer_addr = account.address

print(f"[INFO] Signer : {signer_addr}")
print(f"[INFO] Funder : {funder_addr}")

if funder_addr and funder_addr.lower() != signer_addr.lower():
    print("[WARN] POLYMARKET_PK is NOT the key of POLYMARKET_FUNDER.")
    print("       Go to polymarket.com → Deposit USDC to trigger on-chain approval.")
    sys.exit(1)

usdc = w3.eth.contract(address=USDC_ADDRESS, abi=USDC_ABI)

# ── Print current state ──
balance = usdc.functions.balanceOf(signer_addr).call()
print(f"\n[INFO] USDC balance: {balance / 1e6:.4f} USDC")
for name, addr in SPENDERS.items():
    al = usdc.functions.allowance(signer_addr, Web3.to_checksum_address(addr)).call()
    status = "OK" if al > 0 else "NEED APPROVE"
    print(f"[INFO]   {name}: allowance={al/1e6:.2f} USDC [{status}]")

# ── Approve all spenders that are at 0 ──
MAX_UINT256 = 2**256 - 1
GAS_PRICE   = int(w3.eth.gas_price * 1.5)   # 1.5x current gas price for fast inclusion
print(f"[INFO] Gas price: {w3.from_wei(GAS_PRICE, 'gwei'):.1f} gwei")

def send_approve(name: str, spender: str) -> None:
    spender = Web3.to_checksum_address(spender)
    print(f"\n[SEND] Approving {name} ...")
    nonce = w3.eth.get_transaction_count(signer_addr)
    tx = usdc.functions.approve(spender, MAX_UINT256).build_transaction({
        "from": signer_addr, "nonce": nonce,
        "gas": 100_000, "gasPrice": GAS_PRICE, "chainId": 137,
    })
    signed  = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"[OK] TX: https://polygonscan.com/tx/{tx_hash.hex()}")
    print("[WAIT] Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
    if receipt.status == 1:
        print(f"[OK] {name} approved (block={receipt.blockNumber})")
    else:
        print(f"[ERROR] TX failed: {receipt}")

any_sent = False
for name, addr in SPENDERS.items():
    al = usdc.functions.allowance(signer_addr, Web3.to_checksum_address(addr)).call()
    if al == 0:
        send_approve(name, addr)
        any_sent = True

if not any_sent:
    print("\n[OK] All allowances already set. You can start live trading.")
else:
    print("\n[OK] All approvals done. You can now start live trading.")
