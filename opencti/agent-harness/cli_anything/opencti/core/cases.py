"""Case operations: incidents, RFIs, RFTs."""

from __future__ import annotations

from typing import Optional

from cli_anything.opencti.utils.opencti_backend import graphql_request, paginated

CASE_TYPES = {
    "incident": ("caseIncidents", "caseIncident"),
    "rfi": ("caseRfis", "caseRfi"),
    "rft": ("caseRfts", "caseRft"),
}

LIST_FIELDS = """
edges {
  node {
    id standard_id name severity priority created_at
    createdBy { name }
    objectMarking { definition }
  }
}
pageInfo { endCursor hasNextPage }
"""

DETAIL_FIELDS = """
id standard_id name description severity priority
created_at updated_at
createdBy { name standard_id }
objectLabel { value color }
objectMarking { definition }
objects(first: 50) {
  edges { node { ... on BasicObject { id standard_id entity_type } } }
}
"""


def _query_for(field_name: str, fields: str) -> str:
    return f"""
    query ($first: Int, $after: ID, $search: String) {{
      {field_name}(first: $first, after: $after, search: $search) {{
        {fields}
      }}
    }}"""


def list_cases(case_type: str = "incident", *, search: Optional[str] = None,
               first: int = 25, all_pages: bool = False, **kw):
    field = CASE_TYPES[case_type][0]

    def fetch(after):
        q = _query_for(field, LIST_FIELDS)
        return graphql_request(q, {"first": first, "after": after, "search": search},
                               **kw)[field]

    return paginated(fetch, max_pages=100 if all_pages else 1)


def get_case(case_type: str, case_id: str, **kw):
    q = f"""
    query ($id: String!) {{
      {CASE_TYPES[case_type][1]}(id: $id) {{ {DETAIL_FIELDS} }}
    }}"""
    return graphql_request(q, {"id": case_id}, **kw)[CASE_TYPES[case_type][1]]


# ─── Writes ─────────────────────────────────────────────────────────────────

ADD_RESULT_FIELDS = "id standard_id name created_at"

ADD_INPUT_NAMES = {
    "incident": "CaseIncidentAddInput",
    "rfi": "CaseRfiAddInput",
    "rft": "CaseRftAddInput",
}
MUTATION_NAMES = {
    "incident": "caseIncidentAdd",
    "rfi": "caseRfiAdd",
    "rft": "caseRftAdd",
}


def add_case(case_type: str, name: str, *, severity: Optional[str] = None,
             priority: Optional[str] = None, description: Optional[str] = None,
             labels: Optional[list] = None, **kw) -> Dict[str, Any]:
    """Create a case of the given type."""
    case_type = case_type.lower()
    input_name = ADD_INPUT_NAMES[case_type]
    mutation = MUTATION_NAMES[case_type]
    inp: Dict[str, Any] = {"name": name}
    if severity:
        inp["severity"] = severity.lower()
    if priority:
        inp["priority"] = priority.lower()
    if description:
        inp["description"] = description
    if labels:
        inp["objectLabel"] = [l.strip() for l in labels if l.strip()]
    q = f"""
    mutation ($input: {input_name}!) {{
      {mutation}(input: $input) {{ {ADD_RESULT_FIELDS} }}
    }}"""
    result = graphql_request(q, {"input": inp}, **kw)[mutation]
    if not result:
        raise ValueError(f"case creation failed for {name!r}")
    return result
