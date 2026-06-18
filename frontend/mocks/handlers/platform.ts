import { http, HttpResponse, delay } from "msw";

const BASE = "http://localhost:8080";

// Shape mirrors auth-service WorkspaceController.toJson (F-008): cursor
// pagination + the `workspace_id`/`plan_code`/`industry`/`updated_at` fields
// the FE table reads. Status enum matches the BE CHECK constraint
// (active|inactive|suspended); MSW-only "trial" tile flipped to "active".
// Olist Store — pilot UAT seed (mirrors scripts/seed-pilot-olist.py).
// Same UUID + name as the Postgres seed so the two paths converge:
// MSW dev mode renders this row immediately; full-stack mode (BE +
// disabled MSW) reads it from the live Postgres seed.
export const OLIST_WORKSPACE_ID = "00000000-0000-0000-0001-000000011577";
export const OLIST_ENTERPRISE_ID = "00000000-0000-0000-0002-000000011577";
export const OLIST_USER_ID = "00000000-0000-0000-0003-000000011577";

const MOCK_WORKSPACES = [
  { workspace_id: OLIST_WORKSPACE_ID,                      name: "Olist Store",                    plan_code: "BUSINESS",   industry: "E-commerce / Marketplace", status: "active",    created_at: "2026-05-04T16:00:00Z", updated_at: "2026-05-04T16:00:00Z" },
  { workspace_id: "11111111-1111-1111-1111-100000000001", name: "Công ty TNHH Demo Kaori",      plan_code: "STARTER",    industry: "Retail",     status: "active",    created_at: "2025-01-10T08:00:00Z", updated_at: "2025-01-10T08:00:00Z" },
  { workspace_id: "11111111-1111-1111-1111-100000000002", name: "Tập đoàn Thương Mại ABC",       plan_code: "BUSINESS",   industry: "Wholesale",  status: "active",    created_at: "2025-02-01T09:00:00Z", updated_at: "2025-02-01T09:00:00Z" },
  { workspace_id: "11111111-1111-1111-1111-100000000003", name: "Chuỗi Bán Lẻ XYZ Việt Nam",    plan_code: "ENTERPRISE", industry: "Retail",     status: "active",    created_at: "2025-02-15T10:00:00Z", updated_at: "2025-02-15T10:00:00Z" },
  { workspace_id: "11111111-1111-1111-1111-100000000004", name: "Startup FinTech MNO",           plan_code: "STARTER",    industry: "Fintech",    status: "active",    created_at: "2025-04-20T08:00:00Z", updated_at: "2025-04-20T08:00:00Z" },
  { workspace_id: "11111111-1111-1111-1111-100000000005", name: "Công ty Logistics PQR",         plan_code: "BUSINESS",   industry: "Logistics",  status: "suspended", created_at: "2025-03-10T11:00:00Z", updated_at: "2025-03-10T11:00:00Z" },
];

const MOCK_PLATFORM_ADMINS = [
  { id: "padm_1", email: "superadmin@kaori.io",  full_name: "Kaori System Admin", role: "SUPER_ADMIN", is_active: true,  created_at: "2025-01-01T00:00:00Z" },
  { id: "padm_2", email: "support@kaori.io",     full_name: "Hỗ trợ kỹ thuật",   role: "SUPPORT",     is_active: true,  created_at: "2025-01-15T08:00:00Z" },
  { id: "padm_3", email: "admin2@kaori.io",      full_name: "Quản trị viên 2",    role: "ADMIN",       is_active: true,  created_at: "2025-02-01T09:00:00Z" },
];

interface MockKey {
  key_id:     string;
  workspace_id: string;
  label:      string;
  status:     'active' | 'revoked';
  created_at: string;
  revoked_at: string | null;
}

const MOCK_KEYS: MockKey[] = [
  { key_id: 'k_seed_1', workspace_id: '11111111-1111-1111-1111-100000000001', label: 'ci-runner',   status: 'active',  created_at: '2025-03-01T08:00:00Z', revoked_at: null },
  { key_id: 'k_seed_2', workspace_id: '11111111-1111-1111-1111-100000000001', label: 'stg-deploy',  status: 'active',  created_at: '2025-03-05T10:30:00Z', revoked_at: null },
  { key_id: 'k_seed_3', workspace_id: '11111111-1111-1111-1111-100000000001', label: 'old-dev-key', status: 'revoked', created_at: '2025-01-15T09:00:00Z', revoked_at: '2025-02-20T14:00:00Z' },
];

