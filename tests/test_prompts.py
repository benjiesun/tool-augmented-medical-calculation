import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from toolmed_agent.extraction import ParameterExtractor
from toolmed_agent.memory import MemoryStore
from toolmed_agent.pipeline import CentralHost
from toolmed_agent.prompts import (
    EXTRACTION_REQUIREMENTS, EXTRACTION_SYSTEM, RULE_CURATION_REQUIREMENTS,
    RULE_CURATION_SYSTEM, TOOL_SYNTHESIS_REQUIREMENTS, TOOL_SYNTHESIS_SYSTEM,
    build_rule_curation_messages, calculator_schema,
)
from toolmed_agent.tool_builder.prompts import stage1_build_tool_prompt
from toolmed_agent.tool_generation import _stage1_build_tool_prompt


class Figure2PromptTests(unittest.TestCase):
    def test_rule_curation_requests_all_figure2_fields(self):
        messages = build_rule_curation_messages("5", "MAP", "Synthetic question", "Synthetic rule", [])
        self.assertEqual(messages[0]["content"], RULE_CURATION_SYSTEM)
        text = messages[1]["content"]
        self.assertIn(RULE_CURATION_REQUIREMENTS, text)
        for field in ("conditions", "boundary_cases", "output", "required_fields", "units", "enum", "allow_null", "default"):
            self.assertIn(field, text)

    def test_pipeline_rule_curator_uses_shared_contract(self):
        calls = []
        def chat(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(text='{"rule": {}, "schema": {}}')
        host = CentralHost.__new__(CentralHost)
        host.rule_retriever_llm = SimpleNamespace(available=True, chat=chat)
        host.trace_full_llm_io = False
        result = host._organize_rule_with_llm("5", "MAP", "Synthetic question", "Synthetic rule", [])
        self.assertIn("schema", result)
        self.assertEqual(calls[0]["messages"][0]["content"], RULE_CURATION_SYSTEM)
        self.assertIn(RULE_CURATION_REQUIREMENTS, calls[0]["messages"][1]["content"])

    def test_both_tool_builder_routes_use_figure2_contract(self):
        variants = [
            stage1_build_tool_prompt("5", "MAP", [{"text": "Synthetic rule"}]),
            _stage1_build_tool_prompt("5", "MAP", "Synthetic rule", "decimal", [], []),
        ]
        for messages in variants:
            with self.subTest(messages=messages):
                self.assertEqual(messages[0]["content"], TOOL_SYNTHESIS_SYSTEM)
                self.assertIn(TOOL_SYNTHESIS_REQUIREMENTS, messages[1]["content"])
                self.assertIn("Calculator schema S_c:", messages[1]["content"])
                self.assertIn('"required_fields"', messages[1]["content"])
                self.assertNotIn("return 'N/A'", messages[1]["content"])

    def test_specification_schemas_available_for_all_released_calculators(self):
        root = Path(__file__).resolve().parents[1]
        for path in (root / "artifacts/calculators/gpt_5_5").glob("calculator_*.py"):
            cid = path.name.split("_")[1]
            with self.subTest(calculator_id=cid):
                self.assertTrue(calculator_schema(cid).get("required_fields"))

    def test_extraction_has_three_examples_and_no_extra_arithmetic_instruction(self):
        extractor = ParameterExtractor(SimpleNamespace(available=False))
        calc = {"schema": {"required_fields": ["age"]}, "few_shot": {"examples": [
            {"question": f"Synthetic example {i}", "patient_note": f"Synthetic note {i}",
             "relevant_entities": {"age": [20 + i, "years"]}} for i in range(4)
        ]}}
        prompt = extractor._build_medbench_prompt("2", "Synthetic calculator", "Synthetic question", "Synthetic note", ["age"], calc)
        self.assertIn(EXTRACTION_SYSTEM, prompt)
        self.assertIn(EXTRACTION_REQUIREMENTS, prompt)
        for i in (1, 2, 3):
            self.assertIn(f"Example {i}", prompt)
        self.assertNotIn("Example 4", prompt)
        self.assertNotIn("derive (Systolic", prompt)
        self.assertNotIn("must be populated", prompt)
        self.assertTrue(prompt.endswith("Output JSON z only."))

    def test_rule_schema_survives_memory_storage(self):
        schema = {"required_fields": ["age"]}
        with tempfile.TemporaryDirectory() as directory:
            memory = MemoryStore(directory)
            memory.save_web_rule("2", "Synthetic", "Synthetic question", "Synthetic rule", [],
                                 rule_specification={"conditions": "Synthetic condition"}, schema=schema)
            saved = memory.get_rule("2", "", "")
            self.assertEqual(saved["schema"], schema)
            self.assertIn("conditions", saved["rule_specification"])
            self.assertFalse(memory.static_rules_path.exists())
            self.assertTrue(memory.web_rules_path.read_text(encoding="utf-8").strip())
            memory.refresh()
            self.assertEqual(memory.get_rule("2", "", "")["schema"], schema)

    def test_public_stub_skips_web_only_when_reusing_frozen_tools(self):
        stub = {"source": "public_artifact_stub", "calculator_id": "2"}
        for local_only in (True, False):
            saved = []
            searched = []
            def save(**kwargs):
                saved.append(kwargs)
                return kwargs
            def search(**kwargs):
                searched.append(kwargs)
                return {"evidence_text": "Synthetic evidence", "source_hits": []}
            host = CentralHost.__new__(CentralHost)
            host.local_tools_only = local_only
            host.memory = SimpleNamespace(get_rule=lambda *args: stub, save_web_rule=save)
            host.web_searcher = SimpleNamespace(search_calculator_rule=search)
            host._organize_rule_with_llm = lambda **kwargs: {
                "rule": {"name": "Synthetic", "formula": "Synthetic formula"},
                "schema": {"required_fields": ["age"]},
            }
            with self.subTest(local_only=local_only):
                host._resolve_rule_doc({"Calculator ID": "2", "Calculator Name": "Synthetic", "Question": "Synthetic"}, {})
                self.assertEqual(len(searched), int(not local_only))
                if not local_only:
                    self.assertEqual(saved[0]["schema"]["required_fields"], ["age"])

    def test_on_demand_validation_samples_training_only_and_reuses_eight(self):
        host = CentralHost.__new__(CentralHost)
        host.rows_by_calc = {"2": [{"Row Number": str(i), "split": "train"} for i in range(12)]}
        host.tool_validation_seed = 20260415
        first = host._sample_eval_rows_for_tool_build("2", "test-row")
        second = host._sample_eval_rows_for_tool_build("2", "another-test-row")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertEqual(len({row["Row Number"] for row in first}), 8)
        self.assertTrue(all(row["split"] == "train" for row in first))
        host.rows_by_calc = {}
        with self.assertRaises(ValueError):
            host._sample_eval_rows_for_tool_build("2", "test-row")


if __name__ == "__main__":
    unittest.main()
