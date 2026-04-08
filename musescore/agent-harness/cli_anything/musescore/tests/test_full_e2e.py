"""End-to-end tests for cli-anything-musescore.

These tests require a real MuseScore 4 (mscore) installation and
use the sample files in musescore/test-mscore/twinkle-twinkle/.

Run with: pytest cli_anything/musescore/tests/test_full_e2e.py -v -s
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# ── Test fixture paths ────────────────────────────────────────────────

# Test fixtures live alongside this file
_THIS_DIR = Path(__file__).resolve().parent
_SAMPLE_DIR = _THIS_DIR / "fixtures" / "twinkle-twinkle"
_SAMPLE_MXL = _SAMPLE_DIR / "twinkle_twinkle_G.mxl"
_SAMPLE_MSCZ = _SAMPLE_DIR / "twinkle_twinkle_G.mscz"


def _resolve_cli(name: str) -> list[str]:
    """Resolve the CLI command for subprocess tests.

    If CLI_ANYTHING_FORCE_INSTALLED is set, use the installed command.
    Otherwise, use python -m.
    """
    if os.environ.get("CLI_ANYTHING_FORCE_INSTALLED"):
        import shutil
        path = shutil.which(name)
        if path:
            return [path]
        raise RuntimeError(f"{name} not found on PATH")
    return [sys.executable, "-m", "cli_anything.musescore"]


def _has_mscore() -> bool:
    """Check if mscore is available."""
    try:
        from cli_anything.musescore.utils.musescore_backend import find_musescore
        find_musescore()
        return True
    except RuntimeError:
        return False


def _has_samples() -> bool:
    """Check if sample files exist."""
    return _SAMPLE_MXL.is_file()


requires_mscore = pytest.mark.skipif(
    not _has_mscore(), reason="mscore not installed"
)
requires_samples = pytest.mark.skipif(
    not _has_samples(), reason="sample files not found"
)


# ── Export E2E Tests ──────────────────────────────────────────────────

@requires_mscore
@requires_samples
class TestExportE2E:
    def test_export_pdf(self):
        """Export MXL to PDF, verify magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            out = f.name
        try:
            from cli_anything.musescore.core.export import export_score, verify_output
            export_score(str(_SAMPLE_MXL), out, fmt="pdf")
            result = verify_output(out, "pdf")
            assert result["valid"], f"PDF verification failed: {result}"
            print(f"  PDF output: {out} ({result['size']} bytes)")
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_export_midi(self):
        """Export MXL to MIDI, verify magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            out = f.name
        try:
            from cli_anything.musescore.core.export import export_score, verify_output
            export_score(str(_SAMPLE_MXL), out, fmt="midi")
            result = verify_output(out, "midi")
            assert result["valid"], f"MIDI verification failed: {result}"
            print(f"  MIDI output: {out} ({result['size']} bytes)")
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_export_mp3(self):
        """Export MXL to MP3, verify magic bytes."""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            out = f.name
        try:
            from cli_anything.musescore.core.export import export_score, verify_output
            export_score(str(_SAMPLE_MXL), out, fmt="mp3", bitrate=128)
            result = verify_output(out, "mp3")
            assert result["valid"], f"MP3 verification failed: {result}"
            print(f"  MP3 output: {out} ({result['size']} bytes)")
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_export_musicxml(self):
        """Export MSCZ to MusicXML, verify XML structure."""
        with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as f:
            out = f.name
        try:
            from cli_anything.musescore.core.export import export_score
            export_score(str(_SAMPLE_MSCZ), out, fmt="musicxml")
            import xml.etree.ElementTree as ET
            tree = ET.parse(out)
            assert tree.getroot().tag == "score-partwise"
            print(f"  MusicXML output: {out}")
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_export_png(self):
        """Export MXL to PNG, verify at least one page produced."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = os.path.join(tmpdir, "output.png")
            from cli_anything.musescore.core.export import export_score
            export_score(str(_SAMPLE_MXL), out, fmt="png", dpi=72)
            # mscore produces output-1.png, output-2.png, etc.
            pngs = list(Path(tmpdir).glob("*.png"))
            assert len(pngs) >= 1, f"No PNG files produced in {tmpdir}"
            # Verify first PNG magic bytes
            with open(pngs[0], "rb") as f:
                header = f.read(4)
            assert header == b"\x89PNG", f"Invalid PNG header: {header}"
            print(f"  PNG pages: {len(pngs)}")


# ── Transpose E2E Tests ──────────────────────────────────────────────

@requires_mscore
@requires_samples
class TestTransposeE2E:
    def test_transpose_g_to_c(self):
        """Transpose G major MXL to C major, verify key signature."""
        with tempfile.NamedTemporaryFile(suffix=".mscz", delete=False) as f:
            out = f.name
        try:
            from cli_anything.musescore.core.transpose import transpose_by_key
            result = transpose_by_key(
                str(_SAMPLE_MXL), out,
                target_key="C major",
                direction="closest",
            )
            assert result["target_key_int"] == 0

            # Export to MusicXML and check key signature
            with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False) as fx:
                xml_out = fx.name
            from cli_anything.musescore.core.export import export_score
            export_score(out, xml_out, fmt="musicxml")

            from cli_anything.musescore.utils.mscx_xml import read_score_tree, get_key_signature
            tree = read_score_tree(xml_out)
            keysig = get_key_signature(tree)
            assert keysig == 0, f"Expected keysig=0 (C major), got {keysig}"
            print(f"  Transposed G→C: keysig={keysig}")
            os.unlink(xml_out)
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_transpose_by_interval(self):
        """Transpose by 2 semitones (major second up)."""
        with tempfile.NamedTemporaryFile(suffix=".mscz", delete=False) as f:
            out = f.name
        try:
            from cli_anything.musescore.core.transpose import transpose_by_interval
            result = transpose_by_interval(
                str(_SAMPLE_MXL), out,
                semitones=2,
                direction="up",
            )
            assert result["mode"] == "by_interval"
            assert os.path.isfile(out)
            print(f"  Transposed by +2 semitones: {out}")
        finally:
            if os.path.exists(out):
                os.unlink(out)


