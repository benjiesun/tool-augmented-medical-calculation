import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .prompts import build_extraction_prompt
from .utils import LLMRouter, extract_first_json_object, safe_str


def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", safe_str(s).lower())


def _extract_number(text: str) -> str:
    m = re.search(r"-?\d+(?:\.\d+)?", text)
    return m.group(0) if m else ""


def _extract_with_regex(note: str, key: str):
    n = safe_str(note)
    k = _norm_key(key)

    patterns = {
        "age": r"(\d{1,3})\s*(?:-?year-old|years? old|years?)",
        "weight": r"(?:weight|wt)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(kg|kilograms?|lb|lbs|pounds?)",
        "height": r"(?:height|ht)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|m|in|inch|inches)",
        "creatinine": r"(?:creatinine|scr|serum creatinine)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mg/dl|umol/l|μmol/l|µmol/l)?",
        "systolicbloodpressure": r"(?:systolic(?: blood pressure)?|sbp)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mmhg)?",
        "diastolicbloodpressure": r"(?:diastolic(?: blood pressure)?|dbp)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(mmhg)?",
    }

    if k in {"sex", "gender"}:
        if re.search(r"\bfemale\b", n, flags=re.I):
            return "Female"
        if re.search(r"\bmale\b", n, flags=re.I):
            return "Male"
        return None

    pat = patterns.get(k)
    if pat:
        m = re.search(pat, n, flags=re.I)
        if not m:
            return None
        if len(m.groups()) >= 2 and m.group(2):
            try:
                num = float(m.group(1))
            except Exception:
                num = _extract_number(m.group(1))
            unit = m.group(2)
            return [num, unit]
        if m.groups():
            try:
                return float(m.group(1))
            except Exception:
                return m.group(1)

    generic = re.search(rf"{re.escape(key)}[^\d-]*(-?\d+(?:\.\d+)?)", n, flags=re.I)
    if generic:
        v = generic.group(1)
        try:
            return float(v)
        except Exception:
            return v
    return None


def _trim(text: Any, limit: int) -> str:
    s = safe_str(text)
    if limit <= 0 or len(s) <= limit:
        return s
    return s[:limit].rstrip() + "\n[TRUNCATED]"


def _json_value_schema() -> Dict[str, Any]:
    return {
        "anyOf": [
            {"type": "string"},
            {"type": "number"},
            {"type": "integer"},
            {"type": "boolean"},
            {"type": "null"},
            {
                "type": "array",
                "items": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "number"},
                        {"type": "integer"},
                        {"type": "boolean"},
                        {"type": "null"},
                    ]
                },
            },
            {"type": "object"},
        ]
    }


def _schema_for_fields(fields: Iterable[str]) -> Dict[str, Any]:
    field_list = [safe_str(x).strip() for x in fields if safe_str(x).strip()]
    return {
        "type": "object",
        "properties": {field: _json_value_schema() for field in field_list},
        "required": field_list,
        "additionalProperties": False,
    }


