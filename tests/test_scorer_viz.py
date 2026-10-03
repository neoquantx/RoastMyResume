"""Run with: python -B -m unittest discover -s tests -p 'test_scorer_viz.py'."""

import copy
import json
import unittest

import plotly.graph_objects as go

from core import scorer_viz as viz


INVALID_SCORES = (
    None, "", "not a number", "75%", "NaN", "Infinity", float("nan"),
    float("inf"), float("-inf"), -1, 101, "-0.1", "100.1", True, False,
    [], {}, complex(2, 1), 10 ** 400,
)
SECTIONS = {
    "contact_header": {"score": 0, "risk": "critical"},
    "experience": {"score": 65.5, "risk": "medium"},
    "skills": {"score": 100, "risk": "low"},
}


class FigureAssertions(unittest.TestCase):
    def assert_styled(self, figure):
        self.assertIsInstance(figure, go.Figure)
        self.assertEqual(figure.layout.paper_bgcolor, "#FFFFFF")
        self.assertEqual(figure.layout.plot_bgcolor, "#F7F8F2")
        self.assertEqual(figure.layout.font.color, "#242A20")
        self.assertIn("SF Pro Display", figure.layout.font.family)
        self.assertIn("Avenir Next", figure.layout.font.family)
        self.assertTrue(figure.layout.autosize)
        self.assertIsNone(figure.layout.width)
        # Exercise Plotly serialization, including its property validators.
        payload = figure.to_json(validate=True)
        self.assertIsInstance(json.loads(payload), dict)
        self.assertNotIn("NaN", payload)
        self.assertNotIn("Infinity", payload)
        self.assertNotRegex(json.dumps(json.loads(payload), ensure_ascii=False),
                            "[\U0001F000-\U0001FAFF\u2600-\u27BF]")

    def assert_unavailable(self, figure):
        self.assert_styled(figure)
        self.assertEqual(len(figure.data), 0)
        self.assertIn("unavailable", " ".join(a.text for a in figure.layout.annotations))


class RejectionRiskGaugeTests(FigureAssertions):
    def test_valid_scores_and_thresholds(self):
        for value, risk in ((0, "low"), (29.9, "low"), (30, "medium"),
                            (59.9, "medium"), (60, "high"), (80, "critical"),
                            (100, "critical"), (" 42.5 ", "medium")):
            with self.subTest(value=value):
                figure = viz.build_rejection_risk_gauge(value)
                self.assert_styled(figure)
                indicator = figure.data[0]
                self.assertEqual(indicator.value, float(value))
                self.assertEqual(indicator.mode, "gauge+number")
                self.assertEqual(indicator.number.suffix, " /100")
                self.assertEqual(tuple(indicator.gauge.axis.range), (0, 100))
                self.assertEqual(indicator.gauge.bar.color, viz.RISK_COLORS[risk])
                self.assertNotIn("delta", indicator.to_plotly_json())
                self.assertIn("not a probability", figure.layout.annotations[0].text)

    def test_unavailable_scores_are_not_fabricated(self):
        for value in INVALID_SCORES:
            with self.subTest(value=value):
                self.assert_unavailable(viz.build_rejection_risk_gauge(value))


class ResumeScoreGaugeTests(FigureAssertions):
    def test_valid_scores_and_ratings(self):
        for value, expected_color in (
            (0, "#B35C45"), (49.9, "#B35C45"), (50, "#B35C45"),
            (69.9, "#B35C45"), (70, "#9B712D"), (84.9, "#9B712D"),
            (85, viz.ACCENT), (100, viz.ACCENT), (" 42.5 ", "#B35C45"),
        ):
            with self.subTest(value=value):
                figure = viz.build_resume_score_gauge(value)
                self.assert_styled(figure)
                indicator = figure.data[0]
                self.assertEqual(indicator.value, float(value))
                self.assertEqual(indicator.mode, "gauge")
                self.assertEqual(tuple(indicator.gauge.axis.range), (0, 100))
                self.assertEqual(indicator.gauge.bar.color, expected_color)
                self.assertEqual(figure.layout.annotations[0].text, f"<b>{int(round(float(value)))}</b>")
                self.assertIn("Higher is better", figure.layout.annotations[1].text)

    def test_unavailable_scores_are_not_fabricated(self):
        for value in INVALID_SCORES:
            with self.subTest(value=value):
                self.assert_unavailable(viz.build_resume_score_gauge(value))


