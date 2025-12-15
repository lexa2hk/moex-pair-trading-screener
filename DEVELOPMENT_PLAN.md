# Pair Trading Screener - Development Plan

## Project Overview

A pair trading screener for MOEX (Moscow Exchange) that identifies trading opportunities based on statistical arbitrage strategies. The system will monitor stock pairs, calculate correlation and spread metrics, and send notifications via Telegram when trading opportunities are detected.

## Requirements

1. **Python Programming Language** - Core implementation
2. **Telegram Bot to Channel Notification** - Real-time alerts
3. **Containerization** - Docker deployment
4. **MOEX Data & T-Bank Broker** - Data source and broker integration

## Technology Stack

### Core Technologies
- **Python 3.11+** - Main programming language
- **FastAPI** or **Flask** - API framework (optional, for monitoring/control)
- **asyncio** - Asynchronous operations for data fetching

### Data & Analysis
- **pandas** - Data manipulation and analysis
- **numpy** - Numerical computations
- **scipy** - Statistical functions (correlation, cointegration tests)
- **statsmodels** - Advanced statistical modeling

### Data Sources
- **MOEX ISS API** - Official MOEX data via `moexalgo` or `investpy`
- **T-Bank API** - Broker integration for order execution (if available)
- **Alternative**: `yfinance` or custom MOEX scraper if official API is limited

### Telegram Integration
- **python-telegram-bot** or **aiogram** - Telegram bot framework
- **telegram** - Direct Telegram API client

### Containerization
- **Docker** - Container runtime
- **Docker Compose** - Multi-container orchestration (if needed)

### Additional Tools
- **python-dotenv** - Environment variable management
- **pydantic** - Data validation
- **logging** - Structured logging
- **schedule** or **APScheduler** - Task scheduling
- **SQLite** or **PostgreSQL** - Data persistence (optional, for historical data)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Pair Trading Screener                 │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────┐  │
│  │  Data        │    │  Pair        │    │  Signal  │  │
│  │  Collector   │───▶│  Analyzer    │───▶│  Generator│  │
│  │  (MOEX)      │    │  (Stats)     │    │          │  │
│  └──────────────┘    └──────────────┘    └──────────┘  │
│         │                    │                  │        │
│         │                    │                  │        │
│         ▼                    ▼                  ▼        │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Telegram Notification Service             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                           │
│  ┌──────────────────────────────────────────────────┐  │
│  │         T-Bank Broker Integration (Optional)      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Data Collector Module
**Purpose**: Fetch historical and real-time data from MOEX

**Responsibilities**:
- Connect to MOEX ISS API or alternative data source
- Fetch OHLCV data for selected instruments
- Handle rate limiting and API errors
- Cache data locally to reduce API calls
- Support multiple timeframes (1min, 5min, 1h, 1d)

**Key Functions**:
- `fetch_instruments()` - Get list of available instruments
- `fetch_ohlcv(symbol, timeframe, period)` - Get price data
- `get_realtime_quote(symbol)` - Get current price

### 2. Pair Analyzer Module
**Purpose**: Calculate pair trading metrics and identify opportunities

**Responsibilities**:
- Calculate correlation between pairs
- Perform cointegration tests (ADF, Johansen)
- Calculate spread and z-score
- Determine entry/exit signals based on thresholds
- Track pair performance over time

**Key Functions**:
- `calculate_correlation(pair1, pair2, window)` - Rolling correlation
- `test_cointegration(pair1, pair2)` - Cointegration test
- `calculate_spread(pair1, pair2, hedge_ratio)` - Spread calculation
- `calculate_zscore(spread, window)` - Z-score normalization
- `generate_signals(zscore, entry_threshold, exit_threshold)` - Signal generation

### 3. Signal Generator Module
**Purpose**: Generate trading signals based on analysis

**Responsibilities**:
- Combine multiple indicators
- Apply risk filters (volume, liquidity checks)
- Generate signal metadata (entry price, stop loss, take profit)
- Validate signals before sending

**Key Functions**:
- `validate_signal(signal)` - Risk and validation checks
- `format_signal(signal)` - Format for Telegram
- `calculate_position_size(signal, capital)` - Position sizing

### 4. Telegram Notification Service
**Purpose**: Send alerts to Telegram channel

