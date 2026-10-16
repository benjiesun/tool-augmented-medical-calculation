from typing import Any, Dict, List

from ..prompts import build_tool_synthesis_messages, calculator_schema


def _join_context(snippets: List[Dict[str, Any]], max_chars: int = 4000) -> str:
    parts: List[str] = []
    total = 0
    for i, s in enumerate(snippets, 1):
        txt = str(s.get("text", "")).strip()
        if not txt:
            continue
        head = (
            f"[Ref {i}] calculator_id={s.get('calculator_id', '')} "
            f"title={s.get('title', '')} source={s.get('source', '')}\n"
        )
        chunk = head + txt + "\n"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts).strip()


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


def stage1_build_tool_prompt(
    calculator_id: str,
    calculator_name: str,
    rag_snippets: List[Dict[str, Any]],
    output_type: str = "",
    known_keys: List[str] = None,
    train_examples: List[Dict[str, Any]] = None,
    schema: Dict[str, Any] = None,
) -> List[Dict[str, str]]:
    ctx = _join_context(rag_snippets)
    return build_tool_synthesis_messages(
        calculator_id, calculator_name, output_type, ctx,
        schema if schema is not None else calculator_schema(calculator_id),
        train_examples or [],
    )


def stage1_repair_tool_prompt(
    calculator_id: str,
    calculator_name: str,
    previous_code: str,
    error_report: str,
    rag_snippets: List[Dict[str, Any]],
    output_type: str = "",
    known_keys: List[str] = None,
    train_examples: List[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    ctx = _join_context(rag_snippets)
    output_hint = output_type or "unknown"
    keys_txt = ", ".join((known_keys or [])[:30]) or "(none)"
    train_txt = _render_train_examples(train_examples or [])
    system = (
        "You are fixing a medical calculator Python tool. "
        "Output STRICT JSON only, no markdown, no explanation, no <think>."
    )
    user = (
        f"Calculator ID: {calculator_id}\n"
        f"Calculator Name: {calculator_name}\n\n"
        f"Expected benchmark output type: {output_hint}\n"
        f"Observed training key names: {keys_txt}\n\n"
        "Training examples (for output shape and scale; train-set only):\n"
        f"{train_txt}\n\n"
        "Previous tool code:\n"
        f"{previous_code}\n\n"
        "Observed compile/runtime/answer errors:\n"
        f"{error_report}\n\n"
        "RAG references:\n"
        f"{ctx or '(none)'}\n\n"
        "Please fix code and return strict JSON:\n"
        "{\n"
        '  "required_entities": ["key1", "key2"],\n'
        '  "tool_code": "def calc(relevant):\\n    ..."\n'
        "}\n"
        "Keep robust input parsing and explicit final return.\n"
        "If output type is numeric, return numeric scalar only.\n"
        "Do not use unbounded loops.\n"
        "Do not use import statements.\n"
        "Use str(value).lower() instead of value.lower() for unknown types.\n"
        "/no_think"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def stage2_extract_params_prompt(
    calculator_id: str,
    calculator_name: str,
    question: str,
    note: str,
    rag_snippets: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    ctx = _join_context(rag_snippets)
    system = "Extract calculator parameters from note. Output STRICT JSON only."
    user = (
        f"Calculator ID: {calculator_id}\n"
        f"Calculator Name: {calculator_name}\n"
        f"Question: {question}\n\n"
        "Patient note:\n"
        f"{note}\n\n"
        "RAG references:\n"
        f"{ctx or '(none)'}\n\n"
        "Return JSON:\n"
        '{\n  "relevant_entities": {"key": value or [value, "unit"]}\n}\n'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def stage3_normalize_params_prompt(
    calculator_id: str,
    calculator_name: str,
    raw_entities_json: str,
    rag_snippets: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    ctx = _join_context(rag_snippets)
    system = "Normalize calculator entities. Output STRICT JSON only."
    user = (
        f"Calculator ID: {calculator_id}\n"
        f"Calculator Name: {calculator_name}\n\n"
        f"Raw entities:\n{raw_entities_json}\n\n"
        "RAG references:\n"
        f"{ctx or '(none)'}\n\n"
        "Return JSON:\n"
        '{\n  "normalized_entities": {"key": value or [value, "unit"]}\n}\n'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
