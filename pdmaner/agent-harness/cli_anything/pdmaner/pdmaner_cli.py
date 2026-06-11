#!/usr/bin/env python3
"""PDManer CLI — Command-line interface for PDManer database modeling tool.

Usage:
    cli-anything-pdmaner [OPTIONS] COMMAND [ARGS]...
    cli-anything-pdmaner  (enters REPL mode)
"""

import json
import os
import sys

import click

from cli_anything.pdmaner.core import project, entity, view, diagram, dict_, domain_, export_, session


@click.group(invoke_without_command=True)
@click.option("--json", "-j", "json_mode", is_flag=True, help="Output in JSON format")
@click.option("--project", "-p", "project_path", help="Path to project file (.chnr.json)")
@click.pass_context
def cli(ctx, json_mode, project_path):
    """PDManer CLI — command-line database modeling tool.

    Manipulate PDManer project files (.chnr.json) for entity,
    view, diagram, dictionary, and domain management.
    """
    ctx.ensure_object(dict)
    ctx.obj["json_mode"] = json_mode
    ctx.obj["project_path"] = None
    ctx.obj["session"] = session.get_session()

    if project_path:
        ctx.obj["session"].load(project_path)
        ctx.obj["project_path"] = project_path

    if ctx.invoked_subcommand is None:
        ctx.invoke(repl)


@cli.result_callback()
def _auto_save(result, **kwargs):
    """Auto-save project after one-shot mutations when --project is used."""
    ctx = click.get_current_context()
    proj_path = ctx.obj.get("project_path")
    sess = ctx.obj.get("session")
    if proj_path and sess and sess.data is not None:
        sess.save(proj_path)


def _j(ctx, data):
    """Output as JSON if json_mode, else return string."""
    if ctx.obj.get("json_mode"):
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
        return None
    return data


def _p(data):
    """Print dict/object as formatted output."""
    if isinstance(data, list):
        for item in data:
            _print_item(item)
    elif isinstance(data, dict):
        _print_item(data)
    else:
        click.echo(data)


def _print_item(d):
    """Print a single item as key: value lines."""
    if isinstance(d, dict):
        for k, v in d.items():
            if v is not None and v != "" and v != []:
                click.echo(f"  {k}: {v}")
    click.echo()


def _get_data(ctx):
    """Get the current session data."""
    sess = ctx.obj.get("session")
    if not sess or sess.data is None:
        raise click.UsageError("No project open. Use --project or 'project open' first.")
    return sess.data


def _mark(ctx):
    """Mark session data as changed for undo tracking."""
    sess = ctx.obj.get("session")
    if sess:
        sess.mark_changed()


# ═══════════════════════════════════════════════════════════════════════
# REPL
# ═══════════════════════════════════════════════════════════════════════

