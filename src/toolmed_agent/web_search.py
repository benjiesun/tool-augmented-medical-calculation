import json
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

import requests

from .utils import normalize_space, now_str, safe_str


def _is_http_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return p.scheme in {"http", "https"} and bool(p.netloc)
    except Exception:
        return False


def _strip_html_tags(html: str) -> str:
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.extract()
        text = soup.get_text("\n", strip=True)
        return normalize_space(text)
    except Exception:
        text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
        text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
        text = re.sub(r"(?is)<[^>]+>", " ", text)
        return normalize_space(text)


class WebSearcher:
    def __init__(
        self,
        timeout_sec: int = 15,
        max_hits: int = 6,
        bing_api_key: str = "",
        google_api_key: str = "",
        google_cse_id: str = "",
    ):
        self.timeout_sec = max(5, int(timeout_sec))
        self.max_hits = max(1, int(max_hits))
        self.bing_api_key = safe_str(bing_api_key).strip()
        self.google_api_key = safe_str(google_api_key).strip()
        self.google_cse_id = safe_str(google_cse_id).strip()
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

    def _safe_get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> str:
        try:
            resp = self.session.get(url, params=params, headers=headers, timeout=self.timeout_sec)
            resp.raise_for_status()
            return resp.text
        except Exception:
            return ""

    def _extract_links(self, html: str, allow_domains: Optional[List[str]] = None) -> List[str]:
        urls = re.findall(r'href=["\'](https?://[^"\']+)["\']', html or "")
        out: List[str] = []
        seen = set()
        for url in urls:
            if not _is_http_url(url):
                continue
            if allow_domains:
                host = urlparse(url).netloc.lower()
                if not any(host.endswith(x.lower()) for x in allow_domains):
                    continue
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
        return out

    def _search_mdcalc(self, query: str) -> List[Dict[str, Any]]:
        url = f"https://www.mdcalc.com/search?query={quote_plus(query)}"
        html = self._safe_get(url)
        links = self._extract_links(html, allow_domains=["mdcalc.com"])
        hits = []
        for link in links[: self.max_hits]:
            hits.append({"engine": "mdcalc", "title": "", "url": link, "snippet": ""})
        return hits

    def _search_bing_api(self, query: str) -> List[Dict[str, Any]]:
        if not self.bing_api_key:
            return []
        try:
            resp = self.session.get(
                "https://api.bing.microsoft.com/v7.0/search",
                params={"q": query, "count": self.max_hits, "mkt": "en-US"},
                headers={"Ocp-Apim-Subscription-Key": self.bing_api_key},
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            items = (((data or {}).get("webPages") or {}).get("value") or []) if isinstance(data, dict) else []
            out = []
            for item in items[: self.max_hits]:
                out.append(
                    {
                        "engine": "bing",
                        "title": safe_str(item.get("name", "")),
                        "url": safe_str(item.get("url", "")),
                        "snippet": safe_str(item.get("snippet", "")),
                    }
                )
            return out
        except Exception:
            return []

    def _search_google_api(self, query: str) -> List[Dict[str, Any]]:
        if not self.google_api_key or not self.google_cse_id:
            return []
        try:
            resp = self.session.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": self.google_api_key,
                    "cx": self.google_cse_id,
                    "q": query,
                    "num": min(10, self.max_hits),
                },
                timeout=self.timeout_sec,
            )
            resp.raise_for_status()
            data = resp.json() if "application/json" in resp.headers.get("content-type", "") else {}
            items = data.get("items", []) if isinstance(data, dict) else []
            out = []
            for item in items[: self.max_hits]:
                out.append(
                    {
                        "engine": "google",
                        "title": safe_str(item.get("title", "")),
                        "url": safe_str(item.get("link", "")),
                        "snippet": safe_str(item.get("snippet", "")),
                    }
                )
            return out
        except Exception:
            return []

    def _search_duckduckgo_html(self, query: str) -> List[Dict[str, Any]]:
        html = self._safe_get("https://duckduckgo.com/html/", params={"q": query})
        urls = self._extract_links(html)
        out: List[Dict[str, Any]] = []
        for u in urls[: self.max_hits]:
            out.append({"engine": "duckduckgo", "title": "", "url": u, "snippet": ""})
        return out

    def _fetch_page_text(self, url: str, max_chars: int = 3200) -> str:
        if not _is_http_url(url):
            return ""
        html = self._safe_get(url)
        if not html:
            return ""
        text = _strip_html_tags(html)
        if len(text) > max_chars:
            text = text[:max_chars]
        return text

    def search_calculator_rule(
        self,
        calculator_id: Any,
        calculator_name: str,
        question: str,
    ) -> Dict[str, Any]:
        cid = safe_str(calculator_id).strip()
        query_main = f"{calculator_name} mdcalc calculator"
        query_alt = f"site:mdcalc.com {calculator_name} {question[:180]}"

        hits: List[Dict[str, Any]] = []
        hits.extend(self._search_mdcalc(query_main))
        hits.extend(self._search_bing_api(query_main))
        hits.extend(self._search_google_api(query_main))
        hits.extend(self._search_duckduckgo_html(query_alt))

        dedup: List[Dict[str, Any]] = []
        seen = set()
        for h in hits:
            u = safe_str(h.get("url", "")).strip()
            if not _is_http_url(u) or u in seen:
                continue
            seen.add(u)
            dedup.append(h)
            if len(dedup) >= self.max_hits:
                break

        snippets: List[str] = []
        enriched_hits: List[Dict[str, Any]] = []
        for i, h in enumerate(dedup, start=1):
            u = safe_str(h.get("url", "")).strip()
            text = self._fetch_page_text(u)
            if not text:
                continue
            snippet = text[:1200]
            enriched = {
                **h,
                "text_preview": snippet,
                "fetched_at": now_str(),
            }
            enriched_hits.append(enriched)
            snippets.append(f"[Source {i}] {u}\n{snippet}")

        if not snippets:
            snippets = [
                (
                    f"No external evidence fetched for calculator {cid} ({calculator_name}). "
                    "Use existing memory and local fallback prompts."
                )
            ]

        evidence_text = "\n\n".join(snippets)
        return {
            "calculator_id": cid,
            "calculator_name": safe_str(calculator_name),
            "query": safe_str(question),
            "evidence_text": evidence_text,
            "source_hits": enriched_hits,
        }
