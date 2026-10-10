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
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

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