function genRawKey(): string {
  const ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  const groups = Array.from({ length: 4 }, () =>
    Array.from({ length: 8 }, () =>
      ALPHABET[Math.floor(Math.random() * ALPHABET.length)],
    ).join(''),
  );
  return `KAORI-${groups.join('-')}`;
}

const MOCK_PLATFORM_STATS = {
  total_workspaces:  6,
  active_workspaces: 4,
  total_users:       59,
  total_runs:        490,
  runs_today:        14,
  ollama_online:     true,
  kafka_lag:         0,
  p95_latency_ms:    420,
};

export const platformHandlers = [
  // F-008 — cursor-paginated, envelope { data, meta:{cursor,total} }.
  // Cursor is a stringified offset (good enough for MSW mock).
  http.get(`${BASE}/api/v1/platform/workspaces`, async ({ request }) => {
    const url    = new URL(request.url);
    const limit  = Number(url.searchParams.get("limit") ?? 20);
    const cursor = url.searchParams.get("cursor");
    await delay(250);
    const start  = cursor ? Number(cursor) : 0;
    const slice  = MOCK_WORKSPACES.slice(start, start + limit);
    const next   = start + limit < MOCK_WORKSPACES.length ? String(start + limit) : null;
    return HttpResponse.json({
      data: slice,
      meta: { cursor: next, total: MOCK_WORKSPACES.length },
    });
  }),

  http.post(`${BASE}/api/v1/platform/workspaces`, async ({ request }) => {
    const body = await request.json() as { name: string; plan_code?: string; plan?: string; industry?: string };
    await delay(400);
    const now = new Date().toISOString();
    const ws = {
      workspace_id: `11111111-1111-1111-1111-${String(Date.now()).padStart(12, "0")}`,
      name:         body.name,
      plan_code:    body.plan_code ?? body.plan ?? "STARTER",
      industry:     body.industry ?? "Other",
      status:       "active",
      created_at:   now,
      updated_at:   now,
    };
    MOCK_WORKSPACES.push(ws);
    return HttpResponse.json({ data: ws }, { status: 201 });
  }),

  // F-008 — workspace detail / update / soft-delete
  http.get(`${BASE}/api/v1/platform/workspaces/:id`, async ({ params }) => {
    await delay(150);
    const ws = MOCK_WORKSPACES.find((w) => w.workspace_id === params.id);
    if (!ws) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/workspace-not-found", title: "Workspace not found",
        status: 404, detail: String(params.id),
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    return HttpResponse.json({ data: ws });
  }),

  http.patch(`${BASE}/api/v1/platform/workspaces/:id`, async ({ params, request }) => {
    const body = await request.json() as { name?: string; plan_code?: string; status?: string };
    const ws = MOCK_WORKSPACES.find((w) => w.workspace_id === params.id);
    if (!ws) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/workspace-not-found", title: "Workspace not found",
        status: 404, detail: String(params.id),
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    if (body.name)      ws.name = body.name;
    if (body.plan_code) ws.plan_code = body.plan_code;
    if (body.status)    ws.status = body.status;
    ws.updated_at = new Date().toISOString();
    await delay(180);
    return HttpResponse.json({ data: ws });
  }),

  http.delete(`${BASE}/api/v1/platform/workspaces/:id`, async ({ params }) => {
    const ws = MOCK_WORKSPACES.find((w) => w.workspace_id === params.id);
    if (!ws) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/workspace-not-found", title: "Workspace not found",
        status: 404, detail: String(params.id),
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    ws.status = "inactive";
    ws.updated_at = new Date().toISOString();
    await delay(180);
    return HttpResponse.json({ data: { workspace_id: ws.workspace_id, status: ws.status } });
  }),

  // F-008 — members nested CRUD
  http.get(`${BASE}/api/v1/platform/workspaces/:id/members`, async ({ params }) => {
    await delay(180);
    const wsId = String(params.id);

    // Olist Store seed — single MANAGER cs@olist.local mirrors the
    // Postgres seed.
    if (wsId === OLIST_WORKSPACE_ID) {
      return HttpResponse.json({
        data: [
          { user_id: OLIST_USER_ID, email: "cs@olist.local", full_name: "Olist Customer Success",
            role: "MANAGER", status: "active",
            last_login_at: "2026-05-04T10:00:00Z", created_at: "2026-05-04T16:00:00Z" },
        ],
      });
    }

    const seed = wsId.slice(-1);  // deterministic per workspace
    const members = [
      { user_id: `${wsId}-u1`, email: `manager-${seed}@kaori.io`,  full_name: `Quản lý ${seed}`,    role: "MANAGER",  status: "active", last_login_at: "2026-04-25T08:00:00Z", created_at: "2025-01-15T08:00:00Z" },
      { user_id: `${wsId}-u2`, email: `analyst-${seed}@kaori.io`,  full_name: `Phân tích ${seed}`,  role: "ANALYST",  status: "active", last_login_at: "2026-04-26T10:00:00Z", created_at: "2025-02-10T08:00:00Z" },
      { user_id: `${wsId}-u3`, email: `viewer-${seed}@kaori.io`,   full_name: `Xem ${seed}`,        role: "VIEWER",   status: "active", last_login_at: null,                     created_at: "2025-03-05T08:00:00Z" },
    ];
    return HttpResponse.json({ data: members });
  }),

  http.post(`${BASE}/api/v1/platform/workspaces/:id/members`, async ({ params, request }) => {
    const body = await request.json() as { email: string; role: string };
    await delay(220);
    return HttpResponse.json({
      data: {
        user_id:       `${params.id}-${Date.now()}`,
        email:         body.email,
        full_name:     null,
        role:          body.role,
        status:        "pending",
        last_login_at: null,
        created_at:    new Date().toISOString(),
      },
    }, { status: 201 });
  }),

  http.patch(`${BASE}/api/v1/platform/workspaces/:id/members/:userId`, async ({ params, request }) => {
    const body = await request.json() as { role: string };
    await delay(180);
    return HttpResponse.json({
      data: {
        user_id:       String(params.userId),
        email:         "stub@kaori.io",
        full_name:     "Stub",
        role:          body.role,
        status:        "active",
        last_login_at: null,
        created_at:    "2025-01-01T00:00:00Z",
      },
    });
  }),

  http.delete(`${BASE}/api/v1/platform/workspaces/:id/members/:userId`, async ({ params }) => {
    await delay(150);
    return HttpResponse.json({ data: { user_id: String(params.userId) } });
  }),

  // F-008 / F-011 — workspace billing summary
  http.get(`${BASE}/api/v1/platform/workspaces/:id/billing`, async ({ params }) => {
    await delay(180);
    const wsId = String(params.id);
    const b = MOCK_BILLING.find((x) => x.workspace_id === wsId);
    if (!b) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/workspace-not-found", title: "Workspace not found",
        status: 404, detail: wsId,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    const status   = classify(b.unique_customers, b.quota, b.overage_units);
    const overage  = b.overage_units * 1000; // mock overage rate
    return HttpResponse.json({
      data: {
        workspace_id:        b.workspace_id,
        plan_code:           b.plan_code,
        billing_month:       currentMonthYM(),
        unique_customers:    b.unique_customers,
        quota:               b.quota,
        overage_units:       b.overage_units,
        base_amount_vnd:     b.base_amount_vnd,
        overage_amount_vnd:  overage,
        total_amount_vnd:    b.base_amount_vnd + overage,
        quota_warn_at_pct:   80,
        status,
        next_invoice_date:   nextInvoiceDateISO(),
      },
    });
  }),

  // F-008 — audit log (cursor-paginated)
  http.get(`${BASE}/api/v1/platform/workspaces/:id/audit`, async ({ params, request }) => {
    const url    = new URL(request.url);
    const limit  = Number(url.searchParams.get("limit") ?? 50);
    const cursor = url.searchParams.get("cursor");
    await delay(180);
    const wsId = String(params.id);
    const seed = wsId.slice(-3);
    const allEvents = Array.from({ length: 12 }, (_, i) => ({
      event_id:    `evt-${seed}-${String(i).padStart(3, "0")}`,
      event_type:  ["workspace.updated","member.invited","member.role_changed","key.generated","key.revoked","billing.recalculated"][i % 6],
      actor_email: i % 4 === 0 ? null : "admin@kaori.io",
      actor_role:  i % 4 === 0 ? null : "ADMIN",
      resource:    `member-${seed}-${i}`,
      detail:      `mock event #${i}`,
      ip_address:  i % 4 === 0 ? null : "203.0.113.45",
      created_at:  new Date(Date.now() - i * 6 * 60 * 60 * 1000).toISOString(),
    }));
    const start = cursor ? Number(cursor) : 0;
    const slice = allEvents.slice(start, start + limit);
    const next  = start + limit < allEvents.length ? String(start + limit) : null;
    return HttpResponse.json({
      data: slice,
      meta: { cursor: next, total: allEvents.length },
    });
  }),

  http.get(`${BASE}/api/v1/platform/stats`, async () => {
    await delay(200);
    return HttpResponse.json({ data: MOCK_PLATFORM_STATS });
  }),

  http.get(`${BASE}/api/v1/platform/admins`, async () => {
    await delay(200);
    return HttpResponse.json({ data: MOCK_PLATFORM_ADMINS });
  }),

  // ───────── Workspace API keys (F-009) ─────────
  http.get(`${BASE}/api/v1/platform/workspaces/:id/keys`, async ({ params }) => {
    await delay(180);
    const wsId = String(params.id);
    const items = MOCK_KEYS
      .filter((k) => k.workspace_id === wsId)
      .map(({ workspace_id: _w, ...rest }) => rest);
    return HttpResponse.json({ data: items });
  }),

  http.post(`${BASE}/api/v1/platform/workspaces/:id/keys`, async ({ request, params }) => {
    const wsId = String(params.id);
    const body = (await request.json().catch(() => ({}))) as { label?: string };
    await delay(350);
    const now = new Date().toISOString();
    const created: MockKey = {
      key_id: `k_${Date.now()}`,
      workspace_id: wsId,
      label: body.label?.trim() || '',
      status: 'active',
      created_at: now,
      revoked_at: null,
    };
    MOCK_KEYS.unshift(created);
    const { workspace_id: _w, ...rest } = created;
    return HttpResponse.json(
      {
        data: { ...rest, raw_key: genRawKey() },
        meta: { warning: 'Store this key immediately. It will not be shown again.' },
      },
      { status: 201 },
    );
  }),

  http.delete(`${BASE}/api/v1/platform/workspaces/:id/keys/:keyId`, async ({ params }) => {
    const wsId  = String(params.id);
    const keyId = String(params.keyId);
    await delay(220);
    const target = MOCK_KEYS.find(
      (k) => k.key_id === keyId && k.workspace_id === wsId && k.status === 'active',
    );
    if (!target) {
      return HttpResponse.json(
        { type: '/docs/errors/key-not-found', title: 'Key not found', status: 404, detail: keyId },
        { status: 404 },
      );
    }
    target.status     = 'revoked';
    target.revoked_at = new Date().toISOString();
    return HttpResponse.json({
      data: { key_id: target.key_id, status: 'revoked', revoked_at: target.revoked_at },
    });
  }),

  // ───────── Platform billing (F-011) ─────────
  ...buildBillingHandlers(),

  // ───────── Platform security (Module 3 — MFA + sessions) ─────────
  ...buildSecurityHandlers(),
];

