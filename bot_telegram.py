import logging
import os

from aiohttp import web as aio_web
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import db
import handlers
import scheduler
import web as web_module

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _post_init(application: Application) -> None:
    port = int(os.environ.get("WEB_PORT", "8080"))
    aiohttp_app = web_module.create_web_app(application.bot)
    runner = aio_web.AppRunner(aiohttp_app)
    await runner.setup()
    site = aio_web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    application.bot_data["web_runner"] = runner
    logger.info(f"Web server started on port {port}")


async def _post_shutdown(application: Application) -> None:
    runner = application.bot_data.get("web_runner")
    if runner:
        await runner.cleanup()
        logger.info("Web server stopped")


async def _error_handler(update, context):
    logger.error(f"Exception in bot: {context.error}", exc_info=context.error)


def main():
    db.init_db()

    token = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env")

    app = (
        Application.builder()
        .token(token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", handlers.cmd_start))
    app.add_handler(CommandHandler("plan", handlers.cmd_plan))
    app.add_handler(CommandHandler("stats", handlers.cmd_stats))
    app.add_handler(CommandHandler("reset", handlers.cmd_reset))
    app.add_handler(CommandHandler("resumen", handlers.cmd_resumen))
    app.add_handler(CommandHandler("ayuda", handlers.cmd_ayuda))
    app.add_handler(CommandHandler("perfil", handlers.cmd_perfil))
    app.add_handler(CommandHandler("borrar", handlers.cmd_borrar))
    app.add_handler(CommandHandler("limpiar", handlers.cmd_limpiar))
    app.add_handler(CommandHandler("coach", handlers.cmd_coach))
    app.add_handler(CallbackQueryHandler(handlers.handle_coach_callback, pattern="^coach_mode:"))
    app.add_handler(MessageHandler(filters.PHOTO, handlers.handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message))
    
    app.add_error_handler(_error_handler)

    scheduler.start_scheduler(app)

    logger.info("Coach Kai is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
