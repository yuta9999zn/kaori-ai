"""
Phase 2.5 — compare_to_template tests.

8-section template:
  1. Clause extraction — TITLE-based grouping, body accumulation,
     edge cases (no title, only table, chrome skipped)
  2. Cosine similarity — happy / dim mismatch / zero vectors
  3. Risk keyword bump (low→medium→high, no-op when no match)
  4. Risk score aggregation (missing=high, added=medium, mix)
  5. Embedding pipeline (mocked httpx)
  6. End-to-end compare_to_template — match / modified / missing /
     added (mocked embeddings + LLM)
  7. LLM diff failure fallback (caller never sees raise)
  8. Empty / single-side input + summary counts
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_orchestrator.data_plane_shim import Block, BlockType
from ai_orchestrator.reasoning.template_comparator import (
    DEFAULT_RISK_KEYWORDS,
    Clause,
    ClauseMatch,
    CompareInput,
    CompareOutput,
    _aggregate_risk_score,
    _bump_risk_for_keywords,
    _cosine,
    _llm_diff,
    compare_to_template,
    extract_clauses,
)


ENT = "11111111-1111-1111-1111-111111111111"


# ─── Helpers ────────────────────────────────────────────────────────


def _b(t: BlockType, page: int, text: str, char_start: int = 0) -> Block:
    return Block(type=t, page_idx=page, char_start=char_start,
                  char_end=char_start + len(text), text=text)


def _mock_embed_response(vector: list[float]) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"vector": vector, "dim": len(vector)})
    return resp


def _mock_ctx(post_returns):
    """Build an async-context-manager mock around httpx.AsyncClient.post.
    `post_returns` may be a list (one response per call) or a single
    response (reused)."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=ctx)
    ctx.__aexit__ = AsyncMock(return_value=False)
    if isinstance(post_returns, list):
        ctx.post = AsyncMock(side_effect=post_returns)
    else:
        ctx.post = AsyncMock(return_value=post_returns)
    return ctx


# ═════════════════════════════════════════════════════════════════════
# 1. Clause extraction
# ═════════════════════════════════════════════════════════════════════


class TestExtractClauses:

    def test_title_starts_new_clause(self):
        blocks = [
            _b(BlockType.TITLE, 0, "Điều 1. Định nghĩa"),
            _b(BlockType.TEXT,  0, "Bên A là công ty X."),
            _b(BlockType.TEXT,  0, "Bên B là công ty Y."),
            _b(BlockType.TITLE, 1, "Điều 2. Nghĩa vụ"),
            _b(BlockType.TEXT,  1, "Bên A phải thanh toán."),
        ]
        clauses = extract_clauses(blocks)
        assert len(clauses) == 2
        assert clauses[0].title == "Điều 1. Định nghĩa"
        assert "Bên A là" in clauses[0].text
        assert "Bên B là" in clauses[0].text
        assert clauses[1].title == "Điều 2. Nghĩa vụ"

    def test_no_titles_emits_one_clause(self):
        blocks = [
            _b(BlockType.TEXT, 0, "Paragraph one."),
            _b(BlockType.TEXT, 0, "Paragraph two."),
        ]
        clauses = extract_clauses(blocks)
        assert len(clauses) == 1
        assert clauses[0].title == ""
        assert "Paragraph one" in clauses[0].text
        assert "Paragraph two" in clauses[0].text

    def test_chrome_skipped(self):
        blocks = [
            _b(BlockType.HEADER,      0, "Confidential"),
            _b(BlockType.TITLE,       0, "Điều 1"),
            _b(BlockType.TEXT,        0, "body"),
            _b(BlockType.FOOTER,      0, "Page 1"),
            _b(BlockType.PAGE_NUMBER, 0, "1"),
        ]
        clauses = extract_clauses(blocks)
        assert len(clauses) == 1
        assert "Confidential" not in clauses[0].text
        assert "Page 1" not in clauses[0].text

    def test_table_breaks_clause(self):
        blocks = [
            _b(BlockType.TITLE, 0, "Điều 1"),
            _b(BlockType.TEXT,  0, "Intro paragraph."),
            _b(BlockType.TABLE, 0, "| A | B |"),
            _b(BlockType.TEXT,  0, "Post-table paragraph."),
        ]
        clauses = extract_clauses(blocks)
        # TITLE 'Điều 1' clause (with intro), then TABLE break, then a
        # title-less clause from post-table text.
        assert len(clauses) == 2
        assert clauses[0].title == "Điều 1"
        assert "Intro paragraph" in clauses[0].text
        assert clauses[1].title == ""
        assert "Post-table" in clauses[1].text

    def test_empty_input(self):
        assert extract_clauses([]) == []

    def test_clause_body_capped_at_3kb(self):
        big = "x" * 5000
        blocks = [_b(BlockType.TITLE, 0, "T"), _b(BlockType.TEXT, 0, big)]
        clauses = extract_clauses(blocks)
        assert len(clauses[0].text) <= 3000

    def test_source_block_indices_tracked(self):
        blocks = [
            _b(BlockType.TITLE, 0, "T1"),
            _b(BlockType.TEXT,  0, "body1"),
            _b(BlockType.TEXT,  0, "body2"),
        ]
        clauses = extract_clauses(blocks)
        # Indices 0 (title) + 1 + 2 (bodies)
        assert clauses[0].source_block_indices == (0, 1, 2)


