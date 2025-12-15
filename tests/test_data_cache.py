"""Tests for data cache module."""

import time
from pathlib import Path

import pandas as pd
import pytest

from src.data.cache import DataCache


class TestDataCache:
    """Test DataCache class."""

    def test_initialization(self, temp_cache_dir):
        """Test cache initialization."""
        cache = DataCache(cache_dir=temp_cache_dir)
        assert cache.cache_dir == Path(temp_cache_dir)
        assert cache.cache_dir.exists()

    def test_get_cache_path(self, temp_cache_dir):
        """Test cache path generation."""
        cache = DataCache(cache_dir=temp_cache_dir)
        path = cache._get_cache_path("SBER", "daily")
        expected = Path(temp_cache_dir) / "SBER_daily.parquet"
        assert path == expected

    def test_set_and_get_cache(self, temp_cache_dir):
        """Test setting and getting cached data."""
        cache = DataCache(cache_dir=temp_cache_dir)

        # Create test data
        df = pd.DataFrame(
            {
                "open": [250.0, 251.0, 252.0],
                "close": [250.5, 251.5, 252.5],
                "volume": [1000, 1100, 1200],
            }
        )

        # Set cache
        result = cache.set("SBER", "daily", df)
        assert result is True

        # Get cache
        cached_df = cache.get("SBER", "daily", max_age_minutes=10)
        assert cached_df is not None
        assert len(cached_df) == len(df)
        pd.testing.assert_frame_equal(cached_df, df)

    def test_get_cache_missing(self, temp_cache_dir):
        """Test getting non-existent cache."""
        cache = DataCache(cache_dir=temp_cache_dir)
        result = cache.get("NONEXISTENT", "daily")
        assert result is None

    def test_get_cache_expired(self, temp_cache_dir):
        """Test getting expired cache."""
        cache = DataCache(cache_dir=temp_cache_dir)

        # Create and cache data
        df = pd.DataFrame({"value": [1, 2, 3]})
        cache.set("SBER", "daily", df)

        # Wait a moment and set very short expiration
        time.sleep(0.1)
        result = cache.get("SBER", "daily", max_age_minutes=0.001)

        # Should be None due to expiration
        assert result is None

    def test_get_cache_fresh(self, temp_cache_dir):
        """Test getting fresh cache."""
        cache = DataCache(cache_dir=temp_cache_dir)

        # Create and cache data
        df = pd.DataFrame({"value": [1, 2, 3]})
        cache.set("SBER", "daily", df)

        # Get immediately with reasonable expiration
        result = cache.get("SBER", "daily", max_age_minutes=10)

        assert result is not None
        assert len(result) == len(df)

    def test_clear_cache_all(self, temp_cache_dir):
        """Test clearing all cache files."""
        cache = DataCache(cache_dir=temp_cache_dir)

        # Create multiple cache files
        df1 = pd.DataFrame({"value": [1, 2]})
        df2 = pd.DataFrame({"value": [3, 4]})
        cache.set("SBER", "daily", df1)
        cache.set("GAZP", "daily", df2)

        # Clear all
        deleted = cache.clear()
        assert deleted == 2

        # Verify files are gone
        assert cache.get("SBER", "daily") is None
        assert cache.get("GAZP", "daily") is None

    def test_clear_cache_symbol(self, temp_cache_dir):
        """Test clearing cache for specific symbol."""
        cache = DataCache(cache_dir=temp_cache_dir)

        # Create cache files for multiple symbols
        df1 = pd.DataFrame({"value": [1, 2]})
        df2 = pd.DataFrame({"value": [3, 4]})
        cache.set("SBER", "daily", df1)
        cache.set("SBER", "hourly", df1)
        cache.set("GAZP", "daily", df2)

        # Clear only SBER
        deleted = cache.clear(symbol="SBER")
        assert deleted == 2

        # Verify SBER is gone but GAZP remains
        assert cache.get("SBER", "daily") is None
        assert cache.get("SBER", "hourly") is None
        assert cache.get("GAZP", "daily") is not None

