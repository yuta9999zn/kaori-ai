"""
Workflow activities — first set, one per side-effect class.

K-17 invariant: every activity declares the side_effect_class it falls
under so the Action Runtime + idempotency layer can apply the right
retry / dedup / saga policy. The class is recorded in the activity's
docstring AND on the matching workflow YAML node — they MUST agree.

The set ships covers every class so tests can validate end-to-end
taxonomy coverage without a fake activity:

    pure                  parse_input
    read_only             load_pipeline_run
    write_idempotent      upsert_run_status
    write_non_idempotent  insert_decision_audit
    external              send_completion_notification

Phase 1.5+ adds activities incrementally — each new one declares its
class in module docstring and registers via the worker's
``register_activities()`` listing.

See:
  * docs/strategic/WORKFLOW_SYSTEM.md PART V
  * docs/adr/0014-at-least-once-plus-idempotency.md
"""
from __future__ import annotations

from .analyze import (
    insert_decision_audit,
    load_pipeline_run,
    parse_input,
    send_completion_notification,
    upsert_run_status,
)
from .economics import (
    compute_nov_for_month,
    gather_nov_inputs,
    maybe_dispatch_negative_alert,
    persist_nov_digest,
)
from .memory_loop import (
    loop_evaluate_for_tenant,
    memory_consolidate_for_tenant,
    memory_embed_pending_for_tenant,
    memory_forget_sweep_for_tenant,
    memory_promote_for_tenant,
    memory_promote_kb_for_tenant,
)
from .adoption import (
    compute_tenant_health_snapshot,
    list_active_tenants_for_adoption,
    persist_health_snapshot,
    trigger_intervention_if_needed,
)
from .approval_escalation import escalate_stale_approvals_for_tenant

ALL_ACTIVITIES = (
    parse_input,
    load_pipeline_run,
    upsert_run_status,
    insert_decision_audit,
    send_completion_notification,
    gather_nov_inputs,
    compute_nov_for_month,
    persist_nov_digest,
    maybe_dispatch_negative_alert,
    memory_consolidate_for_tenant,
    memory_promote_for_tenant,
    memory_promote_kb_for_tenant,
    memory_forget_sweep_for_tenant,
    memory_embed_pending_for_tenant,
    loop_evaluate_for_tenant,
    list_active_tenants_for_adoption,
    compute_tenant_health_snapshot,
    persist_health_snapshot,
    trigger_intervention_if_needed,
    escalate_stale_approvals_for_tenant,
)

__all__ = [
    "ALL_ACTIVITIES",
    "parse_input",
    "load_pipeline_run",
    "upsert_run_status",
    "insert_decision_audit",
    "send_completion_notification",
    "gather_nov_inputs",
    "compute_nov_for_month",
    "persist_nov_digest",
    "maybe_dispatch_negative_alert",
    "memory_consolidate_for_tenant",
    "memory_promote_for_tenant",
    "memory_promote_kb_for_tenant",
    "memory_forget_sweep_for_tenant",
    "memory_embed_pending_for_tenant",
    "loop_evaluate_for_tenant",
    "list_active_tenants_for_adoption",
    "compute_tenant_health_snapshot",
    "persist_health_snapshot",
    "trigger_intervention_if_needed",
]
