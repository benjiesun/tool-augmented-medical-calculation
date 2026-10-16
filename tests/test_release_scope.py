import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "src/validate_artifacts.py"
SPEC = importlib.util.spec_from_file_location("validate_artifacts", SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ReleaseScopeTests(unittest.TestCase):
    def test_full_responses_and_extraction_traces_are_private(self):
        values = [
            {"raw_model_output": "synthetic response"},
            {"llm_io": [{"messages": [{"role": "user", "content": "synthetic input"}]}]},
            {"nested": [{"extracted_entities": {"age": 47}}]},
            {"extract_rounds": [{"round": 0}]},
            {"patient_note": "synthetic note"},
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertTrue(VALIDATOR._contains_private_trace(value))

    def test_empty_template_notes_and_configuration_are_allowed(self):
        value = {"schema": {"required_fields": ["age"]}, "patient_note": "",
                 "raw_model_output": "", "parameter_matcher_version": "numeric-safe-v2"}
        self.assertFalse(VALIDATOR._contains_private_trace(value))

    def test_current_publishable_files_pass(self):
        errors = []
        VALIDATOR.validate_release_scope(errors)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
