"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest

from src.config import Settings, get_settings


class TestSettings:
    """Test Settings class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()
        assert settings.moex_api_url == "https://iss.moex.com/iss"
        assert settings.moex_api_timeout == 30
        assert settings.entry_threshold == 2.0
        assert settings.exit_threshold == 0.0
        assert settings.stop_loss_threshold == 3.0
        assert settings.lookback_period == 60
        assert settings.spread_window == 20
        assert settings.max_position_size == 10000.0
        assert settings.max_open_positions == 5
        assert settings.log_level == "INFO"
        assert settings.data_update_interval == 300
        assert settings.analysis_interval == 900

    def test_environment_variable_loading(self):
        """Test loading from environment variables."""
        with patch.dict(
            os.environ,
            {
                "MOEX_API_URL": "https://test.moex.com",
                "MOEX_API_TIMEOUT": "60",
                "ENTRY_THRESHOLD": "2.5",
            },
        ):
            settings = Settings()
            assert settings.moex_api_url == "https://test.moex.com"
            assert settings.moex_api_timeout == 60
            assert settings.entry_threshold == 2.5

    def test_validate_telegram_config_valid(self):
        """Test Telegram config validation with valid values."""
        settings = Settings(
            telegram_bot_token="test_token",
            telegram_channel_id="test_channel",
        )
        assert settings.validate_telegram_config() is True

    def test_validate_telegram_config_invalid(self):
        """Test Telegram config validation with invalid values."""
        settings = Settings(
            telegram_bot_token="",
            telegram_channel_id="",
        )
        assert settings.validate_telegram_config() is False

        settings = Settings(
            telegram_bot_token="test_token",
            telegram_channel_id="",
        )
        assert settings.validate_telegram_config() is False

    def test_validate_tbank_config_valid(self):
        """Test T-Bank config validation with valid values."""
        settings = Settings(
            tbank_api_url="https://api.tbank.ru",
            tbank_api_key="test_key",
            tbank_api_secret="test_secret",
        )
        assert settings.validate_tbank_config() is True

    def test_validate_tbank_config_invalid(self):
        """Test T-Bank config validation with invalid values."""
        settings = Settings()
        assert settings.validate_tbank_config() is False

        settings = Settings(
            tbank_api_url="https://api.tbank.ru",
            tbank_api_key="",
            tbank_api_secret="",
        )
        assert settings.validate_tbank_config() is False

    def test_get_settings_cached(self):
        """Test that get_settings returns cached instance."""
        # Clear cache
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

