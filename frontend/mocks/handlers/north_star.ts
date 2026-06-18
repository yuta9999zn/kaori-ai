import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-060 — mirror the BE shapes from
// services/ai-orchestrator/routers/north_star.py. Lets the dev-mode
// /p2/customers/at-risk page render end-to-end without ai-orchestrator
// + Postgres + Kafka in the loop.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

interface MockCustomer {
  customer_external_id: string;
  revenue_at_risk:      number;
  last_purchase_at:     string | null;
  purchase_count:       number;
  is_actioned:          boolean;
  actioned_at:          string | null;
  actioned_by_user:     string | null;
  computed_at:          string;
}

const days = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();

// Seed a realistic spread: 8 at-risk customers, 3 already actioned, 5
// pending. Revenue values trend down the list so the FE sort + cursor
// pagination renders meaningfully.
const MOCK_CUSTOMERS: MockCustomer[] = [
  { customer_external_id: "CUST-A0001", revenue_at_risk: 480_000_000, last_purchase_at: days(95),  purchase_count: 38, is_actioned: false, actioned_at: null, actioned_by_user: null, computed_at: days(1) },
  { customer_external_id: "CUST-A0007", revenue_at_risk: 320_000_000, last_purchase_at: days(120), purchase_count: 27, is_actioned: false, actioned_at: null, actioned_by_user: null, computed_at: days(1) },
  { customer_external_id: "CUST-B0042", revenue_at_risk: 285_000_000, last_purchase_at: days(60),  purchase_count: 19, is_actioned: true,  actioned_at: days(2), actioned_by_user: "user-mock-001", computed_at: days(1) },
  { customer_external_id: "CUST-A0019", revenue_at_risk: 240_000_000, last_purchase_at: days(80),  purchase_count: 22, is_actioned: false, actioned_at: null, actioned_by_user: null, computed_at: days(1) },
  { customer_external_id: "CUST-C0103", revenue_at_risk: 195_000_000, last_purchase_at: days(45),  purchase_count: 14, is_actioned: true,  actioned_at: days(3), actioned_by_user: "user-mock-001", computed_at: days(1) },
  { customer_external_id: "CUST-B0078", revenue_at_risk: 150_000_000, last_purchase_at: days(110), purchase_count: 11, is_actioned: false, actioned_at: null, actioned_by_user: null, computed_at: days(1) },
  { customer_external_id: "CUST-D0234", revenue_at_risk: 120_000_000, last_purchase_at: days(70),  purchase_count: 9,  is_actioned: false, actioned_at: null, actioned_by_user: null, computed_at: days(1) },
  { customer_external_id: "CUST-E0301", revenue_at_risk:  85_000_000, last_purchase_at: days(40),  purchase_count: 6,  is_actioned: true,  actioned_at: days(5), actioned_by_user: "user-mock-002", computed_at: days(1) },
];

function computeTile() {
  const atRisk = MOCK_CUSTOMERS.filter((c) => c.revenue_at_risk > 0);
  const actioned = atRisk.filter((c) => c.is_actioned);
  const total    = atRisk.reduce((s, c) => s + c.revenue_at_risk, 0);
  const resolved = actioned.reduce((s, c) => s + c.revenue_at_risk, 0);
  const recent   = [...actioned]
    .filter((c) => c.actioned_at)
    .sort((a, b) => (b.actioned_at ?? "").localeCompare(a.actioned_at ?? ""))
    .slice(0, 5)
    .map((c) => ({
      customer_external_id: c.customer_external_id,
      revenue_at_risk:      c.revenue_at_risk,
      actioned_at:          c.actioned_at!,
      actioned_by_user:     c.actioned_by_user,
    }));
  return {
    total_at_risk_vnd:   total,
    resolved_vnd:        resolved,
    resolution_rate_pct: total > 0 ? Math.round((resolved / total) * 1000) / 10 : 0,
    actioned_count:      actioned.length,
    at_risk_count:       atRisk.length,
    recent_actions:      recent,
  };
}

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

function encodeCursor(rev: number, id: string): string {
  return btoa(`${rev}|${id}`)
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function decodeCursor(cursor: string): [number, string] | null {
  try {
    const padded = cursor.replace(/-/g, "+").replace(/_/g, "/")
      + "=".repeat((-cursor.length) & 3);
    const decoded = atob(padded);
    const [rev, id] = decoded.split("|", 2);
    return [Number(rev), id];
  } catch {
    return null;
  }
}

export const northStarHandlers = [
  // ── Tile ────────────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/dashboard/north-star`, async () => {
    await delay(80);
    return HttpResponse.json(computeTile());
  }),

  // ── At-risk list ────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/customers/at-risk`, async ({ request }) => {
    const url      = new URL(request.url);
    const limit    = Math.max(1, Math.min(500, Number(url.searchParams.get("limit") ?? 50)));
    const cursor   = url.searchParams.get("cursor");
    const actioned = url.searchParams.get("actioned");

    let filtered = MOCK_CUSTOMERS.filter((c) => c.revenue_at_risk > 0);
    if (actioned === "true")  filtered = filtered.filter((c) =>  c.is_actioned);
    if (actioned === "false") filtered = filtered.filter((c) => !c.is_actioned);
    // Sort matches BE: revenue_at_risk DESC, customer_external_id DESC.
    filtered.sort((a, b) => {
      if (b.revenue_at_risk !== a.revenue_at_risk) return b.revenue_at_risk - a.revenue_at_risk;
      return b.customer_external_id.localeCompare(a.customer_external_id);
    });

    if (cursor) {
      const decoded = decodeCursor(cursor);
      if (!decoded) return problem(400, "/docs/errors/invalid-cursor", "Invalid cursor", cursor);
      const [cursorRev, cursorId] = decoded;
      filtered = filtered.filter((c) => {
        if (c.revenue_at_risk !== cursorRev) return c.revenue_at_risk < cursorRev;
        return c.customer_external_id < cursorId;
      });
    }

    const items   = filtered.slice(0, limit);
    const hasMore = filtered.length > limit;
    const next    = hasMore && items.length > 0
      ? encodeCursor(items[items.length - 1].revenue_at_risk, items[items.length - 1].customer_external_id)
      : null;

    await delay(80);
    return HttpResponse.json({ items, next_cursor: next });
  }),

  // ── Toggle ──────────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/customers/:id/action`, async ({ params, request }) => {
    const id  = decodeURIComponent(String(params.id));
    const row = MOCK_CUSTOMERS.find((c) => c.customer_external_id === id);
    if (!row) return problem(404, "/docs/errors/customer-not-found", "Customer not found",
      `Customer ${id} not in gold_features — run the gold aggregator first.`);

    const body = (await request.json()) as { is_actioned?: boolean; notes?: string };
    if (body.notes && body.notes.length > 2000) {
      return problem(422, "/docs/errors/validation", "Validation error", "notes must be ≤ 2000 chars");
    }

    row.is_actioned      = !!body.is_actioned;
    row.actioned_at      = body.is_actioned ? new Date().toISOString() : null;
    row.actioned_by_user = body.is_actioned ? "user-mock-001" : null;

    await delay(120);
    return HttpResponse.json({
      customer_external_id: row.customer_external_id,
      is_actioned:          row.is_actioned,
      actioned_at:          row.actioned_at,
      actioned_by_user:     row.actioned_by_user,
      revenue_at_risk:      row.revenue_at_risk,
    });
  }),
];
