"""ADR-0037 Phase 3 — Contract module (generic business contracts + e-sign).

  POST /contracts                 — create (draft) + parties; auto contract_no
  GET  /contracts                 — library list (filter status)
  GET  /contracts/{id}            — detail: contract + parties + signatures
  POST /contracts/{id}/send       — nhap → cho_ky (open for signing)
  POST /contracts/{id}/sign       — internal click-to-sign (append-only proof)
  POST /contracts/{id}/reject     — a party refuses → tu_choi

v1 e-sign = internal click: a signature row (user + ts + IP + doc SHA-256) is the
non-repudiation proof. External providers (VNPT/DocuSign) plug in via `method`.
Multi-party order/completion = contract_lifecycle (reuses Phase-2 chain ideas).
K-1 RLS; dept resolved from the workflow / caller, never the client body.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant, acquire_for_tenant_dept
from ..workflow_runtime import contract_lifecycle as cl

log = structlog.get_logger()
router = APIRouter()


class PartyIn(BaseModel):
    party_role: str
    internal_user_id: Optional[UUID] = None
    external_name: Optional[str] = None
    external_email: Optional[str] = None
    sign_order: int = 1


class ContractIn(BaseModel):
    department_id: UUID
    title: str
    contract_type: Optional[str] = None
    value_vnd: Optional[float] = None
    template_file_id: Optional[UUID] = None
    workflow_run_id: Optional[UUID] = None
    sign_mode: str = "all"
    required_signatures: Optional[int] = None
    parties: list[PartyIn] = Field(default_factory=list)


class SignIn(BaseModel):
    party_id: UUID
    document_sha256: Optional[str] = None


class RejectIn(BaseModel):
    party_id: UUID
    reason: Optional[str] = None


async def _gen_contract_no(conn, enterprise_id: UUID, year: int) -> str:
    n = await conn.fetchval(
        "SELECT count(*) FROM contracts WHERE enterprise_id=$1 "
        "AND contract_no LIKE $2", enterprise_id, f"HD-{year}-%")
    return f"HD-{year}-{(n or 0) + 1:03d}"


@router.post("/contracts", status_code=201)
async def create_contract(body: ContractIn,
                          x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
                          x_user_id: Optional[UUID] = Header(None, alias="X-User-ID")):
    if body.sign_mode not in ("all", "threshold"):
        raise HTTPException(400, "sign_mode must be all|threshold")
    year = datetime.now(timezone.utc).year
    async with acquire_for_tenant(x_enterprise_id) as conn:
        contract_no = await _gen_contract_no(conn, x_enterprise_id, year)
        row = await conn.fetchrow(
            """INSERT INTO contracts
                   (enterprise_id, department_id, workflow_run_id, contract_no, title,
                    contract_type, value_vnd, currency, template_file_id, sign_mode,
                    required_signatures, status, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,'VND',$8,$9,$10,'nhap',$11)
               RETURNING contract_id""",
            x_enterprise_id, body.department_id, body.workflow_run_id, contract_no,
            body.title, body.contract_type, body.value_vnd, body.template_file_id,
            body.sign_mode, body.required_signatures, x_user_id)
        cid = row["contract_id"]
        for p in body.parties:
            await conn.execute(
                """INSERT INTO contract_parties
                       (contract_id, enterprise_id, party_role, internal_user_id,
                        external_name, external_email, sign_order)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                cid, x_enterprise_id, p.party_role, p.internal_user_id,
                p.external_name, p.external_email, p.sign_order)
    return {"contract_id": str(cid), "contract_no": contract_no}


