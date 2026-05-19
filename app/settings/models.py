"""
Settings models.
Defines structures for user preferences, API configuration,
provider selection, and default currency.
"""

from pydantic import BaseModel
from typing import Optional

class UserSettings(BaseModel):
    default_currency: str = "VND"
    preferred_crypto_provider: Optional[str] = "coingecko"
    preferred_stock_provider: Optional[str] = "finnhub"
    preferred_forex_provider: Optional[str] = "exchangerate_api"
    preferred_cs2_provider: Optional[str] = "steam"
