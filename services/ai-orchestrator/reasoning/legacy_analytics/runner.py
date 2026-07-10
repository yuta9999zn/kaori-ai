"""
Analysis runner — orchestrates multi-template execution on Silver data.
K-8: Silver read once, shared (read-only) across all templates.
"""
import asyncio
import json
import os
import time

import pandas as pd
import structlog

from .template_registry import get_eligible_templates
from .engines.statistical import StatisticalEngine
from .engines.ml import MLEngine
from ...engine.llm_router import llm_router, NARRATIVE_MAX_TOKENS
from ...shared.audit import log_decision
from ...shared.db import acquire_for_tenant, get_pool
from ...shared.kafka_producer import emit
from ..knowledge.store import KnowledgeStore
from ..knowledge.inject import ground_analysis, reinforce_cited

log = structlog.get_logger()

# Hard ceiling for the (best-effort) AI narrative calls. The llm_router has its
# own 30s timeout, but with retries/circuit-breaker a cold or unhealthy Ollama
# can stack several attempts and wedge the analyze worker for minutes — and
# since the narrative runs inside the template gather(), a HANG (not a raise)
# strands the whole run in 'running'. wait_for cancels the call outright so the
# run always finishes; the numbers ship with a degraded narrative.
_NARRATIVE_TIMEOUT_S = float(os.getenv("NARRATIVE_TIMEOUT_S", "35"))

_ENGINES = {
    "statistical":     StatisticalEngine(),
    "ml_clustering":   MLEngine(mode="clustering"),
    "ml_classification": MLEngine(mode="classification"),
    "ml_regression":   MLEngine(mode="regression"),
}


