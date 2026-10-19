
from __future__ import annotations

import csv
import io
import logging
import zipfile
from pathlib import PurePosixPath

from docx import Document as WordDocument
from openpyxl import load_workbook
from pptx import Presentation
from pypdf import PdfReader

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
}

MAX_EXTRACTED_CHARACTERS = 5_000_000


def extract_text(filename: str, content: bytes) -> str:
    """Extract text from supported student documents.

    OCR for image-only PDF pages is intentionally handled as a
    separate fallback; pypdf itself does not perform OCR.
    """
    if not content:
        raise ValueError("Uploaded file is empty.")

    extension = PurePosixPath(filename.replace("\\", "/")).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Supported formats: "
            "PDF, DOCX, TXT, MD, CSV, XLSX, and PPTX."
        )

    _validate_container(extension, content)

    try:
        if extension == ".pdf":
            text = _extract_pdf(content)
        elif extension == ".docx":
            text = _extract_docx(content)
        elif extension in {".txt", ".md"}:
            text = _extract_plain_text(content)
        elif extension == ".csv":
            text = _extract_csv(content)
        elif extension == ".xlsx":
            text = _extract_xlsx(content)
        else:
            text = _extract_pptx(content)
    except ValueError:
        raise
    except Exception as exc:
        logger.warning(
            "Document extraction failed for extension %s (%s)",
            extension,
            type(exc).__name__,
        )
        raise ValueError(
            f"Could not read this {extension} file. "
            "It may be damaged, encrypted, or malformed."
        ) from exc

    text = text.strip()

    if not text:
        if extension == ".pdf":
            raise ValueError(
                "No readable text found in the document. The PDF may be "
                "scanned or image-only; OCR support is required for this file."
            )
        raise ValueError("No readable text found in the document.")

    if len(text) > MAX_EXTRACTED_CHARACTERS:
        raise ValueError(
            "Extracted text exceeds the 5-million-character processing limit."
        )

    return text


def _validate_container(extension: str, content: bytes) -> None:
    """Reject obvious format mismatches before parsing."""
    if extension == ".pdf":
        if not content.lstrip().startswith(b"%PDF-"):
            raise ValueError("File contents do not appear to be a valid PDF.")
    elif extension in {".docx", ".xlsx", ".pptx"}:
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise ValueError(
                f"File contents do not appear to be a valid {extension} archive."
            )


def _extract_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content), strict=True)

    if reader.is_encrypted:
        raise ValueError(
            "Encrypted PDFs are not supported. Upload an unlocked PDF."
        )

    if len(reader.pages) > 1000:
        raise ValueError("PDF exceeds the 1000-page processing limit.")

    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")

    return "\n\n".join(pages)


def _extract_docx(content: bytes) -> str:
    document = WordDocument(io.BytesIO(content))
    parts: list[str] = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text)

    for table_number, table in enumerate(document.tables, start=1):
        parts.append(f"Table {table_number}:")
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))

    return "\n".join(parts)


def _extract_plain_text(content: bytes) -> str:
    # Try common encodings in a defined order. Never silently discard
    # undecodable bytes because that can corrupt names or study notes.
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            decoded = content.decode(encoding)
            if "\x00" not in decoded:
                return decoded
        except UnicodeDecodeError:
            continue

    raise ValueError(
        "Text file encoding is unsupported or the file contains binary data."
    )


def _extract_csv(content: bytes) -> str:
    decoded = _extract_plain_text(content)
    sample = decoded[:8192]

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel

    rows = csv.reader(io.StringIO(decoded), dialect)
    return "\n".join(" | ".join(cell for cell in row) for row in rows)


def _extract_xlsx(content: bytes) -> str:
    workbook = load_workbook(
        io.BytesIO(content),
        read_only=True,
        data_only=True,
    )
    parts: list[str] = []

    try:
        for sheet in workbook.worksheets:
            parts.append(f"Worksheet: {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                if any(value.strip() for value in values):
                    parts.append(" | ".join(values))
    finally:
        workbook.close()

    return "\n".join(parts)


def _extract_pptx(content: bytes) -> str:
    presentation = Presentation(io.BytesIO(content))
    parts: list[str] = []

    if len(presentation.slides) > 1000:
        raise ValueError("Presentation exceeds the 1000-slide processing limit.")

    for slide_number, slide in enumerate(presentation.slides, start=1):
        parts.append(f"Slide {slide_number}")

        for shape in slide.shapes:
            if shape.has_text_frame and shape.text.strip():
                parts.append(shape.text)

            if shape.has_table:
                for row in shape.table.rows:
                    parts.append(
                        " | ".join(cell.text.strip() for cell in row.cells)
                    )

    return "\n".join(parts)
