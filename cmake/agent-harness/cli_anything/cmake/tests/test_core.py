import pytest
from cli_anything.cmake.core.session import Session

def test_session_init():
    s = Session()
    assert s.project is None
    assert not s.has_project()

def test_set_project():
    s = Session()
    proj = {"name":"test","metadata":{"modified":""}}
    s.set_project(proj, "/tmp/test.json")
    assert s.has_project()
    assert s.get_project()["name"] == "test"

def test_undo_redo():
    s = Session()
    s.set_project({"name":"v1","metadata":{"modified":""}}, "/tmp/t.json")
    s.snapshot("change")
    s.project["name"] = "v2"
    desc = s.undo()
    assert s.project["name"] == "v1"
    desc = s.redo()
    assert s.project["name"] == "v2"

def test_status():
    s = Session()
    st = s.status()
    assert st["has_project"] is False
    assert st["undo_count"] == 0
    s.set_project({"name":"t","metadata":{"modified":""}}, "/tmp/x.json")
    st = s.status()
    assert st["has_project"] is True
    assert st["project_name"] == "t"

def test_save_session(tmp_path):
    s = Session()
    p = {"name":"test","metadata":{"modified":""}}
    s.set_project(p, str(tmp_path/"out.json"))
    result = s.save_session()
    assert result.endswith("out.json")
    assert not s._modified
