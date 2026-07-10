"""End-to-end tests against the live Mailchimp API.

Skipped unless MAILCHIMP_API_KEY is set. Creates a throwaway audience,
exercises member and merge-field operations, then cleans up.

Run:
    MAILCHIMP_API_KEY=<key>-<dc> pytest tests/test_full_e2e.py -v -s
"""

from __future__ import annotations

import os
import uuid
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("MAILCHIMP_API_KEY"),
    reason="MAILCHIMP_API_KEY not set — skipping live API tests",
)

TEST_LIST_NAME = f"cli-anything-test-{uuid.uuid4().hex[:8]}"
TEST_EMAIL = f"cli-test-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(scope="module")
def client():
    from cli_anything.mailchimp.core.client import MailchimpClient

    return MailchimpClient()


@pytest.fixture(scope="module")
def test_list(client):
    """Create a throwaway Mailchimp audience, yield its ID, then delete it."""
    body = {
        "name": TEST_LIST_NAME,
        "contact": {
            "company": "CLI-Anything Test",
            "address1": "123 Test St",
            "city": "Testville",
            "state": "CA",
            "zip": "90210",
            "country": "US",
        },
        "permission_reminder": "test permission reminder",
        "email_type_option": False,
        "campaign_defaults": {
            "from_name": "CLI Test",
            "from_email": "test@example.com",
            "subject": "Test",
            "language": "en",
        },
    }
    result = client.post("/lists", json=body)
    list_id = result["id"]
    yield list_id
    # Cleanup — delete the test list
    try:
        client.delete(f"/lists/{list_id}")
    except Exception:
        pass


class TestPing:
    def test_ping(self, client):
        result = client.get("/ping")
        assert "health_status" in result


class TestLists:
    def test_get_lists(self, client):
        result = client.get("/lists", params={"count": 1})
        assert "lists" in result
        assert isinstance(result["lists"], list)

    def test_create_and_get_list(self, client, test_list):
        result = client.get(f"/lists/{test_list}")
        assert result["id"] == test_list
        assert result["name"] == TEST_LIST_NAME

    def test_update_list(self, client, test_list):
        new_name = TEST_LIST_NAME + "-updated"
        result = client.patch(f"/lists/{test_list}", json={"name": new_name})
        assert result["name"] == new_name
        # Restore
        client.patch(f"/lists/{test_list}", json={"name": TEST_LIST_NAME})


class TestMembers:
    def test_add_member(self, client, test_list):
        body = {
            "email_address": TEST_EMAIL,
            "status": "subscribed",
        }
        result = client.post(f"/lists/{test_list}/members", json=body)
        assert result["email_address"] == TEST_EMAIL
        assert result["status"] == "subscribed"

    def test_get_member(self, client, test_list):
        from cli_anything.mailchimp.core.client import subscriber_hash

        h = subscriber_hash(TEST_EMAIL)
        result = client.get(f"/lists/{test_list}/members/{h}")
        assert result["email_address"] == TEST_EMAIL

    def test_list_members(self, client, test_list):
        result = client.get(f"/lists/{test_list}/members", params={"count": 10})
        emails = [m["email_address"] for m in result.get("members", [])]
        assert TEST_EMAIL in emails

    def test_archive_member(self, client, test_list):
        from cli_anything.mailchimp.core.client import subscriber_hash

        h = subscriber_hash(TEST_EMAIL)
        result = client.delete(f"/lists/{test_list}/members/{h}")
        assert result == {"ok": True}


class TestMergeFields:
    def test_create_and_list_merge_fields(self, client, test_list):
        body = {"tag": "TESTFIELD", "name": "Test Field", "type": "text"}
        result = client.post(f"/lists/{test_list}/merge-fields", json=body)
        assert result["tag"] == "TESTFIELD"

        fields = client.get(f"/lists/{test_list}/merge-fields")
        tags = [f["tag"] for f in fields.get("merge_fields", [])]
        assert "TESTFIELD" in tags
