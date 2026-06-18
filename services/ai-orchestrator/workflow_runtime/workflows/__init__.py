"""
Workflow types — first set, ships with the analyze_pipeline reference.

Each workflow lives in its own module so the worker can register it by
import without scanning. ``ALL_WORKFLOWS`` collects them for the worker
entrypoint; new workflow modules append to that tuple.

Convention:
  * Workflow class name = PascalCase of the workflow_id.
  * Workflow module name = snake_case matching the workflow_id.
  * The matching YAML lives at infrastructure/workflows/templates/{id}.yaml
    and validates against workflow_runtime.yaml_schema.workflow_yaml_schema().

Phase 1.5 P15-S9 D3 first ships analyze_pipeline (5 nodes covering all
5 side-effect classes). Real product workflows (churn_detection,
adoption_signal_dispatch, NOV_monthly_close) follow in D6/D7.
"""
from __future__ import annotations

from .adoption_hourly_aggregator import AdoptionHourlyAggregatorWorkflow
from .analyze_pipeline import AnalyzePipelineWorkflow
from .memory_loop_workflows import (
    LoopABEvaluateWorkflow,
    MemoryForgetSweepWorkflow,
    MemoryMaintenanceWorkflow,
)
from .nov_monthly_digest import NovMonthlyDigestWorkflow

ALL_WORKFLOWS = (
    AnalyzePipelineWorkflow,
    NovMonthlyDigestWorkflow,
    MemoryMaintenanceWorkflow,
    MemoryForgetSweepWorkflow,
    LoopABEvaluateWorkflow,
    AdoptionHourlyAggregatorWorkflow,
)

__all__ = [
    "ALL_WORKFLOWS",
    "AdoptionHourlyAggregatorWorkflow",
    "AnalyzePipelineWorkflow",
    "LoopABEvaluateWorkflow",
    "MemoryForgetSweepWorkflow",
    "MemoryMaintenanceWorkflow",
    "NovMonthlyDigestWorkflow",
]
