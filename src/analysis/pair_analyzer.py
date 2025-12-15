"""Pair trading analysis module."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import structlog

from src.analysis.statistics import (
    calculate_correlation,
    calculate_half_life,
    calculate_hedge_ratio,
    calculate_hurst_exponent,
    calculate_rolling_correlation,
    check_cointegration,
)

logger = structlog.get_logger()


@dataclass
class PairMetrics:
    """Container for pair trading metrics."""

    symbol1: str
    symbol2: str
    correlation: float
    rolling_correlation: Optional[pd.Series] = None
    is_cointegrated: bool = False
    cointegration_pvalue: float = 1.0
    hedge_ratio: float = 1.0
    hedge_ratio_stats: dict = field(default_factory=dict)
    spread_mean: float = 0.0
    spread_std: float = 1.0
    current_zscore: float = 0.0
    half_life: float = np.inf
    hurst_exponent: float = 0.5
    spread: Optional[pd.Series] = None
    zscore: Optional[pd.Series] = None
    last_updated: datetime = field(default_factory=datetime.now)

    def is_tradeable(
        self,
        min_correlation: float = 0.7,
        max_cointegration_pvalue: float = 0.05,
        max_half_life: float = 30,
        max_hurst: float = 0.5,
    ) -> bool:
        """
        Check if pair meets trading criteria.

        Args:
            min_correlation: Minimum correlation threshold
            max_cointegration_pvalue: Maximum p-value for cointegration
            max_half_life: Maximum half-life in periods
            max_hurst: Maximum Hurst exponent (< 0.5 is mean-reverting)

        Returns:
            True if pair is tradeable
        """
        return (
            abs(self.correlation) >= min_correlation
            and self.is_cointegrated
            and self.cointegration_pvalue <= max_cointegration_pvalue
            and self.half_life <= max_half_life
            and self.hurst_exponent < max_hurst
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "symbol1": self.symbol1,
            "symbol2": self.symbol2,
            "correlation": self.correlation,
            "is_cointegrated": self.is_cointegrated,
            "cointegration_pvalue": self.cointegration_pvalue,
            "hedge_ratio": self.hedge_ratio,
            "spread_mean": self.spread_mean,
            "spread_std": self.spread_std,
            "current_zscore": self.current_zscore,
            "half_life": self.half_life,
            "hurst_exponent": self.hurst_exponent,
            "last_updated": self.last_updated.isoformat(),
        }


class PairAnalyzer:
    """Analyzer for pair trading strategies."""

    def __init__(
        self,
        lookback_period: int = 60,
        zscore_window: int = 20,
        correlation_window: int = 30,
        hedge_ratio_method: str = "ols",
    ):
        """
        Initialize PairAnalyzer.

        Args:
            lookback_period: Number of periods for analysis
            zscore_window: Window for z-score calculation
            correlation_window: Window for rolling correlation
            hedge_ratio_method: Method for hedge ratio ('ols' or 'tls')
        """
        self.lookback_period = lookback_period
        self.zscore_window = zscore_window
        self.correlation_window = correlation_window
        self.hedge_ratio_method = hedge_ratio_method

        logger.info(
            "PairAnalyzer initialized",
            lookback_period=lookback_period,
            zscore_window=zscore_window,
            correlation_window=correlation_window,
            hedge_ratio_method=hedge_ratio_method,
        )

    def analyze_pair(
        self,
        prices1: pd.Series,
        prices2: pd.Series,
        symbol1: str = "SYMBOL1",
        symbol2: str = "SYMBOL2",
    ) -> PairMetrics:
        """
        Perform comprehensive pair analysis.

        Args:
            prices1: Price series for first asset
            prices2: Price series for second asset
            symbol1: Symbol name for first asset
            symbol2: Symbol name for second asset

        Returns:
            PairMetrics object with analysis results
        """
        logger.info(
            "Analyzing pair",
            symbol1=symbol1,
            symbol2=symbol2,
            data_points=min(len(prices1), len(prices2)),
        )

        # Align data
        combined = pd.DataFrame({
            "p1": prices1,
            "p2": prices2,
        }).dropna()

        if len(combined) < self.lookback_period:
            logger.warning(
                "Insufficient data for analysis",
                available=len(combined),
                required=self.lookback_period,
            )

        # Use lookback period
        combined = combined.tail(self.lookback_period)
        p1 = combined["p1"]
        p2 = combined["p2"]

        # 1. Calculate correlation
        correlation = calculate_correlation(p1, p2)
        rolling_corr = calculate_rolling_correlation(
            p1, p2, window=self.correlation_window
        )

        logger.debug("Correlation calculated", correlation=correlation)

        # 2. Test cointegration
        coint_result = check_cointegration(p1, p2)
        is_cointegrated = coint_result["is_cointegrated"]
        coint_pvalue = coint_result["p_value"]

        logger.debug(
            "Cointegration test completed",
            is_cointegrated=is_cointegrated,
            p_value=coint_pvalue,
        )

        # 3. Calculate hedge ratio
        hedge_ratio, hedge_stats = calculate_hedge_ratio(
            p1, p2, method=self.hedge_ratio_method
        )

        logger.debug(
            "Hedge ratio calculated",
            hedge_ratio=hedge_ratio,
            r_squared=hedge_stats.get("r_squared"),
        )

        # 4. Calculate spread
        spread = self.calculate_spread(p1, p2, hedge_ratio)

        # 5. Calculate z-score
        zscore = self.calculate_zscore(spread, window=self.zscore_window)

        # 6. Calculate half-life
        half_life = calculate_half_life(spread)

        # 7. Calculate Hurst exponent
        hurst = calculate_hurst_exponent(spread)

        # Current values
        spread_mean = spread.mean()
        spread_std = spread.std()
        current_zscore = zscore.iloc[-1] if len(zscore) > 0 else 0.0

        logger.info(
            "Pair analysis completed",
            symbol1=symbol1,
            symbol2=symbol2,
            correlation=round(correlation, 4),
            is_cointegrated=is_cointegrated,
            hedge_ratio=round(hedge_ratio, 4) if not np.isnan(hedge_ratio) else None,
            current_zscore=round(current_zscore, 4) if not np.isnan(current_zscore) else None,
            half_life=round(half_life, 2) if not np.isnan(half_life) and half_life != np.inf else None,
            hurst=round(hurst, 4) if not np.isnan(hurst) else None,
        )

        return PairMetrics(
            symbol1=symbol1,
            symbol2=symbol2,
            correlation=correlation,
            rolling_correlation=rolling_corr,
            is_cointegrated=is_cointegrated,
            cointegration_pvalue=coint_pvalue,
            hedge_ratio=hedge_ratio,
            hedge_ratio_stats=hedge_stats,
            spread_mean=spread_mean,
            spread_std=spread_std,
            current_zscore=current_zscore,
            half_life=half_life,
            hurst_exponent=hurst,
            spread=spread,
            zscore=zscore,
            last_updated=datetime.now(),
        )

    def calculate_spread(
        self,
        prices1: pd.Series,
        prices2: pd.Series,
        hedge_ratio: float,
        normalize: bool = False,
    ) -> pd.Series:
        """
        Calculate spread between two price series.

        Spread = prices1 - hedge_ratio * prices2

        Args:
            prices1: First price series
            prices2: Second price series
            hedge_ratio: Hedge ratio (beta)
            normalize: Whether to normalize spread by mean

        Returns:
            Spread series
        """
        if np.isnan(hedge_ratio):
            hedge_ratio = 1.0

        spread = prices1 - hedge_ratio * prices2

        if normalize and spread.std() > 0:
            spread = (spread - spread.mean()) / spread.std()

        return spread

    def calculate_zscore(
        self,
        spread: pd.Series,
        window: Optional[int] = None,
    ) -> pd.Series:
        """
        Calculate z-score of spread.

        Z-score = (spread - rolling_mean) / rolling_std

        Args:
            spread: Spread series
            window: Rolling window size (None for full-sample)

        Returns:
            Z-score series
        """
        if window is None:
            window = self.zscore_window

        rolling_mean = spread.rolling(window=window).mean()
        rolling_std = spread.rolling(window=window).std()

        # Avoid division by zero
        rolling_std = rolling_std.replace(0, np.nan)

        zscore = (spread - rolling_mean) / rolling_std

        return zscore

    def find_tradeable_pairs(
        self,
        price_data: dict[str, pd.Series],
        min_correlation: float = 0.7,
        max_cointegration_pvalue: float = 0.05,
        max_half_life: float = 30,
    ) -> list[PairMetrics]:
        """
        Find tradeable pairs from a set of price series.

        Args:
            price_data: Dictionary of {symbol: price_series}
            min_correlation: Minimum correlation threshold
            max_cointegration_pvalue: Maximum p-value for cointegration
            max_half_life: Maximum half-life in periods

        Returns:
            List of tradeable PairMetrics
        """
        symbols = list(price_data.keys())
        tradeable_pairs = []

        total_pairs = len(symbols) * (len(symbols) - 1) // 2
        logger.info(
            "Scanning for tradeable pairs",
            symbols=len(symbols),
            total_pairs=total_pairs,
        )

        analyzed = 0
        for i, symbol1 in enumerate(symbols):
            for symbol2 in symbols[i + 1:]:
                analyzed += 1

                try:
                    metrics = self.analyze_pair(
                        price_data[symbol1],
                        price_data[symbol2],
                        symbol1,
                        symbol2,
                    )

                    if metrics.is_tradeable(
                        min_correlation=min_correlation,
                        max_cointegration_pvalue=max_cointegration_pvalue,
                        max_half_life=max_half_life,
                    ):
                        tradeable_pairs.append(metrics)
                        logger.info(
                            "Found tradeable pair",
                            pair=f"{symbol1}/{symbol2}",
                            correlation=round(metrics.correlation, 4),
                            coint_pvalue=round(metrics.cointegration_pvalue, 4),
                        )

                except Exception as e:
                    logger.error(
                        "Error analyzing pair",
                        pair=f"{symbol1}/{symbol2}",
                        error=str(e),
                    )

        logger.info(
            "Pair scanning completed",
            analyzed=analyzed,
            tradeable=len(tradeable_pairs),
        )

        # Sort by correlation strength
        tradeable_pairs.sort(key=lambda x: abs(x.correlation), reverse=True)

        return tradeable_pairs

    def update_metrics(
        self,
        metrics: PairMetrics,
        prices1: pd.Series,
        prices2: pd.Series,
    ) -> PairMetrics:
        """
        Update existing metrics with new price data.

        Args:
            metrics: Existing PairMetrics to update
            prices1: Updated price series for first asset
            prices2: Updated price series for second asset

        Returns:
            Updated PairMetrics
        """
        return self.analyze_pair(
            prices1,
            prices2,
            metrics.symbol1,
            metrics.symbol2,
        )


def calculate_pair_statistics(
    prices1: pd.Series,
    prices2: pd.Series,
    window: int = 60,
) -> dict:
    """
    Calculate comprehensive pair statistics.

    Convenience function for quick pair evaluation.

    Args:
        prices1: First price series
        prices2: Second price series
        window: Lookback window

    Returns:
        Dictionary with pair statistics
    """
    analyzer = PairAnalyzer(lookback_period=window)
    metrics = analyzer.analyze_pair(prices1, prices2)
    return metrics.to_dict()

