import { http, HttpResponse, delay } from "msw";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

// Mutable so the upgrade POST flips the response shape without reload.
let MOCK_STATE = {
  enterprise_id:           "11111111-1111-1111-1111-111111111111",
  enterprise_name:         "Công ty TNHH Demo Kaori",
  current_plan:            "ENT_BASIC",
  plan_display_name:       "Enterprise Basic",
  plan_quota:              1000,
  plan_price_vnd:          2_000_000,
  usage_count:             720,
  quota:                   1000,
  usage_pct:               72,
  overage_units:           0,
  forecast_eom:            1080,
  alert_80_fired:          false,
  alert_95_fired:          false,
  billing_month:           "2026-04-01",
  days_in_billing_month:   30,
  days_remaining:          7,
  last_aggregated_at:      "2026-04-27T02:00:00Z",
  pending_upgrade:         null as null | {
    request_id:     string;
    requested_plan: string;
    requested_at:   string;
  },
};

export const subscriptionHandlers = [
  http.get(`${BASE}/api/v1/enterprises/me/subscription`, async () => {
    await delay(180);
    return HttpResponse.json({ data: MOCK_STATE });
  }),

  http.post(`${BASE}/api/v1/enterprises/me/subscription/upgrade`, async ({ request }) => {
    const body = await request.json() as { target_plan: string };
    await delay(220);

    if (MOCK_STATE.pending_upgrade) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/upgrade-pending",
        title: "Upgrade already pending",
        status: 409,
        detail: "An upgrade request is already PENDING for this enterprise",
      }), { status: 409, headers: { "Content-Type": "application/problem+json" } });
    }

    if (body.target_plan === MOCK_STATE.current_plan) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/invalid-plan",
        title: "Invalid plan",
        status: 400,
        detail: "target_plan must differ from current plan",
      }), { status: 400, headers: { "Content-Type": "application/problem+json" } });
    }

    const requestId = crypto.randomUUID();
    MOCK_STATE = {
      ...MOCK_STATE,
      pending_upgrade: {
        request_id:     requestId,
        requested_plan: body.target_plan,
        requested_at:   new Date().toISOString(),
      },
    };
    return HttpResponse.json({
      data: {
        request_id:     requestId,
        enterprise_id:  MOCK_STATE.enterprise_id,
        current_plan:   MOCK_STATE.current_plan,
        requested_plan: body.target_plan,
        status:         "PENDING",
        requested_at:   new Date().toISOString(),
      },
    }, { status: 201 });
  }),
];
