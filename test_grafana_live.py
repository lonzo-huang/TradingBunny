#!/usr/bin/env python3
"""
Test script to verify Grafana Live HTTP Push API is working.
Uses InfluxDB line protocol format.
"""
import urllib.request
import time
import os

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")
GRAFANA_API_TOKEN = os.getenv("GRAFANA_API_TOKEN", "")

def test_push():
    """Push test data to Grafana Live"""
    url = f"{GRAFANA_URL}/api/live/push/pde"
    
    # Build InfluxDB line protocol data
    # Format: measurement[,tag=value] field=value timestamp_ns
    ts_ns = int(time.time() * 1e9)
    line = f"btc price=70000.50 {ts_ns}"
    data = line.encode("utf-8")
    
    # Create request with API Token (preferred) or Basic Auth
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "text/plain")
    
    if GRAFANA_API_TOKEN:
        req.add_header("Authorization", f"Bearer {GRAFANA_API_TOKEN}")
    else:
        import base64
        cred = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASSWORD}".encode()).decode()
        req.add_header("Authorization", f"Basic {cred}")
    
    print(f"📡 Pushing to: {url}")
    print(f"📦 Data: {line}")
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✅ Response: {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error {e.code}: {e.reason}")
        print(f"   Response body: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Grafana Live HTTP Push Test")
    print("="*60)
    print(f"Grafana URL: {GRAFANA_URL}")
    print(f"Credentials: {GRAFANA_USER} / {'*'*len(GRAFANA_PASSWORD)}")
    print("-"*60)
    
    success = test_push()
    
    print("-"*60)
    if success:
        print("✅ Push successful! Check Grafana at:")
        print(f"   {GRAFANA_URL}/d/pde-live")
    else:
        print("❌ Push failed. Check:")
        print("   1. Grafana is running: docker ps")
        print("   2. Environment variables are set")
        print("   3. Channel prefix matches GF_LIVE_ALLOWED_CHANNEL_PREFIXES")
