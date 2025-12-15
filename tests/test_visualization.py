"""Tests for data collection visualization.

These tests fetch real data from MOEX API and generate visualizations
to verify data quality and collection functionality.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import mplfinance as mpf
import numpy as np
import pandas as pd
import pytest

from src.data.collector import MOEXDataCollector


# Output directory for generated charts
CHARTS_DIR = Path(__file__).parent.parent / "charts"


@pytest.fixture(scope="module")
def collector():
    """Create a real data collector for integration tests."""
    return MOEXDataCollector(enable_cache=True)


@pytest.fixture(scope="module", autouse=True)
def setup_charts_dir():
    """Ensure charts output directory exists."""
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Optionally clean up after tests
    # import shutil
    # shutil.rmtree(CHARTS_DIR, ignore_errors=True)


class TestDataCollectionVisualization:
    """Visual tests for data collection functionality."""

    @pytest.mark.integration
    @pytest.mark.slow
    def test_fetch_and_visualize_instruments(self, collector):
        """Fetch instruments list and visualize market composition."""
        df = collector.get_instruments(market="shares", board="TQBR")

        assert df is not None, "Failed to fetch instruments"
        assert len(df) > 0, "No instruments returned"

        print(f"\n📊 Fetched {len(df)} instruments from MOEX TQBR board")
        print(f"Columns: {list(df.columns)}")

        # Create visualization of market composition
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle("MOEX TQBR Instruments Overview", fontsize=14, fontweight="bold")

        # Plot 1: Top instruments by some metric if available
        if "SECID" in df.columns:
            # Show first 20 tickers
            top_tickers = df["SECID"].head(20)
            ax1 = axes[0]
            ax1.barh(range(len(top_tickers)), range(len(top_tickers), 0, -1), color="#2E86AB")
            ax1.set_yticks(range(len(top_tickers)))
            ax1.set_yticklabels(top_tickers)
            ax1.set_xlabel("Rank")
            ax1.set_title("Sample Instruments (First 20)")
            ax1.invert_yaxis()

        # Plot 2: Data availability summary
        ax2 = axes[1]
        col_counts = df.notna().sum()
        ax2.barh(col_counts.index[:15], col_counts.values[:15], color="#A23B72")
        ax2.set_xlabel("Non-null Count")
        ax2.set_title("Data Completeness by Column")

        plt.tight_layout()
        chart_path = CHARTS_DIR / "instruments_overview.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"✅ Chart saved: {chart_path}")
        assert chart_path.exists()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_fetch_and_visualize_ohlcv_single_stock(self, collector):
        """Fetch OHLCV data for a single stock and create candlestick chart."""
        symbol = "SBER"
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        df = collector.get_ohlcv(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=24,  # Daily
            limit=100,
            use_cache=False,  # Force fresh data for visualization
        )

        assert df is not None, f"Failed to fetch OHLCV for {symbol}"
        assert len(df) > 0, f"No OHLCV data returned for {symbol}"

        print(f"\n📈 Fetched {len(df)} candles for {symbol}")
        print(f"Date range: {df.index.min()} to {df.index.max()}")
        print(f"Columns: {list(df.columns)}")
        print(f"\nSample data:\n{df.head()}")

        # Prepare data for mplfinance (requires specific column names)
        ohlcv = df.copy()

        # Ensure we have the required columns
        required_cols = {"open", "high", "low", "close"}
        if not required_cols.issubset(set(ohlcv.columns)):
            print(f"⚠️ Missing columns for candlestick: {required_cols - set(ohlcv.columns)}")
            # Create simple line chart instead
            fig, ax = plt.subplots(figsize=(12, 6))
            if "close" in ohlcv.columns:
                ax.plot(ohlcv.index, ohlcv["close"], label="Close", color="#2E86AB", linewidth=1.5)
            ax.set_title(f"{symbol} Price History")
            ax.set_xlabel("Date")
            ax.set_ylabel("Price")
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.xticks(rotation=45)
        else:
            # Rename columns to standard OHLC format for mplfinance
            ohlcv = ohlcv.rename(
                columns={
                    "open": "Open",
                    "high": "High",
                    "low": "Low",
                    "close": "Close",
                    "volume": "Volume",
                }
            )

            # Create candlestick chart with custom style
            mc = mpf.make_marketcolors(
                up="#26A69A",
                down="#EF5350",
                edge="inherit",
                wick="inherit",
                volume="in",
            )
            style = mpf.make_mpf_style(
                marketcolors=mc,
                gridstyle=":",
                gridcolor="#E0E0E0",
                facecolor="#FAFAFA",
            )

            # Determine if we have volume data
            has_volume = "Volume" in ohlcv.columns and ohlcv["Volume"].notna().any()

            plot_kwargs = {
                "type": "candle",
                "style": style,
                "title": f"\n{symbol} - Daily OHLCV Data",
                "ylabel": "Price (RUB)",
                "figsize": (14, 8),
                "returnfig": True,
            }
            if has_volume:
                plot_kwargs["volume"] = True
                plot_kwargs["ylabel_lower"] = "Volume"

            fig, axes = mpf.plot(ohlcv, **plot_kwargs)

        chart_path = CHARTS_DIR / f"{symbol}_candlestick.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"✅ Candlestick chart saved: {chart_path}")
        assert chart_path.exists()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_fetch_and_visualize_multiple_stocks(self, collector):
        """Fetch and compare OHLCV data for multiple stocks."""
        symbols = ["SBER", "GAZP", "LKOH", "VTBR", "ROSN"]
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

        stock_data = {}
        for symbol in symbols:
            df = collector.get_ohlcv(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=24,
                limit=100,
                use_cache=True,
            )
            if df is not None and len(df) > 0 and "close" in df.columns:
                stock_data[symbol] = df
                print(f"✅ {symbol}: {len(df)} candles")
            else:
                print(f"⚠️ {symbol}: No data or missing close column")

        assert len(stock_data) >= 2, "Need at least 2 stocks for comparison"

        # Create comparison visualization
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("MOEX Blue Chips Comparison", fontsize=14, fontweight="bold")

        # Plot 1: Normalized price comparison
        ax1 = axes[0, 0]
        colors = plt.cm.Set2(np.linspace(0, 1, len(stock_data)))
        for (symbol, df), color in zip(stock_data.items(), colors):
            normalized = df["close"] / df["close"].iloc[0] * 100
            ax1.plot(df.index, normalized, label=symbol, linewidth=1.5, color=color)
        ax1.set_title("Normalized Price (Base = 100)")
        ax1.set_xlabel("Date")
        ax1.set_ylabel("Normalized Price")
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)
        ax1.tick_params(axis="x", rotation=45)

        # Plot 2: Daily returns distribution
        ax2 = axes[0, 1]
        returns_data = []
        labels = []
        for symbol, df in stock_data.items():
            returns = df["close"].pct_change().dropna() * 100
            returns_data.append(returns.values)
            labels.append(symbol)
        ax2.boxplot(returns_data, tick_labels=labels)
        ax2.set_title("Daily Returns Distribution (%)")
        ax2.set_ylabel("Return %")
        ax2.axhline(y=0, color="red", linestyle="--", alpha=0.5)
        ax2.grid(True, alpha=0.3, axis="y")

        # Plot 3: Volatility comparison (rolling std)
        ax3 = axes[1, 0]
        for (symbol, df), color in zip(stock_data.items(), colors):
            returns = df["close"].pct_change()
            volatility = returns.rolling(window=10).std() * np.sqrt(252) * 100
            ax3.plot(df.index, volatility, label=symbol, linewidth=1.5, color=color)
        ax3.set_title("Rolling 10-day Volatility (Annualized %)")
        ax3.set_xlabel("Date")
        ax3.set_ylabel("Volatility %")
        ax3.legend(loc="upper left")
        ax3.grid(True, alpha=0.3)
        ax3.tick_params(axis="x", rotation=45)

        # Plot 4: Volume comparison
        ax4 = axes[1, 1]
        if all("volume" in df.columns for df in stock_data.values()):
            avg_volumes = {s: df["volume"].mean() for s, df in stock_data.items()}
            bars = ax4.bar(avg_volumes.keys(), avg_volumes.values(), color=colors[: len(avg_volumes)])
            ax4.set_title("Average Daily Volume")
            ax4.set_ylabel("Volume")
            ax4.tick_params(axis="x", rotation=45)
            # Add value labels on bars
            for bar, vol in zip(bars, avg_volumes.values()):
                ax4.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{vol / 1e6:.1f}M",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )
        else:
            ax4.text(0.5, 0.5, "Volume data not available", ha="center", va="center")
            ax4.set_title("Average Daily Volume")

        plt.tight_layout()
        chart_path = CHARTS_DIR / "multi_stock_comparison.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"\n✅ Multi-stock comparison saved: {chart_path}")
        assert chart_path.exists()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_fetch_and_visualize_realtime_quotes(self, collector):
        """Fetch real-time quotes and visualize bid/ask spread."""
        symbols = ["SBER", "GAZP", "LKOH", "VTBR", "ROSN"]
        quotes = {}

        for symbol in symbols:
            quote = collector.get_realtime_quote(symbol)
            if quote:
                quotes[symbol] = quote
                print(f"✅ {symbol}: LAST={quote.get('LAST')}")
            else:
                print(f"⚠️ {symbol}: No quote data")

        if len(quotes) < 2:
            pytest.skip("Not enough real-time quotes available")

        # Create visualization
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        fig.suptitle("MOEX Real-time Market Data", fontsize=14, fontweight="bold")

        # Extract prices
        symbols_list = list(quotes.keys())
        last_prices = [float(quotes[s].get("LAST", 0) or 0) for s in symbols_list]
        bids = [float(quotes[s].get("BID", 0) or 0) for s in symbols_list]
        offers = [float(quotes[s].get("OFFER", 0) or 0) for s in symbols_list]

        # Plot 1: Last prices
        ax1 = axes[0]
        bars = ax1.bar(symbols_list, last_prices, color="#2E86AB")
        ax1.set_title("Last Traded Price")
        ax1.set_ylabel("Price (RUB)")
        ax1.tick_params(axis="x", rotation=45)
        for bar, price in zip(bars, last_prices):
            if price > 0:
                ax1.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{price:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

        # Plot 2: Bid/Ask spread
        ax2 = axes[1]
        x = np.arange(len(symbols_list))
        width = 0.35
        bars1 = ax2.bar(x - width / 2, bids, width, label="Bid", color="#26A69A")
        bars2 = ax2.bar(x + width / 2, offers, width, label="Ask", color="#EF5350")
        ax2.set_title("Bid/Ask Prices")
        ax2.set_ylabel("Price (RUB)")
        ax2.set_xticks(x)
        ax2.set_xticklabels(symbols_list, rotation=45)
        ax2.legend()

        plt.tight_layout()
        chart_path = CHARTS_DIR / "realtime_quotes.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"\n✅ Real-time quotes chart saved: {chart_path}")
        assert chart_path.exists()

    @pytest.mark.integration
    @pytest.mark.slow
    def test_data_quality_visualization(self, collector):
        """Visualize data quality metrics for collected data."""
        symbol = "SBER"
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

        df = collector.get_ohlcv(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            interval=24,
            limit=200,
            use_cache=False,
        )

        if df is None or len(df) == 0:
            pytest.skip(f"No OHLCV data available for {symbol}")

        print(f"\n🔍 Data Quality Analysis for {symbol}")
        print(f"Total rows: {len(df)}")
        print(f"Date range: {df.index.min()} to {df.index.max()}")

        # Create quality metrics visualization
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f"{symbol} Data Quality Analysis", fontsize=14, fontweight="bold")

        # Plot 1: Missing data heatmap
        ax1 = axes[0, 0]
        missing_pct = df.isna().sum() / len(df) * 100
        bars = ax1.barh(missing_pct.index, missing_pct.values, color="#EF5350")
        ax1.set_xlabel("Missing Data %")
        ax1.set_title("Data Completeness by Column")
        ax1.set_xlim(0, 100)
        for bar, pct in zip(bars, missing_pct.values):
            ax1.text(
                bar.get_width() + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{pct:.1f}%",
                va="center",
                fontsize=9,
            )

        # Plot 2: Price anomalies (outliers)
        ax2 = axes[0, 1]
        if "close" in df.columns:
            close = df["close"].dropna()
            returns = close.pct_change().dropna() * 100

            # Highlight outliers (> 3 std)
            mean_ret = returns.mean()
            std_ret = returns.std()
            outliers = np.abs(returns - mean_ret) > 3 * std_ret

            ax2.scatter(
                returns.index[~outliers],
                returns[~outliers],
                c="#2E86AB",
                alpha=0.5,
                s=20,
                label="Normal",
            )
            ax2.scatter(
                returns.index[outliers],
                returns[outliers],
                c="#EF5350",
                s=50,
                label=f"Outliers ({outliers.sum()})",
                marker="x",
            )
            ax2.axhline(y=mean_ret, color="green", linestyle="--", alpha=0.7, label="Mean")
            ax2.axhline(y=mean_ret + 3 * std_ret, color="red", linestyle=":", alpha=0.7)
            ax2.axhline(y=mean_ret - 3 * std_ret, color="red", linestyle=":", alpha=0.7)
            ax2.set_title("Daily Returns with Outliers")
            ax2.set_xlabel("Date")
            ax2.set_ylabel("Return %")
            ax2.legend(loc="upper right")
            ax2.tick_params(axis="x", rotation=45)

        # Plot 3: Trading gaps (missing days)
        ax3 = axes[1, 0]
        if len(df) > 1:
            date_diffs = pd.Series(df.index).diff().dt.days.dropna()
            gap_counts = date_diffs.value_counts().sort_index()
            ax3.bar(gap_counts.index.astype(str), gap_counts.values, color="#A23B72")
            ax3.set_title("Distribution of Days Between Records")
            ax3.set_xlabel("Gap (days)")
            ax3.set_ylabel("Frequency")
            ax3.tick_params(axis="x", rotation=45)

        # Plot 4: Volume anomalies
        ax4 = axes[1, 1]
        if "volume" in df.columns:
            volume = df["volume"].dropna()
            ax4.hist(volume, bins=30, color="#2E86AB", alpha=0.7, edgecolor="white")
            ax4.axvline(volume.mean(), color="red", linestyle="--", label=f"Mean: {volume.mean():.0f}")
            ax4.axvline(volume.median(), color="green", linestyle="--", label=f"Median: {volume.median():.0f}")
            ax4.set_title("Volume Distribution")
            ax4.set_xlabel("Volume")
            ax4.set_ylabel("Frequency")
            ax4.legend()
        else:
            ax4.text(0.5, 0.5, "Volume data not available", ha="center", va="center")

        plt.tight_layout()
        chart_path = CHARTS_DIR / f"{symbol}_data_quality.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        # Print summary stats
        print(f"\n📊 Summary Statistics:")
        print(df.describe())

        print(f"\n✅ Data quality chart saved: {chart_path}")
        assert chart_path.exists()


class TestCacheVisualization:
    """Tests to visualize cache effectiveness."""

    @pytest.mark.integration
    def test_cache_performance_visualization(self, collector):
        """Measure and visualize cache performance."""
        import time

        symbol = "SBER"
        times = {"fresh": [], "cached": []}

        # First fetch (fresh)
        start = time.time()
        df = collector.get_ohlcv(symbol, interval=24, limit=50, use_cache=False)
        times["fresh"].append(time.time() - start)

        if df is None:
            pytest.skip("Could not fetch data from API")

        # Cached fetches
        for _ in range(5):
            start = time.time()
            collector.get_ohlcv(symbol, interval=24, limit=50, use_cache=True)
            times["cached"].append(time.time() - start)

        # Visualization
        fig, ax = plt.subplots(figsize=(10, 5))

        categories = ["Fresh (API)"] + [f"Cached #{i+1}" for i in range(len(times["cached"]))]
        all_times = times["fresh"] + times["cached"]
        colors = ["#EF5350"] + ["#26A69A"] * len(times["cached"])

        bars = ax.bar(categories, all_times, color=colors)
        ax.set_ylabel("Time (seconds)")
        ax.set_title(f"Cache Performance: {symbol} OHLCV Data Fetch")
        ax.tick_params(axis="x", rotation=45)

        # Add time labels
        for bar, t in zip(bars, all_times):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height(),
                f"{t*1000:.1f}ms",
                ha="center",
                va="bottom",
                fontsize=9,
            )

        # Add speedup annotation
        if times["cached"]:
            avg_cached = np.mean(times["cached"])
            speedup = times["fresh"][0] / avg_cached if avg_cached > 0 else 0
            ax.annotate(
                f"Speedup: {speedup:.1f}x",
                xy=(0.95, 0.95),
                xycoords="axes fraction",
                ha="right",
                va="top",
                fontsize=12,
                bbox=dict(boxstyle="round", facecolor="#E8F5E9", edgecolor="#26A69A"),
            )

        plt.tight_layout()
        chart_path = CHARTS_DIR / "cache_performance.png"
        plt.savefig(chart_path, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"\n⚡ Cache Performance:")
        print(f"  Fresh fetch: {times['fresh'][0]*1000:.1f}ms")
        print(f"  Cached avg:  {np.mean(times['cached'])*1000:.1f}ms")
        print(f"  Speedup:     {speedup:.1f}x")
        print(f"\n✅ Cache performance chart saved: {chart_path}")

        assert chart_path.exists()


if __name__ == "__main__":
    # Run with: python -m pytest tests/test_visualization.py -v -s --tb=short -m integration
    pytest.main([__file__, "-v", "-s", "--tb=short", "-m", "integration"])

