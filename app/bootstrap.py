"""
Application bootstrap logic.
Wires together repositories, services, integrations, and interfaces.
Keeps startup setup out of server.py.
"""
from fastapi import FastAPI
import asyncio
from app.utils.logging import logger
from app.storage.database import init_db
from app.interfaces.telegram.bot import start_telegram_bot
from app.interfaces.web.routes import router as web_router

async def bootstrap_app(app: FastAPI):
    logger.info("Bootstrapping application components...")
    
    # Initialize Database
    init_db()
    logger.info("Database initialized.")
    
    # Initialize Bounded Activity Queue
    from app.storage.activity_buffer import init_activity_queue
    init_activity_queue()
    logger.info("Bounded Activity Queue seeded.")
    
    # Register Web Interface APIRouter
    app.include_router(web_router)
    logger.info("Web interface routes registered.")
    
    # Initialize Telegram Bot in the background
    asyncio.create_task(start_telegram_bot())
    logger.info("Telegram bot started.")
    
    logger.info("Application bootstrap complete.")
