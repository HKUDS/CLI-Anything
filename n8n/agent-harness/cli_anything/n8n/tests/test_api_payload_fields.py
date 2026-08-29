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
from unittest.mock import patch

import pytest
import requests

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
    "parentFolderId": "fld123",
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
    "parentFolderId",
)


def strip_server_fields(data):
    """`_strip_server_fields` via the module, so upstream builds skip instead of erroring."""
    fn = getattr(n8n_cli, "_strip_server_fields", None)
    if fn is None:
        pytest.skip("_strip_server_fields not present in this build")
    return fn(data)


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

    def test_drops_nulls_for_non_nullable_properties(self):
        """`description` is a plain string in the schema, so a null round-trip 400s.

        A workflow with no description reads back as `"description": null`, which is
        exactly what a backup or an export then tries to send.
        """
        cleaned = _clean_for_api({**SERVER_WORKFLOW, "description": None})
        assert "description" not in cleaned

    def test_keeps_nulls_for_nullable_properties(self):
        """For these, null is the only way to clear the value — dropping it is a bug.

        `versions rollback` restores a snapshot: one taken before any pinned data was
        added carries `pinData: null`, and omitting that key would leave today's
        pinned data in place while the command reports a successful rollback.
        """
        cleaned = _clean_for_api(
            {**SERVER_WORKFLOW, "pinData": None, "staticData": None, "parentFolderId": None}
        )
        assert cleaned["pinData"] is None
        assert cleaned["staticData"] is None
        assert cleaned["parentFolderId"] is None  # documented as "move to the project root"

    def test_always_supplies_the_required_settings_object(self):
        """`settings` is required by the schema; handwritten and older exports omit it."""
        wf = {k: v for k, v in SERVER_WORKFLOW.items() if k != "settings"}
        assert _clean_for_api(wf)["settings"] == {}
        assert _clean_for_api({**SERVER_WORKFLOW, "settings": None})["settings"] == {}

    def test_leaves_a_non_object_settings_for_the_server_to_reject(self):
        """Replacing it with `{}` would drop what the caller wrote without saying so.

        `settings` has to be an object, so a string or a list is invalid input — but
        that is the server's verdict to give, by name.
        """
        for bad in ("nope", [1], 5):
            assert _clean_for_api({**SERVER_WORKFLOW, "settings": bad})["settings"] == bad

    def test_reduces_the_nested_settings_object_too(self):
        """The nested object is additionalProperties:false as well, so an unreduced
        settings block fails the request even when the top level is clean."""
        wf = {**SERVER_WORKFLOW, "settings": {"executionOrder": "v1", "notASetting": 1}}
        assert _clean_for_api(wf)["settings"] == {"executionOrder": "v1"}

    def test_keeps_settings_that_only_newer_schemas_define(self):
        """`binaryMode` is written into every workflow by the editor and became
        writable in 2.33.3, so stripping it here would reset the user's choice on a
        current instance. An older instance rejects it, and the cross-version retry
        is what drops it — at the cost of one failed request, which beats silently
        changing a setting.
        """
        wf = {**SERVER_WORKFLOW, "settings": {"executionOrder": "v1", "binaryMode": "separate"}}
        assert _clean_for_api(wf)["settings"]["binaryMode"] == "separate"

    def test_drops_shared_even_though_the_api_tolerates_it(self):
        """`shared` is ownership data, not part of the definition.

        Unlike the rejected fields it does not draw a 400 — the API answers 200 and
        ignores it (confirmed by reading the workflow back afterwards). That is
        precisely why it needs pinning here: a failing request would not catch it.
        """
        assert "shared" not in _clean_for_api(SERVER_WORKFLOW)

    def test_export_output_can_be_fed_back_to_update(self, tmp_path):
        """Helper-level stand-in for `workflow export` -> `workflow update @file.json`.

        It repeats what those two commands do to the payload rather than invoking
        them, so it pins the reduction, not the click plumbing.
        """
        exported = strip_server_fields(SERVER_WORKFLOW)  # what workflow_export writes
        out = tmp_path / "export.json"
        out.write_text(json.dumps(exported, indent=2))

        payload = _clean_for_api(_load_json_arg(f"@{out}"))  # what workflow_update sends
        leaked = [f for f in REJECTED_BY_API if f in payload]
        assert not leaked, f"export cannot be fed back into update, extra fields: {leaked}"


# ─── Local-only payload ─────────────────────────────────────────────────────

class TestLocalPayload:
    def test_backup_keeps_state_the_api_refuses(self):
        """A backup that drops `active`/`tags` cannot restore what it recorded."""
        kept = strip_server_fields(SERVER_WORKFLOW)
        for field in ("active", "tags", "isArchived"):
            assert field in kept, f"{field} must stay in a backup"

    def test_backup_drops_instance_specific_fields(self):
        kept = strip_server_fields(SERVER_WORKFLOW)
        for field in ("id", "createdAt", "updatedAt", "versionId", "shared"):
            assert field not in kept

    def test_diff_can_still_see_a_state_only_change(self):
        """Two workflows differing only in `active` must not compare as identical."""
        a = {**SERVER_WORKFLOW, "active": False}
        b = {**SERVER_WORKFLOW, "active": True}
        assert strip_server_fields(a) != strip_server_fields(b)


