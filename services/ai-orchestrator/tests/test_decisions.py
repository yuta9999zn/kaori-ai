"""
F-029 — tests for the AI Decision Log endpoints.

Covers:
  GET /decisions          — empty, paginated, cursor round-trip, type filter,
                            q search, from>to, missing tenant header, invalid
                            cursor, limit cap.
  GET /decisions/export.csv — UTF-8 BOM byte check, header rows, X-Export-
                              Truncated header when row count > cap.

Pattern mirrors data-pipeline/tests/test_pipelines_api.py — patch
acquire_for_tenant on the new router module so the in-memory mock conn
powers the test instead of a real Postgres.
"""
from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
DEC_A      = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
DEC_B      = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
HEADERS    = {"X-Enterprise-ID": ENTERPRISE}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn() -> AsyncMock:
    """Mock asyncpg connection with sane defaults."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    return conn


def _make_tenant_ctx(conn):
    """Async-CM that yields the same mock conn regardless of enterprise_id.
    Mirrors the helper in data-pipeline/tests/test_api.py."""
    @asynccontextmanager
    async def _fake(enterprise_id):  # noqa: ARG001
        yield conn
    return _fake


def _decision_row(decision_id: str, *, decision_type: str = "column_map",
                  subject: str = "amount", chosen_value: str = "currency",
                  confidence: float = 0.92, method: str = "llm",
                  reasoning: str | None = "matched dictionary entry",
                  needs_user_confirm: bool = False,
                  uncertainty_flags: list[str] | None = None,
                  alternatives: list | None = None,
                  run_id: str | None = None,
                  created_at: datetime | None = None) -> MagicMock:
    """asyncpg-Record-like dict accessor."""
    base = dict(
        decision_id=uuid.UUID(decision_id),
        run_id=uuid.UUID(run_id) if run_id else None,
        decision_type=decision_type,
        subject=subject,
        chosen_value=chosen_value,
        confidence=confidence,
        method=method,
        alternatives=alternatives or [],
        uncertainty_flags=uncertainty_flags or [],
        reasoning=reasoning,
        needs_user_confirm=needs_user_confirm,
        created_at=created_at or datetime(2026, 4, 27, 10, 0, tzinfo=timezone.utc),
    )
    rec = MagicMock()
    rec.__getitem__ = lambda self, k: base[k]
    rec.get = lambda k, default=None: base.get(k, default)
    return rec


@pytest.fixture
def conn() -> AsyncMock:
    return _make_conn()


@pytest.fixture
def app_client(conn):
    """Standalone TestClient for the F-029 router only."""
    tenant_ctx = _make_tenant_ctx(conn)
    with patch("ai_orchestrator.routers.decisions.acquire_for_tenant", tenant_ctx):
        import ai_orchestrator.routers.decisions as _d  # noqa: PLC0415

        test_app = FastAPI(title="Kaori AI Orchestrator (test — F-029)")
        test_app.include_router(_d.router, prefix="/decisions")

        with TestClient(test_app, raise_server_exceptions=True) as client:
            yield client


# ===========================================================================
# GET /decisions
# ===========================================================================

class TestListDecisions:
    """Black-box contract tests for the cursor-paginated list endpoint."""

    def test_empty_returns_200_with_empty_data_and_no_cursor(self, app_client, conn):
        conn.fetch.return_value = []

        resp = app_client.get("/decisions", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"] == []
        assert body["meta"]["cursor"] is None
        assert body["meta"]["has_more"] is False
        assert body["meta"]["count"] == 0
        assert "server_time" in body["meta"]

    def test_returns_serialised_rows_and_cursor_when_more_exist(self, app_client, conn):
        rows = [
            _decision_row(DEC_A, created_at=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)),
            _decision_row(DEC_B, created_at=datetime(2026, 4, 27, 11, 0, tzinfo=timezone.utc)),
        ]
        conn.fetch.return_value = rows

        resp = app_client.get("/decisions?limit=1", headers=HEADERS)

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == DEC_A
        assert body["data"][0]["entity_ref"] == "amount"
        assert body["data"][0]["confidence"] == 0.92
        assert body["meta"]["has_more"] is True
        assert body["meta"]["cursor"] is not None

    def test_invalid_cursor_returns_400(self, app_client):
        resp = app_client.get("/decisions?cursor=not-base64", headers=HEADERS)
        assert resp.status_code == 400
        body = resp.json()
        assert "Invalid cursor" in body.get("detail", body.get("title", ""))

    def test_type_filter_is_passed_to_db_query(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get(
            "/decisions?type=column_map,cleaning_rule",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        sql, *args = conn.fetch.call_args.args
        # Expected order: enterprise_id, types[], limit+1
        assert ["column_map", "cleaning_rule"] in args
        assert "decision_type = ANY" in sql

    def test_q_search_adds_ilike_clauses(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get("/decisions?q=khách+hàng", headers=HEADERS)
        assert resp.status_code == 200
        sql, *args = conn.fetch.call_args.args
        assert "ILIKE" in sql
        assert "%khách hàng%" in args  # FastAPI decoded the URL form

    def test_from_after_to_returns_400(self, app_client):
        resp = app_client.get(
            "/decisions?from=2026-05-01T00:00:00Z&to=2026-04-01T00:00:00Z",
            headers=HEADERS,
        )
        assert resp.status_code == 400

    def test_limit_above_max_returns_422(self, app_client):
        resp = app_client.get("/decisions?limit=1000", headers=HEADERS)
        assert resp.status_code == 422

    def test_missing_tenant_header_returns_422(self, app_client):
        resp = app_client.get("/decisions")
        assert resp.status_code == 422

    def test_round_trip_cursor_pagination(self, app_client, conn):
        rows = [
            _decision_row(DEC_A, created_at=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)),
            _decision_row(DEC_B, created_at=datetime(2026, 4, 27, 11, 0, tzinfo=timezone.utc)),
        ]
        conn.fetch.return_value = rows

        page1 = app_client.get("/decisions?limit=1", headers=HEADERS).json()
        cursor = page1["meta"]["cursor"]
        assert cursor is not None

        from ai_orchestrator.routers.decisions import _decode_cursor, _encode_cursor
        ts, dec_id = _decode_cursor(cursor)
        assert _encode_cursor(ts, dec_id) == cursor

        conn.fetch.return_value = []
        resp = app_client.get(f"/decisions?limit=1&cursor={cursor}", headers=HEADERS)
        assert resp.status_code == 200


# ===========================================================================
# GET /decisions/export.csv
# ===========================================================================

class TestExportDecisionsCsv:
    """Streaming CSV export — BOM + header + truncation flag."""

    def test_starts_with_utf8_bom_and_includes_header(self, app_client, conn):
        conn.fetch.return_value = [
            _decision_row(DEC_A, subject="Khách hàng A",
                          reasoning="VN diacritics: ăâđêôơư"),
        ]
        resp = app_client.get("/decisions/export.csv", headers=HEADERS)

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "X-Export-Truncated" not in resp.headers
        body = resp.content
        # F-029 DoD: BOM byte check (Vietnamese Excel)
        assert body[:3] == b"\xef\xbb\xbf"
        # Header line follows BOM
        first_line = body[3:].split(b"\n", 1)[0]
        assert b"decision_id" in first_line
        assert b"subject" in first_line
        # Diacritics survive UTF-8 round-trip
        assert "Khách hàng A".encode("utf-8") in body
        assert "ăâđêôơư".encode("utf-8") in body

    def test_truncated_header_set_when_row_count_over_cap(self, app_client, conn):
        from ai_orchestrator.routers.decisions import EXPORT_MAX_ROWS

        # Return EXPORT_MAX_ROWS + 1 — the +1 row triggers the truncation flag.
        conn.fetch.return_value = [
            _decision_row(str(uuid.uuid4()), subject=f"row-{i}")
            for i in range(EXPORT_MAX_ROWS + 1)
        ]
        resp = app_client.get("/decisions/export.csv", headers=HEADERS)

        assert resp.status_code == 200
        assert resp.headers.get("X-Export-Truncated") == "true"

    def test_no_truncation_at_exact_cap(self, app_client, conn):
        from ai_orchestrator.routers.decisions import EXPORT_MAX_ROWS
        conn.fetch.return_value = [
            _decision_row(str(uuid.uuid4()), subject=f"row-{i}")
            for i in range(EXPORT_MAX_ROWS)
        ]
        resp = app_client.get("/decisions/export.csv", headers=HEADERS)
        assert resp.status_code == 200
        assert "X-Export-Truncated" not in resp.headers

    def test_filter_params_are_applied_to_export_query(self, app_client, conn):
        conn.fetch.return_value = []
        resp = app_client.get(
            "/decisions/export.csv?type=cleaning_rule&q=phone",
            headers=HEADERS,
        )
        assert resp.status_code == 200
        sql, *args = conn.fetch.call_args.args
        assert "decision_type = ANY" in sql
        assert "ILIKE" in sql
        assert "%phone%" in args


# ===========================================================================
# F-036 — GET /decisions/{id} + override + revoke
# ===========================================================================

def _override_row(*, override_id: str, decision_id: str, override_value: str = "non-churn",
                  reason: str = "VIP customer renewal in progress",
                  overridden_by: str | None = None,
                  overridden_at: datetime | None = None,
                  revoked_at: datetime | None = None,
                  revoked_by: str | None = None,
                  revoke_reason: str | None = None,
                  original_chosen_value: str | None = "churn") -> MagicMock:
    base = dict(
        override_id=uuid.UUID(override_id),
        decision_id=uuid.UUID(decision_id),
        original_chosen_value=original_chosen_value,
        override_value=override_value,
        reason=reason,
        overridden_by_user=uuid.UUID(overridden_by) if overridden_by else None,
        overridden_at=overridden_at or datetime(2026, 5, 3, 9, tzinfo=timezone.utc),
        revoked_at=revoked_at,
        revoked_by_user=uuid.UUID(revoked_by) if revoked_by else None,
        revoke_reason=revoke_reason,
    )
    rec = MagicMock()
    rec.__getitem__ = lambda self, k: base[k]
    rec.get = lambda k, default=None: base.get(k, default)
    return rec


class TestGetDecisionDetail:

    def test_404_when_decision_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.get(f"/decisions/{DEC_A}", headers=HEADERS)
        assert resp.status_code == 404

    def test_returns_decision_with_overrides_history(self, app_client, conn):
        decision_row = _decision_row(DEC_A)
        # Inject is_actioned + actioned_at + actioned_by + action_notes the
        # SELECT in the production code joins from decision_actions.
        decision_row.__getitem__ = lambda self, k: {
            "decision_id":          uuid.UUID(DEC_A),
            "run_id":               None,
            "decision_type":        "churn_risk",
            "subject":              "customer/CUST-001",
            "chosen_value":         "churn",
            "confidence":           0.78,
            "method":               "ml",
            "alternatives":         [],
            "uncertainty_flags":    [],
            "reasoning":            "low engagement last 90d",
            "needs_user_confirm":   False,
            "created_at":           datetime(2026, 5, 3, tzinfo=timezone.utc),
            "is_actioned":          False,
            "actioned_at":          None,
            "actioned_by":          None,
            "action_notes":         None,
        }[k]
        decision_row.get = lambda k, default=None: None

        # Two overrides — one active, one revoked — descending by overridden_at.
        active = _override_row(
            override_id="11111111-1111-1111-1111-111111111111",
            decision_id=DEC_A,
            override_value="non-churn", reason="VIP renewal",
            overridden_at=datetime(2026, 5, 3, 11, tzinfo=timezone.utc),
        )
        revoked = _override_row(
            override_id="22222222-2222-2222-2222-222222222222",
            decision_id=DEC_A,
            override_value="non-churn", reason="initial typo",
            overridden_at=datetime(2026, 5, 3, 9, tzinfo=timezone.utc),
            revoked_at=datetime(2026, 5, 3, 10, tzinfo=timezone.utc),
            revoke_reason="re-doing with correct reason",
        )

        conn.fetchrow.return_value = decision_row
        conn.fetch.return_value = [active, revoked]

        resp = app_client.get(f"/decisions/{DEC_A}", headers=HEADERS)
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["decision_id"] == DEC_A
        assert data["confidence"] == 0.78
        assert len(data["overrides"]) == 2
        assert data["overrides"][0]["is_active"] is True
        assert data["overrides"][1]["is_active"] is False
        assert data["overrides"][1]["revoked_at"] is not None


class TestCreateOverride:

    def test_404_when_decision_missing(self, app_client, conn):
        conn.fetchrow.return_value = None
        resp = app_client.post(
            f"/decisions/{DEC_A}/override",
            headers=HEADERS,
            json={"override_value": "non-churn", "reason": "VIP"},
        )
        assert resp.status_code == 404

    def test_inserts_row_and_emits_kafka(self, app_client, conn):
        # First fetchrow = decision lookup; second = INSERT RETURNING.
        ov_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
        ts = datetime(2026, 5, 3, 12, tzinfo=timezone.utc)

        decision_lookup = MagicMock()
        decision_lookup.__getitem__ = lambda self, k: {
            "chosen_value": "churn", "decision_type": "churn_risk",
        }[k]
        decision_lookup.get = lambda k, default=None: None

        insert_return = MagicMock()
        insert_return.__getitem__ = lambda self, k: {
            "override_id": ov_id, "overridden_at": ts,
        }[k]
        insert_return.get = lambda k, default=None: None

        conn.fetchrow.side_effect = [decision_lookup, insert_return]

        with patch("ai_orchestrator.routers.decisions.emit",
                   new_callable=AsyncMock) as emit_mock:
            resp = app_client.post(
                f"/decisions/{DEC_A}/override",
                headers={**HEADERS, "X-User-ID": "44444444-4444-4444-4444-444444444444"},
                json={"override_value": "non-churn",
                      "reason": "Customer just renewed yearly contract"},
            )

        assert resp.status_code == 201, resp.text
        body = resp.json()["data"]
        assert body["override_id"] == str(ov_id)
        assert body["original_chosen_value"] == "churn"
        assert body["override_value"] == "non-churn"

        # Kafka emit hit with the right shape.
        emit_mock.assert_awaited_once()
        topic, payload = emit_mock.await_args.args
        assert topic == "kaori.feedback.actions"
        assert payload["action"] == "override.created"
        assert payload["decision_id"] == DEC_A
        assert payload["override_value"] == "non-churn"
        assert payload["original_value"] == "churn"
        assert payload["decision_type"] == "churn_risk"

    def test_validation_rejects_empty_reason(self, app_client):
        resp = app_client.post(
            f"/decisions/{DEC_A}/override",
            headers=HEADERS,
            json={"override_value": "x", "reason": ""},
        )
        # Pydantic min_length=1 → 422
        assert resp.status_code == 422

    def test_validation_rejects_overlong_reason(self, app_client):
        resp = app_client.post(
            f"/decisions/{DEC_A}/override",
            headers=HEADERS,
            json={"override_value": "x", "reason": "x" * 2001},
        )
        assert resp.status_code == 422

    def test_kafka_emit_failure_does_not_break_response(self, app_client, conn):
        """Best-effort emit — a downed Kafka must not roll back the
        override row insert."""
        ov_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
        ts = datetime(2026, 5, 3, tzinfo=timezone.utc)
        decision_lookup = MagicMock()
        decision_lookup.__getitem__ = lambda self, k: {
            "chosen_value": "churn", "decision_type": "churn_risk",
        }[k]
        decision_lookup.get = lambda k, default=None: None
        insert_return = MagicMock()
        insert_return.__getitem__ = lambda self, k: {
            "override_id": ov_id, "overridden_at": ts,
        }[k]
        insert_return.get = lambda k, default=None: None
        conn.fetchrow.side_effect = [decision_lookup, insert_return]

        with patch("ai_orchestrator.routers.decisions.emit",
                   new_callable=AsyncMock) as emit_mock:
            emit_mock.side_effect = RuntimeError("kafka down")
            resp = app_client.post(
                f"/decisions/{DEC_A}/override",
                headers=HEADERS,
                json={"override_value": "x", "reason": "trying"},
            )
        # Override insert succeeded; Kafka failure is logged + swallowed.
        assert resp.status_code == 201


class TestRevokeOverride:

    OV_ID = "66666666-6666-6666-6666-666666666666"

    def test_404_when_override_missing(self, app_client, conn):
        # Update returns None, then existence check returns None.
        conn.fetchrow.side_effect = [None, None]
        resp = app_client.post(
            f"/decisions/{DEC_A}/override/{self.OV_ID}/revoke",
            headers=HEADERS,
            json={"reason": "rolling back"},
        )
        assert resp.status_code == 404

    def test_409_when_already_revoked(self, app_client, conn):
        # Update returns None (no rows match revoked_at IS NULL); existence
        # check returns the row with revoked_at set.
        existing = MagicMock()
        existing.__getitem__ = lambda self, k: {
            "revoked_at": datetime(2026, 5, 3, tzinfo=timezone.utc),
        }[k]
        existing.get = lambda k, default=None: None
        conn.fetchrow.side_effect = [None, existing]
        resp = app_client.post(
            f"/decisions/{DEC_A}/override/{self.OV_ID}/revoke",
            headers=HEADERS, json={"reason": "x"},
        )
        assert resp.status_code == 409

    def test_revoke_happy_path_updates_row_and_emits_kafka(self, app_client, conn):
        ts = datetime(2026, 5, 3, 13, tzinfo=timezone.utc)
        ov_uuid = uuid.UUID(self.OV_ID)
        dec_uuid = uuid.UUID(DEC_A)
        update_row = MagicMock()
        update_row.__getitem__ = lambda _self, k: {
            "override_id":      ov_uuid,
            "decision_id":      dec_uuid,
            "override_value":   "non-churn",
            "reason":           "VIP renewal",
            "revoked_at":       ts,
            "revoked_by_user":  None,
            "revoke_reason":    "rolling back — actually churned",
        }[k]
        update_row.get = lambda k, default=None: None
        conn.fetchrow.return_value = update_row

        with patch("ai_orchestrator.routers.decisions.emit",
                   new_callable=AsyncMock) as emit_mock:
            resp = app_client.post(
                f"/decisions/{DEC_A}/override/{self.OV_ID}/revoke",
                headers=HEADERS,
                json={"reason": "rolling back — actually churned"},
            )

        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        assert body["override_id"] == self.OV_ID
        assert body["revoked_at"] == ts.isoformat()
        emit_mock.assert_awaited_once()
        topic, payload = emit_mock.await_args.args
        assert topic == "kaori.feedback.actions"
        assert payload["action"] == "override.revoked"
        assert payload["override_id"] == self.OV_ID
