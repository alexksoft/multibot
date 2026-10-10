# Practical AI Assistants — Telegram Multibot

5 free thematic Telegram assistants from one codebase. Each bot helps users **prepare** for a purchase or service (calculate materials, build a checklist, generate questions for a pro, compare options, prepare a spec). No bot pretends to be a real company.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

pip install -r requirements.txt

cp .env.example .env
# Fill in tokens and keys

python main.py
```

## Environment Variables

See `.env.example` for all variables. Key ones:

| Variable | Description |
|---|---|
| `BUILDING_BOT_TOKEN` | Telegram token from @BotFather |
| `KIRO_GATEWAY_URL` | Kiro Gateway URL (e.g. `http://localhost:9000`) |
| `KIRO_GATEWAY_API_KEY` | Kiro Gateway API key |
| `GOOGLE_CREDS_PATH` | Path to Google service account JSON |
| `GOOGLE_SHEET_ID` | Default Google Sheet ID for catalog |
| `DIALOG_LOG_ENABLED` | `true` to log all conversations to Sheets |
| `ADMIN_ENABLED` | `true` to start admin panel |
| `ADMIN_PASSWORD_HASH` | bcrypt hash — generate with `python -m admin hash-password` |

## Bot Commands

- `/start` — show disclaimer and menu
- `/stats` — show stats (admin only, requires `ADMIN_CHAT_ID`)
- `/cancel` or `скасувати` — cancel current flow

## Adding a New Bot

1. Create `bots/<name>.yaml` with 6 sections (see `bots/building.yaml` as example)
2. Add `<NAME>_BOT_TOKEN=...` to `.env`
3. Restart `python main.py`

Or use the admin panel (`ADMIN_ENABLED=true`) → "Створити нового бота".

## Google Sheets Matrix

Expected columns: `category | item | price | unit | source_name | source_url | collected_at | active | notes`

- Every price **must** have `source_name` (shop/site) — rows without it are discarded
- Share the sheet with your service account email

## Scraper

Fills the Google Sheets matrix with real market data:

```bash
python -m scraper run --category Фарба --sheet <SHEET_ID>
```

Schedule with cron (runs independently from bots):
```
0 6 * * * cd /home/ubuntu/marketing_multibot_telegram && .venv/bin/python -m scraper run
```

## Admin Panel

```bash
# Generate password hash first:
python -m admin hash-password mypassword

# Add to .env:
# ADMIN_ENABLED=true
# ADMIN_PASSWORD_HASH=<hash from above>

python -m admin
# Opens at http://127.0.0.1:8600
```

## Oracle Cloud Always Free Setup

Oracle Cloud Free Tier: 1 OCPU, 1 GB RAM — sufficient for all 5 bots.

```bash
# 1. Create Always Free VM (Ubuntu 22.04), open port 8600 in security list if needed
# 2. SSH in and install dependencies:
sudo apt update && sudo apt install -y python3-pip python3-venv git

# 3. Clone/copy project
cd /home/ubuntu
git clone <your-repo> marketing_multibot_telegram
cd marketing_multibot_telegram

# 4. Setup
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
nano .env   # fill in tokens

# 5. Install systemd services
sudo cp multibot.service /etc/systemd/system/
sudo cp multibot-admin.service /etc/systemd/system/   # optional

sudo systemctl daemon-reload
sudo systemctl enable multibot
sudo systemctl start multibot

# Check status:
sudo systemctl status multibot
journalctl -u multibot -f

# 6. Admin panel (optional):
sudo systemctl enable multibot-admin
sudo systemctl start multibot-admin
```

### Memory note for 1 GB RAM

The bot process uses ~80–120 MB. With 5 bots + admin panel, total is ~200–300 MB — well within 1 GB.

If you hit memory limits, reduce `max_tokens` in bot configs or disable unused bots.

## Project Structure

```
main.py                     Entry point — starts all bots
src/multibot/
  config/
    sections.py             6-section pydantic schemas
    loader.py               Loads bots/*.yaml
    settings.py             Environment settings
  core/
    flow.py                 FlowEngine — executes conversation flows
    rules.py                Safe AST expression evaluator
    knowledge.py            KnowledgeBase — FAQ + catalog
    catalog.py              GoogleSheetsCatalog + LocalCatalog
    ai_orchestrator.py      AI Policy enforcement
    dialog_log.py           Background conversation logging to Sheets
    storage.py              SQLite + InMemory storage
    capabilities/registry.py  7 built-in capability functions
    providers/kiro_gateway.py  Kiro Gateway HTTP client
    integrations/delivery.py   ResultDelivery
    booking/service.py      Booking slots + demo seeder
  manager.py                BotManager — one Application per bot
bots/                       Bot YAML configs (6 sections each)
scraper/                    Standalone scraper → Google Sheets
admin/                      FastAPI admin panel + CRM
tests/                      pytest tests
```

## Booking (Beauty bot)

The beauty bot has `booking.enabled: true`. Demo masters/services are auto-generated on first run. Users can book appointments via inline buttons. CRM is available in the admin panel at `/crm/appointments`.

## Conversation Flow Question Types

| Type | Description | Example |
|---|---|---|
| `number` | Numeric with optional min/max | Height in meters |
| `text` | Free text | Goal description |
| `choice` | Pick from options list | Work type |
| `dimension` | WxL format | Room size `4x5` |

## Capabilities

| Name | Description |
|---|---|
| `calculate_materials` | Computes quantities using `calculation_rules` + `norms` |
| `search_products` | Finds items in Sheets matrix (always with source) |
| `shopping_list` | Builds shopping list with prices and sources |
| `checklist` | Generates preparation checklist |
| `questions_for_pro` | Generates questions to ask a specialist |
| `compare_options` | Compares catalog items side by side |
| `prepare_request` | Formats final document for the user |
