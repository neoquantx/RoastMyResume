"""
resume_parser.py
Extracts clean text from PDF and DOCX resumes locally using PDFPlumber.
Zero data leaves the machine.
"""

import pdfplumber
import docx
import re
from pathlib import Path


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF resume using PDFPlumber (100% local)."""
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from DOCX resume."""
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs if para.text.strip()])


def parse_resume(uploaded_file) -> dict:
    """
    Parse uploaded resume file (PDF or DOCX).
    Returns a dict with raw_text and structured sections.
    """
    file_name = uploaded_file.name
    extension = Path(file_name).suffix.lower()

    # Save temp file
    import tempfile, os
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    try:
        if extension == ".pdf":
            raw_text = extract_text_from_pdf(tmp_path)
        elif extension in [".docx", ".doc"]:
            raw_text = extract_text_from_docx(tmp_path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")
    finally:
        os.unlink(tmp_path)

    sections = extract_sections(raw_text)
    word_count = len(raw_text.split())
    line_count = len([l for l in raw_text.split("\n") if l.strip()])

    return {
        "raw_text": raw_text,
        "sections": sections,
        "word_count": word_count,
        "line_count": line_count,
        "file_name": file_name,
    }


def extract_sections(text: str) -> dict:
    """
    Heuristically detect resume sections (Experience, Education, Skills, Projects, etc.)
    """
    section_headers = [
        "experience", "work experience", "employment", "internship",
        "education", "academic", "qualification",
        "skills", "technical skills", "core competencies",
        "projects", "personal projects", "academic projects",
        "certifications", "achievements", "awards",
        "summary", "objective", "profile", "about",
        "activities", "extracurricular", "volunteer",
        "contact", "languages", "publications"
    ]

    lines = text.split("\n")
    sections = {}
    current_section = "header"
    current_lines = []

    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()

        is_header = any(
            lower == h or lower.startswith(h + " ") or lower.startswith(h + ":")
            for h in section_headers
        )

        if is_header and len(stripped) < 50:
            if current_lines:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = stripped.lower().split(":")[0].strip()
            current_lines = []
        else:
            if stripped:
                current_lines.append(stripped)

    if current_lines:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections
