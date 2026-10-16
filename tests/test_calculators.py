import re
import shutil
import tempfile
import unittest
from pathlib import Path

from toolmed_agent.evaluation import judge_case
from toolmed_agent.tool_registry import CalculationToolRegistry


ROOT = Path(__file__).resolve().parents[1]
TOOL_DIR = ROOT / "artifacts" / "calculators" / "gpt_5_5"
EXPECTED_IDS = {
    2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 16, 17, 18, 19, 20,
    21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 36, 38, 39,
    40, 43, 44, 45, 46, 48, 49, 51, 56, 57, 58, 59, 60, 61, 62, 63,
    64, 65, 66, 67, 68, 69,
}


class CalculatorArtifactTests(unittest.TestCase):
    def test_expected_calculator_ids_are_present_once(self):
        paths = sorted(TOOL_DIR.glob("calculator_*.py"))
        ids = []
        for path in paths:
            match = re.fullmatch(r"calculator_(\d+)(?:_.*)?", path.stem)
            self.assertIsNotNone(match, path.name)
            ids.append(int(match.group(1)))
        self.assertEqual(len(paths), 55)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), EXPECTED_IDS)

    def _registry_with_tools(self, *calculator_ids):
        temp_dir = tempfile.TemporaryDirectory()
        target = Path(temp_dir.name)
        for calculator_id in calculator_ids:
            source = next(TOOL_DIR.glob(f"calculator_{calculator_id}_*.py"))
            shutil.copy2(source, target / source.name)
        return temp_dir, CalculationToolRegistry(str(target))

    def test_mean_arterial_pressure_tool(self):
        temp_dir, registry = self._registry_with_tools(5)
        self.addCleanup(temp_dir.cleanup)
        result = registry.calculate(
            5,
            {
                "Systolic blood pressure": 120,
                "Diastolic blood pressure": 80,
            },
        )
        self.assertEqual(result.error, "")
        self.assertAlmostEqual(result.result, 93.33333333333333)

    def test_gestational_age_tool_and_submitted_evaluator(self):
        temp_dir, registry = self._registry_with_tools(69)
        self.addCleanup(temp_dir.cleanup)
        result = registry.calculate(
            69,
            {
                "Current Date": "05/23/2024",
                "Last menstrual date": "02/14/2024",
            },
        )
        self.assertEqual(result.error, "")
        self.assertEqual(result.result, ("14 weeks", "1 days"))

        row = {
            "Calculator ID": "69",
            "Relevant Entities": "{}",
            "Ground Truth Answer": "('14 weeks', '1 days')",
            "Lower Limit": "",
            "Upper Limit": "",
        }
        judged = judge_case(row, {}, result.result)
        self.assertEqual(judged["computed_answer"], "N/A")
        self.assertFalse(judged["final_correct"])

    def test_case_c_uses_pinned_gold_not_manuscript_typo(self):
        temp_dir, registry = self._registry_with_tools(24)
        self.addCleanup(temp_dir.cleanup)
        entities = {
            "input steroid": ["Hydrocortisone PO", 162.935, "mg"],
            "target steroid": "Dexamethasone PO",
        }
        execution = registry.calculate(24, entities)
        self.assertEqual(execution.error, "")
        # Freeze the released artifact, including its documented substring bug.
        self.assertAlmostEqual(execution.result, 4.88805)
        self.assertAlmostEqual(162.935 * 0.75 / 20, 6.1100625)
        row = {
            "Calculator ID": "24", "Relevant Entities": entities,
            "Ground Truth Answer": "6.11006",
            "Lower Limit": "5.80456", "Upper Limit": "6.41556",
        }
        self.assertFalse(judge_case(row, entities, execution.result)["final_correct"])
        self.assertTrue(judge_case(row, entities, 6.11006)["final_correct"])
        # The printed label is wrong, but still inside the benchmark tolerance.
        self.assertTrue(judge_case(row, entities, 6.029)["final_correct"])


if __name__ == "__main__":
    unittest.main()
