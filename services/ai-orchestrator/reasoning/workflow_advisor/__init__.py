"""Qwen Workflow Advisor (ADR-0040) — evaluate the workflow itself.

Deterministic rule detectors find issues (static structure + runtime events);
Qwen writes an optional grounded narrative. Engine sibling to kpi_engine.
"""
from .schema import CATEGORIES, SEVERITIES, finding, overall_health
from .service import evaluate, narrate

__all__ = ["evaluate", "narrate", "finding", "overall_health", "CATEGORIES", "SEVERITIES"]
