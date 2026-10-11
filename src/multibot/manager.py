from __future__ import annotations
import logging
import os
from functools import partial

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, BotCommand, InputFile,
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

from .config.sections import BotConfig
from .context import BotContext
from .core.ai_orchestrator import AIOrchestrator
from .core.capabilities.registry import CapabilityRegistry
from .core.catalog import make_catalog_provider
from .core.dialog_log import log_message
from .core.flow import FlowEngine, BotResponse
from .core.integrations.delivery import ResultDelivery
from .core.knowledge import KnowledgeBase
from .core.providers.kiro_gateway import FallbackProvider, KiroGatewayProvider
from .core.rules import RuleEngine
from .core.storage import Storage

logger = logging.getLogger(__name__)

RESTART_BUTTON = "\U0001f504 Почати спочатку"
_REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton(RESTART_BUTTON)]],
    resize_keyboard=True,
    input_field_placeholder="Напишіть або оберіть дію...",
)


def _make_reply_markup(keyboard: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup | None:
    if not keyboard:
        return None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=data) for label, data in row]
        for row in keyboard
    ])


def _safe_text(text: str) -> str:
    return text.encode("utf-16", "surrogatepass").decode("utf-16").encode("utf-8", "ignore").decode("utf-8")


async def _send_response(message_or_query, response: BotResponse, is_callback: bool = False):
    markup = _make_reply_markup(response.keyboard)
    if is_callback:
        send_text = message_or_query.message.reply_text
        send_doc = message_or_query.message.reply_document
    else:
        send_text = message_or_query.reply_text
        send_doc = message_or_query.reply_document

    await send_text(_safe_text(response.text), reply_markup=markup, parse_mode="HTML")
    if response.document:
        import io
        await send_doc(
            document=InputFile(io.BytesIO(response.document), filename=response.document_name),
            caption="📄 Ваш розрахунок у PDF",
        )


def _build_context(cfg: BotConfig, storage: Storage, settings) -> BotContext:
    catalog = make_catalog_provider(
        cfg.knowledge.sheets,
        cfg.knowledge.catalog,
        settings.google_creds_path,
    )
    knowledge = KnowledgeBase(cfg.knowledge, catalog)
    rules = RuleEngine()
    capabilities = CapabilityRegistry(cfg.capabilities, knowledge, rules, cfg.knowledge)

    if settings.kiro_gateway_url and settings.kiro_gateway_api_key:
        provider = KiroGatewayProvider(
            settings.kiro_gateway_url,
            settings.kiro_gateway_api_key,
            settings.kiro_gateway_model,
        )
    else:
        logger.warning(f"[{cfg.name}] Kiro Gateway not configured, using fallback")
        provider = FallbackProvider()

    ai = AIOrchestrator(cfg.ai_policy, cfg.assistant_profile, knowledge, capabilities, provider)

    log_fn = partial(
        log_message,
        enabled=settings.dialog_log_enabled,
        sheet_id=settings.dialog_log_sheet,
        creds_path=settings.google_creds_path,
    )

    flow_engine = FlowEngine(
        cfg.conversation_flows, storage, capabilities, ai, cfg.name, log_fn
    )
    delivery = ResultDelivery()

    return BotContext(cfg, knowledge, capabilities, ai, flow_engine, delivery, storage)


