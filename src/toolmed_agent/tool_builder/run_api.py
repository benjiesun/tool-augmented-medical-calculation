import argparse
import json
import os
import random
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, List, Tuple

from ..case_search import CaseSearcher
from ..memory import MemoryStore
from .common import append_jsonl, calc_id, ensure_dir, load_csv_rows, load_jsonl, now_str, safe_str
from .prompts import stage1_build_tool_prompt
from .rag import MedicalRAG
from .stage1_tool_loop import (
    _build_calc_prompt_profile,
    _build_followup_user_message,
    _calc_sort_key,
    _code_fingerprint,
    _compile_tool,
    _error_report,
    _extract_tool_payload,
    _judge,
    _parse_entities,
    _run_tool,
    _trim_messages_by_char_budget,
)

def _sanitize_tag(s: str) -> str:
    out = "".join(ch if ch.isalnum() else "-" for ch in safe_str(s).strip())
    while "--" in out:
        out = out.replace("--", "-")
    out = out.strip("-")
    return out or "model"


def _estimate_tokens_from_text(text: str) -> int:
    # Conservative fallback when provider response omits usage.
    return max(1, int(len(safe_str(text)) / 4))


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for x in content:
            if isinstance(x, dict):
                if "text" in x:
                    parts.append(safe_str(x.get("text")))
                elif safe_str(x.get("type")).strip().lower() == "text":
                    parts.append(safe_str(x.get("text")))
            else:
                parts.append(safe_str(x))
        return "".join(parts).strip()
    return safe_str(content)


class DashScopeCompatClient:
    def __init__(self, api_base: str, api_key: str, model: str, timeout_sec: int = 120, api_retries: int = 3):
        self.api_base = safe_str(api_base).rstrip("/")
        self.api_key = safe_str(api_key).strip()
        self.model = safe_str(model).strip()
        self.timeout_sec = max(10, int(timeout_sec))
        self.api_retries = max(1, int(api_retries))

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 900,
        temperature: float = 0.0,
        top_p: float = 1.0,
        enable_thinking: bool = False,
    ) -> Tuple[str, Dict[str, int], Dict[str, Any], bool]:
        url = f"{self.api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": int(max(1, max_tokens)),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "stream": False,
            # Some DashScope models may ignore this, but it is safe in compatible mode.
            "enable_thinking": bool(enable_thinking),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_err = ""
        for i in range(1, self.api_retries + 1):
            req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    text = resp.read().decode("utf-8", errors="ignore")
                obj = json.loads(text)
                choices = obj.get("choices", []) if isinstance(obj, dict) else []
                if not choices:
                    raise RuntimeError(f"empty choices in response: {text[:500]}")

                msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                answer = _content_to_text(msg.get("content"))

                usage_obj = obj.get("usage", {}) if isinstance(obj, dict) else {}
                prompt_tokens = int(
                    usage_obj.get("prompt_tokens")
                    or usage_obj.get("input_tokens")
                    or usage_obj.get("promptTokens")
                    or 0
                )
                completion_tokens = int(
                    usage_obj.get("completion_tokens")
                    or usage_obj.get("output_tokens")
                    or usage_obj.get("completionTokens")
                    or 0
                )
                total_tokens = int(
                    usage_obj.get("total_tokens")
                    or usage_obj.get("totalTokens")
                    or (prompt_tokens + completion_tokens)
                )

                usage_estimated = False
                if total_tokens <= 0:
                    prompt_est = _estimate_tokens_from_text(json.dumps(messages, ensure_ascii=False))
                    completion_est = _estimate_tokens_from_text(answer)
                    prompt_tokens = prompt_est
                    completion_tokens = completion_est
                    total_tokens = prompt_est + completion_est
                    usage_estimated = True

                usage = {
                    "prompt_tokens": int(prompt_tokens),
                    "completion_tokens": int(completion_tokens),
                    "total_tokens": int(total_tokens),
                }
                return answer, usage, obj, usage_estimated
            except urllib.error.HTTPError as e:
                try:
                    err_text = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    err_text = safe_str(e)
                last_err = f"HTTPError:{e.code}:{err_text[:500]}"
            except Exception as e:
                last_err = f"{type(e).__name__}:{e}"

            if i < self.api_retries:
                time.sleep(min(8, 1 + i * 2))

        raise RuntimeError(f"api_call_failed after retries: {last_err}")


