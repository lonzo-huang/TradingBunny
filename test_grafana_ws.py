#!/usr/bin/env python3
"""
Test script for Grafana Live WebSocket (official method).
"""
import asyncio
import json
import time
import os
import websockets

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, assume env vars are set manually

GRAFANA_WS_URL = os.getenv("GRAFANA_WS_URL", "ws://localhost:3000/api/live/ws")
GRAFANA_API_TOKEN = os.getenv("GRAFANA_API_TOKEN", "")

async def test_ws():
    headers = {}
    if GRAFANA_API_TOKEN:
        headers["Authorization"] = f"Bearer {GRAFANA_API_TOKEN}"
    
    print(f"🔌 Connecting to {GRAFANA_WS_URL}...")
    
    try:
        async with websockets.connect(GRAFANA_WS_URL, additional_headers=headers) as ws:
            print("✅ Connected to Grafana Live WebSocket!")
            
            # 1. Send connect command
            connect_payload = {
                "id": 1,
                "method": "connect",
                "params": {}
            }
            await ws.send(json.dumps(connect_payload))
            print("📡 Sent connect command")
            await asyncio.sleep(0.2)
            
            # 2. Subscribe to channels
            channels = ["stream/pde/btc", "stream/pde/poly", "stream/pde/latency"]
            
            for msg_id, channel in enumerate(channels, 2):
                sub_payload = {
                    "id": msg_id,
                    "method": "subscribe",
                    "params": {"channel": channel}
                }
                await ws.send(json.dumps(sub_payload))
                print(f"📋 Subscribed to {channel}")
                await asyncio.sleep(0.1)
            
            # 2. Publish test data
            test_data = [
                ("stream/pde/btc", {"price": 70000.50, "move_bps": 15.3}),
                ("stream/pde/poly", {"bid": 0.52, "ask": 0.54, "mid": 0.53}),
                ("stream/pde/latency", {"gap_ms": 45}),
            ]
            
            msg_id = 10
            for channel, data in test_data:
                pub_payload = {
                    "id": msg_id,
                    "method": "publish",
                    "params": {
                        "channel": channel,
                        "data": {
                            **data,
                            "timestamp": time.time()
                        }
                    }
                }
                await ws.send(json.dumps(pub_payload))
                print(f"📡 Published to {channel}: {data}")
                msg_id += 1
                await asyncio.sleep(0.1)
            
            print("✅ All pushes complete! Check Grafana dashboard at:")
            print("   http://localhost:3000/d/pde-live")
            await asyncio.sleep(2)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"   Type: {type(e).__name__}")
        if "401" in str(e):
            print("   💡 Hint: API Token is invalid or missing")
        elif "403" in str(e):
            print("   💡 Hint: Channel prefix not allowed in GF_LIVE_ALLOWED_CHANNEL_PREFIXES")
        elif "Connection refused" in str(e):
            print("   💡 Hint: Grafana is not running or wrong port")

if __name__ == "__main__":
    print("="*60)
    print("Grafana Live WebSocket Test (OFFICIAL)")
    print("="*60)
    print(f"WS URL: {GRAFANA_WS_URL}")
    print(f"API Token: {'***' if GRAFANA_API_TOKEN else 'NOT SET'}")
    print("-"*60)
    
    asyncio.run(test_ws())
