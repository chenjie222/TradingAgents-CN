"""测试慢速接口（需要更长超时时间）"""
import requests

BASE_URL = "http://localhost:8080/api/v1"

print("=" * 60)
print("慢速接口测试（超时60秒）")
print("=" * 60)

# 1. Kline Data with longer timeout
try:
    resp = requests.get(f"{BASE_URL}/market/kline/000001?period=1d&count=5", timeout=30)
    data = resp.json()
    if data["success"] and data["data"] and data["data"].get("kline"):
        klines = data["data"]["kline"]
        print(f"[OK] K线数据: 获取到 {len(klines)} 条K线")
        if klines:
            print(f"     最新K线: {klines[-1]}")
    else:
        print(f"[FAIL] K线数据: {data.get('message', 'No data')}")
except Exception as e:
    print(f"[FAIL] K线数据: {e}")

# 2. Tick Data (should be fast)
try:
    resp = requests.get(f"{BASE_URL}/market/tick/000001", timeout=10)
    data = resp.json()
    if data["success"] and data["data"]:
        tick = data["data"]
        print(f"[OK] 五档盘口: lastPrice={tick['lastPrice']}")
    else:
        print(f"[FAIL] 五档盘口: {data.get('message', 'No data')}")
except Exception as e:
    print(f"[FAIL] 五档盘口: {e}")

# 3. Stock List with longer timeout
try:
    print("\n[Testing] 股票列表（可能需要较长时间下载板块数据）...")
    resp = requests.get(f"{BASE_URL}/market/stock-list?sync=false&limit=5", timeout=60)
    data = resp.json()
    if data["success"] and data["data"]:
        stocks = data["data"].get("stocks", [])
        print(f"[OK] 股票列表: 获取到 {len(stocks)} 只股票")
        for s in stocks[:3]:
            print(f"     - {s.get('code')}: {s.get('name', 'N/A')}")
    else:
        print(f"[FAIL] 股票列表: {data.get('message', 'No data')}")
except Exception as e:
    print(f"[FAIL] 股票列表: {e}")

# 4. Market Overview
try:
    resp = requests.get(f"{BASE_URL}/market/market-overview", timeout=30)
    data = resp.json()
    if data["success"] and data["data"]:
        indexes = data["data"].get("indexes", [])
        print(f"[OK] 大盘指数: 获取到 {len(indexes)} 个指数")
    else:
        print(f"[FAIL] 大盘指数: {data.get('message', 'No data')}")
except Exception as e:
    print(f"[FAIL] 大盘指数: {e}")

# 5. Trade Buy (Dry Run)
print("\n" + "=" * 60)
print("交易接口测试（预演模式）")
print("=" * 60)

try:
    resp = requests.post(f"{BASE_URL}/trade/buy", json={
        "code": "603099",
        "volume": 100,
        "price_type": "FIX",
        "price": 25.0,
        "strategy_name": "Test",
        "order_remark": "测试买入",
        "confirm": False
    }, timeout=15)
    data = resp.json()
    if data["success"]:
        result = data["data"]
        print(f"[OK] 买入预演: dryRun={result.get('dryRun')}, code={result.get('code')}")
    else:
        print(f"[FAIL] 买入预演: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 买入预演: {e}")

# 6. Trade Sell (Dry Run)
try:
    resp = requests.post(f"{BASE_URL}/trade/sell", json={
        "code": "603099",
        "volume": 100,
        "price_type": "FIX",
        "price": 25.0,
        "strategy_name": "Test",
        "order_remark": "测试卖出",
        "confirm": False
    }, timeout=15)
    data = resp.json()
    if data["success"]:
        result = data["data"]
        print(f"[OK] 卖出预演: dryRun={result.get('dryRun')}, code={result.get('code')}")
    else:
        print(f"[FAIL] 卖出预演: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 卖出预演: {e}")

# 7. Cancel (Dry Run)
try:
    resp = requests.post(f"{BASE_URL}/trade/cancel", json={
        "order_id": 123456,
        "confirm": False
    }, timeout=15)
    data = resp.json()
    if data["success"]:
        result = data["data"]
        print(f"[OK] 撤单预演: dryRun={result.get('dryRun')}, orderId={result.get('orderId')}")
    else:
        print(f"[FAIL] 撤单预演: {data.get('message', 'Unknown error')}")
except Exception as e:
    print(f"[FAIL] 撤单预演: {e}")

print("\n" + "=" * 60)
print("测试完成！")
print("=" * 60)
