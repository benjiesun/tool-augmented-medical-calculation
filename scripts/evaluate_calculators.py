#!/usr/bin/env python3
"""Evaluate the released calculators with benchmark ground-truth parameters."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import tempfile
from pathlib import Path

from toolmed_agent.evaluation import judge_case
from toolmed_agent.tool_registry import CalculationToolRegistry
from toolmed_agent.utils import parse_entities


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the released tools on ground-truth entities. This measures tool "
            "execution, not end-to-end parameter extraction."
        )
    )
    parser.add_argument(
        "--test-csv",
        type=Path,
        default=ROOT / "data" / "processed" / "test_data.csv",
    )
    parser.add_argument(
        "--tools-dir",
        type=Path,
        default=ROOT / "artifacts" / "calculators" / "gpt_5_5",
    )
    parser.add_argument(
        "--legacy-evaluator",
        action="store_true",
        help="reproduce the submitted calculator-69 parsing behavior",
    )
    args = parser.parse_args()

    test_csv = args.test_csv.resolve()
    tools_dir = args.tools_dir.resolve()
    with test_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    correct = 0
    runtime_errors = 0
    per_calculator = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_tools = Path(temp_dir)
        for source in tools_dir.glob("calculator_*.py"):
            shutil.copy2(source, temp_tools / source.name)
        registry = CalculationToolRegistry(str(temp_tools))

        for row in rows:
            calculator_id = str(row.get("Calculator ID", "")).strip()
            entities = parse_entities(row.get("Relevant Entities", ""))
            execution = registry.calculate(calculator_id, entities)
            runtime_errors += int(bool(execution.error))
            judged = judge_case(
                row,
                entities,
                execution.result,
                legacy_calc69_parser=args.legacy_evaluator,
            )
            is_correct = int(judged["final_correct"])
            correct += is_correct
            slot = per_calculator.setdefault(
                calculator_id,
                {"cases": 0, "correct": 0},
            )
            slot["cases"] += 1
            slot["correct"] += is_correct

    total = len(rows)
    summary = {
        "evaluation_scope": "calculator tools with ground-truth input entities",
        "legacy_evaluator": args.legacy_evaluator,
        "cases": total,
        "correct": correct,
        "accuracy": round(correct / total, 6) if total else 0.0,
        "runtime_errors": runtime_errors,
        "per_calculator": dict(
            sorted(per_calculator.items(), key=lambda item: int(item[0]))
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if runtime_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
