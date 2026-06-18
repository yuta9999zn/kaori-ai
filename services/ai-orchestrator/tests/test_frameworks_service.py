"""
F-034 Frameworks — service layer tests.

Mirrors test_reports_service.py: asyncpg + llm_router are mocked,
we exercise the orchestration around them. Cases:

  * queue_framework: validates code + question; rejects unknown code,
    empty question, over-long question; on valid input inserts a row.
  * run_framework: happy path marks ready with parsed JSON +
    extracted narrative; LLM failure marks failed without raising;
    crash safety still ends in mark_failed.
  * Per-framework smoke: SWOT / 6W / 2H / Fishbone narratives extract
    correctly from synthetic content.
  * extract_narrative + get_template helpers (templates.py).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest

from ai_orchestrator.frameworks import service, templates
from ai_orchestrator.frameworks.service import (
    InvalidFrameworkInputError,
    UnknownFrameworkError,
)


_ENT_ID = "11111111-1111-1111-1111-111111111111"


def _fake_acquire(conn):
    @asynccontextmanager
    async def _cm(_enterprise_id):
        yield conn
    return _cm


def _row(run_id: UUID, code: str = "swot", **overrides) -> dict:
    base = {
        "run_id":           run_id,
        "framework_code":   code,
        "question":         "Đối thủ mới đang lấn thị phần như thế nào?",
        "source_ref":       "gold_features:retail_2026q1",
        "consent_external": False,
        "status":           "queued",
        "narrative":        None,
        "created_by_user":  None,
        "created_at":       datetime(2026, 5, 3, tzinfo=timezone.utc),
        "completed_at":     None,
        "last_error":       None,
        "content_json":     None,
    }
    base.update(overrides)
    return base


# ─── queue_framework ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_framework_valid_code_inserts_row():
    conn = AsyncMock()
    new_id = uuid4()
    with patch("ai_orchestrator.frameworks.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.frameworks.service.repository.create_run",
               AsyncMock(return_value=new_id)) as create_mock:
        out = await service.queue_framework(
            enterprise_id=_ENT_ID,
            framework_code="swot",
            question="Tại sao churn tăng?",
            source_ref="gold:1",
            consent_external=False,
            created_by_user=None,
        )
    assert out == new_id
    create_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_queue_framework_unknown_code_raises():
    conn = AsyncMock()
    with patch("ai_orchestrator.frameworks.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.frameworks.service.repository.create_run",
               AsyncMock()) as create_mock:
        with pytest.raises(UnknownFrameworkError):
            await service.queue_framework(
                enterprise_id=_ENT_ID,
                framework_code="5why",  # not in v0 registry
                question="x",
                source_ref=None,
                consent_external=False,
                created_by_user=None,
            )
    create_mock.assert_not_called()


@pytest.mark.asyncio
async def test_queue_framework_empty_question_raises():
    with pytest.raises(InvalidFrameworkInputError):
        await service.queue_framework(
            enterprise_id=_ENT_ID,
            framework_code="swot",
            question="    ",
            source_ref=None,
            consent_external=False,
            created_by_user=None,
        )


@pytest.mark.asyncio
async def test_queue_framework_over_long_question_raises():
    with pytest.raises(InvalidFrameworkInputError):
        await service.queue_framework(
            enterprise_id=_ENT_ID,
            framework_code="swot",
            question="x" * 2001,
            source_ref=None,
            consent_external=False,
            created_by_user=None,
        )


# ─── run_framework happy path ────────────────────────────────────

_VALID_SWOT = {
    "strengths": {
        "items": [
            {"text": "Thương hiệu mạnh ở miền Nam", "confidence": 0.85},
            {"text": "Chuỗi cung ứng linh hoạt",       "confidence": 0.70},
        ],
    },
    "weaknesses": {
        "items": [
            {"text": "Chi phí marketing cao", "confidence": 0.60},
            {"text": "Phụ thuộc nhà cung cấp A", "confidence": 0.55},
        ],
    },
    "opportunities": {
        "items": [
            {"text": "Mở rộng kênh online",           "confidence": 0.75},
            {"text": "Hợp tác chuỗi siêu thị quốc gia", "confidence": 0.65},
        ],
    },
    "threats": {
        "items": [
            {"text": "Đối thủ X giảm giá",     "confidence": 0.80},
            {"text": "Nguyên liệu nhập tăng",  "confidence": 0.60},
        ],
    },
    "summary": "Tập trung mở rộng kênh online trong Q2.",
}


@pytest.mark.asyncio
async def test_run_framework_happy_path_marks_ready():
    run_id = uuid4()
    conn = AsyncMock()

    with patch("ai_orchestrator.frameworks.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.frameworks.service.repository.fetch_run",
               AsyncMock(return_value=_row(run_id))), \
         patch("ai_orchestrator.frameworks.service.repository.mark_running",
               AsyncMock()) as mark_running, \
         patch("ai_orchestrator.frameworks.service.repository.mark_ready",
               AsyncMock()) as mark_ready, \
         patch("ai_orchestrator.frameworks.service.repository.mark_failed",
               AsyncMock()) as mark_failed, \
         patch("ai_orchestrator.frameworks.service.llm_router.complete_structured",
               AsyncMock(return_value=_VALID_SWOT)) as llm_call:

        await service.run_framework(enterprise_id=_ENT_ID, run_id=run_id)

    mark_running.assert_awaited_once()
    llm_call.assert_awaited_once()

    # Output_schema flowed through.
    llm_kwargs = llm_call.await_args.kwargs
    assert llm_kwargs["task"] == "frameworks.swot"
    assert llm_kwargs["output_schema"] is not None
    # Question + source_ref substituted into the prompt.
    assert "Đối thủ mới" in llm_kwargs["prompt"]
    assert "retail_2026q1" in llm_kwargs["prompt"]
    assert "{{question}}" not in llm_kwargs["prompt"]

    mark_ready.assert_awaited_once()
    ready_kwargs = mark_ready.await_args.kwargs
    assert ready_kwargs["content_json"] == _VALID_SWOT
    # Narrative comes from summary for SWOT.
    assert "kênh online" in ready_kwargs["narrative"]

    mark_failed.assert_not_called()


# ─── run_framework failure paths ─────────────────────────────────

@pytest.mark.asyncio
async def test_run_framework_llm_failure_marks_failed_no_raise():
    run_id = uuid4()
    conn = AsyncMock()

    with patch("ai_orchestrator.frameworks.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.frameworks.service.repository.fetch_run",
               AsyncMock(return_value=_row(run_id))), \
         patch("ai_orchestrator.frameworks.service.repository.mark_running",
               AsyncMock()), \
         patch("ai_orchestrator.frameworks.service.repository.mark_ready",
               AsyncMock()) as mark_ready, \
         patch("ai_orchestrator.frameworks.service.repository.mark_failed",
               AsyncMock()) as mark_failed, \
         patch("ai_orchestrator.frameworks.service.llm_router.complete_structured",
               AsyncMock(side_effect=RuntimeError("output validation failed"))):
        # Must not raise.
        await service.run_framework(enterprise_id=_ENT_ID, run_id=run_id)

    mark_ready.assert_not_called()
    mark_failed.assert_awaited_once()
    assert "validation failed" in mark_failed.await_args.args[2]


@pytest.mark.asyncio
async def test_run_framework_row_missing_logs_and_returns():
    """Row was deleted between queue + run — should warn + return,
    not raise."""
    conn = AsyncMock()

    with patch("ai_orchestrator.frameworks.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.frameworks.service.repository.fetch_run",
               AsyncMock(return_value=None)), \
         patch("ai_orchestrator.frameworks.service.repository.mark_running",
               AsyncMock()) as mark_running, \
         patch("ai_orchestrator.frameworks.service.repository.mark_failed",
               AsyncMock()) as mark_failed:
        await service.run_framework(enterprise_id=_ENT_ID, run_id=uuid4())
    mark_running.assert_not_called()
    mark_failed.assert_not_called()


@pytest.mark.asyncio
async def test_run_framework_unhandled_exception_falls_back_to_mark_failed():
    """Crash in the inner pipeline (e.g. mark_running raises) still
    ends with a mark_failed write so the row never sits in 'running'
    forever."""
    run_id = uuid4()
    conn = AsyncMock()

    with patch("ai_orchestrator.frameworks.service.acquire_for_tenant",
               side_effect=_fake_acquire(conn)), \
         patch("ai_orchestrator.frameworks.service.repository.fetch_run",
               AsyncMock(side_effect=RuntimeError("DB down"))), \
         patch("ai_orchestrator.frameworks.service.repository.mark_failed",
               AsyncMock()) as mark_failed:
        # Must not raise.
        await service.run_framework(enterprise_id=_ENT_ID, run_id=run_id)
    mark_failed.assert_awaited_once()


# ─── narrative extraction per framework ──────────────────────────

def test_extract_narrative_swot_uses_summary():
    n = templates.extract_narrative("swot", _VALID_SWOT)
    assert n is not None and "kênh online" in n


def test_extract_narrative_6w_uses_summary():
    payload = {
        "who": "Đội Sales",
        "what": "Mất khách hàng B2B",
        "when": "Quý 1/2026",
        "where": "Khu vực miền Bắc",
        "why": "Đối thủ giảm giá 8%",
        "how": "Match giá hoặc tăng dịch vụ hậu mãi",
        "summary": "Đề xuất họp Sales miền Bắc tuần tới.",
    }
    assert templates.extract_narrative("6w", payload) == "Đề xuất họp Sales miền Bắc tuần tới."


def test_extract_narrative_2h_prefers_estimate_unit():
    payload = {
        "how": {"approach": "x", "steps": ["a", "b", "c"]},
        "how_much": {
            "estimate": "≈ 1.500.000.000", "unit": "₫/quý",
            "confidence": 0.65, "assumptions": [],
        },
        "summary": "Có thể làm trong 2 quý.",
    }
    n = templates.extract_narrative("2h", payload)
    assert n == "≈ 1.500.000.000 ₫/quý"


def test_extract_narrative_2h_falls_back_to_summary_when_estimate_missing():
    payload = {
        "how": {"approach": "x", "steps": ["a", "b", "c"]},
        "how_much": {"estimate": "", "unit": "", "confidence": 0, "assumptions": []},
        "summary": "Cần dữ liệu thêm.",
    }
    assert templates.extract_narrative("2h", payload) == "Cần dữ liệu thêm."


def test_extract_narrative_fishbone_uses_root_cause():
    payload = {
        "problem": "Doanh thu kênh A giảm 20%",
        "categories": [
            {"name": "Con người", "causes": [
                {"text": "Thiếu nhân sự", "depth": 2},
                {"text": "Đào tạo chưa đủ", "depth": 1},
            ]},
        ],
        "root_cause_hypothesis": "Quy trình onboarding nhân viên Sales chưa chuẩn hoá.",
    }
    n = templates.extract_narrative("fishbone", payload)
    assert n == "Quy trình onboarding nhân viên Sales chưa chuẩn hoá."


def test_extract_narrative_unknown_code_returns_none():
    assert templates.extract_narrative("unknown", {"summary": "x"}) is None


def test_get_template_returns_registry_entries():
    for code in ("swot", "6w", "2h", "fishbone"):
        t = templates.get_template(code)
        assert t is not None
        assert t["code"] == code
        assert "system_prompt" in t and "{{question}}" in t["system_prompt"]
        assert "output_schema" in t and t["output_schema"]["type"] == "object"
    assert templates.get_template("nope") is None


def test_allowed_codes_match_registry():
    assert templates.ALLOWED_CODES == frozenset(templates.REGISTRY.keys())
