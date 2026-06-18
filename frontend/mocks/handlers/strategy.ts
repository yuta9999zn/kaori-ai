import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-040 Strategy Builder OKR — mirror BE shape from
// services/auth-service/.../EnterpriseOkrController.java. Lets the
// dev-mode /p2/strategy + /p2/strategy/okr pages render end-to-end
// without auth-service + Postgres in the loop.
//
// Status auto-recompute (lag = quarter elapsed - avg KR progress) is
// done client-side here too so Create/Update flows show realistic
// status badges without needing the BE round-trip.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

type ObjStatus = "on_track" | "at_risk" | "off_track";

interface MockKr {
  kr_id:         string;
  title:         string;
  unit:          string;
  target:        number;
  current_value: number;
  display_order: number;
}

interface MockObjective {
  objective_id:    string;
  quarter:         string;
  title:           string;
  owner_user_id:   string | null;
  status:          ObjStatus;
  created_by_user: string | null;
  created_at:      string;
  updated_at:      string;
  key_results:     MockKr[];
}

const days = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();

function uuid(): string {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return ((c === "x" ? r : (r & 0x3) | 0x8)).toString(16);
  });
}

// Simple quarter-elapsed computation matching BE OkrService.
function quarterElapsedFraction(quarter: string): number {
  const m = quarter.match(/^Q([1-4]) (\d{4})$/);
  if (!m) return 0;
  const q = Number(m[1]);
  const year = Number(m[2]);
  const startMonth = (q - 1) * 3;
  const start = new Date(year, startMonth, 1);
  const end   = new Date(year, startMonth + 3, 0);
  const today = new Date();
  if (today < start) return 0;
  if (today > end)   return 1;
  const total   = (end.getTime() - start.getTime()) / 86_400_000 + 1;
  const elapsed = (today.getTime() - start.getTime()) / 86_400_000 + 1;
  return elapsed / total;
}

function computeStatus(quarter: string, krs: MockKr[]): ObjStatus {
  if (krs.length === 0) return "on_track";
  const qElapsed = quarterElapsedFraction(quarter);
  const avg = krs.reduce((s, k) =>
    s + (k.target > 0 ? Math.min(1, Math.max(0, k.current_value / k.target)) : 0), 0) / krs.length;
  const lag = qElapsed - avg;
  if (lag <= 0.05) return "on_track";
  if (lag <= 0.15) return "at_risk";
  return "off_track";
}

let MOCK_OBJECTIVES: MockObjective[] = [
  {
    objective_id: "11111111-1111-1111-1111-111111111111",
    quarter:      "Q2 2026",
    title:        "Tăng doanh thu mảng SME lên 5 tỷ/tháng",
    owner_user_id: "minh-uuid-001",
    status:       "at_risk",
    created_by_user: "user-mock-001",
    created_at:   days(45),
    updated_at:   days(2),
    key_results: [
      { kr_id: uuid(), title: "Số khách SME mới ký HĐ",      unit: "khách", target: 60,        current_value: 28,        display_order: 0 },
      { kr_id: uuid(), title: "ARPU SME trung bình",         unit: "VNĐ",   target: 3_500_000, current_value: 2_800_000, display_order: 1 },
      { kr_id: uuid(), title: "Tỷ lệ giữ chân SME 90 ngày",  unit: "%",     target: 85,        current_value: 72,        display_order: 2 },
    ],
  },
  {
    objective_id: "22222222-2222-2222-2222-222222222222",
    quarter:      "Q2 2026",
    title:        "Triển khai Auto DB cho 3 khách hàng pilot",
    owner_user_id: "huy-uuid-002",
    status:       "off_track",
    created_by_user: "user-mock-001",
    created_at:   days(40),
    updated_at:   days(5),
    key_results: [
      { kr_id: uuid(), title: "Số khách pilot đã go-live",       unit: "khách", target: 3,  current_value: 1,  display_order: 0 },
      { kr_id: uuid(), title: "Schema accuracy đề xuất",         unit: "%",     target: 85, current_value: 78, display_order: 1 },
      { kr_id: uuid(), title: "Số form sinh tự động",            unit: "form",  target: 30, current_value: 12, display_order: 2 },
    ],
  },
  {
    objective_id: "33333333-3333-3333-3333-333333333333",
    quarter:      "Q2 2026",
    title:        "Hoàn thiện documentation pilot",
    owner_user_id: null,
    status:       "on_track",
    created_by_user: "user-mock-002",
    created_at:   days(15),
    updated_at:   days(1),
    key_results: [
      { kr_id: uuid(), title: "Số trang docs hoàn chỉnh",   unit: "trang", target: 80, current_value: 75, display_order: 0 },
      { kr_id: uuid(), title: "Số video walkthrough",       unit: "video", target: 6,  current_value: 5,  display_order: 1 },
    ],
  },
];

