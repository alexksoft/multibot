"""
Admin panel for Practical AI Assistants.
Start: python -m admin
Only runs when ADMIN_ENABLED=true.
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from starlette.middleware.sessions import SessionMiddleware

from admin.auth import hash_password, verify_login
from src.multibot.config.loader import load_configs
from src.multibot.config.sections import BotConfig
from src.multibot.config.settings import settings

BOTS_DIR = Path(settings.bots_dir)
# Absolute path — never depends on working directory
SCRAPER_CONFIG = Path(__file__).parent.parent / "scraper" / "config.yaml"
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["enumerate"] = enumerate

app = FastAPI(title="Multibot Admin", docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=settings.admin_session_secret, max_age=3600)


def require_session(request: Request):
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=302, headers={"Location": "/login"})


@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": ""})


@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    if verify_login(username, password, settings.admin_username, settings.admin_password_hash):
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Невірний логін або пароль"})


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request, _=Depends(require_session)):
    configs = load_configs(settings.bots_dir)
    bots = []
    for cfg in configs:
        bots.append({
            "name": cfg.name,
            "role": cfg.assistant_profile.assistant_role,
            "industry": cfg.assistant_profile.industry,
            "language": cfg.assistant_profile.language,
            "flows": [f.title for f in cfg.conversation_flows.flows],
            "capabilities": [c.name for c in cfg.capabilities.enabled],
            "sheets_enabled": cfg.knowledge.sheets.enabled,
            "has_token": bool(os.environ.get(cfg.token_env, "")),
            "booking_enabled": cfg.booking.enabled,
        })
    return templates.TemplateResponse("index.html", {"request": request, "bots": bots})


@app.get("/bot/{name}", response_class=HTMLResponse)
async def bot_detail(name: str, request: Request, _=Depends(require_session)):
    configs = load_configs(settings.bots_dir)
    cfg = next((c for c in configs if c.name == name), None)
    if not cfg:
        raise HTTPException(404, "Bot not found")
    return templates.TemplateResponse("bot_detail.html", {"request": request, "cfg": cfg})


@app.get("/new", response_class=HTMLResponse)
async def new_bot_get(request: Request, _=Depends(require_session)):
    return templates.TemplateResponse("new_bot.html", {"request": request, "error": "", "yaml_result": ""})


@app.post("/new", response_class=HTMLResponse)
async def new_bot_post(
    request: Request,
    niche: str = Form(...),
    target_user: str = Form(...),
    language: str = Form("uk"),
    tone: str = Form("friendly"),
    needs_sheets: str = Form("no"),
    _=Depends(require_session),
):
    from src.multibot.core.providers.kiro_gateway import KiroGatewayProvider
    from src.multibot.config.sections import BotConfig
    import yaml

    provider = KiroGatewayProvider(settings.kiro_gateway_url, settings.kiro_gateway_api_key)
    prompt = f"""Generate a complete 6-section YAML bot config for the following niche.
Niche/role: {niche}
Target user: {target_user}
Language: {language}
Tone: {tone}
Needs Google Sheets matrix: {needs_sheets}

Return ONLY valid YAML with these top-level keys:
name, token_env, assistant_profile, conversation_flows, capabilities, knowledge, ai_policy, integrations, booking

