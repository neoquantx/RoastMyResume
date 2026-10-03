"""Run with: python -B -m unittest discover -s tests -p 'test_jd_scraper.py'."""

import unittest

from core.jd_scraper import (
    clean_text,
    normalize_block_text,
    parse_jd_text,
    _detect_role_title,
)


class RoleTitleDetectionTests(unittest.TestCase):
    """The detector must prefer a real job title over nav chrome and prose."""

    def assert_role(self, text, expected):
        self.assertEqual(parse_jd_text(text)["role_title"], expected)

    def test_title_on_first_line(self):
        self.assert_role(
            "Backend Engineer\nAcme Corp\nRequirements: 5 years Python.",
            "Backend Engineer",
        )

    def test_nav_breadcrumb_is_skipped(self):
        self.assert_role(
            "Home > Jobs > Search\nSenior Product Designer\nAbout the role\n"
            "You will design end to end systems.",
            "Senior Product Designer",
        )

    def test_company_name_before_title(self):
        self.assert_role(
            "Stripe\nStaff Software Engineer, Payments\nBuild financial infrastructure.",
            "Staff Software Engineer, Payments",
        )

    def test_backend_is_not_mistaken_for_navigation(self):
        """"back" must not make the detector discard "Backend Engineer"."""
        for title in ("Backend Engineer", "Backend Developer", "Back End Engineer"):
            with self.subTest(title=title):
                self.assert_role(f"{title}\nAcme Corp\nWe are hiring.", title)

    def test_feedback_line_is_not_mistaken_for_navigation(self):
        self.assert_role(
            "We welcome feedback from candidates.\nProduct Manager\nOwn the roadmap.",
            "Product Manager",
        )

    def test_short_keywords_match_whole_words_only(self):
        """"ai"/"ml"/"data" must not match inside Maintain, Available, etc."""
        self.assert_role(
            "Apply now\nData-driven decisions\nMachine Learning Engineer\nBuild models.",
            "Machine Learning Engineer",
        )
        self.assert_role(
            "About the role\nMaintain the Available services\nPlatform Engineer\nOwn the runtime.",
            "Platform Engineer",
        )

    def test_long_prose_line_loses_to_real_title(self):
        self.assert_role(
            "We are hiring a wonderful person to join our amazing team of distributed "
            "engineers across the globe.\nSite Reliability Engineer\nRun Kubernetes.",
            "Site Reliability Engineer",
        )

    def test_uppercase_title_is_preserved_verbatim(self):
        self.assert_role("BACKEND ENGINEER\nACME CORP\n5+ years Python", "BACKEND ENGINEER")

    def test_common_title_families(self):
        for title in (
            "Full Stack Engineer",
            "Data Scientist",
            "Frontend Developer",
            "DevOps Engineer",
            "Product Designer",
            "Business Analyst",
            "QA Engineer",
            "Solutions Architect",
            "Marketing Manager",
        ):
            with self.subTest(title=title):
                self.assert_role(f"{title}\nNimbus Labs\nReact, Node, Postgres.", title)

    def test_unrecognisable_input_falls_back_without_raising(self):
        self.assertEqual(parse_jd_text("")["role_title"], "Unknown Role")
        self.assertEqual(_detect_role_title([]), "Unknown Role")

    def test_navigation_only_input_has_no_role(self):
        self.assertEqual(
            parse_jd_text("Apply now\nSign in\nCookie policy")["role_title"],
            "Unknown Role",
        )

    def test_title_is_returned_verbatim_not_normalised(self):
        self.assertEqual(parse_jd_text("Sr. Software Engineer (Remote)")["role_title"],
                         "Sr. Software Engineer (Remote)")


class BlockTextTests(unittest.TestCase):
    """Scraped HTML must keep its line structure or no title can be detected."""

    def test_normalize_block_text_preserves_newlines(self):
        raw = "Backend Engineer\nAcme Corp\n\nAbout the role\n5+ years Python."
        out = normalize_block_text(raw)
        self.assertIn("\n", out)
        self.assertIn("Backend Engineer", out.split("\n")[0])

    def test_blank_line_runs_are_collapsed(self):
        self.assertEqual(normalize_block_text("A\n\n\n\n\nB"), "A\n\nB")

    def test_windows_line_endings_are_normalised(self):
        self.assertEqual(normalize_block_text("A\r\nB\rC"), "A\nB\nC")

    def test_horizontal_whitespace_is_squeezed(self):
        self.assertEqual(normalize_block_text("A  \t B"), "A B")

    def test_end_to_end_scrape_shape_yields_a_real_title(self):
        """The whole scrape path: block text in, sensible title out."""
        scraped = normalize_block_text(
            "Backend Engineer\nAcme Corp\n\nAbout the role\n"
            "We are hiring a backend engineer with 5+ years of Python and Postgres."
        )
        parsed = parse_jd_text(scraped)
        self.assertEqual(parsed["role_title"], "Backend Engineer")
        self.assertIn("5+ years", parsed["experience_required"])


class CleanTextTests(unittest.TestCase):
    def test_printable_unicode_survives(self):
        for text in ("We build — fast", "curly “quotes”", "bullets • here", "café ünïcode", "✓ done"):
            with self.subTest(text=text):
                self.assertEqual(clean_text(text), text)

    def test_control_characters_are_removed(self):
        self.assertEqual(clean_text("a\x00b\x07c\x7fd"), "abcd")

    def test_whitespace_is_collapsed_to_single_spaces(self):
        self.assertEqual(clean_text("a   b\n\n\tc"), "a b c")

    def test_normalize_block_text_keeps_printable_unicode(self):
        self.assertEqual(normalize_block_text("A — B\n• C"), "A — B\n• C")


class ParseJdTextTests(unittest.TestCase):
    def test_experience_is_first_match_and_length_bounded(self):
        parsed = parse_jd_text("Data Engineer\nNeeds 5+ years of SQL experience overall here.")
        self.assertIn("5+ years", parsed["experience_required"])
        self.assertLessEqual(len(parsed["experience_required"]), 200)

    def test_huge_flattened_line_cannot_become_experience_blob(self):
        parsed = parse_jd_text("Engineer\n" + ("We need 3 years experience. " * 200))
        self.assertLessEqual(len(parsed["experience_required"]), 200)

    def test_skills_collected_after_a_skills_header(self):
        parsed = parse_jd_text(
            "Data Analyst\nRequirements\nSQL and Python\nTableau experience"
        )
        self.assertIn("SQL and Python", parsed["required_skills"])

    def test_required_skills_are_capped_at_fifteen(self):
        body = "\n".join(f"Skill number {i}" for i in range(40))
        parsed = parse_jd_text(f"Engineer\nSkills\n{body}")
        self.assertLessEqual(len(parsed["required_skills"]), 15)

    def test_word_count_and_full_text_round_trip(self):
        text = "Data Engineer\nBuild pipelines"
        parsed = parse_jd_text(text)
        self.assertEqual(parsed["full_text"], text)
        self.assertEqual(parsed["word_count"], 4)

    def test_empty_input_returns_safe_defaults(self):
        parsed = parse_jd_text("")
        self.assertEqual(parsed["role_title"], "Unknown Role")
        self.assertEqual(parsed["required_skills"], [])
        self.assertEqual(parsed["experience_required"], "")


if __name__ == "__main__":
    unittest.main()