def _build_rag_docs_if_needed(base_dir: str, python_bin: str, train_csv: str, force_rebuild: bool) -> str:
    rag_docs_dir = os.path.join(base_dir, "rag_docs")
    stage1_docs_jsonl = os.path.join(rag_docs_dir, "stage1_tool_builder.jsonl")
    if (not force_rebuild) and os.path.exists(stage1_docs_jsonl):
        return stage1_docs_jsonl

    builder_path = os.path.join(base_dir, "build_rag_docs.py")
    if not os.path.isfile(builder_path):
        raise RuntimeError(
            "The private RAG preparation script and captured rule corpus are "
            "not distributed in this repository. Supply a prepared, authorized "
            "corpus with --stage1_docs_jsonl, or provide the original private "
            "build_rag_docs.py and its input files in --base_dir. "
            "The public rule stub is not a complete tool-generation corpus."
        )

    ensure_dir(rag_docs_dir)
    cmd = [
        python_bin,
        builder_path,
        "--rules_jsonl",
        os.path.join(base_dir, "docs", "mdcalc_rules_v1.jsonl"),
        "--guide_build_md",
        os.path.join(base_dir, "docs", "tool_builder_guide.md"),
        "--guide_extract_md",
        os.path.join(base_dir, "docs", "parameter_extraction_guide.md"),
        "--guide_normalize_md",
        os.path.join(base_dir, "docs", "normalization_guide.md"),
        "--rag_docs_dir",
        rag_docs_dir,
        "--train_csv",
        train_csv,
    ]
    subprocess.run(cmd, check=True)
    if not os.path.exists(stage1_docs_jsonl):
        raise RuntimeError(f"failed to build stage1 rag docs: {stage1_docs_jsonl}")
    return stage1_docs_jsonl


def _select_calc_ids(
    by_calc: Dict[str, List[Dict[str, Any]]],
    only_calc_ids: str,
    skip_calc_ids: str,
    max_calculators: int,
) -> List[str]:
    calc_ids = sorted(by_calc.keys(), key=_calc_sort_key)
    only_set = {x.strip() for x in safe_str(only_calc_ids).split(",") if x.strip()}
    skip_set = {x.strip() for x in safe_str(skip_calc_ids).split(",") if x.strip()}
    if only_set:
        calc_ids = [x for x in calc_ids if x in only_set]
    if skip_set:
        calc_ids = [x for x in calc_ids if x not in skip_set]
    if int(max_calculators) > 0:
        calc_ids = calc_ids[: int(max_calculators)]
    return calc_ids


def _split_arg_list(value: str) -> List[str]:
    return [x.strip() for x in safe_str(value).replace("\n", ",").split(",") if x.strip()]


def _calculator_id_from_tool_path(path: str) -> str:
    name = os.path.basename(safe_str(path).strip())
    if not (name.startswith("calculator_") and name.endswith(".py")):
        return ""
    stem = name[: -len(".py")]
    cid = stem[len("calculator_") :]
    if "_cycle" in cid:
        cid = cid.split("_cycle", 1)[0]
    return cid.strip()


def _copy_resume_tool(src_path: str, run_tools_dir: str, calculator_id: str) -> str:
    src_path = safe_str(src_path).strip()
    cid = safe_str(calculator_id).strip() or _calculator_id_from_tool_path(src_path)
    if not cid or not src_path or not os.path.exists(src_path):
        return ""
    dest_path = os.path.join(run_tools_dir, f"calculator_{cid}_cycle1.py")
    shutil.copy2(src_path, dest_path)
    return dest_path


def _collect_resume_tools_from_dirs(resume_tools_dir: str) -> Dict[str, str]:
    resume_map: Dict[str, str] = {}
    for tools_dir in _split_arg_list(resume_tools_dir):
        if not os.path.isdir(tools_dir):
            print(f"[{now_str()}] resume warning: tools_dir not found: {tools_dir}")
            continue
        for name in sorted(os.listdir(tools_dir)):
            path = os.path.join(tools_dir, name)
            if not os.path.isfile(path):
                continue
            cid = _calculator_id_from_tool_path(path)
            if cid:
                resume_map[cid] = path
    return resume_map


def _collect_resume_tools_from_results(resume_result_jsonl: str) -> Dict[str, str]:
    resume_map: Dict[str, str] = {}
    for result_path in _split_arg_list(resume_result_jsonl):
        if not os.path.exists(result_path):
            print(f"[{now_str()}] resume warning: result_jsonl not found: {result_path}")
            continue
        for row in load_jsonl(result_path):
            status = safe_str(row.get("status")).strip().lower()
            if status != "success":
                continue
            tool_path = safe_str(row.get("tool_path")).strip()
            cid = safe_str(row.get("Calculator ID") or row.get("calculator_id")).strip()
            if not cid:
                cid = _calculator_id_from_tool_path(tool_path)
            if cid and tool_path and os.path.exists(tool_path):
                # Later result files in the comma-separated list override earlier ones.
                resume_map[cid] = tool_path
    return resume_map


def _prepare_resume_tools(
    resume_result_jsonl: str,
    resume_tools_dir: str,
    run_tools_dir: str,
) -> Dict[str, str]:
    resume_map = _collect_resume_tools_from_dirs(resume_tools_dir)
    resume_map.update(_collect_resume_tools_from_results(resume_result_jsonl))

    copied: Dict[str, str] = {}
    for cid in sorted(resume_map.keys(), key=_calc_sort_key):
        dest = _copy_resume_tool(resume_map[cid], run_tools_dir, cid)
        if dest:
            copied[cid] = dest
    return copied


def _norm_cid(v: Any) -> str:
    s = safe_str(v).strip()
    try:
        return str(int(float(s)))
    except Exception:
        return s


