"""
Kafka consumer — listens on kaori.pipeline.* topics and triggers analysis.

kaori.pipeline.silver.complete   → run eligible templates automatically
                                   (if user opted in)
kaori.pipeline.analysis.complete → (log only, for cross-service tracing)
"""
import asyncio
import json
import os

import structlog
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from ..reasoning.legacy_analytics.runner import run_analysis_for_run
from ..shared import kafka_topics
from ..shared.db import acquire_for_tenant, get_pool
from ..shared.event_schema import raise_or_dlq
from ..shared.outbox import DuplicateEvent, mark_processed

log = structlog.get_logger()

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
CONSUMER_GROUP = "kaori-orchestrator"

_running = True


async def start_pipeline_consumer() -> None:
    # Phase 2 #8 — manual offset commits. The previous setup had
    # enable_auto_commit=True with auto_offset_reset='latest' which means a
    # restart between fetch and dispatch silently skipped events: aiokafka
    # had auto-committed past them, and 'latest' on the next boot started
    # consuming new arrivals only. Outbox dedupe is helpless against this
    # because the dedupe row was never written.
    #
    # New invariant: the consumer commits the offset ONLY after _dispatch
    # has finished successfully (mark_processed succeeded OR DuplicateEvent
    # handled). 'earliest' is now safe to set as default because the dedupe
    # table guarantees no event runs twice across consumer-group lifetimes.
    consumer = AIOKafkaConsumer(
        kafka_topics.PIPELINE_SILVER_COMPLETE,
        kafka_topics.PIPELINE_ANALYSIS_COMPLETE,
        # Gap 4 — listen on bronze_complete to auto-fire KPI compute when
        # the upload is attached to a workflow step. Routing key carries
        # workflow_id + workflow_step_id + department_id (see ingestor.py).
        kafka_topics.PIPELINE_BRONZE_COMPLETE,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda b: json.loads(b.decode()),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )
    # Issue #4 — DLQ producer for payloads that fail schema validation.
    # Schema-bad messages would otherwise loop forever (handler raises →
    # no commit → redelivery → same failure). Routing them to
    # ``kaori.dlq.<topic>`` lets ops replay after the producer is fixed
    # without losing the message and without holding up the partition.
    dlq = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await consumer.start()
    await dlq.start()
    log.info("orchestrator.consumer.started")

    try:
        async for msg in consumer:
            if not _running:
                break
            try:
                # Validate first. On schema failure raise_or_dlq returns
                # False after writing to the DLQ; we commit the offset and
                # skip the business work for THIS message. On success it
                # returns True and we proceed to _dispatch as before.
                ok = await raise_or_dlq(
                    msg.topic, msg.value, dlq,
                    consumer_group=CONSUMER_GROUP,
                    headers=list(msg.headers or []),
                    key=msg.key,
                )
                if ok:
                    await _dispatch(msg.topic, msg.value, msg.key)
                # Commit either way — schema-bad messages are now in the
                # DLQ, so re-reading them would just re-DLQ them. On the
                # successful path, commit only after dispatch finished
                # cleanly (the existing at-least-once guarantee still
                # applies — mark_processed dedupes on redelivery).
                await consumer.commit()
            except Exception as exc:
                log.error(
                    "orchestrator.consumer.dispatch_error",
                    topic=msg.topic,
                    offset=msg.offset,
                    error=str(exc),
                )
                # No commit → at-least-once redelivery on next poll.
    finally:
        await consumer.stop()
        await dlq.stop()
        log.info("orchestrator.consumer.stopped")


async def stop_pipeline_consumer() -> None:
    global _running
    _running = False


async def _dispatch(topic: str, payload: dict, message_key: bytes | None) -> None:
    # G5: dedupe by message key (set by the outbox publisher to the
    # outbox_id). Legacy events produced without the outbox have no
    # key — fall through and process at-least-once until the producer
    # is migrated.
    #
    # NB: this `mark_processed` write hits the consumer-group dedup table
    # which is system-level (NOT tenant-scoped). Intentionally uses raw
    # `pool.acquire()` — when G4c flips kaori_app to NOBYPASSRLS, the
    # outbox tables have NO RLS policies so this stays valid. Only the
    # downstream tenant-scoped reads in _handle_silver_complete need
    # acquire_for_tenant.
    if message_key is not None:
        event_id = message_key.decode()
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await mark_processed(conn, event_id, CONSUMER_GROUP)
        except DuplicateEvent:
            log.info(
                "orchestrator.consumer.duplicate_skipped",
                event_id=event_id,
                topic=topic,
            )
            return

    if topic == kafka_topics.PIPELINE_SILVER_COMPLETE:
        await _handle_silver_complete(payload)
    elif topic == kafka_topics.PIPELINE_BRONZE_COMPLETE:
        await _handle_bronze_complete(payload)
    elif topic == kafka_topics.PIPELINE_ANALYSIS_COMPLETE:
        log.info("orchestrator.analysis.complete_event", run_id=payload.get("run_id"))


