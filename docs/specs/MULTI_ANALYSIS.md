# MULTI-ANALYSIS — Tab Dashboard & Multi-Template Run

> Cơ chế cho phép user chạy **nhiều analysis templates cùng lúc** trên cùng 1 dataset Silver,
> và xem kết quả trong dashboard dạng **tabs**.
>
> Key principle: Silver data được parse 1 lần, mỗi template chạy trên bản copy riêng.
> Không re-upload, không re-clean.

---

## 1. UX Flow — Step 4 (Analysis Config)

```
Step 3: Cleaning Review (xác nhận rules)
    ↓
Step 4: Analysis Config
    ┌─────────────────────────────────────────────────┐
    │ Chọn phân tích bạn muốn chạy                    │
    │                                                 │
    │ [✓] Thống kê tổng quan        (5 hàng tối thiểu)│
    │ [✓] Chuỗi thời gian           (cần cột ngày)    │
    │ [✓] Phân phối dữ liệu         (30 hàng)         │
    │ [ ] Ma trận tương quan  ⚠️    (cần thêm 30 hàng)│
    │ [ ] Phân loại giao dịch NH    (không đủ cột)    │
    │                                                 │
    │ ⏱ Ước tính: ~45 giây · 3 phân tích              │
    │ [Chạy phân tích]                                │
    └─────────────────────────────────────────────────┘

Step 5: Multi-analysis Dashboard
```

**Checkbox** (không phải radio) — user chọn 1-5 templates.

Disabled = không đủ điều kiện (thiếu cột, thiếu hàng) — hiển thị lý do cụ thể.

---

## 2. Tab Dashboard Layout — Step 5

```
┌─ Tổng quan ─┬─ Chuỗi thời gian ─┬─ Phân phối ─┬─ Thống kê ─┐
│ Cross-template summary           │ (spinner)   │            │
│                                  │             │            │
│ ┌──────────┐  ┌──────────┐       │             │            │
│ │ Revenue  │  │ Outliers │       │             │            │
│ │ trend ↑  │  │ 3 items  │       │             │            │
│ └──────────┘  └──────────┘       │             │            │
│                                  │             │            │
│ AI Narrative (Qwen)              │             │            │
│ "Dữ liệu cho thấy..."            │             │            │
└──────────────────────────────────┴─────────────┴────────────┘
```

**"Tổng quan" tab:** tự động generate cross-template insights:
- "Doanh thu tăng 12.4% nhưng phát hiện 3 điểm bất thường cuối tháng"
- "Phân nhóm cho thấy nhóm 2 (VIP) chiếm 31% doanh thu"

Mỗi per-template tab load async — không block lẫn nhau.

---

## 3. Backend — Multi-Template Orchestration

### Request

```python
# POST /api/v1/runs/{run_id}/analyze
{
    "templates": ["summary_stats", "time_series", "distribution"],
    "config": {
        "time_series": {"forecast_days": 30, "granularity": "monthly"},
        "distribution": {"outlier_method": "iqr"}
    }
}
```

### ai-orchestrator Response Flow

```python
# services/ai-orchestrator/consumers/pipeline_consumer.py

async def handle_analyze_request(run_id: str, templates: list[str], config: dict):
    # 1. Load Silver data once
    silver_df = await load_silver(run_id)

    # 2. Run each template as independent coroutine
    tasks = [
        run_template(template_id, silver_df, config.get(template_id, {}), run_id)
        for template_id in templates
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 3. Persist each template result
    for template_id, result in zip(templates, results):
        if isinstance(result, Exception):
            await save_template_error(run_id, template_id, str(result))
        else:
            await save_template_result(run_id, template_id, result)

    # 4. Generate cross-template narrative
    overview = await generate_overview_narrative(templates, results)
    await save_overview(run_id, overview)

    # 5. Emit completion event
    await kafka.emit("pipeline.analysis.complete", {"run_id": run_id, "status": "done"})
```

**Silver data reuse** (K-8 extension): `silver_df` loaded once, passed by reference to all templates (read-only). Memory cost = 1 Silver load, not N.

---

## 4. Frontend — Tab State Management

```typescript
// frontend/src/components/pipeline/ResultsDashboard.tsx

type TemplateStatus = 'pending' | 'running' | 'done' | 'error';

interface MultiAnalysisState {
  overview: OverviewResult | null;
  templates: Record<string, {
    status: TemplateStatus;
    result: TemplateResult | null;
    error: string | null;
  }>;
}
```

**Polling strategy:**
- Poll `GET /api/v1/runs/{run_id}/status` mỗi 3s
- Khi status = `analysis_complete` → fetch `GET /api/v1/runs/{run_id}/results`
- Hoặc SSE (Phase 2): Kafka `pipeline.analysis.complete` → FE gets push notification

---

## 5. Sidebar Analytics Group

```
Navigation Sidebar
├── Dashboard (/)
├── Pipeline (/pipeline)
│   └── Current run status
├── Analytics (/analytics)          ← chỉ hiện khi đã có results
│   ├── Tổng quan
│   ├── Chuỗi thời gian              ← chỉ hiện templates đã chạy
│   ├── Phân phối
│   └── Thống kê
└── Settings
```

Sidebar tự động show/hide analytics sub-items dựa trên `analysis_runs` của user.

---

## 6. Database Schema

```sql
-- analysis_runs: mỗi lần user bấm "Chạy phân tích"
CREATE TABLE analysis_runs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    enterprise_id UUID NOT NULL REFERENCES enterprises(id),
    run_id       UUID NOT NULL REFERENCES pipeline_runs(id),
    templates    TEXT[] NOT NULL,          -- ["summary_stats", "time_series"]
    config       JSONB  NOT NULL DEFAULT '{}',
    status       TEXT   NOT NULL DEFAULT 'running',   -- running|done|error
    overview     JSONB,                    -- cross-template narrative
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- analysis_results: kết quả mỗi template
CREATE TABLE analysis_results (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id),
    enterprise_id  UUID NOT NULL,          -- K-1 denorm
    template_id    TEXT NOT NULL,
    status         TEXT NOT NULL,          -- done|error
    results_payload JSONB,                 -- blocks (charts + narrative)
    error_message  TEXT,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 7. Bookmarkable URLs

```
/pipeline               → Step 1: Upload
/pipeline?step=schema   → Step 2: Schema review
/pipeline?step=clean    → Step 3: Cleaning
/pipeline?step=analyze  → Step 4: Analysis config
/pipeline?step=results  → Step 5: Results

/analytics              → Latest analysis overview
/analytics/time_series  → Time series tab
/analytics/distribution → Distribution tab
/analytics?run_id=uuid  → Specific historical run
```

---

## 8. Implementation Status (2026-04-22)

| Thành phần | Status |
|---|---|
| `TEMPLATE_REGISTRY` (10 templates) | ✅ Done |
| `get_eligible_templates()` | ✅ Done |
| `POST /analyze` endpoint | ✅ Skeleton |
| **asyncio.gather multi-template runner** | ⚠️ Pending |
| **Cross-template overview narrative** | ⚠️ Pending |
| **`analysis_runs` + `analysis_results` tables** | ⚠️ Pending (migrations 005+) |
| **Frontend tab dashboard (step 5)** | ⚠️ Pending |
| **Frontend polling / SSE** | ⚠️ Pending |
| **Sidebar analytics group** | ⚠️ Pending |
| **Per-template result renderers** | ⚠️ Pending (needs chart registry) |
