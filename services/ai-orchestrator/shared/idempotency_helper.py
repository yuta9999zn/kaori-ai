"""K-13 idempotency helper — Phase 2.9 closeout extension.

Reusable wrapper around ``workflow_runtime.idempotency_store`` for router
POST endpoints that need to dedupe ``Idempotency-Key`` header. PR #206
established the inline pattern in dlq_console.py + auth_security.py;
this module extracts the same pattern so 3 new routers (okr, llm_ops,
field-key) don't duplicate.

Pattern in router::

    from ..shared.idempotency_helper import (
        idempotency_short_circuit, record_idempotency_outcome,
    )

    @router.post("/something")
    async def handler(
        ...,
        idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    ):
        cached = await idempotency_short_circuit(
            x_enterprise_id, idempotency_key, side_effect_class="external",
        )
        if cached is not None:
            return MyResponseModel(**cached)

        # ... fire side effect ...

        out = MyResponseModel(...)
        await record_idempotency_outcome(
            x_enterprise_id, idempotency_key, out.model_dump(),
        )
        return out

Pitfall guards baked in (see ``feedback_k13_helper_pitfalls.md``):
  * ``isinstance(idempotency_key, str)`` guard — when caller invokes the
    handler directly (e.g. in tests, not via FastAPI HTTP route), the
    parameter receives the ``Header()`` default OBJECT, not None. Without
    the isinstance check the helper sees a truthy value + tries to run.
  * Relative ``..workflow_runtime`` import — ``ai_orchestrator.workflow_runtime``
    test monkeypatch resolves to the same sys.modules entry the helper
    fetches from.

Backwards compat: no Idempotency-Key header → both functions short-circuit
to no-op; legacy callers stay unchanged.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID


async def idempotency_short_circuit(
    enterprise_id: UUID,
    idempotency_key: Optional[str],
    side_effect_class: str = "external",
    ttl_seconds: int = 86_400,
) -> Optional[dict[str, Any]]:
    """Return cached response_payload dict if duplicate Idempotency-Key,
    else None. Caller proceeds on None + must call record_outcome at end.
    """
    if not isinstance(idempotency_key, str) or not idempotency_key:
        return None
    from ..workflow_runtime.idempotency_store import get_or_set
    hit = await get_or_set(
        enterprise_id=enterprise_id, key=idempotency_key,
        side_effect_class=side_effect_class, ttl_seconds=ttl_seconds,
    )
    return hit.response_payload if hit.cached else None


async def record_idempotency_outcome(
    enterprise_id: UUID,
    idempotency_key: Optional[str],
    response: dict[str, Any],
) -> None:
    """Persist response_payload after side effect completes. No-op when
    no Idempotency-Key provided.
    """
    if not isinstance(idempotency_key, str) or not idempotency_key:
        return
    from ..workflow_runtime.idempotency_store import record_outcome
    await record_outcome(
        enterprise_id=enterprise_id, key=idempotency_key,
        response_payload=response,
    )
