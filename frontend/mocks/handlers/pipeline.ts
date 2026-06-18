import { http, HttpResponse, delay } from "msw";

const BASE = "http://localhost:8080";

let RUN_COUNTER = 2;

const MOCK_SCHEMA_SHEETS = [
  {
    file_id: "file_001",
    sheet_name: "Sheet1",
    detected_purpose: "transaction_list",
    mappings: [
      { source_column: "Mã KH",         canonical_name: "customer_id",   data_type: "id",       confidence: 0.98, method: "exact_match", uncertainty_flags: [] },
      { source_column: "Tên khách",      canonical_name: "customer_name", data_type: "text",     confidence: 0.95, method: "exact_match", uncertainty_flags: [] },
      { source_column: "Ngày giao dịch", canonical_name: "date",          data_type: "date",     confidence: 0.99, method: "exact_match", uncertainty_flags: [] },
      { source_column: "Doanh thu",      canonical_name: "revenue",       data_type: "currency", confidence: 0.97, method: "exact_match", uncertainty_flags: [] },
      { source_column: "Số lượng",       canonical_name: "quantity",      data_type: "integer",  confidence: 0.88, method: "fuzzy_match", uncertainty_flags: ["AMBIGUOUS_TOP2"] },
      { source_column: "Ghi chú",        canonical_name: "note",          data_type: "text",     confidence: 0.51, method: "no_match",   uncertainty_flags: ["LOW_CONFIDENCE", "LLM_FALLBACK_USED"] },
    ],
  },
];

const MOCK_CLEANING_RULES = [
  { rule_id: "trim_whitespace",       name: "Xoá khoảng trắng thừa",           description: "Loại bỏ khoảng trắng đầu/cuối tất cả cột văn bản.",       category: "UNIVERSAL",  safe: true,  target_columns: [] },
  { rule_id: "remove_duplicates",     name: "Loại bỏ hàng trùng lặp",           description: "Xoá hàng có tất cả giá trị giống nhau.",                   category: "UNIVERSAL",  safe: true,  target_columns: [] },
  { rule_id: "standardise_date",      name: "Chuẩn hoá định dạng ngày",         description: "Chuyển tất cả cột ngày về ISO 8601 (YYYY-MM-DD).",          category: "BY_TYPE",    safe: true,  target_columns: ["date"] },
  { rule_id: "fill_missing_numeric",  name: "Điền trung bình vào ô số trống",   description: "Thay NULL ở cột số bằng giá trị trung bình của cột.",       category: "BY_TYPE",    safe: true,  target_columns: ["revenue", "quantity"] },
  { rule_id: "normalise_currency_vn", name: "Chuẩn hoá tiền tệ VNĐ",           description: "Chuyển 1.234.567 hoặc 1234567 về dạng số nguyên chuẩn.",   category: "BY_PURPOSE", safe: true,  target_columns: ["revenue"] },
  { rule_id: "drop_empty_rows",       name: "Xoá hàng toàn NULL",               description: "Loại bỏ hàng mà tất cả cột đều rỗng.",                    category: "UNIVERSAL",  safe: true,  target_columns: [] },
  { rule_id: "cap_outliers",          name: "Giới hạn giá trị ngoại lệ (IQR)",  description: "Cắt bỏ giá trị ngoài 1.5×IQR. Có thể mất dữ liệu thực.", category: "AI_DETECTED", safe: false, target_columns: ["revenue"] },
];

const MOCK_PIPELINE_RUNS = Array.from({ length: 28 }, (_, i) => ({
  id: `run_${String(i + 1).padStart(4, "0")}`,
  original_filename: ["sales_q1_2025.xlsx","customer_master_apr.csv","transactions_march.xlsx","inventory_check.xlsx","daily_revenue_may.csv"][i % 5],
  status: ["done","done","done","error","processing"][i % 5],
  row_count: [1205, 8934, 2341, 567, null][i % 5],
  created_at: new Date(Date.now() - i * 8 * 60 * 60 * 1000).toISOString(),
}));

