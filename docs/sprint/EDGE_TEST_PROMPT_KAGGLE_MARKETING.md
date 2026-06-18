# Edge test prompt — Kaori workflow E2E with Kaggle Marketing data

> **Purpose:** Hand this prompt verbatim to Claude Edge (a fresh agent with no
> memory of the Build Week conversation). The agent should run end-to-end
> on anh's local Kaori stack and exercise both Build-Week guardrails:
> **Gap 5** (IF/ELSE dangling validation) and **Gap 4** (auto KPI trigger
> after upload).
>
> The agent does **not** need access to this doc beyond the prompt block
> below; everything it needs to do its job is inline.

---

## The prompt (paste from here ↓ into Claude Edge)

You're testing the Kaori AI workflow system end-to-end on the local dev stack at `D:\Kaori System`. The work just shipped two guardrails — your job is to prove they hold using real data from Kaggle. Don't fix anything you find broken; report it and stop. Anh will triage.

### Environment (verify first)

- Working dir: `D:\Kaori System`
- Docker stack must be up: `docker compose ps` → `postgres`, `redis`, `kafka`, `ollama`, `ai-orchestrator`, `data-pipeline`, `api-gateway` all `Up`. If any service is down, start the missing ones with `docker compose up -d <name>` then re-check.
- API Gateway: `http://localhost:8080`
- Frontend dev: `http://localhost:3000` (start with `cd frontend && npm run dev` if not running)
- Health check: `curl http://localhost:8080/health` returns 200

### Pre-flight: confirm Build-Week guardrails are in code

Read these three locations and confirm the code is present. If any is missing, stop and report — the Build-Week commits weren't pulled, no point continuing.

| File | Symbol to find |
|---|---|
| `services/ai-orchestrator/routers/workflow_builder.py` | `_check_dangling_branches` function + `_RUNTIME_STATES` constant |
| `services/ai-orchestrator/consumers/pipeline_consumer.py` | `_handle_bronze_complete` async function |
| `services/data-pipeline/data_plane/bronze/ingestor.py` | `bronze_payload` dict carrying `workflow_id` + `workflow_step_id` |

### Dataset

**Primary (preferred):** Kaggle dataset **`jackdaoud/marketing-data`** (≈5 MB, 2240 rows). It's a Marketing department's customer + campaign data — fits `dept_type='marketing'` exactly. Columns: `ID, Year_Birth, Education, Income, Recency, MntWines, NumDealsPurchases, AcceptedCmp1..5, Response`. These columns map cleanly to `gold.customer_360_marketing` so KPIs like `cac`/`ltv`/`roas` produce non-null values.

```bash
mkdir -p ./test-data
kaggle datasets download -d jackdaoud/marketing-data -p ./test-data --unzip
ls ./test-data   # expect marketing_data.csv
export CSV_PATH=./test-data/marketing_data.csv
```

**Fallback (no Kaggle CLI auth required):** Repo ships with the **Kaggle Olist Brazilian E-Commerce** dataset at `data/kaggle/olist/olist_customers_dataset.csv` (~9 MB, 99441 rows). Columns: `customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state`. **Caveat:** Olist customers has no revenue/cost/spend columns, so marketing KPIs (cac/ltv/roas) WILL return null values from Gold. That's still a valid PASS for the Gap 4 contract (wire-up fires, handler logs `measurements_skipped=N` for the right reason) — Test B Step 6 expects 0 rows in `kpi_measurements` and the Báo cáo tab shows the "Chưa có lần compute KPI" empty state. Don't fail the test because of null values; only fail if the consumer didn't log `orchestrator.kpi.workflow_upload_done` at all.

```bash
export CSV_PATH="data/kaggle/olist/olist_customers_dataset.csv"
```

If neither dataset is available:
1. Tell anh: "I have no Kaggle CLI auth and `data/kaggle/olist/olist_customers_dataset.csv` is missing. Manual fetch path: https://www.kaggle.com/datasets/jackdaoud/marketing-data — put `marketing_data.csv` at `./test-data/marketing_data.csv` and resume."
2. Stop until he confirms.

### Pick a real Marketing dept from the seeded Vingroup demo

```bash
psql $DATABASE_URL -c "SELECT e.enterprise_id, e.name AS enterprise, d.department_id, d.name AS dept, d.dept_type FROM enterprises e JOIN departments d ON d.enterprise_id = e.enterprise_id WHERE d.dept_type = 'marketing' LIMIT 5"
```

