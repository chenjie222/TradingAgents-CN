"""
QMT数据提供器
封装 xtquant 库（QMT终端Python接口）
"""
import sys
import os
import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, date, timedelta
import pandas as pd
import asyncio
import math

from ..base_provider import BaseStockDataProvider
from tradingagents.config.providers_config import get_provider_config

logger = logging.getLogger(__name__)

# 模块级标志，防止重复注入 sys.path
_xtquant_path_injected = False
_xtquant_available = False
_xtdata = None
_xtconstant = None

# 周期映射：标准化名称 -> QMT内部名称
PERIOD_MAP = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "1d": "1d", "day": "1d", "daily": "1d",
    "1w": "1w", "week": "1w", "1mon": "1mon", "month": "1mon",
}

# 分块下载配置（避免单次下载超时）
CHUNK_DAYS = {
    "1m": 7, "5m": 30, "15m": 60, "30m": 90, "1h": 180,
    "1d": 730, "1w": 1825, "1mon": 3650,
}

# 板块最小数量阈值（小于50表示板块数据未同步）
_SECTOR_MIN_COUNT = 50


def _inject_xtquant_path() -> bool:
    """
    将 xtquant_path 追加到 sys.path（关键：append 而非 insert）

    QMT 的 site-packages 捆绑了老旧的 numpy 1.19.1 / pandas 0.22.0，
    如果 insert(0, ...) 会覆盖环境的新版本，引发兼容性问题。
    """
    global _xtquant_path_injected

    if _xtquant_path_injected:
        return True

    config = get_provider_config("qmt")
    xtquant_path = config.get("xtquant_path", "")

    if not xtquant_path:
        # 尝试从环境变量获取
        xtquant_path = os.getenv("QMT_XTQUANT_PATH", "")

    if not xtquant_path:
        logger.warning("⚠️ QMT xtquant_path 未配置")
        return False

    if not os.path.exists(xtquant_path):
        logger.warning(f"⚠️ QMT xtquant_path 不存在: {xtquant_path}")
        return False

    # 关键：使用 append 而非 insert
    if xtquant_path not in sys.path:
        sys.path.append(xtquant_path)
        logger.info(f"✅ xtquant_path 已追加到 sys.path: {xtquant_path}")

    _xtquant_path_injected = True
    return True


def _ensure_xtdata() -> bool:
    """
    延迟导入 xtdata + xtconstant

    Returns:
        bool: 是否成功导入
    """
    global _xtquant_available, _xtdata, _xtconstant

    if _xtquant_available and _xtdata is not None:
        return True

    # 先注入路径
    if not _inject_xtquant_path():
        return False

    try:
        from xtquant import xtdata, xtconstant  # type: ignore
        _xtdata = xtdata
        _xtconstant = xtconstant
        _xtquant_available = True
        logger.info("✅ xtquant 模块导入成功")
        return True
    except ImportError as e:
        logger.warning(f"⚠️ xtquant 导入失败: {e}")
        _xtquant_available = False
        return False
    except Exception as e:
        logger.warning(f"⚠️ xtquant 导入异常: {e}")
        _xtquant_available = False
        return False


def get_qmt_provider() -> "QMTProvider":
    """获取 QMT Provider 单例"""
    global _qmt_provider_instance
    if _qmt_provider_instance is None:
        _qmt_provider_instance = QMTProvider()
    return _qmt_provider_instance


_qmt_provider_instance = None


