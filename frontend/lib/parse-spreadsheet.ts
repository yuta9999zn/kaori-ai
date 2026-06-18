/**
 * Client-side spreadsheet parser.
 * Reads Excel / CSV / TSV / ODS via SheetJS, returns column profiles +
 * language/purpose hints for the backend schema-review step.
 *
 * Max 200 rows parsed client-side (preview only — backend processes full file).
 */
import * as XLSX from "xlsx";

// ── Public types ──────────────────────────────────────────────────────────────

export type ColType =
  | "date"
  | "integer"
  | "decimal"
  | "currency"
  | "boolean"
  | "category"
  | "text"
  | "unknown";

export type LangCode = "VI" | "EN" | "JA" | "KO" | "ZH";

export type PurposeHint =
  | "transaction_list"
  | "bank_statement"
  | "customer_master"
  | "product_catalog"
  | "time_series_metrics"
  | "unknown";

export interface ColumnProfile {
  name: string;
  detected_type: ColType;
  null_rate: number;          // 0–1
  sample_values: string[];    // up to 5 non-null values
  unique_count: number;
}

export interface SheetProfile {
  sheet_name: string;
  row_count: number;
  columns: ColumnProfile[];
  language_hint: LangCode;
  purpose_hint: PurposeHint;
}

export interface ParseResult {
  sheets: SheetProfile[];
  primary_language: LangCode;
  primary_purpose: PurposeHint;
  parse_error?: string;
}

// ── Entry point ───────────────────────────────────────────────────────────────

export async function parseSpreadsheet(file: File): Promise<ParseResult> {
  try {
    const buffer = await file.arrayBuffer();
    const workbook = readWorkbook(file.name, buffer);
    const sheets = workbook.SheetNames.map((name) =>
      profileSheet(name, workbook.Sheets[name])
    );

    const primary_language = majorityLang(sheets.map((s) => s.language_hint));
    const primary_purpose =
      sheets.find((s) => s.purpose_hint !== "unknown")?.purpose_hint ?? "unknown";

    return { sheets, primary_language, primary_purpose };
  } catch (err: unknown) {
    return {
      sheets: [],
      primary_language: "EN",
      primary_purpose: "unknown",
      parse_error: (err as Error).message ?? "Unknown parse error",
    };
  }
}

// ── Workbook reading ──────────────────────────────────────────────────────────

function readWorkbook(filename: string, buffer: ArrayBuffer): XLSX.WorkBook {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const data = new Uint8Array(buffer);

  if (ext === "csv") {
    return XLSX.read(data, { type: "array", raw: false, dateNF: "yyyy-mm-dd" });
  }
  if (ext === "tsv") {
    const text = new TextDecoder().decode(data);
    return XLSX.read(text, { type: "string", FS: "\t", dateNF: "yyyy-mm-dd" });
  }
  // xlsx / xlsm / xlsb / xls / ods / zip
  return XLSX.read(data, {
    type: "array",
    cellDates: true,
    dateNF: "yyyy-mm-dd",
    sheetStubs: false,
  });
}

// ── Sheet profiling ───────────────────────────────────────────────────────────

const PREVIEW_ROWS = 200;

function profileSheet(name: string, ws: XLSX.WorkSheet): SheetProfile {
  const rows: Record<string, unknown>[] = XLSX.utils.sheet_to_json(ws, {
    defval: null,
    raw: false,
    dateNF: "yyyy-mm-dd",
  });

  const preview = rows.slice(0, PREVIEW_ROWS);
  const headers = preview.length > 0 ? Object.keys(preview[0]) : [];

  const columns: ColumnProfile[] = headers.map((h) =>
    profileColumn(h, preview)
  );

  const language_hint = detectLanguage(headers);
  const purpose_hint = detectPurpose(columns);

  return {
    sheet_name: name,
    row_count: rows.length,
    columns,
    language_hint,
    purpose_hint,
  };
}

function profileColumn(
  name: string,
  rows: Record<string, unknown>[]
): ColumnProfile {
  const values = rows.map((r) => r[name]);
  const nonNull = values.filter((v) => v !== null && v !== undefined && v !== "");
  const nullRate = rows.length > 0 ? 1 - nonNull.length / rows.length : 0;

  const sample = nonNull
    .slice(0, 10)
    .map(String)
    .filter((v, i, a) => a.indexOf(v) === i) // deduplicate
    .slice(0, 5);

  const uniqueCount = new Set(nonNull.map(String)).size;
  const detected_type = detectType(name, nonNull, uniqueCount);

  return {
    name,
    detected_type,
    null_rate: Math.round(nullRate * 1000) / 1000,
    sample_values: sample,
    unique_count: uniqueCount,
  };
}

// ── Type detection ────────────────────────────────────────────────────────────

