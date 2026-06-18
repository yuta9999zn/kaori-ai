# EU AI Act K-26 Post-market Monitoring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** EU AI Act post-market monitoring (Art 72) + serious-incident register (Art 73): record incidents with a 4-level severity and surface a single-pane monitoring summary, mirroring the `/admin/dlq` console. ADR-0041, invariant K-26.

**Architecture:** A new admin-gated, tenant-scoped router `routers/incidents.py` over a new `ai_incident` table. Record-only this slice (a reusable `record_incident()` helper is the single write path for future auto-hooks). The summary endpoint aggregates ai-orchestrator-native signals (open incidents, recent failed runs, recent low-confidence decisions) — no Layer-2 dependency.

**Tech Stack:** Python FastAPI (ai-orchestrator port 8093) · asyncpg + RLS (`acquire_for_tenant`) · pytest.

**Branch:** `feat/eu-ai-act-k26-monitoring` (off `main`, independent of K-22/K-23/K-24).

**Invariants:** K-1 RLS, K-6 audit, K-12 tenant+role from headers, K-14 RFC 7807, K-21 uuidv7/ulid.

> **⚠️ Migration number = 136.** This branch sees max mig 133, but open PRs #347 (mig 134) and #348 (mig 135) already claim 134/135. Use **136** to avoid a merge collision. (A Flyway gap is harmless; a duplicate number is fatal.)

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `infrastructure/postgres/migrations/136_ai_incident.sql` | `ai_incident` register table (K-21, RLS, 4-level severity) | Create |
| `scripts/test_migration_136_shape.py` | shape test | Create |
| `services/ai-orchestrator/reasoning/incident_rules.py` | pure `validate_severity`/`validate_status` + constant tuples | Create |
| `services/ai-orchestrator/tests/test_incident_rules.py` | unit tests | Create |
| `services/ai-orchestrator/routers/incidents.py` | `record_incident()` + POST/GET/PATCH/summary (admin-gated) | Create |
| `services/ai-orchestrator/tests/test_incidents_router.py` | router tests | Create |
| `services/ai-orchestrator/main.py` | mount the router | Modify |
| OpenAPI spec + RouteConfigTest | drift artefacts | Modify |

---

## Task 1: Migration 136 — `ai_incident`

**Files:**
- Create: `infrastructure/postgres/migrations/136_ai_incident.sql`
- Test: `scripts/test_migration_136_shape.py`

- [ ] **Step 1: Write the migration.** Create `infrastructure/postgres/migrations/136_ai_incident.sql`:

```sql
-- =====================================================================
-- 136_ai_incident.sql — EU AI Act Layer 3 (ADR-0041, K-26)
--
-- Post-market monitoring (Art 72) + serious-incident register (Art 73).
-- Append-and-update register: one row per incident, lifecycle via `status`.
-- severity 'serious' = Art 73-reportable.
--
-- Number 136 (NOT 134/135): those are claimed by open PRs #347 (134) /
-- #348 (135). Gap-tolerant Flyway; avoids a merge collision.
--
-- K-21 (gen_uuid_v7 PK + gen_ulid external) + RLS K-1 (mirror mig 130).
-- Additive: new table only.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ai_incident (
    incident_id    UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    public_ref     TEXT         NOT NULL DEFAULT gen_ulid(),         -- K-21 external
    enterprise_id  UUID         NOT NULL,

    incident_type  VARCHAR(48)  NOT NULL,   -- wrong_decision | data_leak | model_drift | pipeline_failure | other
    severity       VARCHAR(12)  NOT NULL,   -- low | medium | high | serious
    status         VARCHAR(16)  NOT NULL DEFAULT 'open',  -- open | investigating | resolved
    title          VARCHAR(200) NOT NULL,
    description    TEXT,

    decision_id    UUID,
    run_id         UUID,
    workflow_id    UUID,
    detail         JSONB        NOT NULL DEFAULT '{}'::jsonb,

    reported_by    UUID,
    reported_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ,

    CONSTRAINT chk_incident_severity CHECK (severity IN ('low','medium','high','serious')),
    CONSTRAINT chk_incident_status   CHECK (status IN ('open','investigating','resolved')),
    CONSTRAINT uq_incident_public    UNIQUE (public_ref)
);

CREATE INDEX IF NOT EXISTS idx_incident_open
    ON ai_incident(enterprise_id, status, reported_at DESC);
CREATE INDEX IF NOT EXISTS idx_incident_severity
    ON ai_incident(enterprise_id, severity);

-- ─── RLS (K-1) — mirror mig 130 isolation ────────────────────────────
ALTER TABLE ai_incident ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_incident ON ai_incident;
CREATE POLICY isolation_incident ON ai_incident
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ai_incident TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE ai_incident IS
    'ADR-0041 K-26 — EU AI Act post-market monitoring (Art 72) + serious-incident '
    'register (Art 73). severity=serious is reportable. RLS K-1 per mig 130.';

COMMIT;
```

