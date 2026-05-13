"""Tests for QMT Server Pydantic schemas"""
import pytest
from datetime import datetime

from qmt_server.models.schemas import (
    APIResponse, QuoteData, TickResponse, KlineItem, BuyRequest, SellRequest,
    AssetResponse, PositionItem, HealthCheckResponse
)


class TestAPIResponse:
    """Test API response models"""

    def test_api_response_success(self):
        """Test successful API response"""
        response = APIResponse(
            success=True,
            data={"test": "value"},
            message="Success"
        )
        assert response.success is True
        assert response.error is None
        assert response.timestamp is not None

    def test_api_response_error(self):
        """Test error API response"""
        response = APIResponse(
            success=False,
            error={"code": "ERROR", "message": "Something went wrong"},
            message="Failed"
        )
        assert response.success is False
        assert response.error is not None


class TestQuoteData:
    """Test quote data models"""

    def test_quote_data_creation(self):
        """Test creating quote data"""
        quote = QuoteData(
            code="000001",
            full_code="000001.SZ",
            name="平安银行",
            close=10.55,
            volume=1000000
        )
        assert quote.code == "000001"
        assert quote.full_code == "000001.SZ"
        assert quote.close == 10.55

    def test_quote_data_optional_fields(self):
        """Test quote with optional fields"""
        quote = QuoteData(
            code="000001",
            full_code="000001.SZ",
            close=10.55
        )
        assert quote.open is None
        assert quote.high is None


class TestTickResponse:
    """Test tick data models"""

    def test_tick_response_creation(self):
        """Test creating tick response"""
        tick = TickResponse(
            code="000001",
            full_code="000001.SZ",
            last_price=10.55,
            bid_price=[10.54, 10.53, 10.52, 10.51, 10.50],
            bid_vol=[100, 200, 300, 400, 500],
            ask_price=[10.56, 10.57, 10.58, 10.59, 10.60],
            ask_vol=[150, 250, 350, 450, 550]
        )
        assert tick.code == "000001"
        assert len(tick.bid_price) == 5
        assert len(tick.ask_price) == 5


class TestKlineItem:
    """Test kline item models"""

    def test_kline_item_creation(self):
        """Test creating kline item"""
        kline = KlineItem(
            date="20260501",
            open=10.50,
            high=10.68,
            low=10.42,
            close=10.55,
            volume=125000,
            amount=1318750.0
        )
        assert kline.date == "20260501"
        assert kline.close == 10.55


class TestBuyRequest:
    """Test buy request validation"""

    def test_buy_request_valid(self):
        """Test valid buy request"""
        req = BuyRequest(
            code="000001",
            volume=1000,
            price_type="FIX",
            price=10.55
        )
        assert req.code == "000001"
        assert req.volume == 1000
        assert req.confirm is False

    def test_buy_request_volume_validation(self):
        """Test volume must be multiple of 100"""
        with pytest.raises(ValueError):
            BuyRequest(
                code="000001",
                volume=150,
                price_type="FIX",
                price=10.55
            )

    def test_buy_request_price_required_for_fix(self):
        """Test price required when price_type is FIX"""
        with pytest.raises(ValueError):
            BuyRequest(
                code="000001",
                volume=1000,
                price_type="FIX"
            )


class TestSellRequest:
    """Test sell request validation"""

    def test_sell_request_valid(self):
        """Test valid sell request"""
        req = SellRequest(
            code="000001",
            volume=1000,
            price_type="LATEST"
        )
        assert req.code == "000001"
        assert req.volume == 1000


class TestAssetResponse:
    """Test asset response models"""

    def test_asset_response_creation(self):
        """Test creating asset response"""
        asset = AssetResponse(
            account_id="123456",
            account_type="STOCK",
            cash=500000.0,
            frozen_cash=10000.0,
            market_value=2000000.0,
            total_asset=2500000.0
        )
        assert asset.account_id == "123456"
        assert asset.total_asset == 2500000.0


class TestPositionItem:
    """Test position item models"""

    def test_position_item_creation(self):
        """Test creating position item"""
        pos = PositionItem(
            code="600519",
            full_code="600519.SH",
            name="贵州茅台",
            volume=1000,
            can_use_volume=800,
            frozen_volume=200,
            yesterday_volume=1000,
            on_road_volume=0,
            open_price=1800.0,
            market_value=1850000.0
        )
        assert pos.code == "600519"
        assert pos.volume == 1000


class TestHealthCheckResponse:
    """Test health check response"""

    def test_health_check_response(self):
        """Test health check response"""
        health = HealthCheckResponse(
            status="healthy",
            qmt_connected=True,
            xtquant_available=True,
            account_configured=True
        )
        assert health.status == "healthy"
        assert health.qmt_connected is True
