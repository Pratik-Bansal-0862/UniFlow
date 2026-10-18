
from io import BytesIO

from docx import Document
from pypdf import PdfReader


def extract_text(
    filename: str,
    content: bytes,
) -> str:
    """Extract text from a supported PDF or DOCX file."""
    normalized_name = filename.lower()

    if normalized_name.endswith(".pdf"):
        reader = PdfReader(BytesIO(content))

        if reader.is_encrypted:
            raise ValueError(
                "Encrypted PDFs are not supported yet."
            )

        pages = [
            page.extract_text() or ""
            for page in reader.pages
        ]
        text = "\n".join(pages)

    elif normalized_name.endswith(".docx"):
        document = Document(BytesIO(content))
        text = "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

    else:
        raise ValueError(
            "Unsupported file type. Use PDF or DOCX."
        )

    if not text.strip():
        raise ValueError(
            "No readable text found in the document."
        )

    return text.strip()
