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

    def test_gestational_age_tool_and_corrected_evaluator(self):
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
        self.assertTrue(judge_case(row, {}, result.result)["final_correct"])


if __name__ == "__main__":
    unittest.main()
