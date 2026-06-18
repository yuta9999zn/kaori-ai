import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-033 Multi-tier Analysis (PR A — basic + intermediate).
// Mirrors services/ai-orchestrator/routers/multi_tier.py so dev mode renders
// without llm-gateway / postgres running. Templates 35-38 consume these via
// foundation `api()`.
//
// Advanced tier returns 501 (matches BE PR A) — PR B will flip it on.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

type Tier   = "basic" | "intermediate" | "advanced";
type Scope  = "single" | "multi" | "cross";
type Status = "queued" | "running" | "done" | "error";
type Framework = "swot" | "6w" | "2h" | "fishbone";

interface SourceRef {
  layer: "silver" | "gold";
  id:    string;
  label?: string | null;
}

interface MockRun {
  id:                string;
  pipeline_run_id:   string | null;
  tier:              Tier;
  scope:             Scope;
  framework:         Framework | null;
  question:          string | null;
  source_ids:        SourceRef[] | null;
  consent_external:  boolean;
  status:            Status;
  narrative:         string | null;
  templates:         string[];
  config:            Record<string, unknown>;
  workspace_ids:     string[];
  requires_approval: boolean;
  approved_by:       string | null;
  approved_at:       string | null;
  overview:          unknown;
  output_schema_repaired: boolean | null;
  started_at:        string | null;
  completed_at:      string | null;
  created_by_user:   string | null;
  created_at:        string;
}

const hours = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();

// Reuse the F-034 SWOT mock content shape so the result page renders the
// same SWOT view regardless of whether the run came from /frameworks or
// /analysis intermediate. Keeps the FE renderer single-source.
const MOCK_SWOT_CONTENT = {
  strengths: { items: [
    { text: "Doanh thu retail premium tăng 18% YoY", confidence: 0.85 },
    { text: "Loyalty tier-3 retention 91%", confidence: 0.78 },
  ]},
  weaknesses: { items: [
    { text: "Tỷ lệ stock-out kênh online 12%", confidence: 0.7 },
    { text: "CAC channel B tăng 30% Q1", confidence: 0.6 },
  ]},
  opportunities: { items: [
    { text: "Mở SKU premium cho gen Z (5% market share trống)", confidence: 0.65 },
    { text: "Hợp tác chuỗi siêu thị mini quốc gia", confidence: 0.55 },
  ]},
  threats: { items: [
    { text: "Đối thủ X chuẩn bị flash-sale Q3", confidence: 0.7 },
    { text: "Giá nguyên liệu nhập tăng 15% YoY", confidence: 0.6 },
  ]},
  summary: "Đẩy mạnh kênh premium D2C trong Q2 + đa dạng hoá nhà cung cấp; pilot SKU gen-Z trong Q3.",
};

// Two seeded runs so the hub recent-runs section + list endpoint render
// meaningfully on first load. Each tier represented.
const MOCK_RUNS: MockRun[] = [
  {
    id:                "an_mock_intermediate_001",
    pipeline_run_id:   null,
    tier:              "intermediate",
    scope:             "multi",
    framework:         "swot",
    question:          "Mảng bán lẻ Q3 mạnh ở đâu so với đối thủ?",
    source_ids: [
      { layer: "silver", id: "ds-rfm-q3", label: "rfm_q3_2026" },
      { layer: "gold",   id: "revenue_at_risk", label: "revenue_at_risk" },
    ],
    consent_external:  false,
    status:            "done",
    narrative:         MOCK_SWOT_CONTENT.summary,
    templates:         [],
    config:            {},
    workspace_ids:     [],
    requires_approval: false,
    approved_by:       null,
    approved_at:       null,
    overview:          MOCK_SWOT_CONTENT,
    output_schema_repaired: false,
    started_at:        hours(2),
    completed_at:      hours(2),
    created_by_user:   null,
    created_at:        hours(2),
  },
  {
    id:                "an_mock_basic_001",
    pipeline_run_id:   "pr-mock-001",
    tier:              "basic",
    scope:             "single",
    framework:         null,
    question:          "Top 3 yếu tố ảnh hưởng doanh thu kênh D tháng 4?",
    source_ids:        null,
    consent_external:  false,
    status:            "done",
    narrative:         "3 yếu tố chính: (1) khuyến mãi flash giảm 22%; (2) tỷ lệ stock-out tăng 11%; (3) CAC kênh tăng 30%.",
    templates:         ["summary_stats", "rfm_churn"],
    config:            { summary_stats: {} },
    workspace_ids:     [],
    requires_approval: false,
    approved_by:       null,
    approved_at:       null,
    overview: {
      kpi_overview: {
        revenue_total: 5_400_000_000,
        delta_vs_prev_pct: -18.2,
      },
      summary: "3 yếu tố chính: (1) khuyến mãi flash giảm 22%; (2) tỷ lệ stock-out tăng 11%; (3) CAC kênh tăng 30%.",
    },
    output_schema_repaired: null,
    started_at:        hours(36),
    completed_at:      hours(36),
    created_by_user:   null,
    created_at:        hours(36),
  },
];

