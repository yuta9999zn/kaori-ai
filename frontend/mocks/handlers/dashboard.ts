import { http, HttpResponse, delay } from "msw";

const BASE = "http://localhost:8080";

// Matches DashboardPage's StatePayload interface exactly
const DASHBOARD_STATE = {
  state: "results_ready" as const,
  run_id: "run_0001",
  analysis_run_id: "arun_xyz789",
  pipeline_status: "analysis_complete",
  templates_run: ["summary_stats", "time_series"],
  metrics: {
    datasets_processed: 14,
    datasets_delta:     0.17,
    analyses_run:       28,
    analyses_delta:     0.12,
    insights_generated: 45,
    insights_delta:     0.23,
    avg_data_quality:   91,
  },
  quota: { used: 45, total: 100 },
  kpis: [
    {
      template: "summary_stats",
      title: "Tổng quan dữ liệu",
      data: { "Total Rows": 1842, "Avg Revenue": "433.671 ₫", "Max Value": "12.500.000 ₫" },
    },
    {
      template: "time_series",
      title: "Xu hướng doanh thu",
      data: { "Tăng trưởng MoM": "+17%", "Tháng cao nhất": "T4", "Tổng Q1": "470 triệu ₫" },
    },
  ],
};

// CR-0018 — matches ai-orchestrator /insights/feed: {insights:[{title, body,
// category, grounding_score, flagged_claims, disclaimer}]}.
const MOCK_INSIGHTS = [
  {
    id: "ins_1", category: "risk",
    title: "Tỷ lệ churn tháng 3 tăng 18%",
    body: "Churn lên 18% sau khi khuyến mãi Q1 kết thúc; nhóm VIP giảm tần suất mua.",
    grounding_score: 1.0, flagged_claims: [],
    disclaimer: "AI tạo từ dữ liệu — nên kiểm chứng trước khi quyết định.",
  },
  {
    id: "ins_2", category: "opportunity",
    title: "Phân khúc 25–34 tăng 23% MoM",
    body: "Kênh social mang lại khách mới phân khúc 25–34, tăng 23% so tháng trước.",
    grounding_score: 0.5, flagged_claims: [23],
    disclaimer: "⚠ 1 số chưa khớp dữ liệu đo được (23) — kiểm chứng trước khi hành động.",
  },
  {
    id: "ins_3", category: "trend",
    title: "Dữ liệu giao dịch tháng 4 đã chuẩn hoá",
    body: "Pipeline đã chuẩn hoá xong dữ liệu giao dịch tháng 4.",
    grounding_score: 1.0, flagged_claims: [],
    disclaimer: "AI tạo từ dữ liệu — nên kiểm chứng trước khi quyết định.",
  },
];

const MOCK_DECISIONS = Array.from({ length: 42 }, (_, i) => ({
  id: `dec_${i + 1}`,
  decision_type: ["language_detect","column_mapping","purpose_classify","rule_trigger","preflight_go_nogo","model_select"][i % 6],
  entity_ref:    ["sales_q1.xlsx","customer_master.csv","transactions_apr.xlsx", null][i % 4],
  confidence:    [0.98, 0.91, 0.73, 0.62, 0.88, 0.55][i % 6],
  method:        ["exact","fuzzy","llm","heuristic","user_confirmed"][i % 5],
  needs_user_confirm: i % 7 === 0,
  uncertainty_flags: i % 7 === 0 ? ["low_confidence"] : [],
  created_at: new Date(Date.now() - i * 3 * 60 * 60 * 1000).toISOString(),
}));

export const dashboardHandlers = [
  // ── Dashboard state — axios dashboardApi.getState(), FLAT response ──────────
  http.get(`${BASE}/api/v1/dashboard/state`, async () => {
    await delay(280);
    return HttpResponse.json(DASHBOARD_STATE);
  }),

  // ── Insights feed — ai-orchestrator returns { insights: [...] } (CR-0018) ────
  http.get(`${BASE}/api/v1/insights/feed`, async () => {
    await delay(220);
    return HttpResponse.json({ insights: MOCK_INSIGHTS });
  }),

  // ── Strategy ask — axios dashboardApi / direct api(), flat response OK ───────
  http.post(`${BASE}/api/v1/strategy/ask`, async ({ request }) => {
    const body = (await request.json()) as { question: string };
    await delay(1100);
    const q = body.question.toLowerCase();
    if (q.includes("tại sao") || q.includes("why")) {
      return HttpResponse.json({
        framework: "five_why",
        problem: body.question,
        chain: [
          "Doanh số tháng 3 giảm 15% so với tháng 2",
          "Số đơn hàng mới giảm trong khi giá trị đơn TB tăng nhẹ",
          "Lưu lượng kênh online giảm sau khi ngừng chiến dịch email",
          "Ngân sách email marketing bị cắt từ đầu tháng 3",
          "Ưu tiên ngân sách chuyển sang kênh offline trong Q1",
        ],
        narrative: "Nguyên nhân gốc rễ: tái phân bổ ngân sách marketing làm sụt giảm lưu lượng kênh digital.",
        recommendations: [
          "Khôi phục chiến dịch email marketing 2 lần/tuần",
          "A/B test nội dung email để tối ưu tỷ lệ mở",
          "Thiết lập ngân sách tối thiểu 30% cho kênh digital",
        ],
      });
    }
    return HttpResponse.json({
      framework: "swot",
      quadrants: {
        S: ["Dữ liệu khách hàng phong phú (2,8k+)", "Tỷ lệ giữ chân khách VIP >85%"],
        W: ["Chi phí logistics tăng", "Phụ thuộc 2 nhà cung cấp chính"],
        O: ["Thị trường online tier 2–3 chưa bão hoà", "Xu hướng mua sắm di động tăng"],
        T: ["Cạnh tranh sàn TMĐT lớn", "Biến động tỷ giá ảnh hưởng nhập khẩu"],
      },
      narrative: "Nền tảng khách hàng mạnh nhưng cần đa dạng hoá chuỗi cung ứng và đẩy mạnh kênh digital.",
      recommendations: [
        "Xây dựng chương trình loyalty cho khách VIP",
        "Tìm thêm 2–3 nhà cung cấp dự phòng",
        "Thử nghiệm mô hình bán hàng tại thị trường tỉnh",
      ],
    });
  }),

  // ── Billing — fetch-based api(), needs { data: ... } ────────────────────────
  http.get(`${BASE}/api/v1/billing/summary`, async () => {
    await delay(180);
    return HttpResponse.json({
      data: {
        plan: "STARTER", quota_used: 45, quota_limit: 100,
        period_end: new Date(Date.now() + 15 * 24 * 60 * 60 * 1000).toISOString(),
      },
    });
  }),

  // ── Decisions — fetch-based api(), needs { data, total, page, limit } ────────
  http.get(`${BASE}/api/v1/decisions`, async ({ request }) => {
    const url   = new URL(request.url);
    const page  = Number(url.searchParams.get("page")  ?? 1);
    const limit = Number(url.searchParams.get("limit") ?? 20);
    await delay(280);
    const start = (page - 1) * limit;
    return HttpResponse.json({
      data:  MOCK_DECISIONS.slice(start, start + limit),
      total: MOCK_DECISIONS.length,
      page,
      limit,
    });
  }),
];
