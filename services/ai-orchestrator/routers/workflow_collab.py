"""
P2-S16 Multi-user collaboration — assignments + comments + edit locks.

Builds on mig 072 (workflow_editors, workflow_comments, workflow_locks).

Endpoints (mounted under /workflows/{workflow_id})
---------------------------------------------------
    Editors:
      POST   /workflows/{workflow_id}/editors            assign user
      GET    /workflows/{workflow_id}/editors            list
      PATCH  /workflows/{workflow_id}/editors/{user_id}  change role
      DELETE /workflows/{workflow_id}/editors/{user_id}  remove

    Comments:
      POST   /workflows/{workflow_id}/comments           post (top-level or reply)
      GET    /workflows/{workflow_id}/comments           list (filter ?node_id= / ?resolved=)
      PATCH  /workflows/{workflow_id}/comments/{cid}     edit body / resolve

    Locks (optimistic):
      POST   /workflows/{workflow_id}/lock               acquire — returns lock_token
      DELETE /workflows/{workflow_id}/lock               release (token in body)
      GET    /workflows/{workflow_id}/lock               check status

K-1 / K-12: tenant from JWT header.
K-13 anti-IDOR: lock_token is server-issued UUID; client echoes on PATCH/DELETE.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

router = APIRouter()


# ─── Shapes ──────────────────────────────────────────────────────────


class EditorCreate(BaseModel):
    user_id: UUID
    role:    str = Field(default="EDITOR", pattern=r"^(OWNER|EDITOR|REVIEWER|VIEWER)$")


class EditorRoleUpdate(BaseModel):
    role: str = Field(..., pattern=r"^(OWNER|EDITOR|REVIEWER|VIEWER)$")


class EditorOut(BaseModel):
    editor_id:   UUID
    workflow_id: UUID
    user_id:     UUID
    role:        str
    invited_by:  Optional[UUID]
    accepted:    bool
    created_at:  datetime
    accepted_at: Optional[datetime]


class CommentCreate(BaseModel):
    body:              str = Field(..., min_length=1, max_length=4000)
    node_id:           Optional[UUID] = None
    parent_comment_id: Optional[UUID] = None


class CommentUpdate(BaseModel):
    body:     Optional[str] = Field(default=None, min_length=1, max_length=4000)
    resolved: Optional[bool] = None


class CommentOut(BaseModel):
    comment_id:        UUID
    workflow_id:       UUID
    node_id:           Optional[UUID]
    parent_comment_id: Optional[UUID]
    author_user_id:    UUID
    body:              str
    resolved:          bool
    resolved_at:       Optional[datetime]
    resolved_by:       Optional[UUID]
    created_at:        datetime
    edited_at:         Optional[datetime]


class LockAcquire(BaseModel):
    ttl_seconds: int = Field(default=600, ge=30, le=3600)
    intent:      str = Field(default="edit", pattern=r"^(edit|approve|rebuild)$")


class LockOut(BaseModel):
    lock_id:         UUID
    workflow_id:     UUID
    held_by_user_id: UUID
    lock_token:      UUID
    acquired_at:     datetime
    ttl_seconds:     int
    intent:          str
    expires_at:      datetime


class LockRelease(BaseModel):
    lock_token: UUID


# ─── helpers ────────────────────────────────────────────────────────


def _lock_to_out(row) -> LockOut:
    acquired_at = row["acquired_at"]
    return LockOut(
        lock_id=row["lock_id"],
        workflow_id=row["workflow_id"],
        held_by_user_id=row["held_by_user_id"],
        lock_token=row["lock_token"],
        acquired_at=acquired_at,
        ttl_seconds=int(row["ttl_seconds"]),
        intent=row["intent"],
        expires_at=acquired_at + timedelta(seconds=int(row["ttl_seconds"])),
    )


# ═════════════════════════════════════════════════════════════════════
# Editors
# ═════════════════════════════════════════════════════════════════════


@router.post("/workflows/{workflow_id}/editors", response_model=EditorOut, status_code=201)
async def add_editor(
    body: EditorCreate,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow("SELECT 1 FROM workflows WHERE workflow_id = $1", workflow_id)
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        try:
            row = await conn.fetchrow(
                """INSERT INTO workflow_editors
                      (workflow_id, enterprise_id, user_id, role, invited_by)
                   VALUES ($1, $2, $3, $4, $5) RETURNING *""",
                workflow_id, x_enterprise_id, body.user_id, body.role, x_user_id,
            )
        except Exception as e:  # noqa: BLE001
            if "uq_workflow_editor" in str(e):
                raise HTTPException(status_code=409,
                                    detail="user already assigned to this workflow") from e
            raise
    return EditorOut(
        editor_id=row["editor_id"], workflow_id=row["workflow_id"],
        user_id=row["user_id"], role=row["role"],
        invited_by=row["invited_by"], accepted=row["accepted"],
        created_at=row["created_at"], accepted_at=row["accepted_at"],
    )


@router.get("/workflows/{workflow_id}/editors", response_model=list[EditorOut])
async def list_editors(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT * FROM workflow_editors
               WHERE workflow_id = $1
               ORDER BY created_at""",
            workflow_id,
        )
    return [
        EditorOut(
            editor_id=r["editor_id"], workflow_id=r["workflow_id"],
            user_id=r["user_id"], role=r["role"],
            invited_by=r["invited_by"], accepted=r["accepted"],
            created_at=r["created_at"], accepted_at=r["accepted_at"],
        )
        for r in rows
    ]


