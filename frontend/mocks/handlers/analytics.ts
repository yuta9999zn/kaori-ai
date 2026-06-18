import { http, HttpResponse, delay } from "msw";

const BASE = "http://localhost:8080";

const TEMPLATE_IDS = [
  "summary_stats","time_series","distribution","correlation",
  "clustering","cohort","churn","anomaly","regression","bank_classify",
];

// ── Shape for the analytics overview page (fetch-based api(), needs { data: [...] }) ──
const OVERVIEW_RUNS = TEMPLATE_IDS.map((tid, i) => ({
  id: `arun_${tid}`,
  template_id: tid,
  status: (i < 7 ? "done" : i === 7 ? "error" : "running") as "done" | "error" | "running",
  created_at: new Date(Date.now() - i * 4 * 60 * 60 * 1000).toISOString(),
  results_payload:
    i < 7
      ? {
          narrative: "Phân tích hoàn tất. Xem chi tiết từng biểu đồ bên dưới.",
          blocks: [
            { type: "stats_card", label: "Tổng hàng dữ liệu", value: "1.842" },
            {
              type: "chart", title: "Phân phối theo nhóm", chart_kind: "bar",
              columns: ["range", "count"],
              data: [
                { range: "0–100K", count: 234 }, { range: "100–500K", count: 891 },
                { range: "500K–1M", count: 512 }, { range: "1M+", count: 205 },
              ],
            },
          ],
        }
      : undefined,
}));

// ── Shape for ResultsDashboard (axios analyticsApi.getRun(), flat, no wrapper) ──
const RESULT_DASHBOARD_RUN = {
  id: "arun_new001",
  run_id: "run_0002",
  templates: ["summary_stats"],
  status: "done",
  overview: {
    narrative:
      "Tập dữ liệu 1.842 hàng × 6 cột. Doanh thu trung bình 433.671 ₫/đơn. Phát hiện 3 giao dịch nghi ngờ lỗi nhập liệu. Xu hướng tháng 4 tăng 17% so với tháng 3.",
    templates_run: ["summary_stats"],
    row_count: 1842,
    col_count: 6,
  },
  template_results: [
    {
      template_id: "summary_stats",
      status: "done",
      error_message: null,
      results_payload: {
        template_id: "summary_stats",
        blocks: [
          {
            id: "bs1", type: "stats_card", title: "Tổng quan",
            data: [{ "Total Rows": 1842, "Doanh thu TB": "433.671 ₫", "Lớn nhất": "12.500.000 ₫", "Nhỏ nhất": "15.000 ₫" }],
          },
          {
            id: "bc1", type: "chart", title: "Phân phối doanh thu",
            default_chart: "bar", data_shape: "categorical_count",
            meta: { x_axis: "range", y_axis: "count" },
            data: [
              { range: "0–100K", count: 234 }, { range: "100–500K", count: 891 },
              { range: "500K–1M", count: 512 }, { range: "1M+", count: 205 },
            ],
          },
          {
            id: "bc2", type: "chart", title: "Doanh thu theo tháng",
            default_chart: "line", data_shape: "time_series",
            meta: { x_axis: "month", y_axis: "revenue" },
            data: [
              { month: "T1", revenue: 98_000_000 }, { month: "T2", revenue: 123_000_000 },
              { month: "T3", revenue: 104_000_000 }, { month: "T4", revenue: 145_000_000 },
            ],
          },
          {
            id: "bn1", type: "narrative",
            text: "Phân phối doanh thu lệch phải (right-skewed). Nhóm 100–500K chiếm 48% đơn hàng. Tháng 4 đạt doanh thu cao nhất 145 triệu đồng (+17% MoM). Khuyến nghị điều tra 3 giao dịch có giá trị âm.",
            provider: "qwen",
          },
        ],
      },
    },
  ],
};

export const analyticsHandlers = [
  // ── List runs — fetch-based api(), so response MUST have { data: [...] } ────
  http.get(`${BASE}/api/v1/analytics/runs`, async ({ request }) => {
    const url   = new URL(request.url);
    const tid   = url.searchParams.get("template_id");
    const limit = Number(url.searchParams.get("limit") ?? 20);
    await delay(180);
    const filtered = tid
      ? OVERVIEW_RUNS.filter((r) => r.template_id === tid)
      : OVERVIEW_RUNS;
    return HttpResponse.json({ data: filtered.slice(0, limit) });
  }),

  // ── Single run — axios analyticsApi.getRun(), FLAT response (no data: wrap) ─
  http.get(`${BASE}/api/v1/analytics/runs/:runId`, async ({ params }) => {
    await delay(200);
    // Always return the result-dashboard structure regardless of runId
    return HttpResponse.json({ ...RESULT_DASHBOARD_RUN, id: params.runId as string });
  }),

  // ── Available templates ────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/analytics/templates`, async () => {
    await delay(120);
    return HttpResponse.json({
      data: TEMPLATE_IDS.map((id) => ({ id, eligible: true, min_rows_met: true })),
    });
  }),

  // ── Create run — axios analyticsApi.createRun(), FLAT response ──────────────
  http.post(`${BASE}/api/v1/analytics/runs`, async () => {
    await delay(450);
    return HttpResponse.json({ analysis_run_id: "arun_new001", status: "queued" });
  }),
];
