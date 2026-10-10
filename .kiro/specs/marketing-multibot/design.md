# Design Document

## Overview

**Practical AI Assistants** — конфігурований фреймворк на Python для запуску 5 безкоштовних тематичних Telegram-асистентів для звичайних людей з однієї кодової бази. Кожен бот — практичний AI-помічник (НЕ вдає реальну компанію), який готує користувача до покупки/послуги й віддає йому готовий документ. Поведінка кожного повністю визначається **модульною конфігурацією з 6 незалежних секцій**. Один процес завантажує кілька конфігурацій і запускає для кожної окремий екземпляр бота в межах спільного asyncio event loop. Окремий компонент `Scraper` наповнює матриці Google Sheets реальними ринковими даними — боти працюють лише на читання.

LLM-доступ здійснюється через **Kiro Gateway** (OpenAI-сумісний HTTP-ендпоінт), модель за замовчуванням — **Claude Opus 4.7**. Контракт шлюзу перенесено з референсного проєкту `Chatbot_whatsapp_faq` (`app/services/mentor_llm.py` + `app/config/settings.py`).

### Технологічний стек

- **Мова:** Python 3.11+
- **Telegram:** [`python-telegram-bot`](https://docs.python-telegram-bot.org) v21+ (async, кілька `Application` в одному процесі)
- **LLM-шлюз:** Kiro Gateway, HTTP через `httpx.AsyncClient`
- **Конфігурація:** YAML (6 секцій) + валідація `pydantic` v2; env через `pydantic-settings`
- **Сховище:** SQLite через інтерфейс `Storage` (+ in-memory для тестів)
- **Матриця даних:** Google Sheets через `gspread` (сервісний акаунт), з кешем; боти читають матрицю й (опційно) дописують логи діалогів у окремі аркуші `log_<bot_name>`; скрейпер пише матрицю; без Make.com/n8n
- **Скрейпер:** `httpx` + парсер HTML, повага до `robots.txt`, запуск за розкладом окремо від ботів
- **Admin-панель:** `fastapi` + `uvicorn` + `jinja2` (HTML), `passlib[bcrypt]` для хешу пароля; окремий процес, вимкнена за замовчуванням
- **Логування:** стандартний `logging` + маскування секретів

### Чому так

- `python-telegram-bot` v21 тримає кілька `Application` в одному asyncio-процесі → Requirement 1.
- Поділ конфіга на 6 секцій з окремими pydantic-схемами й полем `version` → Requirement 2 (зміна однієї секції не чіпає інші).
- Kiro Gateway OpenAI-сумісний (`/v1/chat/completions`, `Bearer`, `{model, messages, max_tokens}`) → переносимо той самий контракт, що в референсі → Requirement 8.
- Декларативні правила розрахунку + tool-calling з whitelist інструментів → anti-hallucination (Requirement 7.3): ціни/числа беруться з Knowledge/capabilities, не з генерації.
- **Матриця послуг у Google Sheets** як джерело істини для послуг і цін (читається напряму через `gspread`, кешується): усуває головний ризик — вигадані послуги й хибні ціни складних процедур. Make.com/n8n не потрібні, тож немає лімітів операцій оркестратора (Requirement 6).

## Architecture

```
                         ┌───────────────────────────────┐
                         │           main.py             │
                         │   bootstrap + lifecycle        │
                         └───────────────┬───────────────┘
                                         │
                         ┌───────────────▼───────────────┐
                         │         BotManager            │
                         │  load 6-section configs →     │
                         │  validate per-section →       │
                         │  spawn Application per bot     │
                         └───────┬───────────────┬───────┘
                                 │               │
                 ┌───────────────▼──┐        ┌───▼──────────────┐
                 │ Bot #1 (furniture)│ ...    │ Bot #N (salon)   │
                 │ Application       │        │ Application      │
                 └─────────┬─────────┘        └────────┬─────────┘
                           │   shared config-driven handlers      │
          ┌────────────────┴───────────────────────────┴───────────────┐
          │                      Core Engine                           │
          │  Router → FlowEngine (Conversation Flows)                  │
          │     │                                                      │
          │     ├── Consultant  ──► AIOrchestrator (AI Policy)         │
          │     ├── FlowRunner  ──► CapabilityRegistry (Capabilities)  │
          │     └── Delivery    ──► ResultDelivery (Integrations)      │
          └───────┬──────────────┬───────────────┬───────────────┬─────┘
                  │              │               │               │
        ┌─────────▼───┐ ┌────────▼─────┐ ┌───────▼──────┐ ┌──────▼───────┐
        │ KiroGateway │ │ RuleEngine + │ │ KnowledgeBase│ │ ResultDelivery│
        │ Provider    │ │ Capabilities │ │ Sheets matrix│ │ user + sinks │
        │ (Opus 4.7)  │ │ functions    │ │ (scraper-fed)│ │ (off by def.)│
        └─────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │     Storage       │
                         │ state/leads/stats │
                         └───────────────────┘
```

### Мапування 6 секцій на компоненти

| Секція конфігу | Відповідальний компонент |
|----------------|--------------------------|
| 1. Assistant Profile | `BotContext` (роль, тип користувача, мова, тон, disclaimer) |
| 2. Conversation Flows | `FlowEngine` / `FlowRunner` |
| 3. Capabilities | `CapabilityRegistry` + `RuleEngine` |
| 4. Knowledge & Data | `KnowledgeBase` (FAQ matcher + `GoogleSheetsCatalog` матриця реальних цін) |
| 5. AI Policy | `AIOrchestrator` (system prompt, allowed_tools, межі, уточнення) |
| 6. Integrations | `ResultDelivery` (документ користувачу + опційні sink'и) |

Окремий компонент поза ботами: **`Scraper`** — наповнює матриці Google Sheets реальними даними (див. нижче). Боти лише читають.

### Потік обробки повідомлення

1. Telegram доставляє апдейт у конкретний `Application`.
2. `Router` читає стан діалогу зі `Storage` і визначає команду/намір.
3. `FlowEngine` виконує поточний крок активного сценарію (Conversation Flows).
4. За потреби крок звертається до `AIOrchestrator` (LLM через Kiro Gateway), `CapabilityRegistry` (функції), `KnowledgeBase` (факти).
5. При завершенні `ResultDelivery` віддає готовий документ користувачу (і в опційні увімкнені sink'и).
6. Оновлений стан зберігається у `Storage`; відповідь надсилається користувачу.
7. Якщо увімкнено `DIALOG_LOG_ENABLED`, `DialogLogger` фоново дописує вхідне й вихідне повідомлення в аркуш `log_<bot_name>` (не блокує відповідь).

## Components and Interfaces

### Конфігурація: 6 секцій (`config/`)

Кожна секція — окрема pydantic-модель із полем `version`. Один YAML-файл на бота містить 6 top-level ключів. Зміна однієї секції не торкається інших (Requirement 2.5).

```python
# config/sections.py

class AssistantProfile(BaseModel):
    version: int = 1
    series_name: str = "Practical AI Assistants"
    assistant_role: str                # напр. "AI-помічник для планування ремонту"
    industry: str                      # галузь (тематика), НЕ конкретна компанія
    target_user: str                   # напр. "власники житла та майстри"
    language: str = "uk"
    tone: str = "friendly"
    disclaimer: str = ("Безкоштовний демонстраційний AI-асистент. "
                       "Не представляє конкретну компанію чи магазин.")
    developer_note: str | None = None  # ненав'язлива примітка в кінці відповіді (без PII)

class Step(BaseModel):
    id: str
    kind: Literal["message", "question", "capability", "handoff"]
    text: str | None = None
    question_type: Literal["number", "text", "choice", "dimension"] | None = None
    options: list[str] | None = None
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    save_as: str | None = None         # ключ у collected
    capability: str | None = None      # для kind=capability
    next: str | None = None            # лінійний перехід
    transitions: list["Transition"] = []  # умовні переходи

class Transition(BaseModel):
    when: str                          # безпечний вираз над collected
    goto: str

class Flow(BaseModel):
    id: str
    title: str
    start: str
    steps: list[Step]

class ConversationFlows(BaseModel):
    version: int = 1
    menu_title: str = "Оберіть дію:"
    flows: list[Flow]
    cancel_commands: list[str] = ["/cancel", "скасувати"]

class CapabilityRef(BaseModel):
    name: Literal["calculate_materials", "search_products",
                  "shopping_list", "checklist", "questions_for_pro",
                  "compare_options", "prepare_request"]
    params: dict = {}                  # напр. rules для calculate_materials

class Capabilities(BaseModel):
    version: int = 1
    enabled: list[CapabilityRef] = []

class CalculationRule(BaseModel):
    id: str
    label: str
    expression: str                    # безпечний обчислювач
    unit: str | None = None
    round_to: int | None = None

class CatalogItem(BaseModel):
    category: str                      # категорія (напр. "Фарба", "Стрижка")
    item: str = ""                     # конкретна позиція/варіант
    price: float | None = None
    unit: str | None = None            # грн, грн/м², грн/год тощо
    source_name: str | None = None     # ОБОВ'ЯЗКОВО, якщо є price: магазин/сайт
    source_url: str | None = None      # посилання на джерело
    collected_at: str | None = None    # дата збору (скрейпером)
    attributes: dict = {}              # характеристики
    active: bool = True
    notes: str = ""

    @model_validator(mode="after")
    def _price_needs_source(self):
        # Ціна без джерела вважається ненадійною і не допускається (Req 6.4)
        if self.price is not None and not self.source_name:
            raise ValueError("price requires source_name (магазин/сайт)")
        return self

class SheetsSource(BaseModel):
    enabled: bool = False
    sheet_id_env: str = "GOOGLE_SHEET_ID"   # ім'я env-змінної з ID таблиці
    worksheet: str | None = None            # назва аркуша (None → перший)
    cache_ttl_seconds: int = 300            # інтервал кешу

class FAQItem(BaseModel):
    question: str
    answer: str
    keywords: list[str] = []

class KnowledgeData(BaseModel):
    version: int = 1
    faq: list[FAQItem] = []
    catalog: list[CatalogItem] = []    # локальний резерв / fallback
    sheets: SheetsSource = SheetsSource()  # матриця послуг у Google Sheets (джерело істини)
    calculation_rules: list[CalculationRule] = []
    norms: dict[str, float] = {}       # технологічні коефіцієнти

class AIPolicy(BaseModel):
    version: int = 1
    enabled: bool = True
    system_prompt: str                 # індивідуальний для кожного бота
    model: str | None = None           # None → claude-opus-4.7
    allowed_tools: list[str] = []      # підмножина назв capabilities
    max_tokens: int = 600
    forbidden_advice: list[str] = []   # мед/юр/фін/точний техдіагноз → до фахівця
    clarify_when_unsure: bool = True

class RequestField(BaseModel):          # поле для prepare_request (документ користувачу)
    id: str
    label: str
    type: Literal["text", "phone", "choice"]
    required: bool = True
    options: list[str] | None = None

class IntegrationSink(BaseModel):
    type: Literal["telegram_manager", "crm_webhook", "email"]
    enabled: bool = False              # за замовчуванням ВИМКНЕНО (демо)
    config: dict = {}                  # імена env-змінних, не секрети

class Integrations(BaseModel):
    version: int = 1
    request_form: list[RequestField] = []  # поля для готового документа користувачу
    deliver_to_user: bool = True       # за замовчуванням результат — користувачу в чат
    sinks: list[IntegrationSink] = []  # опційні отримувачі (вимкнені)

class BookingConfig(BaseModel):        # фіча-прапорець запису (демо)
    version: int = 1
    enabled: bool = False              # за замовчуванням ВИМКНЕНО (увімкнено лише в beauty)
    provider_term: str = "майстер"     # термінологія ніші: майстер/спеціаліст
    service_term: str = "послуга"      # послуга/робота
    demo_masters: int = 5              # скільки вигаданих майстрів згенерувати
    contacts_text: str = ""            # текст пункту «Контакти» (демо)
    intro: str = ""                    # додатковий промт/вступ для сценарію запису

class BotConfig(BaseModel):
    name: str
    token_env: str                     # ім'я env-змінної з токеном
    assistant_profile: AssistantProfile
    conversation_flows: ConversationFlows
    capabilities: Capabilities = Capabilities()
    knowledge: KnowledgeData = KnowledgeData()
    ai_policy: AIPolicy
    integrations: Integrations = Integrations()
    booking: BookingConfig = BookingConfig()   # опційна фіча запису
```

`ConfigLoader` читає `bots/*.yaml`, валідує секції окремо, логує їх `version` (Req 2.3), пропускає невалідні боти (Req 2.4).

### BotManager (`manager.py`) — Requirement 1

- `load()` — конфіги + перевірка унікальності токенів (Req 1.3).
- `start_all()` — `Application` на кожен бот, спільні хендлери з прив'язаним `BotContext` (конфіг + залежності).
- `error_handler` на рівні `Application` ізолює збій одного бота (Req 1.4).
- `shutdown()` — graceful stop по сигналу (Req 1.5).

### FlowEngine (`core/flow.py`) — Requirements 4, 10

- Виконує `Flow` покроково; стан у `Storage` (`DialogState { user_id, bot_name, flow_id, step_id, collected, updated_at }`).
- `question`-крок валідує відповідь за типом/діапазоном, повторює запит при помилці (Req 4.2, 4.3).
- `transitions[].when` обчислюється безпечним обчислювачем над `collected` (Req 4.4).
- `/cancel` → меню; таймаут сесії очищає стан (Req 4.5, 10.4).
- Меню будується лише з доступних flows (Req 4.6).

### CapabilityRegistry (`core/capabilities/`) — Requirement 5

Вбудовані функції з єдиним інтерфейсом; конфіг лише вмикає й параметризує їх (довільний код у YAML заборонено).

```python
class Capability(Protocol):
    name: str
    async def run(self, ctx: BotContext, args: dict) -> CapabilityResult: ...
```

- `calculate_materials` — використовує `RuleEngine` над `knowledge.calculation_rules` + `norms`.
- `search_products` — пошук у `KnowledgeBase` (матриця Google Sheets); ціна завжди повертається РАЗОМ із `source_name` (магазин/сайт); лише активні позиції (Req 6.2, 6.3).
- `shopping_list` — формує список покупок із позицій (кількість × ціна), кожна ціна з назвою магазину-джерела (Req 6.3).
- `checklist` — генерує чекліст замірів/підготовки за шаблоном ніші (`params.template`).
- `questions_for_pro` — формує перелік запитань до майстра/продавця за зібраними параметрами.
- `compare_options` — порівнює варіанти з матриці за характеристиками/ціною (кожна ціна з джерелом).
- `prepare_request` — формує готовий документ (ТЗ/заявку/список) для САМОГО користувача; передає в `ResultDelivery`.
- Невідома/невключена capability не викликається навіть через LLM (Req 5.4, 7.2).

#### RuleEngine (`core/rules.py`) — Requirements 5.6, 12.4

- Безпечний AST-обчислювач (allow-list: `+ - * / **`, `round`, `min`, `max`, числа, змінні з `collected`/`norms`).
- Похідні для `dimension`: `*_width`, `*_length`, `*_area`, `*_perimeter`.
- Помилка правила → правило пропускається з логом, решта рахується.

### KnowledgeBase (`core/knowledge.py`) — Requirement 6

Єдина точка доступу до фактів. Категорії, позиції, ціни беруться з **матриці Google Sheets** (яку наповнює скрейпер); локальний `catalog` у YAML — лише резерв.

- FAQ matcher (keyword + нормалізація) з пріоритетом над LLM (Req 6.1).
- `list_items(category)` / `find_item(category, item)` — повертають ЛИШЕ активні позиції (Req 6.5). Якщо позиції немає — «не знайдено» (ніколи не вигадують), бот пропонує альтернативи (Req 6.6).
- Кожна ціна повертається РАЗОМ із `source_name`/`source_url`/`collected_at`; позиції з `price` без `source_name` відкидаються ще на рівні валідації `CatalogItem` (Req 6.3, 6.4).
- Джерело даних — `CatalogProvider` (див. нижче): за замовчуванням `GoogleSheetsCatalog`, резерв — `LocalCatalog` з `knowledge.catalog`.
- `norms` постачаються в `RuleEngine` (Req 6.10).

#### CatalogProvider і GoogleSheetsCatalog (`core/catalog.py`) — Requirement 6

Контракт доступу до Google Sheets перенесено **один-в-один** з референсу (`Chatbot_whatsapp_faq/app/services/user_tracker.py`), та сама бібліотека `gspread==6.1.2`:

- автентифікація: `gspread.service_account(filename=GOOGLE_CREDS_PATH)` (JSON-ключ сервісного акаунта);
- відкриття таблиці: `gc.open_by_key(GOOGLE_SHEET_ID)`;
- аркуш: `.worksheet(<назва>)` або перший (`.sheet1`), якщо назву не задано;
- читання рядків: `ws.get_all_records()`;
- graceful degradation — як у `_get_client()` референсу: якщо `GOOGLE_CREDS_PATH`/`GOOGLE_SHEET_ID` не задані або будь-який виняток, повертається «клієнт недоступний», функція тихо вимикається з попередженням у лозі (а бот переходить на кеш/`LocalCatalog`).

```python
class CatalogProvider(Protocol):
    async def items(self) -> list[CatalogItem]: ...

class GoogleSheetsCatalog:
    """
    Читає матрицю реальних даних з Google Sheets і кешує її на cache_ttl_seconds.
    Очікувані колонки заголовка:
      category | item | price | unit | source_name | source_url | collected_at | active | notes
    Рядок з price, але без source_name відкидається (ненадійна ціна).
    """
    def __init__(self, creds_path: str, sheet_id: str,
                 worksheet: str | None, ttl: int): ...
    async def items(self) -> list[CatalogItem]:
        # 1) якщо кеш свіжий → повернути кеш
        # 2) інакше gspread.service_account(...).open_by_key(sheet_id)
        #    .worksheet(worksheet або перший).get_all_records()
        # 3) змапити рядки у CatalogItem, відфільтрувати active=false,
        #    оновити кеш і час
        ...

class LocalCatalog:
    """Резерв: використовує knowledge.catalog із YAML."""
    def __init__(self, items: list[CatalogItem]): ...
```

- **Кешування:** читання Sheets не на кожне повідомлення, а раз на `cache_ttl_seconds` (Req 6.5). Оновлення матриці підхоплюється після закінчення TTL без рестарту (Req 6.6).
- **Fallback:** якщо Sheets недоступний/не налаштований — використати останній кеш, інакше `LocalCatalog`; зафіксувати попередження, не вигадувати дані (Req 6.9). Поведінка graceful, як у референсі (`_get_client()` повертає `None` при недоступності).
- **Парсинг:** `active` приймає `true/1/так/yes`; `price` нормалізується в число; рядок із `price` без `source_name` відкидається (Req 6.4).

### Scraper (`scraper/`) — Requirement 14

Окремий компонент (власний процес/задача за розкладом), що наповнює матриці Google Sheets реальними ринковими даними. **Боти його не викликають** — вони лише читають результат. Пише в ті самі аркуші через той самий сервісний акаунт (`GOOGLE_CREDS_PATH`), що й читають боти.

```python
class SourceAdapter(Protocol):
    name: str                          # назва магазину/сайту (→ source_name)
    base_url: str
    async def fetch(self, category: str) -> list[ScrapedRow]: ...

class ScrapedRow(BaseModel):
    category: str
    item: str
    price: float
    unit: str | None
    source_name: str                   # ОБОВ'ЯЗКОВО
    source_url: str                    # ОБОВ'ЯЗКОВО
    collected_at: str                  # ISO-дата збору
    attributes: dict = {}

class SheetsWriter:
    """Апсертить ScrapedRow у аркуш (ключ: category+item+source_name),
       позначає застарілі рядки active=false. gspread service_account + open_by_key."""
    def upsert(self, worksheet: str, rows: list[ScrapedRow]) -> None: ...
```

Правила (конфіг `scraper/config.yaml`):

- **Етика:** перед запитами читати `robots.txt`; дотримуватись `crawl-delay`/розумних пауз; коректний `User-Agent`; джерела, що забороняють збір, пропускаються з логом (Req 14.4, 14.5).
- **Джерело для кожної ціни обов'язкове:** якщо не вдалося встановити `source_name`/`source_url`, рядок НЕ пишеться (Req 14.2, 14.3).
- **Апсерт без дублів:** ключ `category+item+source_name`; записи, яких більше немає в джерелі, позначаються `active=false`, а не видаляються (Req 14.6).
- **Стійкість:** збій/зміна формату одного джерела логуються й пропускаються, не псуючи наявні валідні дані (Req 14.8).
- **Запуск:** CLI `python -m scraper run [--category ...]` і за розкладом (cron/Task Scheduler), незалежно від ботів (Req 14.7).
- **Прозорість:** `collected_at` і `source_name` стають частиною кожної ціни, яку показує бот.

### Admin-панель (`admin/`) — Requirement 15

Окремий FastAPI-застосунок (власний процес, `uvicorn`), вимкнений за замовчуванням. Показує наявні боти та генерує нові конфіги через Kiro Gateway. **Не керує життєвим циклом ботів** — лише створює YAML і дає інструкцію перезапустити процес.

#### Маршрути (routes)

| Маршрут | Метод | Призначення |
|---------|-------|-------------|
| `/login` | GET/POST | Форма входу; перевірка `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH` |
| `/logout` | POST | Завершити сесію |
| `/` | GET | Список усіх ботів із `bots/*.yaml` + статуси |
| `/bot/{name}` | GET | Картка бота: параметри 6 секцій (без секретів) |
| `/new` | GET | Форма-майстер «Створити нового бота» |
| `/new` | POST | Генерація YAML через Gateway → валідація → запис → інструкція |

Усі маршрути, крім `/login`, захищені залежністю `require_session` (Req 15.2).

#### Автентифікація та сесія

```python
# admin/auth.py
from passlib.hash import bcrypt

def verify_login(username: str, password: str) -> bool:
    return (username == settings.admin_username
            and bool(settings.admin_password_hash)
            and bcrypt.verify(password, settings.admin_password_hash))
```

- Пароль ніколи не зберігається у відкритому вигляді — лише `ADMIN_PASSWORD_HASH` (bcrypt) у `.env` (Req 15.3). Хеш генерується окремою CLI-утилітою (`python -m admin hash-password`).
- Сесія — підписаний cookie (`itsdangerous`/`SessionMiddleware`), час життя обмежений.
- Помилка входу — узагальнене повідомлення без деталей (Req 15.3).

#### BotCatalogView (читання конфігів)

- Читає `bots/*.yaml` через `ConfigLoader`; для кожного бота показує `name`, роль, галузь, мову, увімкнені flows/capabilities, стан `knowledge.sheets.enabled`, і **наявність токена** (`os.environ` за `token_env`) як так/ні — без показу значення (Req 15.4, 15.5, 15.11).
- Файли-шаблони (`_*.yaml`) і секрети не відображаються.

#### BotGenerator (створення нового конфіга) — Req 15.6-15.10

Потік:

1. Майстер `/new` збирає відповіді: ніша/роль, тип користувача, набір сценаріїв (checkbox: розрахунок/чекліст/питання/порівняння/заявка), мова, тон, чи потрібна матриця цін.
2. `BotGenerator` будує промт і звертається до `KiroGatewayProvider` (Opus 4.7) з вимогою повернути YAML за 6-секційною схемою (із прикладом-шаблоном у промті).
3. Відповідь парситься у `BotConfig` **тими самими pydantic-схемами**. Якщо невалідно — до 2 повторів із поверненням помилок валідації в промт; при невдачі показується помилка, файл НЕ пишеться (Req 15.8).
4. `name` санітизується (`[a-z0-9_]`, напр. `pet_care_assistant`); якщо `bots/<name>.yaml` існує — вимагається явне підтвердження перезапису (Req 15.9).
5. Запис дозволений ЛИШЕ в каталог `bots/` (перевірка, що розвʼязаний шлях лежить усередині `bots/`) — захист від path traversal (Req 15.11).
6. Сторінка результату показує інструкцію (Req 15.10):
   - створити бота в @BotFather і скопіювати токен;
   - додати `<NAME>_BOT_TOKEN` у `.env` (і `<NAME>_SHEET_ID`, якщо увімкнено матрицю);
   - за потреби наповнити матрицю скрейпером;
   - **перезапустити процес ботів** (панель не робить це сама).

#### Безпека

- Панель окремий процес; слухає на `ADMIN_HOST`/`ADMIN_PORT` (за замовчуванням локально) (Req 15.12).
- Вимкнена, доки `ADMIN_ENABLED=true` (Req 15.1).
- CSRF-захист форм; запис лише у `bots/`; жодного показу/редагування секретів (Req 15.11).

### DialogLogger (`core/dialog_log.py`) — Requirement 16

Спільний компонент логування бесід у Google Sheets, за підходом трекера з референсу (`Chatbot_whatsapp_faq/app/services/user_tracker.py`): фоновий потік, `append_row`, `_ensure_header`, graceful degradation. **Окремий аркуш (worksheet) на кожного бота** — `log_<bot_name>`.

```python
# core/dialog_log.py
_HEADER = ["timestamp", "bot_name", "user_id", "direction", "flow_id", "step_id", "text"]

def log_message(bot_name: str, user_id: int, direction: str,
                text: str, flow_id: str = "", step_id: str = "") -> None:
    """Записати повідомлення діалогу у фоновому потоці (не блокує відповідь)."""
    if not settings.dialog_log_enabled:
        return
    Thread(target=_write, args=(bot_name, user_id, direction, text, flow_id, step_id),
           daemon=True).start()

def _write(bot_name, user_id, direction, text, flow_id, step_id):
    try:
        ws = _get_worksheet(f"log_{bot_name}")   # створити за потреби + _ensure_header
        if ws is None:                            # Sheets не налаштований → тихо вийти
            return
        ws.append_row([_utcnow(), bot_name, str(user_id), direction, flow_id, step_id, text])
    except Exception as e:
        logger.warning(f"[dialog_log] skip ({bot_name}): {e}")
```

- `direction`: `in` (повідомлення користувача) або `out` (відповідь бота) (Req 16.4).
- Аркуш `log_<bot_name>` створюється за потреби; перший запис додає заголовок `_HEADER` (Req 16.2, 16.3).
- Той самий сервісний акаунт (`GOOGLE_CREDS_PATH`) і таблиця `DIALOG_LOG_SHEET_ID` (за замовчуванням `GOOGLE_SHEET_ID`) (Req 16.7).
- Увімкнено за замовчуванням (`DIALOG_LOG_ENABLED=true`) — обов'язкова функція спостережуваності; фоновий запис, graceful degradation якщо Sheets фізично недоступний (Req 16.1, 16.5, 16.6).
- Логуються лише `user_id` і текст; токени/ключі в лог не потрапляють (Req 16.8). `Router` викликає `log_message` на вхід і на вихід для всіх ботів однаково (Req 16.9).

### Booking (`core/booking/`) — Requirement 17

Спільний модуль запису, активний лише коли `booking.enabled: true` (наразі beauty). Усі дані **демонстраційні**. Зберігання — **SQLite** (цілісність слотів критична; Google Sheets для цього не підходить).

#### Моделі (SQLite)

```python
class Service(BaseModel):
    id: int
    name: str
    price: float
    duration_min: int                  # тривалість у хвилинах (для розкладу слотів)
    is_demo: bool = True

class Master(BaseModel):
    id: int
    name: str
    working_days: list[int]            # 0-6 (пн-нд)
    work_start: str                    # "10:00"
    work_end: str                      # "20:00"
    service_ids: list[int] = []
    is_demo: bool = True

class Appointment(BaseModel):
    id: int
    bot_name: str
    user_id: int
    service_id: int
    master_id: int
    start: datetime
    status: Literal["new", "confirmed", "done", "cancelled"] = "new"
    created_at: datetime

class Client(BaseModel):
    id: int
    bot_name: str
    user_id: int
    name: str
    phone: str
    # історія візитів = Appointment за user_id
```

#### Компоненти

- `DemoSeeder` — при першому вмиканні booking генерує `booking.demo_masters` вигаданих майстрів із послугами, цінами, тривалістю й розкладом (`is_demo=true`); позначає дані як демо (Req 17.2).
- `SlotService` — рахує **вільні слоти** для (майстер, дата): генерує сітку за робочими годинами й `duration_min`, виключає зайняті активними `Appointment`; «Будь-який майстер» = об'єднання вільних слотів усіх майстрів послуги (Req 17.3, 17.4).
- `BookingFlow` — Telegram-сценарій (inline-кнопки): меню «Записатися / Мої записи / Контакти» → послуга (з ціною) → майстер (або «Будь-який») → дата → вільний час → **ім'я + телефон (кнопка "Відправити контакт")** → підсумок → підтвердження. Телефон/ім'я запитуються ЛИШЕ тут (Req 17.5, 17.6).
- При підтвердженні: `Appointment` зберігається, слот зайнятий, адміну йде повідомлення в Telegram (`ADMIN_CHAT_ID`) (Req 17.7).
- «Мої записи» → майбутні записи + «Скасувати» (статус `cancelled`, слот звільняється) (Req 17.8, 17.9).
- «Контакти» → `booking.contacts_text` з нагадуванням, що це демо (Req 17.10, 17.11).
- Термінологія (`provider_term`/`service_term`) підставляється в тексти — щоб той самий модуль працював для авто/меблів тощо (Req 17.12).
- **Відкладено:** нагадування за 2 год (scheduler) — не в поточному обсязі (Req 17.13).

Сторонні записи у `Storage` розширюються таблицями `services`, `masters`, `appointments`, `clients`.

### CRM (розділ admin-панелі) — Requirement 18

Додається як розділ наявної FastAPI admin-панелі (той самий логін, Requirement 15), з'являється коли booking увімкнено хоча б для одного бота.

| Маршрут | Призначення |
|---------|-------------|
| `/crm/appointments` | Список записів із фільтром за датою і майстром; зміна статусу (new/confirmed/done/cancelled) |
| `/crm/services` | Довідник послуг: назва, ціна, тривалість (перегляд/редагування) |
| `/crm/masters` | Довідник майстрів: ім'я, робочі дні та години |
| `/crm/clients` | Клієнти: ім'я, телефон, історія візитів |

- Усі маршрути під `require_session`; дані у SQLite; секрети не показуються (Req 18.1, 18.8).
- Зміни послуг/майстрів/розкладу впливають на розрахунок вільних слотів у боті (`SlotService` читає ту саму БД) (Req 18.7).

### AIOrchestrator (`core/ai_orchestrator.py`) — Requirements 7, 8

- Будує запит до LLM: `system_prompt` з AI Policy + контекст (assistant profile, стислі факти з Knowledge, історія сесії).
- Function-calling: модель може викликати лише `allowed_tools` (мапінг на `CapabilityRegistry`) (Req 7.2). Факти (ціна/кількість) завжди з результату capability/Knowledge, не з тексту моделі (Req 7.3).
- `forbidden_advice` → відмова + пояснення, що рішення за фахівцем, і пропозиція підготувати запитання до нього (Req 7.4).
- `clarify_when_unsure` → уточнювальне питання (Req 7.5).

#### KiroGatewayProvider (`core/providers/kiro_gateway.py`) — Requirement 8

Контракт перенесено з референсу (`mentor_llm.py`):

```python
class KiroGatewayProvider:
    def __init__(self, base_url: str, api_key: str, default_model: str = "claude-opus-4.7"):
        ...
    async def complete(self, system: str, messages: list[dict],
                       model: str | None = None, max_tokens: int = 600,
                       tools: list[dict] | None = None) -> ProviderResult:
        # POST {base_url}/v1/chat/completions
        # headers: Authorization: Bearer <api_key>, Content-Type: application/json
        # json: {"model": model or default_model, "messages": [...], "max_tokens": N, ["tools": ...]}
        # resp: data["choices"][0]["message"]  (content або tool_calls)
```

- `httpx.AsyncClient(timeout=25.0)`, ретраї; таймаут/помилка → `FallbackProvider` (Req 8.4).
- Якщо `KIRO_GATEWAY_URL`/`KIRO_GATEWAY_API_KEY` не задані → режим без LLM, попередження в лозі (Req 8.5).
- `FallbackProvider` — FAQ + шаблонні відповіді без мережі.

### ResultDelivery (`core/delivery/`) — Requirement 9

За замовчуванням результат (`PreparedResult`) віддається **самому користувачу** в чат як структурований текст. Опційні sink'и (вимкнені) показують майбутньому замовнику, що бот МОЖЕ доставляти ліди.

```python
class ResultSink(Protocol):
    type: str
    enabled: bool
    async def deliver(self, result: PreparedResult) -> bool: ...
```

- `UserChatDelivery` — завжди увімкнено: форматує `PreparedResult` і надсилає користувачу (Req 9.1).
- `TelegramManagerSink` — реалізовано, але `enabled=false` за замовчуванням (демо).
- `CrmWebhookSink`, `EmailSink` — адаптери з інтерфейсом; нереалізований/невключений sink позначається недоступним при валідації (Req 9.5).
- При увімкненому sink невдача доставки → локальне збереження + черга ретраю (Req 9.4).
- Бот НЕ стверджує «передано компанії», якщо жоден реальний отримувач не ввімкнений (Req 9.6).

```python
class PreparedResult(BaseModel):
    id: str
    bot_name: str
    industry: str
    user_id: int
    kind: str                          # "spec" | "shopping_list" | "checklist" | ...
    fields: dict[str, str]             # з request_form
    collected_params: dict
    calculation: dict | None           # ціни з source_name
    body_text: str                     # готовий текст для користувача
    created_at: datetime
    delivered_to: list[str] = ["user"]
```

### Storage (`core/storage.py`) — Requirements 10, 11

```python
class Storage(Protocol):
    async def get_state(self, bot_name, user_id) -> DialogState | None: ...
    async def save_state(self, state: DialogState) -> None: ...
    async def clear_state(self, bot_name, user_id) -> None: ...
    async def save_result(self, result: PreparedResult) -> None: ...
    async def incr_counter(self, bot_name, metric) -> None: ...
    async def stats(self, bot_name) -> dict: ...
```

- SQLite за замовчуванням (`dialog_state`, `results`, `counters`, а також `services`, `masters`, `appointments`, `clients` для booking); відновлення станів після рестарту (Req 10.2). `InMemoryStorage` для тестів.

### Admin & Logging — Requirements 11, 12

- `/stats` лише з адмін-чату (Req 11.4).
- Структуроване логування з `bot_name`, `industry`, типом події; фільтр маскування токенів/ключів/телефонів (Req 11.1, 12.3).

## Data Models

Ключові моделі описані вище. Приклад YAML (6 секцій, фрагмент building):

```yaml
name: building_assistant
token_env: BUILDING_BOT_TOKEN

assistant_profile:
  version: 1
  series_name: "Practical AI Assistants"
  assistant_role: "AI-помічник для планування ремонту"
  industry: "будівництво та ремонт"
  target_user: "власники житла та майстри"
  language: uk
  tone: friendly
  # disclaimer має значення за замовчуванням (нейтральне)

conversation_flows:
  version: 1
  menu_title: "Що плануєте зробити?"
  flows:
    - id: estimate
      title: "Розрахувати матеріали"
      start: ask_room
      steps:
        - id: ask_room
          kind: question
          text: "Розміри кімнати (ШxД), напр. 4x5:"
          question_type: dimension
          save_as: room
          next: ask_height
        - id: ask_height
          kind: question
          text: "Висота стін (м)?"
          question_type: number
          min: 2
          max: 5
          save_as: height
          next: do_calc
        - id: do_calc
          kind: capability
          capability: calculate_materials
          next: make_list
        - id: make_list
          kind: capability
          capability: shopping_list      # список покупок із цінами й магазинами
          next: give_result
        - id: give_result
          kind: capability
          capability: prepare_request    # готовий документ користувачу

capabilities:
  version: 1
  enabled:
    - name: calculate_materials
    - name: search_products
    - name: shopping_list
    - name: prepare_request

knowledge:
  version: 1
  sheets:                      # матриця реальних цін (наповнює скрейпер)
    enabled: true
    sheet_id_env: BUILDING_SHEET_ID
    worksheet: "Матеріали"
    cache_ttl_seconds: 300
  calculation_rules:
    - id: wall_area
      label: "Площа стін"
      expression: "(room_width + room_length) * 2 * height"
      unit: "м²"
      round_to: 1
    - id: plaster_kg
      label: "Штукатурка"
      expression: "wall_area * norms_plaster"
      unit: "кг"
      round_to: 0
  norms: { norms_plaster: 8.5 }
  catalog: []                  # локальний резерв, якщо Sheets недоступний
  faq:
    - question: "Скільки сохне штукатурка?"
      answer: "Зазвичай 1-2 доби."
      keywords: ["сохне", "висихання"]

ai_policy:
  version: 1
  enabled: true
  model: claude-opus-4.7
  system_prompt: |
    Ти — безкоштовний AI-помічник для планування ремонту. Ти НЕ представляєш
    конкретний магазин. Пояснюй вибір матеріалів простою мовою. Кількість матеріалів
    бери ЛИШЕ з calculate_materials, а ціни — ЛИШЕ з матриці (search_products),
    завжди з назвою магазину-джерела. Не вигадуй цін. У кінці допоможи сформувати
    список покупок, який користувач візьме в будь-який магазин.
  allowed_tools: ["calculate_materials", "search_products", "shopping_list"]
  forbidden_advice: []

integrations:
  version: 1
  deliver_to_user: true        # результат — користувачу в чат
  request_form:
    - { id: name, label: "Ваше ім'я (необов'язково)", type: text, required: false }
  sinks:                       # опційні отримувачі, вимкнені (демо)
    - type: telegram_manager
      enabled: false
      config: { chat_id_env: BUILDING_MANAGER_CHAT_ID }
```

## Error Handling

| Ситуація | Поведінка | Requirement |
|----------|-----------|-------------|
| Невалідна секція конфіга | Пропустити бота, лог, інші працюють | 2.4, 1.4 |
| Дубль токена | Відхилити другий бот, лог | 1.3 |
| Kiro Gateway недоступний/таймаут | Fallback (FAQ/повідомлення) | 8.4 |
| Gateway не налаштований | Режим без LLM, попередження | 8.5 |
| Google Sheets недоступний/не налаштований | Останній кеш → `LocalCatalog`, попередження, без вигаданих даних | 6.9 |
| Ціна в матриці без `source_name` | Відкинути позицію (ненадійна ціна), не показувати | 6.4 |
| Запит неіснуючої позиції | «Не знайдено» + альтернативи, без вигаданих позицій | 6.6 |
| Невалідний ввід у кроці | Повторний запит з підказкою | 4.3 |
| Помилка виразу правила | Пропустити правило, лог | 5.7 |
| LLM просить недозволений tool | Відмовити, не викликати | 5.4, 7.2 |
| Скрейпер: джерело недоступне/формат змінився | Пропустити джерело, лог, не псувати валідні дані | 14.8 |
| Увімкнений sink: доставка не вдалась | Локальне збереження + ретрай | 9.4 |
| Admin: доступ без сесії | Редірект на `/login` | 15.2 |
| Admin: LLM повернув невалідний YAML | До 2 повторів, інакше помилка, файл не пишеться | 15.8 |
| Admin: `<name>.yaml` уже існує | Вимагати явне підтвердження перезапису | 15.9 |
| Booking: обраний слот уже зайнятий (гонка) | Повідомити й показати оновлені вільні слоти | 17.4 |
| Booking: немає вільних слотів на дату | Запропонувати іншу дату/майстра | 17.4 |
| Виняток під час обробки | `error_handler` ізолює, лог, ввічливе повідомлення | 1.4 |

## Security Considerations

- Секрети (`*_TOKEN`, `KIRO_GATEWAY_API_KEY`, ключі sink'ів) — лише через env/`.env` (у `.gitignore`); у конфігах — імена env-змінних (Req 12.1, 12.2).
- Маскування секретів і телефонів у логах (Req 12.3).
- Безпечний AST-обчислювач без довільного `eval` (Req 12.4).
- LLM обмежений `allowed_tools`; факти — з даних, не з генерації (anti-hallucination, Req 7.3).
- Доступ до Google Sheets — через сервісний акаунт (`GOOGLE_CREDS_PATH` JSON-ключ у `.gitignore`, `GOOGLE_SHEET_ID` з env); бот лише читає матрицю.
- Admin-панель: вимкнена за замовчуванням; логін+пароль (bcrypt-хеш у `.env`, не відкритий пароль); сесія в підписаному cookie; запис лише у `bots/` (захист від path traversal); секрети не показуються й не редагуються через панель.
- Валідація/екранування вводу перед розрахунками, повідомленнями й запитами до Gateway.

## Testing Strategy

- **Unit:** валідація кожної з 6 секцій (валідні/невалідні); `RuleEngine` (вирази, похідні, помилки); парсер `dimension`; FAQ matcher; маскування логів.
- **Unit:** `GoogleSheetsCatalog` з мок-`gspread`: мапінг рядків у `CatalogItem`, фільтр `active=false`, кеш (повторний виклик у межах TTL не йде в мережу), fallback на `LocalCatalog`; `find_item` для неіснуючої позиції повертає «не знайдено».
- **Unit:** `CatalogItem` — ціна без `source_name` відхиляється валідатором; ціна з джерелом проходить.
- **Unit:** `KiroGatewayProvider` з мок-`httpx` (успішна відповідь; tool_call; таймаут → fallback), перевірка контракту (`/v1/chat/completions`, `Bearer`, модель `claude-opus-4.7`).
- **Unit:** `ConfigLoader` — дублі токенів, пропуск невалідних, логування версій секцій.
- **Unit:** `Scraper` з мок-`SourceAdapter`: рядок без `source_name`/`source_url` не пишеться; апсерт без дублів за ключем; застарілі рядки → `active=false`; збій одного джерела не псує інші.
- **Integration:** проходження flow (menu → question → capability → prepare_request) з `InMemoryStorage` і `FallbackProvider`, без реального Telegram (мок `Application`/`Update`).
- **Integration:** anti-hallucination — модель просить недозволений tool → відмова; ціна береться з матриці РАЗОМ із магазином-джерелом, а не з тексту.
- **Integration:** `ResultDelivery` віддає документ користувачу; увімкнений `TelegramManagerSink` (успіх; невдача → локальне збереження + ретрай); відновлення станів після «рестарту».
- **Smoke:** усі 5 прикладів конфігів проходять валідацію всіх секцій (Req 13.4).
- **Admin:** `verify_login` (вірний/невірний пароль); захищені маршрути без сесії → редірект на `/login`; `BotGenerator` з мок-Gateway (валідний YAML пишеться; невалідний → повтор, файл не пишеться); санітизація `name` і заборона запису поза `bots/`; токен не відображається.
- **DialogLogger:** з мок-`gspread`: вимкнено (`DIALOG_LOG_ENABLED=false`) → нічого не пишеться; увімкнено → аркуш `log_<bot_name>` + заголовок, рядок `in`/`out`; Sheets недоступний → тихо пропускає.
- **Booking:** `SlotService` — вільні слоти виключають зайняті записи; «Будь-який майстер» об'єднує слоти; `DemoSeeder` створює N майстрів; скасування звільняє слот; телефон/ім'я запитуються лише на кроці запису; CRM-зміни впливають на слоти.
- Тести запускаються одноразово (`pytest`), без watch-режиму.
