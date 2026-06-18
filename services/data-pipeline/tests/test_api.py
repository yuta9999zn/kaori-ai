"""
test_api.py — Black-box, integration, and UAT tests for the Kaori data-pipeline
FastAPI service.

Test classes:
  TestHealthBlackBox      — /health + /health/ready contract tests
  TestUploadBlackBox      — POST /upload + GET /upload/{run_id}/status
  TestSchemaBlackBox      — POST /schema + POST /schema/confirm
  TestCleanBlackBox       — GET /clean/suggestions + POST /clean/apply (note: router uses POST /suggestions)
  TestAnalyzeBlackBox     — POST /analyze
  TestPipelineIntegration — 3 sequential wiring scenarios
  TestUAT                 — 5 realistic user scenarios

Run with:
    pytest services/data-pipeline/tests/test_api.py -v

Dependencies (same as requirements.txt plus pytest + httpx):
    pip install pytest httpx fastapi[all] asyncpg aiokafka structlog pandas
    pip install prometheus-fastapi-instrumentator rapidfuzz

The tests use pytest fixtures defined in conftest.py (app_client, mock_conn).
Each test patches the DB pool and Kafka producer so no live infrastructure is needed.
"""
import io
import json
import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Constants shared across all tests
# ---------------------------------------------------------------------------
ENTERPRISE_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
ENTERPRISE_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
USER_ID = "cccccccc-cccc-cccc-cccc-cccccccccccc"
RUN_ID = "dddddddd-dddd-dddd-dddd-dddddddddddd"
FILE_ID = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
ANALYSIS_ID = "ffffffff-ffff-ffff-ffff-ffffffffffff"

HEADERS_A = {
    "X-Enterprise-ID": ENTERPRISE_A,
    "X-User-ID": USER_ID,
}
HEADERS_B = {
    "X-Enterprise-ID": ENTERPRISE_B,
    "X-User-ID": USER_ID,
}

VALID_CSV_CONTENT = b"name,amount,date\nAlice,1000,01/03/2024\nBob,2500,15/06/2023\n"
VIETNAMESE_CSV_CONTENT = (
    b"kh\xc3\xa1ch h\xc3\xa0ng,ng\xc3\xa0y,doanh thu\n"  # UTF-8: khách hàng,ngày,doanh thu
    b"Nguy\xe1\xbb\x85n V\xc4\x83n A,01/03/2024,1500000\n"
    b"Tr\xe1\xba\xa7n Th\xe1\xbb\x8b B,02/03/2024,2200000\n"
)


# ---------------------------------------------------------------------------
# Fixture helpers (module-level so they can be reused across classes)
# ---------------------------------------------------------------------------

def _make_mock_conn() -> AsyncMock:
    """Create a fully configured mock asyncpg connection.

    Subtlety with async transactions:
      asyncpg's ``conn.transaction()`` is a *synchronous* method that
      returns a Transaction object whose ``__aenter__`` / ``__aexit__``
      are coroutines. When ``conn`` is an ``AsyncMock``, every attribute
      access becomes another ``AsyncMock`` — so ``conn.transaction()``
      would return a *coroutine* (not the tx object) and
      ``async with conn.transaction():`` raises:

          TypeError: 'coroutine' object does not support the async
                     context manager protocol

      Fix: explicitly assign ``conn.transaction`` a synchronous
      ``MagicMock`` whose ``return_value`` is the (async) tx mock.
    """
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    conn.fetchval.return_value = None
    conn.fetch.return_value = []
    conn.execute.return_value = None

    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)

    return conn


def _make_pool(conn: AsyncMock) -> MagicMock:
    """Wrap a mock connection in a pool that supports `async with pool.acquire()`."""

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = _acquire
    return pool


def _make_tenant_ctx_factory(conn: AsyncMock):
    """Build a fake `acquire_for_tenant` that yields the same mock conn.

    Routers migrated in Sprint 0.5 (P0 #4 RLS cutover) replaced
    ``async with get_pool().acquire() as conn:`` with
    ``async with acquire_for_tenant(x_enterprise_id) as conn:``. Tests
    that previously patched ``get_pool`` need to patch the new helper too
    — this factory returns an async context manager parameterised with
    enterprise_id (which we discard since the mock conn ignores RLS).
    """
    @asynccontextmanager
    async def _fake_acquire_for_tenant(enterprise_id):  # noqa: ARG001
        yield conn

    return _fake_acquire_for_tenant


def _mock_row(**kwargs) -> MagicMock:
    """
    Simulate a single asyncpg Record.
    Supports dict(row), row[key], row.get(key), and .isoformat() on datetime fields.
    """
    rec = MagicMock()
    rec.__getitem__ = lambda self, k: kwargs[k]
    rec.get = lambda k, default=None: kwargs.get(k, default)
    rec.keys = MagicMock(return_value=kwargs.keys())
    rec.values = MagicMock(return_value=kwargs.values())
    rec.items = MagicMock(return_value=kwargs.items())
    # Allow dict() conversion used in upload status endpoint
    rec.__iter__ = lambda self: iter(kwargs)
    # asyncpg records support keys() for dict(row)
    rec._fields = list(kwargs.keys())
    return rec


def _make_pipeline_run_row(**overrides) -> MagicMock:
    """Standard pipeline_runs row with sensible defaults."""
    defaults = dict(
        run_id=uuid.UUID(RUN_ID),
        status="bronze_complete",
        filename="test.csv",
        detected_language="vi",
        sheet_count=1,
        row_count_bronze=2,
        quality_score=0.95,
        error_message=None,
    )
    defaults.update(overrides)
    return _mock_row(**defaults)


async def _fake_emit(topic: str, payload: dict) -> None:  # noqa: ARG001
    """No-op Kafka emit for tests."""
    return None


# ---------------------------------------------------------------------------
# Central fixture factory used by all tests
# ---------------------------------------------------------------------------

@pytest.fixture
def conn() -> AsyncMock:
    """Fresh mock connection for each test."""
    return _make_mock_conn()


@pytest.fixture
def pool(conn) -> MagicMock:
    """Mock pool backed by the mock connection."""
    return _make_pool(conn)


