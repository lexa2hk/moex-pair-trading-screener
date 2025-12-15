"""Signal generation module for pair trading."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd
import structlog

from src.analysis.pair_analyzer import PairMetrics
from src.config import get_settings

logger = structlog.get_logger()


class SignalType(Enum):
    """Types of trading signals."""

    LONG_SPREAD = "LONG_SPREAD"  # Buy symbol1, sell symbol2
    SHORT_SPREAD = "SHORT_SPREAD"  # Sell symbol1, buy symbol2
    EXIT_LONG = "EXIT_LONG"  # Exit long spread position
    EXIT_SHORT = "EXIT_SHORT"  # Exit short spread position
    STOP_LOSS = "STOP_LOSS"  # Stop loss triggered
    NO_SIGNAL = "NO_SIGNAL"  # No action


class SignalStrength(Enum):
    """Signal strength levels."""

    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


@dataclass
class TradingSignal:
    """Trading signal container."""

    signal_type: SignalType
    symbol1: str
    symbol2: str
    zscore: float
    hedge_ratio: float
    strength: SignalStrength = SignalStrength.MODERATE
    confidence: float = 0.0
    entry_price1: Optional[float] = None
    entry_price2: Optional[float] = None
    target_zscore: float = 0.0
    stop_loss_zscore: float = 3.0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "signal_type": self.signal_type.value,
            "symbol1": self.symbol1,
            "symbol2": self.symbol2,
            "zscore": self.zscore,
            "hedge_ratio": self.hedge_ratio,
            "strength": self.strength.value,
            "confidence": self.confidence,
            "entry_price1": self.entry_price1,
            "entry_price2": self.entry_price2,
            "target_zscore": self.target_zscore,
            "stop_loss_zscore": self.stop_loss_zscore,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    def format_message(self) -> str:
        """Format signal as human-readable message."""
        if self.signal_type == SignalType.NO_SIGNAL:
            return f"No signal for {self.symbol1}/{self.symbol2}"

        emoji_map = {
            SignalType.LONG_SPREAD: "🟢 LONG",
            SignalType.SHORT_SPREAD: "🔴 SHORT",
            SignalType.EXIT_LONG: "⬜ EXIT LONG",
            SignalType.EXIT_SHORT: "⬜ EXIT SHORT",
            SignalType.STOP_LOSS: "🛑 STOP LOSS",
        }

        action = emoji_map.get(self.signal_type, "❓")

        if self.signal_type == SignalType.LONG_SPREAD:
            action_detail = f"BUY {self.symbol1} / SELL {self.symbol2}"
        elif self.signal_type == SignalType.SHORT_SPREAD:
            action_detail = f"SELL {self.symbol1} / BUY {self.symbol2}"
        else:
            action_detail = f"{self.symbol1}/{self.symbol2}"

        lines = [
            f"{action} SPREAD",
            f"📊 Pair: {self.symbol1}/{self.symbol2}",
            f"📈 Action: {action_detail}",
            f"📉 Z-Score: {self.zscore:.2f}",
            f"⚖️ Hedge Ratio: {self.hedge_ratio:.4f}",
            f"💪 Strength: {self.strength.value}",
            f"🎯 Target Z: {self.target_zscore:.2f}",
            f"🛑 Stop Z: {self.stop_loss_zscore:.2f}",
        ]

        if self.entry_price1 and self.entry_price2:
            lines.append(f"💰 Prices: {self.symbol1}={self.entry_price1:.2f}, {self.symbol2}={self.entry_price2:.2f}")

        lines.append(f"⏰ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        return "\n".join(lines)


class SignalGenerator:
    """Generate trading signals from pair metrics."""

    def __init__(
        self,
        entry_threshold: Optional[float] = None,
        exit_threshold: Optional[float] = None,
        stop_loss_threshold: Optional[float] = None,
        min_correlation: float = 0.7,
        require_cointegration: bool = True,
    ):
        """
        Initialize SignalGenerator.

        Args:
            entry_threshold: Z-score threshold for entry (default from settings)
            exit_threshold: Z-score threshold for exit (default from settings)
            stop_loss_threshold: Z-score threshold for stop loss (default from settings)
            min_correlation: Minimum correlation for valid signals
            require_cointegration: Require cointegration for signals
        """
        settings = get_settings()

        self.entry_threshold = entry_threshold or settings.entry_threshold
        self.exit_threshold = exit_threshold or settings.exit_threshold
        self.stop_loss_threshold = stop_loss_threshold or settings.stop_loss_threshold
        self.min_correlation = min_correlation
        self.require_cointegration = require_cointegration

        logger.info(
            "SignalGenerator initialized",
            entry_threshold=self.entry_threshold,
            exit_threshold=self.exit_threshold,
            stop_loss_threshold=self.stop_loss_threshold,
            min_correlation=self.min_correlation,
            require_cointegration=self.require_cointegration,
        )

    def generate_signal(
        self,
        metrics: PairMetrics,
        current_position: Optional[SignalType] = None,
        price1: Optional[float] = None,
        price2: Optional[float] = None,
        skip_validation: bool = False,
    ) -> TradingSignal:
        """
        Generate trading signal from pair metrics.

        Args:
            metrics: PairMetrics from pair analysis
            current_position: Current position type (if any)
            price1: Current price of symbol1
            price2: Current price of symbol2
            skip_validation: Skip strict validation (for startup zone check)

        Returns:
            TradingSignal
        """
        zscore = metrics.current_zscore

        # Validate metrics (can be skipped for startup detection)
        if not skip_validation and not self._validate_metrics(metrics):
            return TradingSignal(
                signal_type=SignalType.NO_SIGNAL,
                symbol1=metrics.symbol1,
                symbol2=metrics.symbol2,
                zscore=zscore,
                hedge_ratio=metrics.hedge_ratio,
                metadata={"reason": "Failed validation"},
            )
        
        # Basic validation even when skipping (z-score and hedge ratio must be valid)
        if skip_validation:
            if np.isnan(zscore) or np.isnan(metrics.hedge_ratio):
                return TradingSignal(
                    signal_type=SignalType.NO_SIGNAL,
                    symbol1=metrics.symbol1,
                    symbol2=metrics.symbol2,
                    zscore=zscore,
                    hedge_ratio=metrics.hedge_ratio,
                    metadata={"reason": "Invalid z-score or hedge ratio"},
                )

        # Determine signal type
        signal_type = self._determine_signal_type(zscore, current_position)

        # Calculate signal strength
        strength = self._calculate_strength(zscore)

        # Calculate confidence
        confidence = self._calculate_confidence(metrics)

        # Create signal
        signal = TradingSignal(
            signal_type=signal_type,
            symbol1=metrics.symbol1,
            symbol2=metrics.symbol2,
            zscore=zscore,
            hedge_ratio=metrics.hedge_ratio,
            strength=strength,
            confidence=confidence,
            entry_price1=price1,
            entry_price2=price2,
            target_zscore=self.exit_threshold,
            stop_loss_zscore=self.stop_loss_threshold,
            metadata={
                "correlation": metrics.correlation,
                "is_cointegrated": metrics.is_cointegrated,
                "half_life": metrics.half_life,
                "hurst": metrics.hurst_exponent,
            },
        )

        if signal_type != SignalType.NO_SIGNAL:
            logger.info(
                "Signal generated",
                signal_type=signal_type.value,
                pair=f"{metrics.symbol1}/{metrics.symbol2}",
                zscore=round(zscore, 4),
                strength=strength.value,
                confidence=round(confidence, 4),
            )

        return signal

    def _validate_metrics(self, metrics: PairMetrics) -> bool:
        """Validate metrics for signal generation."""
        # Check correlation
        if abs(metrics.correlation) < self.min_correlation:
            logger.debug(
                "Signal rejected: low correlation",
                correlation=metrics.correlation,
                threshold=self.min_correlation,
            )
            return False

        # Check cointegration
        if self.require_cointegration and not metrics.is_cointegrated:
            logger.debug(
                "Signal rejected: not cointegrated",
                pvalue=metrics.cointegration_pvalue,
            )
            return False

        # Check z-score validity
        if np.isnan(metrics.current_zscore):
            logger.debug("Signal rejected: invalid z-score")
            return False

        # Check hedge ratio validity
        if np.isnan(metrics.hedge_ratio):
            logger.debug("Signal rejected: invalid hedge ratio")
            return False

        return True

    def _determine_signal_type(
        self,
        zscore: float,
        current_position: Optional[SignalType],
    ) -> SignalType:
        """Determine signal type based on z-score and position."""
        # Check for stop loss first
        if abs(zscore) >= self.stop_loss_threshold:
            if current_position == SignalType.LONG_SPREAD:
                return SignalType.STOP_LOSS
            elif current_position == SignalType.SHORT_SPREAD:
                return SignalType.STOP_LOSS

        # Check exit conditions
        if current_position == SignalType.LONG_SPREAD:
            if zscore >= self.exit_threshold:
                return SignalType.EXIT_LONG

        elif current_position == SignalType.SHORT_SPREAD:
            if zscore <= -self.exit_threshold:
                return SignalType.EXIT_SHORT

        # Check entry conditions (no current position)
        if current_position is None or current_position == SignalType.NO_SIGNAL:
            # Long spread: z-score is very negative (spread too low)
            if zscore <= -self.entry_threshold:
                return SignalType.LONG_SPREAD

            # Short spread: z-score is very positive (spread too high)
            if zscore >= self.entry_threshold:
                return SignalType.SHORT_SPREAD

        return SignalType.NO_SIGNAL

    def _calculate_strength(self, zscore: float) -> SignalStrength:
        """Calculate signal strength based on z-score magnitude."""
        abs_zscore = abs(zscore)

        if abs_zscore >= 3.0:
            return SignalStrength.STRONG
        elif abs_zscore >= 2.5:
            return SignalStrength.MODERATE
        else:
            return SignalStrength.WEAK

    def _calculate_confidence(self, metrics: PairMetrics) -> float:
        """
        Calculate confidence score for the signal.

        Score is based on:
        - Correlation strength
        - Cointegration p-value
        - Half-life
        - Hurst exponent
        """
        score = 0.0

        # Correlation component (0-0.25)
        corr_score = min(abs(metrics.correlation) / 0.9, 1.0) * 0.25
        score += corr_score

        # Cointegration component (0-0.25)
        if metrics.is_cointegrated:
            coint_score = max(0, 1 - metrics.cointegration_pvalue / 0.05) * 0.25
            score += coint_score

        # Half-life component (0-0.25)
        # Prefer half-life between 5 and 20
        if 5 <= metrics.half_life <= 20:
            hl_score = 0.25
        elif 3 <= metrics.half_life <= 30:
            hl_score = 0.15
        elif not np.isnan(metrics.half_life) and metrics.half_life < np.inf:
            hl_score = 0.05
        else:
            hl_score = 0.0
        score += hl_score

        # Hurst exponent component (0-0.25)
        # Prefer Hurst < 0.5 (mean-reverting)
        if metrics.hurst_exponent < 0.4:
            hurst_score = 0.25
        elif metrics.hurst_exponent < 0.5:
            hurst_score = 0.15
        elif not np.isnan(metrics.hurst_exponent):
            hurst_score = 0.05
        else:
            hurst_score = 0.0
        score += hurst_score

        return min(score, 1.0)

    def scan_for_signals(
        self,
        pairs_metrics: list[PairMetrics],
        current_prices: Optional[dict[str, float]] = None,
        current_positions: Optional[dict[str, SignalType]] = None,
    ) -> list[TradingSignal]:
        """
        Scan multiple pairs for trading signals.

        Args:
            pairs_metrics: List of PairMetrics to scan
            current_prices: Dictionary of {symbol: current_price}
            current_positions: Dictionary of {pair_key: position_type}

        Returns:
            List of TradingSignals (excluding NO_SIGNAL)
        """
        signals = []
        current_prices = current_prices or {}
        current_positions = current_positions or {}

        for metrics in pairs_metrics:
            pair_key = f"{metrics.symbol1}/{metrics.symbol2}"
            current_pos = current_positions.get(pair_key)

            signal = self.generate_signal(
                metrics,
                current_position=current_pos,
                price1=current_prices.get(metrics.symbol1),
                price2=current_prices.get(metrics.symbol2),
            )

            if signal.signal_type != SignalType.NO_SIGNAL:
                signals.append(signal)

        # Sort by confidence
        signals.sort(key=lambda x: x.confidence, reverse=True)

        logger.info(
            "Signal scan completed",
            pairs_scanned=len(pairs_metrics),
            signals_found=len(signals),
        )

        return signals


def generate_signal_summary(signals: list[TradingSignal]) -> str:
    """
    Generate summary of multiple signals.

    Args:
        signals: List of trading signals

    Returns:
        Formatted summary string
    """
    if not signals:
        return "📊 No signals generated"

    lines = [
        f"📊 Signal Summary ({len(signals)} signals)",
        "=" * 40,
    ]

    # Group by signal type
    by_type = {}
    for sig in signals:
        sig_type = sig.signal_type.value
        if sig_type not in by_type:
            by_type[sig_type] = []
        by_type[sig_type].append(sig)

    for sig_type, sigs in by_type.items():
        lines.append(f"\n{sig_type} ({len(sigs)}):")
        for sig in sigs:
            lines.append(
                f"  • {sig.symbol1}/{sig.symbol2}: "
                f"Z={sig.zscore:.2f}, "
                f"Conf={sig.confidence:.0%}"
            )

    lines.append(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return "\n".join(lines)

