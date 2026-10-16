#!/usr/bin/env python3
"""Rescore a complete raw prediction archive against the pinned test split."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

from toolmed_agent.rescore import rescore_records


ROOT = Path(__file__).resolve().parents[1]
TEST_SHA256 = "91d222234a5a427de1127e864a199a51af9e709357352423c8a22857476e7abf"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True,
                        help="full pipeline *.steps.jsonl or canonical raw predictions; not judge-only scores")
    parser.add_argument("--test-csv", type=Path, default=ROOT / "data/processed/test_data.csv")
    parser.add_argument("--output", type=Path, help="optional JSON aggregate output; keep private traces outside Git")
    args = parser.parse_args()
    try:
        dataset_bytes = args.test_csv.read_bytes()
        if hashlib.sha256(dataset_bytes).hexdigest() != TEST_SHA256:
            raise ValueError("Test CSV does not match the pinned MedCalc-Bench Verified v1.0.7 split")
        with args.test_csv.open(encoding="utf-8-sig", newline="") as stream:
            gold = list(csv.DictReader(stream))
        raw_bytes = args.predictions.read_bytes()
        records = [json.loads(line) for line in raw_bytes.decode("utf-8-sig").splitlines() if line.strip()]
        if not all(isinstance(record, dict) for record in records):
            raise ValueError("Each prediction record must be a JSON object")
        result = rescore_records(gold, records)
        result["source"] = {
            "prediction_file": args.predictions.name,
            "prediction_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "test_csv_sha256": TEST_SHA256,
        }
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output = args.output.resolve()
            if output in {args.test_csv.resolve(), args.predictions.resolve()}:
                raise ValueError("Output must not overwrite a source file")
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(text)
        print(text, end="")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
