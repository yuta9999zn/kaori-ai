"""
approval_gate + read_form_submission executors.

approval_gate pauses the workflow run by returning NodeResult(
status='awaiting_approval'). The runner records the pause in
workflow_run_nodes.status=awaiting_approval + workflow_runs.status=
awaiting_approval. A later POST /workflow-runs/{run_id}/approve resumes
from the pause point.

read_form_submission reads a pending form submission from the
workflow_form_submissions table (mig 089). The caller (UI or webhook
intake) creates the row before triggering the workflow run.

K-17:
  approval_gate          = write_idempotent (UPSERT into workflow_approvals
                            by (run_id, node_id) → same row updated on
                            retry; the pause itself idempotent)
  read_form_submission   = read_only (SELECT only)

K-13 IDOR safety: approval_gate validates approver_role / approver_user_id
against the workflow_approvals row when the resume endpoint fires (not
inside execute() — execute() only records who CAN approve).
"""
from __future__ import annotations

import json
from typing import Any, Optional
from uuid import UUID

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import _resolve

log = structlog.get_logger()


class ApprovalGateExecutor(NodeExecutor):
    """approval_gate — pause the run until a human approves.

    Config:
      approver_role:   'MANAGER' | 'DIRECTOR' | 'CFO' | 'SUPER_ADMIN'
                       (one of these, or list[str] if multiple roles
                       can approve)
      approver_user_id: $.upstream.user_id  (optional — pin to specific user)
      auto_threshold:  {field: '$.upstream.amount', op: '<', value: 10_000_000}
                       (optional — auto-approve when condition true)
      sla_minutes:     240   (optional — runner can timeout + escalate)
      reason_prompt:   "Vui lòng review ..."   (optional context for approver UI)

    Output (when paused):
      {paused: True, approval_id: UUID-str, approver_role: str,
       requested_at: ISO-ts}
    Output (when auto-approved):
      {paused: False, auto_approved: True, reason: 'threshold_below'}
    """
    node_type_key = "approval_gate"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        approver_role_raw = config.get("approver_role")
        chain_id = config.get("approval_chain_id")
        if isinstance(approver_role_raw, str):
            approver_roles = [approver_role_raw.strip()] if approver_role_raw.strip() else []
        elif isinstance(approver_role_raw, list):
            # strip + drop whitespace-only entries — a role of "  " can never
            # match a real user role on resume, so it must not pass validation.
            approver_roles = [str(r).strip() for r in approver_role_raw if str(r).strip()]
        elif approver_role_raw is None:
            approver_roles = []
        else:
            raise NodeExecutorError("approval_gate.approver_role must be str or list[str]")

        # ADR-0037 — a gate binds approvers via approval_chain_id (preferred; the
        # roles come from the chain's level 1 below) OR an explicit approver_role.
        # Require at least one; chain-only is valid (roles filled from the chain).
        if not approver_roles and not chain_id:
            raise NodeExecutorError(
                "approval_gate requires approval_chain_id or a non-empty approver_role")

        approver_user_id = _resolve(config.get("approver_user_id"), ctx)
        sla_minutes = int(config.get("sla_minutes") or 240)
        reason_prompt = str(config.get("reason_prompt") or "")[:1000]

        # Phase 2.7 P3 — declarative policy gate. Build a context dict
        # from the node's upstream resolved values + run metadata; ask
        # the policy engine if any rule matches. Three outcomes:
        #   deny             → raise NodeExecutorError (hard refuse)
        #   require_approval → force approver_roles + sla_minutes from
        #                       action_params, SKIP auto_threshold
        #                       short-circuit (policy wins over config)
        #   allow / no match → fall through to config's auto_threshold
        try:
            from ai_orchestrator.shared.policy_engine import evaluate as _policy_evaluate
            policy_ctx = {
                "enterprise_id":   str(ctx.enterprise_id),
                "node_type_key":   "approval_gate",
                "department_type": str(_resolve(
                    config.get("department_type_ref") or "$.upstream.department_type",
                    ctx,
                ) or ""),
                "amount_vnd":      _resolve(
                    config.get("amount_vnd_ref") or "$.upstream.amount_vnd",
                    ctx,
                ),
                "role":            str(_resolve("$.upstream.role", ctx) or ""),
            }
            decision = await _policy_evaluate(policy_ctx)
        except Exception:  # noqa: BLE001
            log.exception(
                "approval_gate.policy_evaluate_failed",
                run_id=str(ctx.run_id), node_id=str(ctx.node_id),
            )
            decision = None

        policy_forced_approval = False
        if decision is not None and decision.matched:
            if decision.action == "deny":
                raise NodeExecutorError(
                    f"approval_gate denied by policy '{decision.rule_key}': "
                    f"{decision.reason}"
                )
            if decision.action == "require_approval":
                policy_forced_approval = True
                forced_role = decision.action_params.get("required_role")
                if forced_role:
                    approver_roles = [str(forced_role)]
                forced_sla = decision.action_params.get("sla_minutes")
                if forced_sla:
                    try:
                        sla_minutes = int(forced_sla)
                    except (TypeError, ValueError):
                        pass  # keep config sla
                log.info(
                    "approval_gate.policy_require_approval",
                    rule_key=decision.rule_key,
                    forced_role=forced_role, forced_sla=forced_sla,
                    run_id=str(ctx.run_id), node_id=str(ctx.node_id),
                )

        # Auto-threshold check — skip approval when condition true. POLICY
        # OVERRIDE: if a require_approval rule matched, do NOT honor
        # auto_threshold (the rule expressly says "needs human").
        auto_threshold = config.get("auto_threshold")
        if not policy_forced_approval and isinstance(auto_threshold, dict):
            field_val = _resolve(auto_threshold.get("field"), ctx)
            op = auto_threshold.get("op")
            comp_val = auto_threshold.get("value")
            if _eval_threshold(field_val, op, comp_val):
                log.info("approval_gate.auto_approved",
                          run_id=str(ctx.run_id),
                          node_id=str(ctx.node_id),
                          field=auto_threshold.get("field"),
                          op=op, value=comp_val)
                return NodeResult(
                    status="completed",
                    output_data={
                        "paused": False,
                        "auto_approved": True,
                        "reason": "threshold_below",
                        "approver_roles": approver_roles,
                    },
                )

        from ai_orchestrator.shared.db import acquire_for_tenant

        # ADR-0037 Phase 2 — chained approval. When config.approval_chain_id is
        # set, the gate opens at LEVEL 1: load that level's roles + SLA and stamp
        # chain_id/level_no so the approve endpoint can walk levels in order. The
        # chain advances IN-PLACE on the same row (UNIQUE run_id,node_id stays).
        level_no = None

        # UPSERT into workflow_approvals — retry-safe by (run_id, node_id).
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            if chain_id:
                lvl = await conn.fetchrow(
                    """SELECT level_no, approver_roles, sla_minutes
                       FROM approval_levels WHERE chain_id = $1
                       ORDER BY level_no LIMIT 1""", chain_id)
                if lvl is not None:
                    approver_roles = list(lvl["approver_roles"]) or approver_roles
                    sla_minutes = lvl["sla_minutes"] or sla_minutes
                    level_no = lvl["level_no"]
                # Fail loud (K-3) — a chain-only gate whose chain yields no
                # approver roles would pause a live run with nobody to approve.
                # The builder's run-readiness check blocks this, but guard the
                # runtime too in case a chain was emptied after activation.
                if not approver_roles:
                    raise NodeExecutorError(
                        f"approval_gate chain {chain_id} resolved no approver roles")
            row = await conn.fetchrow(
                """INSERT INTO workflow_approvals
                       (run_id, node_id, enterprise_id, approver_roles,
                        approver_user_id, sla_minutes, reason_prompt,
                        status, chain_id, level_no)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', $8, $9)
                   ON CONFLICT (run_id, node_id) DO UPDATE
                   SET approver_roles = EXCLUDED.approver_roles,
                       approver_user_id = EXCLUDED.approver_user_id,
                       sla_minutes = EXCLUDED.sla_minutes,
                       reason_prompt = EXCLUDED.reason_prompt,
                       chain_id = EXCLUDED.chain_id,
                       level_no = EXCLUDED.level_no
                   RETURNING approval_id, created_at""",
                ctx.run_id, ctx.node_id, ctx.enterprise_id,
                approver_roles, approver_user_id, sla_minutes, reason_prompt,
                chain_id, level_no,
            )

        return NodeResult(
            status="awaiting_approval",
            output_data={
                "paused":         True,
                "approval_id":    str(row["approval_id"]),
                "approver_roles": approver_roles,
                "approver_user_id": str(approver_user_id) if approver_user_id else None,
                "requested_at":   row["created_at"].isoformat(),
                "sla_minutes":    sla_minutes,
                "reason_prompt":  reason_prompt,
                "chain_id":       str(chain_id) if chain_id else None,
                "level_no":       level_no,
            },
        )


