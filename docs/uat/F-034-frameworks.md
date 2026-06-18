# UAT — F-034 Analysis Frameworks

> **Function:** F-034 — SWOT / 6W / 2H / Fishbone backend (MoM-YoY + Custom deferred to v1; FE wiring of templates 40-46 separate PR)
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role (no extra role gate beyond the JWT — frameworks are low-risk read-side analysis)
> **Service:** ai-orchestrator (`/api/v1/frameworks/*`) + llm-gateway (Issue #3 path)
> **DB tables:** `framework_runs` (migration 030)
> **Owner:** Customer Success driver
> **Prepared:** 2026-05-03

---

## 0. What landed (this PR)

| Endpoint | Purpose |
|---|---|
| `GET  /api/v1/frameworks/templates` | Static catalogue (4 entries: swot / 6w / 2h / fishbone) — used by FE hub gallery |
| `POST /api/v1/frameworks/generate`  | 202 + `run_id`; spawns `asyncio.create_task(run_framework)`. Validates `framework_code` + question + length |
| `GET  /api/v1/frameworks?cursor=&limit=` | Cursor-paginated list (cursor format `<iso>\|<uuid>`) |
| `GET  /api/v1/frameworks/{run_id}`  | Full detail incl. validated `content_json` |

Background worker:
1. Loads run + flips `status='running'`
2. Renders `templates.py` system_prompt with `{{question}}` + `{{source_ref}}` substitution
3. Calls `llm_router.complete_structured(output_schema=template.schema)` — Issue #3 layer validates + repairs once on JSON failure
4. Writes `mark_ready` with parsed dict + extracted narrative (per-framework rule — see `extract_narrative` in templates.py)

K-4 `consent_external` is per-call. Default OFF (Qwen local). When the request asks for external + tenant `consent_external_ai` is FALSE → llm-gateway raises ConsentDeniedError → run flips `status='failed'`.

---

## 1. Pre-flight

| # | Check | Expected |
|---|---|---|
| A1 | `curl -fsS localhost:8093/health` | ok |
| A2 | `curl -fsS localhost:8095/health` | ok (llm-gateway up) |
| A3 | `SELECT to_regclass('framework_runs');` | non-NULL after migration 030 |
| A4 | `curl -fsS http://localhost:8080/api/v1/frameworks/templates` (any tenant JWT) | 200 with 4 items: swot / 6w / 2h / fishbone |

---

## 2. Happy path — generate SWOT

```bash
EID=<pilot-enterprise-id>
JWT=<JWT for any P2 role with X-Enterprise-ID:$EID>

curl -sX POST http://localhost:8080/api/v1/frameworks/generate \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "framework_code": "swot",
    "question": "Đối thủ X giảm giá 8% — ta giữ thị phần Q2 thế nào?",
    "source_ref": "gold:retail_2026q1",
    "consent_external": false
  }' | jq

# Expected 202:
# { "run_id": "...", "status": "queued" }

# Poll detail until ready (typically 5-15s on Qwen local).
RUN=<run_id from above>
watch -n 2 "curl -s http://localhost:8080/api/v1/frameworks/$RUN \
            -H 'Authorization: Bearer $JWT' | jq -r '.status, .narrative'"

# When status='ready', fetch full payload:
curl -s http://localhost:8080/api/v1/frameworks/$RUN \
     -H "Authorization: Bearer $JWT" | jq '.content_json'
# Expected: object matching SWOT schema — 4 quadrants × ≥2 items each
# with text + confidence, plus a summary string.
```

---

## 3. Per-framework smoke

| Framework | Question | Expected `content_json` shape |
|---|---|---|
| swot | "Đối thủ giảm giá — ta giữ thị phần Q2 thế nào?" | `{ strengths, weaknesses, opportunities, threats, summary }` — 4 quadrants × 2-N items |
| 6w | "Vì sao churn tăng vùng APAC tháng 4?" | `{ who, what, when, where, why, how, summary }` — all string |
| 2h | "Triển khai loyalty mới — bao nhiêu KH ảnh hưởng, chi phí?" | `{ how: { approach, steps[3-7] }, how_much: { estimate, unit, confidence, assumptions }, summary }` |
| fishbone | "Doanh thu kênh A giảm 20% — gốc rễ ở đâu?" | `{ problem, categories[3-6] × causes[2-5], root_cause_hypothesis }` |

---

## 4. Negative paths

| Test | Expected |
|---|---|
| `POST /generate` with `framework_code="5why"` | 400 with detail listing allowed codes |
| `POST /generate` with empty question | 400 — `question is required` |
| `POST /generate` with 2500-char question | 422 (Pydantic max_length=2000) |
| `POST /generate` with `consent_external=true` while tenant has `tenant_settings.consent_external_ai=false` | Run flips to `status='failed'` with `last_error` mentioning K-4 |
| `GET /frameworks/{nonexistent-uuid}` | 404 |
| Cross-tenant `GET` (run belongs to tenant B, header is tenant A) | 404 (RLS makes the row invisible) |
| Bad cursor (`cursor=abc`) | 400 — `invalid cursor (expected '<iso8601>\|<uuid>')` |
| LLM returns malformed JSON 2x in a row (Issue #3 repair fails) | Run flips to `status='failed'` with `LLM.OUTPUT_VALIDATION_FAILED` text |

---

## 5. Forensics queries

```sql
-- "Show me this tenant's last 10 framework runs + their outcomes"
SELECT run_id, framework_code, status, narrative, created_at, completed_at,
       last_error
  FROM framework_runs
 WHERE enterprise_id = '<eid>'
 ORDER BY created_at DESC
 LIMIT 10;

-- "Rate of failed runs by framework code (last 7 days)"
SELECT framework_code,
       COUNT(*) AS total,
       COUNT(*) FILTER (WHERE status = 'failed')   AS failed,
       COUNT(*) FILTER (WHERE status = 'ready')    AS ready
  FROM framework_runs
 WHERE created_at > NOW() - INTERVAL '7 days'
 GROUP BY framework_code
 ORDER BY total DESC;

-- "Stuck-running rows" (worker crashed mid-LLM call)
SELECT run_id, framework_code, created_at
  FROM framework_runs
 WHERE status = 'running' AND created_at < NOW() - INTERVAL '15 minutes';
```

---

## 6. Sign-off — backend (PR #119)

- [ ] Migration 030 applies cleanly (FlywayMigrationIT cold-boot 30/30)
- [ ] `pytest tests/test_frameworks_service.py` 16/16 green
- [ ] ai-orchestrator full suite 311/311 green
- [ ] OpenAPI snapshot refreshed (26 paths)
- [ ] Schema snapshot regenerated (`scripts/schema-drift.py --check` PASS)
- [ ] One real run per framework returns valid `content_json` matching the schema (validated by Issue #3 layer)
- [ ] K-4 path: `consent_external=true` from a non-consent tenant fails cleanly with a captured error
- [ ] Cross-tenant requests return 404

---

## 7. Frontend walk-through (this FE PR)

`/p2/frameworks` hub:

- 2 sections — "Khung sẵn sàng" (4 cards: SWOT / 6W / 2H / Fishbone) + "Sắp ra mắt" (2 dashed cards: MoM/YoY · Custom — link to legacy mock pages).
- "Lịch sử gần đây" table: 10 most recent runs across all frameworks. Click a row → opens `/p2/frameworks/{code}?run=<id>` so the page polls and renders that run.
- K-10 banner ("Một câu hỏi = một khung") always visible at the top.

Per-framework page (e.g. `/p2/frameworks/swot`):

- Form: question textarea (3-2000 chars, counter shown) · optional source_ref input · K-4 consent toggle (default OFF, lock icon when local-only, globe icon when external enabled).
- "Phân tích" → POST `/api/v1/frameworks/generate` → 202 + run_id → URL `?run=<id>` (replace, not push) → page polls every 2s.
- States: queued / running show a spinner card; failed shows last_error + suggestion to bật AI ngoài; ready renders the framework-specific layout below.
- "Run mới" button (visible after a run) clears state + URL.

Result rendering per framework:

| Framework | Layout |
|---|---|
| SWOT | 4-quadrant grid; each cell shows item text + confidence percentage; summary callout above |
| 6W | Vertical card with 6 labeled rows (Who · What · When · Where · Why · How) + narrative |
| 2H | 2-column: How (approach + ordered steps) · How much (large estimate + unit + confidence + assumption bullets) |
| Fishbone | Problem callout + 2-col category grid (each category with its causes + depth badges: triệu chứng / trực tiếp / gốc rễ) + root cause hypothesis in red callout |

| FE test | Expected |
|---|---|
| First load on `/p2/frameworks` | 4 active cards + 2 placeholder cards + 3 seeded MOCK runs (1 SWOT ready, 1 Fishbone ready, 1 6W failed) |
| Click SWOT card → open `/p2/frameworks/swot` | Empty form, no run loaded |
| Submit "Đối thủ giảm giá — Q2 thế nào?" with consent OFF | URL becomes `?run=fr_mock_…`, polling shows "Đã xếp hàng" → "Đang phân tích" → "Hoàn thành" with 4-quadrant SWOT (~3s in MSW dev) |
| Refresh the page mid-run | Polling resumes (URL carries run_id) |
| Open Lịch sử row "Doanh thu kênh A giảm 20%" | Lands on `/p2/frameworks/fishbone-ishikawa?run=…`, renders fishbone layout immediately |
| Open Lịch sử row "Tại sao churn vùng APAC tăng?" (failed) | Lands on `/p2/frameworks/6w?run=…`, renders failure card with last_error |
| Submit empty / 2-char question | "Phân tích" button stays disabled (FE-side validation) |
| Disable MSW (real BE) | Same UI, real `/api/v1/frameworks/*` data — must include `X-Enterprise-ID` header via JWT |
