#!/usr/bin/env python3
"""API tool builder ablation: build calculator tools without retrieved formula rules."""

import argparse
import json
import os
import random
from datetime import datetime
from typing import Any, Dict, List

from .common import append_jsonl, calc_id, ensure_dir, load_csv_rows, now_str, safe_str
from .run_api import (
    DashScopeCompatClient,
    _chat_once_with_optional_format_retry,
    _sanitize_tag,
    _select_calc_ids,
)
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


def _render_train_examples(train_examples: List[Dict[str, Any]], max_items: int = 2) -> str:
    if not train_examples:
        return "(none)"
    parts: List[str] = []
    for i, x in enumerate(train_examples[:max_items], 1):
        parts.append(
            f"[Example {i}] relevant={x.get('relevant_entities_json', '{}')} "
            f"gt_answer={x.get('ground_truth_answer', '')} "
            f"range=[{x.get('lower_limit', '')},{x.get('upper_limit', '')}]"
        )
    return "\n".join(parts)


def _no_web_build_tool_prompt(
    calculator_id: str,
    calculator_name: str,
    output_type: str = "",
    known_keys: List[str] = None,
    train_examples: List[Dict[str, Any]] = None,
    prompt_profile: str = "with_train_profile",
) -> List[Dict[str, str]]:
    output_hint = output_type or "unknown"
    keys_txt = ", ".join((known_keys or [])[:30]) or "(none)"
    train_txt = _render_train_examples(train_examples or [])
    include_profile = safe_str(prompt_profile).strip().lower() != "name_only"

    system = (
        "You are an expert medical calculator tool builder. "
        "This is an ablation run: do not use web search, RAG, MDCalc pages, or retrieved formula rules. "
        "Output STRICT JSON only, no markdown, no explanation, no <think>."
    )
    user_parts = [
        f"Calculator ID: {calculator_id}",
        f"Calculator Name: {calculator_name}",
        "",
        "Ablation setting:",
        "- No web retrieval and no rule/RAG snippets are provided.",
        "- Infer the most standard medical calculator formula/rules from the calculator name and common medical knowledge.",
        "- If several versions exist, implement the most commonly used MDCalc-style version.",
    ]
    if include_profile:
        user_parts.extend(
            [
                "",
                f"Expected benchmark output type: {output_hint}",
                f"Observed training key names: {keys_txt}",
                "",
                "Training examples are provided only for output shape and scale; they are not retrieved formula rules:",
                train_txt,
            ]
        )
    user_parts.extend(
        [
            "",
            "Write robust Python code with function:",
            "def calc(relevant):",
            "Requirements:",
            "1) relevant is a dict; values may be scalar OR [value, unit] OR tuple OR dict.",
            "2) include parsing helpers to safely read number/text/boolean.",
            "3) if required inputs are missing, return 'N/A'.",
            "4) deterministic, concise, runnable code.",
            "5) include explicit final return in calc.",
            "6) no import statements.",
            "7) support case-insensitive and alias keys; do not assume exact capitalization/punctuation.",
            "8) If output type is numeric, return numeric scalar only, not labels/sentences.",
            "9) Do not use unbounded loops.",
            "10) tool_code must be plain Python source, no markdown fences.",
            "11) Never call .lower() on unknown object; cast via str(value).lower().",
            "12) Avoid shadowing builtins such as next.",
            "13) Do not return dict/list/tuple as final answer unless explicitly required by output type.",
            "",
            "Return exactly this JSON schema:",
            "{",
            '  "required_entities": ["key1", "key2"],',
            '  "tool_code": "def calc(relevant):\\n    ..."',
            "}",
            "/no_think",
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": "\n".join(user_parts)}]


def _write_json(path: str, data: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build tools with GPT API without rule/web/RAG retrieval.")
    default_base_dir = os.getcwd()
    parser.add_argument("--base_dir", type=str, default=default_base_dir)
    parser.add_argument("--train_csv", type=str, default="")
    parser.add_argument("--tools_dir", type=str, default="")
    parser.add_argument("--run_name", type=str, default="")
    parser.add_argument("--prompt_profile", type=str, default="with_train_profile", choices=["with_train_profile", "name_only"])

    parser.add_argument(
        "--api_base",
        type=str,
        default="",
        help="explicit OpenAI-compatible endpoint; no third-party endpoint is assumed",
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
    parser.add_argument("--max_new_tokens", type=int, default=1200)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=1.0)
    parser.add_argument("--enable_thinking", type=int, default=0)

    parser.add_argument("--token_budget", type=int, default=1_000_000)
    parser.add_argument("--sample_per_calc", type=int, default=8)
    parser.add_argument("--max_rounds", type=int, default=1)
    parser.add_argument("--disable_feedback", type=int, default=1)
    parser.add_argument("--disable_format_retry", type=int, default=0)
    parser.add_argument("--seed", type=int, default=20260417)
    parser.add_argument("--max_calculators", type=int, default=0)
    parser.add_argument("--only_calc_ids", type=str, default="")
    parser.add_argument("--skip_calc_ids", type=str, default="")
    parser.add_argument("--tool_exec_timeout_sec", type=int, default=3)
    parser.add_argument("--max_input_chars", type=int, default=12000)

    parser.add_argument("--output_jsonl", type=str, default="")
    parser.add_argument("--result_jsonl", type=str, default="")
    parser.add_argument("--summary_json", type=str, default="")
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
    ensure_dir(output_dir)
    ensure_dir(result_dir)

    stamp = datetime.now().strftime("%y%m%d_%H%M%S")
    model_tag = _sanitize_tag(model)
    run_name = safe_str(args.run_name).strip() or (
        f"api_{model_tag}_no_web_rules_r{int(args.max_rounds)}_s{int(args.sample_per_calc)}_"
        f"b{int(args.token_budget)}_{stamp}"
    )
    run_tools_dir = args.tools_dir.strip() or os.path.join(
        base_dir,
        "artifacts",
        "calculators",
        "gpt_5_5",
        run_name,
    )
    ensure_dir(run_tools_dir)

    output_jsonl = args.output_jsonl.strip() or os.path.join(output_dir, f"output_{run_name}.jsonl")
    result_jsonl = args.result_jsonl.strip() or os.path.join(result_dir, f"result_{run_name}.jsonl")
    summary_json = args.summary_json.strip() or os.path.join(result_dir, f"summary_{run_name}.json")

    train_csv = args.train_csv.strip() or os.path.join(
        base_dir,
        "data",
        "processed",
        "train_data.csv",
    )
    if not os.path.exists(train_csv):
        raise RuntimeError(f"train_csv not found: {train_csv}")

    rows = load_csv_rows(train_csv)
    by_calc: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        cid = calc_id(r)
        if cid:
            by_calc.setdefault(cid, []).append(r)

    calc_ids = _select_calc_ids(
        by_calc=by_calc,
        only_calc_ids=args.only_calc_ids,
        skip_calc_ids=args.skip_calc_ids,
        max_calculators=args.max_calculators,
    )
    if not calc_ids:
        raise RuntimeError("no calculators selected")

    client = DashScopeCompatClient(
        api_base=api_base,
        api_key=api_key,
        model=model,
        timeout_sec=args.timeout_sec,
        api_retries=args.api_retries,
    )

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
    disable_feedback = bool(int(args.disable_feedback))
    disable_format_retry = bool(int(args.disable_format_retry))

    print(
        f"[{now_str()}] run={run_name} model={model} calc_count={len(calc_ids)} "
        f"budget={budget} sample_per_calc={args.sample_per_calc} max_rounds={max_rounds} "
        f"prompt_profile={args.prompt_profile} no_web_rules=1 disable_feedback={int(disable_feedback)} "
        f"disable_format_retry={int(disable_format_retry)}"
    )

    budget_hit = False
    cycle_idx = 1
    for cid in calc_ids:
        if total_tokens >= budget:
            budget_hit = True
            stop_reason = "token_budget_reached"
            break

        calc_runs += 1
        rows_c = by_calc[cid]
        calc_name = safe_str(rows_c[0].get("Calculator Name", "")).strip()
        seed_base = int(args.seed) + (int(cid) if cid.isdigit() else sum(ord(c) for c in cid))
        rng = random.Random(seed_base)
        k = min(max(1, int(args.sample_per_calc)), len(rows_c))
        sampled = rng.sample(rows_c, k=k)
        output_type, known_keys, train_examples = _build_calc_prompt_profile(rows=rows_c, sampled=sampled, rng=rng)
        base_messages = _no_web_build_tool_prompt(
            calculator_id=cid,
            calculator_name=calc_name,
            output_type=output_type,
            known_keys=known_keys,
            train_examples=train_examples,
            prompt_profile=args.prompt_profile,
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
                if disable_format_retry:
                    answer, usage, raw_obj, usage_estimated = client.chat(
                        messages=messages,
                        max_tokens=args.max_new_tokens,
                        temperature=args.temperature,
                        top_p=args.top_p,
                        enable_thinking=bool(int(args.enable_thinking)),
                    )
                    format_retry_attempted = False
                    format_retry_used = False
                    extra_calls = 1
                else:
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

            samples_out = [
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
                for x in eval_rows
            ]
            append_jsonl(
                output_jsonl,
                [
                    {
                        "run_name": run_name,
                        "timestamp": now_str(),
                        "ablation": "no_web_rule_retriever",
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
                        "feedback_disabled": bool(disable_feedback),
                        "usage": usage,
                        "cumulative_tokens": int(total_tokens),
                        "api_raw_id": safe_str((raw_obj or {}).get("id")) if isinstance(raw_obj, dict) else "",
                    }
                ],
            )

            print(
                f"[{now_str()}] calc={cid} round={round_i} acc={correct_n}/{len(sampled)} "
                f"compile_error={'yes' if compile_error else 'no'} tokens={usage.get('total_tokens', 0)} "
                f"cumulative={total_tokens}/{budget} no_web=1"
            )

            if correct_n > best_correct:
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
            if disable_feedback:
                # Strict single-pass ablation: do not feed errors back to the LLM.
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
                    "Rewrite tool_code from scratch based on the calculator name and failed rows only.\n"
                    "Do not use web, RAG, or retrieved formula rules.\n\n"
                    f"{feedback_user}"
                )
            else:
                next_round_user_message = feedback_user
            prev_code = tool_code if tool_code else prev_code

        if not best_code:
            best_code = "def calc(relevant):\n    return 'N/A'\n"

        tool_path = os.path.join(run_tools_dir, f"calculator_{cid}_cycle{cycle_idx}.py")
        with open(tool_path, "w", encoding="utf-8") as f:
            f.write(best_code if best_code.endswith("\n") else best_code + "\n")

        if last_round_idx <= 0:
            continue

        append_jsonl(
            result_jsonl,
            [
                {
                    "run_name": run_name,
                    "timestamp": now_str(),
                    "ablation": "no_web_rule_retriever",
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
                }
            ],
        )

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

    latest_total = sum(int(v.get("total", 0)) for v in per_calc_latest.values())
    latest_correct = sum(int(v.get("correct", 0)) for v in per_calc_latest.values())
    best_total = sum(int(v.get("total", 0)) for v in per_calc_best.values())
    best_correct_sum = sum(int(v.get("correct", 0)) for v in per_calc_best.values())

    summary = {
        "run_name": run_name,
        "timestamp": now_str(),
        "ablation": "no_web_rule_retriever",
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
        "cycles_executed": int(1),
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
        "best_per_calc_accuracy": (float(best_correct_sum) / float(best_total)) if best_total else 0.0,
        "stop_reason": stop_reason,
        "train_csv": train_csv,
        "stage1_docs_jsonl": "",
        "use_rag": False,
        "use_web_rule_retriever": False,
        "disable_feedback": bool(disable_feedback),
        "disable_format_retry": bool(disable_format_retry),
        "single_round_only": bool(disable_feedback and max_rounds == 1),
        "prompt_profile": args.prompt_profile,
        "output_jsonl": output_jsonl,
        "result_jsonl": result_jsonl,
        "tools_dir": run_tools_dir,
    }
    _write_json(summary_json, summary)
    registry_path = os.path.join(run_tools_dir, "tool_registry.jsonl")
    if not os.path.exists(registry_path):
        open(registry_path, "a", encoding="utf-8").close()
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
