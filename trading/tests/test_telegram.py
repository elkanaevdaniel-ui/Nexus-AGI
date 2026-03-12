"""Tests for Telegram bot command handling."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.integrations.telegram import TelegramBot


@pytest.fixture
def bot() -> TelegramBot:
    """Disabled bot (no token) for testing logic without API calls."""
    return TelegramBot("", "")


@pytest.fixture
def enabled_bot() -> TelegramBot:
    """Enabled bot with mocked send_message."""
    b = TelegramBot("fake-token", "12345")
    b.send_message = AsyncMock(return_value=True)
    return b


class TestTelegramBotInit:
    def test_disabled_when_no_token(self) -> None:
        bot = TelegramBot("", "")
        assert not bot.enabled

    def test_enabled_without_chat_id_for_auto_discovery(self) -> None:
        bot = TelegramBot("token", "")
        assert bot.enabled  # enabled for auto-discovery; chat_id found on first message

    def test_enabled_with_both(self) -> None:
        bot = TelegramBot("token", "chat_id")
        assert bot.enabled


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_disabled_returns_false(self, bot: TelegramBot) -> None:
        result = await bot.send_message("hello")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_enabled_posts_to_api(self) -> None:
        bot = TelegramBot("fake-token", "12345")
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False
        bot._client = mock_client

        result = await bot.send_message("hello")
        assert result is True
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "hello" in str(call_args)


class TestPendingTradeNotification:
    @pytest.mark.asyncio
    async def test_notification_format(self, enabled_bot: TelegramBot) -> None:
        await enabled_bot.send_pending_trade_notification(
            trade_id="abc12345-def",
            question="Will Bitcoin hit $100k by EOY?",
            estimated_prob=Decimal("0.65"),
            market_price=Decimal("0.50"),
            edge=Decimal("0.12"),
            size_usd=Decimal("50.00"),
            confidence="high",
        )
        enabled_bot.send_message.assert_called_once()
        msg = enabled_bot.send_message.call_args[0][0]
        assert "Bitcoin" in msg
        assert "approve_abc12345" in msg
        assert "skip_abc12345" in msg
        assert "65.0%" in msg
        assert "50.0%" in msg
        assert "$50.00" in msg


class TestCommandDispatch:
    @pytest_asyncio.fixture
    async def ctx(self, trading_ctx):
        return trading_ctx

    @pytest.mark.asyncio
    async def test_help_command(self, enabled_bot: TelegramBot) -> None:
        await enabled_bot._handle_help()
        enabled_bot.send_message.assert_called_once()
        msg = enabled_bot.send_message.call_args[0][0]
        assert "/trades" in msg
        assert "/portfolio" in msg
        assert "/killswitch" in msg

    @pytest.mark.asyncio
    async def test_health_command(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        await enabled_bot._handle_health(trading_ctx)
        enabled_bot.send_message.assert_called_once()
        msg = enabled_bot.send_message.call_args[0][0]
        assert "Bot Health" in msg
        assert "Running" in msg
        assert "paper" in msg

    @pytest.mark.asyncio
    async def test_portfolio_command(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        await enabled_bot._handle_portfolio(trading_ctx)
        enabled_bot.send_message.assert_called_once()
        msg = enabled_bot.send_message.call_args[0][0]
        assert "Portfolio Status" in msg

    @pytest.mark.asyncio
    async def test_trades_empty(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        await enabled_bot._handle_trades(trading_ctx)
        enabled_bot.send_message.assert_called_once()
        msg = enabled_bot.send_message.call_args[0][0]
        assert "No pending trades" in msg

    @pytest.mark.asyncio
    async def test_trades_with_pending(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        # Create a pending trade in the DB
        await trading_ctx.repo.create_pending_trade({
            "market_id": "market_1",
            "question": "Will ETH hit $5k?",
            "action": "BUY",
            "token_id": "token_1",
            "size_usd": Decimal("25.00"),
            "price": Decimal("0.40"),
            "edge_magnitude": Decimal("0.08"),
            "estimated_prob": Decimal("0.50"),
            "market_price": Decimal("0.40"),
            "kelly_fraction": Decimal("0.15"),
            "confidence": "medium",
            "reasoning": "Strong fundamentals",
            "status": "pending",
        })

        await enabled_bot._handle_trades(trading_ctx)
        assert enabled_bot.send_message.call_count >= 1
        msg = enabled_bot.send_message.call_args[0][0]
        assert "ETH" in msg
        assert "approve_" in msg

    @pytest.mark.asyncio
    async def test_killswitch(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        assert not trading_ctx.trading_paused
        await enabled_bot._handle_killswitch(trading_ctx)
        assert trading_ctx.trading_paused
        msg = enabled_bot.send_message.call_args[0][0]
        assert "KILL SWITCH" in msg

    @pytest.mark.asyncio
    async def test_resume_paper_mode(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        trading_ctx.trading_paused = True
        await enabled_bot._handle_resume(trading_ctx)
        assert not trading_ctx.trading_paused
        msg = enabled_bot.send_message.call_args[0][0]
        assert "Resumed" in msg

    @pytest.mark.asyncio
    async def test_resume_blocked_in_live_mode(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        trading_ctx.config.trading_mode = "live"
        trading_ctx.trading_paused = True
        await enabled_bot._handle_resume(trading_ctx)
        assert trading_ctx.trading_paused  # Still paused
        msg = enabled_bot.send_message.call_args[0][0]
        assert "Cannot resume" in msg


class TestTradeApproval:
    @pytest.mark.asyncio
    async def test_approve_nonexistent_trade(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        await enabled_bot._handle_approve("nonexist", trading_ctx)
        msg = enabled_bot.send_message.call_args[0][0]
        assert "not found" in msg

    @pytest.mark.asyncio
    async def test_reject_nonexistent_trade(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        await enabled_bot._handle_reject("nonexist", trading_ctx)
        msg = enabled_bot.send_message.call_args[0][0]
        assert "not found" in msg

    @pytest.mark.asyncio
    async def test_reject_pending_trade(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        pending = await trading_ctx.repo.create_pending_trade({
            "market_id": "market_2",
            "question": "Will SOL hit $500?",
            "action": "BUY",
            "token_id": "token_2",
            "size_usd": Decimal("30.00"),
            "price": Decimal("0.35"),
            "edge_magnitude": Decimal("0.10"),
            "estimated_prob": Decimal("0.45"),
            "market_price": Decimal("0.35"),
            "kelly_fraction": Decimal("0.12"),
            "confidence": "low",
            "reasoning": "Speculative play",
            "status": "pending",
        })

        prefix = pending.id[:8]
        await enabled_bot._handle_reject(prefix, trading_ctx)
        msg = enabled_bot.send_message.call_args[0][0]
        assert "Skipped" in msg

    @pytest.mark.asyncio
    async def test_detail_pending_trade(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        pending = await trading_ctx.repo.create_pending_trade({
            "market_id": "market_3",
            "question": "Will DOGE reach $1?",
            "action": "BUY",
            "token_id": "token_3",
            "size_usd": Decimal("15.00"),
            "price": Decimal("0.20"),
            "edge_magnitude": Decimal("0.05"),
            "estimated_prob": Decimal("0.25"),
            "market_price": Decimal("0.20"),
            "kelly_fraction": Decimal("0.08"),
            "confidence": "low",
            "reasoning": "Community momentum but speculative",
            "status": "pending",
        })

        prefix = pending.id[:8]
        await enabled_bot._handle_detail(prefix, trading_ctx)
        msg = enabled_bot.send_message.call_args[0][0]
        assert "Trade Detail" in msg
        assert "DOGE" in msg
        assert "Community momentum" in msg

    @pytest.mark.asyncio
    async def test_approve_executes_trade(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        pending = await trading_ctx.repo.create_pending_trade({
            "market_id": "market_4",
            "question": "Will ADA hit $10?",
            "action": "BUY",
            "token_id": "token_4",
            "size_usd": Decimal("20.00"),
            "price": Decimal("0.30"),
            "edge_magnitude": Decimal("0.07"),
            "estimated_prob": Decimal("0.37"),
            "market_price": Decimal("0.30"),
            "kelly_fraction": Decimal("0.10"),
            "confidence": "medium",
            "reasoning": "Cardano ecosystem growth",
            "status": "pending",
        })

        prefix = pending.id[:8]

        with patch("src.core.pipeline.execute_decision", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"status": "filled", "order_id": "ord_123"}
            await enabled_bot._handle_approve(prefix, trading_ctx)

        msg = enabled_bot.send_message.call_args[0][0]
        assert "Approved" in msg


class TestDispatchRouting:
    @pytest.mark.asyncio
    async def test_dispatch_routes_correctly(self, enabled_bot: TelegramBot, trading_ctx) -> None:
        """Verify _dispatch_command routes to correct handlers."""
        enabled_bot._handle_help = AsyncMock()
        enabled_bot._handle_trades = AsyncMock()
        enabled_bot._handle_portfolio = AsyncMock()
        enabled_bot._handle_health = AsyncMock()
        enabled_bot._handle_killswitch = AsyncMock()
        enabled_bot._handle_resume = AsyncMock()
        enabled_bot._handle_approve = AsyncMock()
        enabled_bot._handle_reject = AsyncMock()
        enabled_bot._handle_detail = AsyncMock()

        await enabled_bot._dispatch_command("/help", trading_ctx)
        enabled_bot._handle_help.assert_called_once()

        await enabled_bot._dispatch_command("/trades", trading_ctx)
        enabled_bot._handle_trades.assert_called_once()

        await enabled_bot._dispatch_command("/pending", trading_ctx)
        assert enabled_bot._handle_trades.call_count == 2

        await enabled_bot._dispatch_command("/portfolio", trading_ctx)
        enabled_bot._handle_portfolio.assert_called_once()

        await enabled_bot._dispatch_command("/status", trading_ctx)
        assert enabled_bot._handle_portfolio.call_count == 2

        await enabled_bot._dispatch_command("/health", trading_ctx)
        enabled_bot._handle_health.assert_called_once()

        await enabled_bot._dispatch_command("/killswitch", trading_ctx)
        enabled_bot._handle_killswitch.assert_called_once()

        await enabled_bot._dispatch_command("/resume", trading_ctx)
        enabled_bot._handle_resume.assert_called_once()

        await enabled_bot._dispatch_command("/approve_abc12345", trading_ctx)
        enabled_bot._handle_approve.assert_called_once_with("abc12345", trading_ctx)

        await enabled_bot._dispatch_command("/skip_def67890", trading_ctx)
        enabled_bot._handle_reject.assert_called_once_with("def67890", trading_ctx)

        await enabled_bot._dispatch_command("/detail_xyz99999", trading_ctx)
        enabled_bot._handle_detail.assert_called_once_with("xyz99999", trading_ctx)


class TestStartupAlert:
    @pytest.mark.asyncio
    async def test_startup_alert_includes_new_commands(self, enabled_bot: TelegramBot) -> None:
        await enabled_bot.send_startup_alert(mode="paper", paused=False)
        msg = enabled_bot.send_message.call_args[0][0]
        assert "/trades" in msg
        assert "/portfolio" in msg
        assert "/health" in msg
        assert "/help" in msg