class SectionRadarTests(FigureAssertions):
    def test_complete_radar_closes_without_changing_scores(self):
        figure = viz.build_section_radar(SECTIONS)
        self.assert_styled(figure)
        trace = figure.data[0]
        self.assertEqual(tuple(trace.r), (0, 65.5, 100, 0))
        self.assertEqual(trace.theta[0], trace.theta[-1])
        self.assertEqual(trace.fill, "toself")
        self.assertEqual(trace.line.color, viz.ACCENT)
        self.assertEqual(tuple(figure.layout.polar.radialaxis.range), (0, 100))
        self.assertIn("Contact<br>Header", figure.layout.polar.angularaxis.ticktext)

    def test_empty_and_malformed_containers(self):
        for value in ({}, None, [], "sections", 5, {"skills": {}},
                      {"skills": None}, {"skills": []}):
            with self.subTest(value=value):
                self.assert_unavailable(viz.build_section_radar(value))

    def test_invalid_scores_remain_gaps_not_zeros_or_averages(self):
        for value in INVALID_SCORES:
            with self.subTest(value=value):
                figure = viz.build_section_radar({
                    "skills": {"score": "100"},
                    "experience": {"score": value},
                    "education": {"score": 0},
                })
                self.assert_styled(figure)
                trace = figure.data[0]
                self.assertEqual(tuple(trace.r), (100, None, 0, 100))
                self.assertFalse(trace.connectgaps)
                self.assertEqual(trace.fill, "none")
                self.assertIn("N/A", figure.layout.polar.angularaxis.ticktext[1])

    def test_one_and_two_sections_use_markers_without_fake_polygon(self):
        for count in (1, 2):
            with self.subTest(count=count):
                figure = viz.build_section_radar({str(i): {"score": i * 100} for i in range(count)})
                self.assert_styled(figure)
                self.assertEqual(len(figure.data[0].r), count)
                self.assertEqual(figure.data[0].mode, "markers")
                self.assertEqual(figure.data[0].fill, "none")

    def test_all_invalid_scores_are_unavailable(self):
        for value in INVALID_SCORES:
            with self.subTest(value=value):
                self.assert_unavailable(viz.build_section_radar({"skills": {"score": value}}))


class SectionBarTests(FigureAssertions):
    def test_scores_and_boundary_labels_are_not_clipped(self):
        figure = viz.build_section_bar(SECTIONS)
        self.assert_styled(figure)
        self.assertEqual(tuple(figure.data[0].x), (0, 65.5, 100))
        self.assertEqual(tuple(figure.layout.xaxis.range), (0, 100))
        self.assertEqual(tuple(figure.data[0].marker.color),
                         ("#8B1A1A", "#9B712D", "#5F7144"))
        self.assertEqual([a.text for a in figure.layout.annotations], ["0/100", "65.5/100", "100/100"])
        for annotation in figure.layout.annotations:
            self.assertEqual(annotation.xref, "paper")
            self.assertGreater(annotation.x, 1)
        self.assertTrue(figure.layout.yaxis.automargin)

    def test_empty_and_malformed_containers(self):
        for value in ({}, None, [], "sections", 5):
            with self.subTest(value=value):
                self.assert_unavailable(viz.build_section_bar(value))

    def test_invalid_scores_have_no_bar_but_have_unavailable_label(self):
        for value in INVALID_SCORES:
            with self.subTest(value=value):
                figure = viz.build_section_bar({"skills": {"score": value}})
                self.assert_styled(figure)
                self.assertEqual(tuple(figure.data[0].x), (None,))
                self.assertEqual(figure.layout.annotations[0].text, "N/A")
                self.assertIn("unavailable", figure.layout.annotations[1].text)

    def test_missing_and_malformed_section_entries_and_risks(self):
        sections = {
            "missing": {}, "null": None, "list": [],
            "unknown_risk": {"score": "80", "risk": []},
            "normalized_risk": {"score": "12.5", "risk": " HIGH "},
        }
        figure = viz.build_section_bar(sections)
        self.assert_styled(figure)
        self.assertEqual(tuple(figure.data[0].x), (None, None, None, 80, 12.5))
        self.assertEqual(figure.data[0].marker.color[3], viz.MUTED)
        self.assertEqual(figure.data[0].customdata[3][1], "Risk unavailable")
        self.assertEqual(figure.data[0].marker.color[4], viz.RISK_COLORS["high"])

    def test_many_sections_get_readable_row_height(self):
        figure = viz.build_section_bar({f"section_{i}": {"score": i} for i in range(15)})
        self.assert_styled(figure)
        self.assertGreaterEqual(figure.layout.height, 15 * 52)