# ─── Tag reassignment ───────────────────────────────────────────────────────

class TestReapplyTags:
    """`tags` is readOnly on the workflow body and has its own endpoint.

    Anything that recreates or rewinds a workflow therefore loses its tags unless
    they are set separately — and loses them *silently*, since the create itself
    succeeds.
    """

    @staticmethod
    def _reapply():
        fn = getattr(n8n_cli, "_reapply_tags", None)
        if fn is None:
            pytest.skip("_reapply_tags not present in this build")
        return fn

    def test_leaves_tags_alone_when_the_source_recorded_none(self):
        """An older export has no `tags` key at all — that is not "clear the tags"."""
        with patch.object(n8n_cli.workflows, "update_workflow_tags") as mock_put:
            self._reapply()("wf1", None, {})
            mock_put.assert_not_called()

    def test_clears_tags_when_the_source_had_an_empty_list(self):
        """Rolling back to a snapshot taken before any tag existed must remove them."""
        with patch.object(n8n_cli.workflows, "update_workflow_tags") as mock_put:
            self._reapply()("wf1", [], {})
            mock_put.assert_called_once_with("wf1", [])

    def test_sends_only_ids(self):
        """A backup records the whole tag object; the endpoint takes ids."""
        tags = [{"id": "t1", "name": "prod", "createdAt": "2026-01-01"}, {"name": "no id"}]
        with patch.object(n8n_cli.workflows, "update_workflow_tags") as mock_put:
            self._reapply()("wf1", tags, {})
            mock_put.assert_called_once_with("wf1", [{"id": "t1"}])

    def test_leaves_tags_alone_when_none_of_them_carry_an_id(self):
        """An unreadable record must not be treated as "the source had no tags".

        Filtering the ids out of a non-empty list yields an empty list, and sending
        that would clear every tag on the workflow.
        """
        with patch.object(n8n_cli.workflows, "update_workflow_tags") as mock_put:
            self._reapply()("wf1", [{"name": "prod"}, {"nope": 1}], {})
            mock_put.assert_not_called()

    def test_survives_a_tags_value_that_is_not_a_list(self):
        """A scalar would raise on iteration — after the workflow already exists.

        The caller would then report a failure for something that was created, and
        a `restore-all` retry would duplicate it.
        """
        for bad in (1, 1.5, True):
            with patch.object(n8n_cli.workflows, "update_workflow_tags") as mock_put:
                self._reapply()("wf1", bad, {})  # must not raise
                mock_put.assert_not_called()

    def test_survives_a_timeout_not_just_an_http_error(self):
        """The workflow is already created; a tag timeout must not fail the caller.

        `restore-all` would otherwise count the file as failed and a retry would
        create a duplicate workflow.
        """
        for err in (requests.exceptions.Timeout(), requests.exceptions.ConnectionError()):
            with patch.object(n8n_cli.workflows, "update_workflow_tags", side_effect=err):
                self._reapply()("wf1", [{"id": "t1"}], {})  # must not raise

    def test_reports_but_does_not_raise_when_the_ids_are_unknown(self):
        """Restoring into a different instance answers 404 Some tags not found.

        The workflow itself is already created at that point, so failing the whole
        restore over its tags would lose more than it protects.
        """
        err = requests.exceptions.HTTPError("404 Some tags not found")
        with patch.object(n8n_cli.workflows, "update_workflow_tags", side_effect=err):
            self._reapply()("wf1", [{"id": "gone"}], {})  # must not raise

    def test_export_keeps_tags_so_import_can_restore_them(self):
        """`export` writes the local form; the tags are what `import` reattaches.

        Reducing the export to the writable set instead would drop them silently —
        the file would still import, just without its tags.
        """
        exported = strip_server_fields({**SERVER_WORKFLOW, "tags": [{"id": "t1", "name": "prod"}]})
        assert exported["tags"] == [{"id": "t1", "name": "prod"}]


# ─── Cross-version writes ───────────────────────────────────────────────────

