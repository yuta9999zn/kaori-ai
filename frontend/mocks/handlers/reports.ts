import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-038 Reports — mirror the BE shapes from
// services/ai-orchestrator/routers/reports.py so dev mode works without a
// running ai-orchestrator. Templates 47-reports-hub + 48-report-auto consume
// these via the foundation `api()` helper.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

const BUILT_IN_MONTHLY_SUMMARY_ID = "00000000-0000-0000-0000-000000000001";

interface MockReport {
  report_id:    string;
  template_id:  string;
  title:        string;
  owner_email:  string;
  status:       "queued" | "running" | "ready" | "failed";
  narrative:    string | null;
  created_at:   string;
  completed_at: string | null;
  last_error:   string | null;
}

// Seed a small spread of statuses so the hub renders all four badge colours.
const MOCK_REPORTS: MockReport[] = [
  {
    report_id:    "rep_mock_001",
    template_id:  BUILT_IN_MONTHLY_SUMMARY_ID,
    title:        "Báo cáo tổng hợp tháng 4/2026",
    owner_email:  "manager@acme.vn",
    status:       "ready",
    narrative:    "Doanh thu tăng 12% so với tháng 3; rủi ro churn vùng APAC nhô cao.",
    created_at:   new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 2 * 24 * 3600 * 1000 + 45_000).toISOString(),
    last_error:   null,
  },
  {
    report_id:    "rep_mock_002",
    template_id:  BUILT_IN_MONTHLY_SUMMARY_ID,
    title:        "Báo cáo tuần 17 — phân khúc khách hàng",
    owner_email:  "ops@acme.vn",
    status:       "running",
    narrative:    null,
    created_at:   new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    completed_at: null,
    last_error:   null,
  },
  {
    report_id:    "rep_mock_003",
    template_id:  BUILT_IN_MONTHLY_SUMMARY_ID,
    title:        "Báo cáo ROI marketing Q1",
    owner_email:  "minh@acme.vn",
    status:       "queued",
    narrative:    null,
    created_at:   new Date(Date.now() - 30 * 1000).toISOString(),
    completed_at: null,
    last_error:   null,
  },
  {
    report_id:    "rep_mock_004",
    template_id:  "11111111-2222-3333-4444-555555555555", // custom (per-tenant) template
    title:        "Báo cáo tuỳ chỉnh — vùng miền Nam",
    owner_email:  "lan@acme.vn",
    status:       "failed",
    narrative:    null,
    created_at:   new Date(Date.now() - 7 * 3600 * 1000).toISOString(),
    completed_at: new Date(Date.now() - 7 * 3600 * 1000 + 12_000).toISOString(),
    last_error:   "LLM.OUTPUT_VALIDATION_FAILED — schema mismatch on top_risks[].severity",
  },
];

// F-038 distribution (PR #118) audit rows joined to notification_outbox.
// Pre-seeded with one distribution against the first ready report so the
// "Lịch sử" table renders out of the box.
interface MockDistribution {
  distribution_id:    string;
  report_id:          string;
  recipient_email:    string;
  channel:            string;
  outbox_id:          string | null;
  dispatch_status:    string;
  custom_message:     string | null;
  triggered_by_user:  string | null;
  dispatch_error:     string | null;
  created_at:         string;
  outbox_status:      string | null;
  outbox_attempts:    number | null;
  outbox_error:       string | null;
  outbox_sent_at:     string | null;
}

const MOCK_DISTRIBUTIONS: MockDistribution[] = [
  {
    distribution_id:    "dst_mock_seed_001",
    report_id:          "rep_mock_001",
    recipient_email:    "lan@acme.vn",
    channel:            "email",
    outbox_id:          "obx_mock_seed_001",
    dispatch_status:    "sent",
    custom_message:     "Anh chị xem báo cáo trước cuộc họp 15h chiều nay nhé.",
    triggered_by_user:  null,
    dispatch_error:     null,
    created_at:         new Date(Date.now() - 6 * 3600 * 1000).toISOString(),
    outbox_status:      "sent",
    outbox_attempts:    1,
    outbox_error:       null,
    outbox_sent_at:     new Date(Date.now() - 6 * 3600 * 1000 + 8_000).toISOString(),
  },
  {
    distribution_id:    "dst_mock_seed_002",
    report_id:          "rep_mock_001",
    recipient_email:    "huy@acme.vn",
    channel:            "email",
    outbox_id:          "obx_mock_seed_002",
    dispatch_status:    "sent",
    custom_message:     "Anh chị xem báo cáo trước cuộc họp 15h chiều nay nhé.",
    triggered_by_user:  null,
    dispatch_error:     null,
    created_at:         new Date(Date.now() - 6 * 3600 * 1000).toISOString(),
    outbox_status:      "sent",
    outbox_attempts:    2,
    outbox_error:       null,
    outbox_sent_at:     new Date(Date.now() - 6 * 3600 * 1000 + 14_000).toISOString(),
  },
];

