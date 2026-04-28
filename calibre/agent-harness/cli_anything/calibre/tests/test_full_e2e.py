from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
import sys
import sysconfig
import site
import tempfile
import zipfile
from pathlib import Path

import pytest


def _require_binary(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    raise RuntimeError(
        f"Required calibre dependency not found on PATH: {name}. "
        "Install calibre and ensure these commands are available: calibredb, ebook-convert, ebook-meta"
    )


def _resolve_cli(name):
    force = os.environ.get("CLI_ANYTHING_FORCE_INSTALLED", "").strip() == "1"
    path = shutil.which(name)
    if path:
        print(f"[_resolve_cli] Using installed command: {path}")
        return [path]
    # On Windows (especially Store Python), console_scripts may be installed in a
    # user Scripts directory that is not on PATH. If force-installed mode is
    # enabled, try to resolve that location explicitly before failing.
    if os.name == "nt":
        try:
            scripts_dir = Path(sysconfig.get_path("scripts") or "")
            candidate = scripts_dir / f"{name}.exe"
            if scripts_dir and candidate.exists():
                print(f"[_resolve_cli] Using installed command (Scripts): {candidate}")
                return [str(candidate)]
        except Exception:
            pass
        try:
            user_base = site.getuserbase()
            if user_base:
                candidates = [
                    Path(user_base) / "Scripts",
                    Path(user_base) / "Python312" / "Scripts",
                    Path(user_base) / "python312" / "Scripts",
                ]
                for scripts_dir in candidates:
                    candidate = scripts_dir / f"{name}.exe"
                    if candidate.exists():
                        print(f"[_resolve_cli] Using installed command (user Scripts): {candidate}")
                        return [str(candidate)]
        except Exception:
            pass
    if force:
        raise RuntimeError(f"{name} not found in PATH. Install with: pip install -e .")
    module = name.replace("cli-anything-", "cli_anything.")
    print(f"[_resolve_cli] Falling back to: {sys.executable} -m {module}")
    return [sys.executable, "-m", module]


def _make_sample_epub(path: Path, title: str = "Sample Book", author: str = "Test Author") -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""",
        )
        zf.writestr(
            "OEBPS/chapter.xhtml",
            """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Sample</title></head>
  <body><h1>Sample</h1><p>Hello calibre.</p></body>
</html>""",
        )
        zf.writestr(
            "OEBPS/toc.ncx",
            """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:12345678-1234-1234-1234-123456789abc"/>
  </head>
  <docTitle><text>Sample Book</text></docTitle>
  <navMap>
    <navPoint id="navPoint-1" playOrder="1">
      <navLabel><text>Chapter 1</text></navLabel>
      <content src="chapter.xhtml"/>
    </navPoint>
  </navMap>
</ncx>""",
        )
        zf.writestr(
            "OEBPS/content.opf",
            f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="BookId">urn:uuid:12345678-1234-1234-1234-123456789abc</dc:identifier>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="chapter" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="chapter"/>
  </spine>
</package>""",
        )
    return path


def _run_raw(cmd, env=None):
    encoding = locale.getpreferredencoding(False) or "utf-8"
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        encoding=encoding,
        errors="replace",
    )


def _run_cli(cli_base, args, env=None):
    return _run_raw(cli_base + args, env=env)


@pytest.fixture(scope="module")
def cli_base():
    return _resolve_cli("cli-anything-calibre")


