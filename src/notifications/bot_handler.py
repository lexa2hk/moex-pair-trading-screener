"""Interactive Telegram bot handler with keyboard menu."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Any

import structlog
from telegram import (
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from src.analysis.pair_analyzer import PairMetrics
from src.config import get_settings
from src.visualization.charts import PairChartGenerator

logger = structlog.get_logger()


class TelegramBotHandler:
    """Interactive Telegram bot with keyboard menu for pair trading screener."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        allowed_users: Optional[list[int]] = None,
    ):
        """
        Initialize bot handler.

        Args:
            bot_token: Telegram bot token (from @BotFather)
            allowed_users: List of allowed user IDs (None = allow all)
        """
        settings = get_settings()

        self.bot_token = bot_token or settings.telegram_bot_token
        self.allowed_users = allowed_users or []
        self.chart_generator = PairChartGenerator()

        self._application: Optional[Application] = None
        self._screener = None  # Will be set by screener
        self._running = False

        # Callbacks for getting data from screener
        self._get_active_pairs: Optional[Callable[[], list[PairMetrics]]] = None
        self._get_signals_today: Optional[Callable[[], list]] = None
        self._get_positions: Optional[Callable[[], dict]] = None
        self._analyze_pair_callback: Optional[Callable[[str, str], Any]] = None
        self._get_pair_data_callback: Optional[Callable[[str], Any]] = None

        logger.info("TelegramBotHandler initialized")

    def set_screener_callbacks(
        self,
        get_active_pairs: Callable[[], list[PairMetrics]],
        get_signals_today: Callable[[], list],
        get_positions: Callable[[], dict],
        analyze_pair: Optional[Callable[[str, str], Any]] = None,
        get_pair_data: Optional[Callable[[str], Any]] = None,
    ):
        """
        Set callbacks to get data from the screener.

        Args:
            get_active_pairs: Function to get list of active PairMetrics
            get_signals_today: Function to get today's signals
            get_positions: Function to get current positions
            analyze_pair: Function to analyze a specific pair
            get_pair_data: Function to get price data for a symbol
        """
        self._get_active_pairs = get_active_pairs
        self._get_signals_today = get_signals_today
        self._get_positions = get_positions
        self._analyze_pair_callback = analyze_pair
        self._get_pair_data_callback = get_pair_data

        logger.info("Screener callbacks configured")

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized."""
        if not self.allowed_users:
            return True  # No restrictions
        return user_id in self.allowed_users

    def _get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Get main menu keyboard."""
        keyboard = [
            [KeyboardButton("📊 Status"), KeyboardButton("📈 Dashboard")],
            [KeyboardButton("📉 Graphs"), KeyboardButton("💹 Signals")],
            [KeyboardButton("⚙️ Settings"), KeyboardButton("❓ Help")],
        ]
        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )

    def _get_pairs_keyboard(self, pairs: list[PairMetrics]) -> InlineKeyboardMarkup:
        """Get inline keyboard with available pairs."""
        buttons = []
        for metrics in pairs:
            pair_name = f"{metrics.symbol1}/{metrics.symbol2}"
            callback_data = f"pair:{metrics.symbol1}:{metrics.symbol2}"
            buttons.append([InlineKeyboardButton(
                f"📊 {pair_name} (Z={metrics.current_zscore:.2f})",
                callback_data=callback_data
            )])

        # Add back button
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="menu:main")])

        return InlineKeyboardMarkup(buttons)

    def _get_pair_actions_keyboard(self, symbol1: str, symbol2: str) -> InlineKeyboardMarkup:
        """Get inline keyboard with actions for a specific pair."""
        buttons = [
            [
                InlineKeyboardButton("📈 Overview", callback_data=f"chart:overview:{symbol1}:{symbol2}"),
                InlineKeyboardButton("📉 Z-Score", callback_data=f"chart:zscore:{symbol1}:{symbol2}"),
            ],
            [
                InlineKeyboardButton("📊 Metrics", callback_data=f"metrics:{symbol1}:{symbol2}"),
                InlineKeyboardButton("🔄 Refresh", callback_data=f"refresh:{symbol1}:{symbol2}"),
            ],
            [InlineKeyboardButton("🔙 Back to pairs", callback_data="menu:pairs")],
        ]
        return InlineKeyboardMarkup(buttons)

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        if not self._is_authorized(user.id):
            await update.message.reply_text("⛔ Unauthorized access.")
            logger.warning("Unauthorized access attempt", user_id=user.id)
            return

        welcome_text = (
            f"👋 <b>Welcome to MOEX Pair Trading Screener!</b>\n\n"
            f"Hello, {user.first_name}!\n\n"
            f"Use the keyboard below to navigate:\n"
            f"• <b>📊 Status</b> - Current status of all pairs\n"
            f"• <b>📈 Dashboard</b> - Visual dashboard\n"
            f"• <b>📉 Graphs</b> - Charts for each pair\n"
            f"• <b>💹 Signals</b> - Today's trading signals\n"
            f"• <b>⚙️ Settings</b> - View current settings\n"
            f"• <b>❓ Help</b> - Show help\n\n"
            f"Or use commands:\n"
            f"/status - Quick status\n"
            f"/pairs - List monitored pairs\n"
            f"/dashboard - Z-score dashboard\n"
        )

        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_main_keyboard()
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._is_authorized(update.effective_user.id):
            return

        help_text = (
            "📚 <b>Help - Pair Trading Screener Bot</b>\n\n"
            "<b>Commands:</b>\n"
            "/start - Start bot and show menu\n"
            "/status - Quick status overview\n"
            "/pairs - List all monitored pairs\n"
            "/dashboard - Visual Z-score dashboard\n"
            "/signals - Today's trading signals\n"
            "/graph &lt;SYMBOL1&gt; &lt;SYMBOL2&gt; - Chart for specific pair\n"
            "/help - This help message\n\n"
            "<b>Keyboard Menu:</b>\n"
            "Use the buttons below for quick navigation.\n\n"
            "<b>Signal Types:</b>\n"
            "🟢 <b>LONG</b> - Buy spread (buy A, sell B)\n"
            "🔴 <b>SHORT</b> - Sell spread (sell A, buy B)\n"
            "⬜ <b>EXIT</b> - Close position\n"
            "🛑 <b>STOP</b> - Stop loss triggered\n\n"
            "<b>Z-Score Zones:</b>\n"
            "• Z &gt; 2.0: Short entry zone\n"
            "• Z &lt; -2.0: Long entry zone\n"
            "• |Z| &lt; 0.5: Exit zone\n"
        )

        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_main_keyboard()
        )

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command - show quick status."""
        if not self._is_authorized(update.effective_user.id):
            return

        if not self._get_active_pairs:
            await update.message.reply_text("❌ Screener not connected.")
            return

        pairs = self._get_active_pairs()
        positions = self._get_positions() if self._get_positions else {}
        signals_today = self._get_signals_today() if self._get_signals_today else []

        if not pairs:
            await update.message.reply_text(
                "📊 <b>Status</b>\n\nNo active pairs. Run analysis first.",
                parse_mode=ParseMode.HTML
            )
            return

        lines = [
            "📊 <b>Screener Status</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"",
            f"👀 <b>Monitored:</b> {len(pairs)} pairs",
            f"📈 <b>Signals today:</b> {len(signals_today)}",
            f"💼 <b>Open positions:</b> {len(positions)}",
            f"",
            f"<b>Pairs Z-Scores:</b>",
        ]

        settings = get_settings()
        entry_threshold = settings.entry_threshold

        for metrics in sorted(pairs, key=lambda x: abs(x.current_zscore), reverse=True):
            z = metrics.current_zscore
            pair = f"{metrics.symbol1}/{metrics.symbol2}"

            if z >= entry_threshold:
                emoji = "🔴"
                status = "SHORT"
            elif z <= -entry_threshold:
                emoji = "🟢"
                status = "LONG"
            elif abs(z) < 0.5:
                emoji = "⬜"
                status = "FLAT"
            else:
                emoji = "➖"
                status = ""

            coint = "✓" if metrics.is_cointegrated else "✗"
            lines.append(f"{emoji} <code>{pair:12}</code> Z={z:+.2f} {status} [{coint}]")

        lines.extend([
            f"",
            f"⏰ <i>{datetime.now().strftime('%H:%M:%S')}</i>",
        ])

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_main_keyboard()
        )

    async def _cmd_pairs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pairs command - list pairs with buttons."""
        if not self._is_authorized(update.effective_user.id):
            return

        if not self._get_active_pairs:
            await update.message.reply_text("❌ Screener not connected.")
            return

        pairs = self._get_active_pairs()

        if not pairs:
            await update.message.reply_text(
                "📊 <b>Pairs</b>\n\nNo active pairs. Analysis needed.",
                parse_mode=ParseMode.HTML
            )
            return

        await update.message.reply_text(
            "📊 <b>Select a pair for details:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_pairs_keyboard(pairs)
        )

    async def _cmd_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /dashboard command - send visual dashboard."""
        if not self._is_authorized(update.effective_user.id):
            return

        if not self._get_active_pairs:
            await update.message.reply_text("❌ Screener not connected.")
            return

        pairs = self._get_active_pairs()

        if not pairs:
            await update.message.reply_text(
                "📊 <b>Dashboard</b>\n\nNo data available.",
                parse_mode=ParseMode.HTML
            )
            return

        # Send "generating" message
        msg = await update.message.reply_text("⏳ Generating dashboard...")

        try:
            settings = get_settings()
            pairs_data = [metrics.to_dict() for metrics in pairs]

            image_bytes = self.chart_generator.generate_status_dashboard(
                pairs_data,
                entry_threshold=settings.entry_threshold
            )

            await update.message.reply_photo(
                photo=image_bytes,
                caption=f"📊 <b>Z-Score Dashboard</b>\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode=ParseMode.HTML
            )
            await msg.delete()

        except Exception as e:
            logger.error("Failed to generate dashboard", error=str(e))
            await msg.edit_text(f"❌ Error generating dashboard: {e}")

    async def _cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /signals command - show today's signals."""
        if not self._is_authorized(update.effective_user.id):
            return

        if not self._get_signals_today:
            await update.message.reply_text("❌ Screener not connected.")
            return

        signals = self._get_signals_today()

        if not signals:
            await update.message.reply_text(
                "💹 <b>Today's Signals</b>\n\nNo signals generated today.",
                parse_mode=ParseMode.HTML,
                reply_markup=self._get_main_keyboard()
            )
            return

        lines = [
            "💹 <b>Today's Signals</b>",
            f"━━━━━━━━━━━━━━━━━━━━",
            f"Total: {len(signals)}",
            "",
        ]

        for signal in signals[-10:]:  # Last 10 signals
            emoji = {
                "LONG_SPREAD": "🟢",
                "SHORT_SPREAD": "🔴",
                "EXIT_LONG": "⬜",
                "EXIT_SHORT": "⬜",
                "STOP_LOSS": "🛑",
            }.get(signal.signal_type.value, "➖")

            pair = f"{signal.symbol1}/{signal.symbol2}"
            time_str = signal.timestamp.strftime("%H:%M")

            lines.append(
                f"{emoji} <code>{time_str}</code> {pair} Z={signal.zscore:.2f}"
            )

        lines.append(f"\n⏰ <i>{datetime.now().strftime('%H:%M:%S')}</i>")

        await update.message.reply_text(
            "\n".join(lines),
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_main_keyboard()
        )

    async def _cmd_graph(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /graph command - generate chart for specific pair."""
        if not self._is_authorized(update.effective_user.id):
            return

        args = context.args
        if not args or len(args) < 2:
            await update.message.reply_text(
                "❓ <b>Usage:</b> /graph SYMBOL1 SYMBOL2\n\n"
                "Example: /graph SBER VTBR",
                parse_mode=ParseMode.HTML
            )
            return

        symbol1, symbol2 = args[0].upper(), args[1].upper()
        await self._send_pair_chart(update, symbol1, symbol2, "overview")

    async def _send_pair_chart(
        self,
        update: Update,
        symbol1: str,
        symbol2: str,
        chart_type: str = "overview"
    ):
        """Send chart for a pair."""
        if not self._get_active_pairs:
            await update.effective_message.reply_text("❌ Screener not connected.")
            return

        pairs = self._get_active_pairs()
        metrics = None

        for p in pairs:
            if (p.symbol1 == symbol1 and p.symbol2 == symbol2) or \
               (p.symbol1 == symbol2 and p.symbol2 == symbol1):
                metrics = p
                break

        if not metrics:
            await update.effective_message.reply_text(
                f"❌ Pair {symbol1}/{symbol2} not found in active pairs."
            )
            return

        msg = await update.effective_message.reply_text("⏳ Generating chart...")

        try:
            settings = get_settings()

            if chart_type == "zscore" and metrics.zscore is not None:
                image_bytes = self.chart_generator.generate_zscore_chart(
                    zscore=metrics.zscore,
                    symbol1=metrics.symbol1,
                    symbol2=metrics.symbol2,
                    entry_threshold=settings.entry_threshold,
                    stop_threshold=settings.stop_loss_threshold,
                )
                caption = f"📉 <b>Z-Score Chart: {symbol1}/{symbol2}</b>"

            elif metrics.spread is not None and metrics.zscore is not None:
                # Get price data from the callback if available
                if self._get_pair_data_callback:
                    try:
                        data1 = await self._get_pair_data_callback(symbol1)
                        data2 = await self._get_pair_data_callback(symbol2)
                        prices1 = data1["close"].tail(len(metrics.spread))
                        prices2 = data2["close"].tail(len(metrics.spread))
                    except Exception:
                        # Fallback to synthetic data
                        prices1 = metrics.spread + metrics.hedge_ratio * 100
                        prices2 = metrics.spread.copy() * 0 + 100
                else:
                    # Synthetic data for visualization
                    prices1 = metrics.spread + metrics.hedge_ratio * 100
                    prices2 = metrics.spread.copy() * 0 + 100

                image_bytes = self.chart_generator.generate_pair_overview(
                    prices1=prices1,
                    prices2=prices2,
                    spread=metrics.spread,
                    zscore=metrics.zscore,
                    symbol1=metrics.symbol1,
                    symbol2=metrics.symbol2,
                    hedge_ratio=metrics.hedge_ratio,
                    entry_threshold=settings.entry_threshold,
                    exit_threshold=settings.exit_threshold,
                )
                caption = f"📈 <b>Pair Overview: {symbol1}/{symbol2}</b>"
            else:
                await msg.edit_text(f"❌ Insufficient data for {symbol1}/{symbol2} chart.")
                return

            # Add metrics to caption
            caption += (
                f"\n\n"
                f"📊 Z-Score: <b>{metrics.current_zscore:.2f}</b>\n"
                f"🔗 Cointegrated: {'✅' if metrics.is_cointegrated else '❌'}\n"
                f"📈 Correlation: {metrics.correlation:.3f}\n"
                f"⚖️ Hedge Ratio: {metrics.hedge_ratio:.4f}"
            )

            if metrics.half_life != float('inf'):
                caption += f"\n⏱️ Half-life: {metrics.half_life:.1f} days"

            await update.effective_message.reply_photo(
                photo=image_bytes,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=self._get_pair_actions_keyboard(symbol1, symbol2)
            )
            await msg.delete()

        except Exception as e:
            logger.error("Failed to generate chart", error=str(e), pair=f"{symbol1}/{symbol2}")
            await msg.edit_text(f"❌ Error generating chart: {e}")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        await query.answer()

        if not self._is_authorized(query.from_user.id):
            return

        data = query.data

        if data.startswith("pair:"):
            # Show pair actions
            _, symbol1, symbol2 = data.split(":")
            await self._show_pair_details(query, symbol1, symbol2)

        elif data.startswith("chart:"):
            # Generate chart
            parts = data.split(":")
            chart_type, symbol1, symbol2 = parts[1], parts[2], parts[3]
            await self._send_pair_chart(update, symbol1, symbol2, chart_type)

        elif data.startswith("metrics:"):
            # Show detailed metrics
            _, symbol1, symbol2 = data.split(":")
            await self._show_pair_metrics(query, symbol1, symbol2)

        elif data.startswith("refresh:"):
            # Refresh pair analysis
            _, symbol1, symbol2 = data.split(":")
            await self._refresh_pair(query, symbol1, symbol2)

        elif data == "menu:pairs":
            # Back to pairs list
            if self._get_active_pairs:
                pairs = self._get_active_pairs()
                await query.edit_message_text(
                    "📊 <b>Select a pair for details:</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=self._get_pairs_keyboard(pairs)
                )

        elif data == "menu:main":
            await query.edit_message_text(
                "🏠 Use the keyboard menu below.",
                parse_mode=ParseMode.HTML
            )

    async def _show_pair_details(self, query, symbol1: str, symbol2: str):
        """Show details for a specific pair."""
        if not self._get_active_pairs:
            return

        pairs = self._get_active_pairs()
        metrics = None

        for p in pairs:
            if p.symbol1 == symbol1 and p.symbol2 == symbol2:
                metrics = p
                break

        if not metrics:
            await query.edit_message_text(f"❌ Pair {symbol1}/{symbol2} not found.")
            return

        settings = get_settings()
        z = metrics.current_zscore
        entry = settings.entry_threshold

        if z >= entry:
            signal_status = "🔴 <b>SHORT ENTRY ZONE</b>"
        elif z <= -entry:
            signal_status = "🟢 <b>LONG ENTRY ZONE</b>"
        elif abs(z) < settings.exit_threshold + 0.5:
            signal_status = "⬜ <b>EXIT ZONE</b>"
        else:
            signal_status = "➖ Neutral"

        text = (
            f"📊 <b>{symbol1}/{symbol2}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"{signal_status}\n\n"
            f"📉 <b>Z-Score:</b> {z:.3f}\n"
            f"📈 <b>Correlation:</b> {metrics.correlation:.4f}\n"
            f"🔗 <b>Cointegrated:</b> {'✅' if metrics.is_cointegrated else '❌'} "
            f"(p={metrics.cointegration_pvalue:.4f})\n"
            f"⚖️ <b>Hedge Ratio:</b> {metrics.hedge_ratio:.4f}\n"
        )

        if metrics.half_life != float('inf'):
            text += f"⏱️ <b>Half-life:</b> {metrics.half_life:.1f} days\n"

        if metrics.hurst_exponent:
            hurst_desc = "mean-reverting" if metrics.hurst_exponent < 0.5 else "trending"
            text += f"📐 <b>Hurst:</b> {metrics.hurst_exponent:.3f} ({hurst_desc})\n"

        text += f"\n⏰ Updated: {metrics.last_updated.strftime('%H:%M:%S')}"

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_pair_actions_keyboard(symbol1, symbol2)
        )

    async def _show_pair_metrics(self, query, symbol1: str, symbol2: str):
        """Show detailed metrics for a pair."""
        await self._show_pair_details(query, symbol1, symbol2)

    async def _refresh_pair(self, query, symbol1: str, symbol2: str):
        """Refresh analysis for a pair."""
        if not self._analyze_pair_callback:
            await query.answer("Refresh not available", show_alert=True)
            return

        await query.answer("Refreshing...")

        try:
            await self._analyze_pair_callback(symbol1, symbol2)
            await self._show_pair_details(query, symbol1, symbol2)
        except Exception as e:
            logger.error("Failed to refresh pair", error=str(e))
            await query.answer(f"Error: {e}", show_alert=True)

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (keyboard buttons)."""
        if not self._is_authorized(update.effective_user.id):
            return

        text = update.message.text

        if text == "📊 Status":
            await self._cmd_status(update, context)
        elif text == "📈 Dashboard":
            await self._cmd_dashboard(update, context)
        elif text == "📉 Graphs":
            await self._cmd_pairs(update, context)
        elif text == "💹 Signals":
            await self._cmd_signals(update, context)
        elif text == "⚙️ Settings":
            await self._show_settings(update)
        elif text == "❓ Help":
            await self._cmd_help(update, context)
        else:
            await update.message.reply_text(
                "Use the keyboard menu or /help for commands.",
                reply_markup=self._get_main_keyboard()
            )

    async def _show_settings(self, update: Update):
        """Show current settings."""
        settings = get_settings()

        text = (
            "⚙️ <b>Current Settings</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"<b>Trading Parameters:</b>\n"
            f"• Entry threshold: ±{settings.entry_threshold}\n"
            f"• Exit threshold: ±{settings.exit_threshold}\n"
            f"• Stop loss: ±{settings.stop_loss_threshold}\n"
            f"• Lookback period: {settings.lookback_period} days\n"
            f"• Spread window: {settings.spread_window} days\n\n"
            f"<b>Risk Management:</b>\n"
            f"• Max position size: {settings.max_position_size:,.0f} RUB\n"
            f"• Max open positions: {settings.max_open_positions}\n\n"
            f"<b>Scheduler:</b>\n"
            f"• Analysis interval: {settings.analysis_interval}s\n"
            f"• Daily summary: {settings.daily_summary_time}\n"
        )

        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=self._get_main_keyboard()
        )

    async def start(self):
        """Start the bot polling."""
        if not self.bot_token:
            logger.error("Bot token not configured")
            return False

        try:
            self._application = (
                Application.builder()
                .token(self.bot_token)
                .build()
            )

            # Register handlers
            self._application.add_handler(CommandHandler("start", self._cmd_start))
            self._application.add_handler(CommandHandler("help", self._cmd_help))
            self._application.add_handler(CommandHandler("status", self._cmd_status))
            self._application.add_handler(CommandHandler("pairs", self._cmd_pairs))
            self._application.add_handler(CommandHandler("dashboard", self._cmd_dashboard))
            self._application.add_handler(CommandHandler("signals", self._cmd_signals))
            self._application.add_handler(CommandHandler("graph", self._cmd_graph))

            # Callback query handler
            self._application.add_handler(CallbackQueryHandler(self._handle_callback))

            # Message handler for keyboard
            self._application.add_handler(MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self._handle_message
            ))

            self._running = True
            logger.info("Starting Telegram bot polling...")

            await self._application.initialize()
            await self._application.start()
            await self._application.updater.start_polling(drop_pending_updates=True)

            return True

        except Exception as e:
            logger.error("Failed to start bot", error=str(e))
            return False

    async def stop(self):
        """Stop the bot."""
        self._running = False
        if self._application:
            try:
                await self._application.updater.stop()
                await self._application.stop()
                await self._application.shutdown()
                logger.info("Bot stopped")
            except Exception as e:
                logger.error("Error stopping bot", error=str(e))

    def is_running(self) -> bool:
        """Check if bot is running."""
        return self._running

