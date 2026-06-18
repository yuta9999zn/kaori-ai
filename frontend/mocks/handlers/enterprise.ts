import { http, HttpResponse, delay } from "msw";

const BASE = "http://localhost:8080";

// Shape mirrors auth-service EnterpriseSettingsController.toJson (F-016).
// FE settings page reads `consent_external_ai` + the LocalePicker reads
// `locale`; the rest are forward-compatible fields the BE now exposes.
const MOCK_SETTINGS = {
  enterprise_id: "11111111-1111-1111-1111-111111111111",
  enterprise_name: "Công ty TNHH Demo Kaori",
  locale: "vi",
  theme: "light",
  consent_external_ai: false,
  notification_email: true,
  branding_logo_url: null,
  branding_accent_color: null,
  created_at: "2026-04-01T00:00:00Z",
  updated_at: "2026-04-27T00:00:00Z",
};

const MOCK_USERS = [
  { id: "user_1", email: "admin@kaori.io",      full_name: "Nguyễn Minh Khải",  role: "MANAGER",  is_active: true,  created_at: "2025-01-10T08:00:00Z" },
  { id: "user_2", email: "analyst1@kaori.io",   full_name: "Trần Thị Lan",       role: "ANALYST",  is_active: true,  created_at: "2025-02-14T09:30:00Z" },
  { id: "user_3", email: "ops@kaori.io",        full_name: "Lê Văn Đức",         role: "OPERATOR", is_active: true,  created_at: "2025-03-01T10:00:00Z" },
  { id: "user_4", email: "viewer@kaori.io",     full_name: "Phạm Thị Hoa",       role: "VIEWER",   is_active: true,  created_at: "2025-03-15T11:00:00Z" },
  { id: "user_5", email: "analyst2@kaori.io",   full_name: "Hoàng Văn Nam",      role: "ANALYST",  is_active: false, created_at: "2025-04-01T08:45:00Z" },
];

export const enterpriseHandlers = [
  http.get(`${BASE}/api/v1/enterprises/me/settings`, async () => {
    await delay(200);
    return HttpResponse.json({ data: MOCK_SETTINGS });
  }),

  http.patch(`${BASE}/api/v1/enterprises/me/settings`, async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    await delay(300);
    Object.assign(MOCK_SETTINGS, body, { updated_at: new Date().toISOString() });
    return HttpResponse.json({ data: MOCK_SETTINGS });
  }),

  // ── F-015 list (page-based, role/status filter, BE envelope) ──────────────
  http.get(`${BASE}/api/v1/enterprises/users`, async ({ request }) => {
    const url   = new URL(request.url);
    const page  = Number(url.searchParams.get("page")  ?? 1);
    const limit = Number(url.searchParams.get("limit") ?? 20);
    const role  = url.searchParams.get("role");
    const stat  = url.searchParams.get("status");

    let filtered = MOCK_USERS;
    if (role) filtered = filtered.filter((u) => u.role === role);
    if (stat) filtered = filtered.filter((u) =>
      stat === "active" ? u.is_active : !u.is_active);

    await delay(220);
    const start = (page - 1) * limit;
    return HttpResponse.json({
      data: filtered.slice(start, start + limit).map((u) => ({
        id:        u.id,
        user_id:   u.id,
        email:     u.email,
        full_name: u.full_name,
        role:      u.role,
        status:    u.is_active ? "active" : "inactive",
        is_active: u.is_active,
        created_at: u.created_at,
      })),
      meta: { total: filtered.length, page, limit },
    });
  }),

  // ── F-015 invite ──────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/enterprises/users`, async ({ request }) => {
    const body = await request.json() as { email: string; full_name?: string; role: string };
    await delay(280);
    const newUser = {
      id:        `user_${MOCK_USERS.length + 1}`,
      email:     body.email,
      full_name: body.full_name ?? "",
      role:      body.role,
      is_active: true,
      created_at: new Date().toISOString(),
    };
    MOCK_USERS.push(newUser as typeof MOCK_USERS[number]);
    return HttpResponse.json(
      { data: { ...newUser, status: "active", user_id: newUser.id } },
      { status: 201 },
    );
  }),

  // ── F-015 update role / status ────────────────────────────────────────────
  http.patch(`${BASE}/api/v1/enterprises/users/:userId`, async ({ params, request }) => {
    const body = await request.json() as { role?: string; status?: string };
    const u = MOCK_USERS.find((x) => x.id === params.userId);
    if (!u) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/user-not-found",
        title: "User not found",
        status: 404,
        detail: `${params.userId}`,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    if (body.role)   u.role = body.role as typeof u.role;
    if (body.status) u.is_active = body.status === "active";
    await delay(180);
    return HttpResponse.json({ data: {
      id: u.id, user_id: u.id, email: u.email, full_name: u.full_name,
      role: u.role, is_active: u.is_active,
      status: u.is_active ? "active" : "inactive",
      created_at: u.created_at,
    } });
  }),

  // ── F-015 soft delete ─────────────────────────────────────────────────────
  http.delete(`${BASE}/api/v1/enterprises/users/:userId`, async ({ params }) => {
    const idx = MOCK_USERS.findIndex((x) => x.id === params.userId);
    if (idx === -1) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/user-not-found",
        title: "User not found",
        status: 404,
        detail: `${params.userId}`,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    MOCK_USERS.splice(idx, 1);
    await delay(180);
    return HttpResponse.json({ data: { user_id: params.userId, status: "deleted" } });
  }),
];