// ─────────────────────────────────────────────────────────────────────────
// Billing fixtures + handlers (F-011)
// ─────────────────────────────────────────────────────────────────────────
interface BillingFixture {
  enterprise_id:    string;
  enterprise_name:  string;
  workspace_id:     string;
  plan_code:        string;
  unique_customers: number;
  quota:            number;
  overage_units:    number;
  base_amount_vnd:  number;
}
const PLAN_PRICE: Record<string, number> = {
  TRIAL: 0, STARTER: 490_000, BUSINESS: 1_490_000, ENTERPRISE: 4_990_000,
};
const MOCK_BILLING: BillingFixture[] = [
  { enterprise_id: '11111111-1111-1111-1111-100000000001', enterprise_name: 'Công ty TNHH Demo Kaori', workspace_id: '11111111-1111-1111-1111-100000000001', plan_code: 'STARTER',    unique_customers:   80, quota:   500, overage_units: 0, base_amount_vnd: PLAN_PRICE.STARTER    },
  { enterprise_id: '11111111-1111-1111-1111-100000000002', enterprise_name: 'Tập đoàn Thương Mại ABC',  workspace_id: '11111111-1111-1111-1111-100000000002', plan_code: 'BUSINESS',   unique_customers: 1700, quota:  2000, overage_units: 0, base_amount_vnd: PLAN_PRICE.BUSINESS   },
  { enterprise_id: '11111111-1111-1111-1111-100000000003', enterprise_name: 'Chuỗi Bán Lẻ XYZ Việt Nam',workspace_id: '11111111-1111-1111-1111-100000000003', plan_code: 'ENTERPRISE', unique_customers: 9700, quota: 10000, overage_units: 0, base_amount_vnd: PLAN_PRICE.ENTERPRISE },
  { enterprise_id: '11111111-1111-1111-1111-100000000004', enterprise_name: 'Startup FinTech MNO',      workspace_id: '11111111-1111-1111-1111-100000000004', plan_code: 'STARTER',    unique_customers:   12, quota:   500, overage_units: 0, base_amount_vnd: PLAN_PRICE.STARTER    },
  { enterprise_id: '11111111-1111-1111-1111-100000000005', enterprise_name: 'Công ty Logistics PQR',    workspace_id: '11111111-1111-1111-1111-100000000005', plan_code: 'BUSINESS',   unique_customers: 2050, quota:  2000, overage_units: 50, base_amount_vnd: PLAN_PRICE.BUSINESS   },
];

