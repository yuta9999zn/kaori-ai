"""ADR-0033 — inject foundational knowledge into analysis prompts.

The CONSUMER of grounding.py: embeds the analysis subject, retrieves
authority-ranked foundational docs from the DB, computes the |OR| coverage gate,
and renders a prompt preamble built FROM the knowledge_documents rows — no
hardcoded principles, the curated tier-2 seed is the source of truth.

Bounded + fail-open (Engineering Tenet 13, [[feedback_llm_in_request_path_bound]]):
every call is best-effort — a disabled flag, an embed/search error, or an empty
result all yield an empty preamble so the analysis narrative still runs. The
embed + search sit inside the caller's existing narrative timeout. Off-switch
for the pilot 7B box: ``KAORI_KB_GROUND_ANALYZE=false``.
"""
from __future__ import annotations

import os

import structlog

from .embed import embed_text
from .grounding import (
    FOUNDATIONAL_TIERS,
    coverage_gate,
    knowledge_coverage,
    rank_by_authority,
)

log = structlog.get_logger()

_ENABLED = os.getenv("KAORI_KB_GROUND_ANALYZE", "true").lower() != "false"
_TOP_K = int(os.getenv("KAORI_KB_GROUND_TOPK", "5"))
_REINFORCE_GLOBAL = os.getenv("KAORI_KB_REINFORCE_GLOBAL", "true").lower() != "false"

_EMPTY = {"preamble": "", "coverage": 0.0, "can_generalize": True, "cited_ids": []}


def _render_preamble(docs: list, gate: dict) -> str:
    """Build the reasoning preamble from retrieved DB docs + the gate note.
    Each line cites its [source] so the narrative can attribute benchmarks."""
    if not docs:
        return ""
    lines = ["KIẾN THỨC NỀN (suy luận THEO, trích [nguồn] khi dùng; KHÔNG bịa số):"]
    for d in docs:
        src = f" [{d.source}]" if d.source else ""
        lines.append(f"- ({d.category or 'chung'}) {d.title}: {d.content}{src}")
    lines.append(gate["note"])
    return "\n".join(lines) + "\n\n"


async def ground_analysis(
    enterprise_id: str, subject_text: str, *,
    store, embed=embed_text, top_k: int = _TOP_K,
) -> dict:
    """Embed ``subject_text`` → foundational semantic_search → authority rank →
    |OR| coverage gate → DB-sourced preamble. Returns
    ``{preamble, coverage, can_generalize, cited_ids}``. Best-effort: empty
    preamble on any failure or when disabled. ``store``/``embed`` injected for
    tests. The subject is the real analysis subject (templates + columns) so the
    KB is matched semantically — no hardcoded template→category routing."""
    if not _ENABLED or not (subject_text or "").strip():
        return dict(_EMPTY)
    try:
        vec = await embed(subject_text, enterprise_id=enterprise_id)
        if not vec:
            return dict(_EMPTY)
        docs = await store.semantic_search(enterprise_id, vec, top_k=top_k)
        ranked = rank_by_authority(docs)
        foundational = [d for d in ranked if d.tier in FOUNDATIONAL_TIERS][:top_k]
        cov = knowledge_coverage(ranked)
        gate = coverage_gate(cov)
        return {
            "preamble": _render_preamble(foundational, gate),
            "coverage": cov,
            "can_generalize": gate["can_generalize"],
            "cited_ids": [d.document_id for d in foundational],
        }
    except Exception as exc:  # noqa: BLE001 — grounding is best-effort enrichment
        log.warning("kb.ground_analysis.degraded",
                    enterprise_id=enterprise_id, error=str(exc)[:200])
        return dict(_EMPTY)


async def reinforce_cited(enterprise_id: str, cited_ids: list, *, store) -> int:
    """Reinforce-on-cite (ADR-0033 aging) — closes the loop for the FOUNDATIONAL
    layer: cited foundational docs are global (tier 1/2), so they mature via the
    store's admin-context global path (tenant RLS can't write global rows; the
    ``tenant_id IS NULL`` guard there keeps it from ever touching tenant data).
    Best-effort + flag-guarded (KAORI_KB_REINFORCE_GLOBAL). Returns count."""
    if not _REINFORCE_GLOBAL or not cited_ids:
        return 0
    try:
        return await store.reinforce_global(cited_ids)
    except Exception as exc:  # noqa: BLE001 — best-effort enrichment
        log.warning("kb.reinforce_cited.degraded",
                    enterprise_id=enterprise_id, error=str(exc)[:200])
        return 0
