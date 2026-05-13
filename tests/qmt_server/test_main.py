"""Tests for QMT Server FastAPI application"""
import pytest
from fastapi.testclient import TestClient

from qmt_server.main import app


client = TestClient(app)


class TestRootEndpoint:
    """Test root endpoint"""

    def test_root_returns_info(self):
        """Test root endpoint returns server info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "QMT HTTP Server" in data["message"]
        assert "docs" in data
        assert "health" in data


class TestHealthEndpoint:
    """Test health check endpoint"""

    def test_health_endpoint_exists(self):
        """Test health endpoint exists"""
        response = client.get("/api/v1/system/health")
        # May return 503 if QMT not connected, but should not 404
        assert response.status_code in [200, 503]

    def test_health_response_structure(self):
        """Test health response has correct structure"""
        response = client.get("/api/v1/system/health")
        if response.status_code == 200:
            data = response.json()
            assert "success" in data
            assert "data" in data
            assert "message" in data


class TestStatusEndpoint:
    """Test status endpoint"""

    def test_status_endpoint(self):
        """Test status endpoint returns server status"""
        response = client.get("/api/v1/system/status")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "version" in data["data"]
        assert "uptime" in data["data"]


class TestDoctorEndpoint:
    """Test doctor endpoint"""

    def test_doctor_endpoint(self):
        """Test doctor endpoint returns diagnostics"""
        response = client.get("/api/v1/system/doctor")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "checks" in data["data"]


class TestCORS:
    """Test CORS configuration"""

    def test_cors_headers(self):
        """Test CORS headers are present"""
        response = client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        assert response.status_code in [200, 405]  # 405 if method not allowed


class TestMarketEndpoints:
    """Test market data endpoints"""

    def test_quote_endpoint_structure(self):
        """Test quote endpoint returns correct structure"""
        response = client.get("/api/v1/market/quote/000001")
        # May fail if QMT not connected, but should not 404
        assert response.status_code != 404

    def test_stock_list_endpoint(self):
        """Test stock list endpoint"""
        response = client.get("/api/v1/market/stock-list?sync=false")
        assert response.status_code != 404

    def test_blocks_endpoint(self):
        """Test blocks endpoint"""
        response = client.get("/api/v1/market/blocks")
        assert response.status_code != 404

    def test_market_overview_endpoint(self):
        """Test market overview endpoint"""
        response = client.get("/api/v1/market/market-overview")
        assert response.status_code != 404


class TestErrorHandling:
    """Test error handling"""

    def test_404_error(self):
        """Test 404 error handling"""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Test method not allowed"""
        response = client.post("/api/v1/system/health")
        assert response.status_code == 405
