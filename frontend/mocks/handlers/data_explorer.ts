import { http, HttpResponse, delay } from "msw";

// MSW handler for F-NEW3 Data Explorer hub overview — mirrors the
// shape of GET /api/v1/data/explorer (data-pipeline router
// data_explorer.py). Lets /p2/data render end-to-end in dev mode
// without needing the data-pipeline service or Postgres in the loop.

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

const days = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();

const SNAPSHOT = {
  bronze: {
    file_count:        42,
    row_count_total:   158_204,
    size_gb:           2.7,
    last_ingested_at:  days(0.04),     // ~1h ago
    failed_24h:        1,
  },
  silver: {
    dataset_count:     12,
    row_count_total:   154_900,        // some bronze rows dropped during clean
    quality_avg_pct:   92.4,
    last_processed_at: days(0.5),      // 12h ago
  },
  gold: {
    feature_count:     320,
    row_count_total:   320,            // 1-to-1 customer
    last_aggregated_at: days(1),       // 24h ago
    stale_count:       3,
  },
  recent: [
    {
      id:     "11111111-1111-1111-1111-111111111111",
      layer:  "gold",
      name:   "sales-q1-2026.csv",
      action: "Đã tổng hợp",
      at:     days(1),
      status: "ok",
    },
    {
      id:     "22222222-2222-2222-2222-222222222222",
      layer:  "silver",
      name:   "customers-export.xlsx",
      action: "Đã làm sạch",
      at:     days(0.5),
      status: "ok",
    },
    {
      id:     "33333333-3333-3333-3333-333333333333",
      layer:  "bronze",
      name:   "inventory-march.csv",
      action: "Đã ingest",
      at:     days(0.1),
      status: "ok",
    },
    {
      id:     "44444444-4444-4444-4444-444444444444",
      layer:  "bronze",
      name:   "broken-encoding.csv",
      action: "Thất bại",
      at:     days(0.04),
      status: "fail",
    },
    {
      id:     "55555555-5555-5555-5555-555555555555",
      layer:  "silver",
      name:   "orders-april.parquet",
      action: "Đang xác nhận schema",
      at:     days(0.02),
      status: "running",
    },
  ],
};

// ============================================================================
// F-NEW3 v1 — Bronze drill-down fixtures
// ============================================================================

interface MockBronzeFile {
  file_id:           string;
  run_id:            string;
  source_filename:   string;
  run_status:        string;
  sheet_name:        string | null;
  sheet_index:       number;
  detected_purpose:  string | null;
  detected_language: string | null;
  row_count:         number;
  col_count:         number;
  file_format:       string;
  created_at:        string;
}

const BRONZE_FILES: MockBronzeFile[] = [
  {
    file_id: "11111111-1111-1111-1111-111111111111",
    run_id:  "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    source_filename: "sales-q1-2026.csv",
    run_status: "analysis_complete",
    sheet_name: null, sheet_index: 0,
    detected_purpose: "orders", detected_language: "vi",
    row_count: 12_400, col_count: 8, file_format: "csv",
    created_at: days(1),
  },
  {
    file_id: "22222222-2222-2222-2222-222222222222",
    run_id:  "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    source_filename: "customers-export.xlsx",
    run_status: "silver_complete",
    sheet_name: "Customers", sheet_index: 0,
    detected_purpose: "customers", detected_language: "vi",
    row_count: 3_280, col_count: 12, file_format: "xlsx",
    created_at: days(0.5),
  },
  {
    file_id: "33333333-3333-3333-3333-333333333333",
    run_id:  "cccccccc-cccc-cccc-cccc-cccccccccccc",
    source_filename: "inventory-march.csv",
    run_status: "bronze_complete",
    sheet_name: null, sheet_index: 0,
    detected_purpose: "inventory", detected_language: "vi",
    row_count: 8_950, col_count: 6, file_format: "csv",
    created_at: days(0.1),
  },
  {
    file_id: "44444444-4444-4444-4444-444444444444",
    run_id:  "dddddddd-dddd-dddd-dddd-dddddddddddd",
    source_filename: "broken-encoding.csv",
    run_status: "failed",
    sheet_name: null, sheet_index: 0,
    detected_purpose: null, detected_language: null,
    row_count: 0, col_count: 0, file_format: "csv",
    created_at: days(0.04),
  },
  {
    file_id: "55555555-5555-5555-5555-555555555555",
    run_id:  "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    source_filename: "orders-april.parquet",
    run_status: "schema_review",
    sheet_name: null, sheet_index: 0,
    detected_purpose: "orders", detected_language: "vi",
    row_count: 5_120, col_count: 9, file_format: "parquet",
    created_at: days(0.02),
  },
];