class QMTProvider(BaseStockDataProvider):
    """
    QMT 数据提供器

    特点：
    - 需要本地 QMT 终端运行
    - 提供高质量实时行情（直连交易所）
    - 支持多周期 K 线（1m, 5m, 15m, 30m, 1h, 1d, 1w, 1mon）
    - 提供五档盘口数据（独有）
    - 不提供 PE/PB/市值 等估值数据
    - 不提供新闻/公告数据
    """

    def __init__(self):
        super().__init__("QMT")
        self.config = get_provider_config("qmt")
        self.xtdata = None
        self.xtconstant = None
        self._connected = False
        self._platform_ok = sys.platform == "win32"

        if not self._platform_ok:
            self.logger.warning("⚠️ QMT 仅支持 Windows 平台")

    def _ensure_xtdata_instance(self) -> bool:
        """确保 xtdata 实例可用"""
        if self.xtdata is not None:
            return True

        if _ensure_xtdata():
            self.xtdata = _xtdata
            self.xtconstant = _xtconstant
            return True

        return False

    async def connect(self) -> bool:
        """
        连接到 QMT 终端

        通过尝试获取上证指数的日K数据来验证 QMT 是否运行中
        """
        if not self._platform_ok:
            self.logger.warning("⚠️ 非 Windows 平台，QMT 不可用")
            self.connected = False
            return False

        if not self.config.get("enabled", False):
            self.logger.info("QMT 数据源未启用")
            self.connected = False
            return False

        if not self._ensure_xtdata_instance():
            self.logger.warning("⚠️ xtdata 模块不可用")
            self.connected = False
            return False

        try:
            # 测试连接：获取上证指数 1根日K
            result = await asyncio.to_thread(
                self._test_connection_sync
            )

            if result:
                self.connected = True
                self._connected = True
                self.logger.info("✅ QMT 连接成功")
                return True
            else:
                self.connected = False
                self.logger.warning("⚠️ QMT 连接测试失败（终端可能未运行）")
                return False

        except Exception as e:
            self.logger.error(f"❌ QMT 连接测试异常: {e}")
            self.connected = False
            return False

    def connect_sync(self) -> bool:
        """同步版本的连接测试"""
        if not self._platform_ok:
            return False

        if not self.config.get("enabled", False):
            return False

        if not self._ensure_xtdata_instance():
            return False

        try:
            return self._test_connection_sync()
        except Exception as e:
            self.logger.error(f"❌ QMT 连接测试异常: {e}")
            return False

    def _test_connection_sync(self) -> bool:
        """同步连接测试"""
        try:
            # 尝试获取上证指数 000001.SH 的日K数据
            kline = self.xtdata.get_market_data_ex(
                field_list=["close"],
                stock_list=["000001.SH"],
                period="1d",
                count=1
            )

            if kline and "000001.SH" in kline:
                data = kline["000001.SH"]
                if data is not None and len(data.get("close", [])) > 0:
                    self.logger.info("✅ QMT 终端响应正常")
                    return True

            self.logger.warning("⚠️ QMT 终端无响应或数据为空")
            return False

        except Exception as e:
            self.logger.error(f"❌ QMT 连接测试失败: {e}")
            return False

    def is_available(self) -> bool:
        """检查 QMT 是否可用"""
        return self.connected and self._connected and self.xtdata is not None

    async def get_stock_basic_info(self, symbol: str = None) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """
        获取股票基础信息

        QMT 通过板块遍历获取股票列表，单个股票信息通过 get_instrument_detail 获取
        """
        if not self.is_available():
            return None

        if symbol:
            # 获取单只股票信息
            return await asyncio.to_thread(self._get_single_stock_info_sync, symbol)
        else:
            # 获取所有股票列表
            return await self.get_stock_list()

    def _get_single_stock_info_sync(self, symbol: str) -> Optional[Dict[str, Any]]:
        """同步获取单只股票信息"""
        try:
            # 转换为 QMT 格式代码
            qmt_code = self._normalize_to_qmt_code(symbol)

            detail = self.xtdata.get_instrument_detail(qmt_code)
            if detail:
                return {
                    "code": self._extract_6digit_code(qmt_code),
                    "symbol": self._extract_6digit_code(qmt_code),
                    "full_symbol": qmt_code,
                    "ts_code": qmt_code,
                    "name": detail.get("InstrumentName", ""),
                    "data_source": "qmt",
                    "updated_at": datetime.utcnow(),
                }
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取股票信息失败 {symbol}: {e}")
            return None

    async def get_stock_list(self, market: str = "CN") -> Optional[List[Dict[str, Any]]]:
        """
        获取股票列表（通过板块遍历）

        QMT 没有直接获取全市场股票列表的接口，需要：
        1. 先 download_sector_data 同步板块数据
        2. 遍历 get_sector_list 获取板块
        3. 对每个板块调用 get_stock_list_in_sector
        4. 去重合并
        """
        if not self.is_available():
            return None

        try:
            return await asyncio.to_thread(self._get_stock_list_sync)
        except Exception as e:
            self.logger.error(f"❌ 获取股票列表失败: {e}")
            return None

    def _get_stock_list_sync(self) -> List[Dict[str, Any]]:
        """同步获取股票列表"""
        stocks = {}

        try:
            # 确保板块数据已同步
            self._ensure_sector_data()

            # 获取所有板块
            sectors = list(self.xtdata.get_sector_list() or [])
            self.logger.info(f"📊 获取到 {len(sectors)} 个板块")

            # 过滤：只取行业板块和概念板块（排除指数等）
            stock_sectors = []
            for sector in sectors:
                sector_str = str(sector)
                # 行业板块和概念板块通常包含股票
                if any(key in sector_str for key in ["行业", "概念", "板块", "指数成分"]):
                    stock_sectors.append(sector)

            self.logger.info(f"📊 筛选出 {len(stock_sectors)} 个股票板块")

            # 遍历板块获取股票
            for sector in stock_sectors[:100]:  # 限制数量避免超时
                try:
                    sector_stocks = list(self.xtdata.get_stock_list_in_sector(sector) or [])
                    for s in sector_stocks:
                        code = str(s)
                        if code not in stocks:
                            # 获取股票名称
                            name = ""
                            try:
                                detail = self.xtdata.get_instrument_detail(code)
                                if detail:
                                    name = detail.get("InstrumentName", "")
                            except Exception:
                                pass

                            stocks[code] = {
                                "code": self._extract_6digit_code(code),
                                "symbol": self._extract_6digit_code(code),
                                "full_symbol": code,
                                "ts_code": code,
                                "name": name,
                                "market": self._determine_market_from_code(code),
                                "data_source": "qmt",
                                "updated_at": datetime.utcnow(),
                            }
                except Exception as e:
                    self.logger.warning(f"⚠️ 获取板块 {sector} 股票失败: {e}")
                    continue

            self.logger.info(f"✅ 获取到 {len(stocks)} 只股票")
            return list(stocks.values())

        except Exception as e:
            self.logger.error(f"❌ 获取股票列表失败: {e}")
            return []

    def _ensure_sector_data(self):
        """确保板块数据已同步"""
        try:
            sectors = list(self.xtdata.get_sector_list() or [])
            if len(sectors) < _SECTOR_MIN_COUNT:
                self.logger.info("🔄 同步板块数据...")
                self.xtdata.download_sector_data()
                sectors = list(self.xtdata.get_sector_list() or [])
                self.logger.info(f"✅ 板块数据同步完成，共 {len(sectors)} 个板块")
        except Exception as e:
            self.logger.warning(f"⚠️ 同步板块数据失败: {e}")

    async def get_stock_quotes(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取实时行情

        通过 get_market_data_ex 获取日K快照
        """
        if not self.is_available():
            return None

        try:
            return await asyncio.to_thread(self._get_stock_quotes_sync, symbol)
        except Exception as e:
            self.logger.error(f"❌ 获取行情失败 {symbol}: {e}")
            return None

    def _get_stock_quotes_sync(self, symbol: str) -> Optional[Dict[str, Any]]:
        """同步获取行情"""
        try:
            qmt_code = self._normalize_to_qmt_code(symbol)

            # 先下载历史数据确保缓存
            try:
                self.xtdata.download_history_data(qmt_code, period="1d", start_time="", end_time="")
            except Exception:
                pass

            kline = self.xtdata.get_market_data_ex(
                field_list=["open", "high", "low", "close", "volume", "amount"],
                stock_list=[qmt_code],
                period="1d",
                count=2  # 取2根，用于计算涨跌幅
            )

            if kline and qmt_code in kline:
                data = kline[qmt_code]
                if data is not None and len(data.get("close", [])) > 0:
                    close = self._arr_at(data["close"], -1)
                    open_ = self._arr_at(data["open"], -1)
                    high = self._arr_at(data["high"], -1)
                    low = self._arr_at(data["low"], -1)
                    volume = self._arr_at(data["volume"], -1)
                    amount = self._arr_at(data["amount"], -1)

                    # 计算涨跌幅
                    pre_close = self._arr_at(data["close"], -2) if len(data["close"]) > 1 else open_
                    pct_chg = ((close - pre_close) / pre_close * 100) if pre_close else 0

                    return self.standardize_quotes({
                        "symbol": self._extract_6digit_code(qmt_code),
                        "ts_code": qmt_code,
                        "close": close,
                        "open": open_,
                        "high": high,
                        "low": low,
                        "pre_close": pre_close,
                        "volume": volume,
                        "amount": amount,
                        "pct_chg": pct_chg,
                        "change": close - pre_close,
                    })

            return None
        except Exception as e:
            self.logger.error(f"❌ 获取行情失败 {symbol}: {e}")
            return None

    async def get_historical_data(
        self,
        symbol: str,
        start_date: Union[str, date],
        end_date: Union[str, date] = None,
        period: str = "1d"
    ) -> Optional[pd.DataFrame]:
        """
        获取历史K线数据

        Args:
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            period: 周期 (1m, 5m, 15m, 30m, 1h, 1d, 1w, 1mon)
        """
        if not self.is_available():
            return None

        try:
            return await asyncio.to_thread(
                self._get_historical_data_sync, symbol, start_date, end_date, period
            )
        except Exception as e:
            self.logger.error(f"❌ 获取历史数据失败 {symbol}: {e}")
            return None

    def _get_historical_data_sync(
        self, symbol: str, start_date, end_date, period: str
    ) -> Optional[pd.DataFrame]:
        """同步获取历史数据"""
        try:
            qmt_code = self._normalize_to_qmt_code(symbol)
            qmt_period = PERIOD_MAP.get(period, period)

            # 格式化日期
            start_str = self._format_date_for_qmt(start_date)
            end_str = self._format_date_for_qmt(end_date) if end_date else ""

            # 分块下载（避免超时）
            self._download_history_chunked(qmt_code, qmt_period, start_str, end_str)

            # 获取数据
            kline = self.xtdata.get_market_data_ex(
                field_list=["open", "high", "low", "close", "volume", "amount"],
                stock_list=[qmt_code],
                period=qmt_period,
                start_time=start_str,
                end_time=end_str,
            )

            if kline and qmt_code in kline:
                data = kline[qmt_code]
                if data is not None and len(data.get("close", [])) > 0:
                    # 转换为 DataFrame
                    df = pd.DataFrame({
                        "date": list(data.index) if hasattr(data, "index") else range(len(data["close"])),
                        "open": list(data["open"]),
                        "high": list(data["high"]),
                        "low": list(data["low"]),
                        "close": list(data["close"]),
                        "volume": list(data["volume"]),
                        "amount": list(data["amount"]),
                    })
                    return df

            return None
        except Exception as e:
            self.logger.error(f"❌ 获取历史数据失败 {symbol}: {e}")
            return None

    def _download_history_chunked(self, code: str, period: str, start: str, end: str):
        """分块下载历史数据"""
        if not start or not end:
            try:
                self.xtdata.download_history_data(code, period=period, start_time="", end_time="")
            except Exception:
                pass
            return

        try:
            chunk_days = CHUNK_DAYS.get(period, 30)
            end_dt = datetime.strptime(end, "%Y%m%d")
            start_dt = datetime.strptime(start, "%Y%m%d")

            cur_end = end_dt
            while cur_end >= start_dt:
                cur_start = max(start_dt, cur_end - timedelta(days=chunk_days - 1))
                s, e = cur_start.strftime("%Y%m%d"), cur_end.strftime("%Y%m%d")
                try:
                    self.xtdata.download_history_data(code, period=period, start_time=s, end_time=e)
                except Exception:
                    pass

                if cur_start <= start_dt:
                    break
                cur_end = cur_start - timedelta(days=1)

        except Exception as e:
            self.logger.warning(f"⚠️ 分块下载失败: {e}")

    async def get_financial_data(
        self, symbol: str,
        report_type: str = "quarterly",
        limit: int = 4
    ) -> Optional[Dict[str, Any]]:
        """
        获取财务数据

        QMT 提供5张表：Income, Balance, CashFlow, Capital, PershareIndex
        """
        if not self.is_available():
            return None

        try:
            return await asyncio.to_thread(self._get_financial_data_sync, symbol, limit)
        except Exception as e:
            self.logger.error(f"❌ 获取财务数据失败 {symbol}: {e}")
            return None

    def _get_financial_data_sync(self, symbol: str, limit: int) -> Optional[Dict[str, Any]]:
        """同步获取财务数据"""
        try:
            qmt_code = self._normalize_to_qmt_code(symbol)

            tables = ["Income", "Balance", "CashFlow", "Capital", "PershareIndex"]

            # 先下载财务数据
            try:
                self.xtdata.download_financial_data([qmt_code], table_list=tables)
            except Exception:
                pass

            # 获取财务数据
            fin = self.xtdata.get_financial_data(
                [qmt_code],
                table_list=tables,
                report_type="report_time"
            )

            if fin and qmt_code in fin:
                result = {}
                for table_name, df in fin[qmt_code].items():
                    if hasattr(df, "to_dict"):
                        records = df.to_dict(orient="records")
                        result[table_name] = records[-limit:] if len(records) > limit else records
                    elif isinstance(df, list):
                        result[table_name] = df[-limit:] if len(df) > limit else df
                return result

            return None
        except Exception as e:
            self.logger.error(f"❌ 获取财务数据失败 {symbol}: {e}")
            return None

    async def get_full_tick(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        获取五档盘口数据（QMT 独有）

        Returns:
            包含 lastPrice, bidPrice[5], askPrice[5], bidVol[5], askVol[5] 的字典
        """
        if not self.is_available():
            return None

        try:
            return await asyncio.to_thread(self._get_full_tick_sync, symbol)
        except Exception as e:
            self.logger.error(f"❌ 获取盘口数据失败 {symbol}: {e}")
            return None

    def _get_full_tick_sync(self, symbol: str) -> Optional[Dict[str, Any]]:
        """同步获取五档盘口"""
        try:
            qmt_code = self._normalize_to_qmt_code(symbol)

            raw = self.xtdata.get_full_tick([qmt_code])
            if raw and qmt_code in raw:
                tick = raw[qmt_code]
                return {
                    "code": self._extract_6digit_code(qmt_code),
                    "lastPrice": tick.get("lastPrice", 0),
                    "open": tick.get("open", 0),
                    "high": tick.get("high", 0),
                    "low": tick.get("low", 0),
                    "preClose": tick.get("lastClose", 0),
                    "volume": tick.get("volume", 0),
                    "amount": tick.get("amount", 0),
                    "bidPrice": tick.get("bidPrice", []),
                    "askPrice": tick.get("askPrice", []),
                    "bidVol": tick.get("bidVol", []),
                    "askVol": tick.get("askVol", []),
                    "time": tick.get("timetag", ""),
                }
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取盘口数据失败 {symbol}: {e}")
            return None

    def get_realtime_quotes_batch_sync(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        批量获取全市场实时行情（同步版本）

        通过板块遍历获取所有股票，然后批量调用行情接口
        """
        if not self.is_available():
            return None

        try:
            # 获取股票列表
            stocks = self._get_stock_list_sync()
            if not stocks:
                return None

            result = {}
            batch_size = 100

            for i in range(0, len(stocks), batch_size):
                batch = stocks[i:i + batch_size]
                codes = [s["full_symbol"] for s in batch]

                try:
                    # 批量下载确保缓存
                    for code in codes:
                        try:
                            self.xtdata.download_history_data(code, period="1d", start_time="", end_time="")
                        except Exception:
                            pass

                    # 批量获取行情
                    kline = self.xtdata.get_market_data_ex(
                        field_list=["open", "high", "low", "close", "volume", "amount"],
                        stock_list=codes,
                        period="1d",
                        count=2
                    )

                    for code in codes:
                        if code in kline:
                            data = kline[code]
                            if data and len(data.get("close", [])) > 0:
                                close = self._arr_at(data["close"], -1)
                                pre_close = self._arr_at(data["close"], -2) if len(data["close"]) > 1 else self._arr_at(data["open"], -1)
                                pct_chg = ((close - pre_close) / pre_close * 100) if pre_close else 0

                                result[self._extract_6digit_code(code)] = {
                                    "close": close,
                                    "open": self._arr_at(data["open"], -1),
                                    "high": self._arr_at(data["high"], -1),
                                    "low": self._arr_at(data["low"], -1),
                                    "pre_close": pre_close,
                                    "pct_chg": pct_chg,
                                    "volume": self._arr_at(data["volume"], -1),
                                    "amount": self._arr_at(data["amount"], -1),
                                }
                except Exception as e:
                    self.logger.warning(f"⚠️ 批量获取行情失败: {e}")
                    continue

            return result
        except Exception as e:
            self.logger.error(f"❌ 批量获取行情失败: {e}")
            return None

    def find_latest_trade_date_sync(self) -> Optional[str]:
        """同步查找最新交易日期"""
        if not self.is_available():
            return None

        try:
            kline = self.xtdata.get_market_data_ex(
                field_list=["close"],
                stock_list=["000001.SH"],
                period="1d",
                count=5
            )

            if kline and "000001.SH" in kline:
                data = kline["000001.SH"]
                if data and len(data.get("close", [])) > 0:
                    # 从 index 获取日期
                    index_vals = list(data.index) if hasattr(data, "index") else []
                    if index_vals:
                        last_date = str(index_vals[-1])
                        # 解析日期格式
                        if len(last_date) >= 8:
                            return last_date[:8]

            return None
        except Exception as e:
            self.logger.error(f"❌ 查找最新交易日失败: {e}")
            return None

    # ==================== 辅助方法 ====================

    def _normalize_to_qmt_code(self, symbol: str) -> str:
        """
        将 6位代码转换为 QMT 格式 (XXXXXX.SH/SZ)

        Args:
            symbol: 6位股票代码 或已有的 QMT 格式代码

        Returns:
            QMT 格式代码
        """
        if not symbol:
            return ""

        s = str(symbol).strip()

        # 已经是 QMT 格式
        if "." in s:
            return s.upper()

        # 6位数字代码
        if s.isdigit():
            s = s.zfill(6)
            # 根据代码判断交易所
            if s.startswith(("5", "6", "9")):
                return f"{s}.SH"
            elif s.startswith(("0", "3")):
                return f"{s}.SZ"
            elif s.startswith(("4", "8")):
                return f"{s}.BJ"
            else:
                return f"{s}.SZ"  # 默认深交所

        return s

    def _extract_6digit_code(self, qmt_code: str) -> str:
        """从 QMT 格式代码提取 6位数字代码"""
        if "." in qmt_code:
            return qmt_code.split(".")[0].zfill(6)
        return qmt_code.zfill(6)

    def _determine_market_from_code(self, qmt_code: str) -> str:
        """从 QMT 代码判断市场"""
        if qmt_code.endswith(".SH"):
            return "上海证券交易所"
        elif qmt_code.endswith(".SZ"):
            return "深圳证券交易所"
        elif qmt_code.endswith(".BJ"):
            return "北京证券交易所"
        return "未知"

    def _arr_at(self, arr: Any, i: int) -> float:
        """从 pandas Series / numpy / list 取第 i 个元素"""
        if arr is None:
            return 0.0
        try:
            if hasattr(arr, "iloc"):
                return float(arr.iloc[i])
            elif hasattr(arr, "__getitem__"):
                return float(arr[i])
            else:
                return float(arr)
        except Exception:
            return 0.0

    def _format_date_for_qmt(self, date_val: Any) -> str:
        """格式化日期为 QMT 格式 (YYYYMMDD)"""
        if not date_val:
            return ""

        if isinstance(date_val, str):
            # 已经是 YYYYMMDD 格式
            if len(date_val) == 8 and date_val.isdigit():
                return date_val
            # YYYY-MM-DD 格式
            if "-" in date_val:
                return date_val.replace("-", "")[:8]
            return date_val[:8]

        if isinstance(date_val, (date, datetime)):
            return date_val.strftime("%Y%m%d")

        return str(date_val)[:8]

    def _determine_market_info(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """确定市场信息"""
        code = raw_data.get("ts_code", raw_data.get("full_symbol", ""))

        if code.endswith(".SH"):
            return {
                "market": "CN",
                "exchange": "SSE",
                "exchange_name": "上海证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif code.endswith(".SZ"):
            return {
                "market": "CN",
                "exchange": "SZSE",
                "exchange_name": "深圳证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }
        elif code.endswith(".BJ"):
            return {
                "market": "CN",
                "exchange": "BSE",
                "exchange_name": "北京证券交易所",
                "currency": "CNY",
                "timezone": "Asia/Shanghai"
            }

        return super()._determine_market_info(raw_data)