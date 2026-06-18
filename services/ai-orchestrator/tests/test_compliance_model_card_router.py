"""HTTP-surface tests for /compliance/model-cards (author + read) — K-25.

EU AI Act Annex IV-lite model card (ADR-0041, K-25). Mocks acquire_for_tenant
+ record_ai_call; no Postgres. Pattern mirrors test_compliance_risk_router.py.

Coverage focus:
  1. POST a COMPLETE card -> 201, completeness.complete True, INSERT into
     ai_model_card, record_ai_call awaited once for task_kind 'model_card'.
  2. POST an INCOMPLETE card -> 201 (trust-first, not blocked) but the computed
     completeness flags the missing Annex IV-lite sections.
  3. POST without X-Enterprise-ID -> 422.
  4. GET /lookup?model=&version= returns the latest card.
  5. GET /register lists the tenant's cards.
  6. Pure: cc.model_card_completeness.
"""
from __future__ import annotations

import datetime
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.reasoning import compliance_controls as cc


ENTERPRISE_ID = "11111111-1111-1111-1111-111111111111"
USER_ID = "55555555-5555-5555-5555-555555555555"
MODEL_CARD_ID = "99999999-9999-9999-9999-999999999999"

HEADERS = {"X-Enterprise-ID": ENTERPRISE_ID, "X-User-ID": USER_ID}

# The 6 Annex IV-lite required sections, all filled.
COMPLETE_BODY = {
    "model": "qwen2.5:14b",
    "version": "2026-01-01",
    "provider": "ollama",
    "intended_purpose": "Phân tích dữ liệu kinh doanh SME, sinh insight + đề xuất hành động.",
    "capabilities": "Tóm tắt, phân loại, suy luận số liệu, RAG trên KB ngành.",
    "limitations": "Không phải tư vấn pháp lý/tài chính; có thể sai số ở dữ liệu thưa.",
    "training_data_summary": "Qwen 2.5 pretrain + BGE-M3 embeddings; KB nội bộ tenant.",
    "evaluation_summary": "|OR| grounding gate + 7-dim quality scorecard ≥80%.",
    "risk_mitigations": "K-23 human oversight, |OR| decline branch, PII redaction.",
}


def _row(**kwargs) -> MagicMock:
    r = MagicMock()
    r.__getitem__ = lambda _s, k: kwargs[k]
    r.get = lambda k, default=None: kwargs.get(k, default)
    r.keys = lambda: list(kwargs.keys())
    r.__iter__ = lambda _s: iter(kwargs.keys())
    return r


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None
    conn.execute.return_value = "OK"
    return conn


def _ctx(conn):
    @asynccontextmanager
    async def _fake(*_args, **_kwargs):
        yield conn
    return _fake


def _card_row(**overrides) -> MagicMock:
    """Canned row shaped like the INSERT ... RETURNING / SELECT columns."""
    base = dict(
        model_card_id=UUID(MODEL_CARD_ID),
        public_ref="modelcard_01HZZZ",
        model="qwen2.5:14b",
        version="2026-01-01",
        provider="ollama",
        intended_purpose=COMPLETE_BODY["intended_purpose"],
        capabilities=COMPLETE_BODY["capabilities"],
        limitations=COMPLETE_BODY["limitations"],
        training_data_summary=COMPLETE_BODY["training_data_summary"],
        evaluation_summary=COMPLETE_BODY["evaluation_summary"],
        risk_mitigations=COMPLETE_BODY["risk_mitigations"],
        foreseeable_misuse=None,
        annex_iv={},
        completeness={"complete": True, "missing": []},
        status="active",
        authored_at=datetime.datetime(2026, 6, 6),
    )
    base.update(overrides)
    return _row(**base)


@pytest.fixture
def conn():
    return _make_conn()


@pytest.fixture
def record_mock():
    return AsyncMock(return_value=uuid4())


