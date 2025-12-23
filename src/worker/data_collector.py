"""Scheduled worker for collecting MOEX price data."""

import asyncio
import signal
from datetime import datetime, timedelta
from typing import Optional

import structlog

from src.config import get_settings
from src.data.collector import MOEXDataCollector
from src.storage import get_storage, Storage

logger = structlog.get_logger()


class DataCollectionWorker:
    """Worker that periodically collects price data from MOEX."""

    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        interval: Optional[int] = None,
    ):
        """
        Initialize data collection worker.

        Args:
            symbols: List of symbols to collect (default: from active pairs)
            interval: Collection interval in seconds (default: from settings)
        """
        self.settings = get_settings()
        self.collector = MOEXDataCollector()
        self.storage: Storage = get_storage()

        self.symbols = symbols
        self.interval = interval or self.settings.data_update_interval
        self.running = False

        logger.info(
            "DataCollectionWorker initialized",
            symbols=self.symbols,
            interval_seconds=self.interval,
        )

    def _get_symbols_from_pairs(self) -> list[str]:
        """Get unique symbols from active pairs."""
        active_pairs = self.storage.get_active_pairs()
        symbols = set()
        for pair in active_pairs:
            symbols.add(pair.symbol1)
            symbols.add(pair.symbol2)
        return sorted(symbols)

    def _get_date_range(self, days: int = 7) -> tuple[str, str]:
        """Get date range for fetching data."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")

    async def collect_symbol_data(self, symbol: str) -> bool:
        """
        Collect and store data for a single symbol.

        Args:
            symbol: Security ticker

        Returns:
            True if successful, False otherwise
        """
        try:
            # Fetch latest daily data
            start_date, end_date = self._get_date_range(days=7)
            ohlcv = self.collector.get_ohlcv(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=24,  # Daily candles
                limit=10,
                use_cache=False,  # Always fetch fresh data
            )

            if ohlcv is not None and not ohlcv.empty:
                self.storage.save_price_data(symbol, ohlcv, interval=24)
                logger.debug(
                    "Collected daily data",
                    symbol=symbol,
                    rows=len(ohlcv),
                    last_date=str(ohlcv.index.max()) if hasattr(ohlcv.index, 'max') else 'unknown',
                )

            # Also collect intraday data if during market hours
            now = datetime.now()
            if now.time() >= datetime(1, 1, 1, 10, 0).time() and now.time() <= datetime(1, 1, 1, 19, 0).time():
                ohlcv_intraday = self.collector.get_ohlcv(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    interval=1,  # Minute candles
                    limit=60,
                    use_cache=False,
                )

                if ohlcv_intraday is not None and not ohlcv_intraday.empty:
                    self.storage.save_price_data(symbol, ohlcv_intraday, interval=1)
                    logger.debug(
                        "Collected intraday data",
                        symbol=symbol,
                        rows=len(ohlcv_intraday),
                    )

            return True

        except Exception as e:
            logger.error(
                "Failed to collect data for symbol",
                symbol=symbol,
                error=str(e),
            )
            return False

    async def run_collection_cycle(self) -> int:
        """Run one data collection cycle for all symbols."""
        symbols = self.symbols or self._get_symbols_from_pairs()

        if not symbols:
            logger.warning("No symbols to collect")
            return 0

        logger.info(
            "Running data collection cycle",
            symbols_count=len(symbols),
        )

        success_count = 0
        for symbol in symbols:
            if await self.collect_symbol_data(symbol):
                success_count += 1
            await asyncio.sleep(1)  # Rate limiting

        logger.info(
            "Data collection cycle completed",
            total=len(symbols),
            successful=success_count,
        )
        return success_count

    async def run(self):
        """Run the worker loop."""
        if not self.collector.test_connection():
            logger.error("Failed to connect to MOEX API")
            return

        self.running = True
        logger.info("Starting data collection worker")

        while self.running:
            try:
                await self.run_collection_cycle()
                logger.info(f"Waiting {self.interval}s until next collection...")
                await asyncio.sleep(self.interval)

            except Exception as e:
                logger.exception(f"Error in worker loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    def stop(self):
        """Stop the worker."""
        logger.info("Stopping data collection worker...")
        self.running = False


async def main():
    """Main entry point for data collection worker."""
    settings = get_settings()

    # Setup logging
    import logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper()),
        format="%(message)s",
    )

    logger.info("Starting MOEX Data Collection Worker")

    worker = DataCollectionWorker()

    loop = asyncio.get_running_loop()

    def handle_shutdown(sig):
        logger.info(f"Received signal {sig}, shutting down...")
        worker.stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda s=sig: handle_shutdown(s))

    try:
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        worker.stop()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