// Sources picker fixtures — reflect a typical pilot tenant.
const MOCK_SILVER_SOURCES = [
  { id: "pr-mock-001", label: "doanh_thu_q1_2026.xlsx",  layer: "silver", row_count: 12_842 },
  { id: "pr-mock-002", label: "khach_hang_2026q1.csv",   layer: "silver", row_count: 8_120  },
  { id: "pr-mock-003", label: "logistics_2026q1.parquet", layer: "silver", row_count: 4_560  },
];

const MOCK_GOLD_SOURCES = [
  { id: "revenue_at_risk", label: "revenue_at_risk", layer: "gold", row_count: 3_204 },
  { id: "rfm_score",       label: "rfm_score",       layer: "gold", row_count: 8_120 },
  { id: "churn_label",     label: "churn_label",     layer: "gold", row_count: 8_120 },
];

// PR A returns the basic-tier wizard templates. FE 36-analyst-basic.tsx
// expects `{ items: [{id, name, description}] }`.
const MOCK_BASIC_TEMPLATES = [
  { id: "summary_stats", name: "Thống kê tổng hợp",     description: "Mean, median, distribution của các trường số chính." },
  { id: "rfm_churn",     name: "RFM + Churn",            description: "Phân khúc khách hàng theo Recency / Frequency / Monetary, dự đoán churn." },
  { id: "cohort",        name: "Cohort Retention",        description: "Bảng giữ chân khách hàng theo tháng — heatmap cohort × tháng tuổi (M0/M1/M2/...). Cần cột customer_id + ngày giao dịch." },
  { id: "anomaly",       name: "Phát hiện bất thường",   description: "IQR + isolation forest cho các điểm dữ liệu lệch." },
  { id: "time_series",   name: "Time series + forecast", description: "Phân rã trend / season + dự báo 3 kỳ tiếp theo." },
];

// F-035 Cohort heatmap fixture — used when basic run includes the
// `cohort` template. Mirrors what services/ai-orchestrator/analytics/
// engines/statistical.py:_cohort produces (two ChartBlocks: heatmap +
// stats_card). The chart-registry RHeatmap renderer reads
// rows[].cohort + rows[].period + rows[].retention via meta.
const MOCK_COHORT_RETENTION = [
  { cohort: "2026-01", period: 0, retention: 1.0  }, { cohort: "2026-01", period: 1, retention: 0.62 },
  { cohort: "2026-01", period: 2, retention: 0.48 }, { cohort: "2026-01", period: 3, retention: 0.41 },
  { cohort: "2026-02", period: 0, retention: 1.0  }, { cohort: "2026-02", period: 1, retention: 0.68 },
  { cohort: "2026-02", period: 2, retention: 0.55 }, { cohort: "2026-02", period: 3, retention: 0.49 },
  { cohort: "2026-03", period: 0, retention: 1.0  }, { cohort: "2026-03", period: 1, retention: 0.71 },
  { cohort: "2026-03", period: 2, retention: 0.6  },
  { cohort: "2026-04", period: 0, retention: 1.0  }, { cohort: "2026-04", period: 1, retention: 0.74 },
];

const MOCK_COHORT_BLOCKS = [
  {
    id:            "cohort_heatmap",
    type:          "chart",
    title:         "Cohort Retention",
    data_shape:    "scatter_2d",
    default_chart: "heatmap",
    data:          MOCK_COHORT_RETENTION,
    meta:          { x_axis: "period", y_axis: "cohort", value: "retention" },
  },
  {
    id:    "cohort_summary",
    type:  "stats_card",
    title: "Tổng kết Cohort",
    data:  { cohorts_analysed: 4, avg_month1_retention: 0.69 },
  },
];

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