// Per-file sample rows. We synthesise a deterministic 50-row sample
// based on the file's purpose so the FE can render meaningful columns.
function bronzeSample(file: MockBronzeFile, limit: number) {
  const cap = Math.min(file.row_count, limit);
  const rows: Array<{ row_index: number; raw_data: any; row_hash: string; created_at: string }> = [];

  if (file.detected_purpose === "orders") {
    for (let i = 0; i < cap; i++) {
      rows.push({
        row_index: i,
        raw_data: {
          order_id:    `ORD-${String(2026000 + i).padStart(7, "0")}`,
          customer:    `Khách ${i + 1}`,
          amount_vnd:  Math.round(50_000 + Math.random() * 4_950_000),
          paid_at:     days(2 + i / 50),
          status:      i % 7 === 0 ? "refunded" : "paid",
        },
        row_hash:   `h${i.toString(16).padStart(6, "0")}`,
        created_at: file.created_at,
      });
    }
  } else if (file.detected_purpose === "customers") {
    for (let i = 0; i < cap; i++) {
      rows.push({
        row_index: i,
        raw_data: {
          customer_external_id: `CUST-${String(1000 + i).padStart(5, "0")}`,
          name:                 `Khách hàng ${i + 1}`,
          email:                `<EMAIL_${i + 1}>`,    // K-5 PII placeholder
          phone:                `<PHONE_${i + 1}>`,
          city:                 ["Hà Nội", "TPHCM", "Đà Nẵng", "Hải Phòng", "Cần Thơ"][i % 5],
          signup_at:            days(60 + i),
        },
        row_hash:   `h${i.toString(16).padStart(6, "0")}`,
        created_at: file.created_at,
      });
    }
  } else if (file.detected_purpose === "inventory") {
    for (let i = 0; i < cap; i++) {
      rows.push({
        row_index: i,
        raw_data: {
          sku:        `SKU-${String(8000 + i).padStart(5, "0")}`,
          name:       `Sản phẩm ${i + 1}`,
          stock_qty:  Math.round(Math.random() * 500),
          unit_price: Math.round(10_000 + Math.random() * 990_000),
        },
        row_hash:   `h${i.toString(16).padStart(6, "0")}`,
        created_at: file.created_at,
      });
    }
  } else {
    // Generic fallback (failed / unknown purpose) — show raw shape.
    for (let i = 0; i < cap; i++) {
      rows.push({
        row_index: i,
        raw_data: { col_a: `value-${i}`, col_b: i, col_c: i % 2 === 0 },
        row_hash:   `h${i.toString(16).padStart(6, "0")}`,
        created_at: file.created_at,
      });
    }
  }
  return rows;
}

function problem(status: number, type: string, title: string, detail: string) {
  return new HttpResponse(JSON.stringify({ type, title, status, detail }), {
    status,
    headers: { "Content-Type": "application/problem+json" },
  });
}

