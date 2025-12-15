"""Tests for Telegram notification module."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.analysis.pair_analyzer import PairMetrics
from src.analysis.signals import SignalStrength, SignalType, TradingSignal
from src.notifications.telegram import (
    MessageFormatter,
    RateLimiter,
    SyncTelegramNotifier,
    TelegramNotifier,
)


class TestRateLimiter:
    """Test rate limiter functionality."""

    def test_can_send_initially(self):
        """Test that sending is allowed initially."""
        limiter = RateLimiter(max_messages_per_minute=20, max_messages_per_second=1)
        assert limiter.can_send() is True

    def test_rate_limit_per_second(self):
        """Test per-second rate limiting."""
        limiter = RateLimiter(max_messages_per_minute=20, max_messages_per_second=1)

        # First message should be allowed
        assert limiter.can_send() is True
        limiter.record_message()

        # Second message within same second should be blocked
        assert limiter.can_send() is False

    def test_rate_limit_per_minute(self):
        """Test per-minute rate limiting."""
        limiter = RateLimiter(max_messages_per_minute=3, max_messages_per_second=10)

        for _ in range(3):
            assert limiter.can_send() is True
            limiter.record_message()

        # Fourth message should be blocked
        assert limiter.can_send() is False

    def test_time_until_next(self):
        """Test time calculation until next allowed message."""
        limiter = RateLimiter(max_messages_per_minute=20, max_messages_per_second=1)

        # No wait initially
        assert limiter.time_until_next() == 0

        # After sending, should have to wait
        limiter.record_message()
        wait_time = limiter.time_until_next()
        assert wait_time > 0
        assert wait_time <= 1


class TestMessageFormatter:
    """Test message formatting."""

    @pytest.fixture
    def sample_signal(self):
        """Create sample trading signal."""
        return TradingSignal(
            signal_type=SignalType.LONG_SPREAD,
            symbol1="SBER",
            symbol2="GAZP",
            zscore=-2.5,
            hedge_ratio=1.2,
            strength=SignalStrength.MODERATE,
            confidence=0.75,
            entry_price1=300.5,
            entry_price2=250.0,
            target_zscore=0.0,
            stop_loss_zscore=3.0,
            timestamp=datetime(2024, 1, 15, 10, 30, 0),
        )

    @pytest.fixture
    def sample_metrics(self):
        """Create sample pair metrics."""
        return PairMetrics(
            symbol1="SBER",
            symbol2="GAZP",
            correlation=0.85,
            is_cointegrated=True,
            cointegration_pvalue=0.01,
            hedge_ratio=1.2,
            spread_mean=0,
            spread_std=10,
            current_zscore=-1.5,
            half_life=15.5,
            hurst_exponent=0.4,
            last_updated=datetime(2024, 1, 15, 10, 30, 0),
        )

    def test_format_signal_long(self, sample_signal):
        """Test formatting long spread signal."""
        formatter = MessageFormatter()
        message = formatter.format_signal(sample_signal)

        assert "LONG_SPREAD" in message
        assert "SBER" in message
        assert "GAZP" in message
        assert "Z-Score" in message
        assert "-2.5" in message
        assert "BUY" in message
        assert "SELL" in message

    def test_format_signal_short(self, sample_signal):
        """Test formatting short spread signal."""
        sample_signal.signal_type = SignalType.SHORT_SPREAD
        sample_signal.zscore = 2.5

        formatter = MessageFormatter()
        message = formatter.format_signal(sample_signal)

        assert "SHORT_SPREAD" in message
        assert "SELL" in message  # Sell first symbol
        assert "BUY" in message   # Buy second symbol

    def test_format_signal_exit(self, sample_signal):
        """Test formatting exit signal."""
        sample_signal.signal_type = SignalType.EXIT_LONG
        sample_signal.zscore = 0.1

        formatter = MessageFormatter()
        message = formatter.format_signal(sample_signal)

        assert "EXIT" in message

    def test_format_signal_stop_loss(self, sample_signal):
        """Test formatting stop loss signal."""
        sample_signal.signal_type = SignalType.STOP_LOSS
        sample_signal.zscore = -3.5

        formatter = MessageFormatter()
        message = formatter.format_signal(sample_signal)

        assert "STOP" in message

    def test_format_signal_with_prices(self, sample_signal):
        """Test signal formatting includes prices."""
        formatter = MessageFormatter()
        message = formatter.format_signal(sample_signal)

        assert "300.5" in message
        assert "250.0" in message

    def test_format_pair_metrics(self, sample_metrics):
        """Test formatting pair metrics."""
        formatter = MessageFormatter()
        message = formatter.format_pair_metrics(sample_metrics)

        assert "SBER/GAZP" in message
        assert "0.85" in message  # Correlation
        assert "✅" in message  # Cointegrated
        assert "1.2" in message  # Hedge ratio
        assert "-1.5" in message  # Z-score
        assert "15.5" in message  # Half-life
        assert "mean-reverting" in message  # Hurst interpretation

    def test_format_pair_metrics_not_cointegrated(self, sample_metrics):
        """Test formatting when not cointegrated."""
        sample_metrics.is_cointegrated = False

        formatter = MessageFormatter()
        message = formatter.format_pair_metrics(sample_metrics)

        assert "❌" in message

    def test_format_daily_summary(self, sample_signal, sample_metrics):
        """Test formatting daily summary."""
        signals = [sample_signal]
        pairs = [sample_metrics]
        stats = {"total_scanned": 100, "cointegrated": 15}

        formatter = MessageFormatter()
        message = formatter.format_daily_summary(signals, pairs, stats)

        assert "Daily Summary" in message
        assert "Signals Today" in message
        assert "Long: 1" in message
        assert "Monitored Pairs" in message
        assert "100" in message  # Total scanned
        assert "15" in message  # Cointegrated

    def test_format_daily_summary_empty(self):
        """Test formatting empty daily summary."""
        formatter = MessageFormatter()
        message = formatter.format_daily_summary([], [], None)

        assert "Daily Summary" in message
        assert "No signals today" in message

    def test_format_error(self):
        """Test formatting error message."""
        error = ValueError("Test error message")
        context = "During pair analysis"

        formatter = MessageFormatter()
        message = formatter.format_error(error, context)

        assert "Error Alert" in message
        assert "ValueError" in message
        assert "Test error message" in message
        assert "During pair analysis" in message

    def test_format_info(self):
        """Test formatting info message."""
        formatter = MessageFormatter()
        message = formatter.format_info("Test Title", "Test message content")

        assert "ℹ️" in message
        assert "Test Title" in message
        assert "Test message content" in message

    def test_format_warning(self):
        """Test formatting warning message."""
        formatter = MessageFormatter()
        message = formatter.format_warning("Warning Title", "Warning content")

        assert "⚠️" in message
        assert "Warning Title" in message
        assert "Warning content" in message


class TestTelegramNotifier:
    """Test TelegramNotifier class."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock Telegram bot."""
        with patch("src.notifications.telegram.Bot") as mock:
            bot_instance = AsyncMock()
            bot_instance.get_me = AsyncMock(return_value=MagicMock(
                first_name="TestBot",
                username="test_bot",
            ))
            bot_instance.send_message = AsyncMock(return_value=True)
            mock.return_value = bot_instance
            yield bot_instance

    @pytest.fixture
    def notifier(self, mock_bot):
        """Create notifier with mock bot."""
        return TelegramNotifier(
            bot_token="test_token",
            channel_id="test_channel",
            rate_limit_per_minute=60,
            max_retries=1,
        )

    @pytest.mark.asyncio
    async def test_initialize_success(self, notifier, mock_bot):
        """Test successful initialization."""
        result = await notifier.initialize()

        assert result is True
        mock_bot.get_me.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_missing_token(self):
        """Test initialization with missing token."""
        notifier = TelegramNotifier(bot_token="", channel_id="test")
        result = await notifier.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_initialize_missing_channel(self):
        """Test initialization with missing channel."""
        notifier = TelegramNotifier(bot_token="test", channel_id="")
        result = await notifier.initialize()
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_success(self, notifier, mock_bot):
        """Test successful message sending."""
        result = await notifier.send_message("Test message")

        assert result is True
        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args.kwargs
        assert call_kwargs["chat_id"] == "test_channel"
        assert call_kwargs["text"] == "Test message"

    @pytest.mark.asyncio
    async def test_send_signal(self, notifier, mock_bot):
        """Test sending trading signal."""
        signal = TradingSignal(
            signal_type=SignalType.LONG_SPREAD,
            symbol1="SBER",
            symbol2="GAZP",
            zscore=-2.5,
            hedge_ratio=1.2,
        )

        result = await notifier.send_signal(signal)

        assert result is True
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_signal_no_signal_skipped(self, notifier, mock_bot):
        """Test that NO_SIGNAL is skipped."""
        signal = TradingSignal(
            signal_type=SignalType.NO_SIGNAL,
            symbol1="SBER",
            symbol2="GAZP",
            zscore=0.5,
            hedge_ratio=1.2,
        )

        result = await notifier.send_signal(signal)

        assert result is True
        mock_bot.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_signals_batch(self, notifier, mock_bot):
        """Test sending multiple signals."""
        signals = [
            TradingSignal(
                signal_type=SignalType.LONG_SPREAD,
                symbol1="SBER",
                symbol2="GAZP",
                zscore=-2.5,
                hedge_ratio=1.2,
            ),
            TradingSignal(
                signal_type=SignalType.SHORT_SPREAD,
                symbol1="LKOH",
                symbol2="ROSN",
                zscore=2.5,
                hedge_ratio=1.1,
            ),
        ]

        sent = await notifier.send_signals(signals)

        assert sent == 2
        assert mock_bot.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_send_pair_metrics(self, notifier, mock_bot):
        """Test sending pair metrics."""
        metrics = PairMetrics(
            symbol1="SBER",
            symbol2="GAZP",
            correlation=0.85,
            is_cointegrated=True,
            cointegration_pvalue=0.01,
            hedge_ratio=1.2,
            current_zscore=-1.5,
            half_life=15,
            hurst_exponent=0.4,
        )

        result = await notifier.send_pair_metrics(metrics)

        assert result is True
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_daily_summary(self, notifier, mock_bot):
        """Test sending daily summary."""
        result = await notifier.send_daily_summary([], [], None)

        assert result is True
        mock_bot.send_message.assert_called_once()
        call_text = mock_bot.send_message.call_args.kwargs["text"]
        assert "Daily Summary" in call_text

    @pytest.mark.asyncio
    async def test_send_error(self, notifier, mock_bot):
        """Test sending error notification."""
        error = ValueError("Test error")

        result = await notifier.send_error(error, context="Test context")

        assert result is True
        mock_bot.send_message.assert_called_once()
        call_text = mock_bot.send_message.call_args.kwargs["text"]
        assert "Error" in call_text
        assert "Test error" in call_text

    @pytest.mark.asyncio
    async def test_send_info(self, notifier, mock_bot):
        """Test sending info notification."""
        result = await notifier.send_info("Title", "Message")

        assert result is True
        mock_bot.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_warning(self, notifier, mock_bot):
        """Test sending warning notification."""
        result = await notifier.send_warning("Title", "Message")

        assert result is True
        mock_bot.send_message.assert_called_once()


