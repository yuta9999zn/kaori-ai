"""
CDFL — Convergent Dual-Field Learning

Port của thuật toán exploration từ luận văn NNL-NTHT
(Nhất Nguyên Luận, Nhị Trường Hội Tụ — Nguyễn Trường An).

Two layers in this module:

1. **CDFL v3 algorithmic layer** (Phase 1.5 Tuần 4-6 port, P15-S11)
   Ba component được benchmark validate qua 8 phase:
   - Learned transition model P(s'|s,a)         — CRITICAL (-31.6pp khi gỡ)
   - H-step Monte Carlo lookahead               — ~+4pp combined
   - Information gain (novelty × uncertainty)   — <2pp đơn lẻ, combined matters

   Trong Kaori, 3 component map vào:
   - transition_model ↔ Process Mining (direct-follow learning)
   - lookahead        ↔ Workflow planner (top-K action sequences)
   - information_gain ↔ RAG re-ranking + insight prioritisation

2. **CDFL v10/v11 Hilbert-space measurement layer** (P15-S11 2026-05-17 add)
   Per `report CDFL v10.zip` + `report CDFL v11.zip` — full Hilbert
   space formalism verified at v11. The verified result:

       NNL-NTHT là một descriptive mathematical framework đem ra
       cấu trúc cho understanding-building qua interaction. Their
       entanglement (measured by I(I:M)) grows monotonically during
       interaction; growth correlates với prediction accuracy
       (r = +0.796).

   Caveat from v11 ablation: active action selection NOT better than
   random. Framework is descriptive, not prescriptive — we port the
   measurement primitives (I(I:M) gauge) only, NOT the action loop.
   See ADR-0020 for the formal acceptance.

   Public API (this layer):
       from reasoning.cdfl.hilbert_metric import (
           mutual_information, von_neumann_entropy, partial_trace,
           make_random_hermitian, make_pure_product_state,
       )

Public API (overall):
    from reasoning.cdfl import (
        CDFLAgent, TransitionModel, IGScorer, LookaheadPlanner,
        hilbert_metric,
    )

Sources:
    D:\\Luận văn nhất nguyên 2 trường luận giao thoa\\
        - Thuật toán tương ứng.docx  (15-step canonical algorithm)
        - _cdfl_extract\\v8\\REPORT_V8.md  (math formalisation)
        - _cdfl_extract\\v8\\ablation_study.py  (CDFLv3 interface)
        - report CDFL v10.zip       (full Hilbert formalism — verified)
        - report CDFL v11.zip       (bridge test: I(I:M) ↔ accuracy r=+0.796)
"""
from __future__ import annotations

from . import hilbert_metric
from .agent import CDFLAgent
from .empowerment import ProtectionAdvice, option_preserving, protection_advice
from .four_fold_de import FourFoldDE, assemble_de
from .information_gain import IGScorer
from .lookahead import LookaheadPlanner
from .transition_model import TransitionModel
from .types import Action, ActionScore, RolloutResult, State, Transition

__all__ = [
    "Action",
    "ActionScore",
    "CDFLAgent",
    "FourFoldDE",
    "IGScorer",
    "LookaheadPlanner",
    "ProtectionAdvice",
    "RolloutResult",
    "State",
    "Transition",
    "TransitionModel",
    "assemble_de",
    "hilbert_metric",
    "option_preserving",
    "protection_advice",
]
