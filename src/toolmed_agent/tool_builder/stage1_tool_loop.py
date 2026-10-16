import argparse
import ast
import hashlib
import json
import math
import os
import random
import re
import signal
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .common import (
    append_jsonl,
    calc_id,
    ensure_dir,
    extract_calc_code,
    extract_first_json,
    load_csv_rows,
    load_jsonl,
    now_str,
    parse_required_entities,
    safe_float,
    safe_str,
)
from .local_llm import local_vllm
from .prompts import stage1_build_tool_prompt
from .rag import MedicalRAG


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None


def _parse_entities(raw: str) -> Dict[str, Any]:
    txt = safe_str(raw).strip()
    if not txt:
        return {}
    for fn in (ast.literal_eval, json.loads):
        try:
            obj = fn(txt)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    try:
        txt2 = txt.replace("'", '"')
        obj = json.loads(txt2)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    return {}


def _to_scalar_entities(entities: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (entities or {}).items():
        if isinstance(v, tuple):
            v = list(v)
        if isinstance(v, list):
            out[k] = v[0] if v else None
        else:
            out[k] = v
    return out


def _to_wrapped_entities(entities: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in (entities or {}).items():
        if isinstance(v, tuple):
            out[k] = list(v)
        elif isinstance(v, list):
            out[k] = v
        else:
            out[k] = [v]
    return out


def _extract_numeric(v: Any) -> Optional[float]:
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for x in v.values():
            y = _extract_numeric(x)
            if y is not None:
                return y
        return None
    if isinstance(v, (list, tuple)):
        for x in v:
            y = _extract_numeric(x)
            if y is not None:
                return y
        return None
    s = safe_str(v)
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _parse_date(v: Any) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = safe_str(v).strip()
    if not s:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _parse_week_day(v: Any) -> Optional[Tuple[int, int]]:
    if isinstance(v, (list, tuple)) and len(v) >= 2:
        a = _safe_int(v[0])
        b = _safe_int(v[1])
        if a is not None and b is not None:
            return a, b
    s = safe_str(v).lower()
    m1 = re.search(r"(\d+)\s*week", s)
    m2 = re.search(r"(\d+)\s*day", s)
    if m1 and m2:
        return int(m1.group(1)), int(m2.group(1))
    return None


def _norm_text(s: Any) -> str:
    x = safe_str(s).strip().lower()
    x = re.sub(r"\s+", " ", x)
    x = x.replace("−", "-")
    return x


def _safe_code_check_stage1(code: str) -> Tuple[bool, str]:
    s = safe_str(code)
    if not s:
        return False, "empty_code"
    if "def calc(" not in s:
        return False, "missing_calc"
    forbidden = [
        r"(?i)\bimport\b",
        r"(?i)\bexec\s*\(",
        r"(?i)\beval\s*\(",
        r"(?i)\bopen\s*\(",
        r"(?i)\bos\.",
        r"(?i)\bsys\.",
        r"(?i)\bsubprocess\b",
        r"__",
    ]
    for pat in forbidden:
        if re.search(pat, s):
            return False, f"forbidden:{pat}"
    try:
        tree = ast.parse(s)
    except Exception as e:
        return False, f"syntax_error:{type(e).__name__}:{e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and safe_str(getattr(node, "arg", "")).strip() == "next":
            return False, "forbidden_name:next"
        if isinstance(node, ast.Name) and isinstance(getattr(node, "ctx", None), ast.Store) and node.id == "next":
            return False, "forbidden_name:next"
        if isinstance(node, ast.FunctionDef) and safe_str(getattr(node, "name", "")).strip() == "next":
            return False, "forbidden_name:next"
    return True, ""


def _compile_tool(code: str) -> Tuple[Optional[Any], str]:
    ok, reason = _safe_code_check_stage1(code)
    if not ok:
        return None, reason
    if "def calc(" not in safe_str(code):
        return None, "missing_calc"
    g = {
        "__builtins__": {
            "min": min,
            "max": max,
            "abs": abs,
            "round": round,
            "int": int,
            "float": float,
            "sum": sum,
            "len": len,
            "all": all,
            "any": any,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "range": range,
            "pow": pow,
            "isinstance": isinstance,
            "ValueError": ValueError,
            "TypeError": TypeError,
            "KeyError": KeyError,
            "Exception": Exception,
            "__import__": __import__,
        },
        "math": math,
        "datetime": datetime,
        "timedelta": timedelta,
        "date": date,
    }
    try:
        # Use a shared namespace so helpers defined in tool_code are visible from calc().
        exec(code, g, g)
    except Exception as e:
        return None, f"exec_error:{type(e).__name__}:{e}"
    fn = g.get("calc")
    if not callable(fn):
        return None, "calc_not_callable"
    return fn, ""


class _ToolTimeout(Exception):
    pass


def _call_with_timeout(fn: Any, arg: Any, timeout_sec: int) -> Any:
    if timeout_sec <= 0:
        return fn(arg)

    def _handler(signum: int, frame: Any) -> None:
        raise _ToolTimeout("tool_timeout")

    old_handler = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(int(timeout_sec))
    try:
        return fn(arg)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def _run_tool(fn: Any, relevant: Dict[str, Any], timeout_sec: int = 3) -> Tuple[Any, str]:
    attempts = [
        relevant if isinstance(relevant, dict) else {},
        _to_scalar_entities(relevant if isinstance(relevant, dict) else {}),
        _to_wrapped_entities(relevant if isinstance(relevant, dict) else {}),
    ]
    last_err = ""
    for x in attempts:
        try:
            return _call_with_timeout(fn, x, timeout_sec=timeout_sec), ""
        except _ToolTimeout as e:
            last_err = f"{type(e).__name__}:{e}"
        except Exception as e:
            last_err = f"{type(e).__name__}:{e}"
    return None, last_err or "unknown_runtime_error"


def _judge(row: Dict[str, Any], pred: Any) -> Tuple[bool, str]:
    low = safe_float(row.get("Lower Limit"))
    high = safe_float(row.get("Upper Limit"))
    gt = safe_str(row.get("Ground Truth Answer")).strip()

    if low is not None and high is not None:
        pv = _extract_numeric(pred)
        if pv is None:
            return False, "pred_not_numeric"
        if low <= pv <= high:
            return True, "in_numeric_range"
        return False, f"out_of_range:[{low},{high}] pred={pv}"

    pd = _parse_date(pred)
    gd = _parse_date(gt)
    if pd is not None and gd is not None:
        return (pd == gd), f"date_compare pred={pd} gt={gd}"

    pw = _parse_week_day(pred)
    gw = _parse_week_day(gt)
    if pw is not None and gw is not None:
        return (pw == gw), f"week_day_compare pred={pw} gt={gw}"

    ok = _norm_text(pred) == _norm_text(gt)
    return ok, f"text_compare pred={_norm_text(pred)} gt={_norm_text(gt)}"


def _extract_tool_payload(raw_resp: str) -> Tuple[List[str], str]:
    required = parse_required_entities(raw_resp)
    tool_code = ""
    obj = extract_first_json(raw_resp)
    if isinstance(obj, dict):
        if isinstance(obj.get("required_entities"), list):
            required = [safe_str(x).strip() for x in obj.get("required_entities", []) if safe_str(x).strip()]
        tool_code = safe_str(obj.get("tool_code", "")).strip()
    if not tool_code:
        tool_code = extract_calc_code(raw_resp)
    tool_code = safe_str(tool_code).strip()
    if tool_code.startswith("```"):
        m = re.search(r"(?is)```(?:python)?\s*(.*?)```", tool_code)
        if m:
            tool_code = safe_str(m.group(1)).strip()
    # Recover cases where model returns escaped code string with literal \"\\n\".
    if "\\n" in tool_code and "\n" not in tool_code:
        tool_code = tool_code.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "    ")
    # If wrapped in quotes as one long string, unwrap once.
    if (tool_code.startswith('"') and tool_code.endswith('"')) or (
        tool_code.startswith("'") and tool_code.endswith("'")
    ):
        tool_code = tool_code[1:-1]
        if "\\n" in tool_code and "\n" not in tool_code:
            tool_code = tool_code.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "    ")
    return required[:80], tool_code


