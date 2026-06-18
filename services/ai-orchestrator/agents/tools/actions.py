"""
F-061 action tools — write-side operations the agent loop can perform.

Two tools ship in v0:

  * ``draft_followup_email``       — record a follow-up email draft for
                                     a specific customer. dry_run
                                     skips the audit write.
  * ``mark_customer_for_review``   — flag a customer for MANAGER review
                                     by writing a ``decision_audit_log``
                                     row with ``decision_type
                                     ='agent.flag_for_review'``.

Both tools use the existing ``decision_audit_log`` table rather than
introducing a new ``agent_drafts`` / ``agent_flags`` schema. Reasons:

  1. The decision log already enforces append-only (rule on UPDATE/DELETE)
     and is RLS-protected — the right home for an audit-y artefact.
  2. The /p2/decisions list endpoint reads it already (F-029); the
     pilot dashboard surfaces agent actions for free.
  3. Adding tables for v0 is premature — we can promote to a dedicated
     ``agent_actions`` table in Phase 2.7 once shape stabilises.

Notification outbox is intentionally NOT written for v0. Reason: every
``draft_followup_email`` write would otherwise enqueue an email the
SMTP dispatcher might send. Email auto-send is a Phase 2.7 promotion
once the human-in-loop queue (M11 in the BRD) ships. For now the
``draft_followup_email`` tool RECORDS the draft so a MANAGER can
review on /p2/decisions, then manually fan it out via F-038
``distribute_report`` or the regular email channel.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog

from ...chat.tools.base import BaseTool, ToolContext
from ...reasoning.cdfl.empowerment import advise_for_result
from ...shared.db import acquire_for_tenant

log = structlog.get_logger()


# =========================================================================
# draft_followup_email
# =========================================================================


class DraftFollowupEmailTool(BaseTool):
    name = "draft_followup_email"
    # Empowerment (NNL-NTHT): records a reviewable draft, AI never auto-sends →
    # the human keeps the decision → option-PRESERVING for the user's OR.
    option_impact = "preserving"
    description = (
        "Soạn bản nháp email follow-up cho một khách hàng cụ thể. "
        "AI KHÔNG tự gửi — chỉ ghi lại bản nháp vào nhật ký quyết định "
        "để MANAGER xem trên /p2/decisions rồi quyết định gửi hay không."
    )
    scope = "enterprise"
    parameters = {
        "type": "object",
        "properties": {
            "customer_external_id": {
                "type": "string",
                "description": "ID khách hàng (theo nguồn dữ liệu gốc).",
                "minLength": 1,
                "maxLength": 200,
            },
            "subject": {
                "type": "string",
                "description": "Tiêu đề email (≤ 200 ký tự).",
                "minLength": 1,
                "maxLength": 200,
            },
            "body": {
                "type": "string",
                "description": "Nội dung email (tiếng Việt, ≤ 4000 ký tự).",
                "minLength": 1,
                "maxLength": 4000,
            },
        },
        "required": ["customer_external_id", "subject", "body"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict[str, Any]:
        customer_id = args.get("customer_external_id")
        subject     = args.get("subject")
        body        = args.get("body")

        # Argument validation — registry surfaces these as friendly tool
        # results so the planner / critic can self-correct on the next hop.
        if not customer_id or not isinstance(customer_id, str):
            raise ValueError("customer_external_id phải là string không rỗng")
        if not subject or not isinstance(subject, str) or len(subject) > 200:
            raise ValueError("subject phải có và ≤ 200 ký tự")
        if not body or not isinstance(body, str) or len(body) > 4000:
            raise ValueError("body phải có và ≤ 4000 ký tự")
        if not ctx.enterprise_id:
            raise ValueError("enterprise_id missing in ToolContext")

        preview = {
            "would_action":          "draft_followup_email",
            "customer_external_id":  customer_id,
            "subject":               subject,
            "body_chars":            len(body),
            "body_preview":          body[:200] + ("…" if len(body) > 200 else ""),
        }

        if ctx.dry_run:
            # Dry-run path — skip the DB write so the orchestrator can
            # show "if you re-run with dry_run=False, this is what would
            # happen". Tool result still has the draft so the critic
            # can validate shape.
            return {
                **preview,
                "side_effect_fired": False,
                "reason":            "dry_run=true — không ghi audit",
                "protection":        advise_for_result(self.option_impact),
            }

        # Side-effect path — write a decision_audit_log row tagged
        # ``agent.draft_email`` so /p2/decisions surfaces it. Append-only
        # (rule on the table blocks UPDATE/DELETE), RLS-scoped.
        decision_id = uuid4()
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            await conn.execute(
                """
                INSERT INTO decision_audit_log
                    (decision_id, enterprise_id, decision_type, subject,
                     chosen_value, confidence, method, reasoning,
                     alternatives, uncertainty_flags)
                VALUES
                    ($1, $2, $3, $4,
                     $5, $6, $7, $8,
                     $9::jsonb, $10::text[])
                """,
                decision_id,
                UUID(ctx.enterprise_id),
                "agent.draft_email",
                f"draft_followup_email→{customer_id}",
                f"subject={subject!r}",
                1.0,                           # confidence — agent is deterministic about its own draft
                "agent.action.v0",
                f"actor_user={ctx.user_id} body_chars={len(body)}",
                json.dumps([{"body": body, "subject": subject}], ensure_ascii=False),
                ["agent_draft", "needs_human_review"],
            )

        return {
            **preview,
            "side_effect_fired":  True,
            "audit_decision_id":  str(decision_id),
            "review_url":         f"/p2/decisions/{decision_id}",
            "protection":         advise_for_result(self.option_impact),
        }


# =========================================================================
# mark_customer_for_review
# =========================================================================


class MarkCustomerForReviewTool(BaseTool):
    name = "mark_customer_for_review"
    # Empowerment: flags for MANAGER review (human decides) → option-PRESERVING.
    option_impact = "preserving"
    description = (
        "Đánh dấu một khách hàng cần MANAGER review (tách biệt với "
        "is_actioned của F-060 — flag này dùng cho luồng review của agent, "
        "không phải đã xử lý). Ghi vào decision_audit_log."
    )
    scope = "enterprise"
    parameters = {
        "type": "object",
        "properties": {
            "customer_external_id": {
                "type": "string",
                "description": "ID khách hàng (theo nguồn dữ liệu gốc).",
                "minLength": 1,
                "maxLength": 200,
            },
            "reason": {
                "type": "string",
                "description": "Lý do đánh dấu (≤ 1000 ký tự, tiếng Việt).",
                "minLength": 1,
                "maxLength": 1000,
            },
            "priority": {
                "type": "string",
                "description": "Độ ưu tiên review.",
                "enum": ["low", "normal", "high"],
                "default": "normal",
            },
        },
        "required": ["customer_external_id", "reason"],
    }

    async def execute(self, args: dict, ctx: ToolContext) -> dict[str, Any]:
        customer_id = args.get("customer_external_id")
        reason      = args.get("reason")
        priority    = args.get("priority", "normal")

        if not customer_id or not isinstance(customer_id, str):
            raise ValueError("customer_external_id phải là string không rỗng")
        if not reason or not isinstance(reason, str) or len(reason) > 1000:
            raise ValueError("reason phải có và ≤ 1000 ký tự")
        if priority not in ("low", "normal", "high"):
            raise ValueError("priority phải là one of low/normal/high")
        if not ctx.enterprise_id:
            raise ValueError("enterprise_id missing in ToolContext")

        preview = {
            "would_action":         "mark_customer_for_review",
            "customer_external_id": customer_id,
            "reason":               reason,
            "priority":             priority,
            "marked_at":            datetime.now(timezone.utc).isoformat(),
        }

        if ctx.dry_run:
            return {
                **preview,
                "side_effect_fired": False,
                "reason_skipped":    "dry_run=true — không ghi audit",
                "protection":        advise_for_result(self.option_impact),
            }

        decision_id = uuid4()
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            await conn.execute(
                """
                INSERT INTO decision_audit_log
                    (decision_id, enterprise_id, decision_type, subject,
                     chosen_value, confidence, method, reasoning,
                     alternatives, uncertainty_flags)
                VALUES
                    ($1, $2, $3, $4,
                     $5, $6, $7, $8,
                     $9::jsonb, $10::text[])
                """,
                decision_id,
                UUID(ctx.enterprise_id),
                "agent.flag_for_review",
                f"mark_customer_for_review→{customer_id}",
                f"priority={priority}",
                1.0,
                "agent.action.v0",
                f"actor_user={ctx.user_id} reason_chars={len(reason)}",
                json.dumps([{"reason": reason}], ensure_ascii=False),
                ["agent_flag", priority, "needs_human_review"],
            )

        return {
            **preview,
            "side_effect_fired": True,
            "audit_decision_id": str(decision_id),
            "review_url":        f"/p2/decisions/{decision_id}",
            "protection":        advise_for_result(self.option_impact),
        }
