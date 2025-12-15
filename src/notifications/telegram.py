"""Telegram notification service for pair trading alerts."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import structlog
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import RetryAfter, TelegramError, TimedOut

from src.analysis.pair_analyzer import PairMetrics
from src.analysis.signals import SignalType, TradingSignal
from src.config import get_settings

logger = structlog.get_logger()


class NotificationType(Enum):
    """Types of notifications."""

    SIGNAL = "signal"
    DAILY_SUMMARY = "daily_summary"
    ERROR = "error"
    INFO = "info"
    WARNING = "warning"


@dataclass
class RateLimiter:
    """Simple rate limiter for Telegram API."""

    max_messages_per_minute: int = 20
    max_messages_per_second: int = 1
    _message_timestamps: list = field(default_factory=list)

    def can_send(self) -> bool:
        """Check if we can send a message."""
        now = datetime.now()

        # Clean up old timestamps
        self._message_timestamps = [
            ts for ts in self._message_timestamps
            if now - ts < timedelta(minutes=1)
        ]

        # Check per-minute limit
        if len(self._message_timestamps) >= self.max_messages_per_minute:
            return False

        # Check per-second limit
        recent = [ts for ts in self._message_timestamps if now - ts < timedelta(seconds=1)]
        if len(recent) >= self.max_messages_per_second:
            return False

        return True

    def record_message(self):
        """Record a sent message."""
        self._message_timestamps.append(datetime.now())

    def time_until_next(self) -> float:
        """Get seconds until next message can be sent."""
        if self.can_send():
            return 0

        now = datetime.now()

        # Check per-second
        recent = [ts for ts in self._message_timestamps if now - ts < timedelta(seconds=1)]
        if len(recent) >= self.max_messages_per_second:
            oldest_recent = min(recent)
            return (oldest_recent + timedelta(seconds=1) - now).total_seconds()

        # Check per-minute
        oldest = min(self._message_timestamps)
        return (oldest + timedelta(minutes=1) - now).total_seconds()


class MessageFormatter:
    """Format messages for Telegram."""

    @staticmethod
    def format_signal(signal: TradingSignal) -> str:
        """
        Format trading signal for Telegram (HTML format).

        Args:
            signal: Trading signal to format

        Returns:
            HTML formatted message
        """
        emoji_map = {
            SignalType.LONG_SPREAD: "🟢",
            SignalType.SHORT_SPREAD: "🔴",
            SignalType.EXIT_LONG: "⬜",
            SignalType.EXIT_SHORT: "⬜",
            SignalType.STOP_LOSS: "🛑",
            SignalType.NO_SIGNAL: "➖",
        }

        emoji = emoji_map.get(signal.signal_type, "❓")
        
        # Check if this is a startup detection
        is_startup = signal.metadata.get("startup_detection", False)
        startup_label = " <i>(at startup)</i>" if is_startup else ""

        if signal.signal_type == SignalType.LONG_SPREAD:
            action = f"<b>BUY</b> {signal.symbol1} / <b>SELL</b> {signal.symbol2}"
        elif signal.signal_type == SignalType.SHORT_SPREAD:
            action = f"<b>SELL</b> {signal.symbol1} / <b>BUY</b> {signal.symbol2}"
        elif signal.signal_type in (SignalType.EXIT_LONG, SignalType.EXIT_SHORT):
            action = f"<b>EXIT</b> {signal.symbol1}/{signal.symbol2}"
        elif signal.signal_type == SignalType.STOP_LOSS:
            action = f"<b>STOP LOSS</b> {signal.symbol1}/{signal.symbol2}"
        else:
            action = f"{signal.symbol1}/{signal.symbol2}"

        lines = [
            f"{emoji} <b>{signal.signal_type.value}</b>{startup_label}",
            "",
            f"📊 <b>Pair:</b> {signal.symbol1}/{signal.symbol2}",
            f"📈 <b>Action:</b> {action}",
            f"📉 <b>Z-Score:</b> {signal.zscore:.2f}",
            f"⚖️ <b>Hedge Ratio:</b> {signal.hedge_ratio:.4f}",
            f"💪 <b>Strength:</b> {signal.strength.value}",
            f"🎯 <b>Confidence:</b> {signal.confidence:.0%}",
        ]

        if signal.entry_price1 and signal.entry_price2:
            lines.append(
                f"💰 <b>Prices:</b> {signal.symbol1}={signal.entry_price1:.2f}, "
                f"{signal.symbol2}={signal.entry_price2:.2f}"
            )

        lines.extend([
            "",
            f"🎯 Target Z: {signal.target_zscore:.2f}",
            f"🛑 Stop Z: ±{signal.stop_loss_zscore:.2f}",
            "",
            f"⏰ {signal.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ])

        return "\n".join(lines)

    @staticmethod
    def format_pair_metrics(metrics: PairMetrics) -> str:
        """
        Format pair metrics for Telegram (HTML format).

        Args:
            metrics: Pair metrics to format

        Returns:
            HTML formatted message
        """
        coint_emoji = "✅" if metrics.is_cointegrated else "❌"

        lines = [
            f"📊 <b>Pair Analysis: {metrics.symbol1}/{metrics.symbol2}</b>",
            "",
            f"📈 <b>Correlation:</b> {metrics.correlation:.4f}",
            f"🔗 <b>Cointegrated:</b> {coint_emoji} (p={metrics.cointegration_pvalue:.4f})",
            f"⚖️ <b>Hedge Ratio:</b> {metrics.hedge_ratio:.4f}",
            f"📉 <b>Current Z-Score:</b> {metrics.current_zscore:.2f}",
        ]

        if metrics.half_life != float("inf"):
            lines.append(f"⏱️ <b>Half-Life:</b> {metrics.half_life:.1f} days")

        if metrics.hurst_exponent:
            hurst_desc = "mean-reverting" if metrics.hurst_exponent < 0.5 else "trending"
            lines.append(f"📐 <b>Hurst:</b> {metrics.hurst_exponent:.3f} ({hurst_desc})")

        lines.extend([
            "",
            f"⏰ {metrics.last_updated.strftime('%Y-%m-%d %H:%M:%S')}",
        ])

        return "\n".join(lines)

    @staticmethod
    def format_daily_summary(
        signals_today: list[TradingSignal],
        active_pairs: list[PairMetrics],
        stats: Optional[dict] = None,
    ) -> str:
        """
        Format daily summary for Telegram (HTML format).

        Args:
            signals_today: Signals generated today
            active_pairs: Currently monitored pairs
            stats: Optional statistics dictionary

        Returns:
            HTML formatted message
        """
        today = datetime.now().strftime("%Y-%m-%d")

        lines = [
            f"📅 <b>Daily Summary - {today}</b>",
            "=" * 30,
            "",
        ]

        # Signal summary
        if signals_today:
            long_signals = [s for s in signals_today if s.signal_type == SignalType.LONG_SPREAD]
            short_signals = [s for s in signals_today if s.signal_type == SignalType.SHORT_SPREAD]
            exit_signals = [s for s in signals_today if s.signal_type in (
                SignalType.EXIT_LONG, SignalType.EXIT_SHORT
            )]
            stop_signals = [s for s in signals_today if s.signal_type == SignalType.STOP_LOSS]

            lines.append(f"📊 <b>Signals Today:</b> {len(signals_today)}")
            lines.append(f"  🟢 Long: {len(long_signals)}")
            lines.append(f"  🔴 Short: {len(short_signals)}")
            lines.append(f"  ⬜ Exit: {len(exit_signals)}")
            lines.append(f"  🛑 Stop Loss: {len(stop_signals)}")
            lines.append("")
        else:
            lines.append("📊 <b>No signals today</b>")
            lines.append("")

        # Active pairs
        if active_pairs:
            lines.append(f"👀 <b>Monitored Pairs:</b> {len(active_pairs)}")

            # Top 5 pairs by absolute z-score
            top_pairs = sorted(
                active_pairs,
                key=lambda x: abs(x.current_zscore),
                reverse=True
            )[:5]

            for p in top_pairs:
                z_emoji = "🔥" if abs(p.current_zscore) >= 2.0 else "📈"
                lines.append(f"  {z_emoji} {p.symbol1}/{p.symbol2}: Z={p.current_zscore:.2f}")
            lines.append("")

        # Optional stats
        if stats:
            if "total_scanned" in stats:
                lines.append(f"🔍 <b>Pairs Scanned:</b> {stats['total_scanned']}")
            if "cointegrated" in stats:
                lines.append(f"✅ <b>Cointegrated:</b> {stats['cointegrated']}")
            if "api_calls" in stats:
                lines.append(f"🌐 <b>API Calls:</b> {stats['api_calls']}")
            lines.append("")

        lines.append(f"⏰ Generated: {datetime.now().strftime('%H:%M:%S')}")

        return "\n".join(lines)

    @staticmethod
    def format_error(
        error: Exception,
        context: Optional[str] = None,
    ) -> str:
        """
        Format error message for Telegram (HTML format).

        Args:
            error: Exception that occurred
            context: Optional context about where error occurred

        Returns:
            HTML formatted message
        """
        lines = [
            "🚨 <b>Error Alert</b>",
            "",
        ]

        if context:
            lines.append(f"📍 <b>Context:</b> {context}")

        lines.extend([
            f"❌ <b>Error:</b> {type(error).__name__}",
            f"📝 <b>Message:</b> {str(error)}",
            "",
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ])

        return "\n".join(lines)

    @staticmethod
    def format_info(title: str, message: str) -> str:
        """
        Format info message for Telegram (HTML format).

        Args:
            title: Message title
            message: Message content

        Returns:
            HTML formatted message
        """
        return f"ℹ️ <b>{title}</b>\n\n{message}\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"

    @staticmethod
    def format_warning(title: str, message: str) -> str:
        """
        Format warning message for Telegram (HTML format).

        Args:
            title: Warning title
            message: Warning content

        Returns:
            HTML formatted message
        """
        return f"⚠️ <b>{title}</b>\n\n{message}\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"


class TelegramNotifier:
    """Telegram notification service."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        channel_id: Optional[str] = None,
        rate_limit_per_minute: int = 20,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Telegram notifier.

        Args:
            bot_token: Telegram bot token (from @BotFather)
            channel_id: Telegram channel ID for notifications
            rate_limit_per_minute: Maximum messages per minute
            max_retries: Maximum retry attempts for failed sends
            retry_delay: Base delay between retries (seconds)
        """
        settings = get_settings()

        self.bot_token = bot_token or settings.telegram_bot_token
        self.channel_id = channel_id or settings.telegram_channel_id
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limiter = RateLimiter(max_messages_per_minute=rate_limit_per_minute)
        self.formatter = MessageFormatter()

        self._bot: Optional[Bot] = None
        self._initialized = False

        logger.info(
            "TelegramNotifier created",
            channel_id=self.channel_id,
            rate_limit=rate_limit_per_minute,
            max_retries=max_retries,
        )

    def _validate_config(self) -> bool:
        """Validate Telegram configuration."""
        if not self.bot_token:
            logger.error("Telegram bot token not configured")
            return False

        if not self.channel_id:
            logger.error("Telegram channel ID not configured")
            return False

        return True

    def _get_bot(self) -> Bot:
        """Get or create Bot instance."""
        if self._bot is None:
            self._bot = Bot(token=self.bot_token)
        return self._bot

    async def initialize(self) -> bool:
        """
        Initialize and test Telegram connection.

        Returns:
            True if initialization successful
        """
        if not self._validate_config():
            return False

        try:
            bot = self._get_bot()
            me = await bot.get_me()
            logger.info(
                "Telegram bot initialized",
                bot_name=me.first_name,
                bot_username=me.username,
            )
            self._initialized = True
            return True

        except TelegramError as e:
            logger.error("Failed to initialize Telegram bot", error=str(e))
            return False

    async def send_message(
        self,
        text: str,
        parse_mode: str = ParseMode.HTML,
        disable_notification: bool = False,
    ) -> bool:
        """
        Send a message to the configured channel.

        Args:
            text: Message text
            parse_mode: Message parse mode (HTML or Markdown)
            disable_notification: Disable notification sound

        Returns:
            True if message sent successfully
        """
        if not self._validate_config():
            return False

        # Check rate limit
        if not self.rate_limiter.can_send():
            wait_time = self.rate_limiter.time_until_next()
            logger.warning(
                "Rate limit reached, waiting",
                wait_seconds=wait_time,
            )
            await asyncio.sleep(wait_time)

        bot = self._get_bot()

        for attempt in range(self.max_retries):
            try:
                await bot.send_message(
                    chat_id=self.channel_id,
                    text=text,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                )
                self.rate_limiter.record_message()
                logger.debug("Message sent successfully")
                return True

            except RetryAfter as e:
                logger.warning(
                    "Telegram rate limited, waiting",
                    retry_after=e.retry_after,
                )
                await asyncio.sleep(e.retry_after)

            except TimedOut:
                logger.warning(
                    "Telegram request timed out",
                    attempt=attempt + 1,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))

            except TelegramError as e:
                logger.error(
                    "Failed to send Telegram message",
                    error=str(e),
                    attempt=attempt + 1,
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))

        logger.error("Failed to send message after all retries")
        return False

    async def send_signal(
        self,
        signal: TradingSignal,
        disable_notification: bool = False,
    ) -> bool:
        """
        Send trading signal notification.

        Args:
            signal: Trading signal to send
            disable_notification: Disable notification sound

        Returns:
            True if sent successfully
        """
        if signal.signal_type == SignalType.NO_SIGNAL:
            logger.debug("Skipping NO_SIGNAL notification")
            return True

        text = self.formatter.format_signal(signal)

        logger.info(
            "Sending signal notification",
            signal_type=signal.signal_type.value,
            pair=f"{signal.symbol1}/{signal.symbol2}",
        )

        return await self.send_message(
            text,
            disable_notification=disable_notification,
        )

    async def send_signals(
        self,
        signals: list[TradingSignal],
        disable_notification: bool = False,
    ) -> int:
        """
        Send multiple signal notifications.

        Args:
            signals: List of trading signals
            disable_notification: Disable notification sound

        Returns:
            Number of successfully sent messages
        """
        # Filter out NO_SIGNAL
        signals = [s for s in signals if s.signal_type != SignalType.NO_SIGNAL]

        if not signals:
            return 0

        sent = 0
        for signal in signals:
            if await self.send_signal(signal, disable_notification):
                sent += 1
            # Small delay between messages
            await asyncio.sleep(0.5)

        logger.info(
            "Batch signal send completed",
            total=len(signals),
            sent=sent,
        )

        return sent

    async def send_pair_metrics(
        self,
        metrics: PairMetrics,
        disable_notification: bool = True,
    ) -> bool:
        """
        Send pair metrics notification.

        Args:
            metrics: Pair metrics to send
            disable_notification: Disable notification sound (default True for info)

        Returns:
            True if sent successfully
        """
        text = self.formatter.format_pair_metrics(metrics)

        logger.info(
            "Sending pair metrics",
            pair=f"{metrics.symbol1}/{metrics.symbol2}",
        )

        return await self.send_message(
            text,
            disable_notification=disable_notification,
        )

    async def send_daily_summary(
        self,
        signals_today: list[TradingSignal],
        active_pairs: list[PairMetrics],
        stats: Optional[dict] = None,
    ) -> bool:
        """
        Send daily summary notification.

        Args:
            signals_today: Signals generated today
            active_pairs: Currently monitored pairs
            stats: Optional statistics

        Returns:
            True if sent successfully
        """
        text = self.formatter.format_daily_summary(
            signals_today,
            active_pairs,
            stats,
        )

        logger.info("Sending daily summary")

        return await self.send_message(text, disable_notification=False)

    async def send_error(
        self,
        error: Exception,
        context: Optional[str] = None,
    ) -> bool:
        """
        Send error notification.

        Args:
            error: Exception that occurred
            context: Optional context

        Returns:
            True if sent successfully
        """
        text = self.formatter.format_error(error, context)

        logger.info(
            "Sending error notification",
            error_type=type(error).__name__,
        )

        return await self.send_message(text, disable_notification=False)

    async def send_info(
        self,
        title: str,
        message: str,
        disable_notification: bool = True,
    ) -> bool:
        """
        Send info notification.

        Args:
            title: Message title
            message: Message content
            disable_notification: Disable notification sound

        Returns:
            True if sent successfully
        """
        text = self.formatter.format_info(title, message)
        return await self.send_message(text, disable_notification=disable_notification)

    async def send_warning(
        self,
        title: str,
        message: str,
        disable_notification: bool = False,
    ) -> bool:
        """
        Send warning notification.

        Args:
            title: Warning title
            message: Warning content
            disable_notification: Disable notification sound

        Returns:
            True if sent successfully
        """
        text = self.formatter.format_warning(title, message)
        return await self.send_message(text, disable_notification=disable_notification)


# Synchronous wrapper for use in non-async contexts
class SyncTelegramNotifier:
    """Synchronous wrapper for TelegramNotifier."""

    def __init__(self, *args, **kwargs):
        """Initialize with same args as TelegramNotifier."""
        self._async_notifier = TelegramNotifier(*args, **kwargs)

    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(coro)

    def initialize(self) -> bool:
        """Initialize Telegram connection."""
        return self._run_async(self._async_notifier.initialize())

    def send_message(self, text: str, **kwargs) -> bool:
        """Send a message."""
        return self._run_async(self._async_notifier.send_message(text, **kwargs))

    def send_signal(self, signal: TradingSignal, **kwargs) -> bool:
        """Send trading signal."""
        return self._run_async(self._async_notifier.send_signal(signal, **kwargs))

    def send_signals(self, signals: list[TradingSignal], **kwargs) -> int:
        """Send multiple signals."""
        return self._run_async(self._async_notifier.send_signals(signals, **kwargs))

    def send_pair_metrics(self, metrics: PairMetrics, **kwargs) -> bool:
        """Send pair metrics."""
        return self._run_async(self._async_notifier.send_pair_metrics(metrics, **kwargs))

    def send_daily_summary(self, *args, **kwargs) -> bool:
        """Send daily summary."""
        return self._run_async(self._async_notifier.send_daily_summary(*args, **kwargs))

    def send_error(self, error: Exception, **kwargs) -> bool:
        """Send error notification."""
        return self._run_async(self._async_notifier.send_error(error, **kwargs))

    def send_info(self, title: str, message: str, **kwargs) -> bool:
        """Send info notification."""
        return self._run_async(self._async_notifier.send_info(title, message, **kwargs))

    def send_warning(self, title: str, message: str, **kwargs) -> bool:
        """Send warning notification."""
        return self._run_async(self._async_notifier.send_warning(title, message, **kwargs))