def _error_report(compile_error: str, eval_rows: List[Dict[str, Any]]) -> str:
    if compile_error:
        return f"compile_error: {compile_error}"
    fails = [x for x in eval_rows if not x.get("ok")]
    if not fails:
        return "unknown_failure"
    chunks: List[str] = []
    for x in fails[:3]:
        chunks.append(
            "row={row} reason={reason} pred={pred} gt={gt} range=[{low},{high}]".format(
                row=x.get("row_number"),
                reason=x.get("reason"),
                pred=safe_str(x.get("pred")),
                gt=safe_str(x.get("gt")),
                low=safe_str(x.get("low")),
                high=safe_str(x.get("high")),
            )
        )
    return "\n".join(chunks)


def _failed_rows_text(eval_rows: List[Dict[str, Any]], max_rows: int = 5) -> str:
    fails = [x for x in eval_rows if not x.get("ok")]
    if not fails:
        return "(none)"
    lines: List[str] = []
    for x in fails[:max_rows]:
        rel = x.get("relevant")
        rel_txt_raw = json.dumps(rel, ensure_ascii=False) if isinstance(rel, dict) else safe_str(rel)
        rel_txt = rel_txt_raw[:360] + (" ...(truncated)" if len(rel_txt_raw) > 360 else "")
        lines.append(
            "row={row}; reason={reason}; pred={pred}; gt={gt}; range=[{low},{high}]; relevant={rel}".format(
                row=safe_str(x.get("row_number")),
                reason=safe_str(x.get("reason")),
                pred=safe_str(x.get("pred"))[:100],
                gt=safe_str(x.get("gt"))[:100],
                low=safe_str(x.get("low")),
                high=safe_str(x.get("high")),
                rel=rel_txt,
            )
        )
    return "\n".join(lines)


