# QMT HTTP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI-based HTTP server that wraps QMT's xtquant library, enabling TradingAgents-CN to access QMT data and trading capabilities remotely via HTTP API.

**Architecture:** Independent FastAPI server running on Windows with QMT terminal. Server exposes RESTful endpoints for market data (quotes, klines, ticks), account queries (assets, positions, orders, trades), and trading operations (buy, sell, cancel). TradingAgents-CN connects as HTTP client. Uses Pydantic for validation, asyncio for async operations.

**Tech Stack:** Python 3.10/3.11, FastAPI, Pydantic, uvicorn, xtquant (xtdata + xttrader)

---

## File Structure

```
qmt_server/
├── main.py                    # FastAPI app entry point, router registration
├── config.py                  # Configuration loading (JSON + env vars)
├── requirements.txt           # Dependencies
├── routers/
│   ├── __init__.py
│   ├── market.py              # Market data endpoints (quotes, kline, tick, blocks)
│   ├── account.py             # Account endpoints (asset, positions, orders, trades)
│   ├── trade.py               # Trading endpoints (buy, sell, cancel)
│   └── system.py              # System endpoints (health, doctor, status)
├── services/
│   ├── __init__.py
│   ├── xtquant_service.py     # xtdata wrapper, stock list, quotes, kline
│   └── trade_service.py       # xttrader wrapper, orders, positions
├── models/
│   ├── __init__.py
│   └── schemas.py             # All Pydantic request/response models
└── middleware/
    ├── __init__.py
    └── rate_limit.py          # Rate limiting middleware
```

---

## Task 1: Project Setup and Configuration

**Files:**
- Create: `qmt_server/requirements.txt`
- Create: `qmt_server/config.py`
- Test: `tests/qmt_server/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_config.py
import os
import pytest
from qmt_server.config import Config

def test_config_loads_from_env():
    """Test config loads from environment variables"""
    os.environ['QMT_XTQUANT_PATH'] = 'D:\\test\\xtquant'
    os.environ['QMT_SERVER_PORT'] = '9090'
    
    config = Config()
    
    assert config.xtquant_path == 'D:\\test\\xtquant'
    assert config.port == 9090

def test_config_default_values():
    """Test config has sensible defaults"""
    # Clear env vars
    for key in ['QMT_XTQUANT_PATH', 'QMT_SERVER_PORT']:
        os.environ.pop(key, None)
    
    config = Config()
    
    assert config.host == '0.0.0.0'
    assert config.port == 8080
    assert config.log_level == 'INFO'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_config.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'qmt_server'"

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/requirements.txt
fastapi>=0.104.0
uvicorn>=0.24.0
pydantic>=2.0.0
python-multipart>=0.0.6
```

```python
# qmt_server/config.py
"""Configuration management for QMT Server"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """QMT Server configuration loaded from env vars and config.json"""
    
    # Server settings
    host: str = Field(default="0.0.0.0", alias="QMT_SERVER_HOST")
    port: int = Field(default=8080, alias="QMT_SERVER_PORT")
    log_level: str = Field(default="INFO", alias="QMT_LOG_LEVEL")
    
    # QMT paths
    xtquant_path: str = Field(default="", alias="QMT_XTQUANT_PATH")
    userdata_path: str = Field(default="", alias="QMT_USERDATA_PATH")
    
    # Account settings
    account_id: str = Field(default="", alias="QMT_ACCOUNT_ID")
    account_type: str = Field(default="STOCK", alias="QMT_ACCOUNT_TYPE")
    
    # Rate limiting
    rate_limit_enabled: bool = Field(default=True, alias="QMT_RATE_LIMIT_ENABLED")
    rate_limit_rpm: int = Field(default=60, alias="QMT_RATE_LIMIT_RPM")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create global config instance"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """Reload configuration from environment"""
    global _config
    _config = Config()
    return _config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_config.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/requirements.txt qmt_server/config.py tests/qmt_server/test_config.py
git commit -m "feat(qmt-server): add configuration management"
```

---

## Task 2: Pydantic Schemas (Request/Response Models)

**Files:**
- Create: `qmt_server/models/__init__.py`
- Create: `qmt_server/models/schemas.py`
- Test: `tests/qmt_server/test_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_schemas.py
import pytest
from datetime import datetime
from qmt_server.models.schemas import (
    QuoteResponse, KlineResponse, TickResponse,
    BuyRequest, SellRequest, CancelRequest,
    APIResponse, ErrorResponse
)


def test_quote_response_creation():
    """Test QuoteResponse model"""
    data = {
        "code": "000001",
        "fullCode": "000001.SZ",
        "name": "平安银行",
        "open": 10.50,
        "high": 10.68,
        "low": 10.42,
        "close": 10.55,
        "preClose": 10.48,
        "change": 0.07,
        "changePct": 0.67,
        "volume": 125000000,
        "amount": 1318750000.00
    }
    quote = QuoteResponse(**data)
    assert quote.code == "000001"
    assert quote.change_pct == 0.67


def test_buy_request_validation():
    """Test BuyRequest validation"""
    # Valid request
    req = BuyRequest(code="000001", volume=1000, price_type="FIX", price=10.55)
    assert req.code == "000001"
    assert req.confirm is False  # Default value
    
    # Invalid: volume not multiple of 100
    with pytest.raises(ValueError):
        BuyRequest(code="000001", volume=150, price_type="FIX", price=10.55)


def test_api_response_structure():
    """Test APIResponse wrapper"""
    response = APIResponse(
        success=True,
        timestamp=datetime.now(),
        data={"test": "value"},
        message="Success"
    )
    assert response.success is True
    assert response.error is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_schemas.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'qmt_server.models'"

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/models/__init__.py
from .schemas import *
```

