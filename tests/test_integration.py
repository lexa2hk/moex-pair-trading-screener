"""Integration tests for main components."""

from unittest.mock import Mock, patch

import pytest

from src.config import get_settings
from src.data.cache import DataCache
from src.data.collector import MOEXDataCollector
from src.utils.logger import setup_logger


class TestIntegration:
    """Integration tests for happy path scenarios."""

    @pytest.fixture
    def mock_collector_responses(self):
        """Mock all collector responses."""
        return {
            "index": {"data": [["test"]]},
            "instruments": {
                "securities": {
                    "columns": ["SECID", "SHORTNAME"],
                    "data": [["SBER", "Сбербанк"], ["GAZP", "Газпром"]],
                },
            },
            "ohlcv": {
                "candles": {
                    "columns": [
                        "begin",
                        "open",
                        "close",
                        "high",
                        "low",
                        "value",
                        "volume",
                    ],
                    "data": [
                        ["2024-01-01 10:00:00", "250.5", "251.0", "252.0", "250.0", "1000000", "4000"],
                        ["2024-01-02 10:00:00", "251.0", "252.5", "253.0", "250.5", "1100000", "4400"],
                    ],
                },
            },
            "quote": {
                "marketdata": {
                    "columns": ["LAST", "BID", "OFFER"],
                    "data": [["253.5", "253.4", "253.6"]],
                },
            },
        }

    def test_full_workflow(
        self, temp_cache_dir, mock_collector_responses
    ):
        """Test complete workflow: config -> collector -> cache."""
        # Setup logger
        logger = setup_logger(log_level="INFO", log_file=None)

        # Load settings
        settings = get_settings()
        assert settings is not None

        # Initialize collector
        collector = MOEXDataCollector()

        # Mock API responses
        def mock_request(endpoint, params=None):
            # Order matters: more specific matches first
            if "index" in endpoint:
                return mock_collector_responses["index"]
            if "candles" in endpoint:
                return mock_collector_responses["ohlcv"]
            if "marketdata" in str(params):
                return mock_collector_responses["quote"]
            if "securities" in endpoint:
                return mock_collector_responses["instruments"]
            return None

        collector._make_request = Mock(side_effect=mock_request)

        # Test connection
        assert collector.test_connection() is True

        # Fetch instruments
        instruments = collector.get_instruments()
        assert instruments is not None
        assert len(instruments) == 2

        # Fetch OHLCV data
        ohlcv = collector.get_ohlcv("SBER", limit=2)
        assert ohlcv is not None
        assert len(ohlcv) == 2

        # Initialize cache
        cache = DataCache(cache_dir=temp_cache_dir)

        # Cache the data
        assert cache.set("SBER", "daily", ohlcv) is True

        # Retrieve from cache
        cached_data = cache.get("SBER", "daily", max_age_minutes=10)
        assert cached_data is not None
        assert len(cached_data) == len(ohlcv)

        # Fetch real-time quote
        quote = collector.get_realtime_quote("SBER")
        assert quote is not None

        logger.info("Integration test completed successfully")

    def test_settings_validation(self):
        """Test settings validation methods."""
        # Test with valid Telegram config
        settings = get_settings()
        # Note: This will use environment variables from conftest
        # In real scenario, you'd set them explicitly
        assert hasattr(settings, "validate_telegram_config")

        # Test with invalid T-Bank config (default)
        assert settings.validate_tbank_config() is False

    def test_collector_with_cache(
        self, temp_cache_dir, mock_collector_responses
    ):
        """Test collector integration with cache."""
        collector = MOEXDataCollector()
        cache = DataCache(cache_dir=temp_cache_dir)

        # Mock OHLCV response
        collector._make_request = Mock(
            return_value=mock_collector_responses["ohlcv"]
        )

        # First fetch - should come from API
        ohlcv1 = collector.get_ohlcv("SBER", limit=2)
        assert ohlcv1 is not None

        # Cache it
        cache.set("SBER", "daily", ohlcv1)

        # Second fetch - should come from cache
        ohlcv2 = cache.get("SBER", "daily", max_age_minutes=10)
        assert ohlcv2 is not None
        assert len(ohlcv1) == len(ohlcv2)

