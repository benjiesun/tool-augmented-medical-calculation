import json
import re
from typing import Any, Dict, List, Optional

from .utils import LLMRouter, extract_first_json_object, safe_float, safe_str


def _norm_key(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", safe_str(s).lower())


def _norm_unit(s: Any) -> str:
    u = safe_str(s).strip().lower()
    u = u.replace("μ", "u").replace("µ", "u")
    u = u.replace(" ", "")
    return u


def _to_number(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    return safe_float(v)


def _expected_unit_defaults() -> Dict[str, str]:
    return {
        "age": "years",
        "weight": "kg",
        "height": "cm",
        "creatinine": "mg/dL",
        "scr": "mg/dL",
        "systolicbloodpressure": "mmHg",
        "diastolicbloodpressure": "mmHg",
        "glucose": "mg/dL",
        "hemoglobin": "g/dL",
    }


def _alias_to_canonical() -> Dict[str, str]:
    return {
        "gender": "sex",
        "malefemale": "sex",
        "serumcreatinine": "creatinine",
        "scr": "creatinine",
        "cr": "creatinine",
        "wt": "weight",
        "ht": "height",
    }


def _convert(value: float, src_unit: str, dst_unit: str) -> Optional[float]:
    s = _norm_unit(src_unit)
    d = _norm_unit(dst_unit)
    if not s or not d or s == d:
        return value

    factors = {
        ("lb", "kg"): 0.45359237,
        ("lbs", "kg"): 0.45359237,
        ("pound", "kg"): 0.45359237,
        ("pounds", "kg"): 0.45359237,
        ("kg", "lb"): 2.2046226218,
        ("cm", "m"): 0.01,
        ("m", "cm"): 100.0,
        ("inch", "cm"): 2.54,
        ("in", "cm"): 2.54,
        ("cm", "inch"): 0.3937007874,
        ("umol/l", "mg/dl"): 1 / 88.4,
        ("mg/dl", "umol/l"): 88.4,
        ("mmol/l", "mg/dl"): 18.0,
        ("mg/dl", "mmol/l"): 1 / 18.0,
        ("g/l", "g/dl"): 0.1,
        ("g/dl", "g/l"): 10.0,
    }

    key = (s, d)
    if key not in factors:
        return None
    return value * factors[key]


class UnitNormalizer:
    def __init__(
        self,
        llm: Optional[LLMRouter] = None,
        llm_max_tokens: int = 800,
        allow_unit_conversion: bool = True,
        enable_llm_fallback: bool = True,
    ):
        self.llm = llm
        self.llm_max_tokens = max(64, int(llm_max_tokens or 800))
        self.allow_unit_conversion = bool(allow_unit_conversion)
        self.enable_llm_fallback = bool(enable_llm_fallback)
        self.alias_map = _alias_to_canonical()
        self.default_units = _expected_unit_defaults()

    def _canonical_key(self, key: str) -> str:
        nk = _norm_key(key)
        return self.alias_map.get(nk, nk)

    def _infer_expected_units_from_rule(self, rule_text: str) -> Dict[str, str]:
        out: Dict[str, str] = {}
        txt = safe_str(rule_text)

        patterns = {
            "creatinine": r"creatinine[^\n]{0,120}(mg/dl|umol/l|μmol/l|µmol/l)",
            "weight": r"weight[^\n]{0,80}(kg|lb|lbs)",
            "height": r"height[^\n]{0,80}(cm|m|inch|in)",
            "systolicbloodpressure": r"(systolic|sbp)[^\n]{0,80}(mmhg)",
            "diastolicbloodpressure": r"(diastolic|dbp)[^\n]{0,80}(mmhg)",
        }
        for k, pat in patterns.items():
            m = re.search(pat, txt, flags=re.I)
            if m:
                out[k] = m.group(m.lastindex or 0)

        return out

    def _compute_missing(self, normalized_entities: Dict[str, Any], required_entities: List[str]) -> List[str]:
        required = [safe_str(x).strip() for x in required_entities if safe_str(x).strip()]
        required_norm = [self._canonical_key(x) for x in required]

        provided_keys_norm = set()
        for k in (normalized_entities or {}).keys():
            provided_keys_norm.add(self._canonical_key(safe_str(k)))

        missing: List[str] = []
        for raw_req, req_norm in zip(required, required_norm):
            if req_norm not in provided_keys_norm:
                missing.append(raw_req)
        return missing

    def _rule_normalize(
        self,
        extracted_entities: Dict[str, Any],
        required_entities: List[str],
        expected_units: Dict[str, str],
    ) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {}
        conversions: List[Dict[str, Any]] = []
        unresolved_unit_conversions: List[Dict[str, Any]] = []

        for raw_key, raw_val in (extracted_entities or {}).items():
            ckey = self._canonical_key(raw_key)
            target_unit = expected_units.get(ckey, "")

            if isinstance(raw_val, tuple):
                raw_val = list(raw_val)

            if isinstance(raw_val, list) and len(raw_val) >= 2:
                num = _to_number(raw_val[0])
                src_unit = safe_str(raw_val[1]).strip()
                if self.allow_unit_conversion and num is not None and target_unit:
                    converted = _convert(num, src_unit, target_unit)
                    if converted is not None:
                        normalized[raw_key] = [round(float(converted), 6), target_unit]
                        conversions.append(
                            {
                                "key": raw_key,
                                "from": [num, src_unit],
                                "to": normalized[raw_key],
                            }
                        )
                        continue

                    src_u = _norm_unit(src_unit)
                    dst_u = _norm_unit(target_unit)
                    if src_u and dst_u and src_u != dst_u:
                        unresolved_unit_conversions.append(
                            {
                                "key": raw_key,
                                "value": raw_val,
                                "target_unit": target_unit,
                            }
                        )

                normalized[raw_key] = raw_val
                continue

            # Scalar value: keep it unchanged.
            normalized[raw_key] = raw_val

        missing = self._compute_missing(normalized, required_entities)
        return {
            "normalized_entities": normalized,
            "missing_required_params": missing,
            "conversions": conversions,
            "unresolved_unit_conversions": unresolved_unit_conversions,
        }

    def _llm_fix_messages(
        self,
        extracted_entities: Dict[str, Any],
        rule_normalized: Dict[str, Any],
        required_entities: List[str],
        expected_units: Dict[str, str],
        missing_required_params: List[str],
        unresolved_unit_conversions: List[Dict[str, Any]],
        rule_text: str,
    ) -> List[Dict[str, str]]:
        system = (
            "You normalize calculator parameters for medical computation. "
            "Output strict JSON only, no markdown."
        )
        user = (
            "Fix normalized_entities from rule engine output.\n"
            f"Required keys: {required_entities}\n"
            f"Expected units by canonical key: {expected_units}\n"
            f"Missing required params after rule pass: {missing_required_params}\n"
            f"Unresolved unit conversions after rule pass: {unresolved_unit_conversions}\n\n"
            f"Raw extracted entities:\n{json.dumps(extracted_entities, ensure_ascii=False)}\n\n"
            f"Rule-pass normalized entities:\n{json.dumps(rule_normalized, ensure_ascii=False)}\n\n"
            f"Rule reference (truncated):\n{safe_str(rule_text)[:5000]}\n\n"
            "Keep keys stable whenever possible. "
            "If a key cannot be inferred, do not hallucinate values.\n"
            "Return JSON only with this schema:\n"
            '{"normalized_entities": {"key": value or [value, "unit"]}, "notes": "optional"}'
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user}]

    def _parse_llm_entities(self, answer: str) -> Dict[str, Any]:
        obj = extract_first_json_object(answer)
        if not isinstance(obj, dict):
            return {}

        if isinstance(obj.get("normalized_entities"), dict):
            return obj.get("normalized_entities", {})
        if isinstance(obj.get("relevant_entities"), dict):
            return obj.get("relevant_entities", {})

        # fallback: if object itself looks like entities dict
        meta_keys = {"notes", "note", "reason", "rationale", "explanation"}
        cand = {k: v for k, v in obj.items() if k not in meta_keys}
        return cand if cand else {}

    def normalize(
        self,
        extracted_entities: Dict[str, Any],
        required_entities: List[str],
        rule_text: str,
    ) -> Dict[str, Any]:
        required = [safe_str(x).strip() for x in required_entities if safe_str(x).strip()]
        inferred_units = self._infer_expected_units_from_rule(rule_text)
        expected_units = {**self.default_units, **inferred_units}

        rule_pack = self._rule_normalize(
            extracted_entities=extracted_entities,
            required_entities=required,
            expected_units=expected_units,
        )
        normalized = dict(rule_pack.get("normalized_entities", {}) or {})
        missing = list(rule_pack.get("missing_required_params", []) or [])
        conversions = list(rule_pack.get("conversions", []) or [])
        unresolved = list(rule_pack.get("unresolved_unit_conversions", []) or [])

        llm_fallback_triggered = bool(missing or unresolved)
        if not self.enable_llm_fallback:
            llm_fallback_triggered = False
        llm_fallback_used = False
        llm_error = ""
        llm_usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        llm_answer = ""
        llm_entities: Dict[str, Any] = {}

        if llm_fallback_triggered and self.llm is not None and self.llm.available:
            llm_fallback_used = True
            messages = self._llm_fix_messages(
                extracted_entities=extracted_entities or {},
                rule_normalized=normalized,
                required_entities=required,
                expected_units=expected_units,
                missing_required_params=missing,
                unresolved_unit_conversions=unresolved,
                rule_text=rule_text,
            )
            try:
                chat = self.llm.chat(
                    messages=messages,
                    max_tokens=self.llm_max_tokens,
                    temperature=0.0,
                    top_p=1.0,
                )
                llm_answer = chat.text
                llm_usage = {
                    "prompt_tokens": int(chat.usage.get("prompt_tokens", 0) or 0),
                    "completion_tokens": int(chat.usage.get("completion_tokens", 0) or 0),
                    "total_tokens": int(chat.usage.get("total_tokens", 0) or 0),
                }
                llm_entities = self._parse_llm_entities(llm_answer)
            except Exception as e:
                llm_error = f"llm_error:{type(e).__name__}:{e}"

        if llm_entities:
            # LLM output overlays rule output; this keeps stable rule conversions while allowing repair.
            for k, v in llm_entities.items():
                normalized[k] = v

        missing_after = self._compute_missing(normalized, required)

        reflection = {
            "mode": "rule_then_llm",
            "converted_count": len(conversions),
            "conversions": conversions,
            "expected_units": expected_units,
            "missing_required_params_rule": missing,
            "unresolved_unit_conversions_rule": unresolved,
            "missing_required_params_final": missing_after,
            "llm_fallback_triggered": llm_fallback_triggered,
            "llm_fallback_used": llm_fallback_used,
            "llm_error": llm_error,
            "llm_usage": llm_usage,
            "llm_output_used": bool(llm_entities),
            "llm_output_entities_preview": {k: llm_entities[k] for k in list(llm_entities.keys())[:20]},
        }

        if llm_answer:
            reflection["llm_raw_output_preview"] = safe_str(llm_answer)[:1200]

        return {
            "normalized_entities": normalized,
            "missing_required_params": missing_after,
            "reflection": reflection,
        }
