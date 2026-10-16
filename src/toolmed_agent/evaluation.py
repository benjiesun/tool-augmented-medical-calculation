# SPDX-License-Identifier: CC-BY-SA-4.0
#
# The calculator-specific scoring semantics in ``check_correctness`` are
# adapted from MedCalc-Bench-Verified v1.0.7:
# https://github.com/nikhilk7153/MedCalc-Bench-Verified/blob/v1.0.7/evaluation/evaluate.py
# This version retains the submitted project's answer adapter, safe parsing,
# extraction metrics, and equivalent portable date handling. See NOTICE.md.

import ast
import json
import math
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


PARAMETER_MATCHER_VERSION = "numeric-safe-v2"
FINAL_ANSWER_PROTOCOL = "submitted-adapter-v1"


def _safe_to_int(v: Any) -> Optional[int]:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None


def _parse_entities(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    s = str(raw or "").strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return {}
    for parser in (json.loads, ast.literal_eval):
        try:
            obj = parser(s)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return {}


def _norm_key(key: Any) -> str:
    s = str(key).strip().lower().replace("_", " ")
    return re.sub(r"\s+", " ", s)


def _norm_unit(unit: Any) -> str:
    s = str(unit).strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("μ", "u").replace("µ", "u")
    s = s.replace("mm hg", "mmhg")
    s = s.replace("years", "year")
    s = s.replace("yrs", "year")
    s = s.replace("days", "day")
    return s


def _units_match(key: Any, gt_unit: Any, pred_unit: Any) -> bool:
    gt = _norm_unit(gt_unit)
    pred = _norm_unit(pred_unit)
    if gt == pred:
        return True

    field = _norm_key(key)
    electrolyte_fields = {"sodium", "potassium", "chloride", "bicarbonate"}
    if field in electrolyte_fields and {gt, pred} == {"meq/l", "mmol/l"}:
        return True
    if field == "platelet count" and {gt, pred} == {"mm^3", "ul"}:
        return True
    if field in {"heart rate or pulse", "heart rate"} and {gt, pred} == {"bpm", "beats per minute"}:
        return True
    return False


def _to_num(v: Any) -> Optional[float]:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return None
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        if not s:
            return None
        try:
            num = float(s)
            if math.isnan(num) or math.isinf(num):
                return None
            return num
        except Exception:
            return None
    return None


def _to_bool(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        # Only explicit binary flags may represent Boolean annotations.
        # Treating every nonzero number as True made ages 47 and 87 match.
        return bool(v) if v in (0, 1) else None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y", "present", "positive"}:
            return True
        if s in {"false", "0", "no", "n", "absent", "negative"}:
            return False
    return None


def _parse_date(v: Any):
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%Y/%m/%d", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _num_match(a: float, b: float) -> bool:
    tol = max(1e-6, 1e-3 * max(abs(a), abs(b), 1.0))
    return abs(a - b) <= tol


def _scalar_match(gt: Any, pred: Any) -> bool:
    # The gold annotation determines the value kind. Numeric measurements
    # must be compared numerically, never through Python truthiness. In
    # particular, a predicted Boolean is not a measured value of 0 or 1.
    gt_num = _to_num(gt)
    if gt_num is not None:
        pred_num = _to_num(pred)
        return pred_num is not None and _num_match(gt_num, pred_num)

    gt_bool = _to_bool(gt)
    if gt_bool is not None:
        pred_bool = _to_bool(pred)
        return pred_bool is not None and gt_bool == pred_bool

    gt_date = _parse_date(gt)
    pred_date = _parse_date(pred)
    if gt_date is not None and pred_date is not None:
        return gt_date == pred_date

    return str(gt).strip().lower() == str(pred).strip().lower()


def _value_match(gt: Any, pred: Any, key: Any = "") -> bool:
    if isinstance(gt, tuple):
        gt = list(gt)
    if isinstance(pred, tuple):
        pred = list(pred)

    if isinstance(gt, list):
        if not isinstance(pred, list):
            return False
        if len(gt) == 0:
            return len(pred) == 0
        if len(gt) == 1:
            return len(pred) >= 1 and _scalar_match(gt[0], pred[0])
        if len(gt) == 2:
            if len(pred) < 2:
                return False
            return _scalar_match(gt[0], pred[0]) and _units_match(key, gt[1], pred[1])
        if len(pred) < len(gt):
            return False
        for g, p in zip(gt, pred):
            if not _scalar_match(g, p):
                return False
        return True

    return _scalar_match(gt, pred)


def evaluate_extraction(gt_entities_raw: Any, pred_entities: Dict[str, Any]) -> Dict[str, Any]:
    gt = _parse_entities(gt_entities_raw)
    pred_lookup = {_norm_key(k): v for k, v in (pred_entities or {}).items()}

    total = 0
    matched = 0
    miss_keys: List[str] = []
    wrong_keys: List[str] = []

    for gk, gv in gt.items():
        total += 1
        nk = _norm_key(gk)
        pv = pred_lookup.get(nk)
        if pv is None:
            miss_keys.append(str(gk))
            continue
        if _value_match(gv, pv, gk):
            matched += 1
        else:
            wrong_keys.append(str(gk))

    return {
        "matcher_version": PARAMETER_MATCHER_VERSION,
        "total_params": total,
        "matched_params": matched,
        "all_params_correct": bool(total > 0 and matched == total),
        "missing_param_keys": miss_keys,
        "wrong_param_keys": wrong_keys,
        "parameter_match_rate": (matched / total) if total else 0.0,
    }


def extract_answer_for_scoring(
    text: Any,
    calculator_id: Any,
    fallback: str = "N/A",
) -> str:
    """Use the project's submitted answer adapter without rescore changes."""
    if text is None:
        s = ""
    elif isinstance(text, (int, float)):
        s = str(text).strip()
    else:
        s = str(text).strip()
    cid = str(calculator_id).strip()
    if not s:
        return fallback

    if cid in {"13", "68"}:
        m = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4})\b", s)
        return m.group(1) if m else fallback

    if cid == "69":
        m = re.search(r"(\d+)\s*(?:weeks?|w)?\s*[,，]\s*(\d+)\s*(?:days?|d)?", s, flags=re.I)
        if not m:
            m = re.search(r"\(?\s*(\d+)\s*[,，]\s*(\d+)\s*\)?", s)
        if m:
            return f"({m.group(1)}, {m.group(2)})"
        return fallback

    for pat in [
        r"(?i)\banswer\s*[:=]\s*([^\n\r]+)",
        r"(?i)\bresult\s*[:=]\s*([^\n\r]+)",
        r"(?i)\bscore\s*[:=]\s*([^\n\r]+)",
    ]:
        m = re.search(pat, s)
        if m:
            cand = m.group(1).strip()
            nums = re.findall(r"-?\d+(?:\.\d+)?", cand)
            if nums:
                return nums[-1]
            return cand

    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if nums:
        return nums[-1]
    return fallback


