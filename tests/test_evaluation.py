import unittest

from toolmed_agent.evaluation import (
    check_correctness,
    extract_answer_for_scoring,
    judge_case,
)


class Calculator69EvaluationTests(unittest.TestCase):
    def test_corrected_parser_accepts_released_tool_formats(self):
        values = [
            ["14 weeks", "1 days"],
            ("14 weeks", "1 days"),
            "['14 weeks', '1 days']",
            "14 weeks, 1 day",
            "(14, 1)",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(
                    extract_answer_for_scoring(value, 69),
                    "(14, 1)",
                )

    def test_corrected_parser_rejects_incomplete_or_unrelated_values(self):
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

    def test_legacy_mode_preserves_submitted_parser_behavior(self):
        released_output = ("14 weeks", "1 days")
        self.assertEqual(
            extract_answer_for_scoring(
                released_output,
                69,
                legacy_calc69_parser=True,
            ),
            "N/A",
        )
        self.assertEqual(
            extract_answer_for_scoring(
                "14 weeks, 1 day",
                69,
                legacy_calc69_parser=True,
            ),
            "(14, 1)",
        )

    def test_judge_case_threads_parser_mode(self):
        row = {
            "Calculator ID": "69",
            "Relevant Entities": "{}",
            "Ground Truth Answer": "('14 weeks', '1 days')",
            "Lower Limit": "",
            "Upper Limit": "",
        }
        corrected = judge_case(row, {}, ("14 weeks", "1 days"))
        legacy = judge_case(
            row,
            {},
            ("14 weeks", "1 days"),
            legacy_calc69_parser=True,
        )
        self.assertTrue(corrected["final_correct"])
        self.assertFalse(legacy["final_correct"])


class PortableDateEvaluationTests(unittest.TestCase):
    def test_equivalent_date_formats_match(self):
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
                self.assertEqual(
                    check_correctness(
                        "2024-01-02",
                        "01/02/2024",
                        calculator_id,
                        "",
                        "",
                    ),
                    1,
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
