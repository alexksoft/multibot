"""
Facebook scraper local API — runs on Windows laptop.
The Oracle server calls this to scrape Facebook groups using your local browser session.

Start: python agents/facebook/local_api.py
Port: 7771
"""
from __future__ import annotations
import asyncio
import logging
import os
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn


class GroupIn(BaseModel):
    id: int
    url: str
    name: str = ""
    active: bool = True

from agents.facebook.scraper import scrape_group
from agents.facebook.db import init_db, save_posts, list_groups, list_posts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FB Scraper Local API", docs_url="/docs")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "fb-scraper-local"}


@app.post("/setup-profile")
async def setup_profile():
    """One-time: create persistent Chrome profile from fb_session.json."""
    from agents.facebook.scraper import setup_persistent_profile
    ok = await setup_persistent_profile()
    return {"status": "ok" if ok else "failed",
            "message": "Profile created" if ok else "Check fb_session.json and try again"}


@app.post("/scrape/all")
async def scrape_all(groups: list[GroupIn] | None = None):
    """Scrape all active groups. Groups can be passed in body or read from local DB."""
    group_list = [g.model_dump() for g in groups] if groups else [g for g in list_groups() if g["active"]]
    results = []
    for group in group_list:
        try:
            posts = await scrape_group(group["url"])
            if posts:
                save_posts(group["id"], posts)
            results.append({"group_id": group["id"], "name": group.get("name", ""), "posts": len(posts)})
            logger.info("Group %s: %d posts", group.get("name"), len(posts))
        except Exception as e:
            results.append({"group_id": group["id"], "name": group.get("name", ""), "error": str(e)})
            logger.error("Group %s error: %s", group.get("name"), e)
    return {"status": "ok", "results": results}


@app.get("/posts")
async def get_posts(limit: int = 50):
    """Return recently scraped posts."""
    return list_posts(limit=limit)


if __name__ == "__main__":
    init_db()
    # Auto-convert Cookie-Editor format if needed
    import json as _json
    sf = Path(__file__).parent / "fb_session.json"
    if sf.exists():
        raw = _json.loads(sf.read_text(encoding="utf-8"))
        if isinstance(raw, list):  # Cookie-Editor format
            SAME_SITE_MAP = {"lax": "Lax", "strict": "Strict", "no_restriction": "None", None: "None"}
            cookies = [{"domain": c["domain"], "name": c["name"], "value": c["value"],
                        "path": c.get("path", "/"), "secure": c.get("secure", True),
                        "httpOnly": c.get("httpOnly", False),
                        "sameSite": SAME_SITE_MAP.get(c.get("sameSite"), "None")} for c in raw]
            sf.write_text(_json.dumps({"cookies": cookies, "origins": []}, indent=2), encoding="utf-8")
            logger.info("Auto-converted %d cookies to Playwright format", len(cookies))
    port = int(os.getenv("FB_SCRAPER_PORT", "7771"))
    logger.info("Starting FB scraper local API on port %d", port)
    uvicorn.run(app, host="0.0.0.0", port=port)
