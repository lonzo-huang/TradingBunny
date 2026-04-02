"""
utils/find_current_market.py

查询 Polymarket Gamma API + CLOB API，找到当前 btc-updown-5m 5分钟窗口的真实 token ID，
并自动更新 .env 文件中的 TEST_MARKET_ID 和 TEST_MARKET_SLUG。

使用方法：
    python utils/find_current_market.py
"""

import os
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

GAMMA_API = "https://gamma-api.polymarket.com/markets"
CLOB_API  = "https://clob.polymarket.com/markets"
BASE_SLUG  = "btc-updown-5m"
ENV_FILE   = Path(__file__).parent.parent / ".env"


def get_current_slug() -> str:
    now = datetime.now(timezone.utc)
    aligned = (now.minute // 5) * 5
    market_time = now.replace(minute=aligned, second=0, microsecond=0)
    return f"{BASE_SLUG}-{int(market_time.timestamp())}"


def fetch_json(url: str) -> any:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def update_env(key: str, value: str) -> None:
    content = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    pattern = rf'^{re.escape(key)}=.*$'
    new_line = f'{key}="{value}"'
    if re.search(pattern, content, flags=re.MULTILINE):
        content = re.sub(pattern, new_line, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + f"\n{new_line}\n"
    ENV_FILE.write_text(content, encoding="utf-8")
    print(f"✅ .env 已更新：{key}={value[:50]}...")


def main():
    current_slug = get_current_slug()
    print(f"\n📅 当前时间窗口 slug: {current_slug}")
    print(f"🕐 UTC 时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Step 1: Gamma API 获取 conditionId
    params = urllib.parse.urlencode({"slug": current_slug, "active": "true", "limit": 5})
    url = f"{GAMMA_API}?{params}"
    print(f"🔍 Step 1 - Gamma API: {url}")
    markets = fetch_json(url)

    if not markets:
        print("❌ Gamma API 未找到市场")
        return

    market = markets[0]
    slug        = market.get("slug", "")
    title       = market.get("question", market.get("title", ""))
    condition_id = market.get("conditionId") or market.get("condition_id")

    print(f"   slug      : {slug}")
    print(f"   title     : {title}")
    print(f"   conditionId: {condition_id}\n")

    if not condition_id:
        print("❌ 未能获取 conditionId")
        return

    # Step 2: CLOB API 用 conditionId 获取 token IDs
    clob_url = f"{CLOB_API}/{condition_id}"
    print(f"🔍 Step 2 - CLOB API: {clob_url}")
    
    try:
        clob_data = fetch_json(clob_url)
    except Exception as e:
        print(f"❌ CLOB API 请求失败: {e}")
        return

    tokens = clob_data.get("tokens", [])
    print(f"   tokens: {json.dumps(tokens, indent=4)}\n")

    if not tokens:
        print("❌ CLOB API 返回的 tokens 为空")
        return

    # YES token 通常 outcome = "Yes"
    yes_token = next((t for t in tokens if t.get("outcome", "").lower() == "yes"), tokens[0])
    token_id = yes_token.get("token_id")

    print("=" * 60)
    print(f"✅ 找到市场：")
    print(f"   slug      : {slug}")
    print(f"   condition : {condition_id}")
    print(f"   YES token : {token_id}")
    print("=" * 60)

    update_env("TEST_MARKET_SLUG", slug)
    update_env("TEST_MARKET_ID",   token_id)

    print(f"\n✅ 已写入 .env，现在可以运行：")
    print(f"   python live/run_polymarket.py")


if __name__ == "__main__":
    main()