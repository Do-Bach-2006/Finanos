"""
Runtime configuration loader.
Reads values from .env and exposes them through one central config object.
"""
import os
from dotenv import load_dotenv

# Ensure we load from the environment or .env file
load_dotenv()

class Config:
    # App
    APP_ENV = os.getenv("APP_ENV", "local")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///finanos.db")
    DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "VND")
    
    # Intelligence
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_API_KEYS = [k.strip() for k in GEMINI_API_KEY.split(",")] if GEMINI_API_KEY else []
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Firefly III
    FIREFLY_BASE_URL = os.getenv("FIREFLY_BASE_URL")
    FIREFLY_TOKEN = os.getenv("FIREFLY_TOKEN")

    # Crypto APIs
    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")
    COINMARKETCAP_API_KEY = os.getenv("COINMARKETCAP_API_KEY")

    # Stocks / ETFs / Commodities
    FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
    ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

    # Forex APIs
    EXCHANGERATE_API_KEY = os.getenv("EXCHANGERATE_API_KEY")
    CURRENCYFREAKS_API_KEY = os.getenv("CURRENCYFREAKS_API_KEY")

    # CS2 Market
    CS2_MARKET_PROVIDER = os.getenv("CS2_MARKET_PROVIDER")
    CS2_MARKET_API_KEY = os.getenv("CS2_MARKET_API_KEY")

config = Config()
