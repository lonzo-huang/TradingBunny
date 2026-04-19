#!/usr/bin/env python3
"""Comprehensive Grafana Live diagnostic script"""
import subprocess
import urllib.request
import urllib.error
import json
import os

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_USER = os.getenv("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")

def check_docker():
    """Check if Grafana container is running"""
    print("\n" + "="*60)
    print("1. Checking Docker Container Status")
    print("="*60)
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"],
            capture_output=True, text=True
        )
        print(result.stdout)
        if "polymarket-grafana" in result.stdout:
            print("✅ Grafana container is running")
            return True
        else:
            print("❌ Grafana container not found")
            return False
    except Exception as e:
        print(f"❌ Error checking docker: {e}")
        return False

def check_env():
    """Check environment variables"""
    print("\n" + "="*60)
    print("2. Checking Environment Variables")
    print("="*60)
    print(f"GRAFANA_URL: {GRAFANA_URL}")
    print(f"GRAFANA_USER: {GRAFANA_USER}")
    print(f"GRAFANA_PASSWORD: {'*' * len(GRAFANA_PASSWORD)}")
    
def test_api():
    """Test Grafana API with basic auth"""
    print("\n" + "="*60)
    print("3. Testing Grafana API Authentication")
    print("="*60)
    
    # Test 1: Basic auth to API
    url = f"{GRAFANA_URL}/api/org"
    import base64
    cred = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASSWORD}".encode()).decode()
    
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {cred}")
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            print(f"✅ API Auth Success: {data.get('name', 'Unknown Org')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ API Auth Failed: {e.code} - {e.reason}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_live_push():
    """Test Grafana Live Push"""
    print("\n" + "="*60)
    print("4. Testing Grafana Live Push")
    print("="*60)
    
    url = f"{GRAFANA_URL}/api/live/push/pde"
    import time
    import base64
    
    ts_ns = int(time.time() * 1e9)
    line = f"test value=42 {ts_ns}"
    data = line.encode("utf-8")
    
    cred = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASSWORD}".encode()).decode()
    
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "text/plain")
    req.add_header("Authorization", f"Basic {cred}")
    
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"✅ Live Push Success: HTTP {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ Live Push Failed: {e.code} - {e.reason}")
        print(f"   Response: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def suggest_fix():
    """Suggest fixes based on diagnosis"""
    print("\n" + "="*60)
    print("5. Suggested Fixes")
    print("="*60)
    print("""
If authentication is failing, try these steps in order:

Option 1: Reset Grafana completely (loses dashboards)
    cd monitoring
    docker-compose down -v
    docker-compose up -d grafana
    Wait 30 seconds, then:
    curl -X POST http://admin:520Wn1314@localhost:3000/api/user/password \
      -H "Content-Type: application/json" \
      -d '{"oldPassword": "admin", "newPassword": "520Wn1314"}'

Option 2: Use API Token (recommended)
    1. Open http://localhost:3000
    2. Login with current password
    3. Go to Administration > API Keys
    4. Create new key with Admin role
    5. Add to .env: GRAFANA_API_TOKEN=your-token-here

Option 3: Check docker-compose password
    Ensure docker-compose.yml has:
    GF_SECURITY_ADMIN_PASSWORD=520Wn1314
""")

if __name__ == "__main__":
    print("Grafana Live Diagnostics")
    check_docker()
    check_env()
    api_ok = test_api()
    live_ok = test_live_push()
    
    print("\n" + "="*60)
    print("Summary")
    print("="*60)
    if api_ok and live_ok:
        print("✅ All tests passed! Grafana Live should be working.")
    else:
        print("❌ Some tests failed. See suggestions below.")
        suggest_fix()
