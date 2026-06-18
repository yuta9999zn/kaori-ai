"""
CDFL v10/v11 Hilbert-space metric helpers.

Ported from the luận văn `report CDFL v10.zip` and `report CDFL v11.zip`
(D:\\Luận văn nhất nguyên 2 trường luận giao thoa\\). The full v10
implementation (3-fold Φ̂_α pluralism + Ĥ_int coupling + Lindblad
dynamics + M̂_int Kraus + γ function) is research code; here we
port ONLY the measurement primitives, which is the part v11 verified.

Why only the measurement primitives
-----------------------------------
V11 bridge test (Phase 11 of the luận văn) found:
  * I(I:M) growth correlates with prediction accuracy: r = +0.796
  * Active action selection NOT better than random
  * → Framework is **descriptive**, not algorithmic. It describes how
    representational understanding builds during interaction; it does
    NOT prescribe an optimal action policy.

So in Kaori we want the **measurement** (I(I:M) gauge over time) for
observability + ADR-0020 verification, NOT the v10 action-selection
loop (which v11 showed is no better than random).

Provenance
----------
Source: `report CDFL v10.zip`, `cdfl_v10_full.py` lines 28-69.
Source: `report CDFL v11.zip`, `REPORT_V11.md` final position statement.

Quotation from REPORT_V11.md §"Refined position statement":

    NNL-NTHT là một descriptive mathematical framework đem ra cấu trúc
    cho understanding-building qua interaction. Cụ thể:
      - Internal Field (IF) là Hilbert space của internal representations
      - Matter Field (MF) là Hilbert space của environment states
      - Their entanglement (measured by I(I:M)) grows monotonically
        during interaction
      - This growth correlates với prediction accuracy về environment

Public API
----------
  von_neumann_entropy(rho)             — S(ρ) = -tr(ρ log ρ)
  partial_trace(rho, dim_keep, ...)    — tr_B(ρ_AB) or tr_A(ρ_AB)
  mutual_information(rho_IM, dim_I,    — I(I:M) = S(ρ_I) + S(ρ_M) - S(ρ_IM)
                     dim_M)              (the |OR| proxy verified at v11)
  relative_entropy(rho, sigma)         — DE = S(ρ‖σ) (the Dark Existence
                                         quantity; complementary to |OR|)
  make_random_hermitian(dim, scale,    — test fixture: Hermitian matrix
                          seed=None)

All four are pure-Python numpy. No scipy required (the v10 dynamics
operators that needed scipy.linalg.expm are NOT ported — see "Why
only the measurement primitives" above).
"""
from __future__ import annotations

from typing import Optional

import numpy as np


def von_neumann_entropy(rho: np.ndarray, eps: float = 1e-12) -> float:
    """S(ρ) = -tr(ρ log ρ) via eigendecomposition.

    Eigenvalues below `eps` are dropped to avoid log(0) producing -inf;
    the truncation is information-theoretically negligible (those
    eigenvalues carry < eps of probability mass).
    """
    eigenvalues = np.linalg.eigvalsh(rho)
    eigenvalues = eigenvalues[eigenvalues > eps]
    return float(-np.sum(eigenvalues * np.log(eigenvalues + eps)))


def partial_trace(
    rho: np.ndarray, dim_keep: int, dim_trace: int,
    *, keep_first: bool = True,
) -> np.ndarray:
    """tr_B(ρ_AB) when keep_first=True, else tr_A(ρ_AB).

    Args:
      rho:        density operator on ℋ_A ⊗ ℋ_B, shape (dim_A*dim_B, dim_A*dim_B)
      dim_keep:   dimension of the subsystem to KEEP
      dim_trace:  dimension of the subsystem to TRACE OUT
      keep_first: True → trace out ℋ_B; False → trace out ℋ_A
    """
    if keep_first:
        rho_reshape = rho.reshape(dim_keep, dim_trace, dim_keep, dim_trace)
        return np.trace(rho_reshape, axis1=1, axis2=3)
    else:
        rho_reshape = rho.reshape(dim_trace, dim_keep, dim_trace, dim_keep)
        return np.trace(rho_reshape, axis1=0, axis2=2)


