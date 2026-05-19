"""
Forex Market Service.
Fetches live exchange rates for converting multiple currencies to the default currency.
"""
import requests
import time
from app.utils.logging import logger
from my_logic.api_logics import Caching, API_value
import os

# Ensure data directory exists for caching saving (if utilized by Caching)
os.makedirs("./data/api", exist_ok=True)

_forex_cache = Caching(max_size=100, save_path="./data/api/forex_cache.json")
_cache_duration = 3600  # 1 hour in seconds

def get_exchange_rate(base_currency: str, target_currency: str) -> float:
    """
    Fetches the live exchange rate. 
    Uses open.er-api for free live rates with a robust 1-hour in-memory cache and safe fallbacks.
    """
    base_currency = base_currency.upper().strip()
    target_currency = target_currency.upper().strip()
    
    if base_currency == target_currency:
        return 1.0
        
    global _forex_cache
    now = time.time()
    
    # Check cache
    cached_val = _forex_cache.get_by_key(base_currency)
    if cached_val:
        if now - cached_val.last_fetched < _cache_duration:
            rates = cached_val.value
            if target_currency in rates:
                return float(rates[target_currency])
                
    # Cache miss - fetch live exchange rate
    try:
        logger.info(f"[Forex] Fetching exchange rates for base currency {base_currency}")
        url = f"https://open.er-api.com/v6/latest/{base_currency}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            rates = data.get("rates", {})
            if rates:
                _forex_cache.set_value(base_currency, API_value(name=base_currency, value=rates, time=now))
                if target_currency in rates:
                    return float(rates[target_currency])
    except Exception as e:
        logger.error(f"Failed to fetch exchange rate {base_currency}->{target_currency}: {e}")
        
    # Safe fallbacks if API is down / DNS fails
    fallbacks = {
        ("USD", "VND"): 25400.0,
        ("EUR", "VND"): 27500.0,
        ("GBP", "VND"): 32000.0,
        ("VND", "USD"): 1/25400.0,
    }
    return fallbacks.get((base_currency, target_currency), 1.0)
