"""Grounding self-verify (CR-0018) — practical number-overlap |OR|.

Catches an AI insight asserting numbers that are NOT in the measured facts it
was derived from — a deployable anti-fabrication check.

Relation to CDFL (be precise): the paper's |OR| = I(I:M), the von Neumann
mutual information over density operators ρ_IM (reasoning/cdfl/hilbert_metric.py)
— an OBSERVABILITY metric (entanglement of internal representation ↔ environment),
NOT a test of "is this stated number real?". Here |OR| is the pragmatic analog
used in the NNL-Harness prototype: the share of an insight's numeric claims that
match a measured fact within tolerance. Same spirit (overlap of the internal
claim with measured matter), different, deployable form for text claims.

It is a HEURISTIC signal, not a proof: it errs toward NOT flagging (a claimed
number counts as grounded if any measured fact plausibly matches, incl. a
percent/fraction rescale), so a flagged number is a high-confidence fabrication.
Surfaced with a verify-before-action disclaimer (BR-9); NEVER used to silently
rewrite the insight.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# A run of digits possibly with thousands/decimal separators (and a leading
# sign). Currency symbols / % are stripped by _to_float.
_NUM_RE = re.compile(r"-?\d[\d.,]*\d|-?\d")


@dataclass
class Grounding:
    score: float            # |OR| ∈ [0,1]; 1.0 when every claim is grounded (or none)
    n_claims: int
    n_matched: int
    flagged: list[float] = field(default_factory=list)   # claims with no measured match


def _to_float(tok: str) -> Any:
    """Parse one numeric token, tolerating VN/EN separators. Returns float|None."""
    s = tok.strip().strip("%").replace(" ", "")
    if not s or s in {"-", ".", ","}:
        return None
    has_comma, has_dot = "," in s, "." in s
    if has_comma and has_dot:
        # The right-most separator is the decimal point; the other groups.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        # "1,5" → decimal (1-2 trailing digits, single comma); else thousands.
        a, _, b = s.partition(",")
        s = f"{a}.{b}" if (s.count(",") == 1 and len(b) in (1, 2)) else s.replace(",", "")
    elif has_dot:
        # one dot with 1-2 trailing digits = decimal (3.5); otherwise dots are
        # VN thousands separators (1.000.000 → 1000000).
        if not (s.count(".") == 1 and len(s.rsplit(".", 1)[1]) in (1, 2)):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def extract_claims(text: str) -> list[float]:
    """Every numeric value asserted in a piece of text."""
    out: list[float] = []
    for m in _NUM_RE.findall(text or ""):
        v = _to_float(m)
        if v is not None:
            out.append(v)
    return out


def collect_facts(payload: Any) -> list[float]:
    """Recursively pull every number out of a nested results payload (JSONB
    blocks: stat cards, tables, dicts, lists, embedded strings)."""
    facts: list[float] = []

    def walk(x: Any) -> None:
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            facts.append(float(x))
        elif isinstance(x, str):
            facts.extend(extract_claims(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)

    walk(payload)
    return facts


def _matches(claim: float, facts: list[float], *, tol: float) -> bool:
    # Tolerate percent-vs-fraction confusion (85 ↔ 0.85) and scale drift.
    candidates = {claim, claim / 100.0, claim * 100.0}
    for f in facts:
        scale = max(abs(f), 1.0)
        for c in candidates:
            if abs(c - f) <= tol * scale:
                return True
    return False


def ground_claims(text: str, facts: list[float], *, tol: float = 0.02) -> Grounding:
    """|OR| of an insight's numeric claims against the measured facts."""
    claims = extract_claims(text)
    if not claims:
        return Grounding(score=1.0, n_claims=0, n_matched=0, flagged=[])
    flagged = [c for c in claims if not _matches(c, facts, tol=tol)]
    matched = len(claims) - len(flagged)
    return Grounding(
        score=round(matched / len(claims), 4),
        n_claims=len(claims), n_matched=matched, flagged=flagged,
    )


def _fmt(x: float) -> str:
    return str(int(x)) if x == int(x) else str(x)


def disclaimer_for(g: Grounding) -> str:
    """BR-9 — always present; sharpened when a claim is unverified."""
    if g.flagged:
        nums = ", ".join(_fmt(x) for x in g.flagged[:5])
        return (f"⚠ {len(g.flagged)} số chưa khớp dữ liệu đo được ({nums}) — "
                f"kiểm chứng trước khi hành động.")
    return "AI tạo từ dữ liệu — nên kiểm chứng trước khi quyết định."
