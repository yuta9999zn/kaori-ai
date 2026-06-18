# EU AI Act Layer 2 — Classification Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mọi AI-use/workflow mang một `risk_tier` được phân loại và lưu trong `ai_use_risk_register`; workflow `prohibited` bị chặn khi chuyển sang runtime state hoặc khi chạy (RFC 7807 `COMPLIANCE.PROHIBITED_USE`); mỗi lần phân loại tự suy `controls_required` theo tier và ghi 1 dòng `ai_decision_audit` (K-6). Đây là Layer 2 của ADR-0041 (K-22).

**Architecture:** Thêm 1 bảng append-only (`ai_use_risk_register`, đọc bản mới nhất per workflow — mirror `workflow_review` mig 130). Thêm 1 router `compliance_risk.py` (namespace `/compliance/...`, route ở gateway qua `/api/v1/compliance/**`) cho classify + read. Logic suy control là **pure function** trong `reasoning/compliance_controls.py` (test độc lập, không I/O). Chặn prohibited bằng cách thêm 1 guard vào state-transition guard có sẵn ở `workflow_builder.update_workflow` (line 756) + endpoint run (line 2401) — trả `JSONResponse` trực tiếp giống guard dangling-branch/empty-gate đã có (giữ được custom `code`, theo `shared/errors.py:73` chỉ honor str detail).

**Tech Stack:** Python FastAPI 0.111 (ai-orchestrator, port 8093) · PostgreSQL 15 + RLS (`acquire_for_tenant`) · asyncpg · pytest · Java Spring Cloud Gateway (RouteConfigTest) · scripts/{schema-drift.py, dump_openapi.py}.

**Invariant tuân thủ:** K-1 RLS (enterprise isolation) · K-6 audit · K-9 NUMERIC không FLOAT (n/a ở đây) · K-12 tenant chỉ từ JWT header X-Enterprise-ID · K-14 RFC 7807 · K-21 `gen_uuid_v7()` PK + `gen_ulid()` external.

---

## File Structure

| File | Trách nhiệm | Tạo/Sửa |
|---|---|---|
| `infrastructure/postgres/migrations/134_ai_use_risk_register.sql` | Bảng phân loại rủi ro (append-only, RLS) | Create |
| `scripts/test_migration_134_shape.py` | Shape test cho mig 134 | Create |
| `services/ai-orchestrator/reasoning/compliance_controls.py` | Pure logic: tier→controls, validate tier, is_prohibited | Create |
| `services/ai-orchestrator/tests/test_compliance_controls.py` | Unit test pure logic | Create |
| `services/ai-orchestrator/shared/error_codes.py` | Thêm `COMPLIANCE.*` codes | Modify |
| `services/ai-orchestrator/routers/compliance_risk.py` | Endpoint classify + read | Create |
| `services/ai-orchestrator/tests/test_compliance_risk_router.py` | Test router (classify/read/auto-controls/audit) | Create |
| `services/ai-orchestrator/main.py` | Đăng ký router | Modify |
| `services/ai-orchestrator/routers/workflow_builder.py` | Guard `_check_prohibited_use` + hook ở update_workflow & run | Modify |
| `services/ai-orchestrator/tests/test_workflow_prohibited_block.py` | Test chặn prohibited | Create |
| `services/api-gateway/.../config/RouteConfig*.java` + `RouteConfigTest.java` | Route `/api/v1/compliance/**` + test | Modify |
| `frontend/lib/i18n/error-messages.ts` | i18n cho `COMPLIANCE.*` | Modify |

---

## Task 1: Migration 134 — `ai_use_risk_register`

**Files:**
- Create: `infrastructure/postgres/migrations/134_ai_use_risk_register.sql`
- Test: `scripts/test_migration_134_shape.py`

- [ ] **Step 1: Write the migration SQL**

Create `infrastructure/postgres/migrations/134_ai_use_risk_register.sql`:

