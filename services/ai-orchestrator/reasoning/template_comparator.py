"""
Phase 2.5 — `compare_to_template` AI node.

Compares a candidate document against a known-good template. Surfaces
clauses that are MISSING (in template but not candidate), ADDED (in
candidate but not template), MODIFIED (paraphrased / changed terms),
or MATCH (substantively identical).

Use cases (per WORKFLOW_USE_CASES.md):
- Vendor NDA review — does this draft drop the IP-assignment clause?
- Service contract — has anything changed since the last signed
  version vs the standard playbook?
- Procurement PO — did the vendor sneak in their own payment-terms
  clause?
- Regulatory filing — does our submission contain every clause the
  authority's template demands?

Pipeline
--------
1. Extract clauses from both block lists (TITLE → new clause, body
   accumulates from consecutive TEXT/LIST/QUOTE blocks).
2. Embed every clause via llm-gateway /v1/embed.
3. For each candidate clause, find nearest template clause by cosine.
   - sim ≥ threshold → "match candidate" — pair sent to LLM for diff
   - sim < threshold → status='added' (candidate clause has no template
                        peer)
4. Template clauses with no candidate pair above threshold → status=
   'missing'.
5. LLM diff per matched pair returns {status, risk_level, explanation}
   where status ∈ {match, modified}.
6. Aggregate into CompareOutput with summary counts + risk score.

K-rules
-------
K-3: All LLM + embedding calls via llm-gateway only.
K-4: consent_external opt-in. Embedding endpoint refuses
     consent_external anyway (always local); LLM diff respects flag.
K-17: side_effect_class = read_only. Caller persists results into
     `contract_compare_results` table.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx
import structlog

from ..data_plane_shim import Block, BlockType
from ..engine.llm_router import llm_router

log = structlog.get_logger()


LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")
EMBED_TIMEOUT_S = float(os.getenv("EMBED_TIMEOUT_S", "30"))

# Cap a clause body at ~3 KB before embedding — BGE-M3 is well within
# its context window but very long clauses (e.g. a 5-page liability
# annex) dilute the embedding signal. Caller can split before invoking
# if they want per-paragraph granularity.
_CLAUSE_TEXT_CAP = 3000

# Default cosine cutoff for "this candidate clause has a template
# peer". 0.65 calibrated to BGE-M3 + VN/EN business prose — below
# this the LLM diff cost isn't worth it.
_DEFAULT_SIM_THRESHOLD = 0.65

# Default LLM cap per diff call.
_MAX_DIFF_TOKENS = 600


# ─── Shape ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Clause:
    """One logical clause extracted from a Block list. `title` may be
    empty when the block stream had no TITLE separator (the whole doc
    becomes one big clause)."""
    title:                str
    text:                 str
    source_block_indices: tuple[int, ...]
    page_idx:             int


@dataclass
class CompareInput:
    template_blocks:  list[Block]
    candidate_blocks: list[Block]
    enterprise_id:    str
    consent_external: bool = False
    run_id:           Optional[str] = None
    # Cosine cutoff for "this candidate clause has a template peer".
    similarity_threshold: float = _DEFAULT_SIM_THRESHOLD
    # Caller-supplied risk markers — if a clause's `text` contains any
    # of these (case-insensitive), em bump its risk_level one notch.
    # Em default to common VN business risk keywords.
    risk_keywords:    list[str] = None    # type: ignore[assignment]
    # Injection point for tests. Production uses LLM_GATEWAY_URL.
    llm_gateway_url:  Optional[str] = None

    def __post_init__(self):
        if self.risk_keywords is None:
            self.risk_keywords = list(DEFAULT_RISK_KEYWORDS)


DEFAULT_RISK_KEYWORDS = [
    # VN
    "trách nhiệm",      # liability
    "bồi thường",       # indemnity
    "chấm dứt",         # termination
    "đơn phương",       # unilateral
    "phạt vi phạm",     # penalty
    "sở hữu trí tuệ",   # IP
    "bí mật kinh doanh",
    "luật áp dụng",
    "trọng tài",        # arbitration
    "không cạnh tranh", # non-compete
    # EN
    "liability", "indemnity", "termination",
    "intellectual property", "non-compete", "arbitration",
]


@dataclass(frozen=True)
class ClauseMatch:
    """One row in the comparison report."""
    template_clause_idx:  Optional[int]   # None when status='added'
    candidate_clause_idx: Optional[int]   # None when status='missing'
    status:               str             # 'match' | 'modified' | 'missing' | 'added'
    similarity:           float           # 0..1; 0.0 for missing/added
    risk_level:           str             # 'low' | 'medium' | 'high'
    explanation:          str


@dataclass(frozen=True)
class CompareOutput:
    matches:               list[ClauseMatch]
    summary:               dict[str, int]     # counts per status
    overall_risk_score:    float              # 0..1 normalised
    template_clause_count: int
    candidate_clause_count: int


# ─── Clause extraction ──────────────────────────────────────────────


def extract_clauses(blocks: list[Block]) -> list[Clause]:
    """Group a Block list into clauses. Heuristic:
      - Each TITLE block starts a new clause; its `text` becomes title.
      - Subsequent TEXT/LIST/QUOTE blocks accumulate as the body.
      - HEADER/FOOTER/PAGE_NUMBER/IMAGE_REF/CAPTION skipped.
      - TABLE/CODE/EQUATION terminate the current clause body and
        start a new one (they tend to mark structural breaks).

    If the document has zero TITLE blocks, em emit ONE clause with
    title="" + the concatenated body — better than dropping content.
    """
    clauses: list[Clause] = []
    cur_title = ""
    cur_body_bits: list[str] = []
    cur_indices: list[int] = []
    cur_page = 0

    def _flush() -> None:
        body = "\n".join(b for b in cur_body_bits if b)
        if cur_title or body:
            clauses.append(Clause(
                title=cur_title,
                text=body[:_CLAUSE_TEXT_CAP],
                source_block_indices=tuple(cur_indices),
                page_idx=cur_page,
            ))

    for idx, b in enumerate(blocks):
        if b.type in (BlockType.HEADER, BlockType.FOOTER,
                       BlockType.PAGE_NUMBER, BlockType.IMAGE_REF,
                       BlockType.CAPTION):
            continue
        if b.type == BlockType.TITLE:
            _flush()
            cur_title = b.text.strip()
            cur_body_bits = []
            cur_indices = [idx]
            cur_page = b.page_idx
            continue
        if b.type in (BlockType.TABLE, BlockType.CODE, BlockType.EQUATION):
            # Structural break: flush + skip the structured block from
            # the body (it's not prose to diff line-by-line).
            _flush()
            cur_title = ""
            cur_body_bits = []
            cur_indices = []
            cur_page = b.page_idx
            continue
        # TEXT / LIST / QUOTE
        if not cur_indices:
            # Implicit "preface" clause before any title.
            cur_page = b.page_idx
        cur_body_bits.append(b.text.strip())
        cur_indices.append(idx)

    _flush()
    return clauses


# ─── Embeddings + cosine ────────────────────────────────────────────


async def _embed_clauses(
    clauses:        list[Clause],
    enterprise_id:  str,
    gateway_url:    str,
) -> list[list[float]]:
    """Embed every clause via llm-gateway /v1/embed. Empty clauses
    return [] vector; caller handles by treating sim=0."""
    url = gateway_url + "/v1/embed"
    out: list[list[float]] = []
    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT_S) as client:
        for c in clauses:
            payload_text = (c.title + "\n" + c.text).strip()
            if not payload_text:
                out.append([])
                continue
            try:
                resp = await client.post(url, json={
                    "text":          payload_text[:8000],
                    "enterprise_id": enterprise_id,
                })
                resp.raise_for_status()
                vec = resp.json().get("vector") or []
            except Exception as e:    # noqa: BLE001
                log.warning("template_comparator.embed_failed",
                            error=str(e),
                            enterprise_id=enterprise_id)
                vec = []
            out.append([float(x) for x in vec])
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity. Returns 0.0 on dim mismatch or
    zero-magnitude vectors so callers never divide by zero downstream."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


# ─── LLM diff ───────────────────────────────────────────────────────


_DIFF_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["status", "risk_level", "explanation"],
    "properties": {
        "status":      {"type": "string",
                          "enum": ["match", "modified"]},
        "risk_level":  {"type": "string",
                          "enum": ["low", "medium", "high"]},
        "explanation": {"type": "string", "maxLength": 500},
    },
}


def _build_diff_prompt(template_clause: Clause, candidate_clause: Clause) -> str:
    parts = [
        "Bạn so sánh 2 điều khoản hợp đồng cho rủi ro pháp lý / kinh doanh.",
        "",
        f"Điều khoản TEMPLATE (đã được phê duyệt):",
        f"  Tiêu đề: {template_clause.title or '(không có)'}",
        f"  Nội dung:",
        template_clause.text,
        "",
        f"Điều khoản CANDIDATE (cần đánh giá):",
        f"  Tiêu đề: {candidate_clause.title or '(không có)'}",
        f"  Nội dung:",
        candidate_clause.text,
        "",
        "Trả về JSON:",
        "  status       — 'match' nếu nội dung tương đương về nghĩa;",
        "                'modified' nếu có khác biệt thực chất (thêm/bớt nghĩa vụ,",
        "                đổi giới hạn, đổi điều kiện chấm dứt...)",
        "  risk_level   — 'low' (thay đổi ngôn ngữ, không đổi nghĩa);",
        "                'medium' (thay đổi điều kiện nhưng cân bằng cho 2 bên);",
        "                'high' (bất lợi cho phía Kaori: tăng trách nhiệm, giảm",
        "                quyền, bỏ giới hạn bồi thường, đổi luật áp dụng...)",
        "  explanation  — 1-2 câu tiếng Việt giải thích",
        "Không thêm trường khác. Không thêm văn bản ngoài JSON.",
    ]
    return "\n".join(parts)


async def _llm_diff(
    template_clause:  Clause,
    candidate_clause: Clause,
    enterprise_id:    str,
    consent_external: bool,
    run_id:           Optional[str],
) -> dict[str, Any]:
    """One LLM diff call. Returns dict matching _DIFF_OUTPUT_SCHEMA."""
    prompt = _build_diff_prompt(template_clause, candidate_clause)
    try:
        return await llm_router.complete_with_schema(
            prompt=prompt,
            task="compare_to_template",
            output_schema=_DIFF_OUTPUT_SCHEMA,
            consent_external=consent_external,
            enterprise_id=enterprise_id,
            run_id=run_id,
            max_tokens=_MAX_DIFF_TOKENS,
        )
    except AttributeError:
        # Backwards compat (same pattern as classify_document)
        text = await llm_router.complete(
            prompt=prompt,
            task="compare_to_template",
            consent_external=consent_external,
            enterprise_id=enterprise_id,
            run_id=run_id,
            max_tokens=_MAX_DIFF_TOKENS,
        )
        from .document_classifier import _parse_json_fallback
        return _parse_json_fallback(text)


# ─── Risk aggregation ───────────────────────────────────────────────


_RISK_WEIGHTS = {"low": 0.1, "medium": 0.5, "high": 1.0}


def _bump_risk_for_keywords(
    clause: Optional[Clause],
    base_risk: str,
    keywords: list[str],
) -> str:
    """If the clause text contains any caller-supplied risk keyword,
    bump risk one notch (low→medium, medium→high)."""
    if clause is None or not keywords:
        return base_risk
    text_lower = (clause.title + " " + clause.text).lower()
    if not any(kw.lower() in text_lower for kw in keywords):
        return base_risk
    if base_risk == "low":
        return "medium"
    if base_risk == "medium":
        return "high"
    return "high"


def _aggregate_risk_score(matches: list[ClauseMatch]) -> float:
    """Normalise the weighted-risk sum to 0..1. 'missing' counted as
    high (the clause SHOULD be there but isn't); 'added' counted as
    medium (caller's playbook should review)."""
    if not matches:
        return 0.0
    total = 0.0
    for m in matches:
        if m.status == "missing":
            total += _RISK_WEIGHTS["high"]
        elif m.status == "added":
            total += _RISK_WEIGHTS["medium"]
        else:
            total += _RISK_WEIGHTS.get(m.risk_level, 0.1)
    max_possible = len(matches) * _RISK_WEIGHTS["high"]
    return total / max_possible if max_possible > 0 else 0.0


# ─── Top-level API ──────────────────────────────────────────────────


async def compare_to_template(inp: CompareInput) -> CompareOutput:
    """Run the full compare pipeline. Returns CompareOutput with one
    ClauseMatch per (template ∪ candidate) clause + per-status counts +
    normalised risk score."""
    template_clauses = extract_clauses(inp.template_blocks)
    candidate_clauses = extract_clauses(inp.candidate_blocks)

    if not template_clauses and not candidate_clauses:
        return CompareOutput(
            matches=[], summary={}, overall_risk_score=0.0,
            template_clause_count=0, candidate_clause_count=0,
        )

    gateway_url = inp.llm_gateway_url or LLM_GATEWAY_URL
    template_embs = await _embed_clauses(template_clauses, inp.enterprise_id, gateway_url)
    candidate_embs = await _embed_clauses(candidate_clauses, inp.enterprise_id, gateway_url)

    matches: list[ClauseMatch] = []
    used_template_indices: set[int] = set()

    # Pass 1: every candidate clause finds its best template peer.
    for cand_idx, cand_clause in enumerate(candidate_clauses):
        cand_vec = candidate_embs[cand_idx]
        best_template_idx = -1
        best_sim = -1.0
        for tpl_idx, tpl_vec in enumerate(template_embs):
            sim = _cosine(cand_vec, tpl_vec)
            if sim > best_sim:
                best_sim = sim
                best_template_idx = tpl_idx

        if best_template_idx == -1 or best_sim < inp.similarity_threshold:
            # Candidate clause has no template peer above threshold.
            matches.append(ClauseMatch(
                template_clause_idx=None,
                candidate_clause_idx=cand_idx,
                status="added",
                similarity=max(best_sim, 0.0),
                risk_level=_bump_risk_for_keywords(cand_clause, "medium",
                                                     inp.risk_keywords),
                explanation=("Candidate có điều khoản không tìm thấy trong "
                              "template (sim={:.2f}).".format(max(best_sim, 0.0))),
            ))
            continue

        used_template_indices.add(best_template_idx)
        tpl_clause = template_clauses[best_template_idx]

        # Above threshold: ask LLM whether it's a true match or a
        # paraphrased / changed-substance "modified" clause.
        try:
            diff = await _llm_diff(
                tpl_clause, cand_clause,
                enterprise_id=inp.enterprise_id,
                consent_external=inp.consent_external,
                run_id=inp.run_id,
            )
        except Exception as e:    # noqa: BLE001
            log.warning("template_comparator.diff_failed",
                        cand_idx=cand_idx, tpl_idx=best_template_idx,
                        error=str(e),
                        enterprise_id=inp.enterprise_id)
            # Fall back: assume modified, low confidence
            diff = {"status": "modified", "risk_level": "medium",
                     "explanation": f"LLM diff lỗi ({type(e).__name__}); "
                                     f"đánh giá thủ công."}

        status = str(diff.get("status", "modified")).lower()
        if status not in {"match", "modified"}:
            status = "modified"
        risk = str(diff.get("risk_level", "medium")).lower()
        if risk not in _RISK_WEIGHTS:
            risk = "medium"
        explanation = str(diff.get("explanation", ""))[:500]

        bumped_risk = _bump_risk_for_keywords(cand_clause, risk, inp.risk_keywords)

        matches.append(ClauseMatch(
            template_clause_idx=best_template_idx,
            candidate_clause_idx=cand_idx,
            status=status,
            similarity=best_sim,
            risk_level=bumped_risk,
            explanation=explanation,
        ))

    # Pass 2: any template clause that NO candidate mapped to is missing.
    for tpl_idx, tpl_clause in enumerate(template_clauses):
        if tpl_idx in used_template_indices:
            continue
        matches.append(ClauseMatch(
            template_clause_idx=tpl_idx,
            candidate_clause_idx=None,
            status="missing",
            similarity=0.0,
            risk_level=_bump_risk_for_keywords(tpl_clause, "high",
                                                 inp.risk_keywords),
            explanation=(f"Template có điều khoản '{tpl_clause.title or '(không tiêu đề)'}'"
                          " không xuất hiện trong candidate."),
        ))

    summary: dict[str, int] = {"match": 0, "modified": 0, "missing": 0, "added": 0}
    for m in matches:
        summary[m.status] = summary.get(m.status, 0) + 1

    risk_score = _aggregate_risk_score(matches)

    log.info("compare_to_template.done",
             template_clauses=len(template_clauses),
             candidate_clauses=len(candidate_clauses),
             summary=summary,
             risk_score=risk_score,
             enterprise_id=inp.enterprise_id)

    return CompareOutput(
        matches=matches,
        summary=summary,
        overall_risk_score=risk_score,
        template_clause_count=len(template_clauses),
        candidate_clause_count=len(candidate_clauses),
    )
