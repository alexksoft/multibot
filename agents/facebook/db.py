"""SQLite storage for Facebook agent — groups and scraped posts."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "facebook_agent.db"


@contextmanager
def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS fb_groups (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                url       TEXT    NOT NULL UNIQUE,
                name      TEXT    NOT NULL DEFAULT '',
                active    INTEGER NOT NULL DEFAULT 1,
                added_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS fb_posts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id     INTEGER NOT NULL REFERENCES fb_groups(id),
                post_text    TEXT,
                image_url    TEXT,
                post_url     TEXT,
                scraped_at   TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)


# ── Groups ────────────────────────────────────────────────────────────────────

def add_group(url: str, name: str = "") -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO fb_groups (url, name) VALUES (?, ?)", (url, name)
        )
        if cur.lastrowid:
            return cur.lastrowid
        row = con.execute("SELECT id FROM fb_groups WHERE url=?", (url,)).fetchone()
        return row["id"]


def remove_group(group_id: int) -> None:
    with _conn() as con:
        con.execute("DELETE FROM fb_groups WHERE id=?", (group_id,))


def toggle_group(group_id: int) -> None:
    with _conn() as con:
        con.execute("UPDATE fb_groups SET active = 1 - active WHERE id=?", (group_id,))


def list_groups() -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT * FROM fb_groups ORDER BY added_at DESC").fetchall()
        return [dict(r) for r in rows]


# ── Posts ─────────────────────────────────────────────────────────────────────

def save_posts(group_id: int, posts: list[dict]) -> None:
    with _conn() as con:
        for p in posts:
            con.execute(
                "INSERT INTO fb_posts (group_id, post_text, image_url, post_url) VALUES (?,?,?,?)",
                (group_id, p.get("text"), p.get("image_url"), p.get("post_url")),
            )


def list_posts(group_id: int | None = None, limit: int = 50) -> list[dict]:
    with _conn() as con:
        if group_id:
            rows = con.execute(
                "SELECT p.*, g.name as group_name, g.url as group_url "
                "FROM fb_posts p JOIN fb_groups g ON p.group_id=g.id "
                "WHERE p.group_id=? ORDER BY p.scraped_at DESC LIMIT ?",
                (group_id, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT p.*, g.name as group_name, g.url as group_url "
                "FROM fb_posts p JOIN fb_groups g ON p.group_id=g.id "
                "ORDER BY p.scraped_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
