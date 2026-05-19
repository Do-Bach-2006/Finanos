"""
Web interface routes for FinanOS.
Defines endpoints for serving the SPA dashboard, fetching real-time net worth data,
fetching/updating dynamic configurations, and testing API key integrations.
"""
import os
import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.config import config
from app.storage.database import SessionLocal
from app.modules.assets.models import Holding
from app.modules.market.forex import get_exchange_rate
from app.modules.market.service import market_service
from app.integrations.firefly.client import firefly_client, FireflyClient
from app.utils.env_handler import read_all_env_values, update_env_file, update_runtime_config
from app.utils.logging import logger

router = APIRouter()

# HTML Template Path
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

def serve_index_html() -> HTMLResponse:
    """Helper to read index.html and return it as HTMLResponse."""
    index_path = os.path.join(TEMPLATES_DIR, "index.html")
    if not os.path.exists(index_path):
        return HTMLResponse(
            content="<h3>index.html not found. Please create it first.</h3>",
            status_code=404
        )
    with open(index_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)

@router.get("/", response_class=HTMLResponse)
async def home_page():
    """Serves the dashboard home page."""
    return serve_index_html()

@router.get("/settings", response_class=HTMLResponse)
async def settings_page():
    """Serves the settings page (SPA router falls back to index.html)."""
    return serve_index_html()

# --- NET WORTH & PORTFOLIO API ---

