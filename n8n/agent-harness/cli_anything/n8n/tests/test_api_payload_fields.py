"""Payload shape for workflow writes.

The n8n public API workflow schema sets `additionalProperties: false` and marks
`active`, `tags`, `meta`, `isArchived`, `triggerCount` and the id/timestamp fields
`readOnly`, so a create/update body carrying any of them is rejected outright with
`400 - request/body must NOT have additional properties`.

Every command that edits an existing workflow builds its payload from a GET
response, so the payload has to be reduced first. These tests pin that reduction and
keep it distinct from the local-only reduction used by backups and diffs, which has
to preserve exactly the state the API refuses.

No n8n instance required.
"""

import json

import pytest

from cli_anything.n8n import n8n_cli
from cli_anything.n8n.n8n_cli import _clean_for_api, _load_json_arg

# Every key a GET /workflows/{id} returns on n8n 2.16.1, plus the two properties the
# schema gained by 2.33.3 (`nodeGroups`, `parentFolderId`).
SERVER_WORKFLOW = {
    "id": "abc123",
    "name": "Test WF",
    "nodes": [{"type": "n8n-nodes-base.manualTrigger"}],
    "connections": {},
    "settings": {},
    "staticData": {"lastId": 1},
    "pinData": {"Test Node": [{"json": {"x": 1}}]},
    "description": "a description",
    "nodeGroups": [{"name": "group A"}],
    "active": False,
    "activeVersion": None,
    "activeVersionId": None,
    "isArchived": False,
    "meta": {},
    "tags": [],
    "triggerCount": 0,
    "versionCounter": 1,
    "versionId": "v1",
    "createdAt": "2026-01-01",
    "updatedAt": "2026-01-02",
    "shared": [{"role": "owner"}],
}

# readOnly in the schema, or absent from it entirely. Each one draws a 400.
REJECTED_BY_API = (
    "active",
    "activeVersion",
    "activeVersionId",
    "isArchived",
    "meta",
    "tags",
    "triggerCount",
    "versionCounter",
    "id",
    "createdAt",
    "updatedAt",
    "versionId",
)

# Writable per the schema, and confirmed to persist by reading the workflow back.
WRITABLE = (
    "name",
    "description",
    "nodes",
    "connections",
    "settings",
    "staticData",
    "pinData",
    "nodeGroups",
)


# ─── Write payload ──────────────────────────────────────────────────────────

class TestWritePayload:
    def test_drops_every_field_the_api_rejects(self):
        cleaned = _clean_for_api(SERVER_WORKFLOW)
        leaked = [f for f in REJECTED_BY_API if f in cleaned]
        assert not leaked, f"payload would be rejected by n8n, extra fields: {leaked}"

    def test_keeps_writable_fields(self):
        """Narrowing this further would silently discard user data.

        pinData holds pinned sample data, staticData holds stateful-trigger cursors
        and nodeGroups holds the canvas grouping — none of them survive an edit that
        drops them, and none of them fail loudly.
        """
        cleaned = _clean_for_api(SERVER_WORKFLOW)
        for field in WRITABLE:
            assert field in cleaned, f"{field} must survive a workflow edit"

    def test_drops_a_field_the_schema_does_not_define(self):
        """A key from a future n8n release must not reach the API by default.

        This is what a blacklist cannot do: it only removes what it already knows.
        """
        cleaned = _clean_for_api({**SERVER_WORKFLOW, "someFieldAddedLater": "x"})
        assert "someFieldAddedLater" not in cleaned

    def test_drops_nulls_read_back_from_the_server(self):
        """`description` is a plain string in the schema, so a null round-trip 400s.

        A workflow with no description reads back as `"description": null`, which is
        exactly what a backup or an export then tries to send.
        """
        cleaned = _clean_for_api({**SERVER_WORKFLOW, "description": None})
        assert "description" not in cleaned

    def test_reduces_the_nested_settings_object_too(self):
        """Every workflow made in the n8n editor carries `binaryMode` in settings.

        The nested object is additionalProperties:false as well, so an unreduced
        settings block fails the request even when the top level is clean.
        """
        wf = {**SERVER_WORKFLOW, "settings": {"executionOrder": "v1", "binaryMode": "separate"}}
        assert _clean_for_api(wf)["settings"] == {"executionOrder": "v1"}

    def test_export_output_can_be_fed_back_to_update(self, tmp_path):
        """Helper-level stand-in for `workflow export` -> `workflow update @file.json`.

        It repeats what those two commands do to the payload rather than invoking
        them, so it pins the reduction, not the click plumbing.
        """
        exported = _clean_for_api(SERVER_WORKFLOW)
        out = tmp_path / "export.json"
        out.write_text(json.dumps(exported, indent=2))

        payload = _load_json_arg(f"@{out}")
        payload.pop("active", None)  # workflow_update drops this before the PUT
        leaked = [f for f in REJECTED_BY_API if f in payload]
        assert not leaked, f"export cannot be fed back into update, extra fields: {leaked}"


# ─── Local-only payload ─────────────────────────────────────────────────────

class TestLocalPayload:
    @staticmethod
    def _strip(data):
        strip = getattr(n8n_cli, "_strip_server_fields", None)
        if strip is None:
            pytest.skip("_strip_server_fields not present in this build")
        return strip(data)

    def test_backup_keeps_state_the_api_refuses(self):
        """A backup that drops `active`/`tags` cannot restore what it recorded."""
        kept = self._strip(SERVER_WORKFLOW)
        for field in ("active", "tags", "isArchived"):
            assert field in kept, f"{field} must stay in a backup"

    def test_backup_drops_instance_specific_fields(self):
        kept = self._strip(SERVER_WORKFLOW)
        for field in ("id", "createdAt", "updatedAt", "versionId", "shared"):
            assert field not in kept

    def test_diff_can_still_see_a_state_only_change(self):
        """Two workflows differing only in `active` must not compare as identical."""
        a = {**SERVER_WORKFLOW, "active": False}
        b = {**SERVER_WORKFLOW, "active": True}
        assert self._strip(a) != self._strip(b)
