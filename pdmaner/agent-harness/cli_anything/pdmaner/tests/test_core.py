"""Unit tests for cli-anything-pdmaner core modules."""

import os
import json
import tempfile
import pytest

from cli_anything.pdmaner.core.project import (
    create_project, open_project, save_project, get_project_info,
    _get_default_db, EMPTY_PROJECT,
)
from cli_anything.pdmaner.core.entity import (
    get_entities, get_entity, add_entity, update_entity, delete_entity,
    add_field, update_field, delete_field, add_index, delete_index, get_fields,
)
from cli_anything.pdmaner.core.export_ import (
    generate_ddl, generate_ddl_for_entity, export_sql,
    _format_type, _resolve_field_type,
)
from cli_anything.pdmaner.core.dict_ import (
    get_dicts, get_dict, add_dict, delete_dict, add_dict_item, delete_dict_item,
)
from cli_anything.pdmaner.core.domain_ import (
    get_domains, get_domain, add_domain, delete_domain, get_mappings, add_mapping,
)
from cli_anything.pdmaner.core.diagram import (
    get_diagrams, add_diagram, delete_diagram, add_table_to_diagram,
)
from cli_anything.pdmaner.core.view import get_views, add_view, delete_view
from cli_anything.pdmaner.core.session import Session


# ── Project Tests ──────────────────────────────────────────────────────