@router.get("/api/networth")
async def get_networth():
    """
    Calculates consolidated net worth: Cash, Assets, Receivables, Liabilities.
    Performs real-time forex conversions to the configured default currency.
    """
    target_currency = config.DEFAULT_CURRENCY if hasattr(config, 'DEFAULT_CURRENCY') else "VND"
    
    def convert_amount(amount: float, from_curr: str) -> float:
        from my_logic.concurrency_converting import convert_currency
        from_curr = from_curr.upper()
        if from_curr == target_currency:
            return amount
            
        vnd_exchange_rate = {
            from_curr: get_exchange_rate(from_curr, "VND"),
            target_currency: get_exchange_rate(target_currency, "VND")
        }
        return convert_currency(from_curr, target_currency, vnd_exchange_rate, amount)

    try:
        # 1. Fetch Cash accounts from Firefly III
        raw_accounts = firefly_client.get_accounts("asset")
        cash_accounts = []
        total_cash_converted = 0.0
        
        for acc in raw_accounts:
            attrs = acc.get("attributes", {})
            name = attrs.get("name", "Unknown Account")
            bal = float(attrs.get("current_balance", 0.0))
            curr = attrs.get("currency_code", target_currency)
            converted = convert_amount(bal, curr)
            
            total_cash_converted += converted
            cash_accounts.append({
                "id": acc.get("id"),
                "name": name,
                "balance": bal,
                "currency": curr,
                "balance_converted": converted
            })

        # 2. Fetch Assets / Holdings from local DB and query live market prices
        db = SessionLocal()
        holdings = db.query(Holding).all()
        db.close()
        
        portfolio_holdings = []
        total_assets_converted = 0.0
        
        for h in holdings:
            curr = h.currency if hasattr(h, "currency") else "VND"
            total_spent = h.total_spent
            quantity = h.quantity
            symbol = h.symbol
            asset_type = h.asset_type
            
            # Fetch current live price from live integrations (returns price in USD)
            live_price_usd = market_service.get_price(symbol, asset_type)
            
            # Convert live price to default target currency (USD -> target_currency)
            if live_price_usd > 0.0:
                live_price_converted = convert_amount(live_price_usd, "USD")
                live_value_converted = quantity * live_price_converted
            else:
                # Fallback to historical purchase spent if API cannot fetch
                live_price_converted = total_spent / quantity if quantity > 0 else 0.0
                live_value_converted = convert_amount(total_spent, curr)
                live_price_usd = live_price_converted / get_exchange_rate("USD", target_currency)
                
            total_assets_converted += live_value_converted
            
            portfolio_holdings.append({
                "id": h.id,
                "symbol": symbol,
                "asset_type": asset_type,
                "quantity": quantity,
                "total_spent": total_spent,
                "currency": curr,
                "total_spent_converted": convert_amount(total_spent, curr),
                "live_price_usd": live_price_usd,
                "live_value_converted": live_value_converted
            })

        # 3. Fetch Debt (Receivables & Liabilities) from Firefly III
        from app.modules.debt.models import Debt
        db = SessionLocal()
        
        # Receivables (Money owed to us - tracked under Firefly's expense accounts)
        raw_receivables = firefly_client.get_accounts("expense")
        receivables_list = []
        total_receivables_converted = 0.0
        
        EXCLUDE_EXPENSES = {
            "investments", "central investments", "food", "drinks", "groceries", "dining",
            "entertainment", "subscriptions", "shopping", "transport", "utilities", "travel",
            "health", "insurance", "electronics", "misc", "shopping/retail", "household", "education"
        }
        
        for r in raw_receivables:
            attrs = r.get("attributes", {})
            name = attrs.get("name", "Debtor")
            
            if name.lower() in EXCLUDE_EXPENSES:
                continue
                
            bal = abs(float(attrs.get("current_balance", 0.0)))
            curr = attrs.get("currency_code", target_currency)
            converted = convert_amount(bal, curr)
            
            # Lookup or auto-create local metadata in database
            local_debt = db.query(Debt).filter(Debt.person_name == name).first()
            if not local_debt:
                local_debt = Debt(
                    person_name=name,
                    direction="lent",
                    amount=bal,
                    currency=curr,
                    interest_rate=0.0,
                    due_date=None,
                    is_settled=(bal == 0.0)
                )
                db.add(local_debt)
                db.commit()
                db.refresh(local_debt)
            else:
                # Synchronize real balance and status
                if local_debt.amount > 0.0 and bal == 0.0 and not local_debt.is_settled:
                    # Receivable settled: Someone paid us back!
                    logger.info(f"[DebtSystem] RECEIVABLE SETTLED: {name} paid back their balance of {local_debt.amount} {curr}!")
                    from app.storage.models import ActivityLog
                    log_entry = ActivityLog(
                        activity_type="deposit",
                        description=f"🎉 LOAN RECEIVED: {name} has paid back their remaining loan of {local_debt.amount:,.2f} {curr}!",
                        amount=converted
                    )
                    db.add(log_entry)
                local_debt.amount = bal
                local_debt.is_settled = (bal == 0.0)
                db.commit()
                
            receivables_list.append({
                "id": r.get("id"),
                "name": name,
                "balance": bal,
                "currency": curr,
                "balance_converted": converted,
                "interest_rate": local_debt.interest_rate or 0.0,
                "due_date": local_debt.due_date.strftime("%Y-%m-%d") if local_debt.due_date else None,
                "is_settled": local_debt.is_settled
            })
            
            if not local_debt.is_settled:
                total_receivables_converted += converted

        # Liabilities (Money we owe - tracked under Firefly's revenue accounts)
        raw_liabilities = firefly_client.get_accounts("revenue")
        liabilities_list = []
        total_liabilities_converted = 0.0
        
        EXCLUDE_REVENUES = {
            "salary", "payroll", "interests", "dividends", "income", "deposits", "jobs", "employer", "work", "bonus"
        }
        
        for l in raw_liabilities:
            attrs = l.get("attributes", {})
            name = attrs.get("name", "Creditor")
            
            if name.lower() in EXCLUDE_REVENUES:
                continue
                
            bal = abs(float(attrs.get("current_balance", 0.0)))
            curr = attrs.get("currency_code", target_currency)
            converted = convert_amount(bal, curr)
            
            # Lookup or auto-create local metadata in database
            local_debt = db.query(Debt).filter(Debt.person_name == name).first()
            if not local_debt:
                local_debt = Debt(
                    person_name=name,
                    direction="borrowed",
                    amount=bal,
                    currency=curr,
                    interest_rate=0.0,
                    due_date=None,
                    is_settled=(bal == 0.0)
                )
                db.add(local_debt)
                db.commit()
                db.refresh(local_debt)
            else:
                # Synchronize real balance and status
                if local_debt.amount > 0.0 and bal == 0.0 and not local_debt.is_settled:
                    # Liability settled: We paid someone back!
                    logger.info(f"[DebtSystem] LIABILITY SETTLED: Settled outstanding debt of {local_debt.amount} {curr} to {name}!")
                    from app.storage.models import ActivityLog
                    log_entry = ActivityLog(
                        activity_type="debt",
                        description=f"🎉 DEBT PAID: You have fully settled your outstanding debt of {local_debt.amount:,.2f} {curr} to {name}!",
                        amount=converted
                    )
                    db.add(log_entry)
                local_debt.amount = bal
                local_debt.is_settled = (bal == 0.0)
                db.commit()
                
            liabilities_list.append({
                "id": l.get("id"),
                "name": name,
                "balance": bal,
                "currency": curr,
                "balance_converted": converted,
                "interest_rate": local_debt.interest_rate or 0.0,
                "due_date": local_debt.due_date.strftime("%Y-%m-%d") if local_debt.due_date else None,
                "is_settled": local_debt.is_settled
            })
            
            if not local_debt.is_settled:
                total_liabilities_converted += converted
                
        db.close()
        
        # Sort liabilities using custom PriorityQueue (DSA requirement)
        # Prioritize by highest interest rate (negative weight for Min Heap)
        from my_logic.queue import PriorityQueue
        pq = PriorityQueue()
        for liability in liabilities_list:
            # weight is negative interest rate, so highest rate comes first
            pq.push(-liability["interest_rate"], liability)
            
        sorted_liabilities = []
        while True:
            try:
                sorted_liabilities.append(pq.pop())
            except IndexError:
                break
                
        liabilities_list = sorted_liabilities

        net_worth = total_cash_converted + total_assets_converted + total_receivables_converted - total_liabilities_converted

        return {
            "success": True,
            "target_currency": target_currency,
            "net_worth": net_worth,
            "cash": {
                "total": total_cash_converted,
                "accounts": cash_accounts
            },
            "portfolio": {
                "total": total_assets_converted,
                "holdings": portfolio_holdings
            },
            "debt": {
                "receivables_total": total_receivables_converted,
                "liabilities_total": total_liabilities_converted,
                "net_debt": total_receivables_converted - total_liabilities_converted,
                "receivables": receivables_list,
                "liabilities": liabilities_list
            }
        }
    except Exception as e:
        logger.error(f"[WebAPI] Failed to fetch net worth: {e}")
        return {
            "success": False,
            "error": str(e),
            "net_worth": 0.0,
            "cash": {"total": 0.0, "accounts": []},
            "portfolio": {"total": 0.0, "holdings": []},
            "debt": {"receivables_total": 0.0, "liabilities_total": 0.0, "net_debt": 0.0, "receivables": [], "liabilities": []}
        }


# --- SETTINGS MANAGEMENT API ---

@router.get("/api/settings")
async def get_settings():
    """Returns the current application settings and environment variables."""
    # Read fresh from .env file to reflect any manual or file-based updates
    env_vals = read_all_env_values()
    
    # Expose both backend keys and dynamic selections
    return {
        "success": True,
        "config": {
            "DEFAULT_CURRENCY": env_vals.get("DEFAULT_CURRENCY", "VND"),
            "APP_ENV": env_vals.get("APP_ENV", "local"),
            "DATABASE_URL": env_vals.get("DATABASE_URL", "sqlite:///finanos.db"),
            
            "FIREFLY_BASE_URL": env_vals.get("FIREFLY_BASE_URL", ""),
            "FIREFLY_TOKEN": env_vals.get("FIREFLY_TOKEN", ""),
            
            "TELEGRAM_BOT_TOKEN": env_vals.get("TELEGRAM_BOT_TOKEN", ""),
            "GEMINI_API_KEY": env_vals.get("GEMINI_API_KEY", ""),
            
            "COINGECKO_API_KEY": env_vals.get("COINGECKO_API_KEY", ""),
            "COINMARKETCAP_API_KEY": env_vals.get("COINMARKETCAP_API_KEY", ""),
            
            "FINNHUB_API_KEY": env_vals.get("FINNHUB_API_KEY", ""),
            "ALPHAVANTAGE_API_KEY": env_vals.get("ALPHAVANTAGE_API_KEY", ""),
            
            "EXCHANGERATE_API_KEY": env_vals.get("EXCHANGERATE_API_KEY", ""),
            "CURRENCYFREAKS_API_KEY": env_vals.get("CURRENCYFREAKS_API_KEY", ""),
            
            "CS2_MARKET_PROVIDER": env_vals.get("CS2_MARKET_PROVIDER", "steam_analysis"),
            "CS2_MARKET_API_KEY": env_vals.get("CS2_MARKET_API_KEY", "")
        },
        "preferences": {
            "preferred_crypto_provider": env_vals.get("preferred_crypto_provider", "coingecko"),
            "preferred_stock_provider": env_vals.get("preferred_stock_provider", "finnhub"),
            "preferred_forex_provider": env_vals.get("preferred_forex_provider", "exchangerate_api"),
            "preferred_cs2_provider": env_vals.get("preferred_cs2_provider", "steam")
        }
    }

class SettingsUpdatePayload(BaseModel):
    config: Dict[str, str]
    preferences: Dict[str, str]

