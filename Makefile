.PHONY: install dev test lint format clean run-screener run-api run-frontend run-all docker-build docker-run

# Python
install:
	uv sync

dev:
	uv sync --all-extras

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/

format:
	uv run black src/ tests/
	uv run ruff check src/ --fix

# Run individual services
run-screener:
	uv run python -m src.screener

run-api:
	uv run uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && pnpm dev

# Run ALL services together (API + Frontend + Bot)
run-all:
	@mkdir -p logs
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  MOEX Pair Trading Screener - Starting All Services"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "[1/3] Starting FastAPI server on port 8000..."
	@uv run uvicorn src.api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 & echo "$$!" > .pid_api
	@sleep 2
	@echo "  ✓ API server started (http://localhost:8000)"
	@echo ""
	@echo "[2/3] Starting Frontend on port 5173..."
	@cd frontend && pnpm dev > ../logs/frontend.log 2>&1 & echo "$$!" > ../.pid_frontend
	@sleep 3
	@echo "  ✓ Frontend started (http://localhost:5173)"
	@echo ""
	@echo "[3/3] Starting Screener Bot..."
	@uv run python -m src.screener > logs/screener.log 2>&1 & echo "$$!" > .pid_bot
	@sleep 2
	@echo "  ✓ Screener bot started"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  All services running!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "  Dashboard:  http://localhost:5173"
	@echo "  API Docs:   http://localhost:8000/docs"
	@echo ""
	@echo "  Logs: logs/api.log, logs/frontend.log, logs/screener.log"
	@echo ""
	@echo "  Run 'make stop-all' to stop all services"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Run API + Frontend only (no bot)
run-dev:
	@mkdir -p logs
	@echo "Starting API and Frontend..."
	@uv run uvicorn src.api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 & echo "$$!" > .pid_api
	@sleep 2
	@cd frontend && pnpm dev > ../logs/frontend.log 2>&1 & echo "$$!" > ../.pid_frontend
	@sleep 3
	@echo ""
	@echo "✓ Services started!"
	@echo "  Dashboard: http://localhost:5173"
	@echo "  API Docs:  http://localhost:8000/docs"
	@echo ""
	@echo "Run 'make stop-all' to stop"

# Stop all services
stop-all:
	@echo "Stopping all services..."
	@if [ -f .pid_api ]; then kill $$(cat .pid_api) 2>/dev/null || true; rm -f .pid_api; fi
	@if [ -f .pid_frontend ]; then kill $$(cat .pid_frontend) 2>/dev/null || true; rm -f .pid_frontend; fi
	@if [ -f .pid_bot ]; then kill $$(cat .pid_bot) 2>/dev/null || true; rm -f .pid_bot; fi
	@pkill -f "uvicorn src.api.server" 2>/dev/null || true
	@pkill -f "vite" 2>/dev/null || true
	@pkill -f "src.screener" 2>/dev/null || true
	@echo "✓ All services stopped"

# View logs
logs-api:
	@tail -f logs/api.log

logs-frontend:
	@tail -f logs/frontend.log

logs-bot:
	@tail -f logs/screener.log

logs-all:
	@tail -f logs/*.log

# Docker
docker-build:
	docker build -t moex-pair-trading-screener .

docker-run:
	docker run -d --name moex-screener -p 8000:8000 --env-file .env moex-pair-trading-screener

docker-stop:
	docker stop moex-screener && docker rm moex-screener

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -f .pid_api .pid_frontend .pid_bot

# Help
help:
	@echo "MOEX Pair Trading Screener"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Run Services:"
	@echo "  run-all      - Run API + Frontend + Bot (all services)"
	@echo "  run-dev      - Run API + Frontend only (no bot)"
	@echo "  run-api      - Run FastAPI server only"
	@echo "  run-frontend - Run Frontend only"
	@echo "  run-screener - Run Screener bot only"
	@echo "  stop-all     - Stop all running services"
	@echo ""
	@echo "Logs:"
	@echo "  logs-api     - Tail API logs"
	@echo "  logs-frontend - Tail Frontend logs"
	@echo "  logs-bot     - Tail Bot logs"
	@echo "  logs-all     - Tail all logs"
	@echo ""
	@echo "Development:"
	@echo "  install      - Install dependencies"
	@echo "  dev          - Install with dev dependencies"
	@echo "  test         - Run tests"
	@echo "  lint         - Run linter"
	@echo "  format       - Format code"
	@echo "  clean        - Clean cache files"