```python
# qmt_server/models/schemas.py
"""Pydantic models for QMT Server API"""
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Base Response Models
# ============================================================================

class ErrorDetail(BaseModel):
    """Error detail structure"""
    code: str
    message: str
    details: Optional[str] = None


class APIResponse(BaseModel):
    """Standard API response wrapper"""
    success: bool
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Optional[Any] = None
    message: str = ""
    error: Optional[ErrorDetail] = None


# ============================================================================
# Market Data Models
# ============================================================================

class QuoteData(BaseModel):
    """Single stock quote"""
    code: str = Field(..., description="6位股票代码")
    full_code: str = Field(..., alias="fullCode", description="完整代码如 000001.SZ")
    name: Optional[str] = Field(None, description="股票名称")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    pre_close: Optional[float] = Field(None, alias="preClose")
    change: Optional[float] = None
    change_pct: Optional[float] = Field(None, alias="changePct")
    volume: Optional[int] = None
    amount: Optional[float] = None


class QuoteResponse(BaseModel):
    """Quote response wrapper"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: Optional[str] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: float
    pre_close: Optional[float] = Field(None, alias="preClose")
    change: Optional[float] = None
    change_pct: Optional[float] = Field(None, alias="changePct")
    volume: Optional[int] = None
    amount: Optional[float] = None


class KlineItem(BaseModel):
    """Single Kline data point"""
    date: str = Field(..., description="日期格式 YYYYMMDD")
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class KlineResponse(BaseModel):
    """Kline response"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: Optional[str] = None
    period: str
    count: int
    kline: List[KlineItem]


class TickResponse(BaseModel):
    """Five-level tick data response"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: Optional[str] = None
    last_price: float = Field(..., alias="lastPrice")
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    pre_close: Optional[float] = Field(None, alias="preClose")
    volume: Optional[int] = None
    amount: Optional[float] = None
    bid_price: List[float] = Field(..., alias="bidPrice", description="买一~五价")
    bid_vol: List[int] = Field(..., alias="bidVol", description="买一~五量")
    ask_price: List[float] = Field(..., alias="askPrice", description="卖一~五价")
    ask_vol: List[int] = Field(..., alias="askVol", description="卖一~五量")
    time: Optional[str] = None


class StockItem(BaseModel):
    """Stock basic info"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: str
    market: str
    market_name: str = Field(..., alias="marketName")


class StockListResponse(BaseModel):
    """Stock list response"""
    total: int
    stocks: List[StockItem]
    synced: bool
    block_count: int = Field(..., alias="blockCount")


class BlockStocksResponse(BaseModel):
    """Block stocks response"""
    block: str
    total: int
    stocks: List[StockItem]


class FinanceTable(BaseModel):
    """Financial data table"""
    report_date: str = Field(..., alias="reportDate")
    # Dynamic fields based on table type
    data: Dict[str, Any]


class FinanceResponse(BaseModel):
    """Finance data response"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: Optional[str] = None
    tables: Dict[str, List[Dict[str, Any]]]


class IndexOverview(BaseModel):
    """Market index overview"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: str
    close: float
    change: float
    change_pct: float = Field(..., alias="changePct")
    volume: Optional[int] = None
    amount: Optional[float] = None


class MarketOverviewResponse(BaseModel):
    """Market overview response"""
    indexes: List[IndexOverview]


class TradingDatesResponse(BaseModel):
    """Trading dates response"""
    start: str
    end: str
    trading_days: List[str] = Field(..., alias="tradingDays")
    count: int


class InstrumentDetail(BaseModel):
    """Instrument detail"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: str
    type: str
    exchange: str
    exchange_name: str = Field(..., alias="exchangeName")
    listed_date: Optional[str] = Field(None, alias="listedDate")
    delisted: bool = False


class SubscribeRequest(BaseModel):
    """Subscribe request"""
    codes: List[str]
    seconds: int = Field(default=1, ge=1, le=60)


class SubscribeResponse(BaseModel):
    """Subscribe response"""
    subscribed: List[str]
    duration: int
    tick_count: int = Field(..., alias="tickCount")
    ticks: List[TickResponse]


# ============================================================================
# Account Models
# ============================================================================

class AssetResponse(BaseModel):
    """Asset information"""
    account_id: str = Field(..., alias="accountId")
    account_type: str = Field(..., alias="accountType")
    cash: float
    frozen_cash: float = Field(..., alias="frozenCash")
    market_value: float = Field(..., alias="marketValue")
    total_asset: float = Field(..., alias="totalAsset")


class PositionItem(BaseModel):
    """Single position"""
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: Optional[str] = None
    volume: int
    can_use_volume: int = Field(..., alias="canUseVolume")
    frozen_volume: int = Field(..., alias="frozenVolume")
    yesterday_volume: int = Field(..., alias="yesterdayVolume")
    on_road_volume: int = Field(..., alias="onRoadVolume")
    open_price: float = Field(..., alias="openPrice")
    market_value: float = Field(..., alias="marketValue")


class PositionsResponse(BaseModel):
    """Positions response"""
    positions: List[PositionItem]
    total: int


class OrderItem(BaseModel):
    """Single order"""
    order_id: int = Field(..., alias="orderId")
    order_sys_id: str = Field(..., alias="orderSysId")
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: Optional[str] = None
    order_type: int = Field(..., alias="orderType")
    order_type_name: str = Field(..., alias="orderTypeName")
    order_volume: int = Field(..., alias="orderVolume")
    traded_volume: int = Field(..., alias="tradedVolume")
    traded_price: Optional[float] = Field(None, alias="tradedPrice")
    price: float
    price_type: int = Field(..., alias="priceType")
    order_status: int = Field(..., alias="orderStatus")
    order_status_name: str = Field(..., alias="orderStatusName")
    order_time: str = Field(..., alias="orderTime")
    strategy_name: str = Field("", alias="strategyName")
    order_remark: str = Field("", alias="orderRemark")
    cancelable: bool


class OrdersResponse(BaseModel):
    """Orders response"""
    orders: List[OrderItem]
    total: int


class TradeItem(BaseModel):
    """Single trade"""
    trade_id: str = Field(..., alias="tradeId")
    order_id: int = Field(..., alias="orderId")
    order_sys_id: str = Field(..., alias="orderSysId")
    code: str
    full_code: str = Field(..., alias="fullCode")
    name: Optional[str] = None
    order_type: int = Field(..., alias="orderType")
    order_type_name: str = Field(..., alias="orderTypeName")
    traded_price: float = Field(..., alias="tradedPrice")
    traded_volume: int = Field(..., alias="tradedVolume")
    traded_amount: float = Field(..., alias="tradedAmount")
    traded_time: str = Field(..., alias="tradedTime")


class TradesResponse(BaseModel):
    """Trades response"""
    trades: List[TradeItem]
    total: int


# ============================================================================
# Trade Request/Response Models
# ============================================================================

PRICE_TYPES = Literal[
    "FIX", "LATEST", "SH_CONVERT_5_CANCEL", "SH_CONVERT_5_LIMIT",
    "PEER_PRICE_FIRST", "MINE_PRICE_FIRST", "SZ_INSTBUSI_RESTCANCEL",
    "SZ_CONVERT_5_CANCEL", "SZ_FULL_OR_CANCEL"
]


class BuyRequest(BaseModel):
    """Buy order request"""
    code: str = Field(..., description="股票代码")
    volume: int = Field(..., description="买入数量，必须是100的整数倍")
    price_type: PRICE_TYPES = Field(..., alias="priceType")
    price: Optional[float] = Field(None, description="指定价格，price_type=FIX时必填")
    strategy_name: str = Field("", alias="strategyName")
    order_remark: str = Field("", alias="orderRemark")
    confirm: bool = Field(False, description="true=真正下单，false=仅预演")
    
    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v: int) -> int:
        if v % 100 != 0:
            raise ValueError('Volume must be multiple of 100')
        return v
    
    @field_validator('price')
    @classmethod
    def validate_price(cls, v: Optional[float], info) -> Optional[float]:
        if info.data.get('price_type') == 'FIX' and v is None:
            raise ValueError('Price is required when price_type is FIX')
        return v


class SellRequest(BaseModel):
    """Sell order request"""
    code: str = Field(..., description="股票代码")
    volume: int = Field(..., description="卖出数量，必须是100的整数倍")
    price_type: PRICE_TYPES = Field(..., alias="priceType")
    price: Optional[float] = Field(None, description="指定价格，price_type=FIX时必填")
    strategy_name: str = Field("", alias="strategyName")
    order_remark: str = Field("", alias="orderRemark")
    confirm: bool = Field(False, description="true=真正下单，false=仅预演")
    
    @field_validator('volume')
    @classmethod
    def validate_volume(cls, v: int) -> int:
        if v % 100 != 0:
            raise ValueError('Volume must be multiple of 100')
        return v


class CancelRequest(BaseModel):
    """Cancel order request"""
    order_id: int = Field(..., alias="orderId", description="委托编号")
    confirm: bool = Field(False, description="true=真正撤单")


class TradeResult(BaseModel):
    """Trade execution result"""
    dry_run: bool = Field(..., alias="dryRun")
    action: str
    code: str
    full_code: str = Field(..., alias="fullCode")
    volume: int
    price_type: str = Field(..., alias="priceType")
    price: Optional[float] = None
    order_id: Optional[int] = Field(None, alias="orderId")
    order_time: Optional[str] = Field(None, alias="orderTime")
    estimated_amount: Optional[float] = Field(None, alias="estimatedAmount")
    cancel_result: Optional[int] = Field(None, alias="cancelResult")
    cancel_result_name: Optional[str] = Field(None, alias="cancelResultName")
    note: Optional[str] = None


# ============================================================================
# System Models
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    qmt_connected: bool = Field(..., alias="qmtConnected")
    xtquant_available: bool = Field(..., alias="xtquantAvailable")
    account_configured: bool = Field(..., alias="accountConfigured")


class DoctorCheckItem(BaseModel):
    """Single check item"""
    name: str
    ok: bool
    detail: str


class DoctorResponse(BaseModel):
    """Doctor diagnostics response"""
    checks: List[DoctorCheckItem]
    pass_count: int = Field(..., alias="pass")
    fail_count: int = Field(..., alias="fail")
    overall: str


class StatusResponse(BaseModel):
    """Server status response"""
    version: str
    uptime: str
    started_at: str = Field(..., alias="startedAt")
    requests_total: int = Field(..., alias="requestsTotal")
    requests_success: int = Field(..., alias="requestsSuccess")
    requests_failed: int = Field(..., alias="requestsFailed")
    last_error: Optional[str] = Field(None, alias="lastError")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_schemas.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/models/ tests/qmt_server/test_schemas.py
git commit -m "feat(qmt-server): add Pydantic request/response schemas"
```

---

## Task 3: xtquant Service (Market Data)

**Files:**
- Create: `qmt_server/services/__init__.py`
- Create: `qmt_server/services/xtquant_service.py`
- Test: `tests/qmt_server/test_xtquant_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_xtquant_service.py
import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from qmt_server.services.xtquant_service import XTQuantService, get_xtquant_service


@pytest.fixture
def mock_xtdata():
    """Mock xtdata module"""
    with patch('qmt_server.services.xtquant_service.xtdata') as mock:
        mock.get_market_data_ex.return_value = pd.DataFrame({
            'open': [10.5], 'high': [10.68], 'low': [10.42], 'close': [10.55],
            'volume': [125000], 'amount': [1318750.0]
        }, index=['000001.SZ'])
        mock.get_full_tick.return_value = {
            '000001.SZ': {
                'lastPrice': 10.55,
                'open': 10.50, 'high': 10.68, 'low': 10.42, 'close': 10.55,
                'volume': 125000, 'amount': 1318750.0,
                'bidPrice': [10.55, 10.54, 10.53, 10.52, 10.51],
                'bidVol': [5000, 8000, 12000, 15000, 20000],
                'askPrice': [10.56, 10.57, 10.58, 10.59, 10.60],
                'askVol': [6000, 9000, 11000, 14000, 18000],
                'time': 1715418600000
            }
        }
        yield mock


def test_service_singleton():
    """Test service is singleton"""
    service1 = get_xtquant_service()
    service2 = get_xtquant_service()
    assert service1 is service2


def test_get_stock_list(mock_xtdata):
    """Test getting stock list"""
    service = XTQuantService()
    
    # Mock sector data
    mock_xtdata.get_sector_list.return_value = ['沪深300成分', '上证50成分']
    mock_xtdata.get_stock_list_in_sector.side_effect = lambda sector: {
        '沪深300成分': ['000001.SZ', '600519.SH'],
        '上证50成分': ['600519.SH', '601318.SH']
    }.get(sector, [])
    
    stocks = service.get_stock_list()
    
    assert len(stocks) == 3  # 3 unique stocks
    assert any(s['code'] == '000001' for s in stocks)


def test_get_quote_single(mock_xtdata):
    """Test getting single stock quote"""
    service = XTQuantService()
    quote = service.get_quote('000001')
    
    assert quote['code'] == '000001'
    assert quote['fullCode'] == '000001.SZ'
    assert 'close' in quote


def test_get_tick(mock_xtdata):
    """Test getting tick data"""
    service = XTQuantService()
    tick = service.get_tick('000001')
    
    assert tick['code'] == '000001'
    assert len(tick['bidPrice']) == 5
    assert len(tick['askPrice']) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_xtquant_service.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'qmt_server.services'"

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/services/__init__.py
from .xtquant_service import XTQuantService, get_xtquant_service
```

