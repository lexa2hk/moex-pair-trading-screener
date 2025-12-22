# MOEX Pair Trading Dashboard

A modern React dashboard for monitoring and analyzing pair trading opportunities on the Moscow Exchange (MOEX).

## Features

- **Dashboard**: Overview with key metrics, active pairs, and recent signals
- **Pairs Analysis**: Analyze and monitor cointegrated trading pairs
- **Charts**: Interactive Z-Score, Spread, and Price charts
- **Signals**: Real-time trading signals based on statistical analysis
- **Positions**: Track and manage open trading positions
- **Settings**: View trading parameters and system configuration

## Tech Stack

- **React 19** with TypeScript
- **Material UI 7** for components
- **Chart.js** with react-chartjs-2 for visualizations
- **TanStack Query** for data fetching and caching
- **React Router** for navigation
- **Axios** for API communication
- **Vite** for fast development and building

## Getting Started

### Prerequisites

- Node.js 18+
- pnpm (recommended) or npm

### Installation

```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev
```

The frontend will be available at `http://localhost:5173`

### API Configuration

The frontend connects to the FastAPI backend at `http://localhost:8000` by default.

To change the API URL, create a `.env` file:

```env
VITE_API_URL=http://your-api-server:8000
```

## Running with Backend

1. Start the API server (from project root):
```bash
make run-api
# or
uv run uvicorn src.api.server:app --reload --port 8000
```

2. Start the frontend:
```bash
cd frontend
pnpm dev
```

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts       # API client and types
│   ├── components/
│   │   ├── Layout.tsx      # Main layout with sidebar
│   │   ├── StatsCard.tsx   # Statistics card component
│   │   ├── PairsTable.tsx  # Pairs data table
│   │   ├── PairAnalyzer.tsx # Pair analysis form
│   │   ├── ZScoreChart.tsx # Z-Score visualization
│   │   ├── SpreadChart.tsx # Spread visualization
│   │   ├── PriceChart.tsx  # Price chart
│   │   ├── SignalsList.tsx # Signals list
│   │   └── PositionsTable.tsx # Positions table
│   ├── pages/
│   │   ├── Dashboard.tsx   # Main dashboard
│   │   ├── Pairs.tsx       # Pairs management
│   │   ├── Charts.tsx      # Chart viewer
│   │   ├── Signals.tsx     # Signals history
│   │   ├── Positions.tsx   # Position tracker
│   │   └── Settings.tsx    # Settings page
│   ├── theme.ts            # MUI theme configuration
│   ├── App.tsx             # Root component
│   └── main.tsx            # Entry point
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Design

The dashboard features a dark theme optimized for trading terminals with:

- **Typography**: JetBrains Mono for data, Outfit for headings
- **Colors**: Cyan primary (#00E5FF), Orange secondary (#FF6B35)
- **Accents**: Green for bullish, Red for bearish indicators

## Building for Production

```bash
pnpm build
```

The built files will be in the `dist/` directory.

## License

MIT