def mutual_information(
    rho_IM: np.ndarray, dim_I: int, dim_M: int,
) -> float:
    """I(I:M) = S(ρ_I) + S(ρ_M) - S(ρ_IM)

    The "|OR|" quantity in NNL-NTHT. V11 verified: this grows with
    interaction AND correlates with prediction accuracy (r = +0.796).

    Bounded: 0 ≤ I(I:M) ≤ min(log dim_I, log dim_M). Returns 0 when
    ρ_I ⊗ ρ_M = ρ_IM (no entanglement).
    """
    rho_I = partial_trace(rho_IM, dim_I, dim_M, keep_first=True)
    rho_M = partial_trace(rho_IM, dim_M, dim_I, keep_first=False)
    return (
        von_neumann_entropy(rho_I)
        + von_neumann_entropy(rho_M)
        - von_neumann_entropy(rho_IM)
    )


def relative_entropy(
    rho: np.ndarray, sigma: np.ndarray, eps: float = 1e-12,
) -> float:
    """DE = S(ρ ‖ σ) = tr(ρ ln ρ) − tr(ρ ln σ) — quantum relative entropy.

    The Báo cáo-nghiệm-chứng definition of the Dark Existence quantity:
    DE = S(ρ_MF ‖ σ_IF), the divergence between reality (ρ_MF) and the
    agent's belief/representation (σ_IF). Complementary to `mutual_information`
    (|OR|): |OR| measures how much internal & matter fields agree (overlap),
    DE measures how far the belief is from reality (the unknown / mismatch).

    In the 12-axiom framing DE is four-fold (space / time / IF / MF). This
    primitive computes the IF↔MF mismatch component on a shared Hilbert space
    (dim ρ = dim σ); the spatial/temporal faces are tracked separately
    (data-grounding |OR|, knowledge aging — ADR-0033) and combined in the
    grounding envelope, not inside this single quantum gauge.

    Non-negative (Klein's inequality), 0 iff ρ = σ. Computed via
    eigendecomposition; σ's eigenvalues are clipped to `eps` so a belief that
    assigns ~zero mass where reality has support yields a large-but-finite DE
    (a "confidently wrong" / giả-dương signal) instead of +∞.
    """
    if rho.shape != sigma.shape:
        raise ValueError(f"rho {rho.shape} and sigma {sigma.shape} must match")
    er = np.linalg.eigvalsh(rho)
    er = er[er > eps]
    tr_rho_ln_rho = float(np.sum(er * np.log(er)))          # = −S(ρ)
    es, Us = np.linalg.eigh(sigma)
    ln_sigma = (Us * np.log(np.clip(es, eps, None))) @ Us.conj().T
    tr_rho_ln_sigma = float(np.real(np.trace(rho @ ln_sigma)))
    return max(tr_rho_ln_rho - tr_rho_ln_sigma, 0.0)


def make_random_hermitian(
    dim: int, scale: float = 1.0, seed: Optional[int] = None,
) -> np.ndarray:
    """Generate a random Hermitian matrix of dimension `dim`.

    Useful for tests that need a valid Hamiltonian or coupling
    operator. Not used in production paths — exposed so tests can
    reuse the same construction the luận văn v10 code does."""
    if seed is not None:
        np.random.seed(seed)
    A = (np.random.randn(dim, dim) + 1j * np.random.randn(dim, dim)) * scale
    return (A + A.conj().T) / 2


def make_pure_product_state(dim_I: int, dim_M: int) -> np.ndarray:
    """|I_0⟩⟨I_0| ⊗ |M_0⟩⟨M_0| — the canonical initial state.

    Returns the (dim_I·dim_M) × (dim_I·dim_M) density operator where
    both subsystems are in their first basis vector. I(I:M) = 0 for
    this state (no entanglement) — interaction grows the metric from
    there per v11.
    """
    rho_I = np.zeros((dim_I, dim_I), dtype=complex)
    rho_I[0, 0] = 1.0
    rho_M = np.zeros((dim_M, dim_M), dtype=complex)
    rho_M[0, 0] = 1.0
    return np.kron(rho_I, rho_M)
