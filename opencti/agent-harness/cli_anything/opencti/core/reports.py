"""Report operations."""

from __future__ import annotations

from typing import Optional

from cli_anything.opencti.utils.opencti_backend import graphql_request, paginated

LIST_FIELDS = """
edges {
  node {
    id standard_id name published report_types
    created_at updated_at
    createdBy { name }
    objectMarking { definition }
  }
}
pageInfo { endCursor hasNextPage }
"""

DETAIL_FIELDS = """
id standard_id name description published report_types
created_at updated_at
createdBy { name standard_id }
objectLabel { value color }
objectMarking { definition }
objects(first: 50) {
  edges { node { ... on BasicObject { id standard_id entity_type } } }
}
"""


def list_reports(*, search: Optional[str] = None, first: int = 25,
                 all_pages: bool = False, **kw):
    def fetch(after):
        q = f"""
        query ($first: Int, $after: ID, $search: String) {{
          reports(first: $first, after: $after, search: $search) {{
            {LIST_FIELDS}
          }}
        }}"""
        return graphql_request(q, {"first": first, "after": after, "search": search},
                               **kw)["reports"]

    return paginated(fetch, max_pages=100 if all_pages else 1)


def get_report(report_id: str, **kw):
    q = f"""
    query ($id: String!) {{
      report(id: $id) {{ {DETAIL_FIELDS} }}
    }}"""
    return graphql_request(q, {"id": report_id}, **kw)["report"]


# ─── Writes ─────────────────────────────────────────────────────────────────

ADD_RESULT_FIELDS = "id standard_id name published created_at"


def add_report(name: str, *, published: Optional[str] = None,
               description: Optional[str] = None, report_types: Optional[list] = None,
               labels: Optional[list] = None, **kw) -> Dict[str, Any]:
    """Create a threat intelligence report."""
    inp: Dict[str, Any] = {"name": name}
    if published:
        inp["published"] = published
    if description:
        inp["description"] = description
    if report_types:
        inp["report_types"] = [t.strip() for t in report_types if t.strip()]
    if labels:
        inp["objectLabel"] = [l.strip() for l in labels if l.strip()]
    q = """
    mutation ($input: ReportAddInput!) {
      reportAdd(input: $input) { %s }
    }""" % ADD_RESULT_FIELDS
    result = graphql_request(q, {"input": inp}, **kw)["reportAdd"]
    if not result:
        raise ValueError(f"report creation failed for {name!r}")
    return result
