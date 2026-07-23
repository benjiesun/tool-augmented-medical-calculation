#!/usr/bin/env python3
"""Rehydrate untracked few-shot notes from a verified upstream training file."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = ROOT / "data" / "processed" / "case_library_template_v1_8.json"
DEFAULT_TRAIN = ROOT / "data" / "processed" / "train_data.csv"
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "case_library_merged_v1_8.json"


def _norm_id(value: Any) -> str:
    text = str(value or "").strip()
    try:
        return str(int(float(text)))
    except (TypeError, ValueError):
        return text


def _examples(calculator: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    for item in calculator.get("cases", []) or []:
        if isinstance(item, dict):
            yield item
    few_shot = calculator.get("few_shot", {}) or {}
    for item in few_shot.get("examples", []) or []:
        if isinstance(item, dict):
            yield item


def prepare_case_library(
    template_path: Path,
    train_csv: Path,
    output_path: Path,
) -> int:
    template_path = template_path.resolve()
    train_csv = train_csv.resolve()
    output_path = output_path.resolve()
    if output_path == template_path:
        raise ValueError("output must not overwrite the committed note-free template")

    library = json.loads(template_path.read_text(encoding="utf-8"))
    with train_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        training_rows = {
            str(row.get("Row Number", "")).strip(): row
            for row in csv.DictReader(handle)
        }

    hydrated = 0
    for calculator in library.get("calculators", []):
        calculator_id = _norm_id(calculator.get("calculator_id"))
        for example in _examples(calculator):
            # The archived library deliberately kept CSV-fallback duplicates
            # note-free; preserve that behavior instead of hydrating all 495
            # structural records.
            if str(example.get("source", "")).strip() == "csv_few_shot":
                example["patient_note"] = ""
                continue
            row_number = str(example.get("train_row_number", "")).strip()
            row = training_rows.get(row_number)
            if row is None:
                raise KeyError(f"training row {row_number!r} is missing")
            if _norm_id(row.get("Calculator ID")) != calculator_id:
                raise ValueError(
                    f"calculator mismatch for training row {row_number}: "
                    f"template={calculator_id}, train={row.get('Calculator ID')}"
                )
            example["patient_note"] = row.get("Patient Note", "")
            hydrated += 1

    meta = library.setdefault("meta", {})
    meta["patient_notes_committed"] = False
    meta["patient_notes_hydrated_from"] = (
        "MedCalc-Bench-Verified v1.0.7 train_data.csv"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    part_path = output_path.with_suffix(output_path.suffix + ".part")
    try:
        part_path.write_text(
            json.dumps(library, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(part_path, output_path)
    finally:
        if part_path.exists():
            part_path.unlink()
    return hydrated


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the untracked case library from its note-free template."
    )
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--train-csv", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    count = prepare_case_library(args.template, args.train_csv, args.output)
    print(f"[ok] hydrated {count} few-shot entries: {args.output.resolve()}")


if __name__ == "__main__":
    main()
