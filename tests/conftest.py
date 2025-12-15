"""Pytest configuration and fixtures."""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

# Set test environment variables before importing settings
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test_bot_token")
os.environ.setdefault("TELEGRAM_CHANNEL_ID", "test_channel_id")


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    return str(cache_dir)


@pytest.fixture
def mock_moex_response():
    """Mock MOEX API response."""
    return {
        "index": {"data": [["test"]]},
    }


@pytest.fixture
def mock_instruments_response():
    """Mock instruments API response."""
    return {
        "securities": {
            "columns": ["SECID", "SHORTNAME", "LOTSIZE"],
            "data": [
                ["SBER", "Сбербанк", 1],
                ["GAZP", "Газпром", 1],
                ["LKOH", "Лукойл", 1],
            ],
        },
    }


@pytest.fixture
def mock_ohlcv_response():
    """Mock OHLCV API response."""
    return {
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
                ["2024-01-03 10:00:00", "252.5", "253.0", "254.0", "252.0", "1200000", "4800"],
            ],
        },
    }


@pytest.fixture
def mock_quote_response():
    """Mock real-time quote API response."""
    return {
        "marketdata": {
            "columns": ["LAST", "BID", "OFFER", "VOLUME"],
            "data": [
                ["253.5", "253.4", "253.6", "5000"],
            ],
        },
    }


@pytest.fixture
def mock_requests_session():
    """Mock requests session."""
    with patch("src.data.collector.requests.Session") as mock_session:
        session = Mock()
        mock_session.return_value = session
        yield session

