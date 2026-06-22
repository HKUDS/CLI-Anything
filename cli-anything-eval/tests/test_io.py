import json

from cli_anything.eval.io import safe_write_json


def test_writes_json(tmp_path):
    p = tmp_path / "out.json"
    safe_write_json(p, {"a": 1, "b": [1, 2]})
    assert json.loads(p.read_text(encoding="utf-8")) == {"a": 1, "b": [1, 2]}


def test_overwrites_existing(tmp_path):
    p = tmp_path / "out.json"
    p.write_text('{"old": true}', encoding="utf-8")
    safe_write_json(p, {"new": 1})
    assert json.loads(p.read_text(encoding="utf-8")) == {"new": 1}


def test_default_serializer(tmp_path):
    from pathlib import PurePosixPath
    p = tmp_path / "out.json"
    safe_write_json(p, {"path": PurePosixPath("/tmp/x")}, default=str)
    assert json.loads(p.read_text(encoding="utf-8")) == {"path": "/tmp/x"}
