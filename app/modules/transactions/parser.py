"""
Transaction message parser.
Extracts amount, category, note, account, and transaction type from
user messages.
"""
import re
from typing import Dict, Any, Optional

def parse_transaction(text: str) -> Optional[Dict[str, Any]]:
    # Example parsing for "spent 50 on food"
    text = text.lower().strip()
    match = re.search(r'(spent|paid|bought|income)\s+([\d\.]+)\s+(?:on|for|from)\s+(.+)', text)
    if match:
        action, amount, note = match.groups()
        type_map = {"spent": "expense", "paid": "expense", "bought": "expense", "income": "income"}
        return {
            "type": type_map.get(action, "expense"),
            "amount": float(amount),
            "note": note.strip()
        }
    return None
