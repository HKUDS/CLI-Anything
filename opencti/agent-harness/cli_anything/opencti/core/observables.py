"""STIX Cyber Observable operations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from cli_anything.opencti.utils.opencti_backend import graphql_request, paginated

LIST_FIELDS = """
edges {
  node {
    id standard_id entity_type observable_value
    created_at updated_at
    x_opencti_score
    createdBy { name }
    objectMarking { definition }
  }
}
pageInfo { endCursor hasNextPage }
"""

DETAIL_FIELDS = """
id standard_id entity_type observable_value
created_at updated_at
x_opencti_score x_opencti_description
createdBy { name standard_id }
objectLabel { value color }
objectMarking { definition }
externalReferences { edges { node { source_name url description } } }
"""

TYPE_MAP = {
    "ipv4-addr": "IPv4-Addr",
    "ipv6-addr": "IPv6-Addr",
    "url": "Url",
    "domain-name": "Domain-Name",
    "file-sha256": "StixFile",
    "file-md5": "StixFile",
    "file-sha1": "StixFile",
    "email-addr": "Email-Addr",
}


def list_observables(
    *,
    search: Optional[str] = None,
    types: Optional[list] = None,
    first: int = 25,
    all_pages: bool = False,
    **kw,
):
    def fetch(after):
        q = f"""
        query ($first: Int, $after: ID, $search: String, $types: [String]) {{
          stixCyberObservables(first: $first, after: $after, search: $search, types: $types) {{
            {LIST_FIELDS}
          }}
        }}"""
        return graphql_request(q, {"first": first, "after": after, "search": search,
                                   "types": types}, **kw)["stixCyberObservables"]

    return paginated(fetch, max_pages=100 if all_pages else 1)


def get_observable(observable_id: str, *, with_stix: bool = False, **kw):
    fields = DETAIL_FIELDS + ("\ntoStix" if with_stix else "")
    q = f"""
    query ($id: String!) {{
      stixCyberObservable(id: $id) {{ {fields} }}
    }}"""
    return graphql_request(q, {"id": observable_id}, **kw)["stixCyberObservable"]


def export_observable_stix(observable_id: str, **kw) -> Optional[str]:
    data = get_observable(observable_id, with_stix=True, **kw)
    return data.get("toStix") if data else None


# ─── Writes ─────────────────────────────────────────────────────────────────

# cli type -> (GraphQL `type` arg value, typed input field name)
ADD_INPUTS = {
    "ipv4-addr": ("IPv4-Addr", "IPv4Addr"),
    "ipv6-addr": ("IPv6-Addr", "IPv6Addr"),
    "domain-name": ("Domain-Name", "DomainName"),
    "url": ("Url", "Url"),
    "hostname": ("Hostname", "Hostname"),
    "mac-addr": ("Mac-Addr", "MacAddr"),
    "email-addr": ("Email-Addr", "EmailAddr"),
}
FILE_TYPES = {
    "file-sha256": "SHA-256",
    "file-md5": "MD5",
    "file-sha1": "SHA-1",
}

ADD_RESULT_FIELDS = """
id standard_id entity_type observable_value
x_opencti_score x_opencti_description
"""


def add_observable(
    obs_type: str,
    value: str,
    *,
    score: Optional[int] = None,
    description: Optional[str] = None,
    labels: Optional[list] = None,
    create_indicator: bool = False,
    **kw,
) -> Dict[str, Any]:
    """Create a cyber observable; optionally auto-generate its indicator."""
    obs_type = obs_type.lower()
    if obs_type in FILE_TYPES:
        gql_type = "StixFile"
        typed_field = "StixFile"
        typed_value: Dict[str, Any] = {
            "hashes": [{"algorithm": FILE_TYPES[obs_type], "hash": value}]
        }
        var_type = "StixFileAddInput"
    elif obs_type in ADD_INPUTS:
        gql_type, typed_field = ADD_INPUTS[obs_type]
        typed_value = {"value": value}
        var_type = f"{typed_field}AddInput"
    else:
        raise ValueError(
            f"unsupported observable type '{obs_type}'. "
            f"Supported: {', '.join(sorted(ADD_INPUTS) + sorted(FILE_TYPES))}"
        )

    q = f"""
    mutation ($score: Int, $desc: String,
              $labels: [String], $ci: Boolean, $inp: {var_type}!) {{
      stixCyberObservableAdd(type: "{gql_type}", {typed_field}: $inp,
          x_opencti_score: $score, x_opencti_description: $desc,
          objectLabel: $labels, createIndicator: $ci) {{
        {ADD_RESULT_FIELDS}
      }}
    }}"""
    variables: Dict[str, Any] = {"ci": create_indicator, "inp": typed_value}
    if score is not None:
        variables["score"] = score
    if description:
        variables["desc"] = description
    if labels:
        variables["labels"] = [l.strip() for l in labels if l.strip()]
    result = graphql_request(q, variables, **kw)["stixCyberObservableAdd"]
    if not result:
        raise ValueError(f"observable creation failed for {value}")
    return result