export const pipelineHandlers = [
  // ── Upload ──────────────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/upload`, async () => {
    await delay(700);
    const id = `run_${String(++RUN_COUNTER).padStart(4, "0")}`;
    return HttpResponse.json({ run_id: id, status: "processing" });
  }),

  // ── Upload status (polled by FileUploader) ──────────────────────────────────
  http.get(`${BASE}/api/v1/upload/:runId/status`, async ({ params }) => {
    await delay(250);
    return HttpResponse.json({
      run_id: params.runId,
      status: "schema_review",
      row_count: 1842,
      sheet_count: 1,
    });
  }),

  // ── Schema (POST because it may trigger re-analysis) ───────────────────────
  http.post(`${BASE}/api/v1/schema`, async () => {
    await delay(450);
    return HttpResponse.json({ sheets: MOCK_SCHEMA_SHEETS });
  }),

  // ── Confirm schema ─────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/schema/confirm`, async () => {
    await delay(350);
    return HttpResponse.json({ status: "cleaning_pending" });
  }),

  // ── Cleaning suggestions ────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/clean/suggestions`, async () => {
    await delay(350);
    return HttpResponse.json({ rules: MOCK_CLEANING_RULES });
  }),

  // ── Apply cleaning ──────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/clean/apply`, async () => {
    await delay(650);
    return HttpResponse.json({ status: "cleaning_done", rows_cleaned: 1839 });
  }),

  // ── Trigger analysis ────────────────────────────────────────────────────────
  http.post(`${BASE}/api/v1/analyze`, async () => {
    await delay(500);
    return HttpResponse.json({ analysis_run_id: "arun_xyz789", status: "queued" });
  }),

  // ── Pipeline runs list (legacy page-based — kept for backward compat) ──────
  http.get(`${BASE}/api/v1/pipeline/runs`, async ({ request }) => {
    const url   = new URL(request.url);
    const page  = Number(url.searchParams.get("page")  ?? 1);
    const limit = Number(url.searchParams.get("limit") ?? 20);
    await delay(200);
    const start = (page - 1) * limit;
    return HttpResponse.json({
      data:  MOCK_PIPELINE_RUNS.slice(start, start + limit),
      total: MOCK_PIPELINE_RUNS.length,
      page,
      limit,
    });
  }),

  // ── F-022 — cursor-paginated history matching the BE envelope shape ────────
  // BE columns: run_id, status, filename, original_size_bytes, mime_type,
  //             detected_language, sheet_count, row_count_bronze,
  //             row_count_silver, quality_score, error_message,
  //             created_at, updated_at.
  http.get(`${BASE}/api/v1/pipelines`, async ({ request }) => {
    const url    = new URL(request.url);
    const limit  = Math.min(Number(url.searchParams.get("limit") ?? 50), 500);
    const cursor = url.searchParams.get("cursor");

    const all = MOCK_PIPELINE_RUNS.map((r, i) => ({
      run_id:              `${r.id}-uuid-${String(i).padStart(2, "0")}`,
      status:              r.status === "done" ? "analysis_complete" :
                           r.status === "processing" ? "analyzing" :
                           r.status,
      filename:            r.original_filename,
      original_size_bytes: 1024 * 1024 * (i + 1),
      mime_type:           "text/csv",
      detected_language:   "vi",
      sheet_count:         1,
      row_count_bronze:    r.row_count,
      row_count_silver:    r.status === "done" ? r.row_count : null,
      quality_score:       r.status === "done" ? 0.94 : null,
      error_message:       r.status === "error" ? "Mock error for demo" : null,
      created_at:          r.created_at,
      updated_at:          r.created_at,
    }));

    const startIdx = cursor ? Number(decodeURIComponent(cursor)) : 0;
    const slice    = all.slice(startIdx, startIdx + limit);
    const hasMore  = startIdx + limit < all.length;

    await delay(200);
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

  // ── F-NEW2 — SSE status stream mock ────────────────────────────────────────
  // MSW supports streaming via ReadableStream. Emits one event then closes
  // so dev UX still updates without faking long-lived SSE.
  http.get(`${BASE}/api/v1/pipelines/:runId/events`, async ({ params }) => {
    const body = `id: ${crypto.randomUUID()}\nevent: status\n`
               + `data: ${JSON.stringify({
                    run_id: params.runId,
                    status: "analysis_complete",
                    updated_at: new Date().toISOString(),
                  })}\n\n`;
    return new HttpResponse(body, {
      headers: {
        "Content-Type":  "text/event-stream",
        "Cache-Control": "no-cache",
      },
    });
  }),
];
