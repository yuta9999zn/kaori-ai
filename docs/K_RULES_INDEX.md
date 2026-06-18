# Kaori AI — K-Rules Quick Index (K-1 .. K-26)

> **Canonical source: `CLAUDE.md` §4 "Critical Invariants (NEVER BREAK)".** This file is a searchable quick-lookup — when wording differs, `CLAUDE.md` §4 wins. K-rules are stronger than ADRs (they are enforced rules, not just decisions).

| # | One-line | Area / ADR |
|---|---|---|
| K-1 | Every SELECT filters `tenant_id`/`enterprise_id`; RLS via `acquire_for_tenant` GUC | Multi-tenant isolation (ADR-0013) |
| K-2 | Bronze tables append-only — no UPDATE/DELETE | Immutable source of truth (ADR-0002) |
| K-3 | All LLM calls go through `llm-gateway` — never a direct SDK | Cost governance + consent + drift (ADR-0004) |
| K-4 | External AI only with `consent_external=True`; Qwen is default; OCR/embed refuse external entirely | Privacy + cost (ADR-0015) |
| K-5 | PII redaction before any external API call (Vietnamese-aware) | Privacy |
| K-6 | Decision audit log at every automated decision (`decision_audit_log`) | Decision traceability (ADR-0005) |
| K-7 | JWT claims forwarded as `X-*` headers to all services | Identity propagation |
| K-8 | Idempotent pipeline runs via SHA-256 fingerprint (same file = skip) | Dedup ingest |
| K-9 | `NUMERIC(5,4)` for rates, `NUMERIC(14,4)` for money — never FLOAT | Precision |
| K-10 | 1 question = 1 primary analysis framework, optional secondary | Analysis discipline |
| K-11 | Billing unit = `COUNT(DISTINCT customer_external_id)` per month | Anti-gaming billing |
| K-12 | `tenant_id` never accepted via query/body/header — JWT only | Anti-IDOR |
| K-13 | `Idempotency-Key` on all POST mutations (Redis 24h) + per-node ledger (Postgres 7d) | Safe retries (ADR-0014) |
| K-14 | Error format = RFC 7807 Problem Details (`application/problem+json`) | Consistent errors |
| K-15 | MCP tool calls: authz check per tenant + audit every call | MCP isolation |
| K-16 | Chat tools never take tenant/user/workspace id from args — JWT via `ToolContext` | Chat tool isolation (cf. K-12) |
| K-17 | Every workflow node declares `side_effect_class` ∈ {pure, read_only, write_idempotent, write_non_idempotent, external} | Retry + saga compensation (ADR-0014) |
| K-18 | Phase 1.5+ — Vault is the only secret store; no env-var secrets in production | Centralised rotation/audit |
| K-19 | OpenTelemetry mandatory; every span carries `tenant_id` attribute | Cross-tenant trace/leak detection (ADR-0013) |
| K-20 | LLM version pinning per workflow (`model` + `version`); no silent vendor upgrade | Drift control (ADR-0015) |
| K-21 | New tables → `gen_uuid_v7()` PK; external public IDs → `TEXT(26) gen_ulid()`; existing UUIDv4 untouched | ID strategy (ADR-0029) |
| K-22 | EU AI Act risk classification — every AI-use carries `risk_tier` ∈ {prohibited, high, limited, minimal}; `prohibited` blocked at publish+run | EU AI Act Art 5/9 (ADR-0041, mig 134) |
| K-23 | EU AI Act human oversight — `high`-tier workflow needs sign-off before any write_non_idempotent/external node (`eu_ai_act_oversight` gate) | EU AI Act Art 14 (ADR-0041, mig 135) |
| K-24 | EU AI Act transparency — every generative output carries machine-readable disclosure at the K-3 chokepoint; chatbot self-identifies | EU AI Act Art 50 (ADR-0041) |
| K-25 | *(planned — not yet enforced)* Model card / Annex IV-lite technical doc per `model + version` in the K-20 registry | EU AI Act Art 11 (ADR-0041) |
| K-26 | EU AI Act post-market monitoring — incident register (`ai_incident`; `serious` = Art 73-reportable) + bias examination in Stage-4 quality gate | EU AI Act Art 72/73 + Art 10 (ADR-0041, mig 136) |

> EU AI Act cluster (K-22..K-26) all trace to **ADR-0041** (migs 134-136). See also `docs/adr/0041-eu-ai-act-control-framework.md`.
