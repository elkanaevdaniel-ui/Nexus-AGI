"""Unified cost tracker — the single entry-point for all cost/budget operations.

Replaces:
  - ai-projects budget_tracker.py  (daily/monthly budget limits)
  - ai-projects cost_tracker.py    (per-call cost logging)
  - polymarket-agent CostLog model (DB-backed cost tracking with session limits)
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from cost_tracker.models import (
    BudgetConfig,
    BudgetLevel,
    BudgetStatus,
    CostEntry,
    SessionCost,
)
from cost_tracker.storage import CostStorage


def _pct(spend: Decimal, limit: Decimal) -> Decimal:
    """Return spend as a percentage of limit, capped display at 999.99."""
    if limit <= 0:
        return Decimal("0")
    return (spend / limit * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class CostTracker:
    """Async, thread-safe, unified cost tracker.

    Typical lifecycle::

        tracker = CostTracker()          # reads env vars automatically
        await tracker.initialize()       # opens DB, warms cache
        ...
        await tracker.record_call(...)   # log each LLM call
        status = await tracker.is_budget_exceeded()
        ...
        await tracker.close()

    Or use as an async context manager::

        async with CostTracker() as tracker:
            await tracker.record_call(...)
    """

    def __init__(
        self,
        config: Optional[BudgetConfig] = None,
        storage: Optional[CostStorage] = None,
    ) -> None:
        self._config = config or BudgetConfig()
        self._storage = storage or CostStorage(self._config.cost_db_path)
        self._lock = asyncio.Lock()
        # Default run_id for per-run tracking; callers can override per call.
        self._current_run_id: str = uuid.uuid4().hex

    # ------------------------------------------------------------------
    # Async context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> CostTracker:
        await self.initialize()
        return self

    async def __aexit__(
        self,
        exc_type: object,
        exc_val: object,
        exc_tb: object,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialise the underlying storage (creates tables on first use)."""
        await self._storage.initialize()

    async def close(self) -> None:
        """Close the storage connection."""
        await self._storage.close()

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @property
    def config(self) -> BudgetConfig:
        """Return the active budget configuration (read-only)."""
        return self._config

    @property
    def current_run_id(self) -> str:
        """Return the current run ID."""
        return self._current_run_id

    def new_run(self) -> str:
        """Start a new run and return its ID."""
        self._current_run_id = uuid.uuid4().hex
        return self._current_run_id

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    async def record_call(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal | str,
        task_type: Optional[str] = None,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> CostEntry:
        """Record a single LLM call and persist it.

        Parameters
        ----------
        provider:
            LLM provider (e.g. ``"openai"``, ``"anthropic"``).
        model:
            Model identifier (e.g. ``"gpt-4o"``).
        input_tokens:
            Number of input / prompt tokens.
        output_tokens:
            Number of output / completion tokens.
        cost_usd:
            Total cost in USD.  Accepts ``Decimal`` or a string that can be
            converted to ``Decimal`` — *never* pass a ``float``.
        task_type:
            Optional label for the kind of work.
        session_id:
            Optional session identifier for session-level tracking.
        run_id:
            Optional run identifier.  If ``None``, the tracker's
            ``current_run_id`` is used.

        Returns
        -------
        CostEntry
            The persisted entry (including generated ``id`` and ``timestamp``).
        """
        if isinstance(cost_usd, str):
            cost_usd = Decimal(cost_usd)

        entry = CostEntry(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            task_type=task_type,
            session_id=session_id,
            run_id=run_id or self._current_run_id,
        )

        async with self._lock:
            await self._storage.insert(entry)

        return entry

    # ------------------------------------------------------------------
    # Real-time spend queries
    # ------------------------------------------------------------------

    async def get_daily_spend(self) -> Decimal:
        """Return total spend for the current UTC day."""
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        return await self._storage.sum_cost_in_range(day_start, day_end)

    async def get_monthly_spend(self) -> Decimal:
        """Return total spend for the current UTC month."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        # Use a far-future sentinel for the month's upper bound so we
        # capture every entry up to *now*.
        return await self._storage.sum_cost_in_range(month_start, now)

    async def get_session_spend(self, session_id: str) -> Decimal:
        """Return total spend for the given session."""
        return await self._storage.sum_cost_by_session(session_id)

    async def get_run_spend(self, run_id: Optional[str] = None) -> Decimal:
        """Return total spend for the given (or current) run."""
        return await self._storage.sum_cost_by_run(
            run_id or self._current_run_id,
        )

    async def get_session_call_count(self, session_id: str) -> int:
        """Return the number of LLM calls recorded for a session."""
        return await self._storage.count_by_session(session_id)

    async def get_session_cost(self, session_id: str) -> SessionCost:
        """Return a full ``SessionCost`` aggregate."""
        return await self._storage.get_session_cost(session_id)

    # ------------------------------------------------------------------
    # Budget checks
    # ------------------------------------------------------------------

    async def is_budget_exceeded(
        self,
        *,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> BudgetStatus:
        """Check all budget levels and return a ``BudgetStatus`` snapshot.

        Parameters
        ----------
        session_id:
            If provided, session-level call count is checked against the
            configured ``session_call_limit``.
        run_id:
            If provided (or falls back to current run), per-run spend is
            checked against ``per_run_budget_usd``.
        """
        daily_spend = await self.get_daily_spend()
        monthly_spend = await self.get_monthly_spend()
        effective_run_id = run_id or self._current_run_id
        run_spend = await self.get_run_spend(effective_run_id)

        session_calls = 0
        if session_id is not None:
            session_calls = await self.get_session_call_count(session_id)

        cfg = self._config

        return BudgetStatus(
            daily_spend=daily_spend,
            daily_limit=cfg.daily_budget_usd,
            daily_pct=_pct(daily_spend, cfg.daily_budget_usd),
            daily_exceeded=daily_spend >= cfg.daily_budget_usd,

            monthly_spend=monthly_spend,
            monthly_limit=cfg.monthly_budget_usd,
            monthly_pct=_pct(monthly_spend, cfg.monthly_budget_usd),
            monthly_exceeded=monthly_spend >= cfg.monthly_budget_usd,

            per_run_spend=run_spend,
            per_run_limit=cfg.per_run_budget_usd,
            per_run_pct=_pct(run_spend, cfg.per_run_budget_usd),
            per_run_exceeded=run_spend >= cfg.per_run_budget_usd,

            session_call_count=session_calls,
            session_call_limit=cfg.session_call_limit,
            session_exceeded=session_calls >= cfg.session_call_limit,
        )

    async def check_and_raise(
        self,
        *,
        session_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> BudgetStatus:
        """Like ``is_budget_exceeded`` but raises if any limit is hit.

        Returns
        -------
        BudgetStatus
            The snapshot when no budget is exceeded.

        Raises
        ------
        BudgetExceededError
            When at least one budget level is exceeded.
        """
        status = await self.is_budget_exceeded(
            session_id=session_id,
            run_id=run_id,
        )
        if status.is_exceeded:
            raise BudgetExceededError(status)
        return status

    # ------------------------------------------------------------------
    # Query pass-throughs (convenience wrappers)
    # ------------------------------------------------------------------

    async def query_by_date_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[CostEntry]:
        """Return detailed entries in [start, end)."""
        return await self._storage.query_by_date_range(start, end)

    async def query_by_provider(self, provider: str) -> list[CostEntry]:
        """Return all entries for a provider."""
        return await self._storage.query_by_provider(provider)

    async def query_by_session(self, session_id: str) -> list[CostEntry]:
        """Return all entries for a session."""
        return await self._storage.query_by_session(session_id)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class BudgetExceededError(Exception):
    """Raised when a budget limit has been reached."""

    def __init__(self, status: BudgetStatus) -> None:
        self.status = status
        levels = ", ".join(lvl.value for lvl in status.exceeded_levels)
        super().__init__(f"Budget exceeded at level(s): {levels}")
