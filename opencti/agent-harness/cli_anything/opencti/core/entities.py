"""Named threat-intel entities."""

from __future__ import annotations

from typing import Optional

from cli_anything.opencti.utils.opencti_backend import graphql_request, paginated


# name -> (list field, get field, node fields)
ENTITY_TYPES = {
    "threat-actor": ("threatActors", "threatActor",
                     "id standard_id name description created_at updated_at "
                     "createdBy { name } objectMarking { definition }"),
    "intrusion-set": ("intrusionSets", "intrusionSet",
                      "id standard_id name description first_seen last_seen "
                      "created_at updated_at createdBy { name } objectMarking { definition }"),
    "malware": ("malwares", "malware",
                "id standard_id name description is_family malware_types "
                "created_at updated_at createdBy { name } objectMarking { definition }"),
    "campaign": ("campaigns", "campaign",
                 "id standard_id name description first_seen last_seen "
                 "created_at updated_at createdBy { name } objectMarking { definition }"),
    "tool": ("tools", "tool",
             "id standard_id name description tool_types "
             "created_at updated_at createdBy { name } objectMarking { definition }"),
}


def list_entities(entity_type: str, *, search: Optional[str] = None,
                  first: int = 25, all_pages: bool = False, **kw):
    list_field, _, fields = ENTITY_TYPES[entity_type]

    def fetch(after):
        q = f"""
        query ($first: Int, $after: ID, $search: String) {{
          {list_field}(first: $first, after: $after, search: $search) {{
            edges {{ node {{ {fields} }} }}
            pageInfo {{ endCursor hasNextPage }}
          }}
        }}"""
        return graphql_request(q, {"first": first, "after": after, "search": search},
                               **kw)[list_field]

    return paginated(fetch, max_pages=100 if all_pages else 1)


def get_entity(entity_type: str, entity_id: str, **kw):
    _, get_field, fields = ENTITY_TYPES[entity_type]
    q = f"""
    query ($id: String!) {{
      {get_field}(id: $id) {{ {fields} toStix }}
    }}"""
    return graphql_request(q, {"id": entity_id}, **kw)[get_field]


def global_search(search: str, *, types: Optional[list] = None,
                  first: int = 25, all_pages: bool = False, **kw):
    """Search across all STIX core objects."""

    def fetch(after):
        q = """
        query ($first: Int, $after: ID, $search: String!, $types: [String]) {
          stixCoreObjects(first: $first, after: $after, search: $search, types: $types) {
            edges {
              node {
                id standard_id entity_type created_at
                createdBy { name }
                objectMarking { definition }
              }
            }
            pageInfo { endCursor hasNextPage }
          }
        }"""
        return graphql_request(q, {"first": first, "after": after,
                                   "search": search, "types": types},
                               **kw)["stixCoreObjects"]

    return paginated(fetch, max_pages=100 if all_pages else 1)


# ─── Writes ─────────────────────────────────────────────────────────────────

# name -> (add mutation, add input type)
ADD_MUTATIONS = {
    "threat-actor": ("threatActorGroupAdd", "ThreatActorGroupAddInput"),
    "intrusion-set": ("intrusionSetAdd", "IntrusionSetAddInput"),
    "malware": ("malwareAdd", "MalwareAddInput"),
    "campaign": ("campaignAdd", "CampaignAddInput"),
    "tool": ("toolAdd", "ToolAddInput"),
}

ADD_RESULT_FIELDS = "id standard_id entity_type name created_at"


def add_entity(entity_type: str, name: str, *, description: Optional[str] = None,
               aliases: Optional[list] = None, labels: Optional[list] = None,
               **kw) -> Dict[str, Any]:
    """Create a named threat-intel entity."""
    entity_type = entity_type.lower()
    mutation, input_name = ADD_MUTATIONS[entity_type]
    inp: Dict[str, Any] = {"name": name}
    if description:
        inp["description"] = description
    if aliases:
        inp["aliases"] = [a.strip() for a in aliases if a.strip()]
    if labels:
        inp["objectLabel"] = [l.strip() for l in labels if l.strip()]
    q = f"""
    mutation ($input: {input_name}!) {{
      {mutation}(input: $input) {{ {ADD_RESULT_FIELDS} }}
    }}"""
    result = graphql_request(q, {"input": inp}, **kw)[mutation]
    if not result:
        raise ValueError(f"{entity_type} creation failed for {name!r}")
    return result


def delete_object(object_id: str, **kw) -> Any:
    """Delete any STIX core object by ID (destructive)."""
    q = """
    mutation ($id: ID!) {
      stixCoreObjectEdit(id: $id) { delete }
    }"""
    return graphql_request(q, {"id": object_id}, **kw)["stixCoreObjectEdit"]["delete"]
