import unittest

from toolmed_agent.evaluation import (
    check_correctness,
    extract_answer_for_scoring,
    judge_case,
)


class Calculator69EvaluationTests(unittest.TestCase):
    def test_submitted_parser_preserves_quoted_duration_behavior(self):
        values = [
            ["14 weeks", "1 days"],
            ("14 weeks", "1 days"),
            "['14 weeks', '1 days']",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    extract_answer_for_scoring(value, 69),
                    "N/A",
                )

    def test_submitted_parser_accepts_supported_formats(self):
        for value in ("14 weeks, 1 day", "(14, 1)", (14, 1)):
            with self.subTest(value=value):
                self.assertEqual(extract_answer_for_scoring(value, 69), "(14, 1)")

    def test_submitted_parser_rejects_incomplete_or_unrelated_values(self):
        values = [
            None,
            "",
            ("14 weeks",),
            ("14 weeks", "unknown"),
            "2024-01-01",
            "patient 50, score 2",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    extract_answer_for_scoring(value, 69),
                    "N/A",
                )

    def test_scoring_rule_and_project_answer_adapter_are_distinct(self):
        # The upstream-style scoring rule recognizes the quoted pair.
        # The submitted project's preceding adapter still returns N/A.
        released_output = str(("14 weeks", "1 days"))
        self.assertEqual(
            check_correctness(released_output, released_output, 69, "", ""),
            1,
        )
        self.assertEqual(extract_answer_for_scoring(released_output, 69), "N/A")

    def test_judge_case_preserves_submitted_protocol(self):
        row = {
            "Calculator ID": "69",
            "Relevant Entities": "{}",
            "Ground Truth Answer": "('14 weeks', '1 days')",
            "Lower Limit": "",
            "Upper Limit": "",
        }
        submitted = judge_case(row, {}, ("14 weeks", "1 days"))
        supported_format = judge_case(row, {}, "(14, 1)")
        self.assertEqual(submitted["computed_answer"], "N/A")
        self.assertFalse(submitted["final_correct"])
        self.assertTrue(supported_format["final_correct"])


class PortableDateEvaluationTests(unittest.TestCase):
    def test_leading_zero_variants_match(self):
        for calculator_id in (13, 68):
            with self.subTest(calculator_id=calculator_id):
                self.assertEqual(
                    check_correctness(
                        "1/2/2024",
                        "01/02/2024",
                        calculator_id,
                        "",
                        "",
                    ),
                    1,
                )

    def test_other_date_formats_remain_outside_submitted_protocol(self):
        for calculator_id in (13, 68):
            for value in ("2024-01-02", "2024/01/02", "01-02-2024", "01/02/24"):
                with self.subTest(calculator_id=calculator_id, value=value):
                    self.assertEqual(
                        check_correctness(value, "01/02/2024", calculator_id, "", ""),
                        0,
                    )
                    self.assertEqual(
                        check_correctness("01/02/2024", value, calculator_id, "", ""),
                        0,
                    )

    def test_invalid_or_different_dates_do_not_match(self):
        self.assertEqual(
            check_correctness("01/03/2024", "01/02/2024", 13, "", ""),
            0,
        )
        self.assertEqual(
            check_correctness("not-a-date", "01/02/2024", 68, "", ""),
            0,
        )


if __name__ == "__main__":
    unittest.main()
