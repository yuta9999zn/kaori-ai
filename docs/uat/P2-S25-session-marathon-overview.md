# UAT — 2026-05-17 sprint marathon overview

> Umbrella UAT pointing to the per-sprint UAT scripts shipped this session. Use this as a checklist before pilot Olist hits any of these features.

Branch `feat/p15-s9-d1` HEAD `c190fc9` (or later), **126 commits ahead `main`**. ai-orchestrator 1554 → 1575 tests pass. 8 new migrations 068-074. 15 ADRs total (0010-0024).

## Sprint-level UAT links

| Sprint | Feature batch | UAT doc | Pilot risk |
|---|---|---|---|
| P2-S15 | Workflow node catalog + 25 templates + agent palette | (Inline below) | LOW — additive endpoints; existing workflow_builder router unchanged |
| P2-S16 | Workflow as Code YAML + Multi-user collab | (Inline below) | MEDIUM — new mutation surface (import) |
| P2-S18 | Observability deep-dive (anomaly + capacity + replay) | (Inline below) | LOW — read-only metric endpoints + opt-in replay |
| P2-S21 | OKR + NOV recommendations + simulation + T-Cube | (Inline below) | MEDIUM — T-Cube changes Memory L4; gated by `TRACE_DISTILLER_ENABLED` |
| P2-S25 | MFA TOTP + field encryption | [P2-S25 detailed UAT](./P2-S25-mfa-field-encryption.md) | HIGH — auth security; mis-config locks users out |
| Knowing-doing fix | ADR-0023 heuristic gate in chat | (Inline below) | LOW — falls back to `tool_choice="auto"` when score < 0.7 |

## P2-S15 quick UAT

```bash
# List the 45-row catalog
curl /workflow-node-types | jq 'length == 45'

# Filter by category
curl '/workflow-node-types?category=ai' | jq 'all(.[] | .category == "ai")'

# Curated agent palette (5 buckets)
curl '/shared/agents/studio/builder/palette' \
  | jq '.buckets | keys | sort'
# Expect: ["action", "decision", "intake", "output", "reasoning"]

# Industry-filtered templates
curl '/workflow-templates?industry=fintech' | jq '.[] | .industry_vertical'
```

- [ ] `/workflow-node-types` returns 45 rows
- [ ] 6 categories represented (data_input / processing / decision / ai / action / output)
- [ ] Palette curated subset is 20-35 nodes (not all 45)
- [ ] At least one template per industry vertical

## P2-S16 quick UAT

```bash
# Export YAML
curl /workflows/<id>/export.yaml -H "Accept: application/x-yaml"

# Import YAML
curl -X POST /workflows/import \
  -d '{"yaml_content": "<paste>", "department_id": "<uuid>"}'

# Multi-user collab
curl -X POST /workflows/<id>/editors -d '{"user_id": "...", "role": "EDITOR"}'
curl -X POST /workflows/<id>/comments -d '{"body": "Test review"}'
curl -X POST /workflows/<id>/lock -d '{"ttl_seconds": 600}'    # returns lock_token
curl -X DELETE /workflows/<id>/lock -d '{"lock_token": "<from-above>"}'
```

- [ ] Round-trip: export → save → import → diff nodes/edges = 0
- [ ] Unknown `node_type` in YAML rejected with 400 + helpful message
- [ ] Cross-user lock acquire returns 409 with current holder info
- [ ] Wrong `lock_token` on release returns 403 (K-13 anti-IDOR)

## P2-S18 quick UAT

```bash
# Anomaly detection (requires api_request_log + etl_run_log populated)
curl '/platform/observability/metric-anomalies?metric=api_p95_ms&algorithm=zscore'
curl '/platform/observability/capacity?resource=storage_gb&horizon_days=30'

# Session replay consent flow
curl -X POST /platform/observability/sessions/consent -d '{"granted": true}'
curl -X POST /platform/observability/sessions/<id>/record \
  -d '{"started_at": "...", "events": [...]}'
curl /platform/observability/sessions/<id>/replay
```

- [ ] Anomaly endpoint returns 0 alerts on flat data, ≥1 on injected spike
- [ ] Capacity forecast includes `projected_date_to_limit` when slope > 0
- [ ] `record` without prior `consent grant` returns 403
- [ ] Replay returns events with PII redacted (no raw emails / phones in payload)

## P2-S21 quick UAT

```bash
# OKR CRUD
curl -X POST /p2/strategy/okr -d '<json>'
curl '/p2/strategy/okr?period=Q1%202026&status=ACTIVE'
curl -X PATCH /p2/strategy/okr/<id>/key-results/<kr_id> \
  -d '{"current_value": "5.5"}'   # triggers progress recalc

# NOV recommendations + simulation
curl /economics/reports/manager-digest/recommendations
curl -X POST /economics/reports/manager-digest/simulate \
  -d '{"period_label": "2026-04", "revenue_uplift_pct": "10"}'
```

- [ ] OKR creation accepts inline `key_results` array; `progress` is computed
- [ ] PATCH KR `current_value` updates parent OKR `progress` (denormalized)
- [ ] Recommendations returns top-K underperforming workflows when NOV negative for the quarter
- [ ] Simulation returns 95% CI with assumptions (Vietnamese)

## Knowing-doing gap heuristic quick UAT

```bash
# Trigger a high-confidence tool-needing query
curl -X POST /chat -d '{"message": "Liệt kê tất cả khách hàng VIP có doanh thu giảm tháng này"}'
# Then inspect structured log
kubectl logs ai-orchestrator | grep chat.tool_necessity
# Expected line: { needs_tool: true, confidence: 0.85, suggested_tool_choice: "required", ... }

# Chitchat path (should not force tool)
curl -X POST /chat -d '{"message": "Xin chào, bạn là ai?"}'
# Expected line: { needs_tool: false, confidence: ~0.0, suggested_tool_choice: "auto" }
```

- [ ] High-confidence queries log `confidence ≥ 0.7` AND `suggested_tool_choice="required"`
- [ ] Chitchat queries log low confidence + `auto`
- [ ] No latency regression on chat hot path (heuristic < 1ms per call)

## Sign-off

| Tester | Sprint coverage | Date | Pass | Notes |
|---|---|---|---|---|
| | | | | |

## What ISN'T in this UAT (defer)

- SSO OAuth (P2-AUTH-001) — needs anh provision Google+Microsoft OAuth apps
- Vault prod wiring — `KAORI_MFA_KEY` env var only; field keys use `inline:` prefix
- Background re-encrypt worker — manual lazy re-encrypt only
- Temporal worker live — gated behind `TEMPORAL_ENABLE_WORKER`; defer per P15-S9 closeout
- L4b shared cross-tenant trace memory — pending legal review
- P2-S19/S20 service-level extraction — needs anh approve Phase B