```sql
-- =====================================================================
-- 134_ai_use_risk_register.sql — EU AI Act Layer 2 (ADR-0041, K-22)
--
-- Append-only classification of each AI-use / workflow into an EU AI Act
-- risk_tier. Re-classify writes a NEW row; readers take the latest per
-- workflow (mirror workflow_review mig 130). controls_required is the set
-- of Kaori controls (K-23/K-24/K-25/K-26/K-6) auto-derived from the tier.
--
-- Additive: new table only. K-21 (gen_uuid_v7 PK + gen_ulid external) +
-- RLS K-1 (enterprise isolation — mirror mig 130). Nullable workflow_id:
-- an AI-use may not map to a single workflow.
-- =====================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS ai_use_risk_register (
    ai_use_id          UUID         PRIMARY KEY DEFAULT gen_uuid_v7(),   -- K-21
    public_ref         TEXT         NOT NULL DEFAULT gen_ulid(),         -- K-21 external
    enterprise_id      UUID         NOT NULL,
    workflow_id        UUID         REFERENCES workflows(workflow_id) ON DELETE CASCADE,

    use_name           VARCHAR(160) NOT NULL,
    risk_tier          VARCHAR(16)  NOT NULL,   -- prohibited | high | limited | minimal
    annex_iii_category VARCHAR(80),             -- optional Annex III bucket
    rationale          TEXT,
    controls_required  JSONB        NOT NULL DEFAULT '[]'::jsonb,
    status             VARCHAR(16)  NOT NULL DEFAULT 'active',  -- active | blocked

    classified_by      UUID,
    classified_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_airisk_tier   CHECK (risk_tier IN ('prohibited','high','limited','minimal')),
    CONSTRAINT chk_airisk_status CHECK (status IN ('active','blocked')),
    CONSTRAINT uq_airisk_public  UNIQUE (public_ref)
);

-- Latest classification per workflow (the prohibited-block reads this).
CREATE INDEX IF NOT EXISTS idx_airisk_latest
    ON ai_use_risk_register(enterprise_id, workflow_id, classified_at DESC);
CREATE INDEX IF NOT EXISTS idx_airisk_controls
    ON ai_use_risk_register USING GIN (controls_required);

-- ─── RLS (K-1) — mirror mig 130 isolation ────────────────────────────
ALTER TABLE ai_use_risk_register ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS isolation_airisk ON ai_use_risk_register;
CREATE POLICY isolation_airisk ON ai_use_risk_register
    USING      (enterprise_id::text = current_setting('app.current_enterprise_id', true))
    WITH CHECK (enterprise_id::text = current_setting('app.current_enterprise_id', true));

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kaori_app') THEN
        EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ai_use_risk_register TO kaori_app';
    END IF;
END $$;

COMMENT ON TABLE ai_use_risk_register IS
    'ADR-0041 EU AI Act Layer 2 (K-22) — append-only risk classification per '
    'AI-use/workflow. risk_tier drives controls_required (K-23/24/25/26/6). '
    'prohibited => publish/run blocked. RLS K-1 per mig 130.';

COMMIT;
```

- [ ] **Step 2: Write the shape test**

Create `scripts/test_migration_134_shape.py` (mirror `scripts/test_migration_104_shape.py` style — pure text assertions, no DB):

```python
"""Shape test for migration 134 (ai_use_risk_register) — no DB needed."""
from pathlib import Path

MIG = Path(__file__).resolve().parents[1] / "infrastructure/postgres/migrations/134_ai_use_risk_register.sql"


def test_migration_134_exists():
    assert MIG.exists(), f"missing {MIG}"


def test_k21_id_strategy():
    sql = MIG.read_text(encoding="utf-8")
    assert "gen_uuid_v7()" in sql, "K-21: PK must default gen_uuid_v7()"
    assert "gen_ulid()" in sql, "K-21: external public_ref must default gen_ulid()"


def test_rls_enabled():
    sql = MIG.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "isolation_airisk" in sql
    assert "app.current_enterprise_id" in sql


def test_tier_and_status_constraints():
    sql = MIG.read_text(encoding="utf-8")
    for tier in ("prohibited", "high", "limited", "minimal"):
        assert tier in sql, f"tier {tier} must be in CHECK constraint"
    assert "chk_airisk_status" in sql


def test_grant_app_role():
    sql = MIG.read_text(encoding="utf-8")
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON ai_use_risk_register TO kaori_app" in sql
```

