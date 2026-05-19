"""
Asset message parser.
Extracts asset-related information from user messages, such as ticker,
name, quantity, amount spent, and action type.
"""
import re
from typing import Dict, Any, Optional

def parse_asset_action(text: str) -> Optional[Dict[str, Any]]:
    # Example parsing for "buy 2.5 BTC for 150000"
    text = text.lower().strip()
    
    # Very basic regex parser as a placeholder
    # In a real system, you'd use NLP or a more robust parsing engine
    match = re.search(r'(buy|sell)\s+([\d\.]+)\s+([a-z0-9]+)\s+(?:for|at)\s+([\d\.]+)', text)
    if match:
        action, qty, symbol, price = match.groups()
        return {
            "action": action,
            "quantity": float(qty),
            "symbol": symbol.upper(),
            "price": float(price)
        }
    return None