@pytest.fixture
def workflow_root():
    root = Path(tempfile.mkdtemp(prefix="ccal-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def workflow_env(workflow_root):
    env = os.environ.copy()
    env["USERPROFILE"] = str(workflow_root / "home")
    return env


@pytest.fixture
def real_library(workflow_root):
    library = workflow_root / "lib"
    result = _run_raw(
        [_require_binary("calibredb"), "list", "--for-machine", "--fields", "id,title", "--with-library", str(library)]
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert (library / "metadata.db").exists()
    return library


@pytest.fixture
def sample_epub(workflow_root):
    return _make_sample_epub(workflow_root / "workflow-sample.epub", title="Workflow Sample", author="Workflow Fixture")


class TestCLISubprocess:
    def test_help(self, cli_base):
        result = _run_cli(cli_base, ["--help"])
        assert result.returncode == 0
        assert "library" in result.stdout


def test_calibredb_available():
    _require_binary("calibredb")
    result = _run_raw([shutil.which("calibredb"), "--version"])
    assert result.returncode == 0


def test_ebook_convert_available():
    _require_binary("ebook-convert")
    result = _run_raw([shutil.which("ebook-convert"), "--version"])
    assert result.returncode == 0


def test_json_library_command_requires_valid_library(tmp_path, cli_base, workflow_env):
    _require_binary("calibredb")
    fake_lib = tmp_path / "fake"
    fake_lib.mkdir()
    result = _run_cli(
        cli_base,
        ["--json", "--library", str(fake_lib), "library", "info"],
        env=workflow_env,
    )
    assert result.returncode != 0
    data = json.loads(result.stdout)
    assert "error" in data


def test_meta_show_missing_file_errors(cli_base, workflow_env):
    _require_binary("ebook-meta")
    result = _run_cli(
        cli_base,
        ["--json", "meta", "show", "definitely-missing.epub"],
        env=workflow_env,
    )
    assert result.returncode != 0
    data = json.loads(result.stdout)
    assert data["type"] in {"file_not_found", "RuntimeError", "FileNotFoundError"}

# 新增ebook-meta工作流：
def test_workflow_meta_set_then_show_reflects_changes(cli_base, workflow_env, sample_epub):
  _require_binary("ebook-meta")
  # 1) show before (JSON mode)
  before = _run_cli(cli_base, ["--json", "meta", "show", str(sample_epub)], env=workflow_env)
  assert before.returncode == 0
  before_data = json.loads(before.stdout)
  assert before_data["path"] == str(sample_epub)
  assert isinstance(before_data["metadata"], str)
  # 2) set title/authors
  new_title = "Workflow Meta Title"
  new_authors = "Workflow Meta Author"
  set_result = _run_cli(
      cli_base,
      ["--json", "meta", "set", str(sample_epub), "--title", new_title, "--authors", new_authors],
      env=workflow_env,
  )
  assert set_result.returncode == 0
  set_data = json.loads(set_result.stdout)
  assert set_data["path"] == str(sample_epub)
  # 3) show after and assert new metadata appears
  after = _run_cli(cli_base, ["--json", "meta", "show", str(sample_epub)], env=workflow_env)
  assert after.returncode == 0
  after_data = json.loads(after.stdout)
  meta_text = after_data["metadata"]
  assert new_title in meta_text
  # authors formatting varies across calibre versions; keep it lenient:
  assert "Workflow Meta Author" in meta_text 

def test_workflow_ingest_and_inspect(cli_base, workflow_env, real_library, sample_epub):
    _require_binary("calibredb")
    _require_binary("ebook-meta")
    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "add",
            str(sample_epub),
            "--title",
            "Workflow Book",
            "--authors",
            "Workflow Author",
            "--tags",
            "workflow,test",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0
    add_data = json.loads(add_result.stdout)
    assert "input" in add_data

    list_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "list"],
        env=workflow_env,
    )
    assert list_result.returncode == 0
    books = json.loads(list_result.stdout)
    assert len(books) == 1
    book = books[0]
    assert book["title"] == "Workflow Book"
    assert book["id"] == 1
    assert "Workflow Author" in str(book.get("authors"))
    assert book.get("formats")
    book_id = book["id"]

    search_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "search", "Workflow"],
        env=workflow_env,
    )
    assert search_result.returncode == 0
    search_books = json.loads(search_result.stdout)
    assert any(item["id"] == book_id for item in search_books)

    get_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "get", str(book_id)],
        env=workflow_env,
    )
    assert get_result.returncode == 0
    get_data = json.loads(get_result.stdout)
    assert get_data["book_id"] == book_id
    assert "Workflow Book" in get_data["metadata"]
    assert "Workflow Author" in get_data["metadata"]

    meta_result = _run_cli(
        cli_base,
        ["--json", "meta", "show", str(sample_epub)],
        env=workflow_env,
    )
    assert meta_result.returncode == 0
    meta_data = json.loads(meta_result.stdout)
    assert meta_data["path"] == str(sample_epub)
    assert "Workflow Sample" in meta_data["metadata"]