async def run_analysis_for_run(
    analysis_run_id: str,
    run_id: str,
    enterprise_id: str,
    templates: list[str],
    config: dict,
) -> None:
    pool = get_pool()

    if not analysis_run_id:
        log.error("orchestrator.run.empty_id", run_id=run_id)
        return

    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute(
            "UPDATE analysis_runs SET status = 'running', started_at = NOW() "
            "WHERE id = $1::uuid AND enterprise_id = $2::uuid",
            analysis_run_id, enterprise_id,
        )

    # Everything past the 'running' flag is wrapped: the worker is a
    # fire-and-forget asyncio task, so an unhandled exception here would
    # vanish and leave the run stuck 'running' forever (the FE polls it).
    # Any failure must resolve the run to a terminal state.
    try:
        # Load Silver data once — shared across all templates (K-8)
        silver_df = await _load_silver(run_id, enterprise_id, pool)
        if silver_df is None or silver_df.empty:
            await _fail_run(analysis_run_id, enterprise_id, "Silver data empty or unavailable", pool)
            return

        # Run each template concurrently
        tasks = [
            _run_single_template(
                analysis_run_id=analysis_run_id,
                run_id=run_id,
                enterprise_id=enterprise_id,
                template_id=t,
                silver_df=silver_df,
                config=config.get(t, {}),
                pool=pool,
            )
            for t in templates
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        errors = [str(r) for r in results if isinstance(r, Exception)]
        final_status = "error" if len(errors) == len(templates) else "done"

        # Cross-template overview narrative is best-effort enrichment — a
        # gateway/model outage (Ollama 500 → gateway 502) must NOT strand the
        # run in 'running'. Same guard as the per-template narrative (tenet 13).
        overview = None
        if final_status == "done":
            try:
                overview = await asyncio.wait_for(
                    _generate_overview(templates, silver_df, enterprise_id),
                    timeout=_NARRATIVE_TIMEOUT_S,
                )
            except Exception as exc:  # noqa: BLE001 — narrative is non-critical
                # str(TimeoutError()) == "" → fallback class name để overview
                # log có ý nghĩa (TimeoutError vs str rỗng).
                reason = (str(exc) or type(exc).__name__)[:500]
                log.warning("orchestrator.overview.degraded",
                            analysis_run_id=analysis_run_id, error=reason)
                overview = {"degraded": True, "reason": reason}
        elif errors:
            overview = {"error": errors[0][:500]}

        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute("""
                UPDATE analysis_runs
                SET status = $1::text, overview = $2::jsonb, completed_at = NOW()
                WHERE id = $3::uuid AND enterprise_id = $4::uuid
            """, final_status, json.dumps(overview) if overview else None,
                analysis_run_id, enterprise_id)

        # DB đã commit terminal status; từ đây trở đi mọi failure CHỈ được
        # log, KHÔNG được rơi ra outer except (sẽ ghi đè 'done' thành 'error').
        # Kafka schema for kaori.pipeline.analysis.complete restricts /status to
        # success|partial|failed; the DB enum uses done|error|running. Map here
        # so the wire contract stays additive-only (Engineering Tenet 8).
        try:
            kafka_status = {
                "done": "success",
                "error": "failed",
            }.get(final_status, "partial")
            from ...shared import kafka_topics
            await emit(kafka_topics.PIPELINE_ANALYSIS_COMPLETE, {
                "run_id": run_id,
                "analysis_run_id": analysis_run_id,
                "enterprise_id": enterprise_id,
                "status": kafka_status,
                "templates": templates,
            })
        except Exception as exc:  # noqa: BLE001 — Kafka outage không được flip status
            log.warning("orchestrator.kafka.emit_failed",
                        analysis_run_id=analysis_run_id,
                        error=str(exc) or type(exc).__name__)
        log.info("orchestrator.run.finished",
                 analysis_run_id=analysis_run_id, status=final_status)
    except Exception as exc:  # noqa: BLE001 — finalizer guard
        # str(TimeoutError()) == "" → reason ghi vào DB sẽ trống; dùng
        # class name làm fallback để overview.error có ý nghĩa.
        reason = str(exc) or type(exc).__name__
        log.exception("orchestrator.run.crashed",
                      analysis_run_id=analysis_run_id, error=reason)
        try:
            await _fail_run(analysis_run_id, enterprise_id,
                            f"Lỗi hoàn tất phân tích: {reason}"[:500], pool)
        except Exception as exc2:  # noqa: BLE001 — _fail_run cũng có thể fail
            log.exception("orchestrator.run.fail_run_failed",
                          analysis_run_id=analysis_run_id,
                          error=str(exc2) or type(exc2).__name__)


async def _run_single_template(
    analysis_run_id: str,
    run_id: str,
    enterprise_id: str,
    template_id: str,
    silver_df: pd.DataFrame,
    config: dict,
    pool,
) -> None:
    start = time.monotonic()
    try:
        result = await _execute_template(template_id, silver_df, config, enterprise_id)
        elapsed = round(time.monotonic() - start, 2)
        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute("""
                INSERT INTO analysis_results
                    (analysis_run_id, enterprise_id, template_id, status, results_payload)
                VALUES ($1::uuid, $2::uuid, $3::text, 'done', $4::jsonb)
            """, analysis_run_id, enterprise_id, template_id, _dump_result_json(result))
        log.info("orchestrator.template.done",
                 template=template_id, elapsed_s=elapsed)
        # K-6 audit: one row per template execution. Best-effort.
        await log_decision(
            enterprise_id=enterprise_id,
            run_id=run_id,
            decision_type="template_analysis",
            subject=template_id,
            chosen_value="done",
            confidence=1.0,
            method="orchestrator",
            reasoning=f"elapsed_s={elapsed}",
        )
    except Exception as exc:
        log.error("orchestrator.template.error", template=template_id, error=str(exc))
        async with acquire_for_tenant(enterprise_id) as conn:
            await conn.execute("""
                INSERT INTO analysis_results
                    (analysis_run_id, enterprise_id, template_id, status, error_message)
                VALUES ($1::uuid, $2::uuid, $3::text, 'error', $4::text)
            """, analysis_run_id, enterprise_id, template_id, str(exc))
        # K-6 audit: also log error path so the decision log shows what
        # was attempted, not just successes.
        await log_decision(
            enterprise_id=enterprise_id,
            run_id=run_id,
            decision_type="template_analysis",
            subject=template_id,
            chosen_value="error",
            confidence=0.0,
            method="orchestrator",
            reasoning=str(exc),
        )
        raise


async def _execute_template(
    template_id: str,
    df: pd.DataFrame,
    config: dict,
    enterprise_id: str,
) -> dict:
    """Route template_id to correct engine and return blocks payload."""
    from .template_registry import TEMPLATE_REGISTRY

    template = next((t for t in TEMPLATE_REGISTRY if t.template_id == template_id), None)
    if template is None:
        raise ValueError(f"Unknown template: {template_id}")

    engine = _ENGINES.get(template.model_hint)
    if engine is None:
        raise ValueError(f"No engine for model_hint: {template.model_hint}")

    blocks = await engine.run(template_id, df, config)

    # Append AI narrative — best-effort enrichment (tenet 13: a per-item
    # LLM failure must not discard the computed analytical blocks). When
    # the gateway/model is unavailable the numbers still ship; the
    # narrative block degrades to a notice instead of erroring the run.
    degraded_reason = None
    try:
        narrative = await asyncio.wait_for(
            _generate_template_narrative(template_id, blocks, enterprise_id),
            timeout=_NARRATIVE_TIMEOUT_S,
        )
        provider, degraded = "qwen", False
    except Exception as exc:  # noqa: BLE001 — narrative is non-critical
        # str(TimeoutError()) == "" → fallback class name (xem overview path).
        degraded_reason = (str(exc) or type(exc).__name__)[:300]
        log.warning("orchestrator.template.narrative_degraded",
                    template=template_id, error=degraded_reason)
        narrative = "Nhận xét AI tạm thời chưa khả dụng — kết quả phân tích bên dưới vẫn đầy đủ."
        provider, degraded = "none", True
    blocks.append({
        "id": "ai_narrative",
        "type": "narrative",
        "text": narrative,
        "provider": provider,
        "degraded": degraded,
        "reason": degraded_reason,   # why the LLM was skipped (None when ok)
    })
    return {"template_id": template_id, "blocks": blocks}


async def _generate_overview(
    templates: list[str],
    df: pd.DataFrame,
    enterprise_id: str,
) -> dict:
    row_count = len(df)
    col_count = len(df.columns)
    # ADR-0033: ground the narrative in foundational knowledge (best-effort,
    # bounded by the caller's narrative timeout). Subject = what's actually being
    # analysed (templates + columns) so the KB is matched semantically — no
    # hardcoded category routing. coverage_gate tells the model whether it may
    # generalise ("học 1 hiểu 10") or must stay literal.
    store = KnowledgeStore(acquire_for_tenant=acquire_for_tenant)
    subject = " ".join(templates) + " " + " ".join(map(str, df.columns))
    grounding = await ground_analysis(enterprise_id, subject, store=store)
    prompt = (
        grounding["preamble"]
        + f"Tóm tắt kết quả phân tích dữ liệu gồm {row_count} hàng, {col_count} cột.\n"
        f"Các phân tích đã chạy: {', '.join(templates)}.\n"
        "Viết 2-3 câu tổng quan ngắn gọn bằng tiếng Việt, "
        "nêu điểm nổi bật nhất từ dữ liệu."
    )
    text = await llm_router.complete(prompt, task="overview_narrative",
                                     enterprise_id=enterprise_id,
                                     max_tokens=NARRATIVE_MAX_TOKENS)
    if grounding["cited_ids"]:
        await reinforce_cited(enterprise_id, grounding["cited_ids"], store=store)
    return {
        "templates_run": templates,
        "narrative": text,
        "row_count": row_count,
        "col_count": col_count,
        "knowledge_coverage": grounding["coverage"],
    }


async def _generate_template_narrative(
    template_id: str,
    blocks: list[dict],
    enterprise_id: str,
) -> str:
    summary = " | ".join(
        f"{b.get('title', b['id'])}: {_block_summary(b)}"
        for b in blocks
        if b.get("type") == "stats_card"
    )
    # ADR-0033: same foundational grounding as the overview, keyed on this
    # template + its metric labels.
    store = KnowledgeStore(acquire_for_tenant=acquire_for_tenant)
    grounding = await ground_analysis(enterprise_id, f"{template_id} {summary}", store=store)
    prompt = (
        grounding["preamble"]
        + f"Phân tích '{template_id}' đã hoàn thành. Tóm tắt: {summary or 'Không có dữ liệu tóm tắt.'}.\n"
        "Viết 1-2 câu nhận xét ngắn gọn bằng tiếng Việt."
    )
    text = await llm_router.complete(prompt, task="template_narrative",
                                     enterprise_id=enterprise_id,
                                     max_tokens=NARRATIVE_MAX_TOKENS)
    if grounding["cited_ids"]:
        await reinforce_cited(enterprise_id, grounding["cited_ids"], store=store)
    return text


def _block_summary(block: dict) -> str:
    data = block.get("data", {})
    if isinstance(data, dict):
        return ", ".join(f"{k}={v}" for k, v in list(data.items())[:3])
    return str(data)[:60]


async def _load_silver(
    run_id: str,
    enterprise_id: str,
    pool,
) -> pd.DataFrame | None:
    """Load Silver rows for this run into a DataFrame.

    Uses acquire_for_tenant so the NOBYPASSRLS policy on silver_rows
    (migration 024) sees app.enterprise_id; otherwise rows fetch returns
    empty even though data is there.
    """
    async with acquire_for_tenant(enterprise_id) as conn:
        rows = await conn.fetch("""
            SELECT row_data
            FROM silver_rows
            WHERE run_id = $1::uuid AND enterprise_id = $2::uuid
            ORDER BY row_index ASC
        """, run_id, enterprise_id)

    if not rows:
        return None
    records = []
    for r in rows:
        rd = r["row_data"]
        if isinstance(rd, str):
            rd = json.loads(rd)
        records.append(rd)
    return _coerce_datetime(
        _coerce_numeric(_drop_empty_columns(pd.DataFrame(records)))
    )


def _drop_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop columns with no usable data (every cell None/blank).

    Blank "Unnamed: N" columns survive Bronze→Silver when the user didn't
    explicitly remove them at step-2; left in, they coerce to all-NaN numeric
    and inflate both ``null_rate`` and the ``numeric_columns`` count in the
    summary. A column with ANY non-blank value is kept (it carries real data,
    even if poorly named)."""
    keep = [
        c for c in df.columns
        if df[c].map(lambda v: v not in (None, "") and str(v).strip() != "").any()
    ]
    # .copy() bắt buộc: pandas 2.x copy-on-write biến df[keep] thành view,
    # khiến _coerce_numeric sau đó gán `df[col] = ...` thành no-op âm thầm —
    # đúng triệu chứng "no numeric column" đã gặp ở pilot (PR #257).
    return df[keep].copy() if keep else df


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Type-infer numeric columns on read.

    Silver ``row_data`` is JSONB; the schema dictionary currently types
    every column as ``text`` (no per-field ``data_type`` yet), so numeric
    values land as JSON strings (``"8395"``) and arrive here as object
    dtype. The statistical engines select numeric columns via
    ``select_dtypes(include="number")`` and would otherwise see none.

    This is read-side input hygiene (the same inference ``read_csv`` does),
    NOT a Medallion fallback: we only re-type the Silver we were handed.
    A column is upgraded only when EVERY non-null value parses as a number
    AND no value is a leading-zero string (``"0901234567"`` phone,
    ``"007"`` id) — those stay text so identifiers aren't mangled.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        s = df[col]
        non_null = s[s.notna()].astype(str).str.strip()
        if non_null.empty:
            continue
        # Identifier guard: a multi-char value with a leading zero is an
        # id/phone/zip, never a quantity — keep the whole column as text.
        if non_null.str.match(r"^0\d").any():
            continue
        if pd.to_numeric(non_null, errors="coerce").isna().any():
            continue  # at least one value isn't numeric → leave as text
        df[col] = pd.to_numeric(s, errors="coerce")
    return df


def _json_safe(obj):
    """Recursively replace non-finite floats (NaN/±Inf) with None.

    Engines hand back pandas ``.to_dict("records")`` payloads where e.g.
    ``pct_change()`` yields NaN on the first row; ``json.dumps`` emits a
    bare ``NaN`` token that Postgres JSONB rejects, flipping a successful
    template run to status='error' (incident 2026-07-10, run b067818e).
    numpy scalars subclass float so they're covered by the same check.
    """
    if isinstance(obj, float):
        import math
        return None if not math.isfinite(obj) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


def _dump_result_json(result) -> str:
    """json.dumps for analysis_results.results_payload — strict-JSON safe."""
    return json.dumps(_json_safe(result), ensure_ascii=False, default=str)


# ISO-8601 date, optionally with a time part ("2026-01-04", "2026-01-04T09:30",
# "2026-01-04 09:30:00"). The Silver clean rule "Parse dates to ISO" guarantees
# this shape, so anything else stays text on purpose.
_ISO_DATE_RE = r"^\d{4}-\d{2}-\d{2}([ T].*)?$"


def _coerce_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """Type-infer ISO date columns on read — the datetime twin of
    _coerce_numeric (same JSONB-strings-in root cause). Engines detect the
    date axis via ``select_dtypes``/dtype probes ("datetime64"); without
    this, a perfectly clean ``date`` column arrives as object dtype and
    time-series/anomaly templates wrongly report the dataset ineligible.

    A column is upgraded only when EVERY non-null value matches the ISO
    shape — one stray value keeps the whole column text (mirror of the
    numeric rule; never guess on mixed columns). Runs AFTER _coerce_numeric,
    so numeric-looking strings are already gone and can't be misread as
    epoch timestamps.
    """
    for col in df.columns:
        if df[col].dtype != object:
            continue
        s = df[col]
        non_null = s[s.notna()].astype(str).str.strip()
        if non_null.empty:
            continue
        if not non_null.str.match(_ISO_DATE_RE).all():
            continue
        parsed = pd.to_datetime(s, errors="coerce", format="mixed")
        if parsed[s.notna()].isna().any():
            continue  # ISO-shaped but unparseable (e.g. month 13) → keep text
        df[col] = parsed
    return df


async def _fail_run(analysis_run_id: str, enterprise_id: str, reason: str, pool) -> None:
    async with acquire_for_tenant(enterprise_id) as conn:
        await conn.execute("""
            UPDATE analysis_runs
            SET status = 'error', completed_at = NOW(),
                overview = jsonb_build_object('error', $2::text)
            WHERE id = $1::uuid AND enterprise_id = $3::uuid
        """, analysis_run_id, reason, enterprise_id)
    log.error("orchestrator.run.failed", analysis_run_id=analysis_run_id, reason=reason)
