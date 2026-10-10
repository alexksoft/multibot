from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

import aiosqlite

logger = logging.getLogger(__name__)


class DialogState:
    __slots__ = ("bot_name", "user_id", "flow_id", "step_id", "collected", "updated_at")

    def __init__(self, bot_name: str, user_id: int, flow_id: str = "",
                 step_id: str = "", collected: dict | None = None):
        self.bot_name = bot_name
        self.user_id = user_id
        self.flow_id = flow_id
        self.step_id = step_id
        self.collected: dict = collected or {}
        self.updated_at: datetime = datetime.now(timezone.utc)


@runtime_checkable
class Storage(Protocol):
    async def get_state(self, bot_name: str, user_id: int) -> DialogState | None: ...
    async def save_state(self, state: DialogState) -> None: ...
    async def clear_state(self, bot_name: str, user_id: int) -> None: ...
    async def save_result(self, result: dict) -> None: ...
    async def incr_counter(self, bot_name: str, metric: str) -> None: ...
    async def stats(self, bot_name: str) -> dict: ...


class InMemoryStorage:
    def __init__(self):
        self._states: dict[tuple, DialogState] = {}
        self._results: list[dict] = []
        self._counters: dict[tuple, int] = {}

    async def get_state(self, bot_name: str, user_id: int) -> DialogState | None:
        return self._states.get((bot_name, user_id))

    async def save_state(self, state: DialogState) -> None:
        self._states[(state.bot_name, state.user_id)] = state

    async def clear_state(self, bot_name: str, user_id: int) -> None:
        self._states.pop((bot_name, user_id), None)

    async def save_result(self, result: dict) -> None:
        self._results.append(result)

    async def incr_counter(self, bot_name: str, metric: str) -> None:
        key = (bot_name, metric)
        self._counters[key] = self._counters.get(key, 0) + 1

    async def stats(self, bot_name: str) -> dict:
        return {
            k[1]: v for k, v in self._counters.items() if k[0] == bot_name
        }


class SqliteStorage:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def init(self) -> None:
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS dialog_state (
                bot_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                flow_id TEXT DEFAULT '',
                step_id TEXT DEFAULT '',
                collected TEXT DEFAULT '{}',
                updated_at TEXT NOT NULL,
                PRIMARY KEY (bot_name, user_id)
            );
            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY,
                bot_name TEXT NOT NULL,
                data TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS counters (
                bot_name TEXT NOT NULL,
                metric TEXT NOT NULL,
                value INTEGER DEFAULT 0,
                PRIMARY KEY (bot_name, metric)
            );
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                duration_min INTEGER NOT NULL,
                is_demo INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS masters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                name TEXT NOT NULL,
                working_days TEXT NOT NULL,
                work_start TEXT NOT NULL,
                work_end TEXT NOT NULL,
                service_ids TEXT DEFAULT '[]',
                is_demo INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                service_id INTEGER NOT NULL,
                master_id INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                status TEXT DEFAULT 'new',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_name TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                UNIQUE(bot_name, user_id)
            );
        """)
        await self._db.commit()

    async def close(self) -> None:
        if self._db:
            await self._db.close()

    async def get_state(self, bot_name: str, user_id: int) -> DialogState | None:
        async with self._db.execute(
            "SELECT flow_id, step_id, collected FROM dialog_state WHERE bot_name=? AND user_id=?",
            (bot_name, user_id)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        state = DialogState(bot_name, user_id, row[0], row[1], json.loads(row[2]))
        return state

    async def save_state(self, state: DialogState) -> None:
        await self._db.execute(
            """INSERT INTO dialog_state (bot_name, user_id, flow_id, step_id, collected, updated_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(bot_name, user_id) DO UPDATE SET
                 flow_id=excluded.flow_id, step_id=excluded.step_id,
                 collected=excluded.collected, updated_at=excluded.updated_at""",
            (state.bot_name, state.user_id, state.flow_id, state.step_id,
             json.dumps(state.collected, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat())
        )
        await self._db.commit()

    async def clear_state(self, bot_name: str, user_id: int) -> None:
        await self._db.execute(
            "DELETE FROM dialog_state WHERE bot_name=? AND user_id=?",
            (bot_name, user_id)
        )
        await self._db.commit()

    async def save_result(self, result: dict) -> None:
        await self._db.execute(
            "INSERT OR REPLACE INTO results (id, bot_name, data, created_at) VALUES (?,?,?,?)",
            (result.get("id", ""), result.get("bot_name", ""),
             json.dumps(result, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat())
        )
        await self._db.commit()

    async def incr_counter(self, bot_name: str, metric: str) -> None:
        await self._db.execute(
            """INSERT INTO counters (bot_name, metric, value) VALUES (?,?,1)
               ON CONFLICT(bot_name, metric) DO UPDATE SET value=value+1""",
            (bot_name, metric)
        )
        await self._db.commit()

    async def stats(self, bot_name: str) -> dict:
        async with self._db.execute(
            "SELECT metric, value FROM counters WHERE bot_name=?", (bot_name,)
        ) as cur:
            rows = await cur.fetchall()
        return {r[0]: r[1] for r in rows}