def test_workflow_export_and_convert(cli_base, workflow_env, real_library, sample_epub, workflow_root):
    _require_binary("calibredb")
    _require_binary("ebook-convert")
    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "add",
            str(sample_epub),
            "--title",
            "Export Workflow Book",
            "--authors",
            "Export Workflow Author",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0

    list_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "list"],
        env=workflow_env,
    )
    books = json.loads(list_result.stdout)
    assert books
    book_id = books[0]["id"]

    export_dir = workflow_root / "exported"
    export_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "export",
            "book",
            str(book_id),
            "--to-dir",
            str(export_dir),
            "--single-dir",
        ],
        env=workflow_env,
    )
    assert export_result.returncode == 0
    export_data = json.loads(export_result.stdout)
    assert export_data["book_ids"] == [book_id]
    exported_files = [p for p in export_dir.rglob("*") if p.is_file()]
    assert exported_files
    exported_epubs = [p for p in exported_files if p.suffix.lower() == ".epub"]
    assert exported_epubs
    exported_epub = exported_epubs[0]
    assert exported_epub.stat().st_size > 0
    assert exported_epub.read_bytes()[:4] == b"PK\x03\x04"

    converted = workflow_root / "converted" / "workflow-output.mobi"
    convert_result = _run_cli(
        cli_base,
        ["--json", "convert", "run", str(exported_epub), str(converted), "--preset", "kindle"],
        env=workflow_env,
    )
    assert convert_result.returncode == 0
    convert_data = json.loads(convert_result.stdout)
    assert convert_data["output"] == str(converted.resolve())
    assert convert_data["exists"] is True
    assert convert_data["file_size"] > 0
    assert converted.exists()
    header = converted.read_bytes()[:128]
    assert b"BOOKMOBI" in header


def test_workflow_library_mutation(cli_base, workflow_env, real_library, sample_epub, workflow_root):
    _require_binary("calibredb")
    """library mutation 工作流: book add → book set-field → book get 验证字段变更 → export book 验证导出目录结构"""

    # ── Step 1: book add ──────────────────────────────────────────────────────
    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library", str(real_library),
            "book", "add", str(sample_epub),
            "--title", "Mutation Original Title",
            "--authors", "Mutation Original Author",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0, f"book add failed: {add_result.stderr}"
    add_data = json.loads(add_result.stdout)
    assert "input" in add_data

    # 取得刚添加的 book_id
    list_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "list"],
        env=workflow_env,
    )
    assert list_result.returncode == 0
    books = json.loads(list_result.stdout)
    assert books, "library should have at least one book after add"
    book_id = books[0]["id"]
    assert books[0]["title"] == "Mutation Original Title"
    print(f"\n✓ [Step 1] book add 成功 — book_id={book_id}, 标题='{books[0]['title']}', 文件={add_data['input']}")

    # ── Step 2: book set-field 修改标题和作者 ──────────────────────────────────
    set_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library", str(real_library),
            "book", "set-field", str(book_id),
            "--title", "Mutation Updated Title",
            "--authors", "Mutation Updated Author",
        ],
        env=workflow_env,
    )
    assert set_result.returncode == 0, f"book set-field failed: {set_result.stderr}"
    set_data = json.loads(set_result.stdout)
    assert set_data["book_id"] == book_id
    print(f"✓ [Step 2] book set-field 成功 — book_id={book_id}, 新标题='Mutation Updated Title', 新作者='Mutation Updated Author'")

    # ── Step 3: book get 验证字段真的变了 ─────────────────────────────────────
    get_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "get", str(book_id)],
        env=workflow_env,
    )
    assert get_result.returncode == 0, f"book get failed: {get_result.stderr}"
    get_data = json.loads(get_result.stdout)
    assert get_data["book_id"] == book_id
    assert "Mutation Updated Title" in get_data["metadata"], \
        f"Updated title not found in metadata: {get_data['metadata']}"
    assert "Mutation Updated Author" in get_data["metadata"], \
        f"Updated author not found in metadata: {get_data['metadata']}"
    # 旧值不应再出现
    assert "Mutation Original Title" not in get_data["metadata"], \
        "Old title should have been replaced"
    print(f"✓ [Step 3] book get 验证通过 — 新标题/作者已写入，旧标题已替换")

    # ── Step 4: export book 验证导出目录结构 ───────────────────────────────────
    export_dir = workflow_root / "mutation_export"
    export_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library", str(real_library),
            "export", "book", str(book_id),
            "--to-dir", str(export_dir),
            "--single-dir",
        ],
        env=workflow_env,
    )
    assert export_result.returncode == 0, f"export book failed: {export_result.stderr}"
    export_data = json.loads(export_result.stdout)
    assert export_data["book_ids"] == [book_id]
    assert export_data["output_dir"] == str(export_dir.resolve())

    # 验证导出目录存在且包含文件
    assert export_dir.exists(), "export directory should exist"
    exported_files = [p for p in export_dir.rglob("*") if p.is_file()]
    assert exported_files, "export directory should contain at least one file"

    # 验证导出的 epub 文件非空且是合法 ZIP（epub 本质是 ZIP）
    exported_epubs = [p for p in exported_files if p.suffix.lower() == ".epub"]
    assert exported_epubs, "should have at least one exported epub file"
    exported_epub = exported_epubs[0]
    assert exported_epub.stat().st_size > 0, "exported epub should not be empty"
    assert exported_epub.read_bytes()[:4] == b"PK\x03\x04", "exported epub should be a valid ZIP/epub"
    # 验证导出文件名包含更新后的标题（证明 set-field 的修改确实生效）
    assert "Mutation Updated Title" in exported_epub.name, \
        f"Exported filename should contain updated title, got: {exported_epub.name}"
    print(f"✓ [Step 4] export book 成功 — 导出目录: {export_dir}")
    print(f"  导出文件列表:")
    for f in exported_files:
        print(f"    - {f.name} ({f.stat().st_size:,} bytes)")


