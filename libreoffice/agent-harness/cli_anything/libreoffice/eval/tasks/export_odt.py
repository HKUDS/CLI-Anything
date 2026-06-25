"""Eval task: native ODT export (no LibreOffice binary required)."""

from cli_anything.libreoffice.core.document import create_document
from cli_anything.libreoffice.core.writer import add_paragraph
from cli_anything.libreoffice.core.export import export

TASK = {
    "id": "export_odt",
    "name": "ODT export",
    "description": "Create a Writer document with one paragraph and export to ODT",
    "prompt": "Create a Writer document containing 'Hello, World!' and save it as ODT.",
}


def run(ctx):
    doc = create_document(doc_type="writer", name="eval")
    add_paragraph(doc, text="Hello, World!")
    out = ctx.task_artifact_path("out.odt")
    result = export(doc, str(out), preset="odt", overwrite=True)
    return {"metrics": {"file_size": result.get("file_size")}, "artifacts": [str(out)]}


def verify(ctx):
    out = ctx.task_artifact_path("out.odt")
    size = out.stat().st_size if out.exists() else 0
    return {"ok": out.exists() and size > 0, "metrics": {"file_size": size}}
