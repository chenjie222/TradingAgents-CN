"""QMT HTTP Client Adapter

QMT 数据源 HTTP 客户端适配器，连接远程 QMT HTTP Server。
特点：
- 不依赖本地 xtquant（可部署在任意平台）
- 通过 HTTP API 访问 QMT 数据
- 需要配置 QMT_SERVER_URL 指向 QMT Server

配置示例：
```python
QMT_SERVER_URL = "http://192.168.1.100:8080"
QMT_SERVER_TIMEOUT = 30
QMT_SERVER_ENABLED = True
```
"""
import logging
from typing import Optional, Dict, List, Any
import pandas as pd
import requests
from datetime import datetime, timedelta

from .base import DataSourceAdapter
from tradingagents.config.providers_config import get_provider_config

logger = logging.getLogger(__name__)


class QMTAdapter(DataSourceAdapter):
    """QMT HTTP Client 适配器"""

    name = "qmt"
    _priority = 4

    def __init__(self):
        super().__init__()
        self._server_url: Optional[str] = None
        self._timeout: int = 30
        self._enabled: bool = False
        self._session = requests.Session()
        self._initialized = False
        self._available = False

        self._initialize()

    def _initialize(self):
        """初始化适配器"""
        if self._initialized:
            return

        try:
            # 从配置读取
            config = get_provider_config("qmt")
            self._server_url = config.get("server_url", "")
            self._timeout = config.get("timeout", 30)
            self._enabled = config.get("enabled", False)

            if not self._enabled:
                logger.info("QMT HTTP Client 未启用")
                self._initialized = True
                return

            if not self._server_url:
                logger.warning("⚠️ QMT_SERVER_URL 未配置")
                self._initialized = True
                return

            # 测试连接
            if self._check_health():
                self._available = True
                logger.info(f"✅ QMT HTTP Client 初始化成功: {self._server_url}")
            else:
                self._available = False
                logger.warning(f"⚠️ QMT Server 不可达: {self._server_url}")

        except Exception as e:
            logger.warning(f"⚠️ QMT HTTP Client 初始化失败: {e}")
            self._available = False

        self._initialized = True

    def _request(self, method: str, path: str, **kwargs) -> Optional[Dict]:
        """发送 HTTP 请求到 QMT Server"""
        if not self._server_url:
            return None

        url = f"{self._server_url}/api/v1{path}"
        try:
            response = self._session.request(
                method=method,
                url=url,
                timeout=self._timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.debug(f"QMT Server request failed: {e}")
            return None

    def _check_health(self) -> bool:
        """检查 QMT Server 健康状态"""
        try:
            result = self._request("GET", "/system/health")
            if result and result.get("success"):
                return result.get("data", {}).get("qmtConnected", False)
            return False
        except Exception:
            return False

    def _get_default_priority(self) -> int:
        """默认优先级：4（最高）"""
        return self._priority

    def is_available(self) -> bool:
        """检查 QMT Server 是否可用"""
        if not self._initialized:
            self._initialize()

        if not self._enabled or not self._server_url:
            return False

        # 如果之前检测失败，尝试重新检测
        if not self._available:
            self._available = self._check_health()
            if self._available:
                logger.info("✅ QMT Server 已恢复连接")

        return self._available

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """获取股票列表"""
        if not self.is_available():
            return None

        try:
            result = self._request("GET", "/market/stock-list?sync=false")
            if result and result.get("success"):
                stocks = result.get("data", {}).get("stocks", [])
                if stocks:
                    df = pd.DataFrame(stocks)
                    logger.info(f"✅ QMT 获取到 {len(df)} 只股票")
                    return df
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取股票列表失败: {e}")
            return None

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """QMT 不提供 PE/PB/市值 数据"""
        logger.info("QMT 不提供 daily_basic（PE/PB/市值）数据")
        return None

    def get_realtime_quotes(self) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """获取全市场实时行情"""
        if not self.is_available():
            return None

        try:
            result = self._request("GET", "/market/quote?codes=all")
            if result and result.get("success"):
                quotes = result.get("data", {}).get("quotes", [])
                if quotes:
                    # 转换为标准格式
                    result_dict = {}
                    for q in quotes:
                        code = q.get("code")
                        if code:
                            result_dict[code] = {
                                "close": q.get("close"),
                                "change_pct": q.get("changePct"),
                                "volume": q.get("volume"),
                                "amount": q.get("amount")
                            }
                    logger.info(f"✅ QMT 获取到 {len(result_dict)} 只股票的实时行情")
                    return result_dict
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取实时行情失败: {e}")
            return None

    def get_kline(
        self,
        code: str,
        period: str = "day",
        limit: int = 120,
        adj: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """获取 K 线数据"""
        if not self.is_available():
            return None

        try:
            # 映射周期名称
            period_map = {
                "day": "1d", "daily": "1d", "1d": "1d",
                "week": "1w", "1w": "1w",
                "month": "1mon", "1mon": "1mon",
                "5m": "5m", "15m": "15m", "30m": "30m", "60m": "1h", "1h": "1h",
            }
            qmt_period = period_map.get(period, "1d")

            result = self._request("GET", f"/market/kline/{code}?period={qmt_period}&count={limit}")
            if result and result.get("success"):
                klines = result.get("data", {}).get("kline", [])
                if klines:
                    # 转换字段名
                    items = []
                    for k in klines:
                        items.append({
                            "time": k.get("date", ""),
                            "open": k.get("open"),
                            "high": k.get("high"),
                            "low": k.get("low"),
                            "close": k.get("close"),
                            "volume": k.get("volume"),
                            "amount": k.get("amount"),
                        })
                    logger.info(f"✅ QMT 获取 {code} {period} K线 {len(items)} 条")
                    return items
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取 K 线失败 {code}: {e}")
            return None

    def get_news(
        self,
        code: str,
        days: int = 2,
        limit: int = 50,
        include_announcements: bool = True
    ) -> Optional[List[Dict]]:
        """QMT 不提供新闻/公告数据"""
        logger.info("QMT 不提供新闻/公告数据")
        return None

    def find_latest_trade_date(self) -> Optional[str]:
        """查找最新交易日期"""
        if not self.is_available():
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            return yesterday

        try:
            result = self._request("GET", "/market/quote/000001")
            if result and result.get("success"):
                data = result.get("data", {})
                # 获取数据中的日期
                trade_date = datetime.now().strftime("%Y%m%d")
                return trade_date

            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            return yesterday
        except Exception as e:
            logger.warning(f"⚠️ QMT 查找最新交易日失败: {e}")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            return yesterday

    def get_full_tick(self, code: str) -> Optional[Dict]:
        """获取五档盘口数据"""
        if not self.is_available():
            return None

        try:
            result = self._request("GET", f"/market/tick/{code}")
            if result and result.get("success"):
                data = result.get("data", {})
                if data:
                    logger.info(f"✅ QMT 获取 {code} 五档盘口")
                    return data
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取盘口失败 {code}: {e}")
            return None

    def get_financial_data(self, code: str, limit: int = 4) -> Optional[Dict]:
        """获取财务数据"""
        if not self.is_available():
            return None

        try:
            result = self._request("GET", f"/market/finance/{code}?limit={limit}")
            if result and result.get("success"):
                data = result.get("data", {})
                if data:
                    logger.info(f"✅ QMT 获取 {code} 财务数据")
                    return data
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取财务数据失败 {code}: {e}")
            return None

    # ============== Trading Methods (for TradingAgents-CN internal use) ==============

    def get_asset(self) -> Optional[Dict]:
        """获取账户资产"""
        if not self.is_available():
            return None

        try:
            result = self._request("GET", "/account/asset")
            if result and result.get("success"):
                return result.get("data")
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取账户资产失败: {e}")
            return None

    def get_positions(self, code: Optional[str] = None) -> List[Dict]:
        """获取持仓"""
        if not self.is_available():
            return []

        try:
            path = f"/account/positions?code={code}" if code else "/account/positions"
            result = self._request("GET", path)
            if result and result.get("success"):
                return result.get("data", {}).get("positions", [])
            return []
        except Exception as e:
            logger.error(f"❌ QMT 获取持仓失败: {e}")
            return []

    def get_orders(self, cancelable_only: bool = False) -> List[Dict]:
        """获取委托"""
        if not self.is_available():
            return []

        try:
            path = f"/account/orders?cancelable_only={cancelable_only}"
            result = self._request("GET", path)
            if result and result.get("success"):
                return result.get("data", {}).get("orders", [])
            return []
        except Exception as e:
            logger.error(f"❌ QMT 获取委托失败: {e}")
            return []

    def get_trades(self) -> List[Dict]:
        """获取成交"""
        if not self.is_available():
            return []

        try:
            result = self._request("GET", "/account/trades")
            if result and result.get("success"):
                return result.get("data", {}).get("trades", [])
            return []
        except Exception as e:
            logger.error(f"❌ QMT 获取成交失败: {e}")
            return []

    def buy(self, code: str, volume: int, price_type: str = "FIX",
            price: Optional[float] = None) -> Optional[Dict]:
        """买入下单"""
        if not self.is_available():
            return None

        try:
            payload = {
                "code": code,
                "volume": volume,
                "priceType": price_type,
                "price": price,
                "confirm": True
            }
            result = self._request("POST", "/trade/buy", json=payload)
            if result and result.get("success"):
                return result.get("data")
            return None
        except Exception as e:
            logger.error(f"❌ QMT 买入下单失败: {e}")
            return None

    def sell(self, code: str, volume: int, price_type: str = "FIX",
             price: Optional[float] = None) -> Optional[Dict]:
        """卖出下单"""
        if not self.is_available():
            return None

        try:
            payload = {
                "code": code,
                "volume": volume,
                "priceType": price_type,
                "price": price,
                "confirm": True
            }
            result = self._request("POST", "/trade/sell", json=payload)
            if result and result.get("success"):
                return result.get("data")
            return None
        except Exception as e:
            logger.error(f"❌ QMT 卖出下单失败: {e}")
            return None

    def cancel(self, order_id: int) -> Optional[Dict]:
        """撤单"""
        if not self.is_available():
            return None

        try:
            payload = {
                "orderId": order_id,
                "confirm": True
            }
            result = self._request("POST", "/trade/cancel", json=payload)
            if result and result.get("success"):
                return result.get("data")
            return None
        except Exception as e:
            logger.error(f"❌ QMT 撤单失败: {e}")
            return None
