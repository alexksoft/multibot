# Implementation Plan

- [ ] 1. Ініціалізація проєкту та базова структура
  - Створити структуру: `src/multibot/{core,core/capabilities,core/providers,core/integrations,core/booking,config}`, `scraper/`, `admin/` (+`admin/templates`), `bots/`, `tests/`
  - Додати `pyproject.toml` з залежностями (`python-telegram-bot>=21`, `pydantic>=2`, `pydantic-settings`, `pyyaml`, `httpx`, `gspread==6.1.2`, `fastapi`, `uvicorn`, `jinja2`, `passlib[bcrypt]`, `itsdangerous`, `python-dotenv`, `pytest`, `pytest-asyncio`) — `gspread` тієї ж версії, що в `Chatbot_whatsapp_faq`
  - Додати `.gitignore` (`.env`, `*.db`, `__pycache__`), оновити `.env.example`
  - _Requirements: 12.1, 12.2_

- [ ] 2. Налаштування процесу (Settings) і секрети
  - Реалізувати `Settings` на `pydantic-settings`: `KIRO_GATEWAY_URL`, `KIRO_GATEWAY_API_KEY`, `KIRO_GATEWAY_MODEL` (default `claude-opus-4.7`), `GOOGLE_CREDS_PATH`, `GOOGLE_SHEET_ID`, `DIALOG_LOG_ENABLED`, `DIALOG_LOG_SHEET_ID`, `BOTS_DIR`, `ADMIN_CHAT_ID`, `ADMIN_ENABLED`, `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH`, `ADMIN_HOST`, `ADMIN_PORT`, `ADMIN_SESSION_SECRET`, `LOG_LEVEL`, `DB_PATH` (аналогічно референсному `app/config/settings.py`)
  - _Requirements: 8.1, 8.2, 8.5, 12.1, 6.5, 15.1, 15.3, 16.1, 16.7_

- [ ] 3. Pydantic-схеми 6 секцій конфігурації
  - [ ] 3.1 `AssistantProfile` (`series_name`, `assistant_role`, `industry`, `target_user`, мова, тон, нейтральний `disclaimer`, `developer_note`) з `version` — без назви/контактів вигаданої компанії
    - _Requirements: 2.1, 2.3, 3.1, 3.2, 3.5_
  - [ ] 3.2 `ConversationFlows` (`Flow`, `Step`, `Transition`, cancel-команди) з `version` і валідацією (унікальні id кроків, коректні `next`/`goto`)
    - _Requirements: 2.1, 4.1, 4.4_
  - [ ] 3.3 `Capabilities` (`CapabilityRef` з allow-list імен: calculate_materials/search_products/shopping_list/checklist/questions_for_pro/compare_options/prepare_request, + параметри) з `version`
    - _Requirements: 2.1, 5.1, 5.5_
  - [ ] 3.4 `KnowledgeData` (`FAQItem`, `CatalogItem` [category|item|price|unit|source_name|source_url|collected_at|active|notes] з валідатором «price вимагає source_name», `SheetsSource`, `CalculationRule`, `norms`) з `version`
    - _Requirements: 2.1, 6.1, 6.2, 6.3, 6.4, 6.7_
  - [ ] 3.5 `AIPolicy` (`system_prompt`, `model`, `allowed_tools`, `max_tokens`, `forbidden_advice`, `clarify_when_unsure`) з `version`
    - _Requirements: 2.1, 7.1, 7.2, 7.4, 7.5_
  - [ ] 3.6 `Integrations` (`RequestField`, `deliver_to_user`, `IntegrationSink` з `enabled=false`) з `version` і `BotConfig`, що зв'язує 6 секцій + `token_env` (`assistant_profile`)
    - _Requirements: 2.1, 9.1, 9.3, 9.5_
  - [ ] 3.7 Unit-тести валідації кожної секції (валідні/невалідні, узгодженість `choice`+`options`, діапазони)
    - _Requirements: 2.2, 2.4_

- [ ] 4. ConfigLoader (6-секційні YAML)
  - Читати `bots/*.yaml`, валідувати секції окремо, логувати їх `version`, пропускати невалідні боти зі зрозумілою помилкою
  - Unit-тести: валідний конфіг, помилка в одній секції (бот пропускається), порожній каталог
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 13.1_

- [ ] 5. Логування та маскування секретів
  - Структуроване логування (`bot_name`, `industry`, тип події); фільтр маскування токенів, `KIRO_GATEWAY_API_KEY`, телефонів
  - Unit-тести маскування
  - _Requirements: 11.1, 11.2, 12.3_