class BotManager:
    def __init__(self, configs: list[BotConfig], storage: Storage, settings):
        self._configs = configs
        self._storage = storage
        self._settings = settings
        self._apps: list[Application] = []

    def _make_handlers(self, ctx: BotContext):

        async def _do_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await ctx.storage.clear_state(ctx.config.name, update.effective_user.id)
            profile = ctx.config.assistant_profile
            text = _safe_text(f"👋 {profile.assistant_role}\n\nℹ️ {profile.disclaimer}")
            # Persistent restart keyboard
            await update.message.reply_text(text, reply_markup=_REPLY_KEYBOARD, parse_mode="HTML")
            # Inline menu
            menu = ctx.flow_engine._menu_response()
            await update.message.reply_text(
                menu.text,
                reply_markup=_make_reply_markup(menu.keyboard),
            )
            log_message(
                ctx.config.name, update.effective_user.id, "out", text,
                enabled=self._settings.dialog_log_enabled,
                sheet_id=self._settings.dialog_log_sheet,
                creds_path=self._settings.google_creds_path,
            )

        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await _do_start(update, context)

        async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            admin_id = self._settings.admin_chat_id
            if admin_id and str(update.effective_user.id) != str(admin_id):
                return
            data = await ctx.storage.stats(ctx.config.name)
            text = f"📊 {ctx.config.name}:\n" + "\n".join(f"• {k}: {v}" for k, v in data.items()) or "Немає даних"
            await update.message.reply_text(text)

        async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            text = update.message.text or ""
            # Persistent restart button
            if text == RESTART_BUTTON:
                await _do_start(update, context)
                return
            log_message(
                ctx.config.name, user_id, "in", text,
                enabled=self._settings.dialog_log_enabled,
                sheet_id=self._settings.dialog_log_sheet,
                creds_path=self._settings.google_creds_path,
            )
            try:
                response = await ctx.flow_engine.handle(user_id, text)
            except Exception as e:
                logger.error(f"[{ctx.config.name}] Handler error: {e}", exc_info=True)
                response = BotResponse("Виникла помилка. Спробуйте ще раз або введіть /start")
            await _send_response(update.message, response)
            log_message(
                ctx.config.name, user_id, "out", response.text,
                enabled=self._settings.dialog_log_enabled,
                sheet_id=self._settings.dialog_log_sheet,
                creds_path=self._settings.google_creds_path,
            )

        async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()
            user_id = query.from_user.id
            data = query.data or ""
            log_message(
                ctx.config.name, user_id, "in", data,
                enabled=self._settings.dialog_log_enabled,
                sheet_id=self._settings.dialog_log_sheet,
                creds_path=self._settings.google_creds_path,
            )
            try:
                response = await ctx.flow_engine.handle(user_id, data)
                await _send_response(query, response, is_callback=True)
            except Exception as e:
                import traceback
                err_msg = f"Button error data={repr(data)}: {e}\n{traceback.format_exc()}"
                logger.error(f"[{ctx.config.name}] {err_msg}")
                try:
                    with open("/tmp/bot_errors.log", "a") as f:
                        f.write(err_msg + "\n---\n")
                except Exception:
                    pass
                try:
                    await query.message.reply_text("Виникла помилка. Спробуйте ще раз.")
                except Exception:
                    pass
                return
            log_message(
                ctx.config.name, user_id, "out", response.text,
                enabled=self._settings.dialog_log_enabled,
                sheet_id=self._settings.dialog_log_sheet,
                creds_path=self._settings.google_creds_path,
            )

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"[{ctx.config.name}] Telegram error: {context.error}", exc_info=context.error)

        return start, stats_cmd, message, button, error_handler

    def build(self) -> None:
        seen_tokens: dict[str, str] = {}
        for cfg in self._configs:
            token = os.environ.get(cfg.token_env, "")
            if not token:
                logger.warning(f"[manager] Skipping '{cfg.name}': token_env '{cfg.token_env}' not set")
                continue
            if token in seen_tokens:
                logger.error(f"[manager] Skipping '{cfg.name}': duplicate token with '{seen_tokens[token]}'")
                continue
            seen_tokens[token] = cfg.name

            ctx = _build_context(cfg, self._storage, self._settings)
            app = Application.builder().token(token).build()

            start, stats_cmd, message, button, error_handler = self._make_handlers(ctx)
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("stats", stats_cmd))
            app.add_handler(CallbackQueryHandler(button))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
            app.add_error_handler(error_handler)

            self._apps.append(app)
            logger.info(f"[manager] Bot '{cfg.name}' ready")

    async def run_all(self) -> None:
        import asyncio
        if not self._apps:
            logger.error("[manager] No bots to run")
            return

        async def run_one(app: Application):
            await app.initialize()
            try:
                await app.bot.set_my_commands([
                    BotCommand("start", "\U0001f504 Почати спочатку"),
                ])
            except Exception as e:
                logger.warning(f"set_my_commands failed: {e}")
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info(f"[manager] Bot started: {app.bot.username if app.bot else '?'}")

        await asyncio.gather(*[run_one(app) for app in self._apps])

        import signal
        stop_event = asyncio.Event()

        def _stop(*_):
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, _stop)
            except NotImplementedError:
                pass

        await stop_event.wait()
        await self.shutdown()

    async def shutdown(self) -> None:
        import asyncio
        for app in self._apps:
            try:
                await app.updater.stop()
                await app.stop()
                await app.shutdown()
            except Exception as e:
                logger.warning(f"[manager] Shutdown error: {e}")
        logger.info("[manager] All bots stopped")
