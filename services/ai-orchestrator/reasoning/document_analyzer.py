"""Document analyzer — turn extracted document text into insight (Option 1).

For an uploaded hợp đồng / hóa đơn / đơn, produce:
  • risks      — DETERMINISTIC keyword scan (reuse template_comparator's VN/EN
                 business-risk keyword list) → no hallucination.
  • summary    — grounded Qwen summary (2-3 sentences).
  • key_fields — grounded Qwen extraction of số tiền / ngày / các bên / mã số…

Rule-first / LLM-second (K-3 / ADR-0033, same stance as the workflow advisor):
risks are rule-based and always present; the LLM only summarises + extracts and
is told to use ONLY what's in the document. Fail-open: if Qwen is down we still
return the deterministic risks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from .template_comparator import DEFAULT_RISK_KEYWORDS

log = structlog.get_logger()

# Keywords that carry contractual teeth → flag high; the rest medium.
_HIGH_RISK = {
    "trách nhiệm", "bồi thường", "chấm dứt", "đơn phương", "phạt vi phạm",
    "trọng tài", "liability", "indemnity", "termination", "arbitration",
}

_MAX_CHARS = 6000  # cap text fed to the LLM (bounded request, K)


@dataclass
class DocAnalysis:
    summary: str = ""
    key_fields: list[dict] = field(default_factory=list)
    risks: list[dict] = field(default_factory=list)
    model: str = "rules-only"


def scan_risks(text: str) -> list[dict]:
    """Deterministic risk-keyword scan with a short snippet of context."""
    low = text.lower()
    out: list[dict] = []
    seen = set()
    for kw in DEFAULT_RISK_KEYWORDS:
        idx = low.find(kw.lower())
        if idx < 0 or kw.lower() in seen:
            continue
        seen.add(kw.lower())
        start = max(0, idx - 40)
        snippet = text[start: idx + len(kw) + 40].replace("\n", " ").strip()
        out.append({
            "keyword": kw,
            "severity": "high" if kw in _HIGH_RISK else "medium",
            "snippet": snippet,
        })
    return out


_PROMPT = """Dưới đây là nội dung một tài liệu nghiệp vụ (hợp đồng / hóa đơn / đơn …). \
CHỈ dùng thông tin CÓ trong tài liệu — tuyệt đối không bịa.

Trả về DUY NHẤT một JSON object (không thêm chữ nào ngoài JSON) dạng:
{{"summary": "<tóm tắt 2-3 câu tiếng Việt>", "key_fields": [{{"label": "Số tiền", "value": "…"}}]}}

- summary: tài liệu này nói về gì.
- key_fields: các trường khoá nếu có (Số tiền, Ngày, Bên A, Bên B, Mã số, Hiệu lực…); bỏ qua trường không có.

NỘI DUNG:
{text}
"""


def _extract_json(raw: str) -> dict:
    """Pull the first JSON object out of an LLM completion (it may wrap text)."""
    import json as _json
    if not raw:
        return {}
    s, e = raw.find("{"), raw.rfind("}")
    if s < 0 or e <= s:
        return {}
    try:
        obj = _json.loads(raw[s:e + 1])
        return obj if isinstance(obj, dict) else {}
    except (ValueError, TypeError):
        return {}


async def analyze_document(*, text: str, filename: str, enterprise_id: str,
                           with_llm: bool = True) -> DocAnalysis:
    """Analyze extracted document text → risks (rules) + summary/key_fields (Qwen)."""
    text = (text or "").strip()
    risks = scan_risks(text)
    result = DocAnalysis(risks=risks)
    if not text:
        result.summary = "Không có nội dung trích xuất để phân tích."
        return result
    if not with_llm:
        return result

    try:
        from ..engine.llm_router import llm_router
    except Exception:
        return result

    prompt = _PROMPT.format(text=text[:_MAX_CHARS])
    try:
        # The in-process LLMRouter shim exposes complete() (not
        # complete_with_schema) — ask for JSON in the prompt and parse it.
        raw = await llm_router.complete(
            prompt=prompt,
            task="document_analyze",
            consent_external=False,           # Qwen local (K-4) — may carry PII
            enterprise_id=enterprise_id,
            run_id=None,                       # gateway wants a UUID or None, not a filename
            max_tokens=700,
        )
        out = _extract_json(raw or "")
        if out:
            result.summary = (out.get("summary") or "").strip()
            kf = out.get("key_fields") or []
            result.key_fields = [
                {"label": str(f.get("label", "")), "value": str(f.get("value", ""))}
                for f in kf if isinstance(f, dict) and f.get("label")
            ]
            result.model = "qwen2.5-local"
    except Exception as e:  # pragma: no cover - LLM degrade
        log.warning("doc_analyze.llm_failed", filename=filename, error=str(e))

    return result
