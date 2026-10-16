import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .utils import append_jsonl, load_jsonl, now_str, safe_str


class MemoryStore:
    def __init__(self, memory_dir: str):
        self.memory_dir = Path(memory_dir).resolve()
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.static_rules_path = self.memory_dir / "mdcalc_rules_v1.jsonl"
        self.web_rules_path = self.memory_dir / "web_rules.jsonl"
        self.missing_params_path = self.memory_dir / "missing_params_memory.jsonl"
        self.case_memory_path = self.memory_dir / "case_memory.jsonl"
        self.tool_specs_path = self.memory_dir / "tool_specs.jsonl"
        self.tool_build_feedback_path = self.memory_dir / "tool_build_feedback_memory.jsonl"

        for path in (
            self.missing_params_path,
            self.case_memory_path,
            self.tool_specs_path,
            self.tool_build_feedback_path,
            self.web_rules_path,
        ):
            path.touch(exist_ok=True)

        self.refresh()

    @staticmethod
    def _norm_cid(calculator_id: Any) -> str:
        s = safe_str(calculator_id).strip()
        try:
            return str(int(float(s)))
        except Exception:
            return s

    def refresh(self) -> None:
        self._static_rules = (load_jsonl(str(self.static_rules_path))
                              + load_jsonl(str(self.web_rules_path)))

    def _exact_match_rule(self, calculator_id: str) -> Optional[Dict[str, Any]]:
        cid = self._norm_cid(calculator_id)
        for row in reversed(self._static_rules):
            if self._norm_cid(row.get("calculator_id", "")) == cid:
                return dict(row)
        return None

    def get_rule(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
    ) -> Optional[Dict[str, Any]]:
        cid = self._norm_cid(calculator_id)
        matched = self._exact_match_rule(cid)
        return matched

    def save_web_rule(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
        evidence_text: str,
        source_hits: List[Dict[str, Any]],
        *,
        mdcalc_title: str = "",
        mdcalc_url: str = "",
        formula: str = "",
        inputs: str = "",
        instructions: str = "",
        rule_specification: Optional[Dict[str, Any]] = None,
        schema: Optional[Dict[str, Any]] = None,
        source: str = "web_search_codex",
        web_fetch_status: str = "",
    ) -> Dict[str, Any]:
        cid = self._norm_cid(calculator_id)
        built_at = now_str()
        row = {
            "doc_id": f"rules_calc_{cid}_web_{built_at.replace(' ', '_').replace(':', '')}",
            "calculator_id": cid,
            "calculator_name": safe_str(calculator_name).strip(),
            "mdcalc_title": safe_str(mdcalc_title or calculator_name).strip(),
            "mdcalc_url": safe_str(mdcalc_url).strip(),
            "formula": safe_str(formula).strip(),
            "inputs": safe_str(inputs).strip(),
            "instructions": safe_str(instructions).strip(),
            "rule_specification": rule_specification or {},
            "schema": schema or {},
            "evidence_text": safe_str(evidence_text).strip(),
            "web_excerpt": json.dumps(source_hits, ensure_ascii=False)[:3000],
            "web_fetch_status": safe_str(web_fetch_status).strip() or ("ok" if source_hits else "empty"),
            "source": safe_str(source).strip() or "web_search_codex",
            "built_at": built_at,
            "query": safe_str(question).strip(),
        }
        append_jsonl(str(self.web_rules_path), [row])
        self._static_rules.append(row)
        return row

    def record_missing_params(
        self,
        row_number: Any,
        calculator_id: Any,
        calculator_name: str,
        missing_params: List[str],
        extracted_entities: Dict[str, Any],
        note_id: Any = "",
        question: str = "",
    ) -> None:
        cid = self._norm_cid(calculator_id)
        row = {
            "time": now_str(),
            "row_number": safe_str(row_number),
            "note_id": safe_str(note_id),
            "calculator_id": cid,
            "calculator_name": safe_str(calculator_name),
            "question": safe_str(question),
            "missing_params": [safe_str(x).strip() for x in missing_params if safe_str(x).strip()],
            "extracted_entities": extracted_entities or {},
        }
        append_jsonl(str(self.missing_params_path), [row])

    def build_missing_hint(self, calculator_id: Any, top_k: int = 6) -> str:
        cid = self._norm_cid(calculator_id)
        rows = load_jsonl(str(self.missing_params_path))
        hits = [x for x in rows if self._norm_cid(x.get("calculator_id", "")) == cid]
        if not hits:
            return ""
        hits = hits[-max(1, int(top_k)) :]
        missing_union: List[str] = []
        seen = set()
        for h in hits:
            for key in h.get("missing_params", []) or []:
                k = safe_str(key).strip()
                if k and k not in seen:
                    seen.add(k)
                    missing_union.append(k)
        if not missing_union:
            return ""
        return "Previously missing parameters for this calculator: " + ", ".join(missing_union)

    def record_case_examples(
        self,
        row_number: Any,
        calculator_id: Any,
        calculator_name: str,
        examples: List[Dict[str, Any]],
    ) -> None:
        row = {
            "time": now_str(),
            "row_number": safe_str(row_number),
            "calculator_id": self._norm_cid(calculator_id),
            "calculator_name": safe_str(calculator_name),
            "examples": examples,
        }
        append_jsonl(str(self.case_memory_path), [row])

    def record_tool_spec(
        self,
        calculator_id: Any,
        calculator_name: str,
        required_entities: List[str],
        tool_code: str,
        source: str,
    ) -> None:
        row = {
            "time": now_str(),
            "calculator_id": self._norm_cid(calculator_id),
            "calculator_name": safe_str(calculator_name),
            "required_entities": [safe_str(x).strip() for x in required_entities if safe_str(x).strip()],
            "tool_code": safe_str(tool_code),
            "source": safe_str(source),
        }
        append_jsonl(str(self.tool_specs_path), [row])

    def latest_tool_spec(self, calculator_id: Any) -> Optional[Dict[str, Any]]:
        cid = self._norm_cid(calculator_id)
        rows = load_jsonl(str(self.tool_specs_path))
        for row in reversed(rows):
            if self._norm_cid(row.get("calculator_id", "")) == cid:
                return dict(row)
        return None

    def record_tool_build_feedback(
        self,
        run_name: str,
        calculator_id: Any,
        calculator_name: str,
        round_index: int,
        correct: int,
        total: int,
        compile_error: str,
        error_report: str,
        failed_cases: List[Dict[str, Any]],
        tool_code: str = "",
    ) -> Dict[str, Any]:
        row = {
            "time": now_str(),
            "run_name": safe_str(run_name),
            "calculator_id": self._norm_cid(calculator_id),
            "calculator_name": safe_str(calculator_name),
            "round": int(round_index),
            "correct": int(correct),
            "total": int(total),
            "compile_error": safe_str(compile_error),
            "error_report": safe_str(error_report),
            "failed_cases": failed_cases[:8],
            "tool_code_excerpt": safe_str(tool_code)[:4000],
            "source": "tool_build_validation_feedback",
        }
        append_jsonl(str(self.tool_build_feedback_path), [row])
        return row

    def build_tool_feedback_hint(self, calculator_id: Any, top_k: int = 5) -> str:
        cid = self._norm_cid(calculator_id)
        rows = load_jsonl(str(self.tool_build_feedback_path))
        hits = [x for x in rows if self._norm_cid(x.get("calculator_id", "")) == cid]
        if not hits:
            return ""
        hits = hits[-max(1, int(top_k)) :]
        parts: List[str] = []
        for h in hits:
            failed = h.get("failed_cases", []) or []
            failed_text = []
            for case in failed[:3]:
                failed_text.append(
                    "row={row}; reason={reason}; pred={pred}; gt={gt}; range=[{low},{high}]; relevant={relevant}".format(
                        row=safe_str(case.get("row_number", "")),
                        reason=safe_str(case.get("reason", ""))[:120],
                        pred=safe_str(case.get("pred", ""))[:120],
                        gt=safe_str(case.get("gt", ""))[:120],
                        low=safe_str(case.get("low", "")),
                        high=safe_str(case.get("high", "")),
                        relevant=safe_str(case.get("relevant", ""))[:360],
                    )
                )
            parts.append(
                "round={round} correct={correct}/{total}; compile_error={compile}; error={error}; failed_cases={failed}".format(
                    round=safe_str(h.get("round", "")),
                    correct=safe_str(h.get("correct", "")),
                    total=safe_str(h.get("total", "")),
                    compile=safe_str(h.get("compile_error", ""))[:160] or "none",
                    error=safe_str(h.get("error_report", ""))[:300],
                    failed=" | ".join(failed_text) if failed_text else "(none)",
                )
            )
        return "\n".join(parts)