- [ ] **Step 3: Run the shape test (expect PASS — pure text test)**

Run: `python -m pytest scripts/test_migration_134_shape.py -v`
Expected: 5 passed.

- [ ] **Step 4: Commit**

```bash
git add infrastructure/postgres/migrations/134_ai_use_risk_register.sql scripts/test_migration_134_shape.py
git commit -m "feat(compliance): mig 134 ai_use_risk_register (EU AI Act Layer 2, K-22)"
```

---

## Task 2: Pure control-derivation logic

**Files:**
- Create: `services/ai-orchestrator/reasoning/compliance_controls.py`
- Test: `services/ai-orchestrator/tests/test_compliance_controls.py`

- [ ] **Step 1: Write the failing test**

Create `services/ai-orchestrator/tests/test_compliance_controls.py`:

```python
import pytest
from ai_orchestrator.reasoning import compliance_controls as cc


def test_valid_tiers_set():
    assert cc.RISK_TIERS == ("prohibited", "high", "limited", "minimal")


def test_is_prohibited():
    assert cc.is_prohibited("prohibited") is True
    assert cc.is_prohibited("high") is False


def test_high_tier_controls():
    controls = cc.controls_for_tier("high")
    assert "K-23_HUMAN_OVERSIGHT" in controls
    assert "K-25_MODEL_CARD" in controls
    assert "K-26_MONITORING" in controls
    assert "K-6_AUDIT_LOG" in controls


def test_limited_tier_controls():
    controls = cc.controls_for_tier("limited")
    assert "K-24_TRANSPARENCY" in controls
    assert "K-6_AUDIT_LOG" in controls
    assert "K-23_HUMAN_OVERSIGHT" not in controls


def test_minimal_and_prohibited_have_no_runtime_controls():
    assert cc.controls_for_tier("minimal") == []
    assert cc.controls_for_tier("prohibited") == []


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        cc.controls_for_tier("banana")


def test_validate_tier_normalises_case():
    assert cc.validate_tier(" HIGH ") == "high"
    with pytest.raises(ValueError):
        cc.validate_tier("nope")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/ai-orchestrator/tests/test_compliance_controls.py -v`
Expected: FAIL (ModuleNotFoundError: compliance_controls).

- [ ] **Step 3: Write minimal implementation**

Create `services/ai-orchestrator/reasoning/compliance_controls.py`:

```python
"""Pure EU AI Act risk-tier → Kaori control derivation (ADR-0041, K-22).

No I/O. Maps a risk_tier to the set of Kaori controls that MUST be active
for that tier. `prohibited` returns [] because the use is blocked entirely
(see workflow_builder prohibited-block); it never reaches runtime controls.
"""
from __future__ import annotations

RISK_TIERS: tuple[str, ...] = ("prohibited", "high", "limited", "minimal")

# Tier → controls (invariant codes from ADR-0041 §4).
_TIER_CONTROLS: dict[str, list[str]] = {
    "prohibited": [],
    "high":       ["K-23_HUMAN_OVERSIGHT", "K-25_MODEL_CARD",
                   "K-26_MONITORING", "K-6_AUDIT_LOG"],
    "limited":    ["K-24_TRANSPARENCY", "K-6_AUDIT_LOG"],
    "minimal":    [],
}


def validate_tier(tier: str) -> str:
    """Trim + lowercase; raise ValueError if not a known tier."""
    norm = (tier or "").strip().lower()
    if norm not in RISK_TIERS:
        raise ValueError(f"unknown risk_tier: {tier!r} (expected one of {RISK_TIERS})")
    return norm


def is_prohibited(tier: str) -> bool:
    return validate_tier(tier) == "prohibited"


def controls_for_tier(tier: str) -> list[str]:
    """Return a fresh list of control codes for the tier."""
    return list(_TIER_CONTROLS[validate_tier(tier)])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/ai-orchestrator/tests/test_compliance_controls.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add services/ai-orchestrator/reasoning/compliance_controls.py services/ai-orchestrator/tests/test_compliance_controls.py
git commit -m "feat(compliance): pure risk-tier->controls derivation (K-22)"
```