function recomputeAll() {
  MOCK_OBJECTIVES = MOCK_OBJECTIVES.map((o) => ({
    ...o,
    status: computeStatus(o.quarter, o.key_results),
  }));
}

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

function nowIso() { return new Date().toISOString(); }

export const strategyHandlers = [
  // ── Summary ────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/strategy/summary`, async ({ request }) => {
    recomputeAll();
    const url     = new URL(request.url);
    const quarter = url.searchParams.get("quarter");
    const matched = MOCK_OBJECTIVES.filter((o) => !quarter || o.quarter === quarter);
    const by_status: Record<ObjStatus, number> = { on_track: 0, at_risk: 0, off_track: 0 };
    for (const o of matched) by_status[o.status] += 1;
    await delay(60);
    return HttpResponse.json({
      data: { by_status, total: matched.length, quarter: quarter ?? "" },
    });
  }),

  // ── List objectives ─────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/strategy/okr`, async ({ request }) => {
    recomputeAll();
    const url     = new URL(request.url);
    const quarter = url.searchParams.get("quarter");
    const page    = Math.max(1, Number(url.searchParams.get("page") ?? 1));
    const limit   = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") ?? 20)));

    let filtered = [...MOCK_OBJECTIVES];
    if (quarter) filtered = filtered.filter((o) => o.quarter === quarter);
    filtered.sort((a, b) =>
      b.quarter.localeCompare(a.quarter)
      || b.status.localeCompare(a.status)
      || b.objective_id.localeCompare(a.objective_id),
    );

    const start = (page - 1) * limit;
    const items = filtered.slice(start, start + limit);
    await delay(70);
    return HttpResponse.json({ data: items, meta: { total: filtered.length, page, limit } });
  }),

  // ── Get one ─────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/strategy/okr/:objectiveId`, async ({ params }) => {
    recomputeAll();
    const id  = String(params.objectiveId);
    const obj = MOCK_OBJECTIVES.find((o) => o.objective_id === id);
    if (!obj) return problem(404, "/docs/errors/objective-not-found",
                              "Objective not found", `objective not found: ${id}`);
    await delay(50);
    return HttpResponse.json({ data: obj });
  }),

  // ── Create ─────────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/enterprises/strategy/okr`, async ({ request }) => {
    const body = await request.json() as Record<string, any>;
    if (!body?.title || String(body.title).trim() === "")
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "title is required");
    if (!body?.quarter || !/^Q[1-4] \d{4}$/.test(body.quarter))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     "quarter must match 'Q[1-4] YYYY'");
    const krs = (body.key_results ?? []) as Array<{
      title: string; unit?: string; target: number; current_value?: number;
    }>;
    if (krs.length === 0)
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     "at least one key result is required");
    for (const k of krs) {
      if (!k.title || String(k.title).trim() === "")
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
                       "kr title is required");
      if (typeof k.target !== "number" || k.target <= 0)
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
                       "kr target must be > 0");
    }

    const obj: MockObjective = {
      objective_id:    uuid(),
      quarter:         body.quarter,
      title:           String(body.title).trim(),
      owner_user_id:   body.owner_user_id ?? null,
      status:          "on_track",
      created_by_user: "user-mock-001",
      created_at:      nowIso(),
      updated_at:      nowIso(),
      key_results: krs.map((k, i) => ({
        kr_id:         uuid(),
        title:         String(k.title).trim(),
        unit:          k.unit ?? "",
        target:        k.target,
        current_value: k.current_value ?? 0,
        display_order: i,
      })),
    };
    obj.status = computeStatus(obj.quarter, obj.key_results);
    MOCK_OBJECTIVES = [obj, ...MOCK_OBJECTIVES];
    await delay(80);
    return HttpResponse.json({ data: obj }, { status: 201 });
  }),

  // ── Update objective ─────────────────────────────────────────────────────
  http.patch(`${BASE}/api/v1/enterprises/strategy/okr/:objectiveId`, async ({ params, request }) => {
    const id  = String(params.objectiveId);
    const idx = MOCK_OBJECTIVES.findIndex((o) => o.objective_id === id);
    if (idx < 0) return problem(404, "/docs/errors/objective-not-found",
                                  "Objective not found", `objective not found: ${id}`);

    const body = await request.json() as Record<string, any>;
    if (!body || Object.values(body).every((v) => v == null))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     "at least one field must be provided");
    if (body.quarter && !/^Q[1-4] \d{4}$/.test(body.quarter))
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
                     "quarter must match 'Q[1-4] YYYY'");

    const cur = MOCK_OBJECTIVES[idx];
    const updated: MockObjective = {
      ...cur,
      quarter:        body.quarter        ?? cur.quarter,
      title:          body.title          ?? cur.title,
      owner_user_id:  body.owner_user_id  ?? cur.owner_user_id,
      updated_at:     nowIso(),
      key_results:    body.key_results
                        ? (body.key_results as Array<any>).map((k: any, i: number) => ({
                            kr_id:         uuid(),
                            title:         String(k.title).trim(),
                            unit:          k.unit ?? "",
                            target:        k.target,
                            current_value: k.current_value ?? 0,
                            display_order: i,
                          }))
                        : cur.key_results,
    };
    updated.status = body.status ?? computeStatus(updated.quarter, updated.key_results);
    MOCK_OBJECTIVES[idx] = updated;
    await delay(80);
    return HttpResponse.json({ data: updated });
  }),

  // ── Update KR progress ───────────────────────────────────────────────────
  http.patch(
    `${BASE}/api/v1/enterprises/strategy/okr/:objectiveId/kr/:krId/progress`,
    async ({ params, request }) => {
      const id  = String(params.objectiveId);
      const krId = String(params.krId);
      const idx = MOCK_OBJECTIVES.findIndex((o) => o.objective_id === id);
      if (idx < 0) return problem(404, "/docs/errors/objective-not-found",
                                    "Objective not found", `objective not found: ${id}`);

      const body = await request.json() as { current_value?: number };
      if (typeof body?.current_value !== "number" || body.current_value < 0)
        return problem(400, "/docs/errors/invalid-request", "Invalid request",
                       "current_value must be ≥ 0");

      const obj = MOCK_OBJECTIVES[idx];
      const krIdx = obj.key_results.findIndex((k) => k.kr_id === krId);
      if (krIdx < 0) return problem(404, "/docs/errors/objective-not-found",
                                      "KR not found", `kr not found: ${krId}`);

      obj.key_results[krIdx].current_value = body.current_value;
      obj.status = computeStatus(obj.quarter, obj.key_results);
      obj.updated_at = nowIso();
      await delay(70);
      return HttpResponse.json({ data: obj });
    },
  ),

  // ── Soft delete ─────────────────────────────────────────────────────────
  http.delete(`${BASE}/api/v1/enterprises/strategy/okr/:objectiveId`, async ({ params }) => {
    const id  = String(params.objectiveId);
    const idx = MOCK_OBJECTIVES.findIndex((o) => o.objective_id === id);
    if (idx < 0) return problem(404, "/docs/errors/objective-not-found",
                                  "Objective not found", `objective not found: ${id}`);
    MOCK_OBJECTIVES.splice(idx, 1);
    await delay(60);
    return HttpResponse.json({ data: { objective_id: id, status: "deleted" } });
  }),
];