Pick the first row. Capture `enterprise_id` and `department_id`. Find a MANAGER user for that enterprise:

```bash
psql $DATABASE_URL -c "SELECT user_id FROM users WHERE enterprise_id = '<enterprise_id>' AND 'MANAGER' = ANY(roles) LIMIT 1"
```

If no MANAGER user exists, fall back to any user_id from that enterprise and note it in the report.

Set shell vars:

```bash
export EID="<enterprise_id>"
export DID="<department_id>"
export UID="<user_id>"
export H="http://localhost:8080/api/v1"
```

---

### Test A — Gap 5: dangling IF/ELSE must block activation

1. Create an empty workflow:

   ```bash
   curl -sX POST "$H/workflows" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d "{\"name\":\"Edge test — dangling\",\"department_id\":\"$DID\"}"
   ```
   Capture `workflow_id` → `$WF`.

2. Add a `decision_if_else` node:

   ```bash
   curl -sX POST "$H/workflows/$WF/nodes" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d '{"title":"Approve campaign?","node_type":"decision_if_else"}'
   ```
   Capture `node_id` → `$DEC`.

3. Add one follow-up step:

   ```bash
   curl -sX POST "$H/workflows/$WF/nodes" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d '{"title":"Send to creative team","node_type":"step"}'
   ```
   Capture `node_id` → `$NX`.

4. Wire ONLY the IF_TRUE arm (deliberately leave ELSE_FALSE dangling):

   ```bash
   curl -sX POST "$H/workflows/$WF/edges" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d "{\"source_node_id\":\"$DEC\",\"target_node_id\":\"$NX\",\"label\":\"true\"}"
   ```

5. Try to activate:

   ```bash
   curl -i -X PUT "$H/workflows/$WF" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d '{"state":"ACTIVE_BASELINE"}'
   ```

   **PASS criteria — all must hold:**
   - HTTP `400 Bad Request`
   - `detail.code == "WORKFLOW.DANGLING_BRANCH"`
   - `detail.issues` array has one entry where `node_type == "decision_if_else"`, `expected_edges == 2`, `actual_edges == 1`
   - The workflow is **still in DRAFT** state (verify with `GET /workflows/$WF`)

6. Fix the danglе: add an ELSE_FALSE node + arm.

   ```bash
   curl -sX POST "$H/workflows/$WF/nodes" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d '{"title":"Send rejection note","node_type":"step"}'
   # Capture → $NY
   curl -sX POST "$H/workflows/$WF/edges" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d "{\"source_node_id\":\"$DEC\",\"target_node_id\":\"$NY\",\"label\":\"false\"}"
   ```

7. Re-activate. **PASS:** HTTP 200, `state == "ACTIVE_BASELINE"`.

---

### Test B — Gap 4: upload to a workflow step auto-fires KPI compute

1. Create a clean Marketing workflow:

   ```bash
   curl -sX POST "$H/workflows" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d "{\"name\":\"Edge test — Marketing E2E\",\"department_id\":\"$DID\"}"
   # Capture → $WF2
   ```

2. Add step 1 — data intake card with `required_document_types`:

   ```bash
   curl -sX POST "$H/workflows/$WF2/nodes" \
     -H "X-Enterprise-ID: $EID" -H "X-User-ID: $UID" -H "Content-Type: application/json" \
     -d '{
       "title":"Tiếp nhận dữ liệu khách hàng",
       "title_vi":"Tiếp nhận dữ liệu khách hàng",
       "node_type":"step",
       "required_document_types":[{"kind":"csv","name":"Marketing customer data","required":true}]
     }'
   # Capture → $S1
   ```

3. Upload the Kaggle CSV with the workflow-step attachment header:

   ```bash
   curl -sX POST "$H/upload" \
     -H "X-Enterprise-ID: $EID" \
     -H "X-User-ID: $UID" \
     -H "X-Department-ID: $DID" \
     -H "X-Workflow-Step-ID: $S1" \
     -H "Idempotency-Key: $(uuidgen || python -c 'import uuid; print(uuid.uuid4())')" \
     -F "file=@$CSV_PATH"
   ```

   Note: K-13 requires `Idempotency-Key` on every POST under `/api/v1/`. Add it to every mutating `curl` in this prompt; the shell function below covers it. All POST/PUT calls earlier in this doc also need this header — they were elided for brevity.

   **PASS criteria for the response:**
   - HTTP 200
   - `run_id`, `workflow_step_id == $S1`, `workflow_id == $WF2` all present in body
   - `status == "uploading"`