@router.get("/contracts")
async def list_contracts(status: Optional[str] = Query(None),
                         x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
                         x_department_id: Optional[UUID] = Header(None, alias="X-Department-ID")):
    # ABAC (ADR-0037): when a department is supplied, scope the read at the RLS
    # layer (mig-053 abac_dept_scope) — not just an app filter. No dept → all.
    async with acquire_for_tenant_dept(x_enterprise_id, x_department_id) as conn:
        rows = await conn.fetch(
            """SELECT contract_id, contract_no, title, contract_type, status,
                      value_vnd, effective_at, expires_at, created_at
               FROM contracts
               WHERE ($1::text IS NULL OR status = $1)
               ORDER BY created_at DESC""", status)
    return {"contracts": [{**dict(r), "contract_id": str(r["contract_id"]),
                           "value_vnd": float(r["value_vnd"]) if r["value_vnd"] is not None else None,
                           "status_label": cl.STATUS_LABEL.get(r["status"], r["status"]),
                           "effective_at": r["effective_at"].isoformat() if r["effective_at"] else None,
                           "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                           "created_at": r["created_at"].isoformat() if r["created_at"] else None}
                          for r in rows]}


async def _load_parties(conn, contract_id: UUID) -> list[dict]:
    rows = await conn.fetch(
        """SELECT party_id, party_role, internal_user_id, external_name,
                  external_email, sign_order, has_signed
           FROM contract_parties WHERE contract_id=$1 ORDER BY sign_order""", contract_id)
    return [dict(r) for r in rows]


@router.get("/contracts/{contract_id}")
async def get_contract(contract_id: UUID = Path(...),
                       x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        c = await conn.fetchrow("SELECT * FROM contracts WHERE contract_id=$1", contract_id)
        if c is None:
            raise HTTPException(404, "contract not found")
        parties = await _load_parties(conn, contract_id)
        sigs = await conn.fetch(
            """SELECT signature_id, party_id, signer_label, method, signer_ip,
                      document_sha256, signed_at
               FROM contract_signatures WHERE contract_id=$1 ORDER BY signed_at""", contract_id)
    nxt = {str(p["party_id"]) for p in cl.next_signers(parties)}
    return {
        "contract_id": str(contract_id), "contract_no": c["contract_no"],
        "title": c["title"], "contract_type": c["contract_type"], "status": c["status"],
        "status_label": cl.STATUS_LABEL.get(c["status"], c["status"]),
        "value_vnd": float(c["value_vnd"]) if c["value_vnd"] is not None else None,
        "sign_mode": c["sign_mode"], "required_signatures": c["required_signatures"],
        "effective_at": c["effective_at"].isoformat() if c["effective_at"] else None,
        "expires_at": c["expires_at"].isoformat() if c["expires_at"] else None,
        "parties": [{**{k: (str(v) if isinstance(v, UUID) else v) for k, v in p.items()},
                     "is_turn": str(p["party_id"]) in nxt} for p in parties],
        "signatures": [{**dict(s), "signature_id": str(s["signature_id"]),
                        "party_id": str(s["party_id"]),
                        "signed_at": s["signed_at"].isoformat() if s["signed_at"] else None}
                       for s in sigs],
    }


@router.post("/contracts/{contract_id}/send")
async def send_for_signing(contract_id: UUID = Path(...),
                           x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        c = await conn.fetchrow("SELECT status FROM contracts WHERE contract_id=$1", contract_id)
        if c is None:
            raise HTTPException(404, "contract not found")
        if not cl.can_transition(c["status"], cl.CHO_KY):
            raise HTTPException(409, f"không thể gửi ký từ trạng thái '{cl.STATUS_LABEL.get(c['status'])}'")
        await conn.execute("UPDATE contracts SET status='cho_ky', updated_at=NOW() WHERE contract_id=$1", contract_id)
    return {"contract_id": str(contract_id), "status": cl.CHO_KY}


@router.post("/contracts/{contract_id}/sign")
async def sign_contract(body: SignIn, request: Request, background_tasks: BackgroundTasks,
                        contract_id: UUID = Path(...),
                        x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
                        x_user_id: Optional[UUID] = Header(None, alias="X-User-ID")):
    """Internal click-to-sign. Appends an immutable signature; when the required
    signatures land, the contract becomes 'hiệu lực' and (if it was produced by a
    contract node) resumes the paused workflow run."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        c = await conn.fetchrow(
            "SELECT status, sign_mode, required_signatures, workflow_run_id "
            "FROM contracts WHERE contract_id=$1", contract_id)
        if c is None:
            raise HTTPException(404, "contract not found")
        if c["status"] != cl.CHO_KY:
            raise HTTPException(409, "hợp đồng không ở trạng thái chờ ký")
        parties = await _load_parties(conn, contract_id)
        party = next((p for p in parties if str(p["party_id"]) == str(body.party_id)), None)
        if party is None:
            raise HTTPException(404, "party not found")
        if party["has_signed"]:
            raise HTTPException(409, "bên này đã ký")
        if not cl.is_party_turn(parties, body.party_id):
            raise HTTPException(409, "chưa đến lượt bên này ký (ký tuần tự)")
        label = party["external_name"] or (str(party["internal_user_id"]) if party["internal_user_id"] else party["party_role"])
        ip = request.client.host if request.client else None
        await conn.execute(
            """INSERT INTO contract_signatures
                   (contract_id, party_id, enterprise_id, signed_by_user_id,
                    signer_label, signer_ip, document_sha256, method)
               VALUES ($1,$2,$3,$4,$5,$6,$7,'internal_click')""",
            contract_id, body.party_id, x_enterprise_id, x_user_id, label, ip, body.document_sha256)
        await conn.execute("UPDATE contract_parties SET has_signed=TRUE WHERE party_id=$1", body.party_id)
        # mark this party signed in our local copy + check completion
        for p in parties:
            if str(p["party_id"]) == str(body.party_id):
                p["has_signed"] = True
        if cl.signing_complete(parties, c["sign_mode"], c["required_signatures"]):
            await conn.execute(
                "UPDATE contracts SET status='hieu_luc', effective_at=NOW(), updated_at=NOW() WHERE contract_id=$1",
                contract_id)
            log.info("contract.effective", contract_id=str(contract_id))
            # Contract produced by a contract node → resume the paused run (the
            # node's gate completes now the contract is in effect).
            run_id = c["workflow_run_id"]
            if run_id is not None:
                from ..workflow_runtime.runner import resume_after_approval
                background_tasks.add_task(
                    resume_after_approval, run_id=run_id,
                    enterprise_id=x_enterprise_id, user_id=x_user_id)
            return {"contract_id": str(contract_id), "status": cl.HIEU_LUC, "signed": True}
    return {"contract_id": str(contract_id), "status": cl.CHO_KY, "signed": True}


@router.post("/contracts/{contract_id}/reject")
async def reject_contract(body: RejectIn, contract_id: UUID = Path(...),
                          x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
                          x_user_id: Optional[UUID] = Header(None, alias="X-User-ID")):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        c = await conn.fetchrow("SELECT status, department_id FROM contracts WHERE contract_id=$1", contract_id)
        if c is None:
            raise HTTPException(404, "contract not found")
        # RBAC (ADR-0037): rejecting a contract needs 'approve' in its department.
        from ..shared.rbac_guard import assert_permission
        await assert_permission(conn, user_id=x_user_id,
                                department_id=c["department_id"], action="approve")
        if c["status"] != cl.CHO_KY:
            raise HTTPException(409, "chỉ có thể từ chối khi đang chờ ký")
        await conn.execute(
            "UPDATE contracts SET status='tu_choi', updated_at=NOW() WHERE contract_id=$1", contract_id)
    return {"contract_id": str(contract_id), "status": cl.TU_CHOI}
