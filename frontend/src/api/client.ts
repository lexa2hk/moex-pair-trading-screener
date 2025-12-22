import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Types
export interface Instrument {
  secid: string;
  shortname: string;
  prevprice: number | null;
  lotsize: number | null;
}

export interface OHLCVDataPoint {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
}

export interface PairMetrics {
  symbol1: string;
  symbol2: string;
  correlation: number;
  is_cointegrated: boolean;
  cointegration_pvalue: number;
  hedge_ratio: number;
  spread_mean: number;
  spread_std: number;
  current_zscore: number;
  half_life: number;
  hurst_exponent: number;
  last_updated: string;
  is_tradeable: boolean;
}

export interface Signal {
  signal_type: string;
  symbol1: string;
  symbol2: string;
  zscore: number;
  hedge_ratio: number;
  strength: string;
  confidence: number;
  entry_price1: number | null;
  entry_price2: number | null;
  target_zscore: number;
  stop_loss_zscore: number;
  timestamp: string;
}

export interface Position {
  pair_key: string;
  symbol1: string;
  symbol2: string;
  position_type: string;
  entry_zscore: number;
  current_zscore: number;
  entry_price1: number | null;
  entry_price2: number | null;
  current_price1: number | null;
  current_price2: number | null;
  pnl_percent: number | null;
  opened_at: string;
}

export interface SpreadChartData {
  timestamps: string[];
  spread: number[];
  zscore: number[];
  upper_threshold: number;
  lower_threshold: number;
  exit_threshold: number;
}

export interface DashboardStats {
  total_pairs: number;
  active_signals: number;
  open_positions: number;
  cointegrated_pairs: number;
  avg_correlation: number;
  market_status: string;
}

export interface Quote {
  symbol: string;
  last: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  bid: number | null;
  ask: number | null;
  volume: number | null;
  value: number | null;
  change_percent: number | null;
  timestamp: string;
}

export interface Settings {
  entry_threshold: number;
  exit_threshold: number;
  stop_loss_threshold: number;
  lookback_period: number;
  spread_window: number;
  candle_interval: number;
  analysis_interval: number;
}

// API functions
export const api = {
  // Health
  health: () => apiClient.get('/api/health'),

  // Instruments
  getInstruments: (market = 'shares', board = 'TQBR', limit = 50) =>
    apiClient.get<Instrument[]>('/api/instruments', { params: { market, board, limit } }),

  // OHLCV
  getOHLCV: (symbol: string, interval = 24, days = 90) =>
    apiClient.get<OHLCVDataPoint[]>(`/api/ohlcv/${symbol}`, { params: { interval, days } }),

  // Quote
  getQuote: (symbol: string) => apiClient.get<Quote>(`/api/quote/${symbol}`),

  // Pairs
  analyzePair: (symbol1: string, symbol2: string, days = 90) =>
    apiClient.post<PairMetrics>('/api/pairs/analyze', null, {
      params: { symbol1, symbol2, days },
    }),

  getActivePairs: () => apiClient.get<PairMetrics[]>('/api/pairs/active'),

  getSpreadChartData: (symbol1: string, symbol2: string, days = 60) =>
    apiClient.get<SpreadChartData>(`/api/pairs/${symbol1}/${symbol2}/spread`, {
      params: { days },
    }),

  // Signals
  getSignals: (limit = 50) => apiClient.get<Signal[]>('/api/signals', { params: { limit } }),

  generateSignal: (symbol1: string, symbol2: string) =>
    apiClient.post<Signal | null>('/api/signals/generate', null, {
      params: { symbol1, symbol2 },
    }),

  // Positions
  getPositions: () => apiClient.get<Position[]>('/api/positions'),

  openPosition: (
    symbol1: string,
    symbol2: string,
    positionType: string,
    entryZscore: number,
    entryPrice1?: number,
    entryPrice2?: number
  ) =>
    apiClient.post('/api/positions/open', null, {
      params: {
        symbol1,
        symbol2,
        position_type: positionType,
        entry_zscore: entryZscore,
        entry_price1: entryPrice1,
        entry_price2: entryPrice2,
      },
    }),

  closePosition: (symbol1: string, symbol2: string) =>
    apiClient.delete(`/api/positions/${symbol1}/${symbol2}`),

  // Dashboard
  getDashboardStats: () => apiClient.get<DashboardStats>('/api/dashboard/stats'),

  // Settings
  getSettings: () => apiClient.get<Settings>('/api/settings'),
};

export default api;

