import copy
import unittest

from toolmed_agent.rescore import rescore_records


class RawExtractionRescoreTests(unittest.TestCase):
    def setUp(self):
        self.gold = [
            {"Row Number": "1", "Calculator ID": "2", "Category": "lab test", "Note ID": "A",
             "Relevant Entities": {"age": [47, "years"]}},
            {"Row Number": "2", "Calculator ID": "24", "Category": "dosage", "Note ID": "B",
             "Relevant Entities": {"dose": 10}},
        ]
        self.records = [
            {"row_number": "1", "calculator_id": "2", "extracted_entities": {"age": [87, "years"]},
             "final_correct": False},
            {"row_number": "2", "calculator_id": "24", "extracted_entities": {"dose": 10},
             "final_correct": False},
        ]

    def test_corrected_parameter_counts_and_cautious_error_grouping(self):
        result = rescore_records(self.gold, list(reversed(self.records)))
        self.assertEqual(result["corrected"]["matched_parameters"], 1)
        self.assertEqual(result["corrected"]["errors_with_parameter_mismatch"], 1)
        self.assertEqual(result["corrected"]["errors_with_all_parameters_matching"], 1)
        self.assertEqual(result["by_category"]["dosage"]["parameter_match_rate"], 1)
        self.assertIsNone(result["stored_legacy_counts"])

    def test_pipeline_records_use_last_raw_round_not_tool_input(self):
        records = copy.deepcopy(self.records)
        raw = records[0].pop("extracted_entities")
        records[0]["extract_rounds"] = [{"extract_entities": raw}]
        records[0]["tool_call"] = {"tool_input": {"age": [47, "years"]}}
        records[0]["judge"] = {"extraction": {"matched_params": 1, "total_params": 1,
                                               "all_params_correct": True}}
        result = rescore_records(self.gold, records)
        self.assertEqual(result["corrected"]["matched_parameters"], 1)
        self.assertEqual(result["stored_legacy_counts"]["changed_cases"], 1)

    def test_duplicate_unknown_or_incomplete_rows_are_rejected(self):
        for records in ([self.records[0]] * 2, self.records[:1],
                        [dict(self.records[0], row_number="unknown"), self.records[1]]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                rescore_records(self.gold, records)

    def test_wrong_calculator_or_note_is_rejected(self):
        for change in ({"calculator_id": "24"}, {"note_id": "wrong"}):
            records = copy.deepcopy(self.records)
            records[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                rescore_records(self.gold, records)

    def test_stored_scores_cannot_replace_raw_predictions(self):
        records = copy.deepcopy(self.records)
        records[0].pop("extracted_entities")
        records[0]["judge"] = {"extraction": {"matched_params": 1, "total_params": 1}}
        with self.assertRaises(ValueError):
            rescore_records(self.gold, records)

    def test_boolean_final_judgment_is_required(self):
        for invalid in (None, "False", 0, 1):
            records = copy.deepcopy(self.records)
            records[0]["final_correct"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                rescore_records(self.gold, records)


if __name__ == "__main__":
    unittest.main()
