"""
Unified market service.
Routes price lookup requests to live integration APIs:
- Cryptocurrencies (via CoinGecko demo API)
- Stocks (via Finnhub API)
- CS2 Items (via Steam Community Market API)
"""
import requests
import urllib.parse
from app.config import config
from app.utils.logging import logger

COINGECKO_MAP = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "bnb": "binancecoin",
    "xrp": "ripple",
    "doge": "dogecoin",
    "dot": "polkadot",
    "ltc": "litecoin",
    "link": "chainlink",
    "avax": "avalanche-2",
    "trx": "tron",
    "shib": "shiba-inu",
    "ton": "the-open-network"
}

class MarketService:
    def __init__(self):
        self._cs2_cache = None

    def get_price(self, symbol: str, market_type: str = "crypto") -> float:
        """
        Fetches the live USD market price of a given symbol or item.
        Returns 0.0 if not found or on error.
        """
        market_type = market_type.lower().strip()
        symbol_clean = symbol.strip()
        
        if market_type == "crypto":
            return self._get_crypto_price(symbol_clean)
        elif market_type == "stock":
            return self._get_stock_price(symbol_clean)
        elif market_type == "cs2":
            return self._get_cs2_price(symbol_clean)
        
        logger.warning(f"[MarketService] Unknown market type: {market_type}")
        return 0.0

    def _get_crypto_price(self, symbol: str) -> float:
        symbol_lower = symbol.lower()
        coin_id = COINGECKO_MAP.get(symbol_lower, symbol_lower)
        
        headers = {}
        if config.COINGECKO_API_KEY:
            headers["x-cg-demo-api-key"] = config.COINGECKO_API_KEY
            
        cg_base = "https://api.coingecko.com/api/v3"
            
        url = f"{cg_base}/simple/price?ids={coin_id}&vs_currencies=usd"
        try:
            logger.info(f"[MarketService] Fetching CoinGecko price for {coin_id}")
            resp = requests.get(url, headers=headers, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            if coin_id in data and "usd" in data[coin_id]:
                return float(data[coin_id]["usd"])
        except Exception as e:
            logger.error(f"[MarketService] CoinGecko price failed for {symbol}: {e}")
            
        # Try a direct search endpoint as fallback
        try:
            search_url = f"{cg_base}/search?query={symbol_lower}"
            resp = requests.get(search_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                coins = resp.json().get("coins", [])
                if coins:
                    found_id = coins[0]["id"]
                    fallback_url = f"{cg_base}/simple/price?ids={found_id}&vs_currencies=usd"
                    r = requests.get(fallback_url, headers=headers, timeout=5)
                    if r.status_code == 200:
                        d = r.json()
                        if found_id in d:
                            return float(d[found_id]["usd"])
        except Exception as e:
            logger.error(f"[MarketService] CoinGecko search fallback failed for {symbol}: {e}")
            
        return 0.0

    def _get_stock_price(self, symbol: str) -> float:
        symbol_upper = symbol.upper()
        
        # 1. Try Alpha Vantage first since it has a verified working key in .env!
        av_key = config.ALPHAVANTAGE_API_KEY or os.environ.get("ALPHAVANTAGE_API_KEY")
        if av_key and av_key.strip():
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol_upper}&apikey={av_key}"
            try:
                logger.info(f"[MarketService] Fetching Alpha Vantage price for {symbol_upper}")
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    quote = data.get("Global Quote", {})
                    price_str = quote.get("05. price")
                    if price_str:
                        return float(price_str)
            except Exception as e:
                logger.error(f"[MarketService] Alpha Vantage price failed for {symbol}: {e}")
                
        # 2. Fallback to Finnhub
        api_key = config.FINNHUB_API_KEY or os.environ.get("FINNHUB_API_KEY")
        if api_key:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol_upper}&token={api_key}"
            try:
                logger.info(f"[MarketService] Fetching Finnhub price for {symbol_upper}")
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if "c" in data and data["c"] > 0:
                        return float(data["c"])
            except Exception as e:
                logger.error(f"[MarketService] Finnhub price failed for {symbol}: {e}")
                
        return 0.0

    def _get_cs2_price(self, item_name: str) -> float:
        if self._cs2_cache is None:
            try:
                logger.info("[MarketService] Loading CS2 prices from CSGOTrader...")
                resp = requests.get("https://prices.csgotrader.app/latest/buff163.json", timeout=10)
                if resp.status_code == 200:
                    self._cs2_cache = resp.json()
                    logger.info(f"[MarketService] Loaded {len(self._cs2_cache)} CS2 items into memory cache")
                else:
                    logger.warning(f"[MarketService] Failed to load CS2 prices: {resp.status_code}")
                    self._cs2_cache = {}
            except Exception as e:
                logger.error(f"[MarketService] Error loading CS2 price database: {e}")
                self._cs2_cache = {}
                
        # Lookup exact match
        item_data = self._cs2_cache.get(item_name)
        if not item_data:
            # Case-insensitive search
            item_name_lower = item_name.lower().strip()
            for name, details in self._cs2_cache.items():
                if name.lower().strip() == item_name_lower:
                    item_data = details
                    break
                    
        if item_data:
            price = item_data.get("starting_at", {}).get("price") or item_data.get("highest_order", {}).get("price")
            if price:
                return float(price)
                
        return 0.0

    def search_cs2_items(self, query: str, limit: int = 5) -> list:
        """
        Fuzzy searches the loaded CS2 cache for items matching the query.
        Returns up to `limit` matched item names using Smith-Waterman alignment.
        """
        if self._cs2_cache is None:
            # Force cache load
            self._get_cs2_price("")
            
        if not self._cs2_cache:
            return []
            
        from my_logic.fuzzy_finding import FuzzyFinder
        finder = FuzzyFinder()
        
        # Lowercase for better matching, though FuzzyFinder is case-sensitive 
        # based on exact chars unless we normalize. We will pass original keys to keep them valid.
        # We can lowercase query and target for the alignment if we wanted, 
        # but FuzzyFinder takes strings directly. Let's lowercase both in a wrapper.
        query_norm = query.lower().replace(" ", "")
        
        # Create a mapping of normalized to original
        norm_to_orig = {}
        for name in self._cs2_cache.keys():
            name_norm = name.lower().replace(" ", "")
            norm_to_orig[name_norm] = name
            
        results = finder.find_multiple_matches(query_norm, list(norm_to_orig.keys()), top_n=limit)
        
        # Retrieve original names and return
        matches = [norm_to_orig[res[0]] for res in results if res[1] > 0]
        return matches

market_service = MarketService()

