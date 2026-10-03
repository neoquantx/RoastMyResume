"""
test_resume_parser.py
Unit tests for the resume section extractor.
All tests run without any file I/O — section extraction is pure-text logic.
"""

import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import docx

from core import resume_parser
from core.resume_parser import extract_sections, extract_text_from_docx, parse_resume


class ExtractSectionsTests(unittest.TestCase):
    def test_basic_sections_detected(self):
        text = (
            "John Doe | john@email.com\n"
            "Experience\n"
            "Software Engineer at Acme Corp\n"
            "Built internal tools\n\n"
            "Skills\n"
            "Python, SQL, Docker\n\n"
            "Education\n"
            "B.Tech CSE, 2024"
        )
        sections = extract_sections(text)
        self.assertIn("experience", sections)
        self.assertIn("skills", sections)
        self.assertIn("education", sections)

    def test_section_content_is_captured(self):
        text = "Skills\nPython, JavaScript, React"
        sections = extract_sections(text)
        self.assertIn("skills", sections)
        self.assertIn("Python", sections["skills"])

    def test_header_section_captures_preamble(self):
        """Lines before any known header go into the 'header' section."""
        text = "Alice Smith\nalice@example.com\n+91 9876543210\nExperience\nSomething"
        sections = extract_sections(text)
        self.assertIn("header", sections)
        self.assertIn("Alice Smith", sections["header"])

    def test_case_insensitive_section_detection(self):
        """Headers like 'SKILLS' or 'EDUCATION' should still be detected."""
        text = "SKILLS\nPython\nEDUCATION\nIIT Delhi"
        sections = extract_sections(text)
        keys = list(sections.keys())
        self.assertTrue(any("skill" in k for k in keys), f"skills not found in {keys}")
        self.assertTrue(any("education" in k for k in keys), f"education not found in {keys}")

    def test_section_with_colon_detected(self):
        text = "Skills:\nPython, Django"
        sections = extract_sections(text)
        keys = list(sections.keys())
        self.assertTrue(any("skill" in k for k in keys), f"'Skills:' not detected, got {keys}")

    def test_empty_text_returns_empty_or_header_only(self):
        sections = extract_sections("")
        for v in sections.values():
            self.assertEqual(v.strip(), "")

    def test_long_line_with_header_keyword_is_not_a_header(self):
        """A long line that happens to contain a header keyword must NOT split sections."""
        text = (
            "Experience\n"
            "I have experience with many technologies including Python and Java and much more stuff here"
        )
        sections = extract_sections(text)
        if "experience" in sections:
            self.assertIn("Python", sections["experience"])

    def test_multiple_sections_dont_bleed_into_each_other(self):
        text = "Experience\nBuilt X at Y\nSkills\nPython, Go\nEducation\nB.Tech"
        sections = extract_sections(text)
        if "experience" in sections:
            self.assertNotIn("Python", sections["experience"])
        if "skills" in sections:
            self.assertNotIn("B.Tech", sections["skills"])

    def test_projects_section_detected(self):
        text = "Projects\nBuilt a resume analyzer using Llama 3.2"
        sections = extract_sections(text)
        keys = list(sections.keys())
        self.assertTrue(any("project" in k for k in keys), f"projects not found in {keys}")

    def test_summary_section_detected(self):
        text = "Summary\nPassionate developer with 2 years of experience."
        sections = extract_sections(text)
        keys = list(sections.keys())
        self.assertTrue(any("summary" in k for k in keys), f"summary not found in {keys}")


class FakeUpload(io.BytesIO):
    """Minimal stand-in for a Streamlit UploadedFile."""

    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


