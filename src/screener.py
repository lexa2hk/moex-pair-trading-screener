"""Production screener for MOEX pair trading signals."""

import asyncio
import signal
import sys
from datetime import datetime, time, timedelta
from typing import Optional

import pandas as pd
import structlog

from src.analysis.pair_analyzer import PairAnalyzer, PairMetrics
from src.analysis.signals import SignalGenerator, SignalType, TradingSignal
from src.config import get_settings
from src.data.collector import MOEXDataCollector
from src.notifications.telegram import TelegramNotifier
from src.notifications.bot_handler import TelegramBotHandler
from src.utils.logger import setup_logger

logger = structlog.get_logger()


class PairTradingScreener:
    """Main screener that monitors pairs and sends signals."""

    def __init__(
        self,
        pairs: Optional[list[tuple[str, str]]] = None,
        auto_discover: bool = False,
        top_n_stocks: int = 20,
        enable_bot: bool = True,
        allowed_users: Optional[list[int]] = None,
    ):
        """
        Initialize screener.

        Args:
            pairs: List of pairs to monitor as tuples (SYMBOL1, SYMBOL2)
            auto_discover: If True, auto-discover cointegrated pairs
            top_n_stocks: Number of top liquid stocks for auto-discovery
            enable_bot: Enable interactive Telegram bot
            allowed_users: List of Telegram user IDs allowed to use bot (None = all)
        """
        self.settings = get_settings()

        # Initialize components
        self.collector = MOEXDataCollector()
        self.analyzer = PairAnalyzer(
            lookback_period=self.settings.lookback_period,
            zscore_window=self.settings.spread_window,
        )
        self.signal_generator = SignalGenerator(
            entry_threshold=self.settings.entry_threshold,
            exit_threshold=self.settings.exit_threshold,
            stop_loss_threshold=self.settings.stop_loss_threshold,
        )
        self.notifier = TelegramNotifier()

        # Interactive bot
        self.enable_bot = enable_bot
        self.bot_handler: Optional[TelegramBotHandler] = None
        if enable_bot:
            self.bot_handler = TelegramBotHandler(allowed_users=allowed_users)
            self._setup_bot_callbacks()

        # Configuration
        self.pairs = pairs or []
        self.auto_discover = auto_discover
        self.top_n_stocks = top_n_stocks

        # State tracking
        self.current_positions: dict[str, SignalType] = {}
        self.signals_today: list[TradingSignal] = []
        self.active_pairs: list[PairMetrics] = []
        self.last_prices: dict[str, float] = {}
        self.running = False
        self.last_analysis_time: Optional[datetime] = None
        self.last_daily_summary: Optional[datetime] = None
        self.is_first_run: bool = True  # Track startup for initial zone detection

        logger.info(
            "PairTradingScreener initialized",
            pairs_count=len(self.pairs),
            auto_discover=auto_discover,
            bot_enabled=enable_bot,
        )

    def _setup_bot_callbacks(self):
        """Setup callbacks for the bot handler."""
        if self.bot_handler:
            self.bot_handler.set_screener_callbacks(
                get_active_pairs=lambda: self.active_pairs,
                get_signals_today=lambda: self.signals_today,
                get_positions=lambda: self.current_positions,
                analyze_pair=self.analyze_pair,
                get_pair_data=self.fetch_price_data,
            )

    def _parse_pairs_from_settings(self) -> list[tuple[str, str]]:
        """Parse pairs from settings."""
        pairs_str = self.settings.pairs_to_monitor
        if not pairs_str:
            return []

        pairs = []
        for pair in pairs_str.split(","):
            pair = pair.strip()
            if "-" in pair:
                symbols = pair.split("-")
                if len(symbols) == 2:
                    pairs.append((symbols[0].strip(), symbols[1].strip()))
        return pairs

    async def initialize(self) -> bool:
        """Initialize all components."""
        logger.info("Initializing screener...")

        # Test MOEX connection
        if not self.collector.test_connection():
            logger.error("Failed to connect to MOEX API")
            return False
        logger.info("MOEX connection OK")

        # Initialize Telegram notifier
        if not await self.notifier.initialize():
            logger.error("Failed to initialize Telegram notifier")
            return False
        logger.info("Telegram notifier OK")

        # Start interactive bot
        if self.enable_bot and self.bot_handler:
            if await self.bot_handler.start():
                logger.info("Telegram interactive bot started")
            else:
                logger.warning("Failed to start interactive bot, continuing without it")

        # Load pairs from settings if not provided
        if not self.pairs:
            self.pairs = self._parse_pairs_from_settings()

        # Auto-discover pairs if enabled and no pairs configured
        if not self.pairs and self.auto_discover:
            logger.info("Auto-discovering cointegrated pairs...")
            self.pairs = await self._discover_pairs()

        if not self.pairs:
            logger.error(
                "No pairs configured. Set PAIRS_TO_MONITOR in .env "
                "or enable auto-discovery with AUTO_DISCOVER_PAIRS=true"
            )
            return False

        logger.info("Initialized with pairs", pairs=self.pairs)

        # Run initial analysis to populate active_pairs
        logger.info("Running initial analysis...")
        await self.run_analysis_cycle()

        # Send startup notification
        await self.notifier.send_info(
            "🚀 Screener Started",
            f"Monitoring {len(self.pairs)} pairs:\n"
            + "\n".join(f"• {p[0]}/{p[1]}" for p in self.pairs)
            + f"\n\n💬 Interactive bot: {'✅ Active' if self.bot_handler and self.bot_handler.is_running() else '❌ Disabled'}",
        )

        return True

    async def _discover_pairs(self) -> list[tuple[str, str]]:
        """Auto-discover cointegrated pairs from liquid stocks."""
        logger.info("Fetching top liquid stocks...")

        instruments = self.collector.get_instruments()
        if instruments is None or len(instruments) == 0:
            logger.warning("Failed to fetch instruments")
            return []

        # Get top stocks by volume/liquidity
        # Assuming instruments has SECID column
        secid_col = None
        for col in instruments.columns:
            if str(col).upper() == "SECID":
                secid_col = col
                break

        if not secid_col:
            logger.warning("SECID column not found in instruments")
            return []

        top_stocks = list(instruments[secid_col].head(self.top_n_stocks))
        logger.info(f"Analyzing {len(top_stocks)} stocks for pairs")

        # Fetch price data for all stocks
        price_data = {}
        end_date = datetime.now()
        
        # Calculate start date based on interval
        interval = self.settings.candle_interval
        if interval == 1:  # 1-minute candles
            days_needed = max(1, (self.settings.lookback_period // 390) + 2)
        elif interval == 10:  # 10-minute candles
            days_needed = max(1, (self.settings.lookback_period // 39) + 2)
        elif interval == 60:  # hourly candles
            days_needed = max(1, (self.settings.lookback_period // 7) + 2)
        else:  # daily or other
            days_needed = self.settings.lookback_period + 10
        
        start_date = end_date - timedelta(days=days_needed)

        interval = self.settings.candle_interval
        for symbol in top_stocks:
            ohlcv = self.collector.get_ohlcv(
                symbol=symbol,
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d"),
                interval=interval,
                limit=self.settings.lookback_period + 100,
            )
            if ohlcv is not None and len(ohlcv) >= self.settings.lookback_period:
                price_data[symbol] = ohlcv["close"]

        logger.info(f"Loaded price data for {len(price_data)} stocks")

        # Find tradeable pairs
        tradeable = self.analyzer.find_tradeable_pairs(
            price_data,
            min_correlation=0.7,
            max_cointegration_pvalue=0.05,
            max_half_life=30,
        )

        # Return top 10 pairs
        discovered_pairs = [
            (m.symbol1, m.symbol2) for m in tradeable[:10]
        ]

        logger.info(f"Discovered {len(discovered_pairs)} tradeable pairs")
        return discovered_pairs

    async def fetch_price_data(self, symbol: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """Fetch recent price data for a symbol."""
        end_date = datetime.now()
        
        # Calculate start date based on interval
        # For minute candles, we need fewer days but more candles
        interval = self.settings.candle_interval
        if interval == 1:  # 1-minute candles
            # ~390 trading minutes per day, fetch enough days for lookback_period candles
            days_needed = max(1, (self.settings.lookback_period // 390) + 2)
        elif interval == 10:  # 10-minute candles
            days_needed = max(1, (self.settings.lookback_period // 39) + 2)
        elif interval == 60:  # hourly candles
            days_needed = max(1, (self.settings.lookback_period // 7) + 2)
        else:  # daily or other
            days_needed = self.settings.lookback_period + 10
        
        start_date = end_date - timedelta(days=days_needed)

        ohlcv = self.collector.get_ohlcv(
            symbol=symbol,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            interval=interval,
            limit=self.settings.lookback_period + 100,  # Request enough candles
            use_cache=use_cache,
        )

        return ohlcv

    async def analyze_pair(
        self, symbol1: str, symbol2: str, use_cache: bool = True
    ) -> Optional[PairMetrics]:
        """Analyze a single pair."""
        # Fetch data for both symbols
        data1 = await self.fetch_price_data(symbol1, use_cache=use_cache)
        data2 = await self.fetch_price_data(symbol2, use_cache=use_cache)

        if data1 is None or data2 is None:
            logger.warning(f"Failed to fetch data for {symbol1}/{symbol2}")
            return None

        if len(data1) < self.settings.lookback_period or len(data2) < self.settings.lookback_period:
            logger.warning(f"Insufficient data for {symbol1}/{symbol2}")
            return None

        # Analyze pair
        metrics = self.analyzer.analyze_pair(
            data1["close"],
            data2["close"],
            symbol1,
            symbol2,
        )

        # Update last prices
        self.last_prices[symbol1] = float(data1["close"].iloc[-1])
        self.last_prices[symbol2] = float(data2["close"].iloc[-1])

        return metrics

    async def run_analysis_cycle(self):
        """Run one analysis cycle for all pairs."""
        logger.info("Running analysis cycle...", is_first_run=self.is_first_run)

        self.active_pairs = []
        new_signals = []

        for symbol1, symbol2 in self.pairs:
            try:
                metrics = await self.analyze_pair(symbol1, symbol2)
                if metrics is None:
                    continue

                self.active_pairs.append(metrics)

                # Generate signal
                pair_key = f"{symbol1}/{symbol2}"
                current_pos = self.current_positions.get(pair_key)

                # On first run, use relaxed validation to detect pairs already in zones
                signal = self.signal_generator.generate_signal(
                    metrics,
                    current_position=current_pos,
                    price1=self.last_prices.get(symbol1),
                    price2=self.last_prices.get(symbol2),
                    skip_validation=self.is_first_run,  # Skip strict validation on startup
                )

                if signal.signal_type != SignalType.NO_SIGNAL:
                    # Mark signals detected at startup
                    if self.is_first_run and signal.signal_type in (SignalType.LONG_SPREAD, SignalType.SHORT_SPREAD):
                        signal.metadata["startup_detection"] = True
                        logger.info(
                            "Startup signal detected - pair already in zone",
                            pair=pair_key,
                            signal_type=signal.signal_type.value,
                            zscore=round(signal.zscore, 4),
                        )
                    
                    new_signals.append(signal)
                    self.signals_today.append(signal)

                    # Update position tracking
                    if signal.signal_type in (SignalType.LONG_SPREAD, SignalType.SHORT_SPREAD):
                        self.current_positions[pair_key] = signal.signal_type
                    elif signal.signal_type in (
                        SignalType.EXIT_LONG,
                        SignalType.EXIT_SHORT,
                        SignalType.STOP_LOSS,
                    ):
                        self.current_positions.pop(pair_key, None)

            except Exception as e:
                logger.error(f"Error analyzing {symbol1}/{symbol2}: {e}")
                continue

        # Send signals
        if new_signals:
            logger.info(f"Sending {len(new_signals)} signals")
            await self.notifier.send_signals(new_signals)

        self.last_analysis_time = datetime.now()
        
        # Mark first run as complete
        if self.is_first_run:
            self.is_first_run = False

        logger.info(
            "Analysis cycle completed",
            pairs_analyzed=len(self.active_pairs),
            signals_generated=len(new_signals),
        )

    async def send_daily_summary(self):
        """Send daily summary if not sent today."""
        now = datetime.now()

        # Parse configured summary time
        summary_time_str = self.settings.daily_summary_time
        try:
            hour, minute = map(int, summary_time_str.split(":"))
            summary_time = time(hour, minute)
        except ValueError:
            summary_time = time(18, 0)

        # Check if we should send summary
        if now.time() >= summary_time:
            if self.last_daily_summary is None or self.last_daily_summary.date() < now.date():
                logger.info("Sending daily summary...")
                await self.notifier.send_daily_summary(
                    self.signals_today,
                    self.active_pairs,
                    stats={
                        "total_scanned": len(self.pairs),
                        "cointegrated": sum(1 for p in self.active_pairs if p.is_cointegrated),
                    },
                )
                self.last_daily_summary = now

                # Reset daily signals
                self.signals_today = []

    def is_market_hours(self) -> bool:
        """Check if MOEX is open (Moscow time)."""
        now = datetime.now()
        # MOEX main session: 10:00 - 18:50 Moscow time
        # For simplicity, we'll check local time (adjust for your timezone)
        market_open = time(10, 0)
        market_close = time(18, 50)

        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        return market_open <= now.time() <= market_close

    async def run(self):
        """Main screener loop."""
        if not await self.initialize():
            logger.error("Failed to initialize screener")
            return

        self.running = True
        analysis_interval = self.settings.analysis_interval

        logger.info(
            "Starting screener loop",
            analysis_interval_seconds=analysis_interval,
        )

        while self.running:
            try:
                # Check market hours
                if not self.is_market_hours():
                    logger.debug("Market closed, waiting...")
                    await asyncio.sleep(60)
                    continue

                # Run analysis
                await self.run_analysis_cycle()

                # Check for daily summary
                await self.send_daily_summary()

                # Wait for next cycle
                logger.info(f"Waiting {analysis_interval}s until next analysis...")
                await asyncio.sleep(analysis_interval)

            except Exception as e:
                logger.exception(f"Error in screener loop: {e}")
                try:
                    await self.notifier.send_error(e, "Screener loop error")
                except Exception:
                    pass
                await asyncio.sleep(60)

    async def stop(self):
        """Stop the screener."""
        logger.info("Stopping screener...")
        self.running = False

        # Stop the bot
        if self.bot_handler and self.bot_handler.is_running():
            await self.bot_handler.stop()
            logger.info("Bot stopped")


async def main():
    """Main entry point."""
    settings = get_settings()

    # Setup logging
    setup_logger(
        log_level=settings.log_level,
        log_file=settings.log_file,
    )

    logger.info(
        "MOEX Pair Trading Screener starting",
        version="1.0.0",
        log_level=settings.log_level,
    )

    # Check Telegram configuration
    if not settings.validate_telegram_config():
        logger.error(
            "Telegram not configured! Set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHANNEL_ID in .env file"
        )
        sys.exit(1)

    # Parse allowed users if configured
    allowed_users = None
    if hasattr(settings, 'telegram_allowed_users') and settings.telegram_allowed_users:
        try:
            allowed_users = [int(uid.strip()) for uid in settings.telegram_allowed_users.split(",") if uid.strip()]
        except ValueError:
            logger.warning("Invalid TELEGRAM_ALLOWED_USERS format, allowing all users")

    # Create screener
    screener = PairTradingScreener(
        auto_discover=settings.auto_discover_pairs,
        top_n_stocks=settings.top_stocks_count,
        enable_bot=settings.telegram_bot_enabled,
        allowed_users=allowed_users,
    )

    # Handle shutdown signals
    loop = asyncio.get_running_loop()

    def handle_shutdown(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        asyncio.create_task(screener.stop())

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_shutdown(s))

    try:
        await screener.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await screener.stop()
        logger.info("Screener stopped")


if __name__ == "__main__":
    asyncio.run(main())

