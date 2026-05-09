"""
QMT数据初始化API路由
提供Web接口进行QMT数据初始化和管理

注意：QMT 仅支持 Windows 平台，需要本地 QMT 终端运行
"""
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from app.core.database import get_mongo_db
from app.worker.qmt_init_service import get_qmt_init_service
from app.worker.qmt_sync_service import get_qmt_sync_service
from app.routers.auth_db import get_current_user
from app.utils.timezone import now_tz

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qmt-init", tags=["QMT初始化"])

# 全局任务状态存储
_initialization_status = {
    "is_running": False,
    "current_task": None,
    "start_time": None,
    "progress": None,
    "result": None
}


class InitializationRequest(BaseModel):
    """初始化请求模型"""
    historical_days: int = Field(default=365, ge=1, le=3650, description="历史数据天数")
    force: bool = Field(default=False, description="是否强制重新初始化")
    skip_if_exists: bool = Field(default=True, description="如果数据存在是否跳过")


class SyncRequest(BaseModel):
    """同步请求模型"""
    force_update: bool = Field(default=False, description="是否强制更新")
    symbols: Optional[list] = Field(default=None, description="指定股票代码列表")


@router.get("/status")
async def get_database_status():
    """
    获取数据库状态

    Returns:
        数据库状态信息
    """
    try:
        db = get_mongo_db()

        # 检查基础信息
        basic_count = await db.stock_basic_info.count_documents({})
        extended_count = await db.stock_basic_info.count_documents({
            "full_symbol": {"$exists": True}
        })

        # 获取最新更新时间
        latest_basic = await db.stock_basic_info.find_one(
            {}, sort=[("updated_at", -1)]
        )

        # 检查行情数据
        quotes_count = await db.market_quotes.count_documents({})
        latest_quotes = await db.market_quotes.find_one(
            {}, sort=[("updated_at", -1)]
        )

        # 数据质量评估
        data_quality = "excellent"
        if basic_count == 0:
            data_quality = "empty"
        elif extended_count / basic_count < 0.5:
            data_quality = "poor"
        elif extended_count / basic_count < 0.9:
            data_quality = "good"

        return {
            "success": True,
            "data": {
                "basic_info": {
                    "total_count": basic_count,
                    "extended_count": extended_count,
                    "coverage_rate": round(extended_count / basic_count * 100, 2) if basic_count > 0 else 0,
                    "latest_update": latest_basic.get("updated_at") if latest_basic else None
                },
                "market_quotes": {
                    "total_count": quotes_count,
                    "latest_update": latest_quotes.get("updated_at") if latest_quotes else None
                },
                "data_quality": data_quality,
                "check_time": now_tz()
            },
            "message": "数据库状态检查完成"
        }

    except Exception as e:
        logger.error(f"获取数据库状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取数据库状态失败: {str(e)}")


@router.get("/connection-test")
async def test_qmt_connection():
    """
    测试QMT连接状态

    Returns:
        连接测试结果（包含平台检查、xtquant导入、QMT终端状态）
    """
    try:
        # 平台检查
        platform_ok = sys.platform == "win32"
        platform_info = {
            "platform": sys.platform,
            "platform_ok": platform_ok,
            "message": "Windows平台支持" if platform_ok else "QMT仅支持Windows平台"
        }

        if not platform_ok:
            return {
                "success": True,
                "data": {
                    "connected": False,
                    "platform_info": platform_info,
                    "test_time": now_tz()
                },
                "message": "QMT仅支持Windows平台"
            }

        # 尝试获取同步服务
        service = await get_qmt_sync_service()

        result = {
            "connected": service.is_ready(),
            "platform_info": platform_info,
            "test_time": now_tz()
        }

        if service.is_ready():
            # 测试获取股票列表
            try:
                stock_list = await asyncio.to_thread(
                    service.provider._get_stock_list_sync
                )
                result["stock_count"] = len(stock_list) if stock_list else 0
                result["sample_stocks"] = stock_list[:5] if stock_list else []
            except Exception as e:
                result["stock_list_error"] = str(e)

            # 测试获取实时行情
            try:
                quotes = await asyncio.to_thread(
                    service.provider.get_realtime_quotes_batch_sync
                )
                result["quotes_count"] = len(quotes) if quotes else 0
            except Exception as e:
                result["quotes_error"] = str(e)

        return {
            "success": True,
            "data": result,
            "message": "QMT连接测试完成"
        }

    except Exception as e:
        logger.error(f"QMT连接测试失败: {e}")
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")