class DocxTableExtractionTests(unittest.TestCase):
    """Two-column / grid layouts are common in resumes and must not be dropped."""

    @staticmethod
    def _build_docx(paragraphs, tables):
        """``tables`` is a list of tables, each a list of rows of cell strings."""
        document = docx.Document()
        for text in paragraphs:
            document.add_paragraph(text)
        for rows in tables:
            table = document.add_table(rows=len(rows), cols=len(rows[0]))
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    table.cell(r, c).text = value
        return document

    def _extract(self, paragraphs, tables):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "resume.docx"
            self._build_docx(paragraphs, tables).save(path)
            return extract_text_from_docx(str(path))

    def test_two_column_table_content_is_extracted(self):
        text = self._extract(
            ["Jane Doe", "Experience"],
            [[["Acme Corp", "Senior Engineer"], ["Led migration", "SKILLS Python Docker"]]],
        )
        self.assertIn("Acme Corp", text)
        self.assertIn("Senior Engineer", text)
        self.assertIn("SKILLS Python Docker", text)

    def test_multiple_tables_are_all_extracted(self):
        text = self._extract(
            ["Resume"],
            [[["One", "Two"]], [["Three", "Four"]]],
        )
        for expected in ("One", "Two", "Three", "Four"):
            self.assertIn(expected, text)

    def test_paragraph_content_survives_alongside_tables(self):
        text = self._extract(["Jane Doe"], [[["Cell A", "Cell B"]]])
        self.assertIn("Jane Doe", text)
        self.assertIn("Cell A", text)

    def test_repeated_content_in_different_places_is_kept(self):
        """De-duplication must not silently drop real content."""
        text = self._extract(["Python"], [[["Python", "Docker"]]])
        self.assertEqual(text.count("Python"), 2)

    def test_merged_cell_is_emitted_once(self):
        """A merged cell is reported at every grid position it spans."""
        document = docx.Document()
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Merged Heading"
        table.cell(0, 0).merge(table.cell(0, 1))
        table.cell(1, 0).text = "Left"
        table.cell(1, 1).text = "Right"

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "merged.docx"
            document.save(path)
            text = extract_text_from_docx(str(path))

        self.assertEqual(text.count("Merged Heading"), 1)
        self.assertIn("Left", text)
        self.assertIn("Right", text)

    def test_blank_cells_are_skipped(self):
        text = self._extract(["Resume"], [[["Real", ""], ["", "AlsoReal"]]])
        self.assertIn("Real", text)
        self.assertIn("AlsoReal", text)
        self.assertNotIn("\n\n", text)

    def test_document_without_tables_is_unaffected(self):
        text = self._extract(["Jane Doe", "Experience", "Built things"], [])
        self.assertEqual(text.split("\n"), ["Jane Doe", "Experience", "Built things"])

    def test_two_column_resume_keeps_columns_under_their_own_heading(self):
        """A side-by-side grid must not file the left column under the right heading."""
        text = self._extract(
            ["Jane Doe"],
            [[["EXPERIENCE", "TECHNICAL SKILLS"],
              ["Senior Engineer, Acme", "Languages: Python, SQL"],
              ["Led a migration", "Cloud: AWS, Docker"]]],
        )
        self.assertEqual(
            text.split("\n"),
            ["Jane Doe", "EXPERIENCE", "Senior Engineer, Acme", "Led a migration",
             "TECHNICAL SKILLS", "Languages: Python, SQL", "Cloud: AWS, Docker"],
        )

    def test_two_column_layout_yields_a_real_experience_section(self):
        text = self._extract(
            ["Jane Doe"],
            [[["EXPERIENCE", "TECHNICAL SKILLS"],
              ["Senior Engineer, Acme", "Languages: Python, SQL"]]],
        )
        sections = extract_sections(text)
        self.assertIn("experience", sections)
        self.assertIn("Senior Engineer, Acme", sections["experience"])
        self.assertNotIn("Languages: Python", sections["experience"])

    def test_ordinary_two_column_table_is_read_row_by_row(self):
        """A key/value table is data, not a side-by-side layout."""
        text = self._extract(["Resume"], [[["Python", "5 years"], ["Java", "4 years"]]])
        self.assertEqual(text.split("\n"), ["Resume", "Python", "5 years", "Java", "4 years"])

    def test_nested_table_content_is_extracted(self):
        document = docx.Document()
        outer = document.add_table(rows=1, cols=1)
        inner = outer.cell(0, 0).add_table(rows=1, cols=1)
        inner.cell(0, 0).text = "Nested Skill"

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested.docx"
            document.save(path)
            text = extract_text_from_docx(str(path))

        self.assertIn("Nested Skill", text)

    def test_content_after_a_colon_in_a_heading_is_preserved(self):
        """"Languages: Python, SQL" must keep its values."""
        sections = extract_sections("SKILLS\nLanguages: Python, SQL")
        self.assertIn("Python, SQL", sections["languages"])


class ParseResumeTests(unittest.TestCase):
    def test_docx_upload_returns_sections_and_counts(self):
        document = docx.Document()
        document.add_paragraph("Jane Doe")
        document.add_paragraph("Experience")
        document.add_paragraph("Built internal tools")
        buffer = io.BytesIO()
        document.save(buffer)

        result = parse_resume(FakeUpload(buffer.getvalue(), "jane.docx"))

        self.assertEqual(result["file_name"], "jane.docx")
        self.assertIn("Jane Doe", result["raw_text"])
        self.assertIn("Built internal tools", result["raw_text"])
        self.assertTrue(result["word_count"] > 0)
        self.assertTrue(result["line_count"] > 0)
        self.assertIn("experience", result["sections"])

    def test_uppercase_extension_is_handled(self):
        document = docx.Document()
        document.add_paragraph("Upper Case Resume")
        buffer = io.BytesIO()
        document.save(buffer)

        result = parse_resume(FakeUpload(buffer.getvalue(), "JANE.DOCX"))
        self.assertIn("Upper Case Resume", result["raw_text"])

    def test_unsupported_extension_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_resume(FakeUpload(b"data", "resume.txt"))

    def test_temp_file_is_removed_even_on_failure(self):
        """The temp file must be cleaned up even when parsing raises."""
        created = {}
        real_named_temp_file = tempfile.NamedTemporaryFile

        def spy(*args, **kwargs):
            handle = real_named_temp_file(*args, **kwargs)
            created["path"] = handle.name
            return handle

        with mock.patch.object(resume_parser.tempfile, "NamedTemporaryFile", spy):
            with self.assertRaises(Exception):
                parse_resume(FakeUpload(b"not a real docx", "broken.docx"))

        self.assertIn("path", created, "temp file was never created")
        self.assertFalse(os.path.exists(created["path"]), "temp file leaked on failure")

    def test_temp_file_is_removed_on_success(self):
        created = {}
        real_named_temp_file = tempfile.NamedTemporaryFile

        def spy(*args, **kwargs):
            handle = real_named_temp_file(*args, **kwargs)
            created["path"] = handle.name
            return handle

        document = docx.Document()
        document.add_paragraph("Cleanup Check")
        buffer = io.BytesIO()
        document.save(buffer)

        with mock.patch.object(resume_parser.tempfile, "NamedTemporaryFile", spy):
            parse_resume(FakeUpload(buffer.getvalue(), "cleanup.docx"))

        self.assertFalse(os.path.exists(created["path"]), "temp file leaked on success")


if __name__ == "__main__":
    unittest.main()
