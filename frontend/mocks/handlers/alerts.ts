import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-037 Alert Rules — mirror auth-service responses
// from EnterpriseAlertController so dev mode works without the Java
// stack running. Template 62b-alerts-f037 consumes these via foundation
// `api()`.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

const SENTINEL_BILLING_80 = "00000000-0000-0000-0000-000000000080";
const SENTINEL_BILLING_95 = "00000000-0000-0000-0000-000000000095";

interface MockRule {
  rule_id:           string;
  name:              string;
  description:       string | null;
  metric_type:       "billing_quota_pct";
  operator:          "gt" | "gte" | "lt" | "lte" | "eq";
  threshold_value:   number;
  channel:           "email";
  target_email:      string | null;
  cooldown_seconds:  number;
  is_active:         boolean;
  created_at:        string;
  updated_at:        string;
}

interface MockEvent {
  event_id:        string;
  rule_id:         string;
  metric_type:     string;
  metric_value:    number;
  threshold_value: number;
  operator:        "gt" | "gte" | "lt" | "lte" | "eq";
  context:         Record<string, unknown>;
  outbox_id:       string | null;
  suppressed:      boolean;
  fired_at:        string;
}

const now = Date.now();
const hours = (h: number) => new Date(now - h * 3_600_000).toISOString();

const MOCK_RULES: MockRule[] = [
  {
    rule_id:          "rule_mock_001",
    name:             "Cảnh báo sớm 90% hạn mức",
    description:      "Cảnh báo trước khi chạm 95% mặc định để team có thời gian xin nâng cấp",
    metric_type:      "billing_quota_pct",
    operator:         "gte",
    threshold_value:  90,
    channel:          "email",
    target_email:     "billing-ops@acme.vn",
    cooldown_seconds: 7200,
    is_active:        true,
    created_at:       hours(72),
    updated_at:       hours(48),
  },
  {
    rule_id:          "rule_mock_002",
    name:             "Hạn mức đạt 50% — kiểm tra giữa tháng",
    description:      null,
    metric_type:      "billing_quota_pct",
    operator:         "gte",
    threshold_value:  50,
    channel:          "email",
    target_email:     null,
    cooldown_seconds: 86400,
    is_active:        false,
    created_at:       hours(120),
    updated_at:       hours(120),
  },
];

const MOCK_EVENTS: MockEvent[] = [
  {
    event_id:        "evt_mock_001",
    rule_id:         SENTINEL_BILLING_95,
    metric_type:     "billing_quota_pct",
    metric_value:    96,
    threshold_value: 95,
    operator:        "gte",
    context: {
      enterprise_name: "Acme JSC",
      usage_pct:       96,
      used:            9612,
      quota_limit:     10_000,
      plan:            "ENT_MAX",
      plan_label:      "Enterprise Max",
      threshold:       95,
      upgrade_url:     "http://localhost:3000/subscription?tab=upgrade",
    },
    outbox_id:  "outbox_mock_001",
    suppressed: false,
    fired_at:   hours(3),
  },
  {
    event_id:        "evt_mock_002",
    rule_id:         SENTINEL_BILLING_95,
    metric_type:     "billing_quota_pct",
    metric_value:    96,
    threshold_value: 95,
    operator:        "gte",
    context: { suppress_reason: "cooldown", usage_pct: 96, used: 9612, quota_limit: 10_000 },
    outbox_id:  null,
    suppressed: true,
    fired_at:   hours(2),
  },
  {
    event_id:        "evt_mock_003",
    rule_id:         SENTINEL_BILLING_80,
    metric_type:     "billing_quota_pct",
    metric_value:    82,
    threshold_value: 80,
    operator:        "gte",
    context: {
      enterprise_name: "Acme JSC",
      usage_pct:       82,
      used:            8200,
      quota_limit:     10_000,
      plan:            "ENT_MAX",
      plan_label:      "Enterprise Max",
      threshold:       80,
      upgrade_url:     "http://localhost:3000/subscription?tab=upgrade",
    },
    outbox_id:  "outbox_mock_002",
    suppressed: false,
    fired_at:   hours(36),
  },
  {
    event_id:        "evt_mock_004",
    rule_id:         "rule_mock_001",
    metric_type:     "billing_quota_pct",
    metric_value:    91,
    threshold_value: 90,
    operator:        "gte",
    context: {
      enterprise_name: "Acme JSC",
      usage_pct:       91,
      used:            9100,
      quota_limit:     10_000,
      plan:            "ENT_MAX",
      plan_label:      "Enterprise Max",
    },
    outbox_id:  "outbox_mock_003",
    suppressed: false,
    fired_at:   hours(20),
  },
  {
    event_id:        "evt_mock_005",
    rule_id:         "rule_mock_001",
    metric_type:     "billing_quota_pct",
    metric_value:    91,
    threshold_value: 90,
    operator:        "gte",
    context: { suppress_reason: "no_recipient", usage_pct: 91 },
    outbox_id:  null,
    suppressed: true,
    fired_at:   hours(15),
  },
];

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