function classify(used: number, quota: number, overage: number): 'normal' | 'warn' | 'critical' | 'overage' {
  if (overage > 0)  return 'overage';
  if (quota <= 0)   return 'normal';
  const pct = Math.round((used * 100) / quota);
  if (pct >= 95) return 'critical';
  if (pct >= 80) return 'warn';
  return 'normal';
}
function currentMonthYM(): string {
  const d = new Date();
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}
function nextInvoiceDateISO(): string {
  const d = new Date();
  const nm = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1));
  return nm.toISOString().slice(0, 10);
}
function toQuotaRow(b: BillingFixture) {
  const usagePct = b.quota > 0 ? Math.round((b.unique_customers * 10000) / b.quota) / 100 : 0;
  return {
    enterprise_id:   b.enterprise_id,
    enterprise_name: b.enterprise_name,
    workspace_id:    b.workspace_id,
    plan_code:       b.plan_code,
    unique_customers: b.unique_customers,
    quota:            b.quota,
    usage_pct:        usagePct,
    overage_units:    b.overage_units,
    status:           classify(b.unique_customers, b.quota, b.overage_units),
    total_amount_vnd: b.base_amount_vnd,
  };
}

function buildBillingHandlers() {
  return [
    http.get(`${BASE}/api/v1/platform/billing/overview`, async () => {
      await delay(180);
      const rows = MOCK_BILLING.map(toQuotaRow);
      const counts = { normal: 0, warn: 0, critical: 0, overage: 0 };
      for (const r of rows) counts[r.status]++;
      const totalBase = MOCK_BILLING.reduce((s, b) => s + b.base_amount_vnd, 0);
      return HttpResponse.json({
        data: {
          billing_month: currentMonthYM(),
          enterprise_count: MOCK_BILLING.length,
          by_status: counts,
          total_unique_customers: MOCK_BILLING.reduce((s, b) => s + b.unique_customers, 0),
          total_quota:            MOCK_BILLING.reduce((s, b) => s + b.quota, 0),
          total_overage_units:    MOCK_BILLING.reduce((s, b) => s + b.overage_units, 0),
          total_base_amount_vnd:  totalBase,
          total_overage_amount_vnd: 0,
          total_revenue_vnd:      totalBase,
          next_invoice_date:      nextInvoiceDateISO(),
          // Sprint 7 PR C — F-031 cron health surfacing. Mock pretends
          // the cron ran ~2 hours ago and 0 enterprises are stale.
          last_aggregated_at:     new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
          stale_enterprise_count: 0,
        },
      });
    }),

    http.get(`${BASE}/api/v1/platform/billing/enterprises/:id`, async ({ params }) => {
      const id = String(params.id);
      await delay(150);
      const b = MOCK_BILLING.find((x) => x.enterprise_id === id);
      if (!b) {
        return HttpResponse.json(
          { type: '/docs/errors/enterprise-not-found', title: 'Enterprise not found', status: 404, detail: id },
          { status: 404 },
        );
      }
      const status = classify(b.unique_customers, b.quota, b.overage_units);
      return HttpResponse.json({
        data: {
          enterprise_id:   b.enterprise_id,
          enterprise_name: b.enterprise_name,
          workspace_id:    b.workspace_id,
          plan_code:       b.plan_code,
          billing_month:   currentMonthYM(),
          unique_customers: b.unique_customers,
          quota:            b.quota,
          overage_units:    b.overage_units,
          base_amount_vnd:  b.base_amount_vnd,
          overage_amount_vnd: 0,
          total_amount_vnd:   b.base_amount_vnd,
          quota_warn_at_pct:  80,
          status,
          next_invoice_date:  nextInvoiceDateISO(),
        },
      });
    }),

    http.get(`${BASE}/api/v1/platform/billing/quota`, async ({ request }) => {
      const url = new URL(request.url);
      const plan   = url.searchParams.get('plan')   || undefined;
      const status = url.searchParams.get('status') || undefined;
      await delay(220);
      let rows = MOCK_BILLING.map(toQuotaRow);
      if (plan)   rows = rows.filter((r) => r.plan_code === plan);
      if (status) rows = rows.filter((r) => r.status === status);
      return HttpResponse.json({
        data: rows,
        meta: { cursor: null, total: rows.length },
      });
    }),

    http.get(`${BASE}/api/v1/platform/billing/export`, async ({ request }) => {
      const url   = new URL(request.url);
      const month = url.searchParams.get('month') ?? currentMonthYM();
      if (month && !/^\d{4}-\d{2}$/.test(month)) {
        return HttpResponse.json(
          { type: '/docs/errors/invalid-month', title: 'Invalid month', status: 400, detail: month },
          { status: 400 },
        );
      }
      const plan   = url.searchParams.get('plan')   || undefined;
      const status = url.searchParams.get('status') || undefined;
      let rows = MOCK_BILLING.map(toQuotaRow);
      if (plan)   rows = rows.filter((r) => r.plan_code === plan);
      if (status) rows = rows.filter((r) => r.status === status);

      const header = 'enterprise_id,enterprise_name,plan_code,billing_month,'
        + 'unique_customers,quota,usage_pct,overage_units,'
        + 'base_amount_vnd,overage_amount_vnd,total_amount_vnd,status';
      const escape = (s: string) =>
        /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      const body = rows.map((r) =>
        [
          r.enterprise_id, escape(r.enterprise_name), r.plan_code, month,
          r.unique_customers, r.quota, r.usage_pct, r.overage_units,
          r.total_amount_vnd.toFixed(2), '0.00', r.total_amount_vnd.toFixed(2),
          r.status,
        ].join(','),
      ).join('\r\n');
      const csv  = header + '\r\n' + body + (body ? '\r\n' : '');

      // UTF-8 BOM (EF BB BF) prefix — matches backend.
      const bom  = new Uint8Array([0xEF, 0xBB, 0xBF]);
      const data = new TextEncoder().encode(csv);
      const buf  = new Uint8Array(bom.length + data.length);
      buf.set(bom);
      buf.set(data, bom.length);

      return new HttpResponse(buf, {
        status: 200,
        headers: {
          'Content-Type':        'text/csv; charset=utf-8',
          'Content-Disposition': `attachment; filename="kaori-billing-${month}.csv"`,
        },
      });
    }),
  ];
}

