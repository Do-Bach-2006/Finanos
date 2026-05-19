"""
Transaction business logic.
Creates, validates, updates, and syncs transactions with Firefly III.
"""
from typing import Dict, Any

class TransactionService:
    def __init__(self):
        # Firefly III client will be injected here
        pass

    def sync_transaction(self, tx_data: Dict[str, Any]):
        # This will call Firefly III API via integration layer
        # For now, it's a placeholder
        print(f"Syncing transaction to Firefly III: {tx_data}")
        return True

transaction_service = TransactionService()
