import ast
import csv
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover - unavailable on Windows
    fcntl = None  # type: ignore


def safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)


def safe_int(v: Any) -> Optional[int]:
    try:
        return int(float(str(v).strip()))
    except Exception:
        return None


def safe_float(v: Any) -> Optional[float]:
    try:
        return float(str(v).strip())
    except Exception:
        return None


def calc_id(row: Dict[str, Any]) -> str:
    v = row.get("Calculator ID", "")
    x = safe_int(v)
    return str(x) if x is not None else safe_str(v).strip()


def note_id(row: Dict[str, Any]) -> str:
    return safe_str(row.get("Note ID", "")).strip()


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def load_csv_rows(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "a", encoding="utf-8") as f:
        if fcntl is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            if fcntl is not None:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not os.path.exists(path):
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def normalize_ws(s: Any) -> str:
    return re.sub(r"\s+", " ", safe_str(s)).strip()


def normalize_key(s: Any) -> str:
    text = safe_str(s).strip().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def strip_think_tags(s: Any) -> str:
    text = safe_str(s)
    text = re.sub(r"(?is)<think>.*?</think>", " ", text)
    text = text.replace("<think>", " ").replace("</think>", " ")
    return text.strip()


def extract_first_json(text: Any) -> Optional[Any]:
    s = strip_think_tags(text)
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch not in "{[":
            continue
        try:
            obj, end = decoder.raw_decode(s[i:])
            if end > 0:
                return obj
        except Exception:
            continue
    return None


def extract_calc_code(raw_text: Any) -> str:
    s = safe_str(raw_text)
    if not s:
        return ""
    m_fence = re.search(r"(?is)```(?:python)?\s*(.*?)```", s)
    if m_fence:
        cand = safe_str(m_fence.group(1)).strip()
        if "def calc(" in cand:
            return cand
    m = re.search(r"(?is)\bdef\s+calc\s*\(\s*relevant\s*\)\s*:\s*.*", s)
    return safe_str(m.group(0)).strip() if m else ""


def parse_required_entities(raw_text: Any) -> List[str]:
    obj = extract_first_json(raw_text)
    if isinstance(obj, dict) and isinstance(obj.get("required_entities"), list):
        out = [safe_str(x).strip() for x in obj["required_entities"] if safe_str(x).strip()]
        return out[:64]

    s = safe_str(raw_text)
    vals = re.findall(r'(?is)"required_entities"\s*:\s*\[(.*?)\]', s)
    out: List[str] = []
    for body in vals:
        pairs = re.findall(r'"([^"]+)"|\'([^\']+)\'', body)
        for a, b in pairs:
            v = (a or b or "").strip()
            if v:
                out.append(v)
    uniq: List[str] = []
    seen = set()
    for x in out:
        k = normalize_key(x)
        if not k or k in seen:
            continue
        seen.add(k)
        uniq.append(x)
    return uniq[:64]


def safe_code_check(code: str) -> Tuple[bool, str]:
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
        if isinstance(node, ast.Return):
            if isinstance(node.value, (ast.Dict, ast.List)):
                return False, "return_dict_or_list_not_allowed"
    return True, ""
