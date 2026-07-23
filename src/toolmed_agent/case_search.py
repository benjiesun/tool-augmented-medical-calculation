import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from .utils import parse_entities, safe_str, topk_by_overlap


class CaseSearcher:
    def __init__(self, few_shot_csv: str, case_library_json: str = ""):
        self.few_shot_csv = Path(few_shot_csv).resolve()
        self.case_library_json = Path(case_library_json).resolve() if safe_str(case_library_json).strip() else None
        self.rows: List[Dict[str, Any]] = []
        self.by_calc: Dict[str, List[Dict[str, Any]]] = {}
        self._load()

    @staticmethod
    def _norm_cid(v: Any) -> str:
        s = safe_str(v).strip()
        try:
            return str(int(float(s)))
        except Exception:
            return s

    def _load(self) -> None:
        loaded = False
        if self.case_library_json and self.case_library_json.exists():
            loaded = self._load_case_library_json()
        if not loaded:
            self._load_csv_fallback()

    def _ingest_item(self, item: Dict[str, Any]) -> None:
        cid = self._norm_cid(item.get("calculator_id", ""))
        calc_name = safe_str(item.get("calculator_name", "")).strip()
        question = safe_str(item.get("question", "")).strip()
        patient_note = safe_str(item.get("patient_note", "")).strip()
        rel_raw = item.get("relevant_entities", {})
        rel = rel_raw if isinstance(rel_raw, dict) else parse_entities(rel_raw)
        out = {
            "calculator_id": cid,
            "calculator_name": calc_name,
            "question": question,
            "patient_note": patient_note,
            "relevant_entities": rel,
            "train_row_number": safe_str(item.get("train_row_number", "")).strip(),
            "train_note_id": safe_str(item.get("train_note_id", "")).strip(),
        }
        self.rows.append(out)
        if cid:
            self.by_calc.setdefault(cid, []).append(out)

    def _load_case_library_json(self) -> bool:
        try:
            obj = json.loads(self.case_library_json.read_text(encoding="utf-8"))
        except Exception:
            return False
        calculators = obj.get("calculators", []) if isinstance(obj, dict) else []
        if not isinstance(calculators, list):
            return False

        before = len(self.rows)
        for calc in calculators:
            if not isinstance(calc, dict):
                continue
            cid = self._norm_cid(calc.get("calculator_id", ""))
            calc_name = safe_str(calc.get("calculator_name", "")).strip()

            cases = calc.get("cases", [])
            if not isinstance(cases, list) or not cases:
                cases = ((calc.get("few_shot", {}) or {}).get("examples", []) or [])
            if not isinstance(cases, list):
                continue

            for ex in cases:
                if not isinstance(ex, dict):
                    continue
                self._ingest_item(
                    {
                        "calculator_id": cid,
                        "calculator_name": calc_name,
                        "question": ex.get("question", calc.get("question", "")),
                        "patient_note": ex.get("patient_note", ""),
                        "relevant_entities": ex.get("relevant_entities", {}),
                        "train_row_number": ex.get("train_row_number", ""),
                        "train_note_id": ex.get("train_note_id", ""),
                    }
                )
        return len(self.rows) > before

    def _load_csv_fallback(self) -> None:
        if not self.few_shot_csv.exists():
            return

        with self.few_shot_csv.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for raw in reader:
                row = dict(raw)
                self._ingest_item(
                    {
                        "calculator_id": row.get("Calculator ID", ""),
                        "calculator_name": row.get("Calculator Name", ""),
                        "question": row.get("Question", ""),
                        "patient_note": "",
                        "relevant_entities": row.get("Relevant Entities (Final)", ""),
                        "train_row_number": row.get("Train Row Number", ""),
                        "train_note_id": row.get("Train Note ID", ""),
                    }
                )

    def retrieve(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
        patient_note: str,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        cid = self._norm_cid(calculator_id)
        pool = self.by_calc.get(cid, [])
        if not pool:
            pool = self.rows

        query = "\n".join(
            [
                safe_str(calculator_name),
                safe_str(question),
                safe_str(patient_note)[:900],
            ]
        )
        ranked = topk_by_overlap(
            items=pool,
            query=query,
            text_keys=["calculator_name", "question", "patient_note"],
            top_k=max(1, int(top_k)),
        )

        out: List[Dict[str, Any]] = []
        for item in ranked:
            out.append(
                {
                    "calculator_id": item.get("calculator_id", ""),
                    "calculator_name": item.get("calculator_name", ""),
                    "question": item.get("question", ""),
                    "patient_note": item.get("patient_note", ""),
                    "relevant_entities": item.get("relevant_entities", {}),
                    "train_row_number": item.get("train_row_number", ""),
                    "train_note_id": item.get("train_note_id", ""),
                    "score": item.get("overlap_score", 0.0),
                }
            )
        return out
