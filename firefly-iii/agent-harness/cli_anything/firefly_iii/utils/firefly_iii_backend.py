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
            if response.status_code == 204:
                return {"status": "success", "code": 204}
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

    # ========== About ==========
    def get_about(self) -> Dict[str, Any]:
        """Get Firefly III system information"""
        return self.get("/about")

    # ========== Accounts ==========
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

    # ========== Transactions ==========
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

    # ========== Budgets ==========
    def get_budgets(self, params: Dict = None) -> Dict[str, Any]:
        """Get budget list"""
        return self.get("/budgets", params=params)

    def get_budget(self, budget_id: int) -> Dict[str, Any]:
        """Get single budget details"""
        return self.get(f"/budgets/{budget_id}")

    def create_budget(self, data: Dict) -> Dict[str, Any]:
        """Create new budget"""
        return self.post("/budgets", data=data)

    def update_budget(self, budget_id: int, data: Dict) -> Dict[str, Any]:
        """Update budget"""
        return self.put(f"/budgets/{budget_id}", data=data)

    def delete_budget(self, budget_id: int) -> Dict[str, Any]:
        """Delete budget"""
        return self.delete(f"/budgets/{budget_id}")

    def get_budget_limits(self, budget_id: int, params: Dict = None) -> Dict[str, Any]:
        """Get budget limits for a budget"""
        return self.get(f"/budgets/{budget_id}/limits", params=params)

    def create_budget_limit(self, budget_id: int, data: Dict) -> Dict[str, Any]:
        """Create budget limit"""
        return self.post(f"/budgets/{budget_id}/limits", data=data)

    def update_budget_limit(self, budget_limit_id: int, data: Dict) -> Dict[str, Any]:
        """Update budget limit"""
        return self.put(f"/budget_limits/{budget_limit_id}", data=data)

    def delete_budget_limit(self, budget_limit_id: int) -> Dict[str, Any]:
        """Delete budget limit"""
        return self.delete(f"/budget_limits/{budget_limit_id}")

    # ========== Categories ==========
    def get_categories(self, params: Dict = None) -> Dict[str, Any]:
        """Get category list"""
        return self.get("/categories", params=params)

    def get_category(self, category_id: int) -> Dict[str, Any]:
        """Get single category details"""
        return self.get(f"/categories/{category_id}")

    def create_category(self, data: Dict) -> Dict[str, Any]:
        """Create new category"""
        return self.post("/categories", data=data)

    def update_category(self, category_id: int, data: Dict) -> Dict[str, Any]:
        """Update category"""
        return self.put(f"/categories/{category_id}", data=data)

    def delete_category(self, category_id: int) -> Dict[str, Any]:
        """Delete category"""
        return self.delete(f"/categories/{category_id}")

    # ========== Tags ==========
    def get_tags(self, params: Dict = None) -> Dict[str, Any]:
        """Get tag list"""
        return self.get("/tags", params=params)

    def get_tag(self, tag_id: str) -> Dict[str, Any]:
        """Get single tag details"""
        return self.get(f"/tags/{tag_id}")

    def create_tag(self, data: Dict) -> Dict[str, Any]:
        """Create new tag"""
        return self.post("/tags", data=data)

    def update_tag(self, tag_id: str, data: Dict) -> Dict[str, Any]:
        """Update tag"""
        return self.put(f"/tags/{tag_id}", data=data)

    def delete_tag(self, tag_id: str) -> Dict[str, Any]:
        """Delete tag"""
        return self.delete(f"/tags/{tag_id}")

    # ========== Bills ==========
    def get_bills(self, params: Dict = None) -> Dict[str, Any]:
        """Get bill list"""
        return self.get("/bills", params=params)

    def get_bill(self, bill_id: int) -> Dict[str, Any]:
        """Get single bill details"""
        return self.get(f"/bills/{bill_id}")

    def create_bill(self, data: Dict) -> Dict[str, Any]:
        """Create new bill"""
        return self.post("/bills", data=data)

    def update_bill(self, bill_id: int, data: Dict) -> Dict[str, Any]:
        """Update bill"""
        return self.put(f"/bills/{bill_id}", data=data)

    def delete_bill(self, bill_id: int) -> Dict[str, Any]:
        """Delete bill"""
        return self.delete(f"/bills/{bill_id}")

    # ========== Piggy Banks ==========
    def get_piggy_banks(self, params: Dict = None) -> Dict[str, Any]:
        """Get piggy bank list"""
        return self.get("/piggy-banks", params=params)

    def get_piggy_bank(self, piggy_bank_id: int) -> Dict[str, Any]:
        """Get single piggy bank details"""
        return self.get(f"/piggy-banks/{piggy_bank_id}")

    def create_piggy_bank(self, data: Dict) -> Dict[str, Any]:
        """Create new piggy bank"""
        return self.post("/piggy-banks", data=data)

    def update_piggy_bank(self, piggy_bank_id: int, data: Dict) -> Dict[str, Any]:
        """Update piggy bank"""
        return self.put(f"/piggy-banks/{piggy_bank_id}", data=data)

    def delete_piggy_bank(self, piggy_bank_id: int) -> Dict[str, Any]:
        """Delete piggy bank"""
        return self.delete(f"/piggy-banks/{piggy_bank_id}")

    def get_piggy_bank_events(self, piggy_bank_id: int) -> Dict[str, Any]:
        """Get piggy bank events"""
        return self.get(f"/piggy-banks/{piggy_bank_id}/events")

    def create_piggy_bank_event(self, piggy_bank_id: int, data: Dict) -> Dict[str, Any]:
        """Add money to piggy bank"""
        return self.post(f"/piggy-banks/{piggy_bank_id}/events", data=data)

    # ========== Autocomplete ==========
    def autocomplete_accounts(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete accounts"""
        return self.get("/autocomplete/accounts", params=params)

    def autocomplete_bills(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete bills"""
        return self.get("/autocomplete/bills", params=params)

    def autocomplete_budgets(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete budgets"""
        return self.get("/autocomplete/budgets", params=params)

    def autocomplete_categories(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete categories"""
        return self.get("/autocomplete/categories", params=params)

    def autocomplete_currencies(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete currencies"""
        return self.get("/autocomplete/currencies", params=params)

    def autocomplete_piggy_banks(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete piggy banks"""
        return self.get("/autocomplete/piggy-banks", params=params)

    def autocomplete_tags(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete tags"""
        return self.get("/autocomplete/tags", params=params)

    def autocomplete_transactions(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete transactions"""
        return self.get("/autocomplete/transactions", params=params)

    def autocomplete_rule_groups(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete rule groups"""
        return self.get("/autocomplete/rule-groups", params=params)

    def autocomplete_rules(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete rules"""
        return self.get("/autocomplete/rules", params=params)

    def autocomplete_recurring(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete recurring transactions"""
        return self.get("/autocomplete/recurring", params=params)

    def autocomplete_object_groups(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete object groups"""
        return self.get("/autocomplete/object-groups", params=params)

    def autocomplete_transaction_types(self, params: Dict = None) -> Dict[str, Any]:
        """Autocomplete transaction types"""
        return self.get("/autocomplete/transaction-types", params=params)

    # ========== Currencies ==========
    def get_currencies(self, params: Dict = None) -> Dict[str, Any]:
        """Get currency list"""
        return self.get("/currencies", params=params)

    def get_currency(self, currency_id: int) -> Dict[str, Any]:
        """Get single currency details"""
        return self.get(f"/currencies/{currency_id}")

    def create_currency(self, data: Dict) -> Dict[str, Any]:
        """Create new currency"""
        return self.post("/currencies", data=data)

    def update_currency(self, currency_id: int, data: Dict) -> Dict[str, Any]:
        """Update currency"""
        return self.put(f"/currencies/{currency_id}", data=data)

    def delete_currency(self, currency_id: int) -> Dict[str, Any]:
        """Delete currency"""
        return self.delete(f"/currencies/{currency_id}")

    def get_currency_exchange_rates(self, params: Dict = None) -> Dict[str, Any]:
        """Get currency exchange rates"""
        return self.get("/currency_exchange_rates", params=params)

    # ========== Recurrences ==========
    def get_recurrences(self, params: Dict = None) -> Dict[str, Any]:
        """Get recurring transaction list"""
        return self.get("/recurrences", params=params)

    def get_recurrence(self, recurrence_id: int) -> Dict[str, Any]:
        """Get single recurring transaction details"""
        return self.get(f"/recurrences/{recurrence_id}")

    def create_recurrence(self, data: Dict) -> Dict[str, Any]:
        """Create new recurring transaction"""
        return self.post("/recurrences", data=data)

    def update_recurrence(self, recurrence_id: int, data: Dict) -> Dict[str, Any]:
        """Update recurring transaction"""
        return self.put(f"/recurrences/{recurrence_id}", data=data)

    def delete_recurrence(self, recurrence_id: int) -> Dict[str, Any]:
        """Delete recurring transaction"""
        return self.delete(f"/recurrences/{recurrence_id}")

    # ========== Rules ==========
    def get_rules(self, params: Dict = None) -> Dict[str, Any]:
        """Get rule list"""
        return self.get("/rules", params=params)

    def get_rule(self, rule_id: int) -> Dict[str, Any]:
        """Get single rule details"""
        return self.get(f"/rules/{rule_id}")

    def create_rule(self, data: Dict) -> Dict[str, Any]:
        """Create new rule"""
        return self.post("/rules", data=data)

    def update_rule(self, rule_id: int, data: Dict) -> Dict[str, Any]:
        """Update rule"""
        return self.put(f"/rules/{rule_id}", data=data)

    def delete_rule(self, rule_id: int) -> Dict[str, Any]:
        """Delete rule"""
        return self.delete(f"/rules/{rule_id}")

    def test_rule(self, rule_id: int, data: Dict = None) -> Dict[str, Any]:
        """Test a rule"""
        return self.post(f"/rules/{rule_id}/test", data=data)

    def execute_rule(self, rule_id: int) -> Dict[str, Any]:
        """Execute a rule"""
        return self.post(f"/rules/{rule_id}/trigger")

    # ========== Rule Groups ==========
    def get_rule_groups(self, params: Dict = None) -> Dict[str, Any]:
        """Get rule group list"""
        return self.get("/rule-groups", params=params)

    def get_rule_group(self, rule_group_id: int) -> Dict[str, Any]:
        """Get single rule group details"""
        return self.get(f"/rule-groups/{rule_group_id}")

    def create_rule_group(self, data: Dict) -> Dict[str, Any]:
        """Create new rule group"""
        return self.post("/rule-groups", data=data)

    def update_rule_group(self, rule_group_id: int, data: Dict) -> Dict[str, Any]:
        """Update rule group"""
        return self.put(f"/rule-groups/{rule_group_id}", data=data)

    def delete_rule_group(self, rule_group_id: int) -> Dict[str, Any]:
        """Delete rule group"""
        return self.delete(f"/rule-groups/{rule_group_id}")

    def execute_rule_group(self, rule_group_id: int) -> Dict[str, Any]:
        """Execute a rule group"""
        return self.post(f"/rule-groups/{rule_group_id}/trigger")

    # ========== Summary ==========
    def get_summary(self, summary_type: str, params: Dict = None) -> Dict[str, Any]:
        """Get summary report"""
        return self.get(f"/summary/{summary_type}", params=params)

    # ========== Webhooks ==========
    def get_webhooks(self, params: Dict = None) -> Dict[str, Any]:
        """Get webhook list"""
        return self.get("/webhooks", params=params)

    def get_webhook(self, webhook_id: int) -> Dict[str, Any]:
        """Get single webhook details"""
        return self.get(f"/webhooks/{webhook_id}")

    def create_webhook(self, data: Dict) -> Dict[str, Any]:
        """Create new webhook"""
        return self.post("/webhooks", data=data)

    def update_webhook(self, webhook_id: int, data: Dict) -> Dict[str, Any]:
        """Update webhook"""
        return self.put(f"/webhooks/{webhook_id}", data=data)

    def delete_webhook(self, webhook_id: int) -> Dict[str, Any]:
        """Delete webhook"""
        return self.delete(f"/webhooks/{webhook_id}")

    def trigger_webhook(self, webhook_id: int) -> Dict[str, Any]:
        """Trigger a webhook"""
        return self.post(f"/webhooks/{webhook_id}/trigger")

    # ========== Insights ==========
    def get_insight(self, insight_type: str, params: Dict = None) -> Dict[str, Any]:
        """Get insight report"""
        return self.get(f"/insight/{insight_type}", params=params)

    # ========== Search ==========
    def search(self, query: str, params: Dict = None) -> Dict[str, Any]:
        """Search transactions"""
        search_params = params or {}
        search_params['query'] = query
        return self.get("/search/transactions", params=search_params)

    # ========== Export ==========
    def export_data(self, data_type: str, params: Dict = None) -> Dict[str, Any]:
        """Export data"""
        return self.get(f"/data/export/{data_type}", params=params)

    # ========== Charts ==========
    def get_chart_account_overview(self, params: Dict) -> Dict[str, Any]:
        """Get account overview chart"""
        return self.get("/chart/account/overview", params=params)

    def get_chart_balance(self, params: Dict) -> Dict[str, Any]:
        """Get balance chart"""
        return self.get("/chart/balance/balance", params=params)

    def get_chart_budget_overview(self, params: Dict) -> Dict[str, Any]:
        """Get budget overview chart"""
        return self.get("/chart/budget/overview", params=params)

    def get_chart_category_overview(self, params: Dict) -> Dict[str, Any]:
        """Get category overview chart"""
        return self.get("/chart/category/overview", params=params)

    # ========== Available Budgets ==========
    def get_available_budgets(self, params: Dict = None) -> Dict[str, Any]:
        """Get available budgets"""
        return self.get("/available_budgets", params=params)

    def create_available_budget(self, data: Dict) -> Dict[str, Any]:
        """Create available budget"""
        return self.post("/available_budgets", data=data)

    def update_available_budget(self, available_budget_id: int, data: Dict) -> Dict[str, Any]:
        """Update available budget"""
        return self.put(f"/available_budgets/{available_budget_id}", data=data)

    def delete_available_budget(self, available_budget_id: int) -> Dict[str, Any]:
        """Delete available budget"""
        return self.delete(f"/available_budgets/{available_budget_id}")

    # ========== Object Groups ==========
    def get_object_groups(self, params: Dict = None) -> Dict[str, Any]:
        """Get object group list"""
        return self.get("/object-groups", params=params)

    def get_object_group(self, object_group_id: int) -> Dict[str, Any]:
        """Get single object group details"""
        return self.get(f"/object-groups/{object_group_id}")

    def create_object_group(self, data: Dict) -> Dict[str, Any]:
        """Create new object group"""
        return self.post("/object-groups", data=data)

    def update_object_group(self, object_group_id: int, data: Dict) -> Dict[str, Any]:
        """Update object group"""
        return self.put(f"/object-groups/{object_group_id}", data=data)

    def delete_object_group(self, object_group_id: int) -> Dict[str, Any]:
        """Delete object group"""
        return self.delete(f"/object-groups/{object_group_id}")

    # ========== Links ==========
    def get_links(self, params: Dict = None) -> Dict[str, Any]:
        """Get transaction link types"""
        return self.get("/links", params=params)

    def create_link(self, data: Dict) -> Dict[str, Any]:
        """Create transaction link type"""
        return self.post("/links", data=data)

    def update_link(self, link_id: int, data: Dict) -> Dict[str, Any]:
        """Update transaction link type"""
        return self.put(f"/links/{link_id}", data=data)

    def delete_link(self, link_id: int) -> Dict[str, Any]:
        """Delete transaction link type"""
        return self.delete(f"/links/{link_id}")

    # ========== Attachments ==========
    def get_attachments(self, params: Dict = None) -> Dict[str, Any]:
        """Get attachment list"""
        return self.get("/attachments", params=params)

    def get_attachment(self, attachment_id: int) -> Dict[str, Any]:
        """Get single attachment details"""
        return self.get(f"/attachments/{attachment_id}")

    def download_attachment(self, attachment_id: int) -> bytes:
        """Download attachment file"""
        url = f"{self.base_url}/api/v1/attachments/{attachment_id}/download"
        response = requests.get(url, headers=self.headers, timeout=30)
        response.raise_for_status()
        return response.content

    def create_attachment(self, data: Dict) -> Dict[str, Any]:
        """Create new attachment"""
        return self.post("/attachments", data=data)

    def update_attachment(self, attachment_id: int, data: Dict) -> Dict[str, Any]:
        """Update attachment"""
        return self.put(f"/attachments/{attachment_id}", data=data)

    def delete_attachment(self, attachment_id: int) -> Dict[str, Any]:
        """Delete attachment"""
        return self.delete(f"/attachments/{attachment_id}")

    # ========== Configuration ==========
    def get_configuration(self) -> Dict[str, Any]:
        """Get configuration"""
        return self.get("/configuration")

    def update_configuration(self, data: Dict) -> Dict[str, Any]:
        """Update configuration"""
        return self.put("/configuration", data=data)

    # ========== Preferences ==========
    def get_preferences(self) -> Dict[str, Any]:
        """Get user preferences"""
        return self.get("/preferences")

    def update_preference(self, key: str, data: Dict) -> Dict[str, Any]:
        """Update a preference"""
        return self.put(f"/preferences/{key}", data=data)

    # ========== Users ==========
    def get_users(self, params: Dict = None) -> Dict[str, Any]:
        """Get user list"""
        return self.get("/users", params=params)

    def get_user(self, user_id: int) -> Dict[str, Any]:
        """Get single user details"""
        return self.get(f"/users/{user_id}")

    def create_user(self, data: Dict) -> Dict[str, Any]:
        """Create new user"""
        return self.post("/users", data=data)

    def update_user(self, user_id: int, data: Dict) -> Dict[str, Any]:
        """Update user"""
        return self.put(f"/users/{user_id}", data=data)

    def delete_user(self, user_id: int) -> Dict[str, Any]:
        """Delete user"""
        return self.delete(f"/users/{user_id}")

    # ========== User Groups ==========
    def get_user_groups(self, params: Dict = None) -> Dict[str, Any]:
        """Get user group list"""
        return self.get("/user-groups", params=params)

    def get_user_group(self, user_group_id: int) -> Dict[str, Any]:
        """Get single user group details"""
        return self.get(f"/user-groups/{user_group_id}")

    # ========== Data ==========
    def bulk_update_transactions(self, data: Dict) -> Dict[str, Any]:
        """Bulk update transactions"""
        return self.post("/data/bulk/transactions", data=data)

    def destroy_data(self, data_type: str) -> Dict[str, Any]:
        """Destroy user data"""
        return self.delete(f"/data/destroy?objects={data_type}")

    def purge_data(self) -> Dict[str, Any]:
        """Purge deleted data"""
        return self.delete("/data/purge")
