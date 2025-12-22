"""FastAPI server for trading dashboard."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.analysis.pair_analyzer import PairAnalyzer, PairMetrics
from src.analysis.signals import SignalGenerator, SignalType, TradingSignal
from src.config import get_settings
from src.data.collector import MOEXDataCollector
from src.utils.logger import setup_logger

logger = structlog.get_logger()

# Global state
collector: Optional[MOEXDataCollector] = None
analyzer: Optional[PairAnalyzer] = None
signal_generator: Optional[SignalGenerator] = None

# In-memory storage for demo (replace with database in production)
active_pairs: list[PairMetrics] = []
signals_history: list[TradingSignal] = []
current_positions: dict[str, dict] = {}


# Pydantic models for API responses
class InstrumentResponse(BaseModel):
    secid: str
    shortname: str
    prevprice: Optional[float] = None
    lotsize: Optional[int] = None


class OHLCVDataPoint(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class PairMetricsResponse(BaseModel):
    symbol1: str
    symbol2: str
    correlation: float
    is_cointegrated: bool
    cointegration_pvalue: float
    hedge_ratio: float
    spread_mean: float
    spread_std: float
    current_zscore: float
    half_life: float
    hurst_exponent: float
    last_updated: str
    is_tradeable: bool


class SignalResponse(BaseModel):
    signal_type: str
    symbol1: str
    symbol2: str
    zscore: float
    hedge_ratio: float
    strength: str
    confidence: float
    entry_price1: Optional[float] = None
    entry_price2: Optional[float] = None
    target_zscore: float
    stop_loss_zscore: float
    timestamp: str


class PositionResponse(BaseModel):
    pair_key: str
    symbol1: str
    symbol2: str
    position_type: str
    entry_zscore: float
    current_zscore: float
    entry_price1: Optional[float] = None
    entry_price2: Optional[float] = None
    current_price1: Optional[float] = None
    current_price2: Optional[float] = None
    pnl_percent: Optional[float] = None
    opened_at: str


class SpreadChartData(BaseModel):
    timestamps: list[str]
    spread: list[float]
    zscore: list[float]
    upper_threshold: float
    lower_threshold: float
    exit_threshold: float


class DashboardStats(BaseModel):
    total_pairs: int
    active_signals: int
    open_positions: int
    cointegrated_pairs: int
    avg_correlation: float
    market_status: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup."""
    global collector, analyzer, signal_generator
    
    settings = get_settings()
    setup_logger(log_level=settings.log_level)
    
    logger.info("Initializing API server components...")
    
    collector = MOEXDataCollector()
    analyzer = PairAnalyzer(
        lookback_period=settings.lookback_period,
        zscore_window=settings.spread_window,
    )
    signal_generator = SignalGenerator(
        entry_threshold=settings.entry_threshold,
        exit_threshold=settings.exit_threshold,
        stop_loss_threshold=settings.stop_loss_threshold,
    )
    
    logger.info("API server components initialized")
    yield
    logger.info("API server shutting down")


app = FastAPI(
    title="MOEX Pair Trading Screener API",
    description="API for pair trading dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/instruments", response_model=list[InstrumentResponse])
async def get_instruments(
    market: str = Query(default="shares"),
    board: str = Query(default="TQBR"),
    limit: int = Query(default=50, le=100),
):
    """Get list of available instruments."""
    if not collector:
        raise HTTPException(status_code=503, detail="Collector not initialized")
    
    instruments = collector.get_instruments(market=market, board=board)
    if instruments is None:
        raise HTTPException(status_code=500, detail="Failed to fetch instruments")
    
    result = []
    for _, row in instruments.head(limit).iterrows():
        result.append(InstrumentResponse(
            secid=str(row.get("SECID", "")),
            shortname=str(row.get("SHORTNAME", "")),
            prevprice=float(row["PREVPRICE"]) if pd.notna(row.get("PREVPRICE")) else None,
            lotsize=int(row["LOTSIZE"]) if pd.notna(row.get("LOTSIZE")) else None,
        ))
    
    return result


