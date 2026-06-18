"""Tests for the v10/v11 Hilbert-space measurement primitives.

Three families:
  1. von_neumann_entropy correctness (pure state, maximally mixed, mid).
  2. partial_trace + mutual_information identities.
  3. The v11 finding: I(I:M) grows under interaction.

Pure numpy, no fixtures, no LLM, no Postgres.
"""
from __future__ import annotations

import numpy as np
import pytest

from ai_orchestrator.reasoning.cdfl.hilbert_metric import (
    make_pure_product_state,
    make_random_hermitian,
    mutual_information,
    partial_trace,
    relative_entropy,
    von_neumann_entropy,
)


# ─── von Neumann entropy ────────────────────────────────────────────


class TestVonNeumannEntropy:

    def test_pure_state_has_zero_entropy(self):
        # |0⟩⟨0| is pure → S = 0
        rho = np.array([[1, 0], [0, 0]], dtype=complex)
        assert von_neumann_entropy(rho) == pytest.approx(0.0, abs=1e-9)

    def test_maximally_mixed_state_has_max_entropy(self):
        # I/d → S = log d
        d = 4
        rho = np.eye(d, dtype=complex) / d
        assert von_neumann_entropy(rho) == pytest.approx(np.log(d), abs=1e-9)

    def test_intermediate_mixedness(self):
        # diag(0.5, 0.5) → S = log 2
        rho = np.array([[0.5, 0], [0, 0.5]], dtype=complex)
        assert von_neumann_entropy(rho) == pytest.approx(np.log(2), abs=1e-9)

    def test_nonnegativity(self):
        # Random valid density operator must give S ≥ 0
        np.random.seed(42)
        for d in (2, 4, 8):
            H = make_random_hermitian(d, seed=d)
            evals, evecs = np.linalg.eigh(H @ H.conj().T)   # positive
            rho = evecs @ np.diag(evals / evals.sum()) @ evecs.conj().T
            assert von_neumann_entropy(rho) >= -1e-9


# ─── partial_trace ──────────────────────────────────────────────────


class TestPartialTrace:

    def test_product_state_partial_trace(self):
        # ρ = ρ_A ⊗ ρ_B → tr_B(ρ) = ρ_A
        rho_A = np.array([[0.7, 0.3], [0.3, 0.3]], dtype=complex)
        rho_B = np.array([[0.5, 0.1], [0.1, 0.5]], dtype=complex)
        rho   = np.kron(rho_A, rho_B)
        out   = partial_trace(rho, dim_keep=2, dim_trace=2, keep_first=True)
        np.testing.assert_allclose(out, rho_A, atol=1e-9)

    def test_partial_trace_other_side(self):
        rho_A = np.array([[0.7, 0.3], [0.3, 0.3]], dtype=complex)
        rho_B = np.array([[0.5, 0.1], [0.1, 0.5]], dtype=complex)
        rho   = np.kron(rho_A, rho_B)
        out   = partial_trace(rho, dim_keep=2, dim_trace=2, keep_first=False)
        np.testing.assert_allclose(out, rho_B, atol=1e-9)

    def test_partial_trace_preserves_trace(self):
        rho = make_pure_product_state(3, 4)
        out = partial_trace(rho, dim_keep=3, dim_trace=4, keep_first=True)
        assert np.trace(out).real == pytest.approx(1.0, abs=1e-9)


# ─── mutual_information ─────────────────────────────────────────────


class TestMutualInformation:

    def test_pure_product_state_has_zero_mutual_info(self):
        rho = make_pure_product_state(3, 3)
        assert mutual_information(rho, 3, 3) == pytest.approx(0.0, abs=1e-9)

    def test_product_state_has_zero_mutual_info(self):
        # I(I:M) = 0 when ρ = ρ_I ⊗ ρ_M (no entanglement, no correlation)
        rho_I = np.array([[0.6, 0], [0, 0.4]], dtype=complex)
        rho_M = np.array([[0.3, 0], [0, 0.7]], dtype=complex)
        rho   = np.kron(rho_I, rho_M)
        assert mutual_information(rho, 2, 2) == pytest.approx(0.0, abs=1e-9)

    def test_maximally_entangled_state_saturates_bound(self):
        # |Φ+⟩ = (|00⟩ + |11⟩)/√2 → ρ = |Φ+⟩⟨Φ+|, I(I:M) = 2 log 2
        psi = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
        rho = np.outer(psi, psi.conj())
        # I(I:M) = S(ρ_I) + S(ρ_M) - 0 = log 2 + log 2 = 2 log 2
        assert mutual_information(rho, 2, 2) == pytest.approx(
            2 * np.log(2), abs=1e-9
        )

    def test_mutual_information_nonnegative(self):
        np.random.seed(7)
        for _ in range(5):
            H = make_random_hermitian(6)
            evals, evecs = np.linalg.eigh(H @ H.conj().T)
            rho = evecs @ np.diag(evals / evals.sum()) @ evecs.conj().T
            assert mutual_information(rho, 2, 3) >= -1e-9


