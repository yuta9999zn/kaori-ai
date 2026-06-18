"""
External/integration action executors — wave 3 of workflow-gap closeout.

3 executors that talk to external systems or chain workflow runs:

  call_api           external — generic HTTP POST/GET with K-13 idempotency
  trigger_workflow   write_non_idempotent — start a child workflow run
  generate_report    write_idempotent — INSERT into reports queue
                                          (poller renders + delivers)

K-3 NA — these are not LLM calls but external service integrations.
K-13 idempotency: call_api derives source_ref from (run_id, node_id) so
                  a retry of the same node hits the dedup record and
                  short-circuits without re-firing.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Optional
from uuid import UUID

import httpx
import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeExecutorError, NodeResult
from ..side_effect import SideEffectClass
from .pure import _resolve

log = structlog.get_logger()


# ─── 1. call_api ────────────────────────────────────────────────────


# Hosts the workflow runner is allowed to call. Set via env so prod can
# tighten beyond dev defaults. Comma-separated.
_ALLOWED_HOST_ENV = "WORKFLOW_CALL_API_ALLOWED_HOSTS"
_ALLOWED_HOSTS_DEFAULT = "localhost,127.0.0.1,llm-gateway,notification-service,ai-orchestrator"


def _allowed_hosts() -> set[str]:
    raw = os.getenv(_ALLOWED_HOST_ENV, _ALLOWED_HOSTS_DEFAULT)
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


class CallApiExecutor(NodeExecutor):
    """call_api — generic HTTP call to a whitelisted host.

    Config:
      method:    'GET' | 'POST' | 'PUT' | 'DELETE'  (default 'POST')
      url:       'http://notification-service/send'  or
                 'https://api.partner.com/v1/refund'  (must be in whitelist)
      headers:   {Key: $.upstream.value, ...}  (optional)
      body:      dict (POST/PUT only)
      timeout_s: 30   (1..300)
    Output:
      {status_code: int, response_body: dict | str, dedup_hit: bool,
       source_ref: str}

    K-13: source_ref = sha256(run_id + node_id + url + body_hash).
    Inserts into workflow_api_call_log (mig 091b — TBD) on first call,
    skips on retry. v0 ships in-process dedup map; persistent dedup is
    follow-up.
    """
    node_type_key = "call_api"
    side_effect_class = SideEffectClass.EXTERNAL

    # In-process dedup ledger (per worker process). Kept as a fast-path
    # fallback when the persistent ledger is unreachable (Postgres down)
    # — same retry from the same worker still dedups. Survival across
    # worker restarts is provided by workflow_idempotency_records (P0.3).
    _DEDUP_CACHE: dict[str, dict[str, Any]] = {}

    # TTL for the persistent ledger. 24h covers most retry windows for
    # external APIs + their saga compensation.
    _IDEMPOTENCY_TTL_S = 86_400

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        method = (config.get("method") or "POST").upper()
        if method not in ("GET", "POST", "PUT", "DELETE"):
            raise NodeExecutorError(f"call_api.method={method!r} invalid")

        url = _resolve(config.get("url"), ctx)
        if not isinstance(url, str) or not url.strip():
            raise NodeExecutorError("call_api.url required (non-empty string)")
        url = url.strip()

        # Host allowlist — defense-in-depth against SSRF
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower()
        except Exception:  # noqa: BLE001
            raise NodeExecutorError(f"call_api.url not parseable: {url!r}")
        if not host:
            raise NodeExecutorError(f"call_api.url missing host: {url!r}")
        whitelist = _allowed_hosts()
        if host not in whitelist:
            raise NodeExecutorError(
                f"call_api host {host!r} not in whitelist {sorted(whitelist)}. "
                f"Set env {_ALLOWED_HOST_ENV} to extend."
            )

        timeout_s = float(config.get("timeout_s") or 30)
        if timeout_s < 1 or timeout_s > 300:
            raise NodeExecutorError("call_api.timeout_s must be 1..300")

        headers_raw = config.get("headers") or {}
        if not isinstance(headers_raw, dict):
            raise NodeExecutorError("call_api.headers must be dict")
        headers: dict[str, str] = {}
        for k, v in headers_raw.items():
            resolved_v = _resolve(v, ctx)
            if resolved_v is None:
                continue
            headers[str(k)[:200]] = str(resolved_v)[:1000]

        body_raw = config.get("body")
        body_str = ""
        body_payload: Any = None
        if body_raw is not None:
            body_payload = _resolve(body_raw, ctx) if isinstance(body_raw, str) else body_raw
            if isinstance(body_payload, dict):
                body_payload = {k: _resolve(v, ctx) for k, v in body_payload.items()}
            try:
                body_str = json.dumps(body_payload, ensure_ascii=False, sort_keys=True)
            except (TypeError, ValueError):
                body_str = str(body_payload)

        # Idempotency key (K-13)
        source_ref = ctx.idempotency_key or hashlib.sha256(
            f"{ctx.run_id}|{ctx.node_id}|{method}|{url}|{body_str}".encode("utf-8")
        ).hexdigest()

        # In-process fast path (cache hit ≪ Postgres roundtrip)
        cached = self._DEDUP_CACHE.get(source_ref)
        if cached is not None:
            log.info("call_api.dedup_hit_local",
                      source_ref=source_ref[:12],
                      url=url, enterprise_id=str(ctx.enterprise_id))
            return NodeResult(
                status="completed",
                output_data={**cached, "dedup_hit": True, "source_ref": source_ref},
            )

        # Persistent ledger (P0.3) — survives worker restart.
        try:
            from ..idempotency_store import get_or_set
            hit = await get_or_set(
                enterprise_id=ctx.enterprise_id,
                key=source_ref,
                side_effect_class="external",
                run_id=ctx.run_id,
                node_id=ctx.node_id,
                ttl_seconds=self._IDEMPOTENCY_TTL_S,
            )
        except Exception:  # noqa: BLE001
            log.exception("call_api.idempotency_store_unreachable",
                            source_ref=source_ref[:12])
            hit = None

        if hit is not None and hit.cached and hit.response_status == "completed":
            # Persisted result from a prior attempt — short-circuit.
            log.info("call_api.dedup_hit_persistent",
                      source_ref=source_ref[:12],
                      url=url, attempt_count=hit.attempt_count,
                      enterprise_id=str(ctx.enterprise_id))
            payload = hit.response_payload or {}
            # Cache locally so subsequent retries in this worker skip DB.
            if payload:
                self._DEDUP_CACHE[source_ref] = payload
            return NodeResult(
                status="completed",
                output_data={**payload, "dedup_hit": True, "source_ref": source_ref},
            )

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    resp = await client.request(
                        method, url,
                        headers={**headers, "Content-Type": "application/json"},
                        content=body_str if body_payload is not None else None,
                    )
        except httpx.HTTPError as exc:
            raise NodeExecutorError(
                f"call_api {method} {url} failed: {type(exc).__name__}: {exc}"
            )

        # Try to parse JSON body; fall back to text.
        response_body: Any
        try:
            response_body = resp.json()
        except Exception:  # noqa: BLE001
            response_body = resp.text[:5000]

        result = {
            "status_code":   resp.status_code,
            "response_body": response_body,
            "method":        method,
            "url":           url,
        }
        if resp.status_code < 500:
            self._DEDUP_CACHE[source_ref] = result  # cache 2xx, 4xx, ignore 5xx (retry)
            # Persist to ledger so a crashed worker doesn't re-fire.
            try:
                from ..idempotency_store import record_outcome
                await record_outcome(
                    enterprise_id=ctx.enterprise_id,
                    key=source_ref,
                    response_payload=result,
                    response_status="completed",
                )
            except Exception:  # noqa: BLE001
                log.exception("call_api.idempotency_persist_failed",
                                source_ref=source_ref[:12])

        log.info("call_api.executed",
                  method=method, url=url,
                  status_code=resp.status_code,
                  source_ref=source_ref[:12],
                  enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={**result, "dedup_hit": False, "source_ref": source_ref},
        )


# ─── 2. trigger_workflow ────────────────────────────────────────────


class TriggerWorkflowExecutor(NodeExecutor):
    """trigger_workflow — start a child workflow run.

    Config:
      target_workflow_id:  UUID-str of an active workflow in same tenant
                            (required)
      input_data:          dict  (optional — passed as the child's input)
      wait_for_complete:   False  (default — fire-and-forget; True is
                                    Phase 4 + needs synchronous coupling)
    Output:
      {child_run_id: UUID-str, target_workflow_id: UUID-str, mode: 'async'}

    K-12: tenant scope enforced — child workflow must belong to caller's
    enterprise. RLS via acquire_for_tenant.
    """
    node_type_key = "trigger_workflow"
    side_effect_class = SideEffectClass.WRITE_NON_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        target_raw = _resolve(config.get("target_workflow_id"), ctx)
        if not target_raw:
            raise NodeExecutorError("trigger_workflow.target_workflow_id required")
        try:
            target_id = UUID(str(target_raw))
        except ValueError:
            raise NodeExecutorError(
                f"trigger_workflow.target_workflow_id not a UUID: {target_raw!r}"
            )

        input_data = config.get("input_data") or {}
        if not isinstance(input_data, dict):
            raise NodeExecutorError("trigger_workflow.input_data must be dict")
        # Resolve any $.refs inside input_data values
        resolved_input = {k: _resolve(v, ctx) for k, v in input_data.items()}

        if config.get("wait_for_complete"):
            # Synchronous coupling — Phase 4. v0 fires async.
            log.warning("trigger_workflow.wait_for_complete_not_supported_v0")

        from ai_orchestrator.shared.db import acquire_for_tenant
        from ..runner import WorkflowRunner, run_in_background

        # K-12 check: target workflow must exist in caller's tenant.
        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                "SELECT workflow_id, workspace_id FROM workflows "
                "WHERE workflow_id = $1",
                target_id,
            )
        if row is None:
            raise NodeExecutorError(
                f"trigger_workflow target {target_id} not found in tenant scope"
            )

        # Derive deterministic idempotency_key so retrying THIS node
        # doesn't spawn duplicate child runs.
        idem_key = f"trig:{ctx.run_id}:{ctx.node_id}"

        child_run_id = await WorkflowRunner.create_run(
            workflow_id=target_id,
            enterprise_id=ctx.enterprise_id,
            workspace_id=row["workspace_id"],
            triggered_by=ctx.user_id,
            trigger_source="event",
            input_data=resolved_input,
            idempotency_key=idem_key,
        )

        # Fire async — the child runs in the same process via
        # FastAPI BackgroundTasks. v0 simplification; Phase 4 routes
        # through Temporal for cross-pod resilience.
        import asyncio
        asyncio.create_task(
            run_in_background(
                run_id=child_run_id,
                enterprise_id=ctx.enterprise_id,
                user_id=ctx.user_id,
            )
        )

        log.info("trigger_workflow.spawned",
                  child_run_id=str(child_run_id),
                  target_workflow_id=str(target_id),
                  parent_run_id=str(ctx.run_id),
                  enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "child_run_id":       str(child_run_id),
                "target_workflow_id": str(target_id),
                "mode":               "async",
            },
        )


# ─── 3. generate_report ─────────────────────────────────────────────


class GenerateReportExecutor(NodeExecutor):
    """generate_report — enqueue a report render request.

    Reports are heavy to build (charts + tables + LLM narrative + PDF
    render) so this executor only enqueues — a poller renders + delivers.

    Config:
      report_template_id:  'monthly_close_pdf'  (template registered
                              in mig 054 templates or future
                              report_templates table)
      report_title:        'Báo cáo tháng 5/2026'
      params:              {period_month: '2026-05', ...}
      recipient_emails:    ['cfo@kaori.vn', 'board@kaori.vn']
                            (the notification-service consumer dispatches
                              after render completes)
    Output:
      {report_task_id: UUID-str, status: 'queued'}

    write_idempotent: queues into workflow_tasks with task_key derived
    from (run_id, node_id, template_id) so retries collapse to 1 row.
    """
    node_type_key = "generate_report"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        template_id_raw = _resolve(config.get("report_template_id"), ctx)
        if not isinstance(template_id_raw, str) or not template_id_raw.strip():
            raise NodeExecutorError("generate_report.report_template_id required")
        template_id = template_id_raw.strip()[:128]

        report_title = _resolve(config.get("report_title"), ctx)
        if not isinstance(report_title, str) or not report_title.strip():
            raise NodeExecutorError("generate_report.report_title required")
        report_title = report_title.strip()[:300]

        params_raw = config.get("params") or {}
        if not isinstance(params_raw, dict):
            raise NodeExecutorError("generate_report.params must be dict")
        resolved_params = {k: _resolve(v, ctx) for k, v in params_raw.items()}

        recipients_raw = config.get("recipient_emails") or []
        if not isinstance(recipients_raw, list):
            raise NodeExecutorError("generate_report.recipient_emails must be list[str]")
        recipients = [str(e).strip() for e in recipients_raw if "@" in str(e)]

        task_key = f"report:{ctx.run_id}:{ctx.node_id}:{template_id}"
        metadata = {
            "kind":              "report_render",
            "template_id":       template_id,
            "params":            resolved_params,
            "recipient_emails":  recipients,
        }

        from ai_orchestrator.shared.db import acquire_for_tenant

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            row = await conn.fetchrow(
                """INSERT INTO workflow_tasks
                       (enterprise_id, run_id, node_id, task_key, title,
                        description, priority, metadata)
                   VALUES ($1, $2, $3, $4, $5, $6, 'normal', $7)
                   ON CONFLICT (enterprise_id, task_key) DO UPDATE
                   SET title = EXCLUDED.title,
                       description = EXCLUDED.description,
                       metadata = EXCLUDED.metadata
                   RETURNING task_id, (xmax = 0) AS inserted""",
                ctx.enterprise_id, ctx.run_id, ctx.node_id, task_key,
                report_title,
                f"Render report {template_id} cho {len(recipients)} người nhận.",
                json.dumps(metadata),
            )

        status = "queued" if row["inserted"] else "requeued"
        log.info("generate_report.enqueued",
                  report_task_id=str(row["task_id"]),
                  template_id=template_id, recipient_count=len(recipients),
                  status=status, enterprise_id=str(ctx.enterprise_id))

        return NodeResult(
            status="completed",
            output_data={
                "report_task_id":  str(row["task_id"]),
                "template_id":     template_id,
                "recipient_count": len(recipients),
                "status":          status,
            },
        )