def _memory_rule_to_snippet(rule: Dict[str, Any]) -> Dict[str, Any]:
    parts = []
    for label, key in (
        ("Formula/Rules", "formula"),
        ("Inputs", "inputs"),
        ("Instructions", "instructions"),
        ("Evidence", "evidence_text"),
    ):
        txt = safe_str(rule.get(key, "")).strip()
        if txt:
            parts.append(f"{label}: {txt}")
    text = "\n\n".join(parts).strip()
    return {
        "calculator_id": _norm_cid(rule.get("calculator_id", "")),
        "title": safe_str(rule.get("calculator_name") or rule.get("mdcalc_title", "")),
        "source": safe_str(rule.get("source", "medagent_memory_rule")) or "medagent_memory_rule",
        "text": text,
    }


def _case_examples_to_snippets(case_examples: List[Dict[str, Any]], max_items: int = 3) -> List[Dict[str, Any]]:
    snippets: List[Dict[str, Any]] = []
    for i, ex in enumerate(case_examples[: max(0, int(max_items))], 1):
        text = "\n".join(
            [
                "Retrieved case example from medagent case retriever.",
                f"question={safe_str(ex.get('question', ''))}",
                f"relevant_entities={safe_str(ex.get('relevant_entities', {}))}",
                f"train_row_number={safe_str(ex.get('train_row_number', ''))}",
                f"train_note_id={safe_str(ex.get('train_note_id', ''))}",
            ]
        )
        snippets.append(
            {
                "calculator_id": _norm_cid(ex.get("calculator_id", "")),
                "title": f"case_retriever_example_{i}",
                "source": "medagent_case_retriever",
                "text": text,
            }
        )
    return snippets


def _feedback_hint_to_snippet(calculator_id: Any, feedback_hint: str) -> List[Dict[str, Any]]:
    hint = safe_str(feedback_hint).strip()
    if not hint:
        return []
    return [
        {
            "calculator_id": _norm_cid(calculator_id),
            "title": "tool_build_feedback_memory",
            "source": "medagent_tool_build_feedback_memory",
            "text": (
                "Prior tool build validation failures for this calculator from medagent memory. "
                "Use these to avoid repeating known formula, branch, alias, parsing, and unit mistakes.\n"
                f"{hint}"
            ),
        }
    ]


def _failed_cases_for_memory(eval_rows: List[Dict[str, Any]], max_items: int = 8) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for x in eval_rows:
        if x.get("ok"):
            continue
        out.append(
            {
                "row_number": safe_str(x.get("row_number", "")),
                "reason": safe_str(x.get("reason", "")),
                "pred": x.get("pred"),
                "gt": x.get("gt"),
                "low": x.get("low"),
                "high": x.get("high"),
                "relevant": x.get("relevant", {}),
            }
        )
        if len(out) >= max(1, int(max_items)):
            break
    return out