@pytest.fixture
def app_client(conn, record_mock):
    with patch("ai_orchestrator.routers.compliance_model_card.acquire_for_tenant",
               _ctx(conn)), \
         patch("ai_orchestrator.routers.compliance_model_card.record_ai_call",
               record_mock):
        import ai_orchestrator.routers.compliance_model_card as mc
        from ai_orchestrator.shared.errors import register_problem_handlers
        test_app = FastAPI()
        test_app.include_router(mc.router)
        register_problem_handlers(test_app)
        with TestClient(test_app, raise_server_exceptions=True) as c:
            yield c


def _insert_completeness(conn) -> dict:
    """The completeness JSON the router computed and passed as INSERT param $13."""
    args = conn.fetchrow.await_args.args
    return json.loads(args[13])


# ─── author ──────────────────────────────────────────────────────────


def test_author_complete_card_201(app_client, conn, record_mock):
    conn.fetchrow.return_value = _card_row()

    resp = app_client.post("/compliance/model-cards", json=COMPLETE_BODY, headers=HEADERS)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["model"] == "qwen2.5:14b"
    assert body["completeness"]["complete"] is True

    insert_sql = conn.fetchrow.await_args.args[0]
    assert "INSERT INTO ai_model_card" in insert_sql
    # Router computed completeness = complete for a fully-filled card.
    assert _insert_completeness(conn) == {"complete": True, "missing": []}

    record_mock.assert_awaited_once()
    assert record_mock.await_args.kwargs["task_kind"] == "model_card"
    assert record_mock.await_args.kwargs["model_version"] == "qwen2.5:14b@2026-01-01"


def test_author_incomplete_card_flags_missing(app_client, conn, record_mock):
    incomplete = {k: v for k, v in COMPLETE_BODY.items()
                  if k not in ("limitations", "evaluation_summary")}
    conn.fetchrow.return_value = _card_row(
        limitations=None, evaluation_summary=None,
        completeness={"complete": False, "missing": ["limitations", "evaluation_summary"]},
    )

    resp = app_client.post("/compliance/model-cards", json=incomplete, headers=HEADERS)
    # Trust-first: an incomplete card is recorded (201), not hard-blocked.
    assert resp.status_code == 201, resp.text

    computed = _insert_completeness(conn)
    assert computed["complete"] is False
    assert computed["missing"] == ["limitations", "evaluation_summary"]


def test_author_missing_enterprise_header_422(app_client):
    resp = app_client.post("/compliance/model-cards", json=COMPLETE_BODY,
                           headers={"X-User-ID": USER_ID})  # no X-Enterprise-ID
    assert resp.status_code == 422


# ─── read ────────────────────────────────────────────────────────────


def test_lookup_returns_latest(app_client, conn):
    conn.fetchrow.return_value = _card_row()
    resp = app_client.get(
        "/compliance/model-cards/lookup?model=qwen2.5:14b&version=2026-01-01",
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model"] == "qwen2.5:14b"
    assert body["version"] == "2026-01-01"
    assert body["completeness"]["complete"] is True


def test_register_lists_cards(app_client, conn):
    conn.fetch.return_value = [_card_row()]
    resp = app_client.get("/compliance/model-cards/register", headers=HEADERS)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["model"] == "qwen2.5:14b"


# ─── pure: model_card_completeness ───────────────────────────────────


def test_completeness_full_card():
    assert cc.model_card_completeness(COMPLETE_BODY) == {"complete": True, "missing": []}


def test_completeness_flags_blank_and_missing_sections():
    card = dict(COMPLETE_BODY)
    card["limitations"] = "   "   # whitespace = not present
    del card["risk_mitigations"]  # absent
    out = cc.model_card_completeness(card)
    assert out["complete"] is False
    assert "limitations" in out["missing"]
    assert "risk_mitigations" in out["missing"]


def test_completeness_handles_none_card():
    out = cc.model_card_completeness(None)
    assert out["complete"] is False
    assert set(out["missing"]) == set(cc.MODEL_CARD_REQUIRED_FIELDS)