**Responsibilities**:
- Initialize Telegram bot connection
- Format messages with trading signals
- Send notifications to configured channel
- Handle rate limiting and retries
- Support rich formatting (markdown/HTML)

**Key Functions**:
- `send_signal_notification(signal)` - Send trading signal
- `send_daily_summary()` - Daily performance summary
- `send_error_alert(error)` - Error notifications

### 5. T-Bank Broker Integration (Optional)
**Purpose**: Execute trades automatically (if API available)

**Responsibilities**:
- Authenticate with T-Bank API
- Place market/limit orders
- Check account balance and positions
- Monitor order status
- Implement risk management (max position size, stop losses)

**Key Functions**:
- `place_order(signal)` - Execute trade
- `get_account_info()` - Account status
- `get_positions()` - Current positions
- `cancel_order(order_id)` - Cancel order

### 6. Configuration Management
**Purpose**: Manage settings and parameters

**Responsibilities**:
- Load configuration from environment variables
- Validate configuration
- Provide default values
- Support different environments (dev, prod)

**Configuration Parameters**:
- MOEX API credentials/endpoints
- Telegram bot token and channel ID
- T-Bank API credentials
- Trading parameters (entry/exit thresholds, lookback periods)
- Instrument pairs to monitor
- Risk parameters (max position size, stop loss %)

### 7. Scheduler Module
**Purpose**: Orchestrate periodic tasks

**Responsibilities**:
- Schedule data collection (every 1-5 minutes)
- Schedule pair analysis (every 5-15 minutes)
- Schedule daily summaries
- Handle task failures and retries

## Development Phases

### Phase 1: Foundation Setup (Week 1)
- [x] Project structure setup
- [x] Docker configuration
- [x] Environment configuration
- [x] Basic logging setup
- [x] MOEX data connection (test data fetching)

### Phase 2: Data Collection (Week 1-2)
- [x] Implement MOEX data collector
- [x] Data caching mechanism
- [x] Error handling and retries
- [x] Unit tests for data collection

### Phase 3: Pair Analysis (Week 2-3)
- [x] Implement correlation calculations
- [x] Cointegration testing
- [x] Spread and z-score calculations
- [x] Signal generation logic
- [ ] Backtesting framework (optional)

### Phase 4: Telegram Integration (Week 3)
- [x] Telegram bot setup
- [x] Message formatting
- [x] Notification service implementation
- [x] Error handling and rate limiting

### Phase 5: T-Bank Integration (Week 4, Optional)
- [ ] T-Bank API research and authentication
- [ ] Order placement functions
- [ ] Position monitoring
- [ ] Risk management integration

### Phase 6: Containerization (Week 4)
- [ ] Dockerfile optimization
- [ ] Docker Compose setup (if needed)
- [ ] Environment variable management
- [ ] Health checks

### Phase 7: Testing & Optimization (Week 5)
- [ ] Integration testing
- [ ] Performance optimization
- [ ] Error handling improvements
- [ ] Documentation

### Phase 8: Deployment (Week 5-6)
- [ ] Production configuration
- [ ] Monitoring setup
- [ ] Deployment documentation
- [ ] User guide

## Project Structure

```
moex-pair-trading-screener/
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # Configuration management
│   ├── data/
│   │   ├── __init__.py
│   │   ├── collector.py        # MOEX data collection
│   │   └── cache.py            # Data caching
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── pair_analyzer.py    # Pair analysis logic
│   │   ├── signals.py          # Signal generation
│   │   └── statistics.py       # Statistical functions
│   ├── notifications/
│   │   ├── __init__.py
│   │   └── telegram.py         # Telegram integration
│   ├── broker/
│   │   ├── __init__.py
│   │   └── tbank.py            # T-Bank integration
│   └── utils/
│       ├── __init__.py
│       ├── logger.py           # Logging setup
│       └── scheduler.py        # Task scheduling
├── tests/
│   ├── __init__.py
│   ├── test_data_collector.py
│   ├── test_pair_analyzer.py
│   └── test_signals.py
├── .env.example                # Environment variables template
├── .gitignore
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── DEVELOPMENT_PLAN.md         # This file
└── docker-compose.yml          # Docker orchestration
```

## Key Implementation Details