```python
# qmt_server/services/xtquant_service.py
"""xtquant data service wrapper"""
import sys
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd

from qmt_server.config import get_config

logger = logging.getLogger(__name__)

# Module-level xtdata reference
xtdata = None
_xtquant_available = False


def _inject_xtquant_path():
    """Inject xtquant path to sys.path"""
    config = get_config()
    if config.xtquant_path and config.xtquant_path not in sys.path:
        sys.path.append(config.xtquant_path)
        logger.info(f"Added xtquant path: {config.xtquant_path}")


def _ensure_xtdata():
    """Ensure xtdata is imported"""
    global xtdata, _xtquant_available
    
    if xtdata is not None:
        return
    
    _inject_xtquant_path()
    
    try:
        from xtquant import xtdata as xtdata_module
        xtdata = xtdata_module
        _xtquant_available = True
        logger.info("xtdata imported successfully")
    except ImportError as e:
        logger.error(f"Failed to import xtdata: {e}")
        _xtquant_available = False
        raise


class XTQuantService:
    """Service wrapper for xtquant market data"""
    
    def __init__(self):
        self._connected = False
        self._stock_cache: Dict[str, Dict] = {}
        self._last_sector_sync: Optional[datetime] = None
    
    def connect(self) -> bool:
        """Test connection to QMT"""
        try:
            _ensure_xtdata()
            # Test by getting a simple quote
            test_data = xtdata.get_market_data_ex(
                field_list=['close'],
                stock_list=['000001.SH'],
                period='1d',
                count=1
            )
            self._connected = True
            logger.info("QMT connection verified")
            return True
        except Exception as e:
            logger.error(f"QMT connection failed: {e}")
            self._connected = False
            return False
    
    def is_ready(self) -> bool:
        """Check if service is ready"""
        return _xtquant_available and self._connected
    
    def _resolve_code(self, code: str) -> str:
        """Resolve 6-digit code to full code format"""
        if '.' in code:
            return code
        
        # Determine exchange based on code prefix
        prefix = code[:3] if len(code) >= 3 else code
        
        if prefix.startswith('6'):
            return f"{code}.SH"
        elif prefix.startswith('0') or prefix.startswith('3'):
            return f"{code}.SZ"
        elif prefix.startswith('8') or prefix.startswith('4'):
            return f"{code}.BJ"
        elif code == '000001':  # Special case for 上证指数
            return f"{code}.SH"
        else:
            return f"{code}.SZ"  # Default
    
    def _code_from_full(self, full_code: str) -> str:
        """Extract 6-digit code from full code"""
        return full_code.split('.')[0]
    
    def download_sector_data(self) -> bool:
        """Download sector data from QMT"""
        try:
            _ensure_xtdata()
            xtdata.download_sector_data()
            self._last_sector_sync = datetime.now()
            logger.info("Sector data downloaded")
            return True
        except Exception as e:
            logger.error(f"Failed to download sector data: {e}")
            return False
    
    def get_stock_list(self, sync: bool = True) -> List[Dict]:
        """Get all stocks via sector traversal"""
        _ensure_xtdata()
        
        if sync or self._last_sector_sync is None:
            self.download_sector_data()
        
        sectors = xtdata.get_sector_list()
        seen_codes = set()
        stocks = []
        
        for sector in sectors:
            try:
                sector_stocks = xtdata.get_stock_list_in_sector(sector)
                for full_code in sector_stocks:
                    code = self._code_from_full(full_code)
                    if code not in seen_codes:
                        seen_codes.add(code)
                        stocks.append({
                            'code': code,
                            'fullCode': full_code,
                            'name': '',  # Name lookup requires additional API call
                            'market': full_code.split('.')[1],
                            'marketName': self._get_market_name(full_code)
                        })
            except Exception as e:
                logger.warning(f"Failed to get stocks from sector {sector}: {e}")
        
        return stocks
    
    def _get_market_name(self, full_code: str) -> str:
        """Get market name from code"""
        exchange = full_code.split('.')[1]
        names = {
            'SH': '上海证券交易所',
            'SZ': '深圳证券交易所',
            'BJ': '北京证券交易所'
        }
        return names.get(exchange, '未知交易所')
    
    def get_quote(self, code: str) -> Optional[Dict]:
        """Get single stock quote"""
        _ensure_xtdata()
        
        full_code = self._resolve_code(code)
        
        try:
            data = xtdata.get_market_data_ex(
                field_list=['open', 'high', 'low', 'close', 'preClose',
                           'volume', 'amount'],
                stock_list=[full_code],
                period='1d',
                count=1
            )
            
            if data is None or full_code not in data.index:
                return None
            
            row = data.loc[full_code]
            return {
                'code': code,
                'fullCode': full_code,
                'name': '',
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'preClose': float(row.get('preClose', 0)),
                'change': float(row.get('close', 0)) - float(row.get('preClose', 0)),
                'changePct': (float(row.get('close', 0)) / float(row.get('preClose', 1)) - 1) * 100 if row.get('preClose') else 0,
                'volume': int(row.get('volume', 0)),
                'amount': float(row.get('amount', 0))
            }
        except Exception as e:
            logger.error(f"Failed to get quote for {code}: {e}")
            return None
    
    def get_quotes_batch(self, codes: List[str]) -> List[Dict]:
        """Get multiple stock quotes"""
        _ensure_xtdata()
        
        full_codes = [self._resolve_code(c) for c in codes]
        
        try:
            data = xtdata.get_market_data_ex(
                field_list=['open', 'high', 'low', 'close', 'preClose',
                           'volume', 'amount'],
                stock_list=full_codes,
                period='1d',
                count=1
            )
            
            if data is None:
                return []
            
            results = []
            for code, full_code in zip(codes, full_codes):
                if full_code in data.index:
                    row = data.loc[full_code]
                    results.append({
                        'code': code,
                        'fullCode': full_code,
                        'name': '',
                        'close': float(row.get('close', 0)),
                        'changePct': (float(row.get('close', 0)) / float(row.get('preClose', 1)) - 1) * 100 if row.get('preClose') else 0
                    })
            
            return results
        except Exception as e:
            logger.error(f"Failed to get batch quotes: {e}")
            return []
    
    def get_tick(self, code: str) -> Optional[Dict]:
        """Get five-level tick data"""
        _ensure_xtdata()
        
        full_code = self._resolve_code(code)
        
        try:
            tick_data = xtdata.get_full_tick([full_code])
            
            if not tick_data or full_code not in tick_data:
                return None
            
            tick = tick_data[full_code]
            
            return {
                'code': code,
                'fullCode': full_code,
                'name': '',
                'lastPrice': tick.get('lastPrice', 0),
                'open': tick.get('open', 0),
                'high': tick.get('high', 0),
                'low': tick.get('low', 0),
                'preClose': tick.get('lastClose', 0),
                'volume': tick.get('volume', 0),
                'amount': tick.get('amount', 0),
                'bidPrice': list(tick.get('bidPrice', [0]*5)),
                'bidVol': list(tick.get('bidVol', [0]*5)),
                'askPrice': list(tick.get('askPrice', [0]*5)),
                'askVol': list(tick.get('askVol', [0]*5)),
                'time': str(tick.get('time', ''))
            }
        except Exception as e:
            logger.error(f"Failed to get tick for {code}: {e}")
            return None
    
    def get_kline(self, code: str, period: str = '1d',
                  count: int = 100, start: str = None, end: str = None) -> Optional[Dict]:
        """Get Kline data"""
        _ensure_xtdata()
        
        full_code = self._resolve_code(code)
        
        # Map period to xtquant format
        period_map = {
            '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '1d': '1d', '1w': '1w', '1mon': '1mon'
        }
        xt_period = period_map.get(period, '1d')
        
        try:
            # Download history data if date range specified
            if start and end:
                xtdata.download_history_data(full_code, xt_period, start, end)
            
            data = xtdata.get_market_data_ex(
                field_list=['open', 'high', 'low', 'close', 'volume', 'amount'],
                stock_list=[full_code],
                period=xt_period,
                count=count
            )
            
            if data is None or full_code not in data.index:
                return None
            
            # Convert to kline format
            df = data.reset_index() if hasattr(data, 'reset_index') else data
            klines = []
            
            # Handle multi-index DataFrame
            if isinstance(data.index, pd.MultiIndex):
                for idx, row in data.iterrows():
                    klines.append({
                        'date': str(idx[1]) if len(idx) > 1 else str(idx),
                        'open': float(row.get('open', 0)),
                        'high': float(row.get('high', 0)),
                        'low': float(row.get('low', 0)),
                        'close': float(row.get('close', 0)),
                        'volume': int(row.get('volume', 0)),
                        'amount': float(row.get('amount', 0))
                    })
            
            return {
                'code': code,
                'fullCode': full_code,
                'name': '',
                'period': period,
                'count': len(klines),
                'kline': klines
            }
        except Exception as e:
            logger.error(f"Failed to get kline for {code}: {e}")
            return None
    
    def get_sectors(self) -> List[str]:
        """Get all sector names"""
        _ensure_xtdata()
        
        try:
            if self._last_sector_sync is None:
                self.download_sector_data()
            return xtdata.get_sector_list()
        except Exception as e:
            logger.error(f"Failed to get sectors: {e}")
            return []
    
    def get_block_stocks(self, block_name: str) -> List[Dict]:
        """Get stocks in a block/sector"""
        _ensure_xtdata()
        
        try:
            full_codes = xtdata.get_stock_list_in_sector(block_name)
            return [
                {
                    'code': self._code_from_full(fc),
                    'fullCode': fc,
                    'name': '',
                    'market': fc.split('.')[1],
                    'marketName': self._get_market_name(fc)
                }
                for fc in full_codes
            ]
        except Exception as e:
            logger.error(f"Failed to get block stocks for {block_name}: {e}")
            return []


# Global service instance
_service_instance: Optional[XTQuantService] = None


def get_xtquant_service() -> XTQuantService:
    """Get global XTQuantService instance"""
    global _service_instance
    if _service_instance is None:
        _service_instance = XTQuantService()
    return _service_instance
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_xtquant_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/services/xtquant_service.py tests/qmt_server/test_xtquant_service.py
git commit -m "feat(qmt-server): add xtquant market data service"
```

---

## Task 4: Market Router (Market Data Endpoints)

**Files:**
- Create: `qmt_server/routers/__init__.py`
- Create: `qmt_server/routers/market.py`
- Test: `tests/qmt_server/test_market_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_market_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from qmt_server.main import app


client = TestClient(app)


def test_get_quote_single():
    """Test GET /market/quote/{code}"""
    with patch('qmt_server.routers.market.get_xtquant_service') as mock_get:
        mock_service = Mock()
        mock_service.get_quote.return_value = {
            'code': '000001',
            'fullCode': '000001.SZ',
            'name': '平安银行',
            'close': 10.55,
            'changePct': 0.67
        }
        mock_get.return_value = mock_service
        
        response = client.get('/api/v1/market/quote/000001')
        
        assert response.status_code == 200
        assert response.json()['success'] is True
        assert response.json()['data']['code'] == '000001'


def test_get_quote_batch():
    """Test GET /market/quote?codes=..."""
    with patch('qmt_server.routers.market.get_xtquant_service') as mock_get:
        mock_service = Mock()
        mock_service.get_quotes_batch.return_value = [
            {'code': '000001', 'fullCode': '000001.SZ', 'close': 10.55}
        ]
        mock_get.return_value = mock_service
        
        response = client.get('/api/v1/market/quote?codes=000001,600519')
        
        assert response.status_code == 200
        assert response.json()['data']['total'] == 1


def test_get_kline():
    """Test GET /market/kline/{code}"""
    with patch('qmt_server.routers.market.get_xtquant_service') as mock_get:
        mock_service = Mock()
        mock_service.get_kline.return_value = {
            'code': '000001',
            'fullCode': '000001.SZ',
            'period': '1d',
            'count': 2,
            'kline': [
                {'date': '20260501', 'open': 10.5, 'high': 10.68, 'low': 10.42, 'close': 10.55, 'volume': 125000, 'amount': 1318750.0},
                {'date': '20260502', 'open': 10.55, 'high': 10.70, 'low': 10.50, 'close': 10.62, 'volume': 98765, 'amount': 1045230.0}
            ]
        }
        mock_get.return_value = mock_service
        
        response = client.get('/api/v1/market/kline/000001?period=1d&count=2')
        
        assert response.status_code == 200
        assert len(response.json()['data']['kline']) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_market_router.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/routers/__init__.py
from .market import router as market_router
from .account import router as account_router
from .trade import router as trade_router
from .system import router as system_router
```

