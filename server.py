"""
Main application entry point.
Starts the local server, loads configuration, initializes services,
connects the Telegram bot, and prepares the app runtime.
"""

import asyncio
import uvicorn
from fastapi import FastAPI

from app.config import config
from app.utils.logging import logger
from app.bootstrap import bootstrap_app

app = FastAPI(title="FinanOS", description="Personal Finance Management API")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting FinanOS server...")
    await bootstrap_app(app)

def main():
    logger.info(f"Starting web server in {config.APP_ENV} mode")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=(config.APP_ENV == "local"))

if __name__ == "__main__":
    main()
