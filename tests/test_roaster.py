import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from core import roaster


UNAVAILABLE = {
    "analysis_error": True,
    "sections": {},
    "missing_keywords": [],
    "strong_keywords_found": [],
}


def valid_scores():
    return {
        "overall_rejection_risk": 35,
        "attention_seconds": 12,
        "sections": {
            "summary": {"score": 80, "risk": "low", "one_liner": "Clear focus"},
            "experience": {"score": 65, "risk": "medium", "one_liner": "Add metrics"},
        },
        "jd_keyword_match_percent": 75,
        "missing_keywords": ["Kubernetes"],
        "strong_keywords_found": ["Python", "SQL"],
        "ats_compatibility": "good",
        "resume_type_verdict": "junior_ready",
    }


class RoasterTests(unittest.TestCase):
    def setUp(self):
        client_patch = patch.object(roaster, "_client")
        self.client = client_patch.start()
        self.addCleanup(client_patch.stop)

    def score_response(self, raw):
        self.client.chat.return_value = SimpleNamespace(message=SimpleNamespace(content=raw))
        return roaster.get_rejection_scores("resume", "job", model="llama3.2:1b")

    def test_stream_passes_temperature_and_preserves_persona(self):
        for temperature in (0.0, 0.3, 1.2):
            with self.subTest(temperature=temperature):
                self.client.chat.return_value = [
                    SimpleNamespace(message=SimpleNamespace(content="Hello ")),
                    SimpleNamespace(message=SimpleNamespace(content="world")),
                ]
                chunks = list(roaster.stream_roast(
                    "resume", "job", "llama3.2:1b", "Be constructive", temperature
                ))
                self.assertEqual(chunks, ["Hello ", "world"])
                kwargs = self.client.chat.call_args.kwargs
                self.assertEqual(kwargs["options"]["temperature"], temperature)
                self.assertEqual(kwargs["model"], "llama3.2:1b")
                self.assertTrue(kwargs["stream"])
                self.assertEqual(kwargs["messages"][0], {
                    "role": "system", "content": "Be constructive"
                })

    def test_stream_retains_default_temperature_and_accepts_dict_chunks(self):
        self.client.chat.return_value = [{"message": {"content": "roast"}}]
        self.assertEqual(list(roaster.stream_roast("resume", "job", model="local:tag")), ["roast"])
        self.assertEqual(self.client.chat.call_args.kwargs["options"]["temperature"], 0.85)

    def test_installed_models_preserve_exact_names_and_order(self):
        names = ["llama3.2:1b", "llama3.2:latest", "registry.example/team/custom:q4_K_M"]
        self.client.list.return_value = SimpleNamespace(
            models=[SimpleNamespace(model=name) for name in names]
        )
        self.assertEqual(roaster.get_installed_models(), names)
        self.client.list.assert_called_once_with()

    def test_installed_models_support_dict_responses(self):
        self.client.list.return_value = {"models": [
            {"model": "llama3.2:1b"}, {"name": "mistral:7b"}, {"model": None}
        ]}
        self.assertEqual(roaster.get_installed_models(), ["llama3.2:1b", "mistral:7b"])

    def test_installed_models_empty_or_disconnected(self):
        self.client.list.return_value = SimpleNamespace(models=[])
        self.assertEqual(roaster.get_installed_models(), [])
        self.client.list.side_effect = ConnectionError("Ollama is offline")
        self.assertEqual(roaster.get_installed_models(), [])

    def test_valid_json_and_fenced_json(self):
        expected = valid_scores()
        raw = json.dumps(expected)
        for content in (raw, f"```json\n{raw}\n```", f" \n```\n{raw}\n```\n "):
            with self.subTest(content=content):
                self.assertEqual(self.score_response(content), expected)
                self.assertEqual(self.client.chat.call_args.kwargs["model"], "llama3.2:1b")

    def test_valid_dict_backend_response(self):
        expected = valid_scores()
        self.client.chat.return_value = {"message": {"content": json.dumps(expected)}}
        self.assertEqual(roaster.get_rejection_scores("resume", "job", "local:tag"), expected)

    def test_numeric_strings_are_parsed_and_scores_clamped(self):
        scores = valid_scores()
        scores.update(overall_rejection_risk=" 150 ", jd_keyword_match_percent="-10", attention_seconds="7.5")
        scores["sections"]["summary"]["score"] = "101"
        scores["sections"]["experience"]["score"] = "-2.5"
        result = self.score_response(json.dumps(scores))
        self.assertEqual(result["overall_rejection_risk"], 100)
        self.assertEqual(result["jd_keyword_match_percent"], 0)
        self.assertEqual(result["attention_seconds"], 7.5)
        self.assertEqual(result["sections"]["summary"]["score"], 100)
        self.assertEqual(result["sections"]["experience"]["score"], 0)

    def test_fractional_scores_and_zero_are_valid(self):
        scores = valid_scores()
        scores["overall_rejection_risk"] = 0
        scores["sections"]["summary"]["score"] = "82.5"
        result = self.score_response(json.dumps(scores))
        self.assertEqual(result["overall_rejection_risk"], 0)
        self.assertEqual(result["sections"]["summary"]["score"], 82.5)

    def test_attention_is_nonnegative_not_a_percentage(self):
        for seconds, expected in ((-5, 0), (120, 120)):
            with self.subTest(seconds=seconds):
                scores = valid_scores()
                scores["attention_seconds"] = seconds
                self.assertEqual(self.score_response(json.dumps(scores))["attention_seconds"], expected)

    def test_invalid_missing_and_non_object_json_are_unavailable(self):
        for raw in ("", "No analysis", "{broken}", "{}", "[]", "null", "true", "50",
                    json.dumps([valid_scores()]), json.dumps(json.dumps(valid_scores())),
                    "```json\n[]\n```", None):
            with self.subTest(raw=raw):
                self.assertEqual(self.score_response(raw), UNAVAILABLE)

    def test_missing_required_fields_are_unavailable(self):
        for field in ("overall_rejection_risk", "attention_seconds", "jd_keyword_match_percent", "sections"):
            with self.subTest(field=field):
                scores = valid_scores()
                del scores[field]
                self.assertEqual(self.score_response(json.dumps(scores)), UNAVAILABLE)

    def test_invalid_numbers_are_unavailable(self):
        invalid_values = (None, True, False, [], {}, "", "high", "50%", "NaN", "Infinity", "1e999", float("nan"))
        for field in ("overall_rejection_risk", "attention_seconds", "jd_keyword_match_percent", "section_score"):
            for value in invalid_values:
                with self.subTest(field=field, value=value):
                    scores = valid_scores()
                    if field == "section_score":
                        scores["sections"]["experience"]["score"] = value
                    else:
                        scores[field] = value
                    self.assertEqual(self.score_response(json.dumps(scores)), UNAVAILABLE)

    def test_invalid_sections_are_unavailable(self):
        for sections in (None, [], {}, "summary", {"summary": 50}, {"summary": {}},
                         {"summary": {"risk": "low"}}, {"summary": {"score": 70, "risk": []}},
                         {"summary": {"score": 70, "one_liner": None}}):
            with self.subTest(sections=sections):
                scores = valid_scores()
                scores["sections"] = sections
                self.assertEqual(self.score_response(json.dumps(scores)), UNAVAILABLE)

    def test_each_section_is_validated(self):
        scores = valid_scores()
        scores["sections"]["additional_section"] = {"score": "unavailable"}
        self.assertEqual(self.score_response(json.dumps(scores)), UNAVAILABLE)

    def test_invalid_keyword_lists_are_unavailable(self):
        for field in ("missing_keywords", "strong_keywords_found"):
            for keywords in (None, "Python", {}, 5, ["Python", None], [1], [{}]):
                with self.subTest(field=field, keywords=keywords):
                    scores = valid_scores()
                    scores[field] = keywords
                    self.assertEqual(self.score_response(json.dumps(scores)), UNAVAILABLE)

    def test_missing_keyword_lists_are_safe_empty_lists(self):
        scores = valid_scores()
        del scores["missing_keywords"]
        del scores["strong_keywords_found"]
        result = self.score_response(json.dumps(scores))
        self.assertEqual(result["missing_keywords"], [])
        self.assertEqual(result["strong_keywords_found"], [])
        self.assertNotIn("analysis_error", result)

    def test_invalid_verdict_types_are_unavailable(self):
        for field in ("ats_compatibility", "resume_type_verdict"):
            for value in (None, [], {}, 5):
                with self.subTest(field=field, value=value):
                    scores = valid_scores()
                    scores[field] = value
                    self.assertEqual(self.score_response(json.dumps(scores)), UNAVAILABLE)

    def test_backend_failures_and_missing_content_are_unavailable(self):
        for response in (None, {}, SimpleNamespace(message=None)):
            with self.subTest(response=response):
                self.client.chat.return_value = response
                self.assertEqual(roaster.get_rejection_scores("resume", "job", "local:tag"), UNAVAILABLE)
        self.client.chat.side_effect = ConnectionError("Ollama is offline")
        self.assertEqual(roaster.get_rejection_scores("resume", "job", "local:tag"), UNAVAILABLE)

    def test_error_sentinel_has_no_numeric_defaults_and_is_fresh(self):
        expected = deepcopy(UNAVAILABLE)
        result = roaster._default_scores()
        self.assertEqual(result, expected)
        result["sections"]["summary"] = {"score": 50}
        result["missing_keywords"].append("Python")
        self.assertEqual(roaster._default_scores(), expected)


if __name__ == "__main__":
    unittest.main()
