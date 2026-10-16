"""Shared prompt contracts transcribed from final-manuscript Figure 2.

Only task data (evidence, schema, examples, and patient note) are interpolated.
These templates contain no historical model answers or patient-note archive.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any


PROMPT_CONTRACT_VERSION = "final-manuscript-figure2-v1"

RULE_CURATION_SYSTEM = (
    "You are a medical calculator rule curator.\n"
    "Read web evidence and output STRICT JSON only."
)
RULE_CURATION_REQUIREMENTS = (
    "Return calculator rule: name, URL, formula or scoring rule, input variables, "
    "conditions, boundary cases, output format, evidence text.\n"
    "Return calculator schema: required_fields; value kinds; allowed units; "
    "categorical enums; nullable/default behavior.\n"
    "Do not invent facts absent from evidence."
)

TOOL_SYNTHESIS_SYSTEM = (
    "You are an expert medical calculator tool builder.\n"
    "Output STRICT JSON only, no markdown, no explanation."
)
TOOL_SYNTHESIS_REQUIREMENTS = (
    "Write robust Python: def calc(relevant): values may be scalar, "
    "[value, unit], tuple, or dict.\n"
    "Add safe parsing helpers for numbers, text, Booleans, dates, and units.\n"
    "Implement formula/scoring logic, branches, boundary cases, rounding, and output contract.\n"
    "If required inputs are missing, return the benchmark-specified missing-value output.\n"
    "Deterministic, runnable, no external dependencies.\n"
    'Return JSON: {"required_entities": [...], "tool_code": "def calc(relevant): ..."}'
)

EXTRACTION_SYSTEM = (
    "You are extracting parameters for a medical calculator.\n"
    "Return only one valid JSON object, no markdown or extra keys."
)
EXTRACTION_REQUIREMENTS = (
    "Return measured values as [value, unit]; preserve allowed source units when possible.\n"
    "Use null for unsupported required fields; use false for absent Boolean criteria.\n"
    "For categorical fields, explicit negative evidence maps to the negative enum value."
)


@lru_cache(maxsize=4)
def _load_schemas(path: str) -> dict[str, Any]:
    source = Path(path)
    if not source.is_file():
        return {}
    with source.open(encoding="utf-8") as stream:
        data = json.load(stream)
    return {
        str(item["calculator_id"]): item.get("schema", {})
        for item in data.get("calculators", [])
        if isinstance(item, dict) and "calculator_id" in item
    }


def calculator_schema(calculator_id: Any) -> dict[str, Any]:
    """Read the released specification-derived schema, never infer it from test labels."""
    default = Path(__file__).resolve().parents[2] / "data/processed/case_library_template_v1_8.json"
    path = os.environ.get("TOOL_SCHEMA_JSON", str(default))
    return _load_schemas(str(Path(path).resolve())).get(str(calculator_id), {})


def build_rule_curation_messages(
    calculator_id: str, calculator_name: str, question: str,
    evidence_text: str, source_hits: list[dict[str, Any]],
) -> list[dict[str, str]]:
    user = (
        f"Calculator ID: {calculator_id}\nCalculator Name: {calculator_name}\nQuestion: {question}\n\n"
        f"Retrieved evidence snippets:\n{evidence_text}\n\n"
        f"Source hits:\n{json.dumps(source_hits, ensure_ascii=False)}\n\n"
        f"{RULE_CURATION_REQUIREMENTS}\n\n"
        "Return one JSON object with a rule object and a schema object.\n"
        'rule: {"name": ..., "URL": ..., "formula": ..., "inputs": ..., '
        '"conditions": ..., "boundary_cases": ..., "output": ..., "evidence_text": ...}\n'
        'schema: {"required_fields": [...], "fields": {"field_name": '
        '{"value_kind": ..., "units": [...], "enum": [...], "allow_null": ..., "default": ...}}}'
    )
    return [{"role": "system", "content": RULE_CURATION_SYSTEM}, {"role": "user", "content": user}]


def build_tool_synthesis_messages(
    calculator_id: str, calculator_name: str, output_type: str,
    curated_rule: str, schema: dict[str, Any], training_examples: list[dict[str, Any]],
) -> list[dict[str, str]]:
    user = (
        f"Calculator ID: {calculator_id}\nCalculator Name: {calculator_name}\n"
        f"Expected output type: {output_type or 'unknown'}\n\n"
        f"Curated rule and RAG rule references:\n{curated_rule or '(none)'}\n\n"
        f"Calculator schema S_c:\n{json.dumps(schema, ensure_ascii=False, indent=2)}\n\n"
        f"Training examples:\n{json.dumps(training_examples, ensure_ascii=False, indent=2)}\n\n"
        f"{TOOL_SYNTHESIS_REQUIREMENTS}"
    )
    return [{"role": "system", "content": TOOL_SYNTHESIS_SYSTEM}, {"role": "user", "content": user}]


def build_extraction_prompt(
    calculator_id: str, calculator_name: str, question: str, patient_note: str,
    fields: list[str], output_schema: dict[str, Any], field_specs: str, fewshot: str,
) -> str:
    return "\n\n".join([
        EXTRACTION_SYSTEM, EXTRACTION_REQUIREMENTS,
        f"Calculator ID: {calculator_id}\nCalculator Name: {calculator_name}\nQuestion: {question}",
        f"Required parameters from schema: {', '.join(fields)}",
        "JSON schema for the required output (value kinds, allowed units, enums, nullable fields):\n"
        + json.dumps(output_schema, ensure_ascii=False, indent=2),
        f"Field specs:\n{field_specs}",
        f"k = 3 same-calculator examples:\n{fewshot or '(none supplied)'}",
        f"Patient note n:\n{patient_note}",
        "Output JSON z only.",
    ])
