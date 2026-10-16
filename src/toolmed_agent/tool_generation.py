import ast
import json
import math
import re
import signal
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .prompts import build_tool_synthesis_messages, calculator_schema
from .utils import LLMRouter, extract_first_json_object, parse_entities, safe_float, safe_str


def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None


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


def _safe_code_check(code: str) -> Tuple[bool, str]:
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
    ok, reason = _safe_code_check(code)
    if not ok:
        return None, reason

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


def _extract_code(answer: str) -> str:
    obj = extract_first_json_object(answer)
    if isinstance(obj, dict):
        c = safe_str(obj.get("tool_code", "")).strip()
        if c:
            if "\\n" in c and "\n" not in c:
                c = c.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\t", "    ")
            return c

    m = re.search(r"(?is)```(?:python)?\s*(.*?)```", safe_str(answer))
    if m:
        cand = safe_str(m.group(1)).strip()
        if "def calc(" in cand:
            return cand

    m2 = re.search(r"(?is)\bdef\s+calc\s*\(\s*relevant\s*\)\s*:\s*.*", safe_str(answer))
    return safe_str(m2.group(0)).strip() if m2 else ""


def _extract_required_entities(answer: str) -> List[str]:
    obj = extract_first_json_object(answer)
    out: List[str] = []
    if isinstance(obj, dict) and isinstance(obj.get("required_entities"), list):
        for x in obj.get("required_entities", []):
            v = safe_str(x).strip()
            if v:
                out.append(v)
        if out:
            return out

    m = re.search(r"(?is)required_entities\s*[:=]\s*\[(.*?)\]", safe_str(answer))
    if m:
        raw = "{" + f'"required_entities": [{m.group(1)}]' + "}"
        obj2 = parse_entities(raw)
        if isinstance(obj2.get("required_entities"), list):
            return [safe_str(x).strip() for x in obj2["required_entities"] if safe_str(x).strip()]
    return out


def _extract_tool_payload(raw_resp: str) -> Tuple[List[str], str]:
    required = _extract_required_entities(raw_resp)
    tool_code = _extract_code(raw_resp)
    return required[:80], safe_str(tool_code).strip()


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


def _failed_rows_text(eval_rows: List[Dict[str, Any]], max_rows: int = 4) -> str:
    fails = [x for x in eval_rows if not x.get("ok")]
    if not fails:
        return "(none)"
    lines: List[str] = []
    for x in fails[:max_rows]:
        lines.append(
            "row={row}; reason={reason}; pred={pred}; gt={gt}; range=[{low},{high}]; relevant={rel}".format(
                row=safe_str(x.get("row_number")),
                reason=safe_str(x.get("reason")),
                pred=safe_str(x.get("pred"))[:120],
                gt=safe_str(x.get("gt"))[:120],
                low=safe_str(x.get("low")),
                high=safe_str(x.get("high")),
                rel=safe_str(x.get("relevant"))[:400],
            )
        )
    return "\n".join(lines)


def _build_calc_prompt_profile(sample_eval_rows: List[Dict[str, Any]]) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    output_type = safe_str(sample_eval_rows[0].get("Output Type", "")).strip() if sample_eval_rows else ""

    key_counter: Dict[str, int] = {}
    for row in sample_eval_rows:
        rel = parse_entities(row.get("Relevant Entities", ""))
        for k in rel.keys():
            kk = safe_str(k).strip()
            if kk:
                key_counter[kk] = key_counter.get(kk, 0) + 1
    known_keys = [k for k, _ in sorted(key_counter.items(), key=lambda kv: (-kv[1], kv[0]))[:30]]

    train_examples: List[Dict[str, Any]] = []
    for row in sample_eval_rows[:2]:
        rel = parse_entities(row.get("Relevant Entities", ""))
        train_examples.append(
            {
                "relevant_entities_json": rel,
                "ground_truth_answer": safe_str(row.get("Ground Truth Answer", "")),
                "lower_limit": safe_str(row.get("Lower Limit", "")),
                "upper_limit": safe_str(row.get("Upper Limit", "")),
            }
        )
    return output_type, known_keys, train_examples


def _join_context_snippets(rule_text: str, case_examples: List[Dict[str, Any]], max_chars: int = 4800) -> str:
    parts: List[str] = []
    txt = safe_str(rule_text).strip()
    if txt:
        parts.append(f"[Ref 1] rules\n{txt[:3600]}")

    for i, ex in enumerate(case_examples[:3], start=2):
        parts.append(
            "\n".join(
                [
                    f"[Ref {i}] few-shot",
                    f"question={safe_str(ex.get('question', ''))}",
                    f"relevant={safe_str(ex.get('relevant_entities', {}))}",
                ]
            )
        )

    out = "\n\n".join(parts).strip()
    return out[:max_chars]


