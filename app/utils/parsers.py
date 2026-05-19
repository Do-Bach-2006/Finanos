"""
Utility functions to parse text values using Gemini.
Used by the strict state machine to extract normalized data.
"""
import json
import google.generativeai as genai
from app.config import config
from app.utils.logging import logger
from my_logic.api_logics import GeminiDistributor

gemini_distributor = None
if hasattr(config, 'GEMINI_API_KEYS') and config.GEMINI_API_KEYS:
    gemini_distributor = GeminiDistributor(config.GEMINI_API_KEYS)

def get_gemini_model(model_name: str = 'gemini-2.5-flash'):
    if not gemini_distributor:
        return None
    try:
        key = gemini_distributor.get_next_endpoint()
        genai.configure(api_key=key)
        return genai.GenerativeModel(model_name)
    except Exception as e:
        logger.error(f"Failed to configure gemini model: {e}")
        return None

def extract_tags(description: str) -> list:
    """Extracts tags from a natural language description (e.g. 'nước mía' -> ['food', 'drinks'])."""
    model = get_gemini_model()
    if not model:
        return []
        
    prompt = f"""
    You are a categorization engine for a personal finance app.
    Given the transaction description "{description}", return a JSON array of 1 to 3 relevant category tags in English.
    For example: "nước mía" -> ["food", "drinks"]
    "netflix" -> ["entertainment", "subscriptions"]
    
    Return ONLY a JSON array, no markdown.
    """
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception as e:
        logger.error(f"Gemini tag extraction failed: {e}")
        return []

def extract_amount(text: str) -> float:
    """Converts a natural language amount (e.g. '10k', '2.5 dollars') to a float."""
    model = get_gemini_model()
    if not model:
        # Fallback basic parsing
        text = text.lower().replace(",", "").replace("$", "").replace("k", "000")
        try:
            return float(text.split()[0])
        except ValueError:
            return 0.0
            
    prompt = f"""
    Extract the numeric amount from this text: "{text}".
    Convert abbreviations (like 'k' for thousand, 'm' for million).
    If it's in another language like Vietnamese (e.g. '10k vnd'), convert it to the full number (10000).
    Return ONLY the raw float value, no other text.
    """
    try:
        response = model.generate_content(prompt)
        import re
        clean_text = re.sub(r'[^\d.]', '', response.text.strip())
        return float(clean_text) if clean_text else 0.0
    except Exception as e:
        logger.error(f"Gemini amount extraction failed: {e}")
        # Robust local fallback
        import re
        clean_text = text.lower().replace(",", "").replace("$", "").replace("k", "000").replace("m", "000000")
        matches = re.findall(r'\d+(?:\.\d+)?', clean_text)
        if matches:
            return float(matches[0])
        return 0.0

def extract_amount_and_currency(text: str) -> tuple:
    """
    Extracts a numeric amount (float) and currency code (string or None)
    from text string.
    """
    import re
    clean_text = text.strip().lower()
    
    currency_map = {
        "$": "USD",
        "usd": "USD",
        "£": "GBP",
        "gbp": "GBP",
        "€": "EUR",
        "eur": "EUR",
        "đ": "VND",
        "vnd": "VND",
        "d": "VND"
    }
    
    detected_currency = None
    for sym, abb in currency_map.items():
        if sym in clean_text:
            detected_currency = abb
            break
            
    if not detected_currency:
        words = re.findall(r'\b[a-zA-Z]{3}\b', clean_text)
        for w in words:
            if w.upper() in ["VND", "USD", "EUR", "GBP", "AUD", "CAD", "SGD", "JPY"]:
                detected_currency = w.upper()
                break
                
    amount = extract_amount(text)
    return amount, detected_currency

def parse_natural_purchase(text: str) -> dict:
    """
    Parses a natural language purchase string using Gemini.
    Returns a dict with: 'amount', 'description', 'tags'.
    """
    default_res = {"amount": 0.0, "description": text, "tags": ["purchase"]}
    model = get_gemini_model()
    if not model:
        return default_res
        
    prompt = f"""
    You are an AI financial parsing assistant.
    The user wrote: "{text}"
    
    Parse this into a structured purchase transaction.
    Return a JSON object with:
    - "amount": the numeric amount as a float (convert 'k' to thousands, 'm' to millions, e.g., '50k' -> 50000, '1.5m' -> 1500000).
    - "description": a clean, concise description of what was bought.
    - "tags": a list of 1 to 3 relevant category tags in English representing this expense.
    
    Existing standard category tags for guidance:
    ["food", "drinks", "entertainment", "subscriptions", "shopping", "transport", "utilities", "travel", "health", "insurance", "electronics", "misc"]
    
    Return ONLY a JSON object, no markdown.
    """
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        return {
            "amount": float(data.get("amount", 0.0)),
            "description": str(data.get("description", text)),
            "tags": list(data.get("tags", ["purchase"]))
        }
    except Exception as e:
        logger.error(f"Gemini natural purchase parsing failed: {e}")
        return default_res

