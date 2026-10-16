import unittest

from toolmed_agent.evaluation import (
    check_correctness,
    evaluate_extraction,
    extract_answer_for_scoring,
    judge_case,
)


class ParameterMatchingTests(unittest.TestCase):
    def test_nonzero_numbers_do_not_collapse_to_true(self):
        for gold, predicted in ((47, 87), (87, 47), (1.4, 1.8), (-2, 2), (1, 2)):
            with self.subTest(gold=gold, predicted=predicted):
                result = evaluate_extraction({"value": gold}, {"value": predicted})
                self.assertEqual(result["matched_params"], 0)
                self.assertFalse(result["all_params_correct"])

    def test_age_value_unit_pairs_and_numeric_strings(self):
        for gold, predicted in (([47, "years"], [87, "year"]), (["47", "years"], [87, "years"])):
            with self.subTest(gold=gold, predicted=predicted):
                self.assertEqual(evaluate_extraction({"age": gold}, {"age": predicted})["matched_params"], 0)
        self.assertEqual(evaluate_extraction({"age": [47, "years"]}, {"age": ["47", "year"]})["matched_params"], 1)

    def test_boolean_flags_accept_only_explicit_binary_values(self):
        for gold, predicted in ((True, 1), (False, 0), (True, "yes"), (False, "negative")):
            with self.subTest(gold=gold, predicted=predicted):
                self.assertEqual(evaluate_extraction({"flag": gold}, {"flag": predicted})["matched_params"], 1)
        for gold, predicted in ((True, 47), (True, 87), (False, 2), (1, True), (0, False)):
            with self.subTest(gold=gold, predicted=predicted):
                self.assertEqual(evaluate_extraction({"value": gold}, {"value": predicted})["matched_params"], 0)

    def test_numeric_tolerance_and_nonfinite_predictions(self):
        self.assertEqual(evaluate_extraction({"x": 1000}, {"x": 1000.5})["matched_params"], 1)
        for predicted in (float("nan"), float("inf"), "nan", "inf", True):
            with self.subTest(predicted=predicted):
                self.assertEqual(evaluate_extraction({"x": 47}, {"x": predicted})["matched_params"], 0)

    def test_dates_units_missing_keys_and_aggregate(self):
        result = evaluate_extraction(
            {"age": [47, "years"], "date": "01/02/2024", "sodium": [140, "mEq/L"], "missing": 1},
            {"age": [87, "year"], "date": "2024-01-02", "sodium": [140, "mmol/L"]},
        )
        self.assertEqual((result["matched_params"], result["total_params"]), (2, 4))
        self.assertEqual(result["wrong_param_keys"], ["age"])
        self.assertEqual(result["missing_param_keys"], ["missing"])
        self.assertEqual(result["matcher_version"], "numeric-safe-v2")

    def test_parameter_mismatch_does_not_change_final_answer_judgment(self):
        row = {"Calculator ID": "2", "Relevant Entities": {"age": [47, "years"]},
               "Ground Truth Answer": "25", "Lower Limit": "24", "Upper Limit": "26"}
        result = judge_case(row, {"age": [87, "years"]}, 25)
        self.assertFalse(result["extraction"]["all_params_correct"])
        self.assertTrue(result["final_correct"])


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
