"""
CS2 price provider abstraction.
"""
from app.config import config

class CS2PriceProvider:
    def __init__(self):
        self.provider = config.CS2_MARKET_PROVIDER
        self.api_key = config.CS2_MARKET_API_KEY

    def get_item_price(self, item_name: str) -> float:
        if self.provider == "steam_analysis":
            print(f"Fetching {item_name} from steam_analysis...")
            # Implement steam analysis API here
            return 0.0
        return 0.0

cs2_provider = CS2PriceProvider()
