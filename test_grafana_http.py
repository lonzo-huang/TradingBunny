#!/usr/bin/env python3
"""
Test script for Grafana Live HTTP Push (/api/live/publish/<channel>).
Uses JSON format with Bearer token authentication.
"""
import urllib.request
import json
import time
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_API_TOKEN = os.getenv("GRAFANA_API_TOKEN", "")

def push_to_channel(channel: str, data: dict) -> bool:
    """Push data to Grafana Live via HTTP Publish API"""
    # Format: /api/live/publish/<channel>
    url = f"{GRAFANA_URL}/api/live/publish/{channel}"
    
    payload = {
        "data": data,
        "timestamp": time.time()
    }
    
    body = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    
    if GRAFANA_API_TOKEN:
        req.add_header("Authorization", f"Bearer {GRAFANA_API_TOKEN}")
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✅ {channel}: HTTP {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ {channel}: HTTP {e.code} - {e.reason}")
        try:
            error_body = e.read().decode()
            print(f"   Response: {error_body[:200]}")
        except:
            pass
        return False
    except Exception as e:
        print(f"❌ {channel}: Error - {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Grafana Live HTTP Push Test")
    print("="*60)
    print(f"Grafana URL: {GRAFANA_URL}")
    print(f"API Token: {'***' if GRAFANA_API_TOKEN else 'NOT SET'}")
    print("-"*60)
    
    # Test data
    tests = [
        ("stream/pde/btc", {"price": 70000.50, "move_bps": 15.3}),
        ("stream/pde/poly", {"bid": 0.52, "ask": 0.54, "mid": 0.53}),
        ("stream/pde/latency", {"gap_ms": 45}),
    ]
    
    success_count = 0
    for channel, data in tests:
        if push_to_channel(channel, data):
            success_count += 1
        time.sleep(0.1)
    
    print("-"*60)
    if success_count == len(tests):
        print("✅ All pushes successful! Check Grafana dashboard at:")
        print(f"   {GRAFANA_URL}/d/pde-live")
    else:
        print(f"❌ {len(tests) - success_count}/{len(tests)} pushes failed")
        print("   Check:")
        print("   1. GF_LIVE_ENABLED=true in docker-compose")
        print("   2. GF_LIVE_ALLOWED_CHANNEL_PREFIXES=stream/pde")
        print("   3. GRAFANA_API_TOKEN is valid")