### MOEX Data Integration
- **Primary Option**: MOEX ISS API (REST/WebSocket)
  - Documentation: https://www.moex.com/a2193
  - Endpoints for historical and real-time data
- **Alternative Options**:
  - `moexalgo` Python library (if available)
  - Custom HTTP client with MOEX ISS API
  - Third-party data providers

### Pair Trading Strategy
1. **Pair Selection**: Pre-configured list of correlated pairs
2. **Cointegration Test**: Ensure pairs are cointegrated (long-term relationship)
3. **Spread Calculation**: Calculate normalized spread using hedge ratio
4. **Z-Score**: Normalize spread to identify deviations
5. **Entry Signals**:
   - Long spread when z-score < -2 (spread too low, expect reversion)
   - Short spread when z-score > +2 (spread too high, expect reversion)
6. **Exit Signals**:
   - Exit long when z-score > 0
   - Exit short when z-score < 0
   - Stop loss: z-score exceeds ±3

### Telegram Bot Setup
1. Create bot via @BotFather on Telegram
2. Get bot token
3. Add bot to channel as administrator
4. Get channel ID (use @userinfobot or Telegram API)
5. Configure bot token and channel ID in environment variables

### Docker Configuration
- Multi-stage build for optimization
- Python 3.11 slim base image
- Non-root user for security
- Health check endpoint
- Volume mounts for data persistence (optional)

## Dependencies (requirements.txt)

```
# Core
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
statsmodels>=0.14.0

# Data Sources
requests>=2.31.0
websocket-client>=1.6.0  # For MOEX WebSocket if needed

# Telegram
python-telegram-bot>=20.0  # or aiogram>=3.0

# Configuration
python-dotenv>=1.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0

# Scheduling
APScheduler>=3.10.0

# Logging
structlog>=23.0.0

# Testing (dev)
pytest>=7.4.0
pytest-asyncio>=0.21.0
pytest-cov>=4.1.0

# Optional: Database
sqlalchemy>=2.0.0  # If using database
```

## Environment Variables (.env)

```bash
# MOEX API
MOEX_API_URL=https://iss.moex.com/iss
MOEX_API_TIMEOUT=30

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHANNEL_ID=your_channel_id_here

# T-Bank API (if available)
TBANK_API_URL=https://api.tbank.ru
TBANK_API_KEY=your_api_key
TBANK_API_SECRET=your_api_secret

# Trading Parameters
ENTRY_THRESHOLD=2.0      # Z-score entry threshold
EXIT_THRESHOLD=0.0       # Z-score exit threshold
STOP_LOSS_THRESHOLD=3.0  # Z-score stop loss
LOOKBACK_PERIOD=60       # Days for correlation/cointegration
SPREAD_WINDOW=20         # Days for spread calculation

# Risk Management
MAX_POSITION_SIZE=10000   # Maximum position size in RUB
MAX_OPEN_POSITIONS=5      # Maximum concurrent positions

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/screener.log

# Scheduler
DATA_UPDATE_INTERVAL=300  # Seconds (5 minutes)
ANALYSIS_INTERVAL=900     # Seconds (15 minutes)
```

## Risk Considerations

1. **Data Quality**: Validate MOEX data before analysis
2. **API Rate Limits**: Implement proper rate limiting and caching
3. **Network Failures**: Robust error handling and retry logic
4. **Signal Validation**: Multiple confirmation before sending signals
5. **Position Sizing**: Never risk more than configured limits
6. **Market Hours**: Only trade during MOEX trading hours
7. **Liquidity Checks**: Ensure sufficient volume before signaling

## Future Enhancements

1. **Web Dashboard**: Real-time monitoring interface
2. **Backtesting Engine**: Historical strategy performance
3. **Machine Learning**: ML-based pair selection and signal generation
4. **Multi-Broker Support**: Support for additional brokers
5. **Portfolio Management**: Track multiple pairs simultaneously
6. **Alert Customization**: User-defined alert rules
7. **Performance Analytics**: Detailed performance metrics and reporting

## Notes

- T-Bank API availability and documentation should be verified
- MOEX ISS API may require registration or have usage limits
- Consider paper trading mode before live trading
- Implement comprehensive logging for debugging and audit trails
- Regular monitoring and maintenance required for production use

