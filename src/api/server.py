"""FastAPI server for trading dashboard - reads from shared storage."""

from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta
from typing import Optional

import pandas as pd
import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import get_settings
from src.data.collector import MOEXDataCollector
from src.analysis.pair_analyzer import PairAnalyzer
from src.storage import get_storage, Storage
from src.utils.logger import setup_logger
import numpy as np

logger = structlog.get_logger()

# Global state
collector: Optional[MOEXDataCollector] = None
storage: Optional[Storage] = None
analyzer: Optional[PairAnalyzer] = None


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


class AddPairRequest(BaseModel):
    symbol1: str
    symbol2: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup."""
    global collector, storage, analyzer
    
    settings = get_settings()
    setup_logger(log_level=settings.log_level)
    
    logger.info("Initializing API server components...")
    
    collector = MOEXDataCollector()
    storage = get_storage()
    analyzer = PairAnalyzer(
        lookback_period=settings.lookback_period,
        zscore_window=settings.spread_window,
    )
    
    logger.info("API server components initialized", storage_db=settings.storage_db_path)
    yield
    logger.info("API server shutting down")


app = FastAPI(
    title="MOEX Pair Trading Screener API",
    description="API for pair trading dashboard - reads from screener storage",
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
    """Get OHLCV data for a symbol - from database if available, otherwise from MOEX."""
    if not collector or not storage:
        raise HTTPException(status_code=503, detail="Collector or storage not initialized")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    # Try to get from database first
    db_data = storage.get_price_data(
        symbol=symbol,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=500,
    )
    
    if db_data is not None and len(db_data) > 0:
        logger.debug("Returning OHLCV data from database", symbol=symbol, rows=len(db_data))
        result = []
        for idx, row in db_data.iterrows():
            result.append(OHLCVDataPoint(
                timestamp=str(idx),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]) if "volume" in row and pd.notna(row.get("volume")) else None,
            ))
        return result
    
    # Fallback to MOEX API
    ohlcv = collector.get_ohlcv(
        symbol=symbol,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=500,
        use_cache=False,
    )
    
    if ohlcv is None or len(ohlcv) == 0:
        raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
    
    # Save to database
    storage.save_price_data(symbol, ohlcv, interval=interval)
    
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


# ==================== PAIRS ====================

@app.get("/api/pairs/active", response_model=list[PairMetricsResponse])
async def get_active_pairs():
    """Get all active/monitored pairs with their latest metrics."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    # Get all active pairs first
    active_pairs = storage.get_active_pairs()
    metrics_data = storage.get_latest_metrics()
    
    # Create a map of metrics by pair key
    metrics_map = {
        f"{m['symbol1']}/{m['symbol2']}": m 
        for m in metrics_data
    }
    
    result = []
    for pair in active_pairs:
        pair_key = f"{pair.symbol1}/{pair.symbol2}"
        m = metrics_map.get(pair_key)
        
        if m:
            # Pair has metrics
            result.append(PairMetricsResponse(
                symbol1=m["symbol1"],
                symbol2=m["symbol2"],
                correlation=round(m["correlation"] or 0, 4),
                is_cointegrated=bool(m["is_cointegrated"]),
                cointegration_pvalue=round(m["cointegration_pvalue"] or 1.0, 4),
                hedge_ratio=round(m["hedge_ratio"] or 1.0, 4),
                spread_mean=round(m["spread_mean"] or 0, 4),
                spread_std=round(m["spread_std"] or 1, 4),
                current_zscore=round(m["current_zscore"] or 0, 4),
                half_life=round(m["half_life"] or 999, 2),
                hurst_exponent=round(m["hurst_exponent"] or 0.5, 4),
                last_updated=m["analyzed_at"] or datetime.now().isoformat(),
                is_tradeable=bool(m["is_tradeable"]),
            ))
        else:
            # Pair is active but not yet analyzed - show placeholder
            result.append(PairMetricsResponse(
                symbol1=pair.symbol1,
                symbol2=pair.symbol2,
                correlation=0,
                is_cointegrated=False,
                cointegration_pvalue=1.0,
                hedge_ratio=1.0,
                spread_mean=0,
                spread_std=1,
                current_zscore=0,
                half_life=999,
                hurst_exponent=0.5,
                last_updated=pair.created_at.isoformat(),
                is_tradeable=False,
            ))
    
    return result