def _safe_code_excerpt(code: Any, max_chars: int = 3400, max_lines: int = 120) -> str:
    lines = safe_str(code).splitlines()
    clipped = lines[: max(1, int(max_lines))]
    txt = "\n".join(clipped)
    if len(lines) > len(clipped):
        txt += "\n# ...(line-truncated)..."
    if len(txt) > max_chars:
        head = txt[: max_chars]
        cut = head.rfind("\n")
        if cut > 0:
            head = head[:cut]
        txt = head + "\n# ...(char-truncated)..."
    return txt


def _extract_out_of_range_ratio(reason: str) -> Optional[float]:
    s = safe_str(reason).strip()
    m = re.search(r"out_of_range:\[([\-0-9.eE]+),([\-0-9.eE]+)\]\s*pred=([\-0-9.eE]+)", s)
    if not m:
        return None
    try:
        low = float(m.group(1))
        high = float(m.group(2))
        pred = float(m.group(3))
    except Exception:
        return None
    mid = (low + high) / 2.0
    if abs(mid) < 1e-12:
        return None
    return abs(pred / mid)


def _classify_error_signature(compile_error: str, eval_rows: List[Dict[str, Any]]) -> Tuple[str, str]:
    ce = safe_str(compile_error).strip().lower()
    failed = [x for x in eval_rows if not x.get("ok")]
    reasons = [safe_str(x.get("reason")) for x in failed]
    rtxt = "\n".join(reasons).lower()

    if ce:
        if "empty_code" in ce:
            return "format_empty_code", "Model output format broke: no usable tool_code."
        if "syntax_error" in ce:
            return "compile_syntax_error", "Generated Python has syntax errors."
        if "forbidden" in ce:
            return "policy_forbidden_code", "Generated code violates sandbox rules (e.g. import)."
        return "compile_other", "Compilation failed before evaluation."

    if "pred_not_numeric" in rtxt:
        return "pred_not_numeric", "Numeric calculator returned non-numeric outputs."
    if "nameerror" in rtxt:
        return "name_error", "Undefined symbol/helper at runtime."
    if "keyerror" in rtxt:
        return "key_alias_mismatch", "Input key lookup mismatch (alias/case/punctuation)."
    if "typeerror" in rtxt:
        return "type_parse_error", "Input type parsing failed."
    if "valueerror" in rtxt:
        return "value_parse_error", "Numeric/date conversion failed on raw inputs."

    ratios: List[float] = []
    for r in reasons:
        rv = _extract_out_of_range_ratio(r)
        if rv is not None:
            ratios.append(rv)
    if ratios:
        large = sum(1 for v in ratios if v >= 10.0 or v <= 0.1)
        if large >= max(1, len(ratios) // 2):
            return "unit_scale_error", "Predictions show systematic unit/magnitude mismatch (often x10/x100/x1000)."
        return "formula_branch_error", "Values are numeric but branch/threshold/formula logic is wrong."

    if failed:
        return "runtime_or_logic_other", "Runtime/logic mismatch with benchmark."
    return "unknown_failure", "No explicit failure signature found."


def _suggest_fix_hints(
    compile_error: str,
    eval_rows: List[Dict[str, Any]],
    same_code_streak: int = 0,
    no_improve_streak: int = 0,
) -> str:
    hints: List[str] = []
    ce = safe_str(compile_error).strip()
    if ce:
        hints.append("Regenerate complete code from scratch; ensure quotes/brackets/colons are fully closed.")
        hints.append("Keep code shorter and avoid oversized literal tables in one expression.")
    reason_list = [safe_str(x.get("reason")) for x in eval_rows if not x.get("ok")]
    reason_text = "\n".join(reason_list).lower()
    if "pred_not_numeric" in reason_text:
        hints.append("Return numeric scalar for numeric calculators; avoid labels or 'N/A' on valid inputs.")
    if "nameerror" in reason_text:
        hints.append("Define helper functions in the same code block and ensure calc() can access them.")
    if "argument of type 'float' is not iterable" in reason_text:
        hints.append("Do not use `'unit' in value` when value may be float; split value and unit first.")
    if "keyerror" in reason_text:
        hints.append("Use alias/case-insensitive key lookup; never assume exact key spelling.")
    if "out_of_range" in reason_text:
        hints.append("Re-check formula branch logic and unit conversion using failed examples.")
        ratios: List[float] = []
        for r in reason_list:
            rv = _extract_out_of_range_ratio(r)
            if rv is not None:
                ratios.append(rv)
        if ratios:
            large = sum(1 for v in ratios if v >= 10.0 or v <= 0.1)
            if large >= max(1, len(ratios) // 2):
                hints.append("Most errors are large-magnitude: verify unit conversion (cm/m, mg/dL/mmol/L, kg/lb).")
    if int(same_code_streak) >= 2 or int(no_improve_streak) >= 2:
        hints.append("Must make a material logic/parsing change; do not return near-identical code.")
    if not hints:
        hints.append("Apply targeted fix based on failed rows and keep the rest unchanged.")
    uniq: List[str] = []
    seen = set()
    for h in hints:
        k = h.strip().lower()
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(h)
    return "\n".join(f"- {h}" for h in uniq[:5])


def _build_followup_user_message(
    round_i: int,
    sample_total: int,
    correct_n: int,
    compile_error: str,
    error_report: str,
    previous_code: str,
    eval_rows: List[Dict[str, Any]],
    same_code_streak: int = 0,
    same_compile_streak: int = 0,
    no_improve_streak: int = 0,
    patch_mode: bool = False,
) -> str:
    failed_txt = _failed_rows_text(eval_rows, max_rows=4)
    compile_txt = safe_str(compile_error).strip() or "none"
    prev_code = _safe_code_excerpt(previous_code, max_chars=2800, max_lines=90)
    err_class, err_class_desc = _classify_error_signature(compile_error=compile_error, eval_rows=eval_rows)
    hints_txt = _suggest_fix_hints(
        compile_error=compile_error,
        eval_rows=eval_rows,
        same_code_streak=same_code_streak,
        no_improve_streak=no_improve_streak,
    )
    mode_txt = (
        "PATCH MODE (high-score safeguard): keep current structure and make minimal targeted edits only.\n"
        "Do NOT rewrite from scratch; preserve behavior on already-correct cases."
        if patch_mode
        else "REPAIR MODE: you may refactor more broadly if needed, but fix the identified root cause first."
    )
    return (
        f"Round {round_i} feedback for the same calculator.\n"
        "Write improved tool_code using the initial calculator rules and the previous-round failures only.\n\n"
        f"{mode_txt}\n\n"
        f"Previous round summary: sampled_correct={correct_n}/{sample_total}; compile_error={compile_txt}; "
        f"same_compile_streak={int(same_compile_streak)}; same_code_streak={int(same_code_streak)}; "
        f"no_improve_streak={int(no_improve_streak)}.\n"
        f"primary_error_class: {err_class}\n"
        f"primary_error_explanation: {err_class_desc}\n"
        f"error_report: {error_report}\n\n"
        "Previous round tool code:\n"
        f"{prev_code}\n\n"
        "Previous round failed cases (must include input/pred/gt, top 4):\n"
        f"{failed_txt}\n\n"
        "Suggested fixes:\n"
        f"{hints_txt}\n\n"
        "Rules:\n"
        "- Keep formula/rules consistent with calculator references.\n"
        "- Handle inputs robustly: scalar OR [value, unit] OR tuple OR dict.\n"
        "- Support alias/case-insensitive key matching where needed.\n"
        "- No markdown, no explanation, no import.\n\n"
        "Return STRICT JSON only:\n"
        "{\n"
        '  "required_entities": ["key1", "key2"],\n'
        '  "fix_plan": "one short sentence root-cause fix",\n'
        '  "tool_code": "def calc(relevant):\\n    ..."\n'
        "}"
    )


def _trim_conversation_messages(messages: List[Dict[str, str]], keep_tail_pairs: int = 3) -> List[Dict[str, str]]:
    # Keep initial system+task prompt and the most recent assistant/user turns.
    if len(messages) <= 2 + keep_tail_pairs * 2:
        return list(messages)
    head = list(messages[:2])
    tail = list(messages[-keep_tail_pairs * 2 :])
    bridge = {
        "role": "user",
        "content": (
            "Context note: earlier rounds are truncated for length. "
            "Use initial calculator rules plus the latest code/errors to continue fixing."
        ),
    }
    return head + [bridge] + tail


def _clip_text_keep_head(s: Any, max_chars: int) -> str:
    txt = safe_str(s)
    if max_chars <= 0:
        return ""
    if len(txt) <= max_chars:
        return txt
    marker = "\n...(truncated)...\n"
    k = max(0, max_chars - len(marker))
    return txt[:k] + marker


def _compact_assistant_history(raw_resp: str, required_entities: List[str], tool_code: str) -> str:
    code = safe_str(tool_code).strip()
    if code:
        payload = {"required_entities": [safe_str(x) for x in (required_entities or [])[:40]]}
        if len(code) <= 2400:
            payload["tool_code"] = code
        else:
            payload["tool_code_excerpt"] = _safe_code_excerpt(code, max_chars=1800, max_lines=70)
            payload["note"] = "excerpt only; may be incomplete. regenerate complete code."
        return json.dumps(payload, ensure_ascii=False)
    return _clip_text_keep_head(raw_resp, 2200)


def _code_fingerprint(tool_code: str, raw_resp: str) -> str:
    txt = safe_str(tool_code).strip() or safe_str(raw_resp).strip()
    if not txt:
        return ""
    return hashlib.md5(txt.encode("utf-8", errors="ignore")).hexdigest()


def _trim_messages_by_char_budget(messages: List[Dict[str, str]], max_total_chars: int) -> List[Dict[str, str]]:
    if not messages:
        return []

    def _limit_for_role(role: str) -> int:
        if role == "system":
            return 1200
        if role == "assistant":
            return 2600
        return 4200

    trimmed: List[Dict[str, str]] = []
    for m in messages:
        role = safe_str(m.get("role")).strip() or "user"
        content = _clip_text_keep_head(m.get("content", ""), _limit_for_role(role))
        trimmed.append({"role": role, "content": content})

    total = sum(len(x.get("content", "")) for x in trimmed)
    if total <= max_total_chars:
        return trimmed

    head = trimmed[:2]
    budget = max_total_chars - sum(len(x.get("content", "")) for x in head)
    if budget <= 600:
        out = list(head[:1])
        if len(trimmed) >= 2:
            out.append(
                {
                    "role": head[1].get("role", "user"),
                    "content": _clip_text_keep_head(head[1].get("content", ""), max(300, max_total_chars - 300)),
                }
            )
        return out

    tail: List[Dict[str, str]] = []
    for m in reversed(trimmed[2:]):
        c = m.get("content", "")
        if len(c) <= budget:
            tail.append(m)
            budget -= len(c)
            continue
        if budget > 500:
            tail.append({"role": m.get("role", "user"), "content": _clip_text_keep_head(c, budget)})
            budget = 0
        break

    tail.reverse()
    return head + tail


def _calc_sort_key(cid: str) -> Tuple[int, str]:
    x = _safe_int(cid)
    return (x if x is not None else 10**9, cid)


def _build_calc_prompt_profile(
    rows: List[Dict[str, Any]],
    sampled: List[Dict[str, Any]],
    rng: random.Random,
) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    output_type = safe_str(rows[0].get("Output Type", "")).strip() if rows else ""
    key_counter: Dict[str, int] = {}
    for r in rows:
        rel = _parse_entities(r.get("Relevant Entities", ""))
        for k in rel.keys():
            kk = safe_str(k).strip()
            if not kk:
                continue
            key_counter[kk] = key_counter.get(kk, 0) + 1
    known_keys = [k for k, _ in sorted(key_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:30]]

    sampled_ids = {safe_str(r.get("Row Number")) for r in sampled}
    candidates = [r for r in rows if safe_str(r.get("Row Number")) not in sampled_ids]
    if not candidates:
        candidates = rows
    ex_k = min(2, len(candidates))
    ex_rows = rng.sample(candidates, k=ex_k) if ex_k > 0 else []
    train_examples: List[Dict[str, Any]] = []
    for r in ex_rows:
        rel = _parse_entities(r.get("Relevant Entities", ""))
        train_examples.append(
            {
                "relevant_entities_json": json.dumps(rel, ensure_ascii=False),
                "ground_truth_answer": safe_str(r.get("Ground Truth Answer")),
                "lower_limit": safe_str(r.get("Lower Limit")),
                "upper_limit": safe_str(r.get("Upper Limit")),
            }
        )
    return output_type, known_keys, train_examples

def main() -> None:
    parser = argparse.ArgumentParser()
    project_root = os.getcwd()
    parser.add_argument(
        "--train_csv",
        type=str,
        default=os.path.join(project_root, "data", "processed", "train_data.csv"),
    )
    parser.add_argument(
        "--stage1_docs_jsonl",
        type=str,
        default=os.path.join(project_root, "data", "processed", "stage1_tool_builder.jsonl"),
    )
    parser.add_argument(
        "--tools_dir",
        type=str,
        default=os.path.join(project_root, "artifacts", "calculators", "gpt_5_5"),
    )
    parser.add_argument(
        "--meta_dir",
        type=str,
        default=os.path.join(project_root, "artifacts", "tool_builder", "meta"),
    )
    parser.add_argument(
        "--output_tool_dir",
        type=str,
        default=os.path.join(project_root, "artifacts", "tool_builder", "output"),
    )
    parser.add_argument(
        "--result_dir",
        type=str,
        default=os.path.join(project_root, "artifacts", "tool_builder", "results"),
    )
    parser.add_argument(
        "--embedding_model_path",
        type=str,
        default=os.path.join(project_root, "models", "bge-base-en-v1.5"),
    )
    parser.add_argument("--builder_llm_name", type=str, default="Qwen3-8B")
    parser.add_argument(
        "--builder_model_path",
        type=str,
        default=os.path.join(project_root, "models", "Qwen3-8B"),
    )
    parser.add_argument("--sample_per_calc", type=int, default=8)
    parser.add_argument("--max_rounds", type=int, default=5)
    parser.add_argument("--rag_top_k", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260415)
    parser.add_argument("--max_calculators", type=int, default=0)
    parser.add_argument("--only_calc_ids", type=str, default="")
    parser.add_argument("--skip_calc_ids", type=str, default="")
    parser.add_argument("--max_input_tokens", type=int, default=8192)
    parser.add_argument("--max_new_tokens", type=int, default=1000)
    parser.add_argument("--enforce_eager", type=int, default=1)
    parser.add_argument("--gpu_memory_utilization", type=float, default=0.8)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=1.0)
    parser.add_argument("--enable_thinking", type=str, default="false")
    parser.add_argument("--tensor_parallel_size", type=int, default=1)
    parser.add_argument("--tool_exec_timeout_sec", type=int, default=3)
    parser.add_argument("--dialogue_output_jsonl", type=str, default="")
    parser.add_argument("--final_result_jsonl", type=str, default="")
    parser.add_argument("--overall_summary_json", type=str, default="")
    parser.add_argument("--clear_stream_files", type=int, default=0)
    parser.add_argument("--persist_internal_logs", type=int, default=0)
    parser.add_argument("--run_name", type=str, default="")
    args = parser.parse_args()

    ensure_dir(args.tools_dir)
    ensure_dir(args.meta_dir)
    ensure_dir(args.output_tool_dir)
    ensure_dir(args.result_dir)

    run_name = args.run_name.strip() or f"stage1_tool_loop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    rounds_jsonl = os.path.join(args.result_dir, f"{run_name}_rounds.jsonl")
    per_calc_jsonl = os.path.join(args.output_tool_dir, f"{run_name}_per_calc.jsonl")
    summary_json = os.path.join(args.output_tool_dir, f"{run_name}_summary.json")
    dialogue_output_jsonl = (
        args.dialogue_output_jsonl.strip()
        or os.path.join(args.output_tool_dir, "dialogue_rounds.jsonl")
    )
    final_result_jsonl = (
        args.final_result_jsonl.strip()
        or os.path.join(args.result_dir, "final_accuracy_by_calculator.jsonl")
    )
    overall_summary_json = (
        args.overall_summary_json.strip()
        or os.path.join(args.result_dir, "summary.json")
    )
    if int(args.clear_stream_files) == 1:
        for p in [dialogue_output_jsonl, final_result_jsonl, overall_summary_json]:
            if os.path.exists(p):
                os.remove(p)

    train_rows = load_csv_rows(args.train_csv)
    by_calc: Dict[str, List[Dict[str, Any]]] = {}
    for row in train_rows:
        cid = calc_id(row)
        if not cid:
            continue
        by_calc.setdefault(cid, []).append(row)
    calc_ids = sorted(by_calc.keys(), key=_calc_sort_key)
    only_set = {x.strip() for x in safe_str(args.only_calc_ids).split(",") if x.strip()}
    skip_set = {x.strip() for x in safe_str(args.skip_calc_ids).split(",") if x.strip()}
    if only_set:
        calc_ids = [x for x in calc_ids if x in only_set]
    if skip_set:
        calc_ids = [x for x in calc_ids if x not in skip_set]
    if int(args.max_calculators) > 0:
        calc_ids = calc_ids[: int(args.max_calculators)]
    if not calc_ids:
        raise RuntimeError("no calculators found in train set")

    llm = local_vllm(
        llm_name=args.builder_llm_name,
        model_path=args.builder_model_path,
        max_input_tokens=args.max_input_tokens,
        max_new_tokens=args.max_new_tokens,
        tensor_parallel_size=max(1, int(args.tensor_parallel_size)),
        enforce_eager=bool(int(args.enforce_eager)),
        gpu_memory_utilization=args.gpu_memory_utilization,
        temperature=args.temperature,
        top_p=args.top_p,
        enable_thinking=(str(args.enable_thinking).lower() == "true"),
    )

    stage1_docs = load_jsonl(args.stage1_docs_jsonl)
    if not stage1_docs:
        raise RuntimeError(f"empty stage1 rag docs: {args.stage1_docs_jsonl}")
    rag = MedicalRAG(stage1_docs, embedding_model_path=args.embedding_model_path, use_embedding=True)

    total_sample_cases = 0
    total_sample_correct = 0
    total_best_sample_correct = 0
    total_calc_success = 0
    per_calc_rows: List[Dict[str, Any]] = []

    for idx, cid in enumerate(calc_ids, 1):
        rows = by_calc[cid]
        calc_name = safe_str(rows[0].get("Calculator Name", "")).strip()
        cid_seed = _safe_int(cid) if _safe_int(cid) is not None else sum(ord(c) for c in cid)
        rng = random.Random(args.seed + int(cid_seed))
        k = min(max(1, int(args.sample_per_calc)), len(rows))
        sampled = rng.sample(rows, k=k)
        output_type, known_keys, train_examples = _build_calc_prompt_profile(rows, sampled, rng)

        query = (
            f"{calc_name}. Build an executable calculator function with exact formula/rules, "
            "required inputs, and edge conditions."
        )
        refs = rag.retrieve(query=query, calculator_id=cid, top_k=args.rag_top_k)

        best_round = 0
        best_correct = -1
        best_code = ""
        best_required: List[str] = []
        final_status = "failed"
        last_error_report = "not_started"
        first_round_acc = 0.0
        last_round_acc = 0.0
        last_round_correct = 0
        last_round_idx = 0

        prev_code = ""
        prev_code_fp = ""
        same_code_streak = 0
        prev_compile_error = ""
        same_compile_streak = 0
        no_improve_streak = 0
        base_messages = stage1_build_tool_prompt(
            cid,
            calc_name,
            refs,
            output_type=output_type,
            known_keys=known_keys,
            train_examples=train_examples,
        )
        next_round_user_message = ""

        print(f"[{now_str()}] [stage1] calc={cid} name={calc_name} sampled={k} start")
        for round_i in range(1, max(1, int(args.max_rounds)) + 1):
            if round_i == 1 or not next_round_user_message:
                messages = list(base_messages)
            else:
                messages = [base_messages[0], base_messages[1], {"role": "user", "content": next_round_user_message}]
            char_budget = max(10000, int(args.max_input_tokens) * 3 // 2)
            messages = _trim_messages_by_char_budget(messages, max_total_chars=char_budget)
            raw_resp = llm.answer(messages)
            required_entities, tool_code = _extract_tool_payload(raw_resp)
            first_obj = extract_first_json(raw_resp)
            format_retry_attempted = False
            format_retry_used = False
            if (not tool_code) or (not isinstance(first_obj, dict)):
                format_retry_attempted = True
                retry_user = {
                    "role": "user",
                    "content": (
                        "FORMAT RETRY (single retry): your previous output was empty_code or invalid JSON.\n"
                        "Return STRICT JSON only with keys required_entities/fix_plan/tool_code.\n"
                        "tool_code must be plain Python source starting with: def calc(relevant):\n"
                        "No markdown, no extra keys, no prose."
                    ),
                }
                retry_messages = _trim_messages_by_char_budget(messages + [retry_user], max_total_chars=char_budget)
                raw_retry = llm.answer(retry_messages)
                req2, code2 = _extract_tool_payload(raw_retry)
                if code2:
                    raw_resp = raw_retry
                    required_entities = req2
                    tool_code = code2
                    format_retry_used = True

            fn, compile_error = _compile_tool(tool_code)
            eval_rows: List[Dict[str, Any]] = []
            correct_n = 0

            if fn is not None:
                for sr in sampled:
                    relevant = _parse_entities(sr.get("Relevant Entities", ""))
                    pred, runtime_error = _run_tool(fn, relevant, timeout_sec=int(args.tool_exec_timeout_sec))
                    ok = False
                    reason = runtime_error if runtime_error else ""
                    if not runtime_error:
                        ok, reason = _judge(sr, pred)
                    if ok:
                        correct_n += 1
                    eval_rows.append(
                        {
                            "row_number": safe_str(sr.get("Row Number")),
                            "ok": bool(ok),
                            "reason": reason,
                            "pred": pred,
                            "gt": sr.get("Ground Truth Answer"),
                            "low": sr.get("Lower Limit"),
                            "high": sr.get("Upper Limit"),
                            "relevant": relevant,
                        }
                    )

            all_pass = (fn is not None) and (correct_n == len(sampled))
            round_acc = (correct_n / len(sampled)) if sampled else 0.0
            if round_i == 1:
                first_round_acc = round_acc
            last_round_acc = round_acc
            last_round_correct = correct_n
            last_round_idx = round_i
            err_report = _error_report(compile_error, eval_rows)
            last_error_report = err_report

            round_record = {
                "run_name": run_name,
                "timestamp": now_str(),
                "calculator_id": cid,
                "calculator_name": calc_name,
                "round": round_i,
                "sample_count": len(sampled),
                "correct_count": correct_n,
                "all_pass": all_pass,
                "compile_error": compile_error,
                "format_retry_attempted": bool(format_retry_attempted),
                "format_retry_used": bool(format_retry_used),
                "error_report_for_next_round": err_report,
                "prompt_messages": messages,
                "llm_response_raw": raw_resp,
                "parsed_required_entities": required_entities,
                "parsed_tool_code": tool_code,
                "sample_eval": eval_rows,
            }
            if int(args.persist_internal_logs) == 1:
                append_jsonl(rounds_jsonl, [round_record])

            samples_out: List[Dict[str, Any]] = []
            for x in eval_rows:
                samples_out.append(
                    {
                        "Row Number": x.get("row_number"),
                        "Relevant Entities": x.get("relevant"),
                        "tool_result": x.get("pred"),
                        "Ground Truth Answer": x.get("gt"),
                        "Lower Limit": x.get("low"),
                        "Upper Limit": x.get("high"),
                        "is_correct": bool(x.get("ok")),
                        "reason": x.get("reason"),
                    }
                )
            dialogue_record = {
                "run_name": run_name,
                "timestamp": now_str(),
                "Calculator ID": cid,
                "Calculator Name": calc_name,
                "round": round_i,
                "prompt": messages,
                "llm_answer": raw_resp,
                "round_samples": samples_out,
                "round_correct": correct_n,
                "round_total": len(sampled),
                "round_accuracy": round_acc,
                "first_round_overall_accuracy": first_round_acc,
                "all_correct_this_round": all_pass,
                "compile_error": compile_error,
                "format_retry_attempted": bool(format_retry_attempted),
                "format_retry_used": bool(format_retry_used),
            }
            append_jsonl(dialogue_output_jsonl, [dialogue_record])
            print(
                f"[{now_str()}] [stage1] calc={cid} round={round_i} "
                f"correct={correct_n}/{len(sampled)} pass={all_pass} compile_error={compile_error}"
            )

            improved_this_round = correct_n > best_correct
            if improved_this_round:
                best_correct = correct_n
                best_round = round_i
                best_code = tool_code
                best_required = required_entities
                no_improve_streak = 0
            else:
                no_improve_streak += 1

            fp = _code_fingerprint(tool_code=tool_code, raw_resp=raw_resp)
            if fp and fp == prev_code_fp:
                same_code_streak += 1
            else:
                same_code_streak = 0
            prev_code_fp = fp

            ce = safe_str(compile_error).strip()
            if ce and ce == prev_compile_error:
                same_compile_streak += 1
            elif ce:
                same_compile_streak = 1
            else:
                same_compile_streak = 0
            prev_compile_error = ce

            if all_pass:
                final_status = "success"
                break

            patch_mode = (len(sampled) > 0) and (correct_n / len(sampled) >= 0.7) and (not bool(compile_error))
            feedback_user = _build_followup_user_message(
                round_i=round_i,
                sample_total=len(sampled),
                correct_n=correct_n,
                compile_error=compile_error,
                error_report=err_report,
                previous_code=(tool_code or prev_code),
                eval_rows=eval_rows,
                same_code_streak=same_code_streak,
                same_compile_streak=same_compile_streak,
                no_improve_streak=no_improve_streak,
                patch_mode=patch_mode,
            )
            hard_reset = (bool(compile_error) and same_compile_streak >= 2) or (
                (not bool(compile_error)) and same_code_streak >= 2 and no_improve_streak >= 3
            )
            if patch_mode:
                hard_reset = False
            if hard_reset:
                next_round_user_message = (
                    "Recovery mode: repeated same error/behavior detected.\n"
                    "Rewrite tool_code from scratch based on calculator rules and failed rows.\n"
                    "Do not reuse previous broken structure.\n\n"
                    f"{feedback_user}"
                )
            else:
                next_round_user_message = feedback_user
            prev_code = tool_code if tool_code else prev_code

        if not best_code:
            best_code = "def calc(relevant):\n    return 'N/A'\n"

        tool_path = os.path.join(args.tools_dir, f"calculator_{cid}.py")
        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(best_code if best_code.endswith("\n") else best_code + "\n")

        meta = {
            "run_name": run_name,
            "timestamp": now_str(),
            "calculator_id": cid,
            "calculator_name": calc_name,
            "final_status": final_status,
            "best_round": best_round,
            "best_correct": best_correct,
            "sample_count": len(sampled),
            "best_required_entities": best_required,
            "last_error_report": last_error_report,
            "tool_path": tool_path,
            "rounds_log": rounds_jsonl,
        }
        with open(os.path.join(args.meta_dir, f"calculator_{cid}.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        out_row = {
            "run_name": run_name,
            "calculator_id": cid,
            "calculator_name": calc_name,
            "status": final_status,
            "best_round": best_round,
            "best_correct": best_correct,
            "sample_count": len(sampled),
            "best_sample_acc": (best_correct / len(sampled)) if sampled else 0.0,
            "tool_path": tool_path,
        }
        if int(args.persist_internal_logs) == 1:
            append_jsonl(per_calc_jsonl, [out_row])
        per_calc_rows.append(out_row)

        total_sample_cases += len(sampled)
        total_sample_correct += max(0, int(last_round_correct))
        total_best_sample_correct += max(0, int(best_correct))
        if final_status == "success":
            total_calc_success += 1

        append_jsonl(
            final_result_jsonl,
            [
                {
                    "run_name": run_name,
                    "timestamp": now_str(),
                    "Calculator ID": cid,
                    "Calculator Name": calc_name,
                    "final_round": int(last_round_idx),
                    "final_round_correct": int(last_round_correct),
                    "final_round_total": int(len(sampled)),
                    "final_round_accuracy": float(last_round_acc),
                    "best_round": int(best_round),
                    "best_round_correct": int(best_correct),
                    "best_round_accuracy": (float(best_correct) / float(len(sampled))) if sampled else 0.0,
                    "status": final_status,
                }
            ],
        )
        print(
            f"[{now_str()}] [stage1] calc={cid} finished status={final_status} "
            f"best={best_correct}/{len(sampled)}"
        )

    summary = {
        "run_name": run_name,
        "timestamp": now_str(),
        "train_csv": args.train_csv,
        "stage1_docs_jsonl": args.stage1_docs_jsonl,
        "total_calculators": len(calc_ids),
        "successful_calculators": total_calc_success,
        "calculator_success_rate": (total_calc_success / len(calc_ids)) if calc_ids else 0.0,
        "sampled_cases_total": total_sample_cases,
        "sampled_cases_correct": total_sample_correct,
        "sampled_case_accuracy": (total_sample_correct / total_sample_cases) if total_sample_cases else 0.0,
        "best_sampled_cases_correct": total_best_sample_correct,
        "best_sampled_case_accuracy": (total_best_sample_correct / total_sample_cases) if total_sample_cases else 0.0,
        "dialogue_output_jsonl": dialogue_output_jsonl,
        "final_result_jsonl": final_result_jsonl,
    }
    with open(overall_summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if int(args.persist_internal_logs) == 1:
        with open(summary_json, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