```python
# qmt_server/routers/market.py
"""Market data router"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException

from qmt_server.models.schemas import (
    APIResponse, QuoteResponse, KlineResponse, TickResponse,
    StockListResponse, StockItem, BlockStocksResponse,
    FinanceResponse, MarketOverviewResponse, TradingDatesResponse,
    InstrumentDetail, SubscribeRequest, SubscribeResponse
)
from qmt_server.services.xtquant_service import get_xtquant_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/market", tags=["Market"])


@router.get("/quote/{code}", response_model=APIResponse)
async def get_quote_single(code: str):
    """Get single stock quote"""
    try:
        service = get_xtquant_service()
        data = service.get_quote(code)
        
        if data is None:
            raise HTTPException(status_code=404, detail=f"Quote not found for {code}")
        
        return APIResponse(
            success=True,
            data=data,
            message=f"Get quote for {code}"
        )
    except Exception as e:
        logger.error(f"Error getting quote for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quote", response_model=APIResponse)
async def get_quote_batch(
    codes: str = Query(..., description="Comma-separated stock codes"),
    names: bool = Query(True, description="Include stock names")
):
    """Get batch stock quotes"""
    try:
        service = get_xtquant_service()
        code_list = [c.strip() for c in codes.split(',')]
        quotes = service.get_quotes_batch(code_list)
        
        return APIResponse(
            success=True,
            data={"total": len(quotes), "quotes": quotes},
            message=f"Get {len(quotes)} stock quotes"
        )
    except Exception as e:
        logger.error(f"Error getting batch quotes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/kline/{code}", response_model=APIResponse)
async def get_kline(
    code: str,
    period: str = Query('1d', description="Period: 1m,5m,15m,30m,1h,1d,1w,1mon"),
    count: int = Query(100, ge=1, le=1000),
    start: Optional[str] = Query(None, description="Start date YYYYMMDD"),
    end: Optional[str] = Query(None, description="End date YYYYMMDD"),
    download: bool = Query(True, description="Download history data first")
):
    """Get Kline data"""
    try:
        service = get_xtquant_service()
        data = service.get_kline(code, period, count, start, end)
        
        if data is None:
            raise HTTPException(status_code=404, detail=f"Kline not found for {code}")
        
        return APIResponse(
            success=True,
            data=data,
            message=f"Get {code} {count} {period} klines"
        )
    except Exception as e:
        logger.error(f"Error getting kline for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tick/{code}", response_model=APIResponse)
async def get_tick_single(code: str):
    """Get five-level tick data"""
    try:
        service = get_xtquant_service()
        data = service.get_tick(code)
        
        if data is None:
            raise HTTPException(status_code=404, detail=f"Tick not found for {code}")
        
        return APIResponse(
            success=True,
            data=data,
            message=f"Get {code} tick"
        )
    except Exception as e:
        logger.error(f"Error getting tick for {code}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tick", response_model=APIResponse)
async def get_tick_batch(codes: str = Query(..., description="Comma-separated codes")):
    """Get batch tick data"""
    try:
        service = get_xtquant_service()
        code_list = [c.strip() for c in codes.split(',')]
        ticks = [service.get_tick(c) for c in code_list]
        ticks = [t for t in ticks if t is not None]
        
        return APIResponse(
            success=True,
            data={"total": len(ticks), "ticks": ticks},
            message=f"Get {len(ticks)} tick data"
        )
    except Exception as e:
        logger.error(f"Error getting batch ticks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stock-list", response_model=APIResponse)
async def get_stock_list(
    sync: bool = Query(True, description="Sync sector data first"),
    market: str = Query('all', description="Filter by market: sh,sz,bj,all")
):
    """Get all stock list"""
    try:
        service = get_xtquant_service()
        stocks = service.get_stock_list(sync)
        
        # Filter by market if specified
        if market != 'all':
            stocks = [s for s in stocks if s['market'].lower() == market.lower()]
        
        return APIResponse(
            success=True,
            data={
                "total": len(stocks),
                "stocks": stocks[:100],  # Limit response size
                "synced": sync,
                "blockCount": len(service.get_sectors())
            },
            message=f"Get {len(stocks)} stocks"
        )
    except Exception as e:
        logger.error(f"Error getting stock list: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks", response_model=APIResponse)
async def get_blocks(
    keyword: Optional[str] = Query(None, description="Filter keyword"),
    type: str = Query('all', description="Block type: industry,concept,index,all"),
    sync: bool = Query(False, description="Force re-sync"),
    limit: int = Query(200, ge=1, le=1000)
):
    """Get block/sector list"""
    try:
        service = get_xtquant_service()
        
        if sync:
            service.download_sector_data()
        
        blocks = service.get_sectors()
        
        if keyword:
            blocks = [b for b in blocks if keyword in b]
        
        return APIResponse(
            success=True,
            data={
                "total": len(blocks),
                "returned": min(limit, len(blocks)),
                "blocks": blocks[:limit]
            },
            message=f"Get {len(blocks)} blocks"
        )
    except Exception as e:
        logger.error(f"Error getting blocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/block-stocks", response_model=APIResponse)
async def get_block_stocks(
    block: str = Query(..., description="Block name"),
    limit: int = Query(50, ge=1, le=500)
):
    """Get stocks in a block"""
    try:
        service = get_xtquant_service()
        stocks = service.get_block_stocks(block)
        
        return APIResponse(
            success=True,
            data={
                "block": block,
                "total": len(stocks),
                "stocks": stocks[:limit]
            },
            message=f"Get {len(stocks)} stocks from {block}"
        )
    except Exception as e:
        logger.error(f"Error getting block stocks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/finance/{code}", response_model=APIResponse)
async def get_finance(
    code: str,
    tables: str = Query('all', description="Tables: Income,Balance,CashFlow,Capital,PershareIndex,all"),
    limit: int = Query(4, ge=1, le=20)
):
    """Get financial data (placeholder)"""
    # TODO: Implement with xtdata.download_financial_data
    return APIResponse(
        success=True,
        data={"code": code, "tables": {}, "note": "Not yet implemented"},
        message="Financial data endpoint (placeholder)"
    )


@router.get("/market-overview", response_model=APIResponse)
async def get_market_overview():
    """Get market overview"""
    try:
        service = get_xtquant_service()
        # Get major index quotes
        indices = ['000001.SH', '399001.SZ', '399006.SZ']
        quotes = []
        
        for idx in indices:
            code = idx.split('.')[0]
            q = service.get_quote(code)
            if q:
                quotes.append(q)
        
        return APIResponse(
            success=True,
            data={"indexes": quotes},
            message="Market overview"
        )
    except Exception as e:
        logger.error(f"Error getting market overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trading-dates", response_model=APIResponse)
async def get_trading_dates(
    start: str = Query(..., description="Start date YYYYMMDD"),
    end: str = Query(..., description="End date YYYYMMDD")
):
    """Get trading dates (placeholder)"""
    # TODO: Implement with xtdata.get_trading_dates
    return APIResponse(
        success=True,
        data={"start": start, "end": end, "tradingDays": [], "count": 0},
        message="Trading dates endpoint (placeholder)"
    )


@router.get("/instrument/{code}", response_model=APIResponse)
async def get_instrument(code: str):
    """Get instrument detail"""
    try:
        service = get_xtquant_service()
        quote = service.get_quote(code)
        
        if quote is None:
            raise HTTPException(status_code=404, detail=f"Instrument not found: {code}")
        
        # Build instrument detail from quote
        instrument = {
            "code": code,
            "fullCode": quote['fullCode'],
            "name": quote.get('name', ''),
            "type": "股票",
            "exchange": quote['fullCode'].split('.')[1],
            "exchangeName": service._get_market_name(quote['fullCode']),
            "listedDate": None,
            "delisted": False
        }
        
        return APIResponse(
            success=True,
            data=instrument,
            message=f"Get instrument {code}"
        )
    except Exception as e:
        logger.error(f"Error getting instrument: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/subscribe", response_model=APIResponse)
async def subscribe(request: SubscribeRequest):
    """Subscribe to tick data (blocking mode)"""
    import asyncio
    import time
    
    try:
        service = get_xtquant_service()
        start_time = time.time()
        ticks = []
        
        # Blocking wait for specified seconds
        # Note: In real implementation, this would use xtdata.subscribe_quote
        # For now, just simulate by polling
        while time.time() - start_time < request.seconds:
            for code in request.codes:
                tick = service.get_tick(code)
                if tick:
                    ticks.append(tick)
            await asyncio.sleep(0.5)
        
        duration = int(time.time() - start_time)
        
        return APIResponse(
            success=True,
            data={
                "subscribed": request.codes,
                "duration": duration,
                "tickCount": len(ticks),
                "ticks": ticks
            },
            message=f"Subscribe {len(request.codes)} stocks for {duration}s, got {len(ticks)} ticks"
        )
    except Exception as e:
        logger.error(f"Error in subscribe: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_market_router.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/routers/market.py tests/qmt_server/test_market_router.py
git commit -m "feat(qmt-server): add market data router with all endpoints"
```

---

## Task 5: Trade Service (xttrader Wrapper)