@cli.command("repl")
@click.argument("project_path", required=False)
@click.pass_context
def repl(ctx, project_path):
    """Enter interactive REPL mode."""
    from cli_anything.pdmaner.utils.repl_skin import ReplSkin
    skin = ReplSkin("pdmaner", version="0.1.0")

    skin.print_banner()

    sess = ctx.obj.get("session")

    if project_path:
        sess.load(project_path)
        skin.success(f"Opened: {project_path}")
    elif sess.data is None:
        skin.hint("No project open. Use 'project new' or 'project open' to start.")

    pt_session = skin.create_prompt_session()

    commands = {
        "project new": "Create a new project",
        "project open <path>": "Open a project file",
        "project save": "Save current project",
        "project info": "Show project info",
        "entity list": "List entities",
        "entity add": "Add a new entity",
        "entity get <id>": "Get entity details",
        "entity delete <id>": "Delete an entity",
        "entity add-field": "Add a field to an entity",
        "view list": "List views",
        "view add": "Add a view",
        "diagram list": "List diagrams",
        "diagram add": "Add a diagram",
        "dict list": "List dictionaries",
        "dict add": "Add a dictionary",
        "dict add-item": "Add dictionary item",
        "domain list": "List domains",
        "domain add": "Add a domain",
        "export ddl": "Generate DDL statements",
        "export sql": "Export DDL to SQL file",
        "undo": "Undo last change",
        "redo": "Redo last undone change",
        "status": "Show session status",
        "help": "Show this help",
        "quit": "Exit REPL",
    }

    while True:
        try:
            prompt_name = sess.data.get("name", "") if sess.data else ""
            line = skin.get_input(pt_session, project_name=prompt_name, modified=False)
        except (EOFError, KeyboardInterrupt):
            skin.print_goodbye()
            break

        if not line:
            continue

        if line == "quit" or line == "exit":
            skin.print_goodbye()
            break
        elif line == "help":
            skin.help(commands)
        elif line.startswith("project new"):
            parts = line.split(maxsplit=2)
            name = parts[2] if len(parts) > 2 else "untitled"
            sess.create(name, describe=name)
            skin.success(f"Created project: {name}")
        elif line.startswith("project open"):
            path = line.split(maxsplit=2)[2] if len(line.split(maxsplit=2)) > 2 else ""
            if path:
                try:
                    sess.load(path)
                    skin.success(f"Opened: {path}")
                except Exception as e:
                    skin.error(str(e))
        elif line == "project save":
            try:
                path = sess.save()
                skin.success(f"Saved: {path}")
            except Exception as e:
                skin.error(str(e))
        elif line == "project info":
            info = project.get_project_info(sess.data, as_dict=True)
            if ctx.obj.get("json_mode"):
                click.echo(json.dumps(info, ensure_ascii=False, indent=2))
            else:
                skin.status_block(info, title="Project Info")
        elif line == "entity list":
            ents = entity.get_entities(sess.data)
            if ctx.obj.get("json_mode"):
                click.echo(json.dumps(ents, ensure_ascii=False, indent=2))
            else:
                rows = [[e["defKey"], e.get("defName", ""), str(len(e.get("fields", []))), e.get("comment", "")]
                        for e in ents]
                skin.table(["defKey", "defName", "Fields", "Comment"], rows)
        elif line == "undo":
            if sess.undo():
                skin.success("Undo")
            else:
                skin.warning("Nothing to undo")
        elif line == "redo":
            if sess.redo():
                skin.success("Redo")
            else:
                skin.warning("Nothing to redo")
        elif line == "status":
            status = sess.status()
            if ctx.obj.get("json_mode"):
                click.echo(json.dumps(status, ensure_ascii=False, indent=2))
            else:
                skin.status_block(status, title="Session Status")
        elif line.startswith("export ddl"):
            try:
                ddls = export_.generate_ddl(sess.data)
                if ctx.obj.get("json_mode"):
                    click.echo(json.dumps(ddls, ensure_ascii=False, indent=2))
                else:
                    for ddl in ddls:
                        click.echo(ddl)
                        click.echo()
            except Exception as e:
                skin.error(str(e))
        elif line.startswith("entity add"):
            # Quick add: entity add <defKey> <defName>
            parts = line.split(maxsplit=3)
            if len(parts) >= 3:
                ek = parts[2]
                en = parts[3] if len(parts) > 3 else ek
                e = entity.add_entity(sess.data, ek, en)
                _mark(ctx)
                skin.success(f"Added entity: {ek} ({en})")
            else:
                skin.error("Usage: entity add <defKey> <defName>")
        elif line.startswith("domain add"):
            parts = line.split(maxsplit=4)
            if len(parts) >= 3:
                dk = parts[2]
                dn = parts[3] if len(parts) > 3 else dk
                af = parts[4] if len(parts) > 4 else ""
                d = domain_.add_domain(sess.data, dk, dn, af)
                _mark(ctx)
                skin.success(f"Added domain: {dk}")
        else:
            skin.error(f"Unknown command: {line} (type 'help')")


# ═══════════════════════════════════════════════════════════════════════
# Project Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("project")
def project_group():
    """Project management: new, open, save, info."""
    pass


@project_group.command("new")
@click.option("--name", "-n", required=True, help="Project name")
@click.option("--describe", "-d", default="", help="Project description")
@click.option("--output", "-o", default=None, help="Output file path")
@click.pass_context
def project_new(ctx, name, describe, output):
    """Create a new PDManer project."""
    sess = ctx.obj.get("session")
    sess.create(name, describe, path=output)
    result = {
        "status": "created",
        "name": name,
        "path": output or "(in memory)",
    }
    data = _j(ctx, result)
    if data:
        click.echo(f"Created project: {name}")