@router.patch("/workflows/{workflow_id}/editors/{user_id}", response_model=EditorOut)
async def update_editor_role(
    body: EditorRoleUpdate,
    workflow_id: UUID = Path(...),
    user_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE workflow_editors SET role = $1
               WHERE workflow_id = $2 AND user_id = $3 RETURNING *""",
            body.role, workflow_id, user_id,
        )
    if row is None:
        raise HTTPException(status_code=404, detail="editor not found")
    return EditorOut(
        editor_id=row["editor_id"], workflow_id=row["workflow_id"],
        user_id=row["user_id"], role=row["role"],
        invited_by=row["invited_by"], accepted=row["accepted"],
        created_at=row["created_at"], accepted_at=row["accepted_at"],
    )


@router.delete("/workflows/{workflow_id}/editors/{user_id}", status_code=204)
async def remove_editor(
    workflow_id: UUID = Path(...),
    user_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute(
            "DELETE FROM workflow_editors WHERE workflow_id = $1 AND user_id = $2",
            workflow_id, user_id,
        )
    return None


# ═════════════════════════════════════════════════════════════════════
# Comments
# ═════════════════════════════════════════════════════════════════════


@router.post("/workflows/{workflow_id}/comments", response_model=CommentOut, status_code=201)
async def post_comment(
    body: CommentCreate,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow("SELECT 1 FROM workflows WHERE workflow_id = $1", workflow_id)
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        if body.parent_comment_id is not None:
            parent = await conn.fetchrow(
                """SELECT 1 FROM workflow_comments
                   WHERE comment_id = $1 AND workflow_id = $2""",
                body.parent_comment_id, workflow_id,
            )
            if parent is None:
                raise HTTPException(status_code=400,
                                    detail="parent_comment_id not in this workflow")
        row = await conn.fetchrow(
            """INSERT INTO workflow_comments
                  (workflow_id, node_id, enterprise_id, parent_comment_id,
                   author_user_id, body)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            workflow_id, body.node_id, x_enterprise_id,
            body.parent_comment_id, x_user_id, body.body,
        )
    return CommentOut(**dict(row))


