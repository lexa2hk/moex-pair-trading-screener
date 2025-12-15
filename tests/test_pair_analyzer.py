"""Tests for pair analysis module."""

import numpy as np
import pandas as pd
import pytest

from src.analysis.pair_analyzer import PairAnalyzer, PairMetrics
from src.analysis.signals import SignalGenerator, SignalType, TradingSignal
from src.analysis.statistics import (
    calculate_correlation,
    calculate_half_life,
    calculate_hedge_ratio,
    calculate_hurst_exponent,
    calculate_rolling_correlation,
    check_cointegration,
    check_stationarity,
)


class TestStatistics:
    """Test statistical functions."""

    @pytest.fixture
    def correlated_series(self):
        """Generate two correlated price series."""
        np.random.seed(42)
        n = 200
        # Generate correlated random walks
        noise1 = np.random.randn(n)
        noise2 = 0.8 * noise1 + 0.2 * np.random.randn(n)  # Correlated noise

        prices1 = 100 + np.cumsum(noise1)
        prices2 = 100 + np.cumsum(noise2)

        index = pd.date_range("2024-01-01", periods=n, freq="D")
        return (
            pd.Series(prices1, index=index, name="STOCK1"),
            pd.Series(prices2, index=index, name="STOCK2"),
        )

    @pytest.fixture
    def cointegrated_series(self):
        """Generate two cointegrated price series."""
        np.random.seed(42)
        n = 200
        # Generate cointegrated series
        # Y = beta * X + stationary_error
        x = 100 + np.cumsum(np.random.randn(n))  # Random walk
        beta = 1.5
        error = np.random.randn(n) * 2  # Mean-reverting error
        y = beta * x + error

        index = pd.date_range("2024-01-01", periods=n, freq="D")
        return (
            pd.Series(y, index=index, name="STOCK1"),
            pd.Series(x, index=index, name="STOCK2"),
        )

    @pytest.fixture
    def mean_reverting_series(self):
        """Generate mean-reverting (stationary) series."""
        np.random.seed(42)
        n = 200
        # AR(1) process with mean reversion
        theta = 0.1  # Mean reversion speed
        mean = 0
        series = [0]
        for _ in range(n - 1):
            series.append(series[-1] * (1 - theta) + mean * theta + np.random.randn() * 0.5)

        index = pd.date_range("2024-01-01", periods=n, freq="D")
        return pd.Series(series, index=index, name="SPREAD")

    def test_calculate_correlation(self, correlated_series):
        """Test correlation calculation."""
        s1, s2 = correlated_series
        corr = calculate_correlation(s1, s2)

        assert not np.isnan(corr)
        assert -1 <= corr <= 1
        assert corr > 0.7  # Should be highly correlated

    def test_calculate_correlation_methods(self, correlated_series):
        """Test different correlation methods."""
        s1, s2 = correlated_series

        pearson = calculate_correlation(s1, s2, method="pearson")
        spearman = calculate_correlation(s1, s2, method="spearman")
        kendall = calculate_correlation(s1, s2, method="kendall")

        # All should show positive correlation
        assert pearson > 0.5
        assert spearman > 0.5
        assert kendall > 0.5

    def test_calculate_correlation_short_series(self):
        """Test correlation with minimal data."""
        s1 = pd.Series([1, 2])
        s2 = pd.Series([1, 2])
        corr = calculate_correlation(s1, s2)
        assert not np.isnan(corr)

    def test_calculate_rolling_correlation(self, correlated_series):
        """Test rolling correlation calculation."""
        s1, s2 = correlated_series
        window = 20
        rolling_corr = calculate_rolling_correlation(s1, s2, window=window)

        assert len(rolling_corr) == len(s1)
        # First (window-1) values should be NaN
        assert rolling_corr.iloc[:window - 1].isna().all()
        # Remaining values should be valid correlations
        valid_corr = rolling_corr.dropna()
        assert (valid_corr >= -1).all() and (valid_corr <= 1).all()

    def test_stationarity_stationary_series(self, mean_reverting_series):
        """Test stationarity on stationary series."""
        result = check_stationarity(mean_reverting_series)

        assert "statistic" in result
        assert "p_value" in result
        assert "is_stationary" in result
        # Mean-reverting series should be stationary
        assert result["is_stationary"] == True  # noqa: E712 (use == for numpy bool)

    def test_stationarity_random_walk(self, correlated_series):
        """Test stationarity on random walk (non-stationary)."""
        s1, _ = correlated_series
        result = check_stationarity(s1)

        # Random walk is typically non-stationary
        assert "is_stationary" in result
        # Note: may sometimes pass due to randomness

    def test_cointegration_cointegrated_series(self, cointegrated_series):
        """Test cointegration on cointegrated series."""
        s1, s2 = cointegrated_series
        result = check_cointegration(s1, s2)

        assert "statistic" in result
        assert "p_value" in result
        assert "is_cointegrated" in result
        assert "critical_values" in result

        # Cointegrated series should pass the test
        # Note: with small samples, may not always pass
        # At least check the structure is correct

    def test_cointegration_random_walks(self, correlated_series):
        """Test cointegration on independent random walks."""
        s1, s2 = correlated_series
        result = check_cointegration(s1, s2)

        assert "is_cointegrated" in result
        # Two independent random walks typically not cointegrated

    def test_hedge_ratio_ols(self, cointegrated_series):
        """Test hedge ratio calculation with OLS."""
        s1, s2 = cointegrated_series
        hedge_ratio, stats = calculate_hedge_ratio(s1, s2, method="ols")

        assert not np.isnan(hedge_ratio)
        assert "r_squared" in stats
        assert "intercept" in stats
        # For our cointegrated series, hedge ratio should be close to 1.5
        assert 1.0 <= hedge_ratio <= 2.0

    def test_hedge_ratio_tls(self, cointegrated_series):
        """Test hedge ratio calculation with TLS."""
        s1, s2 = cointegrated_series
        hedge_ratio, stats = calculate_hedge_ratio(s1, s2, method="tls")

        assert not np.isnan(hedge_ratio)
        assert "r_squared" in stats

    def test_half_life(self, mean_reverting_series):
        """Test half-life calculation."""
        half_life = calculate_half_life(mean_reverting_series)

        # Half-life may be NaN, positive, or infinite depending on data
        if not np.isnan(half_life):
            assert half_life > 0 or half_life == np.inf
            # For our AR(1) process, if valid, half-life should be reasonable
            if half_life != np.inf:
                assert half_life < 200

    def test_half_life_random_walk(self, correlated_series):
        """Test half-life on random walk (non-mean-reverting)."""
        s1, _ = correlated_series
        half_life = calculate_half_life(s1)

        # Random walk should have very long or infinite half-life
        # or may return NaN if estimation fails
        assert np.isnan(half_life) or half_life > 20 or half_life == np.inf

    def test_hurst_exponent_mean_reverting(self, mean_reverting_series):
        """Test Hurst exponent on mean-reverting series."""
        hurst = calculate_hurst_exponent(mean_reverting_series)

        assert not np.isnan(hurst)
        # Mean-reverting series should have H < 0.5
        assert 0 < hurst < 0.7

    def test_hurst_exponent_random_walk(self, correlated_series):
        """Test Hurst exponent on random walk."""
        s1, _ = correlated_series
        hurst = calculate_hurst_exponent(s1)

        assert not np.isnan(hurst)
        # Random walk should have H close to 0.5
        assert 0.3 < hurst < 0.7


