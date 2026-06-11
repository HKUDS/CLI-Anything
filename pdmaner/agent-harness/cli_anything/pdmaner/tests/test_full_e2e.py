"""End-to-end tests for cli-anything-pdmaner.

Tests the full pipeline: CLI commands -> JSON project -> DDL export.
"""

import os
import sys
import json
import tempfile
import subprocess
import pytest


def _resolve_cli(name):
    """Resolve installed CLI command; falls back to python -m for dev."""
    import shutil
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = "cli_anything.pdmaner.pdmaner_cli"
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


class TestCLISubprocess:
    CLI_BASE = _resolve_cli("cli-anything-pdmaner")

    def _run(self, args, check=True):
        return subprocess.run(
            self.CLI_BASE + args,
            capture_output=True, text=True,
            check=check,
        )

    def test_help(self):
        result = self._run(["--help"])
        assert result.returncode == 0
        assert "PDManer" in result.stdout

    def test_project_new_json(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        result = self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "created"
        assert data["name"] == "testdb"
        assert os.path.exists(path)

    def test_project_open_and_info(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        result = self._run(["--json", "--project", path, "project", "info"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["name"] == "testdb"

    def test_entity_list_empty(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        result = self._run(["--json", "--project", path, "entity", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data == []

    def test_entity_add(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        result = self._run(["--json", "--project", path, "entity", "add",
                           "--defkey", "users", "--defname", "用户表"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "added"
        assert data["defKey"] == "users"

    def test_entity_get(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        result = self._run(["--json", "--project", path, "entity", "add",
                           "--defkey", "users", "--defname", "用户表"])
        entity_data = json.loads(result.stdout)
        result = self._run(["--json", "--project", path, "entity", "get", "users"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["defKey"] == "users"

    def test_add_field(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        self._run(["--json", "--project", path, "entity", "add", "--defkey", "users"])
        result = self._run(["--json", "--project", path, "entity", "add-field",
                           "users", "--defkey", "name", "--type", "VARCHAR",
                           "--len", "64", "--notnull"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "added"

    def test_export_ddl(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        out_sql = str(tmp_path / "output.sql")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        self._run(["--json", "--project", path, "entity", "add", "--defkey", "users"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "users", "--defkey", "id", "--type", "BIGINT", "--pk", "--notnull", "--autoinc"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "users", "--defkey", "name", "--type", "VARCHAR", "--len", "64", "--notnull"])

        # Export SQL file
        result = self._run(["--json", "--project", path, "export", "sql",
                           "-o", out_sql, "--db", "MySQL"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "exported"
        assert os.path.exists(out_sql)

        with open(out_sql) as f:
            content = f.read()
        assert "CREATE TABLE" in content
        assert "users" in content
        assert "BIGINT" in content

    def test_dict_operations(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])

        # Add dict
        result = self._run(["--json", "--project", path, "dict", "add",
                           "--defkey", "gender", "--defname", "性别"])
        assert result.returncode == 0

        # Add item
        result = self._run(["--json", "--project", path, "dict", "add-item",
                           "gender", "--defkey", "M", "--defname", "男"])
        assert result.returncode == 0

        # List
        result = self._run(["--json", "--project", path, "dict", "list"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert len(data) == 1

    def test_view_operations(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        result = self._run(["--json", "--project", path, "view", "add",
                           "--defkey", "user_view", "--defname", "用户视图"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "added"

    def test_domain_operations(self, tmp_path):
        path = str(tmp_path / "test.chnr.json")
        self._run(["--json", "project", "new", "-n", "testdb", "-o", path])
        result = self._run(["--json", "--project", path, "domain", "add",
                           "--defkey", "text32", "--defname", "Text32",
                           "--applyfor", "VARCHAR", "--len", "32"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == "added"

    def test_full_workflow(self, tmp_path):
        """Full E2E: create project, add entities with fields, export DDL."""
        path = str(tmp_path / "mydb.chnr.json")
        out_sql = str(tmp_path / "mydb.sql")

        # 1. Create project
        r = self._run(["--json", "project", "new", "-n", "myapp", "-d",
                       "My Application Database", "-o", path])
        assert r.returncode == 0

        # 2. Add user entity
        self._run(["--json", "--project", path, "entity", "add",
                  "--defkey", "sys_user", "--defname", "系统用户", "--comment", "System user table"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "sys_user", "--defkey", "id", "--type", "BIGINT",
                  "--pk", "--notnull", "--autoinc", "--comment", "主键ID"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "sys_user", "--defkey", "username", "--type", "VARCHAR",
                  "--len", "64", "--notnull", "--comment", "用户名"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "sys_user", "--defkey", "email", "--type", "VARCHAR",
                  "--len", "128", "--comment", "邮箱"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "sys_user", "--defkey", "created_at", "--type", "DATETIME",
                  "--notnull", "--comment", "创建时间"])

        # 3. Add role entity
        self._run(["--json", "--project", path, "entity", "add",
                  "--defkey", "sys_role", "--defname", "系统角色"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "sys_role", "--defkey", "id", "--type", "BIGINT",
                  "--pk", "--notnull", "--autoinc"])
        self._run(["--json", "--project", path, "entity", "add-field",
                  "sys_role", "--defkey", "role_name", "--type", "VARCHAR",
                  "--len", "32", "--notnull"])

        # 4. Export DDL
        result = self._run(["--json", "--project", path, "export", "ddl", "--db", "MySQL"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        ddls = data["ddl"][0] if isinstance(data["ddl"][0], list) else data["ddl"]
        all_ddl = "\n".join(ddls if isinstance(ddls, list) else [ddls])
        assert "sys_user" in all_ddl
        assert "sys_role" in all_ddl
        assert "BIGINT" in all_ddl
        assert "VARCHAR" in all_ddl
        assert "PRIMARY KEY" in all_ddl

        # 5. Export SQL file
        r = self._run(["--json", "--project", path, "export", "sql", "-o", out_sql, "--db", "MySQL"])
        assert r.returncode == 0
        assert os.path.exists(out_sql)
        assert os.path.getsize(out_sql) > 0
        print(f"\n  SQL artifact: {out_sql} ({os.path.getsize(out_sql):,} bytes)")
        with open(out_sql) as f:
            content = f.read()
        assert "sys_user" in content

        # 6. Verify project file structure
        with open(path) as f:
            saved = json.load(f)
        assert saved["name"] == "myapp"
        assert len(saved["entities"]) == 2
        user_entity = saved["entities"][0]
        assert len(user_entity["fields"]) == 4
        assert user_entity["fields"][0]["defKey"] == "id"
        assert user_entity["fields"][0]["primaryKey"] is True


class TestE2EInMemory:
    """Tests that exercise core modules directly (no subprocess)."""

    def test_full_workflow_programmatic(self, tmp_path):
        from cli_anything.pdmaner.core.project import create_project, save_project
        from cli_anything.pdmaner.core.entity import add_entity, add_field, get_entity
        from cli_anything.pdmaner.core.diagram import add_diagram, add_table_to_diagram, add_relation_to_diagram
        from cli_anything.pdmaner.core.export_ import generate_ddl, export_sql

        p = create_project("testdb", "Test DB")

        # Create entities
        users = add_entity(p, "users", "用户表")
        add_field(p, users["id"], "id", "ID", "BIGINT", primaryKey=True, notNull=True, autoIncrement=True, comment="PK")
        add_field(p, users["id"], "name", "名称", "VARCHAR", len_="64", notNull=True)

        orders = add_entity(p, "orders", "订单表")
        add_field(p, orders["id"], "id", "ID", "BIGINT", primaryKey=True, notNull=True, autoIncrement=True)
        add_field(p, orders["id"], "user_id", "用户ID", "BIGINT", notNull=True)
        add_field(p, orders["id"], "amount", "金额", "DECIMAL", len_="10", scale="2")

        # Create diagram with relation
        dia = add_diagram(p, "main", "主关系图")
        add_table_to_diagram(p, dia["id"], users["id"])
        add_table_to_diagram(p, dia["id"], orders["id"])
        add_relation_to_diagram(p, dia["id"], users["id"], orders["id"],
                                "id", "user_id", "1:n")

        # Verify diagram
        assert len(dia["canvasData"]["cells"]) == 3  # 2 tables + 1 edge

        # Generate DDL
        ddls = generate_ddl(p, "MySQL")
        assert len(ddls) == 2
        assert any("users" in d for d in ddls)
        assert any("orders" in d for d in ddls)

        # Save
        path = str(tmp_path / "test.chnr.json")
        save_project(p, path)
        assert os.path.exists(path)
        print(f"\n  Project artifact: {path} ({os.path.getsize(path):,} bytes)")

        # Export SQL file
        sql_path = str(tmp_path / "test.sql")
        export_sql(p, sql_path, "MySQL")
        with open(sql_path) as f:
            content = f.read()
        assert "CREATE TABLE" in content
        print(f"  SQL artifact: {sql_path} ({os.path.getsize(sql_path):,} bytes)")
