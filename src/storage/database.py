"""SQLite-based storage for screener data."""

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from src.config import get_settings

logger = structlog.get_logger()

# Singleton storage instance
_storage_instance: Optional["Storage"] = None


@dataclass
class StoredPair:
    """Stored pair configuration."""
    id: int
    symbol1: str
    symbol2: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class StoredPairMetrics:
    """Stored pair analysis metrics."""
    id: int
    pair_id: int
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
    is_tradeable: bool
    analyzed_at: datetime


@dataclass
class StoredSignal:
    """Stored trading signal."""
    id: int
    pair_id: int
    symbol1: str
    symbol2: str
    signal_type: str
    zscore: float
    hedge_ratio: float
    strength: str
    confidence: float
    entry_price1: Optional[float]
    entry_price2: Optional[float]
    target_zscore: float
    stop_loss_zscore: float
    created_at: datetime
    notified: bool


@dataclass
class StoredPosition:
    """Stored position."""
    id: int
    pair_id: int
    symbol1: str
    symbol2: str
    position_type: str
    entry_zscore: float
    current_zscore: float
    entry_price1: Optional[float]
    entry_price2: Optional[float]
    current_price1: Optional[float]
    current_price2: Optional[float]
    pnl_percent: Optional[float]
    opened_at: datetime
    closed_at: Optional[datetime]
    is_open: bool