**Files:**
- Create: `qmt_server/services/trade_service.py`
- Test: `tests/qmt_server/test_trade_service.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_trade_service.py
import pytest
from unittest.mock import Mock, patch, MagicMock

from qmt_server.services.trade_service import TradeService, get_trade_service


def test_trade_service_singleton():
    """Test trade service is singleton"""
    service1 = get_trade_service()
    service2 = get_trade_service()
    assert service1 is service2


def test_trade_service_not_ready_without_config():
    """Test service not ready without account config"""
    with patch('qmt_server.services.trade_service.get_config') as mock_config:
        mock_config.return_value = Mock(account_id='', userdata_path='')
        service = TradeService()
        assert service.is_ready() is False


def test_get_asset():
    """Test getting account asset"""
    with patch('qmt_server.services.trade_service.get_config') as mock_config:
        with patch('qmt_server.services.trade_service.xttrader') as mock_xt:
            mock_config.return_value = Mock(
                account_id='123456',
                userdata_path='D:\\test',
                account_type='STOCK'
            )
            
            mock_trader = Mock()
            mock_trader.query_stock_asset.return_value = Mock(
                m_dAccountID='123456',
                m_dAvailableCash=500000.0,
                m_dFrozenCash=10000.0,
                m_dMarketValue=2000000.0,
                m_dTotalAsset=2500000.0
            )
            mock_xt.XtQuantTrader.return_value = mock_trader
            
            service = TradeService()
            service._trader = mock_trader
            service._connected = True
            
            asset = service.get_asset()
            
            assert asset['accountId'] == '123456'
            assert asset['cash'] == 500000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_trade_service.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/services/trade_service.py
"""xttrader trading service wrapper"""
import sys
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from qmt_server.config import get_config, Config

logger = logging.getLogger(__name__)

# Module-level xttrader reference
xttrader = None
xtconstant = None
_xtt_available = False


def _ensure_xttrader():
    """Ensure xttrader is imported"""
    global xttrader, xtconstant, _xtt_available
    
    if xttrader is not None:
        return
    
    try:
        from xtquant import xttrader as xt, xtconstant as xc
        xttrader = xt
        xtconstant = xc
        _xtt_available = True
        logger.info("xttrader imported successfully")
    except ImportError as e:
        logger.error(f"Failed to import xttrader: {e}")
        _xtt_available = False
        raise


class TradeService:
    """Service wrapper for xttrader trading operations"""
    
    def __init__(self):
        self._trader = None
        self._connected = False
        self._account_id: Optional[str] = None
        self._config: Optional[Config] = None
    
    def _load_config(self):
        """Load account configuration"""
        self._config = get_config()
        self._account_id = self._config.account_id
    
    def connect(self) -> bool:
        """Connect to xttrader"""
        try:
            _ensure_xttrader()
            self._load_config()
            
            if not self._config.userdata_path or not self._account_id:
                logger.warning("Account not configured")
                return False
            
            # Create trader instance
            self._trader = xttrader.XtQuantTrader(
                self._config.userdata_path,
                int(self._account_id)
            )
            
            # Start trader
            self._trader.start()
            self._connected = True
            logger.info(f"XtQuantTrader started for account {self._account_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to xttrader: {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Disconnect from xttrader"""
        if self._trader:
            try:
                self._trader.stop()
                logger.info("XtQuantTrader stopped")
            except Exception as e:
                logger.error(f"Error stopping trader: {e}")
        self._connected = False
    
    def is_ready(self) -> bool:
        """Check if trade service is ready"""
        return _xtt_available and self._connected and self._trader is not None
    
    def _resolve_code(self, code: str) -> str:
        """Resolve 6-digit code to full code"""
        if '.' in code:
            return code
        
        prefix = code[:3] if len(code) >= 3 else code
        if prefix.startswith('6') or code == '000001':
            return f"{code}.SH"
        elif prefix.startswith('0') or prefix.startswith('3'):
            return f"{code}.SZ"
        elif prefix.startswith('8') or prefix.startswith('4'):
            return f"{code}.BJ"
        else:
            return f"{code}.SZ"
    
    def get_asset(self) -> Optional[Dict]:
        """Get account asset information"""
        if not self.is_ready():
            return None
        
        try:
            asset = self._trader.query_stock_asset(self._account_id)
            
            if asset is None:
                return None
            
            return {
                'accountId': asset.m_dAccountID,
                'accountType': self._config.account_type if self._config else 'STOCK',
                'cash': float(asset.m_dAvailableCash),
                'frozenCash': float(asset.m_dFrozenCash),
                'marketValue': float(asset.m_dMarketValue),
                'totalAsset': float(asset.m_dTotalAsset)
            }
        except Exception as e:
            logger.error(f"Failed to query asset: {e}")
            return None
    
    def get_positions(self, code: Optional[str] = None) -> List[Dict]:
        """Get positions"""
        if not self.is_ready():
            return []
        
        try:
            positions = self._trader.query_stock_positions(self._account_id)
            
            result = []
            for pos in positions:
                pos_code = pos.m_sCode
                if code and not pos_code.endswith(code):
                    continue
                
                result.append({
                    'code': code or pos_code.split('.')[0],
                    'fullCode': pos_code,
                    'name': '',
                    'volume': int(pos.m_nVolume),
                    'canUseVolume': int(pos.m_nCanUseVolume),
                    'frozenVolume': int(pos.m_nVolume) - int(pos.m_nCanUseVolume),
                    'yesterdayVolume': int(pos.m_nYesterdayVolume),
                    'onRoadVolume': int(pos.m_nOnRoadVolume),
                    'openPrice': float(pos.m_dOpenPrice),
                    'marketValue': float(pos.m_dMarketValue)
                })
            
            return result
        except Exception as e:
            logger.error(f"Failed to query positions: {e}")
            return []
    
    def get_orders(self, cancelable_only: bool = False) -> List[Dict]:
        """Get orders"""
        if not self.is_ready():
            return []
        
        try:
            if cancelable_only:
                orders = self._trader.query_stock_orders(self._account_id, cancelable_only)
            else:
                orders = self._trader.query_stock_orders(self._account_id)
            
            result = []
            for order in orders:
                # Map order type
                type_names = {23: '买入', 24: '卖出'}
                status_names = {
                    48: '未报', 49: '待报', 50: '已报', 51: '已报待撤',
                    52: '部成待撤', 53: '部撤', 54: '已撤',
                    55: '部成', 56: '已成', 57: '废单', 255: '未知'
                }
                
                result.append({
                    'orderId': int(order.m_nOrderID),
                    'orderSysId': str(order.m_strOrderSysID),
                    'code': order.m_sCode.split('.')[0],
                    'fullCode': order.m_sCode,
                    'name': '',
                    'orderType': int(order.m_nOrderType),
                    'orderTypeName': type_names.get(int(order.m_nOrderType), '未知'),
                    'orderVolume': int(order.m_nOrderVolume),
                    'tradedVolume': int(order.m_nTradedVolume),
                    'tradedPrice': float(order.m_dTradedPrice) if order.m_dTradedPrice else None,
                    'price': float(order.m_dPrice),
                    'priceType': int(order.m_nPriceType),
                    'orderStatus': int(order.m_nOrderStatus),
                    'orderStatusName': status_names.get(int(order.m_nOrderStatus), '未知'),
                    'orderTime': str(order.m_sOrderTime),
                    'strategyName': str(order.m_sStrategyName),
                    'orderRemark': str(order.m_sOrderRemark),
                    'cancelable': int(order.m_nOrderStatus) in [50, 55]  # 已报 or 部成
                })
            
            return result
        except Exception as e:
            logger.error(f"Failed to query orders: {e}")
            return []
    
    def get_trades(self) -> List[Dict]:
        """Get trades"""
        if not self.is_ready():
            return []
        
        try:
            trades = self._trader.query_stock_trades(self._account_id)
            
            result = []
            for trade in trades:
                type_names = {23: '买入', 24: '卖出'}
                
                result.append({
                    'tradeId': str(trade.m_sTradeID),
                    'orderId': int(trade.m_nOrderID),
                    'orderSysId': str(trade.m_strOrderSysID),
                    'code': trade.m_sCode.split('.')[0],
                    'fullCode': trade.m_sCode,
                    'name': '',
                    'orderType': int(trade.m_nOrderType),
                    'orderTypeName': type_names.get(int(trade.m_nOrderType), '未知'),
                    'tradedPrice': float(trade.m_dTradedPrice),
                    'tradedVolume': int(trade.m_nTradedVolume),
                    'tradedAmount': float(trade.m_dTradedAmount),
                    'tradedTime': str(trade.m_sTradedTime)
                })
            
            return result
        except Exception as e:
            logger.error(f"Failed to query trades: {e}")
            return []
    
    def buy(self, code: str, volume: int, price_type: str, price: Optional[float] = None,
            strategy_name: str = '', order_remark: str = '') -> Dict:
        """Place buy order"""
        if not self.is_ready():
            return {'success': False, 'error': 'Trade service not ready'}
        
        try:
            full_code = self._resolve_code(code)
            
            # Map price type to xtconstant
            price_type_map = {
                'FIX': xtconstant.FIX_PRICE,
                'LATEST': xtconstant.LATEST_PRICE,
                'SH_CONVERT_5_CANCEL': xtconstant.MARKET_SH_CONVERT_5_CANCEL,
                'SH_CONVERT_5_LIMIT': xtconstant.MARKET_SH_CONVERT_5_LIMIT,
                'PEER_PRICE_FIRST': xtconstant.MARKET_PEER_PRICE_FIRST,
                'MINE_PRICE_FIRST': xtconstant.MARKET_MINE_PRICE_FIRST,
                'SZ_INSTBUSI_RESTCANCEL': xtconstant.MARKET_SZ_INSTBUSI_RESTCANCEL,
                'SZ_CONVERT_5_CANCEL': xtconstant.MARKET_SZ_CONVERT_5_CANCEL,
                'SZ_FULL_OR_CANCEL': xtconstant.MARKET_SZ_FULL_OR_CANCEL
            }
            
            xt_price_type = price_type_map.get(price_type, xtconstant.FIX_PRICE)
            order_price = price if price else 0.0
            
            order_id = self._trader.order_stock(
                self._account_id,
                full_code,
                xtconstant.STOCK_BUY,
                volume,
                xt_price_type,
                order_price,
                strategy_name,
                order_remark
            )
            
            return {
                'success': order_id > 0,
                'orderId': order_id,
                'error': None if order_id > 0 else 'Order failed'
            }
        except Exception as e:
            logger.error(f"Failed to place buy order: {e}")
            return {'success': False, 'error': str(e)}
    
    def sell(self, code: str, volume: int, price_type: str, price: Optional[float] = None,
             strategy_name: str = '', order_remark: str = '') -> Dict:
        """Place sell order"""
        if not self.is_ready():
            return {'success': False, 'error': 'Trade service not ready'}
        
        try:
            full_code = self._resolve_code(code)
            
            price_type_map = {
                'FIX': xtconstant.FIX_PRICE,
                'LATEST': xtconstant.LATEST_PRICE,
                'SH_CONVERT_5_CANCEL': xtconstant.MARKET_SH_CONVERT_5_CANCEL,
                'SH_CONVERT_5_LIMIT': xtconstant.MARKET_SH_CONVERT_5_LIMIT,
                'PEER_PRICE_FIRST': xtconstant.MARKET_PEER_PRICE_FIRST,
                'MINE_PRICE_FIRST': xtconstant.MARKET_MINE_PRICE_FIRST,
                'SZ_INSTBUSI_RESTCANCEL': xtconstant.MARKET_SZ_INSTBUSI_RESTCANCEL,
                'SZ_CONVERT_5_CANCEL': xtconstant.MARKET_SZ_CONVERT_5_CANCEL,
                'SZ_FULL_OR_CANCEL': xtconstant.MARKET_SZ_FULL_OR_CANCEL
            }
            
            xt_price_type = price_type_map.get(price_type, xtconstant.FIX_PRICE)
            order_price = price if price else 0.0
            
            order_id = self._trader.order_stock(
                self._account_id,
                full_code,
                xtconstant.STOCK_SELL,
                volume,
                xt_price_type,
                order_price,
                strategy_name,
                order_remark
            )
            
            return {
                'success': order_id > 0,
                'orderId': order_id,
                'error': None if order_id > 0 else 'Order failed'
            }
        except Exception as e:
            logger.error(f"Failed to place sell order: {e}")
            return {'success': False, 'error': str(e)}
    
    def cancel(self, order_id: int) -> Dict:
        """Cancel order"""
        if not self.is_ready():
            return {'success': False, 'error': 'Trade service not ready', 'result': -3}
        
        try:
            result = self._trader.cancel_order_stock(self._account_id, order_id)
            
            result_names = {
                0: '撤单成功',
                -1: '托已完成，不可撤',
                -2: '未找到对应委托',
                -3: '账号未登录'
            }
            
            return {
                'success': result == 0,
                'result': result,
                'resultName': result_names.get(result, '未知'),
                'error': None if result == 0 else result_names.get(result, 'Unknown')
            }
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")
            return {'success': False, 'error': str(e), 'result': -3}


# Global service instance
_trade_service: Optional[TradeService] = None


def get_trade_service() -> TradeService:
    """Get global TradeService instance"""
    global _trade_service
    if _trade_service is None:
        _trade_service = TradeService()
    return _trade_service
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_trade_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/services/trade_service.py tests/qmt_server/test_trade_service.py
git commit -m "feat(qmt-server): add trade service with xttrader wrapper"
```

