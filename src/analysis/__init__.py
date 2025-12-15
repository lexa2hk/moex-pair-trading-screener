"""Analysis module for pair trading."""

from src.analysis.pair_analyzer import (
    PairAnalyzer,
    PairMetrics,
    calculate_pair_statistics,
)
from src.analysis.signals import (
    SignalGenerator,
    SignalStrength,
    SignalType,
    TradingSignal,
    generate_signal_summary,
)
from src.analysis.statistics import (
    calculate_correlation,
    calculate_half_life,
    calculate_hedge_ratio,
    calculate_hurst_exponent,
    calculate_returns,
    calculate_rolling_correlation,
    calculate_volatility,
    check_cointegration,
    check_stationarity,
)

__all__ = [
    # Pair Analysis
    "PairAnalyzer",
    "PairMetrics",
    "calculate_pair_statistics",
    # Signals
    "SignalGenerator",
    "SignalType",
    "SignalStrength",
    "TradingSignal",
    "generate_signal_summary",
    # Statistics
    "calculate_correlation",
    "calculate_rolling_correlation",
    "check_stationarity",
    "check_cointegration",
    "calculate_hedge_ratio",
    "calculate_half_life",
    "calculate_hurst_exponent",
    "calculate_returns",
    "calculate_volatility",
]
