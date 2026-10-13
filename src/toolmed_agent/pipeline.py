import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .case_search import CaseSearcher
from .evaluation import judge_case, summarize
from .extraction import ParameterExtractor
from .memory import MemoryStore
from .normalization import UnitNormalizer
from .tool_generation import FormulaWriter
from .tool_registry import CalculationToolRegistry
from .utils import (
    LLMRouter,
    append_jsonl,
    bool_env,
    ensure_dir,
    extract_first_json_object,
    load_csv_rows,
    load_env_file,
    now_compact,
    now_str,
    resolve_lora_adapter_path,
    safe_int,
    safe_str,
    write_json,
)
from .web_search import WebSearcher


def _norm_cid(v: Any) -> str:
    s = safe_str(v).strip()
    try:
        return str(int(float(s)))
    except Exception:
        return s


def _env(name: str, default: str = "") -> str:
    return safe_str(os.getenv(name, default)).strip()


def _path_env(name: str, default: Path, root_dir: Path) -> Path:
    raw = _env(name, str(default))
    path = Path(raw)
    if not path.is_absolute():
        path = root_dir / path
    return path.resolve()


def _build_llm(
    prefix: str,
    fallback_api_key: str,
    fallback_prefix: str = "",
    root_dir: Optional[Path] = None,
) -> LLMRouter:
    # prefix examples: CENTRAL / EXTRACTION / NORMALIZATION / TOOL_WRITER
    def _get(name: str, default: str = "") -> str:
        cur = _env(f"{prefix}_{name}", "")
        if cur:
            return cur
        if fallback_prefix:
            fb = _env(f"{fallback_prefix}_{name}", "")
            if fb:
                return fb
        return default

    mode = _get("MODE", "api")
    api_key = _get("API_KEY", fallback_api_key)
    api_base = _get("API_BASE", _env("API_BASE", ""))
    model_name = _get("MODEL_NAME", "")
    model_path = _get("MODEL_PATH", "")
    tp = safe_int(_get("TP", "1")) or 1
    max_new_tokens = safe_int(_get("MAX_NEW_TOKENS", "1024")) or 1024
    max_input_tokens = safe_int(_get("MAX_INPUT_TOKENS", "20000")) or 20000
    gpu_mem = float(_get("GPU_MEMORY_UTILIZATION", "0.9") or 0.9)
    enforce_eager = bool_env(_get("ENFORCE_EAGER", "0"), default=False)
    temperature = float(_get("TEMPERATURE", "0.0") or 0.0)
    top_p = float(_get("TOP_P", "1.0") or 1.0)
    use_sft_default = prefix.upper() == "EXTRACTION"
    use_sft = bool_env(
        _env(f"{prefix}_USE_SFT", _env("USE_SFT", "1" if use_sft_default else "0")),
        default=use_sft_default,
    )
    lora_raw_path = _env(
        f"{prefix}_SFT_LORA_PATH",
        _env(f"{prefix}_LORA_PATH", _env("LORA_PATH", "")),
    )
    sft_tar = _env(f"{prefix}_SFT_TAR", _env("SFT_TAR", ""))
    project_root = (root_dir or Path.cwd()).resolve()
    sft_extract_root = _env(
        f"{prefix}_SFT_EXTRACT_ROOT",
        _env("SFT_EXTRACT_ROOT", str(project_root)),
    )
    sft_dir_name = _env(
        f"{prefix}_SFT_DIR_NAME",
        _env(f"{prefix}_LORA_DIR_NAME", _env("LORA_DIR_NAME", "")),
    )
    lora_name = _env(
        f"{prefix}_SFT_NAME",
        _env(f"{prefix}_LORA_NAME", _env("LORA_NAME", f"{prefix.lower()}_sft")),
    )
    lora_id = safe_int(
        _env(f"{prefix}_SFT_ID", _env(f"{prefix}_LORA_ID", _env("LORA_ID", "1")))
    ) or 1
    resolved_lora_path = ""
    if safe_str(mode).strip().lower() == "local" and use_sft:
        resolved_lora_path = resolve_lora_adapter_path(
            lora_path=lora_raw_path,
            sft_tar=sft_tar,
            sft_extract_root=sft_extract_root,
            sft_dir_name=sft_dir_name,
        )

    return LLMRouter(
        mode=mode,
        api_base=api_base,
        api_key=api_key,
        model_name=model_name,
        model_path=model_path,
        max_new_tokens=max_new_tokens,
        max_input_tokens=max_input_tokens,
        tensor_parallel_size=tp,
        enforce_eager=enforce_eager,
        gpu_memory_utilization=gpu_mem,
        temperature=temperature,
        top_p=top_p,
        lora_path=resolved_lora_path,
        lora_name=lora_name,
        lora_id=lora_id,
    )


