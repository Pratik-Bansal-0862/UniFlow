from io import BytesIO

import pytest
from docx import Document
from pypdf import PdfWriter

from app.services.document_chunking_service import chunk_text
from app.services.document_extraction_service import extract_text

def test_chunking_preserves_text_and_overlap():
    text = "A" * 1800

    chunks = chunk_text(
        text,
        chunk_size=1000,
        overlap=150,
    )

    assert len(chunks) == 2
    assert chunks[0][-150:] == chunks[1][:150]
    assert "".join([]) == ""
    assert len(chunks[0]) == 1000


def test_empty_text_returns_no_chunks():
    assert chunk_text("   ") == []


def test_invalid_chunk_settings_are_rejected():
    with pytest.raises(ValueError):
        chunk_text("example", chunk_size=100, overlap=100)


def test_unsupported_file_type_is_rejected():
    with pytest.raises(ValueError):
        extract_text("notes.txt", b"Hello world")


def test_extract_text_rejects_unsupported_file_type():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("notes.txt", b"Some text")


def test_extract_text_rejects_empty_docx():
    buffer = BytesIO()
    document = Document()
    document.add_paragraph("   ")
    document.save(buffer)

    with pytest.raises(ValueError, match="No readable text"):
        extract_text("notes.docx", buffer.getvalue())


def test_extract_text_rejects_empty_pdf():
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)

    with pytest.raises(ValueError, match="No readable text"):
        extract_text("empty.pdf", buffer.getvalue())


def test_extract_text_reads_docx_paragraphs():
    buffer = BytesIO()
    document = Document()
    document.add_paragraph("UniFlow study notes")
    document.add_paragraph("Document ingestion test")
    document.save(buffer)

    result = extract_text("notes.docx", buffer.getvalue())

    assert "UniFlow study notes" in result
    assert "Document ingestion test" in result