# ── Parts E2E Tests ──────────────────────────────────────────────────

@requires_mscore
@requires_samples
class TestPartsE2E:
    def test_list_parts(self):
        """List parts in the sample score."""
        from cli_anything.musescore.core.parts import list_parts
        parts = list_parts(str(_SAMPLE_MXL))
        assert len(parts) >= 1
        print(f"  Parts: {[p['name'] for p in parts]}")

    def test_extract_part(self):
        """Extract the first part."""
        from cli_anything.musescore.core.parts import list_parts, extract_part
        parts = list_parts(str(_SAMPLE_MXL))
        if not parts:
            pytest.skip("No parts found")

        first_part = parts[0]["name"]
        with tempfile.NamedTemporaryFile(suffix=".mscz", delete=False) as f:
            out = f.name
        try:
            result = extract_part(str(_SAMPLE_MXL), first_part, out)
            assert os.path.isfile(out)
            assert result["size_bytes"] > 0
            print(f"  Extracted '{first_part}': {result['size_bytes']} bytes")
        finally:
            if os.path.exists(out):
                os.unlink(out)


# ── Media E2E Tests ──────────────────────────────────────────────────

@requires_mscore
@requires_samples
class TestMediaE2E:
    def test_probe_mxl(self):
        """Probe sample MXL file."""
        from cli_anything.musescore.core.media import probe_score
        result = probe_score(str(_SAMPLE_MXL))
        assert result["format"] == "mxl"
        assert "metadata" in result
        print(f"  Probe: {json.dumps(result.get('metadata', {}), indent=2, default=str)[:200]}")

    def test_probe_mscz(self):
        """Probe sample MSCZ file."""
        from cli_anything.musescore.core.media import probe_score
        result = probe_score(str(_SAMPLE_MSCZ))
        assert result["format"] == "mscz"
        assert "metadata" in result

    def test_stats_mxl(self):
        """Get stats for sample MXL file."""
        from cli_anything.musescore.core.media import score_stats
        result = score_stats(str(_SAMPLE_MXL))
        assert "stats" in result
        assert result["stats"]["measures"] > 0
        assert result["stats"]["notes"] > 0
        print(f"  Stats: {result['stats']}")


# ── CLI Subprocess Tests ─────────────────────────────────────────────

class TestCLISubprocess:
    def test_help(self):
        """Test --help flag."""
        cmd = _resolve_cli("cli-anything-musescore") + ["--help"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0
        assert "MuseScore CLI" in result.stdout or "musescore" in result.stdout.lower()
        print(f"  --help: OK ({len(result.stdout)} chars)")

    @requires_mscore
    @requires_samples
    def test_json_project_info(self):
        """Test --json project info via subprocess."""
        cmd = _resolve_cli("cli-anything-musescore") + [
            "--json", "project", "info", "-i", str(_SAMPLE_MXL)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "metadata" in data or "path" in data
        print(f"  JSON project info: OK")

    @requires_mscore
    @requires_samples
    def test_json_export_pdf(self):
        """Test --json export pdf via subprocess."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            out = f.name
        try:
            cmd = _resolve_cli("cli-anything-musescore") + [
                "--json", "export", "pdf",
                "-i", str(_SAMPLE_MXL),
                "-o", out,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data.get("format") == "pdf"
            # Verify the output file
            assert os.path.isfile(out)
            with open(out, "rb") as f:
                header = f.read(5)
            assert header == b"%PDF-"
            print(f"  JSON export pdf: OK")
        finally:
            if os.path.exists(out):
                os.unlink(out)

    @requires_mscore
    @requires_samples
    def test_json_transpose_by_key(self):
        """Test --json transpose by-key via subprocess."""
        with tempfile.NamedTemporaryFile(suffix=".mscz", delete=False) as f:
            out = f.name
        try:
            cmd = _resolve_cli("cli-anything-musescore") + [
                "--json", "transpose", "by-key",
                "-i", str(_SAMPLE_MXL),
                "-o", out,
                "--target-key", "C major",
                "--direction", "closest",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert data.get("target_key_int") == 0
            print(f"  JSON transpose by-key: OK")
        finally:
            if os.path.exists(out):
                os.unlink(out)

    @requires_mscore
    @requires_samples
    def test_full_workflow(self):
        """Test a full workflow: info → transpose → export PDF → verify."""
        with tempfile.TemporaryDirectory() as tmpdir:
            transposed = os.path.join(tmpdir, "transposed.mscz")
            pdf_out = os.path.join(tmpdir, "output.pdf")

            # 1. Transpose G → C
            cmd = _resolve_cli("cli-anything-musescore") + [
                "--json", "transpose", "by-key",
                "-i", str(_SAMPLE_MXL),
                "-o", transposed,
                "--target-key", "C major",
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, f"Transpose failed: {r.stderr}"

            # 2. Export to PDF
            cmd = _resolve_cli("cli-anything-musescore") + [
                "--json", "export", "pdf",
                "-i", transposed,
                "-o", pdf_out,
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, f"Export failed: {r.stderr}"

            # 3. Verify PDF
            with open(pdf_out, "rb") as f:
                assert f.read(5) == b"%PDF-"

            print(f"  Full workflow: transpose → export → verify: OK")
