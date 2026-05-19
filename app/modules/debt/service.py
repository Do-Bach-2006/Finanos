"""
Debt business logic.
Handles creating debt records, updating repayments, marking debts as paid,
and checking outstanding balances.
"""
from typing import Dict, Any
from app.modules.debt.models import Debt

class DebtService:
    def __init__(self):
        pass

    def add_debt(self, db, data: Dict[str, Any]):
        new_debt = Debt(
            person_name=data.get("person_name"),
            direction=data.get("direction"),
            amount=data.get("amount"),
        )
        db.add(new_debt)
        db.commit()
        return new_debt

debt_service = DebtService()