function encodeCursor(createdAt: string, fileId: string): string {
  return btoa(`${createdAt}|${fileId}`)
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
function decodeCursor(cursor: string): [string, string] | null {
  try {
    const padded = cursor.replace(/-/g, "+").replace(/_/g, "/")
      + "=".repeat((-cursor.length) & 3);
    const [ts, id] = atob(padded).split("|", 2);
    return [ts, id];
  } catch { return null; }
}

export const dataExplorerHandlers = [
  http.get(`${BASE}/api/v1/data/explorer`, async () => {
    await delay(80);
    return HttpResponse.json(SNAPSHOT);
  }),

  // ── Bronze files list ───────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/data/bronze/files`, async ({ request }) => {
    const url    = new URL(request.url);
    const limit  = Math.max(1, Math.min(500, Number(url.searchParams.get("limit") ?? 50)));
    const cursor = url.searchParams.get("cursor");

    let filtered = [...BRONZE_FILES];
    // Sort matches BE: created_at DESC, file_id DESC.
    filtered.sort((a, b) => b.created_at.localeCompare(a.created_at)
                          || b.file_id.localeCompare(a.file_id));

    if (cursor) {
      const decoded = decodeCursor(cursor);
      if (!decoded) return problem(400, "/docs/errors/invalid-cursor", "Invalid cursor", cursor);
      const [cursorTs, cursorId] = decoded;
      filtered = filtered.filter((f) => {
        if (f.created_at !== cursorTs) return f.created_at < cursorTs;
        return f.file_id < cursorId;
      });
    }

    const items   = filtered.slice(0, limit);
    const hasMore = filtered.length > limit;
    const next    = hasMore && items.length > 0
      ? encodeCursor(items[items.length - 1].created_at, items[items.length - 1].file_id)
      : null;

    await delay(80);
    return HttpResponse.json({
      data: items,
      meta: { cursor: next, limit, count: items.length, has_more: hasMore },
    });
  }),

  // ── Bronze sample ───────────────────────────────────────────────────────
  http.get(`${BASE}/api/v1/data/bronze/files/:fileId/sample`, async ({ params, request }) => {
    const id    = String(params.fileId);
    const url   = new URL(request.url);
    const limit = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") ?? 50)));

    const file = BRONZE_FILES.find((f) => f.file_id === id);
    if (!file) return problem(404, "/docs/errors/bronze-file-not-found",
                                "Bronze file not found", `Bronze file not found: ${id}`);

    await delay(100);
    return HttpResponse.json({
      data: {
        file: {
          file_id:         file.file_id,
          sheet_name:      file.sheet_name,
          row_count:       file.row_count,
          col_count:       file.col_count,
          file_format:     file.file_format,
          source_filename: file.source_filename,
          created_at:      file.created_at,
        },
        rows:  bronzeSample(file, limit),
        limit,
      },
    });
  }),

  // ── Silver datasets list ────────────────────────────────────────────────
  // Synthesise a silver dataset for each non-failed bronze file. Cleaned
  // row count = bronze rows minus a small drop_rate to mimic the
  // "removed empty rows" cleaning step.
  http.get(`${BASE}/api/v1/data/silver/datasets`, async ({ request }) => {
    const url   = new URL(request.url);
    const limit = Math.max(1, Math.min(500, Number(url.searchParams.get("limit") ?? 50)));
    const cursor = url.searchParams.get("cursor");

    let datasets = BRONZE_FILES
      .filter((f) => f.run_status !== "failed" && f.run_status !== "uploading")
      .map((f) => ({
        file_id:            f.file_id,
        source_filename:    f.source_filename,
        sheet_name:         f.sheet_name,
        run_status:         f.run_status,
        row_count:          Math.round(f.row_count * 0.97),
        col_count:          f.col_count,
        quality_avg_pct:    Math.round((85 + Math.random() * 14) * 10) / 10,
        first_processed_at: f.created_at,
        last_processed_at:  f.created_at,
        applied_rules_top: [
          { rule_id: "trim_whitespace", rule_category: "UNIVERSAL", rows_affected: f.row_count },
          { rule_id: "parse_date",      rule_category: "BY_TYPE",   rows_affected: Math.round(f.row_count * 0.6) },
          { rule_id: "redact_pii",      rule_category: "AI_DETECTED", rows_affected: Math.round(f.row_count * 0.2) },
        ],
      }));

    datasets.sort((a, b) => b.last_processed_at.localeCompare(a.last_processed_at)
                          || b.file_id.localeCompare(a.file_id));

    if (cursor) {
      const decoded = decodeCursor(cursor);
      if (!decoded) return problem(400, "/docs/errors/invalid-cursor", "Invalid cursor", cursor);
      const [cursorTs, cursorId] = decoded;
      datasets = datasets.filter((d) => {
        if (d.last_processed_at !== cursorTs) return d.last_processed_at < cursorTs;
        return d.file_id < cursorId;
      });
    }

    const items   = datasets.slice(0, limit);
    const hasMore = datasets.length > limit;
    const next    = hasMore && items.length > 0
      ? encodeCursor(items[items.length - 1].last_processed_at, items[items.length - 1].file_id)
      : null;

    await delay(80);
    return HttpResponse.json({
      data: items,
      meta: { cursor: next, limit, count: items.length, has_more: hasMore },
    });
  }),

  // ── Silver sample ───────────────────────────────────────────────────────
  // Returns the same synthesised rows as bronzeSample but with all PII
  // fields replaced by K-5 placeholders, plus per-row applied_rules + quality_score.
  http.get(`${BASE}/api/v1/data/silver/datasets/:fileId/sample`, async ({ params, request }) => {
    const id    = String(params.fileId);
    const url   = new URL(request.url);
    const limit = Math.max(1, Math.min(200, Number(url.searchParams.get("limit") ?? 50)));

    const file = BRONZE_FILES.find((f) => f.file_id === id);
    if (!file || file.run_status === "failed") {
      return problem(404, "/docs/errors/silver-dataset-not-found",
                       "Silver dataset not found",
                       `Silver dataset not found (or never cleaned): ${id}`);
    }

    const bronzeRows = bronzeSample(file, limit);
    const silverRows = bronzeRows.map((r) => {
      // PII redaction simulation — replace email/phone/name with placeholders
      // even if the bronze fixture didn't already have them.
      const cleaned: Record<string, unknown> = { ...(r.raw_data as Record<string, unknown>) };
      if ("email" in cleaned) cleaned.email = `<EMAIL_${r.row_index + 1}>`;
      if ("phone" in cleaned) cleaned.phone = `<PHONE_${r.row_index + 1}>`;
      if ("name"  in cleaned && typeof cleaned.name === "string") {
        cleaned.name = `<NAME_${r.row_index + 1}>`;
      }
      return {
        row_index:     r.row_index,
        clean_data:    cleaned,
        applied_rules: ["trim_whitespace", "parse_date", "redact_pii"].slice(0, 1 + (r.row_index % 3)),
        quality_score: 0.85 + ((r.row_index % 15) / 100),
        created_at:    r.created_at,
      };
    });

    await delay(100);
    return HttpResponse.json({
      data: {
        file: {
          file_id:           file.file_id,
          sheet_name:        file.sheet_name,
          row_count:         Math.round(file.row_count * 0.97),
          col_count:         file.col_count,
          file_format:       file.file_format,
          source_filename:   file.source_filename,
          last_processed_at: file.created_at,
        },
        rows:  silverRows,
        limit,
      },
    });
  }),

  // ── Lineage trace ───────────────────────────────────────────────────────
  // Synthesise a 3-layer chain for any known bronze fixture file. Gold
  // link is null for "broken-encoding" + "inventory" (no customer key);
  // present for everything else.
  http.get(`${BASE}/api/v1/data/lineage`, async ({ request }) => {
    const url     = new URL(request.url);
    const fileId  = url.searchParams.get("file_id");
    if (!fileId) {
      return problem(422, "/docs/errors/missing-file-id",
                       "file_id required", "file_id query param is required");
    }

    const file = BRONZE_FILES.find((f) => f.file_id === fileId);
    if (!file) {
      return problem(404, "/docs/errors/bronze-file-not-found",
                       "Bronze file not found", `Bronze file not found: ${fileId}`);
    }

    const isFailed       = file.run_status === "failed";
    const hasCustomerKey = file.detected_purpose === "customers"
                        || file.detected_purpose === "orders";

    const silver = isFailed ? null : {
      row_count:           Math.round(file.row_count * 0.97),
      quality_avg_pct:     Math.round((85 + Math.random() * 14) * 10) / 10,
      first_processed_at:  file.created_at,
      last_processed_at:   file.created_at,
      applied_rules_top: [
        { rule_id: "trim_whitespace", rule_category: "UNIVERSAL",   rows_affected: file.row_count },
        { rule_id: "parse_date",      rule_category: "BY_TYPE",     rows_affected: Math.round(file.row_count * 0.6) },
        { rule_id: "redact_pii",      rule_category: "AI_DETECTED", rows_affected: Math.round(file.row_count * 0.2) },
      ],
    };

    const gold = (isFailed || !hasCustomerKey) ? null : {
      linked_customer_count:    Math.round(file.row_count * 0.04),
      silver_rows_with_key:     Math.round(file.row_count * 0.97),
      distinct_ids_in_silver:   Math.round(file.row_count * 0.05),
      customer_id_key:          "customer_external_id",
    };

    await delay(80);
    return HttpResponse.json({
      data: {
        bronze: {
          file_id:           file.file_id,
          run_id:            file.run_id,
          source_filename:   file.source_filename,
          run_status:        file.run_status,
          uploaded_by:       "user-mock-001",
          sheet_name:        file.sheet_name,
          sheet_index:       file.sheet_index,
          detected_purpose:  file.detected_purpose,
          detected_language: file.detected_language,
          row_count:         file.row_count,
          col_count:         file.col_count,
          file_format:       file.file_format,
          ingested_at:       file.created_at,
          run_row_count_bronze: file.row_count,
          run_row_count_silver: silver?.row_count ?? null,
          run_quality_score:    silver ? silver.quality_avg_pct / 100 : null,
        },
        silver,
        gold,
      },
    });
  }),

  // ── Gold customers list ─────────────────────────────────────────────────
  // Synthesise 12 gold_features rows so the FE can paginate (≥ default
  // page size of 50 isn't necessary — analyst seldom scrolls past page 1
  // in dev mode). actioned filter is honoured.
  http.get(`${BASE}/api/v1/data/gold/customers`, async ({ request }) => {
    const url      = new URL(request.url);
    const limit    = Math.max(1, Math.min(500, Number(url.searchParams.get("limit") ?? 50)));
    const cursor   = url.searchParams.get("cursor");
    const actioned = url.searchParams.get("actioned");

    interface MockGold {
      customer_external_id: string;
      revenue_at_risk:      number;
      last_purchase_at:     string | null;
      total_purchases:      number | null;
      purchase_count:       number;
      avg_purchase_value:   number | null;
      is_actioned:          boolean;
      actioned_at:          string | null;
      computed_at:          string;
    }

    const NOW = days(0.04);   // ~1h ago
    const seedGold: MockGold[] = [];
    for (let i = 0; i < 12; i++) {
      const isAtRisk = i % 3 === 0;
      seedGold.push({
        customer_external_id: `CUST-${String(1000 + i).padStart(5, "0")}`,
        revenue_at_risk:      isAtRisk ? Math.round(50_000_000 + Math.random() * 950_000_000) : 0,
        last_purchase_at:     isAtRisk ? days(60 + i * 2) : days(5 + i),
        total_purchases:      Math.round(5_000_000 + Math.random() * 95_000_000),
        purchase_count:       2 + i,
        avg_purchase_value:   Math.round(100_000 + Math.random() * 4_900_000),
        is_actioned:          i % 5 === 0,
        actioned_at:          i % 5 === 0 ? days(2) : null,
        computed_at:          NOW,
      });
    }

    let filtered = seedGold;
    if (actioned === "true")  filtered = filtered.filter((c) =>  c.is_actioned);
    if (actioned === "false") filtered = filtered.filter((c) => !c.is_actioned);
    filtered.sort((a, b) => b.computed_at.localeCompare(a.computed_at)
                          || b.customer_external_id.localeCompare(a.customer_external_id));

    if (cursor) {
      const decoded = decodeCursor(cursor);
      if (!decoded) return problem(400, "/docs/errors/invalid-cursor", "Invalid cursor", cursor);
      const [cursorTs, cursorId] = decoded;
      filtered = filtered.filter((c) => {
        if (c.computed_at !== cursorTs) return c.computed_at < cursorTs;
        return c.customer_external_id < cursorId;
      });
    }

    const items   = filtered.slice(0, limit);
    const hasMore = filtered.length > limit;
    const next    = hasMore && items.length > 0
      ? encodeCursor(items[items.length - 1].computed_at,
                     items[items.length - 1].customer_external_id)
      : null;

    await delay(80);
    return HttpResponse.json({
      data: items,
      meta: { cursor: next, limit, count: items.length, has_more: hasMore },
    });
  }),
];
