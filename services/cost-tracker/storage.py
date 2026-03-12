"""SQLite-backed storage with in-memory cache for the cost tracking system."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import aiosqlite

from cost_tracker.models import CostEntry, SessionCost

# ---------------------------------------------------------------------------
# SQL constants
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cost_entries (
    id            TEXT PRIMARY KEY,
    timestamp     TEXT    NOT NULL,
    provider      TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd      TEXT    NOT NULL,
    task_type     TEXT,
    session_id    TEXT,
    run_id        TEXT
);
"""

_CREATE_IDX_TIMESTAMP = """
CREATE INDEX IF NOT EXISTS idx_cost_entries_timestamp
    ON cost_entries (timestamp);
"""

_CREATE_IDX_SESSION = """
CREATE INDEX IF NOT EXISTS idx_cost_entries_session
    ON cost_entries (session_id);
"""

_CREATE_IDX_PROVIDER = """
CREATE INDEX IF NOT EXISTS idx_cost_entries_provider
    ON cost_entries (provider);
"""

_INSERT = """
INSERT OR IGNORE INTO cost_entries
    (id, timestamp, provider, model, input_tokens, output_tokens,
     cost_usd, task_type, session_id, run_id)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""

_SELECT_BY_DATE_RANGE = """
SELECT * FROM cost_entries
WHERE timestamp >= ? AND timestamp < ?
ORDER BY timestamp;
"""

_SELECT_BY_PROVIDER = """
SELECT * FROM cost_entries
WHERE provider = ?
ORDER BY timestamp;
"""

_SELECT_BY_SESSION = """
SELECT * FROM cost_entries
WHERE session_id = ?
ORDER BY timestamp;
"""

_SELECT_BY_RUN = """
SELECT * FROM cost_entries
WHERE run_id = ?
ORDER BY timestamp;
"""

_SUM_BY_DATE_RANGE = """
SELECT COALESCE(SUM(CAST(cost_usd AS REAL)), 0)
FROM cost_entries
WHERE timestamp >= ? AND timestamp < ?;
"""

_COUNT_BY_SESSION = """
SELECT COUNT(*)
FROM cost_entries
WHERE session_id = ?;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_entry(row: aiosqlite.Row) -> CostEntry:
    """Convert a database row to a CostEntry model."""
    return CostEntry(
        id=row[0],
        timestamp=datetime.fromisoformat(row[1]),
        provider=row[2],
        model=row[3],
        input_tokens=row[4],
        output_tokens=row[5],
        cost_usd=Decimal(row[6]),
        task_type=row[7],
        session_id=row[8],
        run_id=row[9],
    )


# ---------------------------------------------------------------------------
# Storage class
# ---------------------------------------------------------------------------

class CostStorage:
    """Async SQLite storage with an in-memory write-through cache.

    Usage::

        storage = CostStorage("costs.db")
        await storage.initialize()
        await storage.insert(entry)
        ...
        await storage.close()
    """

    def __init__(self, db_path: str = "costs.db") -> None:
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

        # In-memory cache keyed by entry id for fast lookups.
        self._cache: dict[str, CostEntry] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Open the database and create tables if they do not exist."""
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute(_CREATE_TABLE)
            await self._db.execute(_CREATE_IDX_TIMESTAMP)
            await self._db.execute(_CREATE_IDX_SESSION)
            await self._db.execute(_CREATE_IDX_PROVIDER)
            await self._db.commit()
            # Warm the cache with today's entries so real-time queries are
            # fast from the start.
            await self._warm_cache()
            self._initialized = True

    async def close(self) -> None:
        """Flush and close the database connection."""
        if self._db is not None:
            await self._db.close()
            self._db = None
        self._initialized = False

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def insert(self, entry: CostEntry) -> None:
        """Persist a CostEntry to SQLite and the in-memory cache."""
        await self._ensure_initialized()
        async with self._lock:
            assert self._db is not None
            await self._db.execute(
                _INSERT,
                (
                    entry.id,
                    entry.timestamp.isoformat(),
                    entry.provider,
                    entry.model,
                    entry.input_tokens,
                    entry.output_tokens,
                    str(entry.cost_usd),
                    entry.task_type,
                    entry.session_id,
                    entry.run_id,
                ),
            )
            await self._db.commit()
            self._cache[entry.id] = entry

    # ------------------------------------------------------------------
    # Read — aggregation helpers (use cache first, fall back to DB)
    # ------------------------------------------------------------------

    async def sum_cost_in_range(
        self,
        start: datetime,
        end: datetime,
    ) -> Decimal:
        """Return total cost_usd for entries whose timestamp is in [start, end)."""
        # Fast path: sum from cache.
        total = Decimal("0")
        for entry in self._cache.values():
            if start <= entry.timestamp < end:
                total += entry.cost_usd
        return total

    async def sum_cost_by_session(self, session_id: str) -> Decimal:
        """Return total cost_usd for a given session from the cache."""
        total = Decimal("0")
        for entry in self._cache.values():
            if entry.session_id == session_id:
                total += entry.cost_usd
        return total

    async def sum_cost_by_run(self, run_id: str) -> Decimal:
        """Return total cost_usd for a given run from the cache."""
        total = Decimal("0")
        for entry in self._cache.values():
            if entry.run_id == run_id:
                total += entry.cost_usd
        return total

    async def count_by_session(self, session_id: str) -> int:
        """Return the number of calls recorded for *session_id*."""
        return sum(
            1
            for entry in self._cache.values()
            if entry.session_id == session_id
        )

    # ------------------------------------------------------------------
    # Read — detailed queries
    # ------------------------------------------------------------------

    async def query_by_date_range(
        self,
        start: datetime,
        end: datetime,
    ) -> list[CostEntry]:
        """Return all entries in [start, end) ordered by timestamp."""
        return sorted(
            (
                e
                for e in self._cache.values()
                if start <= e.timestamp < end
            ),
            key=lambda e: e.timestamp,
        )

    async def query_by_provider(self, provider: str) -> list[CostEntry]:
        """Return all cached entries for a given provider."""
        return sorted(
            (e for e in self._cache.values() if e.provider == provider),
            key=lambda e: e.timestamp,
        )

    async def query_by_session(self, session_id: str) -> list[CostEntry]:
        """Return all cached entries for a given session."""
        return sorted(
            (e for e in self._cache.values() if e.session_id == session_id),
            key=lambda e: e.timestamp,
        )

    async def get_session_cost(self, session_id: str) -> SessionCost:
        """Build a SessionCost aggregate for the given session."""
        entries = await self.query_by_session(session_id)
        if not entries:
            return SessionCost(session_id=session_id)
        return SessionCost(
            session_id=session_id,
            total_cost=sum((e.cost_usd for e in entries), Decimal("0")),
            call_count=len(entries),
            started_at=entries[0].timestamp,
            last_call_at=entries[-1].timestamp,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _ensure_initialized(self) -> None:
        if not self._initialized:
            await self.initialize()

    async def _warm_cache(self) -> None:
        """Load the current month's entries into the in-memory cache.

        This keeps cache memory bounded while still allowing fast daily and
        monthly aggregation without hitting SQLite.
        """
        assert self._db is not None
        now = datetime.now(timezone.utc)
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0,
        )
        async with self._db.execute(
            _SELECT_BY_DATE_RANGE,
            (month_start.isoformat(), now.isoformat()),
        ) as cursor:
            async for row in cursor:
                entry = _row_to_entry(row)
                self._cache[entry.id] = entry
