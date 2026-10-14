import tempfile
import unittest
from pathlib import Path

from toolmed_agent.tool_builder.run_api import _build_rag_docs_if_needed


class ToolBuilderInputTests(unittest.TestCase):
    def test_missing_private_material_explains_the_supported_input(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaisesRegex(RuntimeError, "--stage1_docs_jsonl"):
                _build_rag_docs_if_needed(temp_dir, "python", "train.csv", False)
            self.assertFalse((Path(temp_dir) / "rag_docs").exists())

    def test_existing_prepared_corpus_does_not_need_the_private_builder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            corpus = Path(temp_dir) / "rag_docs" / "stage1_tool_builder.jsonl"
            corpus.parent.mkdir()
            corpus.write_text('{"text": "test rule"}\n', encoding="utf-8")
            self.assertEqual(
                _build_rag_docs_if_needed(temp_dir, "python", "train.csv", False),
                str(corpus),
            )


if __name__ == "__main__":
    unittest.main()
