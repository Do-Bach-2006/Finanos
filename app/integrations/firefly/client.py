"""
Firefly III API client.
Handles HTTP requests to Firefly III, including accounts, transactions,
categories, budgets, and summaries.
"""
import requests
from typing import Dict, Any, List
from app.config import config
from app.utils.logging import logger

class FireflyClient:
    def __init__(self):
        self.base_url = config.FIREFLY_BASE_URL.rstrip('/') if config.FIREFLY_BASE_URL else ""
        self.token = config.FIREFLY_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    def _get(self, endpoint: str) -> Dict[str, Any]:
        if not self.base_url or not self.token:
            logger.error("Firefly III not configured (Missing URL or Token).")
            return {}
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        logger.info(f"[FireflyClient] GET {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            logger.info(f"[FireflyClient] Response Status: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"[FireflyClient] GET Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"[FireflyClient] Response Body: {e.response.text}")
            return {}

    def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.base_url or not self.token:
            logger.error("Firefly III not configured (Missing URL or Token).")
            return {}
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        logger.info(f"[FireflyClient] POST {url} with payload: {payload}")
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            logger.info(f"[FireflyClient] Response Status: {response.status_code}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"[FireflyClient] POST Error: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"[FireflyClient] Response Body: {e.response.text}")
            return {}

    def get_accounts(self, account_type: str = "asset") -> List[Dict[str, Any]]:
        """Fetch accounts by type (asset, expense, revenue, liability, initial-balance)."""
        data = self._get(f"accounts?type={account_type}")
        return data.get("data", [])

    def search_account(self, name: str, account_type: str = None) -> Dict[str, Any]:
        """Search for an account by exact name."""
        data = self._get(f"search/accounts?query={name}&field=name")
        results = data.get("data", [])
        for account in results:
            attrs = account.get("attributes", {})
            if attrs.get("name", "").lower() == name.lower():
                if account_type and attrs.get("type") != account_type:
                    continue
                return account
        return None

    def create_account(self, name: str, account_type: str) -> Dict[str, Any]:
        """Create a new account (e.g., 'Investments' as an expense or asset account)."""
        payload = {
            "name": name,
            "type": account_type
        }
        return self._post("accounts", payload)

    def get_or_create_account(self, name: str, account_type: str) -> str:
        """Returns the account ID, creating it if it doesn't exist."""
        acc = self.search_account(name, account_type)
        if acc:
            return acc["id"]
        
        logger.info(f"[FireflyClient] Account '{name}' ({account_type}) not found. Creating...")
        new_acc = self.create_account(name, account_type)
        if new_acc and "data" in new_acc:
            return new_acc["data"]["id"]
        return None

    def create_transaction(self, tx_data: Dict[str, Any]):
        return self._post("transactions", tx_data)

firefly_client = FireflyClient()