export const multiTierHandlers = [
  // ── Sources picker ─────────────────────────────────────────────
  http.get(`${BASE}/api/v1/analysis/sources`, async ({ request }) => {
    const url = new URL(request.url);
    const layer = (url.searchParams.get("layer") ?? "silver,gold").toLowerCase();
    const layers = new Set(layer.split(",").map((s) => s.trim()).filter(Boolean));
    if (![...layers].every((l) => l === "silver" || l === "gold")) {
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
        "layer must be 'silver', 'gold', or both");
    }
    const items: typeof MOCK_SILVER_SOURCES = [];
    if (layers.has("silver")) items.push(...MOCK_SILVER_SOURCES);
    if (layers.has("gold"))   items.push(...MOCK_GOLD_SOURCES);
    await delay(50);
    return HttpResponse.json({ items });
  }),

  // ── Cross-workspaces (PR B placeholder) ────────────────────────
  http.get(`${BASE}/api/v1/analysis/cross-workspaces`, async () => {
    await delay(40);
    return HttpResponse.json({
      items: [{
        id:           "ws_current",
        name:         "(workspace hiện tại)",
        can_include:  true,
        member_role:  "MANAGER",
      }],
    });
  }),

  // ── External AI quota (PR B placeholder) ───────────────────────
  http.get(`${BASE}/api/v1/analysis/quota/external-ai`, async () => {
    const today = new Date();
    const period = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}`;
    await delay(30);
    return HttpResponse.json({
      external_calls_used:  0,
      external_calls_limit: 100,
      period,
    });
  }),

  // ── List basic-tier templates (FE 36 still hits /api/v2/...) ────
  // Until F-033 PR A's BE wires GET /analysis/templates, this MSW row
  // satisfies the 36-analyst-basic.tsx page on dev mode. Same fixture
  // the wizard step-4 uses (kept consistent so FE behaviour matches).
  http.get(`${BASE}/api/v2/enterprise/analysis/templates`, async ({ request }) => {
    const url = new URL(request.url);
    const tier = url.searchParams.get("tier");
    if (tier && tier !== "basic") {
      return HttpResponse.json({ items: [] });
    }
    await delay(40);
    return HttpResponse.json({ items: MOCK_BASIC_TEMPLATES });
  }),

  // (Pipelines list /api/v1/pipelines is owned by pipeline.ts handler —
  // returns the cursor envelope {data, meta}. Template 36 normalises both
  // shapes itself rather than duplicate handlers here.)

  // ── List runs ──────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/analysis/runs`, async ({ request }) => {
    const url = new URL(request.url);
    const tier = url.searchParams.get("tier");
    const limit = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") ?? 50)));
    let rows = MOCK_RUNS;
    if (tier && tier !== "basic" && tier !== "intermediate" && tier !== "advanced") {
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
        `tier must be 'basic', 'intermediate', or 'advanced'`);
    }
    if (tier) rows = rows.filter((r) => r.tier === tier);
    await delay(60);
    return HttpResponse.json({
      // Strip overview/templates/config from list rows to match BE shape.
      items: rows.slice(0, limit).map(({ overview: _o, templates: _t, config: _c, workspace_ids: _w, requires_approval: _r, approved_by: _ab, approved_at: _at, output_schema_repaired: _os, ...rest }) => rest),
      next_cursor: null,
    });
  }),

  // ── Run detail ─────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/analysis/runs/:id`, async ({ params }) => {
    const id = String(params.id);
    const row = MOCK_RUNS.find((r) => r.id === id);
    if (!row) {
      return problem(404, "/docs/errors/run-not-found", "Analysis run not found", id);
    }
    return HttpResponse.json(row);
  }),

  // ── Create run (basic / intermediate; advanced returns 501) ────
  http.post(`${BASE}/api/v1/analysis/runs`, async ({ request }) => {
    const body = (await request.json()) as {
      tier: Tier;
      pipeline_run_id?: string;
      templates?: string[];
      config?: Record<string, unknown>;
      framework?: Framework;
      question?: string;
      source_ids?: SourceRef[];
      consent_external?: boolean;
    };

    if (body.tier !== "basic" && body.tier !== "intermediate" && body.tier !== "advanced") {
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
        `tier must be 'basic', 'intermediate', or 'advanced' (got '${body.tier}')`);
    }

    if (body.tier === "advanced") {
      if (!body.consent_external) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "tier='advanced' requires consent_external=true (K-4)");
      }
      if (!body.framework) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "framework is required for tier='advanced'");
      }
      const q = (body.question ?? "").trim();
      if (!q) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "question is required for tier='advanced'");
      }
      if (!body.source_ids || body.source_ids.length < 2 || body.source_ids.length > 5) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "source_ids must contain 2 to 5 items for tier='advanced'");
      }
    } else if (body.tier === "basic") {
      if (!body.pipeline_run_id) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "pipeline_run_id is required for tier='basic'");
      }
      if (!body.templates || body.templates.length === 0) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "templates is required for tier='basic'");
      }
      if (body.templates.length > 10) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "at most 10 templates per basic run");
      }
    } else {
      // intermediate
      if (!body.framework) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "framework is required for tier='intermediate'");
      }
      const q = (body.question ?? "").trim();
      if (!q) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "question is required for tier='intermediate'");
      }
      if (!body.source_ids || body.source_ids.length < 2) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "source_ids must contain at least 2 sources for tier='intermediate'");
      }
      if (body.source_ids.length > 5) {
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
          "source_ids must contain 2 to 5 items");
      }
    }

    // Mock tenant flag — flip to `true` to simulate workspace having
    // already opted in to external AI at the tenant level (no per-run
    // approval needed). Default `false` so reviewers can see the gate.
    const tenantConsent = (globalThis as any).__kaoriMockTenantConsent === true;
    const requiresApproval = body.tier === "advanced" && !tenantConsent;

    const newRun: MockRun = {
      id:                `an_mock_${Date.now()}`,
      pipeline_run_id:   body.tier === "basic" ? body.pipeline_run_id! : null,
      tier:              body.tier,
      scope:             body.tier === "basic" ? "single" : body.tier === "intermediate" ? "multi" : "cross",
      framework:         body.tier !== "basic" ? body.framework ?? null : null,
      question:          body.question?.trim() ?? null,
      source_ids:        body.tier !== "basic" ? body.source_ids ?? null : null,
      consent_external:  !!body.consent_external,
      status:            "queued",
      narrative:         null,
      templates:         body.tier === "basic" ? body.templates ?? [] : [],
      config:            body.tier === "basic" ? (body.config ?? {}) : {},
      workspace_ids:     body.tier === "advanced" ? ((body as any).workspace_ids ?? []) : [],
      requires_approval: requiresApproval,
      approved_by:       null,
      approved_at:       null,
      overview:          null,
      output_schema_repaired: null,
      started_at:        null,
      completed_at:      null,
      created_by_user:   null,
      created_at:        new Date().toISOString(),
    };
    MOCK_RUNS.unshift(newRun);

    // Simulate worker — only kick off if the run isn't waiting for
    // approval. The approve endpoint below restarts the timers.
    if (!requiresApproval) {
      kickWorker(newRun);
    }

    await delay(120);
    return HttpResponse.json(
      {
        run_id: newRun.id,
        tier:   newRun.tier,
        status: requiresApproval ? "awaiting_approval" : "queued",
      },
      { status: 202 },
    );
  }),

  // ── Approve advanced run (PR B) ────────────────────────────────
  http.post(`${BASE}/api/v1/analysis/runs/:id/approve`, async ({ params, request }) => {
    const id = String(params.id);
    const row = MOCK_RUNS.find((r) => r.id === id);
    if (!row) return problem(404, "/docs/errors/run-not-found", "Run not found", id);

    // BE enforces X-Role=MANAGER. MSW dev mode trusts the caller —
    // pilots can flip __kaoriMockRole=VIEWER in DevTools to test the 403.
    const role = (globalThis as any).__kaoriMockRole;
    if (role && role !== "MANAGER") {
      return problem(403, "/docs/errors/forbidden", "Forbidden",
        "Only MANAGER can approve advanced runs");
    }
    if (row.tier !== "advanced" || !row.requires_approval || row.approved_at) {
      return problem(404, "/docs/errors/run-not-found", "Not pending",
        "Run not found or already actioned");
    }

    row.approved_by = "11111111-1111-1111-1111-111111111111";
    row.approved_at = new Date().toISOString();
    kickWorker(row);
    await delay(80);
    return HttpResponse.json(row);
  }),
];

