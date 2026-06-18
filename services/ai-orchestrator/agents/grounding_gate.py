"""|OR| grounding gate for the agent critic (RAG×harness step 2).

Turns the evidence the agent actually gathered (retrieve_evidence citations +
recall_memory hits in the transcript) into a coverage score, then runs it
through the ADR-0033 coverage_gate ("học 1 hiểu 10"): enough overlap (IF∩MF)
→ allow conclusions; too little (DE dominates) → the critic forces another
retrieval round or, when it can't improve, declines — no hallucination (K-3).

Pure + deterministic: no LLM, no DB. The critic composes this with its LLM
judgement; for workflows that opt in (`Workflow.requires_grounding`) an
ungrounded "accept" is overridden to "replan".
"""
from __future__ import annotations

import math
import os
from typing import Any

from ..reasoning.knowledge.grounding import coverage_gate


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Saturation rate of the gate's coverage curve. Decoupled from ADR-0033's KB
# `_COVERAGE_K` (0.6) because the gate now aggregates differently (max-agg with
# decay, below) over bge-m3's modest similarity scale — a strong on-KB hit tops
# out near ~0.6 cosine, so the gate needs a higher rate to map "a couple of good
# hits" onto the "đủ" band. Env-tunable; calibrate against the live bge-m3
# similarity distribution (CDFL audit 2026-06-02 follow-up).
_GATE_K = _env_float("KAORI_GATE_COVERAGE_K", 0.85)
_MEM_MASS = 0.2          # each recalled memory adds modest mass (capped)
_MEM_CAP = 3
# Per-citation relevance floor. top-K retrieval ALWAYS returns K docs, so an
# off-domain query still yields K weak (~0.25) cosine hits. Citations below the
# floor contribute NO mass — only genuinely relevant hits count toward "học 1
# hiểu 10" (K-3). bge-m3 gives a ~0.23 same-language floor; 0.35 keeps moderate+
# hits, drops noise. Tunable.
_SIM_FLOOR = _env_float("KAORI_KB_SIM_FLOOR", 0.35)
# Max-aggregation decay (CDFL audit 2026-06-02 P1 — "còn nợ max-agg"). The floor
# alone stops a clearly off-domain query (all hits < floor → 0 mass), but with a
# plain SUM a query returning several citations JUST above the floor still piled
# up coverage (quantity-bù-chất-lượng). We instead rank above-floor hits and add
# them with geometric decay `_AGG_DECAY**i`, so the best hit dominates and the
# tail contributes ever less. Consequence: the mass of N hits at similarity s is
# bounded by s/(1−decay), so MANY mediocre hits can never reach "đủ" — only a
# genuinely strong hit (or a few good ones) can. decay→1 recovers the old SUM;
# decay→0 is pure max(). 0.6 keeps real multi-source on-KB answers at "đủ" while
# capping just-above-floor padding below the generalise threshold.
_AGG_DECAY = _env_float("KAORI_KB_AGG_DECAY", 0.6)


def _result_dict(entry: Any) -> dict:
    r = getattr(entry, "tool_result", None)
    return r if isinstance(r, dict) else {}


def assess_grounding(transcripts: list, *, k: float = _GATE_K) -> dict:
    """Coverage of the session's conclusion by gathered evidence, gated.

    Returns the coverage_gate dict (can_generalize / band / coverage / note)
    plus evidence_count + memory_hits for transparency.
    """
    sims: list[float] = []
    memory_hits = 0
    for entry in transcripts:
        if getattr(entry, "role", None) != "executor":
            continue
        name = getattr(entry, "tool_name", None)
        res = _result_dict(entry)
        if name == "retrieve_evidence":
            for c in (res.get("citations") or []):
                s = c.get("similarity") if isinstance(c, dict) else None
                if isinstance(s, (int, float)):
                    sims.append(max(0.0, float(s)))
        elif name == "recall_memory":
            memory_hits += int(res.get("recalled") or 0)

    # Only above-floor citations contribute mass (quantity ≠ coverage), and they
    # are combined by MAX-AGGREGATION: ranked high→low and summed with geometric
    # decay so the best hit dominates and extra hits add ever less. This bounds
    # the mass of N weak-but-above-floor hits by s/(1−decay), so padding can't
    # reach "đủ" (the decline branch stays alive — K-3). All numeric-similarity
    # citations still count toward evidence_count for transcript transparency.
    above = sorted((s for s in sims if s >= _SIM_FLOOR), reverse=True)
    relevant_mass = sum(s * (_AGG_DECAY ** i) for i, s in enumerate(above))
    mass = relevant_mass + _MEM_MASS * min(memory_hits, _MEM_CAP)
    coverage = round(1.0 - math.exp(-k * mass), 4)
    gate = coverage_gate(coverage)
    return {**gate, "evidence_count": len(sims), "memory_hits": memory_hits}