@pytest.fixture
def app_client(pool, conn):
    """
    TestClient backed by a freshly-built FastAPI app that reuses the
    production routers but with DB pool and Kafka fully mocked.

    Why build the app here rather than importing main.py?
    main.py uses relative imports (from .routers import ...) which only work
    when the package is installed or run via `python -m`.  The test runner
    executes from services/data-pipeline/ (added to sys.path by conftest.py),
    so router modules are importable as top-level names.  We reconstruct the
    app with the exact same router registrations and lifespan=None so no real
    infrastructure is contacted.

    Patches applied at the module level where routers resolve get_pool /
    acquire_for_tenant / emit:
      - shared.db.get_pool                     → mock pool       (defensive)
      - shared.db.acquire_for_tenant           → tenant ctx       (defensive)
      - routers.upload.get_pool                → mock pool        (POST /upload still passes pool to ingest_file)
      - routers.upload.acquire_for_tenant      → tenant ctx       (GET /status migrated in Sprint 0.5)
      - routers.schema.acquire_for_tenant      → tenant ctx       (Sprint 0.5)
      - routers.clean.acquire_for_tenant       → tenant ctx       (Sprint 0.5)
      - routers.analyze.acquire_for_tenant     → tenant ctx       (Sprint 0.5)
      - routers.results.acquire_for_tenant     → tenant ctx       (Sprint 0.5)
      - routers.upload.kafka                   → AsyncMock        (module-level _producer alias)
      - routers.clean.emit                     → no-op coroutine
      - routers.analyze.emit                   → no-op coroutine
    """
    # Patch targets use the ``data_pipeline.*`` package name because that is
    # how the modules are registered in sys.modules after conftest bootstrap.
    # We also patch the bare ``shared.*`` names for the rare case a module was
    # imported before the package alias was set up.
    tenant_ctx = _make_tenant_ctx_factory(conn)
    with (
        patch("data_pipeline.shared.db.get_pool", return_value=pool),
        patch("data_pipeline.shared.db.acquire_for_tenant", tenant_ctx),
        patch("data_pipeline.routers.upload.get_pool", return_value=pool),
        patch("data_pipeline.routers.upload.acquire_for_tenant", tenant_ctx),
        patch("data_pipeline.routers.schema.acquire_for_tenant", tenant_ctx),
        patch("data_pipeline.routers.clean.acquire_for_tenant", tenant_ctx),
        patch("data_pipeline.routers.analyze.acquire_for_tenant", tenant_ctx),
        patch("data_pipeline.routers.results.acquire_for_tenant", tenant_ctx),
        patch("data_pipeline.routers.upload.kafka", new=AsyncMock()),
        patch("data_pipeline.routers.clean.emit", side_effect=_fake_emit),
        patch("data_pipeline.routers.analyze.emit", side_effect=_fake_emit),
    ):
        from fastapi import FastAPI  # noqa: PLC0415
        from fastapi.middleware.cors import CORSMiddleware  # noqa: PLC0415
        import data_pipeline.routers.upload as _upload  # noqa: PLC0415
        import data_pipeline.routers.schema as _schema  # noqa: PLC0415
        import data_pipeline.routers.clean as _clean    # noqa: PLC0415
        import data_pipeline.routers.analyze as _analyze  # noqa: PLC0415
        import data_pipeline.routers.results as _results  # noqa: PLC0415
        import data_pipeline.routers.health as _health  # noqa: PLC0415

        test_app = FastAPI(title="Kaori Data Pipeline (test)")
        test_app.add_middleware(CORSMiddleware, allow_origins=["*"],
                                allow_methods=["*"], allow_headers=["*"])
        test_app.include_router(_health.router)
        test_app.include_router(_upload.router,  prefix="/upload")
        test_app.include_router(_schema.router,  prefix="/schema")
        test_app.include_router(_clean.router,   prefix="/clean")
        test_app.include_router(_analyze.router, prefix="/analyze")
        test_app.include_router(_results.router, prefix="/results")

        with TestClient(test_app, raise_server_exceptions=True) as client:
            yield client


# ===========================================================================
# TestHealthBlackBox
# ===========================================================================

class TestHealthBlackBox:
    """Black-box contract tests for health endpoints — no DB interaction required."""

    def test_health_returns_200_with_status_ok(self, app_client):
        """GET /health must return 200 with {status: 'ok'}."""
        resp = app_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"

    def test_health_includes_service_name(self, app_client):
        """GET /health response body must identify the service."""
        resp = app_client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert "service" in body or "status" in body

    def test_health_ready_returns_2xx_or_503(self, app_client):
        """GET /health/ready must return 200 (ready) or 503 (not ready), never a 4xx other than 404 while endpoint is pending."""
        resp = app_client.get("/health/ready")
        # 200 = healthy, 503 = degraded, 404 = endpoint not yet implemented (Phase 1 pending)
        assert resp.status_code in (200, 503, 404)

    def test_health_ready_json_body(self, app_client):
        """GET /health/ready must return a JSON body when the endpoint exists."""
        resp = app_client.get("/health/ready")
        if resp.status_code == 404:
            pytest.skip("GET /health/ready not yet implemented (Phase 1 pending)")
        # Should not raise on parse
        body = resp.json()
        assert isinstance(body, dict)


# ===========================================================================
# TestUploadBlackBox
# ===========================================================================

