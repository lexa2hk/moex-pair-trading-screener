"""Statistical functions for pair trading analysis."""

from typing import Optional, Tuple

import numpy as np
import pandas as pd
import structlog
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tsa.stattools import adfuller, coint

logger = structlog.get_logger()


def calculate_correlation(
    series1: pd.Series,
    series2: pd.Series,
    method: str = "pearson",
) -> float:
    """
    Calculate correlation between two price series.

    Args:
        series1: First price series
        series2: Second price series
        method: Correlation method ('pearson', 'spearman', 'kendall')

    Returns:
        Correlation coefficient (-1 to 1)
    """
    if len(series1) != len(series2):
        raise ValueError("Series must have the same length")

    if len(series1) < 2:
        raise ValueError("Series must have at least 2 data points")

    # Align and drop NaN values
    combined = pd.DataFrame({"s1": series1, "s2": series2}).dropna()

    if len(combined) < 2:
        logger.warning("Insufficient data after dropping NaN values")
        return np.nan

    correlation = combined["s1"].corr(combined["s2"], method=method)
    return correlation


def calculate_rolling_correlation(
    series1: pd.Series,
    series2: pd.Series,
    window: int = 20,
    method: str = "pearson",
) -> pd.Series:
    """
    Calculate rolling correlation between two price series.

    Args:
        series1: First price series
        series2: Second price series
        window: Rolling window size
        method: Correlation method ('pearson', 'spearman', 'kendall')

    Returns:
        Series of rolling correlations
    """
    if len(series1) != len(series2):
        raise ValueError("Series must have the same length")

    if window < 2:
        raise ValueError("Window must be at least 2")

    combined = pd.DataFrame({"s1": series1, "s2": series2})
    rolling_corr = combined["s1"].rolling(window=window).corr(combined["s2"])

    return rolling_corr


def check_stationarity(
    series: pd.Series,
    significance_level: float = 0.05,
) -> dict:
    """
    Test if a series is stationary using Augmented Dickey-Fuller test.

    Args:
        series: Time series to test
        significance_level: Significance level for the test

    Returns:
        Dictionary with test results:
        - statistic: ADF test statistic
        - p_value: p-value
        - is_stationary: True if series is stationary
        - critical_values: Critical values at different significance levels
    """
    series_clean = series.dropna()

    if len(series_clean) < 20:
        logger.warning("Series too short for reliable ADF test", length=len(series_clean))
        return {
            "statistic": np.nan,
            "p_value": np.nan,
            "is_stationary": False,
            "critical_values": {},
            "used_lag": 0,
            "n_obs": len(series_clean),
        }

    try:
        result = adfuller(series_clean, autolag="AIC")
        adf_stat, p_value, used_lag, n_obs, critical_values, icbest = result

        return {
            "statistic": adf_stat,
            "p_value": p_value,
            "is_stationary": p_value < significance_level,
            "critical_values": critical_values,
            "used_lag": used_lag,
            "n_obs": n_obs,
        }
    except Exception as e:
        logger.error("ADF test failed", error=str(e))
        return {
            "statistic": np.nan,
            "p_value": np.nan,
            "is_stationary": False,
            "critical_values": {},
            "used_lag": 0,
            "n_obs": 0,
        }


def check_cointegration(
    series1: pd.Series,
    series2: pd.Series,
    significance_level: float = 0.05,
) -> dict:
    """
    Test cointegration between two price series using Engle-Granger method.

    Args:
        series1: First price series
        series2: Second price series
        significance_level: Significance level for the test

    Returns:
        Dictionary with test results:
        - statistic: Test statistic
        - p_value: p-value
        - is_cointegrated: True if series are cointegrated
        - critical_values: Critical values at different significance levels
    """
    # Align series
    combined = pd.DataFrame({"s1": series1, "s2": series2}).dropna()

    if len(combined) < 30:
        logger.warning(
            "Insufficient data for cointegration test",
            length=len(combined),
        )
        return {
            "statistic": np.nan,
            "p_value": np.nan,
            "is_cointegrated": False,
            "critical_values": {},
        }

    try:
        coint_stat, p_value, critical_values = coint(
            combined["s1"],
            combined["s2"],
        )

        return {
            "statistic": coint_stat,
            "p_value": p_value,
            "is_cointegrated": p_value < significance_level,
            "critical_values": {
                "1%": critical_values[0],
                "5%": critical_values[1],
                "10%": critical_values[2],
            },
        }
    except Exception as e:
        logger.error("Cointegration test failed", error=str(e))
        return {
            "statistic": np.nan,
            "p_value": np.nan,
            "is_cointegrated": False,
            "critical_values": {},
        }


