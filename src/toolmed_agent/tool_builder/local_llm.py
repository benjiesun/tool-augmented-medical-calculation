import json
import os
from typing import Dict, List, Optional, Tuple


class LocalVLLM:
    def __init__(
        self,
        llm_name: str,
        model_path: Optional[str] = None,
        lora_path: Optional[str] = None,
        max_input_tokens: int = 20000,
        max_new_tokens: int = 1024,
        tensor_parallel_size: int = 1,
        enforce_eager: bool = False,
        gpu_memory_utilization: float = 0.9,
        temperature: float = 0.0,
        top_p: float = 1.0,
        enable_thinking: Optional[bool] = None,
    ):
        from vllm import LLM, SamplingParams

        self.SamplingParams = SamplingParams
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.enable_thinking = enable_thinking

        path = model_path or self._resolve_model_path(llm_name)
        base_model_path, adapter_path = self._resolve_base_and_lora(path, lora_path=lora_path)
        self.adapter_path = adapter_path
        self._lora_request = None

        llm_kwargs = dict(
            model=base_model_path,
            tensor_parallel_size=tensor_parallel_size,
            max_model_len=max_input_tokens,
            trust_remote_code=True,
            enforce_eager=enforce_eager,
            gpu_memory_utilization=float(gpu_memory_utilization),
        )
        if self.adapter_path:
            llm_kwargs["enable_lora"] = True
            # vLLM default max_lora_rank can be smaller than adapter rank (e.g. rank=32).
            inferred_rank = self._infer_lora_rank(self.adapter_path)
            llm_kwargs["max_lora_rank"] = max(32, int(inferred_rank or 0))

        last_type_error: Optional[TypeError] = None
        init_attempts = [dict(llm_kwargs, disable_log_stats=True), dict(llm_kwargs)]
        if "max_lora_rank" in llm_kwargs:
            no_rank_kwargs = dict(llm_kwargs)
            no_rank_kwargs.pop("max_lora_rank", None)
            init_attempts.extend([dict(no_rank_kwargs, disable_log_stats=True), dict(no_rank_kwargs)])

        for kwargs in init_attempts:
            try:
                self.llm = LLM(**kwargs)
                break
            except TypeError as e:
                last_type_error = e
        else:
            if last_type_error is not None:
                raise last_type_error
            raise RuntimeError("failed to initialize vLLM")
        self.tokenizer = self.llm.get_tokenizer()

        if self.adapter_path:
            self._lora_request = self._build_lora_request(self.adapter_path)

    @staticmethod
    def _resolve_model_path(llm_name: str) -> str:
        models_dir = os.path.join(os.getcwd(), "models")
        model_paths = {
            "Qwen3-8B": os.path.join(models_dir, "Qwen3-8B"),
            "Qwen2.5-7B": os.path.join(models_dir, "Qwen2.5-7B"),
            "glm4_9b_chat": os.path.join(models_dir, "glm-4-9b-chat-hf"),
            "deepSeek-r1-Distill-Qwen-7B": os.path.join(
                models_dir,
                "DeepSeek-R1-Distill-Qwen-7B",
            ),
        }
        return model_paths.get(llm_name, llm_name)

    @staticmethod
    def _is_lora_adapter_dir(path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        return os.path.exists(os.path.join(path, "adapter_config.json")) and os.path.exists(
            os.path.join(path, "adapter_model.safetensors")
        )

    @staticmethod
    def _resolve_base_and_lora(path: str, lora_path: Optional[str] = None) -> Tuple[str, Optional[str]]:
        if lora_path:
            return path, lora_path
        if LocalVLLM._is_lora_adapter_dir(path):
            cfg_path = os.path.join(path, "adapter_config.json")
            base = ""
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            base = str(cfg.get("base_model_name_or_path") or cfg.get("base_model") or "").strip()
            if not base:
                raise RuntimeError(f"cannot find base_model_name_or_path in {cfg_path}")
            return base, path
        return path, None

    @staticmethod
    def _infer_lora_rank(adapter_path: str) -> Optional[int]:
        cfg_path = os.path.join(adapter_path, "adapter_config.json")
        if not os.path.exists(cfg_path):
            return None
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            for key in ("r", "lora_r"):
                val = cfg.get(key)
                if isinstance(val, int) and val > 0:
                    return val
        except Exception:
            return None
        return None

    @staticmethod
    def _build_lora_request(adapter_path: str):
        from vllm.lora.request import LoRARequest

        for args in (
            ("v1_adapter", 1, adapter_path),
            ("v1_adapter", 1, adapter_path, 1),
        ):
            try:
                return LoRARequest(*args)
            except TypeError:
                continue
        return LoRARequest("v1_adapter", 1, adapter_path)

    def _sampling_params(self):
        return self.SamplingParams(
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_new_tokens,
        )

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        try:
            if hasattr(self.tokenizer, "apply_chat_template"):
                base = dict(conversation=messages, tokenize=False, add_generation_prompt=True)
                if self.enable_thinking is None:
                    return self.tokenizer.apply_chat_template(**base)
                for extra in (
                    {"enable_thinking": self.enable_thinking},
                    {"tokenizer_kwargs": {"enable_thinking": self.enable_thinking}},
                    {},
                ):
                    try:
                        return self.tokenizer.apply_chat_template(**base, **extra)
                    except TypeError:
                        continue
        except Exception:
            pass
        return "\n".join([f"{m['role']}: {m['content']}" for m in messages])

    def _generate(self, prompts: List[str]):
        params = self._sampling_params()
        for extra in ({"use_tqdm": False}, {"tqdm": False}, {}):
            try:
                if self._lora_request is not None:
                    return self.llm.generate(prompts, sampling_params=params, lora_request=self._lora_request, **extra)
                return self.llm.generate(prompts, sampling_params=params, **extra)
            except TypeError:
                continue
        if self._lora_request is not None:
            return self.llm.generate(prompts, sampling_params=params, lora_request=self._lora_request)
        return self.llm.generate(prompts, sampling_params=params)

    def _clean(self, text: str) -> str:
        s = "" if text is None else str(text)
        for t in [getattr(self.tokenizer, "eos_token", None), "<|end_of_solution|>", "</s>"]:
            if t and t in s:
                s = s.split(t)[0]
        return s.replace("\r\n", "\n").replace("\r", "\n").strip()

    def answer(self, messages: List[Dict[str, str]]) -> str:
        prompt = self._format_messages(messages)
        outputs = self._generate([prompt])
        return self._clean(outputs[0].outputs[0].text)

    def answer_batch(self, messages_list: List[List[Dict[str, str]]]) -> List[str]:
        if not messages_list:
            return []
        prompts = [self._format_messages(x) for x in messages_list]
        outputs = self._generate(prompts)
        return [self._clean(x.outputs[0].text) for x in outputs]


def local_vllm(
    llm_name: str = "Qwen3-8B",
    model_path: Optional[str] = None,
    lora_path: Optional[str] = None,
    max_input_tokens: int = 20000,
    max_new_tokens: int = 1024,
    tensor_parallel_size: int = 1,
    enforce_eager: bool = False,
    gpu_memory_utilization: float = 0.9,
    temperature: float = 0.0,
    top_p: float = 1.0,
    enable_thinking: Optional[bool] = None,
) -> LocalVLLM:
    return LocalVLLM(
        llm_name=llm_name,
        model_path=model_path,
        lora_path=lora_path,
        max_input_tokens=max_input_tokens,
        max_new_tokens=max_new_tokens,
        tensor_parallel_size=tensor_parallel_size,
        enforce_eager=enforce_eager,
        gpu_memory_utilization=gpu_memory_utilization,
        temperature=temperature,
        top_p=top_p,
        enable_thinking=enable_thinking,
    )
