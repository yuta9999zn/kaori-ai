import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-039 Risk Management — mirror BE shapes from
// services/auth-service/.../EnterpriseRiskController.java. Lets the
// dev-mode /p2/risks pages render end-to-end without auth-service +
// Postgres in the loop. Score + severity are computed client-side
// here to match the migration-033 trigger.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

type Severity = "low" | "medium" | "high" | "critical";
type Status   = "open" | "mitigating" | "closed";
type Category =
  | "operational" | "financial" | "regulatory"
  | "reputational" | "strategic" | "technical";

interface MockRisk {
  risk_id:             string;
  title:               string;
  description:         string | null;
  category:            Category;
  likelihood:          number;
  impact:              number;
  score:               number;
  severity:            Severity;
  status:              Status;
  mitigation_plan:     string | null;
  mitigation_progress: number;
  owner_user_id:       string | null;
  due_date:            string | null;
  source:              "manual" | "auto";
  created_by_user:     string | null;
  created_at:          string;
  updated_at:          string;
}

const ALLOWED_STATUS: Status[] = ["open", "mitigating", "closed"];
const ALLOWED_SEVERITY: Severity[] = ["low", "medium", "high", "critical"];
const ALLOWED_CATEGORY: Category[] = [
  "operational", "financial", "regulatory",
  "reputational", "strategic", "technical",
];

function severityFor(score: number): Severity {
  if (score >= 15) return "critical";
  if (score >=  9) return "high";
  if (score >=  5) return "medium";
  return "low";
}

const days = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();
const future = (d: number) =>
  new Date(Date.now() + d * 86_400_000).toISOString().slice(0, 10);

let MOCK_RISKS: MockRisk[] = [
  {
    risk_id: "11111111-1111-1111-1111-111111111111",
    title: "Phụ thuộc 1 nhà cung cấp Ollama GPU duy nhất",
    description: "Toàn bộ inference Qwen 2.5 chạy trên 1 instance Ollama. Nếu instance lỗi >2h, mọi pipeline mới bị block.",
    category: "technical",
    likelihood: 3, impact: 5, score: 15, severity: "critical",
    status: "open",
    mitigation_plan: "Triển khai instance phụ + HAProxy failover", mitigation_progress: 25,
    owner_user_id: "huy-uuid-001", due_date: future(20),
    source: "manual", created_by_user: "user-mock-001",
    created_at: days(15), updated_at: days(2),
  },
  {
    risk_id: "22222222-2222-2222-2222-222222222222",
    title: "Compliance GDPR cho data EU customer",
    description: "Khách EU lưu trên S3 chung region với khách VN — vi phạm data residency.",
    category: "regulatory",
    likelihood: 4, impact: 5, score: 20, severity: "critical",
    status: "mitigating",
    mitigation_plan: "Tách bucket region eu-central-1 + DPA", mitigation_progress: 60,
    owner_user_id: "lan-uuid-002", due_date: future(28),
    source: "manual", created_by_user: "user-mock-001",
    created_at: days(20), updated_at: days(1),
  },
  {
    risk_id: "33333333-3333-3333-3333-333333333333",
    title: "Churn key-account >5 tỷ/năm",
    description: "ACME Corp đã 90 ngày không pipeline — CSM chưa contact.",
    category: "financial",
    likelihood: 2, impact: 5, score: 10, severity: "high",
    status: "mitigating",
    mitigation_plan: "QBR + giảm giá 15% Q3", mitigation_progress: 40,
    owner_user_id: "minh-uuid-003", due_date: future(11),
    source: "manual", created_by_user: "user-mock-002",
    created_at: days(30), updated_at: days(3),
  },
  {
    risk_id: "44444444-4444-4444-4444-444444444444",
    title: "Nhân sự lead ML rời công ty",
    description: "Lead ML offer outside Q3 — chưa có successor.",
    category: "operational",
    likelihood: 2, impact: 4, score: 8, severity: "medium",
    status: "open",
    mitigation_plan: null, mitigation_progress: 0,
    owner_user_id: null, due_date: null,
    source: "manual", created_by_user: "user-mock-001",
    created_at: days(25), updated_at: days(25),
  },
  {
    risk_id: "55555555-5555-5555-5555-555555555555",
    title: "Lộ insight nội bộ qua AI ngoài (PII leak)",
    description: "Một analyst paste raw query có PII vào ChatGPT external — chưa có policy enforce.",
    category: "reputational",
    likelihood: 2, impact: 5, score: 10, severity: "high",
    status: "mitigating",
    mitigation_plan: "Đẩy K-5 PII redaction strict + training", mitigation_progress: 70,
    owner_user_id: "lan-uuid-002", due_date: future(6),
    source: "manual", created_by_user: "user-mock-001",
    created_at: days(18), updated_at: days(4),
  },
  {
    risk_id: "66666666-6666-6666-6666-666666666666",
    title: "Đối thủ ra sản phẩm AI giá rẻ",
    description: "Startup đối thủ launch tier free 500 customer — có thể hút SMB pipeline khỏi Kaori.",
    category: "strategic",
    likelihood: 4, impact: 3, score: 12, severity: "high",
    status: "open",
    mitigation_plan: "Định vị lại ENT BASIC + ROI demo", mitigation_progress: 10,
    owner_user_id: "minh-uuid-003", due_date: future(60),
    source: "manual", created_by_user: "user-mock-002",
    created_at: days(10), updated_at: days(10),
  },
  {
    risk_id: "77777777-7777-7777-7777-777777777777",
    title: "Dataset Bronze hỏng do disk full",
    description: "Bronze MinIO chỉ còn 12% disk — pipeline lớn next quarter có nguy cơ fail.",
    category: "technical",
    likelihood: 2, impact: 3, score: 6, severity: "medium",
    status: "mitigating",
    mitigation_plan: "Tăng SSD 2TB + lifecycle rule retention 90 ngày", mitigation_progress: 80,
    owner_user_id: "huy-uuid-001", due_date: future(2),
    source: "manual", created_by_user: "user-mock-001",
    created_at: days(7), updated_at: days(1),
  },
  {
    risk_id: "88888888-8888-8888-8888-888888888888",
    title: "Quy định thuế mới ảnh hưởng pricing",
    description: "Nghị định 132 áp dụng từ Q3 — pricing model cần điều chỉnh tax-included vs net.",
    category: "regulatory",
    likelihood: 2, impact: 2, score: 4, severity: "low",
    status: "open",
    mitigation_plan: null, mitigation_progress: 0,
    owner_user_id: "lan-uuid-002", due_date: future(90),
    source: "manual", created_by_user: "user-mock-002",
    created_at: days(12), updated_at: days(12),
  },
];

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