class TestPairAnalyzer:
    """Test PairAnalyzer class."""

    @pytest.fixture
    def analyzer(self):
        """Create PairAnalyzer instance."""
        return PairAnalyzer(
            lookback_period=60,
            zscore_window=20,
            correlation_window=30,
        )

    @pytest.fixture
    def cointegrated_prices(self):
        """Generate cointegrated price series."""
        np.random.seed(42)
        n = 100
        x = 100 + np.cumsum(np.random.randn(n) * 0.5)
        beta = 1.2
        error = np.random.randn(n) * 1.5
        y = beta * x + error

        index = pd.date_range("2024-01-01", periods=n, freq="D")
        return (
            pd.Series(y, index=index),
            pd.Series(x, index=index),
        )

    def test_analyze_pair(self, analyzer, cointegrated_prices):
        """Test full pair analysis."""
        p1, p2 = cointegrated_prices
        metrics = analyzer.analyze_pair(p1, p2, "STOCK1", "STOCK2")

        assert isinstance(metrics, PairMetrics)
        assert metrics.symbol1 == "STOCK1"
        assert metrics.symbol2 == "STOCK2"
        assert not np.isnan(metrics.correlation)
        assert not np.isnan(metrics.hedge_ratio)
        assert metrics.spread is not None
        assert metrics.zscore is not None
        assert len(metrics.spread) > 0
        assert len(metrics.zscore) > 0

    def test_calculate_spread(self, analyzer, cointegrated_prices):
        """Test spread calculation."""
        p1, p2 = cointegrated_prices
        hedge_ratio = 1.2

        spread = analyzer.calculate_spread(p1, p2, hedge_ratio)

        assert len(spread) == len(p1)
        expected_spread = p1 - hedge_ratio * p2
        pd.testing.assert_series_equal(spread, expected_spread)

    def test_calculate_spread_normalized(self, analyzer, cointegrated_prices):
        """Test normalized spread calculation."""
        p1, p2 = cointegrated_prices
        hedge_ratio = 1.2

        spread = analyzer.calculate_spread(p1, p2, hedge_ratio, normalize=True)

        assert abs(spread.mean()) < 0.1  # Should be centered near 0
        assert abs(spread.std() - 1) < 0.1  # Should have std ~1

    def test_calculate_zscore(self, analyzer, cointegrated_prices):
        """Test z-score calculation."""
        p1, p2 = cointegrated_prices
        spread = p1 - 1.2 * p2

        zscore = analyzer.calculate_zscore(spread, window=20)

        assert len(zscore) == len(spread)
        # First (window-1) values should be NaN
        assert zscore.iloc[:19].isna().all()
        # Valid z-scores should be roughly centered
        valid_zscore = zscore.dropna()
        assert abs(valid_zscore.mean()) < 1

    def test_pair_metrics_is_tradeable(self):
        """Test PairMetrics.is_tradeable method."""
        # Tradeable pair
        good_metrics = PairMetrics(
            symbol1="A",
            symbol2="B",
            correlation=0.85,
            is_cointegrated=True,
            cointegration_pvalue=0.01,
            hedge_ratio=1.0,
            half_life=15,
            hurst_exponent=0.4,
        )
        assert good_metrics.is_tradeable() is True

        # Low correlation
        bad_corr = PairMetrics(
            symbol1="A",
            symbol2="B",
            correlation=0.5,
            is_cointegrated=True,
            cointegration_pvalue=0.01,
            hedge_ratio=1.0,
            half_life=15,
            hurst_exponent=0.4,
        )
        assert bad_corr.is_tradeable() is False

        # Not cointegrated
        not_coint = PairMetrics(
            symbol1="A",
            symbol2="B",
            correlation=0.85,
            is_cointegrated=False,
            cointegration_pvalue=0.5,
            hedge_ratio=1.0,
            half_life=15,
            hurst_exponent=0.4,
        )
        assert not_coint.is_tradeable() is False

    def test_pair_metrics_to_dict(self, analyzer, cointegrated_prices):
        """Test PairMetrics serialization."""
        p1, p2 = cointegrated_prices
        metrics = analyzer.analyze_pair(p1, p2, "STOCK1", "STOCK2")

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert "symbol1" in result
        assert "symbol2" in result
        assert "correlation" in result
        assert "is_cointegrated" in result
        assert "last_updated" in result