@app.get("/api/ohlcv/{symbol}", response_model=list[OHLCVDataPoint])
async def get_ohlcv(
    symbol: str,
    interval: int = Query(default=24, description="Candle interval: 1, 10, 60, 24"),
    days: int = Query(default=90, le=365),
):
    """Get OHLCV data for a symbol."""
    if not collector:
        raise HTTPException(status_code=503, detail="Collector not initialized")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    ohlcv = collector.get_ohlcv(
        symbol=symbol,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=500,
    )
    
    if ohlcv is None or len(ohlcv) == 0:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    result = []
    for idx, row in ohlcv.iterrows():
        result.append(OHLCVDataPoint(
            timestamp=str(idx),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]) if "volume" in row and pd.notna(row["volume"]) else None,
        ))
    
    return result


@app.get("/api/quote/{symbol}")
async def get_quote(symbol: str):
    """Get real-time quote for a symbol."""
    if not collector:
        raise HTTPException(status_code=503, detail="Collector not initialized")
    
    quote = collector.get_realtime_quote(symbol)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"Quote not found for {symbol}")
    
    return {
        "symbol": symbol,
        "last": quote.get("LAST"),
        "open": quote.get("OPEN"),
        "high": quote.get("HIGH"),
        "low": quote.get("LOW"),
        "bid": quote.get("BID"),
        "ask": quote.get("OFFER"),
        "volume": quote.get("VOLTODAY"),
        "value": quote.get("VALTODAY"),
        "change_percent": quote.get("LASTTOPREVPRICE"),
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/api/pairs/analyze", response_model=PairMetricsResponse)
async def analyze_pair(
    symbol1: str = Query(...),
    symbol2: str = Query(...),
    days: int = Query(default=90, le=365),
):
    """Analyze a trading pair."""
    if not collector or not analyzer:
        raise HTTPException(status_code=503, detail="Components not initialized")
    
    settings = get_settings()
    end_date = datetime.now()
    
    # Calculate days needed based on interval
    interval = settings.candle_interval
    if interval == 1:
        days_needed = max(days, (settings.lookback_period // 390) + 5)
    elif interval == 60:
        days_needed = max(days, (settings.lookback_period // 7) + 5)
    else:
        days_needed = max(days, settings.lookback_period + 10)
    
    start_date = end_date - timedelta(days=days_needed)
    
    # Fetch data for both symbols
    data1 = collector.get_ohlcv(
        symbol=symbol1,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=settings.lookback_period + 100,
    )
    
    data2 = collector.get_ohlcv(
        symbol=symbol2,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=settings.lookback_period + 100,
    )
    
    if data1 is None or data2 is None:
        raise HTTPException(status_code=404, detail="Failed to fetch data for one or both symbols")
    
    if len(data1) < settings.lookback_period or len(data2) < settings.lookback_period:
        raise HTTPException(status_code=400, detail="Insufficient data for analysis")
    
    # Analyze pair
    metrics = analyzer.analyze_pair(
        data1["close"],
        data2["close"],
        symbol1,
        symbol2,
    )
    
    # Store in active pairs
    global active_pairs
    # Remove existing entry for this pair
    active_pairs = [p for p in active_pairs if not (p.symbol1 == symbol1 and p.symbol2 == symbol2)]
    active_pairs.append(metrics)
    
    return PairMetricsResponse(
        symbol1=metrics.symbol1,
        symbol2=metrics.symbol2,
        correlation=round(metrics.correlation, 4),
        is_cointegrated=metrics.is_cointegrated,
        cointegration_pvalue=round(metrics.cointegration_pvalue, 4),
        hedge_ratio=round(metrics.hedge_ratio, 4),
        spread_mean=round(metrics.spread_mean, 4),
        spread_std=round(metrics.spread_std, 4),
        current_zscore=round(metrics.current_zscore, 4),
        half_life=round(metrics.half_life, 2) if metrics.half_life < float('inf') else 999.0,
        hurst_exponent=round(metrics.hurst_exponent, 4),
        last_updated=metrics.last_updated.isoformat(),
        is_tradeable=metrics.is_tradeable(),
    )


@app.get("/api/pairs/active", response_model=list[PairMetricsResponse])
async def get_active_pairs():
    """Get all active/monitored pairs."""
    return [
        PairMetricsResponse(
            symbol1=m.symbol1,
            symbol2=m.symbol2,
            correlation=round(m.correlation, 4),
            is_cointegrated=m.is_cointegrated,
            cointegration_pvalue=round(m.cointegration_pvalue, 4),
            hedge_ratio=round(m.hedge_ratio, 4),
            spread_mean=round(m.spread_mean, 4),
            spread_std=round(m.spread_std, 4),
            current_zscore=round(m.current_zscore, 4),
            half_life=round(m.half_life, 2) if m.half_life < float('inf') else 999.0,
            hurst_exponent=round(m.hurst_exponent, 4),
            last_updated=m.last_updated.isoformat(),
            is_tradeable=m.is_tradeable(),
        )
        for m in active_pairs
    ]


@app.get("/api/pairs/{symbol1}/{symbol2}/spread", response_model=SpreadChartData)
async def get_spread_chart_data(
    symbol1: str,
    symbol2: str,
    days: int = Query(default=60, le=180),
):
    """Get spread and z-score chart data for a pair."""
    if not collector or not analyzer:
        raise HTTPException(status_code=503, detail="Components not initialized")
    
    settings = get_settings()
    end_date = datetime.now()
    interval = settings.candle_interval
    
    if interval == 1:
        days_needed = max(days, (settings.lookback_period // 390) + 5)
    elif interval == 60:
        days_needed = max(days, (settings.lookback_period // 7) + 5)
    else:
        days_needed = max(days, settings.lookback_period + 10)
    
    start_date = end_date - timedelta(days=days_needed)
    
    data1 = collector.get_ohlcv(
        symbol=symbol1,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=500,
    )
    
    data2 = collector.get_ohlcv(
        symbol=symbol2,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=500,
    )
    
    if data1 is None or data2 is None:
        raise HTTPException(status_code=404, detail="Failed to fetch data")
    
    # Analyze and get spread/zscore
    metrics = analyzer.analyze_pair(data1["close"], data2["close"], symbol1, symbol2)
    
    if metrics.spread is None or metrics.zscore is None:
        raise HTTPException(status_code=500, detail="Failed to calculate spread")
    
    # Convert to lists
    spread_clean = metrics.spread.dropna()
    zscore_clean = metrics.zscore.dropna()
    
    # Align indices
    common_idx = spread_clean.index.intersection(zscore_clean.index)
    
    return SpreadChartData(
        timestamps=[str(ts) for ts in common_idx],
        spread=[round(float(v), 4) for v in spread_clean.loc[common_idx].values],
        zscore=[round(float(v), 4) for v in zscore_clean.loc[common_idx].values],
        upper_threshold=settings.entry_threshold,
        lower_threshold=-settings.entry_threshold,
        exit_threshold=settings.exit_threshold,
    )


@app.get("/api/signals", response_model=list[SignalResponse])
async def get_signals(limit: int = Query(default=50, le=200)):
    """Get recent signals history."""
    return [
        SignalResponse(
            signal_type=s.signal_type.value,
            symbol1=s.symbol1,
            symbol2=s.symbol2,
            zscore=round(s.zscore, 4),
            hedge_ratio=round(s.hedge_ratio, 4),
            strength=s.strength.value,
            confidence=round(s.confidence, 4),
            entry_price1=s.entry_price1,
            entry_price2=s.entry_price2,
            target_zscore=s.target_zscore,
            stop_loss_zscore=s.stop_loss_zscore,
            timestamp=s.timestamp.isoformat(),
        )
        for s in signals_history[-limit:]
    ]


@app.post("/api/signals/generate", response_model=Optional[SignalResponse])
async def generate_signal_for_pair(
    symbol1: str = Query(...),
    symbol2: str = Query(...),
):
    """Generate a trading signal for a pair."""
    if not collector or not analyzer or not signal_generator:
        raise HTTPException(status_code=503, detail="Components not initialized")
    
    settings = get_settings()
    end_date = datetime.now()
    interval = settings.candle_interval
    
    if interval == 1:
        days_needed = (settings.lookback_period // 390) + 5
    elif interval == 60:
        days_needed = (settings.lookback_period // 7) + 5
    else:
        days_needed = settings.lookback_period + 10
    
    start_date = end_date - timedelta(days=days_needed)
    
    data1 = collector.get_ohlcv(
        symbol=symbol1,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=settings.lookback_period + 100,
    )
    
    data2 = collector.get_ohlcv(
        symbol=symbol2,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=settings.lookback_period + 100,
    )
    
    if data1 is None or data2 is None:
        raise HTTPException(status_code=404, detail="Failed to fetch data")
    
    metrics = analyzer.analyze_pair(data1["close"], data2["close"], symbol1, symbol2)
    
    pair_key = f"{symbol1}/{symbol2}"
    current_pos = current_positions.get(pair_key, {}).get("position_type")
    current_pos_enum = SignalType[current_pos] if current_pos else None
    
    signal = signal_generator.generate_signal(
        metrics,
        current_position=current_pos_enum,
        price1=float(data1["close"].iloc[-1]),
        price2=float(data2["close"].iloc[-1]),
    )
    
    if signal.signal_type != SignalType.NO_SIGNAL:
        signals_history.append(signal)
        
        return SignalResponse(
            signal_type=signal.signal_type.value,
            symbol1=signal.symbol1,
            symbol2=signal.symbol2,
            zscore=round(signal.zscore, 4),
            hedge_ratio=round(signal.hedge_ratio, 4),
            strength=signal.strength.value,
            confidence=round(signal.confidence, 4),
            entry_price1=signal.entry_price1,
            entry_price2=signal.entry_price2,
            target_zscore=signal.target_zscore,
            stop_loss_zscore=signal.stop_loss_zscore,
            timestamp=signal.timestamp.isoformat(),
        )
    
    return None


@app.get("/api/positions", response_model=list[PositionResponse])
async def get_positions():
    """Get current open positions."""
    return [
        PositionResponse(**pos)
        for pos in current_positions.values()
    ]


@app.post("/api/positions/open")
async def open_position(
    symbol1: str = Query(...),
    symbol2: str = Query(...),
    position_type: str = Query(..., description="LONG_SPREAD or SHORT_SPREAD"),
    entry_zscore: float = Query(...),
    entry_price1: Optional[float] = Query(default=None),
    entry_price2: Optional[float] = Query(default=None),
):
    """Open a new position (for tracking)."""
    pair_key = f"{symbol1}/{symbol2}"
    
    if pair_key in current_positions:
        raise HTTPException(status_code=400, detail="Position already exists for this pair")
    
    current_positions[pair_key] = {
        "pair_key": pair_key,
        "symbol1": symbol1,
        "symbol2": symbol2,
        "position_type": position_type,
        "entry_zscore": entry_zscore,
        "current_zscore": entry_zscore,
        "entry_price1": entry_price1,
        "entry_price2": entry_price2,
        "current_price1": entry_price1,
        "current_price2": entry_price2,
        "pnl_percent": 0.0,
        "opened_at": datetime.now().isoformat(),
    }
    
    return {"status": "ok", "message": f"Position opened for {pair_key}"}


@app.delete("/api/positions/{symbol1}/{symbol2}")
async def close_position(symbol1: str, symbol2: str):
    """Close a position."""
    pair_key = f"{symbol1}/{symbol2}"
    
    if pair_key not in current_positions:
        raise HTTPException(status_code=404, detail="Position not found")
    
    del current_positions[pair_key]
    return {"status": "ok", "message": f"Position closed for {pair_key}"}


@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get dashboard statistics."""
    now = datetime.now()
    # MOEX trading hours: 10:00 - 18:50 Moscow time
    is_market_open = (
        now.weekday() < 5 and
        now.hour >= 10 and
        (now.hour < 18 or (now.hour == 18 and now.minute <= 50))
    )
    
    cointegrated = sum(1 for p in active_pairs if p.is_cointegrated)
    avg_corr = sum(abs(p.correlation) for p in active_pairs) / len(active_pairs) if active_pairs else 0
    
    active_signals = sum(
        1 for s in signals_history
        if s.signal_type in (SignalType.LONG_SPREAD, SignalType.SHORT_SPREAD)
        and (datetime.now() - s.timestamp).total_seconds() < 3600
    )
    
    return DashboardStats(
        total_pairs=len(active_pairs),
        active_signals=active_signals,
        open_positions=len(current_positions),
        cointegrated_pairs=cointegrated,
        avg_correlation=round(avg_corr, 4),
        market_status="open" if is_market_open else "closed",
    )


@app.get("/api/settings")
async def get_settings_info():
    """Get current settings."""
    settings = get_settings()
    return {
        "entry_threshold": settings.entry_threshold,
        "exit_threshold": settings.exit_threshold,
        "stop_loss_threshold": settings.stop_loss_threshold,
        "lookback_period": settings.lookback_period,
        "spread_window": settings.spread_window,
        "candle_interval": settings.candle_interval,
        "analysis_interval": settings.analysis_interval,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

