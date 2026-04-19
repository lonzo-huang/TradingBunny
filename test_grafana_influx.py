#!/usr/bin/env python3
"""
Test script for Grafana Live HTTP Push with InfluxDB line protocol.
Endpoint: /api/live/push/:streamId
"""
import urllib.request
import time
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_API_TOKEN = os.getenv("GRAFANA_API_TOKEN", "")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")

def push_influx(stream_id: str, measurement: str, fields: dict) -> bool:
    """Push InfluxDB line protocol data to Grafana Live"""
    url = f"{GRAFANA_URL}/api/live/push/{stream_id}"
    
    # Build InfluxDB line: measurement field=value timestamp_ns
    ts_ns = int(time.time() * 1e9)
    field_parts = ",".join([f"{k}={v}" for k, v in fields.items()])
    line = f"{measurement} {field_parts} {ts_ns}"
    data = line.encode("utf-8")
    
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "text/plain")
    
    # Use API Token if available, otherwise Basic Auth
    if GRAFANA_API_TOKEN:
        req.add_header("Authorization", f"Bearer {GRAFANA_API_TOKEN}")
    else:
        import base64
        cred = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASSWORD}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✅ {measurement}: HTTP {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ {measurement}: HTTP {e.code} - {e.reason}")
        try:
            print(f"   Response: {e.read().decode()[:200]}")
        except:
            pass
        return False
    except Exception as e:
        print(f"❌ {measurement}: Error - {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Grafana Live InfluxDB Push Test")
    print("="*60)
    print(f"Grafana URL: {GRAFANA_URL}")
    print(f"Auth: {'API Token' if GRAFANA_API_TOKEN else 'Basic Auth'}")
    print("-"*60)
    
    # Test with stream_id "pde" (not stream/pde)
    tests = [
        ("pde", "btc", {"price": 70000.50, "move_bps": 15.3}),
        ("pde", "poly", {"bid": 0.52, "ask": 0.54, "mid": 0.53}),
        ("pde", "latency", {"gap_ms": 45}),
    ]
    
    success_count = 0
    for stream_id, measurement, fields in tests:
        if push_influx(stream_id, measurement, fields):
            success_count += 1
        time.sleep(0.1)
    
    print("-"*60)
    if success_count == len(tests):
        print("✅ All pushes successful!")
        print(f"   Check Grafana at: {GRAFANA_URL}/d/pde-live")
        print("   (Note: dashboard channels should be 'pde/btc', not 'stream/pde/btc')")
    else:
        print(f"❌ {len(tests) - success_count}/{len(tests)} pushes failed")