class Storage:
    """SQLite storage for screener data."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize storage."""
        settings = get_settings()
        self.db_path = db_path or settings.storage_db_path
        
        # Create directory if needed
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()
        logger.info("Storage initialized", db_path=self.db_path)

    @contextmanager
    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                -- Pairs to monitor
                CREATE TABLE IF NOT EXISTS pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol1 TEXT NOT NULL,
                    symbol2 TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol1, symbol2)
                );

                -- Latest metrics for each pair
                CREATE TABLE IF NOT EXISTS pair_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id INTEGER NOT NULL,
                    symbol1 TEXT NOT NULL,
                    symbol2 TEXT NOT NULL,
                    correlation REAL,
                    is_cointegrated BOOLEAN,
                    cointegration_pvalue REAL,
                    hedge_ratio REAL,
                    spread_mean REAL,
                    spread_std REAL,
                    current_zscore REAL,
                    half_life REAL,
                    hurst_exponent REAL,
                    is_tradeable BOOLEAN,
                    spread_data TEXT,  -- JSON array for charts
                    zscore_data TEXT,  -- JSON array for charts
                    timestamps TEXT,   -- JSON array for charts
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (pair_id) REFERENCES pairs(id)
                );

                -- Trading signals history
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id INTEGER NOT NULL,
                    symbol1 TEXT NOT NULL,
                    symbol2 TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    zscore REAL,
                    hedge_ratio REAL,
                    strength TEXT,
                    confidence REAL,
                    entry_price1 REAL,
                    entry_price2 REAL,
                    target_zscore REAL,
                    stop_loss_zscore REAL,
                    metadata TEXT,  -- JSON
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified BOOLEAN DEFAULT 0,
                    FOREIGN KEY (pair_id) REFERENCES pairs(id)
                );

                -- Open positions
                CREATE TABLE IF NOT EXISTS positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pair_id INTEGER NOT NULL,
                    symbol1 TEXT NOT NULL,
                    symbol2 TEXT NOT NULL,
                    position_type TEXT NOT NULL,
                    entry_zscore REAL,
                    current_zscore REAL,
                    entry_price1 REAL,
                    entry_price2 REAL,
                    current_price1 REAL,
                    current_price2 REAL,
                    pnl_percent REAL,
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    closed_at TIMESTAMP,
                    is_open BOOLEAN DEFAULT 1,
                    FOREIGN KEY (pair_id) REFERENCES pairs(id)
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_pairs_active ON pairs(is_active);
                CREATE INDEX IF NOT EXISTS idx_metrics_pair ON pair_metrics(pair_id);
                CREATE INDEX IF NOT EXISTS idx_signals_pair ON signals(pair_id);
                CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);
                CREATE INDEX IF NOT EXISTS idx_positions_open ON positions(is_open);
            """)

    # ==================== PAIRS ====================

    def add_pair(self, symbol1: str, symbol2: str) -> Optional[int]:
        """Add a new pair to monitor."""
        with self._get_conn() as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO pairs (symbol1, symbol2) VALUES (?, ?)",
                    (symbol1.upper(), symbol2.upper())
                )
                pair_id = cursor.lastrowid
                logger.info("Pair added", symbol1=symbol1, symbol2=symbol2, pair_id=pair_id)
                return pair_id
            except sqlite3.IntegrityError:
                # Pair already exists, reactivate if inactive
                conn.execute(
                    "UPDATE pairs SET is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE symbol1 = ? AND symbol2 = ?",
                    (symbol1.upper(), symbol2.upper())
                )
                cursor = conn.execute(
                    "SELECT id FROM pairs WHERE symbol1 = ? AND symbol2 = ?",
                    (symbol1.upper(), symbol2.upper())
                )
                row = cursor.fetchone()
                logger.info("Pair reactivated", symbol1=symbol1, symbol2=symbol2)
                return row["id"] if row else None

    def remove_pair(self, symbol1: str, symbol2: str) -> bool:
        """Deactivate a pair (soft delete)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE pairs SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE symbol1 = ? AND symbol2 = ?",
                (symbol1.upper(), symbol2.upper())
            )
            if cursor.rowcount > 0:
                logger.info("Pair removed", symbol1=symbol1, symbol2=symbol2)
                return True
            return False

    def get_active_pairs(self) -> list[StoredPair]:
        """Get all active pairs."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM pairs WHERE is_active = 1 ORDER BY created_at"
            )
            return [
                StoredPair(
                    id=row["id"],
                    symbol1=row["symbol1"],
                    symbol2=row["symbol2"],
                    is_active=bool(row["is_active"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
                for row in cursor.fetchall()
            ]

    def get_pair_id(self, symbol1: str, symbol2: str) -> Optional[int]:
        """Get pair ID by symbols."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT id FROM pairs WHERE symbol1 = ? AND symbol2 = ?",
                (symbol1.upper(), symbol2.upper())
            )
            row = cursor.fetchone()
            return row["id"] if row else None

    # ==================== METRICS ====================

    def save_metrics(
        self,
        pair_id: int,
        symbol1: str,
        symbol2: str,
        correlation: float,
        is_cointegrated: bool,
        cointegration_pvalue: float,
        hedge_ratio: float,
        spread_mean: float,
        spread_std: float,
        current_zscore: float,
        half_life: float,
        hurst_exponent: float,
        is_tradeable: bool,
        spread_data: Optional[list[float]] = None,
        zscore_data: Optional[list[float]] = None,
        timestamps: Optional[list[str]] = None,
    ) -> int:
        """Save pair metrics (creates new record each time for history)."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pair_metrics (
                    pair_id, symbol1, symbol2, correlation, is_cointegrated,
                    cointegration_pvalue, hedge_ratio, spread_mean, spread_std,
                    current_zscore, half_life, hurst_exponent, is_tradeable,
                    spread_data, zscore_data, timestamps
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pair_id, symbol1, symbol2, correlation, is_cointegrated,
                    cointegration_pvalue, hedge_ratio, spread_mean, spread_std,
                    current_zscore, half_life, hurst_exponent, is_tradeable,
                    json.dumps(spread_data) if spread_data else None,
                    json.dumps(zscore_data) if zscore_data else None,
                    json.dumps(timestamps) if timestamps else None,
                )
            )
            return cursor.lastrowid

    def get_latest_metrics(self, pair_id: Optional[int] = None) -> list[dict]:
        """Get latest metrics for all pairs or a specific pair."""
        with self._get_conn() as conn:
            if pair_id:
                cursor = conn.execute(
                    """
                    SELECT * FROM pair_metrics 
                    WHERE pair_id = ?
                    ORDER BY analyzed_at DESC LIMIT 1
                    """,
                    (pair_id,)
                )
            else:
                # Get latest metrics for each active pair
                cursor = conn.execute(
                    """
                    SELECT pm.* FROM pair_metrics pm
                    INNER JOIN (
                        SELECT pair_id, MAX(analyzed_at) as max_date
                        FROM pair_metrics
                        GROUP BY pair_id
                    ) latest ON pm.pair_id = latest.pair_id AND pm.analyzed_at = latest.max_date
                    INNER JOIN pairs p ON pm.pair_id = p.id
                    WHERE p.is_active = 1
                    ORDER BY pm.analyzed_at DESC
                    """
                )
            
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                # Parse JSON fields
                if data.get("spread_data"):
                    data["spread_data"] = json.loads(data["spread_data"])
                if data.get("zscore_data"):
                    data["zscore_data"] = json.loads(data["zscore_data"])
                if data.get("timestamps"):
                    data["timestamps"] = json.loads(data["timestamps"])
                results.append(data)
            
            return results

    def get_spread_chart_data(self, symbol1: str, symbol2: str) -> Optional[dict]:
        """Get spread chart data for a pair."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT spread_data, zscore_data, timestamps 
                FROM pair_metrics pm
                JOIN pairs p ON pm.pair_id = p.id
                WHERE p.symbol1 = ? AND p.symbol2 = ?
                ORDER BY pm.analyzed_at DESC LIMIT 1
                """,
                (symbol1.upper(), symbol2.upper())
            )
            row = cursor.fetchone()
            if row and row["spread_data"] and row["zscore_data"] and row["timestamps"]:
                return {
                    "spread": json.loads(row["spread_data"]),
                    "zscore": json.loads(row["zscore_data"]),
                    "timestamps": json.loads(row["timestamps"]),
                }
            return None

    # ==================== SIGNALS ====================

    def save_signal(
        self,
        pair_id: int,
        symbol1: str,
        symbol2: str,
        signal_type: str,
        zscore: float,
        hedge_ratio: float,
        strength: str,
        confidence: float,
        entry_price1: Optional[float] = None,
        entry_price2: Optional[float] = None,
        target_zscore: float = 0.0,
        stop_loss_zscore: float = 3.0,
        metadata: Optional[dict] = None,
    ) -> int:
        """Save a trading signal."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO signals (
                    pair_id, symbol1, symbol2, signal_type, zscore, hedge_ratio,
                    strength, confidence, entry_price1, entry_price2,
                    target_zscore, stop_loss_zscore, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pair_id, symbol1, symbol2, signal_type, zscore, hedge_ratio,
                    strength, confidence, entry_price1, entry_price2,
                    target_zscore, stop_loss_zscore,
                    json.dumps(metadata) if metadata else None,
                )
            )
            logger.info(
                "Signal saved",
                signal_type=signal_type,
                symbol1=symbol1,
                symbol2=symbol2,
                zscore=round(zscore, 4),
            )
            return cursor.lastrowid

    def get_signals(self, limit: int = 50, unnotified_only: bool = False) -> list[dict]:
        """Get recent signals."""
        with self._get_conn() as conn:
            query = "SELECT * FROM signals"
            if unnotified_only:
                query += " WHERE notified = 0"
            query += " ORDER BY created_at DESC LIMIT ?"
            
            cursor = conn.execute(query, (limit,))
            results = []
            for row in cursor.fetchall():
                data = dict(row)
                if data.get("metadata"):
                    data["metadata"] = json.loads(data["metadata"])
                results.append(data)
            return results

    def mark_signal_notified(self, signal_id: int):
        """Mark a signal as notified."""
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE signals SET notified = 1 WHERE id = ?",
                (signal_id,)
            )

    # ==================== POSITIONS ====================

    def open_position(
        self,
        pair_id: int,
        symbol1: str,
        symbol2: str,
        position_type: str,
        entry_zscore: float,
        entry_price1: Optional[float] = None,
        entry_price2: Optional[float] = None,
    ) -> int:
        """Open a new position."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                INSERT INTO positions (
                    pair_id, symbol1, symbol2, position_type,
                    entry_zscore, current_zscore, entry_price1, entry_price2
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pair_id, symbol1, symbol2, position_type,
                    entry_zscore, entry_zscore, entry_price1, entry_price2,
                )
            )
            logger.info(
                "Position opened",
                position_type=position_type,
                symbol1=symbol1,
                symbol2=symbol2,
            )
            return cursor.lastrowid

    def update_position(
        self,
        position_id: int,
        current_zscore: float,
        current_price1: Optional[float] = None,
        current_price2: Optional[float] = None,
        pnl_percent: Optional[float] = None,
    ):
        """Update position with current values."""
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE positions SET
                    current_zscore = ?,
                    current_price1 = ?,
                    current_price2 = ?,
                    pnl_percent = ?
                WHERE id = ?
                """,
                (current_zscore, current_price1, current_price2, pnl_percent, position_id)
            )

    def close_position(self, symbol1: str, symbol2: str) -> bool:
        """Close an open position."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                UPDATE positions SET
                    is_open = 0,
                    closed_at = CURRENT_TIMESTAMP
                WHERE symbol1 = ? AND symbol2 = ? AND is_open = 1
                """,
                (symbol1.upper(), symbol2.upper())
            )
            if cursor.rowcount > 0:
                logger.info("Position closed", symbol1=symbol1, symbol2=symbol2)
                return True
            return False

    def get_open_positions(self) -> list[dict]:
        """Get all open positions."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM positions WHERE is_open = 1 ORDER BY opened_at"
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_position_for_pair(self, symbol1: str, symbol2: str) -> Optional[dict]:
        """Get open position for a specific pair."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT * FROM positions WHERE symbol1 = ? AND symbol2 = ? AND is_open = 1",
                (symbol1.upper(), symbol2.upper())
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== STATS ====================

    def get_stats(self) -> dict:
        """Get dashboard statistics."""
        with self._get_conn() as conn:
            # Total active pairs
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM pairs WHERE is_active = 1")
            total_pairs = cursor.fetchone()["cnt"]

            # Cointegrated pairs (from latest metrics)
            cursor = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM pair_metrics pm
                INNER JOIN (
                    SELECT pair_id, MAX(analyzed_at) as max_date
                    FROM pair_metrics GROUP BY pair_id
                ) latest ON pm.pair_id = latest.pair_id AND pm.analyzed_at = latest.max_date
                INNER JOIN pairs p ON pm.pair_id = p.id
                WHERE p.is_active = 1 AND pm.is_cointegrated = 1
                """
            )
            cointegrated = cursor.fetchone()["cnt"]

            # Open positions
            cursor = conn.execute("SELECT COUNT(*) as cnt FROM positions WHERE is_open = 1")
            open_positions = cursor.fetchone()["cnt"]

            # Recent signals (last hour)
            cursor = conn.execute(
                """
                SELECT COUNT(*) as cnt FROM signals 
                WHERE created_at > datetime('now', '-1 hour')
                AND signal_type IN ('LONG_SPREAD', 'SHORT_SPREAD')
                """
            )
            recent_signals = cursor.fetchone()["cnt"]

            # Average correlation
            cursor = conn.execute(
                """
                SELECT AVG(ABS(correlation)) as avg_corr FROM pair_metrics pm
                INNER JOIN (
                    SELECT pair_id, MAX(analyzed_at) as max_date
                    FROM pair_metrics GROUP BY pair_id
                ) latest ON pm.pair_id = latest.pair_id AND pm.analyzed_at = latest.max_date
                INNER JOIN pairs p ON pm.pair_id = p.id
                WHERE p.is_active = 1
                """
            )
            avg_corr = cursor.fetchone()["avg_corr"] or 0

            return {
                "total_pairs": total_pairs,
                "cointegrated_pairs": cointegrated,
                "open_positions": open_positions,
                "active_signals": recent_signals,
                "avg_correlation": avg_corr,
            }


def get_storage() -> Storage:
    """Get or create singleton storage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = Storage()
    return _storage_instance

