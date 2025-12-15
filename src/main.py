"""Main entry point for MOEX Pair Trading Screener."""

import asyncio
import sys

import structlog

from src.config import get_settings
from src.data.collector import MOEXDataCollector
from src.utils.logger import setup_logger

logger = structlog.get_logger()


async def test_moex_connection():
    """Test MOEX data connection and fetch sample data."""
    logger.info("Starting MOEX connection test")

    settings = get_settings()
    logger.info("Configuration loaded", moex_url=settings.moex_api_url)

    # Initialize collector
    collector = MOEXDataCollector()

    # Test connection
    if not collector.test_connection():
        logger.error("MOEX API connection test failed")
        return False

    # Test fetching instruments
    logger.info("Testing instrument fetch...")
    instruments = collector.get_instruments()
    if instruments is not None and len(instruments) > 0:
        # Handle possible column naming differences gracefully
        secid_col = None
        for col in instruments.columns:
            if str(col).upper() == "SECID":
                secid_col = col
                break

        sample_tickers = []
        if secid_col:
            sample_tickers = list(instruments[secid_col].head(10))
        elif len(instruments.columns) > 0:
            # Fallback: use the first column as a sample identifier
            sample_tickers = list(instruments.iloc[:, 0].head(10))

        logger.info(
            "Instruments fetched successfully",
            count=len(instruments),
            sample_tickers=sample_tickers,
            columns=list(instruments.columns),
        )
    else:
        logger.warning("Failed to fetch instruments")

    # Test fetching OHLCV data for a popular stock (SBER)
    logger.info("Testing OHLCV data fetch for SBER...")
    from datetime import datetime, timedelta

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    ohlcv = collector.get_ohlcv(
        symbol="SBER",
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=24,  # Daily
        limit=30,
    )

    if ohlcv is not None and len(ohlcv) > 0:
        logger.info(
            "OHLCV data fetched successfully",
            symbol="SBER",
            rows=len(ohlcv),
            latest_close=ohlcv["close"].iloc[-1],
            date_range=f"{ohlcv.index.min()} to {ohlcv.index.max()}",
        )
        logger.debug("Sample OHLCV data", data=ohlcv.tail(5).to_dict())
    else:
        logger.warning("Failed to fetch OHLCV data for SBER")

    # Test real-time quote
    logger.info("Testing real-time quote fetch for SBER...")
    quote = collector.get_realtime_quote("SBER")
    if quote:
        logger.info(
            "Real-time quote fetched successfully",
            symbol="SBER",
            last_price=quote.get("LAST"),
            bid=quote.get("BID"),
            ask=quote.get("OFFER"),
        )
    else:
        logger.warning("Failed to fetch real-time quote for SBER")

    logger.info("MOEX connection test completed")
    return True


def main():
    """Main function."""
    # Load settings
    settings = get_settings()

    # Setup logging
    setup_logger(
        log_level=settings.log_level,
        log_file=settings.log_file,
    )

    logger.info(
        "MOEX Pair Trading Screener starting",
        version="0.1.0",
        log_level=settings.log_level,
    )

    # Validate configuration
    if not settings.validate_telegram_config():
        logger.warning(
            "Telegram configuration incomplete - Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env file"
        )

    # Run MOEX connection test
    try:
        success = asyncio.run(test_moex_connection())
        if success:
            logger.info("Phase 1 setup completed successfully")
            sys.exit(0)
        else:
            logger.error("Phase 1 setup completed with errors")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unexpected error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

