"""Run with: python -B -m unittest discover -s tests -p 'test_word_diff.py'."""

import unittest

from ui.diff import render_word_diff


class WordDiffMarkupTests(unittest.TestCase):
    """The diff is rendered with unsafe_allow_html=True, so it must be escaped."""

    def test_unchanged_text_has_no_highlight_spans(self):
        markup = render_word_diff("Built internal tools", "Built internal tools")
        self.assertNotIn("<span", markup)

    def test_additions_are_wrapped_in_the_green_style(self):
        markup = render_word_diff("Worked on React", "Shipped accessible React")
        self.assertIn("background:#d7f5d7", markup)
        self.assertIn("Shipped accessible", markup)

    def test_removals_are_wrapped_in_the_red_struck_style(self):
        markup = render_word_diff("Worked on React", "Shipped accessible React")
        self.assertIn("#ffd7d7", markup)
        self.assertIn("line-through", markup)
        self.assertIn("Worked on", markup)

    def test_pure_insertion_has_no_removal_span(self):
        markup = render_word_diff("React", "React and TypeScript")
        self.assertIn("background:#d7f5d7", markup)
        self.assertNotIn("#ffd7d7", markup)

    def test_pure_deletion_has_no_addition_span(self):
        markup = render_word_diff("React and TypeScript", "React")
        self.assertIn("#ffd7d7", markup)
        self.assertNotIn("background:#d7f5d7", markup)

    def test_model_output_cannot_inject_html(self):
        hostile = '<img src=x onerror="alert(1)"> <script>alert(2)</script>'
        markup = render_word_diff(hostile, hostile + " improved")
        # Angle brackets must be escaped, so nothing becomes a real tag/attribute.
        self.assertNotIn("<script>", markup)
        self.assertNotIn("<img", markup)
        self.assertIn("&lt;script&gt;", markup)
        self.assertIn("&lt;img", markup)
        # The only real tags in the output are the diff spans we add ourselves.
        self.assertEqual(markup.count("<span"), markup.count("</span>"))
        self.assertEqual(markup.count("<span"), 1)

    def test_hostile_text_inside_a_change_span_is_still_escaped(self):
        markup = render_word_diff("safe words", '<script>alert(1)</script>')
        self.assertIn("&lt;script&gt;", markup)
        self.assertNotIn("<script>", markup)

    def test_ampersands_and_quotes_are_escaped(self):
        markup = render_word_diff('a & b "c"', 'a & b "c" <d>')
        self.assertNotIn("<d>", markup)
        self.assertIn("&amp;", markup)
        self.assertIn("&quot;", markup)

    def test_empty_inputs_do_not_raise(self):
        self.assertEqual(render_word_diff("", ""), "")
        self.assertEqual(render_word_diff("", "new words"), render_word_diff("", "new words"))
        self.assertIn("new words", render_word_diff("", "new words"))

    def test_output_is_a_single_line_of_markup(self):
        markup = render_word_diff("one two three", "one 2 three four")
        self.assertNotIn("\n", markup)


if __name__ == "__main__":
    unittest.main()