class CentralHost:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()

        processed_data_dir = self.root_dir / "data" / "processed"
        self.dataset_csv = _path_env(
            "DATASET_CSV",
            processed_data_dir / "test_data.csv",
            self.root_dir,
        )
        self.few_shot_csv = _path_env(
            "FEW_SHOT_CSV",
            processed_data_dir / "few_shot_selected_train_rows_k3.csv",
            self.root_dir,
        )
        self.case_library_json = _path_env(
            "CASE_LIBRARY_JSON",
            processed_data_dir / "case_library_merged_v1_8.json",
            self.root_dir,
        )
        self.memory_dir = _path_env(
            "MEMORY_DIR",
            self.root_dir / "artifacts" / "memory",
            self.root_dir,
        )
        tool_path_opt = _env("TOOL_PATH", _env("LOCAL_TOOLS_DIR", ""))
        calc_tools_path = (
            Path(tool_path_opt)
            if tool_path_opt
            else self.root_dir / "artifacts" / "calculators" / "gpt_5_5"
        )
        if not calc_tools_path.is_absolute():
            calc_tools_path = self.root_dir / calc_tools_path
        self.calc_tools_dir = calc_tools_path.resolve()
        self.local_tools_only = bool_env(_env("LOCAL_TOOLS_ONLY", "0"), default=False)
        self.output_dir = _path_env("OUTPUT_DIR", self.root_dir / "output", self.root_dir)
        self.result_dir = _path_env("RESULT_DIR", self.root_dir / "result", self.root_dir)
        self.judge_dir = _path_env("JUDGE_DIR", self.root_dir / "judge", self.root_dir)

        for p in (self.output_dir, self.result_dir, self.judge_dir):
            ensure_dir(str(p))

        self.dataset_rows_all = load_csv_rows(str(self.dataset_csv)) if self.dataset_csv.exists() else []
        self.rows_by_calc: Dict[str, List[Dict[str, Any]]] = {}
        self.row_by_number: Dict[str, Dict[str, Any]] = {}
        for row in self.dataset_rows_all:
            cid = _norm_cid(row.get("Calculator ID", ""))
            self.rows_by_calc.setdefault(cid, []).append(row)
            rn = safe_str(row.get("Row Number", "")).strip()
            if rn:
                self.row_by_number[rn] = row

        api_key = _env("API_KEY", "")
        self.central_llm = _build_llm(
            "CENTRAL",
            fallback_api_key=api_key,
            root_dir=self.root_dir,
        )
        self.tool_writer_llm = _build_llm(
            "TOOL_WRITER",
            fallback_api_key=api_key,
            fallback_prefix="CENTRAL",
            root_dir=self.root_dir,
        )
        self.rule_retriever_llm = _build_llm(
            "RULE_RETRIEVER",
            fallback_api_key=api_key,
            fallback_prefix="TOOL_WRITER",
            root_dir=self.root_dir,
        )
        central_mode = _env("CENTRAL_MODE", "").lower()
        extract_mode = _env("EXTRACTION_MODE", "").lower()
        norm_mode = _env("NORMALIZATION_MODE", "").lower()
        central_model_path = safe_str(_env("CENTRAL_MODEL_PATH", "")).strip()
        extract_model_path = safe_str(_env("EXTRACTION_MODEL_PATH", "")).strip()
        norm_model_path = safe_str(_env("NORMALIZATION_MODEL_PATH", "")).strip()
        extract_use_sft = bool_env(
            _env("EXTRACTION_USE_SFT", _env("USE_SFT", "1")),
            default=True,
        )
        self.extract_llm_shared_with_central = False
        share_central_extract = bool_env(_env("SHARE_CENTRAL_AND_EXTRACTION", "0"), default=False)
        can_share_central_extract = (
            share_central_extract
            and central_mode == "local"
            and extract_mode == "local"
            and (not extract_use_sft)
            and central_model_path
            and extract_model_path
            and (Path(central_model_path).resolve() == Path(extract_model_path).resolve())
            and self.central_llm.available
        )
        if can_share_central_extract:
            self.extract_llm = self.central_llm
            self.extract_llm_shared_with_central = True
        else:
            self.extract_llm = _build_llm(
                "EXTRACTION",
                fallback_api_key=api_key,
                root_dir=self.root_dir,
            )
        self.norm_llm_shared_with_central = False
        share_central_norm = bool_env(_env("SHARE_CENTRAL_AND_NORMALIZATION", "0"), default=False)
        norm_use_sft = bool_env(
            _env("NORMALIZATION_USE_SFT", _env("USE_SFT", "0")),
            default=False,
        )

        can_share_central_norm = (
            share_central_norm
            and central_mode == "local"
            and norm_mode == "local"
            and (not norm_use_sft)
            and central_model_path
            and norm_model_path
            and (Path(central_model_path).resolve() == Path(norm_model_path).resolve())
            and self.central_llm.available
        )
        if can_share_central_norm:
            self.norm_llm = self.central_llm
            self.norm_llm_shared_with_central = True
        else:
            self.norm_llm = _build_llm(
                "NORMALIZATION",
                fallback_api_key=api_key,
                root_dir=self.root_dir,
            )

        self.memory = MemoryStore(str(self.memory_dir))
        self.web_searcher = WebSearcher(
            timeout_sec=safe_int(_env("WEB_TIMEOUT_SEC", "15")) or 15,
            max_hits=safe_int(_env("WEB_MAX_HITS", "6")) or 6,
            bing_api_key=_env("BING_API_KEY", ""),
            google_api_key=_env("GOOGLE_API_KEY", ""),
            google_cse_id=_env("GOOGLE_CSE_ID", ""),
        )
        self.disable_case_retriever = bool_env(_env("DISABLE_CASE_RETRIEVER", "0"), default=False)
        self.disable_unit_normalizer = bool_env(_env("DISABLE_UNIT_NORMALIZER", "0"), default=False)
        self.case_searcher = CaseSearcher(
            str(self.few_shot_csv),
            case_library_json=str(self.case_library_json),
        )
        self.formula_writer = FormulaWriter(
            self.tool_writer_llm,
            max_rounds=safe_int(_env("TOOL_WRITER_MAX_ROUNDS", "4")) or 4,
            max_new_tokens=safe_int(_env("TOOL_WRITER_MAX_NEW_TOKENS", _env("CENTRAL_MAX_NEW_TOKENS", "1800")))
            or 1800,
            tool_exec_timeout_sec=safe_int(_env("TOOL_EXEC_TIMEOUT_SEC", "3")) or 3,
        )
        default_extract_rag = self.root_dir / "rag_assets" / "extraction_rag_schema_fewshot_v1_8.json"
        self.extraction_medbench_compat = bool_env(_env("EXTRACTION_MEDBENCH_COMPAT", "0"), default=False)
        self.extraction_force_schema_required = bool_env(
            _env(
                "EXTRACTION_FORCE_SCHEMA_REQUIRED",
                "1" if self.extraction_medbench_compat else "0",
            ),
            default=self.extraction_medbench_compat,
        )
        self.trace_full_llm_io = bool_env(_env("TRACE_FULL_LLM_IO", "0"), default=False)
        if self.disable_case_retriever:
            self.extraction_medbench_compat = False
            self.extraction_force_schema_required = False
        self.param_extractor = ParameterExtractor(
            self.extract_llm,
            medbench_compat=self.extraction_medbench_compat,
            rag_json_path=_env("EXTRACTION_RAG_JSON", str(default_extract_rag)),
            case_library_json_path=str(self.case_library_json),
            fewshot_note_chars=safe_int(_env("EXTRACTION_FEWSHOT_NOTE_CHARS", "900")) or 900,
            patient_note_chars=safe_int(_env("EXTRACTION_PATIENT_NOTE_CHARS", "18000")) or 18000,
            max_tokens=safe_int(_env("EXTRACTION_MAX_NEW_TOKENS", "1400")) or 1400,
            trace_full_llm_io=self.trace_full_llm_io,
        )
        self.normalization_allow_unit_conversion = bool_env(
            _env("NORMALIZATION_ALLOW_UNIT_CONVERSION", "0"),
            default=False,
        )
        self.normalization_enable_llm_fallback = bool_env(
            _env("NORMALIZATION_ENABLE_LLM_FALLBACK", "0"),
            default=False,
        )
        self.unit_normalizer = UnitNormalizer(
            self.norm_llm,
            llm_max_tokens=safe_int(_env("NORMALIZATION_MAX_NEW_TOKENS", "800")) or 800,
            allow_unit_conversion=self.normalization_allow_unit_conversion,
            enable_llm_fallback=self.normalization_enable_llm_fallback,
        )
        self.tool_registry = CalculationToolRegistry(str(self.calc_tools_dir))

        self.max_reflect_rounds = safe_int(_env("MAX_REFLECT_ROUNDS", "1")) or 1
        judge_source = _env("JUDGE_EXTRACTION_SOURCE", "raw").strip().lower()
        self.judge_extraction_source = judge_source if judge_source in {"normalized", "raw"} else "raw"
        policy = _env("TOOL_INPUT_POLICY", "raw_first").strip().lower()
        self.tool_input_policy = policy if policy in {"raw_first", "normalized_first", "raw_only", "normalized_only"} else "raw_first"
        self.enable_central_final_answer = bool_env(_env("ENABLE_CENTRAL_FINAL_ANSWER", "1"), default=True)
        self.require_core_llms_available = bool_env(_env("REQUIRE_CORE_LLMS_AVAILABLE", "0"), default=False)
        if self.require_core_llms_available:
            missing = []
            required_llms = [
                ("central", self.central_llm),
                ("extraction", self.extract_llm),
            ]
            if not self.disable_unit_normalizer:
                required_llms.append(("normalization", self.norm_llm))
            for name, llm in required_llms:
                if not llm.available:
                    missing.append(f"{name}:{llm.init_error or 'unavailable'}")
            if missing:
                raise RuntimeError("required_core_llms_unavailable:" + " | ".join(missing))

    def _sample_eval_rows_for_tool_build(
        self,
        calculator_id: Any,
        current_row_number: Any,
        max_rows: int = 5,
    ) -> List[Dict[str, Any]]:
        cid = _norm_cid(calculator_id)
        rn = safe_str(current_row_number).strip()
        pool = list(self.rows_by_calc.get(cid, []))
        if not pool:
            return []

        out: List[Dict[str, Any]] = []
        cur = self.row_by_number.get(rn)
        if cur and _norm_cid(cur.get("Calculator ID", "")) == cid:
            out.append(cur)
        for row in pool:
            if len(out) >= max(1, int(max_rows)):
                break
            if safe_str(row.get("Row Number", "")).strip() == rn:
                continue
            out.append(row)
        return out[: max(1, int(max_rows))]

    @staticmethod
    def _first_mdcalc_url(source_hits: List[Dict[str, Any]]) -> str:
        for h in source_hits or []:
            u = safe_str((h or {}).get("url", "")).strip()
            if "mdcalc.com" in u.lower():
                return u
        return ""

    def _organize_rule_with_llm(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
        web_evidence_text: str,
        source_hits: List[Dict[str, Any]],
        trace: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.rule_retriever_llm.available:
            return {}

        system = (
            "You are a medical calculator rule curator. "
            "Read web evidence and output STRICT JSON only."
        )
        user = (
            f"Calculator ID: {_norm_cid(calculator_id)}\n"
            f"Calculator Name: {safe_str(calculator_name)}\n"
            f"Question: {safe_str(question)}\n\n"
            "Web evidence snippets:\n"
            f"{safe_str(web_evidence_text)[:12000]}\n\n"
            "Web source hits (JSON):\n"
            f"{json.dumps(source_hits[:8], ensure_ascii=False)}\n\n"
            "Return JSON with fields:\n"
            "{\n"
            '  "mdcalc_title": "string",\n'
            '  "mdcalc_url": "string",\n'
            '  "formula": "string",\n'
            '  "inputs": "string",\n'
            '  "instructions": "string",\n'
            '  "evidence_text": "string"\n'
            "}\n"
            "Do not invent facts absent from evidence."
        )

        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        answer = ""
        error = ""
        try:
            ans = self.rule_retriever_llm.chat(
                messages=messages,
                max_tokens=safe_int(_env("RULE_RETRIEVER_MAX_NEW_TOKENS", "1400")) or 1400,
                temperature=0.0,
                top_p=1.0,
            ).text
            answer = ans
        except Exception as e:
            error = f"rule_retriever_error:{type(e).__name__}:{e}"
            if self.trace_full_llm_io and trace is not None:
                trace["rule_retriever_llm_io"] = {
                    "stage": "rule_retriever",
                    "messages": messages,
                    "max_tokens": safe_int(_env("RULE_RETRIEVER_MAX_NEW_TOKENS", "1400")) or 1400,
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "output": "",
                    "error": error,
                }
            return {}

        if self.trace_full_llm_io and trace is not None:
            trace["rule_retriever_llm_io"] = {
                "stage": "rule_retriever",
                "messages": messages,
                "max_tokens": safe_int(_env("RULE_RETRIEVER_MAX_NEW_TOKENS", "1400")) or 1400,
                "temperature": 0.0,
                "top_p": 1.0,
                "output": answer,
                "error": error,
            }
        obj = extract_first_json_object(answer)
        return obj if isinstance(obj, dict) else {}

    def _resolve_rule_doc(self, row: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
        cid = row.get("Calculator ID", "")
        calc_name = row.get("Calculator Name", "")
        question = row.get("Question", "")

        existing = self.memory.get_rule(cid, calc_name, question)
        if existing:
            trace["rule_source"] = existing.get("source", "memory")
            trace["rule_status"] = "hit"
            return existing

        web = self.web_searcher.search_calculator_rule(
            calculator_id=cid,
            calculator_name=safe_str(calc_name),
            question=safe_str(question),
        )
        source_hits = web.get("source_hits", []) or []
        organized = self._organize_rule_with_llm(
            calculator_id=cid,
            calculator_name=safe_str(calc_name),
            question=safe_str(question),
            web_evidence_text=safe_str(web.get("evidence_text", "")),
            source_hits=source_hits,
            trace=trace,
        )
        mdcalc_url = safe_str(organized.get("mdcalc_url", "")).strip() or self._first_mdcalc_url(source_hits)
        evidence_text = safe_str(organized.get("evidence_text", "")).strip() or safe_str(web.get("evidence_text", ""))
        saved = self.memory.save_web_rule(
            calculator_id=cid,
            calculator_name=safe_str(calc_name),
            question=safe_str(question),
            evidence_text=evidence_text,
            source_hits=source_hits,
            mdcalc_title=safe_str(organized.get("mdcalc_title", "")).strip() or safe_str(calc_name),
            mdcalc_url=mdcalc_url,
            formula=safe_str(organized.get("formula", "")).strip(),
            inputs=safe_str(organized.get("inputs", "")).strip(),
            instructions=safe_str(organized.get("instructions", "")).strip(),
            source="web_search_codex" if organized else "web_search_raw",
            web_fetch_status="ok" if source_hits else "empty",
        )
        trace["rule_source"] = saved.get("source", "web_search_codex")
        trace["rule_status"] = "miss_then_web"
        trace["web_search_hits"] = source_hits
        trace["rule_organized_with_llm"] = bool(organized)
        return saved

    def _ensure_tool(self, row: Dict[str, Any], rule_doc: Dict[str, Any], case_examples: List[Dict[str, Any]], trace: Dict[str, Any]) -> Dict[str, Any]:
        cid = row.get("Calculator ID", "")
        calc_name = row.get("Calculator Name", "")
        question = row.get("Question", "")

        local_required = self.tool_registry.latest_required_entities(cid)
        if not local_required:
            local_required = self.tool_registry.infer_required_entities_from_tool(cid)

        if self.tool_registry.has_tool(cid):
            trace["tool_reused"] = True
            trace["tool_source"] = "local_tools_dir"
            return {
                "calculator_id": _norm_cid(cid),
                "calculator_name": safe_str(calc_name),
                "required_entities": local_required,
                "tool_code": "",
                "source": "local_tools_dir",
                "error": "",
            }

        tool_spec = self.memory.latest_tool_spec(cid)
        if tool_spec and safe_str(tool_spec.get("tool_code", "")).strip():
            req = tool_spec.get("required_entities", []) or local_required
            code = safe_str(tool_spec.get("tool_code", ""))
            source = safe_str(tool_spec.get("source", "memory")) or "memory"
            reg = self.tool_registry.register_tool(
                calculator_id=cid,
                calculator_name=safe_str(calc_name),
                required_entities=req,
                tool_code=code,
                source=f"{source}_restore",
            )
            trace["tool_reused"] = True
            trace["tool_source"] = "memory_restore"
            return {
                "calculator_id": _norm_cid(cid),
                "calculator_name": safe_str(calc_name),
                "required_entities": req,
                "tool_code": code,
                "source": f"{source}_restore",
                "registration": reg,
                "error": "",
            }

        if self.local_tools_only:
            trace["tool_reused"] = False
            trace["tool_generation"] = {
                "source": "disabled_by_LOCAL_TOOLS_ONLY",
                "required_entities": local_required,
                "error": "local_tool_missing_and_generation_disabled",
                "valid": False,
                "validation_message": "tool_not_found_in_TOOL_PATH",
                "rounds": [],
                "usage": {},
                "sample_eval_rows": [],
            }
            return {
                "calculator_id": _norm_cid(cid),
                "calculator_name": safe_str(calc_name),
                "required_entities": local_required,
                "tool_code": "",
                "source": "local_tools_only",
                "error": "local_tool_missing_and_generation_disabled",
            }

        eval_rows = self._sample_eval_rows_for_tool_build(
            calculator_id=cid,
            current_row_number=row.get("Row Number", ""),
            max_rows=safe_int(_env("TOOL_WRITER_SAMPLE_PER_CALC", "5")) or 5,
        )
        generated = self.formula_writer.build_tool(
            calculator_id=cid,
            calculator_name=safe_str(calc_name),
            question=safe_str(question),
            rule_doc=rule_doc,
            case_examples=case_examples,
            sample_eval_rows=eval_rows,
        )

        req = generated.get("required_entities", []) or []
        code = safe_str(generated.get("tool_code", ""))
        source = safe_str(generated.get("source", "llm"))

        reg = self.tool_registry.register_tool(
            calculator_id=cid,
            calculator_name=safe_str(calc_name),
            required_entities=req,
            tool_code=code,
            source=source,
        )

        self.memory.record_tool_spec(
            calculator_id=cid,
            calculator_name=safe_str(calc_name),
            required_entities=req,
            tool_code=code,
            source=source,
        )

        out = {
            "calculator_id": _norm_cid(cid),
            "calculator_name": safe_str(calc_name),
            "required_entities": req,
            "tool_code": code,
            "source": source,
            "registration": reg,
            "error": generated.get("error", ""),
        }
        trace["tool_reused"] = False
        trace["tool_generation"] = {
            "source": source,
            "required_entities": req,
            "error": generated.get("error", ""),
            "valid": reg.get("valid", False),
            "validation_message": reg.get("validation_message", ""),
            "rounds": generated.get("rounds", []),
            "usage": generated.get("usage", {}),
            "sample_eval_rows": [
                {
                    "Row Number": x.get("Row Number", ""),
                    "Ground Truth Answer": x.get("Ground Truth Answer", ""),
                    "Lower Limit": x.get("Lower Limit", ""),
                    "Upper Limit": x.get("Upper Limit", ""),
                }
                for x in eval_rows
            ],
        }
        return out

    def _extract_with_reflection(
        self,
        row: Dict[str, Any],
        rule_doc: Dict[str, Any],
        required_entities: List[str],
        case_examples: List[Dict[str, Any]],
        trace: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
        cid = row.get("Calculator ID", "")
        calc_name = row.get("Calculator Name", "")
        question = row.get("Question", "")
        note = row.get("Patient Note", "")

        rounds: List[Dict[str, Any]] = []
        last_entities: Dict[str, Any] = {}
        last_norm: Dict[str, Any] = {"normalized_entities": {}, "missing_required_params": []}

        for ridx in range(self.max_reflect_rounds + 1):
            missing_hint = self.memory.build_missing_hint(cid)
            if ridx > 0 and last_norm.get("missing_required_params"):
                missing_hint = (missing_hint + " ; ".join(last_norm.get("missing_required_params", []))).strip(" ;")

            extracted = self.param_extractor.extract(
                calculator_id=cid,
                calculator_name=safe_str(calc_name),
                question=safe_str(question),
                patient_note=safe_str(note),
                rule_text=safe_str(rule_doc.get("evidence_text", "") or rule_doc.get("text", "")),
                required_entities=required_entities,
                case_examples=case_examples,
                missing_hint=missing_hint,
            )
            entities = extracted.get("relevant_entities", {}) or {}
            if self.disable_unit_normalizer:
                normalized = {
                    "normalized_entities": entities,
                    "missing_required_params": [],
                    "reflection": {"disabled_by_config": True},
                }
            else:
                normalized = self.unit_normalizer.normalize(
                    extracted_entities=entities,
                    required_entities=required_entities,
                    rule_text=safe_str(rule_doc.get("evidence_text", "") or rule_doc.get("text", "")),
                )

            missing = normalized.get("missing_required_params", []) or []
            rounds.append(
                {
                    "round": ridx,
                    "extract_error": extracted.get("error", ""),
                    "extract_mode": extracted.get("mode", ""),
                    "extract_entities": entities,
                    "llm_io": extracted.get("llm_io", []),
                    "normalize_reflection": normalized.get("reflection", {}),
                    "missing_required_params": missing,
                }
            )

            last_entities = entities
            last_norm = normalized

            if not missing:
                break

            self.memory.record_missing_params(
                row_number=row.get("Row Number", ""),
                calculator_id=cid,
                calculator_name=safe_str(calc_name),
                missing_params=missing,
                extracted_entities=entities,
                note_id=row.get("Note ID", ""),
                question=safe_str(question),
            )

        trace["extract_rounds"] = rounds
        return last_entities, last_norm, rounds

    @staticmethod
    def _is_unusable_tool_result(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            s = safe_str(v).strip().lower()
            if s in {"", "n/a", "na", "none", "null"}:
                return True
        return False

    def _execute_tool_with_policy(
        self,
        calculator_id: Any,
        raw_entities: Dict[str, Any],
        normalized_entities: Dict[str, Any],
    ):
        attempts: List[Tuple[str, Dict[str, Any]]] = []
        raw_pack = raw_entities or {}
        norm_pack = normalized_entities or {}
        if self.tool_input_policy == "raw_only":
            attempts = [("raw", raw_pack)]
        elif self.tool_input_policy == "normalized_only":
            attempts = [("normalized", norm_pack)]
        elif self.tool_input_policy == "normalized_first":
            attempts = [("normalized", norm_pack), ("raw", raw_pack)]
        else:
            attempts = [("raw", raw_pack), ("normalized", norm_pack)]

        if len(attempts) > 1 and (
            attempts[0][1] is attempts[1][1] or attempts[0][1] == attempts[1][1]
        ):
            attempts = attempts[:1]

        selected_source = attempts[0][0] if attempts else "raw"
        selected_input = attempts[0][1] if attempts else {}
        selected_exec = None
        attempt_logs: List[Dict[str, Any]] = []

        for idx, (source, pack) in enumerate(attempts):
            exec_ret = self.tool_registry.calculate(calculator_id=calculator_id, relevant=pack)
            attempt_logs.append(
                {
                    "index": idx,
                    "source": source,
                    "tool_name": exec_ret.tool_name,
                    "tool_error": exec_ret.error,
                    "result_preview": safe_str(exec_ret.result)[:200],
                    "result_unusable": self._is_unusable_tool_result(exec_ret.result),
                }
            )
            if not exec_ret.error and not self._is_unusable_tool_result(exec_ret.result):
                selected_source = source
                selected_input = pack
                selected_exec = exec_ret
                break
            # Keep first attempt as fallback if all attempts fail/unusable.
            if idx == 0:
                selected_source = source
                selected_input = pack
                selected_exec = exec_ret

        if selected_exec is None:
            selected_exec = self.tool_registry.calculate(calculator_id=calculator_id, relevant=selected_input)

        return selected_source, selected_input, selected_exec, attempt_logs

    def _central_finalize_answer(
        self,
        row: Dict[str, Any],
        tool_output: Any,
        tool_input: Dict[str, Any],
        tool_name: str,
    ) -> Tuple[str, str, Dict[str, Any]]:
        fallback = safe_str(tool_output)
        if not self.enable_central_final_answer:
            return fallback, "disabled_by_config", {}
        if not self.central_llm.available:
            return fallback, f"central_llm_unavailable:{self.central_llm.init_error}", {}

        payload = (
            f"Calculator Name: {safe_str(row.get('Calculator Name', ''))}\n"
            f"Question: {safe_str(row.get('Question', ''))}\n"
            f"Tool Name: {safe_str(tool_name)}\n"
            f"Tool Input JSON: {json.dumps(tool_input or {}, ensure_ascii=False)}\n"
            f"Tool Output: {json.dumps(tool_output, ensure_ascii=False) if not isinstance(tool_output, str) else safe_str(tool_output)}\n\n"
            "Please output the final answer for this question, grounded on the tool output. "
            "Keep it concise and do not invent additional values."
        )

        messages = [
            {
                "role": "system",
                "content": "You are a medical calculator assistant. Return the final answer based on provided tool output.",
            },
            {"role": "user", "content": payload},
        ]
        llm_io: Dict[str, Any] = {}
        try:
            ans = self.central_llm.chat(
                messages=messages,
                max_tokens=safe_int(_env("CENTRAL_FINAL_MAX_NEW_TOKENS", "256")) or 256,
                temperature=0.0,
                top_p=1.0,
            ).text
            text = safe_str(ans).strip()
            if self.trace_full_llm_io:
                llm_io = {
                    "stage": "central_final_answer",
                    "messages": messages,
                    "max_tokens": safe_int(_env("CENTRAL_FINAL_MAX_NEW_TOKENS", "256")) or 256,
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "output": ans,
                    "error": "",
                }
            return (text or fallback), "", llm_io
        except Exception as e:
            error = f"central_finalize_error:{type(e).__name__}:{e}"
            if self.trace_full_llm_io:
                llm_io = {
                    "stage": "central_final_answer",
                    "messages": messages,
                    "max_tokens": safe_int(_env("CENTRAL_FINAL_MAX_NEW_TOKENS", "256")) or 256,
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "output": "",
                    "error": error,
                }
            return fallback, error, llm_io

    def run_one_case(self, row: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        row_number = row.get("Row Number", "")
        cid = row.get("Calculator ID", "")
        calc_name = row.get("Calculator Name", "")

        trace: Dict[str, Any] = {
            "time": now_str(),
            "row_number": row_number,
            "calculator_id": _norm_cid(cid),
            "calculator_name": safe_str(calc_name),
            "question": row.get("Question", ""),
            "note_id": row.get("Note ID", ""),
        }

        rule_doc = self._resolve_rule_doc(row, trace)
        if self.disable_case_retriever:
            case_examples = []
            trace["case_retriever_disabled"] = True
        else:
            case_examples = self.case_searcher.retrieve(
                calculator_id=cid,
                calculator_name=safe_str(calc_name),
                question=safe_str(row.get("Question", "")),
                patient_note=safe_str(row.get("Patient Note", "")),
                top_k=safe_int(_env("CASE_SEARCH_TOPK", "3")) or 3,
            )
            self.memory.record_case_examples(
                row_number=row_number,
                calculator_id=cid,
                calculator_name=safe_str(calc_name),
                examples=case_examples,
            )
        trace["case_examples"] = case_examples

        tool_spec = self._ensure_tool(row, rule_doc, case_examples, trace)
        required_entities = tool_spec.get("required_entities", []) or []
        if not required_entities:
            required_entities = self.tool_registry.latest_required_entities(cid)
        schema_required = self.param_extractor.schema_required_fields(cid)
        if self.extraction_force_schema_required and schema_required:
            required_entities = schema_required
            trace["required_entities_source"] = "extraction_rag_schema"
        elif required_entities:
            trace["required_entities_source"] = "tool_or_registry"
        else:
            trace["required_entities_source"] = "empty"
        trace["required_entities"] = required_entities

        extracted_entities, normalized_pack, _rounds = self._extract_with_reflection(
            row=row,
            rule_doc=rule_doc,
            required_entities=required_entities,
            case_examples=case_examples,
            trace=trace,
        )

        normalized_tool_input = normalized_pack.get("normalized_entities", {}) or {}
        (
            selected_tool_input_source,
            tool_input,
            tool_exec,
            tool_exec_attempts,
        ) = self._execute_tool_with_policy(
            calculator_id=cid,
            raw_entities=extracted_entities,
            normalized_entities=normalized_tool_input,
        )
        final_answer_text, final_answer_error, final_answer_llm_io = self._central_finalize_answer(
            row=row,
            tool_output=tool_exec.result,
            tool_input=tool_input,
            tool_name=tool_exec.tool_name,
        )

        judge_raw = judge_case(
            row=row,
            extracted_entities=extracted_entities,
            tool_result_raw=tool_exec.result,
        )
        judge_normalized = judge_case(
            row=row,
            extracted_entities=tool_input,
            tool_result_raw=tool_exec.result,
        )
        judge = judge_raw if self.judge_extraction_source == "raw" else judge_normalized

        trace["tool_call"] = {
            "tool_name": tool_exec.tool_name,
            "tool_input_source": selected_tool_input_source,
            "tool_input": tool_input,
            "tool_output": tool_exec.result,
            "tool_error": tool_exec.error,
            "tool_attempts": tool_exec_attempts,
        }
        trace["final_answer"] = {
            "text": final_answer_text,
            "error": final_answer_error,
            "llm_io": final_answer_llm_io,
        }
        trace["judge"] = judge
        trace["judge_raw_extraction"] = judge_raw
        trace["judge_normalized_input"] = judge_normalized

        result_row = {
            "Row Number": row_number,
            "Calculator ID": _norm_cid(cid),
            "Calculator Name": safe_str(calc_name),
            "Category": safe_str(row.get("Category", "")),
            "Note ID": safe_str(row.get("Note ID", "")),
            "Question": safe_str(row.get("Question", "")),
            "Raw Extracted Relevant Entities": extracted_entities,
            "Normalized Relevant Entities": normalized_tool_input,
            "Tool Input Source": selected_tool_input_source,
            "Tool Input Relevant Entities": tool_input,
            "Tool Name": tool_exec.tool_name,
            "Tool Output": tool_exec.result,
            "Tool Error": tool_exec.error,
            "Final Answer (Central)": final_answer_text,
            "Final Answer Error (Central)": final_answer_error,
            "Computed Answer": judge.get("computed_answer", "N/A"),
            "Ground Truth Answer": row.get("Ground Truth Answer", ""),
            "Result": "Correct" if judge.get("final_correct") else "Incorrect",
            "Falsified": 0 if judge.get("final_correct") else 1,
            "Judge": judge,
            "Judge Raw Extraction": judge_raw,
            "Judge Normalized Input": judge_normalized,
        }
        return result_row, trace

    def run_dataset(self, limit: int = 0, start_row: int = 0) -> Dict[str, Any]:
        rows = load_csv_rows(str(self.dataset_csv))
        if start_row > 0:
            rows = [r for r in rows if (safe_int(r.get("Row Number")) or 0) >= start_row]
        if limit > 0:
            rows = rows[:limit]

        ts = now_compact()
        output_steps_path = self.output_dir / f"case_steps_{ts}.jsonl"
        result_jsonl_path = self.result_dir / f"run_result_{ts}.jsonl"
        result_summary_path = self.result_dir / f"run_summary_{ts}.json"
        judge_jsonl_path = self.judge_dir / f"judge_result_{ts}.jsonl"
        judge_summary_path = self.judge_dir / f"judge_summary_{ts}.json"

        result_rows: List[Dict[str, Any]] = []
        judge_rows: List[Dict[str, Any]] = []
        judge_rows_raw: List[Dict[str, Any]] = []
        judge_rows_normalized: List[Dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            result_row, trace = self.run_one_case(row)
            append_jsonl(str(output_steps_path), [trace])
            append_jsonl(str(result_jsonl_path), [result_row])

            judge_rows.append(
                {
                    "Row Number": result_row.get("Row Number"),
                    "Calculator ID": result_row.get("Calculator ID"),
                    "calculator_name": result_row.get("Calculator Name"),
                    "judge": result_row.get("Judge", {}),
                    "result": result_row.get("Result", ""),
                }
            )
            append_jsonl(str(judge_jsonl_path), [judge_rows[-1]])
            result_rows.append(result_row)
            judge_rows_raw.append(
                {
                    "Row Number": result_row.get("Row Number"),
                    "Calculator ID": result_row.get("Calculator ID"),
                    "calculator_name": result_row.get("Calculator Name"),
                    "judge": result_row.get("Judge Raw Extraction", result_row.get("Judge", {})),
                    "result": result_row.get("Result", ""),
                }
            )
            judge_rows_normalized.append(
                {
                    "Row Number": result_row.get("Row Number"),
                    "Calculator ID": result_row.get("Calculator ID"),
                    "calculator_name": result_row.get("Calculator Name"),
                    "judge": result_row.get("Judge Normalized Input", result_row.get("Judge", {})),
                    "result": result_row.get("Result", ""),
                }
            )

            if idx % 20 == 0:
                print(f"[Progress] {idx}/{len(rows)}", flush=True)

        summary = summarize(judge_rows)
        raw_extraction_summary = summarize(judge_rows_raw)
        normalized_extraction_summary = summarize(judge_rows_normalized)
        summary.update(
            {
                "time": now_str(),
                "dataset_csv": str(self.dataset_csv),
                "cases": len(rows),
                "output_steps_jsonl": str(output_steps_path),
                "result_jsonl": str(result_jsonl_path),
                "judge_jsonl": str(judge_jsonl_path),
                "central_llm_available": self.central_llm.available,
                "tool_writer_llm_available": self.tool_writer_llm.available,
                "rule_retriever_llm_available": self.rule_retriever_llm.available,
                "extract_llm_available": self.extract_llm.available,
                "normalize_llm_available": self.norm_llm.available,
                "central_llm_error": self.central_llm.init_error,
                "tool_writer_llm_error": self.tool_writer_llm.init_error,
                "rule_retriever_llm_error": self.rule_retriever_llm.init_error,
                "extract_llm_error": self.extract_llm.init_error,
                "normalize_llm_error": self.norm_llm.init_error,
                "tool_path": str(self.calc_tools_dir),
                "case_library_json": str(self.case_library_json),
                "local_tools_only": bool(self.local_tools_only),
                "norm_llm_shared_with_central": bool(self.norm_llm_shared_with_central),
                "extract_llm_shared_with_central": bool(self.extract_llm_shared_with_central),
                "judge_extraction_source": self.judge_extraction_source,
                "legacy_evaluator": True,
                "tool_input_policy": self.tool_input_policy,
                "enable_central_final_answer": bool(self.enable_central_final_answer),
                "require_core_llms_available": bool(self.require_core_llms_available),
                "disable_case_retriever": bool(self.disable_case_retriever),
                "disable_unit_normalizer": bool(self.disable_unit_normalizer),
                "extraction_medbench_compat": bool(self.extraction_medbench_compat),
                "extraction_force_schema_required": bool(self.extraction_force_schema_required),
                "normalization_allow_unit_conversion": bool(self.normalization_allow_unit_conversion),
                "normalization_enable_llm_fallback": bool(self.normalization_enable_llm_fallback),
                "trace_full_llm_io": bool(self.trace_full_llm_io),
                "raw_extraction_summary": {
                    "total_params": raw_extraction_summary.get("total_params", 0),
                    "matched_params": raw_extraction_summary.get("matched_params", 0),
                    "param_match_rate": raw_extraction_summary.get("param_match_rate", 0.0),
                    "all_params_correct_cases": raw_extraction_summary.get("all_params_correct_cases", 0),
                },
                "normalized_input_extraction_summary": {
                    "total_params": normalized_extraction_summary.get("total_params", 0),
                    "matched_params": normalized_extraction_summary.get("matched_params", 0),
                    "param_match_rate": normalized_extraction_summary.get("param_match_rate", 0.0),
                    "all_params_correct_cases": normalized_extraction_summary.get("all_params_correct_cases", 0),
                },
            }
        )

        write_json(str(result_summary_path), summary, indent=2)
        write_json(str(judge_summary_path), summary, indent=2)

        return {
            "summary": summary,
            "output_steps_jsonl": str(output_steps_path),
            "result_jsonl": str(result_jsonl_path),
            "result_summary_json": str(result_summary_path),
            "judge_jsonl": str(judge_jsonl_path),
            "judge_summary_json": str(judge_summary_path),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="MedAgent central host pipeline")
    parser.add_argument(
        "--root-dir",
        "--root_dir",
        dest="root_dir",
        default=str(Path.cwd()),
    )
    parser.add_argument("--env-file", "--env_file", dest="env_file", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start-row", "--start_row", dest="start_row", type=int, default=0)
    args = parser.parse_args()

    root_dir = Path(args.root_dir).expanduser().resolve()
    env_file = args.env_file or str(root_dir / "runtime.env")
    load_env_file(env_file)
    host = CentralHost(root_dir)
    outputs = host.run_dataset(limit=args.limit, start_row=args.start_row)

    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
