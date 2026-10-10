from __future__ import annotations
import json
import logging
import random
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

import aiosqlite

logger = logging.getLogger(__name__)

DEMO_NAMES = ["Олена", "Марія", "Анна", "Катерина", "Наталія",
              "Ірина", "Тетяна", "Юлія", "Оксана", "Людмила"]
DEMO_SERVICES_BEAUTY = [
    ("Стрижка жіноча", 450.0, 60),
    ("Фарбування", 900.0, 120),
    ("Манікюр", 350.0, 60),
    ("Педикюр", 400.0, 75),
    ("Ламінування волосся", 700.0, 90),
]


class DemoSeeder:
    def __init__(self, db: aiosqlite.Connection, bot_name: str, demo_masters: int):
        self._db = db
        self._bot_name = bot_name
        self._n = demo_masters

    async def seed_if_empty(self) -> None:
        async with self._db.execute(
            "SELECT COUNT(*) FROM masters WHERE bot_name=?", (self._bot_name,)
        ) as cur:
            count = (await cur.fetchone())[0]
        if count > 0:
            return

        service_ids = []
        for name, price, duration in DEMO_SERVICES_BEAUTY:
            async with self._db.execute(
                "INSERT INTO services (bot_name, name, price, duration_min, is_demo) VALUES (?,?,?,?,1)",
                (self._bot_name, name, price, duration)
            ) as cur:
                service_ids.append(cur.lastrowid)

        names = random.sample(DEMO_NAMES, min(self._n, len(DEMO_NAMES)))
        for name in names:
            await self._db.execute(
                "INSERT INTO masters (bot_name, name, working_days, work_start, work_end, service_ids, is_demo) VALUES (?,?,?,?,?,?,1)",
                (self._bot_name, name, json.dumps([1, 2, 3, 4, 5]),
                 "10:00", "20:00", json.dumps(service_ids))
            )
        await self._db.commit()
        logger.info(f"[booking] Seeded {len(names)} demo masters for '{self._bot_name}'")


class SlotService:
    def __init__(self, db: aiosqlite.Connection, bot_name: str):
        self._db = db
        self._bot_name = bot_name

    async def get_services(self) -> list[dict]:
        async with self._db.execute(
            "SELECT id, name, price, duration_min FROM services WHERE bot_name=?",
            (self._bot_name,)
        ) as cur:
            rows = await cur.fetchall()
        return [{"id": r[0], "name": r[1], "price": r[2], "duration_min": r[3]} for r in rows]

    async def get_masters(self, service_id: int | None = None) -> list[dict]:
        async with self._db.execute(
            "SELECT id, name, working_days, work_start, work_end, service_ids FROM masters WHERE bot_name=?",
            (self._bot_name,)
        ) as cur:
            rows = await cur.fetchall()
        masters = []
        for r in rows:
            sids = json.loads(r[5])
            if service_id is None or service_id in sids:
                masters.append({
                    "id": r[0], "name": r[1],
                    "working_days": json.loads(r[2]),
                    "work_start": r[3], "work_end": r[4],
                })
        return masters

    async def free_slots(self, master_id: int, for_date: date, duration_min: int) -> list[str]:
        async with self._db.execute(
            "SELECT id, name, work_start, work_end FROM masters WHERE id=?", (master_id,)
        ) as cur:
            master = await cur.fetchone()
        if not master:
            return []

        # Check working day
        async with self._db.execute(
            "SELECT working_days FROM masters WHERE id=?", (master_id,)
        ) as cur:
            wd_row = await cur.fetchone()
        working_days = json.loads(wd_row[0]) if wd_row else list(range(7))
        if for_date.weekday() not in working_days:
            return []

        start_h, start_m = map(int, master[2].split(":"))
        end_h, end_m = map(int, master[3].split(":"))
        work_start = datetime.combine(for_date, time(start_h, start_m))
        work_end = datetime.combine(for_date, time(end_h, end_m))

        # Get booked slots
        day_start = datetime.combine(for_date, time(0, 0)).isoformat()
        day_end = datetime.combine(for_date, time(23, 59)).isoformat()
        async with self._db.execute(
            """SELECT start_time FROM appointments
               WHERE master_id=? AND start_time>=? AND start_time<=? AND status!='cancelled'""",
            (master_id, day_start, day_end)
        ) as cur:
            booked = {row[0][:16] for row in await cur.fetchall()}

        slots = []
        current = work_start
        while current + timedelta(minutes=duration_min) <= work_end:
            slot_str = current.strftime("%H:%M")
            if current.isoformat()[:16] not in booked:
                slots.append(slot_str)
            current += timedelta(minutes=duration_min)
        return slots

    async def book(self, user_id: int, service_id: int, master_id: int,
                   start: datetime) -> int:
        async with self._db.execute(
            """INSERT INTO appointments (bot_name, user_id, service_id, master_id, start_time, status, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (self._bot_name, user_id, service_id, master_id,
             start.isoformat(), "new", datetime.now(timezone.utc).isoformat())
        ) as cur:
            appt_id = cur.lastrowid
        await self._db.commit()
        return appt_id

    async def cancel(self, appointment_id: int, user_id: int) -> bool:
        await self._db.execute(
            "UPDATE appointments SET status='cancelled' WHERE id=? AND user_id=?",
            (appointment_id, user_id)
        )
        await self._db.commit()
        return True

    async def user_appointments(self, user_id: int) -> list[dict]:
        now = datetime.now(timezone.utc).isoformat()
        async with self._db.execute(
            """SELECT a.id, s.name, m.name, a.start_time, a.status, s.price
               FROM appointments a
               JOIN services s ON s.id=a.service_id
               JOIN masters m ON m.id=a.master_id
               WHERE a.user_id=? AND a.bot_name=? AND a.start_time>=? AND a.status!='cancelled'
               ORDER BY a.start_time""",
            (user_id, self._bot_name, now)
        ) as cur:
            rows = await cur.fetchall()
        return [{"id": r[0], "service": r[1], "master": r[2],
                 "start": r[3], "status": r[4], "price": r[5]} for r in rows]

    async def save_client(self, user_id: int, name: str, phone: str) -> None:
        await self._db.execute(
            """INSERT INTO clients (bot_name, user_id, name, phone)
               VALUES (?,?,?,?)
               ON CONFLICT(bot_name, user_id) DO UPDATE SET name=excluded.name, phone=excluded.phone""",
            (self._bot_name, user_id, name, phone)
        )
        await self._db.commit()