---

## Task 6: Account Router (Account Query Endpoints)

**Files:**
- Create: `qmt_server/routers/account.py`
- Test: `tests/qmt_server/test_account_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_account_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from qmt_server.main import app


client = TestClient(app)


def test_get_asset():
    """Test GET /account/asset"""
    with patch('qmt_server.routers.account.get_trade_service') as mock_get:
        mock_service = Mock()
        mock_service.is_ready.return_value = True
        mock_service.get_asset.return_value = {
            'accountId': '123456',
            'accountType': 'STOCK',
            'cash': 500000.0,
            'frozenCash': 10000.0,
            'marketValue': 2000000.0,
            'totalAsset': 2500000.0
        }
        mock_get.return_value = mock_service
        
        response = client.get('/api/v1/account/asset')
        
        assert response.status_code == 200
        assert response.json()['success'] is True
        assert response.json()['data']['cash'] == 500000.0


def test_get_positions():
    """Test GET /account/positions"""
    with patch('qmt_server.routers.account.get_trade_service') as mock_get:
        mock_service = Mock()
        mock_service.is_ready.return_value = True
        mock_service.get_positions.return_value = [
            {
                'code': '600519',
                'fullCode': '600519.SH',
                'name': '贵州茅台',
                'volume': 1000,
                'canUseVolume': 800
            }
        ]
        mock_get.return_value = mock_service
        
        response = client.get('/api/v1/account/positions')
        
        assert response.status_code == 200
        assert len(response.json()['data']['positions']) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_account_router.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/routers/account.py
"""Account router"""
import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from qmt_server.models.schemas import (
    APIResponse, AssetResponse, PositionsResponse, OrdersResponse, TradesResponse
)
from qmt_server.services.trade_service import get_trade_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/account", tags=["Account"])


@router.get("/asset", response_model=APIResponse)
async def get_asset():
    """Get account asset information"""
    try:
        service = get_trade_service()
        
        if not service.is_ready():
            raise HTTPException(
                status_code=503,
                detail="Account not configured or trade service not connected"
            )
        
        asset = service.get_asset()
        
        if asset is None:
            raise HTTPException(status_code=404, detail="Asset information not available")
        
        return APIResponse(
            success=True,
            data=asset,
            message="Asset information"
        )
    except Exception as e:
        logger.error(f"Error getting asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=APIResponse)
async def get_positions(
    code: Optional[str] = Query(None, description="Filter by stock code")
):
    """Get positions"""
    try:
        service = get_trade_service()
        
        if not service.is_ready():
            raise HTTPException(
                status_code=503,
                detail="Account not configured or trade service not connected"
            )
        
        positions = service.get_positions(code)
        
        return APIResponse(
            success=True,
            data={"positions": positions, "total": len(positions)},
            message="Positions query"
        )
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders", response_model=APIResponse)
async def get_orders(
    cancelable_only: bool = Query(False, alias="cancelable_only")
):
    """Get orders"""
    try:
        service = get_trade_service()
        
        if not service.is_ready():
            raise HTTPException(
                status_code=503,
                detail="Account not configured or trade service not connected"
            )
        
        orders = service.get_orders(cancelable_only)
        
        return APIResponse(
            success=True,
            data={"orders": orders, "total": len(orders)},
            message="Today's orders"
        )
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades", response_model=APIResponse)
async def get_trades():
    """Get trades"""
    try:
        service = get_trade_service()
        
        if not service.is_ready():
            raise HTTPException(
                status_code=503,
                detail="Account not configured or trade service not connected"
            )
        
        trades = service.get_trades()
        
        return APIResponse(
            success=True,
            data={"trades": trades, "total": len(trades)},
            message="Today's trades"
        )
    except Exception as e:
        logger.error(f"Error getting trades: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_account_router.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/routers/account.py tests/qmt_server/test_account_router.py
git commit -m "feat(qmt-server): add account router for asset/positions/orders/trades"
```

---

## Task 7: Trade Router (Trading Endpoints)

**Files:**
- Create: `qmt_server/routers/trade.py`
- Test: `tests/qmt_server/test_trade_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_trade_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from qmt_server.main import app


client = TestClient(app)


def test_buy_dry_run():
    """Test POST /trade/buy without confirm"""
    with patch('qmt_server.routers.trade.get_trade_service') as mock_get:
        mock_service = Mock()
        mock_service.is_ready.return_value = True
        mock_get.return_value = mock_service
        
        response = client.post('/api/v1/trade/buy', json={
            'code': '000001',
            'volume': 1000,
            'priceType': 'FIX',
            'price': 10.55,
            'confirm': False
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['dryRun'] is True
        assert 'estimatedAmount' in data['data']


def test_buy_confirmed():
    """Test POST /trade/buy with confirm=true"""
    with patch('qmt_server.routers.trade.get_trade_service') as mock_get:
        mock_service = Mock()
        mock_service.is_ready.return_value = True
        mock_service.buy.return_value = {
            'success': True,
            'orderId': 123456789
        }
        mock_get.return_value = mock_service
        
        response = client.post('/api/v1/trade/buy', json={
            'code': '000001',
            'volume': 1000,
            'priceType': 'FIX',
            'price': 10.55,
            'confirm': True
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['dryRun'] is False
        assert data['data']['orderId'] == 123456789


def test_cancel_order():
    """Test POST /trade/cancel"""
    with patch('qmt_server.routers.trade.get_trade_service') as mock_get:
        mock_service = Mock()
        mock_service.is_ready.return_value = True
        mock_service.cancel.return_value = {
            'success': True,
            'result': 0,
            'resultName': '撤单成功'
        }
        mock_get.return_value = mock_service
        
        response = client.post('/api/v1/trade/cancel', json={
            'orderId': 123456789,
            'confirm': True
        })
        
        assert response.status_code == 200
        assert response.json()['data']['cancelResult'] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_trade_router.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/routers/trade.py
"""Trade router"""
import logging
from fastapi import APIRouter, HTTPException

from qmt_server.models.schemas import (
    APIResponse, BuyRequest, SellRequest, CancelRequest, TradeResult
)
from qmt_server.services.trade_service import get_trade_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trade", tags=["Trade"])


@router.post("/buy", response_model=APIResponse)
async def buy(request: BuyRequest):
    """Place buy order"""
    try:
        service = get_trade_service()
        full_code = service._resolve_code(request.code) if service.is_ready() else f"{request.code}.SZ"
        
        # Calculate estimated amount for dry run
        estimated_amount = request.volume * (request.price or 0)
        
        if not request.confirm:
            # Dry run mode
            return APIResponse(
                success=True,
                data={
                    "dryRun": True,
                    "action": "BUY",
                    "code": request.code,
                    "fullCode": full_code,
                    "volume": request.volume,
                    "priceType": request.price_type,
                    "price": request.price,
                    "estimatedAmount": estimated_amount,
                    "note": "confirm=false, dry run only, order not sent to QMT"
                },
                message="Dry run (order not placed)"
            )
        
        # Real order
        if not service.is_ready():
            raise HTTPException(
                status_code=503,
                detail="Trade service not ready"
            )
        
        result = service.buy(
            code=request.code,
            volume=request.volume,
            price_type=request.price_type,
            price=request.price,
            strategy_name=request.strategy_name,
            order_remark=request.order_remark
        )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Order failed'))
        
        return APIResponse(
            success=True,
            data={
                "dryRun": False,
                "action": "BUY",
                "code": request.code,
                "fullCode": full_code,
                "volume": request.volume,
                "priceType": request.price_type,
                "price": request.price,
                "orderId": result['orderId'],
                "orderTime": logger.info("Order placed") or None  # Will be set by caller
            },
            message=f"Buy order submitted, orderId={result['orderId']}"
        )
    except Exception as e:
        logger.error(f"Error placing buy order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sell", response_model=APIResponse)
async def sell(request: SellRequest):
    """Place sell order"""
    try:
        service = get_trade_service()
        full_code = service._resolve_code(request.code) if service.is_ready() else f"{request.code}.SZ"
        
        estimated_amount = request.volume * (request.price or 0)
        
        if not request.confirm:
            return APIResponse(
                success=True,
                data={
                    "dryRun": True,
                    "action": "SELL",
                    "code": request.code,
                    "fullCode": full_code,
                    "volume": request.volume,
                    "priceType": request.price_type,
                    "price": request.price,
                    "estimatedAmount": estimated_amount,
                    "note": "confirm=false, dry run only, order not sent to QMT"
                },
                message="Dry run (order not placed)"
            )
        
        if not service.is_ready():
            raise HTTPException(status_code=503, detail="Trade service not ready")
        
        result = service.sell(
            code=request.code,
            volume=request.volume,
            price_type=request.price_type,
            price=request.price,
            strategy_name=request.strategy_name,
            order_remark=request.order_remark
        )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Order failed'))
        
        return APIResponse(
            success=True,
            data={
                "dryRun": False,
                "action": "SELL",
                "code": request.code,
                "fullCode": full_code,
                "volume": request.volume,
                "priceType": request.price_type,
                "price": request.price,
                "orderId": result['orderId']
            },
            message=f"Sell order submitted, orderId={result['orderId']}"
        )
    except Exception as e:
        logger.error(f"Error placing sell order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel", response_model=APIResponse)
async def cancel(request: CancelRequest):
    """Cancel order"""
    try:
        service = get_trade_service()
        
        if not request.confirm:
            return APIResponse(
                success=True,
                data={
                    "dryRun": True,
                    "action": "CANCEL",
                    "orderId": request.order_id,
                    "note": "confirm=false, dry run only, order not cancelled"
                },
                message="Dry run (order not cancelled)"
            )
        
        if not service.is_ready():
            raise HTTPException(status_code=503, detail="Trade service not ready")
        
        result = service.cancel(request.order_id)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=result.get('error', 'Cancel failed'))
        
        return APIResponse(
            success=True,
            data={
                "dryRun": False,
                "action": "CANCEL",
                "orderId": request.order_id,
                "cancelResult": result['result'],
                "cancelResultName": result['resultName']
            },
            message="Cancel order success"
        )
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_trade_router.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/routers/trade.py tests/qmt_server/test_trade_router.py
git commit -m "feat(qmt-server): add trade router with buy/sell/cancel endpoints"
```