- [ ] **Step 2: Write the shape test.** Create `scripts/test_migration_136_shape.py`:

```python
"""Shape test for migration 136 (ai_incident) — no DB."""
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "infrastructure/postgres/migrations/136_ai_incident.sql"


def test_migration_136_exists():
    assert MIG.exists(), f"missing {MIG}"


def test_k21_id_strategy():
    sql = MIG.read_text(encoding="utf-8")
    assert "gen_uuid_v7()" in sql
    assert "gen_ulid()" in sql


def test_severity_and_status_constraints():
    sql = MIG.read_text(encoding="utf-8")
    for s in ("low", "medium", "high", "serious"):
        assert s in sql, f"severity {s} missing"
    assert "chk_incident_severity" in sql
    assert "chk_incident_status" in sql


def test_rls_enabled():
    sql = MIG.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "isolation_incident" in sql
    assert "app.current_enterprise_id" in sql


def test_grant_app_role():
    sql = MIG.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ai_incident TO kaori_app" in sql
```

- [ ] **Step 3: Run the shape test.** Run: `python -m pytest scripts/test_migration_136_shape.py -v` — Expected: 5 passed.

- [ ] **Step 4: Confirm 136 is free + not colliding.** Run `ls infrastructure/postgres/migrations/13*.sql` — confirm no `136_*` pre-exists and max on this branch is 133 (134/135 belong to open PRs, intentionally skipped here).

- [ ] **Step 5: Commit.**
```bash
git add infrastructure/postgres/migrations/136_ai_incident.sql scripts/test_migration_136_shape.py
git commit -m "feat(compliance): mig 136 ai_incident register (EU AI Act K-26)"
```

---

## Task 2: Pure incident rules

**Files:**
- Create: `services/ai-orchestrator/reasoning/incident_rules.py`
- Test: `services/ai-orchestrator/tests/test_incident_rules.py`

- [ ] **Step 1: Write the failing test.** Create `services/ai-orchestrator/tests/test_incident_rules.py`:

```python
import pytest
from ai_orchestrator.reasoning import incident_rules as ir


def test_severities_tuple():
    assert ir.SEVERITIES == ("low", "medium", "high", "serious")


def test_statuses_tuple():
    assert ir.INCIDENT_STATUSES == ("open", "investigating", "resolved")


def test_validate_severity_normalises():
    assert ir.validate_severity(" SERIOUS ") == "serious"
    with pytest.raises(ValueError):
        ir.validate_severity("catastrophic")


def test_validate_status_normalises():
    assert ir.validate_status(" Resolved ") == "resolved"
    with pytest.raises(ValueError):
        ir.validate_status("closed")
```

- [ ] **Step 2: Run to verify it fails.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_incident_rules.py -v` — Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement.** Create `services/ai-orchestrator/reasoning/incident_rules.py`:

```python
"""Pure EU AI Act K-26 incident vocabulary + validation (ADR-0041 Layer 3).

No I/O. Severity 'serious' = Art 73-reportable. Used by the incidents router
to validate input before the DB write.
"""
from __future__ import annotations

SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "serious")
INCIDENT_STATUSES: tuple[str, ...] = ("open", "investigating", "resolved")


def validate_severity(value: str) -> str:
    norm = (value or "").strip().lower()
    if norm not in SEVERITIES:
        raise ValueError(f"unknown severity: {value!r} (expected one of {SEVERITIES})")
    return norm


def validate_status(value: str) -> str:
    norm = (value or "").strip().lower()
    if norm not in INCIDENT_STATUSES:
        raise ValueError(f"unknown status: {value!r} (expected one of {INCIDENT_STATUSES})")
    return norm
```

- [ ] **Step 4: Run to verify it passes.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_incident_rules.py -v` — Expected: 4 passed.

- [ ] **Step 5: Commit.**
```bash
git add services/ai-orchestrator/reasoning/incident_rules.py services/ai-orchestrator/tests/test_incident_rules.py
git commit -m "feat(compliance): pure K-26 incident severity/status validation"
```

---

## Task 3: `incidents.py` router + `record_incident` helper + mount

**Files:**
- Create: `services/ai-orchestrator/routers/incidents.py`
- Modify: `services/ai-orchestrator/main.py`
- Test: `services/ai-orchestrator/tests/test_incidents_router.py`

**Context:** Mirror `routers/dlq_console.py` for the admin gate + tenant pattern: `_require_admin(x_user_role)` raising 403 unless role in {SUPER_ADMIN, ADMIN}; `acquire_for_tenant(x_enterprise_id)`; header `X-Enterprise-ID` / `X-User-Role` / `X-User-ID`. `record_ai_call` is `from ..shared.ai_governance import record_ai_call` (async, keyword-only). For the summary, `ai_decision_audit` has `enterprise_id, confidence, created_at`; `workflow_runs` has `status` + a creation timestamp — confirm its exact name (`created_at` or `started_at`) by reading the table's migration / an existing query, and use it.

- [ ] **Step 1: Write the failing test.** Create `services/ai-orchestrator/tests/test_incidents_router.py`, mirroring the fake-conn + TestClient + monkeypatch pattern from `tests/test_compliance_risk_router.py` (or `test_workflow_run_stop.py`). Patch `ai_orchestrator.routers.incidents.record_ai_call` with an AsyncMock. Behaviours:

```
1. POST /admin/incidents {incident_type:"wrong_decision", severity:"serious", title:"x"} with X-User-Role=ADMIN
   -> 201; response severity=="serious", status=="open"; INSERT into ai_incident issued;
      record_ai_call awaited once with task_kind="incident_recorded".
2. POST with severity="catastrophic" -> 422.
3. POST with X-User-Role=VIEWER -> 403 (admin gate).
4. GET /admin/incidents?status=open&severity=serious (ADMIN) -> 200, returns the fake rows.
5. PATCH /admin/incidents/{id} {status:"resolved"} (ADMIN) -> 200; UPDATE sets status + resolved_at.
6. PATCH with status="closed" -> 422.
7. GET /admin/incidents/summary (ADMIN) -> 200 with keys open_incidents_by_severity,
   failed_runs_recent, low_confidence_decisions_recent, window_days, low_confidence_threshold.
8. POST without X-Enterprise-ID -> 422.
```

Make the fake conn dispatch by SQL: INSERT...ai_incident returns the canned row; SELECT...ai_incident returns list/row; the three summary SELECTs return canned counts (fetch/fetchval).

