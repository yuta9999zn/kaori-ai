# P15-S9 Pre-emptive Self-Review

> **Reviewer:** Claude (em) walking own diff `main..feat/p15-s9-d1`
> **Date:** 2026-05-10 (post pre-emptive CI fixes commit `339e3d8`)
> **Scope:** 11 commits, 82 files, ~9000 lines code on branch
> **Goal:** catch logic bug em tự miss khi build single-session 2026-05-08 → reduce reviewer burden when PR #179 sống lại June

Severity legend: **CRITICAL** (production-impact bug) · **MEDIUM** (correctness issue, reachable but constrained) · **LOW** (cosmetic / suggested cleanup).

---

## D5 — Telegram + REL-011 webhook (commit `2e312a3`)

### CRITICAL — W7: notification-service DB pool only initialised behind `outbox_poll_enabled` flag

**File:** `services/notification-service/main.py:43-46` + `db.py:45-48`

The lifespan calls `init_db_pool(settings)` only when `settings.outbox_poll_enabled` is True. The new `/webhook/telegram` route always calls `get_pool()` (main.py:154) which raises `RuntimeError("DB pool not initialised")` when the flag is False.

**Reproduction:** deploy with `OUTBOX_POLL_ENABLED=false` + Telegram bot configured → first manager tap → 500 ISE → silent loss of approval.

**Fix shipped this session (commit `db5eaf3`):** init pool unconditionally if Telegram bot is configured; gate ONLY the poller spawn behind the flag.

### CRITICAL — W4: webhook secret empty default = silent disable

**File:** `services/notification-service/bot/webhook.py:188-189`

`_verify_secret` returns silently when `expected` is empty (`if not expected: return`). If production deploy forgets to set `KAORI_TELEGRAM_WEBHOOK_SECRET`, the webhook accepts forged callback POSTs from anyone who can reach the public endpoint. No log + no startup warning.

**Reproduction:** deploy without env var → attacker POSTs crafted Telegram callback → arbitrary `workflow_approvals` row inserted → workflow gets bogus "approve" decision.

**Fix shipped this session:** log explicit warning at startup if Telegram bot configured but webhook_secret empty; keep "empty = disabled" semantics for tests but make it loud.

### MEDIUM — W1: enterprise_resolver stub ignores callback contents

**File:** `services/notification-service/main.py:106-130`

`_resolve_enterprise_for_callback` accepts the decoded `ApprovalCallback` (with workflow_id / run_id / node_id) but returns the env-var override or 503 — never looks up `workflow_runs` to derive the actual tenant.

In Olist single-tenant pilot this is "OK because env var = Olist". When tenant #2 lands, every approval gets attributed to whichever tenant the env var names → cross-tenant leak (K-1 violation).

**Recommendation (defer to D5 follow-up):** wire real `workflow_runs` lookup. Tracked as known stub in the function docstring but should fail loud when `KAORI_TELEGRAM_DEFAULT_ENTERPRISE_ID` is set + `tenant_count > 1`.

### MEDIUM — W2: bot_token in URL → log leak risk

**File:** `services/notification-service/bot/telegram.py:102, 153`

`url = f"{api_base}/bot{bot_token}/sendMessage"`. httpx exception messages typically include URL (`ConnectError: ... attempt connect to https://api.telegram.org/bot<TOKEN>/sendMessage failed`). When the wrapped `BotSendError` is caught + logged by structlog or sent to Sentry, the token leaks.

**Recommendation:** strip token from URL in exception messages: `url = url.replace(bot_token, "<TOKEN>")` before raising.

### LOW — W3: enterprise_id type not validated at boundary

**File:** `services/notification-service/bot/webhook.py:226`

`enterprise_id: UUID = await ctx.enterprise_resolver(decoded)` — type hint `UUID` but no runtime check. If a future resolver returns `None` or `str`, the asyncpg query later fails with cryptic encoding error instead of a clear "resolver contract broken".

