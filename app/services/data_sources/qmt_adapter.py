"""
QMT data source adapter

QMT 是本地量化交易终端，通过 xtquant Python 库提供数据。
特点：
- 需要本地 QMT 终端运行（Windows only）
- 提供高质量实时行情（直连交易所）
- 提供五档盘口数据（独有）
- 不提供 PE/PB/市值 等估值数据
- 不提供新闻/公告数据
"""
import sys
from typing import Optional, Dict, List
import logging
from datetime import datetime, timedelta
import pandas as pd

from .base import DataSourceAdapter

logger = logging.getLogger(__name__)

# QMT Provider 单例（延迟加载）
_qmt_provider = None


def _get_qmt_provider():
    """获取 QMT Provider 单例"""
    global _qmt_provider
    if _qmt_provider is None:
        try:
            from tradingagents.dataflows.providers.china.qmt import get_qmt_provider
            _qmt_provider = get_qmt_provider()
        except ImportError:
            logger.warning("⚠️ QMT Provider 导入失败")
            _qmt_provider = None
    return _qmt_provider


class QMTAdapter(DataSourceAdapter):
    """QMT 数据源适配器"""

    def __init__(self):
        super().__init__()
        self._provider = None
        self._initialized = False
        self._available = False
        self._initialize()

    def _initialize(self):
        """初始化适配器"""
        if self._initialized:
            return

        try:
            # 检查配置是否启用
            from tradingagents.config.providers_config import get_provider_config
            config = get_provider_config("qmt")
            if not config.get("enabled", False):
                logger.info("QMT 数据源未启用（QMT_ENABLED=False）")
                self._available = False
                self._initialized = True
                return

            # 检查平台
            if sys.platform != "win32":
                logger.info("QMT 仅支持 Windows 平台")
                self._available = False
                self._initialized = True
                return

            # 尝试获取 Provider
            self._provider = _get_qmt_provider()
            if self._provider is None:
                logger.warning("⚠️ QMT Provider 不可用")
                self._available = False
                self._initialized = True
                return

            # 尝试连接测试
            try:
                if self._provider.connect_sync():
                    self._available = True
                    logger.info("✅ QMT Adapter 初始化成功")
                else:
                    self._available = False
                    logger.info("⚠️ QMT 终端未运行")
            except Exception as e:
                logger.warning(f"⚠️ QMT 连接测试失败: {e}")
                self._available = False

        except Exception as e:
            logger.warning(f"⚠️ QMT Adapter 初始化失败: {e}")
            self._available = False

        self._initialized = True

    @property
    def name(self) -> str:
        return "qmt"

    def _get_default_priority(self) -> int:
        """
        默认优先级：4（最高）

        QMT 可用时优先使用，因为：
        - 本地直连交易所，数据质量最高
        - 无 API 限流
        - 实时行情响应快
        """
        return 4

    def is_available(self) -> bool:
        """
        检查 QMT 是否可用

        条件：
        1. QMT_ENABLED 配置为 True
        2. Windows 平台
        3. xtquant 可导入
        4. QMT 终端正在运行
        """
        if not self._initialized:
            self._initialize()

        # 如果之前检测为不可用，尝试重新检测（QMT 可能后来启动了）
        if not self._available and self._provider is not None:
            try:
                if self._provider.connect_sync():
                    self._available = True
                    logger.info("✅ QMT 终端已启动")
            except Exception:
                pass

        return self._available

    def get_stock_list(self) -> Optional[pd.DataFrame]:
        """
        获取股票列表

        QMT 通过板块遍历获取股票列表：
        1. 先 download_sector_data 同步板块数据
        2. 遍历 get_sector_list 获取板块
        3. 对每个板块调用 get_stock_list_in_sector
        4. 去重合并
        """
        if not self.is_available():
            return None

        try:
            import asyncio

            # 同步包装异步调用
            stocks = self._provider._get_stock_list_sync()

            if stocks:
                df = pd.DataFrame(stocks)
                logger.info(f"✅ QMT 获取到 {len(df)} 只股票")
                return df

            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取股票列表失败: {e}")
            return None

    def get_daily_basic(self, trade_date: str) -> Optional[pd.DataFrame]:
        """
        QMT 不提供 PE/PB/市值 等估值数据

        Returns:
            None - QMT 无此数据，DataSourceManager 会自动回退到其他数据源
        """
        logger.info("QMT 不提供 daily_basic（PE/PB/市值）数据")
        return None

    def get_realtime_quotes(self) -> Optional[Dict[str, Dict[str, Optional[float]]]]:
        """
        获取全市场实时行情

        QMT 的实时行情质量最高，直连交易所
        """
        if not self.is_available():
            return None

        try:
            # 使用 Provider 的批量获取方法
            quotes = self._provider.get_realtime_quotes_batch_sync()

            if quotes:
                logger.info(f"✅ QMT 获取到 {len(quotes)} 只股票的实时行情")
                return quotes

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
        """
        获取 K 线数据

        QMT 支持多周期：1m, 5m, 15m, 30m, 1h, 1d, 1w, 1mon

        Args:
            code: 6位股票代码
            period: 周期
            limit: 返回数量
            adj: 复权方式（QMT 不支持复权参数）
        """
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
            qmt_period = period_map.get(period, period)

            # 格式化代码
            qmt_code = self._provider._normalize_to_qmt_code(code)

            # 先下载历史数据（确保缓存）
            try:
                self._provider.xtdata.download_history_data(
                    qmt_code, period=qmt_period, start_time="", end_time=""
                )
            except Exception:
                pass

            # 获取 K 线数据
            kline = self._provider.xtdata.get_market_data_ex(
                field_list=["open", "high", "low", "close", "volume", "amount"],
                stock_list=[qmt_code],
                period=qmt_period,
                count=limit
            )

            if kline and qmt_code in kline:
                data = kline[qmt_code]
                if data and len(data.get("close", [])) > 0:
                    items = []
                    index_vals = list(data.index) if hasattr(data, "index") else []

                    for i in range(len(data["close"])):
                        item = {
                            "time": str(index_vals[i] if i < len(index_vals) else ""),
                            "open": self._provider._arr_at(data["open"], i),
                            "high": self._provider._arr_at(data["high"], i),
                            "low": self._provider._arr_at(data["low"], i),
                            "close": self._provider._arr_at(data["close"], i),
                            "volume": self._provider._arr_at(data["volume"], i),
                            "amount": self._provider._arr_at(data["amount"], i),
                        }
                        items.append(item)

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
        """
        QMT 不提供新闻/公告数据

        Returns:
            None - QMT 无此数据，DataSourceManager 会自动回退
        """
        logger.info("QMT 不提供新闻/公告数据")
        return None

    def find_latest_trade_date(self) -> Optional[str]:
        """
        查找最新交易日期

        通过获取上证指数的日K数据来确定最新交易日
        """
        if not self.is_available():
            # 回退到昨天
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            return yesterday

        try:
            trade_date = self._provider.find_latest_trade_date_sync()
            if trade_date:
                return trade_date

            # 回退到昨天
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            return yesterday
        except Exception as e:
            logger.warning(f"⚠️ QMT 查找最新交易日失败: {e}")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
            return yesterday

    def get_full_tick(self, code: str) -> Optional[Dict]:
        """
        获取五档盘口数据（QMT 独有功能）

        Args:
            code: 6位股票代码

        Returns:
            包含 bidPrice[5], askPrice[5], bidVol[5], askVol[5] 的字典
        """
        if not self.is_available():
            return None

        try:
            import asyncio
            tick = self._provider._get_full_tick_sync(code)
            if tick:
                logger.info(f"✅ QMT 获取 {code} 五档盘口")
                return tick
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取盘口失败 {code}: {e}")
            return None

    def get_financial_data(self, code: str, limit: int = 4) -> Optional[Dict]:
        """
        获取财务数据

        QMT 提供5张财务表：Income, Balance, CashFlow, Capital, PershareIndex
        """
        if not self.is_available():
            return None

        try:
            import asyncio
            fin = self._provider._get_financial_data_sync(code, limit)
            if fin:
                logger.info(f"✅ QMT 获取 {code} 财务数据")
                return fin
            return None
        except Exception as e:
            logger.error(f"❌ QMT 获取财务数据失败 {code}: {e}")
            return None