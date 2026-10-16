#!/usr/bin/env python3
"""Run a released calculator on a JSON object of structured parameters."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from dataclasses import asdict
from pathlib import Path

from toolmed_agent.tool_registry import CalculationToolRegistry


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="JSON input file")
    parser.add_argument(
        "--tools-dir",
        type=Path,
        default=ROOT / "artifacts" / "calculators" / "gpt_5_5",
    )
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or not isinstance(payload.get("relevant_entities"), dict):
            raise ValueError("input must contain a relevant_entities object")
        calculator_id = payload.get("calculator_id")
        if not str(calculator_id or "").strip():
            raise ValueError("input must contain calculator_id")
        if not args.tools_dir.is_dir():
            raise ValueError("tools directory does not exist")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    # Keep the frozen artifact directory free of generated registry files.
    with tempfile.TemporaryDirectory() as temp_dir:
        destination = Path(temp_dir)
        for source in args.tools_dir.glob("calculator_*.py"):
            shutil.copy2(source, destination / source.name)
        registry = CalculationToolRegistry(str(destination))
        result = registry.calculate(calculator_id, payload["relevant_entities"])
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        if result.error:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
