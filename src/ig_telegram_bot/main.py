from __future__ import annotations

import hashlib
import logging
import os
import time

from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from .config import ConfigurationError, Settings
from .service import InstagramBotService

_STARTED_AT = time.monotonic()


def _format_uptime(seconds: int) -> str:
    hours, remainder = divmod(max(0, seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} ساعت و {minutes} دقیقه"
    if minutes:
        return f"{minutes} دقیقه و {secs} ثانیه"
    return f"{secs} ثانیه"


async def _status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if not update.effective_message:
        return
    uptime = int(time.monotonic() - _STARTED_AT)
    await update.effective_message.reply_text(
        "🟢 وضعیت ربات: آنلاین\n"
        f"⏱ زمان فعالیت: {_format_uptime(uptime)}\n"
        "⚡ سرویس آماده دریافت لینک Instagram است."
    )


def _webhook_security(settings: Settings) -> tuple[str, str]:
    configured_secret = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()
    secret = configured_secret or hashlib.sha256(
        f"telegram-webhook:{settings.telegram_bot_token}".encode()
    ).hexdigest()
    configured_path = os.getenv("WEBHOOK_PATH", "").strip("/")
    path = configured_path or f"telegram-{secret[:24]}"
    return path, secret


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(
        [
            BotCommand("start", "شروع ربات"),
            BotCommand("help", "راهنمای استفاده"),
            BotCommand("status", "وضعیت ربات"),
            BotCommand("privacy", "حریم خصوصی"),
        ]
    )


def build_application(settings: Settings) -> Application:
    service = InstagramBotService(settings)
    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .concurrent_updates(8)
        .connection_pool_size(16)
        .pool_timeout(30)
        .connect_timeout(15)
        .read_timeout(60)
        .write_timeout(120)
        .media_write_timeout(120)
        .post_init(_post_init)
        .build()
    )
    application.add_handler(CommandHandler("start", service.start))
    application.add_handler(CommandHandler("help", service.help))
    application.add_handler(CommandHandler("status", _status_handler))
    application.add_handler(CommandHandler("privacy", service.privacy))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, service.handle_text))
    return application


def main() -> None:
    load_dotenv()
    try:
        settings = Settings.from_environment()
    except ConfigurationError as exc:
        raise SystemExit(f"خطای تنظیمات: {exc}") from exc

    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    application = build_application(settings)

    external_url = (
        os.getenv("RENDER_EXTERNAL_URL", "").strip().rstrip("/")
        or os.getenv("WEBHOOK_BASE_URL", "").strip().rstrip("/")
    )

    if external_url:
        port = int(os.getenv("PORT", "10000"))
        webhook_path, webhook_secret = _webhook_security(settings)
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=webhook_path,
            webhook_url=f"{external_url}/{webhook_path}",
            secret_token=webhook_secret,
            allowed_updates=[Update.MESSAGE],
            drop_pending_updates=False,
        )
    else:
        application.run_polling(
            allowed_updates=[Update.MESSAGE],
            drop_pending_updates=False,
        )


if __name__ == "__main__":
    main()