class TestProject:
    def test_create_project(self):
        p = create_project("testdb", "Test database")
        assert p["name"] == "testdb"
        assert p["describe"] == "Test database"
        assert p["version"] == "4.9.4"
        assert "createdTime" in p
        assert p["entities"] == []
        assert p["views"] == []

    def test_create_project_with_path(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        p = create_project("testdb", path=path)
        assert os.path.exists(path)
        with open(path, "r") as f:
            saved = json.load(f)
        assert saved["name"] == "testdb"

    def test_open_project(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        create_project("testdb", path=path)
        p = open_project(path)
        assert p["name"] == "testdb"
        assert p["_path"] == path
        assert "_modified" in p

    def test_save_project(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        p = create_project("testdb")
        save_project(p, path)
        assert os.path.exists(path)

    def test_save_as(self, tmp_path):
        path1 = str(tmp_path / "test.chnr.json")
        path2 = str(tmp_path / "test2.chnr.json")
        p = create_project("testdb", path=path1)
        save_project(p, path2)
        assert os.path.exists(path2)

    def test_get_project_info(self):
        p = create_project("testdb")
        add_entity(p, "users", "用户表")
        add_entity(p, "orders", "订单表")
        info = get_project_info(p, as_dict=True)
        assert info["name"] == "testdb"
        assert info["entityCount"] == 2
        assert info["viewCount"] == 0

    def test_get_project_info_empty(self):
        p = create_project("empty")
        info = get_project_info(p, as_dict=True)
        assert info["entityCount"] == 0
        assert info["dictCount"] == 0


# ── Entity Tests ───────────────────────────────────────────────────────

class TestEntity:
    def make_project(self):
        return create_project("test")

    def test_add_entity(self):
        p = self.make_project()
        e = add_entity(p, "users", "用户表", "User table")
        assert e["defKey"] == "users"
        assert e["defName"] == "用户表"
        assert e["comment"] == "User table"
        assert e["type"] == "P"
        assert "id" in e
        assert len(p["entities"]) == 1

    def test_get_entity_by_id(self):
        p = self.make_project()
        e = add_entity(p, "users")
        found = get_entity(p, e["id"])
        assert found is not None

    def test_get_entity_by_defkey(self):
        p = self.make_project()
        add_entity(p, "users")
        found = get_entity(p, "users")
        assert found is not None

    def test_get_entity_not_found(self):
        p = self.make_project()
        assert get_entity(p, "NONEXISTENT") is None

    def test_delete_entity(self):
        p = self.make_project()
        e = add_entity(p, "users")
        assert len(p["entities"]) == 1
        delete_entity(p, e["id"])
        assert len(p["entities"]) == 0

    def test_delete_entity_cleans_diagram(self):
        p = self.make_project()
        e = add_entity(p, "users")
        dia = add_diagram(p, "main")
        add_table_to_diagram(p, dia["id"], e["id"])
        assert len(dia["canvasData"]["cells"]) == 1
        delete_entity(p, e["id"])
        assert len(dia["canvasData"]["cells"]) == 0

    def test_add_field(self):
        p = self.make_project()
        e = add_entity(p, "users")
        f = add_field(p, e["id"], "name", "姓名", "VARCHAR", len_="64", notNull=True, comment="名称")
        assert f["defKey"] == "name"
        assert f["defName"] == "姓名"
        assert f["type"] == "VARCHAR"
        assert f["len"] == "64"
        assert f["notNull"] is True
        assert f["comment"] == "名称"

    def test_add_field_with_pk(self):
        p = self.make_project()
        e = add_entity(p, "users")
        f = add_field(p, e["id"], "user_id", primaryKey=True, autoIncrement=True)
        assert f["primaryKey"] is True
        assert f["autoIncrement"] is True

    def test_update_field(self):
        p = self.make_project()
        e = add_entity(p, "users")
        f = add_field(p, e["id"], "name")
        updated = update_field(p, e["id"], f["id"], defKey="full_name", comment="Full name")
        assert updated["defKey"] == "full_name"
        assert updated["comment"] == "Full name"

    def test_delete_field(self):
        p = self.make_project()
        e = add_entity(p, "users")
        f = add_field(p, e["id"], "name")
        assert len(e["fields"]) == 1
        delete_field(p, e["id"], f["id"])
        assert len(e["fields"]) == 0

    def test_add_index(self):
        p = self.make_project()
        e = add_entity(p, "users")
        f = add_field(p, e["id"], "email")
        idx = add_index(p, e["id"], "idx_email", fields=["email"], unique=True)
        assert idx["defKey"] == "idx_email"
        assert idx["unique"] is True

    def test_delete_index(self):
        p = self.make_project()
        e = add_entity(p, "users")
        add_field(p, e["id"], "email")
        add_index(p, e["id"], "idx_email", fields=["email"])
        assert len(e["indexes"]) == 1
        delete_index(p, e["id"], "idx_email")
        assert len(e["indexes"]) == 0

    def test_update_entity_metadata(self):
        p = self.make_project()
        e = add_entity(p, "users", "用户")
        updated = update_entity(p, e["id"], defKey="accounts", defName="账号表")
        assert updated["defKey"] == "accounts"
        assert updated["defName"] == "账号表"

    def test_get_fields(self):
        p = self.make_project()
        e = add_entity(p, "users")
        add_field(p, e["id"], "id", field_type="BIGINT")
        add_field(p, e["id"], "name", field_type="VARCHAR")
        fields = get_fields(p, e["id"])
        assert len(fields) == 2


# ── Export Tests ───────────────────────────────────────────────────────

class TestExport:
    def make_project_with_entity(self):
        p = create_project("testdb")
        e = add_entity(p, "users", "用户表", "User table")
        add_field(p, e["id"], "id", "ID", "BIGINT", primaryKey=True, notNull=True, autoIncrement=True)
        add_field(p, e["id"], "name", "名称", "VARCHAR", len_="64", notNull=True)
        add_field(p, e["id"], "email", "邮箱", "VARCHAR", len_="128")
        add_field(p, e["id"], "age", "年龄", "INT")
        return p

    def test_format_type_varchar(self):
        assert _format_type("VARCHAR", "64", "", "MySQL") == "VARCHAR(64)"

    def test_format_type_varchar_no_len(self):
        assert _format_type("VARCHAR", "", "", "MySQL") == "VARCHAR(255)"

    def test_format_type_decimal(self):
        assert _format_type("DECIMAL", "10", "2", "MySQL") == "DECIMAL(10,2)"

    def test_format_type_int(self):
        assert _format_type("INT", "", "", "MySQL") == "INT"

    def test_generate_ddl(self):
        p = self.make_project_with_entity()
        ddls = generate_ddl(p, "MySQL")
        assert len(ddls) == 1
        ddl = ddls[0]
        assert 'CREATE TABLE "users"' in ddl
        assert '"id"' in ddl
        assert '"name"' in ddl
        assert "NOT NULL" in ddl
        assert "AUTO_INCREMENT" in ddl

    def test_generate_ddl_multiple_entities(self):
        p = self.make_project_with_entity()
        e2 = add_entity(p, "orders", "订单表")
        add_field(p, e2["id"], "order_id", "订单ID", "BIGINT", primaryKey=True)
        ddls = generate_ddl(p, "MySQL")
        assert len(ddls) == 2

    def test_generate_ddl_empty_entity(self):
        p = create_project("testdb")
        add_entity(p, "empty_table")
        ddls = generate_ddl(p, "MySQL")
        assert len(ddls) == 0

    def test_generate_ddl_for_entity(self):
        p = self.make_project_with_entity()
        e2 = add_entity(p, "orders")
        add_field(p, e2["id"], "order_id", "订单ID", "BIGINT", primaryKey=True)
        ddls = generate_ddl_for_entity(p, e2["id"], "MySQL")
        assert len(ddls) == 1
        assert "orders" in ddls[0]

    def test_export_sql(self, tmp_path):
        p = self.make_project_with_entity()
        path = str(tmp_path / "output.sql")
        result = export_sql(p, path, "MySQL")
        assert result == path
        with open(path) as f:
            content = f.read()
        assert "users" in content


# ── Dict Tests ─────────────────────────────────────────────────────────

class TestDict:
    def test_add_dict(self):
        p = create_project("test")
        d = add_dict(p, "gender", "性别")
        assert d["defKey"] == "gender"
        assert d["defName"] == "性别"
        assert len(p["dicts"]) == 1

    def test_get_dict(self):
        p = create_project("test")
        d = add_dict(p, "gender")
        assert get_dict(p, d["id"]) is not None
        assert get_dict(p, "gender") is not None

    def test_delete_dict(self):
        p = create_project("test")
        d = add_dict(p, "gender")
        assert len(p["dicts"]) == 1
        delete_dict(p, d["id"])
        assert len(p["dicts"]) == 0

    def test_add_dict_item(self):
        p = create_project("test")
        d = add_dict(p, "gender")
        item = add_dict_item(p, d["id"], "male", "男", sort="1")
        assert item["defKey"] == "male"
        assert item["defName"] == "男"
        assert len(d["items"]) == 1

    def test_delete_dict_item(self):
        p = create_project("test")
        d = add_dict(p, "gender")
        add_dict_item(p, d["id"], "male", "男")
        assert len(d["items"]) == 1
        delete_dict_item(p, d["id"], "male")
        assert len(d["items"]) == 0


# ── Domain Tests ───────────────────────────────────────────────────────

class TestDomain:
    def test_add_domain(self):
        p = create_project("test")
        d = add_domain(p, "text32", "Text32", "VARCHAR", len_="32")
        assert d["defKey"] == "text32"
        assert d["applyFor"] == "VARCHAR"
        assert d["len"] == "32"
        assert len(p["domains"]) == 1

    def test_delete_domain(self):
        p = create_project("test")
        d = add_domain(p, "text32")
        assert len(p["domains"]) == 1
        delete_domain(p, d["id"])
        assert len(p["domains"]) == 0

    def test_get_domains(self):
        p = create_project("test")
        add_domain(p, "text32")
        add_domain(p, "int10")
        assert len(get_domains(p)) == 2

    def test_add_mapping(self):
        p = create_project("test")
        m = add_mapping(p, "VARCHAR", "Variable String", MySQL="VARCHAR", PostgreSQL="VARCHAR")
        assert m["defKey"] == "VARCHAR"
        assert m["MySQL"] == "VARCHAR"
        mappings = get_mappings(p)
        assert len(mappings) == 1


# ── Diagram Tests ──────────────────────────────────────────────────────

class TestDiagram:
    def test_add_diagram(self):
        p = create_project("test")
        d = add_diagram(p, "main", "Main Diagram")
        assert d["defKey"] == "main"
        assert d["canvasData"]["cells"] == []
        assert len(p["diagrams"]) == 1

    def test_add_table_to_diagram(self):
        p = create_project("test")
        e = add_entity(p, "users")
        d = add_diagram(p, "main")
        node = add_table_to_diagram(p, d["id"], e["id"])
        assert node["shape"] == "table"
        assert node["originKey"] == e["id"]
        assert len(d["canvasData"]["cells"]) == 1

    def test_delete_diagram(self):
        p = create_project("test")
        d = add_diagram(p, "main")
        assert len(p["diagrams"]) == 1
        delete_diagram(p, d["id"])
        assert len(p["diagrams"]) == 0


# ── View Tests ─────────────────────────────────────────────────────────

class TestView:
    def test_add_view(self):
        p = create_project("test")
        v = add_view(p, "user_summary", "用户汇总")
        assert v["defKey"] == "user_summary"
        assert len(p["views"]) == 1

    def test_delete_view(self):
        p = create_project("test")
        v = add_view(p, "user_summary")
        assert len(p["views"]) == 1
        delete_view(p, v["id"])
        assert len(p["views"]) == 0


# ── Session Tests ──────────────────────────────────────────────────────

class TestSession:
    def test_create_session(self):
        s = Session()
        s.create("testdb")
        assert s.data is not None
        assert s.data["name"] == "testdb"

    def test_load_session(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        create_project("testdb", path=path)
        s = Session()
        s.load(path)
        assert s.data["name"] == "testdb"

    def test_undo_redo(self):
        s = Session()
        s.create("testdb")
        add_entity(s.data, "table1")
        s.mark_changed()
        assert len(s.data["entities"]) == 1
        s.undo()
        assert len(s.data["entities"]) == 0
        s.redo()
        assert len(s.data["entities"]) == 1

    def test_undo_at_beginning(self):
        s = Session()
        s.create("testdb")
        assert s.undo() is False

    def test_redo_at_end(self):
        s = Session()
        s.create("testdb")
        assert s.redo() is False

    def test_session_status(self):
        s = Session()
        s.create("testdb", path="/tmp/test.chnr.json")
        status = s.status()
        assert status["name"] == "testdb"
        assert "canUndo" in status
        assert "path" in status

    def test_session_save(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        s = Session()
        s.create("testdb", path=path)
        add_entity(s.data, "users")
        s.mark_changed()
        s.save()
        assert os.path.exists(path)