export const reportsHandlers = [
  // ── List (cursor-paginated, F-038) ──────────────────────────────────────
  http.get(`${BASE}/api/v1/reports`, async ({ request }) => {
    const url    = new URL(request.url);
    const limit  = Math.min(Number(url.searchParams.get("limit") ?? 50), 200);
    const cursor = url.searchParams.get("cursor");

    // Cursor format mirrors BE: <iso>|<uuid>. We only use the index portion in
    // mock-land for simplicity.
    const startIdx = cursor ? Number(cursor.split("|")[0]) || 0 : 0;
    const slice    = MOCK_REPORTS.slice(startIdx, startIdx + limit);
    const hasMore  = startIdx + limit < MOCK_REPORTS.length;
    const next     = hasMore && slice.length > 0
      ? `${startIdx + limit}|${slice[slice.length - 1].report_id}`
      : null;

    await delay(180);
    return HttpResponse.json({
      items:       slice,
      next_cursor: next,
    });
  }),

  // ── Detail (F-038) ──────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/reports/:id`, async ({ params }) => {
    const id  = String(params.id);
    const row = MOCK_REPORTS.find((r) => r.report_id === id);
    if (!row) {
      return new HttpResponse(JSON.stringify({
        type:   "/docs/errors/report-not-found",
        title:  "Report not found",
        status: 404,
        detail: id,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    return HttpResponse.json({
      ...row,
      content_json: row.status === "ready" ? {
        kpi_overview: [
          { label: "Doanh thu tháng",     value: "1.234.000.000 ₫", delta_pct: 12.4 },
          { label: "Khách hàng hoạt động", value: 4_812,             delta_pct:  3.1 },
          { label: "Tỷ lệ churn",          value: "7.2%",            delta_pct: -0.6 },
        ],
        trends: [
          { metric: "Doanh thu",     direction: "up",   reason: "Mở rộng kênh phân phối miền Nam." },
          { metric: "Tỷ lệ churn",   direction: "down", reason: "Chương trình loyalty quý 1 hiệu quả." },
        ],
        top_risks: [
          { name: "Tồn kho phụ kiện cao",  severity: "medium", impact_vnd: 420_000_000 },
          { name: "Thiếu nhân sự CS",      severity: "high",   impact_vnd: 180_000_000 },
        ],
        recommendations: [
          "Triển khai chiến dịch flash-sale phụ kiện trong 2 tuần đầu tháng 5.",
          "Tuyển bổ sung 3 nhân sự CS cho khu vực TP.HCM.",
          "Mở thêm điểm bán tại Đà Nẵng — phân tích cohort cho thấy nhu cầu chưa được đáp ứng.",
        ],
      } : null,
    });
  }),

  // ── Generate (F-038) — 202 + queued report ──────────────────────────────
  http.post(`${BASE}/api/v1/reports/generate`, async ({ request }) => {
    const body = (await request.json()) as {
      template_id: string;
      title:       string;
      owner_email: string;
      params?:     Record<string, unknown>;
    };

    if (!body.title || body.title.trim().length < 3) {
      return new HttpResponse(JSON.stringify({
        type:   "/docs/errors/validation",
        title:  "Validation error",
        status: 422,
        detail: "title must be at least 3 characters",
      }), { status: 422, headers: { "Content-Type": "application/problem+json" } });
    }

    const newReport: MockReport = {
      report_id:    `rep_mock_${Date.now()}`,
      template_id:  body.template_id,
      title:        body.title,
      owner_email:  body.owner_email,
      status:       "queued",
      narrative:    null,
      created_at:   new Date().toISOString(),
      completed_at: null,
      last_error:   null,
    };
    MOCK_REPORTS.unshift(newReport);

    // Simulate the background worker promoting status to ready after a beat
    // so the FE list refresh actually shows progress in dev mode.
    setTimeout(() => {
      newReport.status       = "ready";
      newReport.narrative    = "Báo cáo demo đã sinh xong. Mở chi tiết để xem nội dung.";
      newReport.completed_at = new Date().toISOString();
    }, 4_000);

    await delay(120);
    return HttpResponse.json({
      report_id: newReport.report_id,
      status:    "queued",
    }, { status: 202 });
  }),

  // ─── Distribute (F-038 follow-up — BE PR #118) ──────────────────────────
  // Per-recipient outbox enqueue + audit row. Mirrors the BE shape so the
  // wired UI exercises the real fields without ai-orchestrator running.
  http.post(`${BASE}/api/v1/reports/:id/distribute`, async ({ params, request }) => {
    const id  = String(params.id);
    const row = MOCK_REPORTS.find((r) => r.report_id === id);
    if (!row) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/report-not-found",
        title: "Report not found", status: 404, detail: id,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    if (row.status !== "ready") {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/report-not-ready", status: 409,
        title: "Report not ready",
        detail: `report ${id} is in status '${row.status}', only 'ready' reports can be distributed`,
      }), { status: 409, headers: { "Content-Type": "application/problem+json" } });
    }

    const body = (await request.json()) as {
      recipients?:    string[];
      custom_message?: string;
    };
    const recipients = Array.isArray(body.recipients)
      ? body.recipients.map((r) => (r ?? "").trim()).filter(Boolean)
      : [];
    if (recipients.length === 0) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/invalid-request", status: 400,
        title: "Invalid request",
        detail: "at least one recipient is required",
      }), { status: 400, headers: { "Content-Type": "application/problem+json" } });
    }
    if (recipients.length > 50) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/invalid-request", status: 400,
        title: "Invalid request",
        detail: `recipient list capped at 50 (got ${recipients.length})`,
      }), { status: 400, headers: { "Content-Type": "application/problem+json" } });
    }
    // Server-side dedup mirror.
    const seen = new Set<string>();
    const unique: string[] = [];
    for (const r of recipients) {
      const k = r.toLowerCase();
      if (seen.has(k)) continue;
      seen.add(k); unique.push(r);
    }

    const now = new Date().toISOString();
    const trimmed = (body.custom_message ?? "").slice(0, 500) || null;
    const distributions = unique.map((recipient) => {
      const distributionId = `dst_mock_${Date.now()}_${recipient.length}_${Math.random().toString(36).slice(2, 6)}`;
      const outboxId       = `obx_mock_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
      MOCK_DISTRIBUTIONS.unshift({
        distribution_id:    distributionId,
        report_id:          id,
        recipient_email:    recipient,
        channel:            "email",
        outbox_id:          outboxId,
        dispatch_status:    "pending",
        custom_message:     trimmed,
        triggered_by_user:  null,
        dispatch_error:     null,
        created_at:         now,
        outbox_status:      "pending",
        outbox_attempts:    0,
        outbox_error:       null,
        outbox_sent_at:     null,
      });

      // Mark as sent after a beat so the history table shows lifecycle in dev.
      setTimeout(() => {
        const target = MOCK_DISTRIBUTIONS.find((d) => d.distribution_id === distributionId);
        if (target) {
          target.outbox_status   = "sent";
          target.outbox_attempts = 1;
          target.outbox_sent_at  = new Date().toISOString();
        }
      }, 2500);

      return { recipient, distribution_id: distributionId, outbox_id: outboxId, status: "pending" };
    });

    await delay(150);
    return HttpResponse.json({
      report_id:       id,
      recipient_count: unique.length,
      success_count:   unique.length,
      failure_count:   0,
      distributions,
    }, { status: 202 });
  }),

  // ─── List distributions ─────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/reports/:id/distributions`, async ({ params }) => {
    const id = String(params.id);
    const items = MOCK_DISTRIBUTIONS.filter((d) => d.report_id === id);
    await delay(80);
    return HttpResponse.json({ items });
  }),
];
