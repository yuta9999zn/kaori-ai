"""
Tests for P1.2 queue routing — pure function tests, no infra needed.
Verifies the routing decision logic so config changes get caught.
"""
from __future__ import annotations

import pytest

from workflow_runtime.queue_routing import (
    ALL_QUEUES,
    QUEUE_CRITICAL_FINANCE,
    QUEUE_DEFAULT,
    QUEUE_LOW_PRIORITY,
    RoutingInputs,
    activities_for_queue,
    all_queues,
    route_activity_to_queue,
    route_node_to_queue,
)


class TestQueueConstants:
    def test_three_distinct_queues(self):
        assert len(ALL_QUEUES) == 3
        assert QUEUE_CRITICAL_FINANCE in ALL_QUEUES
        assert QUEUE_DEFAULT in ALL_QUEUES
        assert QUEUE_LOW_PRIORITY in ALL_QUEUES

    def test_all_queues_helper(self):
        assert all_queues() == ALL_QUEUES


class TestNodeRouting:
    def test_finance_approval_gate_goes_critical(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="approval_gate",
            department_type="finance",
        ))
        assert result == QUEUE_CRITICAL_FINANCE

    def test_finance_call_api_goes_critical(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="call_api",
            department_type="finance",
        ))
        assert result == QUEUE_CRITICAL_FINANCE

    def test_finance_save_to_db_goes_critical(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="save_to_database",
            department_type="finance",
        ))
        assert result == QUEUE_CRITICAL_FINANCE

    def test_finance_update_record_goes_critical(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="update_record",
            department_type="finance",
        ))
        assert result == QUEUE_CRITICAL_FINANCE

    def test_marketing_approval_gate_goes_default(self):
        """Approval gate routes critical only on finance — other depts
        use default queue."""
        result = route_node_to_queue(RoutingInputs(
            node_type_key="approval_gate",
            department_type="marketing",
        ))
        assert result == QUEUE_DEFAULT

    def test_forecasting_goes_low_priority(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="call_forecasting",
            department_type="sales",
        ))
        assert result == QUEUE_LOW_PRIORITY

    def test_rag_query_goes_low_priority(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="rag_query",
        ))
        assert result == QUEUE_LOW_PRIORITY

    def test_extract_entities_goes_low_priority(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="extract_entities",
        ))
        assert result == QUEUE_LOW_PRIORITY

    def test_call_recommendation_goes_low_priority(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="call_recommendation_engine",
        ))
        assert result == QUEUE_LOW_PRIORITY

    def test_unknown_node_falls_to_default(self):
        result = route_node_to_queue(RoutingInputs(
            node_type_key="never_seen_node",
            department_type="random_dept",
        ))
        assert result == QUEUE_DEFAULT

    def test_empty_inputs_defaults(self):
        result = route_node_to_queue(RoutingInputs())
        assert result == QUEUE_DEFAULT


class TestActivityRouting:
    def test_adoption_activities_go_low_priority(self):
        for activity in (
            "list_active_tenants_for_adoption",
            "compute_tenant_health_snapshot",
            "persist_health_snapshot",
            "trigger_intervention_if_needed",
        ):
            assert route_activity_to_queue(activity) == QUEUE_LOW_PRIORITY, activity

    def test_nov_activities_go_low_priority(self):
        for activity in (
            "gather_nov_inputs",
            "compute_nov_for_month",
            "persist_nov_digest",
            "maybe_dispatch_negative_alert",
        ):
            assert route_activity_to_queue(activity) == QUEUE_LOW_PRIORITY, activity

    def test_memory_activities_go_low_priority(self):
        for activity in (
            "memory_consolidate_for_tenant",
            "memory_promote_for_tenant",
            "memory_forget_sweep_for_tenant",
            "memory_embed_pending_for_tenant",
            "loop_evaluate_for_tenant",
        ):
            assert route_activity_to_queue(activity) == QUEUE_LOW_PRIORITY, activity

    def test_analyze_pipeline_activities_go_default(self):
        for activity in (
            "parse_input",
            "load_pipeline_run",
            "upsert_run_status",
            "insert_decision_audit",
            "send_completion_notification",
        ):
            assert route_activity_to_queue(activity) == QUEUE_DEFAULT, activity

    def test_unknown_activity_falls_to_default(self):
        assert route_activity_to_queue("nonexistent_activity") == QUEUE_DEFAULT


class TestActivitiesForQueue:
    def test_low_priority_queue_includes_adoption(self):
        activities = activities_for_queue(QUEUE_LOW_PRIORITY)
        assert "list_active_tenants_for_adoption" in activities
        assert "compute_nov_for_month" in activities
        assert "memory_consolidate_for_tenant" in activities

    def test_default_queue_includes_analyze(self):
        activities = activities_for_queue(QUEUE_DEFAULT)
        assert "parse_input" in activities
        assert "insert_decision_audit" in activities

    def test_critical_finance_queue_is_node_based_not_activity(self):
        # Activity map currently has no entries for critical-finance —
        # routing for that queue is via route_node_to_queue (node-level
        # only). This documents the design + protects against accidental
        # cross-pollination.
        activities = activities_for_queue(QUEUE_CRITICAL_FINANCE)
        assert activities == []

    def test_inverse_returns_sorted(self):
        activities = activities_for_queue(QUEUE_LOW_PRIORITY)
        assert activities == sorted(activities)


class TestRoutingDeterminism:
    """Routing must be stable across runs — same inputs = same queue."""
    def test_finance_approval_stable_across_calls(self):
        inp = RoutingInputs(node_type_key="approval_gate", department_type="finance")
        q1 = route_node_to_queue(inp)
        q2 = route_node_to_queue(inp)
        assert q1 == q2 == QUEUE_CRITICAL_FINANCE

    def test_finance_marketing_distinct(self):
        """Same node_type, different department → different queue."""
        finance = route_node_to_queue(RoutingInputs(
            node_type_key="approval_gate", department_type="finance"))
        marketing = route_node_to_queue(RoutingInputs(
            node_type_key="approval_gate", department_type="marketing"))
        assert finance != marketing
