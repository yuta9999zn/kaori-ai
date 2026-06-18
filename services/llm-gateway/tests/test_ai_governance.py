"""
Tests for Phase 2.7 P3 — services/llm-gateway/ai_governance.py.

The gateway uses its own pool (system-wide; no acquire_for_tenant
helper) and sets the `app.enterprise_id` GUC LOCAL=true inside the
transaction so the RLS policy on ai_decision_audit lets the INSERT
through.

Best-effort write: a DB failure is logged but never raises.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from llm_gateway import ai_governance  # noqa: E402  registered in conftest.py


# ─── Hash helpers ─────────────────────────────────────────────────────


class TestHashPrompt:
    def test_empty_prompt_returns_sha_of_empty(self):
        empty = ai_governance.hash_prompt("")
        assert isinstance(empty, str)
        assert len(empty) == 64  # SHA-256 hex
        # Determinism
        assert ai_governance.hash_prompt("") == empty

    def test_deterministic_for_same_input(self):
        a = ai_governance.hash_prompt("hello world")
        b = ai_governance.hash_prompt("hello world")
        assert a == b

    def test_different_inputs_yield_different_hashes(self):
        a = ai_governance.hash_prompt("hello world")
        b = ai_governance.hash_prompt("hello world!")
        assert a != b

    def test_truncates_at_1_MB(self):
        big = "x" * 2_000_000
        h = ai_governance.hash_prompt(big)
        # Should equal hash of the 1 MB prefix
        assert h == ai_governance.hash_prompt("x" * 1_000_000)

    def test_hash_output_alias(self):
        assert ai_governance.hash_output("ok") == ai_governance.hash_prompt("ok")
        assert ai_governance.hash_output("") == ai_governance.hash_prompt("")
        assert ai_governance.hash_output(None) == ai_governance.hash_prompt("")  # type: ignore[arg-type]


# ─── Pool / connection scaffold ────────────────────────────────────────


def _mock_pool_returning(audit_id: UUID):
    """Build a pool whose acquire() + transaction() context yield a conn
    that records every conn.execute call and returns audit_id from
    fetchrow.
    """
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetchrow = AsyncMock(return_value={"audit_id": audit_id})

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool, conn


# ─── Happy path ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_inserts_row_and_returns_audit_id():
    audit_id = uuid4()
    pool, conn = _mock_pool_returning(audit_id)

    out = await ai_governance.record_ai_call(
        pool,
        enterprise_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        task_kind="schema_mapping",
        model_version="qwen2.5:14b",
        model_provider="ollama",
        prompt="hello world",
        output="ok",
        consent_external=False,
        pii_redacted=False,
        latency_ms=210,
        token_input_count=11,
        token_output_count=2,
    )

    assert out == audit_id

    # First execute call sets the app.enterprise_id GUC.
    set_config_call = conn.execute.await_args_list[0]
    assert "set_config" in set_config_call.args[0]
    assert set_config_call.args[1] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    # The INSERT goes through fetchrow.
    conn.fetchrow.assert_awaited_once()
    insert_sql = conn.fetchrow.await_args.args[0]
    assert "INSERT INTO ai_decision_audit" in insert_sql

    # Positional args follow the INSERT order: args[0]=SQL,
    # args[1]=enterprise_id ($1), then $2..$21 in INSERT column order:
    # request_id, decision_id, run_id, node_id, task_kind, model_version,
    # model_provider, prompt_hash, prompt_size_bytes, context_refs(json),
    # confidence, output_hash, output_size_bytes, output_validated,
    # consent_external, pii_redacted, latency_ms, tok_in, tok_out, cost.
    args = conn.fetchrow.await_args.args
    assert isinstance(args[1], UUID)
    assert args[6] == "schema_mapping"          # task_kind   ($6)
    assert args[7] == "qwen2.5:14b"              # model_version ($7)
    assert args[8] == "ollama"                   # model_provider ($8)
    assert len(args[9]) == 64                    # prompt_hash hex ($9)
    assert args[10] == len("hello world")        # prompt_size_bytes ($10)
    assert args[16] is False                     # consent_external ($16)
    assert args[17] is False                     # pii_redacted ($17)
    assert args[18] == 210                       # latency_ms ($18)


@pytest.mark.asyncio
async def test_optional_uuid_fields_pass_through():
    audit_id = uuid4()
    run_id = uuid4()
    node_id = uuid4()
    pool, conn = _mock_pool_returning(audit_id)

    await ai_governance.record_ai_call(
        pool,
        enterprise_id=uuid4(),
        task_kind="x",
        model_version="qwen2.5:14b",
        model_provider="ollama",
        prompt="hi",
        run_id=run_id,
        node_id=node_id,
    )

    args = conn.fetchrow.await_args.args
    assert args[4] == run_id     # $4 run_id
    assert args[5] == node_id    # $5 node_id


# ─── Skip / fail-soft ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_returns_none_when_enterprise_id_is_empty():
    pool = MagicMock()
    out = await ai_governance.record_ai_call(
        pool,
        enterprise_id="",
        task_kind="x",
        model_version="qwen2.5:14b",
        model_provider="ollama",
        prompt="hi",
    )
    assert out is None
    pool.acquire.assert_not_called()


@pytest.mark.asyncio
async def test_db_error_is_swallowed_returns_none():
    """Best-effort: a DB failure during gov audit MUST NOT raise."""
    conn = AsyncMock()
    conn.execute = AsyncMock(side_effect=Exception("connection refused"))

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)

    pool = MagicMock()
    pool.acquire = MagicMock(return_value=acquire_cm)

    # Reaches the next line with None return = pass.
    out = await ai_governance.record_ai_call(
        pool,
        enterprise_id=uuid4(),
        task_kind="x",
        model_version="qwen2.5:14b",
        model_provider="ollama",
        prompt="hi",
    )
    assert out is None


# ─── Hash + size shape ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_output_hash_present_when_output_passed():
    pool, conn = _mock_pool_returning(uuid4())
    await ai_governance.record_ai_call(
        pool,
        enterprise_id=uuid4(),
        task_kind="x",
        model_version="qwen2.5:14b",
        model_provider="ollama",
        prompt="hi",
        output="answered",
    )
    args = conn.fetchrow.await_args.args
    # output_hash is $13 → args[13]; output_size_bytes is $14 → args[14].
    assert args[13] is not None
    assert len(args[13]) == 64
    assert args[14] == len("answered")


@pytest.mark.asyncio
async def test_output_hash_none_when_output_empty():
    pool, conn = _mock_pool_returning(uuid4())
    await ai_governance.record_ai_call(
        pool,
        enterprise_id=uuid4(),
        task_kind="x",
        model_version="qwen2.5:14b",
        model_provider="ollama",
        prompt="hi",
        output="",
    )
    args = conn.fetchrow.await_args.args
    assert args[13] is None
    assert args[14] == 0


@pytest.mark.asyncio
async def test_context_refs_serialised_to_json():
    pool, conn = _mock_pool_returning(uuid4())
    await ai_governance.record_ai_call(
        pool,
        enterprise_id=uuid4(),
        task_kind="x",
        model_version="qwen2.5:14b",
        model_provider="ollama",
        prompt="hi",
        context_refs=[{"doc_id": "abc", "page": 2}, {"doc_id": "xyz"}],
    )
    args = conn.fetchrow.await_args.args
    # context_refs is $11 → args[11] (json string)
    refs_str = args[11]
    assert "abc" in refs_str
    assert "page" in refs_str