// ─────────────────────────────────────────────────────────────────────────
// Security fixtures + handlers (Module 3)
// ─────────────────────────────────────────────────────────────────────────

interface MockSession {
  session_id:     string;
  ip_address:     string;
  user_agent:     string;
  device_label:   string;
  created_at:     string;
  last_active_at: string;
  revoked_at:     string | null;
}

const MOCK_SESSIONS: MockSession[] = [
  {
    session_id:     'sess_current',
    ip_address:     '203.0.113.42',
    user_agent:     'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) Chrome/120.0',
    device_label:   'Chrome trên macOS',
    created_at:     '2026-04-26T07:00:00Z',
    last_active_at: '2026-04-26T11:30:00Z',
    revoked_at:     null,
  },
  {
    session_id:     'sess_phone',
    ip_address:     '198.51.100.7',
    user_agent:     'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4) Safari/605',
    device_label:   'Safari trên iPhone',
    created_at:     '2026-04-25T18:00:00Z',
    last_active_at: '2026-04-26T08:15:00Z',
    revoked_at:     null,
  },
];

let MOCK_MFA_ENABLED = false;
const DEMO_OTPAUTH = 'otpauth://totp/Kaori:demo%40kaori.io?secret=JBSWY3DPEHPK3PXP&issuer=Kaori&algorithm=SHA1&digits=6&period=30';
const DEMO_SECRET  = 'JBSWY3DPEHPK3PXP';

