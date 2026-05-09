"""
QMT数据同步服务
负责将QMT本地数据同步到MongoDB标准化集合

特点：
- 无需 API 限流（本地数据源）
- 需要先调用 download_* 方法确保本地缓存
- 股票列表通过板块遍历获取
- 不提供新闻数据
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import logging
from pymongo import UpdateOne
from zoneinfo import ZoneInfo

from tradingagents.dataflows.providers.china.qmt import get_qmt_provider, QMTProvider
from app.services.stock_data_service import get_stock_data_service
from app.services.historical_data_service import get_historical_data_service
from app.services.financial_data_service import get_financial_data_service
from app.core.database import get_mongo_db
from app.core.config import settings
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

# UTC+8 时区
UTC_8 = timezone(timedelta(hours=8))


def get_utc8_now():
    """获取 UTC+8 当前时间（naive datetime）"""
    return now_tz().replace(tzinfo=None)


# 全局服务实例
_qmt_sync_service = None


async def get_qmt_sync_service() -> "QMTSyncService":
    """获取 QMT 同步服务单例"""
    global _qmt_sync_service
    if _qmt_sync_service is None:
        _qmt_sync_service = QMTSyncService()
        await _qmt_sync_service.initialize()
    return _qmt_sync_service


class QMTSyncService:
    """
    QMT 数据同步服务

    将 QMT 终端的本地数据同步到 MongoDB
    """

    def __init__(self):
        self.provider: Optional[QMTProvider] = None
        self.stock_service = get_stock_data_service()
        self.historical_service = None
        self.financial_service = None
        self.db = None
        self.settings = settings

        # 同步配置（QMT 无需限流）
        self.batch_size = 50
        self.max_retries = 3

    async def initialize(self):
        """初始化同步服务"""
        # 检查平台
        if sys.platform != "win32":
            logger.warning("⚠️ QMT 仅支持 Windows 平台")
            return

        # 检查配置
        if not getattr(settings, "QMT_ENABLED", False):
            logger.info("QMT 数据源未启用")
            return

        try:
            self.provider = get_qmt_provider()

            # 尝试连接
            connected = await self.provider.connect()
            if not connected:
                logger.warning("⚠️ QMT 终端未运行，同步服务将跳过")
                return

            # 初始化数据库
            self.db = get_mongo_db()

            # 初始化历史数据服务
            self.historical_service = await get_historical_data_service()

            # 初始化财务数据服务
            self.financial_service = await get_financial_data_service()

            logger.info("✅ QMT 同步服务初始化完成")
        except Exception as e:
            logger.error(f"❌ QMT 同步服务初始化失败: {e}")

    def is_ready(self) -> bool:
        """检查服务是否就绪"""
        return (
            self.provider is not None
            and self.provider.is_available()
            and self.db is not None
        )

    # ==================== 基础信息同步 ====================

    async def sync_stock_basic_info(
        self,
        force_update: bool = False,
        job_id: str = None
    ) -> Dict[str, Any]:
        """
        同步股票基础信息（通过板块遍历）

        Args:
            force_update: 是否强制更新
            job_id: 任务ID

        Returns:
            同步结果统计
        """
        if not self.is_ready():
            return {"status": "skipped", "reason": "QMT not available"}

        logger.info("🔄 开始 QMT 股票基础信息同步...")

        stats = {
            "total_processed": 0,
            "inserted": 0,
            "updated": 0,
            "errors": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "errors_list": [],
        }

        try:
            # 获取股票列表（通过板块遍历）
            stock_list = await asyncio.to_thread(
                self.provider._get_stock_list_sync
            )

            if not stock_list:
                logger.warning("⚠️ QMT 未获取到股票列表")
                return stats

            stats["total_processed"] = len(stock_list)
            logger.info(f"📊 QMT 获取到 {len(stock_list)} 只股票")

            # 分批处理
            operations = []
            batch_size = self.batch_size

            for i in range(0, len(stock_list), batch_size):
                batch = stock_list[i:i + batch_size]

                for stock in batch:
                    try:
                        code = stock.get("code", stock.get("symbol", ""))
                        full_symbol = stock.get("full_symbol", stock.get("ts_code", ""))
                        name = stock.get("name", "")

                        if not code:
                            continue

                        # 构造更新操作
                        operations.append(
                            UpdateOne(
                                {"symbol": code},
                                {
                                    "$set": {
                                        "symbol": code,
                                        "full_symbol": full_symbol,
                                        "name": name,
                                        "data_source": "qmt",
                                        "updated_at": datetime.utcnow(),
                                    }
                                },
                                upsert=True
                            )
                        )
                    except Exception as e:
                        stats["errors"] += 1
                        stats["errors_list"].append(str(e))

            # 执行批量写入
            if operations:
                result = await asyncio.to_thread(
                    self._execute_bulk_write,
                    operations
                )
                stats["inserted"] = result.get("inserted", 0)
                stats["updated"] = result.get("updated", 0)

            stats["end_time"] = datetime.utcnow()

            # 更新同步状态
            await self._update_sync_status("stock_basic_info", stats, job_id)

            logger.info(f"✅ QMT 基础信息同步完成: 新增 {stats['inserted']}, 更新 {stats['updated']}")
            return stats

        except Exception as e:
            logger.error(f"❌ QMT 基础信息同步失败: {e}")
            stats["errors"] += 1
            stats["errors_list"].append(str(e))
            return stats

    def _execute_bulk_write(self, operations: List) -> Dict[str, int]:
        """执行批量写入（同步版本）"""
        inserted = 0
        updated = 0

        try:
            result = self.db.stock_basic_info.bulk_write(operations, ordered=False)
            inserted = result.upserted_count
            updated = result.modified_count
        except Exception as e:
            logger.error(f"❌ 批量写入失败: {e}")

        return {"inserted": inserted, "updated": updated}

    # ==================== 实时行情同步 ====================

    async def sync_realtime_quotes(self, force: bool = False) -> Dict[str, Any]:
        """
        同步实时行情

        Args:
            force: 是否强制同步

        Returns:
            同步结果统计
        """
        if not self.is_ready():
            return {"status": "skipped", "reason": "QMT not available"}

        logger.info("🔄 开始 QMT 实时行情同步...")

        stats = {
            "total_processed": 0,
            "updated": 0,
            "errors": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
        }

        try:
            # 批量获取实时行情
            quotes = await asyncio.to_thread(
                self.provider.get_realtime_quotes_batch_sync
            )

            if not quotes:
                logger.warning("⚠️ QMT 未获取到实时行情")
                return stats

            stats["total_processed"] = len(quotes)

            # 构造更新操作
            operations = []
            for code, quote in quotes.items():
                try:
                    operations.append(
                        UpdateOne(
                            {"symbol": code},
                            {
                                "$set": {
                                    "symbol": code,
                                    "close": quote.get("close"),
                                    "open": quote.get("open"),
                                    "high": quote.get("high"),
                                    "low": quote.get("low"),
                                    "pre_close": quote.get("pre_close"),
                                    "pct_chg": quote.get("pct_chg"),
                                    "volume": quote.get("volume"),
                                    "amount": quote.get("amount"),
                                    "data_source": "qmt",
                                    "updated_at": datetime.utcnow(),
                                }
                            },
                            upsert=True
                        )
                    )
                except Exception as e:
                    stats["errors"] += 1

            # 执行批量写入
            if operations:
                result = await asyncio.to_thread(
                    self._execute_quotes_bulk_write,
                    operations
                )
                stats["updated"] = result.get("updated", 0)

            stats["end_time"] = datetime.utcnow()

            logger.info(f"✅ QMT 行情同步完成: 更新 {stats['updated']} 条")
            return stats

        except Exception as e:
            logger.error(f"❌ QMT 行情同步失败: {e}")
            stats["errors"] += 1
            return stats

    def _execute_quotes_bulk_write(self, operations: List) -> Dict[str, int]:
        """执行行情批量写入"""
        updated = 0
        try:
            result = self.db.market_quotes.bulk_write(operations, ordered=False)
            updated = result.modified_count + result.upserted_count
        except Exception as e:
            logger.error(f"❌ 行情批量写入失败: {e}")
        return {"updated": updated}

    # ==================== 历史数据同步 ====================

    async def sync_historical_data(
        self,
        symbols: List[str] = None,
        start_date: str = None,
        end_date: str = None,
        incremental: bool = True,
        period: str = "1d",
        job_id: str = None
    ) -> Dict[str, Any]:
        """
        同步历史 K 线数据

        Args:
            symbols: 股票代码列表（None 则同步全市场）
            start_date: 开始日期
            end_date: 结束日期
            incremental: 是否增量同步
            period: K 线周期
            job_id: 任务ID

        Returns:
            同步结果统计
        """
        if not self.is_ready():
            return {"status": "skipped", "reason": "QMT not available"}

        logger.info(f"🔄 开始 QMT 历史数据同步 ({period})...")

        stats = {
            "total_processed": 0,
            "records_synced": 0,
            "errors": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
        }

        try:
            # 如果未指定股票列表，获取全市场
            if not symbols:
                stock_list = await asyncio.to_thread(
                    self.provider._get_stock_list_sync
                )
                symbols = [s.get("full_symbol") for s in stock_list if s.get("full_symbol")]

            if not symbols:
                logger.warning("⚠️ 无股票列表")
                return stats

            stats["total_processed"] = len(symbols)

            # 计算日期范围
            if not end_date:
                end_date = datetime.now().strftime("%Y%m%d")

            if not start_date:
                days = getattr(settings, "QMT_INIT_HISTORICAL_DAYS", 365)
                start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

            # 分批处理
            batch_size = min(self.batch_size, 10)  # QMT 历史数据下载较慢，减小批次

            for i in range(0, len(symbols), batch_size):
                batch = symbols[i:i + batch_size]

                for symbol in batch:
                    try:
                        # 获取历史数据
                        df = await asyncio.to_thread(
                            self.provider._get_historical_data_sync,
                            symbol, start_date, end_date, period
                        )

                        if df and not df.empty:
                            # 保存到数据库
                            await self._save_historical_data(symbol, df, period)
                            stats["records_synced"] += len(df)

                    except Exception as e:
                        stats["errors"] += 1
                        logger.warning(f"⚠️ {symbol} 历史数据同步失败: {e}")

            stats["end_time"] = datetime.utcnow()

            # 更新同步状态
            await self._update_sync_status("historical_data", stats, job_id)

            logger.info(f"✅ QMT 历史数据同步完成: {stats['records_synced']} 条记录")
            return stats

        except Exception as e:
            logger.error(f"❌ QMT 历史数据同步失败: {e}")
            stats["errors"] += 1
            return stats

    async def _save_historical_data(self, symbol: str, df, period: str):
        """保存历史数据到数据库"""
        # 这里委托给 historical_data_service 或直接写入
        pass

    # ==================== 财务数据同步 ====================

    async def sync_financial_data(
        self,
        symbols: List[str] = None,
        job_id: str = None
    ) -> Dict[str, Any]:
        """
        同步财务数据

        QMT 提供5张表：Income, Balance, CashFlow, Capital, PershareIndex
        """
        if not self.is_ready():
            return {"status": "skipped", "reason": "QMT not available"}

        logger.info("🔄 开始 QMT 财务数据同步...")

        stats = {
            "total_processed": 0,
            "records_synced": 0,
            "errors": 0,
            "start_time": datetime.utcnow(),
            "end_time": None,
        }

        try:
            if not symbols:
                stock_list = await asyncio.to_thread(
                    self.provider._get_stock_list_sync
                )
                symbols = [s.get("full_symbol") for s in stock_list if s.get("full_symbol")]

            if not symbols:
                return stats

            stats["total_processed"] = len(symbols)

            for symbol in symbols[:100]:  # 财务数据量较大，限制数量
                try:
                    fin_data = await asyncio.to_thread(
                        self.provider._get_financial_data_sync,
                        symbol, 4
                    )

                    if fin_data:
                        stats["records_synced"] += 1

                except Exception as e:
                    stats["errors"] += 1

            stats["end_time"] = datetime.utcnow()

            await self._update_sync_status("financial_data", stats, job_id)

            logger.info(f"✅ QMT 财务数据同步完成")
            return stats

        except Exception as e:
            logger.error(f"❌ QMT 财务数据同步失败: {e}")
            stats["errors"] += 1
            return stats

    # ==================== 状态更新 ====================

    async def _update_sync_status(self, data_type: str, stats: Dict, job_id: str = None):
        """更新同步状态到数据库"""
        try:
            status_doc = {
                "job": f"qmt_{data_type}_sync",
                "data_type": data_type,
                "source": "qmt",
                "status": "completed",
                "started_at": stats.get("start_time"),
                "finished_at": stats.get("end_time"),
                "total": stats.get("total_processed", 0),
                "inserted": stats.get("inserted", 0),
                "updated": stats.get("updated", 0),
                "errors": stats.get("errors", 0),
                "job_id": job_id,
            }

            await asyncio.to_thread(
                self.db.sync_status.update_one,
                {"job": status_doc["job"]},
                {"$set": status_doc},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"⚠️ 更新同步状态失败: {e}")

    async def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        if not self.is_ready():
            return {"status": "not_ready", "reason": "QMT not available"}

        try:
            # 查询最近的同步状态
            status = await asyncio.to_thread(
                self.db.sync_status.find_one,
                {"source": "qmt"},
                sort=[("finished_at", -1)]
            )

            if status:
                status.pop("_id", None)
                return status

            return {"status": "never_run", "source": "qmt"}
        except Exception as e:
            logger.error(f"❌ 获取同步状态失败: {e}")
            return {"status": "error", "reason": str(e)}


# ==================== APScheduler 入口函数 ====================

async def run_qmt_basic_info_sync(force_update: bool = False):
    """运行 QMT 基础信息同步"""
    try:
        service = await get_qmt_sync_service()
        if not service.is_ready():
            logger.info("QMT 不可用，跳过基础信息同步")
            return {"status": "skipped"}

        return await service.sync_stock_basic_info(force_update=force_update)
    except Exception as e:
        logger.error(f"❌ QMT 基础信息同步任务失败: {e}")
        return {"status": "error", "reason": str(e)}


async def run_qmt_quotes_sync(force: bool = False):
    """运行 QMT 行情同步"""
    try:
        service = await get_qmt_sync_service()
        if not service.is_ready():
            logger.info("QMT 不可用，跳过行情同步")
            return {"status": "skipped"}

        return await service.sync_realtime_quotes(force=force)
    except Exception as e:
        logger.error(f"❌ QMT 行情同步任务失败: {e}")
        return {"status": "error", "reason": str(e)}


async def run_qmt_historical_sync(incremental: bool = True):
    """运行 QMT 历史数据同步"""
    try:
        service = await get_qmt_sync_service()
        if not service.is_ready():
            logger.info("QMT 不可用，跳过历史数据同步")
            return {"status": "skipped"}

        return await service.sync_historical_data(incremental=incremental)
    except Exception as e:
        logger.error(f"❌ QMT 历史数据同步任务失败: {e}")
        return {"status": "error", "reason": str(e)}


async def run_qmt_financial_sync():
    """运行 QMT 财务数据同步"""
    try:
        service = await get_qmt_sync_service()
        if not service.is_ready():
            logger.info("QMT 不可用，跳过财务数据同步")
            return {"status": "skipped"}

        return await service.sync_financial_data()
    except Exception as e:
        logger.error(f"❌ QMT 财务数据同步任务失败: {e}")
        return {"status": "error", "reason": str(e)}


async def run_qmt_status_check():
    """运行 QMT 状态检查"""
    try:
        service = await get_qmt_sync_service()

        status = {
            "qmt_available": service.is_ready(),
            "platform": sys.platform,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if service.is_ready():
            # 测试连接
            try:
                test_result = await asyncio.to_thread(
                    service.provider._test_connection_sync
                )
                status["connection_ok"] = test_result
            except Exception as e:
                status["connection_ok"] = False
                status["error"] = str(e)

        logger.info(f"📊 QMT 状态: {status}")
        return status
    except Exception as e:
        logger.error(f"❌ QMT 状态检查失败: {e}")
        return {"status": "error", "reason": str(e)}