"""Eval task: PDF export via headless LibreOffice (skipped if absent)."""

from cli_anything.libreoffice.core.document import create_document
from cli_anything.libreoffice.core.writer import add_paragraph
from cli_anything.libreoffice.core.export import export

TASK = {
    "id": "export_pdf",
    "name": "PDF export",
    "description": "Export a Writer document to PDF using headless LibreOffice",
    "prompt": "Create a Writer document and export it to PDF.",
}


def precheck(ctx):
    from cli_anything.libreoffice.utils.lo_backend import find_libreoffice
    try:
        find_libreoffice()
    except RuntimeError as exc:
        return f"LibreOffice not available: {exc}"
    return None


def run(ctx):
    doc = create_document(doc_type="writer", name="eval")
    add_paragraph(doc, text="Hello, PDF!")
    out = ctx.task_artifact_path("out.pdf")
    result = export(doc, str(out), preset="pdf", overwrite=True)
    return {"metrics": {"file_size": result.get("file_size")}, "artifacts": [str(out)]}


def verify(ctx):
    out = ctx.task_artifact_path("out.pdf")
    ok = out.exists() and out.read_bytes()[:5] == b"%PDF-"
    return {"ok": ok, "metrics": {"file_size": out.stat().st_size if out.exists() else 0}}