@router.get("/workflows/{workflow_id}/comments", response_model=list[CommentOut])
async def list_comments(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    node_id: Optional[UUID] = Query(default=None),
    resolved: Optional[bool] = Query(default=None),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = "SELECT * FROM workflow_comments WHERE workflow_id = $1"
        params: list[Any] = [workflow_id]
        if node_id is not None:
            params.append(node_id)
            sql += f" AND node_id = ${len(params)}"
        if resolved is not None:
            params.append(resolved)
            sql += f" AND resolved = ${len(params)}"
        sql += " ORDER BY created_at"
        rows = await conn.fetch(sql, *params)
    return [CommentOut(**dict(r)) for r in rows]


@router.patch("/workflows/{workflow_id}/comments/{comment_id}", response_model=CommentOut)
async def update_comment(
    body: CommentUpdate,
    workflow_id: UUID = Path(...),
    comment_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    updates: list[str] = []
    params: list[Any] = []
    if body.body is not None:
        params.append(body.body)
        updates.append(f"body = ${len(params)}, edited_at = NOW()")
    if body.resolved is True:
        params.append(x_user_id)
        updates.append(
            f"resolved = TRUE, resolved_at = NOW(), resolved_by = ${len(params)}"
        )
    elif body.resolved is False:
        updates.append("resolved = FALSE, resolved_at = NULL, resolved_by = NULL")
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    params.extend([comment_id, workflow_id])
    sql = (
        f"UPDATE workflow_comments SET {', '.join(updates)} "
        f"WHERE comment_id = ${len(params) - 1} AND workflow_id = ${len(params)} "
        f"RETURNING *"
    )
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(sql, *params)
    if row is None:
        raise HTTPException(status_code=404, detail="comment not found")
    return CommentOut(**dict(row))


# ═════════════════════════════════════════════════════════════════════
# Locks (optimistic)
# ═════════════════════════════════════════════════════════════════════


@router.post("/workflows/{workflow_id}/lock", response_model=LockOut, status_code=201)
async def acquire_lock(
    body: LockAcquire,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Acquire an edit lock. Conflict (409) if another user holds a
    non-expired lock; same-user re-acquire refreshes acquired_at."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        wf = await conn.fetchrow("SELECT 1 FROM workflows WHERE workflow_id = $1", workflow_id)
        if wf is None:
            raise HTTPException(status_code=404, detail="workflow not found")

        existing = await conn.fetchrow(
            "SELECT * FROM workflow_locks WHERE workflow_id = $1", workflow_id,
        )
        if existing is not None:
            expires_at = existing["acquired_at"] + timedelta(
                seconds=int(existing["ttl_seconds"])
            )
            if expires_at > datetime.now(timezone.utc):
                if existing["held_by_user_id"] == x_user_id:
                    # Same user refreshes
                    row = await conn.fetchrow(
                        """UPDATE workflow_locks
                           SET acquired_at = NOW(), ttl_seconds = $1, intent = $2,
                               lock_token = gen_random_uuid()
                           WHERE workflow_id = $3 RETURNING *""",
                        body.ttl_seconds, body.intent, workflow_id,
                    )
                    return _lock_to_out(row)
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"workflow locked by user "
                        f"{existing['held_by_user_id']} until {expires_at.isoformat()}"
                    ),
                )
            # Expired — release + re-acquire
            await conn.execute(
                "DELETE FROM workflow_locks WHERE workflow_id = $1", workflow_id,
            )

        row = await conn.fetchrow(
            """INSERT INTO workflow_locks
                  (workflow_id, enterprise_id, held_by_user_id, ttl_seconds, intent)
               VALUES ($1, $2, $3, $4, $5) RETURNING *""",
            workflow_id, x_enterprise_id, x_user_id, body.ttl_seconds, body.intent,
        )
    return _lock_to_out(row)


@router.delete("/workflows/{workflow_id}/lock", status_code=204)
async def release_lock(
    body: LockRelease,
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
):
    """Release lock. Caller must echo the lock_token issued on acquire."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """DELETE FROM workflow_locks
               WHERE workflow_id = $1 AND lock_token = $2
                 AND held_by_user_id = $3
               RETURNING workflow_id""",
            workflow_id, body.lock_token, x_user_id,
        )
    if row is None:
        raise HTTPException(
            status_code=403,
            detail="lock_token mismatch or lock not held by you",
        )
    return None


@router.get("/workflows/{workflow_id}/lock", response_model=Optional[LockOut])
async def check_lock(
    workflow_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Return current lock holder or null if free. Auto-prunes expired."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM workflow_locks WHERE workflow_id = $1", workflow_id,
        )
        if row is None:
            return None
        expires_at = row["acquired_at"] + timedelta(
            seconds=int(row["ttl_seconds"])
        )
        if expires_at <= datetime.now(timezone.utc):
            await conn.execute(
                "DELETE FROM workflow_locks WHERE workflow_id = $1", workflow_id,
            )
            return None
    return _lock_to_out(row)