- [ ] 6. Сховище (Storage)
  - [ ] 6.1 Протокол `Storage` + `SqliteStorage` (`dialog_state`, `results`, `counters`; booking-таблиці `services`/`masters`/`appointments`/`clients` додаються в завданні 20a): `get_state`/`save_state`/`clear_state`/`save_result`/`incr_counter`/`stats`
    - _Requirements: 10.1, 10.3, 11.3_
  - [ ] 6.2 `InMemoryStorage` для тестів
    - _Requirements: 10.1_
  - [ ] 6.3 Unit-тести: збереження/читання стану, відновлення після «рестарту», результат, лічильники
    - _Requirements: 10.2, 10.3, 11.3_

- [ ] 7. Безпечний обчислювач виразів і RuleEngine
  - [ ] 7.1 AST allow-list обчислювач (`+ - * / **`, `round`, `min`, `max`, числа, змінні) без довільного `eval`
    - _Requirements: 12.4_
  - [ ] 7.2 `RuleEngine`: обчислення `calculation_rules`, похідні для `dimension` (`*_width/_length/_area/_perimeter`), доступ до `norms`, округлення, пропуск помилкового правила
    - _Requirements: 5.7, 6.10_
  - [ ] 7.3 Unit-тести: коректні вирази, похідні, невалідний вираз, заборона небезпечних конструкцій
    - _Requirements: 5.7, 12.4_

- [ ] 8. CatalogProvider: матриця реальних даних у Google Sheets
  - [ ] 8.1 `CatalogProvider` (Protocol), `GoogleSheetsCatalog` через `gspread.service_account(GOOGLE_CREDS_PATH)` + `open_by_key(GOOGLE_SHEET_ID)`; мапінг заголовка `category|item|price|unit|source_name|source_url|collected_at|active|notes` у `CatalogItem`; відкидання рядка з `price` без `source_name`; фільтр `active=false`; кеш на `cache_ttl_seconds`
    - _Requirements: 6.2, 6.3, 6.4, 6.5, 6.7, 6.8_
  - [ ] 8.2 `LocalCatalog` (резерв із `knowledge.catalog`) і graceful fallback: Sheets недоступний/не налаштований → останній кеш → LocalCatalog, попередження, без вигаданих даних
    - _Requirements: 6.9_
  - [ ] 8.3 Unit-тести з мок-`gspread`: мапінг рядків, відкидання ціни без джерела, фільтр активності, кеш (у межах TTL без мережі), fallback на LocalCatalog
    - _Requirements: 6.3, 6.4, 6.7, 6.9_

- [ ] 9. KnowledgeBase
  - FAQ matcher (keyword + нормалізація, пріоритет над LLM); `list_items(category)`/`find_item()` поверх `CatalogProvider` — повертають ЛИШЕ активні позиції; кожна ціна з `source_name`/`source_url`/`collected_at`; неіснуюча позиція → «не знайдено» + альтернативи (без вигадування); постачання `norms` у RuleEngine
  - Unit-тести: збіг FAQ, пошук активної позиції з джерелом, запит неіснуючої позиції (не знайдено), відсутні дані
  - _Requirements: 6.1, 6.2, 6.3, 6.5, 6.6, 6.10_

