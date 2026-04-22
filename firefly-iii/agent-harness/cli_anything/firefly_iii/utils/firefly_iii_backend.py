r"""
Firefly III API Backend Client

Wraps Firefly III REST API calls, handles authentication, errors, and response parsing.
"""

import requests
import os
from typing import Dict, Any, Optional


class FireflyIIIBackend:
    """Firefly III API backend client"""

    def __init__(self, base_url: str, pat: str):
        """
        Initialize Firefly III backend client

        Args:
            base_url: Firefly III instance base URL
            pat: Personal Access Token
        """
        self.base_url = base_url.rstrip('/')
        self.pat = pat
        self.headers = {
            'Authorization': f'Bearer {pat}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        # Validate connection
        self._validate_connection()

    def _validate_connection(self):
        """Validate connection to Firefly III instance"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/about",
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to Firefly III instance: {self.base_url}\n"
                f"Please ensure:\n"
                f"1. Firefly III instance is running\n"
                f"2. Base URL is correct\n"
                f"3. Network connection is normal"
            )
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise RuntimeError(
                    "Authentication failed: Personal Access Token is invalid\n"
                    "Please generate a new PAT in Firefly III Options > Profile > OAuth"
                )
            raise RuntimeError(f"HTTP Error {response.status_code}: {response.text}")

    def request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict[str, Any]:
        """
        Send request to Firefly III API

        Args:
            method: HTTP method (get, post, put, delete)
            endpoint: API endpoint path (e.g., /accounts)
            params: URL query parameters
            data: Request body data

        Returns:
            API response JSON data

        Raises:
            RuntimeError: Connection error or HTTP error
        """
        url = f"{self.base_url}/api/v1{endpoint}"

        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=self.headers,
                params=params,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Cannot connect to Firefly III instance: {self.base_url}")
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise RuntimeError("Authentication failed: Personal Access Token is invalid")
            elif response.status_code == 404:
                raise RuntimeError(f"Resource not found: {endpoint}")
            elif response.status_code == 422:
                error_detail = response.json().get('message', 'Unknown error')
                raise RuntimeError(f"Request parameter error: {error_detail}")
            else:
                raise RuntimeError(f"HTTP Error {response.status_code}: {response.text}")
        except requests.exceptions.Timeout:
            raise RuntimeError("Request timeout, please check network connection")
        except Exception as e:
            raise RuntimeError(f"Request failed: {e}")

    def get(self, endpoint: str, params: Dict = None) -> Dict[str, Any]:
        """Send GET request"""
        return self.request('get', endpoint, params=params)

    def post(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """Send POST request"""
        return self.request('post', endpoint, data=data)

    def put(self, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """Send PUT request"""
        return self.request('put', endpoint, data=data)

    def delete(self, endpoint: str) -> Dict[str, Any]:
        """Send DELETE request"""
        return self.request('delete', endpoint)

    def get_about(self) -> Dict[str, Any]:
        """Get Firefly III system information"""
        return self.get("/about")

    def get_accounts(self, params: Dict = None) -> Dict[str, Any]:
        """Get account list"""
        return self.get("/accounts", params=params)

    def get_account(self, account_id: int) -> Dict[str, Any]:
        """Get single account details"""
        return self.get(f"/accounts/{account_id}")

    def create_account(self, data: Dict) -> Dict[str, Any]:
        """Create new account"""
        return self.post("/accounts", data=data)

    def update_account(self, account_id: int, data: Dict) -> Dict[str, Any]:
        """Update account"""
        return self.put(f"/accounts/{account_id}", data=data)

    def delete_account(self, account_id: int) -> Dict[str, Any]:
        """Delete account"""
        return self.delete(f"/accounts/{account_id}")

    def get_transactions(self, params: Dict = None) -> Dict[str, Any]:
        """Get transaction list"""
        return self.get("/transactions", params=params)

    def get_transaction(self, transaction_id: int) -> Dict[str, Any]:
        """Get single transaction details"""
        return self.get(f"/transactions/{transaction_id}")

    def create_transaction(self, data: Dict) -> Dict[str, Any]:
        """Create new transaction"""
        return self.post("/transactions", data=data)

    def update_transaction(self, transaction_id: int, data: Dict) -> Dict[str, Any]:
        """Update transaction"""
        return self.put(f"/transactions/{transaction_id}", data=data)

    def delete_transaction(self, transaction_id: int) -> Dict[str, Any]:
        """Delete transaction"""
        return self.delete(f"/transactions/{transaction_id}")

    def get_budgets(self, params: Dict = None) -> Dict[str, Any]:
        """Get budget list"""
        return self.get("/budgets", params=params)

    def get_budget(self, budget_id: int) -> Dict[str, Any]:
        """Get single budget details"""
        return self.get(f"/budgets/{budget_id}")

    def get_categories(self, params: Dict = None) -> Dict[str, Any]:
        """Get category list"""
        return self.get("/categories", params=params)

    def get_tags(self, params: Dict = None) -> Dict[str, Any]:
        """Get tag list"""
        return self.get("/tags", params=params)

    def get_bills(self, params: Dict = None) -> Dict[str, Any]:
        """Get bill list"""
        return self.get("/bills", params=params)

    def get_piggy_banks(self, params: Dict = None) -> Dict[str, Any]:
        """Get piggy bank list"""
        return self.get("/piggy-banks", params=params)

    def get_insight(self, insight_type: str, params: Dict = None) -> Dict[str, Any]:
        """Get insight report"""
        return self.get(f"/insight/{insight_type}", params=params)

    def search(self, query: str, params: Dict = None) -> Dict[str, Any]:
        """Search transactions"""
        search_params = params or {}
        search_params['query'] = query
        return self.get("/search/transactions", params=search_params)

    def export_data(self, data_type: str, params: Dict = None) -> Dict[str, Any]:
        """Export data"""
        return self.get(f"/data/export/{data_type}", params=params)
