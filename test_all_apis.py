"""
全面测试 QMT Server 所有接口
"""
import sys
import os

# Add xtquant path
xtquant_path = r"D:\software\54QMT\国金证券QMT交易端\bin.x64\Lib\site-packages"
if xtquant_path not in sys.path:
    sys.path.append(xtquant_path)

import requests
import json

BASE_URL = "http://localhost:8080/api/v1"

def test_api(method, path, desc, data=None):
    """测试 API"""
    print(f"\n{'='*60}")
    print(f"{desc}")
    print(f"{'='*60}")
    print(f"{method.upper()} {path}")

    try:
        url = f"{BASE_URL}{path}"
        if method.upper() == "GET":
            resp = requests.get(url, timeout=30)
        elif method.upper() == "POST":
            resp = requests.post(url, json=data, timeout=30)
        else:
            resp = requests.request(method, url, json=data, timeout=30)

        resp.raise_for_status()
        result = resp.json()

        if result.get("success"):
            print(f"[OK] 成功")
            return result.get("data")
        else:
            print(f"[FAIL] 失败: {result.get('message')}")
            return None
    except Exception as e:
        print(f"[FAIL] 错误: {e}")
        return None

print("=" * 60)
print("QMT Server 全面接口测试")
print("=" * 60)

# ========== 系统接口 ==========
print("\n" + "="*60)
print("【系统接口】")
print("="*60)

# 1. 健康检查
data = test_api("GET", "/system/health", "[1/15] 健康检查")
if data:
    print(f"   状态: {data.get('status')}")
    print(f"   QMT连接: {data.get('qmtConnected')}")

# 2. 系统信息
data = test_api("GET", "/system/status", "[2/15] 系统状态")
if data:
    print(f"   版本: {data.get('version')}")
    print(f"   运行时间: {data.get('uptime')}")

# ========== 行情接口 ==========
print("\n" + "="*60)
print("【行情接口】")
print("="*60)

# 3. 单只股票行情
data = test_api("GET", "/market/quote/000001", "[3/15] 获取行情 (000001)")
if data:
    print(f"   代码: {data.get('code')}")
    print(f"   名称: {data.get('name')}")
    print(f"   最新价: {data.get('close')}")
    print(f"   涨跌幅: {data.get('changePct')}%")

# 4. 批量行情
data = test_api("GET", "/market/quote?codes=000001,600519&names=true", "[4/15] 批量行情")
if data:
    quotes = data.get("quotes", [])
    print(f"   获取到 {len(quotes)} 只股票")
    for q in quotes[:2]:
        print(f"   - {q.get('code')}: {q.get('close')}")

# 5. K线数据
data = test_api("GET", "/market/kline/000001?period=1d&count=5", "[5/15] K线数据")
if data:
    klines = data.get("kline", [])
    print(f"   获取到 {len(klines)} 条K线")
    if klines:
        print(f"   最新K线: {klines[-1]}")

# 6. 五档盘口
data = test_api("GET", "/market/tick/000001", "[6/15] 五档盘口")
if data:
    print(f"   最新价: {data.get('lastPrice')}")
    print(f"   买五: {data.get('bidPrice', [])}")
    print(f"   卖五: {data.get('askPrice', [])}")

# 7. 股票列表
data = test_api("GET", "/market/stock-list?sync=false&limit=10", "[7/15] 股票列表")
if data:
    stocks = data.get("stocks", [])
    print(f"   获取到 {len(stocks)} 只股票")
    if stocks:
        print(f"   前3只: {[s.get('code') for s in stocks[:3]]}")

# 8. 板块列表
data = test_api("GET", "/market/blocks?limit=5", "[8/15] 板块列表")
if data:
    blocks = data.get("blocks", [])
    print(f"   获取到 {data.get('total')} 个板块")
    if blocks:
        print(f"   前5个: {blocks[:5]}")

# 9. 大盘指数
data = test_api("GET", "/market/market-overview", "[9/15] 大盘指数")
if data:
    indexes = data.get("indexes", [])
    print(f"   获取到 {len(indexes)} 个指数")
    for idx in indexes:
        print(f"   - {idx.get('name')}: {idx.get('close')} ({idx.get('changePct')}%)")

# ========== 账户接口 ==========
print("\n" + "="*60)
print("【账户接口】")
print("="*60)

# 10. 账户资产
data = test_api("GET", "/account/asset", "[10/15] 账户资产")
if data:
    print(f"   账户ID: {data.get('accountId')}")
    print(f"   现金: {data.get('cash'):,.2f}")
    print(f"   冻结资金: {data.get('frozenCash'):,.2f}")
    print(f"   市值: {data.get('marketValue'):,.2f}")
    print(f"   总资产: {data.get('totalAsset'):,.2f}")

# 11. 持仓
data = test_api("GET", "/account/positions", "[11/15] 持仓查询")
if data:
    positions = data.get("positions", [])
    print(f"   持仓数量: {len(positions)}")
    for pos in positions[:3]:
        print(f"   - {pos.get('code')}: {pos.get('volume')} 股")

# 12. 委托
data = test_api("GET", "/account/orders", "[12/15] 委托查询")
if data:
    orders = data.get("orders", [])
    print(f"   委托数量: {len(orders)}")
    for order in orders[:3]:
        print(f"   - 订单{order.get('orderId')}: {order.get('code')} {order.get('orderStatusName')}")

# 13. 成交
data = test_api("GET", "/account/trades", "[13/15] 成交查询")
if data:
    trades = data.get("trades", [])
    print(f"   成交数量: {len(trades)}")

# ========== 交易接口（预演模式） ==========
print("\n" + "="*60)
print("【交易接口（预演模式）】")
print("="*60)

# 14. 买入预演
data = test_api("POST", "/trade/buy", "[14/15] 买入预演", {
    "code": "603099",
    "volume": 100,
    "price_type": "FIX",
    "price": 25.00,
    "strategy_name": "Test",
    "order_remark": "测试买入",
    "confirm": False
})
if data:
    print(f"   预演模式: {data.get('dryRun')}")
    print(f"   股票: {data.get('code')}")
    print(f"   数量: {data.get('volume')}")
    print(f"   价格: {data.get('price')}")
    print(f"   备注: {data.get('note')}")

# 15. 撤单预演
data = test_api("POST", "/trade/cancel", "[15/15] 撤单预演", {
    "order_id": 123456,
    "confirm": False
})
if data:
    print(f"   预演模式: {data.get('dryRun')}")
    print(f"   订单ID: {data.get('orderId')}")
    print(f"   备注: {data.get('note')}")

print("\n" + "="*60)
print("测试完成！")
print("="*60)