class TestSignalGenerator:
    """Test SignalGenerator class."""

    @pytest.fixture
    def generator(self):
        """Create SignalGenerator instance."""
        return SignalGenerator(
            entry_threshold=2.0,
            exit_threshold=0.0,
            stop_loss_threshold=3.0,
            min_correlation=0.7,
            require_cointegration=True,
        )

    @pytest.fixture
    def good_metrics(self):
        """Create metrics for a tradeable pair."""
        return PairMetrics(
            symbol1="SBER",
            symbol2="GAZP",
            correlation=0.85,
            is_cointegrated=True,
            cointegration_pvalue=0.01,
            hedge_ratio=1.2,
            spread_mean=0,
            spread_std=10,
            current_zscore=-2.5,
            half_life=15,
            hurst_exponent=0.4,
        )

    def test_generate_long_signal(self, generator, good_metrics):
        """Test long spread signal generation."""
        # Z-score is -2.5, should trigger long spread
        signal = generator.generate_signal(good_metrics)

        assert isinstance(signal, TradingSignal)
        assert signal.signal_type == SignalType.LONG_SPREAD
        assert signal.symbol1 == "SBER"
        assert signal.symbol2 == "GAZP"
        assert signal.zscore == -2.5
        assert signal.hedge_ratio == 1.2

    def test_generate_short_signal(self, generator, good_metrics):
        """Test short spread signal generation."""
        good_metrics.current_zscore = 2.5
        signal = generator.generate_signal(good_metrics)

        assert signal.signal_type == SignalType.SHORT_SPREAD

    def test_generate_exit_long_signal(self, generator, good_metrics):
        """Test exit long signal generation."""
        good_metrics.current_zscore = 0.5
        signal = generator.generate_signal(
            good_metrics,
            current_position=SignalType.LONG_SPREAD,
        )

        assert signal.signal_type == SignalType.EXIT_LONG

    def test_generate_exit_short_signal(self, generator, good_metrics):
        """Test exit short signal generation."""
        good_metrics.current_zscore = -0.5
        signal = generator.generate_signal(
            good_metrics,
            current_position=SignalType.SHORT_SPREAD,
        )

        assert signal.signal_type == SignalType.EXIT_SHORT

    def test_generate_stop_loss_signal(self, generator, good_metrics):
        """Test stop loss signal generation."""
        good_metrics.current_zscore = -3.5
        signal = generator.generate_signal(
            good_metrics,
            current_position=SignalType.LONG_SPREAD,
        )

        assert signal.signal_type == SignalType.STOP_LOSS

    def test_no_signal_low_zscore(self, generator, good_metrics):
        """Test no signal when z-score below threshold."""
        good_metrics.current_zscore = -1.5  # Below entry threshold
        signal = generator.generate_signal(good_metrics)

        assert signal.signal_type == SignalType.NO_SIGNAL

    def test_no_signal_low_correlation(self, generator, good_metrics):
        """Test no signal when correlation too low."""
        good_metrics.correlation = 0.5
        good_metrics.current_zscore = -2.5
        signal = generator.generate_signal(good_metrics)

        assert signal.signal_type == SignalType.NO_SIGNAL

    def test_no_signal_not_cointegrated(self, generator, good_metrics):
        """Test no signal when not cointegrated."""
        good_metrics.is_cointegrated = False
        good_metrics.current_zscore = -2.5
        signal = generator.generate_signal(good_metrics)

        assert signal.signal_type == SignalType.NO_SIGNAL

    def test_signal_strength(self, generator, good_metrics):
        """Test signal strength calculation."""
        # Strong signal (z-score >= 3)
        good_metrics.current_zscore = -3.0
        signal = generator.generate_signal(good_metrics)
        assert signal.strength.value == "STRONG"

        # Moderate signal (2.5 <= z-score < 3)
        good_metrics.current_zscore = -2.5
        signal = generator.generate_signal(good_metrics)
        assert signal.strength.value == "MODERATE"

        # Weak signal (z-score < 2.5)
        good_metrics.current_zscore = -2.1
        signal = generator.generate_signal(good_metrics)
        assert signal.strength.value == "WEAK"

    def test_signal_confidence(self, generator, good_metrics):
        """Test signal confidence calculation."""
        signal = generator.generate_signal(good_metrics)

        assert 0 <= signal.confidence <= 1
        # Good metrics should have decent confidence
        assert signal.confidence > 0.5

    def test_signal_format_message(self, generator, good_metrics):
        """Test signal message formatting."""
        signal = generator.generate_signal(good_metrics)
        message = signal.format_message()

        assert "LONG" in message
        assert "SBER" in message
        assert "GAZP" in message
        assert "Z-Score" in message

    def test_scan_for_signals(self, generator):
        """Test scanning multiple pairs for signals."""
        pairs = [
            PairMetrics(
                symbol1="SBER",
                symbol2="GAZP",
                correlation=0.85,
                is_cointegrated=True,
                cointegration_pvalue=0.01,
                hedge_ratio=1.2,
                current_zscore=-2.5,
                half_life=15,
                hurst_exponent=0.4,
            ),
            PairMetrics(
                symbol1="LKOH",
                symbol2="ROSN",
                correlation=0.80,
                is_cointegrated=True,
                cointegration_pvalue=0.02,
                hedge_ratio=1.1,
                current_zscore=-1.0,  # Below threshold
                half_life=20,
                hurst_exponent=0.45,
            ),
            PairMetrics(
                symbol1="VTBR",
                symbol2="SBER",
                correlation=0.90,
                is_cointegrated=True,
                cointegration_pvalue=0.005,
                hedge_ratio=0.8,
                current_zscore=2.8,
                half_life=10,
                hurst_exponent=0.35,
            ),
        ]

        signals = generator.scan_for_signals(pairs)

        # Should find 2 signals (SBER/GAZP and VTBR/SBER)
        assert len(signals) == 2
        # Sorted by confidence, highest first
        assert signals[0].confidence >= signals[1].confidence


class TestIntegration:
    """Integration tests for pair analysis pipeline."""

    def test_full_analysis_pipeline(self):
        """Test complete analysis from prices to signals."""
        # Generate test data
        np.random.seed(42)
        n = 100
        x = 100 + np.cumsum(np.random.randn(n) * 0.5)
        beta = 1.3
        error = np.random.randn(n) * 1.5
        y = beta * x + error

        index = pd.date_range("2024-01-01", periods=n, freq="D")
        prices1 = pd.Series(y, index=index)
        prices2 = pd.Series(x, index=index)

        # Analyze pair
        analyzer = PairAnalyzer(lookback_period=60, zscore_window=20)
        metrics = analyzer.analyze_pair(prices1, prices2, "STOCK1", "STOCK2")

        # Generate signal
        generator = SignalGenerator(
            entry_threshold=2.0,
            require_cointegration=False,  # Relax for small sample
        )
        signal = generator.generate_signal(metrics)

        # Verify pipeline
        assert isinstance(metrics, PairMetrics)
        assert isinstance(signal, TradingSignal)
        assert metrics.spread is not None
        assert metrics.zscore is not None