def calculate_hedge_ratio(
    series1: pd.Series,
    series2: pd.Series,
    method: str = "ols",
) -> Tuple[float, dict]:
    """
    Calculate hedge ratio between two series.

    The hedge ratio determines how many units of series2 to hold
    for each unit of series1 to create a mean-reverting spread.

    Args:
        series1: Dependent variable (Y)
        series2: Independent variable (X)
        method: Method to calculate hedge ratio ('ols', 'tls')

    Returns:
        Tuple of (hedge_ratio, stats_dict)
    """
    # Align series
    combined = pd.DataFrame({"y": series1, "x": series2}).dropna()

    if len(combined) < 10:
        logger.warning("Insufficient data for hedge ratio calculation")
        return np.nan, {"r_squared": np.nan, "std_error": np.nan}

    if method == "ols":
        # Ordinary Least Squares: Y = beta * X + alpha
        X = combined["x"].values
        Y = combined["y"].values
        X_with_const = np.column_stack([np.ones(len(X)), X])

        try:
            model = OLS(Y, X_with_const).fit()
            hedge_ratio = model.params[1]  # beta coefficient
            stats_dict = {
                "intercept": model.params[0],
                "r_squared": model.rsquared,
                "std_error": model.bse[1],
                "t_stat": model.tvalues[1],
                "p_value": model.pvalues[1],
            }
            return hedge_ratio, stats_dict
        except Exception as e:
            logger.error("OLS hedge ratio calculation failed", error=str(e))
            return np.nan, {"r_squared": np.nan, "std_error": np.nan}

    elif method == "tls":
        # Total Least Squares (orthogonal regression)
        X = combined["x"].values
        Y = combined["y"].values

        # Center the data
        X_centered = X - X.mean()
        Y_centered = Y - Y.mean()

        # TLS solution
        data_matrix = np.column_stack([X_centered, Y_centered])
        _, _, Vt = np.linalg.svd(data_matrix)
        hedge_ratio = -Vt[-1, 0] / Vt[-1, 1]

        # Calculate R-squared equivalent
        spread = Y - hedge_ratio * X
        ss_res = np.sum((spread - spread.mean()) ** 2)
        ss_tot = np.sum((Y - Y.mean()) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

        return hedge_ratio, {"r_squared": r_squared, "std_error": np.nan}

    else:
        raise ValueError(f"Unknown method: {method}")


def calculate_half_life(spread: pd.Series) -> float:
    """
    Calculate the half-life of mean reversion for a spread.

    The half-life indicates how long it takes for the spread
    to revert halfway back to its mean.

    Args:
        spread: Spread series

    Returns:
        Half-life in periods (e.g., days if daily data)
    """
    spread_clean = spread.dropna()

    if len(spread_clean) < 10:
        logger.warning("Insufficient data for half-life calculation")
        return np.nan

    # Create aligned lagged spread and differences
    spread_lag = spread_clean.shift(1)
    spread_diff = spread_clean.diff()

    # Create DataFrame for alignment and drop NaN rows
    df = pd.DataFrame({
        "lag": spread_lag,
        "diff": spread_diff,
    }).dropna()

    if len(df) < 2:
        return np.nan

    try:
        # Regress: delta_spread = theta * spread_lag + epsilon
        # Half-life = -ln(2) / theta
        X = df["lag"].values.reshape(-1, 1)
        Y = df["diff"].values

        model = OLS(Y, X).fit()
        theta = model.params[0]

        if theta >= 0:
            # Not mean-reverting
            logger.debug("Spread is not mean-reverting (theta >= 0)")
            return np.inf

        half_life = -np.log(2) / theta
        return float(half_life)

    except Exception as e:
        logger.error("Half-life calculation failed", error=str(e))
        return np.nan


def calculate_hurst_exponent(series: pd.Series, max_lag: int = 100) -> float:
    """
    Calculate Hurst exponent to determine if series is mean-reverting.

    H < 0.5: Mean-reverting (good for pair trading)
    H = 0.5: Random walk
    H > 0.5: Trending

    Args:
        series: Price or spread series
        max_lag: Maximum lag for calculation

    Returns:
        Hurst exponent (0 to 1)
    """
    series_clean = series.dropna().values

    if len(series_clean) < max_lag:
        max_lag = len(series_clean) // 2

    if max_lag < 10:
        logger.warning("Insufficient data for Hurst exponent calculation")
        return np.nan

    lags = range(2, max_lag)
    tau = []
    lagvec = []

    for lag in lags:
        # Calculate standard deviation of differences
        pp = np.subtract(series_clean[lag:], series_clean[:-lag])
        tau.append(np.std(pp))
        lagvec.append(lag)

    tau = np.array(tau)
    lagvec = np.array(lagvec)

    # Filter out zeros
    valid = tau > 0
    if not np.any(valid):
        return np.nan

    tau = tau[valid]
    lagvec = lagvec[valid]

    # Linear regression on log-log scale
    log_lags = np.log(lagvec)
    log_tau = np.log(tau)

    slope, _, _, _, _ = stats.linregress(log_lags, log_tau)
    hurst = slope

    return hurst


def calculate_returns(prices: pd.Series, method: str = "simple") -> pd.Series:
    """
    Calculate returns from price series.

    Args:
        prices: Price series
        method: 'simple' for arithmetic returns, 'log' for log returns

    Returns:
        Returns series
    """
    if method == "simple":
        return prices.pct_change()
    elif method == "log":
        return np.log(prices / prices.shift(1))
    else:
        raise ValueError(f"Unknown method: {method}")


def calculate_volatility(
    returns: pd.Series,
    window: int = 20,
    annualize: bool = True,
    trading_days: int = 252,
) -> pd.Series:
    """
    Calculate rolling volatility.

    Args:
        returns: Returns series
        window: Rolling window size
        annualize: Whether to annualize the volatility
        trading_days: Number of trading days per year

    Returns:
        Rolling volatility series
    """
    vol = returns.rolling(window=window).std()

    if annualize:
        vol = vol * np.sqrt(trading_days)

    return vol

