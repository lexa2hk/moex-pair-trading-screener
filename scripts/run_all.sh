#!/bin/bash
# Run all services: FastAPI, Frontend, and Screener Bot

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  MOEX Pair Trading Screener - Starting All Services${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    # Kill all background processes
    if [ ! -z "$API_PID" ]; then
        echo -e "Stopping API server (PID: $API_PID)..."
        kill $API_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        echo -e "Stopping Frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$BOT_PID" ]; then
        echo -e "Stopping Bot (PID: $BOT_PID)..."
        kill $BOT_PID 2>/dev/null || true
    fi
    
    # Kill any remaining child processes
    pkill -P $$ 2>/dev/null || true
    
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Create logs directory
mkdir -p logs

# Start FastAPI server
echo -e "\n${GREEN}[1/3] Starting FastAPI server on port 8000...${NC}"
uv run uvicorn src.api.server:app --host 0.0.0.0 --port 8000 > logs/api.log 2>&1 &
API_PID=$!
sleep 2

if ps -p $API_PID > /dev/null; then
    echo -e "  ${GREEN}✓${NC} API server started (PID: $API_PID)"
else
    echo -e "  ${RED}✗${NC} API server failed to start. Check logs/api.log"
    exit 1
fi

# Start Frontend dev server
echo -e "\n${GREEN}[2/3] Starting Frontend on port 5173...${NC}"
cd frontend
pnpm dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..
sleep 3

if ps -p $FRONTEND_PID > /dev/null; then
    echo -e "  ${GREEN}✓${NC} Frontend started (PID: $FRONTEND_PID)"
else
    echo -e "  ${RED}✗${NC} Frontend failed to start. Check logs/frontend.log"
fi

# Start Screener Bot (optional - only if Telegram is configured)
echo -e "\n${GREEN}[3/3] Starting Screener Bot...${NC}"
if [ -f ".env" ] && grep -q "TELEGRAM_BOT_TOKEN" .env && ! grep -q "TELEGRAM_BOT_TOKEN=$" .env; then
    uv run python -m src.screener > logs/screener.log 2>&1 &
    BOT_PID=$!
    sleep 2
    
    if ps -p $BOT_PID > /dev/null; then
        echo -e "  ${GREEN}✓${NC} Screener bot started (PID: $BOT_PID)"
    else
        echo -e "  ${YELLOW}!${NC} Screener bot exited. Check logs/screener.log"
        BOT_PID=""
    fi
else
    echo -e "  ${YELLOW}!${NC} Telegram not configured. Skipping bot."
    echo -e "    Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env to enable."
    BOT_PID=""
fi

# Print status
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}All services are running!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e ""
echo -e "  ${BLUE}Dashboard:${NC}  http://localhost:5173"
echo -e "  ${BLUE}API Docs:${NC}   http://localhost:8000/docs"
echo -e "  ${BLUE}API:${NC}        http://localhost:8000/api"
echo -e ""
echo -e "  ${YELLOW}Logs:${NC}"
echo -e "    - API:      logs/api.log"
echo -e "    - Frontend: logs/frontend.log"
echo -e "    - Bot:      logs/screener.log"
echo -e ""
echo -e "  Press ${RED}Ctrl+C${NC} to stop all services"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Wait for any process to exit
wait