---

## Task 3: Add `COMPLIANCE.*` error codes

**Files:**
- Modify: `services/ai-orchestrator/shared/error_codes.py`

- [ ] **Step 1: Add the constants**

In `services/ai-orchestrator/shared/error_codes.py`, after the `LLM —` block (after line 89 `LLM_QUOTA_EXCEEDED`), insert:

```python
# ============================================================
# COMPLIANCE — EU AI Act control framework (ADR-0041, K-22..K-26)
# ============================================================
COMPLIANCE_PROHIBITED_USE  = "COMPLIANCE.PROHIBITED_USE"   # 403 — Art 5 prohibited tier
COMPLIANCE_NOT_CLASSIFIED  = "COMPLIANCE.NOT_CLASSIFIED"   # 409 — high-risk action w/o classification
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from ai_orchestrator.shared.error_codes import COMPLIANCE_PROHIBITED_USE; print(COMPLIANCE_PROHIBITED_USE)"`
Expected: `COMPLIANCE.PROHIBITED_USE`

(Run from `services/ai-orchestrator` with the service venv / `PYTHONPATH` as other tests use. If the package import path differs, mirror exactly how `tests/test_compliance_controls.py` imports `ai_orchestrator.*`.)

- [ ] **Step 3: Commit**

```bash
git add services/ai-orchestrator/shared/error_codes.py
git commit -m "feat(compliance): add COMPLIANCE.* error codes (K-22)"
```

---

## Task 4: `compliance_risk.py` router — classify + read

**Files:**
- Create: `services/ai-orchestrator/routers/compliance_risk.py`
- Test: `services/ai-orchestrator/tests/test_compliance_risk_router.py`

- [ ] **Step 1: Write the failing test**

Create `services/ai-orchestrator/tests/test_compliance_risk_router.py`. Mirror the DB-mocking / TestClient pattern used in `tests/test_industry_bootstrap_router.py` (read that file first to copy the exact `acquire_for_tenant` fake-connection fixture and header setup). The behavioural assertions to encode:

```python
# Pseudocode of the behaviours — adapt to the repo's existing fake-conn fixture.
#
# 1. POST /compliance/ai-uses with risk_tier="high" + workflow_id:
#    -> 201; response.controls_required contains "K-23_HUMAN_OVERSIGHT";
#       response.status == "active";
#       a row was INSERTed into ai_use_risk_register;
#       record_ai_call was awaited once with task_kind="risk_classification".
#
# 2. POST /compliance/ai-uses with risk_tier="prohibited":
#    -> 201; response.status == "blocked"; controls_required == [].
#
# 3. POST /compliance/ai-uses with risk_tier="banana":
#    -> 422 (validation) OR 400 with code VALIDATION.INVALID_ENUM.
#
# 4. GET /compliance/ai-uses?workflow_id=<id> returns the latest row.
#
# 5. Missing X-Enterprise-ID header -> 422 (FastAPI required header).
```

