"""Tests for QMT Server configuration"""
import os
import pytest

from qmt_server.config import Config, get_config, reload_config


class TestConfig:
    """Test configuration management"""

    def test_config_loads_from_env(self):
        """Test config loads from environment variables"""
        os.environ['QMT_XTQUANT_PATH'] = 'D:\\test\\xtquant'
        os.environ['QMT_SERVER_PORT'] = '9090'

        config = reload_config()

        assert config.xtquant_path == 'D:\\test\\xtquant'
        assert config.port == 9090

    def test_config_default_values(self):
        """Test config has sensible defaults"""
        # Clear env vars
        for key in ['QMT_XTQUANT_PATH', 'QMT_SERVER_PORT']:
            os.environ.pop(key, None)

        config = reload_config()

        assert config.host == '0.0.0.0'
        assert config.port == 8080
        assert config.log_level == 'INFO'
        assert config.rate_limit_enabled is True
        assert config.rate_limit_rpm == 60

    def test_config_singleton(self):
        """Test config is singleton via get_config"""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_config_account_settings(self):
        """Test account configuration"""
        os.environ['QMT_ACCOUNT_ID'] = '12345678'
        os.environ['QMT_USERDATA_PATH'] = 'D:\\QMT\\userdata'

        config = reload_config()

        assert config.account_id == '12345678'
        assert config.userdata_path == 'D:\\QMT\\userdata'
