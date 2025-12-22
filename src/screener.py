"""Production screener for MOEX pair trading signals."""

import asyncio
import signal
import sys
from datetime import datetime, time, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import structlog

from src.analysis.pair_analyzer import PairAnalyzer, PairMetrics
from src.analysis.signals import SignalGenerator, SignalType, TradingSignal
from src.config import get_settings
from src.data.collector import MOEXDataCollector
from src.notifications.telegram import TelegramNotifier
from src.notifications.bot_handler import TelegramBotHandler
from src.storage import get_storage, Storage
from src.utils.logger import setup_logger

logger = structlog.get_logger()


class PairTradingScreener:
    """Main screener that monitors pairs and sends signals."""

    def __init__(
        self,
        auto_discover: bool = False,
        top_n_stocks: int = 20,
        enable_bot: bool = True,
        allowed_users: Optional[list[int]] = None,
    ):
        """
        Initialize screener.

        Args:
            auto_discover: If True, auto-discover cointegrated pairs
            top_n_stocks: Number of top liquid stocks for auto-discovery
            enable_bot: Enable interactive Telegram bot
            allowed_users: List of Telegram user IDs allowed to use bot (None = all)
        """
        self.settings = get_settings()

        # Initialize storage
        self.storage: Storage = get_storage()

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
        self.auto_discover = auto_discover
        self.top_n_stocks = top_n_stocks

        # State tracking
        self.last_prices: dict[str, float] = {}
        self.running = False
        self.last_analysis_time: Optional[datetime] = None
        self.last_daily_summary: Optional[datetime] = None
        self.is_first_run: bool = True

        logger.info(
            "PairTradingScreener initialized",
            auto_discover=auto_discover,
            bot_enabled=enable_bot,
            storage_db=self.settings.storage_db_path,
        )

    def _setup_bot_callbacks(self):
        """Setup callbacks for the bot handler."""
        if self.bot_handler:
            self.bot_handler.set_screener_callbacks(
                get_active_pairs=self._get_active_pairs_metrics,
                get_signals_today=self._get_signals_today,
                get_positions=self._get_positions_dict,
                analyze_pair=self.analyze_pair,
                get_pair_data=self.fetch_price_data,
            )

    def _get_active_pairs_metrics(self) -> list[PairMetrics]:
        """Get active pairs with their latest metrics."""
        metrics_data = self.storage.get_latest_metrics()
        result = []
        for m in metrics_data:
            result.append(PairMetrics(
                symbol1=m["symbol1"],
                symbol2=m["symbol2"],
                correlation=m["correlation"] or 0,
                is_cointegrated=bool(m["is_cointegrated"]),
                cointegration_pvalue=m["cointegration_pvalue"] or 1.0,
                hedge_ratio=m["hedge_ratio"] or 1.0,
                spread_mean=m["spread_mean"] or 0,
                spread_std=m["spread_std"] or 1,
                current_zscore=m["current_zscore"] or 0,
                half_life=m["half_life"] or float('inf'),
                hurst_exponent=m["hurst_exponent"] or 0.5,
                last_updated=datetime.fromisoformat(m["analyzed_at"]) if m["analyzed_at"] else datetime.now(),
            ))
        return result

    def _get_signals_today(self) -> list[TradingSignal]:
        """Get today's signals from storage."""
        signals_data = self.storage.get_signals(limit=50)
        result = []
        for s in signals_data:
            result.append(TradingSignal(
                signal_type=SignalType[s["signal_type"]],
                symbol1=s["symbol1"],
                symbol2=s["symbol2"],
                zscore=s["zscore"] or 0,
                hedge_ratio=s["hedge_ratio"] or 1,
                strength=s["strength"] if s["strength"] else "MODERATE",
                confidence=s["confidence"] or 0,
                entry_price1=s["entry_price1"],
                entry_price2=s["entry_price2"],
                target_zscore=s["target_zscore"] or 0,
                stop_loss_zscore=s["stop_loss_zscore"] or 3,
                timestamp=datetime.fromisoformat(s["created_at"]) if s["created_at"] else datetime.now(),
            ))
        return result

    def _get_positions_dict(self) -> dict[str, SignalType]:
        """Get current positions as dict for signal generator."""
        positions = self.storage.get_open_positions()
        return {
            f"{p['symbol1']}/{p['symbol2']}": SignalType[p["position_type"]]
            for p in positions
        }

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

        # Load pairs from settings if storage is empty
        active_pairs = self.storage.get_active_pairs()
        if not active_pairs:
            pairs_from_settings = self._parse_pairs_from_settings()
            for s1, s2 in pairs_from_settings:
                self.storage.add_pair(s1, s2)
            active_pairs = self.storage.get_active_pairs()

        # Auto-discover pairs if enabled and no pairs configured
        if not active_pairs and self.auto_discover:
            logger.info("Auto-discovering cointegrated pairs...")
            discovered = await self._discover_pairs()
            for s1, s2 in discovered:
                self.storage.add_pair(s1, s2)
            active_pairs = self.storage.get_active_pairs()

        if not active_pairs:
            logger.warning(
                "No pairs configured. Add pairs via API, Telegram bot, "
                "or set PAIRS_TO_MONITOR in .env"
            )

        pairs_list = [(p.symbol1, p.symbol2) for p in active_pairs]
        logger.info("Initialized with pairs", pairs=pairs_list)

        # Run initial analysis
        logger.info("Running initial analysis...")
        await self.run_analysis_cycle()

        # Send startup notification
        await self.notifier.send_info(
            "🚀 Screener Started",
            f"Monitoring {len(active_pairs)} pairs:\n"
            + "\n".join(f"• {p.symbol1}/{p.symbol2}" for p in active_pairs[:10])
            + (f"\n... and {len(active_pairs) - 10} more" if len(active_pairs) > 10 else "")
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

        price_data = {}
        end_date = datetime.now()
        
        interval = self.settings.candle_interval
        if interval == 1:
            days_needed = max(1, (self.settings.lookback_period // 390) + 2)
        elif interval == 10:
            days_needed = max(1, (self.settings.lookback_period // 39) + 2)
        elif interval == 60:
            days_needed = max(1, (self.settings.lookback_period // 7) + 2)
        else:
            days_needed = self.settings.lookback_period + 10
        
        start_date = end_date - timedelta(days=days_needed)

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

        tradeable = self.analyzer.find_tradeable_pairs(
            price_data,
            min_correlation=0.7,
            max_cointegration_pvalue=0.05,
            max_half_life=30,
        )

        discovered_pairs = [(m.symbol1, m.symbol2) for m in tradeable[:10]]
        logger.info(f"Discovered {len(discovered_pairs)} tradeable pairs")
        return discovered_pairs

    async def fetch_price_data(self, symbol: str, use_cache: bool = True) -> Optional[pd.DataFrame]:
        """Fetch recent price data for a symbol."""
        end_date = datetime.now()
        
        interval = self.settings.candle_interval
        if interval == 1:
            days_needed = max(1, (self.settings.lookback_period // 390) + 2)
        elif interval == 10:
            days_needed = max(1, (self.settings.lookback_period // 39) + 2)
        elif interval == 60:
            days_needed = max(1, (self.settings.lookback_period // 7) + 2)
        else:
            days_needed = self.settings.lookback_period + 10
        
        start_date = end_date - timedelta(days=days_needed)

        ohlcv = self.collector.get_ohlcv(
            symbol=symbol,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
            interval=interval,
            limit=self.settings.lookback_period + 100,
            use_cache=use_cache,
        )

        return ohlcv

    async def analyze_pair(
        self, symbol1: str, symbol2: str, use_cache: bool = True
    ) -> Optional[PairMetrics]:
        """Analyze a single pair and save results to storage."""
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

        # Ensure pair exists in storage
        pair_id = self.storage.get_pair_id(symbol1, symbol2)
        if pair_id is None:
            pair_id = self.storage.add_pair(symbol1, symbol2)

        # Extract spread/zscore data for charts
        spread_data = None
        zscore_data = None
        timestamps = None
        if metrics.spread is not None and metrics.zscore is not None:
            spread_clean = metrics.spread.dropna()
            zscore_clean = metrics.zscore.dropna()
            common_idx = spread_clean.index.intersection(zscore_clean.index)
            
            spread_data = [float(v) for v in spread_clean.loc[common_idx].values]
            zscore_data = [float(v) for v in zscore_clean.loc[common_idx].values]
            timestamps = [str(ts) for ts in common_idx]

        # Save metrics to storage
        if pair_id:
            self.storage.save_metrics(
                pair_id=pair_id,
                symbol1=symbol1,
                symbol2=symbol2,
                correlation=float(metrics.correlation) if not np.isnan(metrics.correlation) else 0,
                is_cointegrated=bool(metrics.is_cointegrated),  # Convert numpy bool to Python bool
                cointegration_pvalue=float(metrics.cointegration_pvalue),
                hedge_ratio=float(metrics.hedge_ratio) if not np.isnan(metrics.hedge_ratio) else 1.0,
                spread_mean=float(metrics.spread_mean) if not np.isnan(metrics.spread_mean) else 0,
                spread_std=float(metrics.spread_std) if not np.isnan(metrics.spread_std) else 1,
                current_zscore=float(metrics.current_zscore) if not np.isnan(metrics.current_zscore) else 0,
                half_life=float(metrics.half_life) if not np.isnan(metrics.half_life) and metrics.half_life != float('inf') else 999999,
                hurst_exponent=float(metrics.hurst_exponent) if not np.isnan(metrics.hurst_exponent) else 0.5,
                is_tradeable=bool(metrics.is_tradeable()),  # Convert to Python bool
                spread_data=spread_data,
                zscore_data=zscore_data,
                timestamps=timestamps,
            )

        return metrics

    async def run_analysis_cycle(self):
        """Run one analysis cycle for all pairs."""
        logger.info("Running analysis cycle...", is_first_run=self.is_first_run)

        active_pairs = self.storage.get_active_pairs()
        new_signals = []
        current_positions = self._get_positions_dict()

        for pair in active_pairs:
            try:
                metrics = await self.analyze_pair(pair.symbol1, pair.symbol2)
                if metrics is None:
                    continue

                # Generate signal
                pair_key = f"{pair.symbol1}/{pair.symbol2}"
                current_pos = current_positions.get(pair_key)

                signal = self.signal_generator.generate_signal(
                    metrics,
                    current_position=current_pos,
                    price1=self.last_prices.get(pair.symbol1),
                    price2=self.last_prices.get(pair.symbol2),
                    skip_validation=self.is_first_run,
                )

                if signal.signal_type != SignalType.NO_SIGNAL:
                    if self.is_first_run and signal.signal_type in (SignalType.LONG_SPREAD, SignalType.SHORT_SPREAD):
                        signal.metadata["startup_detection"] = True
                        logger.info(
                            "Startup signal detected - pair already in zone",
                            pair=pair_key,
                            signal_type=signal.signal_type.value,
                            zscore=round(signal.zscore, 4),
                        )

                    # Save signal to storage - convert numpy types to Python types
                    self.storage.save_signal(
                        pair_id=pair.id,
                        symbol1=signal.symbol1,
                        symbol2=signal.symbol2,
                        signal_type=signal.signal_type.value,
                        zscore=float(signal.zscore),
                        hedge_ratio=float(signal.hedge_ratio),
                        strength=signal.strength.value if hasattr(signal.strength, 'value') else str(signal.strength),
                        confidence=float(signal.confidence),
                        entry_price1=float(signal.entry_price1) if signal.entry_price1 is not None else None,
                        entry_price2=float(signal.entry_price2) if signal.entry_price2 is not None else None,
                        target_zscore=float(signal.target_zscore),
                        stop_loss_zscore=float(signal.stop_loss_zscore),
                        metadata={k: (bool(v) if isinstance(v, (np.bool_,)) else float(v) if isinstance(v, (np.floating, np.integer)) else v) 
                                  for k, v in (signal.metadata or {}).items()},
                    )

                    new_signals.append(signal)

                    # Update position tracking in storage
                    if signal.signal_type in (SignalType.LONG_SPREAD, SignalType.SHORT_SPREAD):
                        # Check if position already exists
                        existing_pos = self.storage.get_position_for_pair(pair.symbol1, pair.symbol2)
                        if not existing_pos:
                            self.storage.open_position(
                                pair_id=pair.id,
                                symbol1=pair.symbol1,
                                symbol2=pair.symbol2,
                                position_type=signal.signal_type.value,
                                entry_zscore=signal.zscore,
                                entry_price1=signal.entry_price1,
                                entry_price2=signal.entry_price2,
                            )
                    elif signal.signal_type in (
                        SignalType.EXIT_LONG,
                        SignalType.EXIT_SHORT,
                        SignalType.STOP_LOSS,
                    ):
                        self.storage.close_position(pair.symbol1, pair.symbol2)

            except Exception as e:
                logger.error(f"Error analyzing {pair.symbol1}/{pair.symbol2}: {e}")
                continue

        # Send signals via Telegram
        if new_signals:
            logger.info(f"Sending {len(new_signals)} signals")
            await self.notifier.send_signals(new_signals)

        self.last_analysis_time = datetime.now()
        
        if self.is_first_run:
            self.is_first_run = False

        logger.info(
            "Analysis cycle completed",
            pairs_analyzed=len(active_pairs),
            signals_generated=len(new_signals),
        )

    async def send_daily_summary(self):
        """Send daily summary if not sent today."""
        now = datetime.now()

        summary_time_str = self.settings.daily_summary_time
        try:
            hour, minute = map(int, summary_time_str.split(":"))
            summary_time = time(hour, minute)
        except ValueError:
            summary_time = time(18, 0)

        if now.time() >= summary_time:
            if self.last_daily_summary is None or self.last_daily_summary.date() < now.date():
                logger.info("Sending daily summary...")
                
                signals_today = self._get_signals_today()
                active_pairs_metrics = self._get_active_pairs_metrics()
                stats = self.storage.get_stats()
                
                await self.notifier.send_daily_summary(
                    signals_today,
                    active_pairs_metrics,
                    stats={
                        "total_scanned": stats["total_pairs"],
                        "cointegrated": stats["cointegrated_pairs"],
                    },
                )
                self.last_daily_summary = now

    def is_market_hours(self) -> bool:
        """Check if MOEX is open (Moscow time)."""
        now = datetime.now()
        market_open = time(10, 0)
        market_close = time(18, 50)

        if now.weekday() >= 5:
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
                if not self.is_market_hours():
                    logger.debug("Market closed, waiting...")
                    await asyncio.sleep(60)
                    continue

                await self.run_analysis_cycle()
                await self.send_daily_summary()

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

        if self.bot_handler and self.bot_handler.is_running():
            await self.bot_handler.stop()
            logger.info("Bot stopped")


async def main():
    """Main entry point."""
    settings = get_settings()

    setup_logger(
        log_level=settings.log_level,
        log_file=settings.log_file,
    )

    logger.info(
        "MOEX Pair Trading Screener starting",
        version="1.0.0",
        log_level=settings.log_level,
    )

    if not settings.validate_telegram_config():
        logger.error(
            "Telegram not configured! Set TELEGRAM_BOT_TOKEN and "
            "TELEGRAM_CHANNEL_ID in .env file"
        )
        sys.exit(1)

    allowed_users = None
    if hasattr(settings, 'telegram_allowed_users') and settings.telegram_allowed_users:
        try:
            allowed_users = [int(uid.strip()) for uid in settings.telegram_allowed_users.split(",") if uid.strip()]
        except ValueError:
            logger.warning("Invalid TELEGRAM_ALLOWED_USERS format, allowing all users")

    screener = PairTradingScreener(
        auto_discover=settings.auto_discover_pairs,
        top_n_stocks=settings.top_stocks_count,
        enable_bot=settings.telegram_bot_enabled,
        allowed_users=allowed_users,
    )

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