Write these as real pytest functions using the same TestClient + monkeypatch style as `test_industry_bootstrap_router.py` (monkeypatch `routers.compliance_risk.record_ai_call` with an `AsyncMock`, and the `acquire_for_tenant` fake connection returning canned rows).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/ai-orchestrator/tests/test_compliance_risk_router.py -v`
Expected: FAIL (ModuleNotFoundError: routers.compliance_risk).

- [ ] **Step 3: Write the router**

Create `services/ai-orchestrator/routers/compliance_risk.py`:

```python
"""EU AI Act risk classification gate — Layer 2 (ADR-0041, K-22).

Classify an AI-use / workflow into a risk_tier; auto-derive controls_required;
record the classification in ai_decision_audit (K-6). prohibited => status
'blocked' (the workflow_builder guard refuses to publish/run it).

Namespace /compliance/... — routed at the edge via /api/v1/compliance/**.
K-1 RLS via acquire_for_tenant. K-12 tenant from X-Enterprise-ID only.
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant
from ..shared.ai_governance import record_ai_call
from ..reasoning import compliance_controls as cc

log = structlog.get_logger()
router = APIRouter()


class ClassifyIn(BaseModel):
    use_name: str = Field(..., max_length=160)
    risk_tier: str
    workflow_id: Optional[UUID] = None
    annex_iii_category: Optional[str] = Field(None, max_length=80)
    rationale: Optional[str] = None


class RiskUseOut(BaseModel):
    ai_use_id: str
    public_ref: str
    workflow_id: Optional[str]
    use_name: str
    risk_tier: str
    annex_iii_category: Optional[str]
    rationale: Optional[str]
    controls_required: list[str]
    status: str
    classified_at: Optional[str]


def _row_to_out(row) -> RiskUseOut:
    controls = row["controls_required"]
    if isinstance(controls, str):
        try:
            controls = json.loads(controls)
        except (ValueError, TypeError):
            controls = []
    return RiskUseOut(
        ai_use_id=str(row["ai_use_id"]),
        public_ref=row["public_ref"],
        workflow_id=str(row["workflow_id"]) if row["workflow_id"] else None,
        use_name=row["use_name"],
        risk_tier=row["risk_tier"],
        annex_iii_category=row["annex_iii_category"],
        rationale=row["rationale"],
        controls_required=controls,
        status=row["status"],
        classified_at=row["classified_at"].isoformat() if row["classified_at"] else None,
    )


@router.post("/compliance/ai-uses", response_model=RiskUseOut, status_code=201)
async def classify_ai_use(
    body: ClassifyIn,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: Optional[UUID] = Header(None, alias="X-User-ID"),
):
    """Classify an AI-use into a risk_tier; auto-derive controls; audit (K-6)."""
    try:
        tier = cc.validate_tier(body.risk_tier)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"invalid risk_tier: {body.risk_tier}")

    controls = cc.controls_for_tier(tier)
    status = "blocked" if cc.is_prohibited(tier) else "active"

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """INSERT INTO ai_use_risk_register
                   (enterprise_id, workflow_id, use_name, risk_tier,
                    annex_iii_category, rationale, controls_required,
                    status, classified_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
               RETURNING ai_use_id, public_ref, workflow_id, use_name,
                         risk_tier, annex_iii_category, rationale,
                         controls_required, status, classified_at""",
            x_enterprise_id, body.workflow_id, body.use_name, tier,
            body.annex_iii_category, body.rationale, json.dumps(controls),
            status, x_user_id,
        )

    # K-6 audit — reuse the AI audit ledger for the governance event.
    try:
        await record_ai_call(
            enterprise_id=x_enterprise_id,
            task_kind="risk_classification",
            model_version="rules-only",
            model_provider="kaori-compliance",
            prompt=f"{body.use_name}|tier={tier}|wf={body.workflow_id}",
            output=json.dumps({"tier": tier, "controls": controls, "status": status}),
            confidence=None,
        )
    except Exception as e:  # audit must not break the classification
        log.warning("compliance.audit_failed", error=str(e))

    log.info("compliance.classified", tier=tier, status=status,
             workflow_id=str(body.workflow_id) if body.workflow_id else None)
    return _row_to_out(row)


@router.get("/compliance/ai-uses", response_model=Optional[RiskUseOut])
async def get_latest_for_workflow(
    workflow_id: UUID = Query(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Latest classification for a workflow, or null."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT ai_use_id, public_ref, workflow_id, use_name, risk_tier,
                      annex_iii_category, rationale, controls_required,
                      status, classified_at
               FROM ai_use_risk_register
               WHERE workflow_id = $1
               ORDER BY classified_at DESC
               LIMIT 1""",
            workflow_id,
        )
    return _row_to_out(row) if row else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest services/ai-orchestrator/tests/test_compliance_risk_router.py -v`
Expected: all behaviours pass.

- [ ] **Step 5: Commit**

```bash
git add services/ai-orchestrator/routers/compliance_risk.py services/ai-orchestrator/tests/test_compliance_risk_router.py
git commit -m "feat(compliance): classify+read AI-use risk router (K-22)"
```

---

## Task 5: Register router in `main.py`

**Files:**
- Modify: `services/ai-orchestrator/main.py:27` (import) and `:~228` (include)

- [ ] **Step 1: Add the import**

On line 27 (the long `from .routers import ...` line), append `, compliance_risk` to the import list.

- [ ] **Step 2: Add the include**

After line 228 (`app.include_router(industry_bootstrap.router, tags=["Industry Template"])`), add:

```python
app.include_router(compliance_risk.router, tags=["Compliance (EU AI Act, ADR-0041)"])
```

- [ ] **Step 3: Verify the app boots & route is mounted**

Run: `python -m pytest services/ai-orchestrator/tests/test_compliance_risk_router.py -v`
Expected: still passes (TestClient builds the app — a bad import would fail collection).

- [ ] **Step 4: Commit**

```bash
git add services/ai-orchestrator/main.py
git commit -m "feat(compliance): mount compliance_risk router"
```

---

## Task 6: Prohibited-block hook in `workflow_builder.py`

**Files:**
- Modify: `services/ai-orchestrator/routers/workflow_builder.py` (add guard ~after line 434; hook at line 756 block and at run endpoint line 2401)
- Test: `services/ai-orchestrator/tests/test_workflow_prohibited_block.py`

- [ ] **Step 1: Write the failing test**

Create `services/ai-orchestrator/tests/test_workflow_prohibited_block.py`. Using the same fake-conn fixture as `test_industry_bootstrap_router.py`, encode:

```python
# 1. PUT /workflows/{id} with state="ACTIVE_BASELINE" where the latest
#    ai_use_risk_register row for that workflow has risk_tier="prohibited":
#    -> 403; body["code"] == "COMPLIANCE.PROHIBITED_USE";
#       media type application/problem+json; the UPDATE is NOT executed.
#
# 2. Same PUT but latest tier="high":
#    -> proceeds past the prohibited guard (then hits the existing
#       dangling/gate guards or succeeds).
#
# 3. POST /workflows/{id}/run when latest tier="prohibited":
#    -> 403; body["code"] == "COMPLIANCE.PROHIBITED_USE".
```

(Make the fake connection return a `{"risk_tier": "prohibited"}` row for the `_check_prohibited_use` SELECT, and empty lists for the dangling/gate SELECTs.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest services/ai-orchestrator/tests/test_workflow_prohibited_block.py -v`
Expected: FAIL (guard not implemented; PUT returns 200 / run returns 202).

