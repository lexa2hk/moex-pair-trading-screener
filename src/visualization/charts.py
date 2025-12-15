"""Chart generation for pair trading analysis."""

import io
from datetime import datetime
from typing import Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import structlog

matplotlib.use("Agg")  # Non-interactive backend for server use

logger = structlog.get_logger()

# Set style
plt.style.use("seaborn-v0_8-darkgrid")


class PairChartGenerator:
    """Generate charts for pair trading analysis."""

    def __init__(
        self,
        figsize: tuple[int, int] = (12, 8),
        dpi: int = 100,
    ):
        """
        Initialize chart generator.

        Args:
            figsize: Figure size (width, height) in inches
            dpi: Dots per inch for output
        """
        self.figsize = figsize
        self.dpi = dpi

        # Color scheme - dark professional theme
        self.colors = {
            "bg": "#1a1a2e",
            "panel": "#16213e",
            "text": "#e8e8e8",
            "grid": "#394867",
            "price1": "#00d9ff",
            "price2": "#ff6b6b",
            "spread": "#4ecdc4",
            "zscore": "#ffd93d",
            "entry_long": "#00ff88",
            "entry_short": "#ff4757",
            "exit": "#a29bfe",
            "zero": "#636e72",
        }

    def _setup_figure(self, rows: int = 2) -> tuple[plt.Figure, list]:
        """Setup figure with dark theme."""
        fig, axes = plt.subplots(
            rows, 1,
            figsize=self.figsize,
            facecolor=self.colors["bg"],
            gridspec_kw={"hspace": 0.3}
        )

        if rows == 1:
            axes = [axes]

        for ax in axes:
            ax.set_facecolor(self.colors["panel"])
            ax.tick_params(colors=self.colors["text"], which="both")
            ax.xaxis.label.set_color(self.colors["text"])
            ax.yaxis.label.set_color(self.colors["text"])
            ax.title.set_color(self.colors["text"])
            for spine in ax.spines.values():
                spine.set_color(self.colors["grid"])
            ax.grid(True, alpha=0.3, color=self.colors["grid"])

        return fig, axes

    def generate_pair_overview(
        self,
        prices1: pd.Series,
        prices2: pd.Series,
        spread: pd.Series,
        zscore: pd.Series,
        symbol1: str,
        symbol2: str,
        hedge_ratio: float,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.0,
    ) -> bytes:
        """
        Generate comprehensive pair overview chart.

        Args:
            prices1: Price series for first asset
            prices2: Price series for second asset
            spread: Spread series
            zscore: Z-score series
            symbol1: First symbol name
            symbol2: Second symbol name
            hedge_ratio: Hedge ratio
            entry_threshold: Z-score entry threshold
            exit_threshold: Z-score exit threshold

        Returns:
            PNG image as bytes
        """
        fig, axes = self._setup_figure(rows=3)
        ax_prices, ax_spread, ax_zscore = axes

        # Normalize prices for comparison
        norm_p1 = prices1 / prices1.iloc[0] * 100
        norm_p2 = prices2 / prices2.iloc[0] * 100

        # Plot 1: Normalized Prices
        ax_prices.plot(
            norm_p1.index, norm_p1.values,
            color=self.colors["price1"],
            linewidth=1.5,
            label=f"{symbol1}",
            alpha=0.9
        )
        ax_prices.plot(
            norm_p2.index, norm_p2.values,
            color=self.colors["price2"],
            linewidth=1.5,
            label=f"{symbol2}",
            alpha=0.9
        )
        ax_prices.set_title(
            f"📈 {symbol1} vs {symbol2} (Normalized)",
            fontsize=12,
            fontweight="bold",
            pad=10
        )
        ax_prices.set_ylabel("Price (indexed to 100)", fontsize=10)
        ax_prices.legend(
            loc="upper left",
            facecolor=self.colors["panel"],
            edgecolor=self.colors["grid"],
            labelcolor=self.colors["text"]
        )

        # Plot 2: Spread
        ax_spread.fill_between(
            spread.index, spread.values, 0,
            alpha=0.3,
            color=self.colors["spread"]
        )
        ax_spread.plot(
            spread.index, spread.values,
            color=self.colors["spread"],
            linewidth=1.5
        )
        ax_spread.axhline(
            y=spread.mean(),
            color=self.colors["zero"],
            linestyle="--",
            linewidth=1,
            label=f"Mean: {spread.mean():.2f}"
        )
        ax_spread.set_title(
            f"📊 Spread (β = {hedge_ratio:.4f})",
            fontsize=12,
            fontweight="bold",
            pad=10
        )
        ax_spread.set_ylabel("Spread", fontsize=10)
        ax_spread.legend(
            loc="upper left",
            facecolor=self.colors["panel"],
            edgecolor=self.colors["grid"],
            labelcolor=self.colors["text"]
        )

        # Plot 3: Z-Score with thresholds
        ax_zscore.fill_between(
            zscore.index, zscore.values, 0,
            where=zscore.values > entry_threshold,
            alpha=0.3,
            color=self.colors["entry_short"],
            label="Short zone"
        )
        ax_zscore.fill_between(
            zscore.index, zscore.values, 0,
            where=zscore.values < -entry_threshold,
            alpha=0.3,
            color=self.colors["entry_long"],
            label="Long zone"
        )
        ax_zscore.plot(
            zscore.index, zscore.values,
            color=self.colors["zscore"],
            linewidth=1.5
        )

        # Threshold lines
        ax_zscore.axhline(
            y=entry_threshold,
            color=self.colors["entry_short"],
            linestyle="--",
            linewidth=1,
            alpha=0.8
        )
        ax_zscore.axhline(
            y=-entry_threshold,
            color=self.colors["entry_long"],
            linestyle="--",
            linewidth=1,
            alpha=0.8
        )
        ax_zscore.axhline(
            y=exit_threshold,
            color=self.colors["exit"],
            linestyle=":",
            linewidth=1,
            alpha=0.6
        )
        ax_zscore.axhline(
            y=0,
            color=self.colors["zero"],
            linestyle="-",
            linewidth=0.5,
            alpha=0.5
        )

        current_z = zscore.iloc[-1] if len(zscore) > 0 else 0
        ax_zscore.scatter(
            [zscore.index[-1]], [current_z],
            color=self.colors["zscore"],
            s=100,
            zorder=5,
            edgecolors="white",
            linewidth=2
        )
        ax_zscore.annotate(
            f"Current: {current_z:.2f}",
            xy=(zscore.index[-1], current_z),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=10,
            color=self.colors["text"],
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor=self.colors["panel"],
                edgecolor=self.colors["zscore"]
            )
        )

        ax_zscore.set_title(
            f"📉 Z-Score (entry: ±{entry_threshold})",
            fontsize=12,
            fontweight="bold",
            pad=10
        )
        ax_zscore.set_ylabel("Z-Score", fontsize=10)
        ax_zscore.set_xlabel("Date", fontsize=10)
        ax_zscore.legend(
            loc="upper left",
            facecolor=self.colors["panel"],
            edgecolor=self.colors["grid"],
            labelcolor=self.colors["text"]
        )

        # Add timestamp
        fig.text(
            0.99, 0.01,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ha="right",
            fontsize=8,
            color=self.colors["grid"]
        )

        plt.tight_layout()

        # Convert to bytes
        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=self.dpi,
            facecolor=self.colors["bg"],
            edgecolor="none",
            bbox_inches="tight"
        )
        buf.seek(0)
        plt.close(fig)

        return buf.getvalue()

    def generate_zscore_chart(
        self,
        zscore: pd.Series,
        symbol1: str,
        symbol2: str,
        entry_threshold: float = 2.0,
        stop_threshold: float = 3.0,
    ) -> bytes:
        """
        Generate Z-score chart with entry/exit zones.

        Args:
            zscore: Z-score series
            symbol1: First symbol name
            symbol2: Second symbol name
            entry_threshold: Z-score entry threshold
            stop_threshold: Stop loss threshold

        Returns:
            PNG image as bytes
        """
        fig, ax = self._setup_figure(rows=1)
        ax = ax[0]

        # Fill zones
        ax.fill_between(
            zscore.index, entry_threshold, stop_threshold,
            alpha=0.2,
            color=self.colors["entry_short"],
            label="Short entry zone"
        )
        ax.fill_between(
            zscore.index, -entry_threshold, -stop_threshold,
            alpha=0.2,
            color=self.colors["entry_long"],
            label="Long entry zone"
        )
        ax.fill_between(
            zscore.index, stop_threshold, stop_threshold + 1,
            alpha=0.3,
            color="#ff0000",
            label="Stop loss zone"
        )
        ax.fill_between(
            zscore.index, -stop_threshold, -stop_threshold - 1,
            alpha=0.3,
            color="#ff0000"
        )

        # Plot z-score
        ax.plot(
            zscore.index, zscore.values,
            color=self.colors["zscore"],
            linewidth=2
        )

        # Threshold lines
        for threshold, color, label in [
            (entry_threshold, self.colors["entry_short"], f"Entry +{entry_threshold}"),
            (-entry_threshold, self.colors["entry_long"], f"Entry -{entry_threshold}"),
            (stop_threshold, "#ff0000", f"Stop +{stop_threshold}"),
            (-stop_threshold, "#ff0000", f"Stop -{stop_threshold}"),
            (0, self.colors["zero"], "Zero"),
        ]:
            ax.axhline(
                y=threshold,
                color=color,
                linestyle="--" if "Entry" in label else "-",
                linewidth=1,
                alpha=0.7
            )

        # Current position marker
        current_z = zscore.iloc[-1] if len(zscore) > 0 else 0
        ax.scatter(
            [zscore.index[-1]], [current_z],
            color=self.colors["zscore"],
            s=150,
            zorder=5,
            edgecolors="white",
            linewidth=2,
            marker="o"
        )

        # Status text
        if abs(current_z) >= stop_threshold:
            status = "🛑 STOP LOSS ZONE"
            status_color = "#ff0000"
        elif current_z >= entry_threshold:
            status = "🔴 SHORT ENTRY"
            status_color = self.colors["entry_short"]
        elif current_z <= -entry_threshold:
            status = "🟢 LONG ENTRY"
            status_color = self.colors["entry_long"]
        else:
            status = "➖ NEUTRAL"
            status_color = self.colors["text"]

        ax.set_title(
            f"📊 {symbol1}/{symbol2} Z-Score | {status} | Z = {current_z:.2f}",
            fontsize=14,
            fontweight="bold",
            color=status_color,
            pad=15
        )
        ax.set_ylabel("Z-Score", fontsize=11)
        ax.set_xlabel("Date", fontsize=11)
        ax.legend(
            loc="upper right",
            facecolor=self.colors["panel"],
            edgecolor=self.colors["grid"],
            labelcolor=self.colors["text"]
        )

        # Set y-axis limits
        y_max = max(abs(zscore.max()), abs(zscore.min()), stop_threshold + 0.5)
        ax.set_ylim(-y_max - 0.5, y_max + 0.5)

        # Timestamp
        fig.text(
            0.99, 0.01,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ha="right",
            fontsize=8,
            color=self.colors["grid"]
        )

        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=self.dpi,
            facecolor=self.colors["bg"],
            edgecolor="none",
            bbox_inches="tight"
        )
        buf.seek(0)
        plt.close(fig)

        return buf.getvalue()

    def generate_status_dashboard(
        self,
        pairs_data: list[dict],
        entry_threshold: float = 2.0,
    ) -> bytes:
        """
        Generate status dashboard for all monitored pairs.

        Args:
            pairs_data: List of dicts with pair metrics
            entry_threshold: Z-score entry threshold

        Returns:
            PNG image as bytes
        """
        n_pairs = len(pairs_data)
        if n_pairs == 0:
            # Empty dashboard
            fig, ax = self._setup_figure(rows=1)
            ax = ax[0]
            ax.text(
                0.5, 0.5,
                "No pairs to display",
                ha="center", va="center",
                fontsize=16,
                color=self.colors["text"]
            )
            ax.axis("off")
        else:
            fig, ax = plt.subplots(
                figsize=(12, max(4, n_pairs * 1.2)),
                facecolor=self.colors["bg"]
            )
            ax.set_facecolor(self.colors["panel"])

            # Create horizontal bar chart of z-scores
            pairs = [f"{d['symbol1']}/{d['symbol2']}" for d in pairs_data]
            zscores = [d.get("current_zscore", 0) for d in pairs_data]

            y_pos = np.arange(len(pairs))

            # Color based on z-score
            colors = []
            for z in zscores:
                if z >= entry_threshold:
                    colors.append(self.colors["entry_short"])
                elif z <= -entry_threshold:
                    colors.append(self.colors["entry_long"])
                else:
                    colors.append(self.colors["zscore"])

            bars = ax.barh(y_pos, zscores, color=colors, alpha=0.8, height=0.6)

            # Add value labels
            for i, (bar, z) in enumerate(zip(bars, zscores)):
                width = bar.get_width()
                label_x = width + 0.1 if width >= 0 else width - 0.1
                ha = "left" if width >= 0 else "right"
                ax.text(
                    label_x, bar.get_y() + bar.get_height() / 2,
                    f"{z:.2f}",
                    ha=ha, va="center",
                    fontsize=10,
                    fontweight="bold",
                    color=self.colors["text"]
                )

            # Threshold lines
            ax.axvline(x=entry_threshold, color=self.colors["entry_short"],
                       linestyle="--", linewidth=2, alpha=0.7, label=f"Entry +{entry_threshold}")
            ax.axvline(x=-entry_threshold, color=self.colors["entry_long"],
                       linestyle="--", linewidth=2, alpha=0.7, label=f"Entry -{entry_threshold}")
            ax.axvline(x=0, color=self.colors["zero"], linewidth=1, alpha=0.5)

            ax.set_yticks(y_pos)
            ax.set_yticklabels(pairs, fontsize=11, color=self.colors["text"])
            ax.set_xlabel("Z-Score", fontsize=12, color=self.colors["text"])
            ax.set_title(
                f"📊 Pair Trading Dashboard | {len(pairs_data)} Pairs",
                fontsize=14,
                fontweight="bold",
                color=self.colors["text"],
                pad=15
            )

            # Style
            ax.tick_params(colors=self.colors["text"])
            for spine in ax.spines.values():
                spine.set_color(self.colors["grid"])
            ax.grid(True, axis="x", alpha=0.3, color=self.colors["grid"])

            # Legend
            ax.legend(
                loc="lower right",
                facecolor=self.colors["panel"],
                edgecolor=self.colors["grid"],
                labelcolor=self.colors["text"]
            )

            # Extend x-axis to show labels
            x_max = max(abs(min(zscores)), abs(max(zscores)), entry_threshold) + 1
            ax.set_xlim(-x_max, x_max)

        # Timestamp
        fig.text(
            0.99, 0.01,
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            ha="right",
            fontsize=8,
            color=self.colors["grid"]
        )

        plt.tight_layout()

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=self.dpi,
            facecolor=self.colors["bg"],
            edgecolor="none",
            bbox_inches="tight"
        )
        buf.seek(0)
        plt.close(fig)

        return buf.getvalue()

