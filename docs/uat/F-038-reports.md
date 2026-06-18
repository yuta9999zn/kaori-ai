# UAT — F-038 Reports (auto LLM-generated)

> **Function:** F-038 — Reports (auto path only this round; builder + templates library + distribution = follow-up PRs)
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role can list + read; MANAGER+ recommended for `/generate` (no role gate enforced server-side yet — Phase 2 follow-up if pilot abuses it)
> **Service:** ai-orchestrator (`/api/v1/reports/*`) + llm-gateway (Issue #3 path) + notification-service (outbox dispatcher)
> **DB tables:** `report_templates`, `reports` (migration 027)
> **Owner:** Customer Success driver
> **Prepared:** 2026-05-02

---

## 0. What landed (PR #113)

| Endpoint | Purpose |
|---|---|
| `POST /api/v1/reports/generate` | 202 + `report_id`; spawns `asyncio.create_task(run_report)` background worker |
| `GET /api/v1/reports?cursor=&limit=` | Cursor-paginated list. Items omit `content_json` |
| `GET /api/v1/reports/{id}` | Full detail incl. validated `content_json` |

Background worker fetches the template, calls `llm_router.complete_structured(output_schema=template.output_schema)` (Issue #3 — gateway repairs once on validation failure), writes `mark_ready` with parsed JSON + extracted narrative, emits `kaori.reports.generated` (Issue #4), enqueues `notification_outbox` row with `template='report-ready'` (Issue #6).

Built-in seed: `monthly_summary` at template_id `00000000-0000-0000-0000-000000000001`.

---

## 1. Pre-flight checks

| # | Check | Expected |
|---|---|---|
| A1 | `curl -fsS localhost:8093/health` | `{"status":"ok"}` |
| A2 | `curl -fsS localhost:8095/health` | `{"status":"ok"}` |
| A3 | Migration 027 applied (`SELECT to_regclass('report_templates'); SELECT to_regclass('reports');`) | both return non-NULL |
| A4 | Built-in template visible (`SELECT slug, is_built_in FROM report_templates WHERE template_id = '00000000-0000-0000-0000-000000000001';`) | `monthly_summary, t` |
| A5 | Pilot tenant has ≥ 3 `analysis_runs` rows with non-null `overview` | LLM context block needs prior analysis to summarise |
| A6 | `notification-service` running and dispatcher polling | check `services/notification-service` logs for outbox poll |

If A5 fails the report still generates but `kpi_overview` will read "Chưa có phân tích nào" — escalate to anh to load datasets first via the F-017→F-021 wizard.

---

## 2. Test scenarios (auto-generate path)

### SCN-1 — Happy path generate + read

| Step | Action | Expected |
|------|--------|----------|
| 1 | `POST /api/v1/reports/generate` with body `{template_id: "00000000-0000-0000-0000-000000000001", title: "Báo cáo tháng 4/2026", owner_email: "anh@example.com", params: {period: "2026-04"}}` + `X-Enterprise-ID: <pilot tenant>` | **202** with `{"report_id": "<uuid>", "status": "queued"}` |
| 2 | Immediately `GET /api/v1/reports/{id}` | `status` is `queued` or `running`. `content_json` is null |
| 3 | Wait 10–30 s (Qwen 7B), re-`GET` | `status` = `ready`. `content_json` populated with `{kpi_overview, trends, top_risks, recommendations}` matching the schema. `narrative` = short text |
| 4 | `GET /api/v1/reports?limit=10` | The new report appears at the top. `next_cursor` is null if total ≤ 10, else opaque string |
| 5 | Inspect `notification_outbox`: `SELECT template, status, payload->>'report_id' FROM notification_outbox ORDER BY created_at DESC LIMIT 1;` | `template = report-ready`, `status` cycles `pending → sent` once dispatcher picks up |
| 6 | Inspect Kafka topic `kaori.reports.generated` (Kafka UI on `localhost:8085`) | One message keyed by `tenant_id` with payload `{report_id, enterprise_id, template_id, status: "ready", title, owner_email}` |

### SCN-2 — Output schema validation + repair (Issue #3)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Run SCN-1 multiple times against Qwen 7B (less reliable than 14B) | Some runs trigger the gateway's one-shot repair path |
| 2 | After runs, query: `SELECT decision_type, output_value->>'schema_repaired' AS repaired, COUNT(*) FROM decision_audit_log WHERE decision_type = 'llm.completion' AND created_at > NOW() - INTERVAL '1 hour' GROUP BY 1, 2;` | At least some rows with `repaired = true` are expected on Qwen 7B; on 14B they should be rare |
| 3 | If a 2nd attempt also fails → BE returns `mark_failed` with `last_error = "LLM.OUTPUT_VALIDATION_FAILED"` | Visible via `GET /api/v1/reports/{id}` (`status = failed`, `last_error` set) |

### SCN-3 — Tenant isolation (K-1, K-12, RLS)

| Step | Action | Expected |
|------|--------|----------|
| 1 | As Tenant A: generate a report → grab `report_id` | 202 + uuid |
| 2 | As Tenant B (different `X-Enterprise-ID` JWT): `GET /api/v1/reports/{tenantA-report-id}` | **404** (NOT 403). RLS hides the row entirely from the SELECT — same path as not-exists |
| 3 | As Tenant B: `GET /api/v1/reports?limit=200` | Tenant A's report is NOT in the items list |

### SCN-4 — Validation errors

| Step | Action | Expected |
|------|--------|----------|
| 1 | `POST /api/v1/reports/generate` with `title: "ab"` (< 3 chars) | **422** with field-level error |
| 2 | Same with `owner_email: "not-an-email"` | **422** |
| 3 | Same with `template_id: "11111111-1111-1111-1111-111111111111"` (unknown) | **404** RFC 7807 |
| 4 | `GET /api/v1/reports?cursor=garbage` | **400** `"invalid cursor (expected '<iso8601>|<uuid>')"` |
| 5 | `GET /api/v1/reports?limit=500` | **422** (server cap is 200) |

### SCN-5 — Pagination

| Step | Action | Expected |
|------|--------|----------|
| 1 | Generate 12 reports (script or hand-loop SCN-1) | 12 rows in `reports` for the tenant |
| 2 | `GET /api/v1/reports?limit=5` | 5 items, `next_cursor` populated |
| 3 | `GET /api/v1/reports?limit=5&cursor=<from prev>` | next 5 items, no overlap with page 1, `next_cursor` populated |
| 4 | `GET /api/v1/reports?limit=5&cursor=<from prev>` | last 2 items, `next_cursor: null` |

### SCN-6 — Worker safety net

| Step | Action | Expected |
|------|--------|----------|
| 1 | Stop llm-gateway (`docker compose stop llm-gateway`) → generate a report | 202 immediately. Worker raises inside `run_report` |
| 2 | Wait 10 s, re-`GET /api/v1/reports/{id}` | `status = failed`, `last_error` non-null |
| 3 | Inspect `kaori.reports.generated` topic | One message with `status = failed` (worker emitted before failing) |
| 4 | Inspect `notification_outbox` | NO `report-ready` row for the failed report (only on success) |
| 5 | Restart llm-gateway | regression smoke: generate a fresh report, expect SCN-1 happy path |

---

## 3. Cross-cutting expectations

| # | Check |
|---|---|
| X1 | Response envelope is plain `{report_id, status, ...}` (no `data` wrapper for these endpoints — matches v1-era convention; v2 envelope rollout is a Phase 2 cross-cutting PR) |
| X2 | RFC 7807 on errors (`application/problem+json`) — verified manually because Pydantic validation surfaces on FastAPI default formatter; gateway pass-through |
| X3 | `enterprise_id` never accepted from query string — JWT only via `X-Enterprise-ID` header from gateway (K-12) |
| X4 | Idempotency-Key header on `POST /generate` is honored at the gateway layer (K-13). Same key replayed within 24h returns the original 202 |
| X5 | Every successful generation writes a `decision_audit_log` row from llm-gateway (`decision_type = 'llm.completion'`, `chosen_method = 'qwen-internal'` unless tenant has consent_external_ai = true) |
| X6 | Email body uses `services/notification-service/templates/report_ready.html` (Vietnamese; mirrors invite.html design) |

---

## 4. Frontend wiring (next PR — UAT post-merge)

The 5 P2 templates in `frontend/components/p2/templates/`:

| Template | Status post-FE-PR | UAT step |
|---|---|---|
| 47-reports-hub.tsx | Wired to `GET /api/v1/reports` | Visit `/p2/reports/hub` → list view |
| 48-report-auto.tsx | Wired to `POST /api/v1/reports/generate` (single-recipient v0) | Fill form → submit → success banner with report_id |
| 49-report-builder.tsx | F-053 typo patched only; FE wiring deferred (no `POST /reports` builder endpoint yet) | n/a this round |
| 50-report-template.tsx | F-053 typo patched only; FE wiring deferred | n/a this round |
| 51-report-distribution.tsx | F-053 typo patched only; FE wiring deferred | n/a this round |

---

## 4b. Distribution dispatcher (this PR — migration 029)

Manual multi-recipient send for a ready report. Reuses the `report-ready`
template — pilot can forward a finished monthly summary to a leadership
list without regenerating.

```bash
EID=<pilot-enterprise-id>
RID=<a ready report's report_id>

# 1. Distribute to 2 recipients with a custom intro.
curl -sX POST -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" \
  -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/reports/$RID/distribute -d '{
    "recipients": ["lan@acme.vn", "huy@acme.vn"],
    "custom_message": "Anh chị xem báo cáo trước cuộc họp 15h nhé."
  }' | jq

# Expected 202 + summary:
# { "report_id": "...", "recipient_count": 2, "success_count": 2,
#   "failure_count": 0, "distributions": [
#     { "recipient": "lan@acme.vn", "distribution_id": "...", "outbox_id": "...", "status": "pending" },
#     { "recipient": "huy@acme.vn", "distribution_id": "...", "outbox_id": "...", "status": "pending" }
#   ]}

# 2. Inspect the audit trail (joined to live notification_outbox state).
curl -s -H "X-Enterprise-ID: $EID" \
  http://localhost:8080/api/v1/reports/$RID/distributions | jq
# Each item carries dispatch_status (frozen at distribute-time) +
# outbox_status / outbox_attempts / outbox_sent_at (live from the
# notification-service poller).

# 3. Confirm SMTP delivery (after notification-service poller tick).
psql -c "SELECT recipient_email, status, attempts, sent_at, last_error
           FROM notification_outbox
          WHERE source_ref = 'report:$RID:dist'
          ORDER BY created_at DESC;"
```

| Negative test | Expected |
|---|---|
| Distribute a `status='running'` report | 409 with detail "only 'ready' reports can be distributed" |
| Distribute non-existent report (or another tenant's) | 404 with detail "report not found" (RLS makes cross-tenant invisible) |
| Empty `recipients` list | 400 with detail "at least one recipient is required" |
| 60 recipients in one call | 400 with detail "recipient list capped at 50" |
| Same email twice (different casing) | Server de-dupes silently — `recipient_count` = 1 |
| `custom_message` with 1500 chars | Trimmed to 500 chars in `report_distributions.custom_message` + email body |

---

## 4c. Frontend walk-through (distribution FE — this PR)

`/p2/reports/distribution` covers two states:

**No `?report=` querystring** — picker mode:
- Search input + table of all `status='ready'` reports
- Row click → URL push with `?report=<id>` → switches to distribute mode

**With `?report=<id>`** — distribute mode:
- "Đổi báo cáo" link top-left → goes back to picker
- Report context card (title / owner / completion time / narrative + green `ready` badge). When status ≠ ready, yellow warn card explains BE will reject (409)
- Form: recipients textarea (split by `,` or newline · live dedup count + cap warning ≥ 50) · custom_message ≤ 500 chars (counter live)
- "Gửi ngay" → POST `/distribute` → success banner ("Đã enqueue N email") + history refresh. Failures surface as RFC 7807 problem
- "Lịch sử phát hành" table joins with `notification_outbox` for live SMTP state. Each row: recipient · custom_message · SMTP badge (Đã gửi / Đang chờ / Thất bại) · time
- Bottom hint reminds channel=email only · cron + role-groups + Slack/webhook are v1

`/p2/reports` hub Send icon:
- For published (ready) rows → deep-links to `/p2/reports/distribution?report=<id>`
- For other statuses → disabled with tooltip "Chỉ phát hành được khi báo cáo ở trạng thái 'Đã phát hành'"

| FE test | Expected |
|---|---|
| First load no querystring | Picker shows MSW MOCK_REPORTS filtered to ready (1 seeded row) |
| Click picker row | URL becomes `?report=rep_mock_001`, distribute panel renders with seeded 2-row history |
| Submit empty recipients | Button stays disabled |
| Type "lan@acme.vn, Lan@Acme.VN, huy@acme.vn" | Counter "2 email duy nhất sau khi gộp trùng" (case-insensitive) |
| 51 distinct emails | Counter goes red "vượt giới hạn 50"; button disabled |
| Submit 2 recipients with custom message | Success banner, form clears, history refreshes with 2 new rows pending → sent (~2.5s MSW lifecycle) |
| Click hub Send icon on ready row | Deep-links to distribution with `?report=` set |
| Click hub Send icon on running/failed row | Disabled, tooltip explains |
| Disable MSW (real BE) | Same UI, real `/api/v1/reports/{id}/distribute` round-trip |

---

## 5. Known limitations (intentional — sign-off acknowledges)

| Limitation | Workaround | Closes when |
|---|---|---|
| ~~Single recipient per report~~ | ~~Manually forward email~~ | ✅ Closed by distribution dispatcher this PR (50 recipients/call, custom message) |
| Distribution channels = email only | (channel CHECK constraint blocks others) | v1 follow-up — Slack webhook + generic webhook |
| No `schedule_cron` runner | Generate manually via `/p2/reports/auto` form per cycle | Small scheduler service (Phase 2 follow-up; F-038 spec line item) |
| ~~FE distribution screen mock-only~~ | ~~Use Auto path + curl/Postman~~ | ✅ Closed by FE this PR — `/p2/reports/distribution?report=<id>` wired |
| Builder / template-library screens are still mock-only | Use Auto path only for pilot demo | F-038 follow-up PRs |
| Gold dataset picker (`GET /api/v1/data/gold/datasets`) returns 404 in dev | Hub page falls back to MOCK_DATASETS fixtures | Separate "data exploration" feature surface (Phase 2) |
| Qwen 7B occasionally fails output schema → repair → still fails → `mark_failed` | Re-run; escalate to Qwen 14B if reproducible | Phase 3 — fine-tuning F-074 |

---

## 6. Sign-off

| Role | Name | Date | Result (PASS / FAIL) |
|------|------|------|----------------------|
| Tester (CS driver) |  |  |  |
| Pilot tenant lead |  |  |  |
| Backend dev |  |  |  |
