import { http, HttpResponse, delay } from "msw";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

const DECISION_TYPES = [
  "column_map", "cleaning_rule", "template_analysis",
  "language_detect", "purpose_classify", "model_select",
];
const METHODS = ["llm", "fuzzy", "exact", "heuristic", "user_confirmed"];

// F-036 override row shape — matches services/ai-orchestrator/routers/decisions.py
// _override_to_view().
interface MockOverride {
  override_id:           string;
  decision_id:           string;
  original_chosen_value: string | null;
  override_value:        string;
  reason:                string;
  overridden_by_user:    string | null;
  overridden_at:         string | null;
  revoked_at:            string | null;
  revoked_by_user:       string | null;
  revoke_reason:         string | null;
  is_active:             boolean;
}

const MOCK_DECISIONS = Array.from({ length: 60 }, (_, i) => ({
  id:                  `dec-${String(i + 1).padStart(4, "0")}-uuid`,
  decision_id:         `dec-${String(i + 1).padStart(4, "0")}-uuid`,
  decision_type:       DECISION_TYPES[i % DECISION_TYPES.length],
  entity_ref:          ["customer_name", "amount", "date", "phone", "Doanh thu", "Ngày giao dịch"][i % 6],
  subject:             ["customer_name", "amount", "date", "phone", "Doanh thu", "Ngày giao dịch"][i % 6],
  chosen_value:        ["text", "currency", "date", "phone", "currency", "date"][i % 6],
  confidence:          0.55 + ((i * 13) % 45) / 100,
  method:              METHODS[i % METHODS.length],
  alternatives:        [] as Array<{ title?: string; rejected_reason?: string; confidence?: number; [k: string]: unknown }>,
  uncertainty_flags:   i % 7 === 0 ? ["LOW_CONFIDENCE"] : [],
  reasoning:           `Mock decision #${i + 1} — heuristic match against language dictionary.`,
  needs_user_confirm:  i % 9 === 0,
  run_id:              `run-${String(((i % 5) + 1)).padStart(4, "0")}-uuid`,
  created_at:          new Date(Date.now() - i * 30 * 60 * 1000).toISOString(),
  // Sprint 7 PR D — North Star manual toggle. Pretend every 5th row is
  // already actioned so the dev-mode page renders both states.
  is_actioned:         i % 5 === 0,
  actioned_at:         i % 5 === 0
                          ? new Date(Date.now() - i * 30 * 60 * 1000 + 60_000).toISOString()
                          : null,
}));

// Hydrate two decisions with rich content so the wired detail page renders
// non-trivially on first hit. dec-0001 has alternatives + a seeded
// override; dec-0006 has alternatives only.
MOCK_DECISIONS[0].alternatives = [
  { title: "non-churn", rejected_reason: "engagement chỉ -10%, dưới ngưỡng 30%", confidence: 0.42 },
  { title: "churn-low", rejected_reason: "không đủ feature signal về xu hướng", confidence: 0.28 },
];
MOCK_DECISIONS[0].reasoning =
  "Engagement metric tụt 35% trong 90 ngày + payment history có 1 missed payment Q4. " +
  "Cross-check với cohort cùng segment cho thấy churn rate trung bình 22%.";
MOCK_DECISIONS[5].alternatives = [
  { title: "currency", rejected_reason: "tên cột không match từ điển 'currency'", confidence: 0.55 },
];

