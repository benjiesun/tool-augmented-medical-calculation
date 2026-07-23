import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence

from .common import load_jsonl, normalize_key, safe_str


def _tokenize(s: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", safe_str(s).lower())


def _overlap_score(query: str, text: str) -> float:
    q = set(_tokenize(query))
    t = set(_tokenize(text))
    if not q or not t:
        return 0.0
    inter = len(q & t)
    return inter / max(1.0, math.sqrt(len(q) * len(t)))


class MedicalRAG:
    def __init__(
        self,
        docs: List[Dict[str, Any]],
        embedding_model_path: str = "",
        use_embedding: bool = True,
    ):
        self.docs = docs
        self._docs_by_calc: Dict[str, List[int]] = {}
        for i, d in enumerate(docs):
            cid = safe_str(d.get("calculator_id", "")).strip()
            if cid:
                self._docs_by_calc.setdefault(cid, []).append(i)

        self._embed_model = None
        self._doc_emb = None
        self._np = None

        if use_embedding and embedding_model_path and os.path.exists(embedding_model_path):
            try:
                import numpy as np
                from sentence_transformers import SentenceTransformer

                self._np = np
                # Keep embedding model on CPU so vLLM can fully occupy GPU.
                self._embed_model = SentenceTransformer(
                    embedding_model_path,
                    trust_remote_code=True,
                    device="cpu",
                )
                texts = [safe_str(d.get("text", ""))[:4000] for d in self.docs]
                emb = self._embed_model.encode(
                    texts,
                    show_progress_bar=False,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )
                self._doc_emb = emb
            except Exception:
                self._embed_model = None
                self._doc_emb = None
                self._np = None

    @staticmethod
    def from_files(
        rules_jsonl: str,
        guide_extract_md: Optional[str] = None,
        guide_normalize_md: Optional[str] = None,
        embedding_model_path: str = "",
        use_embedding: bool = True,
    ) -> "MedicalRAG":
        docs = load_rules_docs(rules_jsonl)
        if guide_extract_md and os.path.exists(guide_extract_md):
            with open(guide_extract_md, "r", encoding="utf-8") as f:
                txt = f.read().strip()
            docs.append(
                {
                    "doc_id": "guide_extract",
                    "calculator_id": "",
                    "title": "Parameter Extraction Guide",
                    "url": "",
                    "source": "guide_extract",
                    "text": txt,
                }
            )
        if guide_normalize_md and os.path.exists(guide_normalize_md):
            with open(guide_normalize_md, "r", encoding="utf-8") as f:
                txt = f.read().strip()
            docs.append(
                {
                    "doc_id": "guide_normalize",
                    "calculator_id": "",
                    "title": "Normalization Guide",
                    "url": "",
                    "source": "guide_normalize",
                    "text": txt,
                }
            )
        return MedicalRAG(docs=docs, embedding_model_path=embedding_model_path, use_embedding=use_embedding)

    def _candidate_indices(
        self,
        calculator_id: str = "",
        source_allow: Optional[Sequence[str]] = None,
    ) -> List[int]:
        cid = safe_str(calculator_id).strip()
        if cid and cid in self._docs_by_calc:
            cand = list(self._docs_by_calc[cid])
            # Always allow guide docs for extraction/normalization.
            for i, d in enumerate(self.docs):
                if safe_str(d.get("source", "")).startswith("guide_"):
                    cand.append(i)
        else:
            cand = list(range(len(self.docs)))

        if source_allow:
            allow = set(source_allow)
            cand = [i for i in cand if safe_str(self.docs[i].get("source", "")) in allow]
        return cand

    def retrieve(
        self,
        query: str,
        calculator_id: str = "",
        top_k: int = 5,
        source_allow: Optional[Sequence[str]] = None,
        alpha_embedding: float = 0.65,
    ) -> List[Dict[str, Any]]:
        indices = self._candidate_indices(calculator_id=calculator_id, source_allow=source_allow)
        if not indices:
            return []

        lex_scores: List[float] = []
        for i in indices:
            d = self.docs[i]
            text = f"{safe_str(d.get('title', ''))}\n{safe_str(d.get('text', ''))[:4000]}"
            lex_scores.append(_overlap_score(query, text))

        emb_scores = [0.0 for _ in indices]
        if self._embed_model is not None and self._doc_emb is not None and self._np is not None:
            try:
                q = self._embed_model.encode(
                    [query],
                    show_progress_bar=False,
                    normalize_embeddings=True,
                    convert_to_numpy=True,
                )[0]
                doc_mat = self._doc_emb[indices]
                sims = doc_mat @ q
                emb_scores = [float(x) for x in sims]
            except Exception:
                emb_scores = [0.0 for _ in indices]

        scored = []
        for idx, ls, es in zip(indices, lex_scores, emb_scores):
            s = alpha_embedding * es + (1.0 - alpha_embedding) * ls
            scored.append((s, idx))
        scored.sort(key=lambda x: x[0], reverse=True)

        out: List[Dict[str, Any]] = []
        for score, idx in scored[: max(1, int(top_k))]:
            d = dict(self.docs[idx])
            d["relevance_score"] = round(float(score), 6)
            d["text"] = safe_str(d.get("text", ""))[:3000]
            out.append(d)
        return out


def load_rules_docs(rules_jsonl: str) -> List[Dict[str, Any]]:
    rows = load_jsonl(rules_jsonl)
    docs: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        cid = safe_str(row.get("calculator_id", row.get("target_calculator_id", ""))).strip()
        title = safe_str(
            row.get("calculator_name", row.get("target_calculator_name", row.get("mdcalc_title", "")))
        ).strip()
        url = safe_str(row.get("mdcalc_url", row.get("url", ""))).strip()
        text = safe_str(row.get("evidence_text", row.get("text", ""))).strip()
        if not text:
            chunks = [
                safe_str(row.get("formula", "")),
                safe_str(row.get("inputs", "")),
                safe_str(row.get("instructions", "")),
                safe_str(row.get("why_use", "")),
                safe_str(row.get("pearls_pitfalls", "")),
            ]
            text = "\n".join([x for x in chunks if x]).strip()
        if not text:
            continue
        docs.append(
            {
                "doc_id": safe_str(row.get("doc_id", f"rules_{i}")),
                "calculator_id": cid,
                "title": title,
                "url": url,
                "source": safe_str(row.get("source", "rules")) or "rules",
                "text": text,
                "key_norm": normalize_key(title),
            }
        )
    return docs
