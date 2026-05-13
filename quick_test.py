"""快速测试 QMT Server 接口"""
import requests

BASE_URL = "http://localhost:8080/api/v1"

print("=" * 60)
print("QMT Server 快速接口验证")
print("=" * 60)

# 1. Health Check
try:
    resp = requests.get(f"{BASE_URL}/system/health", timeout=10)
    data = resp.json()
    print(f"[OK] 健康检查: status={data['data']['status']}, qmtConnected={data['data']['qmtConnected']}")
except Exception as e:
    print(f"[FAIL] 健康检查: {e}")

# 2. System Status
try:
    resp = requests.get(f"{BASE_URL}/system/status", timeout=10)
    data = resp.json()
    print(f"[OK] 系统状态: version={data['data']['version']}")
except Exception as e:
    print(f"[FAIL] 系统状态: {e}")

# 3. Quote
try:
    resp = requests.get(f"{BASE_URL}/market/quote/000001", timeout=10)
    data = resp.json()
    if data["success"] and data["data"]:
        print(f"[OK] 行情查询: code={data['data']['code']}, close={data['data']['close']}")
    else:
        print(f"[FAIL] 行情查询: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 行情查询: {e}")

# 4. Account Asset
try:
    resp = requests.get(f"{BASE_URL}/account/asset", timeout=10)
    data = resp.json()
    if data["success"] and data["data"]:
        print(f"[OK] 账户资产: cash={data['data']['cash']:,.2f}, total={data['data']['totalAsset']:,.2f}")
    else:
        print(f"[FAIL] 账户资产: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 账户资产: {e}")

# 5. Positions
try:
    resp = requests.get(f"{BASE_URL}/account/positions", timeout=10)
    data = resp.json()
    if data["success"]:
        positions = data["data"].get("positions", [])
        print(f"[OK] 持仓查询: 持仓数量={len(positions)}")
    else:
        print(f"[FAIL] 持仓查询: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 持仓查询: {e}")

# 6. Orders
try:
    resp = requests.get(f"{BASE_URL}/account/orders", timeout=10)
    data = resp.json()
    if data["success"]:
        orders = data["data"].get("orders", [])
        print(f"[OK] 委托查询: 委托数量={len(orders)}")
    else:
        print(f"[FAIL] 委托查询: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 委托查询: {e}")

# 7. Trades
try:
    resp = requests.get(f"{BASE_URL}/account/trades", timeout=10)
    data = resp.json()
    if data["success"]:
        trades = data["data"].get("trades", [])
        print(f"[OK] 成交查询: 成交数量={len(trades)}")
    else:
        print(f"[FAIL] 成交查询: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 成交查询: {e}")

print("=" * 60)
print("测试完成！")
print("=" * 60)
