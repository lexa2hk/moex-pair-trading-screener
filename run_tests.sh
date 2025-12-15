#!/bin/bash
# Test runner script

set -e

echo "🧪 Running MOEX Pair Trading Screener Tests"
echo "============================================"

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo "❌ UV is not installed. Please install it first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Install dependencies if needed
echo "📦 Installing/updating dependencies..."
uv pip install -e ".[dev]"

# Run tests
echo ""
echo "🚀 Running tests..."
uv run pytest tests/ -v --tb=short

echo ""
echo "✅ Tests completed!"