- [ ] **Step 2: Run to verify it fails.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_incidents_router.py -v` — Expected: FAIL (ModuleNotFoundError: routers.incidents).

- [ ] **Step 3: Write the router.** Create `services/ai-orchestrator/routers/incidents.py`:

```python
"""EU AI Act post-market monitoring + incident register — Layer 3 (ADR-0041, K-26).

Admin-gated (SUPER_ADMIN/ADMIN), tenant-scoped (K-1/K-12). Record-only this
slice: record_incident() is the single write path future auto-hooks call.
Namespace /admin/incidents — same edge reachability as /admin/dlq.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant
from ..shared.ai_governance import record_ai_call
from ..reasoning import incident_rules as ir

log = structlog.get_logger()
router = APIRouter()


def _require_admin(role: Optional[str]) -> None:
    if role not in ("SUPER_ADMIN", "ADMIN"):
        raise HTTPException(
            status_code=403,
            detail=f"incident console requires SUPER_ADMIN or ADMIN role; got {role!r}",
        )


class IncidentIn(BaseModel):
    incident_type: str = Field(..., max_length=48)
    severity:      str
    title:         str = Field(..., max_length=200)
    description:   Optional[str] = None
    decision_id:   Optional[UUID] = None
    run_id:        Optional[UUID] = None
    workflow_id:   Optional[UUID] = None
    detail:        Optional[dict] = None


class IncidentPatch(BaseModel):
    status:          str
    resolution_note: Optional[str] = Field(default=None, max_length=2000)


class IncidentOut(BaseModel):
    incident_id:   str
    public_ref:    str
    incident_type: str
    severity:      str
    status:        str
    title:         str
    description:   Optional[str]
    decision_id:   Optional[str]
    run_id:        Optional[str]
    workflow_id:   Optional[str]
    reported_at:   Optional[str]
    resolved_at:   Optional[str]


def _row_to_out(row) -> IncidentOut:
    def _s(v):
        return str(v) if v else None
    return IncidentOut(
        incident_id=str(row["incident_id"]),
        public_ref=row["public_ref"],
        incident_type=row["incident_type"],
        severity=row["severity"],
        status=row["status"],
        title=row["title"],
        description=row["description"],
        decision_id=_s(row["decision_id"]),
        run_id=_s(row["run_id"]),
        workflow_id=_s(row["workflow_id"]),
        reported_at=row["reported_at"].isoformat() if row["reported_at"] else None,
        resolved_at=row["resolved_at"].isoformat() if row["resolved_at"] else None,
    )


async def record_incident(
    *,
    enterprise_id: UUID,
    incident_type: str,
    severity: str,
    title: str,
    description: Optional[str] = None,
    decision_id: Optional[UUID] = None,
    run_id: Optional[UUID] = None,
    workflow_id: Optional[UUID] = None,
    detail: Optional[dict] = None,
    reported_by: Optional[UUID] = None,
):
    """Single write path for K-26 incidents. Validates severity, inserts the
    row, audits (K-6). Returns the new row record."""
    sev = ir.validate_severity(severity)
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO ai_incident
                   (enterprise_id, incident_type, severity, title, description,
                    decision_id, run_id, workflow_id, detail, reported_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
               RETURNING incident_id, public_ref, incident_type, severity, status,
                         title, description, decision_id, run_id, workflow_id,
                         reported_at, resolved_at""",
            enterprise_id, incident_type, sev, title, description,
            decision_id, run_id, workflow_id, json.dumps(detail or {}), reported_by,
        )
    try:
        await record_ai_call(
            enterprise_id=enterprise_id, task_kind="incident_recorded",
            model_version="rules-only", model_provider="kaori-compliance",
            prompt=f"incident|{incident_type}|sev={sev}|{title}",
            output=json.dumps({"severity": sev, "type": incident_type}),
            confidence=None,
        )
    except Exception as e:  # noqa: BLE001 — audit must not break recording
        log.warning("incident.audit_failed", error=str(e))
    return row