@router.get("/doctor")
async def qmt_doctor():
    """
    QMT环境诊断

    执行完整的环境检查：
    1. 平台检查（Windows）
    2. Python版本检查（3.10/3.11）
    3. xtquant路径配置检查
    4. xtquant导入检查
    5. QMT终端连接检查
    6. 数据获取测试

    Returns:
        诊断结果报告
    """
    import platform

    diagnostics = {
        "test_time": now_tz(),
        "checks": [],
        "overall_status": "unknown"
    }

    # 1. 平台检查
    platform_check = {
        "name": "平台检查",
        "status": "pass" if sys.platform == "win32" else "fail",
        "details": {
            "platform": sys.platform,
            "expected": "win32"
        },
        "message": "Windows平台" if sys.platform == "win32" else "QMT仅支持Windows平台"
    }
    diagnostics["checks"].append(platform_check)

    # 2. Python版本检查
    python_version = platform.python_version()
    version_ok = python_version.startswith("3.10") or python_version.startswith("3.11")
    version_check = {
        "name": "Python版本检查",
        "status": "pass" if version_ok else "warning",
        "details": {
            "version": python_version,
            "expected": "3.10.x or 3.11.x"
        },
        "message": "Python版本兼容" if version_ok else "xtquant .pyd可能需要Python 3.10/3.11"
    }
    diagnostics["checks"].append(version_check)

    # 3. xtquant路径配置检查
    try:
        from tradingagents.config.providers_config import get_provider_config
        qmt_config = get_provider_config("qmt")
        xtquant_path = qmt_config.get("xtquant_path", "")
        userdata_path = qmt_config.get("userdata_path", "")

        path_check = {
            "name": "xtquant路径配置",
            "status": "pass" if xtquant_path else "warning",
            "details": {
                "xtquant_path": xtquant_path or "未配置",
                "userdata_path": userdata_path or "未配置"
            },
            "message": "路径已配置" if xtquant_path else "建议配置QMT_XTQUANT_PATH"
        }
        diagnostics["checks"].append(path_check)
    except Exception as e:
        diagnostics["checks"].append({
            "name": "xtquant路径配置",
            "status": "fail",
            "details": {"error": str(e)},
            "message": "配置检查失败"
        })

    # 4. xtquant导入检查
    try:
        from tradingagents.dataflows.providers.china import QMT_AVAILABLE
        from tradingagents.dataflows.providers.china.qmt import _xtquant_available
        import_check = {
            "name": "xtquant导入检查",
            "status": "pass" if QMT_AVAILABLE else "fail",
            "details": {
                "QMT_AVAILABLE": QMT_AVAILABLE,
                "_xtquant_available": _xtquant_available
            },
            "message": "xtquant导入成功" if QMT_AVAILABLE else "xtquant导入失败，检查路径配置"
        }
        diagnostics["checks"].append(import_check)
    except Exception as e:
        diagnostics["checks"].append({
            "name": "xtquant导入检查",
            "status": "fail",
            "details": {"error": str(e)},
            "message": "xtquant导入失败"
        })

    # 5. QMT终端连接检查
    try:
        service = await get_qmt_sync_service()
        connection_ok = service.is_ready()

        connection_check = {
            "name": "QMT终端连接",
            "status": "pass" if connection_ok else "fail",
            "details": {
                "is_ready": connection_ok,
                "provider_available": service.provider is not None
            },
            "message": "QMT终端已连接" if connection_ok else "QMT终端未运行或连接失败"
        }
        diagnostics["checks"].append(connection_check)

        # 6. 数据获取测试（仅在连接成功时）
        if connection_ok:
            try:
                # 测试获取股票列表
                stock_list = await asyncio.to_thread(
                    service.provider._get_stock_list_sync
                )
                stock_count = len(stock_list) if stock_list else 0

                data_check = {
                    "name": "数据获取测试",
                    "status": "pass" if stock_count > 0 else "warning",
                    "details": {
                        "stock_count": stock_count
                    },
                    "message": f"成功获取{stock_count}只股票数据" if stock_count > 0 else "股票列表为空"
                }
                diagnostics["checks"].append(data_check)
            except Exception as e:
                diagnostics["checks"].append({
                    "name": "数据获取测试",
                    "status": "fail",
                    "details": {"error": str(e)},
                    "message": "数据获取失败"
                })
    except Exception as e:
        diagnostics["checks"].append({
            "name": "QMT终端连接",
            "status": "fail",
            "details": {"error": str(e)},
            "message": "连接检查失败"
        })

    # 计算总体状态
    pass_count = sum(1 for c in diagnostics["checks"] if c["status"] == "pass")
    fail_count = sum(1 for c in diagnostics["checks"] if c["status"] == "fail")
    warning_count = sum(1 for c in diagnostics["checks"] if c["status"] == "warning")

    if fail_count > 0:
        diagnostics["overall_status"] = "fail"
    elif warning_count > 0:
        diagnostics["overall_status"] = "warning"
    else:
        diagnostics["overall_status"] = "pass"

    diagnostics["summary"] = {
        "pass": pass_count,
        "fail": fail_count,
        "warning": warning_count,
        "total": len(diagnostics["checks"])
    }

    return {
        "success": True,
        "data": diagnostics,
        "message": f"诊断完成: {diagnostics['overall_status']}"
    }


