import { http, HttpResponse, delay } from "msw";

// MSW handler for F-041 Explainability — mirror BE shape from
// services/ai-orchestrator/routers/explainability.py. The decision
// detail page (32b-decisions-id-wired.tsx) calls this endpoint when
// the user hits "Tạo giải thích".
//
// Returns a deterministic top-3 + Vietnamese narrative so dev mode
// renders without llm-gateway running. Branches the narrative on the
// decision_id prefix so reviewers can see different shapes:
//   "fail-..." → 502 (ExplanationFailedError path)
//   "miss-..." → 404 (DecisionNotFoundError path)
//   anything else → happy path

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

const HAPPY_FACTORS = [
  {
    factor_name: "Khớp ngữ nghĩa Levenshtein cao với từ điển VI",
    direction:   "positive" as const,
    weight:      0.65,
    evidence:    "Edit-distance 0.92 với 'revenue' trong language_dictionary VI — khoảng cách rất gần.",
  },
  {
    factor_name: "Ứng viên thay thế kém cách biệt",
    direction:   "positive" as const,
    weight:      0.22,
    evidence:    "Lựa chọn 'sales' chỉ đạt 0.71 — kém 'revenue' 0.21 điểm; không đủ lý do bỏ qua.",
  },
  {
    factor_name: "Không có cờ uncertainty từ pipeline",
    direction:   "neutral" as const,
    weight:      0.13,
    evidence:    "uncertainty_flags rỗng — không có warning từ tầng cleaning rule.",
  },
];

const HAPPY_RESPONSE = {
  top_factors:            HAPPY_FACTORS,
  narrative:              "Kaori chọn map 'doanh_thu' sang 'revenue' vì độ khớp ngữ nghĩa rất cao và không có lựa chọn cạnh tranh đáng kể. Decision này phù hợp template canonical schema cho domain bán lẻ.",
  confidence_explanation: "Confidence 0.92 phản ánh khoảng cách edit-distance gần 1.0 — rất ít rủi ro nhầm. Nếu pilot phát hiện sai, override sẽ ghi vào kaori.feedback.actions để retrain.",
};

export const explainabilityHandlers = [
  http.post(`${BASE}/api/v1/explainability/explain`, async ({ request }) => {
    const body = (await request.json()) as { decision_id: string };
    const id = String(body.decision_id);

    if (id.startsWith("miss-")) {
      return problem(404, "/docs/errors/decision-not-found", "Decision not found", id);
    }
    if (id.startsWith("fail-")) {
      return problem(502, "/docs/errors/llm-failed", "LLM failed",
        "LLM gave up explaining this decision: gateway 502 LLM.OUTPUT_VALIDATION_FAILED");
    }

    await delay(1200);
    return HttpResponse.json({
      decision_id:            id,
      ...HAPPY_RESPONSE,
    });
  }),
];
