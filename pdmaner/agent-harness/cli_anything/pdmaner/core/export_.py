"""Export operations: DDL/SQL generation from entity definitions."""

from .project import _get_default_db


def _get_type_mappings(data):
    """Return all logical-type -> database-type mapping entries."""
    return data.get("dataTypeMapping", {}).get("mappings", [])


def _resolve_db_key(data, db_defkey):
    """Map a database defKey (e.g. ``MYSQL``) to the mapping key.

    Real PDManer files key ``dataTypeMapping.mappings`` entries by the database
    *id* from ``profile.dataTypeSupports``; simplified fixtures may use the
    database name directly. Both forms are supported.
    """
    if not db_defkey:
        db_defkey = _get_default_db(data)

    supports = data.get("profile", {}).get("dataTypeSupports", [])
    for s in supports:
        if s.get("id") == db_defkey:
            return db_defkey
        if s.get("defKey", "").lower() == (db_defkey or "").lower():
            return s.get("id") or db_defkey
    return db_defkey


def _find_domain(field, domains):
    """Find the domain referenced by a field (by id or defKey)."""
    domain_key = field.get("domain", "")
    if not domain_key:
        return None
    for d in domains:
        if d.get("id") == domain_key or d.get("defKey") == domain_key:
            return d
    return None


def _lookup_mapping(mappings, apply_for):
    """Find the mapping entry referenced by a domain's ``applyFor``.

    PDManer stores the mapping entry ``id`` in ``applyFor``; accept a logical
    ``defKey`` too so hand-written project files keep working.
    """
    if not apply_for:
        return None
    for m in mappings:
        if m.get("id") == apply_for or m.get("defKey") == apply_for:
            return m
    return None


def _lookup_db_type(mapping, db_key):
    """Read the column type for a database key, tolerating case differences."""
    for key in (db_key, (db_key or "").upper(), (db_key or "").lower()):
        if key and mapping.get(key):
            return mapping[key]
    return ""


def _resolve_field_type(field, domains, mappings, db_key):
    """Resolve a field's domain/base type to the actual database column type.

    Real PDManer files store ``domain.applyFor`` as the referenced mapping
    entry ``id`` (``baseType`` does the same for fields without a domain), and
    each mapping entry maps database ids to concrete column types.
    """
    field_type = field.get("type", "")

    # If field has a direct type set, use it
    if field_type:
        return field_type

    domain = _find_domain(field, domains)
    if domain:
        mapping = _lookup_mapping(mappings, domain.get("applyFor", ""))
        if mapping:
            resolved = _lookup_db_type(mapping, db_key)
            if resolved:
                return resolved
    else:
        # Fields may reference a base data type directly via baseType
        mapping = _lookup_mapping(mappings, field.get("baseType", ""))
        if mapping:
            resolved = _lookup_db_type(mapping, db_key)
            if resolved:
                return resolved

    # Fall back to the mapping entry named after the field type itself
    return field_type


def _resolve_field_len(field, domains):
    """Field length, falling back to the referenced domain's default."""
    if field.get("len"):
        return field["len"]
    domain = _find_domain(field, domains)
    return domain.get("len", "") if domain else ""


def _resolve_field_scale(field, domains):
    """Field scale, falling back to the referenced domain's default."""
    if field.get("scale"):
        return field["scale"]
    domain = _find_domain(field, domains)
    return domain.get("scale", "") if domain else ""


def generate_ddl(data, db_defkey=None, include_drop=False):
    """Generate CREATE TABLE DDL statements for all entities.

    Returns a list of DDL strings.
    """
    if not db_defkey:
        db_defkey = _get_default_db(data)

    db_key = _resolve_db_key(data, db_defkey)
    mappings = _get_type_mappings(data)
    domains = data.get("domains", [])
    entities = data.get("entities", [])
    statements = []

    for entity in entities:
        table_name = entity.get("defKey", "")
        if not table_name:
            continue

        fields = entity.get("fields", [])
        if not fields:
            continue

        cols = []
        pks = []

        for f in fields:
            fdef = f.get("defKey", "")
            if not fdef:
                continue
            ftype = _resolve_field_type(f, domains, mappings, db_key)
            flen = _resolve_field_len(f, domains)
            fscale = _resolve_field_scale(f, domains)
            fcomment = f.get("comment", "")
            fnotnull = f.get("notNull", False)
            fauto = f.get("autoIncrement", False)
            fdefault = f.get("defaultValue", "")
            fpk = f.get("primaryKey", False)

            type_str = _format_type(ftype, flen, fscale, db_defkey)

            col_parts = [f'  "{fdef}" {type_str}']
            if fnotnull:
                col_parts.append("NOT NULL")
            if fauto:
                if "postgre" in (db_defkey or "").lower():
                    col_parts.append("GENERATED BY DEFAULT AS IDENTITY")
                else:
                    col_parts.append("AUTO_INCREMENT")
            if fdefault:
                col_parts.append(f"DEFAULT {fdefault}")
            if fcomment and db_defkey and "hive" not in db_defkey.lower():
                col_parts.append(f"COMMENT '{fcomment}'")
            cols.append(" ".join(col_parts))

            if fpk:
                pks.append(f'"{fdef}"')

        if pks:
            cols.append(f'  PRIMARY KEY ({", ".join(pks)})')

        comment = entity.get("comment", "")
        table_comment = f" COMMENT = '{comment}'" if comment and "hive" not in (db_defkey or "").lower() else ""

        ddl = ""
        if include_drop:
            ddl += f'DROP TABLE IF EXISTS "{table_name}";\n'
        ddl += f'CREATE TABLE "{table_name}" (\n' + ",\n".join(cols) + f'\n){table_comment};'

        statements.append(ddl)

    return statements


def generate_ddl_for_entity(data, entity_id, db_defkey=None, include_drop=False):
    """Generate DDL for a single entity."""
    from .entity import get_entity
    entity = get_entity(data, entity_id)
    if not entity:
        raise ValueError(f"Entity not found: {entity_id}")
    # Temporarily replace entities list with just this one
    saved = data.get("entities", [])
    data["entities"] = [entity]
    result = generate_ddl(data, db_defkey, include_drop)
    data["entities"] = saved
    return result


def _format_type(ftype, flen, fscale, db_defkey):
    """Format a type with length/scale for the target database."""
    db_lower = (db_defkey or "").lower()
    ftype_upper = (ftype or "").upper()

    if not ftype:
        return "TEXT"

    if ftype_upper in ("VARCHAR", "CHAR", "NVARCHAR", "NCHAR"):
        if flen:
            return f"{ftype_upper}({flen})"
        return f"{ftype_upper}(255)"

    if ftype_upper in ("DECIMAL", "NUMERIC"):
        if flen and fscale:
            return f"{ftype_upper}({flen},{fscale})"
        if flen:
            return f"{ftype_upper}({flen})"
        return f"{ftype_upper}(10,0)"

    if ftype_upper in ("INT", "INTEGER", "BIGINT", "SMALLINT", "TINYINT",
                       "FLOAT", "DOUBLE", "REAL", "BOOLEAN"):
        return ftype_upper

    return ftype_upper


def export_sql(data, output_path, db_defkey=None, include_drop=False):
    """Export all DDL to a SQL file."""
    statements = generate_ddl(data, db_defkey, include_drop)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(statements))
        f.write("\n")
    return output_path