@app.post("/api/pairs/add")
async def add_pair(request: AddPairRequest):
    """Add a new pair to monitor. The screener will analyze it on the next cycle."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    pair_id = storage.add_pair(request.symbol1.upper(), request.symbol2.upper())
    
    if pair_id:
        return {
            "status": "ok",
            "message": f"Pair {request.symbol1}/{request.symbol2} added. Will be analyzed on next screener cycle.",
            "pair_id": pair_id,
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to add pair")


@app.post("/api/pairs/analyze", response_model=PairMetricsResponse)
async def analyze_pair_endpoint(
    symbol1: str = Query(...),
    symbol2: str = Query(...),
    force_refresh: Optional[str] = Query(default=None, description="Force re-analysis (true/false)"),
    days: Optional[int] = Query(default=None, description="Deprecated, ignored"),
):
    """
    Add a pair to monitoring and analyze it immediately.
    """
    if not storage or not collector or not analyzer:
        raise HTTPException(status_code=503, detail="Server not fully initialized")
    
    settings = get_settings()
    s1, s2 = symbol1.upper(), symbol2.upper()
    
    # Parse force_refresh (accept bool-like strings)
    should_refresh = force_refresh and force_refresh.lower() in ('true', '1', 'yes')
    
    # Add pair to storage (or reactivate if exists)
    pair_id = storage.add_pair(s1, s2)
    
    if not pair_id:
        raise HTTPException(status_code=500, detail="Failed to create pair")
    
    # Check if we have recent metrics (within last hour) and not forcing refresh
    if not should_refresh:
        metrics_list = storage.get_latest_metrics(pair_id)
        if metrics_list:
            m = metrics_list[0]
            analyzed_at = datetime.fromisoformat(m["analyzed_at"]) if m["analyzed_at"] else None
            # If analyzed within last hour, return existing
            if analyzed_at and (datetime.now() - analyzed_at).total_seconds() < 3600:
                return PairMetricsResponse(
                    symbol1=m["symbol1"],
                    symbol2=m["symbol2"],
                    correlation=round(m["correlation"] or 0, 4),
                    is_cointegrated=bool(m["is_cointegrated"]),
                    cointegration_pvalue=round(m["cointegration_pvalue"] or 1.0, 4),
                    hedge_ratio=round(m["hedge_ratio"] or 1.0, 4),
                    spread_mean=round(m["spread_mean"] or 0, 4),
                    spread_std=round(m["spread_std"] or 1, 4),
                    current_zscore=round(m["current_zscore"] or 0, 4),
                    half_life=round(m["half_life"] or 999, 2),
                    hurst_exponent=round(m["hurst_exponent"] or 0.5, 4),
                    last_updated=m["analyzed_at"] or datetime.now().isoformat(),
                    is_tradeable=bool(m["is_tradeable"]),
                )
    
    # Fetch data and analyze
    end_date = datetime.now()
    interval = settings.candle_interval
    if interval == 1:
        days_needed = max(1, (settings.lookback_period // 390) + 2)
    elif interval == 10:
        days_needed = max(1, (settings.lookback_period // 39) + 2)
    elif interval == 60:
        days_needed = max(1, (settings.lookback_period // 7) + 2)
    else:
        days_needed = settings.lookback_period + 10
    
    start_date = end_date - timedelta(days=days_needed)
    
    # Fetch data for both symbols
    data1 = collector.get_ohlcv(
        symbol=s1,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=settings.lookback_period + 100,
        use_cache=False,  # Fresh data
    )
    data2 = collector.get_ohlcv(
        symbol=s2,
        start_date=start_date.strftime("%Y-%m-%d"),
        end_date=end_date.strftime("%Y-%m-%d"),
        interval=interval,
        limit=settings.lookback_period + 100,
        use_cache=False,
    )
    
    if data1 is None or len(data1) < settings.lookback_period:
        raise HTTPException(status_code=404, detail=f"Insufficient data for {s1}")
    if data2 is None or len(data2) < settings.lookback_period:
        raise HTTPException(status_code=404, detail=f"Insufficient data for {s2}")
    
    # Analyze pair
    metrics = analyzer.analyze_pair(
        data1["close"],
        data2["close"],
        s1,
        s2,
    )
    
    # Extract spread/zscore data for charts
    spread_data = None
    zscore_data = None
    timestamps = None
    if metrics.spread is not None and metrics.zscore is not None:
        spread_clean = metrics.spread.dropna()
        zscore_clean = metrics.zscore.dropna()
        common_idx = spread_clean.index.intersection(zscore_clean.index)
        
        spread_data = [float(v) for v in spread_clean.loc[common_idx].values]
        zscore_data = [float(v) for v in zscore_clean.loc[common_idx].values]
        timestamps = [str(ts) for ts in common_idx]
    
    # #region agent log H5
    import json, datetime as _dt; _ts_first = timestamps[0] if timestamps else 'none'; _ts_last = timestamps[-1] if timestamps else 'none'; open('/Users/lexa2hk/dev/moex-pair-trading-screener/.cursor/debug.log','a').write(json.dumps({"hypothesisId":"H5","location":"server.py:analyze:save_metrics","message":"Saving metrics to storage","data":{"symbol1":s1,"symbol2":s2,"timestamps_count":len(timestamps) if timestamps else 0,"first_ts":_ts_first,"last_ts":_ts_last,"zscore":float(metrics.current_zscore) if not np.isnan(metrics.current_zscore) else 0},"timestamp":_dt.datetime.now().isoformat()})+'\n')
    # #endregion
    # Save metrics to storage
    storage.save_metrics(
        pair_id=pair_id,
        symbol1=s1,
        symbol2=s2,
        correlation=float(metrics.correlation) if not np.isnan(metrics.correlation) else 0,
        is_cointegrated=bool(metrics.is_cointegrated),
        cointegration_pvalue=float(metrics.cointegration_pvalue),
        hedge_ratio=float(metrics.hedge_ratio) if not np.isnan(metrics.hedge_ratio) else 1.0,
        spread_mean=float(metrics.spread_mean) if not np.isnan(metrics.spread_mean) else 0,
        spread_std=float(metrics.spread_std) if not np.isnan(metrics.spread_std) else 1,
        current_zscore=float(metrics.current_zscore) if not np.isnan(metrics.current_zscore) else 0,
        half_life=float(metrics.half_life) if not np.isnan(metrics.half_life) and metrics.half_life != float('inf') else 999999,
        hurst_exponent=float(metrics.hurst_exponent) if not np.isnan(metrics.hurst_exponent) else 0.5,
        is_tradeable=bool(metrics.is_tradeable()),
        spread_data=spread_data,
        zscore_data=zscore_data,
        timestamps=timestamps,
    )
    
    return PairMetricsResponse(
        symbol1=s1,
        symbol2=s2,
        correlation=round(float(metrics.correlation), 4) if not np.isnan(metrics.correlation) else 0,
        is_cointegrated=bool(metrics.is_cointegrated),
        cointegration_pvalue=round(float(metrics.cointegration_pvalue), 4),
        hedge_ratio=round(float(metrics.hedge_ratio), 4) if not np.isnan(metrics.hedge_ratio) else 1.0,
        spread_mean=round(float(metrics.spread_mean), 4) if not np.isnan(metrics.spread_mean) else 0,
        spread_std=round(float(metrics.spread_std), 4) if not np.isnan(metrics.spread_std) else 1,
        current_zscore=round(float(metrics.current_zscore), 4) if not np.isnan(metrics.current_zscore) else 0,
        half_life=round(float(metrics.half_life), 2) if not np.isnan(metrics.half_life) and metrics.half_life != float('inf') else 999,
        hurst_exponent=round(float(metrics.hurst_exponent), 4) if not np.isnan(metrics.hurst_exponent) else 0.5,
        last_updated=datetime.now().isoformat(),
        is_tradeable=bool(metrics.is_tradeable()),
    )


@app.delete("/api/pairs/{symbol1}/{symbol2}")
async def remove_pair(symbol1: str, symbol2: str):
    """Remove a pair from monitoring."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    if storage.remove_pair(symbol1, symbol2):
        return {"status": "ok", "message": f"Pair {symbol1}/{symbol2} removed"}
    else:
        raise HTTPException(status_code=404, detail="Pair not found")