class TestSyncTelegramNotifier:
    """Test synchronous wrapper."""

    @pytest.fixture
    def mock_bot(self):
        """Create mock Telegram bot."""
        with patch("src.notifications.telegram.Bot") as mock:
            bot_instance = AsyncMock()
            bot_instance.get_me = AsyncMock(return_value=MagicMock(
                first_name="TestBot",
                username="test_bot",
            ))
            bot_instance.send_message = AsyncMock(return_value=True)
            mock.return_value = bot_instance
            yield bot_instance

    @pytest.fixture
    def sync_notifier(self, mock_bot):
        """Create sync notifier with mock bot."""
        return SyncTelegramNotifier(
            bot_token="test_token",
            channel_id="test_channel",
            rate_limit_per_minute=60,
        )

    def test_sync_initialize(self, sync_notifier, mock_bot):
        """Test sync initialization."""
        result = sync_notifier.initialize()
        assert result is True

    def test_sync_send_message(self, sync_notifier, mock_bot):
        """Test sync message sending."""
        result = sync_notifier.send_message("Test")
        assert result is True

    def test_sync_send_signal(self, sync_notifier, mock_bot):
        """Test sync signal sending."""
        signal = TradingSignal(
            signal_type=SignalType.LONG_SPREAD,
            symbol1="SBER",
            symbol2="GAZP",
            zscore=-2.5,
            hedge_ratio=1.2,
        )
        result = sync_notifier.send_signal(signal)
        assert result is True

    def test_sync_send_info(self, sync_notifier, mock_bot):
        """Test sync info sending."""
        result = sync_notifier.send_info("Title", "Message")
        assert result is True

