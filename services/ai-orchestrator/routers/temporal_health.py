"""
Temporal worker health endpoint — Gap 3 of chaos-matrix.md follow-up.

Closes the "schedules fire into a void" failure mode: if
`TEMPORAL_ENABLE_WORKER=true` is set but the worker process isn't
actually running (crashed, K8s pod not scheduled, image pull failed),
every cron + every `start_workflow()` call queues a task that no one
picks up. No surface, no alert.

This endpoint probes Temporal directly:
  - When TEMPORAL_ENABLE_WORKER is FALSE → returns `status=disabled`
    with 200. That's a deliberate config choice; not a fault.
  - When TRUE + workers present → 200 with worker count per queue.
  - When TRUE + zero workers on ALL critical queues → 503 so K8s
    readiness probe fails + ops gets a clear signal.
  - When the Temporal cluster itself is unreachable → 503 with
    error detail so ops can distinguish "no workers" from "no cluster".

K8s wiring (when activated):
  readinessProbe:
    httpGet:
      path: /health/temporal
      port: 8093
    periodSeconds: 30
    failureThreshold: 3   # 90s grace before pod marked unready
"""
from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse

log = structlog.get_logger()

router = APIRouter()


# Critical queues to probe. If TEMPORAL_ENABLE_WORKER is true and none
# of these has a registered worker, the runtime is unable to drain ANY
# scheduled crons (adoption hourly / NOV monthly / memory loops / etc.).
_PROBED_QUEUES = (
    "kaori-default",
    "kaori-critical-finance",
    "kaori-low-priority",
)


@router.get("/health/temporal")
async def temporal_health() -> Any:
    """K8s readiness probe target. Returns 200 with detail when
    healthy or deliberately disabled; 503 when the worker should be
    running but the cluster reports no pollers."""
    # Lazy import — temporal_client uses lazy `temporalio` import too,
    # so this stays cheap on the worker-disabled path.
    from ..workflow_runtime.temporal_client import TemporalConfig, connect

    cfg = TemporalConfig.from_env()

    # Case 1: worker disabled by config. Surface as `disabled` (NOT
    # failure) — early Phase 1.5 environments run without Temporal at
    # all + that's fine.
    if not cfg.enable_worker:
        return {
            "status":     "disabled",
            "reason":     "TEMPORAL_ENABLE_WORKER not truthy",
            "address":    cfg.address,
            "namespace":  cfg.namespace,
            "task_queue": cfg.task_queue,
            "worker_count": 0,
        }

    # Case 2: worker enabled — probe each critical queue's poller count.
    try:
        client = await connect(cfg)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "temporal.health.cluster_unreachable",
            address=cfg.address,
            error_type=type(exc).__name__,
            detail=str(exc)[:200],
        )
        return JSONResponse(
            status_code=503,
            content={
                "status":     "cluster_unreachable",
                "address":    cfg.address,
                "namespace":  cfg.namespace,
                "error_type": type(exc).__name__,
                "detail":     str(exc)[:500],
            },
        )

    queues_status: dict[str, int] = {}
    probe_error: dict[str, str] = {}

    try:
        from temporalio.api.enums.v1 import TaskQueueType
        from temporalio.api.taskqueue.v1 import TaskQueue
        from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
    except ImportError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "status": "sdk_missing",
                "detail": f"temporalio SDK not installed: {exc}",
            },
        )

    for queue in _PROBED_QUEUES:
        try:
            req = DescribeTaskQueueRequest(
                namespace=cfg.namespace,
                task_queue=TaskQueue(name=queue),
                task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
            )
            resp = await client.workflow_service.describe_task_queue(req)
            queues_status[queue] = len(resp.pollers)
        except Exception as exc:  # noqa: BLE001
            queues_status[queue] = 0
            probe_error[queue] = type(exc).__name__
            log.warning(
                "temporal.health.queue_probe_failed",
                queue=queue,
                error_type=type(exc).__name__,
                detail=str(exc)[:200],
            )

    total_workers = sum(queues_status.values())

    body = {
        "status":        "healthy" if total_workers > 0 else "no_workers",
        "address":       cfg.address,
        "namespace":     cfg.namespace,
        "primary_queue": cfg.task_queue,
        "queues":        queues_status,
        "total_workers": total_workers,
    }
    if probe_error:
        body["probe_errors"] = probe_error

    if total_workers == 0:
        body["detail"] = (
            "TEMPORAL_ENABLE_WORKER=true but no workers registered on any "
            "critical queue. Either the worker pod isn't running or it "
            "registered to a different queue."
        )
        return JSONResponse(status_code=503, content=body)
    return body
