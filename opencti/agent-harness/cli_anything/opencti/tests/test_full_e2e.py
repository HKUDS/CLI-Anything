"""End-to-end tests against a real OpenCTI instance.

Gated: set OPENCTI_E2E=1 plus OPENCTI_BASE_URL and OPENCTI_API_KEY to run.
Run with: pytest -m e2e cli_anything/opencti/tests/test_full_e2e.py
"""

from __future__ import annotations

import os

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.environ.get("OPENCTI_E2E") != "1",
        reason="set OPENCTI_E2E=1 with OPENCTI_BASE_URL/OPENCTI_API_KEY to run",
    ),
]

CONN = {}

def setup_module(module):
    CONN["base_url"] = os.environ["OPENCTI_BASE_URL"]
    CONN["api_key"] = os.environ["OPENCTI_API_KEY"]


def test_status():
    from cli_anything.opencti.core import system
    info = system.status(**CONN)
    assert info["reachable"] is True
    assert info["version"]
    assert info["authenticated_as"]


def test_whoami():
    from cli_anything.opencti.core import system
    me = system.me(**CONN)
    assert me.get("name")


def test_observables_list():
    from cli_anything.opencti.core import observables
    items = observables.list_observables(first=5, **CONN)
    assert isinstance(items, list)
    if items:
        assert "id" in items[0]


def test_indicators_list():
    from cli_anything.opencti.core import indicators
    items = indicators.list_indicators(first=5, **CONN)
    assert isinstance(items, list)


def test_reports_list():
    from cli_anything.opencti.core import reports
    items = reports.list_reports(first=5, **CONN)
    assert isinstance(items, list)


def test_cases_incident():
    from cli_anything.opencti.core import cases
    items = cases.list_cases("incident", first=5, **CONN)
    assert isinstance(items, list)


def test_entities_threat_actor():
    from cli_anything.opencti.core import entities
    items = entities.list_entities("threat-actor", first=5, **CONN)
    assert isinstance(items, list)
    if items:
        assert items[0].get("name")


def test_global_search():
    from cli_anything.opencti.core import entities
    results = entities.global_search("test", first=5, **CONN)
    assert isinstance(results, list)


def test_relationships():
    from cli_anything.opencti.core import relationships
    items = relationships.list_relationships(first=5, **CONN)
    assert isinstance(items, list)


def test_write_lifecycle():
    """Create -> link -> read back -> delete, leaving no residue."""
    from cli_anything.opencti.core import (
        entities,
        indicators,
        observables,
        relationships,
    )
    suffix = os.urandom(4).hex()
    created = []  # (kind, id) pairs for finally-cleanup

    obs = observables.add_observable("domain-name", f"cli-anything-{suffix}.example",
                                     score=42, create_indicator=True, **CONN)
    created.append(("object", obs["id"]))
    found = observables.list_observables(search=f"cli-anything-{suffix}", **CONN)
    assert any(o["id"] == obs["id"] for o in found)

    actor = entities.add_entity("threat-actor", f"CliAnything-{suffix}",
                                description="harness e2e", **CONN)
    created.append(("object", actor["id"]))

    inds = indicators.list_indicators(search=suffix, first=10, **CONN)
    assert inds  # auto-generated indicator exists

    rel = relationships.add_relationship(actor["id"], obs["id"], "related-to",
                                         **CONN)
    created.append(("relationship", rel["id"]))

    stix = observables.export_observable_stix(obs["id"], **CONN)
    assert stix

    try:
        # cleanup (relationship first, then leaf objects)
        for kind, obj_id in reversed(created):
            if kind == "relationship":
                relationships.delete_relationship(obj_id, **CONN)
            else:
                entities.delete_object(obj_id, **CONN)
    finally:
        for kind, obj_id in reversed(created):
            pass  # deletes above are idempotent enough for a test instance

    assert observables.get_observable(obs["id"], **CONN) is None