@router.post("/api/settings")
async def save_settings(payload: SettingsUpdatePayload):
    """Saves updated settings to .env file and updates runtime config in-memory."""
    try:
        # Group all updates
        updates = {}
        for k, v in payload.config.items():
            updates[k] = v.strip()
            
        for k, v in payload.preferences.items():
            updates[k] = v.strip()
            
        # 1. Update the physical .env file
        update_env_file(updates)
        
        # 2. Update the active process in-memory config & reload providers
        update_runtime_config(updates)
        
        return {"success": True, "message": "Settings updated and applied successfully!"}
    except Exception as e:
        logger.error(f"[WebAPI] Save settings failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- API INTEGRATION TESTING ENDPOINTS ---

class TestFireflyPayload(BaseModel):
    base_url: str
    token: str

@router.post("/api/test/firefly")
async def test_firefly(payload: TestFireflyPayload):
    """Tests connection to Firefly III instance."""
    base_url = payload.base_url.rstrip('/')
    token = payload.token
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    test_url = f"{base_url}/api/v1/about"
    try:
        logger.info(f"[TestAPI] Testing Firefly III on: {test_url}")
        resp = requests.get(test_url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            version = data.get("data", {}).get("version", "Unknown")
            return {"success": True, "message": f"Connected! Firefly III Version: {version}"}
        else:
            return {"success": False, "message": f"Connection failed. Status Code: {resp.status_code}. Response: {resp.text[:100]}"}
    except Exception as e:
        return {"success": False, "message": f"Error connecting to Firefly III: {str(e)}"}

class TestTelegramPayload(BaseModel):
    token: str

@router.post("/api/test/telegram")
async def test_telegram(payload: TestTelegramPayload):
    """Tests validity of Telegram bot token."""
    token = payload.token
    test_url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        logger.info("[TestAPI] Testing Telegram token...")
        resp = requests.get(test_url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            bot_info = data.get("result", {})
            username = bot_info.get("username", "Unknown")
            first_name = bot_info.get("first_name", "Bot")
            return {"success": True, "message": f"Connected! Active Bot: @{username} ({first_name})"}
        else:
            return {"success": False, "message": f"Invalid token. Status Code: {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"Error connecting to Telegram: {str(e)}"}

class TestGeminiPayload(BaseModel):
    api_key: str

@router.post("/api/test/gemini")
async def test_gemini(payload: TestGeminiPayload):
    """Tests validity of Gemini API Key."""
    api_key = payload.api_key
    try:
        logger.info("[TestAPI] Testing Gemini API connection...")
        import google.generativeai as genai
        # Temporarily configure with target test key
        # Note: If there are multiple keys tested, this only tests the first one if comma-separated. We will just take the first.
        test_key = api_key.split(",")[0].strip()
        genai.configure(api_key=test_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content("Ping. Return only the word 'Pong'.")
        
        clean_text = response.text.strip()
        if "pong" in clean_text.lower():
            return {"success": True, "message": "Successfully authenticated and communicated with Gemini!"}
        return {"success": True, "message": f"Authenticated, but unexpected response: {clean_text}"}
    except Exception as e:
        return {"success": False, "message": f"Gemini API authentication failed: {str(e)}"}


class DebtUpdateRequest(BaseModel):
    person_name: str
    interest_rate: float
    due_date: Optional[str] = None # YYYY-MM-DD format

@router.post("/api/debts/update")
async def update_debt_metadata(payload: DebtUpdateRequest):
    """Updates interest rate and due date of a specific debt/borrower by name."""
    from app.modules.debt.models import Debt
    from datetime import datetime
    db = SessionLocal()
    try:
        debt = db.query(Debt).filter(Debt.person_name == payload.person_name).first()
        if not debt:
            # Auto-create if not found
            debt = Debt(
                person_name=payload.person_name,
                direction="borrowed", # fallback
                amount=0.0,
                currency="VND",
                interest_rate=0.0
            )
            db.add(debt)
            
        debt.interest_rate = payload.interest_rate
        if payload.due_date:
            try:
                debt.due_date = datetime.strptime(payload.due_date, "%Y-%m-%d")
            except Exception:
                debt.due_date = None
        else:
            debt.due_date = None
            
        db.commit()
        return {"success": True, "message": f"Successfully updated terms for {payload.person_name}!"}
    except Exception as e:
        logger.error(f"[WebAPI] Failed to update debt terms: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# --- ACTIVITY HISTORY LOGS API ---

@router.get("/api/activity")
async def get_activity():
    """Returns the recent activities logged in the database."""
    from app.storage.activity_buffer import get_activity_queue_list
    try:
        # Utilize the custom Queue (Bounded Linked List) for O(1) reads instead of hitting the database!
        result = get_activity_queue_list()
        return {"success": True, "activities": result}
    except Exception as e:
        logger.error(f"[WebAPI] Failed to fetch activities from Queue: {e}")
        return {"success": False, "error": str(e), "activities": []}

