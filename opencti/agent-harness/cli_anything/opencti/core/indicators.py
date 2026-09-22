"""Indicator operations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from cli_anything.opencti.utils.opencti_backend import graphql_request, paginated

LIST_FIELDS = """
edges {
  node {
    id standard_id name pattern pattern_type
    valid_from valid_until confidence
    created_at updated_at
    createdBy { name }
    objectMarking { definition }
  }
}
pageInfo { endCursor hasNextPage }
"""

DETAIL_FIELDS = """
id standard_id name description pattern pattern_type
valid_from valid_until confidence revoked
created_at updated_at
createdBy { name standard_id }
objectLabel { value color }
objectMarking { definition }
externalReferences { source_name url }
"""


def list_indicators(
    *,
    search: Optional[str] = None,
    first: int = 25,
    all_pages: bool = False,
    **kw,
):
    def fetch(after):
        q = f"""
        query ($first: Int, $after: ID, $search: String) {{
          indicators(first: $first, after: $after, search: $search) {{
            {LIST_FIELDS}
          }}
        }}"""
        return graphql_request(q, {"first": first, "after": after, "search": search},
                               **kw)["indicators"]

    return paginated(fetch, max_pages=100 if all_pages else 1)


def get_indicator(indicator_id: str, **kw):
    q = f"""
    query ($id: String!) {{
      indicator(id: $id) {{ {DETAIL_FIELDS} }}
    }}"""
    return graphql_request(q, {"id": indicator_id}, **kw)["indicator"]


def search_by_pattern(pattern: str, *, first: int = 25, **kw):
    """Find indicators whose STIX pattern matches the given substring."""
    filters = {"mode": "and",
               "filters": [{"key": "pattern", "values": [pattern], "operator": "starts_with"}],
               "filterGroups": []}

    def fetch(after):
        q = f"""
        query ($first: Int, $after: ID, $filters: FilterGroup) {{
          indicators(first: $first, after: $after, filters: $filters) {{ {LIST_FIELDS} }}
        }}"""
        return graphql_request(q, {"first": first, "after": after,
                                   "filters": filters}, **kw)["indicators"]

    return paginated(fetch, max_pages=1)


# ─── Writes ─────────────────────────────────────────────────────────────────

ADD_RESULT_FIELDS = """
id standard_id name pattern pattern_type
x_opencti_score valid_from valid_until
"""


def add_indicator(name: str, pattern: str, *, pattern_type: str = "stix",
                  score: Optional[int] = None, description: Optional[str] = None,
                  valid_until: Optional[str] = None, labels: Optional[list] = None,
                  **kw) -> Dict[str, Any]:
    """Create an indicator from a detection pattern."""
    inp: Dict[str, Any] = {"name": name, "pattern": pattern,
                           "pattern_type": pattern_type}
    if score is not None:
        inp["x_opencti_score"] = score
    if description:
        inp["description"] = description
    if valid_until:
        inp["valid_until"] = valid_until
    if labels:
        inp["objectLabel"] = [l.strip() for l in labels if l.strip()]
    q = """
    mutation ($input: IndicatorAddInput!) {
      indicatorAdd(input: $input) { %s }
    }""" % ADD_RESULT_FIELDS
    result = graphql_request(q, {"input": inp}, **kw)["indicatorAdd"]
    if not result:
        raise ValueError(f"indicator creation failed for {name!r}")
    return result


def delete_indicator(indicator_id: str, **kw) -> Any:
    """Delete an indicator by ID."""
    q = """
    mutation ($id: ID!) { indicatorDelete(id: $id) }"""
    return graphql_request(q, {"id": indicator_id}, **kw)["indicatorDelete"]