@app.get("/api/pairs/{symbol1}/{symbol2}/spread", response_model=SpreadChartData)
async def get_spread_chart_data(
    symbol1: str,
    symbol2: str,
    days: int = Query(default=60, le=180),
):
    """Get spread and z-score chart data for a pair from storage."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    settings = get_settings()
    chart_data = storage.get_spread_chart_data(symbol1, symbol2)
    
    if chart_data:
        return SpreadChartData(
            timestamps=chart_data["timestamps"],
            spread=chart_data["spread"],
            zscore=chart_data["zscore"],
            upper_threshold=settings.entry_threshold,
            lower_threshold=-settings.entry_threshold,
            exit_threshold=settings.exit_threshold,
        )
    
    # No data in storage
    raise HTTPException(
        status_code=404, 
        detail=f"No chart data for {symbol1}/{symbol2}. Wait for screener to analyze this pair."
    )


# ==================== SIGNALS ====================

@app.get("/api/signals", response_model=list[SignalResponse])
async def get_signals(limit: int = Query(default=50, le=200)):
    """Get recent signals from storage."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    signals_data = storage.get_signals(limit=limit)
    
    return [
        SignalResponse(
            signal_type=s["signal_type"],
            symbol1=s["symbol1"],
            symbol2=s["symbol2"],
            zscore=round(s["zscore"] or 0, 4),
            hedge_ratio=round(s["hedge_ratio"] or 1, 4),
            strength=s["strength"] or "MODERATE",
            confidence=round(s["confidence"] or 0, 4),
            entry_price1=s["entry_price1"],
            entry_price2=s["entry_price2"],
            target_zscore=s["target_zscore"] or 0,
            stop_loss_zscore=s["stop_loss_zscore"] or 3,
            timestamp=s["created_at"] or datetime.now().isoformat(),
        )
        for s in signals_data
    ]


