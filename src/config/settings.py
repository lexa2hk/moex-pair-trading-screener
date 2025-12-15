"""Application settings and configuration."""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # MOEX API Configuration
    moex_api_url: str = Field(
        default="https://iss.moex.com/iss",
        description="MOEX ISS API base URL",
    )
    moex_api_timeout: int = Field(
        default=30,
        description="MOEX API request timeout in seconds",
    )
    moex_api_max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for MOEX API requests",
        ge=0,
        le=10,
    )
    moex_api_retry_backoff: float = Field(
        default=1.0,
        description="Base backoff (seconds) for MOEX API retries",
        ge=0.0,
    )
    moex_cache_dir: str = Field(
        default="data/cache",
        description="Directory for MOEX data cache",
    )
    moex_cache_ttl_minutes: int = Field(
        default=5,
        description="Cache TTL in minutes for MOEX data",
        ge=0,
    )
    moex_cache_enabled: bool = Field(
        default=True,
        description="Enable file-based caching for MOEX data",
    )

    # Telegram Bot Configuration
    telegram_bot_token: str = Field(
        default="",
        description="Telegram bot token from @BotFather",
    )
    telegram_channel_id: str = Field(
        default="",
        description="Telegram channel ID for notifications",
    )
    telegram_allowed_users: str = Field(
        default="",
        description="Comma-separated list of Telegram user IDs allowed to use the bot (empty = all)",
    )
    telegram_bot_enabled: bool = Field(
        default=True,
        description="Enable interactive Telegram bot with keyboard menu",
    )

    # T-Bank API Configuration (Optional)
    tbank_api_url: Optional[str] = Field(
        default=None,
        description="T-Bank API base URL",
    )
    tbank_api_key: Optional[str] = Field(
        default=None,
        description="T-Bank API key",
    )
    tbank_api_secret: Optional[str] = Field(
        default=None,
        description="T-Bank API secret",
    )

    # Trading Parameters
    entry_threshold: float = Field(
        default=2.0,
        description="Z-score entry threshold",
    )
    exit_threshold: float = Field(
        default=0.0,
        description="Z-score exit threshold",
    )
    stop_loss_threshold: float = Field(
        default=3.0,
        description="Z-score stop loss threshold",
    )
    lookback_period: int = Field(
        default=60,
        description="Days for correlation/cointegration analysis",
    )
    spread_window: int = Field(
        default=20,
        description="Days for spread calculation",
    )

    # Risk Management
    max_position_size: float = Field(
        default=10000.0,
        description="Maximum position size in RUB",
    )
    max_open_positions: int = Field(
        default=5,
        description="Maximum concurrent positions",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    log_file: str = Field(
        default="logs/screener.log",
        description="Log file path",
    )

    # Scheduler
    data_update_interval: int = Field(
        default=300,
        description="Data update interval in seconds (5 minutes)",
    )
    analysis_interval: int = Field(
        default=900,
        description="Analysis interval in seconds (15 minutes)",
    )

    # Screener Configuration
    pairs_to_monitor: str = Field(
        default="",
        description="Comma-separated pairs to monitor (e.g. SBER-VTBR,GAZP-LKOH)",
    )
    auto_discover_pairs: bool = Field(
        default=False,
        description="Auto-discover cointegrated pairs",
    )
    top_stocks_count: int = Field(
        default=20,
        description="Number of top liquid stocks for auto-discovery",
    )
    daily_summary_time: str = Field(
        default="18:00",
        description="Time to send daily summary (HH:MM format)",
    )

    def validate_telegram_config(self) -> bool:
        """Validate Telegram configuration."""
        return bool(self.telegram_bot_token and self.telegram_channel_id)

    def validate_tbank_config(self) -> bool:
        """Validate T-Bank configuration."""
        # Check for placeholder values in API key and secret only
        placeholders = {"your_api_key", "your_api_secret"}
        if (
            isinstance(self.tbank_api_key, str)
            and self.tbank_api_key in placeholders
        ) or (
            isinstance(self.tbank_api_secret, str)
            and self.tbank_api_secret in placeholders
        ):
            return False

        return bool(
            self.tbank_api_url
            and self.tbank_api_key
            and self.tbank_api_secret
        )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

