import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-034 Frameworks — mirror BE shapes from
// services/ai-orchestrator/routers/frameworks.py so dev mode renders
// without the LLM stack running. Templates f034-frameworks-wired.tsx
// consume these via foundation `api()`.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

type FrameworkCode = "swot" | "6w" | "2h" | "fishbone";
type RunStatus     = "queued" | "running" | "ready" | "failed";

interface MockRun {
  run_id:           string;
  framework_code:   FrameworkCode;
  question:         string;
  source_ref:       string | null;
  consent_external: boolean;
  status:           RunStatus;
  narrative:        string | null;
  content_json:     any | null;
  created_at:       string;
  completed_at:     string | null;
  last_error:       string | null;
}

// Catalogue mirrors REGISTRY in services/ai-orchestrator/frameworks/templates.py.
const CATALOGUE = [
  { code: "swot",     name: "SWOT Analysis",       description: "Strengths · Weaknesses · Opportunities · Threats — đánh giá vị thế cạnh tranh dựa trên dữ liệu thực." },
  { code: "6w",       name: "6W Analysis",         description: "Who · What · When · Where · Why · How — phân tích bối cảnh đầy đủ trước khi quyết định." },
  { code: "2h",       name: "2H Analysis",         description: "How · How much — đào sâu cách thực hiện và định lượng quy mô." },
  { code: "fishbone", name: "Fishbone (Ishikawa)", description: "Truy nguyên gốc rễ — nhóm nguyên nhân theo 4M (Man / Method / Machine / Material) hoặc tự đề xuất." },
];

const hours = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString();

// Seed two completed runs of distinct frameworks so the hub history table
// renders meaningfully on first load. Each carries valid content_json so
// the corresponding framework page also renders cleanly when opened with
// ?run=<id>.

const MOCK_SWOT_CONTENT = {
  strengths: { items: [
    { text: "Thương hiệu mạnh ở miền Nam",        confidence: 0.85 },
    { text: "Chuỗi cung ứng linh hoạt — 48h đến tay khách", confidence: 0.7 },
  ]},
  weaknesses: { items: [
    { text: "Chi phí marketing trên doanh thu cao (~22%)", confidence: 0.6 },
    { text: "Phụ thuộc 60% nguyên liệu từ 1 nhà cung cấp",  confidence: 0.55 },
  ]},
  opportunities: { items: [
    { text: "Mở rộng kênh online — D2C tăng 3× YoY",        confidence: 0.75 },
    { text: "Hợp tác chuỗi siêu thị quốc gia (đang đàm phán)", confidence: 0.65 },
  ]},
  threats: { items: [
    { text: "Đối thủ X giảm giá 8% từ tháng 4",  confidence: 0.8 },
    { text: "Nguyên liệu nhập tăng 12% YoY",      confidence: 0.6 },
  ]},
  summary: "Tập trung mở rộng kênh online trong Q2 + đa dạng hoá nhà cung cấp để đối phó nguy cơ giá.",
};

const MOCK_FISHBONE_CONTENT = {
  problem: "Doanh thu kênh A (cửa hàng truyền thống) giảm 20% trong tháng 4/2026.",
  categories: [
    { name: "Con người", causes: [
      { text: "Onboarding nhân viên Sales mới chưa đủ kỹ năng cross-sell", depth: 2 },
      { text: "Tỷ lệ nghỉ việc 18% Q1 — nhân sự thiếu liên tục",         depth: 1 },
    ]},
    { name: "Quy trình", causes: [
      { text: "Quy trình kiểm soát giá vùng chưa chuẩn hoá",            depth: 3 },
      { text: "Thiếu cơ chế escalation khi đối thủ giảm giá",            depth: 2 },
    ]},
    { name: "Công cụ", causes: [
      { text: "POS không cập nhật tồn kho realtime — bán nhầm hết hàng", depth: 2 },
    ]},
    { name: "Dữ liệu", causes: [
      { text: "Báo cáo doanh số trễ 3 ngày — phản ứng chậm",             depth: 1 },
    ]},
  ],
  root_cause_hypothesis:
    "Quy trình kiểm soát giá vùng chưa chuẩn hoá dẫn tới phản ứng chậm khi đối thủ giảm giá, kết hợp với onboarding Sales chưa đủ tự tin xử lý phản đối giá.",
};

