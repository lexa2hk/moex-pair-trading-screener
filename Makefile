.PHONY: install install-dev test run docker-build docker-up docker-down clean

# Install dependencies using UV
install:
	uv pip install -e .

# Install with dev dependencies
install-dev:
	uv pip install -e ".[dev]"

# Run tests
test:
	uv run pytest tests/ -v

# Run tests with coverage
test-cov:
	uv run pytest tests/ --cov=src --cov-report=html --cov-report=term

# Run only unit tests
test-unit:
	uv run pytest tests/ -v -m unit

# Run only integration tests
test-integration:
	uv run pytest tests/ -v -m integration

# Run connection test
test-connection:
	python src/main.py

# Run production screener
run:
	python -m src.screener

# Run production screener with verbose logging
run-debug:
	LOG_LEVEL=DEBUG python -m src.screener

# Build Docker image
docker-build:
	docker-compose build

# Start Docker containers
docker-up:
	docker-compose up -d

# Stop Docker containers
docker-down:
	docker-compose down

# Clean up
clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	rm -rf .pytest_cache
	rm -rf .coverage
	rm -rf htmlcov