def _stage1_build_tool_prompt(
    calculator_id: str,
    calculator_name: str,
    context_text: str,
    output_type: str,
    known_keys: List[str],
    train_examples: List[Dict[str, Any]],
    schema: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    return build_tool_synthesis_messages(
        calculator_id, calculator_name, output_type, context_text,
        schema if schema is not None else calculator_schema(calculator_id), train_examples,
    )


def _build_followup_user_message(
    round_i: int,
    sample_total: int,
    correct_n: int,
    compile_error: str,
    error_report: str,
    previous_code: str,
    eval_rows: List[Dict[str, Any]],
) -> str:
    failed_txt = _failed_rows_text(eval_rows, max_rows=4)
    compile_txt = safe_str(compile_error).strip() or "none"
    return (
        f"Round {round_i} feedback for the same calculator.\n"
        "Write improved tool_code using the initial calculator rules and previous failures only.\n\n"
        f"Previous round summary: sampled_correct={correct_n}/{sample_total}; compile_error={compile_txt}.\n"
        f"error_report: {error_report}\n\n"
        "Previous tool code:\n"
        f"{safe_str(previous_code)[:3000]}\n\n"
        "Previous failed rows:\n"
        f"{failed_txt}\n\n"
        "Return STRICT JSON only:\n"
        "{\n"
        '  "required_entities": ["key1", "key2"],\n'
        '  "fix_plan": "one short sentence",\n'
        '  "tool_code": "def calc(relevant):\\n    ..."\n'
        "}"
    )


class FormulaWriter:
    def __init__(
        self,
        llm: LLMRouter,
        max_rounds: int = 5,
        max_new_tokens: int = 1800,
        tool_exec_timeout_sec: int = 3,
    ):
        self.llm = llm
        self.max_rounds = max(1, int(max_rounds))
        self.max_new_tokens = max(200, int(max_new_tokens))
        self.tool_exec_timeout_sec = max(1, int(tool_exec_timeout_sec))

    @staticmethod
    def _fallback_tool(required_hint: List[str], error_msg: str = "") -> Dict[str, Any]:
        keys = [safe_str(x).strip() for x in required_hint if safe_str(x).strip()]
        code = (
            "def calc(relevant):\n"
            "    if not isinstance(relevant, dict):\n"
            "        return 'N/A'\n"
            "    return 'N/A'\n"
        )
        return {
            "required_entities": keys,
            "tool_code": code,
            "source": "fallback",
            "error": error_msg or "llm_unavailable_or_invalid",
            "rounds": [],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "calls": 0,
            },
        }

    def build_tool(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
        rule_doc: Dict[str, Any],
        case_examples: List[Dict[str, Any]],
        sample_eval_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        cid = safe_str(calculator_id).strip()
        rule_text = json.dumps(
            rule_doc.get("rule_specification") or {
                key: rule_doc[key] for key in (
                    "formula", "inputs", "instructions", "evidence_text", "text",
                ) if key in rule_doc
            }, ensure_ascii=False,
        )[:9000]
        context_text = _join_context_snippets(rule_text=rule_text, case_examples=case_examples)
        output_type, known_keys, train_examples = _build_calc_prompt_profile(sample_eval_rows)

        messages_base = _stage1_build_tool_prompt(
            calculator_id=cid,
            calculator_name=safe_str(calculator_name),
            context_text=context_text,
            output_type=output_type,
            known_keys=known_keys,
            train_examples=train_examples,
            schema=rule_doc.get("schema") or calculator_schema(cid),
        )

        if not self.llm.available:
            return self._fallback_tool([], error_msg=f"llm_unavailable:{self.llm.init_error}")

        best_required: List[str] = []
        best_code = ""
        best_correct = -1
        final_error = ""
        rounds_log: List[Dict[str, Any]] = []

        usage_prompt = 0
        usage_completion = 0
        usage_total = 0
        usage_calls = 0

        next_feedback = ""
        prev_code = ""

        for round_i in range(1, self.max_rounds + 1):
            if round_i == 1 or not next_feedback:
                messages = list(messages_base)
            else:
                messages = [messages_base[0], messages_base[1], {"role": "user", "content": next_feedback}]

            # 1st call
            try:
                chat = self.llm.chat(messages=messages, max_tokens=self.max_new_tokens, temperature=0.0, top_p=1.0)
                ans = chat.text
                usage_prompt += int(chat.usage.get("prompt_tokens", 0) or 0)
                usage_completion += int(chat.usage.get("completion_tokens", 0) or 0)
                usage_total += int(chat.usage.get("total_tokens", 0) or 0)
                usage_calls += 1
            except Exception as e:
                final_error = f"llm_error_round_{round_i}:{type(e).__name__}:{e}"
                break

            required, code = _extract_tool_payload(ans)

            # format retry
            format_retry_used = False
            first_obj = extract_first_json_object(ans)
            if (not code) or (not isinstance(first_obj, dict)):
                retry_messages = messages + [
                    {
                        "role": "user",
                        "content": (
                            "FORMAT RETRY (single retry): previous output was invalid JSON or empty_code.\n"
                            "Return STRICT JSON only with keys required_entities/fix_plan/tool_code.\n"
                            "tool_code must start with: def calc(relevant):"
                        ),
                    }
                ]
                try:
                    chat2 = self.llm.chat(
                        messages=retry_messages,
                        max_tokens=min(1200, self.max_new_tokens),
                        temperature=0.0,
                        top_p=1.0,
                    )
                    ans2 = chat2.text
                    usage_prompt += int(chat2.usage.get("prompt_tokens", 0) or 0)
                    usage_completion += int(chat2.usage.get("completion_tokens", 0) or 0)
                    usage_total += int(chat2.usage.get("total_tokens", 0) or 0)
                    usage_calls += 1

                    req2, code2 = _extract_tool_payload(ans2)
                    if code2:
                        ans = ans2
                        required = req2
                        code = code2
                        format_retry_used = True
                except Exception:
                    pass

            fn, compile_error = _compile_tool(code)
            eval_rows: List[Dict[str, Any]] = []
            correct_n = 0
            if fn is not None:
                for sr in sample_eval_rows:
                    relevant = parse_entities(sr.get("Relevant Entities", ""))
                    pred, runtime_error = _run_tool(fn, relevant, timeout_sec=self.tool_exec_timeout_sec)
                    ok = False
                    reason = runtime_error if runtime_error else ""
                    if not runtime_error:
                        ok, reason = _judge(sr, pred)
                    if ok:
                        correct_n += 1
                    eval_rows.append(
                        {
                            "row_number": safe_str(sr.get("Row Number", "")),
                            "ok": bool(ok),
                            "reason": reason,
                            "pred": pred,
                            "gt": sr.get("Ground Truth Answer"),
                            "low": sr.get("Lower Limit"),
                            "high": sr.get("Upper Limit"),
                            "relevant": relevant,
                        }
                    )

            all_pass = (fn is not None) and (correct_n == len(sample_eval_rows))
            round_acc = (correct_n / len(sample_eval_rows)) if sample_eval_rows else 0.0
            err_report = _error_report(compile_error, eval_rows)

            rounds_log.append(
                {
                    "round": round_i,
                    "correct": correct_n,
                    "total": len(sample_eval_rows),
                    "round_acc": round_acc,
                    "compile_error": compile_error,
                    "error_report": err_report,
                    "format_retry_used": format_retry_used,
                    "required_entities": required,
                }
            )

            if correct_n > best_correct:
                best_correct = correct_n
                best_code = code
                best_required = required

            if all_pass:
                final_error = ""
                break

            final_error = err_report
            next_feedback = _build_followup_user_message(
                round_i=round_i,
                sample_total=len(sample_eval_rows),
                correct_n=correct_n,
                compile_error=compile_error,
                error_report=err_report,
                previous_code=(code or prev_code),
                eval_rows=eval_rows,
            )
            prev_code = code if code else prev_code

        if not best_code:
            return self._fallback_tool(best_required, error_msg=final_error or "no_valid_tool_generated")

        ok, reason = _safe_code_check(best_code)
        if not ok:
            return self._fallback_tool(best_required, error_msg=f"invalid_best_tool:{reason};{final_error}".strip(";"))

        return {
            "required_entities": best_required,
            "tool_code": best_code,
            "source": "llm_stage1_loop",
            "error": final_error,
            "rounds": rounds_log,
            "usage": {
                "prompt_tokens": usage_prompt,
                "completion_tokens": usage_completion,
                "total_tokens": usage_total,
                "calls": usage_calls,
            },
        }