- [ ] **Step 3: Add the guard helper**

In `services/ai-orchestrator/routers/workflow_builder.py`, after `_check_approval_gates` (after line ~434), add:

```python
async def _check_prohibited_use(conn, workflow_id: UUID) -> bool:
    """True if the latest EU AI Act classification for this workflow is
    'prohibited' (ADR-0041 K-22). Reads ai_use_risk_register under the same
    tenant connection so RLS scopes it (K-1). Tolerates the table being
    absent on lean deployments (returns False)."""
    try:
        row = await conn.fetchrow(
            """SELECT risk_tier FROM ai_use_risk_register
               WHERE workflow_id = $1
               ORDER BY classified_at DESC
               LIMIT 1""",
            workflow_id,
        )
    except Exception:
        return False
    return bool(row) and row["risk_tier"] == "prohibited"


def _prohibited_problem(workflow_id: UUID) -> JSONResponse:
    """RFC 7807 envelope for a blocked prohibited-tier workflow (K-22).
    Returned directly (not via HTTPException) so the COMPLIANCE.* code
    survives — shared/errors.py:73 only honours str detail."""
    return JSONResponse(
        status_code=403,
        media_type="application/problem+json",
        content={
            "type":     "/problems/compliance-prohibited-use",
            "title":    "Workflow bị chặn — phân loại rủi ro EU AI Act = prohibited",
            "status":   403,
            "code":     "COMPLIANCE.PROHIBITED_USE",
            "instance": f"/workflows/{workflow_id}",
        },
    )
```