class KeywordMatchDonutTests(FigureAssertions):
    def test_valid_percentages_including_zero_and_full_match(self):
        for value in (0, 42.5, 100, " 75 "):
            with self.subTest(value=value):
                figure = viz.build_keyword_match_donut(value)
                self.assert_styled(figure)
                self.assertEqual(tuple(figure.data[0].values), (float(value), 100 - float(value)))
                self.assertEqual(sum(figure.data[0].values), 100)
                self.assertEqual(tuple(figure.data[0].labels), ("Matched", "Not matched"))
                self.assertEqual(tuple(figure.data[0].marker.colors), (viz.ACCENT, viz.TINT))
                self.assertIn("Role keyword match", figure.layout.title.text)
                self.assertIn(f"{float(value):g}%", figure.layout.annotations[0].text)
                self.assertEqual(figure.layout.legend.orientation, "h")
                # Hiding one wedge must not re-normalize the remaining match to 100%.
                self.assertFalse(figure.layout.legend.itemclick)
                self.assertFalse(figure.layout.legend.itemdoubleclick)

    def test_unavailable_data_is_not_a_zero_match(self):
        for value in INVALID_SCORES:
            with self.subTest(value=value):
                self.assert_unavailable(viz.build_keyword_match_donut(value))


class SharedBehaviorTests(FigureAssertions):
    def test_input_data_is_not_mutated(self):
        original = copy.deepcopy(SECTIONS)
        viz.build_section_radar(SECTIONS)
        viz.build_section_bar(SECTIONS)
        self.assertEqual(SECTIONS, original)

    def test_long_duplicate_display_labels_do_not_merge_sections(self):
        sections = {
            "very_long_section_name_with_shared_prefix_one": {"score": 0},
            "very_long_section_name_with_shared_prefix_two": {"score": 100},
            "<b>skills</b>": {"score": "75.25"},
            42: {"score": 50},
        }
        for builder in (viz.build_section_radar, viz.build_section_bar):
            with self.subTest(builder=builder.__name__):
                figure = builder(sections)
                self.assert_styled(figure)
                trace = figure.data[0]
                label = trace.customdata[2] if trace.type == "scatterpolar" else trace.customdata[2][0]
                self.assertEqual(label, "&lt;B&gt;Skills&lt;/B&gt;")
                positions = trace.theta[:-1] if trace.type == "scatterpolar" else trace.y
                self.assertEqual(len(set(positions)), 4)

    def test_attention_text_valid_values_are_estimates_without_emojis(self):
        for value in (0, 3, 6, 10, 20, 30, 100, " 6.5 "):
            with self.subTest(value=value):
                text = viz.build_attention_timer_text(value)
                self.assertIn("Estimated attention", text)
                self.assertIn(f"**{float(value):g}s**", text)
                self.assertNotRegex(text, "[\U0001F000-\U0001FAFF\u2600-\u27BF]")

    def test_attention_text_invalid_values_are_unavailable(self):
        for value in (None, "bad", "NaN", float("inf"), -1, True, [], {}):
            with self.subTest(value=value):
                self.assertEqual(viz.build_attention_timer_text(value), "Estimated attention unavailable.")

    def test_verdicts_keep_legacy_return_contract_without_emojis(self):
        expected = {
            "complete_overhaul": ("Comprehensive revision needed", "#B35C45"),
            "needs_work": ("Needs refinement", "#9B712D"),
            "junior_ready": ("Ready for junior roles", "#5F7144"),
            "strong_candidate": ("Strong candidate", "#5F7144"),
        }
        for key, result in expected.items():
            with self.subTest(key=key):
                self.assertEqual(viz.get_verdict_color_and_emoji(key), result)
                self.assertEqual(viz.get_verdict_color_and_emoji(f" {key.upper()} "), result)
        for value in ("unknown", None, [], {}, 3):
            with self.subTest(value=value):
                self.assertEqual(viz.get_verdict_color_and_emoji(value), ("Assessment unavailable", viz.MUTED))


if __name__ == "__main__":
    unittest.main()