export const alertsHandlers = [
  // ── List rules ──────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/alerts`, async ({ request }) => {
    const url   = new URL(request.url);
    const page  = Math.max(1, Number(url.searchParams.get("page")  ?? 1));
    const limit = Math.max(1, Math.min(100, Number(url.searchParams.get("limit") ?? 20)));
    const start = (page - 1) * limit;
    await delay(80);
    return HttpResponse.json({
      data: MOCK_RULES.slice(start, start + limit),
      meta: { total: MOCK_RULES.length, page, limit },
    });
  }),

  // ── Recent events ───────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/alerts/events`, async ({ request }) => {
    const url   = new URL(request.url);
    const limit = Math.max(1, Math.min(500, Number(url.searchParams.get("limit") ?? 50)));
    await delay(80);
    return HttpResponse.json({ data: MOCK_EVENTS.slice(0, limit) });
  }),

  // ── Single rule ─────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/enterprises/alerts/:id`, async ({ params }) => {
    const id  = String(params.id);
    const row = MOCK_RULES.find((r) => r.rule_id === id);
    if (!row) return problem(404, "/docs/errors/alert-rule-not-found", "Alert rule not found", id);
    return HttpResponse.json({ data: row });
  }),

  // ── Create ──────────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/enterprises/alerts`, async ({ request }) => {
    const body = (await request.json()) as Partial<MockRule>;
    if (!body?.name || String(body.name).trim().length === 0) {
      return problem(400, "/docs/errors/invalid-request", "Invalid request", "name is required");
    }
    if (body.metric_type !== "billing_quota_pct") {
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
        "metric_type must be one of [billing_quota_pct]");
    }
    if (typeof body.threshold_value !== "number" || body.threshold_value < 0) {
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
        "threshold_value must be ≥ 0");
    }

    const newRule: MockRule = {
      rule_id:          `rule_mock_${Date.now()}`,
      name:             String(body.name).trim(),
      description:      body.description ?? null,
      metric_type:      "billing_quota_pct",
      operator:         (body.operator as MockRule["operator"]) ?? "gte",
      threshold_value:  Number(body.threshold_value),
      channel:          "email",
      target_email:     body.target_email ?? null,
      cooldown_seconds: body.cooldown_seconds ?? 300,
      is_active:        body.is_active ?? true,
      created_at:       new Date().toISOString(),
      updated_at:       new Date().toISOString(),
    };
    MOCK_RULES.unshift(newRule);
    await delay(120);
    return HttpResponse.json({ data: newRule }, { status: 201 });
  }),

  // ── Update ──────────────────────────────────────────────────────────────
  http.patch(`${BASE}/api/v1/enterprises/alerts/:id`, async ({ params, request }) => {
    const id    = String(params.id);
    const idx   = MOCK_RULES.findIndex((r) => r.rule_id === id);
    if (idx < 0) return problem(404, "/docs/errors/alert-rule-not-found", "Alert rule not found", id);
    const patch = (await request.json()) as Partial<MockRule>;
    const empty = Object.values(patch ?? {}).every((v) => v === undefined);
    if (empty) {
      return problem(400, "/docs/errors/invalid-request", "Invalid request",
        "at least one field must be provided");
    }
    MOCK_RULES[idx] = {
      ...MOCK_RULES[idx],
      ...patch,
      rule_id:    MOCK_RULES[idx].rule_id,
      updated_at: new Date().toISOString(),
    } as MockRule;
    await delay(80);
    return HttpResponse.json({ data: MOCK_RULES[idx] });
  }),

  // ── Soft delete ─────────────────────────────────────────────────────────
  http.delete(`${BASE}/api/v1/enterprises/alerts/:id`, async ({ params }) => {
    const id  = String(params.id);
    const idx = MOCK_RULES.findIndex((r) => r.rule_id === id);
    if (idx < 0) return problem(404, "/docs/errors/alert-rule-not-found", "Alert rule not found", id);
    MOCK_RULES.splice(idx, 1);
    await delay(60);
    return HttpResponse.json({ data: { rule_id: id, status: "deleted" } });
  }),
];