### LOW — W5: New httpx.AsyncClient per call

**File:** `bot/telegram.py:112, 161`

No connection pooling between calls. For approval-heavy flows (1 send + 1 ack per approval = 2 TCP+TLS handshakes each). Performance not correctness.

### LOW — W6: imports inside function bodies

`webhook.py:193 import secrets`, `:309 import json` — should be top-level.

---

## D7 — NOV monthly + ROI dashboard (commit `d7bc5f3`)

### LOW — R3: `_dec_str` has dead `isinstance` branch

**File:** `services/ai-orchestrator/routers/economics.py:167-175`

```python
def _dec_str(value: ...) -> str:
    if isinstance(value, Decimal):
        return str(value)
    return str(value)
```

Both branches do the same thing. Either remove the check or differentiate (e.g. `Decimal` path forces `f"{value:.4f}"` to preserve trailing zeros from `NUMERIC(14,4)`).

### LOW — R1: required X-Enterprise-Id falls into FastAPI 422, not RFC 7807

**File:** `services/ai-orchestrator/routers/economics.py:91, 114`

`x_enterprise_id: Annotated[str, Header()]` — FastAPI default 422 for missing header. K-14 says all errors RFC 7807. Likely handled by `register_problem_handlers` upstream — verify covers `RequestValidationError` for headers.

### LOW — E2: stub activity logs identical structured event as real impl

**File:** `services/ai-orchestrator/workflow_runtime/activities/economics.py:235`

`log.info("activity.persist_nov_digest", ...)` looks like a real persistence event in operator dashboards. The synthetic `row_id="digest-..."` is the only marker. Recommend `log.info("activity.persist_nov_digest.STUB", ...)` until D7 follow-up wires real persistence.

---

## D6 — Adoption signals (commit `70f0d7f`)

### MEDIUM — S2: SignalSample.raw_count semantics inconsistent across signals

**File:** `services/ai-orchestrator/org_intel/adoption/signals.py`