@project_group.command("open")
@click.argument("path")
@click.pass_context
def project_open(ctx, path):
    """Open an existing .chnr.json project file."""
    sess = ctx.obj.get("session")
    sess.load(path)
    info = project.get_project_info(sess.data, as_dict=True)
    data = _j(ctx, info)
    if data:
        click.echo(f"Opened: {path}")
        click.echo(f"  Entities: {info['entityCount']}, Views: {info['viewCount']}, Dicts: {info['dictCount']}")


@project_group.command("save")
@click.option("--output", "-o", default=None, help="Output file path (save as)")
@click.pass_context
def project_save(ctx, output):
    """Save the current project."""
    data = _get_data(ctx)
    path = project.save_project(data, output)
    result = {"status": "saved", "path": path}
    out = _j(ctx, result)
    if out:
        click.echo(f"Saved: {path}")


@project_group.command("info")
@click.pass_context
def project_info(ctx):
    """Show project information."""
    data = _get_data(ctx)
    info = project.get_project_info(data, as_dict=True)
    out = _j(ctx, info)
    if out:
        _p(out)


# ═══════════════════════════════════════════════════════════════════════
# Entity Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("entity")
def entity_group():
    """Entity (data table) management."""
    pass


@entity_group.command("list")
@click.pass_context
def entity_list(ctx):
    """List all entities."""
    data = _get_data(ctx)
    entities = entity.get_entities(data)
    result = [{"id": e["id"], "defKey": e["defKey"], "defName": e.get("defName", ""),
               "comment": e.get("comment", ""), "fieldCount": len(e.get("fields", []))}
              for e in entities]
    out = _j(ctx, result)
    if out:
        for e in result:
            click.echo(f"  {e['defKey']:30s} {e['defName']:20s} fields={e['fieldCount']}  {e['comment']}")


@entity_group.command("get")
@click.argument("id")
@click.pass_context
def entity_get(ctx, id):
    """Get entity details by id or defKey."""
    data = _get_data(ctx)
    e = entity.get_entity(data, id)
    if not e:
        click.echo(f"Entity not found: {id}", err=True)
        sys.exit(1)
    result = {
        "id": e["id"], "defKey": e["defKey"], "defName": e.get("defName", ""),
        "comment": e.get("comment", ""), "type": e.get("type", "P"),
        "fields": [{"defKey": f["defKey"], "defName": f.get("defName", ""),
                    "type": f.get("type", ""), "primaryKey": f.get("primaryKey", False)}
                   for f in e.get("fields", [])],
        "indexes": [{"defKey": i["defKey"], "unique": i.get("unique", False)}
                    for i in e.get("indexes", [])],
    }
    out = _j(ctx, result)
    if out:
        click.echo(f"Entity: {e['defKey']} ({e.get('defName', '')})")
        click.echo(f"  Type: {e.get('type', 'P')}, Comment: {e.get('comment', '')}")
        click.echo(f"  Fields ({len(result['fields'])}):")
        for f in result["fields"]:
            pk = " [PK]" if f["primaryKey"] else ""
            click.echo(f"    {f['defKey']:25s} {f['type']:15s} {f['defName']}{pk}")
        click.echo(f"  Indexes ({len(result['indexes'])}):")
        for i in result["indexes"]:
            u = " (unique)" if i["unique"] else ""
            click.echo(f"    {i['defKey']}{u}")