def _eval_threshold(field_val: Any, op: Any, comp_val: Any) -> bool:
    """Same logic as if_else._eval_condition but bare-leaf.
    Returns False on any type mismatch or unknown op."""
    if op not in ("<", "<=", ">", ">=", "==", "!="):
        return False
    try:
        if op == "<":  return field_val < comp_val
        if op == "<=": return field_val <= comp_val
        if op == ">":  return field_val > comp_val
        if op == ">=": return field_val >= comp_val
        if op == "==": return field_val == comp_val
        if op == "!=": return field_val != comp_val
    except TypeError:
        return False
    return False


class ReadFormSubmissionExecutor(NodeExecutor):
    """read_form_submission — pull a single submitted form payload.

    Config:
      form_key:        'refund_request'  (string identifier — matches
                                          submission row's form_key column)
      submission_id:   $.input.submission_id   (optional — when caller
                                                passes specific row)
      latest_for_form: True            (optional — if no submission_id,
                                         pick newest unprocessed row)
    Output:
      {submission_id: UUID-str, form_key: str, payload: dict,
       submitted_by_user_id: UUID-str | None, submitted_at: ISO-ts}

    K-12: RLS via acquire_for_tenant — submissions are tenant-scoped.
    K-17: read_only — no DB mutation.
    """
    node_type_key = "read_form_submission"
    side_effect_class = SideEffectClass.READ_ONLY

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        form_key = config.get("form_key")
        if not form_key or not isinstance(form_key, str):
            raise NodeExecutorError("read_form_submission.form_key required (string)")

        submission_id = _resolve(config.get("submission_id"), ctx)
        latest_for_form = bool(config.get("latest_for_form"))

        # Also accept submission_id from workflow run's input_data
        if not submission_id and "submission_id" in (ctx.input_data or {}):
            submission_id = ctx.input_data["submission_id"]

        if not submission_id and not latest_for_form:
            raise NodeExecutorError(
                "read_form_submission: provide either submission_id "
                "(from config or run input_data) or latest_for_form=True"
            )

        # Validate UUID before opening DB connection — keeps unit tests
        # that monkey-patch the pool safe.
        sid: Optional[UUID] = None
        if submission_id:
            try:
                sid = UUID(str(submission_id))
            except ValueError:
                raise NodeExecutorError(
                    f"read_form_submission.submission_id not a UUID: {submission_id!r}"
                )

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            if sid is not None:
                row = await conn.fetchrow(
                    """SELECT submission_id, form_key, payload,
                              submitted_by_user_id, submitted_at
                       FROM workflow_form_submissions
                       WHERE submission_id = $1 AND form_key = $2""",
                    sid, form_key,
                )
            else:
                row = await conn.fetchrow(
                    """SELECT submission_id, form_key, payload,
                              submitted_by_user_id, submitted_at
                       FROM workflow_form_submissions
                       WHERE form_key = $1 AND status = 'pending'
                       ORDER BY submitted_at ASC LIMIT 1""",
                    form_key,
                )

        if row is None:
            return NodeResult(
                status="completed",
                output_data={
                    "found": False, "form_key": form_key,
                    "submission_id": None, "payload": None,
                },
            )

        payload = row["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}

        return NodeResult(
            status="completed",
            output_data={
                "found":                True,
                "form_key":             row["form_key"],
                "submission_id":        str(row["submission_id"]),
                "payload":              payload,
                "submitted_by_user_id": (
                    str(row["submitted_by_user_id"])
                    if row["submitted_by_user_id"] else None
                ),
                "submitted_at":         row["submitted_at"].isoformat(),
            },
        )