async def _handle_silver_complete(payload: dict) -> None:
    """
    When Silver layer is ready, check if there's a pending analysis request.
    analysis_runs rows in status='queued' are picked up here.
    """
    run_id = payload.get("run_id")
    enterprise_id = payload.get("enterprise_id")
    if not run_id or not enterprise_id:
        log.warning("orchestrator.consumer.missing_fields", payload=payload)
        return

    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch("""
            SELECT id, templates, config
            FROM analysis_runs
            WHERE run_id = $1
              AND enterprise_id = $2
              AND status = 'queued'
            ORDER BY created_at ASC
        """, run_id, enterprise_id)

    if not rows:
        log.debug("orchestrator.consumer.no_queued_runs", run_id=run_id)
        return

    import json as _json
    for row in rows:
        log.info("orchestrator.consumer.dispatching",
                 analysis_run_id=str(row["id"]), run_id=run_id)
        cfg = row["config"]
        if isinstance(cfg, str):
            cfg = _json.loads(cfg) if cfg else {}
        cfg = cfg or {}
        asyncio.create_task(
            run_analysis_for_run(
                analysis_run_id=str(row["id"]),
                run_id=run_id,
                enterprise_id=enterprise_id,
                templates=list(row["templates"]) if row["templates"] else [],
                config=cfg,
            )
        )


async def _handle_bronze_complete(payload: dict) -> None:
    """
    Gap 4 — when a workflow-attached upload finishes Bronze landing, run
    every active KPI for the department's dept_type and persist results
    to kpi_measurements (the FE Báo cáo tab reads from there).

    Non-workflow uploads (legacy /upload without X-Workflow-Step-ID) are
    skipped silently — the producer omits workflow_step_id in that case.

    Gold view may not be populated yet on the very first upload; KPI rows
    with raw_value=None are skipped here and re-computed on a subsequent
    upload once Gold catches up. The kpi_measurements UNIQUE constraint
    on (enterprise_id, department_id, kpi_code, period_kind, period_start)
    makes the upsert idempotent across retries.
    """
    workflow_step_id = payload.get("workflow_step_id")
    workflow_id      = payload.get("workflow_id")
    enterprise_id    = payload.get("enterprise_id")
    department_id    = payload.get("department_id")
    branch_id        = payload.get("branch_id")

    if not (workflow_step_id and workflow_id and enterprise_id and department_id):
        log.debug(
            "orchestrator.kpi.skip_not_workflow",
            run_id=payload.get("run_id"),
        )
        return

    from datetime import date
    from ..reasoning.kpi_engine import compute_kpi, list_kpis_for_dept

    today        = date.today()
    period_start = today.replace(day=1)
    period_end   = today

    async with acquire_for_tenant(enterprise_id) as conn:
        # kpi_definitions is keyed by dept_type, not department_id —
        # all Sales depts across the enterprise share the same KPIs.
        dept_row = await conn.fetchrow(
            "SELECT dept_type FROM departments WHERE department_id = $1",
            department_id,
        )
        if dept_row is None or not dept_row["dept_type"]:
            log.warning(
                "orchestrator.kpi.dept_type_missing",
                department_id=department_id,
            )
            return
        dept_type = dept_row["dept_type"]

        kpis = await list_kpis_for_dept(conn, dept_type=dept_type)
        if not kpis:
            log.info(
                "orchestrator.kpi.no_kpis_for_dept",
                dept_type=dept_type, department_id=department_id,
            )
            return

        ok      = 0
        skipped = 0
        for kpi in kpis:
            try:
                measurement = await compute_kpi(
                    conn,
                    enterprise_id=enterprise_id,
                    department_id=department_id,
                    kpi_code=kpi.kpi_code,
                    dept_type=dept_type,
                    period_start=period_start,
                    period_end=period_end,
                    branch_id=branch_id,
                    skip_benchmark=True,
                )
            except Exception as exc:
                log.warning(
                    "orchestrator.kpi.compute_failed",
                    kpi_code=kpi.kpi_code, error=str(exc),
                )
                skipped += 1
                continue

            if measurement.raw_value is None:
                skipped += 1
                continue

            await conn.execute(
                """INSERT INTO kpi_measurements (
                       enterprise_id, department_id, branch_id, kpi_code,
                       period_start, period_end, period_kind,
                       raw_value, classification,
                       sql_executed, sql_row_count,
                       computed_at, computed_by)
                   VALUES ($1, $2, $3, $4, $5, $6, 'monthly',
                           $7, $8, $9, $10, NOW(), 'workflow_upload')
                   ON CONFLICT (enterprise_id, department_id, kpi_code,
                                period_kind, period_start)
                   DO UPDATE SET raw_value=$7, classification=$8,
                                 sql_executed=$9, sql_row_count=$10,
                                 computed_at=NOW(),
                                 computed_by='workflow_upload'""",
                enterprise_id, department_id,
                branch_id, kpi.kpi_code,
                period_start, period_end,
                measurement.raw_value, measurement.classification,
                measurement.sql_executed, measurement.sql_row_count,
            )
            ok += 1

        log.info(
            "orchestrator.kpi.workflow_upload_done",
            workflow_id=workflow_id,
            workflow_step_id=workflow_step_id,
            department_id=department_id,
            dept_type=dept_type,
            measurements_written=ok,
            measurements_skipped=skipped,
            total_kpis=len(kpis),
        )