def suggest_alternative_symbols(symbol: str, asset_type: str) -> list:
    """
    Generates 3-5 real, trackable standard symbol/name suggestions for a given search query and asset type.
    Specifically useful for CS2 skins (performing a fast, local fuzzy search on our real cached item names),
    or Stocks/Cryptos (using Gemini).
    """
    asset_type = asset_type.lower().strip()
    if asset_type == "cs2":
        try:
            from app.modules.market.service import market_service
            local_matches = market_service.search_cs2_items(symbol, limit=5)
            if local_matches:
                logger.info(f"Local CS2 search found {len(local_matches)} matches for '{symbol}'")
                return local_matches
        except Exception as e:
            logger.error(f"Local CS2 search failed: {e}")
            
    model = get_gemini_model()
    if not model:
        return []
        
    prompt = f"""
    The user is trying to add a '{asset_type}' asset in a finance app and entered: "{symbol}".
    We could not find an exact market price overview for this.
    
    Please provide a list of 3 to 5 most likely, real, standard, and highly accurate symbols or names for this asset type that are known on public markets.
    - For 'cs2', suggest the exact Steam Community Market hash names including real weapon skin conditions (e.g., 'AK-47 | Redline (Field-Tested)', 'AK-47 | Redline (Minimal Wear)', etc.).
    - For 'stock', suggest standard ticker symbols (e.g., 'AAPL', 'TSLA').
    - For 'crypto', suggest standard ticker symbols (e.g., 'BTC', 'ETH').
    
    Return ONLY a JSON array of strings, no other text or markdown.
    """
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        candidates = json.loads(clean_text)
        
        # Filter suggested candidates to only those that resolve to a valid market price
        from app.modules.market.service import market_service
        verified = []
        for candidate in candidates:
            cand_strip = candidate.strip()
            # Check price lookup
            price = market_service.get_price(cand_strip, asset_type)
            if price > 0.0:
                verified.append(cand_strip)
                
        logger.info(f"Gemini suggested candidates {candidates}, filtered down to verified options: {verified}")
        return verified
    except Exception as e:
        logger.error(f"Gemini symbol suggestions failed: {e}")
        return []

def parse_natural_debt_or_loan(text: str) -> dict:
    """
    Parses a natural language debt or loan string using Gemini.
    Extracts name, amount, currency, and due_date (calculated as YYYY-MM-DD based on today's date).
    """
    import datetime
    today_str = datetime.date.today().strftime("%A, %B %d, %Y")
    
    default_res = {
        "name": None,
        "amount": None,
        "currency": None,
        "due_date": None
    }
    
    model = get_gemini_model()
    if not model:
        return default_res
        
    prompt = f"""
    You are an AI financial parsing assistant.
    Today is {today_str}.
    
    The user wrote a sentence describing a debt, borrow, or lend transaction:
    "{text}"
    
    Your task is to extract the following fields:
    1. "name": The name of the person borrowed from or lent to (e.g. "MrBeast" or "Giang"). Do NOT include words like "Mr" or "Mrs" or "borrowed" or "lent" unless it's part of a proper name. Return null if not mentioned.
    2. "amount": The numeric amount as a float (e.g. "50k" -> 50000.0, "200,000" -> 200000.0). Return null if not mentioned.
    3. "currency": The currency code (e.g., "VND", "USD", "GBP", "EUR") or null if not specified.
    4. "due_date": The calendar date when this debt is due in YYYY-MM-DD format.
       Calculate this relative to today's date ({today_str}) based on descriptions like "due in 4 weeks", "next 5 weeks", "tomorrow", "next Friday", "in 1 month".
       If no due date or timeframe is specified, return null.
       
    Return ONLY a JSON object with these keys: "name", "amount", "currency", "due_date". Do not include any other text or markdown block formatting.
    """
    try:
        response = model.generate_content(prompt)
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        
        # Normalize fields
        amount_val = data.get("amount")
        if amount_val is not None:
            try:
                amount_val = float(amount_val)
            except (ValueError, TypeError):
                amount_val = None
                
        return {
            "name": data.get("name") if data.get("name") else None,
            "amount": amount_val,
            "currency": data.get("currency") if data.get("currency") else None,
            "due_date": data.get("due_date") if data.get("due_date") else None
        }
    except Exception as e:
        logger.error(f"Gemini natural debt parsing failed: {e}")
        return default_res