- [ ] 9a. DialogLogger (лог бесід у Google Sheets)
  - `core/dialog_log.py`: `log_message(bot_name, user_id, direction, text, flow_id, step_id)` — фоновий потік; окремий аркуш `log_<bot_name>` (створення + `_ensure_header` з `[timestamp, bot_name, user_id, direction, flow_id, step_id, text]`); `append_row`; той самий сервісний акаунт + `DIALOG_LOG_SHEET_ID`; УВІМКНЕНО за замовчуванням (обов'язкове); graceful degradation якщо Sheets недоступний; у лог не потрапляють токени/ключі
  - Unit-тести з мок-`gspread`: увімкнено (дефолт) → аркуш+заголовок+рядок in/out; явно вимкнено → не пишеться; Sheets недоступний → тихо пропускає
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5, 16.6, 16.7, 16.8, 16.9_

- [ ] 10. KiroGatewayProvider і Fallback
  - [ ] 10.1 `FallbackProvider` (без мережі: FAQ + шаблони)
    - _Requirements: 8.4_
  - [ ] 10.2 `KiroGatewayProvider`: `POST {url}/v1/chat/completions`, `Authorization: Bearer`, body `{model, messages, max_tokens, [tools]}`, парсинг `choices[0].message`; `httpx.AsyncClient` таймаут/ретраї; default `claude-opus-4.7`; перемикання на fallback при помилці; режим без LLM якщо gateway не налаштований
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_
  - [ ] 10.3 Unit-тести з мок-`httpx`: нормальна відповідь, tool_call, таймаут → fallback, перевірка контракту (ендпоінт/заголовок/модель)
    - _Requirements: 8.1, 8.2, 8.4_

- [ ] 11. CapabilityRegistry і вбудовані функції
  - [ ] 11.1 Протокол `Capability` + реєстр; дозволено викликати лише включені в конфіг capability
    - _Requirements: 5.1, 5.2, 5.4_
  - [ ] 11.2 `calculate_materials` (через `RuleEngine` + `norms`) і `search_products` (через `KnowledgeBase`; ціна завжди з `source_name`)
    - _Requirements: 5.1, 5.7, 6.2, 6.3_
  - [ ] 11.3 `shopping_list` (список покупок: кількість × ціна з магазином-джерелом), `checklist` (чекліст за `params.template`), `questions_for_pro` (питання до майстра), `compare_options` (порівняння з матриці)
    - _Requirements: 5.1, 5.5, 6.3_
  - [ ] 11.4 `prepare_request` — формує готовий документ (ТЗ/список/заявку) для САМОГО користувача, передає в `ResultDelivery`
    - _Requirements: 5.5, 5.6, 9.1_
  - [ ] 11.5 Unit-тести: валідні/невалідні входи, заборона невключеної capability, `shopping_list`/`compare_options` показують ціну з джерелом
    - _Requirements: 5.2, 5.3, 5.4, 6.3_

- [ ] 12. AIOrchestrator (AI Policy)
  - Будувати запит: `system_prompt` + контекст (assistant profile, факти з Knowledge, історія); function-calling лише з `allowed_tools`; факти з capability/Knowledge (anti-hallucination); `forbidden_advice` → до фахівця + питання до нього; `clarify_when_unsure` → уточнення
  - Integration-тести: недозволений tool відхилено; ціна з матриці Sheets разом із магазином-джерелом, не з тексту; заборонена порада → перенаправлення до фахівця
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [ ] 13. FlowEngine (Conversation Flows)
  - [ ] 13.1 Виконання `Flow` покроково (`message`/`question`/`capability`/`handoff`), валідація відповідей за типом/діапазоном, повтор при помилці, збереження у `save_as`; виклик `DialogLogger.log_message` на вхід (`in`) і на вихід (`out`)
    - _Requirements: 4.1, 4.2, 4.3, 16.4, 16.9_
  - [ ] 13.2 Умовні переходи `transitions[].when` (безпечний обчислювач над `collected`), лінійний `next`, динамічне меню з доступних flows, обробка cancel-команд
    - _Requirements: 4.4, 4.5, 4.6_
  - [ ] 13.3 Збереження/відновлення стану через `Storage`, таймаут сесії
    - _Requirements: 10.1, 10.2, 10.4_
  - [ ] 13.4 Integration-тести: повний прохід flow (menu → question → capability → prepare_request), скасування, відновлення після рестарту
    - _Requirements: 4.1, 4.5, 10.2_

- [ ] 14. ResultDelivery (видача результату користувачу + опційні sink'и)
  - [ ] 14.1 `PreparedResult` + `UserChatDelivery` (завжди увімкнено): форматує документ і надсилає користувачу; ціни з магазином-джерелом
    - _Requirements: 9.1, 9.2_
  - [ ] 14.2 `TelegramManagerSink` (реалізовано, `enabled=false` за замовчуванням) + заглушки `CrmWebhookSink`/`EmailSink`; нереалізований/невключений sink позначається недоступним при валідації; увімкнений sink: невдача → локальне збереження + ретрай
    - _Requirements: 9.3, 9.4, 9.5_
  - [ ] 14.3 Бот НЕ стверджує «передано компанії» без реального отримувача; інкремент лічильника результатів
    - _Requirements: 9.6, 11.3_
  - [ ] 14.4 Integration-тести: видача користувачу; увімкнений sink — успіх і невдача (локальне збереження + ретрай); відсутність хибного «передано компанії»
    - _Requirements: 9.1, 9.4, 9.6_

- [ ] 15. Адмін-команди та статистика
  - `/stats` з авторизацією за `ADMIN_CHAT_ID`; кількість діалогів/заявок зі `Storage`
  - Тести авторизації
  - _Requirements: 11.4_

- [ ] 16. BotManager і зв'язування хендлерів
  - [ ] 16.1 `load()` (конфіги + унікальність токенів) і `start_all()` (`Application` на бот, спільні хендлери з `BotContext`, що тримає 6 секцій + залежності)
    - _Requirements: 1.1, 1.2, 1.3_
  - [ ] 16.2 Ізоляція збоїв (`error_handler` на рівні Application) + graceful shutdown по сигналу
    - _Requirements: 1.4, 1.5_
  - [ ] 16.3 Integration-тест багатоботовості з мок-`Application` (дубль токена відхиляється; збій одного не впливає на інших)
    - _Requirements: 1.3, 1.4_

- [ ] 17. Точка входу (main.py)
  - Зчитати `.env`/`Settings`, зібрати залежності (`Storage`, `CatalogProvider`, `KiroGatewayProvider`/`FallbackProvider`, `ResultDelivery`, `DialogLogger`), запустити `BotManager`; коректна обробка сигналів
  - _Requirements: 1.1, 1.5, 8.5_

- [ ] 18. Скрейпер реальних даних у матрицю Google Sheets (окремий компонент)
  - [ ] 18.1 `SourceAdapter` (Protocol) + `ScrapedRow` (обов'язкові `source_name`/`source_url`/`collected_at`); базовий HTTP-клієнт на `httpx` з повагою до `robots.txt`, паузами й коректним User-Agent
    - _Requirements: 14.1, 14.2, 14.4, 14.5_
  - [ ] 18.2 `SheetsWriter` (`gspread.service_account(GOOGLE_CREDS_PATH)` + `open_by_key`): апсерт без дублів (ключ `category+item+source_name`), застарілі рядки → `active=false`; рядок без джерела не пишеться
    - _Requirements: 14.2, 14.3, 14.6, 14.9_
  - [ ] 18.3 CLI `python -m scraper run [--category ...]` + конфіг `scraper/config.yaml`; стійкість: збій/зміна формату джерела логується й пропускається, валідні дані не псуються
    - _Requirements: 14.1, 14.7, 14.8_
  - [ ] 18.4 Принаймні 1-2 реальні `SourceAdapter` під будівельну нішу (пріоритет №1) як приклад
    - _Requirements: 14.1, 14.2_
  - [ ] 18.5 Unit-тести з мок-`SourceAdapter`/мок-`gspread`: рядок без джерела не пишеться; апсерт без дублів; застарілі → `active=false`; збій джерела не псує інші
    - _Requirements: 14.2, 14.3, 14.6, 14.8_

- [ ] 19. Приклади конфігурацій серії Practical AI Assistants (6 секцій кожна)
  - `bots/building.yaml` (пріоритет №1), `bots/furniture.yaml`, `bots/auto_service.yaml`, `bots/windows.yaml`, `bots/beauty.yaml`
  - building/windows — з `calculation_rules`; усі з матрицею `knowledge.sheets` і `prepare_request`; у кожного власний `ai_policy.system_prompt` і нейтральний disclaimer; sink'и вимкнені
  - Smoke-тест: усі приклади проходять валідацію всіх 6 секцій
  - _Requirements: 13.4, 2.1, 2.2, 3.2_

- [ ] 20. Admin-панель (FastAPI, окремий процес)
  - [ ] 20.1 Застосунок FastAPI + Jinja2-шаблони; запуск лише коли `ADMIN_ENABLED=true`, слухає `ADMIN_HOST`/`ADMIN_PORT`; `python -m admin` як точка входу (окремо від ботів)
    - _Requirements: 15.1, 15.12_
  - [ ] 20.2 Автентифікація: `verify_login` (bcrypt через `passlib`), `/login` GET/POST, `/logout`, сесія в підписаному cookie (`SessionMiddleware`); залежність `require_session` для захищених маршрутів; CLI `python -m admin hash-password`
    - _Requirements: 15.2, 15.3_
  - [ ] 20.3 `BotCatalogView`: `/` список ботів із `bots/*.yaml` (name, роль, галузь, мова, flows/capabilities, `sheets.enabled`, наявність токена без значення); `/bot/{name}` картка 6 секцій без секретів; ігнорувати `_*.yaml`
    - _Requirements: 15.4, 15.5, 15.11_
  - [ ] 20.4 `BotGenerator`: майстер `/new` (GET форма; POST обробка) → промт у `KiroGatewayProvider` → YAML → pydantic-валідація (до 2 повторів) → санітизація `name` (`[a-z0-9_]`) → запис ЛИШЕ у `bots/` (захист від path traversal, підтвердження перезапису)
    - _Requirements: 15.6, 15.7, 15.8, 15.9, 15.11_
  - [ ] 20.5 Сторінка результату з інструкцією: @BotFather → `<NAME>_BOT_TOKEN` у `.env` (+ `<NAME>_SHEET_ID`), наповнення скрейпером, перезапуск процесу (без авто-рестарту)
    - _Requirements: 15.10_
  - [ ] 20.6 Тести: `verify_login` (вірний/невірний), захищений маршрут без сесії → `/login`, `BotGenerator` з мок-Gateway (валідний пишеться; невалідний → повтор, файл не пишеться), санітизація `name` і заборона запису поза `bots/`, токен не відображається
    - _Requirements: 15.2, 15.3, 15.8, 15.9, 15.11_

- [ ] 20a. Booking-модуль (фіча-прапорець, демо-дані) — SQLite
  - [ ] 20a.1 `BookingConfig` у схемі конфіга (enabled, provider_term, service_term, demo_masters, contacts_text, intro) + таблиці `services`/`masters`/`appointments`/`clients` у `Storage`
    - _Requirements: 17.1, 17.12, 18.8_
  - [ ] 20a.2 `DemoSeeder`: при першому вмиканні генерує `demo_masters` вигаданих майстрів із послугами/цінами/тривалістю/розкладом (`is_demo=true`)
    - _Requirements: 17.2, 17.11_
  - [ ] 20a.3 `SlotService`: вільні слоти за (майстер, дата) з робочих годин і `duration_min`, виключення зайнятих; «Будь-який майстер» = об'єднання
    - _Requirements: 17.3, 17.4, 18.7_
  - [ ] 20a.4 `BookingFlow` (Telegram inline): меню Записатися/Мої записи/Контакти → послуга→майстер→дата→вільний час → ім'я+телефон (кнопка «Відправити контакт», лише тут) → підсумок → підтвердження → збереження + сповіщення адміну (`ADMIN_CHAT_ID`)
    - _Requirements: 17.1, 17.3, 17.5, 17.6, 17.7, 17.10_
  - [ ] 20a.5 «Мої записи» + «Скасувати» (статус cancelled, слот звільняється); демо-мітки у текстах; термінологія з конфіга
    - _Requirements: 17.8, 17.9, 17.11, 17.12_
  - [ ] 20a.6 Тести: вільні слоти виключають зайняті, «Будь-який» об'єднує, скасування звільняє слот, телефон питається лише на кроці запису, seeder створює N майстрів
    - _Requirements: 17.2, 17.4, 17.5, 17.9_

- [ ] 20b. CRM (розділ admin-панелі)
  - `/crm/appointments` (фільтр дата+майстер, зміна статусу new/confirmed/done/cancelled), `/crm/services` (назва/ціна/тривалість), `/crm/masters` (ім'я/дні/години), `/crm/clients` (ім'я/телефон/історія); під `require_session`; дані SQLite; зміни впливають на слоти
  - Тести: фільтри, зміна статусу, редагування довідників відображається у `SlotService`
  - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5, 18.6, 18.7, 18.8_

- [ ] 21. Документація
  - `README.md`: серія Practical AI Assistants і позиціонування (демо, не реальні компанії); опис секцій конфіга і схем (включно з `booking`); перелік `question_type` і capabilities (включно з `prepare_request`); формат матриці Google Sheets (колонки `category|item|price|unit|source_name|source_url|collected_at|active|notes`) з обов'язковим джерелом ціни; логування бесід; booking-фіча (demo, вмикання, CRM); налаштування сервісного акаунта (`GOOGLE_CREDS_PATH`/`GOOGLE_SHEET_ID`); запуск скрейпера; запуск admin-панелі + CRM (`ADMIN_ENABLED`, логін/пароль, `hash-password`); Kiro Gateway (`KIRO_GATEWAY_URL`/`KIRO_GATEWAY_API_KEY`, Opus 4.7); як додати нову нішу
  - _Requirements: 13.1, 13.2, 13.3, 15.10_

### Рекомендований порядок реалізації ботів

Будівельний (1) → Меблевий (2) → Авто (3) → Вікна (4) → Beauty (5). Для першого релізу кожному боту достатньо 3-4 добре реалізованих сценаріїв, зрозумілого меню, обробки помилок і однієї справді корисної функції.