def check_correctness(answer: str, ground_truth: Any, calid: Any, upper_limit: Any, lower_limit: Any) -> int:
    try:
        calid = int(float(str(calid)))
    except Exception:
        return 0

    if answer in (None, "", "N/A"):
        return 0

    if calid in [13, 68]:
        try:
            # Preserve the submitted %m/%d/%Y format and exact-date rule,
            # without POSIX-only strftime directives that fail on Windows.
            answer_date = datetime.strptime(str(answer), "%m/%d/%Y").date()
            ground_truth_date = datetime.strptime(str(ground_truth), "%m/%d/%Y").date()
            return int(answer_date == ground_truth_date)
        except (TypeError, ValueError):
            return 0

    if calid in [69]:
        try:
            mg = re.search(r"\(?[\"']?(\d+)\s*(weeks?)?[\"']?,?\s*[\"']?(\d+)\s*(days?)?[\"']?\s*\)?", str(ground_truth))
            ma = re.search(r"\(?[\"']?(\d+)\s*(weeks?)?[\"']?,?\s*[\"']?(\d+)\s*(days?)?[\"']?\s*\)?", str(answer))
            if not mg or not ma:
                return 0
            g = (int(mg.group(1)), int(mg.group(3)))
            a = (int(ma.group(1)), int(ma.group(3)))
            return 1 if a == g else 0
        except Exception:
            return 0

    if calid in [4, 15, 16, 17, 18, 20, 21, 25, 27, 28, 29, 32, 33, 36, 43, 45, 48, 51, 69]:
        try:
            return 1 if round(float(answer)) == float(ground_truth) else 0
        except Exception:
            return 0

    if calid in [2, 3, 5, 6, 7, 8, 9, 10, 11, 19, 22, 23, 24, 26, 30, 31, 38, 39, 40, 44, 46, 49, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67]:
        try:
            a = float(answer)
            lo = float(lower_limit)
            hi = float(upper_limit)
            return 1 if lo <= a <= hi else 0
        except Exception:
            return 0

    return 0


def judge_case(
    row: Dict[str, Any],
    extracted_entities: Dict[str, Any],
    tool_result_raw: Any,
) -> Dict[str, Any]:
    extraction = evaluate_extraction(row.get("Relevant Entities"), extracted_entities)
    computed = extract_answer_for_scoring(
        tool_result_raw,
        row.get("Calculator ID"),
        fallback="N/A",
    )
    correct = check_correctness(
        computed,
        row.get("Ground Truth Answer"),
        row.get("Calculator ID"),
        row.get("Upper Limit"),
        row.get("Lower Limit"),
    )

    return {
        "extraction": extraction,
        "computed_answer": computed,
        "final_correct": bool(correct),
        "final_answer_protocol": FINAL_ANSWER_PROTOCOL,
    }


def summarize(judge_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_cases = len(judge_rows)
    correct_cases = 0
    total_params = 0
    matched_params = 0
    all_params_correct_cases = 0

    for row in judge_rows:
        ex = (row.get("judge") or {}).get("extraction", {})
        if (row.get("judge") or {}).get("final_correct"):
            correct_cases += 1
        total_params += int(ex.get("total_params", 0) or 0)
        matched_params += int(ex.get("matched_params", 0) or 0)
        if ex.get("all_params_correct"):
            all_params_correct_cases += 1

    return {
        "parameter_matcher_version": PARAMETER_MATCHER_VERSION,
        "final_answer_protocol": FINAL_ANSWER_PROTOCOL,
        "total_cases": total_cases,
        "final_correct_cases": correct_cases,
        "final_accuracy": round(correct_cases / total_cases, 6) if total_cases else 0.0,
        "total_params": total_params,
        "matched_params": matched_params,
        "param_match_rate": round(matched_params / total_params, 6) if total_params else 0.0,
        "all_params_correct_cases": all_params_correct_cases,
    }
