"""
Debt message parser.
Extracts debt-related information from user messages, such as person,
amount, due date, direction, and interest.
"""
import re
from typing import Dict, Any, Optional

def parse_debt_action(text: str) -> Optional[Dict[str, Any]]:
    text = text.lower().strip()
    match = re.search(r'(borrowed|lent)\s+([\d\.]+)\s+(?:from|to)\s+([a-z0-9]+)', text)
    if match:
        direction, amount, person = match.groups()
        return {
            "direction": direction,
            "amount": float(amount),
            "person_name": person.capitalize()
        }
    return None