# ─── v11 finding — I(I:M) grows under interaction ───────────────────


class TestV11BridgeFinding:
    """v11 result: I(I:M) grows monotonically (not strictly — small
    oscillations are tolerated) during interaction with environment.

    We don't reproduce the full Lindblad evolution — that's research-
    level code with scipy.linalg.expm. We just verify the metric
    BEHAVES correctly: starts at 0 from a product state, can be
    increased by entangling unitary."""

    def test_iim_increases_after_entangling_unitary(self):
        rho = make_pure_product_state(2, 2)
        assert mutual_information(rho, 2, 2) == pytest.approx(0.0, abs=1e-9)

        # CNOT in computational basis |00>, |01>, |10>, |11> with the
        # first qubit as control. |ab> → |a, a⊕b>.
        cnot = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 0, 1],
            [0, 0, 1, 0],
        ], dtype=complex)
        # First apply Hadamard on subsystem A to create superposition
        H = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
        H_full = np.kron(H, np.eye(2))
        rho2 = H_full @ rho @ H_full.conj().T
        rho3 = cnot @ rho2 @ cnot.conj().T

        # After H ⊗ I → CNOT we expect a Bell pair → I(I:M) = 2 log 2
        info = mutual_information(rho3, 2, 2)
        assert info == pytest.approx(2 * np.log(2), abs=1e-9)
        assert info > 0   # explicit assertion: interaction grew the metric

    def test_iim_bounded_by_subsystem_entropy(self):
        """I(I:M) ≤ 2 min(S(ρ_I), S(ρ_M)) ≤ 2 log(min(dim_I, dim_M))"""
        psi = np.array([1, 0, 0, 1], dtype=complex) / np.sqrt(2)
        rho = np.outer(psi, psi.conj())
        info = mutual_information(rho, 2, 2)
        # min(log 2, log 2) = log 2; I(I:M) ≤ 2 log 2
        assert info <= 2 * np.log(2) + 1e-9


# ─── relative_entropy (DE = S(ρ‖σ)) ─────────────────────────────────


class TestRelativeEntropy:
    """DE = S(ρ_MF ‖ σ_IF): 0 iff belief == reality, else > 0, finite even
    when belief assigns ~0 mass where reality has support (giả-dương)."""

    def test_identical_states_zero(self):
        rho = np.array([[0.6, 0], [0, 0.4]], dtype=complex)
        assert relative_entropy(rho, rho) == pytest.approx(0.0, abs=1e-9)

    def test_positive_when_mismatched(self):
        rho = np.array([[0.7, 0], [0, 0.3]], dtype=complex)   # reality
        sigma = np.array([[0.4, 0], [0, 0.6]], dtype=complex)  # belief
        assert relative_entropy(rho, sigma) > 0.0

    def test_matches_classical_kl_for_diagonal(self):
        # Diagonal ρ,σ → S(ρ‖σ) = Σ p_i (ln p_i − ln q_i) (classical KL)
        p = np.array([0.7, 0.3]); q = np.array([0.4, 0.6])
        rho = np.diag(p).astype(complex); sigma = np.diag(q).astype(complex)
        kl = float(np.sum(p * (np.log(p) - np.log(q))))
        assert relative_entropy(rho, sigma) == pytest.approx(kl, abs=1e-9)

    def test_confidently_wrong_is_large_but_finite(self):
        # Belief ~0 where reality has mass → big but finite DE (not +inf)
        rho = np.array([[0.5, 0], [0, 0.5]], dtype=complex)
        sigma = np.array([[1.0, 0], [0, 0.0]], dtype=complex)
        de = relative_entropy(rho, sigma)
        assert np.isfinite(de) and de > 5.0

    def test_shape_mismatch_raises(self):
        with pytest.raises(ValueError):
            relative_entropy(np.eye(2, dtype=complex), np.eye(3, dtype=complex) / 3)


# ─── Reproducibility / fixture helpers ──────────────────────────────


class TestMakeRandomHermitian:
    def test_hermitian(self):
        H = make_random_hermitian(5, seed=1)
        np.testing.assert_allclose(H, H.conj().T, atol=1e-12)

    def test_seed_reproducible(self):
        a = make_random_hermitian(3, seed=42)
        b = make_random_hermitian(3, seed=42)
        np.testing.assert_array_equal(a, b)
