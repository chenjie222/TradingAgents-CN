"""QMT Server 集成测试 (无颜色版本)

测试真实运行的 QMT Server API
"""
import requests
import sys
from datetime import datetime

# QMT Server 地址
BASE_URL = "http://localhost:8080"
API_URL = f"{BASE_URL}/api/v1"


def test_endpoint(name, method, path, expected_status=None, **kwargs):
    """测试单个接口"""
    url = f"{API_URL}{path}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=30, **kwargs)
        elif method == "POST":
            response = requests.post(url, timeout=30, **kwargs)
        else:
            print(f"[FAIL] {name}: 不支持的HTTP方法 {method}")
            return None

        if expected_status and response.status_code != expected_status:
            print(f"[FAIL] {name}: HTTP {response.status_code} (期望 {expected_status})")
            return None

        try:
            data = response.json()
            if data.get("success"):
                print(f"[PASS] {name}: HTTP {response.status_code}, success=True")
                return data
            else:
                error = data.get("error", {}).get("message", "Unknown error")
                print(f"[WARN] {name}: success=False, error={error}")
                return data
        except:
            print(f"[PASS] {name}: HTTP {response.status_code} (无JSON响应)")
            return {"status_code": response.status_code, "text": response.text}

    except requests.exceptions.ConnectionError:
        print(f"[FAIL] {name}: 连接失败，请确认QMT Server已启动在 {BASE_URL}")
        return None
    except requests.exceptions.Timeout:
        print(f"[FAIL] {name}: 请求超时")
        return None
    except Exception as e:
        print(f"[FAIL] {name}: 异常 - {e}")
        return None


def test_system_endpoints():
    """测试系统接口"""
    print("\n=== 系统接口测试 ===")

    # 1. 健康检查
    data = test_endpoint("健康检查", "GET", "/system/health")
    if data and data.get("data"):
        status = data["data"].get("status")
        qmt_connected = data["data"].get("qmtConnected")
        print(f"  状态: {status}, QMT连接: {qmt_connected}")

    # 2. 环境诊断
    data = test_endpoint("环境诊断", "GET", "/system/doctor")
    if data and data.get("data"):
        checks = data["data"].get("checks", [])
        for check in checks:
            status = "OK" if check.get("ok") else "FAIL"
            name = check.get('name', '')
            detail = check.get('detail', '')
            try:
                print(f"  [{status}] {name}: {detail}")
            except:
                print(f"  [{status}] {name}: (detail)")

    # 3. 服务状态
    data = test_endpoint("服务状态", "GET", "/system/status")
    if data and data.get("data"):
        version = data["data"].get("version")
        uptime = data["data"].get("uptime")
        print(f"  版本: {version}, 运行时间: {uptime}")


def test_market_endpoints():
    """测试行情接口"""
    print("\n=== 行情接口测试 ===")

    # 1. 单只行情
    data = test_endpoint("平安银行行情", "GET", "/market/quote/000001")
    if data and data.get("data"):
        quote = data["data"]
        print(f"  代码: {quote.get('code')}, 名称: {quote.get('name')}")
        print(f"  最新价: {quote.get('close')}, 涨跌: {quote.get('changePct')}%")

    # 2. 批量行情
    data = test_endpoint("批量行情(3只)", "GET", "/market/quote?codes=000001,600519,300750")
    if data and data.get("data"):
        quotes = data["data"].get("quotes", [])
        print(f"  获取到 {len(quotes)} 只股票行情")
        for q in quotes[:3]:
            print(f"    {q.get('code')}: {q.get('close')}")

    # 3. 五档盘口
    data = test_endpoint("平安银行盘口", "GET", "/market/tick/000001")
    if data and data.get("data"):
        tick = data["data"]
        bid = tick.get("bidPrice", [])
        ask = tick.get("askPrice", [])
        print(f"  买一: {bid[0] if bid else 'N/A'}, 卖一: {ask[0] if ask else 'N/A'}")

    # 4. K线数据
    data = test_endpoint("平安银行日K", "GET", "/market/kline/000001?period=1d&count=5")
    if data and data.get("data"):
        klines = data["data"].get("kline", [])
        print(f"  获取到 {len(klines)} 条K线")
        for k in klines[:2]:
            print(f"    {k.get('date')}: 开{k.get('open')}, 收{k.get('close')}")

    # 5. 股票列表
    data = test_endpoint("股票列表(前5只)", "GET", "/market/stock-list?sync=false&limit=5")
    if data and data.get("data"):
        stocks = data["data"].get("stocks", [])
        total = data["data"].get("total")
        print(f"  总数: {total}, 返回: {len(stocks)}")
        for s in stocks[:3]:
            print(f"    {s.get('code')}: {s.get('name')}")

    # 6. 板块列表
    data = test_endpoint("板块列表", "GET", "/market/blocks?limit=5")
    if data and data.get("data"):
        blocks = data["data"].get("blocks", [])
        print(f"  获取到 {len(blocks)} 个板块")
        for b in blocks[:3]:
            print(f"    {b}")

    # 7. 大盘概览
    data = test_endpoint("大盘概览", "GET", "/market/market-overview")
    if data and data.get("data"):
        indexes = data["data"].get("indexes", [])
        print(f"  获取到 {len(indexes)} 个指数")
        for idx in indexes:
            print(f"    {idx.get('name')}: {idx.get('close')} ({idx.get('changePct')}%)")