# ═════════════════════════════════════════════════════════════════════
# 2. Cosine
# ═════════════════════════════════════════════════════════════════════


class TestCosine:

    def test_identical_vectors_one(self):
        v = [0.1, 0.2, 0.3]
        assert abs(_cosine(v, v) - 1.0) < 1e-9

    def test_orthogonal_zero(self):
        assert abs(_cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9

    def test_opposite_minus_one(self):
        assert abs(_cosine([1.0, 0.0], [-1.0, 0.0]) - (-1.0)) < 1e-9

    def test_dim_mismatch_returns_zero(self):
        assert _cosine([1, 2, 3], [1, 2]) == 0.0

    def test_empty_returns_zero(self):
        assert _cosine([], []) == 0.0
        assert _cosine([], [1, 2]) == 0.0

    def test_zero_magnitude_safe(self):
        assert _cosine([0, 0, 0], [1, 1, 1]) == 0.0


# ═════════════════════════════════════════════════════════════════════
# 3. Risk keyword bump
# ═════════════════════════════════════════════════════════════════════


class TestRiskKeywordBump:

    def _clause(self, text: str) -> Clause:
        return Clause(title="", text=text, source_block_indices=(),
                       page_idx=0)

    def test_vn_keyword_bumps_low_to_medium(self):
        c = self._clause("Bên A có trách nhiệm bồi thường.")
        out = _bump_risk_for_keywords(c, "low", DEFAULT_RISK_KEYWORDS)
        assert out == "medium"

    def test_vn_keyword_bumps_medium_to_high(self):
        c = self._clause("Bồi thường tối đa 100M VND.")
        out = _bump_risk_for_keywords(c, "medium", DEFAULT_RISK_KEYWORDS)
        assert out == "high"

    def test_en_keyword_bumps(self):
        c = self._clause("Liability is capped at $1M.")
        out = _bump_risk_for_keywords(c, "low", DEFAULT_RISK_KEYWORDS)
        assert out == "medium"

    def test_no_keyword_no_bump(self):
        c = self._clause("Phương thức thanh toán: chuyển khoản.")
        assert _bump_risk_for_keywords(c, "low", DEFAULT_RISK_KEYWORDS) == "low"

    def test_high_stays_high(self):
        c = self._clause("Trọng tài tại Singapore.")
        assert _bump_risk_for_keywords(c, "high", DEFAULT_RISK_KEYWORDS) == "high"

    def test_none_clause_passthrough(self):
        assert _bump_risk_for_keywords(None, "low", DEFAULT_RISK_KEYWORDS) == "low"

    def test_empty_keywords_passthrough(self):
        c = self._clause("trách nhiệm")
        assert _bump_risk_for_keywords(c, "low", []) == "low"


# ═════════════════════════════════════════════════════════════════════
# 4. Risk score aggregation
# ═════════════════════════════════════════════════════════════════════


class TestRiskAggregation:

    def _mk(self, status: str, risk: str = "low") -> ClauseMatch:
        return ClauseMatch(template_clause_idx=0,
                            candidate_clause_idx=0,
                            status=status,
                            similarity=0.8 if status != "missing" else 0.0,
                            risk_level=risk, explanation="")

    def test_empty(self):
        assert _aggregate_risk_score([]) == 0.0

    def test_all_low_match_low_score(self):
        score = _aggregate_risk_score([self._mk("match", "low")] * 5)
        assert 0.0 < score < 0.2

    def test_all_high_match_max_score(self):
        score = _aggregate_risk_score([self._mk("match", "high")] * 3)
        assert score == 1.0

    def test_missing_counts_high(self):
        score = _aggregate_risk_score([self._mk("missing")] * 2)
        assert score == 1.0       # 2 missing × high weight, max possible same

    def test_added_counts_medium(self):
        score = _aggregate_risk_score([self._mk("added")] * 2)
        assert abs(score - 0.5) < 1e-9

    def test_mixed(self):
        ms = [self._mk("match", "low"),     # 0.1
              self._mk("missing"),           # 1.0
              self._mk("modified", "medium")]  # 0.5
        # Sum = 1.6, max = 3.0 → ~0.533
        score = _aggregate_risk_score(ms)
        assert 0.5 < score < 0.6


# ═════════════════════════════════════════════════════════════════════
# 5. Embedding pipeline (mocked httpx)
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEmbedClauses:

    async def test_each_clause_gets_one_embed_call(self):
        from ai_orchestrator.reasoning.template_comparator import _embed_clauses

        clauses = [
            Clause(title="T1", text="b1", source_block_indices=(), page_idx=0),
            Clause(title="T2", text="b2", source_block_indices=(), page_idx=0),
        ]
        ctx = _mock_ctx([
            _mock_embed_response([0.1, 0.2]),
            _mock_embed_response([0.3, 0.4]),
        ])
        with patch("httpx.AsyncClient", return_value=ctx):
            vecs = await _embed_clauses(clauses, ENT, "http://fake")
        assert vecs == [[0.1, 0.2], [0.3, 0.4]]
        assert ctx.post.call_count == 2

    async def test_empty_clause_returns_empty_vector_without_call(self):
        from ai_orchestrator.reasoning.template_comparator import _embed_clauses

        clauses = [
            Clause(title="", text="", source_block_indices=(), page_idx=0),
            Clause(title="X", text="real", source_block_indices=(), page_idx=0),
        ]
        ctx = _mock_ctx([_mock_embed_response([0.1, 0.2])])
        with patch("httpx.AsyncClient", return_value=ctx):
            vecs = await _embed_clauses(clauses, ENT, "http://fake")
        # First empty → [], second got the call
        assert vecs[0] == []
        assert vecs[1] == [0.1, 0.2]
        assert ctx.post.call_count == 1

    async def test_network_error_returns_empty_vector(self):
        from ai_orchestrator.reasoning.template_comparator import _embed_clauses
        import httpx

        clauses = [Clause(title="X", text="y", source_block_indices=(), page_idx=0)]
        ctx = _mock_ctx([])
        ctx.post = AsyncMock(side_effect=httpx.ConnectError("down"))
        with patch("httpx.AsyncClient", return_value=ctx):
            vecs = await _embed_clauses(clauses, ENT, "http://fake")
        assert vecs == [[]]


# ═════════════════════════════════════════════════════════════════════
# 6. End-to-end compare_to_template
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestCompareEnd2End:

    async def _run(self, *, template_blocks, candidate_blocks,
                    template_vecs, candidate_vecs, llm_diffs,
                    threshold: float = 0.65):
        """Helper — drives compare_to_template with mocked embed + LLM."""
        # Stage embed responses in order: template first then candidate
        embed_responses = [_mock_embed_response(v) for v in template_vecs] + \
                            [_mock_embed_response(v) for v in candidate_vecs]
        ctx = _mock_ctx(embed_responses)

        # Stage LLM diff results
        llm_iter = iter(llm_diffs)
        async def fake_diff(*a, **kw):
            return next(llm_iter)

        with patch("httpx.AsyncClient", return_value=ctx), \
              patch("ai_orchestrator.reasoning.template_comparator.llm_router",
                    complete_with_schema=AsyncMock(side_effect=fake_diff)):
            return await compare_to_template(CompareInput(
                template_blocks=template_blocks,
                candidate_blocks=candidate_blocks,
                enterprise_id=ENT,
                similarity_threshold=threshold,
                llm_gateway_url="http://fake",
            ))

    async def test_full_match(self):
        tpl = [_b(BlockType.TITLE, 0, "Điều 1"), _b(BlockType.TEXT, 0, "A")]
        cand = [_b(BlockType.TITLE, 0, "Điều 1"), _b(BlockType.TEXT, 0, "A")]
        # Identical embeddings → cosine = 1
        out = await self._run(
            template_blocks=tpl, candidate_blocks=cand,
            template_vecs=[[1.0, 0.0]],
            candidate_vecs=[[1.0, 0.0]],
            llm_diffs=[{"status": "match", "risk_level": "low",
                          "explanation": "Giống hệt."}],
        )
        assert out.template_clause_count == 1
        assert out.candidate_clause_count == 1
        assert out.summary["match"] == 1
        assert out.summary["modified"] == 0
        assert out.summary["missing"] == 0
        assert out.summary["added"] == 0
        assert out.matches[0].similarity == pytest.approx(1.0)
        # Low risk on match → overall ≤ 0.2
        assert out.overall_risk_score < 0.2

    async def test_modified_clause(self):
        tpl = [_b(BlockType.TITLE, 0, "Điều 1"),
                _b(BlockType.TEXT, 0, "Giới hạn trách nhiệm 100M.")]
        cand = [_b(BlockType.TITLE, 0, "Điều 1"),
                 _b(BlockType.TEXT, 0, "Giới hạn trách nhiệm 50M.")]
        out = await self._run(
            template_blocks=tpl, candidate_blocks=cand,
            template_vecs=[[1.0, 0.0]],
            candidate_vecs=[[0.95, 0.31]],   # high sim, above threshold
            llm_diffs=[{"status": "modified", "risk_level": "high",
                          "explanation": "Giảm giới hạn bồi thường."}],
        )
        assert out.summary["modified"] == 1
        # 'trách nhiệm' keyword bumps high → high (stays)
        assert out.matches[0].risk_level == "high"

    async def test_added_clause(self):
        """Candidate clause has no template peer above threshold."""
        tpl = [_b(BlockType.TITLE, 0, "Điều 1"),
                _b(BlockType.TEXT, 0, "Mục A")]
        cand = [_b(BlockType.TITLE, 0, "Điều 1"),
                 _b(BlockType.TEXT, 0, "Mục A"),
                 _b(BlockType.TITLE, 0, "Điều 99"),
                 _b(BlockType.TEXT, 0, "Mục lạ")]
        out = await self._run(
            template_blocks=tpl, candidate_blocks=cand,
            template_vecs=[[1.0, 0.0]],
            candidate_vecs=[[1.0, 0.0], [0.0, 1.0]],  # 2nd is orthogonal
            llm_diffs=[{"status": "match", "risk_level": "low",
                          "explanation": "ok"}],
        )
        assert out.summary["match"] == 1
        assert out.summary["added"] == 1
        added = [m for m in out.matches if m.status == "added"][0]
        assert added.candidate_clause_idx == 1
        assert added.template_clause_idx is None

    async def test_missing_clause(self):
        """Template has 2 clauses; candidate only has 1 matching."""
        tpl = [_b(BlockType.TITLE, 0, "Điều 1"),
                _b(BlockType.TEXT, 0, "A"),
                _b(BlockType.TITLE, 0, "Điều 2"),
                _b(BlockType.TEXT, 0, "B")]
        cand = [_b(BlockType.TITLE, 0, "Điều 1"),
                 _b(BlockType.TEXT, 0, "A")]
        out = await self._run(
            template_blocks=tpl, candidate_blocks=cand,
            template_vecs=[[1.0, 0.0], [0.0, 1.0]],
            candidate_vecs=[[1.0, 0.0]],
            llm_diffs=[{"status": "match", "risk_level": "low",
                          "explanation": "ok"}],
        )
        assert out.summary["match"] == 1
        assert out.summary["missing"] == 1
        missing = [m for m in out.matches if m.status == "missing"][0]
        assert missing.template_clause_idx == 1
        assert missing.candidate_clause_idx is None
        # Missing → high risk
        assert missing.risk_level == "high"


# ═════════════════════════════════════════════════════════════════════
# 7. LLM diff failure fallback
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestLlmDiffFailure:

    async def test_llm_raises_falls_back_to_modified_medium(self):
        tpl = [_b(BlockType.TITLE, 0, "T"), _b(BlockType.TEXT, 0, "A")]
        cand = [_b(BlockType.TITLE, 0, "T"), _b(BlockType.TEXT, 0, "A")]

        embed_responses = [_mock_embed_response([1.0, 0.0])] * 2
        ctx = _mock_ctx(embed_responses)

        async def boom(*a, **kw):
            raise RuntimeError("LLM gateway down")

        with patch("httpx.AsyncClient", return_value=ctx), \
              patch("ai_orchestrator.reasoning.template_comparator.llm_router",
                    complete_with_schema=AsyncMock(side_effect=boom)):
            out = await compare_to_template(CompareInput(
                template_blocks=tpl, candidate_blocks=cand,
                enterprise_id=ENT, llm_gateway_url="http://fake",
            ))

        # 1 candidate → 1 match emitted; fallback status='modified'
        assert len(out.matches) == 1
        assert out.matches[0].status == "modified"
        assert out.matches[0].risk_level == "medium"
        assert "LLM diff lỗi" in out.matches[0].explanation


# ═════════════════════════════════════════════════════════════════════
# 8. Empty + single-side input
# ═════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
class TestEdgeCases:

    async def test_empty_both_sides(self):
        out = await compare_to_template(CompareInput(
            template_blocks=[], candidate_blocks=[],
            enterprise_id=ENT, llm_gateway_url="http://fake",
        ))
        assert out.matches == []
        assert out.template_clause_count == 0
        assert out.candidate_clause_count == 0
        assert out.overall_risk_score == 0.0

    async def test_template_only_all_missing(self):
        tpl = [_b(BlockType.TITLE, 0, "T1"),
                _b(BlockType.TEXT, 0, "A"),
                _b(BlockType.TITLE, 0, "T2"),
                _b(BlockType.TEXT, 0, "B")]
        ctx = _mock_ctx([
            _mock_embed_response([1.0, 0.0]),
            _mock_embed_response([0.0, 1.0]),
        ])
        with patch("httpx.AsyncClient", return_value=ctx):
            out = await compare_to_template(CompareInput(
                template_blocks=tpl, candidate_blocks=[],
                enterprise_id=ENT, llm_gateway_url="http://fake",
            ))
        assert out.summary["missing"] == 2
        assert out.summary.get("match", 0) == 0
        assert out.overall_risk_score == 1.0

    async def test_candidate_only_all_added(self):
        cand = [_b(BlockType.TITLE, 0, "T1"), _b(BlockType.TEXT, 0, "A")]
        ctx = _mock_ctx([_mock_embed_response([1.0, 0.0])])
        with patch("httpx.AsyncClient", return_value=ctx):
            out = await compare_to_template(CompareInput(
                template_blocks=[], candidate_blocks=cand,
                enterprise_id=ENT, llm_gateway_url="http://fake",
            ))
        assert out.summary["added"] == 1
        assert out.summary.get("missing", 0) == 0

    async def test_summary_keys_always_present(self):
        """All 4 status keys initialised to 0 — caller never KeyErrors
        when rendering the summary card."""
        out = await compare_to_template(CompareInput(
            template_blocks=[], candidate_blocks=[],
            enterprise_id=ENT, llm_gateway_url="http://fake",
        ))
        # Empty input early-returns with summary={}; non-empty paths
        # initialise all four — em pin that explicitly here.
        cand = [_b(BlockType.TEXT, 0, "x")]
        ctx = _mock_ctx([_mock_embed_response([1.0, 0.0])])
        with patch("httpx.AsyncClient", return_value=ctx):
            out2 = await compare_to_template(CompareInput(
                template_blocks=[], candidate_blocks=cand,
                enterprise_id=ENT, llm_gateway_url="http://fake",
            ))
        for k in ("match", "modified", "missing", "added"):
            assert k in out2.summary