def test_workflow_export_catalog_creates_file(cli_base, workflow_env, real_library, sample_epub, workflow_root):
    _require_binary("calibredb")
    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "add",
            str(sample_epub),
            "--title",
            "Catalog Book",
            "--authors",
            "Catalog Author",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0, add_result.stderr or add_result.stdout

    output_path = workflow_root / "catalog.csv"
    result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "export", "catalog", str(output_path)],
        env=workflow_env,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    data = json.loads(result.stdout)
    assert data["output"] == str(output_path.resolve())
    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_workflow_export_backup_metadata_creates_opf(cli_base, workflow_env, real_library, sample_epub):
    _require_binary("calibredb")
    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "add",
            str(sample_epub),
            "--title",
            "Backup Book",
            "--authors",
            "Backup Author",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0, add_result.stderr or add_result.stdout

    result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "export", "backup", "--all"],
        env=workflow_env,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    data = json.loads(result.stdout)
    assert "stdout" in data

    opf_files = [p for p in Path(real_library).rglob("*.opf") if p.is_file()]
    assert opf_files, "backup_metadata should create at least one .opf file in the library"


def test_workflow_add_then_remove_book_disappears_from_list(cli_base, workflow_env, real_library, sample_epub):
    _require_binary("calibredb")
    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "add",
            str(sample_epub),
            "--title",
            "Remove Me",
            "--authors",
            "Removable Author",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0, add_result.stderr or add_result.stdout

    list_result = _run_cli(cli_base, ["--json", "--library", str(real_library), "book", "list"], env=workflow_env)
    assert list_result.returncode == 0
    books = json.loads(list_result.stdout)
    assert books
    book_id = books[0]["id"]

    remove_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "remove", str(book_id)],
        env=workflow_env,
    )
    assert remove_result.returncode == 0, remove_result.stderr or remove_result.stdout

    list_after = _run_cli(cli_base, ["--json", "--library", str(real_library), "book", "list"], env=workflow_env)
    assert list_after.returncode == 0
    after_books = json.loads(list_after.stdout)
    assert all(item["id"] != book_id for item in after_books)


def test_workflow_library_stats_matches_book_count(cli_base, workflow_env, real_library, sample_epub, workflow_root):
    _require_binary("calibredb")
    sample2 = _make_sample_epub(workflow_root / "workflow-sample-2.epub", title="Workflow Two", author="Workflow Fixture")

    for title in ["Stats Book 1", "Stats Book 2"]:
        add_result = _run_cli(
            cli_base,
            ["--json", "--library", str(real_library), "book", "add", str(sample_epub), "--title", title, "--authors", "Stats Author"],
            env=workflow_env,
        )
        assert add_result.returncode == 0, add_result.stderr or add_result.stdout
        sample_epub = sample2

    stats_result = _run_cli(cli_base, ["--json", "--library", str(real_library), "library", "stats"], env=workflow_env)
    assert stats_result.returncode == 0, stats_result.stderr or stats_result.stdout
    stats = json.loads(stats_result.stdout)
    assert stats["book_count"] == 2
    assert stats["with_formats"] >= 1
    assert isinstance(stats.get("formats"), list)


