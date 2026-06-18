"""
P2-S21 D4 — TraceDistillerWorker tests.

Comprehensive suite per anh's "chuẩn chỉ + hiệu năng + phi chức năng"
template. Layout:

  1. Functional               — happy path: candidates → distill → mark success
  2. Idempotency              — re-running on same set is a NO-OP
  3. Confidence threshold     — low-confidence rows skipped
  4. Max retry cap            — failed-3x rows skipped
  5. PII mask                 — reasoning + subject masked before distill
  6. Tenant isolation         — enterprise_id filter passes through
  7. Determinism              — stats counts match for same input
  8. Error path               — distill failure marks retry_count, doesn't crash

Mocks asyncpg `db` (AsyncMock with fetch/fetchrow/execute) + LLM client
+ MemoryService. No DB needed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.reasoning.memory.service import MemoryService
from ai_orchestrator.reasoning.memory.types import MemoryType
from ai_orchestrator.reasoning.trace_distiller import (
    DEFAULT_MAX_RETRIES,
    TCubeTransformer,
    TraceDistillerWorker,
    WorkerStats,
)


T1 = UUID("11111111-1111-1111-1111-111111111111")
T2 = UUID("22222222-2222-2222-2222-222222222222")
NOW = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)


# ─── Fakes ──────────────────────────────────────────────────────────


class _FakeLLM:
    """Returns per-form-marker canned text. Tracks call count."""

    def __init__(self):
        self.call_count = 0

    async def complete(self, *, tenant_id, prompt, max_tokens, model=None):
        self.call_count += 1
        if "5 BƯỚC" in prompt:
            return "1. A\n2. B\n3. C\n4. D\n5. E"
        if "INSIGHT" in prompt:
            return "Khi X xảy ra, làm Y để đạt Z."
        return "- BẪY: foo | TRÁNH: bar"


class _RaisingLLM:
    async def complete(self, **_kw):
        raise RuntimeError("LLM gateway 503")


def _row(
    *, decision_id=None, enterprise_id=T1, decision_type="risk_assessment",
    subject="Churn risk for customer ABC", confidence=0.8, method="reasoning",
    alternatives=None, llm_provider="qwen",
    reasoning="Customer email is john@example.com, churn pattern detected...",
    created_at=NOW,
) -> dict:
    return {
        "decision_id":   decision_id or uuid4(),
        "enterprise_id": enterprise_id,
        "decision_type": decision_type,
        "subject":       subject,
        "confidence":    confidence,
        "method":        method,
        "alternatives":  alternatives,
        "llm_provider":  llm_provider,
        "reasoning":     reasoning,
        "created_at":    created_at,
    }


def _make_db(candidate_rows: list[dict], retry_counts: dict = None) -> AsyncMock:
    """Build an AsyncMock that returns the given rows on fetch + 0 retries
    on fetchrow (unless overridden)."""
    db = AsyncMock()
    # Row-shaped mock supporting __getitem__
    def _wrap(d: dict) -> MagicMock:
        r = MagicMock()
        r.__getitem__ = lambda _self, k: d[k]
        return r
    db.fetch.return_value = [_wrap(r) for r in candidate_rows]

    counts = retry_counts or {}
    async def _fetchrow(_sql, decision_id):
        rc = counts.get(decision_id)
        if rc is None:
            return None
        r = MagicMock()
        r.__getitem__ = lambda _self, k: rc if k == "retry_count" else None
        return r
    db.fetchrow = _fetchrow
    db.execute = AsyncMock(return_value=None)
    return db


def _make_worker(db, *, llm=None, threshold=0.6) -> TraceDistillerWorker:
    transformer = TCubeTransformer(llm or _FakeLLM(),
                                   distiller_model="qwen2.5:14b",
                                   distiller_version="2026-05-08")
    return TraceDistillerWorker(
        db=db,
        transformer=transformer,
        memory_service=MemoryService(),
        confidence_threshold=threshold,
    )


# ═════════════════════════════════════════════════════════════════════
# 1. Functional — happy path
# ═════════════════════════════════════════════════════════════════════


class TestHappyPath:

    @pytest.mark.asyncio
    async def test_distills_and_marks_success(self):
        rows = [_row(), _row(), _row()]
        db = _make_db(rows)
        worker = _make_worker(db)
        stats = await worker.run_once()
        assert stats.candidates_scanned == 3
        assert stats.distilled_ok == 3
        assert stats.distilled_failed == 0
        # 3 successes → 3 INSERT … ON CONFLICT calls
        assert db.execute.await_count == 3

    @pytest.mark.asyncio
    async def test_writes_three_records_per_distill_to_memory(self):
        rows = [_row()]
        db = _make_db(rows)
        worker = _make_worker(db)
        await worker.run_once()
        # Memory L4 PROCEDURAL now holds 3 records (struct/semantic/reflect)
        records = await worker._memory.l4.list_all(T1)
        procedural = [r for r in records if r.memory_type == MemoryType.PROCEDURAL]
        assert len(procedural) == 3
        forms = {r.metadata["tcube_form"] for r in procedural}
        assert forms == {"struct", "semantic", "reflect"}


# ═════════════════════════════════════════════════════════════════════
# 2. Idempotency
# ═════════════════════════════════════════════════════════════════════


class TestIdempotency:

    @pytest.mark.asyncio
    async def test_query_excludes_already_distilled(self):
        """The SQL LEFT JOIN + WHERE clause filters out rows whose
        cache row has error_message IS NULL. The mock's fetch returns
        whatever we hand it, so we verify the SQL shape itself."""
        db = _make_db([_row()])
        worker = _make_worker(db)
        await worker.run_once()
        # Last fetch call's SQL must reference distilled_decisions JOIN
        called_sql = db.fetch.await_args.args[0]
        assert "distilled_decisions" in called_sql
        assert "LEFT JOIN" in called_sql
        assert "c.decision_id IS NULL OR c.error_message IS NOT NULL" in called_sql

    @pytest.mark.asyncio
    async def test_insert_uses_on_conflict_do_update(self):
        """ON CONFLICT (decision_id) DO UPDATE — required for retry path
        + idempotent re-distillation under K-13."""
        rows = [_row()]
        db = _make_db(rows)
        worker = _make_worker(db)
        await worker.run_once()
        insert_sql = db.execute.await_args_list[0].args[0]
        assert "ON CONFLICT (decision_id)" in insert_sql
        assert "DO UPDATE" in insert_sql


# ═════════════════════════════════════════════════════════════════════
# 3. Confidence threshold
# ═════════════════════════════════════════════════════════════════════


class TestConfidenceThreshold:

    @pytest.mark.asyncio
    async def test_below_threshold_skipped(self):
        rows = [
            _row(confidence=0.4),
            _row(confidence=0.5),
            _row(confidence=0.7),
        ]
        db = _make_db(rows)
        worker = _make_worker(db, threshold=0.6)
        stats = await worker.run_once()
        assert stats.candidates_scanned == 3
        assert stats.skipped_low_conf == 2
        assert stats.distilled_ok == 1

    @pytest.mark.asyncio
    async def test_null_confidence_treated_as_zero(self):
        rows = [_row(confidence=None)]
        db = _make_db(rows)
        worker = _make_worker(db, threshold=0.6)
        stats = await worker.run_once()
        assert stats.skipped_low_conf == 1
        assert stats.distilled_ok == 0


# ═════════════════════════════════════════════════════════════════════
# 4. Max retry cap
# ═════════════════════════════════════════════════════════════════════


class TestMaxRetryCap:

    @pytest.mark.asyncio
    async def test_row_with_retries_above_cap_skipped(self):
        d_id = uuid4()
        rows = [_row(decision_id=d_id)]
        db = _make_db(rows, retry_counts={d_id: DEFAULT_MAX_RETRIES})
        worker = _make_worker(db)
        stats = await worker.run_once()
        assert stats.skipped_max_retry == 1
        assert stats.distilled_ok == 0

    @pytest.mark.asyncio
    async def test_row_at_max_minus_one_still_processed(self):
        d_id = uuid4()
        rows = [_row(decision_id=d_id)]
        db = _make_db(rows, retry_counts={d_id: DEFAULT_MAX_RETRIES - 1})
        worker = _make_worker(db)
        stats = await worker.run_once()
        # Below cap → still processed (this attempt = #DEFAULT_MAX_RETRIES)
        assert stats.skipped_max_retry == 0
        assert stats.distilled_ok == 1


# ═════════════════════════════════════════════════════════════════════
# 5. PII mask (K-5)
# ═════════════════════════════════════════════════════════════════════


class TestPIIMask:

    @pytest.mark.asyncio
    async def test_reasoning_email_masked_before_distill(self):
        llm = _FakeLLM()
        rows = [_row(reasoning="Email customer at john.doe@acme.com to recover")]
        db = _make_db(rows)
        worker = _make_worker(db, llm=llm)
        await worker.run_once()
        # Inspect what reached the transformer via the LLM prompts —
        # the redacted form must appear, the raw email must not.
        all_prompts = "\n".join(
            c["prompt"] if isinstance(c, dict) else ""
            for c in []  # _FakeLLM doesn't record prompts; verify via row_to_trace directly
        )
        # Direct call test: _row_to_trace must mask the email
        trace = TraceDistillerWorker._row_to_trace(
            MagicMock(**{"__getitem__": lambda _self, k: rows[0][k]})
        )
        assert "john.doe@acme.com" not in trace.raw_text
        assert "<EMAIL>" in trace.raw_text

    def test_phone_in_subject_masked(self):
        row = _row(subject="Call 0901234567 about churn", reasoning="x")
        r = MagicMock()
        r.__getitem__ = lambda _self, k: row[k]
        trace = TraceDistillerWorker._row_to_trace(r)
        assert "0901234567" not in trace.problem_context
        assert "<PHONE>" in trace.problem_context

    def test_alternatives_folded_into_context(self):
        row = _row(alternatives=[{"option": "do nothing"}, {"option": "discount"}])
        r = MagicMock()
        r.__getitem__ = lambda _self, k: row[k]
        trace = TraceDistillerWorker._row_to_trace(r)
        assert "alternatives" in trace.problem_context
        assert "discount" in trace.problem_context


# ═════════════════════════════════════════════════════════════════════
# 6. Tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    @pytest.mark.asyncio
    async def test_enterprise_id_filter_in_sql(self):
        rows = [_row()]
        db = _make_db(rows)
        worker = _make_worker(db)
        await worker.run_once(enterprise_id=T2)
        called_sql = db.fetch.await_args.args[0]
        called_params = db.fetch.await_args.args[1:]
        assert "d.enterprise_id =" in called_sql
        assert T2 in called_params

    @pytest.mark.asyncio
    async def test_no_enterprise_filter_when_none(self):
        rows = [_row()]
        db = _make_db(rows)
        worker = _make_worker(db)
        await worker.run_once()  # enterprise_id=None
        called_sql = db.fetch.await_args.args[0]
        # Without enterprise_id, the SQL should NOT include the filter
        assert "d.enterprise_id =" not in called_sql


# ═════════════════════════════════════════════════════════════════════
# 7. Determinism
# ═════════════════════════════════════════════════════════════════════


class TestDeterminism:

    @pytest.mark.asyncio
    async def test_same_input_same_stats_across_two_runs(self):
        rows = [_row(confidence=0.8), _row(confidence=0.3), _row(confidence=0.9)]
        db1 = _make_db(rows)
        db2 = _make_db(rows)
        w1 = _make_worker(db1)
        w2 = _make_worker(db2)
        s1 = await w1.run_once()
        s2 = await w2.run_once()
        assert s1 == s2  # WorkerStats is a dataclass with eq


# ═════════════════════════════════════════════════════════════════════
# 8. Error path
# ═════════════════════════════════════════════════════════════════════


class TestErrorPath:

    @pytest.mark.asyncio
    async def test_llm_failure_does_not_crash_batch(self):
        """One row fails distill → marked failure, batch continues."""
        rows = [_row(), _row(), _row()]
        db = _make_db(rows)
        worker = _make_worker(db, llm=_RaisingLLM())
        stats = await worker.run_once()
        assert stats.distilled_failed == 3
        assert stats.distilled_ok == 0
        # Each failure does ONE execute (insert with error_message)
        assert db.execute.await_count == 3
        # The insert SQL must record error_message
        any_insert_with_error = any(
            "error_message" in call.args[0] and "$5" in call.args[0]
            for call in db.execute.await_args_list
        )
        assert any_insert_with_error

    @pytest.mark.asyncio
    async def test_partial_batch_some_ok_some_fail(self):
        """If LLM is flaky (succeeds for some calls, fails for others),
        the worker tracks both buckets correctly."""

        class _FlakyLLM:
            def __init__(self):
                self.n = 0

            async def complete(self, **_kw):
                self.n += 1
                # Fail every 4th call (so 1 trace's 3 forms — fail on
                # call #4 = first form of trace #2)
                if self.n == 4:
                    raise RuntimeError("flaky")
                return "ok"

        rows = [_row(), _row()]
        db = _make_db(rows)
        worker = _make_worker(db, llm=_FlakyLLM())
        stats = await worker.run_once()
        # 1 trace OK + 1 trace failed
        assert stats.distilled_ok + stats.distilled_failed == 2
        assert stats.distilled_failed >= 1