- [ ] **Step 4: Hook into the state-transition guard**

In `update_workflow`, inside the `if body.state in _RUNTIME_STATES:` block (line 756) — BEFORE the dangling-branch check at line 757 — add:

```python
            if await _check_prohibited_use(conn, workflow_id):
                return _prohibited_problem(workflow_id)
```

- [ ] **Step 5: Hook into the run endpoint**

In the `POST /workflows/{workflow_id}/run` handler (starts line 2401), inside its `async with acquire_for_tenant(...) as conn:` block, before it kicks the run, add:

```python
        if await _check_prohibited_use(conn, workflow_id):
            return _prohibited_problem(workflow_id)
```

(If the run handler is declared with `response_model=WorkflowRunOut`, returning a `JSONResponse` is fine — FastAPI lets a handler return a `Response` subclass directly, bypassing the model. Confirm the handler doesn't early-`raise` before the connection is open; place the guard right after the connection opens, mirroring the dangling guard.)

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest services/ai-orchestrator/tests/test_workflow_prohibited_block.py -v`
Expected: all pass.

- [ ] **Step 7: Run the broader workflow_builder suite (no regressions)**

Run: `python -m pytest services/ai-orchestrator/tests/ -k "workflow" -q`
Expected: no new failures vs baseline.

- [ ] **Step 8: Commit**

```bash
git add services/ai-orchestrator/routers/workflow_builder.py services/ai-orchestrator/tests/test_workflow_prohibited_block.py
git commit -m "feat(compliance): block prohibited-tier workflow publish+run (K-22)"
```

---

## Task 7: Refresh ALL FOUR drift artefacts

> Per `feedback_endpoint_addition_drift_checks`: RouteConfigTest + schema_snapshot + openapi + FE types — all four BEFORE first push.

**Files:**
- Modify: `services/api-gateway/.../config/RouteConfig*.java` + `RouteConfigTest.java`
- Regenerate: `schema_snapshot.txt`, OpenAPI spec, FE error i18n

- [ ] **Step 1: Gateway route for `/api/v1/compliance/**`**

Open the gateway route config (the source the test in `services/api-gateway/src/test/java/com/kaorisystem/gateway/config/RouteConfigTest.java` asserts against — usually `application.yml` routes or a `RouteConfig.java`). Add a route forwarding `/api/v1/compliance/**` to the ai-orchestrator service, mirroring the existing `/api/v1/workflows/**` route entry. Then add the matching assertion in `RouteConfigTest.java`.

Run: `cd services/api-gateway && ./mvnw -q -Dtest=RouteConfigTest test`
Expected: PASS (new compliance route asserted).

- [ ] **Step 2: Regenerate the schema snapshot (drift gate)**

Run: `python scripts/schema-drift.py --write`
Expected: `schema_snapshot.txt` updated to include `ai_use_risk_register` (partition children `*_YYYY_MM` excluded — deterministic per CLAUDE.md).

Verify it's deterministic:
Run: `python scripts/schema-drift.py` (no `--write`)
Expected: exit 0, "no drift".

- [ ] **Step 3: Regenerate the OpenAPI spec**

Run: `python scripts/dump_openapi.py` (or `bash scripts/openapi_precommit_hook.sh` if that's the canonical entry — check which the repo uses).
Expected: the OpenAPI artefact now lists `POST /compliance/ai-uses` + `GET /compliance/ai-uses`.

- [ ] **Step 4: FE types + i18n for `COMPLIANCE.*`**

In `frontend/lib/i18n/error-messages.ts`, add user-facing Vietnamese strings for the two new codes:

```ts
"COMPLIANCE.PROHIBITED_USE": "Quy trình này bị chặn vì thuộc nhóm bị cấm theo EU AI Act. Liên hệ quản trị để phân loại lại.",
"COMPLIANCE.NOT_CLASSIFIED": "Quy trình chưa được phân loại rủi ro. Vui lòng phân loại trước khi kích hoạt.",
```

If the FE consumes generated OpenAPI types (check `frontend/lib/` for a generated types file), regenerate them from the Step-3 OpenAPI output per the repo's FE-types generation command.

- [ ] **Step 5: Commit all four drift artefacts together**

```bash
git add services/api-gateway schema_snapshot.txt docs/api-specs frontend/lib/i18n/error-messages.ts frontend/lib
git commit -m "chore(compliance): refresh drift artefacts for /compliance/ai-uses (route+schema+openapi+fe)"
```

(Adjust the exact OpenAPI artefact path — `docs/api-specs/` or wherever `dump_openapi.py` writes — and the FE generated-types path to match what actually changed.)

---

## Self-Review

**Spec coverage (vs `6.1` §5 Layer 2):**
- ✅ Bảng `ai_use_risk_register` K-21 additive/nullable → Task 1.
- ✅ Endpoint đăng ký + classify `risk_tier` → Task 4 (`POST /compliance/ai-uses`).
- ✅ Chặn build/publish khi prohibited + RFC 7807 `COMPLIANCE.PROHIBITED_USE` → Task 6 (state-transition + run hook).
- ✅ Auto-bật `controls_required` theo tier → Task 2 (pure) + Task 4 (persist).
- ✅ Ghi `ai_decision_audit` → Task 4 (`record_ai_call` task_kind="risk_classification").
- ✅ Refresh ALL FOUR drift artefacts → Task 7.

**Placeholder scan:** không có TBD/TODO; mỗi step có code/command thật. Hai chỗ cố ý để engineer xác nhận tại chỗ (vì phụ thuộc file repo thực): (a) đường dẫn OpenAPI/FE-types output trong Task 7, (b) fixture fake-conn copy từ `test_industry_bootstrap_router.py` — đã chỉ rõ file nguồn để copy.

**Type consistency:** `controls_for_tier`/`validate_tier`/`is_prohibited` (Task 2) dùng nhất quán ở Task 4 & 6. `RiskUseOut` field names khớp cột SQL Task 1. Error code string `COMPLIANCE.PROHIBITED_USE` khớp giữa Task 3 (constant), Task 6 (JSONResponse), Task 7 (i18n).

**Scope:** một subsystem (classification gate), một service chính (ai-orchestrator) + drift touch-ups. Đủ gọn cho một plan.

---

## Execution Handoff

Plan đã lưu `docs/superpowers/plans/2026-06-03-eu-ai-act-layer2-classification-gate.md`. Hai cách thực thi:

**1. Subagent-Driven (recommended)** — mỗi task 1 subagent mới, review giữa các task, lặp nhanh.

**2. Inline Execution** — chạy trong session này theo executing-plans, batch + checkpoint.

Anh chọn cách nào?
