import ast
import csv
import json
import os
import re
import tarfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


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


def now_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def now_compact() -> str:
    return time.strftime("%y%m%d_%H%M%S")


def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def read_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def write_text(path: str, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def load_csv_rows(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def load_json(path: str, default: Any = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: str, obj: Any, indent: int = 2) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=indent), encoding="utf-8")


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    p = Path(path)
    if not p.exists():
        return rows
    with p.open("r", encoding="utf-8") as f:
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


def append_jsonl(path: str, rows: Sequence[Dict[str, Any]]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def normalize_space(text: Any) -> str:
    return re.sub(r"\s+", " ", safe_str(text)).strip()


def normalize_key(text: Any) -> str:
    s = safe_str(text).strip().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def tokenize(text: Any) -> List[str]:
    return re.findall(r"[a-z0-9]+", safe_str(text).lower())


def overlap_score(query: str, text: str) -> float:
    q = set(tokenize(query))
    t = set(tokenize(text))
    if not q or not t:
        return 0.0
    inter = len(q & t)
    return inter / max(1.0, (len(q) * len(t)) ** 0.5)


def parse_entities(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    s = safe_str(raw).strip()
    if not s or s.lower() in {"none", "null", "nan"}:
        return {}
    for fn in (json.loads, ast.literal_eval):
        try:
            obj = fn(s)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return {}


def strip_think_tags(text: Any) -> str:
    s = safe_str(text)
    s = re.sub(r"(?is)<think>.*?</think>", " ", s)
    return s.replace("<think>", " ").replace("</think>", " ").strip()


def extract_first_json_object(text: Any) -> Dict[str, Any]:
    s = strip_think_tags(text).strip()
    if not s:
        return {}
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    decoder = json.JSONDecoder()
    for i, ch in enumerate(s):
        if ch != "{":
            continue
        try:
            obj, end = decoder.raw_decode(s[i:])
            if end > 0 and isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return {}


def load_env_file(env_path: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    p = Path(env_path)
    if not p.exists():
        return out

    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if "=" not in s:
            continue
        key, value = s.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        out[key] = value
        if key and key not in os.environ:
            os.environ[key] = value
    return out


def bool_env(value: Any, default: bool = False) -> bool:
    s = safe_str(value).strip().lower()
    if not s:
        return default
    if s in {"1", "true", "yes", "y", "on"}:
        return True
    if s in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _safe_extract_tar(tf: tarfile.TarFile, extract_root: Path) -> None:
    root = extract_root.resolve()
    for member in tf.getmembers():
        if member.issym() or member.islnk():
            raise ValueError(f"archive links are not allowed: {member.name}")
        target = (root / member.name).resolve()
        if target != root and root not in target.parents:
            raise ValueError(f"archive member escapes extraction root: {member.name}")
    tf.extractall(path=root)


def resolve_lora_adapter_path(
    lora_path: str = "",
    sft_tar: str = "",
    sft_extract_root: str = "",
    sft_dir_name: str = "",
) -> str:
    def _has_adapter(path_obj: Optional[Path]) -> bool:
        if path_obj is None:
            return False
        return (path_obj / "adapter_model.safetensors").exists() and (path_obj / "adapter_config.json").exists()

    candidate: Optional[Path] = None
    raw_lora_path = safe_str(lora_path).strip()
    if raw_lora_path:
        candidate = Path(raw_lora_path).expanduser()
        if _has_adapter(candidate):
            return str(candidate.resolve())
    elif safe_str(sft_extract_root).strip() and safe_str(sft_dir_name).strip():
        candidate = Path(sft_extract_root).expanduser() / safe_str(sft_dir_name).strip()
        if _has_adapter(candidate):
            return str(candidate.resolve())

    tar_path = Path(safe_str(sft_tar).strip()).expanduser() if safe_str(sft_tar).strip() else None
    extract_root = Path(safe_str(sft_extract_root).strip()).expanduser() if safe_str(sft_extract_root).strip() else None
    if tar_path is not None and tar_path.exists() and extract_root is not None:
        try:
            extract_root.mkdir(parents=True, exist_ok=True)
            with tarfile.open(tar_path, "r:*") as tf:
                _safe_extract_tar(tf, extract_root)
        except Exception:
            pass

    if candidate is not None and _has_adapter(candidate):
        return str(candidate.resolve())

    if candidate is None and extract_root is not None and safe_str(sft_dir_name).strip():
        candidate = extract_root / safe_str(sft_dir_name).strip()
        if _has_adapter(candidate):
            return str(candidate.resolve())

    if candidate is not None:
        return str(candidate.resolve())
    return ""


@dataclass
class ChatResult:
    text: str
    usage: Dict[str, int]
    raw: Dict[str, Any]
    usage_estimated: bool = False


class OpenAICompatClient:
    def __init__(self, api_base: str, api_key: str, model: str, timeout_sec: int = 120, retries: int = 3):
        self.api_base = safe_str(api_base).rstrip("/")
        self.api_key = safe_str(api_key).strip()
        self.model = safe_str(model).strip()
        self.timeout_sec = max(10, int(timeout_sec))
        self.retries = max(1, int(retries))

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, int(len(safe_str(text)) / 4))

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: List[str] = []
            for x in content:
                if isinstance(x, dict):
                    parts.append(safe_str(x.get("text", "")))
                else:
                    parts.append(safe_str(x))
            return "".join(parts).strip()
        return safe_str(content)

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1200,
        temperature: float = 0.0,
        top_p: float = 1.0,
        enable_thinking: bool = False,
    ) -> ChatResult:
        if not self.api_base or not self.api_key or not self.model:
            raise RuntimeError("api config missing for OpenAICompatClient")

        url = f"{self.api_base}/chat/completions"
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": int(max(1, max_tokens)),
            "temperature": float(temperature),
            "top_p": float(top_p),
            "stream": False,
            "enable_thinking": bool(enable_thinking),
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = ""
        for i in range(1, self.retries + 1):
            req = urllib.request.Request(url=url, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    text = resp.read().decode("utf-8", errors="ignore")
                raw = json.loads(text)
                choices = raw.get("choices", []) if isinstance(raw, dict) else []
                if not choices:
                    raise RuntimeError(f"empty choices: {text[:500]}")

                msg = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
                answer = self._content_to_text(msg.get("content"))
                usage_obj = raw.get("usage", {}) if isinstance(raw, dict) else {}

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
                    prompt_tokens = self._estimate_tokens(json.dumps(messages, ensure_ascii=False))
                    completion_tokens = self._estimate_tokens(answer)
                    total_tokens = prompt_tokens + completion_tokens
                    usage_estimated = True

                return ChatResult(
                    text=answer,
                    usage={
                        "prompt_tokens": int(prompt_tokens),
                        "completion_tokens": int(completion_tokens),
                        "total_tokens": int(total_tokens),
                    },
                    raw=raw if isinstance(raw, dict) else {},
                    usage_estimated=usage_estimated,
                )
            except urllib.error.HTTPError as e:
                try:
                    msg = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    msg = safe_str(e)
                last_error = f"HTTPError:{e.code}:{msg[:500]}"
            except Exception as e:
                last_error = f"{type(e).__name__}:{e}"

            if i < self.retries:
                time.sleep(min(8, 1 + i * 2))

        raise RuntimeError(f"api_call_failed: {last_error}")


class LocalVLLMClient:
    def __init__(
        self,
        model_path: str,
        max_input_tokens: int = 20000,
        max_new_tokens: int = 1024,
        tensor_parallel_size: int = 1,
        enforce_eager: bool = False,
        gpu_memory_utilization: float = 0.9,
        temperature: float = 0.0,
        top_p: float = 1.0,
        lora_path: str = "",
        lora_name: str = "sft_adapter",
        lora_id: int = 1,
    ):
        from vllm import LLM, SamplingParams

        self.SamplingParams = SamplingParams
        self.max_new_tokens = int(max_new_tokens)
        self.temperature = float(temperature)
        self.top_p = float(top_p)
        self.lora_request: Any = None

        llm_kwargs: Dict[str, Any] = {
            "model": model_path,
            "tensor_parallel_size": int(tensor_parallel_size),
            "max_model_len": int(max_input_tokens),
            "trust_remote_code": True,
            "enforce_eager": bool(enforce_eager),
            "gpu_memory_utilization": float(gpu_memory_utilization),
            "disable_log_stats": True,
        }

        raw_lora_path = safe_str(lora_path).strip()
        if raw_lora_path:
            adapter_dir = Path(raw_lora_path).expanduser().resolve()
            if not (adapter_dir / "adapter_model.safetensors").exists() or not (adapter_dir / "adapter_config.json").exists():
                raise RuntimeError(f"missing_lora_adapter:{adapter_dir}")

            try:
                from vllm.lora.request import LoRARequest
            except Exception as e:
                raise RuntimeError(f"lora_import_error:{type(e).__name__}:{e}") from e

            llm_kwargs["enable_lora"] = True
            self.lora_request = LoRARequest(
                safe_str(lora_name).strip() or "sft_adapter",
                int(lora_id),
                str(adapter_dir),
            )

        self.llm = LLM(**llm_kwargs)
        self.tokenizer = self.llm.get_tokenizer()

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        if hasattr(self.tokenizer, "apply_chat_template"):
            try:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                return self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        return "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages])

    def _sampling(self, max_tokens: Optional[int] = None, json_schema: Optional[Dict[str, Any]] = None):
        use_max_tokens = int(max_tokens or self.max_new_tokens)
        base: Dict[str, Any] = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": use_max_tokens,
        }

        if json_schema:
            try:
                try:
                    from vllm.sampling_params import GuidedDecodingParams
                except Exception:
                    from vllm import GuidedDecodingParams  # type: ignore

                if hasattr(GuidedDecodingParams, "from_optional"):
                    guided = GuidedDecodingParams.from_optional(
                        json=json_schema,
                        whitespace_pattern=r"[\n\r\t ]*",
                    )
                else:
                    guided = GuidedDecodingParams(json=json_schema)

                for key in ("structured_outputs", "guided_decoding"):
                    try:
                        return self.SamplingParams(**base, **{key: guided})
                    except TypeError:
                        continue
            except Exception:
                pass

        return self.SamplingParams(**base)

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> ChatResult:
        prompt = self._format_messages(messages)
        gen_kwargs: Dict[str, Any] = {
            "sampling_params": self._sampling(max_tokens=max_tokens, json_schema=json_schema),
            "use_tqdm": False,
        }
        if self.lora_request is not None:
            gen_kwargs["lora_request"] = self.lora_request
        outputs = self.llm.generate([prompt], **gen_kwargs)
        text = outputs[0].outputs[0].text if outputs and outputs[0].outputs else ""
        text = safe_str(text).strip()
        usage = {
            "prompt_tokens": max(1, int(len(prompt) / 4)),
            "completion_tokens": max(1, int(len(text) / 4)),
            "total_tokens": max(1, int((len(prompt) + len(text)) / 4)),
        }
        return ChatResult(text=text, usage=usage, raw={}, usage_estimated=True)


class LLMRouter:
    def __init__(
        self,
        mode: str,
        api_base: str = "",
        api_key: str = "",
        model_name: str = "",
        model_path: str = "",
        timeout_sec: int = 120,
        retries: int = 3,
        max_input_tokens: int = 20000,
        max_new_tokens: int = 1024,
        tensor_parallel_size: int = 1,
        enforce_eager: bool = False,
        gpu_memory_utilization: float = 0.9,
        temperature: float = 0.0,
        top_p: float = 1.0,
        lora_path: str = "",
        lora_name: str = "sft_adapter",
        lora_id: int = 1,
    ):
        m = safe_str(mode).strip().lower() or "api"
        self.mode = m
        self._client: Any = None
        self._init_error = ""

        try:
            if m == "local":
                if not safe_str(model_path).strip():
                    raise RuntimeError("missing_local_model_path")
                self._client = LocalVLLMClient(
                    model_path=model_path,
                    max_input_tokens=max_input_tokens,
                    max_new_tokens=max_new_tokens,
                    tensor_parallel_size=tensor_parallel_size,
                    enforce_eager=enforce_eager,
                    gpu_memory_utilization=gpu_memory_utilization,
                    temperature=temperature,
                    top_p=top_p,
                    lora_path=lora_path,
                    lora_name=lora_name,
                    lora_id=lora_id,
                )
            else:
                if not safe_str(api_base).strip() or not safe_str(api_key).strip() or not safe_str(model_name).strip():
                    raise RuntimeError("missing_api_base_or_key_or_model_name")
                self._client = OpenAICompatClient(
                    api_base=api_base,
                    api_key=api_key,
                    model=model_name,
                    timeout_sec=timeout_sec,
                    retries=retries,
                )
        except Exception as e:
            self._init_error = f"{type(e).__name__}:{e}"
            self._client = None

    @property
    def available(self) -> bool:
        return self._client is not None

    @property
    def init_error(self) -> str:
        return self._init_error

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1200,
        temperature: float = 0.0,
        top_p: float = 1.0,
        enable_thinking: bool = False,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> ChatResult:
        if self._client is None:
            raise RuntimeError(f"llm_unavailable:{self._init_error or 'not_initialized'}")

        if isinstance(self._client, OpenAICompatClient):
            return self._client.chat(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                enable_thinking=enable_thinking,
            )
        return self._client.chat(
            messages,
            max_tokens=max_tokens,
            json_schema=json_schema,
        )


def topk_by_overlap(items: Iterable[Dict[str, Any]], query: str, text_keys: Sequence[str], top_k: int) -> List[Dict[str, Any]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for item in items:
        parts = [safe_str(item.get(k, "")) for k in text_keys]
        text = "\n".join([x for x in parts if x]).strip()
        score = overlap_score(query, text)
        scored.append((score, dict(item)))
    scored.sort(key=lambda x: x[0], reverse=True)
    out: List[Dict[str, Any]] = []
    for score, item in scored[: max(1, int(top_k))]:
        x = dict(item)
        x["overlap_score"] = round(float(score), 6)
        out.append(x)
    return out