def _output_schema_for_calc(calc: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    field_list = [safe_str(x).strip() for x in fields if safe_str(x).strip()]
    field_specs = ((calc.get("schema", {}) or {}).get("fields", {}) or {}) if isinstance(calc, dict) else {}
    properties: Dict[str, Any] = {}
    for field in field_list:
        spec = field_specs.get(field, {}) if isinstance(field_specs, dict) else {}
        kind = safe_str((spec or {}).get("value_kind", "")).strip().lower()
        units = (spec or {}).get("units", []) or []
        enum = (spec or {}).get("enum", []) or []
        allow_null = bool((spec or {}).get("allow_null", True))
        if kind == "boolean":
            properties[field] = {"type": ["boolean", "null"]}
        elif kind == "string":
            properties[field] = {"type": ["string", "null"] if allow_null else "string"}
            if enum:
                properties[field]["enum"] = list(enum) + ([None] if allow_null and None not in enum else [])
        elif kind in {"numeric_with_unit", "number", "numeric"}:
            unit_item: Dict[str, Any] = {"type": "string"}
            if units:
                unit_item["enum"] = list(units)
            alternatives: List[Dict[str, Any]] = [
                {"type": "number"},
                {
                    "type": "array",
                    "prefixItems": [{"type": "number"}, unit_item],
                    "minItems": 2,
                    "maxItems": 2,
                },
            ]
            if allow_null:
                alternatives.insert(0, {"type": "null"})
            properties[field] = {
                "anyOf": alternatives
            }
        else:
            properties[field] = _json_value_schema()
    return {
        "type": "object",
        "required": field_list,
        "additionalProperties": False,
        "properties": properties,
    }


def _complete_entities_for_fields(entities: Dict[str, Any], calc: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    field_specs = ((calc.get("schema", {}) or {}).get("fields", {}) or {}) if isinstance(calc, dict) else {}
    out: Dict[str, Any] = {}
    for field in fields:
        if field in entities:
            out[field] = entities[field]
            continue
        spec = field_specs.get(field, {}) if isinstance(field_specs, dict) else {}
        kind = safe_str((spec or {}).get("value_kind", "")).strip().lower()
        out[field] = False if kind == "boolean" else None
    return out


def _schema_violations(entities: Dict[str, Any], calc: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    field_specs = ((calc.get("schema", {}) or {}).get("fields", {}) or {}) if isinstance(calc, dict) else {}
    violations: List[str] = []
    for field in fields:
        spec = field_specs.get(field, {}) if isinstance(field_specs, dict) else {}
        value = entities.get(field)
        allow_null = bool((spec or {}).get("allow_null", True))
        enum = (spec or {}).get("enum", []) or []
        units = (spec or {}).get("units", []) or []
        if value is None:
            if not allow_null:
                violations.append(f"{field} must not be null")
            continue
        if enum and value not in enum:
            violations.append(f"{field} must be one of {enum}")
        if units and isinstance(value, (list, tuple)) and len(value) >= 2 and value[1] not in units:
            violations.append(f"{field} unit must be one of {units}")
    return violations


def _format_field_specs(calc: Dict[str, Any], fields: Iterable[str]) -> str:
    field_specs = ((calc.get("schema", {}) or {}).get("fields", {}) or {}) if isinstance(calc, dict) else {}
    lines: List[str] = []
    for field in fields:
        spec = field_specs.get(field, {}) if isinstance(field_specs, dict) else {}
        attrs = [
            f"kind={safe_str((spec or {}).get('value_kind', 'any') or 'any')}",
            f"value_type={safe_str((spec or {}).get('value_type', 'any') or 'any')}",
        ]
        units = (spec or {}).get("units", []) or []
        enum = (spec or {}).get("enum", []) or []
        if units:
            attrs.append(f"units={json.dumps(units, ensure_ascii=False)}")
        if enum:
            attrs.append(f"allowed_values={json.dumps(enum, ensure_ascii=False)}")
        lines.append(f"- {field}: " + ", ".join(attrs))
    return "\n".join(lines)


class ParameterExtractor:
    def __init__(
        self,
        llm: LLMRouter,
        medbench_compat: bool = False,
        rag_json_path: str = "",
        case_library_json_path: str = "",
        fewshot_note_chars: int = 900,
        patient_note_chars: int = 18000,
        max_tokens: int = 1400,
        trace_full_llm_io: bool = False,
    ):
        self.llm = llm
        self.medbench_compat = bool(medbench_compat)
        self.rag_json_path = safe_str(rag_json_path).strip()
        self.case_library_json_path = safe_str(case_library_json_path).strip()
        self.fewshot_note_chars = max(0, int(fewshot_note_chars))
        self.patient_note_chars = max(0, int(patient_note_chars))
        self.max_tokens = max(200, int(max_tokens))
        self.trace_full_llm_io = bool(trace_full_llm_io)
        self.case_library_by_cid = self._load_case_library_map(self.case_library_json_path) if self.medbench_compat else {}
        self.rag_by_cid = self._load_rag_map(self.rag_json_path) if self.medbench_compat else {}

    @staticmethod
    def _norm_cid(v: Any) -> str:
        s = safe_str(v).strip()
        try:
            return str(int(float(s)))
        except Exception:
            return s

    def _load_rag_map(self, path: str) -> Dict[str, Dict[str, Any]]:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        for item in obj.get("calculators", []) if isinstance(obj, dict) else []:
            cid = self._norm_cid(item.get("calculator_id", ""))
            if cid:
                out[cid] = item
        return out

    def _load_case_library_map(self, path: str) -> Dict[str, Dict[str, Any]]:
        p = Path(path)
        if not p.exists():
            return {}
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
        out: Dict[str, Dict[str, Any]] = {}
        calculators = obj.get("calculators", []) if isinstance(obj, dict) else []
        for item in calculators if isinstance(calculators, list) else []:
            if not isinstance(item, dict):
                continue
            cid = self._norm_cid(item.get("calculator_id", ""))
            if cid:
                out[cid] = item
        return out

    def schema_required_fields(self, calculator_id: Any) -> List[str]:
        cid = self._norm_cid(calculator_id)
        calc = self.case_library_by_cid.get(cid) or self.rag_by_cid.get(cid, {})
        fields = calc.get("schema", {}).get("required_fields", []) if isinstance(calc, dict) else []
        out = [safe_str(x).strip() for x in fields if safe_str(x).strip()]
        return out

    @staticmethod
    def _fewshot_examples_from_calc(calc: Dict[str, Any]) -> List[Dict[str, Any]]:
        few_shot_examples = ((calc.get("few_shot", {}) or {}).get("examples", []) or [])
        if isinstance(few_shot_examples, list) and few_shot_examples:
            return [x for x in few_shot_examples if isinstance(x, dict)]
        cases = calc.get("cases", [])
        if isinstance(cases, list) and cases:
            return [x for x in cases if isinstance(x, dict)]
        return []

    def _format_fewshot(self, calc: Dict[str, Any], fields: Iterable[str]) -> str:
        chunks: List[str] = []
        examples = self._fewshot_examples_from_calc(calc)[:3]
        for idx, ex in enumerate(examples, start=1):
            entities = _complete_entities_for_fields(ex.get("relevant_entities") or {}, calc, fields)
            chunks.append(
                "\n".join(
                    [
                        f"Example {idx}",
                        f"Question: {safe_str(ex.get('question', ''))}",
                        f"Patient Note: {_trim(ex.get('patient_note', ''), self.fewshot_note_chars)}",
                        "Output JSON:",
                        json.dumps(entities, ensure_ascii=False, sort_keys=False),
                    ]
                )
            )
        return "\n\n".join(chunks)

    def _build_medbench_prompt(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
        patient_note: str,
        required_entities: List[str],
        calc: Dict[str, Any],
    ) -> str:
        fields = calc.get("schema", {}).get("required_fields", []) or required_entities
        fields = [safe_str(x).strip() for x in fields if safe_str(x).strip()]
        fewshot = self._format_fewshot(calc, fields)
        output_schema = _output_schema_for_calc(calc, fields)
        return build_extraction_prompt(
            self._norm_cid(calculator_id), safe_str(calc.get("calculator_name", calculator_name)),
            safe_str(question), _trim(patient_note, self.patient_note_chars), fields,
            output_schema, _format_field_specs(calc, fields), fewshot,
        )

    def _fallback_extract(self, note: str, required_entities: List[str]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key in required_entities:
            v = _extract_with_regex(note, key)
            if v is not None:
                out[key] = v
        return out

    def extract(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
        patient_note: str,
        rule_text: str,
        required_entities: List[str],
        case_examples: List[Dict[str, Any]],
        missing_hint: str = "",
    ) -> Dict[str, Any]:
        required_entities = [safe_str(x).strip() for x in required_entities if safe_str(x).strip()]

        if self.medbench_compat:
            schema_fields = self.schema_required_fields(calculator_id)
            if schema_fields:
                required_entities = schema_fields

        generic_calc = {
            "schema": {"required_fields": required_entities},
            "few_shot": {"examples": case_examples[:3]},
        }
        messages = [{"role": "user", "content": self._build_medbench_prompt(
            calculator_id, calculator_name, question, patient_note, required_entities, generic_calc,
        )}]
        llm_io: List[Dict[str, Any]] = []

        def record_llm_io(
            stage: str,
            request_messages: List[Dict[str, Any]],
            output: str,
            call_error: str = "",
            json_schema: Optional[Dict[str, Any]] = None,
        ) -> None:
            if not self.trace_full_llm_io:
                return
            call: Dict[str, Any] = {
                "stage": stage,
                "messages": request_messages,
                "max_tokens": self.max_tokens,
                "temperature": 0.0,
                "top_p": 1.0,
                "output": output,
                "error": call_error,
            }
            if json_schema is not None:
                call["json_schema"] = json_schema
            llm_io.append(call)

        if not self.llm.available:
            fallback = self._fallback_extract(patient_note, required_entities)
            return {
                "relevant_entities": fallback,
                "raw_model_output": "",
                "error": "llm_unavailable",
                "mode": "fallback_regex",
                "llm_io": llm_io,
            }

        answer = ""
        error = ""
        mode = "figure2_generic"
        strict_schema = False
        strict_calc: Dict[str, Any] = {}
        strict_prompt = ""
        strict_output_schema: Dict[str, Any] = {}

        if self.medbench_compat:
            cid = self._norm_cid(calculator_id)
            calc = self.case_library_by_cid.get(cid) or self.rag_by_cid.get(cid, {})
            if calc:
                medbench_prompt = self._build_medbench_prompt(
                    calculator_id=calculator_id,
                    calculator_name=calculator_name,
                    question=question,
                    patient_note=patient_note,
                    required_entities=required_entities,
                    calc=calc,
                )
                strict_schema = bool((calc.get("schema", {}) or {}).get("enforce_output_constraints", False))
                schema = (
                    _output_schema_for_calc(calc, required_entities)
                    if strict_schema
                    else _schema_for_fields(required_entities)
                )
                strict_calc = calc
                strict_prompt = medbench_prompt
                strict_output_schema = schema
                mode = "medbench_compatible_strict_schema" if strict_schema else "medbench_compatible"
                medbench_messages = [{"role": "user", "content": medbench_prompt}]
                try:
                    answer = self.llm.chat(
                        messages=medbench_messages,
                        max_tokens=self.max_tokens,
                        temperature=0.0,
                        top_p=1.0,
                        json_schema=schema,
                    ).text
                except Exception as e:
                    error = f"llm_error:{type(e).__name__}:{e}"
                record_llm_io(mode, medbench_messages, answer, error, schema)

        if not answer and not error:
            legacy_error = ""
            try:
                answer = self.llm.chat(messages=messages, max_tokens=self.max_tokens, temperature=0.0, top_p=1.0).text
            except Exception as e:
                legacy_error = f"llm_error:{type(e).__name__}:{e}"
                error = legacy_error
            mode = "figure2_generic"
            record_llm_io(mode, messages, answer, legacy_error)

        parsed = extract_first_json_object(answer)
        entities = {}
        if isinstance(parsed.get("relevant_entities"), dict):
            entities = parsed.get("relevant_entities", {})
        elif parsed:
            # Sometimes model returns plain dict directly.
            entities = parsed

        if entities and strict_schema:
            violations = _schema_violations(entities, strict_calc, required_entities)
            if violations:
                correction_prompt = "\n\n".join(
                    [
                        strict_prompt,
                        "The previous output violated the required schema:",
                        "\n".join(f"- {item}" for item in violations),
                        f"Previous output: {json.dumps(entities, ensure_ascii=False)}",
                        "Return a corrected JSON object only.",
                    ]
                )
                correction_messages = [{"role": "user", "content": correction_prompt}]
                corrected_answer = ""
                correction_error = ""
                try:
                    corrected_answer = self.llm.chat(
                        messages=correction_messages,
                        max_tokens=self.max_tokens,
                        temperature=0.0,
                        top_p=1.0,
                        json_schema=strict_output_schema,
                    ).text
                    corrected = extract_first_json_object(corrected_answer)
                    corrected_entities = corrected.get("relevant_entities", {}) if isinstance(corrected.get("relevant_entities"), dict) else corrected
                    if isinstance(corrected_entities, dict) and not _schema_violations(
                        corrected_entities, strict_calc, required_entities
                    ):
                        answer = corrected_answer
                        entities = corrected_entities
                        mode = f"{mode}_corrected"
                    else:
                        error = error or "strict_schema_validation_failed_after_retry"
                except Exception as e:
                    correction_error = f"strict_schema_retry_error:{type(e).__name__}:{e}"
                    error = error or correction_error
                record_llm_io(
                    "strict_schema_correction",
                    correction_messages,
                    corrected_answer,
                    correction_error,
                    strict_output_schema,
                )

        if not entities:
            entities = self._fallback_extract(patient_note, required_entities)
            if not error:
                error = "empty_or_invalid_json_from_llm"
            mode = "fallback_regex"

        return {
            "relevant_entities": entities,
            "raw_model_output": answer,
            "error": error,
            "mode": mode,
            "llm_io": llm_io,
        }
