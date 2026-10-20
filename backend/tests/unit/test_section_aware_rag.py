from app.services.document_chunking_service import chunk_text

def test_heading_aware_chunking_keeps_resume_sections():
    text = "EDUCATION\nB.Tech Computer Science, SRM University, 2023-2027.\n\nEXPERIENCE\nResearch Intern at DRDO from June 2026.\nBuilt a biometric authentication system.\n\nTECHNICAL SKILLS\nPython, FastAPI, PostgreSQL.\n"
    chunks = chunk_text(text, chunk_size=300, overlap=40)
    joined = "\n".join(chunks)
    assert "Section: EDUCATION" in joined
    assert "Section: EXPERIENCE" in joined
    assert "Section: TECHNICAL SKILLS" in joined
    assert "Research Intern at DRDO" in joined
    assert "Python, FastAPI, PostgreSQL" in joined

def test_chunking_plain_prose_does_not_require_headings():
    text = "Students may apply for financial aid. " * 80
    chunks = chunk_text(text, chunk_size=250, overlap=40)
    assert len(chunks) > 1
    assert all(chunks)

def test_chunking_empty_and_validation():
    assert chunk_text("") == []
    try:
        chunk_text("abc", chunk_size=100, overlap=100)
    except ValueError:
        pass
    else:
        raise AssertionError("overlap >= chunk_size must fail")