---

## Task 8: System Router (Health/Doctor/Status)

**Files:**
- Create: `qmt_server/routers/system.py`
- Create: `qmt_server/middleware/rate_limit.py`
- Test: `tests/qmt_server/test_system_router.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_system_router.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from qmt_server.main import app


client = TestClient(app)


def test_health_check():
    """Test GET /system/health"""
    with patch('qmt_server.routers.system.get_xtquant_service') as mock_xt, \
         patch('qmt_server.routers.system.get_trade_service') as mock_trade:
        
        mock_xt_service = Mock()
        mock_xt_service.is_ready.return_value = True
        mock_xt.return_value = mock_xt_service
        
        mock_trade_service = Mock()
        mock_trade_service.is_ready.return_value = True
        mock_trade.return_value = mock_trade_service
        
        response = client.get('/api/v1/system/health')
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['status'] == 'healthy'


def test_doctor():
    """Test GET /system/doctor"""
    response = client.get('/api/v1/system/doctor')
    
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert 'checks' in data['data']


def test_status():
    """Test GET /system/status"""
    response = client.get('/api/v1/system/status')
    
    assert response.status_code == 200
    data = response.json()
    assert data['success'] is True
    assert 'version' in data['data']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_system_router.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/middleware/rate_limit.py
"""Rate limiting middleware"""
import time
import logging
from typing import Dict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from qmt_server.config import get_config

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, list] = {}
    
    async def dispatch(self, request: Request, call_next):
        config = get_config()
        
        if not config.rate_limit_enabled:
            return await call_next(request)
        
        # Get client IP
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        
        # Clean old requests
        if client_ip in self.requests:
            self.requests[client_ip] = [
                t for t in self.requests[client_ip]
                if now - t < 60
            ]
        else:
            self.requests[client_ip] = []
        
        # Check rate limit
        if len(self.requests.get(client_ip, [])) >= config.rate_limit_rpm:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Record request
        self.requests.setdefault(client_ip, []).append(now)
        
        return await call_next(request)
```

```python
# qmt_server/routers/system.py
"""System router"""
import sys
import platform
import logging
import time
from datetime import datetime
from typing import List, Dict
from fastapi import APIRouter, HTTPException

from qmt_server.models.schemas import (
    APIResponse, HealthCheckResponse, DoctorCheckItem, DoctorResponse, StatusResponse
)
from qmt_server.services.xtquant_service import get_xtquant_service, _xtquant_available
from qmt_server.services.trade_service import get_trade_service, _xtt_available
from qmt_server.config import get_config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/system", tags=["System"])

# Server startup time
START_TIME = datetime.now()

# Request counters
REQUESTS_TOTAL = 0
REQUESTS_SUCCESS = 0
REQUESTS_FAILED = 0
LAST_ERROR: str = ""


def increment_request(success: bool, error: str = ""):
    """Increment request counters"""
    global REQUESTS_TOTAL, REQUESTS_SUCCESS, REQUESTS_FAILED, LAST_ERROR
    REQUESTS_TOTAL += 1
    if success:
        REQUESTS_SUCCESS += 1
    else:
        REQUESTS_FAILED += 1
        LAST_ERROR = f"{datetime.now().isoformat()} {error}"


@router.get("/health", response_model=APIResponse)
async def health_check():
    """Health check endpoint"""
    try:
        xt_service = get_xtquant_service()
        trade_service = get_trade_service()
        config = get_config()
        
        qmt_connected = xt_service.is_ready()
        account_configured = bool(config.account_id and config.userdata_path)
        
        status = "healthy" if qmt_connected else "degraded"
        
        return APIResponse(
            success=True,
            data={
                "status": status,
                "qmtConnected": qmt_connected,
                "xtquantAvailable": _xtquant_available,
                "accountConfigured": account_configured
            },
            message="System healthy" if status == "healthy" else "System degraded - QMT not connected"
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/doctor", response_model=APIResponse)
async def doctor():
    """Environment diagnostics"""
    import sys
    import os
    
    checks: List[DoctorCheckItem] = []
    config = get_config()
    
    # 1. Platform check
    platform_ok = sys.platform == "win32"
    checks.append({
        "name": "平台检查",
        "ok": platform_ok,
        "detail": f"Windows" if platform_ok else f"{sys.platform} (QMT仅支持Windows)"
    })
    
    # 2. Python version check
    py_version = platform.python_version()
    version_ok = py_version.startswith("3.10") or py_version.startswith("3.11")
    checks.append({
        "name": "Python版本",
        "ok": version_ok,
        "detail": f"{py_version} {'✓' if version_ok else 'xtquant可能需要3.10/3.11'}"
    })
    
    # 3. xtquant path check
    path_ok = bool(config.xtquant_path)
    checks.append({
        "name": "xtquant路径配置",
        "ok": path_ok,
        "detail": config.xtquant_path if path_ok else "未配置 (QMT_XTQUANT_PATH)"
    })
    
    # 4. xtquant import check
    import_ok = _xtquant_available
    checks.append({
        "name": "xtquant导入",
        "ok": import_ok,
        "detail": "导入成功" if import_ok else "导入失败"
    })
    
    # 5. QMT connection check
    conn_ok = False
    conn_detail = "未测试"
    if import_ok:
        try:
            xt_service = get_xtquant_service()
            conn_ok = xt_service.connect()
            conn_detail = "QMT终端连接成功" if conn_ok else "QMT终端未运行"
        except Exception as e:
            conn_detail = str(e)
    
    checks.append({
        "name": "QMT终端连接",
        "ok": conn_ok,
        "detail": conn_detail
    })
    
    # 6. Account configuration check
    account_ok = bool(config.account_id and config.userdata_path)
    checks.append({
        "name": "账号配置",
        "ok": account_ok,
        "detail": f"account_id: {config.account_id[:4]}****" if account_ok else "未配置"
    })
    
    pass_count = sum(1 for c in checks if c["ok"])
    fail_count = len(checks) - pass_count
    overall = "pass" if fail_count == 0 else "fail" if fail_count > 1 else "warning"
    
    return APIResponse(
        success=True,
        data={
            "checks": checks,
            "pass": pass_count,
            "fail": fail_count,
            "overall": overall
        },
        message=f"Diagnostics complete: {overall}"
    )


@router.get("/status", response_model=APIResponse)
async def status():
    """Server status"""
    uptime = datetime.now() - START_TIME
    uptime_str = f"{uptime.days}d{uptime.seconds//3600}h{(uptime.seconds//60)%60}m"
    
    return APIResponse(
        success=True,
        data={
            "version": "1.0.0",
            "uptime": uptime_str,
            "startedAt": START_TIME.isoformat(),
            "requestsTotal": REQUESTS_TOTAL,
            "requestsSuccess": REQUESTS_SUCCESS,
            "requestsFailed": REQUESTS_FAILED,
            "lastError": LAST_ERROR if LAST_ERROR else None
        },
        message="Server status"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_system_router.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/routers/system.py qmt_server/middleware/rate_limit.py tests/qmt_server/test_system_router.py
git commit -m "feat(qmt-server): add system router with health/doctor/status endpoints"
```

---

## Task 9: Main Application Entry Point