const RE_DATE = /^\d{4}[-/]\d{1,2}[-/]\d{1,2}([ T]\d{2}:\d{2})?|^\d{1,2}[-/]\d{1,2}[-/]\d{4}/;
const RE_NUM = /^-?[\d,. ]+$/;
const BOOL_VALS = new Set(["true","false","yes","no","có","không","1","0","y","n"]);

function detectType(
  colName: string,
  nonNull: unknown[],
  uniqueCount: number
): ColType {
  if (nonNull.length === 0) return "unknown";

  const name = colName.toLowerCase();
  const sample = nonNull.slice(0, 50).map(String);

  // Date — check by SheetJS Date objects or ISO string patterns
  const dateMatches = sample.filter(
    (v) => RE_DATE.test(v) || nonNull[sample.indexOf(v)] instanceof Date
  );
  if (dateMatches.length / sample.length >= 0.7) return "date";

  // Boolean
  const boolMatches = sample.filter((v) => BOOL_VALS.has(v.toLowerCase()));
  if (boolMatches.length / sample.length >= 0.8 && uniqueCount <= 3) return "boolean";

  // Numeric analysis
  const stripped = sample.map((v) => v.replace(/[,. ₫$€£¥,]/g, "").replace(/\s/g, ""));
  const numMatches = stripped.filter((v) => v !== "" && !isNaN(Number(v)));
  if (numMatches.length / sample.length >= 0.8) {
    const nums = numMatches.map(Number);
    const avg = nums.reduce((a, b) => a + b, 0) / nums.length;
    const hasDecimal = sample.some((v) => /[.,]\d{1,2}$/.test(v) && !/^\d{4}[-/]/.test(v));

    // Currency heuristic: money-related column name OR large numbers
    const isMoneyCols = /amount|so_tien|tien|doanh|revenue|price|gia|balance|du_no|credit|debit|total|tong/
      .test(name);
    if (isMoneyCols || avg > 10000) return "currency";
    if (hasDecimal) return "decimal";
    return "integer";
  }

  // Category — low cardinality string
  if (uniqueCount <= Math.min(20, nonNull.length * 0.3)) return "category";

  return "text";
}

// ── Language detection ────────────────────────────────────────────────────────

const VI_MARKERS = /[đĐàáâãèéêìíòóôõùúýăắặằẳẵấầẩẫậéếệềểễ]/i;
const VI_KEYWORDS = /\b(ma|ten|ngay|khach|hang|san_pham|doanh_thu|chi_nhanh|gio|thang|nam)\b/i;
const JA_RE = /[぀-ゟ゠-ヿ]/;
const KO_RE = /[가-힣ᄀ-ᇿ]/;
const ZH_RE = /[一-鿿㐀-䶿]/;

function detectLanguage(headers: string[]): LangCode {
  const text = headers.join(" ");
  if (JA_RE.test(text)) return "JA";
  if (KO_RE.test(text)) return "KO";
  if (ZH_RE.test(text)) return "ZH";
  if (VI_MARKERS.test(text) || VI_KEYWORDS.test(text)) return "VI";
  return "EN";
}

// ── Purpose detection ─────────────────────────────────────────────────────────

function detectPurpose(cols: ColumnProfile[]): PurposeHint {
  const names = cols.map((c) => c.name.toLowerCase());
  const types = cols.map((c) => c.detected_type);

  const hasDate     = types.includes("date");
  const hasAmount   = names.some((n) => /amount|so_tien|credit|debit|tien|balance|du_no/.test(n));
  const hasCustomer = names.some((n) => /customer|khach|cust_id|ma_khach/.test(n));
  const hasDesc     = names.some((n) => /description|narration|mo_ta|noi_dung|detail/.test(n));
  const hasBalance  = names.some((n) => /balance|du_no/.test(n));
  const hasProduct  = names.some((n) => /product|san_pham|item|sku|hang_hoa/.test(n));
  const hasPrice    = names.some((n) => /price|gia|unit_price|don_gia/.test(n));
  const numericCols = types.filter((t) => ["integer","decimal","currency"].includes(t)).length;

  if (hasBalance && hasDesc) return "bank_statement";
  if (hasDate && hasAmount && hasCustomer) return "transaction_list";
  if (hasDate && hasAmount && !hasCustomer) return "transaction_list";
  if (hasCustomer && !hasAmount) return "customer_master";
  if (hasProduct && hasPrice) return "product_catalog";
  if (hasDate && numericCols >= 2) return "time_series_metrics";
  return "unknown";
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function majorityLang(langs: LangCode[]): LangCode {
  const counts: Record<string, number> = {};
  for (const l of langs) counts[l] = (counts[l] ?? 0) + 1;
  return (Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "EN") as LangCode;
}