const MOCK_RUNS: MockRun[] = [
  {
    run_id:           "fr_mock_swot_001",
    framework_code:   "swot",
    question:         "Đối thủ X giảm giá 8% — chiến lược giữ thị phần Q2 thế nào?",
    source_ref:       "gold:retail_2026q1",
    consent_external: false,
    status:           "ready",
    narrative:        "Tập trung mở rộng kênh online trong Q2 + đa dạng hoá nhà cung cấp để đối phó nguy cơ giá.",
    content_json:     MOCK_SWOT_CONTENT,
    created_at:       hours(28),
    completed_at:     new Date(+new Date(hours(28)) + 12_000).toISOString(),
    last_error:       null,
  },
  {
    run_id:           "fr_mock_fishbone_001",
    framework_code:   "fishbone",
    question:         "Doanh thu kênh A giảm 20% — gốc rễ ở đâu?",
    source_ref:       "analysis_run:42",
    consent_external: false,
    status:           "ready",
    narrative:
      "Quy trình kiểm soát giá vùng chưa chuẩn hoá dẫn tới phản ứng chậm khi đối thủ giảm giá, kết hợp với onboarding Sales chưa đủ tự tin xử lý phản đối giá.",
    content_json:     MOCK_FISHBONE_CONTENT,
    created_at:       hours(50),
    completed_at:     new Date(+new Date(hours(50)) + 14_000).toISOString(),
    last_error:       null,
  },
  {
    run_id:           "fr_mock_failed_001",
    framework_code:   "6w",
    question:         "Tại sao churn vùng APAC tăng?",
    source_ref:       null,
    consent_external: true,
    status:           "failed",
    narrative:        null,
    content_json:     null,
    created_at:       hours(72),
    completed_at:     new Date(+new Date(hours(72)) + 8_000).toISOString(),
    last_error:       "LLM.OUTPUT_VALIDATION_FAILED — schema repair did not yield valid JSON after 2 attempts.",
  },
];

// Per-framework synthetic content used when a fresh /generate is dispatched
// in dev mode. Keeps the "Phân tích" button useful without an LLM.
const MOCK_FRESH_CONTENT: Record<FrameworkCode, any> = {
  swot: MOCK_SWOT_CONTENT,
  fishbone: MOCK_FISHBONE_CONTENT,
  "6w": {
    who:     "Đội Sales miền Bắc + đối tác phân phối B2B.",
    what:    "Mất 3 khách hàng B2B lớn trong Q1, doanh thu kênh giảm 12%.",
    when:    "Quý 1/2026 (cao điểm tháng 2).",
    where:   "Tập trung Hà Nội + Hải Phòng.",
    why:     "Đối thủ Y giảm giá 8% kèm gói trả chậm 60 ngày.",
    how:     "Match giá trên hợp đồng năm + tăng dịch vụ hậu mãi (free training 4 buổi/quý).",
    summary: "Đề xuất họp Sales miền Bắc tuần tới + xin duyệt ngân sách khuyến mãi B2B 800tr/quý.",
  },
  "2h": {
    how: {
      approach: "Triển khai loyalty mới theo 3 giai đoạn — pilot 2 cửa hàng → mở rộng 10 → toàn chuỗi.",
      steps: [
        "Tuần 1-2: thiết kế chương trình điểm + tier với Marketing.",
        "Tuần 3-4: pilot tại 2 cửa hàng quận 1 + Bình Thạnh.",
        "Tuần 5-6: đo conversion + retention, tinh chỉnh tier.",
        "Tuần 7-8: mở rộng 10 cửa hàng tier-1.",
        "Tháng 3-6: rollout toàn chuỗi 45 cửa hàng.",
      ],
    },
    how_much: {
      estimate:    "≈ 1.500.000.000",
      unit:        "₫ chi phí năm đầu",
      confidence:  0.65,
      assumptions: [
        "Giả định 30% khách hiện tại tham gia.",
        "Chi phí phần thưởng = 4% doanh thu kênh.",
        "Không tính chi phí marketing launch (~200tr riêng).",
      ],
    },
    summary: "Có thể triển khai trong 2 quý — ROI hoà vốn sau 14 tháng nếu retention tăng 8%+.",
  },
};