function buildSecurityHandlers() {
  return [
    http.post(`${BASE}/api/v1/platform/security/mfa/enable`, async () => {
      await delay(220);
      // Reset enabled state — re-enabling forces re-verify of the new secret.
      MOCK_MFA_ENABLED = false;
      return HttpResponse.json({
        data: {
          secret:      DEMO_SECRET,
          otpauth_url: DEMO_OTPAUTH,
          issuer:      'Kaori',
          account:     'demo@kaori.io',
        },
        meta: {
          warning: 'Scan the QR code in Google Authenticator and verify a code within 30 seconds.',
        },
      });
    }),

    http.post(`${BASE}/api/v1/platform/security/mfa/verify`, async ({ request }) => {
      const body = (await request.json().catch(() => ({}))) as { code?: string };
      await delay(180);
      // Mock acceptance: any 6-digit code where digits sum to an even number.
      // Avoids hard-coding "123456" while still letting any tester pick a code.
      const code = String(body.code ?? '');
      if (!/^\d{6}$/.test(code)) {
        return HttpResponse.json(
          { type: '/docs/errors/invalid-code', title: 'Invalid or expired code', status: 400, detail: 'code must be 6 digits' },
          { status: 400 },
        );
      }
      const sum = [...code].reduce((s, ch) => s + Number(ch), 0);
      if (sum % 2 !== 0) {
        return HttpResponse.json(
          { type: '/docs/errors/invalid-code', title: 'Invalid or expired code', status: 400, detail: 'mock: pick a code with even digit sum' },
          { status: 400 },
        );
      }
      MOCK_MFA_ENABLED = true;
      return HttpResponse.json({
        data: { mfa_enabled: true, verified_at: new Date().toISOString() },
      });
    }),

    http.get(`${BASE}/api/v1/platform/security/sessions`, async () => {
      await delay(150);
      const items = MOCK_SESSIONS
        .filter((s) => !s.revoked_at)
        .map((s) => ({
          session_id:     s.session_id,
          ip_address:     s.ip_address,
          user_agent:     s.user_agent,
          device_label:   s.device_label,
          created_at:     s.created_at,
          last_active_at: s.last_active_at,
          is_current:     s.session_id === 'sess_current',
        }));
      return HttpResponse.json({ data: items });
    }),

    http.post(`${BASE}/api/v1/platform/security/sessions/revoke-others`, async () => {
      await delay(220);
      let count = 0;
      const now = new Date().toISOString();
      for (const s of MOCK_SESSIONS) {
        if (!s.revoked_at && s.session_id !== 'sess_current') {
          s.revoked_at = now;
          count++;
        }
      }
      return HttpResponse.json({
        data: {
          revoked_count:    count,
          kept_session_id:  'sess_current',
          revoked_at:       now,
        },
      });
    }),

    http.delete(`${BASE}/api/v1/platform/security/sessions/:id`, async ({ params }) => {
      const id = String(params.id);
      await delay(180);
      const target = MOCK_SESSIONS.find((s) => s.session_id === id && !s.revoked_at);
      if (!target) {
        return HttpResponse.json(
          { type: '/docs/errors/session-not-found', title: 'Session not found', status: 404, detail: id },
          { status: 404 },
        );
      }
      target.revoked_at = new Date().toISOString();
      return HttpResponse.json({
        data: { session_id: target.session_id, revoked_at: target.revoked_at },
        meta: { signed_out: target.session_id === 'sess_current' },
      });
    }),
  ];
}

// Tiny helper so MOCK_MFA_ENABLED isn't flagged as unused if we add a status
// endpoint later. Keeps the const live in dev tooling.
export function _devMfaState() { return MOCK_MFA_ENABLED; }
