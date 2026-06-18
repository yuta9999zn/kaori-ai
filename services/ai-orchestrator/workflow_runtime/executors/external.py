"""
External-effect executors — send_email.

K-17 side_effect_class = external (irreversible). Requires idempotency
dedup (ctx.idempotency_key) — same key on retry skips the send.

Implementation
==============
Inserts into ``notification_outbox`` (mig 026). The notification-service
poller picks the row up, renders the ``workflow-freeform`` template,
and dispatches via SMTP. The insert is K-13 idempotent via the
``source_ref`` column (the executor's idempotency_key) + DB UNIQUE
constraint on (enterprise_id, source_ref).
"""
from __future__ import annotations

from typing import Any

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import _resolve

log = structlog.get_logger()


class SendEmailExecutor(NodeExecutor):
    """send_email — enqueue email via notification_outbox.

    Config:
      to:       'user@example.com'  or  $.upstream.email   (required)
      subject:  'Hợp đồng cần duyệt'                         (required, ≤200 chars)
      body:     'Xin chào ...'  (plain text; multi-line OK)  (required, ≤10000 chars)
      cc:       ['cc1@...', ...]                              (optional)
    Output:
      {outbox_id: UUID-str, recipient: str, queued: True}

    K-13 idempotency: caller's run + node combination produces unique
    source_ref so retry on same node hits ON CONFLICT DO NOTHING.
    """
    node_type_key = "send_email"
    side_effect_class = SideEffectClass.EXTERNAL

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        to_addr = _resolve(config.get("to"), ctx)
        subject = _resolve(config.get("subject"), ctx)
        body    = _resolve(config.get("body"), ctx)

        if not isinstance(to_addr, str) or "@" not in to_addr:
            raise NodeExecutorError(f"send_email.to invalid: {to_addr!r}")
        if not isinstance(subject, str) or not subject.strip():
            raise NodeExecutorError("send_email.subject required (non-empty string)")
        if not isinstance(body, str) or not body.strip():
            raise NodeExecutorError("send_email.body required (non-empty string)")
        if len(subject) > 200:
            raise NodeExecutorError("send_email.subject > 200 chars")
        if len(body) > 10000:
            raise NodeExecutorError("send_email.body > 10000 chars")

        cc = config.get("cc") or []
        if cc and not isinstance(cc, list):
            raise NodeExecutorError("send_email.cc must be list[str]")

        # Idempotency: same node-in-run produces same source_ref so a
        # retry hits the partial unique index + we get the existing
        # outbox_id instead of a duplicate send.
        source_ref = ctx.idempotency_key or (
            f"wf:{ctx.run_id}:{ctx.node_id}"
        )

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            # Check existing first (idempotency dedup).
            existing = await conn.fetchrow(
                "SELECT outbox_id FROM notification_outbox "
                "WHERE enterprise_id = $1 AND source_ref = $2 LIMIT 1",
                ctx.enterprise_id, source_ref,
            )
            if existing:
                log.info("send_email.dedup_hit",
                         source_ref=source_ref,
                         outbox_id=str(existing["outbox_id"]),
                         enterprise_id=str(ctx.enterprise_id))
                return NodeResult(
                    status="completed",
                    output_data={
                        "outbox_id":  str(existing["outbox_id"]),
                        "recipient":  to_addr,
                        "queued":     True,
                        "dedup_hit":  True,
                    },
                )

            context_payload: dict[str, Any] = {
                "subject":  subject,
                "body":     body,
                "cc":       cc,
            }
            row = await conn.fetchrow(
                """INSERT INTO notification_outbox
                       (enterprise_id, template, recipient_email,
                        context, source_ref)
                   VALUES ($1, 'workflow-freeform', $2, $3, $4)
                   RETURNING outbox_id""",
                ctx.enterprise_id, to_addr, context_payload, source_ref,
            )

        log.info("send_email.queued",
                 outbox_id=str(row["outbox_id"]),
                 recipient=to_addr,
                 source_ref=source_ref,
                 enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "outbox_id":  str(row["outbox_id"]),
                "recipient":  to_addr,
                "queued":     True,
                "dedup_hit":  False,
            },
        )