const MOCK_OVERRIDES: MockOverride[] = [
  {
    override_id:           "ov-0001-mock-uuid",
    decision_id:           "dec-0001-uuid",
    original_chosen_value: MOCK_DECISIONS[0].chosen_value,
    override_value:        "non-churn",
    reason:                "Khách VIP vừa ký lại hợp đồng năm — AI chưa thấy event renewal.",
    overridden_by_user:    "user-0001-uuid",
    overridden_at:         new Date(Date.now() - 8 * 3600 * 1000).toISOString(),
    revoked_at:            null,
    revoked_by_user:       null,
    revoke_reason:         null,
    is_active:             true,
  },
  {
    override_id:           "ov-0002-mock-uuid",
    decision_id:           "dec-0001-uuid",
    original_chosen_value: MOCK_DECISIONS[0].chosen_value,
    override_value:        "churn-low",
    reason:                "Initial guess — typo, sửa lại ở override_id ov-0001.",
    overridden_by_user:    "user-0001-uuid",
    overridden_at:         new Date(Date.now() - 9 * 3600 * 1000).toISOString(),
    revoked_at:            new Date(Date.now() - 8.5 * 3600 * 1000).toISOString(),
    revoked_by_user:       "user-0001-uuid",
    revoke_reason:         "Sai giá trị — re-do với non-churn.",
    is_active:             false,
  },
];