@router.post("/admin/incidents", response_model=IncidentOut, status_code=201)
async def create_incident(
    body: IncidentIn,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    _require_admin(x_user_role)
    try:
        ir.validate_severity(body.severity)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid severity: {body.severity}")
    row = await record_incident(
        enterprise_id=x_enterprise_id, incident_type=body.incident_type,
        severity=body.severity, title=body.title, description=body.description,
        decision_id=body.decision_id, run_id=body.run_id, workflow_id=body.workflow_id,
        detail=body.detail, reported_by=x_user_id,
    )
    return _row_to_out(row)


@router.get("/admin/incidents", response_model=list[IncidentOut])
async def list_incidents(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
):
    _require_admin(x_user_role)
    clauses, params = [], []
    if status:
        params.append(ir.validate_status(status)); clauses.append(f"status = ${len(params)}")
    if severity:
        params.append(ir.validate_severity(severity)); clauses.append(f"severity = ${len(params)}")
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            f"""SELECT incident_id, public_ref, incident_type, severity, status,
                       title, description, decision_id, run_id, workflow_id,
                       reported_at, resolved_at
                FROM ai_incident{where}
                ORDER BY reported_at DESC LIMIT ${len(params)}""",
            *params,
        )
    return [_row_to_out(r) for r in rows]


