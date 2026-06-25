from click.testing import CliRunner

from cli_anything.eval.cli import build_eval_command, main
from cli_anything.eval.runner import discover_tasks  # noqa: F401  (import sanity)
from tests._util import make_tasks_pkg

PASS_SRC = '''
TASK = {"id": "p", "name": "P", "description": "d"}
def run(ctx):
    return {"ok": True}
'''


def test_build_eval_command_run(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": PASS_SRC})
    group = build_eval_command(pkg, "Demo")
    runner = CliRunner()
    result = runner.invoke(group, ["run", "-o", str(tmp_path / "o"), "--json"])
    assert result.exit_code == 0
    assert '"passed": 1' in result.output


def test_build_eval_command_list(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": PASS_SRC})
    group = build_eval_command(pkg, "Demo")
    result = CliRunner().invoke(group, ["list"])
    assert result.exit_code == 0
    assert "p" in result.output


def test_main_run(tmp_path):
    pkg = make_tasks_pkg(tmp_path, {"m": PASS_SRC})
    result = CliRunner().invoke(
        main, ["run", "--harness", pkg, "--name", "Demo", "-o", str(tmp_path / "o"), "--json"])
    assert result.exit_code == 0
    assert '"passed": 1' in result.output