# ==================== POSITIONS ====================

@app.get("/api/positions", response_model=list[PositionResponse])
async def get_positions():
    """Get current open positions from storage."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    positions = storage.get_open_positions()
    
    return [
        PositionResponse(
            pair_key=f"{p['symbol1']}/{p['symbol2']}",
            symbol1=p["symbol1"],
            symbol2=p["symbol2"],
            position_type=p["position_type"],
            entry_zscore=p["entry_zscore"] or 0,
            current_zscore=p["current_zscore"] or 0,
            entry_price1=p["entry_price1"],
            entry_price2=p["entry_price2"],
            current_price1=p["current_price1"],
            current_price2=p["current_price2"],
            pnl_percent=p["pnl_percent"],
            opened_at=p["opened_at"] or datetime.now().isoformat(),
        )
        for p in positions
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
    """Manually open a position (for tracking)."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    pair_id = storage.get_pair_id(symbol1, symbol2)
    if not pair_id:
        pair_id = storage.add_pair(symbol1, symbol2)
    
    if not pair_id:
        raise HTTPException(status_code=500, detail="Failed to create pair")
    
    # Check if position already exists
    existing = storage.get_position_for_pair(symbol1, symbol2)
    if existing:
        raise HTTPException(status_code=400, detail="Position already exists for this pair")
    
    position_id = storage.open_position(
        pair_id=pair_id,
        symbol1=symbol1.upper(),
        symbol2=symbol2.upper(),
        position_type=position_type,
        entry_zscore=entry_zscore,
        entry_price1=entry_price1,
        entry_price2=entry_price2,
    )
    
    return {"status": "ok", "message": f"Position opened", "position_id": position_id}


@app.delete("/api/positions/{symbol1}/{symbol2}")
async def close_position(symbol1: str, symbol2: str):
    """Close a position."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    if storage.close_position(symbol1, symbol2):
        return {"status": "ok", "message": f"Position closed for {symbol1}/{symbol2}"}
    else:
        raise HTTPException(status_code=404, detail="Position not found")


# ==================== DASHBOARD ====================

@app.get("/api/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """Get dashboard statistics from storage."""
    if not storage:
        raise HTTPException(status_code=503, detail="Storage not initialized")
    
    stats = storage.get_stats()
    
    # Check market hours
    now = datetime.now()
    market_open = time(10, 0)
    market_close = time(18, 50)
    is_market_open = (
        now.weekday() < 5 and
        market_open <= now.time() <= market_close
    )
    
    return DashboardStats(
        total_pairs=stats["total_pairs"],
        active_signals=stats["active_signals"],
        open_positions=stats["open_positions"],
        cointegrated_pairs=stats["cointegrated_pairs"],
        avg_correlation=round(stats["avg_correlation"], 4),
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
