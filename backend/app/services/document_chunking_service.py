from __future__ import annotations
import re

_HEADING_PATTERNS = (
    re.compile(r"^[A-Z][A-Z0-9 &/,()'â€™:+\-]{1,70}$"),
    re.compile(r"^(?:education|experience|work experience|professional experience|internships?|projects?|technical skills|skills|certifications?|achievements?|publications?|coursework|summary|profile|responsibilities|research|awards|languages|volunteering|extracurricular activities|leadership|contact|objective)\s*:?\s*$", re.IGNORECASE),
    re.compile(r"^\d+(?:\.\d+)*[.)]?\s+[A-Z].{1,70}$"),
)

def _is_heading(line: str) -> bool:
    candidate = line.strip().strip("â€¢*- \t")
    if not candidate or len(candidate) > 90:
        return False
    if any(pattern.match(candidate) for pattern in _HEADING_PATTERNS):
        return True
    words = candidate.split()
    return (1 <= len(words) <= 5 and len(candidate) <= 48
            and not candidate.endswith((".", ",", ";"))
            and candidate == candidate.title()
            and not re.search(r"\b(?:is|are|was|were|using|with|from|into|that|which)\b", candidate, re.IGNORECASE))

def _split_long_section(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start, length = 0, len(text)
    while start < length:
        hard_end = min(start + chunk_size, length)
        end = hard_end
        if hard_end < length:
            floor = start + max(1, int(chunk_size * 0.55))
            # Prefer natural boundaries only when they do not materially shrink a chunk.
            candidates = [
                (text.rfind("\n\n", floor, hard_end), 2),
                (text.rfind("\n", floor, hard_end), 1),
                (text.rfind(". ", floor, hard_end), 2),
                (text.rfind("; ", floor, hard_end), 2),
                (text.rfind(" ", floor, hard_end), 1),
            ]
            boundary, width = max(candidates, key=lambda item: item[0])
            if boundary >= floor:
                end = boundary + width
        part = text[start:end].strip()
        if part:
            chunks.append(part)
        if end >= length:
            break
        next_start = max(start + 1, end - overlap)
        # Preserve exact overlap for fixed-width text; align only when a nearby word boundary exists.
        if not text.strip() or len(text) > chunk_size:
            nearby = [p for p in (text.find(" ", next_start, min(next_start + 12, length)),
                                   text.find("\n", next_start, min(next_start + 12, length))) if p >= 0]
            if nearby and min(nearby) - next_start <= 3:
                next_start = min(nearby) + 1
        start = next_start
    return chunks

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")
    cleaned = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        return []
    sections: list[tuple[str, str]] = []
    heading, body, saw_heading = "Document", [], False
    def flush():
        content = "\n".join(body).strip()
        if content:
            sections.append((heading, content))
        body.clear()
    for line in cleaned.splitlines():
        if _is_heading(line.strip()) and (body or not sections):
            flush()
            heading = line.strip().strip("â€¢*- \t").rstrip(":")
            saw_heading = True
        else:
            body.append(line)
    flush()
    if not saw_heading:
        sections = [("Document", cleaned)]
    output: list[str] = []
    for section_name, section_text in sections:
        if not section_text:
            continue
        prefix = f"Section: {section_name}\n"
        # Preserve requested chunk_size for ordinary prose. Section labels are added only to headed documents.
        budget = max(120, chunk_size - len(prefix)) if section_name != "Document" else chunk_size
        for part in _split_long_section(section_text, budget, overlap):
            chunk = prefix + part if section_name != "Document" else part
            if chunk.strip():
                output.append(chunk.strip())
    return output