@router.patch("/admin/incidents/{incident_id}", response_model=IncidentOut)
async def update_incident(
    body: IncidentPatch,
    incident_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
):
    _require_admin(x_user_role)
    try:
        new_status = ir.validate_status(body.status)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid status: {body.status}")
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE ai_incident
                  SET status = $2,
                      resolved_at = CASE WHEN $2 = 'resolved' THEN NOW() ELSE resolved_at END,
                      detail = detail || $3::jsonb
                WHERE incident_id = $1
              RETURNING incident_id, public_ref, incident_type, severity, status,
                        title, description, decision_id, run_id, workflow_id,
                        reported_at, resolved_at""",
            incident_id, new_status,
            json.dumps({"resolution_note": body.resolution_note} if body.resolution_note else {}),
        )
    if row is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return _row_to_out(row)


@router.get("/admin/incidents/summary")
async def incidents_summary(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    window_days: int = Query(7, ge=1, le=90),
    low_confidence_threshold: float = Query(0.5, ge=0.0, le=1.0),
):
    """Art 72 monitoring single-pane: open incidents by severity + recent
    failed runs + recent low-confidence decisions."""
    _require_admin(x_user_role)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sev_rows = await conn.fetch(
            """SELECT severity, COUNT(*) AS n FROM ai_incident
               WHERE status <> 'resolved' GROUP BY severity""",
        )
        failed_runs = await conn.fetchval(
            f"""SELECT COUNT(*) FROM workflow_runs
                WHERE status = 'failed'
                  AND created_at >= NOW() - ($1 || ' days')::interval""",
            window_days,
        )
        low_conf = await conn.fetchval(
            f"""SELECT COUNT(*) FROM ai_decision_audit
                WHERE confidence IS NOT NULL AND confidence < $1
                  AND created_at >= NOW() - ($2 || ' days')::interval""",
            low_confidence_threshold, window_days,
        )
    return {
        "open_incidents_by_severity": {r["severity"]: int(r["n"]) for r in sev_rows},
        "failed_runs_recent": int(failed_runs or 0),
        "low_confidence_decisions_recent": int(low_conf or 0),
        "window_days": window_days,
        "low_confidence_threshold": low_confidence_threshold,
    }
```

(Verify the `workflow_runs` timestamp column is `created_at`; if it's `started_at`/`created`, adjust the summary SQL. Confirm `ai_decision_audit` has `created_at` + `confidence` — it does per `shared/ai_governance.py`. If `_fetch`/`fetchval` interval-cast syntax differs from repo norms, match an existing time-window query.)

- [ ] **Step 4: Mount in main.py.** In `services/ai-orchestrator/main.py`: add `incidents` to the `from .routers import ...` list (line 27) and, after the dlq_console include (`app.include_router(dlq_console.router, tags=["DLQ Console"])`), add:
```python
app.include_router(incidents.router, tags=["Incidents (EU AI Act, ADR-0041)"])
```

- [ ] **Step 5: Run the test.** Run: `cd services/ai-orchestrator && python -m pytest tests/test_incidents_router.py -v` — Expected: all pass.

- [ ] **Step 6: Regression.** Run: `cd services/ai-orchestrator && python -m pytest tests/ -k "incident or dlq or admin" -q` — Expected: no new failures.

- [ ] **Step 7: Commit.**
```bash
git add services/ai-orchestrator/routers/incidents.py services/ai-orchestrator/main.py services/ai-orchestrator/tests/test_incidents_router.py
git commit -m "feat(compliance): incident register + monitoring summary router (K-26)"
```

---

## Task 4: Drift artefacts

- [ ] **Step 1: OpenAPI regen.** Run: `cd D:\Kaori System && python scripts/dump_openapi.py orchestrator`. Confirm `docs/api-specs/orchestrator.openapi.json` now contains `/admin/incidents` (+ `/summary`). If the script errors, report BLOCKED.

- [ ] **Step 2: Gateway routing check.** Read `services/api-gateway/src/test/java/com/kaorisystem/gateway/config/RouteConfigTest.java` + `RouteConfig.java`: determine how `/admin/dlq` reaches ai-orchestrator (search for an `/admin` or catch-all orchestrator route). If `/admin/**` is already routed to the orchestrator, `/admin/incidents` is reachable with NO RouteConfig change — add a RouteConfigTest assertion only if the file asserts admin paths (it may not). If `/admin/**` is NOT routed at the gateway (admin console is internal-only, like `/admin/dlq` appears to be), then `/admin/incidents` follows the same model — note this, no gateway change. Report what you found.

- [ ] **Step 3: Schema snapshot — flag.** Mig 136 adds `ai_incident`. `infrastructure/postgres/schema_snapshot.txt` must be regenerated before merge (`python scripts/schema-drift.py --write` against a DB with mig 136). No full-schema DB locally (pilot at Flyway v99) → do NOT edit it; report as the required pre-merge follow-up.

- [ ] **Step 4: Commit what changed.**
```bash
git add docs/api-specs/orchestrator.openapi.json services/api-gateway
git commit -m "chore(compliance): drift artefacts for /admin/incidents (K-26)"
```
(Only add files that actually changed. If OpenAPI didn't change and no gateway edit was needed, report "no drift commit needed" instead.)

---

## Self-Review

**Spec coverage:**
- ✅ `ai_incident` register (K-21, RLS, 4-level severity) → Task 1.
- ✅ Pure severity/status validation → Task 2.
- ✅ `record_incident` helper (single write path) + POST/GET/PATCH/summary admin-gated → Task 3.
- ✅ Monitoring summary aggregates open-incidents/failed-runs/low-confidence (no Layer-2 join) → Task 3 Step 3.
- ✅ K-6 audit → Task 3 (`record_incident`).
- ✅ Drift → Task 4. Record-only (no auto-detect) honored; severity 'serious' = Art 73.

**Placeholder scan:** No TBD/TODO. The "confirm workflow_runs timestamp column" + "mirror dlq admin gate" + "mirror existing router test harness" notes are match-existing-code instructions (real, varies by repo), not unspecified logic — all production code given verbatim.

**Type consistency:** `SEVERITIES`/`INCIDENT_STATUSES` + `validate_severity`/`validate_status` consistent Task 2 ↔ Task 3. `record_incident(...)` signature consistent with its call in `create_incident`. `IncidentOut` fields match the INSERT/SELECT `RETURNING` columns + mig 136 columns. Migration number 136 consistent (file, shape test, comment).

**Scope:** One subsystem (incident register + monitoring), one service + a possible gateway-test assertion. Focused.

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-06-04-eu-ai-act-k26-monitoring.md`. Two options:
1. **Subagent-Driven (recommended)** — fresh subagent per task + spec/quality review.
2. **Inline Execution** — executing-plans, batch + checkpoints.

Which approach?
