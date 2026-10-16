"""Audit raw extraction predictions without changing archived final judgments."""

from __future__ import annotations

from typing import Any

from .evaluation import PARAMETER_MATCHER_VERSION, evaluate_extraction


def _prediction(record: dict[str, Any]) -> dict[str, Any]:
    if "extracted_entities" in record:
        value = record["extracted_entities"]
    else:
        rounds = record.get("extract_rounds")
        if not isinstance(rounds, list) or not rounds:
            raise ValueError("Raw extracted_entities or extract_rounds are required; stored scores are insufficient")
        last = rounds[-1]
        if not isinstance(last, dict) or "extract_entities" not in last:
            raise ValueError("The last extraction round has no raw extract_entities")
        value = last["extract_entities"]
    if not isinstance(value, dict):
        raise ValueError("Raw extraction must be a JSON object (use an explicit empty object for a failed extraction)")
    return value


def _empty_bucket() -> dict[str, int]:
    return dict.fromkeys(
        ("cases", "final_correct_cases", "total_parameters", "matched_parameters",
         "all_parameters_correct_cases", "errors_with_parameter_mismatch",
         "errors_with_all_parameters_matching"), 0,
    )


def _finish(bucket: dict[str, int]) -> dict[str, Any]:
    return {
        **bucket,
        "parameter_match_rate": round(bucket["matched_parameters"] / bucket["total_parameters"], 9),
        "final_accuracy": round(bucket["final_correct_cases"] / bucket["cases"], 9),
    }


def rescore_records(
    gold_rows: list[dict[str, Any]], records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Require one-to-one row IDs and raw predictions; never infer missing runs.

    Accepted records have row_number, calculator_id, extracted_entities and a
    Boolean final_correct, or the pipeline's full *.steps.jsonl structure.
    Archived final-answer judgments are retained, not recalculated from PMR.
    """
    gold = {}
    for row in gold_rows:
        row_id = str(row.get("Row Number", "")).strip()
        if not row_id or row_id in gold:
            raise ValueError("Gold row IDs must be nonempty and unique")
        gold[row_id] = row
    seen = set()
    totals = _empty_bucket()
    categories: dict[str, dict[str, int]] = {}
    calculators: dict[str, dict[str, int]] = {}
    stored = {"cases_with_stored_counts": 0, "matched_parameters": 0,
              "total_parameters": 0, "all_parameters_correct_cases": 0,
              "changed_cases": 0, "errors_with_parameter_mismatch": 0,
              "errors_with_all_parameters_matching": 0}
    for record in records:
        row_id = str(record.get("row_number", "")).strip()
        if not row_id or row_id in seen or row_id not in gold:
            raise ValueError("Prediction row IDs must be unique and present in the gold dataset")
        seen.add(row_id)
        row = gold[row_id]
        cid = str(record.get("calculator_id", "")).strip()
        if cid != str(row.get("Calculator ID", "")).strip():
            raise ValueError(f"Calculator ID mismatch at row {row_id}")
        if "note_id" in record and str(record["note_id"]) != str(row.get("Note ID")):
            raise ValueError(f"Note ID mismatch at row {row_id}")
        judge = record.get("judge") or {}
        correct = record.get("final_correct", judge.get("final_correct"))
        if not isinstance(correct, bool):
            raise ValueError(f"An archived Boolean final_correct is required at row {row_id}")
        ex = evaluate_extraction(row.get("Relevant Entities"), _prediction(record))
        if not ex["total_params"]:
            raise ValueError(f"Missing or empty gold entities at row {row_id}")
        category = str(row.get("Category") or "unspecified")
        groups = (totals, categories.setdefault(category, _empty_bucket()),
                  calculators.setdefault(cid, _empty_bucket()))
        for bucket in groups:
            bucket["cases"] += 1
            bucket["final_correct_cases"] += int(correct)
            bucket["total_parameters"] += ex["total_params"]
            bucket["matched_parameters"] += ex["matched_params"]
            bucket["all_parameters_correct_cases"] += int(ex["all_params_correct"])
            if not correct:
                key = ("errors_with_all_parameters_matching" if ex["all_params_correct"]
                       else "errors_with_parameter_mismatch")
                bucket[key] += 1
        old = (record.get("judge_raw_extraction") or judge).get("extraction")
        if old is not None:
            count = old.get("matched_params")
            total = old.get("total_params")
            if (type(count) is not int or type(total) is not int
                    or total != ex["total_params"] or not 0 <= count <= total
                    or type(old.get("all_params_correct")) is not bool
                    or old["all_params_correct"] != (count == total)):
                raise ValueError(f"Invalid or incompatible stored extraction counts at row {row_id}")
            stored["cases_with_stored_counts"] += 1
            stored["matched_parameters"] += count
            stored["total_parameters"] += total
            stored["all_parameters_correct_cases"] += int(old["all_params_correct"])
            stored["changed_cases"] += int(count != ex["matched_params"])
            if not correct:
                key = ("errors_with_all_parameters_matching" if old["all_params_correct"]
                       else "errors_with_parameter_mismatch")
                stored[key] += 1
    if not gold or seen != set(gold):
        raise ValueError(f"Incomplete predictions: {len(seen)} records for {len(gold)} gold rows")
    return {
        "schema_version": 1,
        "parameter_matcher_version": PARAMETER_MATCHER_VERSION,
        "prediction_source": "raw extraction, not normalized tool input",
        "final_judgments": "preserved from archive; not independently regenerated",
        "error_grouping_note": (
            "All-parameters-matching errors require inspection of the tool, answer adapter, "
            "and benchmark contract; they are not automatically generated-tool errors."
        ),
        "corrected": _finish(totals),
        "stored_legacy_counts": stored if stored["cases_with_stored_counts"] else None,
        "by_category": {key: _finish(value) for key, value in sorted(categories.items())},
        "by_calculator": {key: _finish(value) for key, value in sorted(calculators.items())},
    }
