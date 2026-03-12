"""Telegram alert bot for real-time notifications and kill switch commands."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import TYPE_CHECKING

import httpx
from loguru import logger

if TYPE_CHECKING:
    from src.context import TradingContext


class TelegramBot:
    """Sends alerts to a Telegram chat, listens for commands, and bridges to Agent Zero."""

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(
        self,
        token: str,
        chat_id: str,
        agent_zero_url: str = "",
        agent_zero_api_key: str = "",
    ) -> None:
        self._token = token
        self._chat_id = chat_id
        self._enabled = bool(token)  # enable if token exists; chat_id can be auto-discovered
        self._client: httpx.AsyncClient | None = None

        # Agent Zero bridge
        self._az_url = agent_zero_url.rstrip("/") if agent_zero_url else ""
        self._az_api_key = agent_zero_api_key
        self._az_context_id: str = ""  # persistent conversation context

    def _get_client(self) -> httpx.AsyncClient:
        """Get or create a reusable httpx client.

        Timeout is set high enough to support Telegram long-polling
        (getUpdates with timeout=30 needs at least 35s on the client).
        """
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=40.0)
        return self._client

    @property
    def enabled(self) -> bool:
        return self._enabled

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Outbound Messages ────────────────────────────────────

    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to the configured chat."""
        if not self._enabled or not self._chat_id:
            return False

        try:
            client = self._get_client()
            response = await client.post(
                f"{self.BASE_URL.format(token=self._token)}/sendMessage",
                json={
                    "chat_id": self._chat_id,
                    "text": text[:4096],  # Telegram message limit
                    "parse_mode": parse_mode,
                },
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Telegram send failed: {e}")
            return False

    async def send_trade_alert(
        self,
        action: str,
        market_question: str,
        size_usd: float,
        price: float,
        edge: float,
        is_paper: bool = True,
    ) -> bool:
        """Send a formatted trade alert."""
        mode = "PAPER" if is_paper else "LIVE"
        text = (
            f"{'📝' if is_paper else '🔴'} <b>[{mode}] {action}</b>\n"
            f"📊 {market_question[:100]}\n"
            f"💰 Size: ${size_usd:.2f} @ {price:.3f}\n"
            f"📈 Edge: {edge:.2%}"
        )
        return await self.send_message(text)

    async def send_pending_trade_notification(
        self,
        trade_id: str,
        question: str,
        estimated_prob: Decimal,
        market_price: Decimal,
        edge: Decimal,
        size_usd: Decimal,
        confidence: str,
    ) -> bool:
        """Notify user of a new pending trade awaiting approval."""
        text = (
            f"🔔 <b>New Trade Opportunity</b>\n\n"
            f"📊 {question[:150]}\n\n"
            f"Our estimate: <b>{float(estimated_prob):.1%}</b>\n"
            f"Market price: <b>{float(market_price):.1%}</b>\n"
            f"Edge: <b>{float(edge):.1%}</b> after fees\n"
            f"Bet size: <b>${float(size_usd):.2f}</b>\n"
            f"Confidence: {confidence}\n\n"
            f"/approve_{trade_id[:8]} - Approve\n"
            f"/skip_{trade_id[:8]} - Skip\n"
            f"/detail_{trade_id[:8]} - Full analysis"
        )
        return await self.send_message(text)

    async def send_risk_alert(
        self, breaker_type: str, value: float, threshold: float
    ) -> bool:
        """Send a risk/circuit breaker alert."""
        text = (
            f"🚨 <b>CIRCUIT BREAKER: {breaker_type}</b>\n"
            f"Value: {value:.4f}\n"
            f"Threshold: {threshold:.4f}\n"
            f"Trading has been PAUSED."
        )
        return await self.send_message(text)

    async def send_startup_alert(self, mode: str, paused: bool) -> bool:
        """Send a startup notification."""
        status = "PAUSED" if paused else "ACTIVE"
        text = (
            f"🤖 <b>Trading Bot Started</b>\n"
            f"Mode: {mode}\n"
            f"Status: {status}\n\n"
            f"<b>Commands:</b>\n"
            f"/trades - Pending trade opportunities\n"
            f"/portfolio - Portfolio summary\n"
            f"/health - Bot health check\n"
            f"/killswitch - Emergency stop\n"
            f"/resume - Resume trading\n"
            f"/help - All commands"
        )
        return await self.send_message(text)

    # ── Command Polling ─────────────────────────────────────

    async def start_command_listener(self, ctx: TradingContext) -> None:
        """Poll for Telegram commands and execute them."""
        if not self._enabled:
            return

        if not self._chat_id:
            logger.info(
                "TELEGRAM_CHAT_ID not set — waiting for first message to auto-discover. "
                "Send any message to your bot on Telegram."
            )

        logger.info("Telegram command listener started.")
        last_update_id = 0

        while True:
            try:
                client = self._get_client()
                resp = await client.get(
                    f"{self.BASE_URL.format(token=self._token)}/getUpdates",
                    params={"offset": last_update_id + 1, "timeout": 30},
                    timeout=35.0,
                )
                resp.raise_for_status()
                updates = resp.json().get("result", [])

                for update in updates:
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    text = message.get("text", "").strip()
                    chat_id = str(message.get("chat", {}).get("id", ""))

                    if not chat_id:
                        continue

                    # Auto-discover chat_id from the first message
                    if not self._chat_id:
                        self._chat_id = chat_id
                        self._save_chat_id(chat_id)
                        logger.info(f"Auto-discovered Telegram chat_id: {chat_id}")
                        await self.send_message(
                            "🤖 <b>Bot linked!</b>\n"
                            f"Chat ID <code>{chat_id}</code> saved.\n\n"
                            "Send /help for available commands."
                        )
                        continue

                    # Only respond to the configured chat
                    if chat_id != self._chat_id:
                        continue

                    await self._dispatch_command(text, ctx)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Telegram polling error: {e}")
                await asyncio.sleep(5)

    @staticmethod
    def _save_chat_id(chat_id: str) -> None:
        """Persist the discovered chat_id to .env so it survives restarts."""
        import re
        from pathlib import Path

        # Use absolute path relative to project root (where this package lives)
        project_root = Path(__file__).resolve().parent.parent.parent
        env_path = project_root / ".env"

        if not env_path.exists():
            env_path.write_text(f"TELEGRAM_CHAT_ID={chat_id}\n")
            logger.info(f"Created {env_path} with TELEGRAM_CHAT_ID={chat_id}")
            return

        content = env_path.read_text()
        if re.search(r"^TELEGRAM_CHAT_ID=", content, re.MULTILINE):
            content = re.sub(
                r"^TELEGRAM_CHAT_ID=.*$",
                f"TELEGRAM_CHAT_ID={chat_id}",
                content,
                flags=re.MULTILINE,
            )
        else:
            content += f"\nTELEGRAM_CHAT_ID={chat_id}\n"
        env_path.write_text(content)
        logger.info(f"Saved TELEGRAM_CHAT_ID={chat_id} to {env_path}")

    async def _dispatch_command(self, text: str, ctx: TradingContext) -> None:
        """Route incoming text to the appropriate handler.

        Slash commands are handled locally. Everything else is forwarded
        to Agent Zero as natural language.
        """
        if text in ("/start", "/help"):
            await self._handle_help()
        elif text == "/killswitch":
            await self._handle_killswitch(ctx)
        elif text in ("/status", "/portfolio"):
            await self._handle_portfolio(ctx)
        elif text == "/resume":
            await self._handle_resume(ctx)
        elif text in ("/trades", "/pending"):
            await self._handle_trades(ctx)
        elif text == "/health":
            await self._handle_health(ctx)
        elif text == "/reset":
            await self._handle_reset_context()
        elif text.startswith("/approve_"):
            trade_prefix = text.replace("/approve_", "").strip()
            await self._handle_approve(trade_prefix, ctx)
        elif text.startswith("/skip_"):
            trade_prefix = text.replace("/skip_", "").strip()
            await self._handle_reject(trade_prefix, ctx)
        elif text.startswith("/detail_"):
            trade_prefix = text.replace("/detail_", "").strip()
            await self._handle_detail(trade_prefix, ctx)
        elif text and not text.startswith("/"):
            # Forward natural language to Agent Zero
            await self._forward_to_agent_zero(text)

    # ── Command Handlers ─────────────────────────────────────

    async def _handle_help(self) -> None:
        """Show all available commands."""
        az_status = "🟢 Connected" if self._az_url else "⚪ Not configured"
        text = (
            "📋 <b>Available Commands</b>\n\n"
            "<b>Trading:</b>\n"
            "/trades - Show pending trade opportunities\n"
            "/portfolio - Portfolio summary & P&L\n"
            "/health - Bot health check\n"
            "/killswitch - Emergency stop (pause + cancel all)\n"
            "/resume - Resume trading\n"
            "/help - This message\n\n"
            "<b>Trade actions:</b>\n"
            "/approve_XXXX - Approve a pending trade\n"
            "/skip_XXXX - Skip/reject a pending trade\n"
            "/detail_XXXX - See full analysis for a trade\n\n"
            "<b>Agent Zero:</b>\n"
            f"Status: {az_status}\n"
            "Just type any message to chat with Agent Zero.\n"
            "/reset - Start a new Agent Zero conversation"
        )
        await self.send_message(text)

    async def _handle_trades(self, ctx: TradingContext) -> None:
        """List pending trades awaiting approval."""
        pending = await ctx.repo.get_pending_trades()
        if not pending:
            await self.send_message("No pending trades right now.")
            return

        for trade in pending:
            text = (
                f"🔔 <b>Pending Trade</b>\n"
                f"📊 {trade.question[:120]}\n"
                f"Our est: {float(trade.estimated_prob):.1%} | "
                f"Market: {float(trade.market_price):.1%}\n"
                f"Edge: {float(trade.edge_magnitude):.1%} | "
                f"Bet: ${float(trade.size_usd):.2f}\n\n"
                f"/approve_{trade.id[:8]} | "
                f"/skip_{trade.id[:8]} | "
                f"/detail_{trade.id[:8]}"
            )
            await self.send_message(text)

    async def _handle_approve(self, trade_prefix: str, ctx: TradingContext) -> None:
        """Approve a pending trade by ID prefix."""
        trade = await self._find_trade_by_prefix(trade_prefix, ctx)
        if not trade:
            await self.send_message(f"Trade starting with '{trade_prefix}' not found.")
            return

        if trade.status != "pending":
            await self.send_message(f"Trade already {trade.status}.")
            return

        # Mark as approved and execute
        await ctx.repo.update_pending_trade_status(trade.id, "approved")

        from src.core.pipeline import execute_decision
        from src.data.schemas import TradeDecision

        decision = TradeDecision(
            action=trade.action,
            reason=f"User-approved via Telegram",
            market_id=trade.market_id,
            token_id=trade.token_id,
            size_usd=trade.size_usd,
            price=trade.price,
        )

        try:
            result = await execute_decision(decision, ctx)
            exec_status = result.get("status", "unknown")
            await self.send_message(
                f"✅ <b>Trade Approved & Executed</b>\n"
                f"📊 {trade.question[:80]}\n"
                f"Status: {exec_status}"
            )
            logger.info(f"Trade {trade.id} approved via Telegram: {exec_status}")
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            await self.send_message(
                f"❌ <b>Execution Failed</b>\n"
                f"Trade {trade.id[:8]} approved but execution error:\n"
                f"{str(e)[:200]}"
            )

    async def _handle_reject(self, trade_prefix: str, ctx: TradingContext) -> None:
        """Reject/skip a pending trade by ID prefix."""
        trade = await self._find_trade_by_prefix(trade_prefix, ctx)
        if not trade:
            await self.send_message(f"Trade starting with '{trade_prefix}' not found.")
            return

        if trade.status != "pending":
            await self.send_message(f"Trade already {trade.status}.")
            return

        await ctx.repo.update_pending_trade_status(trade.id, "rejected")
        await self.send_message(
            f"⏭️ <b>Trade Skipped</b>\n"
            f"{trade.question[:80]}"
        )
        logger.info(f"Trade {trade.id} rejected via Telegram")

    async def _handle_detail(self, trade_prefix: str, ctx: TradingContext) -> None:
        """Show full analysis detail for a pending trade."""
        trade = await self._find_trade_by_prefix(trade_prefix, ctx)
        if not trade:
            await self.send_message(f"Trade starting with '{trade_prefix}' not found.")
            return

        text = (
            f"📋 <b>Trade Detail</b>\n\n"
            f"<b>Market:</b> {trade.question[:200]}\n\n"
            f"<b>Direction:</b> {trade.action}\n"
            f"<b>Our estimate:</b> {float(trade.estimated_prob):.1%}\n"
            f"<b>Market price:</b> {float(trade.market_price):.1%}\n"
            f"<b>Edge:</b> {float(trade.edge_magnitude):.1%}\n"
            f"<b>Kelly fraction:</b> {float(trade.kelly_fraction):.2f}\n"
            f"<b>Bet size:</b> ${float(trade.size_usd):.2f}\n"
            f"<b>Entry price:</b> {float(trade.price):.4f}\n"
            f"<b>Confidence:</b> {trade.confidence}\n\n"
            f"<b>Reasoning:</b>\n{trade.reasoning[:1000]}\n\n"
            f"/approve_{trade.id[:8]} | /skip_{trade.id[:8]}"
        )
        await self.send_message(text)

    async def _handle_portfolio(self, ctx: TradingContext) -> None:
        """Send portfolio summary."""
        if ctx.portfolio:
            try:
                summary = await ctx.portfolio.get_summary(ctx)
                text = (
                    f"📊 <b>Portfolio Status</b>\n"
                    f"Total Value: ${float(summary.total_value):.2f}\n"
                    f"Cash: ${float(summary.cash_balance):.2f}\n"
                    f"Unrealized P&L: ${float(summary.unrealized_pnl):.2f}\n"
                    f"Realized P&L: ${float(summary.realized_pnl):.2f}\n"
                    f"Open Positions: {summary.open_positions_count}\n"
                    f"Trading: {'PAUSED' if ctx.trading_paused else 'ACTIVE'}"
                )
            except Exception as e:
                logger.warning(f"Failed to get portfolio summary: {e}")
                text = (
                    f"📊 <b>Status</b>\n"
                    f"Mode: {ctx.config.trading_mode}\n"
                    f"Trading: {'PAUSED' if ctx.trading_paused else 'ACTIVE'}"
                )
        else:
            text = (
                f"📊 <b>Status</b>\n"
                f"Mode: {ctx.config.trading_mode}\n"
                f"Trading: {'PAUSED' if ctx.trading_paused else 'ACTIVE'}"
            )
        await self.send_message(text)

    async def _handle_health(self, ctx: TradingContext) -> None:
        """Send bot health information."""
        uptime_h = ctx.uptime_seconds / 3600
        mode = ctx.config.trading_mode
        paused = ctx.trading_paused

        # Count pending trades
        pending = await ctx.repo.get_pending_trades()
        pending_count = len(pending)

        text = (
            f"🏥 <b>Bot Health</b>\n\n"
            f"Status: {'🟢 Running' if not paused else '🟡 Paused'}\n"
            f"Mode: {mode}\n"
            f"Uptime: {uptime_h:.1f}h\n"
            f"Pending trades: {pending_count}\n"
            f"Database: {'🟢 OK' if ctx.repo else '🔴 Error'}\n"
            f"Gamma API: {'🟢 Connected' if ctx.gamma else '🔴 Down'}\n"
            f"CLOB: {'🟢 Connected' if ctx.clob else '⚪ Not configured'}"
        )
        await self.send_message(text)

    async def _handle_killswitch(self, ctx: TradingContext) -> None:
        """Pause trading and cancel all orders."""
        ctx.trading_paused = True
        logger.warning("KILL SWITCH activated via Telegram!")

        cancelled = 0
        if hasattr(ctx, "executor") and ctx.executor:
            try:
                cancelled = await ctx.executor.cancel_all_orders()
            except Exception as e:
                logger.error(f"Failed to cancel orders: {e}")

        await self.send_message(
            f"🛑 <b>KILL SWITCH ACTIVATED</b>\n"
            f"Trading: PAUSED\n"
            f"Orders cancelled: {cancelled}"
        )

    async def _handle_resume(self, ctx: TradingContext) -> None:
        """Resume trading."""
        if ctx.config.trading_mode == "live":
            await self.send_message(
                "⚠️ Cannot resume live trading via Telegram. "
                "Use the dashboard for safety."
            )
            return

        ctx.trading_paused = False
        logger.info("Trading resumed via Telegram command.")
        await self.send_message("✅ <b>Trading Resumed</b>")

    # ── Agent Zero Bridge ─────────────────────────────────────

    async def _forward_to_agent_zero(self, text: str) -> None:
        """Forward a natural-language message to Agent Zero and relay the reply."""
        if not self._az_url:
            await self.send_message(
                "Agent Zero is not configured.\n"
                "Set <code>AGENT_ZERO_URL</code> and <code>AGENT_ZERO_API_KEY</code> in .env",
            )
            return

        # Send typing indicator so the user knows something is happening
        await self._send_chat_action("typing")

        try:
            client = self._get_client()
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._az_api_key:
                headers["X-API-KEY"] = self._az_api_key

            payload: dict[str, str | int] = {
                "message": text,
                "lifetime_hours": 24,
            }
            if self._az_context_id:
                payload["context_id"] = self._az_context_id

            resp = await client.post(
                f"{self._az_url}/api_message",
                json=payload,
                headers=headers,
                timeout=300.0,  # Agent Zero can take a while to think
            )
            resp.raise_for_status()
            data = resp.json()

            # Persist context for follow-up messages
            if data.get("context_id"):
                self._az_context_id = data["context_id"]

            reply = data.get("response", "").strip()
            if not reply:
                reply = "(Agent Zero returned an empty response)"

            # Telegram messages max 4096 chars — split if needed
            for chunk in self._split_message(reply):
                await self.send_message(chunk, parse_mode="")
                await asyncio.sleep(0.3)  # avoid rate limits

        except httpx.TimeoutException:
            await self.send_message("Agent Zero timed out (5 min). Try a simpler request.")
        except httpx.HTTPStatusError as e:
            logger.warning(f"Agent Zero HTTP error: {e.response.status_code}")
            await self.send_message(
                f"Agent Zero error: HTTP {e.response.status_code}\n"
                f"{e.response.text[:200]}"
            )
        except Exception as e:
            logger.warning(f"Agent Zero bridge error: {e}")
            await self.send_message(f"Agent Zero error: {str(e)[:300]}")

    async def _handle_reset_context(self) -> None:
        """Reset the Agent Zero conversation context."""
        self._az_context_id = ""
        await self.send_message("Agent Zero conversation reset. Next message starts fresh.")

    async def _send_chat_action(self, action: str = "typing") -> None:
        """Send a chat action (typing indicator) to Telegram."""
        if not self._chat_id:
            return
        try:
            client = self._get_client()
            await client.post(
                f"{self.BASE_URL.format(token=self._token)}/sendChatAction",
                json={"chat_id": self._chat_id, "action": action},
            )
        except Exception:
            pass  # typing indicator is best-effort

    @staticmethod
    def _split_message(text: str, max_len: int = 4096) -> list[str]:
        """Split a long message into Telegram-safe chunks."""
        if len(text) <= max_len:
            return [text]
        chunks: list[str] = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break
            # Try to split at a newline
            split_at = text.rfind("\n", 0, max_len)
            if split_at < max_len // 2:
                split_at = max_len  # no good newline, hard split
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks

    # ── Helpers ──────────────────────────────────────────────

    async def _find_trade_by_prefix(
        self, prefix: str, ctx: TradingContext
    ):
        """Find a pending trade whose ID starts with the given prefix."""
        pending = await ctx.repo.get_pending_trades()
        # Also check approved/rejected trades for detail viewing
        for trade in pending:
            if trade.id.startswith(prefix):
                return trade

        # Try getting by exact ID or prefix match from all pending trades
        trade = await ctx.repo.get_pending_trade(prefix)
        if trade:
            return trade

        return None