class TestNewerSchemaFallback:
    """A file exported from n8n 2.33.3+ has to remain importable into an older one.

    `nodeGroups` and `parentFolderId` do not exist in the older schema, whose
    additionalProperties:false rejects the whole request.
    """

    @staticmethod
    def _send():
        fn = getattr(n8n_cli, "_send_workflow", None)
        if fn is None:
            pytest.skip("_send_workflow not present in this build")
        return fn

    @staticmethod
    def _http_error(status, message="request/body must NOT have additional properties"):
        resp = type("R", (), {"status_code": status, "json": lambda self: {"message": message}})()
        return requests.exceptions.HTTPError(response=resp)

    def test_retries_without_the_newer_properties(self):
        seen = []

        def send(body):
            seen.append(dict(body))
            if "nodeGroups" in body:
                raise self._http_error(400)
            return {"id": "wf1"}

        payload = {"name": "x", "nodes": [], "nodeGroups": [{"name": "g"}], "parentFolderId": "f1"}
        assert self._send()(send, payload) == {"id": "wf1"}
        assert len(seen) == 2
        assert "nodeGroups" not in seen[1] and "parentFolderId" not in seen[1]
        assert seen[1]["name"] == "x"  # everything else survives

    def test_also_strips_newer_properties_nested_in_settings(self):
        """`settings` is additionalProperties:false too — dropping only the outer
        ones would retry and fail on the same request."""
        seen = []

        def send(body):
            seen.append({**body, "settings": dict(body.get("settings", {}))})
            if "binaryMode" in body.get("settings", {}):
                raise self._http_error(400)
            return {"id": "wf1"}

        payload = {
            "name": "x",
            "nodes": [],
            "settings": {"executionOrder": "v1", "binaryMode": "separate"},
        }
        assert self._send()(send, payload) == {"id": "wf1"}
        assert len(seen) == 2
        assert seen[1]["settings"] == {"executionOrder": "v1"}

    def test_does_not_retry_when_the_payload_has_none_of_them(self):
        """A 400 about something else must surface, not be masked by a pointless retry."""
        calls = []

        def send(body):
            calls.append(body)
            raise self._http_error(400)

        with pytest.raises(requests.exceptions.HTTPError):
            self._send()(send, {"name": "x", "nodes": []})
        assert len(calls) == 1

    def test_does_not_retry_on_other_status_codes(self):
        def send(body):
            raise self._http_error(401)

        with pytest.raises(requests.exceptions.HTTPError):
            self._send()(send, {"name": "x", "nodeGroups": []})

    def test_does_not_retry_when_the_400_is_about_a_bad_value(self):
        """A rejected *value* must surface, not be silenced by dropping the property.

        n8n answers `must be number` / `must be string` for these, as opposed to
        `must NOT have additional properties`. Retrying without the property would
        drop configuration the caller asked for and then report success — which is
        worse than the original failure, because it looks like it worked.
        """
        calls = []

        def send(body):
            calls.append(body)
            raise self._http_error(400, "request/body/settings/executionTimeout must be number")

        payload = {"name": "x", "nodes": [], "nodeGroups": [{"name": "g"}]}
        with pytest.raises(requests.exceptions.HTTPError):
            self._send()(send, payload)
        assert len(calls) == 1, "a bad value must not trigger the compatibility retry"

    def test_does_not_retry_when_the_offending_property_is_nested_deeper(self):
        """Same wording, different meaning: this is malformed input, not a version gap.

        A grouping whose item carries an unexpected member reports
        `request/body/nodeGroups/0 must NOT have additional properties`. Treating
        that as a compatibility problem would drop the entire grouping and could
        then succeed — turning invalid input into a success that lost data.
        """
        for path in ("request/body/nodeGroups/0", "request/body/nodes/0"):
            calls = []

            def send(body):
                calls.append(body)
                raise self._http_error(400, f"{path} must NOT have additional properties")

            with pytest.raises(requests.exceptions.HTTPError):
                self._send()(send, {"name": "x", "nodeGroups": [{"name": "g", "bogus": 1}]})
            assert len(calls) == 1, f"{path} must not trigger the compatibility retry"

    def test_retries_for_both_reducible_paths(self):
        """The two levels the retry actually reduces."""
        for path in ("request/body", "request/body/settings"):
            calls = []

            def send(body):
                calls.append(body)
                if len(calls) == 1:
                    raise self._http_error(400, f"{path} must NOT have additional properties")
                return {"id": "wf1"}

            payload = {"name": "x", "nodeGroups": [], "settings": {"binaryMode": "separate"}}
            assert self._send()(send, payload) == {"id": "wf1"}
            assert len(calls) == 2

    def test_does_not_retry_when_the_error_body_is_unreadable(self):
        """No message to inspect means no evidence for a compatibility problem."""
        resp = type("R", (), {"status_code": 400, "json": lambda self: (_ for _ in ()).throw(ValueError())})()
        calls = []

        def send(body):
            calls.append(body)
            raise requests.exceptions.HTTPError(response=resp)

        with pytest.raises(requests.exceptions.HTTPError):
            self._send()(send, {"name": "x", "nodeGroups": []})
        assert len(calls) == 1



# ─── Diagnostics ────────────────────────────────────────────────────────────

class TestDiagnosticsStream:
    def test_fallback_diagnostics_go_to_stderr(self, capsys):
        """`--json` output has to stay parseable when a fallback fires.

        `warn()` prints to stdout, so the diagnostics on these paths deliberately
        do not use it.
        """
        diag = getattr(n8n_cli, "_diag", None)
        if diag is None:
            pytest.skip("_diag not present in this build")
        diag("something happened")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "something happened" in captured.err