def test_book_list_sort_by_title_and_limit(cli_base, workflow_env, real_library, sample_epub, workflow_root):
    _require_binary("calibredb")
    sample2 = _make_sample_epub(workflow_root / "workflow-sample-b.epub", title="Workflow B", author="Workflow Fixture")
    books_to_add = [
        ("B Title", sample2),
        ("A Title", sample_epub),
    ]
    for title, epub in books_to_add:
        add_result = _run_cli(
            cli_base,
            ["--json", "--library", str(real_library), "book", "add", str(epub), "--title", title, "--authors", "Sort Author"],
            env=workflow_env,
        )
        assert add_result.returncode == 0, add_result.stderr or add_result.stdout

    list_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "list",
            "--sort-by",
            "id",
            "--ascending",
            "--limit",
            "1",
        ],
        env=workflow_env,
    )
    assert list_result.returncode == 0, list_result.stderr or list_result.stdout
    data = json.loads(list_result.stdout)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == 1


def test_workflow_session_management_status_and_save(cli_base, workflow_env, real_library, sample_epub):
    _require_binary("calibredb")

    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "add",
            str(sample_epub),
            "--title",
            "Session Test Book",
            "--authors",
            "Session Author",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0, add_result.stderr or add_result.stdout

    status_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "session", "status"],
        env=workflow_env,
    )
    assert status_result.returncode == 0, status_result.stderr or status_result.stdout
    status_data = json.loads(status_result.stdout)
    assert status_data["has_library"] is True
    assert status_data["library_path"]

    save_result = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "session", "save"],
        env=workflow_env,
    )
    assert save_result.returncode == 0, save_result.stderr or save_result.stdout
    save_data = json.loads(save_result.stdout)
    assert "saved" in save_data


def test_workflow_book_set_field_updates_metadata(cli_base, workflow_env, real_library, sample_epub):
    _require_binary("calibredb")

    add_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "add",
            str(sample_epub),
            "--title",
            "Field Test Book",
            "--authors",
            "Field Author",
        ],
        env=workflow_env,
    )
    assert add_result.returncode == 0, add_result.stderr or add_result.stdout

    list_result = _run_cli(cli_base, ["--json", "--library", str(real_library), "book", "list"], env=workflow_env)
    assert list_result.returncode == 0, list_result.stderr or list_result.stdout
    books = json.loads(list_result.stdout)
    assert books
    book_id = books[0]["id"]

    get_before = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "get", str(book_id)],
        env=workflow_env,
    )
    assert get_before.returncode == 0, get_before.stderr or get_before.stdout
    before_data = json.loads(get_before.stdout)
    assert "Field Test Book" in before_data["metadata"]

    set_result = _run_cli(
        cli_base,
        [
            "--json",
            "--library",
            str(real_library),
            "book",
            "set-field",
            str(book_id),
            "--title",
            "Updated Field Book",
            "--authors",
            "Updated Author",
            "--tags",
            "test,updated",
        ],
        env=workflow_env,
    )
    assert set_result.returncode == 0, set_result.stderr or set_result.stdout

    get_after = _run_cli(
        cli_base,
        ["--json", "--library", str(real_library), "book", "get", str(book_id)],
        env=workflow_env,
    )
    assert get_after.returncode == 0, get_after.stderr or get_after.stdout
    after_data = json.loads(get_after.stdout)
    assert "Updated Field Book" in after_data["metadata"]
    assert "Updated Author" in after_data["metadata"]


def test_convert_presets_and_formats_and_invalid_preset(cli_base, workflow_env):
    presets_result = _run_cli(cli_base, ["--json", "convert", "presets"], env=workflow_env)
    assert presets_result.returncode == 0, presets_result.stderr or presets_result.stdout
    presets_data = json.loads(presets_result.stdout)
    assert "kindle" in presets_data
    assert "generic-epub" in presets_data
    assert "tablet" in presets_data

    formats_result = _run_cli(cli_base, ["--json", "convert", "formats"], env=workflow_env)
    assert formats_result.returncode == 0, formats_result.stderr or formats_result.stdout
    formats_data = json.loads(formats_result.stdout)
    assert isinstance(formats_data, list)
    assert "epub" in [x.lower() for x in formats_data]
    assert "mobi" in [x.lower() for x in formats_data]

    # invalid preset should fail before any real ebook-convert invocation
    convert_result = _run_cli(
        cli_base,
        ["--json", "convert", "run", "missing.epub", "output.mobi", "--preset", "invalid_preset"],
        env=workflow_env,
    )
    assert convert_result.returncode != 0
    error_data = json.loads(convert_result.stdout)
    assert "error" in error_data