@entity_group.command("add")
@click.option("--defkey", "-k", required=True, help="Entity code (defKey)")
@click.option("--defname", "-n", default="", help="Entity display name (defName)")
@click.option("--comment", "-c", default="", help="Comment")
@click.option("--type", "-t", "entity_type", default="P", help="Entity type: P=physical, L=logical")
@click.pass_context
def entity_add(ctx, defkey, defname, comment, entity_type):
    """Add a new entity (data table)."""
    data = _get_data(ctx)
    e = entity.add_entity(data, defkey, defname or defkey, comment, entity_type)
    _mark(ctx)
    result = {"status": "added", "id": e["id"], "defKey": e["defKey"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added entity: {defkey} ({e['id']})")


@entity_group.command("update")
@click.argument("id")
@click.option("--defkey", "-k", default=None, help="New entity code")
@click.option("--defname", "-n", default=None, help="New display name")
@click.option("--comment", "-c", default=None, help="New comment")
@click.pass_context
def entity_update(ctx, id, defkey, defname, comment):
    """Update entity metadata."""
    data = _get_data(ctx)
    kwargs = {k: v for k, v in [("defKey", defkey), ("defName", defname), ("comment", comment)] if v is not None}
    e = entity.update_entity(data, id, **kwargs)
    _mark(ctx)
    result = {"status": "updated", "id": e["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Updated entity: {id}")


@entity_group.command("delete")
@click.argument("id")
@click.option("--yes", is_flag=True, help="Skip confirmation")
@click.pass_context
def entity_delete(ctx, id, yes):
    """Delete an entity."""
    if not yes:
        click.confirm(f"Delete entity '{id}' and remove from all diagrams?", abort=True)
    data = _get_data(ctx)
    entity.delete_entity(data, id)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted entity: {id}")


@entity_group.command("add-field")
@click.argument("entity_id")
@click.option("--defkey", "-k", required=True, help="Field code (defKey)")
@click.option("--defname", "-n", default="", help="Field name")
@click.option("--type", "-t", "field_type", default="", help="Database type")
@click.option("--domain", "-d", default="", help="Domain reference")
@click.option("--len", "-l", "len_", default="", help="Length")
@click.option("--scale", "-s", default="", help="Scale")
@click.option("--pk/--no-pk", default=False, help="Primary key")
@click.option("--notnull/--null", default=False, help="Not null")
@click.option("--autoinc/--no-autoinc", default=False, help="Auto increment")
@click.option("--comment", "-c", default="", help="Comment")
@click.option("--default", "default_", default="", help="Default value")
@click.pass_context
def entity_add_field(ctx, entity_id, defkey, defname, field_type, domain, len_, scale, pk, notnull, autoinc, comment, default_):
    """Add a field to an entity."""
    data = _get_data(ctx)
    f = entity.add_field(data, entity_id, defkey, defname or defkey, field_type, domain,
                         len_, scale, pk, notnull, autoinc, comment, default_)
    _mark(ctx)
    result = {"status": "added", "id": f["id"], "defKey": f["defKey"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added field '{defkey}' to entity")


@entity_group.command("update-field")
@click.argument("entity_id")
@click.argument("field")
@click.option("--defkey", "-k", default=None, help="New field code")
@click.option("--defname", "-n", default=None, help="New field name")
@click.option("--type", "-t", "field_type", default=None, help="New database type")
@click.option("--domain", "-d", default=None, help="New domain reference")
@click.option("--len", "-l", "len_", default=None, help="New length")
@click.option("--scale", "-s", default=None, help="New scale")
@click.option("--pk/--no-pk", default=None, help="Primary key")
@click.option("--notnull/--null", default=None, help="Not null")
@click.option("--comment", "-c", default=None, help="New comment")
@click.pass_context
def entity_update_field(ctx, entity_id, field, defkey, defname, field_type, domain, len_, scale, pk, notnull, comment):
    """Update a field in an entity."""
    data = _get_data(ctx)
    args = {}
    if defkey is not None: args["defKey"] = defkey
    if defname is not None: args["defName"] = defname
    if field_type is not None: args["field_type"] = field_type
    if domain is not None: args["domain"] = domain
    if len_ is not None: args["len_"] = len_
    if scale is not None: args["scale"] = scale
    if pk is not None: args["primaryKey"] = pk
    if notnull is not None: args["notNull"] = notnull
    if comment is not None: args["comment"] = comment
    f = entity.update_field(data, entity_id, field, **args)
    _mark(ctx)
    result = {"status": "updated"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Updated field in entity")


@entity_group.command("delete-field")
@click.argument("entity_id")
@click.argument("field")
@click.pass_context
def entity_delete_field(ctx, entity_id, field):
    """Delete a field from an entity."""
    data = _get_data(ctx)
    entity.delete_field(data, entity_id, field)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted field from entity")


@entity_group.command("add-index")
@click.argument("entity_id")
@click.option("--defkey", "-k", required=True, help="Index name/code")
@click.option("--fields", "-f", multiple=True, help="Fields in index (repeatable)")
@click.option("--unique/--no-unique", default=False, help="Unique constraint")
@click.option("--comment", "-c", default="", help="Comment")
@click.pass_context
def entity_add_index(ctx, entity_id, defkey, fields, unique, comment):
    """Add an index to an entity."""
    data = _get_data(ctx)
    idx = entity.add_index(data, entity_id, defkey, list(fields), unique, comment)
    _mark(ctx)
    result = {"status": "added", "defKey": idx["defKey"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added index '{defkey}' to entity")


@entity_group.command("delete-index")
@click.argument("entity_id")
@click.argument("index")
@click.pass_context
def entity_delete_index(ctx, entity_id, index):
    """Delete an index from an entity."""
    data = _get_data(ctx)
    entity.delete_index(data, entity_id, index)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted index from entity")


# ═══════════════════════════════════════════════════════════════════════
# View Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("view")
def view_group():
    """View management."""
    pass


@view_group.command("list")
@click.pass_context
def view_list(ctx):
    """List all views."""
    data = _get_data(ctx)
    views = view.get_views(data)
    result = [{"id": v["id"], "defKey": v["defKey"], "defName": v.get("defName", ""),
               "comment": v.get("comment", "")} for v in views]
    out = _j(ctx, result)
    if out:
        for v in result:
            click.echo(f"  {v['defKey']:30s} {v['defName']}")


@view_group.command("add")
@click.option("--defkey", "-k", required=True, help="View code")
@click.option("--defname", "-n", default="", help="View name")
@click.option("--comment", "-c", default="", help="Comment")
@click.pass_context
def view_add(ctx, defkey, defname, comment):
    """Add a new view."""
    data = _get_data(ctx)
    v = view.add_view(data, defkey, defname or defkey, comment)
    _mark(ctx)
    result = {"status": "added", "id": v["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added view: {defkey}")


@view_group.command("delete")
@click.argument("id")
@click.pass_context
def view_delete(ctx, id):
    """Delete a view."""
    data = _get_data(ctx)
    view.delete_view(data, id)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted view: {id}")


# ═══════════════════════════════════════════════════════════════════════
# Diagram Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("diagram")
def diagram_group():
    """ER Diagram management."""
    pass


@diagram_group.command("list")
@click.pass_context
def diagram_list(ctx):
    """List all ER diagrams."""
    data = _get_data(ctx)
    diagrams = diagram.get_diagrams(data)
    result = [{"id": d["id"], "defKey": d["defKey"], "defName": d.get("defName", ""),
               "relationType": d.get("relationType", ""),
               "cellCount": len(d.get("canvasData", {}).get("cells", []))}
              for d in diagrams]
    out = _j(ctx, result)
    if out:
        for d in result:
            click.echo(f"  {d['defKey']:30s} {d['defName']} cells={d['cellCount']}")


@diagram_group.command("add")
@click.option("--defkey", "-k", required=True, help="Diagram code")
@click.option("--defname", "-n", default="", help="Diagram name")
@click.option("--type", "-t", "relation_type", default="entity", help="Relation type: entity, field, logic")
@click.option("--comment", "-c", default="", help="Comment")
@click.pass_context
def diagram_add(ctx, defkey, defname, relation_type, comment):
    """Add a new ER diagram."""
    data = _get_data(ctx)
    d = diagram.add_diagram(data, defkey, defname or defkey, relation_type, comment)
    _mark(ctx)
    result = {"status": "added", "id": d["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added diagram: {defkey}")


@diagram_group.command("delete")
@click.argument("id")
@click.pass_context
def diagram_delete(ctx, id):
    """Delete an ER diagram."""
    data = _get_data(ctx)
    diagram.delete_diagram(data, id)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted diagram: {id}")


@diagram_group.command("add-table")
@click.argument("diagram")
@click.argument("entity")
@click.option("--x", type=int, default=100, help="X position")
@click.option("--y", type=int, default=100, help="Y position")
@click.pass_context
def diagram_add_table(ctx, diagram, entity, x, y):
    """Add an entity table to a diagram."""
    data = _get_data(ctx)
    node = diagram.add_table_to_diagram(data, diagram, entity, x, y)
    _mark(ctx)
    result = {"status": "added", "nodeId": node["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added table to diagram: {node['id']}")


@diagram_group.command("add-relation")
@click.argument("diagram")
@click.option("--source", "-s", required=True, help="Source entity id")
@click.option("--target", "-t", required=True, help="Target entity id")
@click.option("--source-field", required=True, help="Source field defKey")
@click.option("--target-field", required=True, help="Target field defKey")
@click.option("--relation", "-r", default="1:n", help="Relation type: 1:n, 1:1, n:m")
@click.pass_context
def diagram_add_relation(ctx, diagram, source, target, source_field, target_field, relation):
    """Add an ER relation between two tables on a diagram."""
    data = _get_data(ctx)
    edge = diagram.add_relation_to_diagram(
        data, diagram, source, target, source_field, target_field, relation
    )
    _mark(ctx)
    result = {"status": "added", "edgeId": edge["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added relation: {source_field} -> {target_field} ({relation})")


# ═══════════════════════════════════════════════════════════════════════
# Dictionary Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("dict")
def dict_group():
    """Data dictionary management."""
    pass


@dict_group.command("list")
@click.pass_context
def dict_list(ctx):
    """List all dictionaries."""
    data = _get_data(ctx)
    dicts = dict_.get_dicts(data)
    result = [{"id": d["id"], "defKey": d["defKey"], "defName": d.get("defName", ""),
               "itemCount": len(d.get("items", []))} for d in dicts]
    out = _j(ctx, result)
    if out:
        for d in result:
            click.echo(f"  {d['defKey']:30s} {d['defName']} items={d['itemCount']}")


@dict_group.command("add")
@click.option("--defkey", "-k", required=True, help="Dictionary code")
@click.option("--defname", "-n", default="", help="Dictionary name")
@click.option("--sort", default="", help="Sort field")
@click.option("--intro", default="", help="Intro/description")
@click.pass_context
def dict_add(ctx, defkey, defname, sort, intro):
    """Add a new data dictionary."""
    data = _get_data(ctx)
    d = dict_.add_dict(data, defkey, defname or defkey, sort, intro)
    _mark(ctx)
    result = {"status": "added", "id": d["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added dictionary: {defkey}")


@dict_group.command("delete")
@click.argument("id")
@click.pass_context
def dict_delete(ctx, id):
    """Delete a dictionary."""
    data = _get_data(ctx)
    dict_.delete_dict(data, id)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted dictionary: {id}")


@dict_group.command("add-item")
@click.argument("dict")
@click.option("--defkey", "-k", required=True, help="Item code")
@click.option("--defname", "-n", default="", help="Item name")
@click.option("--sort", default="", help="Sort value")
@click.option("--intro", default="", help="Item description")
@click.option("--parent", "-p", default="", help="Parent item key")
@click.pass_context
def dict_add_item(ctx, dict, defkey, defname, sort, intro, parent):
    """Add an item to a dictionary."""
    data = _get_data(ctx)
    item = dict_.add_dict_item(data, dict, defkey, defname or defkey, sort, intro, parent)
    _mark(ctx)
    result = {"status": "added", "id": item["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added item '{defkey}' to dictionary")


@dict_group.command("delete-item")
@click.argument("dict")
@click.argument("item")
@click.pass_context
def dict_delete_item(ctx, dict, item):
    """Delete an item from a dictionary."""
    data = _get_data(ctx)
    dict_.delete_dict_item(data, dict, item)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted item from dictionary")


# ═══════════════════════════════════════════════════════════════════════
# Domain Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("domain")
def domain_group():
    """Domain (data type) management."""
    pass


@domain_group.command("list")
@click.pass_context
def domain_list(ctx):
    """List all domains."""
    data = _get_data(ctx)
    domains = domain_.get_domains(data)
    result = [{"id": d["id"], "defKey": d["defKey"], "defName": d.get("defName", ""),
               "applyFor": d.get("applyFor", ""), "len": d.get("len", ""), "scale": d.get("scale", "")}
              for d in domains]
    out = _j(ctx, result)
    if out:
        for d in result:
            click.echo(f"  {d['defKey']:25s} applyFor={d['applyFor']:15s} len={d['len']} scale={d['scale']}  {d['defName']}")


@domain_group.command("add")
@click.option("--defkey", "-k", required=True, help="Domain code")
@click.option("--defname", "-n", default="", help="Domain name")
@click.option("--applyfor", "-a", default="", help="Apply for (mapping defKey)")
@click.option("--len", "-l", "len_", default="", help="Default length")
@click.option("--scale", "-s", default="", help="Default scale")
@click.option("--uihint", default="", help="UI hint")
@click.pass_context
def domain_add(ctx, defkey, defname, applyfor, len_, scale, uihint):
    """Add a new domain."""
    data = _get_data(ctx)
    d = domain_.add_domain(data, defkey, defname or defkey, applyfor, len_, scale, uihint)
    _mark(ctx)
    result = {"status": "added", "id": d["id"]}
    out = _j(ctx, result)
    if out:
        click.echo(f"Added domain: {defkey}")


@domain_group.command("delete")
@click.argument("id")
@click.pass_context
def domain_delete(ctx, id):
    """Delete a domain."""
    data = _get_data(ctx)
    domain_.delete_domain(data, id)
    _mark(ctx)
    result = {"status": "deleted"}
    out = _j(ctx, result)
    if out:
        click.echo(f"Deleted domain: {id}")


@domain_group.command("mappings")
@click.pass_context
def domain_mappings(ctx):
    """List data type mappings."""
    data = _get_data(ctx)
    mappings = domain_.get_mappings(data)
    out = _j(ctx, mappings)
    if out:
        for m in mappings:
            click.echo(f"  {m.get('defKey', ''):20s} {m.get('defName', '')}")


@domain_group.command("supports")
@click.pass_context
def domain_supports(ctx):
    """List supported database types."""
    data = _get_data(ctx)
    supports = domain_.get_data_type_supports(data)
    out = _j(ctx, supports)
    if out:
        for s in supports:
            click.echo(f"  {s.get('defKey', '')}")


# ═══════════════════════════════════════════════════════════════════════
# Export Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("export")
def export_group():
    """Export DDL, SQL, and other formats."""
    pass


@export_group.command("ddl")
@click.option("--db", "-d", default=None, help="Target database type (e.g., MySQL, PostgreSQL)")
@click.option("--entity", "-e", default=None, help="Entity id (omit for all)")
@click.option("--drop/--no-drop", default=False, help="Include DROP statements")
@click.pass_context
def export_ddl(ctx, db, entity, drop):
    """Generate CREATE TABLE DDL statements."""
    data = _get_data(ctx)
    if entity:
        ddls = export_.generate_ddl_for_entity(data, entity, db, drop)
    else:
        ddls = export_.generate_ddl(data, db, drop)
    result = {"ddl": [ddls] if isinstance(ddls, str) else ddls}
    out = _j(ctx, result)
    if out:
        for ddl in (ddls if isinstance(ddls, list) else [ddls]):
            click.echo(ddl)
            click.echo()


@export_group.command("sql")
@click.option("--output", "-o", required=True, help="Output SQL file path")
@click.option("--db", "-d", default=None, help="Target database type")
@click.option("--drop/--no-drop", default=False, help="Include DROP statements")
@click.pass_context
def export_sql(ctx, output, db, drop):
    """Export DDL to a SQL file."""
    data = _get_data(ctx)
    path = export_.export_sql(data, output, db, drop)
    result = {"status": "exported", "path": path}
    out = _j(ctx, result)
    if out:
        click.echo(f"Exported SQL to: {path}")


# ═══════════════════════════════════════════════════════════════════════
# Session Commands
# ═══════════════════════════════════════════════════════════════════════

@cli.group("session")
def session_group():
    """Session and history management."""
    pass


@session_group.command("status")
@click.pass_context
def session_status(ctx):
    """Show session status."""
    sess = ctx.obj.get("session")
    status = sess.status()
    out = _j(ctx, status)
    if out:
        for k, v in status.items():
            click.echo(f"  {k}: {v}")


@session_group.command("undo")
@click.pass_context
def session_undo(ctx):
    """Undo last change."""
    sess = ctx.obj.get("session")
    if sess.undo():
        result = {"status": "undone"}
        out = _j(ctx, result)
        if out:
            click.echo("Undo successful")
    else:
        click.echo("Nothing to undo", err=True)


@session_group.command("redo")
@click.pass_context
def session_redo(ctx):
    """Redo last undone change."""
    sess = ctx.obj.get("session")
    if sess.redo():
        result = {"status": "redone"}
        out = _j(ctx, result)
        if out:
            click.echo("Redo successful")
    else:
        click.echo("Nothing to redo", err=True)


@session_group.command("save")
@click.option("--output", "-o", default=None, help="Output file path")
@click.pass_context
def session_save(ctx, output):
    """Save the project."""
    sess = ctx.obj.get("session")
    path = sess.save(output)
    result = {"status": "saved", "path": path}
    out = _j(ctx, result)
    if out:
        click.echo(f"Saved: {path}")


def main():
    """Entry point for console_scripts."""
    cli(obj={})


if __name__ == "__main__":
    main()