@router.post("/start-full")
async def start_full_initialization(
    request: InitializationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    启动完整的数据初始化

    Args:
        request: 初始化请求参数
        background_tasks: 后台任务管理器
        current_user: 当前用户信息

    Returns:
        初始化启动结果
    """
    global _initialization_status

    # 检查平台
    if sys.platform != "win32":
        raise HTTPException(status_code=400, detail="QMT仅支持Windows平台")

    if _initialization_status["is_running"]:
        raise HTTPException(status_code=400, detail="初始化任务正在运行中")

    try:
        # 设置任务状态
        _initialization_status.update({
            "is_running": True,
            "current_task": "full_initialization",
            "start_time": now_tz(),
            "progress": {"current_step": "准备中", "completed_steps": 0, "total_steps": 5},
            "result": None
        })

        # 启动后台任务
        background_tasks.add_task(
            _run_full_initialization_background,
            request.historical_days,
            not request.skip_if_exists
        )

        return {
            "success": True,
            "data": {
                "task_id": "full_initialization",
                "start_time": _initialization_status["start_time"],
                "parameters": {
                    "historical_days": request.historical_days,
                    "force": not request.skip_if_exists
                }
            },
            "message": "完整初始化任务已启动，请使用 /initialization-status 查看进度"
        }

    except Exception as e:
        _initialization_status["is_running"] = False
        logger.error(f"启动完整初始化失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动初始化失败: {str(e)}")


@router.post("/start-basic-sync")
async def start_basic_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    启动基础信息同步

    Args:
        request: 同步请求参数
        background_tasks: 后台任务管理器
        current_user: 当前用户信息

    Returns:
        同步启动结果
    """
    global _initialization_status

    # 检查平台
    if sys.platform != "win32":
        raise HTTPException(status_code=400, detail="QMT仅支持Windows平台")

    if _initialization_status["is_running"]:
        raise HTTPException(status_code=400, detail="同步任务正在运行中")

    try:
        # 设置任务状态
        _initialization_status.update({
            "is_running": True,
            "current_task": "basic_sync",
            "start_time": now_tz(),
            "progress": {"current_step": "同步基础信息", "completed_steps": 0, "total_steps": 1},
            "result": None
        })

        # 启动后台任务
        background_tasks.add_task(
            _run_basic_sync_background,
            request.force_update
        )

        return {
            "success": True,
            "data": {
                "task_id": "basic_sync",
                "start_time": _initialization_status["start_time"],
                "parameters": {
                    "force_update": request.force_update
                }
            },
            "message": "基础信息同步任务已启动"
        }

    except Exception as e:
        _initialization_status["is_running"] = False
        logger.error(f"启动基础信息同步失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动同步失败: {str(e)}")


@router.get("/initialization-status")
async def get_initialization_status():
    """
    获取初始化任务状态

    Returns:
        当前任务状态
    """
    global _initialization_status

    return {
        "success": True,
        "data": {
            "is_running": _initialization_status["is_running"],
            "current_task": _initialization_status["current_task"],
            "start_time": _initialization_status["start_time"],
            "progress": _initialization_status["progress"],
            "result": _initialization_status["result"],
            "duration": (
                (now_tz() - _initialization_status["start_time"]).total_seconds()
                if _initialization_status["start_time"] else 0
            )
        },
        "message": "任务状态获取成功"
    }


@router.post("/stop")
async def stop_initialization(current_user: dict = Depends(get_current_user)):
    """
    停止当前初始化任务

    Args:
        current_user: 当前用户信息

    Returns:
        停止结果
    """
    global _initialization_status

    if not _initialization_status["is_running"]:
        raise HTTPException(status_code=400, detail="没有正在运行的任务")

    try:
        # 重置任务状态
        _initialization_status.update({
            "is_running": False,
            "current_task": None,
            "start_time": None,
            "progress": None,
            "result": {"stopped": True, "stop_time": datetime.utcnow()}
        })

        return {
            "success": True,
            "data": {
                "stopped": True,
                "stop_time": datetime.utcnow()
            },
            "message": "初始化任务已停止"
        }

    except Exception as e:
        logger.error(f"停止初始化任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"停止任务失败: {str(e)}")


async def _run_full_initialization_background(historical_days: int, force: bool):
    """后台运行完整初始化"""
    global _initialization_status

    try:
        service = await get_qmt_init_service()
        result = await service.run_full_initialization(
            historical_days=historical_days,
            skip_if_exists=not force
        )

        _initialization_status.update({
            "is_running": False,
            "result": result
        })

        logger.info(f"完整初始化后台任务完成: {result}")

    except Exception as e:
        _initialization_status.update({
            "is_running": False,
            "result": {"success": False, "error": str(e)}
        })
        logger.error(f"完整初始化后台任务失败: {e}")


async def _run_basic_sync_background(force_update: bool):
    """后台运行基础信息同步"""
    global _initialization_status

    try:
        service = await get_qmt_sync_service()
        result = await service.sync_stock_basic_info(force_update=force_update)

        _initialization_status.update({
            "is_running": False,
            "result": result
        })

        logger.info(f"基础信息同步后台任务完成: {result}")

    except Exception as e:
        _initialization_status.update({
            "is_running": False,
            "result": {"success": False, "error": str(e)}
        })
        logger.error(f"基础信息同步后台任务失败: {e}")