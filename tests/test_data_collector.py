"""Tests for MOEXDataCollector."""

from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from src.data.cache import DataCache
from src.data.collector import MOEXDataCollector


class TestMOEXDataCollector:
    """Test suite for MOEXDataCollector."""

    def test_make_request_retries_success(
        self,
        mock_requests_session,
        mock_moex_response,
    ):
        """Ensure retries happen and succeed after transient error."""
        response_success = Mock()
        response_success.raise_for_status.return_value = None
        response_success.json.return_value = mock_moex_response

        mock_requests_session.get.side_effect = [
            requests.exceptions.Timeout("transient"),
            response_success,
        ]

        collector = MOEXDataCollector(
            session=mock_requests_session,
            enable_cache=False,
            max_retries=2,
            retry_backoff=0,
        )

        data = collector._make_request("index.json")

        assert data == mock_moex_response
        assert mock_requests_session.get.call_count == 2

    def test_make_request_gives_none_after_retries(self, mock_requests_session):
        """Return None when all retries fail."""
        mock_requests_session.get.side_effect = requests.exceptions.ConnectionError("boom")

        collector = MOEXDataCollector(
            session=mock_requests_session,
            enable_cache=False,
            max_retries=2,
            retry_backoff=0,
        )

        data = collector._make_request("index.json")

        assert data is None
        assert mock_requests_session.get.call_count == 2

    def test_get_instruments_parses_and_caches(
        self,
        temp_cache_dir,
        mock_requests_session,
        mock_instruments_response,
    ):
        """Fetch instruments, parse response, and store cache."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = mock_instruments_response
        mock_requests_session.get.return_value = response

        cache = DataCache(cache_dir=temp_cache_dir)
        collector = MOEXDataCollector(
            cache=cache,
            session=mock_requests_session,
            enable_cache=True,
            cache_ttl_minutes=10,
        )

        df = collector.get_instruments()

        assert df is not None
        assert "SECID" in df.columns
        assert len(df) == 3

        cached = cache.get("instruments_shares_TQBR", "list", max_age_minutes=10)
        assert cached is not None
        assert len(cached) == len(df)

    def test_get_ohlcv_uses_cache(
        self,
        temp_cache_dir,
    ):
        """Return cached OHLCV data without calling API."""
        cache = DataCache(cache_dir=temp_cache_dir)
        cached_df = pd.DataFrame(
            {
                "open": [1, 2],
                "close": [1.1, 2.2],
                "volume": [100, 200],
            },
            index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
        )
        cache.set("SBER", "ohlcv_24", cached_df)

        session = Mock()
        collector = MOEXDataCollector(
            cache=cache,
            session=session,
            enable_cache=True,
            cache_ttl_minutes=10,
        )

        df = collector.get_ohlcv("SBER", interval=24, use_cache=True)

        assert df is not None
        assert len(df) == len(cached_df)
        session.get.assert_not_called()

    def test_get_ohlcv_fetches_and_caches(
        self,
        temp_cache_dir,
        mock_requests_session,
        mock_ohlcv_response,
    ):
        """Fetch OHLCV data, parse, and cache."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = mock_ohlcv_response
        mock_requests_session.get.return_value = response

        cache = DataCache(cache_dir=temp_cache_dir)
        collector = MOEXDataCollector(
            cache=cache,
            session=mock_requests_session,
            enable_cache=True,
            cache_ttl_minutes=10,
        )

        df = collector.get_ohlcv("SBER", interval=24, use_cache=False)

        assert df is not None
        assert "open" in df.columns
        assert len(df) == 3
        assert mock_requests_session.get.call_count == 1

        cached = cache.get("SBER", "ohlcv_24", max_age_minutes=10)
        assert cached is not None
        assert len(cached) == len(df)

    def test_realtime_quote(self, mock_requests_session, mock_quote_response):
        """Fetch real-time quote successfully."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = mock_quote_response
        mock_requests_session.get.return_value = response

        collector = MOEXDataCollector(
            session=mock_requests_session,
            enable_cache=False,
        )

        quote = collector.get_realtime_quote("SBER")

        assert quote is not None
        assert quote.get("LAST") == mock_quote_response["marketdata"]["data"][0][0]

    def test_test_connection(self, mock_requests_session, mock_moex_response):
        """Test connection success path."""
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = mock_moex_response
        mock_requests_session.get.return_value = response

        collector = MOEXDataCollector(
            session=mock_requests_session,
            enable_cache=False,
        )

        assert collector.test_connection() is True