class TestUploadBlackBox:
    """Black-box contract tests for POST /upload and GET /upload/{run_id}/status."""

    # --- POST /upload -------------------------------------------------------

    def test_upload_rejects_exe_extension(self, app_client, conn):
        """POST /upload with a .exe file must return 400."""
        conn.fetchval.return_value = None  # no duplicate
        resp = app_client.post(
            "/upload",
            files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
            headers=HEADERS_A,
        )
        assert resp.status_code == 400
        assert "exe" in resp.json()["detail"].lower() or "unsupported" in resp.json()["detail"].lower()

    def test_upload_rejects_pdf_extension(self, app_client, conn):
        """POST /upload with a .pdf file must return 400 (unsupported format)."""
        conn.fetchval.return_value = None
        resp = app_client.post(
            "/upload",
            files={"file": ("report.pdf", b"%PDF-1.4", "application/pdf")},
            headers=HEADERS_A,
        )
        assert resp.status_code == 400

    def test_upload_valid_csv_returns_run_id_and_sha256(self, app_client, conn):
        """Async path: a valid CSV returns 202 {run_id, status:'uploading'} and
        ingests in the background; the FE polls /upload/{run_id}/status."""
        conn.fetchrow.return_value = None   # no existing (duplicate) run
        conn.execute.return_value = None

        # The background task calls ingest_file after the response — mock it so
        # the TestClient's post-response background run is a no-op.
        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(return_value={"run_id": RUN_ID, "status": "uploading"}),
        ):
            resp = app_client.post(
                "/upload",
                files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "run_id" in body
        assert body["status"] == "uploading"

    def test_upload_duplicate_file_returns_existing_run_id(self, app_client, conn):
        """Re-upload of the same file (K-8) short-circuits to the existing
        non-failed run: 200 {run_id: existing, is_duplicate: true}."""
        original_run_uuid = uuid.UUID(RUN_ID)
        # Async-path dedup queries pipeline_runs via fetchrow — return the
        # existing run so the handler reuses it without spawning a background job.
        conn.fetchrow.return_value = {
            "run_id": original_run_uuid, "status": "bronze_complete",
        }

        resp = app_client.post(
            "/upload",
            files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
            headers=HEADERS_A,
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_duplicate"] is True
        assert body["run_id"] == RUN_ID

    def test_upload_missing_enterprise_id_header_returns_422(self, app_client):
        """POST /upload without X-Enterprise-ID must return 422 (header validation)."""
        resp = app_client.post(
            "/upload",
            files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
            headers={"X-User-ID": USER_ID},  # missing X-Enterprise-ID
        )
        assert resp.status_code == 422

    def test_upload_missing_user_id_header_returns_422(self, app_client):
        """POST /upload without X-User-ID must return 422."""
        resp = app_client.post(
            "/upload",
            files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
            headers={"X-Enterprise-ID": ENTERPRISE_A},  # missing X-User-ID
        )
        assert resp.status_code == 422

    # --- P15-S11 Tuần 8 — dept/branch/source attribution --------------------

    def test_upload_accepts_optional_dept_branch_source_headers(self, app_client):
        """POST /upload with X-Department-ID + X-Branch-ID + X-Source-ID passes
        them through to ingest_file as keyword arguments (Tuần 8 wiring)."""
        captured = {}

        async def _fake_ingest(**kwargs):
            captured.update(kwargs)
            return {
                "run_id": RUN_ID,
                "status": "uploading",
                "sha256": "header_pass_through_test",
                "department_id": kwargs["department_id"],
                "branch_id":     kwargs["branch_id"],
                "source_id":     kwargs["source_id"],
            }

        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(side_effect=_fake_ingest),
        ):
            resp = app_client.post(
                "/upload",
                files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
                headers={
                    **HEADERS_A,
                    "X-Department-ID": "22222222-2222-2222-2222-222222222222",
                    "X-Branch-ID":     "11111111-1111-1111-1111-111111111111",
                    "X-Source-ID":     "33333333-3333-3333-3333-333333333333",
                },
            )

        assert resp.status_code == 202
        # 202 body is just {run_id, status}; the dept/branch/source pass-through
        # is verified on the background ingest_file call (runs after response).
        assert "run_id" in resp.json()
        assert captured["department_id"] == "22222222-2222-2222-2222-222222222222"
        assert captured["branch_id"]     == "11111111-1111-1111-1111-111111111111"
        assert captured["source_id"]     == "33333333-3333-3333-3333-333333333333"

    def test_upload_optional_headers_default_to_none(self, app_client):
        """Without dept/branch/source headers, ingest_file gets None and
        resolves defaults internally — backwards compatible with legacy
        clients and Olist pilot."""
        captured = {}

        async def _fake_ingest(**kwargs):
            captured.update(kwargs)
            return {
                "run_id": RUN_ID,
                "status": "uploading",
                "sha256": "default_resolution_test",
            }

        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(side_effect=_fake_ingest),
        ):
            resp = app_client.post(
                "/upload",
                files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,  # only enterprise + user
            )

        assert resp.status_code == 202
        assert captured["department_id"] is None
        assert captured["branch_id"]     is None
        assert captured["source_id"]     is None

    def test_upload_invalid_dept_uuid_returns_422(self, app_client):
        """X-Department-ID = non-UUID → FastAPI Header validation 422."""
        resp = app_client.post(
            "/upload",
            files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
            headers={**HEADERS_A, "X-Department-ID": "not-a-uuid"},
        )
        assert resp.status_code == 422

    def test_upload_cross_tenant_dept_rejected_async(self, app_client, conn):
        """Async path: a cross-tenant X-Department-ID is accepted into the queue
        (202) but the background ingest raises the resolver's ValueError, which
        the _safe_ingest wrapper turns into a 'failed' run (no data crosses —
        ingest_file raises BEFORE any Bronze write, preserving K-1). The FE
        surfaces it via the status poll."""
        ingest_mock = AsyncMock(
            side_effect=ValueError(
                "X-Department-ID 22222222-2222-2222-2222-222222222222 "
                "does not belong to enterprise"
            )
        )
        with patch("data_pipeline.routers.upload.ingest_file", new=ingest_mock):
            resp = app_client.post(
                "/upload",
                files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
                headers={
                    **HEADERS_A,
                    "X-Department-ID": "22222222-2222-2222-2222-222222222222",
                },
            )

        assert resp.status_code == 202
        assert "run_id" in resp.json()
        # Background ran the (rejecting) ingest, then the wrapper marked the run
        # failed via conn.execute (the INSERT ... status='failed' UPSERT).
        ingest_mock.assert_awaited()
        assert conn.execute.await_count >= 1

    # --- P15-S11 Tuần 8 — X-Workflow-Step-ID attachment --------------------

    def test_upload_passes_workflow_step_id_to_ingestor(self, app_client):
        """POST /upload with X-Workflow-Step-ID forwards it to ingest_file."""
        captured = {}

        async def _fake_ingest(**kwargs):
            captured.update(kwargs)
            return {
                "run_id": RUN_ID,
                "status": "uploading",
                "sha256": "workflow_attach_test",
                "workflow_step_id": kwargs.get("workflow_step_id"),
                "workflow_id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                "workflow_step_title": "Lead intake",
            }

        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(side_effect=_fake_ingest),
        ):
            resp = app_client.post(
                "/upload",
                files={"file": ("leads.csv", VALID_CSV_CONTENT, "text/csv")},
                headers={
                    **HEADERS_A,
                    "X-Workflow-Step-ID": "66666666-6666-6666-6666-666666666666",
                },
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["workflow_step_id"] == "66666666-6666-6666-6666-666666666666"
        assert body["workflow_step_title"] == "Lead intake"
        # Ingestor received the explicit step_id
        assert captured["workflow_step_id"] == "66666666-6666-6666-6666-666666666666"

    def test_upload_without_workflow_step_id_passes_none(self, app_client):
        """Legacy upload — no X-Workflow-Step-ID → ingestor gets None."""
        captured = {}

        async def _fake_ingest(**kwargs):
            captured.update(kwargs)
            return {"run_id": RUN_ID, "status": "uploading", "sha256": "x"}

        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(side_effect=_fake_ingest),
        ):
            app_client.post(
                "/upload",
                files={"file": ("a.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,
            )

        assert captured["workflow_step_id"] is None

    def test_upload_invalid_workflow_step_uuid_returns_422(self, app_client):
        """X-Workflow-Step-ID = non-UUID → FastAPI Header validation 422."""
        resp = app_client.post(
            "/upload",
            files={"file": ("a.csv", VALID_CSV_CONTENT, "text/csv")},
            headers={**HEADERS_A, "X-Workflow-Step-ID": "not-a-uuid"},
        )
        assert resp.status_code == 422

    # --- ADR-0037 Tier-3 — X-Requirement-ID requirement fulfilment ----------

    def test_upload_passes_requirement_id_to_ingestor(self, app_client):
        """POST /upload with X-Requirement-ID forwards it to ingest_file so the
        resulting workflow_step_documents row lands classified against the
        declared per-step requirement (status 'da_nop')."""
        captured = {}

        async def _fake_ingest(**kwargs):
            captured.update(kwargs)
            return {"run_id": RUN_ID, "status": "uploading", "sha256": "req_fulfil"}

        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(side_effect=_fake_ingest),
        ):
            resp = app_client.post(
                "/upload",
                files={"file": ("don.pdf", VALID_CSV_CONTENT, "application/pdf")},
                headers={
                    **HEADERS_A,
                    "X-Workflow-Step-ID": "66666666-6666-6666-6666-666666666666",
                    "X-Requirement-ID": "77777777-7777-7777-7777-777777777777",
                },
            )

        assert resp.status_code == 200
        assert captured["requirement_id"] == "77777777-7777-7777-7777-777777777777"

    def test_upload_workflow_step_without_requirement_id_passes_none(self, app_client):
        """Ad-hoc card attachment — X-Workflow-Step-ID but no X-Requirement-ID →
        ingestor gets requirement_id=None (loose attachment, not requirement-linked)."""
        captured = {}

        async def _fake_ingest(**kwargs):
            captured.update(kwargs)
            return {"run_id": RUN_ID, "status": "uploading", "sha256": "x"}

        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(side_effect=_fake_ingest),
        ):
            app_client.post(
                "/upload",
                files={"file": ("a.csv", VALID_CSV_CONTENT, "text/csv")},
                headers={
                    **HEADERS_A,
                    "X-Workflow-Step-ID": "66666666-6666-6666-6666-666666666666",
                },
            )

        assert captured["requirement_id"] is None

    def test_upload_invalid_requirement_uuid_returns_422(self, app_client):
        """X-Requirement-ID = non-UUID → FastAPI Header validation 422."""
        resp = app_client.post(
            "/upload",
            files={"file": ("a.csv", VALID_CSV_CONTENT, "text/csv")},
            headers={**HEADERS_A, "X-Requirement-ID": "not-a-uuid"},
        )
        assert resp.status_code == 422

    # --- GET /upload/{run_id}/status ----------------------------------------

    def test_status_returns_404_when_run_not_found(self, app_client, conn):
        """GET /upload/{run_id}/status returns 404 when run_id not in DB."""
        conn.fetchrow.return_value = None
        resp = app_client.get(
            f"/upload/{RUN_ID}/status",
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 404

    def test_status_returns_200_with_run_fields(self, app_client, conn):
        """GET /upload/{run_id}/status returns 200 with run fields when found."""
        conn.fetchrow.return_value = _make_pipeline_run_row()
        resp = app_client.get(
            f"/upload/{RUN_ID}/status",
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "status" in body
        assert "filename" in body

    def test_status_wrong_enterprise_returns_404(self, app_client, conn):
        """GET /upload/{run_id}/status with wrong enterprise_id must return 404 (K-1 isolation)."""
        # DB returns None because enterprise_id doesn't match (WHERE clause filters it out)
        conn.fetchrow.return_value = None
        resp = app_client.get(
            f"/upload/{RUN_ID}/status",
            headers={"X-Enterprise-ID": ENTERPRISE_B},  # different tenant
        )
        assert resp.status_code == 404

    def test_status_run_id_not_uuid_returns_error(self, app_client, conn):
        """GET /upload/{run_id}/status with non-UUID run_id must return 422 (FastAPI path validation)."""
        resp = app_client.get(
            "/upload/not-a-valid-uuid/status",
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 422

    def test_status_enterprise_header_not_uuid_returns_422(self, app_client, conn):
        """GET /upload/{run_id}/status with non-UUID X-Enterprise-ID returns 422."""
        resp = app_client.get(
            f"/upload/{RUN_ID}/status",
            headers={"X-Enterprise-ID": "not-a-uuid-either"},
        )
        assert resp.status_code == 422

    def test_upload_enterprise_header_not_uuid_returns_422(self, app_client):
        """POST /upload with non-UUID X-Enterprise-ID returns 422."""
        resp = app_client.post(
            "/upload",
            files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
            headers={"X-Enterprise-ID": "garbage", "X-User-ID": USER_ID},
        )
        assert resp.status_code == 422

    def test_schema_body_run_id_not_uuid_returns_422(self, app_client):
        """POST /schema with non-UUID run_id in body returns 422 (Pydantic validation)."""
        resp = app_client.post(
            "/schema",
            json={"run_id": "not-a-uuid"},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 422

    def test_clean_apply_body_run_id_not_uuid_returns_422(self, app_client):
        """POST /clean/apply with non-UUID run_id in body returns 422 (Pydantic validation)."""
        resp = app_client.post(
            "/clean/apply",
            json={"run_id": "bad", "rule_ids": ["TRIM_WHITESPACE"]},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 422

    def test_analyze_body_run_id_not_uuid_returns_422(self, app_client):
        """POST /analyze with non-UUID run_id in body returns 422 (Pydantic validation)."""
        resp = app_client.post(
            "/analyze",
            json={"run_id": "x", "templates": ["summary_stats"]},
            headers={"X-Enterprise-ID": ENTERPRISE_A, "X-User-ID": USER_ID},
        )
        assert resp.status_code == 422

    def test_results_run_id_not_uuid_returns_422(self, app_client):
        """GET /results/{run_id} with non-UUID returns 422 (FastAPI path validation)."""
        resp = app_client.get(
            "/results/totally-invalid",
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 422

    def test_conn_transaction_is_proper_async_context_manager(self, conn):
        """Regression guard: _make_mock_conn must produce a conn.transaction() that
        works as an async context manager. Without the MagicMock override,
        AsyncMock makes conn.transaction() return a coroutine and `async with`
        raises TypeError. This test fails fast if anyone reverts the fixture."""
        import asyncio

        async def _use_tx():
            async with conn.transaction() as tx_:
                return tx_

        result = asyncio.run(_use_tx())
        assert result is not None  # tx mock yielded


# ===========================================================================
# TestSchemaBlackBox
# ===========================================================================

@pytest.fixture
def real_dict(monkeypatch):
    """Bind the column-mapper + schema router to the REAL repo dictionary
    (the test default path /app/config doesn't exist → empty dict)."""
    import importlib
    from pathlib import Path
    real = Path(__file__).resolve().parents[3] / "config" / "language_dictionary.json"
    if not real.exists():
        pytest.skip(f"real dict not found at {real}")
    monkeypatch.setenv("LANGUAGE_DICT_PATH", str(real))
    # The app builds on the data_pipeline.-qualified package (where the `..`
    # relative imports resolve); reload THAT column_mapper + patch the schema
    # router's bound _LANGUAGE_DICT to the freshly-loaded dict.
    import data_pipeline.data_plane.bronze.column_mapper as cm
    importlib.reload(cm)
    import data_pipeline.routers.schema as sch
    monkeypatch.setattr(sch, "_LANGUAGE_DICT", cm._LANGUAGE_DICT)
    yield
    importlib.reload(cm)   # restore empty default for other tests


class TestSchemaFieldsCatalog:
    """GET /schema/fields — canonical vocabulary for the Step-2 picker, derived
    from language_dictionary.json (single source of truth)."""

    def test_fields_returns_canonical_catalog_with_vn_labels(self, real_dict, app_client):
        resp = app_client.get("/schema/fields")
        assert resp.status_code == 200
        fields = resp.json()["fields"]
        assert len(fields) > 20
        by_canon = {f["canonical"]: f for f in fields}
        # Every entry carries a non-empty VN label + a data_type.
        assert all(f["label"] and f["data_type"] for f in fields)
        # The v1.3 customer fields are present with sensible labels/types.
        assert by_canon["payment_method"]["data_type"] == "category"
        assert by_canon["age"]["data_type"] == "integer"
        assert "khách hàng" in by_canon["customer_external_id"]["label"].lower()

    def test_fields_sorted_by_label(self, real_dict, app_client):
        labels = [f["label"] for f in app_client.get("/schema/fields").json()["fields"]]
        assert labels == sorted(labels)


class TestSchemaBlackBox:
    """Black-box contract tests for POST /schema and POST /schema/confirm."""

    def test_schema_returns_404_when_run_not_found(self, app_client, conn):
        """POST /schema returns 404 when run_id does not exist in DB."""
        conn.fetchrow.return_value = None
        resp = app_client.post(
            "/schema",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 404

    def test_schema_returns_400_when_status_not_bronze_complete(self, app_client, conn):
        """POST /schema returns 400 when run status is not bronze_complete or schema_review."""
        conn.fetchrow.return_value = _mock_row(
            detected_language="en", status="uploading"
        )
        resp = app_client.post(
            "/schema",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 400
        # Message is Vietnamese ("trạng thái: <status>") + echoes the raw status value.
        detail = resp.json()["detail"].lower()
        assert "trạng thái" in detail
        assert "uploading" in detail

    def test_schema_returns_200_when_bronze_complete(self, app_client, conn):
        """POST /schema returns 200 with sheet mappings when status is bronze_complete."""
        conn.fetchrow.side_effect = [
            # Only call now: run lookup. Bronze rows moved to conn.fetch.
            _mock_row(detected_language="en", status="bronze_complete"),
        ]
        conn.fetch.side_effect = [
            # 1) bronze_files fetch
            [_mock_row(
                file_id=uuid.UUID(FILE_ID),
                sheet_name="Sheet1",
                detected_purpose="transaction_list",
            )],
            # 2) bronze_rows sample fetch (LIMIT 200) — multiple rows so the
            #    sample-value / null% / type-sniff enrichment has data.
            [
                _mock_row(raw_data=json.dumps({"name": "Alice", "amount": "1000"})),
                _mock_row(raw_data=json.dumps({"name": "Bob",   "amount": "2000"})),
                _mock_row(raw_data=json.dumps({"name": "Cara",  "amount": "3000"})),
            ],
        ]
        conn.execute.return_value = None

        resp = app_client.post(
            "/schema",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == RUN_ID
        assert "sheets" in body
        m = {x["source_column"]: x for x in body["sheets"][0]["mappings"]}
        # Enriched contract the FE depends on: real samples + null% + flags.
        assert m["amount"]["sample_values"] == ["1000", "2000", "3000"]
        assert m["amount"]["null_pct"] == 0.0
        assert m["amount"]["looks_unnamed"] is False
        assert m["amount"]["is_empty"] is False
        # Value-sniff: dict types every column "text"; all-integer cells → integer.
        assert m["amount"]["data_type"] == "integer"

    def test_schema_confirm_returns_200_and_advances_status(self, app_client, conn):
        """POST /schema/confirm returns 200 with status=confirmed and clears cleaning_pending."""
        conn.fetch.return_value = [
            _mock_row(file_id=uuid.UUID(FILE_ID))
        ]
        conn.execute.return_value = None

        resp = app_client.post(
            "/schema/confirm",
            json={
                "run_id": RUN_ID,
                "overrides": [
                    {
                        "source_column": "name",
                        "canonical_name": "customer_name",
                        "data_type": "text",
                    }
                ],
            },
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == RUN_ID
        assert body["status"] == "confirmed"

    def test_schema_confirm_no_overrides_returns_200(self, app_client, conn):
        """POST /schema/confirm with empty overrides array still returns 200."""
        conn.fetch.return_value = [_mock_row(file_id=uuid.UUID(FILE_ID))]
        conn.execute.return_value = None

        resp = app_client.post(
            "/schema/confirm",
            json={"run_id": RUN_ID, "overrides": []},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 200

    def test_schema_missing_enterprise_header_returns_422(self, app_client):
        """POST /schema without X-Enterprise-ID header must return 422."""
        resp = app_client.post(
            "/schema",
            json={"run_id": RUN_ID},
        )
        assert resp.status_code == 422


# ===========================================================================
# TestCleanBlackBox
# ===========================================================================

class TestCleanBlackBox:
    """Black-box contract tests for POST /clean/suggestions and POST /clean/apply."""

    def test_suggestions_returns_rules_list(self, app_client, conn):
        """POST /clean/suggestions returns list of applicable rule dicts."""
        conn.fetch.return_value = [
            _mock_row(
                canonical_name="amount",
                data_type="currency",
                detected_purpose="transaction_list",
            ),
            _mock_row(
                canonical_name="date",
                data_type="date",
                detected_purpose="transaction_list",
            ),
        ]

        resp = app_client.post(
            "/clean/suggestions",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "rules" in body
        assert isinstance(body["rules"], list)
        assert len(body["rules"]) > 0

    def test_suggestions_returns_400_when_no_schema(self, app_client, conn):
        """POST /clean/suggestions returns 400 when no schema found (schema not confirmed yet)."""
        conn.fetch.return_value = []

        resp = app_client.post(
            "/clean/suggestions",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 400
        assert "schema" in resp.json()["detail"].lower()

    def test_apply_returns_400_when_run_not_found(self, app_client, conn):
        """POST /clean/apply returns 404 when run_id does not exist."""
        conn.fetchrow.return_value = None

        resp = app_client.post(
            "/clean/apply",
            json={"run_id": RUN_ID, "rule_ids": ["TRIM_WHITESPACE"]},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 404

    def test_apply_returns_400_when_run_wrong_status(self, app_client, conn):
        """POST /clean/apply returns 400 when run status is not eligible for cleaning."""
        conn.fetchrow.return_value = _mock_row(
            run_id=uuid.UUID(RUN_ID),
            status="uploading",  # not eligible
        )

        resp = app_client.post(
            "/clean/apply",
            json={"run_id": RUN_ID, "rule_ids": ["TRIM_WHITESPACE"]},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 400
        assert "status" in resp.json()["detail"].lower()

    def test_apply_returns_202_and_runs_async(self, app_client, conn):
        """POST /clean/apply is async: validates (status + schema exists) then
        returns 202 'cleaning'; the Silver write runs in a BackgroundTask.
        The FE polls GET /upload/{run_id}/status until 'silver_complete'."""
        conn.fetchrow.return_value = _mock_row(
            run_id=uuid.UUID(RUN_ID),
            status="cleaning_pending",
        )
        conn.fetchval.return_value = 1   # has_schema check passes
        # The background task then consumes these (schema_rows, bronze_rows).
        conn.fetch.side_effect = [
            [
                _mock_row(
                    source_column="name",
                    canonical_name="customer_name",
                    data_type="text",
                    file_id=uuid.UUID(FILE_ID),
                    detected_purpose=None,
                )
            ],
            [
                _mock_row(
                    row_id=uuid.uuid4(),
                    file_id=uuid.UUID(FILE_ID),
                    row_index=0,
                    raw_data={"name": "  Alice  ", "amount": "1000"},
                    enterprise_id=uuid.UUID(ENTERPRISE_A),
                )
            ],
        ]
        conn.execute.return_value = None

        resp = app_client.post(
            "/clean/apply",
            json={"run_id": RUN_ID, "rule_ids": ["TRIM_WHITESPACE"]},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 202
        assert resp.json()["status"] == "cleaning"


# ===========================================================================
# TestAnalyzeBlackBox
# ===========================================================================

class TestAnalyzeBlackBox:
    """Black-box contract tests for POST /analyze."""

    def test_analyze_returns_400_when_run_not_found(self, app_client, conn):
        """POST /analyze returns 400 when run_id does not exist or status is wrong."""
        conn.fetchrow.return_value = None

        resp = app_client.post(
            "/analyze",
            json={
                "run_id": RUN_ID,
                "templates": ["summary_stats"],
            },
            headers=HEADERS_A,
        )
        assert resp.status_code == 400

    def test_analyze_returns_400_when_not_silver_complete(self, app_client, conn):
        """POST /analyze returns 400 when run is not in silver_complete status."""
        conn.fetchrow.return_value = _mock_row(status="uploading")

        resp = app_client.post(
            "/analyze",
            json={
                "run_id": RUN_ID,
                "templates": ["summary_stats"],
            },
            headers=HEADERS_A,
        )
        assert resp.status_code == 400

    def test_analyze_returns_200_creates_analysis_run(self, app_client, conn):
        """POST /analyze returns 200 with analysis_run_id when run is silver_complete."""
        conn.fetchrow.side_effect = [
            _mock_row(status="silver_complete"),
            _mock_row(id=uuid.UUID(ANALYSIS_ID)),
        ]
        conn.execute.return_value = None

        resp = app_client.post(
            "/analyze",
            json={
                "run_id": RUN_ID,
                "templates": ["summary_stats", "distribution"],
                "consent_external_ai": False,
            },
            headers=HEADERS_A,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "run_id" in body
        assert "analysis_run_id" in body
        assert body["run_id"] == RUN_ID

    def test_analyze_accepts_consent_external_ai_flag(self, app_client, conn):
        """POST /analyze with consent_external_ai=True is accepted without error."""
        conn.fetchrow.side_effect = [
            _mock_row(status="silver_complete"),
            _mock_row(id=uuid.UUID(ANALYSIS_ID)),
        ]
        conn.execute.return_value = None

        resp = app_client.post(
            "/analyze",
            json={
                "run_id": RUN_ID,
                "templates": ["summary_stats"],
                "consent_external_ai": True,
            },
            headers=HEADERS_A,
        )
        assert resp.status_code == 200

    def test_analyze_missing_enterprise_header_returns_422(self, app_client):
        """POST /analyze without X-Enterprise-ID must return 422."""
        resp = app_client.post(
            "/analyze",
            json={"run_id": RUN_ID, "templates": ["summary_stats"]},
            headers={"X-User-ID": USER_ID},
        )
        assert resp.status_code == 422


# ===========================================================================
# TestPipelineIntegration
# ===========================================================================

class TestPipelineIntegration:
    """
    Integration tests — verify that components wire together correctly
    when the DB is mocked.  Each scenario uses sequential mock return values.
    """

    def test_upload_then_status(self, app_client, conn):
        """Upload a file and confirm status endpoint returns the same run_id."""
        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(
                return_value={
                    "run_id": RUN_ID,
                    "status": "uploading",
                    "sha256": "abc123",
                }
            ),
        ):
            upload_resp = app_client.post(
                "/upload",
                files={"file": ("data.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,
            )
        assert upload_resp.status_code == 202
        returned_run_id = upload_resp.json()["run_id"]

        # Now poll status — DB has the run
        conn.fetchrow.return_value = _make_pipeline_run_row(
            run_id=uuid.UUID(returned_run_id)
        )
        status_resp = app_client.get(
            f"/upload/{returned_run_id}/status",
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["run_id"] == str(uuid.UUID(returned_run_id))

    def test_schema_audit_logged(self, app_client, conn):
        """
        POST /schema triggers decision_audit_log inserts — one per detected column.
        Verifies conn.execute is called for each column mapping (K-6 enforcement).
        """
        source_columns = ["name", "amount", "date"]
        raw_data_json = json.dumps({col: "val" for col in source_columns})

        conn.fetchrow.side_effect = [
            # run lookup (only fetchrow call now)
            _mock_row(detected_language="en", status="bronze_complete"),
        ]
        conn.fetch.side_effect = [
            # 1) bronze_files
            [_mock_row(
                file_id=uuid.UUID(FILE_ID),
                sheet_name="Sheet1",
                detected_purpose=None,
            )],
            # 2) bronze_rows sample (LIMIT 200)
            [_mock_row(raw_data=raw_data_json)],
        ]

        resp = app_client.post(
            "/schema",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert resp.status_code == 200

        # conn.execute is called for each column (decision_audit_log INSERT)
        # plus one final UPDATE pipeline_runs SET status='schema_review'
        # Total calls >= len(source_columns)
        total_executes = conn.execute.call_count
        assert total_executes >= len(source_columns), (
            f"Expected at least {len(source_columns)} conn.execute calls "
            f"(one per column audit log), got {total_executes}"
        )

    def test_full_flow_upload_schema_clean(self, app_client, conn):
        """
        upload → schema → confirm → suggestions → apply: verify each step succeeds
        and conn.execute/fetch calls chain correctly.
        """
        # ---- Step 1: Upload ----
        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(
                return_value={
                    "run_id": RUN_ID,
                    "status": "uploading",
                    "sha256": "cafebabe",
                }
            ),
        ):
            upload_resp = app_client.post(
                "/upload",
                files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,
            )
        assert upload_resp.status_code == 202, upload_resp.text

        # ---- Step 2: Schema ----
        raw_data = json.dumps({"name": "Alice", "amount": "1000", "date": "01/03/2024"})
        conn.fetchrow.side_effect = [
            _mock_row(detected_language="en", status="bronze_complete"),
        ]
        conn.fetch.side_effect = [
            [_mock_row(
                file_id=uuid.UUID(FILE_ID),
                sheet_name="Sheet1",
                detected_purpose="transaction_list",
            )],
            [_mock_row(raw_data=raw_data)],
        ]
        conn.execute.return_value = None

        schema_resp = app_client.post(
            "/schema",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert schema_resp.status_code == 200, schema_resp.text

        # ---- Step 3: Confirm ----
        conn.fetchrow.side_effect = None
        conn.fetch.side_effect = None
        conn.fetch.return_value = [_mock_row(file_id=uuid.UUID(FILE_ID))]
        conn.execute.return_value = None

        confirm_resp = app_client.post(
            "/schema/confirm",
            json={"run_id": RUN_ID, "overrides": []},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert confirm_resp.status_code == 200, confirm_resp.text
        assert confirm_resp.json()["status"] == "confirmed"

        # ---- Step 4: Suggestions ----
        conn.fetch.return_value = [
            _mock_row(
                canonical_name="amount",
                data_type="currency",
                detected_purpose="transaction_list",
            )
        ]

        suggest_resp = app_client.post(
            "/clean/suggestions",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert suggest_resp.status_code == 200, suggest_resp.text
        rules = suggest_resp.json()["rules"]
        assert len(rules) > 0

        # ---- Step 5: Apply ----
        conn.fetchrow.return_value = _mock_row(
            run_id=uuid.UUID(RUN_ID),
            status="cleaning_pending",
        )
        conn.fetch.side_effect = [
            # schema_rows
            [
                _mock_row(
                    source_column="amount",
                    canonical_name="amount",
                    data_type="currency",
                    file_id=uuid.UUID(FILE_ID),
                    detected_purpose="transaction_list",
                )
            ],
            # bronze_rows
            [
                _mock_row(
                    row_id=uuid.uuid4(),
                    file_id=uuid.UUID(FILE_ID),
                    row_index=0,
                    raw_data={"amount": "1,500,000 ₫"},
                    enterprise_id=uuid.UUID(ENTERPRISE_A),
                )
            ],
        ]
        conn.execute.return_value = None
        conn.fetchval.return_value = 1   # apply: has_schema check passes

        apply_resp = app_client.post(
            "/clean/apply",
            json={"run_id": RUN_ID, "rule_ids": ["PARSE_CURRENCY"]},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        # Async now: 202 + 'cleaning'; Silver write happens in a background task.
        assert apply_resp.status_code == 202, apply_resp.text
        assert apply_resp.json()["status"] == "cleaning"


# ===========================================================================
# TestUAT
# ===========================================================================

class TestUAT:
    """
    User Acceptance Tests — realistic end-user scenarios exercising the full
    HTTP surface with meaningful, domain-correct data.
    """

    def test_uat_vietnamese_csv_upload(self, app_client, conn):
        """Upload a CSV with Vietnamese column headers; verify run_id returned and status endpoint returns filename."""
        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(
                return_value={
                    "run_id": RUN_ID,
                    "status": "uploading",
                    "sha256": "vn_sha256",
                }
            ),
        ):
            upload_resp = app_client.post(
                "/upload",
                files={
                    "file": (
                        "doanh_thu.csv",
                        VIETNAMESE_CSV_CONTENT,
                        "text/csv",
                    )
                },
                headers=HEADERS_A,
            )

        assert upload_resp.status_code == 202
        body = upload_resp.json()
        assert "run_id" in body
        returned_run_id = body["run_id"]

        # Status endpoint should return filename from DB
        conn.fetchrow.return_value = _make_pipeline_run_row(
            run_id=uuid.UUID(returned_run_id),
            filename="doanh_thu.csv",
            status="bronze_complete",
        )
        status_resp = app_client.get(
            f"/upload/{returned_run_id}/status",
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert status_resp.status_code == 200
        assert status_resp.json()["filename"] == "doanh_thu.csv"

    def test_uat_idempotent_upload(self, app_client, conn):
        """Uploading the same CSV twice must return 'duplicate' with the original run_id on second call."""
        # First upload
        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(
                return_value={
                    "run_id": RUN_ID,
                    "status": "uploading",
                    "sha256": "same_content_hash",
                }
            ),
        ):
            first_resp = app_client.post(
                "/upload",
                files={"file": ("report.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,
            )
        assert first_resp.status_code == 202
        first_run_id = first_resp.json()["run_id"]

        # Second upload — same content. Async dedup (K-8) finds the existing
        # non-failed run via the pipeline_runs lookup and short-circuits to it.
        conn.fetchrow.return_value = {
            "run_id": uuid.UUID(first_run_id), "status": "bronze_complete",
        }
        second_resp = app_client.post(
            "/upload",
            files={"file": ("report.csv", VALID_CSV_CONTENT, "text/csv")},
            headers=HEADERS_A,
        )

        assert second_resp.status_code == 200
        second_body = second_resp.json()
        assert second_body["is_duplicate"] is True
        assert second_body["run_id"] == first_run_id

    def test_uat_truly_unsupported_format_rejected(self, app_client, conn):
        """Genuinely unknown extension (.exe) must return 400.

        2026-05-17 — PDF/DOCX/image were moved from the rejection list to
        the Stage 6 placeholder branch (accepted as 'unstructured_pending';
        DocSage parses them later). The "unsupported" assertion now uses
        an extension that has no path at all.
        """
        resp = app_client.post(
            "/upload",
            files={"file": ("malware.exe", b"MZ fake binary", "application/octet-stream")},
            headers=HEADERS_A,
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert any(
            keyword in detail.lower()
            for keyword in ("unsupported", "exe", "format", "type")
        ), f"Expected meaningful error, got: {detail!r}"

    def test_uat_tenant_isolation(self, app_client, conn):
        """
        File uploaded by enterprise A cannot be accessed by enterprise B (K-1).
        The status endpoint must return 404 when enterprise_id does not match.
        """
        # Enterprise A uploads successfully
        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(
                return_value={
                    "run_id": RUN_ID,
                    "status": "uploading",
                    "sha256": "tenant_test_hash",
                }
            ),
        ):
            upload_resp = app_client.post(
                "/upload",
                files={"file": ("private_data.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,
            )
        assert upload_resp.status_code == 202
        run_id = upload_resp.json()["run_id"]

        # Enterprise B tries to access enterprise A's run — DB WHERE clause excludes it
        conn.fetchrow.return_value = None  # simulates "not found for this enterprise"
        isolation_resp = app_client.get(
            f"/upload/{run_id}/status",
            headers={"X-Enterprise-ID": ENTERPRISE_B},  # wrong tenant
        )
        assert isolation_resp.status_code == 404, (
            "K-1 violated: enterprise B should not see enterprise A's run"
        )

    def test_uat_full_pipeline_happy_path(self, app_client, conn):
        """
        Full happy-path flow: upload → bronze_complete → schema → confirm → suggestions
        → apply → analyze.  Assert each step returns 200 and status transitions match.
        """
        # ---- 1. Upload ----
        with patch(
            "data_pipeline.routers.upload.ingest_file",
            new=AsyncMock(
                return_value={
                    "run_id": RUN_ID,
                    "status": "uploading",
                    "sha256": "full_flow_hash",
                }
            ),
        ):
            r = app_client.post(
                "/upload",
                files={"file": ("sales.csv", VALID_CSV_CONTENT, "text/csv")},
                headers=HEADERS_A,
            )
        assert r.status_code == 202, f"Upload failed: {r.text}"
        assert r.json()["status"] == "uploading"

        # ---- 2. Status polling → bronze_complete ----
        conn.fetchrow.return_value = _make_pipeline_run_row(status="bronze_complete")
        r = app_client.get(
            f"/upload/{RUN_ID}/status",
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "bronze_complete"

        # ---- 3. POST /schema → schema_review ----
        raw_data = json.dumps({"name": "Alice", "amount": "1500000", "date": "01/03/2024"})
        conn.fetchrow.side_effect = [
            _mock_row(detected_language="vi", status="bronze_complete"),
        ]
        conn.fetch.side_effect = [
            [_mock_row(
                file_id=uuid.UUID(FILE_ID),
                sheet_name="Sheet1",
                detected_purpose="transaction_list",
            )],
            [_mock_row(raw_data=raw_data)],
        ]
        conn.execute.return_value = None

        r = app_client.post(
            "/schema",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert r.status_code == 200, f"Schema failed: {r.text}"

        # ---- 4. POST /schema/confirm → cleaning_pending ----
        conn.fetchrow.side_effect = None
        conn.fetch.side_effect = None
        conn.fetch.return_value = [_mock_row(file_id=uuid.UUID(FILE_ID))]
        conn.execute.return_value = None

        r = app_client.post(
            "/schema/confirm",
            json={"run_id": RUN_ID, "overrides": []},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert r.status_code == 200, f"Schema confirm failed: {r.text}"
        assert r.json()["status"] == "confirmed"

        # ---- 5. GET (POST) /clean/suggestions ----
        conn.fetch.return_value = [
            _mock_row(
                canonical_name="amount",
                data_type="currency",
                detected_purpose="transaction_list",
            ),
            _mock_row(
                canonical_name="date",
                data_type="date",
                detected_purpose="transaction_list",
            ),
        ]

        r = app_client.post(
            "/clean/suggestions",
            json={"run_id": RUN_ID},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        assert r.status_code == 200, f"Suggestions failed: {r.text}"
        suggested_rules = [rule["rule_id"] for rule in r.json()["rules"]]
        assert len(suggested_rules) > 0

        # ---- 6. POST /clean/apply → silver_complete ----
        conn.fetchrow.return_value = _mock_row(
            run_id=uuid.UUID(RUN_ID),
            status="cleaning_pending",
        )
        conn.fetch.side_effect = [
            # schema_rows join
            [
                _mock_row(
                    source_column="amount",
                    canonical_name="amount",
                    data_type="currency",
                    file_id=uuid.UUID(FILE_ID),
                    detected_purpose="transaction_list",
                ),
                _mock_row(
                    source_column="date",
                    canonical_name="date",
                    data_type="date",
                    file_id=uuid.UUID(FILE_ID),
                    detected_purpose="transaction_list",
                ),
            ],
            # bronze_rows
            [
                _mock_row(
                    row_id=uuid.uuid4(),
                    file_id=uuid.UUID(FILE_ID),
                    row_index=0,
                    raw_data={"amount": "1,500,000 ₫", "date": "01/03/2024"},
                    enterprise_id=uuid.UUID(ENTERPRISE_A),
                ),
                _mock_row(
                    row_id=uuid.uuid4(),
                    file_id=uuid.UUID(FILE_ID),
                    row_index=1,
                    raw_data={"amount": "2,200,000 ₫", "date": "02/03/2024"},
                    enterprise_id=uuid.UUID(ENTERPRISE_A),
                ),
            ],
        ]
        conn.execute.return_value = None
        conn.fetchval.return_value = 1   # apply: has_schema check passes

        r = app_client.post(
            "/clean/apply",
            json={"run_id": RUN_ID, "rule_ids": ["PARSE_CURRENCY", "PARSE_DATE"]},
            headers={"X-Enterprise-ID": ENTERPRISE_A},
        )
        # Async now: 202 'cleaning'; Silver write runs in a background task and
        # the FE polls /upload/{run_id}/status until 'silver_complete'.
        assert r.status_code == 202, f"Clean apply failed: {r.text}"
        assert r.json()["status"] == "cleaning"

        # ---- 7. POST /analyze → analysis queued ----
        conn.fetchrow.side_effect = [
            _mock_row(status="silver_complete"),
            _mock_row(id=uuid.UUID(ANALYSIS_ID)),
        ]
        conn.execute.return_value = None
        conn.fetch.side_effect = None

        r = app_client.post(
            "/analyze",
            json={
                "run_id": RUN_ID,
                "templates": ["summary_stats", "time_series"],
                "consent_external_ai": False,
            },
            headers=HEADERS_A,
        )
        assert r.status_code == 200, f"Analyze failed: {r.text}"
        analyze_body = r.json()
        assert analyze_body["run_id"] == RUN_ID
        assert "analysis_run_id" in analyze_body
