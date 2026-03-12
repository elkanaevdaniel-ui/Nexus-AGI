"""Agent Zero tool — Polymarket trading via the trading service."""

import os
from typing import Any

import httpx

from python.helpers.tool import Tool, Response
from python.helpers.print_style import PrintStyle

SERVICE_URL = os.environ.get("TRADING_SERVICE_URL", "http://localhost:8000")
SERVICE_TIMEOUT = int(os.environ.get("TRADING_SERVICE_TIMEOUT", "60"))

VALID_ACTIONS = ("scan", "analyze", "trade", "positions", "risk", "portfolio")


class Trading(Tool):

    async def execute(self, **kwargs) -> Response:
        action: str = self.args.get("action", "")
        market_id: str = self.args.get("market_id", "")
        amount: str = self.args.get("amount", "")
        side: str = self.args.get("side", "")
        confirm: str = self.args.get("confirm", "false")

        if not action or action not in VALID_ACTIONS:
            return Response(
                message=f"Error: 'action' must be one of {VALID_ACTIONS}.",
                break_loop=False,
            )

        PrintStyle(font_color="#10b981", bold=True).print(
            f"{self.agent.agent_name}: Trading Service — {action}"
        )

        try:
            handler = {
                "scan": self._scan,
                "analyze": self._analyze,
                "trade": self._trade,
                "positions": self._positions,
                "risk": self._risk,
                "portfolio": self._portfolio,
            }[action]
            return await handler(
                market_id=market_id, amount=amount, side=side, confirm=confirm,
            )
        except httpx.ConnectError:
            return Response(
                message=(
                    f"Trading service is not reachable at {SERVICE_URL}. "
                    "Ensure the service is running."
                ),
                break_loop=False,
            )
        except httpx.HTTPStatusError as exc:
            return Response(
                message=f"Trading service error: {exc.response.status_code} — {exc.response.text}",
                break_loop=False,
            )

    async def _scan(self, **kw) -> Response:
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.get(f"{SERVICE_URL}/markets/scan")
            resp.raise_for_status()
            data = resp.json()

        opportunities = data.get("opportunities", data if isinstance(data, list) else [])
        if not opportunities:
            return Response(message="No trading opportunities found.", break_loop=False)

        lines: list[str] = ["**Trading Opportunities**\n"]
        for opp in opportunities:
            mid = opp.get("market_id", opp.get("id", "?"))
            title = opp.get("title", opp.get("question", ""))
            edge = opp.get("edge", opp.get("expected_edge", "N/A"))
            lines.append(f"- [{mid}] {title} | edge: {edge}")

        result = "\n".join(lines)
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _analyze(self, **kw) -> Response:
        market_id = kw.get("market_id", "")
        if not market_id:
            return Response(
                message="Error: 'market_id' is required for the analyze action.",
                break_loop=False,
            )

        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.post(
                f"{SERVICE_URL}/markets/{market_id}/analyze",
            )
            resp.raise_for_status()
            data = resp.json()

        prob = data.get("probability", "N/A")
        confidence = data.get("confidence", "N/A")
        reasoning = data.get("reasoning", data.get("summary", ""))
        market_price = data.get("market_price", "N/A")

        result = (
            f"**Market Analysis — {market_id}**\n\n"
            f"Market price: {market_price}\n"
            f"Estimated probability: {prob}\n"
            f"Confidence: {confidence}\n"
            f"Reasoning: {reasoning}"
        )
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _trade(self, **kw) -> Response:
        market_id = kw.get("market_id", "")
        amount = kw.get("amount", "")
        side = kw.get("side", "")
        confirm = kw.get("confirm", "false")

        if not market_id or not amount:
            return Response(
                message="Error: 'market_id' and 'amount' are required for trading.",
                break_loop=False,
            )

        if confirm.lower() not in ("true", "yes", "1"):
            return Response(
                message=(
                    f"Trade preview: {side or 'buy'} ${amount} on market {market_id}. "
                    "Set confirm='true' to execute this trade."
                ),
                break_loop=False,
            )

        payload: dict[str, Any] = {
            "market_id": market_id,
            "amount": float(amount),
        }
        if side:
            payload["side"] = side

        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.post(f"{SERVICE_URL}/trades", json=payload)
            resp.raise_for_status()
            data = resp.json()

        trade_id = data.get("trade_id", data.get("id", "N/A"))
        status = data.get("status", "submitted")
        return Response(
            message=f"Trade {trade_id} {status}: {side or 'buy'} ${amount} on {market_id}.",
            break_loop=False,
        )

    async def _positions(self, **kw) -> Response:
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.get(f"{SERVICE_URL}/positions")
            resp.raise_for_status()
            data = resp.json()

        positions = data.get("positions", data if isinstance(data, list) else [])
        if not positions:
            return Response(message="No open positions.", break_loop=False)

        lines: list[str] = ["**Open Positions**\n"]
        for pos in positions:
            mid = pos.get("market_id", "?")
            side = pos.get("side", "?")
            size = pos.get("size", pos.get("amount", "?"))
            pnl = pos.get("pnl", pos.get("unrealized_pnl", "N/A"))
            lines.append(f"- [{mid}] {side} ${size} | PnL: {pnl}")

        result = "\n".join(lines)
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _risk(self, **kw) -> Response:
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.get(f"{SERVICE_URL}/risk")
            resp.raise_for_status()
            data = resp.json()

        lines = ["**Risk Metrics**\n"]
        for key in ("circuit_breaker", "max_drawdown", "total_exposure", "daily_pnl"):
            lines.append(f"{key.replace('_', ' ').title()}: {data.get(key, 'N/A')}")
        result = "\n".join(lines)
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)

    async def _portfolio(self, **kw) -> Response:
        async with httpx.AsyncClient(timeout=SERVICE_TIMEOUT) as client:
            resp = await client.get(f"{SERVICE_URL}/portfolio")
            resp.raise_for_status()
            data = resp.json()

        lines = ["**Portfolio Summary**\n"]
        for key in ("balance", "total_pnl", "win_rate", "total_trades"):
            lines.append(f"{key.replace('_', ' ').title()}: {data.get(key, 'N/A')}")
        result = "\n".join(lines)
        PrintStyle(font_color="#85C1E9").print(result)
        return Response(message=result, break_loop=False)
