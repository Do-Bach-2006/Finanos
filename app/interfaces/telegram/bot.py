"""
Telegram bot setup.
Creates the Telegram application, registers handlers, and starts polling.
"""
from telegram.ext import ApplicationBuilder
from telegram.request import HTTPXRequest
from app.config import config
from app.interfaces.telegram.handlers import get_conversation_handler, get_view_handlers
from app.utils.logging import logger

async def start_telegram_bot():
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set. Telegram bot will not start.")
        return
        
    logger.info("Initializing Telegram bot with robust 20-second connection timeouts...")
    request_config = HTTPXRequest(connect_timeout=20.0, read_timeout=20.0)
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).request(request_config).build()
    
    # Add conversation handler
    app.add_handler(get_conversation_handler())
    for handler in get_view_handlers():
        app.add_handler(handler)
    
    # Start polling
    logger.info("Starting Telegram polling...")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
