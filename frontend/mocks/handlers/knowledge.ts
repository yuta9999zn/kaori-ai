import { http, HttpResponse, delay } from "msw";

// MSW handlers for F-061 Knowledge Base (ai-orchestrator knowledge_base.py /
// CR-0017). Lets /p2/insights/knowledge-base render end-to-end in dev mode
// without ai-orchestrator + Postgres + llm-gateway in the loop.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

const GLOBAL_DOCS = [
  {
    document_id: "kb-rfm",
    tier: 2, scope: "global", category: "rfm", lang: "vi",
    title: "Phân khúc RFM — Recency, Frequency, Monetary",
    source: "Nguyên lý phân tích bán lẻ SME (tổng hợp)",
    source_url: null, tags: ["rfm", "segmentation"],
    snippet: "RFM chấm điểm khách theo 3 trục: Recency, Frequency, Monetary. Chia theo ngũ phân vị trên chính tập khách — không gán ngưỡng cứng.",
    similarity: null,
  },
  {
    document_id: "kb-churn",
    tier: 3, scope: "global", category: "churn", lang: "vi",
    title: "Cửa sổ rời bỏ và dấu hiệu churn (advisory)",
    source: "Heuristic ngành bán lẻ (tham khảo)",
    source_url: null, tags: ["churn", "recency"],
    snippet: "Khách không mua quá ~90 ngày thường bắt đầu có nguy cơ; cửa sổ cứu ~90–270 ngày. Hiệu chỉnh theo chu kỳ mua của ngành.",
    similarity: null,
  },
  {
    document_id: "kb-retention",
    tier: 3, scope: "global", category: "retention", lang: "vi",
    title: "Playbook giữ chân theo giá trị + recency",
    source: "Heuristic ngành bán lẻ (tham khảo)",
    source_url: null, tags: ["retention", "win-back"],
    snippet: "LTV cao + recency nông → CSM gọi 1-1. Recency sâu hơn → voucher có điều kiện. Quá sâu → tái kích hoạt diện rộng.",
    similarity: null,
  },
];

const TENANT_DOCS = [
  {
    document_id: "kb-own-1",
    tier: 4, scope: "tenant", category: "retention", lang: "vi",
    title: "SOP win-back VIP của workspace",
    source: "Nội bộ", source_url: null, tags: ["vip", "sop"],
    snippet: "Khách VIP rời bỏ: CSM gọi trong 24h, ưu đãi tối đa 10%, ghi log vào CRM.",
    similarity: null,
  },
];

export const knowledgeHandlers = [
  http.get(`${BASE}/api/v1/knowledge-base/documents`, async () => {
    await delay(120);
    return HttpResponse.json({ documents: [...GLOBAL_DOCS, ...TENANT_DOCS] });
  }),

  http.post(`${BASE}/api/v1/knowledge-base/search`, async ({ request }) => {
    await delay(180);
    const body = (await request.json().catch(() => ({}))) as { query?: string; top_k?: number };
    const all = [...GLOBAL_DOCS, ...TENANT_DOCS];
    // Fake relevance: keyword overlap on the query, else everything; attach a
    // descending similarity so the UI shows the % badge.
    const q = (body.query ?? "").toLowerCase();
    const hits = all
      .map((d) => ({
        d,
        hit: q && (d.title.toLowerCase().includes(q) || (d.category ?? "").includes(q)
          || d.snippet.toLowerCase().includes(q)),
      }))
      .filter((x) => (q ? x.hit : true))
      .slice(0, body.top_k ?? 8);
    const results = (hits.length ? hits.map((x) => x.d) : all.slice(0, 3)).map((d, i) => ({
      ...d, similarity: Math.max(0.5, 0.96 - i * 0.08),
    }));
    return HttpResponse.json({ query: body.query ?? "", results });
  }),

  http.post(`${BASE}/api/v1/knowledge-base/documents`, async ({ request }) => {
    await delay(200);
    const body = (await request.json().catch(() => ({}))) as { title?: string };
    if (!body.title) {
      return HttpResponse.json({ detail: { title: "title required" } }, { status: 422 });
    }
    return HttpResponse.json(
      { document_id: `kb-own-${Date.now()}`, status: "active" },
      { status: 201 },
    );
  }),
];
