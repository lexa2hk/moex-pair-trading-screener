# MOEX Pair Trading Screener

A pair trading screener for Moscow Exchange (MOEX) that identifies statistical arbitrage opportunities and sends notifications via Telegram.

## Features

- 📊 Real-time MOEX data collection
- 🔍 Pair correlation and cointegration analysis
- 📈 Automated signal generation based on z-score deviations
- 📱 Telegram channel notifications
- 🐳 Docker containerization
- 🏦 T-Bank broker integration (optional)

## Quick Start

### Prerequisites

- Python 3.11+
- [UV](https://github.com/astral-sh/uv) package manager
- Docker and Docker Compose (optional)
- Telegram bot token and channel ID

### Installation

1. Install UV (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone the repository:
```bash
git clone <repository-url>
cd moex-pair-trading-screener
```

3. Install dependencies using UV:
```bash
uv pip install -e .
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. Run the screener:
```bash
python src/main.py
```

### Docker Setup

```bash
docker-compose up -d
```

## Development

### Using UV

UV is used for package management instead of pip:

```bash
# Install dependencies
uv pip install -e .

# Install dev dependencies
uv pip install -e ".[dev]"

# Add a new dependency
uv pip install package-name

# Update dependencies
uv pip install --upgrade package-name
```

### Running Tests

```bash
# Install dev dependencies first
uv pip install -e ".[dev]"

# Run all tests
uv run pytest tests/ -v

# Or use the test script
./run_tests.sh

# Or use Make
make test
```

See `TEST_SUMMARY.md` for detailed test documentation.

## Configuration

See `DEVELOPMENT_PLAN.md` for detailed configuration options and environment variables.

## Project Structure

```
moex-pair-trading-screener/
├── src/              # Source code
│   ├── config/       # Configuration management
│   ├── data/         # Data collection
│   ├── utils/        # Utilities
│   └── main.py       # Entry point
├── tests/            # Unit tests
├── docker/           # Docker configuration
├── .env.example      # Environment template
├── pyproject.toml    # Project configuration (UV)
└── requirements.txt  # Python dependencies
```

## Development

See `DEVELOPMENT_PLAN.md` for the complete development roadmap and architecture.

## License

[Specify your license]

## Disclaimer

This software is for educational purposes only. Trading involves risk. Always test thoroughly before using with real money.
