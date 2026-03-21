import pytest
from cli_anything.48_drift.core.session import Session
def test_session(): s = Session(); assert not s.has_project()
def test_session_set(): s = Session(); s.set_project({"name":"t","metadata":{}}); assert s.has_project()
def test_undo(): s = Session(); s.set_project({"name":"v1","metadata":{}}); s.snapshot("c"); s.project["name"]="v2"; s.undo(); assert s.project["name"]=="v1"
def test_redo(): s = Session(); s.set_project({"name":"v1","metadata":{}}); s.snapshot("c"); s.project["name"]="v2"; s.undo(); s.redo(); assert s.project["name"]=="v2"
def test_history(): s = Session(); s.set_project({"name":"t","metadata":{}}); s.snapshot("a"); s.project["x"]=1; assert len(s.list_history())==1