const MOCK_NARRATIVES: Record<FrameworkCode, (c: any) => string> = {
  swot:     (c) => c?.summary ?? "",
  "6w":     (c) => c?.summary ?? "",
  "2h":     (c) => `${c?.how_much?.estimate ?? ""} ${c?.how_much?.unit ?? ""}`.trim(),
  fishbone: (c) => c?.root_cause_hypothesis ?? "",
};

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

export const frameworksHandlers = [
  // ── Catalogue ──────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/frameworks/templates`, async () => {
    await delay(40);
    return HttpResponse.json({ items: CATALOGUE });
  }),

  // ── List runs ──────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/frameworks`, async ({ request }) => {
    const url   = new URL(request.url);
    const limit = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") ?? 50)));
    await delay(60);
    return HttpResponse.json({
      items: MOCK_RUNS.slice(0, limit).map(({ content_json, ...rest }) => rest),
      next_cursor: null,
    });
  }),

  // ── Single run ─────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/frameworks/:id`, async ({ params }) => {
    const id = String(params.id);
    const row = MOCK_RUNS.find((r) => r.run_id === id);
    if (!row) return problem(404, "/docs/errors/framework-run-not-found", "Framework run not found", id);
    return HttpResponse.json(row);
  }),

  // ── Generate ───────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/frameworks/generate`, async ({ request }) => {
    const body = (await request.json()) as {
      framework_code:   string;
      question?:        string;
      source_ref?:      string | null;
      consent_external?: boolean;
    };

    if (!CATALOGUE.find((c) => c.code === body.framework_code)) {
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
        `unknown framework_code '${body.framework_code}' — allowed: ${CATALOGUE.map((c) => c.code).join(", ")}`);
    }
    const q = (body.question ?? "").trim();
    if (q.length < 3) {
      return problem(422, "/docs/errors/validation", "Validation error",
        "question must be at least 3 characters");
    }
    if (q.length > 2000) {
      return problem(422, "/docs/errors/validation", "Validation error",
        "question must be ≤ 2000 characters");
    }

    const code = body.framework_code as FrameworkCode;
    const newRun: MockRun = {
      run_id:           `fr_mock_${Date.now()}`,
      framework_code:   code,
      question:         q,
      source_ref:       body.source_ref ?? null,
      consent_external: !!body.consent_external,
      status:           "queued",
      narrative:        null,
      content_json:     null,
      created_at:       new Date().toISOString(),
      completed_at:     null,
      last_error:       null,
    };
    MOCK_RUNS.unshift(newRun);

    // Simulate worker — running after ~600ms, ready after ~3s.
    setTimeout(() => { newRun.status = "running"; }, 600);
    setTimeout(() => {
      const content = MOCK_FRESH_CONTENT[code];
      newRun.status       = "ready";
      newRun.narrative    = MOCK_NARRATIVES[code](content) || null;
      newRun.content_json = content;
      newRun.completed_at = new Date().toISOString();
    }, 3000);

    await delay(120);
    return HttpResponse.json({ run_id: newRun.run_id, status: "queued" }, { status: 202 });
  }),
];
