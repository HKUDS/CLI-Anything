"""End-to-end tests for cli-anything-nslogger using real files and subprocess."""
from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile

import pytest

from cli_anything.nslogger.utils.generate import generate_sample_file
from cli_anything.nslogger.core.parser import parse_raw_file
from cli_anything.nslogger.core.filter import filter_messages
from cli_anything.nslogger.core.stats import compute_stats
from cli_anything.nslogger.core.exporter import export_messages


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_cli(name: str) -> list[str]:
    """Return argv prefix for the CLI, respecting test-mode env var."""
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED"):
        return [name]
    # When not installed, run via python -m
    return [sys.executable, "-m", f"cli_anything.nslogger.nslogger_cli"]


def run_cli(*args, expect_ok=True) -> subprocess.CompletedProcess:
    cmd = _resolve_cli("cli-anything-nslogger") + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if expect_ok and result.returncode != 0:
        pytest.fail(f"CLI failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
    return result


@pytest.fixture(scope="module")
def sample_file(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("data") / "sample.rawnsloggerdata")
    generate_sample_file(path, count=30)
    return path


# ---------------------------------------------------------------------------
# generate command
# ---------------------------------------------------------------------------

class TestGenerateCommand:
    def test_generate_creates_file(self, tmp_path):
        out = str(tmp_path / "gen.rawnsloggerdata")
        result = run_cli("generate", out, "--count", "10")
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

    def test_generate_output_mentions_count(self, tmp_path):
        out = str(tmp_path / "gen.rawnsloggerdata")
        result = run_cli("generate", out, "--count", "10")
        assert "10" in result.stdout

    def test_generate_parseable(self, tmp_path):
        out = str(tmp_path / "gen.rawnsloggerdata")
        run_cli("generate", out, "--count", "15")
        msgs = list(parse_raw_file(out))
        assert len(msgs) >= 15


# ---------------------------------------------------------------------------
# read command
# ---------------------------------------------------------------------------

class TestReadCommand:
    def test_read_outputs_messages(self, sample_file):
        result = run_cli("read", sample_file)
        lines = [l for l in result.stdout.strip().splitlines() if l]
        assert len(lines) > 0

    def test_read_json_valid(self, sample_file):
        result = run_cli("read", sample_file, "--json")
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_read_json_message_shape(self, sample_file):
        result = run_cli("read", sample_file, "--json")
        data = json.loads(result.stdout)
        msg = data[0]
        for key in ("sequence", "level", "level_name", "type", "text"):
            assert key in msg

    def test_read_level_filter(self, sample_file):
        result = run_cli("read", sample_file, "--level", "0", "--json")
        data = json.loads(result.stdout)
        assert all(m["level"] <= 0 for m in data)

    def test_read_limit(self, sample_file):
        result = run_cli("read", sample_file, "--limit", "5", "--json")
        data = json.loads(result.stdout)
        assert len(data) <= 5

    def test_read_search(self, sample_file):
        result = run_cli("read", sample_file, "--search", "error", "--json")
        data = json.loads(result.stdout)
        for m in data:
            assert "error" in m["text"].lower() or m["level"] == 0


# ---------------------------------------------------------------------------
# filter command
# ---------------------------------------------------------------------------

class TestFilterCommand:
    def test_filter_by_level(self, sample_file):
        result = run_cli("filter", sample_file, "--level", "1", "--json")
        data = json.loads(result.stdout)
        assert all(m["level"] <= 1 for m in data)

    def test_filter_no_results(self, sample_file, tmp_path):
        # Generate file with no level-99 messages
        out = str(tmp_path / "g.rawnsloggerdata")
        generate_sample_file(out, count=5)
        result = run_cli("filter", out, "--search", "XYZZY_NEVER_MATCHES_ANYTHING")
        assert result.stdout.strip() == ""

    def test_filter_regex(self, sample_file):
        result = run_cli("filter", sample_file, "--regex", r"(error|failed)", "--json")
        data = json.loads(result.stdout)
        import re
        pattern = re.compile(r"(error|failed)", re.IGNORECASE)
        for m in data:
            assert pattern.search(m["text"]), f"No match in: {m['text']!r}"


# ---------------------------------------------------------------------------
# export command
# ---------------------------------------------------------------------------

class TestExportCommand:
    def test_export_text_stdout(self, sample_file):
        result = run_cli("export", sample_file, "--format", "text")
        assert len(result.stdout) > 0

    def test_export_json_stdout(self, sample_file):
        result = run_cli("export", sample_file, "--format", "json")
        data = json.loads(result.stdout)
        assert isinstance(data, list)

    def test_export_csv_stdout(self, sample_file):
        result = run_cli("export", sample_file, "--format", "csv")
        lines = result.stdout.strip().splitlines()
        assert "sequence" in lines[0]
        assert len(lines) > 1

    def test_export_to_file(self, sample_file, tmp_path):
        out = str(tmp_path / "export.json")
        run_cli("export", sample_file, "--format", "json", "--output", out)
        assert os.path.exists(out)
        with open(out) as f:
            data = json.load(f)
        assert isinstance(data, list)

    def test_export_with_level_filter(self, sample_file):
        result = run_cli("export", sample_file, "--format", "json", "--level", "1")
        data = json.loads(result.stdout)
        assert all(m["level"] <= 1 for m in data)


# ---------------------------------------------------------------------------
# stats command
# ---------------------------------------------------------------------------

class TestStatsCommand:
    def test_stats_text_output(self, sample_file):
        result = run_cli("stats", sample_file)
        assert "Total" in result.stdout or "total" in result.stdout.lower()

    def test_stats_json_output(self, sample_file):
        result = run_cli("stats", sample_file, "--json")
        data = json.loads(result.stdout)
        assert "total" in data
        assert data["total"] > 0

    def test_stats_json_has_by_level(self, sample_file):
        result = run_cli("stats", sample_file, "--json")
        data = json.loads(result.stdout)
        assert "by_level" in data

    def test_stats_json_has_by_tag(self, sample_file):
        result = run_cli("stats", sample_file, "--json")
        data = json.loads(result.stdout)
        assert "by_tag" in data


# ---------------------------------------------------------------------------
# Full pipeline workflow test
# ---------------------------------------------------------------------------

class TestWorkflow:
    def test_generate_filter_export_pipeline(self, tmp_path):
        """Generate → filter errors → export JSON."""
        log_file = str(tmp_path / "app.rawnsloggerdata")
        generate_sample_file(log_file, count=50)

        msgs = list(parse_raw_file(log_file))
        assert len(msgs) > 0

        errors = list(filter_messages(iter(msgs), max_level=0))
        assert isinstance(errors, list)

        out = export_messages(iter(errors), fmt="json")
        data = json.loads(out)
        for m in data:
            assert m["level"] <= 0

    def test_stats_on_generated_file(self, tmp_path):
        log_file = str(tmp_path / "app.rawnsloggerdata")
        generate_sample_file(log_file, count=40)
        msgs = list(parse_raw_file(log_file))
        s = compute_stats(iter(msgs))
        assert s["total"] >= 40
        assert "by_level" in s
        assert "by_tag" in s

    def test_cli_help_shows_commands(self):
        result = run_cli("--help")
        for cmd in ("read", "filter", "export", "stats", "listen", "generate"):
            assert cmd in result.stdout


# ---------------------------------------------------------------------------
# TestCLISubprocess — installed entrypoint tests
# ---------------------------------------------------------------------------

class TestCLISubprocess:
    def test_installed_cli_help(self):
        cmd = _resolve_cli("cli-anything-nslogger") + ["--help"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        assert result.returncode == 0
        assert "NSLogger" in result.stdout

    def test_installed_generate_and_read(self, tmp_path):
        out = str(tmp_path / "sub.rawnsloggerdata")
        run_cli("generate", out, "--count", "5")
        result = run_cli("read", out, "--json")
        data = json.loads(result.stdout)
        assert len(data) >= 5

    def test_installed_stats_json(self, tmp_path):
        out = str(tmp_path / "sub2.rawnsloggerdata")
        run_cli("generate", out, "--count", "8")
        result = run_cli("stats", out, "--json")
        data = json.loads(result.stdout)
        assert data["total"] >= 8

    def test_installed_export_csv(self, tmp_path):
        out = str(tmp_path / "sub3.rawnsloggerdata")
        run_cli("generate", out, "--count", "5")
        result = run_cli("export", out, "--format", "csv")
        assert "sequence" in result.stdout.splitlines()[0]


# ---------------------------------------------------------------------------
# tail command
# ---------------------------------------------------------------------------

class TestTailCommand:
    def test_tail_returns_last_n(self, tmp_path):
        out = str(tmp_path / "tail.rawnsloggerdata")
        run_cli("generate", out, "--count", "20")
        result_all = run_cli("read", out, "--json")
        result_tail = run_cli("tail", out, "--count", "5", "--json")
        all_msgs = json.loads(result_all.stdout)
        tail_msgs = json.loads(result_tail.stdout)
        assert len(tail_msgs) == 5
        # Last 5 of all should match tail
        assert [m["sequence"] for m in tail_msgs] == [m["sequence"] for m in all_msgs[-5:]]

    def test_tail_default_count(self, tmp_path):
        out = str(tmp_path / "tail2.rawnsloggerdata")
        run_cli("generate", out, "--count", "30")
        result = run_cli("tail", out, "--json")
        data = json.loads(result.stdout)
        assert len(data) == 20  # default is 20

    def test_tail_text_output(self, tmp_path):
        out = str(tmp_path / "tail3.rawnsloggerdata")
        run_cli("generate", out, "--count", "5")
        result = run_cli("tail", out)
        assert len(result.stdout.strip().splitlines()) > 0


# ---------------------------------------------------------------------------
# clients command
# ---------------------------------------------------------------------------

class TestClientsCommand:
    def test_clients_json_output(self, sample_file):
        result = run_cli("clients", sample_file, "--json")
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        # sample file should have at least one client_info
        if data:
            assert "client_name" in data[0]

    def test_clients_text_output(self, sample_file):
        result = run_cli("clients", sample_file)
        assert result.returncode == 0  # may output "No client_info" or real clients

    def test_clients_empty_file(self, tmp_path):
        # File with only plain log messages, no client_info
        from cli_anything.nslogger.utils.generate import encode_message
        path = str(tmp_path / "no_clients.rawnsloggerdata")
        with open(path, "wb") as f:
            f.write(encode_message(sequence=0, text="plain log"))
        result = run_cli("clients", path)
        assert result.returncode == 0
        assert "No client_info" in result.stdout


# ---------------------------------------------------------------------------
# blocks command
# ---------------------------------------------------------------------------

class TestBlocksCommand:
    def test_blocks_text_output(self, sample_file):
        result = run_cli("blocks", sample_file)
        assert result.returncode == 0
        assert len(result.stdout.strip()) > 0

    def test_blocks_json_output(self, sample_file):
        result = run_cli("blocks", sample_file, "--json")
        data = json.loads(result.stdout)
        assert isinstance(data, list)
        for entry in data:
            assert "depth" in entry
            assert "sequence" in entry

    def test_blocks_indent_applied(self, tmp_path):
        from cli_anything.nslogger.utils.generate import encode_message
        from cli_anything.nslogger.core.message import MSG_TYPE_BLOCK_START, MSG_TYPE_BLOCK_END
        path = str(tmp_path / "blk.rawnsloggerdata")
        with open(path, "wb") as f:
            f.write(encode_message(sequence=0, text="before"))
            f.write(encode_message(sequence=1, msg_type=MSG_TYPE_BLOCK_START, text="enter"))
            f.write(encode_message(sequence=2, text="inside"))
            f.write(encode_message(sequence=3, msg_type=MSG_TYPE_BLOCK_END, text="exit"))
        result = run_cli("blocks", path, "--indent", "4")
        lines = result.stdout.splitlines()
        # "inside" should be indented (4 spaces)
        inside_lines = [l for l in lines if "inside" in l]
        assert inside_lines and inside_lines[0].startswith("    ")


# ---------------------------------------------------------------------------
# merge command
# ---------------------------------------------------------------------------

class TestMergeCommand:
    def test_merge_two_files(self, tmp_path):
        a = str(tmp_path / "a.rawnsloggerdata")
        b = str(tmp_path / "b.rawnsloggerdata")
        run_cli("generate", a, "--count", "5")
        run_cli("generate", b, "--count", "5")
        result = run_cli("merge", a, b, "--format", "json")
        data = json.loads(result.stdout)
        assert len(data) >= 10

    def test_merge_to_file(self, tmp_path):
        a = str(tmp_path / "c.rawnsloggerdata")
        b = str(tmp_path / "d.rawnsloggerdata")
        out = str(tmp_path / "merged.json")
        run_cli("generate", a, "--count", "5")
        run_cli("generate", b, "--count", "5")
        run_cli("merge", a, b, "--format", "json", "--output", out)
        assert os.path.exists(out)
        with open(out) as f:
            data = json.load(f)
        assert len(data) >= 10

    def test_merge_csv_format(self, tmp_path):
        a = str(tmp_path / "e.rawnsloggerdata")
        run_cli("generate", a, "--count", "5")
        result = run_cli("merge", a, "--format", "csv")
        assert "sequence" in result.stdout.splitlines()[0]


# ---------------------------------------------------------------------------
# filter — new options (time-range, seq-range)
# ---------------------------------------------------------------------------

class TestFilterExtendedOptions:
    def test_filter_from_seq(self, tmp_path):
        out = str(tmp_path / "seqtest.rawnsloggerdata")
        run_cli("generate", out, "--count", "10")
        all_data = json.loads(run_cli("read", out, "--json").stdout)
        mid_seq = all_data[5]["sequence"]
        result = run_cli("filter", out, "--from-seq", str(mid_seq), "--json")
        data = json.loads(result.stdout)
        assert all(m["sequence"] >= mid_seq for m in data)

    def test_filter_to_seq(self, tmp_path):
        out = str(tmp_path / "seqtest2.rawnsloggerdata")
        run_cli("generate", out, "--count", "10")
        all_data = json.loads(run_cli("read", out, "--json").stdout)
        mid_seq = all_data[5]["sequence"]
        result = run_cli("filter", out, "--to-seq", str(mid_seq), "--json")
        data = json.loads(result.stdout)
        assert all(m["sequence"] <= mid_seq for m in data)