**Files:**
- Create: `qmt_server/main.py`
- Test: `tests/qmt_server/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/qmt_server/test_main.py
import pytest
from fastapi.testclient import TestClient

from qmt_server.main import app


client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint redirects to docs"""
    response = client.get("/")
    assert response.status_code in [200, 307, 308]  # OK or redirect


def test_api_v1_prefix():
    """Test API v1 prefix exists"""
    response = client.get("/api/v1/system/health")
    # May fail due to QMT not being available, but should not 404
    assert response.status_code != 404


def test_cors_headers():
    """Test CORS is configured"""
    response = client.options("/", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    })
    assert "access-control-allow-origin" in response.headers or response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/qmt_server/test_main.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# qmt_server/main.py
"""QMT HTTP Server main entry point"""
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from qmt_server.config import get_config, reload_config
from qmt_server.routers import market_router, account_router, trade_router, system_router
from qmt_server.middleware.rate_limit import RateLimitMiddleware
from qmt_server.services.xtquant_service import get_xtquant_service
from qmt_server.services.trade_service import get_trade_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("QMT Server starting up...")
    config = get_config()
    
    # Log configuration
    logger.info(f"Server config: host={config.host}, port={config.port}")
    logger.info(f"QMT config: xtquant_path={config.xtquant_path}, account_id={config.account_id}")
    
    # Try to connect to xtquant
    try:
        xt_service = get_xtquant_service()
        if xt_service.connect():
            logger.info("✅ Connected to QMT via xtquant")
        else:
            logger.warning("⚠️ Failed to connect to QMT - check if QMT terminal is running")
    except Exception as e:
        logger.error(f"❌ Failed to initialize xtquant: {e}")
    
    # Try to connect to xttrader (if configured)
    if config.account_id and config.userdata_path:
        try:
            trade_service = get_trade_service()
            if trade_service.connect():
                logger.info("✅ Connected to xttrader")
            else:
                logger.warning("⚠️ Failed to connect to xttrader")
        except Exception as e:
            logger.error(f"❌ Failed to initialize xttrader: {e}")
    
    yield
    
    # Shutdown
    logger.info("QMT Server shutting down...")
    try:
        trade_service = get_trade_service()
        trade_service.disconnect()
    except:
        pass


# Create FastAPI app
app = FastAPI(
    title="QMT HTTP Server",
    description="HTTP API wrapper for QMT (Quantitative Trading) xtquant library",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limit middleware
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(market_router, prefix="/api/v1")
app.include_router(account_router, prefix="/api/v1")
app.include_router(trade_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint - redirect to docs"""
    return {
        "message": "QMT HTTP Server",
        "docs": "/docs",
        "health": "/api/v1/system/health"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "timestamp": "",
            "error": {
                "code": "INTERNAL_ERROR",
                "message": str(exc)
            }
        }
    )


def main():
    """Main entry point"""
    config = get_config()
    
    import uvicorn
    uvicorn.run(
        "qmt_server.main:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower()
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/qmt_server/test_main.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add qmt_server/main.py tests/qmt_server/test_main.py
git commit -m "feat(qmt-server): add main FastAPI application entry point"
```

---

## Task 10: Update TradingAgents-CN QMT Adapter

**Files:**
- Modify: `app/services/data_sources/qmt_adapter.py`
- Test: `tests/test_qmt_adapter_http.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_qmt_adapter_http.py
import pytest
from unittest.mock import Mock, patch

from app.services.data_sources.qmt_adapter import QMTAdapter


def test_qmt_adapter_init():
    """Test QMT adapter initialization"""
    with patch('app.services.data_sources.qmt_adapter.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            QMT_SERVER_URL="http://localhost:8080",
            QMT_SERVER_TIMEOUT=30
        )
        
        adapter = QMTAdapter()
        assert adapter.server_url == "http://localhost:8080"
        assert adapter.timeout == 30


def test_is_available():
    """Test is_available checks server health"""
    with patch('app.services.data_sources.qmt_adapter.get_settings') as mock_settings, \
         patch('requests.get') as mock_get:
        
        mock_settings.return_value = Mock(
            QMT_SERVER_URL="http://localhost:8080",
            QMT_SERVER_TIMEOUT=30
        )
        mock_get.return_value = Mock(
            json=lambda: {"success": True, "data": {"qmtConnected": True}},
            status_code=200
        )
        
        adapter = QMTAdapter()
        assert adapter.is_available() is True


def test_get_realtime_quotes():
    """Test get_realtime_quotes via HTTP"""
    with patch('app.services.data_sources.qmt_adapter.get_settings') as mock_settings, \
         patch('requests.get') as mock_get:
        
        mock_settings.return_value = Mock(
            QMT_SERVER_URL="http://localhost:8080",
            QMT_SERVER_TIMEOUT=30
        )
        mock_get.return_value = Mock(
            json=lambda: {
                "success": True,
                "data": {
                    "quotes": [
                        {"code": "000001", "fullCode": "000001.SZ", "close": 10.55}
                    ]
                }
            },
            status_code=200
        )
        
        adapter = QMTAdapter()
        quotes = adapter.get_realtime_quotes()
        
        assert quotes is not None
        assert len(quotes) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_qmt_adapter_http.py -v`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
# app/services/data_sources/qmt_adapter.py
"""QMT HTTP Client Adapter for TradingAgents-CN

Connects to remote QMT HTTP Server instead of local xtquant.
"""
import logging
from typing import Optional, Dict, Any, List
import requests

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class QMTAdapter:
    """QMT HTTP Client - connects to remote QMT Server"""
    
    name = "qmt"
    _priority = 4
    
    def __init__(self):
        settings = get_settings()
        self.server_url = getattr(settings, 'QMT_SERVER_URL', 'http://localhost:8080')
        self.timeout = getattr(settings, 'QMT_SERVER_TIMEOUT', 30)
        self._session = requests.Session()
    
    def _request(self, method: str, path: str, **kwargs) -> Optional[Dict]:
        """Make HTTP request to QMT Server"""
        url = f"{self.server_url}/api/v1{path}"
        try:
            response = self._session.request(
                method, url,
                timeout=self.timeout,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"QMT Server request failed: {e}")
            return None
    
    def is_available(self) -> bool:
        """Check if QMT Server is available"""
        try:
            result = self._request("GET", "/system/health")
            if result and result.get("success"):
                return result.get("data", {}).get("qmtConnected", False)
            return False
        except Exception as e:
            logger.debug(f"QMT health check failed: {e}")
            return False
    
    def get_stock_list(self) -> Optional[List[Dict]]:
        """Get stock list via HTTP"""
        result = self._request("GET", "/market/stock-list?sync=false")
        if result and result.get("success"):
            return result.get("data", {}).get("stocks", [])
        return None
    
    def get_realtime_quotes(self, codes: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Get realtime quotes via HTTP"""
        if codes:
            codes_str = ",".join(codes)
            result = self._request("GET", f"/market/quote?codes={codes_str}")
        else:
            result = self._request("GET", "/market/quote?codes=all")
        
        if result and result.get("success"):
            quotes = result.get("data", {}).get("quotes", [])
            return {q["code"]: q for q in quotes}
        return None
    
    def get_kline(self, code: str, period: str = "1d",
                  start_date: Optional[str] = None,
                  end_date: Optional[str] = None) -> Optional[List[Dict]]:
        """Get Kline data via HTTP"""
        # Map period to server format
        period_map = {"day": "1d", "week": "1w", "month": "1mon"}
        server_period = period_map.get(period, period)
        
        params = f"period={server_period}&count=1000"
        if start_date:
            params += f"&start={start_date}"
        if end_date:
            params += f"&end={end_date}"
        
        result = self._request("GET", f"/market/kline/{code}?{params}")
        if result and result.get("success"):
            return result.get("data", {}).get("kline", [])
        return None
    
    def get_daily_basic(self, code: str) -> Optional[Dict]:
        """QMT doesn't provide PE/PB data"""
        return None
    
    def get_news(self, start_date: Optional[str] = None,
                 end_date: Optional[str] = None) -> Optional[List[Dict]]:
        """QMT doesn't provide news data"""
        return None
    
    def find_latest_trade_date(self) -> Optional[str]:
        """Find latest trade date via market overview"""
        result = self._request("GET", "/market/quote/000001")
        if result and result.get("success"):
            return result.get("data", {}).get("date")
        return None
    
    # Trade methods (for trading operations)
    def get_asset(self) -> Optional[Dict]:
        """Get account asset"""
        result = self._request("GET", "/account/asset")
        if result and result.get("success"):
            return result.get("data")
        return None
    
    def get_positions(self, code: Optional[str] = None) -> List[Dict]:
        """Get positions"""
        params = f"?code={code}" if code else ""
        result = self._request("GET", f"/account/positions{params}")
        if result and result.get("success"):
            return result.get("data", {}).get("positions", [])
        return []
    
    def buy(self, code: str, volume: int, price_type: str = "FIX",
            price: Optional[float] = None) -> Optional[Dict]:
        """Place buy order"""
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
    
    def sell(self, code: str, volume: int, price_type: str = "FIX",
             price: Optional[float] = None) -> Optional[Dict]:
        """Place sell order"""
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
    
    def cancel(self, order_id: int) -> Optional[Dict]:
        """Cancel order"""
        payload = {"orderId": order_id, "confirm": True}
        result = self._request("POST", "/trade/cancel", json=payload)
        if result and result.get("success"):
            return result.get("data")
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_qmt_adapter_http.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/data_sources/qmt_adapter.py tests/test_qmt_adapter_http.py
git commit -m "feat(qmt-server): update QMT adapter to HTTP client mode"
```

---

## Task 11: Add Configuration to TradingAgents-CN

**Files:**
- Modify: `app/core/config.py`
- Test: Tests should pass

- [ ] **Step 1: Add QMT Server configuration**

```python
# Add to app/core/config.py in the Config class

# QMT Server configuration (HTTP client mode)
QMT_SERVER_URL: str = Field(default="http://localhost:8080", description="QMT HTTP Server URL")
QMT_SERVER_TIMEOUT: int = Field(default=30, description="QMT HTTP request timeout in seconds")
QMT_SERVER_ENABLED: bool = Field(default=True, description="Enable QMT HTTP client")
```

- [ ] **Step 2: Update manager.py to use new adapter**

The manager should already use QMTAdapter - verify it works with HTTP mode.

- [ ] **Step 3: Commit**

```bash
git add app/core/config.py
git commit -m "feat(qmt-server): add QMT Server HTTP client configuration"
```

---

## Summary

This plan implements the QMT HTTP Server with the following components:

1. **Server (qmt_server/)**:
   - `config.py` - Configuration management
   - `models/schemas.py` - Pydantic models for all APIs
   - `services/xtquant_service.py` - xtdata wrapper for market data
   - `services/trade_service.py` - xttrader wrapper for trading
   - `routers/market.py` - 13 market data endpoints
   - `routers/account.py` - 4 account query endpoints
   - `routers/trade.py` - 3 trading endpoints with dry-run protection
   - `routers/system.py` - Health, doctor, status endpoints
   - `middleware/rate_limit.py` - Rate limiting
   - `main.py` - FastAPI entry point

2. **Client (app/services/data_sources/)**:
   - Modified `qmt_adapter.py` to use HTTP instead of local xtquant

3. **Configuration**:
   - Added `QMT_SERVER_URL`, `QMT_SERVER_TIMEOUT` settings

---

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-05-11-qmt-server.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach would you prefer?