- AI-SIG-001..006: `raw_count` = bad-event count (abandonments, overrides, interventions, etc.)
- AI-SIG-008: `raw_count` = `int(observed_seconds)` — a duration, not a count
- AI-SIG-007: `raw_count` = negative_comments (count, OK)
- AI-SIG-009: `raw_count` likely also count (didn't read but infer from doc)

Operator dashboards aggregate `SUM(raw_count) GROUP BY signal_id` — for SIG-008 this aggregates wall-clock seconds (meaningless if rolled up). Recommend either rename to `numerator_or_observed` or move SIG-008's seconds into `note` only.

---

## D4b — Excel filesystem connector (commit `088382b`)

### MEDIUM — X4: `follow_symlinks=False` only filters file-symlinks, not directory-symlinks

**File:** `services/data-pipeline/ingestion/connectors/excel_filesystem/connector.py:106, 118`

`Path.glob(pattern)` descends through directory symlinks regardless of the `follow_symlinks` config. The post-glob filter at line 118 only catches file-level symlinks. Docstring claims "prevents accidental escape from a tenant-isolated mount" — partial.

**Reproduction:** `watch_path = /share/tenant-A/excel/` and someone creates `/share/tenant-A/excel/escape -> /share/tenant-B/` symlink. Connector glob descends → reads tenant B's xlsx files → emits events tagged with tenant_id=A.

**Fix recommendation:** use `os.walk(top, followlinks=False)` for traversal; honors symlinks at directory boundary. Or pre-resolve `watch_path.resolve(strict=True)` and verify each candidate's resolved path stays under it.

### LOW — X1: PII boundary delegated to "downstream redactor" — no test asserts redactor runs

The connector's docstring (lines 28-35) claims `payload['path']` is redacted by K-5 layer before Kafka publish. No test in `test_excel_filesystem_connector.py` verifies this contract holds — if the publish layer changes, connector silently leaks file paths.

**Recommendation:** add an integration test that asserts the publish path masks `<EMAIL>` / Vietnamese names from `payload['actor']` and `payload['path']`.

### LOW — X2: redundant `or None`

`actor=str(payload.get("last_modified_by") or "") or None` — `"" or None` already `None`. Either drop one `or` or extract a clearer helper.

---

## D3 — Temporal client + scaffolding (commit `0b9041a`)

### MEDIUM — T1: no TLS / no auth on connect

**File:** `services/ai-orchestrator/workflow_runtime/temporal_client.py:117`

`Client.connect(cfg.address, namespace=cfg.namespace)` — no `tls_config=`, no API key. For docker-compose dev OK; production K8s Temporal cluster typically uses mTLS. Phase 1.5 D1 K8s deploy will need to wire this before the worker pod can talk to a real cluster.

**Recommendation:** add `tls_cert_path` / `tls_key_path` env vars + pass to `Client.connect` when set. Acceptable to defer until production deploy actually happens; tracked in P15-S9 D1 (FPT Cloud) follow-up.

### LOW — T4: connect() race condition

`if _client is not None: return _client` — between concurrent first-callers, multiple `Client.connect()` may fire. asyncio.Lock would fix. Singleton pattern in practice doesn't hit this; low risk.

### LOW — T2: no retry on cold-start

If Temporal frontend pod not ready, first `connect()` fails. Caller has to retry. Tenacity wrap would help; defer.

---

## D2 — Vault HA + kaori_vault.py (commits `7cbb904` + `4042096`)

Reviewed at file structure level (4 copies of `kaori_vault.py` across services).

### LOW — V1: 4 identical `kaori_vault.py` copies

`services/{ai-orchestrator,data-pipeline,llm-gateway,notification-service}/{shared/,}/kaori_vault.py` — verbatim copies. Rationale: each service installs from its own requirements.txt (no shared package). Acceptable Phase 1.5; consider extracting `kaori-shared` Python package Phase 2 microservices extract.

### LOW — V2: Java `VaultClient.java` deferred — explicit gap

Already noted in `docs/sprint/P15-S9_CI_BACKLOG.md` deferral list. No new finding.

---

## D1 — K8s Helm + Telegram bridge (commit `c2b2f85`)

YAML + bash review only. No bugs found in scope.

### Note D1-1: Helm `values.yaml` defaults

Reviewed `infrastructure/k8s/helm-charts/kaori-services/values.yaml`. Resource requests/limits are conservative (good for dev cluster); production deploy must override.

---

## D8 — ClickHouse Helm + 3 schemas (commit `2892cfe`)

YAML + SQL review.

### LOW — D8-1: 3 schemas use different partitioning conventions

- `01_silver_pipeline_rows.sql` — `PARTITION BY (tenant_id, toYYYYMM(ingested_at))`
- `02_otel_traces.sql` — `PARTITION BY toYYYYMMDD(timestamp)` (no tenant_id partition)
- `03_nov_time_series.sql` — `PARTITION BY (tenant_id, toYYYYMM(month_start))`

OTel traces lacks tenant_id partition → cross-tenant trace search slower; aligns with K-19 (tenant_id is span ATTRIBUTE not partition key) so OK by design, but worth a comment in the schema explaining the divergence.

---

## Summary

| Severity | Count | Action |
|---|---|---|
| CRITICAL | 2 (W4, W7) | **Fix this session** before next push |
| MEDIUM | 5 (W1, W2, S2, X4, T1) | Note for reviewer; fix as follow-up commits this session if cheap |
| LOW | 12+ | Note for reviewer; defer to next sprint cleanup pass |

CRITICAL fixes shipped commit `db5eaf3`. MEDIUM fixes NOT shipped this session — left for reviewer judgment (W1 multi-tenant resolver = product decision; W2 token-redact = trivial follow-up; X4 symlink traversal = security hardening better handled with eyes on it).

Reviewer should prioritise eyeballing W1 (multi-tenant resolver stub) + X4 (symlink directory traversal) — both reachable from outside in adversarial scenarios.