function kickWorker(run: MockRun) {
  // running after ~600ms, done after ~3s.
  setTimeout(() => { run.status = "running"; run.started_at = new Date().toISOString(); }, 600);
  setTimeout(() => {
    run.status       = "done";
    run.completed_at = new Date().toISOString();
    if (run.tier !== "basic" && run.framework === "swot") {
      run.overview  = MOCK_SWOT_CONTENT;
      run.narrative = MOCK_SWOT_CONTENT.summary;
    } else if (run.tier !== "basic") {
      run.overview = {
        framework: run.framework,
        summary:   `Mock kết quả tier=${run.tier} framework=${run.framework} cho câu hỏi: "${run.question}".`,
      };
      run.narrative = `Mock kết quả tier=${run.tier} framework=${run.framework}.`;
    } else if (run.templates.includes("cohort")) {
      // F-035: cohort runs carry the heatmap + stats_card blocks so the
      // result page can render the matrix. Mirrors the engine output
      // shape from analytics/engines/statistical.py:_cohort.
      run.overview = {
        summary:   "Cohort Retention đã chạy — average M1 retention 69% trên 4 cohort tháng đầu năm.",
        blocks:    MOCK_COHORT_BLOCKS,
        templates: run.templates,
      };
      run.narrative = "M1 retention trung bình ~69%; cohort tháng 4 mạnh nhất (74%). Ưu tiên pattern onboarding của cohort tháng 4 cho các tháng tiếp.";
    } else {
      run.overview = {
        summary:   `Mock basic run — ${run.templates.length} template chạy trên pipeline ${run.pipeline_run_id}.`,
        templates: run.templates,
      };
      run.narrative = `Mock basic run — ${run.templates.length} template.`;
    }
  }, 3000);
}