export const decisionsHandlers = [
  // ── List (cursor-paginated, F-029) ─────────────────────────────────────────
  http.get(`${BASE}/api/v1/decisions`, async ({ request }) => {
    const url    = new URL(request.url);
    const limit  = Math.min(Number(url.searchParams.get("limit") ?? 50), 500);
    const cursor = url.searchParams.get("cursor");
    const type   = url.searchParams.get("type");
    const q      = url.searchParams.get("q");

    let filtered = MOCK_DECISIONS;
    if (type) {
      const types = type.split(",").map((s) => s.trim());
      filtered = filtered.filter((d) => types.includes(d.decision_type));
    }
    if (q) {
      const needle = q.toLowerCase();
      filtered = filtered.filter((d) =>
        (d.subject ?? "").toLowerCase().includes(needle) ||
        (d.reasoning ?? "").toLowerCase().includes(needle) ||
        (d.chosen_value ?? "").toLowerCase().includes(needle)
      );
    }

    const startIdx = cursor ? Number(decodeURIComponent(cursor)) : 0;
    const slice    = filtered.slice(startIdx, startIdx + limit);
    const hasMore  = startIdx + limit < filtered.length;

    await delay(180);
    return HttpResponse.json({
      data: slice,
      meta: {
        cursor:      hasMore ? String(startIdx + limit) : null,
        limit,
        count:       slice.length,
        has_more:    hasMore,
        request_id:  crypto.randomUUID(),
        trace_id:    null,
        server_time: new Date().toISOString(),
      },
    });
  }),

  // ── Action toggle (Sprint 7 PR D — North Star manual) ─────────────────────
  http.post(`${BASE}/api/v1/decisions/:id/action`, async ({ params, request }) => {
    const id   = String(params.id);
    const body = (await request.json()) as { is_actioned: boolean; notes?: string };
    const row  = MOCK_DECISIONS.find((d) => d.decision_id === id);
    if (!row) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/decision-not-found",
        title: "Decision not found",
        status: 404,
        detail: id,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    row.is_actioned = body.is_actioned;
    row.actioned_at = body.is_actioned ? new Date().toISOString() : null;
    await delay(150);
    return HttpResponse.json({
      data: {
        decision_id:  id,
        is_actioned:  row.is_actioned,
        actioned_at:  row.actioned_at,
        notes:        body.notes ?? null,
        updated_at:   new Date().toISOString(),
      },
    });
  }),

  // ── Detail (F-036) ─────────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/decisions/:id`, async ({ params }) => {
    const id  = String(params.id);
    const row = MOCK_DECISIONS.find((d) => d.decision_id === id);
    if (!row) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/decision-not-found",
        title: "Decision not found", status: 404, detail: id,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    const overrides = MOCK_OVERRIDES
      .filter((o) => o.decision_id === id)
      .sort((a, b) => (b.overridden_at ?? "").localeCompare(a.overridden_at ?? ""));

    await delay(120);
    return HttpResponse.json({
      data: { ...row, overrides },
    });
  }),

  // ── Create override (F-036) ────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/decisions/:id/override`, async ({ params, request }) => {
    const id  = String(params.id);
    const row = MOCK_DECISIONS.find((d) => d.decision_id === id);
    if (!row) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/decision-not-found",
        title: "Decision not found", status: 404, detail: id,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    const body = (await request.json()) as { override_value?: string; reason?: string };
    const overrideValue = (body.override_value ?? "").trim();
    const reason        = (body.reason ?? "").trim();
    if (!overrideValue || !reason) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/validation", status: 422,
        title: "Validation error",
        detail: "override_value and reason are required",
      }), { status: 422, headers: { "Content-Type": "application/problem+json" } });
    }
    if (overrideValue.length > 500 || reason.length > 2000) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/validation", status: 422,
        title: "Validation error",
        detail: "override_value ≤ 500 / reason ≤ 2000 chars",
      }), { status: 422, headers: { "Content-Type": "application/problem+json" } });
    }

    const ov: MockOverride = {
      override_id:           `ov-${Date.now()}-mock`,
      decision_id:           id,
      original_chosen_value: row.chosen_value,
      override_value:        overrideValue,
      reason:                reason,
      overridden_by_user:    null,
      overridden_at:         new Date().toISOString(),
      revoked_at:            null,
      revoked_by_user:       null,
      revoke_reason:         null,
      is_active:             true,
    };
    MOCK_OVERRIDES.unshift(ov);
    await delay(120);
    return HttpResponse.json({
      data: {
        override_id:           ov.override_id,
        decision_id:           id,
        original_chosen_value: ov.original_chosen_value,
        override_value:        ov.override_value,
        reason:                ov.reason,
        overridden_by_user:    null,
        overridden_at:         ov.overridden_at,
      },
    }, { status: 201 });
  }),

  // ── Revoke override (F-036) ────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/decisions/:id/override/:oid/revoke`, async ({ params, request }) => {
    const oid    = String(params.oid);
    const target = MOCK_OVERRIDES.find((o) => o.override_id === oid);
    if (!target) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/override-not-found",
        title: "Override not found", status: 404, detail: oid,
      }), { status: 404, headers: { "Content-Type": "application/problem+json" } });
    }
    if (target.revoked_at) {
      return new HttpResponse(JSON.stringify({
        type: "/docs/errors/override-already-revoked",
        title: "Override already revoked", status: 409,
        detail: `Override already revoked at ${target.revoked_at}`,
      }), { status: 409, headers: { "Content-Type": "application/problem+json" } });
    }
    const body = (await request.json()) as { reason?: string };
    target.revoked_at      = new Date().toISOString();
    target.revoked_by_user = null;
    target.revoke_reason   = body.reason ?? null;
    target.is_active       = false;
    await delay(100);
    return HttpResponse.json({
      data: {
        override_id:     target.override_id,
        decision_id:     target.decision_id,
        revoked_at:      target.revoked_at,
        revoked_by_user: null,
        revoke_reason:   target.revoke_reason,
      },
    });
  }),

  // ── CSV export (UTF-8 BOM, F-029) ──────────────────────────────────────────
  http.get(`${BASE}/api/v1/decisions/export.csv`, async () => {
    const header = "decision_id,created_at,decision_type,subject,chosen_value,"
                 + "confidence,method,needs_user_confirm,uncertainty_flags,"
                 + "reasoning,run_id\n";
    const rows = MOCK_DECISIONS.slice(0, 5).map((d) => [
      d.decision_id, d.created_at, d.decision_type, d.subject, d.chosen_value,
      d.confidence.toFixed(4), d.method, String(d.needs_user_confirm),
      d.uncertainty_flags.join("|"), d.reasoning, d.run_id,
    ].join(",")).join("\n");
    // Prepend the UTF-8 BOM so Vietnamese Excel renders diacritics correctly.
    const body = "﻿" + header + rows + "\n";
    await delay(220);
    return new HttpResponse(body, {
      headers: {
        "Content-Type":        "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="kaori-decisions-mock.csv"`,
      },
    });
  }),
];
