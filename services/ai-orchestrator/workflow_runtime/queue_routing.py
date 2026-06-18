"""
Queue routing config — P1.2 of orchestration hardening.

Pre-P1.2: every Temporal activity ran on a single task_queue
`kaori-default`. PM mining batch job COULD block invoice approval.

P1.2 splits work into tiered queues:

  kaori-critical-finance   high-value approval flows + payment + billing
  kaori-default            general workflows (most templates)
  kaori-low-priority       PM mining, analytics, NOV monthly digest,
                            memory maintenance, adoption hourly

Routing decision = function of (side_effect_class, node_type_key,
workflow's department_type). Defaults are conservative — if no specific
rule matches, route to `kaori-default`.

Activation
----------
P1.2 ships the ROUTING TABLE + decorator + tests. Actual worker pool
deployment requires:
  1. Temporal cluster up (TEMPORAL_ENABLE_WORKER=true)
  2. Multiple worker processes started with different task_queue env vars
  3. K8s manifest with N replicas per tier

The runbook (docs/runbooks/workflow-execution-enable.md §3c) is
extended with the queue registration commands.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Canonical queue names — extend by adding to this enum + ROUTING_RULES.
QUEUE_CRITICAL_FINANCE   = "kaori-critical-finance"
QUEUE_DEFAULT            = "kaori-default"
QUEUE_LOW_PRIORITY       = "kaori-low-priority"

ALL_QUEUES = frozenset({
    QUEUE_CRITICAL_FINANCE,
    QUEUE_DEFAULT,
    QUEUE_LOW_PRIORITY,
})


# Routing rules — first matching rule wins. Each rule is a dict with:
#   match_node_types   set[str]    — exact match on node_type_key
#   match_departments  set[str]    — exact match on workflow.department_type
#   match_side_effects set[str]    — match on side_effect_class
#   queue              str         — target queue name
#
# All three match keys are AND'd. Empty set = wildcard (match all).
_RULES: tuple[dict, ...] = (
    # Priority 1: finance approval flows route to critical queue.
    # These are typically high-value monetary actions where queue
    # latency directly translates to business risk.
    {
        "match_node_types":   {"approval_gate", "call_api"},
        "match_departments":  {"finance"},
        "match_side_effects": set(),
        "queue":              QUEUE_CRITICAL_FINANCE,
    },
    # Priority 2: high-value finance writes regardless of department.
    {
        "match_node_types":   {"save_to_database", "update_record"},
        "match_departments":  {"finance"},
        "match_side_effects": set(),
        "queue":              QUEUE_CRITICAL_FINANCE,
    },
    # Priority 3: low-priority — analytics + process mining + memory
    # maintenance. These are large bounded jobs; latency tolerance is
    # high so they're isolated from interactive flows.
    {
        "match_node_types":   {"call_forecasting", "rag_query",
                                "extract_entities", "call_recommendation_engine"},
        "match_departments":  set(),
        "match_side_effects": set(),
        "queue":              QUEUE_LOW_PRIORITY,
    },
    # Priority 4: PM mining + adoption batch (workflow_type names
    # the worker registers — handled by activity name routing below).
)


# Direct activity-name → queue mapping for Temporal activities (not
# in-process node executors). Adoption hourly aggregator + NOV monthly
# + memory maintenance all run on the low-priority queue.
_ACTIVITY_QUEUE_MAP: dict[str, str] = {
    "list_active_tenants_for_adoption":   QUEUE_LOW_PRIORITY,
    "compute_tenant_health_snapshot":     QUEUE_LOW_PRIORITY,
    "persist_health_snapshot":            QUEUE_LOW_PRIORITY,
    "trigger_intervention_if_needed":     QUEUE_LOW_PRIORITY,

    "gather_nov_inputs":                  QUEUE_LOW_PRIORITY,
    "compute_nov_for_month":              QUEUE_LOW_PRIORITY,
    "persist_nov_digest":                 QUEUE_LOW_PRIORITY,
    "maybe_dispatch_negative_alert":      QUEUE_LOW_PRIORITY,

    "memory_consolidate_for_tenant":      QUEUE_LOW_PRIORITY,
    "memory_promote_for_tenant":          QUEUE_LOW_PRIORITY,
    "memory_promote_kb_for_tenant":       QUEUE_LOW_PRIORITY,
    "escalate_stale_approvals_for_tenant": QUEUE_LOW_PRIORITY,
    "memory_forget_sweep_for_tenant":     QUEUE_LOW_PRIORITY,
    "memory_embed_pending_for_tenant":    QUEUE_LOW_PRIORITY,
    "loop_evaluate_for_tenant":           QUEUE_LOW_PRIORITY,

    # analyze_pipeline activities go to default — they ARE the interactive
    # path users invoke from the wizard.
    "parse_input":                         QUEUE_DEFAULT,
    "load_pipeline_run":                   QUEUE_DEFAULT,
    "upsert_run_status":                   QUEUE_DEFAULT,
    "insert_decision_audit":               QUEUE_DEFAULT,
    "send_completion_notification":        QUEUE_DEFAULT,
}


@dataclass(frozen=True)
class RoutingInputs:
    """Inputs to the routing decision. Caller passes what it knows;
    missing fields are treated as wildcards."""
    node_type_key:      Optional[str] = None
    department_type:    Optional[str] = None
    side_effect_class:  Optional[str] = None


def route_node_to_queue(inputs: RoutingInputs) -> str:
    """Return the queue name for a node + workflow context. Falls
    through to QUEUE_DEFAULT when no rule matches.

    Determinism: ties are resolved by rule order (first match wins),
    so rule order in _RULES matters.
    """
    for rule in _RULES:
        if rule["match_node_types"]:
            if inputs.node_type_key not in rule["match_node_types"]:
                continue
        if rule["match_departments"]:
            if inputs.department_type not in rule["match_departments"]:
                continue
        if rule["match_side_effects"]:
            if inputs.side_effect_class not in rule["match_side_effects"]:
                continue
        return rule["queue"]
    return QUEUE_DEFAULT


def route_activity_to_queue(activity_name: str) -> str:
    """Direct activity-name routing for Temporal activities registered
    on the worker. Returns QUEUE_DEFAULT if the activity is not in the
    explicit map — caller's responsibility to keep the map current."""
    return _ACTIVITY_QUEUE_MAP.get(activity_name, QUEUE_DEFAULT)


def all_queues() -> frozenset[str]:
    """For worker deployment runbook + the K8s manifest generator."""
    return ALL_QUEUES


def activities_for_queue(queue_name: str) -> list[str]:
    """Inverse: list activity names assigned to a queue. Used by the
    worker entrypoint when a process is started with a specific queue."""
    return sorted(
        a for a, q in _ACTIVITY_QUEUE_MAP.items()
        if q == queue_name
    )
