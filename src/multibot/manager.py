from __future__ import annotations
import logging
import os
from functools import partial

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from .config.sections import BotConfig
from .context import BotContext
from .core.ai_orchestrator import AIOrchestrator
from .core.capabilities.registry import CapabilityRegistry
from .core.catalog import make_catalog_provider
from .core.dialog_log import log_message
from .core.flow import FlowEngine
from .core.integrations.delivery import ResultDelivery
from .core.knowledge import KnowledgeBase
from .core.providers.kiro_gateway import FallbackProvider, KiroGatewayProvider
from .core.rules import RuleEngine
from .core.storage import Storage

logger = logging.getLogger(__name__)


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
        async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
            profile = ctx.config.assistant_profile
            text = (
                f"👋 {profile.assistant_role}\n\n"
                f"ℹ️ {profile.disclaimer}\n\n"
                + ctx.flow_engine._build_menu()
            )
            await update.message.reply_text(text)
            log_message(
                ctx.config.name, update.effective_user.id, "out", text,
                enabled=self._settings.dialog_log_enabled,
                sheet_id=self._settings.dialog_log_sheet,
                creds_path=self._settings.google_creds_path,
            )

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
                response = "Виникла помилка. Спробуйте ще раз або введіть /start"
            await update.message.reply_text(response)
            log_message(
                ctx.config.name, user_id, "out", response,
                enabled=self._settings.dialog_log_enabled,
                sheet_id=self._settings.dialog_log_sheet,
                creds_path=self._settings.google_creds_path,
            )

        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"[{ctx.config.name}] Telegram error: {context.error}", exc_info=context.error)

        return start, stats_cmd, message, error_handler

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

            start, stats_cmd, message, error_handler = self._make_handlers(ctx)
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("stats", stats_cmd))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message))
            app.add_error_handler(error_handler)

            self._apps.append(app)
            logger.info(f"[manager] Bot '{cfg.name}' ready")

    async def run_all(self) -> None:
        """Run all bots concurrently using polling."""
        import asyncio
        if not self._apps:
            logger.error("[manager] No bots to run")
            return

        async def run_one(app: Application):
            await app.initialize()
            await app.start()
            await app.updater.start_polling(drop_pending_updates=True)
            logger.info(f"[manager] Bot started: {app.bot.username if app.bot else '?'}")

        await asyncio.gather(*[run_one(app) for app in self._apps])

        # Keep running until interrupted
        import signal
        stop_event = asyncio.Event()

        def _stop(*_):
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_event_loop().add_signal_handler(sig, _stop)
            except NotImplementedError:
                pass  # Windows

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