Rules:
- name must match [a-z0-9_]+
- token_env must be NAME_BOT_TOKEN
- assistant_profile.disclaimer must be neutral (no real company)
- booking.enabled: false
- all sinks enabled: false
- language: {language}
"""
    yaml_text = ""
    error = ""
    for attempt in range(3):
        result = await provider.complete(
            system="You are a bot config generator. Return only valid YAML, no markdown fences.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
        )
        yaml_text = result.content.strip().removeprefix("```yaml").removeprefix("```").removesuffix("```").strip()
        try:
            raw = yaml.safe_load(yaml_text)
            cfg = BotConfig.model_validate(raw)
            # Sanitize name
            safe_name = re.sub(r"[^a-z0-9_]", "_", cfg.name.lower())
            target_path = BOTS_DIR / f"{safe_name}.yaml"
            if target_path.exists():
                error = f"File {target_path} already exists. Rename or delete it first."
                break
            # Ensure path is inside bots/
            if not str(target_path.resolve()).startswith(str(BOTS_DIR.resolve())):
                error = "Invalid path"
                break
            target_path.write_text(yaml_text, encoding="utf-8")
            instruction = (
                f"✅ Bot '{safe_name}' created!\n\n"
                f"1. Create bot in @BotFather → copy token\n"
                f"2. Add to .env: {cfg.token_env}=<your_token>\n"
                + (f"3. Add {cfg.knowledge.sheets.sheet_id_env}=<sheet_id> to .env\n" if cfg.knowledge.sheets.enabled else "")
                + "4. Restart the bot process: python main.py"
            )
            return templates.TemplateResponse("new_bot.html", {
                "request": request, "error": "", "yaml_result": yaml_text, "instruction": instruction
            })
        except Exception as e:
            error = f"Validation failed (attempt {attempt+1}): {e}"
            prompt += f"\n\nPrevious attempt failed validation: {e}\nFix and return corrected YAML."

    return templates.TemplateResponse("new_bot.html", {
        "request": request, "error": error, "yaml_result": yaml_text, "instruction": ""
    })


# ── Scraper routes ────────────────────────────────────────────────────────────

def _load_scraper_config() -> dict:
    if SCRAPER_CONFIG.exists():
        import yaml
        return yaml.safe_load(SCRAPER_CONFIG.read_text(encoding="utf-8")) or {"bots": {}}
    return {"bots": {}}


def _save_scraper_config(cfg: dict) -> None:
    import yaml
    SCRAPER_CONFIG.write_text(yaml.dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


@app.get("/scraper", response_class=HTMLResponse)
async def scraper_page(request: Request, _=Depends(require_session)):
    configs = load_configs(settings.bots_dir)
    scraper_cfg = _load_scraper_config()
    bots_data = []
    for cfg in configs:
        bot_scraper = scraper_cfg.get("bots", {}).get(cfg.name, {"worksheet": "", "sources": []})
        sheet_id = os.environ.get(cfg.knowledge.sheets.sheet_id_env, "") if cfg.knowledge.sheets.enabled else ""
        bots_data.append({
            "name": cfg.name,
            "role": cfg.assistant_profile.assistant_role,
            "industry": cfg.assistant_profile.industry,
            "sheets_enabled": cfg.knowledge.sheets.enabled,
            "sheet_id": sheet_id,
            "worksheet": bot_scraper.get("worksheet", ""),
            "sources": bot_scraper.get("sources", []),
        })
    return templates.TemplateResponse("scraper.html", {"request": request, "bots": bots_data, "msg": ""})


@app.post("/scraper/check-robots", response_class=HTMLResponse)
async def check_robots(request: Request, url: str = Form(...), _=Depends(require_session)):
    from scraper.http_scraper import check_robots_async
    result = await check_robots_async(url)
    return templates.TemplateResponse("scraper_robots_result.html", {"request": request, "result": result, "url": url})


@app.post("/scraper/discover", response_class=HTMLResponse)
async def discover_sources(
    request: Request,
    bot_name: str = Form(...),
    industry: str = Form(...),
    _=Depends(require_session),
):
    """Use AI to find Ukrainian shops for the given industry, check robots.txt, add allowed ones."""
    from src.multibot.core.providers.kiro_gateway import KiroGatewayProvider
    from scraper.http_scraper import check_robots_async
    import json as _json

    provider = KiroGatewayProvider(settings.kiro_gateway_url, settings.kiro_gateway_api_key)
    prompt = (
        f"List 10 real Ukrainian online shops or price aggregators for '{industry}' "
        f"that have product listings with prices. "
        f"Return ONLY a JSON array, no markdown, no explanation. Format:\n"
        f'[{{"name": "Shop Name", "base_url": "https://example.ua", '
        f'"category_url": "https://example.ua/category/"}}]'
    )
    result = await provider.complete(
        system="You are a helpful assistant. Return only valid JSON, no markdown.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
    )

    discovered = []
    errors = []
    try:
        text = result.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        shops = _json.loads(text)
    except Exception as e:
        errors.append(f"AI parse error: {e}")
        shops = []

    cfg = _load_scraper_config()
    bot_cfg = cfg.setdefault("bots", {}).setdefault(bot_name, {"worksheet": f"{bot_name}_prices", "sources": []})
    existing_urls = {s["base_url"] for s in bot_cfg.get("sources", [])}

    for shop in shops:
        base_url = shop.get("base_url", "").rstrip("/")
        name = shop.get("name", base_url)
        cat_url = shop.get("category_url", base_url)
        if not base_url:
            continue
        robots = await check_robots_async(cat_url)
        status = "allowed" if robots["allowed"] else "blocked"
        discovered.append({"name": name, "base_url": base_url, "cat_url": cat_url,
                           "allowed": robots["allowed"], "delay": robots["delay"], "status": status})
        if robots["allowed"] and base_url not in existing_urls:
            bot_cfg.setdefault("sources", []).append({
                "name": name,
                "base_url": base_url,
                "categories": [{"name": industry, "url": cat_url}]
            })
            existing_urls.add(base_url)

    _save_scraper_config(cfg)
    return templates.TemplateResponse("scraper_discover.html", {
        "request": request, "bot_name": bot_name, "industry": industry,
        "discovered": discovered, "errors": errors,
    })


@app.post("/scraper/add-source")
async def add_source(
    request: Request,
    bot_name: str = Form(...),
    source_name: str = Form(...),
    base_url: str = Form(...),
    _=Depends(require_session),
):
    cfg = _load_scraper_config()
    bot_cfg = cfg.setdefault("bots", {}).setdefault(bot_name, {"worksheet": "", "sources": []})
    # Avoid duplicates
    existing = [s["base_url"] for s in bot_cfg.get("sources", [])]
    if base_url not in existing:
        bot_cfg.setdefault("sources", []).append({"name": source_name, "base_url": base_url, "categories": []})
        _save_scraper_config(cfg)
    return RedirectResponse(f"/scraper#{bot_name}", status_code=302)


@app.post("/scraper/add-category")
async def add_category(
    request: Request,
    bot_name: str = Form(...),
    source_index: int = Form(...),
    cat_name: str = Form(...),
    cat_url: str = Form(...),
    _=Depends(require_session),
):
    cfg = _load_scraper_config()
    sources = cfg.get("bots", {}).get(bot_name, {}).get("sources", [])
    if 0 <= source_index < len(sources):
        sources[source_index].setdefault("categories", []).append({"name": cat_name, "url": cat_url})
        _save_scraper_config(cfg)
    return RedirectResponse(f"/scraper#{bot_name}", status_code=302)


@app.post("/scraper/remove-category")
async def remove_category(
    request: Request,
    bot_name: str = Form(...),
    source_index: int = Form(...),
    cat_index: int = Form(...),
    _=Depends(require_session),
):
    cfg = _load_scraper_config()
    sources = cfg.get("bots", {}).get(bot_name, {}).get("sources", [])
    if 0 <= source_index < len(sources):
        cats = sources[source_index].get("categories", [])
        if 0 <= cat_index < len(cats):
            cats.pop(cat_index)
            _save_scraper_config(cfg)
    return RedirectResponse(f"/scraper#{bot_name}", status_code=302)


@app.post("/scraper/run", response_class=HTMLResponse)
async def run_scraper(
    request: Request,
    bot_name: str = Form(...),
    _=Depends(require_session),
):
    from scraper.http_scraper import run_scraper as do_scrape
    scraper_cfg = _load_scraper_config()
    bot_cfg = scraper_cfg.get("bots", {}).get(bot_name, {})
    sources = bot_cfg.get("sources", [])
    worksheet = f"{bot_name}_prices"  # always bot_name_prices

    configs = load_configs(settings.bots_dir)
    cfg = next((c for c in configs if c.name == bot_name), None)
    sheet_id = ""
    if cfg and cfg.knowledge.sheets.enabled:
        sheet_id = os.environ.get(cfg.knowledge.sheets.sheet_id_env, "")

    result = await do_scrape(
        bot_name=bot_name,
        config=sources,
        creds_path=settings.google_creds_path,
        sheet_id=sheet_id,
        worksheet=worksheet,
        kiro_url=settings.kiro_gateway_url,
        kiro_key=settings.kiro_gateway_api_key,
    )
    return templates.TemplateResponse("scraper_result.html", {"request": request, "result": result})