def _chat_once_with_optional_format_retry(
    client: DashScopeCompatClient,
    messages: List[Dict[str, str]],
    max_new_tokens: int,
    temperature: float,
    top_p: float,
    enable_thinking: bool,
    max_input_chars: int,
    budget: int,
    total_tokens_used: int,
) -> Tuple[str, Dict[str, int], Dict[str, Any], bool, bool, bool, int]:
    answer, usage, raw_obj, usage_estimated = client.chat(
        messages=messages,
        max_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        enable_thinking=enable_thinking,
    )
    extra_calls = 1
    format_retry_attempted = False
    format_retry_used = False

    required_entities, tool_code = _extract_tool_payload(answer)
    first_obj = None
    try:
        first_obj = json.loads(answer)
    except Exception:
        first_obj = None

    if (not tool_code) or (not isinstance(first_obj, dict)):
        format_retry_attempted = True
        if (total_tokens_used + int(usage.get("total_tokens", 0))) < budget:
            retry_user = {
                "role": "user",
                "content": (
                    "FORMAT RETRY (single retry): previous output was empty_code or invalid JSON.\n"
                    "Return STRICT JSON only with keys required_entities/fix_plan/tool_code.\n"
                    "tool_code must start with: def calc(relevant):\n"
                    "No markdown, no prose."
                ),
            }
            retry_messages = _trim_messages_by_char_budget(
                messages + [retry_user], max_total_chars=max(2000, int(max_input_chars))
            )
            try:
                answer2, usage2, raw_obj2, usage_estimated2 = client.chat(
                    messages=retry_messages,
                    max_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    enable_thinking=enable_thinking,
                )
                extra_calls += 1
                usage["prompt_tokens"] = int(usage.get("prompt_tokens", 0)) + int(usage2.get("prompt_tokens", 0))
                usage["completion_tokens"] = int(usage.get("completion_tokens", 0)) + int(
                    usage2.get("completion_tokens", 0)
                )
                usage["total_tokens"] = int(usage.get("total_tokens", 0)) + int(usage2.get("total_tokens", 0))
                usage_estimated = usage_estimated or usage_estimated2

                req2, code2 = _extract_tool_payload(answer2)
                if code2:
                    answer = answer2
                    raw_obj = raw_obj2
                    required_entities = req2
                    tool_code = code2
                    format_retry_used = True
            except Exception:
                pass

    # Return answer/usage plus parsed artifacts via raw_obj extra keys to avoid re-parsing.
    if isinstance(raw_obj, dict):
        raw_obj["_parsed_required_entities"] = required_entities
        raw_obj["_parsed_tool_code"] = tool_code
    return (
        answer,
        usage,
        raw_obj,
        usage_estimated,
        format_retry_attempted,
        format_retry_used,
        extra_calls,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    default_base_dir = os.getcwd()
    parser.add_argument("--base_dir", type=str, default=default_base_dir)
    parser.add_argument("--python_bin", type=str, default="python")
    parser.add_argument("--train_csv", type=str, default="")
    parser.add_argument("--stage1_docs_jsonl", type=str, default="")
    parser.add_argument("--embedding_model_path", type=str, default="")
    parser.add_argument("--use_embedding", type=int, default=0)
    parser.add_argument("--rebuild_rag_docs", type=int, default=0)
    parser.add_argument("--use_medagent_memory", type=int, default=0)
    parser.add_argument("--memory_dir", type=str, default="")
    parser.add_argument("--few_shot_csv", type=str, default="")
    parser.add_argument("--case_library_json", type=str, default="")
    parser.add_argument("--case_search_top_k", type=int, default=3)
    parser.add_argument("--tool_feedback_memory_top_k", type=int, default=5)
    parser.add_argument("--tools_root_dir", type=str, default="")
    parser.add_argument("--run_tools_dir", type=str, default="")

    parser.add_argument(
        "--api_base",
        type=str,
        default="",
        help="explicit OpenAI-compatible endpoint; no provider is assumed",
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default="",
        help="API key; prefer TOOL_WRITER_API_KEY to avoid shell history",
    )
    parser.add_argument("--model", type=str, default="")
    parser.add_argument("--timeout_sec", type=int, default=600)
    parser.add_argument("--api_retries", type=int, default=5)
    parser.add_argument("--max_new_tokens", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=1.0)
    parser.add_argument("--enable_thinking", type=int, default=0)

    parser.add_argument("--token_budget", type=int, default=1_000_000)
    parser.add_argument("--sample_per_calc", type=int, default=8)
    parser.add_argument("--max_rounds", type=int, default=10)
    parser.add_argument("--rag_top_k", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260417)
    parser.add_argument("--max_calculators", type=int, default=0)
    parser.add_argument("--only_calc_ids", type=str, default="")
    parser.add_argument("--skip_calc_ids", type=str, default="")
    parser.add_argument("--tool_exec_timeout_sec", type=int, default=3)
    parser.add_argument("--max_input_chars", type=int, default=12000)

    # Default to single-cycle run. Set repeat_until_budget=1/max_passes>1 to enable multi-cycle.
    parser.add_argument("--repeat_until_budget", type=int, default=0)
    parser.add_argument("--max_passes", type=int, default=1)
    parser.add_argument(
        "--skip_success_in_later_cycles",
        type=int,
        default=1,
        help="If 1, calculators that already reached all-pass in previous cycles are skipped.",
    )

    parser.add_argument("--output_jsonl", type=str, default="")
    parser.add_argument("--result_jsonl", type=str, default="")
    parser.add_argument("--summary_json", type=str, default="")
    parser.add_argument(
        "--resume_result_jsonl",
        type=str,
        default="",
        help="Comma-separated previous result jsonl files; only rows with status=success are reused.",
    )
    parser.add_argument(
        "--resume_tools_dir",
        type=str,
        default="",
        help="Comma-separated previous tools dirs; all calculator_*.py files are reused. Prefer resume_result_jsonl.",
    )
    args = parser.parse_args()

    api_key = (
        safe_str(args.api_key).strip()
        or safe_str(os.getenv("TOOL_WRITER_API_KEY")).strip()
    )
    api_base = safe_str(args.api_base).strip() or safe_str(
        os.getenv("TOOL_WRITER_API_BASE")
    ).strip()
    model = safe_str(args.model).strip() or safe_str(
        os.getenv("TOOL_WRITER_MODEL_NAME")
    ).strip()
    if not api_base:
        raise RuntimeError(
            "missing API endpoint; set TOOL_WRITER_API_BASE or pass --api_base"
        )
    if not api_key:
        raise RuntimeError("missing API key; set TOOL_WRITER_API_KEY")
    if not model:
        raise RuntimeError(
            "missing model name; set TOOL_WRITER_MODEL_NAME or pass --model"
        )

    base_dir = os.path.abspath(args.base_dir)
    output_dir = os.path.join(base_dir, "artifacts", "tool_builder", "output")
    result_dir = os.path.join(base_dir, "artifacts", "tool_builder", "results")
    tools_dir = args.tools_root_dir.strip() or os.path.join(
        base_dir,
        "artifacts",
        "calculators",
        "gpt_5_5",
    )
    ensure_dir(output_dir)
    ensure_dir(result_dir)
    ensure_dir(tools_dir)

    stamp = datetime.now().strftime("%y%m%d_%H%M%S")
    model_tag = _sanitize_tag(model)
    run_suffix = (
        f"api_{model_tag}_r{int(args.max_rounds)}_s{int(args.sample_per_calc)}_b{int(args.token_budget)}_{stamp}"
    )
    output_jsonl = args.output_jsonl.strip() or os.path.join(output_dir, f"output_{run_suffix}.jsonl")
    result_jsonl = args.result_jsonl.strip() or os.path.join(result_dir, f"result_{run_suffix}.jsonl")
    summary_json = args.summary_json.strip() or os.path.join(result_dir, f"summary_{run_suffix}.json")
    run_tools_dir = args.run_tools_dir.strip() or os.path.join(tools_dir, run_suffix)
    ensure_dir(run_tools_dir)

    train_csv = args.train_csv.strip() or os.path.join(
        base_dir,
        "data",
        "processed",
        "train_data.csv",
    )
    if not os.path.exists(train_csv):
        raise RuntimeError(f"train_csv not found: {train_csv}")

    stage1_docs_jsonl = args.stage1_docs_jsonl.strip()
    if not stage1_docs_jsonl:
        stage1_docs_jsonl = _build_rag_docs_if_needed(
            base_dir=base_dir,
            python_bin=args.python_bin,
            train_csv=train_csv,
            force_rebuild=bool(int(args.rebuild_rag_docs)),
        )
    if not os.path.exists(stage1_docs_jsonl):
        raise RuntimeError(f"stage1 docs not found: {stage1_docs_jsonl}")

    rows = load_csv_rows(train_csv)
    by_calc: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        cid = calc_id(r)
        if not cid:
            continue
        by_calc.setdefault(cid, []).append(r)

    resumed_tools = _prepare_resume_tools(
        resume_result_jsonl=args.resume_result_jsonl,
        resume_tools_dir=args.resume_tools_dir,
        run_tools_dir=run_tools_dir,
    )
    resumed_cids = set(resumed_tools.keys())
    combined_skip_calc_ids = ",".join(
        [x for x in [safe_str(args.skip_calc_ids).strip(), ",".join(sorted(resumed_cids, key=_calc_sort_key))] if x]
    )

    calc_ids = _select_calc_ids(
        by_calc=by_calc,
        only_calc_ids=args.only_calc_ids,
        skip_calc_ids=combined_skip_calc_ids,
        max_calculators=args.max_calculators,
    )
    if resumed_cids:
        print(
            f"[{now_str()}] resume copied_tools={len(resumed_cids)} "
            f"remaining_calculators={len(calc_ids)}"
        )
    if not calc_ids:
        if resumed_cids:
            summary = {
                "run_name": run_suffix,
                "timestamp": now_str(),
                "model": model,
                "api_base": api_base,
                "token_budget": int(args.token_budget),
                "token_used": 0,
                "token_used_ratio": 0.0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "api_calls": 0,
                "usage_estimated_calls": 0,
                "format_retry_attempted": 0,
                "format_retry_used": 0,
                "cycles_executed": 0,
                "calculator_runs": 0,
                "solved_calculators": 0,
                "round_records": 0,
                "unique_calculators_covered": 0,
                "all_round_sampled_cases_total": 0,
                "all_round_sampled_cases_correct": 0,
                "all_round_accuracy": 0.0,
                "latest_per_calc_accuracy": 0.0,
                "best_per_calc_accuracy": 0.0,
                "stop_reason": "all_selected_calculators_already_resumed",
                "train_csv": train_csv,
                "stage1_docs_jsonl": stage1_docs_jsonl,
                "output_jsonl": output_jsonl,
                "result_jsonl": result_jsonl,
                "tools_dir": run_tools_dir,
                "resume_result_jsonl": args.resume_result_jsonl,
                "resume_tools_dir": args.resume_tools_dir,
                "resumed_tools": int(len(resumed_cids)),
                "resumed_calculator_ids": sorted(resumed_cids, key=_calc_sort_key),
            }
            with open(summary_json, "w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return
        raise RuntimeError("no calculators selected")

    rag_docs = load_jsonl(stage1_docs_jsonl)
    if not rag_docs:
        raise RuntimeError(f"empty stage1 docs: {stage1_docs_jsonl}")
    rag = MedicalRAG(
        docs=rag_docs,
        embedding_model_path=args.embedding_model_path,
        use_embedding=bool(int(args.use_embedding)),
    )

    use_medagent_memory = bool(int(args.use_medagent_memory))
    memory = None
    case_searcher = None
    memory_dir = args.memory_dir.strip() or os.path.join(base_dir, "artifacts", "memory")
    few_shot_csv = args.few_shot_csv.strip() or os.path.join(
        base_dir,
        "data",
        "processed",
        "few_shot_selected_train_rows_k3.csv",
    )
    case_library_json = args.case_library_json.strip() or os.path.join(
        base_dir,
        "data",
        "processed",
        "case_library_merged_v1_8.json",
    )
    if use_medagent_memory:
        memory = MemoryStore(memory_dir)
        case_searcher = CaseSearcher(few_shot_csv, case_library_json=case_library_json)

    client = DashScopeCompatClient(
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout_sec=args.timeout_sec,
        api_retries=args.api_retries,
    )

    # fresh files for this run suffix
    for fp in [output_jsonl, result_jsonl, summary_json]:
        if os.path.exists(fp):
            os.remove(fp)

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    api_calls = 0
    usage_estimated_calls = 0
    retry_attempted = 0
    retry_used = 0

    all_round_sample_total = 0
    all_round_sample_correct = 0
    all_round_records = 0

    per_calc_latest: Dict[str, Dict[str, int]] = {}
    per_calc_best: Dict[str, Dict[str, int]] = {}
    solved_cids = set()
    calc_runs = 0
    stop_reason = "completed"

    budget = max(1, int(args.token_budget))
    max_rounds = max(1, int(args.max_rounds))
    max_cycles = max(1, int(args.max_passes))
    repeat_until_budget = bool(int(args.repeat_until_budget))

    print(
        f"[{now_str()}] run={run_suffix} model={model} calc_count={len(calc_ids)} "
        f"budget={budget} sample_per_calc={args.sample_per_calc} max_rounds={max_rounds}"
    )

    budget_hit = False
    cycle_idx = 0
    while cycle_idx < max_cycles and not budget_hit:
        cycle_idx += 1
        progressed_this_cycle = False
        for cid in calc_ids:
            if int(args.skip_success_in_later_cycles) == 1 and cid in solved_cids:
                continue
            if total_tokens >= budget:
                budget_hit = True
                stop_reason = "token_budget_reached"
                break

            progressed_this_cycle = True
            calc_runs += 1
            rows_c = by_calc[cid]
            calc_name = safe_str(rows_c[0].get("Calculator Name", "")).strip()
            seed_base = int(args.seed) + cycle_idx * 100003 + (int(cid) if cid.isdigit() else sum(ord(c) for c in cid))
            rng = random.Random(seed_base)
            k = min(max(1, int(args.sample_per_calc)), len(rows_c))
            sampled = rng.sample(rows_c, k=k)
            output_type, known_keys, train_examples = _build_calc_prompt_profile(rows=rows_c, sampled=sampled, rng=rng)

            query = (
                f"{calc_name}. Build an executable calculator function with exact formula/rules, "
                "required inputs, and edge conditions."
            )
            refs = rag.retrieve(query=query, calculator_id=cid, top_k=args.rag_top_k)
            medagent_case_examples: List[Dict[str, Any]] = []
            medagent_memory_refs: List[Dict[str, Any]] = []
            memory_rule_used = False
            if use_medagent_memory and memory is not None:
                question_for_memory = safe_str(rows_c[0].get("Question", ""))
                memory_rule = memory.get_rule(cid, calc_name, question_for_memory)
                if memory_rule:
                    medagent_memory_refs.append(_memory_rule_to_snippet(memory_rule))
                    memory_rule_used = True
                feedback_hint = memory.build_tool_feedback_hint(
                    cid,
                    top_k=max(1, int(args.tool_feedback_memory_top_k)),
                )
                medagent_memory_refs.extend(_feedback_hint_to_snippet(cid, feedback_hint))
                if case_searcher is not None:
                    patient_note_for_search = safe_str(sampled[0].get("Patient Note", "")) if sampled else ""
                    question_for_search = safe_str(sampled[0].get("Question", question_for_memory)) if sampled else question_for_memory
                    medagent_case_examples = case_searcher.retrieve(
                        calculator_id=cid,
                        calculator_name=calc_name,
                        question=question_for_search,
                        patient_note=patient_note_for_search,
                        top_k=max(1, int(args.case_search_top_k)),
                    )
                    memory.record_case_examples(
                        row_number=f"tool_build:{run_suffix}:cycle{cycle_idx}",
                        calculator_id=cid,
                        calculator_name=calc_name,
                        examples=medagent_case_examples,
                    )
                    medagent_memory_refs.extend(_case_examples_to_snippets(medagent_case_examples))
            if medagent_memory_refs:
                # Put medagent memory and retrieved cases first so they are visible even if context is trimmed.
                refs = medagent_memory_refs + refs
            base_messages = stage1_build_tool_prompt(
                calculator_id=cid,
                calculator_name=calc_name,
                rag_snippets=refs,
                output_type=output_type,
                known_keys=known_keys,
                train_examples=train_examples,
            )

            best_round = 0
            best_correct = -1
            best_code = ""
            best_required: List[str] = []
            final_status = "failed"
            last_error_report = "not_started"
            last_round_acc = 0.0
            last_round_correct = 0
            last_round_idx = 0

            prev_code = ""
            prev_code_fp = ""
            same_code_streak = 0
            prev_compile_error = ""
            same_compile_streak = 0
            no_improve_streak = 0
            next_round_user_message = ""
            final_compile_error = ""

            for round_i in range(1, max_rounds + 1):
                if total_tokens >= budget:
                    budget_hit = True
                    stop_reason = "token_budget_reached"
                    break

                if round_i == 1 or not next_round_user_message:
                    messages = list(base_messages)
                else:
                    messages = [base_messages[0], base_messages[1], {"role": "user", "content": next_round_user_message}]
                messages = _trim_messages_by_char_budget(messages, max_total_chars=max(2000, int(args.max_input_chars)))

                try:
                    (
                        answer,
                        usage,
                        raw_obj,
                        usage_estimated,
                        format_retry_attempted,
                        format_retry_used,
                        extra_calls,
                    ) = _chat_once_with_optional_format_retry(
                        client=client,
                        messages=messages,
                        max_new_tokens=args.max_new_tokens,
                        temperature=args.temperature,
                        top_p=args.top_p,
                        enable_thinking=bool(int(args.enable_thinking)),
                        max_input_chars=args.max_input_chars,
                        budget=budget,
                        total_tokens_used=total_tokens,
                    )
                except Exception as e:
                    stop_reason = f"api_error:{type(e).__name__}:{e}"
                    print(f"[{now_str()}] stop on api error calc={cid} round={round_i}: {stop_reason}")
                    budget_hit = True
                    break

                api_calls += int(extra_calls)
                total_prompt_tokens += int(usage.get("prompt_tokens", 0))
                total_completion_tokens += int(usage.get("completion_tokens", 0))
                total_tokens += int(usage.get("total_tokens", 0))
                if usage_estimated:
                    usage_estimated_calls += 1
                if format_retry_attempted:
                    retry_attempted += 1
                if format_retry_used:
                    retry_used += 1

                required_entities = []
                tool_code = ""
                if isinstance(raw_obj, dict):
                    required_entities = raw_obj.get("_parsed_required_entities", []) or []
                    tool_code = safe_str(raw_obj.get("_parsed_tool_code", ""))
                if not tool_code:
                    required_entities, tool_code = _extract_tool_payload(answer)

                fn, compile_error = _compile_tool(tool_code)
                final_compile_error = compile_error
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
                last_round_acc = round_acc
                last_round_correct = correct_n
                last_round_idx = round_i
                err_report = _error_report(compile_error, eval_rows)
                last_error_report = err_report

                all_round_sample_total += len(sampled)
                all_round_sample_correct += correct_n
                all_round_records += 1

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

                out_row = {
                    "run_name": run_suffix,
                    "timestamp": now_str(),
                    "cycle": int(cycle_idx),
                    "Calculator ID": cid,
                    "Calculator Name": calc_name,
                    "round": int(round_i),
                    "prompt": messages,
                    "llm_answer": answer,
                    "round_samples": samples_out,
                    "round_correct": int(correct_n),
                    "round_total": int(len(sampled)),
                    "round_accuracy": float(round_acc),
                    "all_correct_this_round": bool(all_pass),
                    "compile_error": compile_error,
                    "error_report_for_next_round": err_report,
                    "required_entities": required_entities,
                    "format_retry_attempted": bool(format_retry_attempted),
                    "format_retry_used": bool(format_retry_used),
                    "use_medagent_memory": bool(use_medagent_memory),
                    "memory_rule_used": bool(memory_rule_used),
                    "case_retriever_examples": medagent_case_examples,
                    "usage": usage,
                    "cumulative_tokens": int(total_tokens),
                    "api_raw_id": safe_str((raw_obj or {}).get("id")),
                }
                append_jsonl(output_jsonl, [out_row])

                print(
                    f"[{now_str()}] cycle={cycle_idx} calc={cid} round={round_i} "
                    f"acc={correct_n}/{len(sampled)} compile_error={'yes' if compile_error else 'no'} "
                    f"tokens={usage.get('total_tokens', 0)} cumulative={total_tokens}/{budget}"
                )

                improved_this_round = correct_n > best_correct
                if improved_this_round:
                    best_correct = correct_n
                    best_round = round_i
                    best_code = tool_code
                    best_required = list(required_entities)
                    no_improve_streak = 0
                else:
                    no_improve_streak += 1

                fp = _code_fingerprint(tool_code=tool_code, raw_resp=answer)
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

                if use_medagent_memory and memory is not None:
                    failed_cases = _failed_cases_for_memory(eval_rows, max_items=8)
                    memory.record_tool_build_feedback(
                        run_name=run_suffix,
                        calculator_id=cid,
                        calculator_name=calc_name,
                        round_index=round_i,
                        correct=correct_n,
                        total=len(sampled),
                        compile_error=compile_error,
                        error_report=err_report,
                        failed_cases=failed_cases,
                        tool_code=tool_code,
                    )

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
                if use_medagent_memory and memory is not None:
                    memory_hint = memory.build_tool_feedback_hint(
                        cid,
                        top_k=max(1, int(args.tool_feedback_memory_top_k)),
                    )
                    if memory_hint:
                        feedback_user = (
                            "Medagent memory update for this calculator from prior validation failures:\n"
                            f"{memory_hint[:3000]}\n\n"
                            f"{feedback_user}"
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

            # End rounds for current calculator
            if not best_code:
                best_code = "def calc(relevant):\n    return 'N/A'\n"

            tool_path = os.path.join(run_tools_dir, f"calculator_{cid}_cycle{cycle_idx}.py")
            with open(tool_path, "w", encoding="utf-8") as f:
                f.write(best_code if best_code.endswith("\n") else best_code + "\n")

            # If we never entered a round (budget hit right before this calculator), skip result row.
            if last_round_idx <= 0:
                continue

            result_row = {
                "run_name": run_suffix,
                "timestamp": now_str(),
                "cycle": int(cycle_idx),
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
                "final_compile_error": final_compile_error,
                "last_error_report": last_error_report,
                "best_required_entities": best_required,
                "tool_path": tool_path,
                "cumulative_tokens": int(total_tokens),
                "use_medagent_memory": bool(use_medagent_memory),
                "memory_rule_used": bool(memory_rule_used),
                "case_retriever_examples_count": int(len(medagent_case_examples)),
            }
            append_jsonl(result_jsonl, [result_row])

            per_calc_latest[cid] = {"correct": int(last_round_correct), "total": int(len(sampled))}
            old = per_calc_best.get(cid, {"correct": -1, "total": int(len(sampled))})
            if int(best_correct) > int(old.get("correct", -1)):
                per_calc_best[cid] = {"correct": int(best_correct), "total": int(len(sampled))}
            elif cid not in per_calc_best:
                per_calc_best[cid] = {"correct": int(best_correct), "total": int(len(sampled))}

            if final_status == "success":
                solved_cids.add(cid)

            if budget_hit:
                break

        if int(args.skip_success_in_later_cycles) == 1 and len(solved_cids) >= len(calc_ids):
            stop_reason = "all_calculators_solved"
            break
        if budget_hit:
            break
        if not progressed_this_cycle:
            stop_reason = "no_progress"
            break
        if not repeat_until_budget:
            stop_reason = "single_cycle_completed"
            break

    if not budget_hit and repeat_until_budget and cycle_idx >= max_cycles:
        stop_reason = "max_passes_reached"

    latest_total = sum(int(v.get("total", 0)) for v in per_calc_latest.values())
    latest_correct = sum(int(v.get("correct", 0)) for v in per_calc_latest.values())
    best_total = sum(int(v.get("total", 0)) for v in per_calc_best.values())
    best_correct = sum(int(v.get("correct", 0)) for v in per_calc_best.values())

    summary = {
        "run_name": run_suffix,
        "timestamp": now_str(),
        "model": model,
        "api_base": api_base,
        "token_budget": int(budget),
        "token_used": int(total_tokens),
        "token_used_ratio": (float(total_tokens) / float(budget)) if budget else 0.0,
        "prompt_tokens": int(total_prompt_tokens),
        "completion_tokens": int(total_completion_tokens),
        "api_calls": int(api_calls),
        "usage_estimated_calls": int(usage_estimated_calls),
        "format_retry_attempted": int(retry_attempted),
        "format_retry_used": int(retry_used),
        "cycles_executed": int(cycle_idx),
        "calculator_runs": int(calc_runs),
        "solved_calculators": int(len(solved_cids)),
        "round_records": int(all_round_records),
        "unique_calculators_covered": int(len(per_calc_latest)),
        "all_round_sampled_cases_total": int(all_round_sample_total),
        "all_round_sampled_cases_correct": int(all_round_sample_correct),
        "all_round_accuracy": (float(all_round_sample_correct) / float(all_round_sample_total))
        if all_round_sample_total
        else 0.0,
        "latest_per_calc_accuracy": (float(latest_correct) / float(latest_total)) if latest_total else 0.0,
        "best_per_calc_accuracy": (float(best_correct) / float(best_total)) if best_total else 0.0,
        "stop_reason": stop_reason,
        "train_csv": train_csv,
        "stage1_docs_jsonl": stage1_docs_jsonl,
        "output_jsonl": output_jsonl,
        "result_jsonl": result_jsonl,
        "tools_dir": run_tools_dir,
        "use_medagent_memory": bool(use_medagent_memory),
        "memory_dir": memory_dir if use_medagent_memory else "",
        "tool_build_feedback_memory_jsonl": str(memory.tool_build_feedback_path) if memory is not None else "",
        "few_shot_csv": few_shot_csv if use_medagent_memory else "",
        "case_library_json": case_library_json if use_medagent_memory else "",
        "case_search_top_k": int(args.case_search_top_k) if use_medagent_memory else 0,
        "tool_feedback_memory_top_k": int(args.tool_feedback_memory_top_k) if use_medagent_memory else 0,
        "resume_result_jsonl": args.resume_result_jsonl,
        "resume_tools_dir": args.resume_tools_dir,
        "resumed_tools": int(len(resumed_cids)),
        "resumed_calculator_ids": sorted(resumed_cids, key=_calc_sort_key),
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
