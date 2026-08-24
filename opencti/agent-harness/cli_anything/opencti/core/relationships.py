"""STIX core relationship operations."""

from __future__ import annotations

from cli_anything.opencti.utils.opencti_backend import graphql_request, paginated

REL_LIST_FIELDS = """
edges {
  node {
    id standard_id entity_type relationship_type
    created_at updated_at confidence
    from { ... on BasicObject { id standard_id entity_type } }
    to { ... on BasicObject { id standard_id entity_type } }
  }
}
pageInfo { endCursor hasNextPage }
"""


def list_relationships(*, first: int = 25, all_pages: bool = False, **kw):
    def fetch(after):
        q = f"""
        query ($first: Int, $after: ID) {{
          stixCoreRelationships(first: $first, after: $after) {{
            {REL_LIST_FIELDS}
          }}
        }}"""
        return graphql_request(q, {"first": first, "after": after}, **kw)[
            "stixCoreRelationships"
        ]

    return paginated(fetch, max_pages=100 if all_pages else 1)


# ─── Writes ─────────────────────────────────────────────────────────────────

ADD_RESULT_FIELDS = """
id standard_id relationship_type created_at
from { ... on BasicObject { id standard_id entity_type } }
to { ... on BasicObject { id standard_id entity_type } }
"""


def add_relationship(from_id: str, to_id: str, relationship_type: str, *,
                     description: Optional[str] = None,
                     start_time: Optional[str] = None,
                     stop_time: Optional[str] = None, **kw):
    """Create a STIX core relationship between two objects."""
    inp: Dict[str, Any] = {"fromId": from_id, "toId": to_id,
                           "relationship_type": relationship_type}
    if description:
        inp["description"] = description
    if start_time:
        inp["start_time"] = start_time
    if stop_time:
        inp["stop_time"] = stop_time
    q = f"""
    mutation ($input: StixCoreRelationshipAddInput!) {{
      stixCoreRelationshipAdd(input: $input) {{ {ADD_RESULT_FIELDS} }}
    }}"""
    result = graphql_request(q, {"input": inp}, **kw)["stixCoreRelationshipAdd"]
    if not result:
        raise ValueError("relationship creation failed")
    return result


def delete_relationship(relationship_id: str, **kw) -> Any:
    """Delete a relationship by its ID (destructive)."""
    q = """
    mutation ($id: ID!) {
      stixCoreRelationshipEdit(id: $id) { delete }
    }"""
    return graphql_request(q, {"id": relationship_id}, **kw)[
        "stixCoreRelationshipEdit"
    ]["delete"]