// Single source of severity rollup — matches BE backfill (always 4 buckets, 0 if missing).
function rollup(): { critical: number; high: number; medium: number; low: number } {
  const out = { critical: 0, high: 0, medium: 0, low: 0 };
  for (const r of MOCK_RISKS) {
    if (r.status === "closed") continue;
    out[r.severity] += 1;
  }
  return out;
}

function nowIso() { return new Date().toISOString(); }

function uuid(): string {
  // Pure-JS UUID v4 — crypto.randomUUID may not be available in jsdom
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export const risksHandlers = [
  // ── List ────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/risks`, async ({ request }) => {
    const url      = new URL(request.url);
    const page     = Math.max(1, Number(url.searchParams.get("page") ?? 1));
    const limit    = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") ?? 20)));
    const status   = url.searchParams.get("status");
    const severity = url.searchParams.get("severity");
    const category = url.searchParams.get("category");

    if (status   && !ALLOWED_STATUS.includes(status as Status))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     `status must be one of [open, mitigating, closed]`);
    if (severity && !ALLOWED_SEVERITY.includes(severity as Severity))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     `severity must be one of [low, medium, high, critical]`);
    if (category && !ALLOWED_CATEGORY.includes(category as Category))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     `category must be one of [operational, financial, regulatory, reputational, strategic, technical]`);

    let filtered = [...MOCK_RISKS];
    if (status)   filtered = filtered.filter((r) => r.status === status);
    if (severity) filtered = filtered.filter((r) => r.severity === severity);
    if (category) filtered = filtered.filter((r) => r.category === category);
    // BE order: score DESC, risk_id DESC
    filtered.sort((a, b) => b.score - a.score || b.risk_id.localeCompare(a.risk_id));

    const total = filtered.length;
    const start = (page - 1) * limit;
    const items = filtered.slice(start, start + limit);

    await delay(60);
    return HttpResponse.json({
      data: items,
      meta: { total, page, limit },
    });
  }),

  // ── Severity rollup ─────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/risks/severity-rollup`, async () => {
    const by_severity = rollup();
    const open_total  = by_severity.critical + by_severity.high
                      + by_severity.medium   + by_severity.low;
    await delay(50);
    return HttpResponse.json({
      data: { by_severity, open_total },
    });
  }),

  // ── Get one ─────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/risks/:riskId`, async ({ params }) => {
    const id = String(params.riskId);
    const row = MOCK_RISKS.find((r) => r.risk_id === id);
    if (!row) return problem(404, "/docs/errors/risk-item-not-found",
                              "Risk item not found", `risk item not found: ${id}`);
    await delay(40);
    return HttpResponse.json({ data: row });
  }),

  // ── Create (MANAGER only — MSW skips role check; assume caller is MANAGER) ─
  http.post(`${BASE}/api/v1/enterprises/risks`, async ({ request }) => {
    const body = await request.json() as Record<string, any>;
    if (!body || typeof body.title !== "string" || body.title.trim() === "")
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "title is required");
    if (body.title.length > 200)
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "title must be ≤ 200 characters");
    if (typeof body.likelihood !== "number" || body.likelihood < 1 || body.likelihood > 5)
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "likelihood must be 1..5");
    if (typeof body.impact !== "number" || body.impact < 1 || body.impact > 5)
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "impact must be 1..5");
    if (body.status && !ALLOWED_STATUS.includes(body.status))
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "status invalid");
    if (body.category && !ALLOWED_CATEGORY.includes(body.category))
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "category invalid");
    if (body.mitigation_progress != null
        && (body.mitigation_progress < 0 || body.mitigation_progress > 100))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     "mitigation_progress must be 0..100");

    const score = body.likelihood * body.impact;
    const row: MockRisk = {
      risk_id:             uuid(),
      title:               body.title.trim(),
      description:         body.description ?? null,
      category:            (body.category ?? "operational") as Category,
      likelihood:          body.likelihood,
      impact:              body.impact,
      score,
      severity:            severityFor(score),
      status:              (body.status ?? "open") as Status,
      mitigation_plan:     body.mitigation_plan ?? null,
      mitigation_progress: body.mitigation_progress ?? 0,
      owner_user_id:       body.owner_user_id ?? null,
      due_date:            body.due_date ?? null,
      source:              "manual",
      created_by_user:     "user-mock-001",
      created_at:          nowIso(),
      updated_at:          nowIso(),
    };
    MOCK_RISKS = [row, ...MOCK_RISKS];
    await delay(80);
    return HttpResponse.json({ data: row }, { status: 201 });
  }),

  // ── Update ──────────────────────────────────────────────────────────────
  http.patch(`${BASE}/api/v1/enterprises/risks/:riskId`, async ({ params, request }) => {
    const id  = String(params.riskId);
    const idx = MOCK_RISKS.findIndex((r) => r.risk_id === id);
    if (idx < 0) return problem(404, "/docs/errors/risk-item-not-found",
                                  "Risk item not found", `risk item not found: ${id}`);
    const body = await request.json() as Record<string, any>;
    if (!body || Object.values(body).every((v) => v == null))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     "at least one field must be provided");
    if (body.title != null && body.title.trim() === "")
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "title is required");
    if (body.likelihood != null && (body.likelihood < 1 || body.likelihood > 5))
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "likelihood must be 1..5");
    if (body.impact != null && (body.impact < 1 || body.impact > 5))
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "impact must be 1..5");
    if (body.status && !ALLOWED_STATUS.includes(body.status))
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "status invalid");
    if (body.category && !ALLOWED_CATEGORY.includes(body.category))
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "category invalid");
    if (body.mitigation_progress != null
        && (body.mitigation_progress < 0 || body.mitigation_progress > 100))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     "mitigation_progress must be 0..100");

    const cur = MOCK_RISKS[idx];
    const lik = body.likelihood ?? cur.likelihood;
    const imp = body.impact     ?? cur.impact;
    const score = lik * imp;
    const updated: MockRisk = {
      ...cur,
      title:               body.title             ?? cur.title,
      description:         body.description       ?? cur.description,
      category:            body.category          ?? cur.category,
      likelihood:          lik,
      impact:              imp,
      score,
      severity:            severityFor(score),
      status:              body.status            ?? cur.status,
      mitigation_plan:     body.mitigation_plan   ?? cur.mitigation_plan,
      mitigation_progress: body.mitigation_progress ?? cur.mitigation_progress,
      owner_user_id:       body.owner_user_id     ?? cur.owner_user_id,
      due_date:            body.due_date          ?? cur.due_date,
      updated_at:          nowIso(),
    };
    MOCK_RISKS[idx] = updated;
    await delay(80);
    return HttpResponse.json({ data: updated });
  }),

  // ── Soft delete ─────────────────────────────────────────────────────────
  http.delete(`${BASE}/api/v1/enterprises/risks/:riskId`, async ({ params }) => {
    const id  = String(params.riskId);
    const idx = MOCK_RISKS.findIndex((r) => r.risk_id === id);
    if (idx < 0) return problem(404, "/docs/errors/risk-item-not-found",
                                  "Risk item not found", `risk item not found: ${id}`);
    MOCK_RISKS.splice(idx, 1);
    await delay(60);
    return HttpResponse.json({ data: { risk_id: id, status: "deleted" } });
  }),
];