4. **Wait 15 seconds** (parse + Bronze land + Kafka dispatch is async).

5. Verify the consumer fired:

   ```bash
   docker compose logs ai-orchestrator --tail 200 | grep "orchestrator.kpi.workflow_upload_done"
   ```

   **PASS:** at least one log line tagged with `dept_type=marketing`, `total_kpis>=1`. Capture `measurements_written` and `measurements_skipped` for the report.

6. Verify `kpi_measurements` rows landed:

   ```bash
   psql $DATABASE_URL -c "SELECT kpi_code, raw_value, classification, period_kind, computed_by, computed_at FROM kpi_measurements WHERE department_id = '$DID' AND computed_by = 'workflow_upload' ORDER BY computed_at DESC LIMIT 10"
   ```

   **PASS criteria — pick the right branch based on the dataset chosen at the top:**

   - **If using `jackdaoud/marketing-data` (preferred):** ≥1 row with `computed_by = 'workflow_upload'` AND non-null `raw_value` on at least cac/ltv/roas. The Báo cáo tab in Test C will show actual numbers.
   - **If using `data/kaggle/olist/olist_customers_dataset.csv` (fallback):** 0 rows is the **expected** outcome — the handler logged `measurements_skipped = total_kpis` because Olist customers has no revenue/spend/cost columns for marketing KPI formulas to hit. PASS only if the consumer logged `orchestrator.kpi.workflow_upload_done` (Step 5) without errors. The Báo cáo tab in Test C will show the empty state "Chưa có lần compute KPI".

6b. **Optional — diagnose Gold-empty if you see 0 rows.** Run this query to confirm WHERE the pipeline stopped:

   ```bash
   psql $DATABASE_URL -c "SELECT 'bronze_rows' AS tier, count(*) FROM bronze_rows WHERE enterprise_id='$EID' UNION ALL SELECT 'silver_rows', count(*) FROM silver_rows WHERE enterprise_id='$EID' UNION ALL SELECT 'gold.customer_360_marketing', count(*) FROM gold.customer_360_marketing WHERE enterprise_id='$EID'"
   ```

   Known state today (2026-05-16): Bronze→Silver projection does NOT auto-fire after upload — needs explicit `POST /api/v1/clean`. If Silver=0 with Bronze>0, that's the documented gap, not a regression. Note it for follow-up #6 ("Auto Bronze→Silver→Gold trigger").

---

### Test C — FE verification (light)

Open `http://localhost:3000/p2/workflows/$WF2` in a browser:

1. Tab "Cây tài liệu" → step "Tiếp nhận dữ liệu khách hàng" should show `marketing_data.csv` as an attached file.
2. Tab "Báo cáo" → KPI panel. If Test B Step 6 returned ≥1 row with non-null `raw_value`, the panel shows the number(s). If all were null-skipped, the panel still shows "Chưa có lần compute KPI" — note that, it's expected on a cold Gold tier.

Take 1 screenshot of each tab. Attach to the report.

---

### Reporting back

Send anh exactly this shape, no preamble:

```
GAP 5 (dangling validation): PASS | FAIL — <one-line evidence>
GAP 4 (auto KPI trigger):    PASS | FAIL — <one-line evidence>
Workflow E2E happy path:     PASS | FAIL — <one-line evidence>
FE verification:             PASS | FAIL — <one-line evidence>

Dataset: <jackdaoud/marketing-data | kaggle/olist olist_customers_dataset.csv (fallback)>, <row_count> rows
Enterprise: <enterprise_name> (<eid>)
Department: <dept_name> (<did>), dept_type=marketing

Surprises / blockers: <bullet list, or "none">
Suggested follow-ups for anh: <bullet list>
```

Rules:
- **Do not** attempt to fix anything you find broken. Report and stop.
- **Do not** push, commit, or modify code. This is a read/test pass only.
- If a step blocks for >2 minutes with no clear cause, stop and report.
- If `kpi_definitions` table has zero rows for `dept_type='marketing'`, that's a seed gap — note it, Test B's "measurements_written" expectation drops to 0 and `total_kpis=0`. Still report Gap 4 as PASS if the consumer logged `orchestrator.kpi.no_kpis_for_dept` (correct fast-path behaviour).
- Vietnamese in titles is fine; use Vietnamese-aware tools (don't strip diacritics).

End of prompt.