def test_account_endpoints():
    """测试账户接口（需要配置账号）"""
    print("\n=== 账户接口测试 ===")

    # 1. 账户资产
    data = test_endpoint("账户资产", "GET", "/account/asset")
    if data and data.get("success") and data.get("data"):
        asset = data["data"]
        print(f"  总资产: {asset.get('totalAsset')}")
        print(f"  可用资金: {asset.get('cash')}")
        print(f"  持仓市值: {asset.get('marketValue')}")

    # 2. 持仓
    data = test_endpoint("持仓查询", "GET", "/account/positions")
    if data and data.get("success") and data.get("data"):
        positions = data["data"].get("positions", [])
        print(f"  持仓数量: {len(positions)}")
        for pos in positions[:3]:
            print(f"    {pos.get('code')}: {pos.get('volume')}股")

    # 3. 今日委托
    data = test_endpoint("今日委托", "GET", "/account/orders")
    if data and data.get("success") and data.get("data"):
        orders = data["data"].get("orders", [])
        print(f"  委托数量: {len(orders)}")

    # 4. 今日成交
    data = test_endpoint("今日成交", "GET", "/account/trades")
    if data and data.get("success") and data.get("data"):
        trades = data["data"].get("trades", [])
        print(f"  成交数量: {len(trades)}")


def test_trade_endpoints():
    """测试交易接口（预演模式，不下单）"""
    print("\n=== 交易接口测试（预演模式） ===")

    # 1. 买入预演
    data = test_endpoint(
        "买入预演",
        "POST",
        "/trade/buy",
        json={
            "code": "000001",
            "volume": 1000,
            "priceType": "FIX",
            "price": 10.50,
            "confirm": False
        }
    )
    if data and data.get("data"):
        result = data["data"]
        if result.get("dryRun"):
            print(f"  预演金额: {result.get('estimatedAmount')}")

    # 2. 卖出预演
    data = test_endpoint(
        "卖出预演",
        "POST",
        "/trade/sell",
        json={
            "code": "000001",
            "volume": 500,
            "priceType": "LATEST",
            "confirm": False
        }
    )
    if data and data.get("data"):
        result = data["data"]
        if result.get("dryRun"):
            print(f"  预演金额: {result.get('estimatedAmount')}")


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print(f"QMT Server 集成测试")
    print(f"目标地址: {BASE_URL}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        test_system_endpoints()
        test_market_endpoints()
        test_account_endpoints()
        test_trade_endpoints()

        print("\n" + "=" * 50)
        print("测试完成！")
        print("=" * 50)

    except KeyboardInterrupt:
        print("\n测试被中断")
    except Exception as e:
        print(f"[FAIL] 测试异常: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 检查是否指定了URL
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
        API_URL = f"{BASE_URL}/api/v1"

    run_all_tests()
