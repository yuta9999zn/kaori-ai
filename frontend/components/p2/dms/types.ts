// ADR-0042 — Confluence-style DMS types (mig 139).

export type FieldKind =
  | 'text' | 'long_text' | 'number' | 'money' | 'date'
  | 'user' | 'department' | 'select' | 'status' | 'link';

export interface FieldDef {
  key: string;
  label_vi: string;
  kind: FieldKind;
  required?: boolean;
  options?: string[];
  default?: string;
  width?: number; // độ rộng cột (px) khi là cột bảng
  // 5-locale labels: label_en / label_ja / label_ko / label_zh (optional).
  [extra: string]: unknown;
}

export interface DocNote {
  note_id: string;
  body_md: string;
  author_id: string | null;
  created_at: string | null;
}

export interface SectionDef {
  key?: string;
  heading_vi: string;
  icon?: string;
  hint_vi?: string;
  body_kind?: 'prose' | 'table' | 'checklist';
  columns?: FieldDef[];
  [extra: string]: unknown;
}

// ── 5-locale label resolution: locale → en → vi (vi authoritative) ──────
export function pickLabel(
  obj: Record<string, unknown> | null | undefined,
  locale: string,
  base = 'label',
): string {
  if (!obj) return '';
  const tryKeys = locale === 'vi'
    ? [`${base}_vi`]
    : [`${base}_${locale}`, `${base}_en`, `${base}_vi`];
  for (const k of tryKeys) {
    const v = obj[k];
    if (typeof v === 'string' && v) return v;
  }
  return String(obj[`${base}_vi`] ?? '');
}

// ── authored document content (mig 140) ────────────────────────────────
export interface LinkVal { text: string; url: string; }

export interface SectionContent {
  key: string;
  heading_vi?: string;
  heading_en?: string;
  body_md?: string;
  rows?: Record<string, unknown>[];
  links?: LinkVal[];
  // bảng tự do (tài liệu không mẫu): cột khai ngay trong content
  columns?: FieldDef[];
}

export interface AuthoredDoc {
  doc_id: string;
  name_vi: string;
  doc_kind: 'file' | 'authored';
  status: string;
  version: number;
  is_current: boolean;
  content: { sections: SectionContent[] };
  template_id: string | null;
  template_name: string | null;
  template_icon: string | null;
  section_outline: SectionDef[];
  metadata_schema: FieldDef[];
  labels: string[];
  metadata: Record<string, unknown>;
  completeness: number | null;
  folder_id: string;
  change_reason: string | null;
  uploaded_at: string | null;
}

export interface DocHistoryRow {
  doc_id: string;
  version: number;
  is_current: boolean;
  change_reason: string | null;
  uploaded_by: string | null;
  uploaded_at: string | null;
}

export interface TemplateDef {
  template_id: string;
  external_ref: string;
  is_global: boolean;
  type_key: string;
  name_vi: string;
  icon: string | null;
  description: string | null;
  metadata_schema: FieldDef[];
  section_outline: SectionDef[];
  default_labels: string[];
  requires_approval: boolean;
  is_active: boolean;
  updated_at: string | null;
}

export interface FolderPageData {
  folder_id: string;
  name_vi: string;
  path: string;
  body_md: string | null;
  default_template_id: string | null;
  sample_file_id: string | null;
  default_labels: string[];
  page_version: number;
  updated_at: string | null;
  effective_template: TemplateDef | null;
  effective_labels: string[];
  template_inherited_from: string | null;
}

export interface PageVersion {
  version_no: number;
  body_md: string | null;
  template_snapshot: { template_id?: string; name_vi?: string } | null;
  sample_file_id: string | null;
  edited_by: string | null;
  edited_at: string | null;
  change_note: string | null;
}

export interface DocRow {
  doc_id: string;
  name_vi: string;
  doc_type: string | null;
  status: string;
  version: number;
  storage_tier: string;
  uploaded_at: string | null;
  doc_date: string | null;
  period_kind: string | null;
  file_id?: string | null;
  template_id?: string | null;
  labels?: string[];
  completeness?: number | null;
  metadata?: Record<string, unknown>;
  doc_kind?: 'file' | 'authored';
  // Cầu Kho ↔ kho dữ liệu: run resolve qua K-8 sha256 (BE lateral join)
  pipeline_run_id?: string | null;
  pipeline_run_status?: string | null;
}

export interface IndexRow extends DocRow {
  external_ref: string;
  folder_id: string;
  path: string;
  metadata: Record<string, unknown>;
  labels: string[];
}

export interface InsightData {
  insight_id: string;
  scope_kind: 'group' | 'folder';
  status: 'pending' | 'running' | 'complete' | 'failed';
  doc_count: number | null;
  model: string | null;
  stats: Record<string, any>;
  summary: string | null;
  findings: { title: string; detail: string }[];
  error: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface EnterpriseUser {
  id: string;
  name: string;
  email: string;
}

// Status lozenge tone — generic heuristic, KHÔNG hardcode per-template:
// first option = chưa bắt đầu (gray) · last = hoàn tất (green) · giữa = đang chạy (amber).
export function statusTone(value: string, options: string[] = []): 'gray' | 'amber' | 'green' {
  const i = options.indexOf(value);
  if (i < 0 || options.length < 2) return 'gray';
  if (i === options.length - 1) return 'green';
  return i === 0 ? 'gray' : 'amber';
}

export const TONE_CLS: Record<'gray' | 'amber' | 'green', string> = {
  gray: 'bg-slate-100 text-slate-600 border-slate-200',
  amber: 'bg-amber-50 text-amber-700 border-amber-200',
  green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

export function statusLabel(v: string): string {
  return v.replace(/_/g, ' ');
}

// ── Độ rộng cột: 4 mức chọn sẵn, an toàn trên PC/laptop/mobile ──────────
// (bảng luôn nằm trong khung cuộn ngang; minWidth giữ cột không bị bóp nát)
export const WIDTH_PRESETS: { value: number | undefined; label: string }[] = [
  { value: undefined, label: 'Tự động' },
  { value: 90, label: 'Hẹp' },
  { value: 160, label: 'Vừa' },
  { value: 280, label: 'Rộng' },
  { value: 420, label: 'Rất rộng' },
];

// ── Bộ cột chuẩn cho bảng tự do — chọn thay vì gõ tuỳ ý ────────────────
export const COLUMN_PRESETS: FieldDef[] = [
  { key: 'ma', label_vi: 'Mã', label_en: 'Code', kind: 'text', width: 90 },
  { key: 'ten', label_vi: 'Tên', label_en: 'Name', kind: 'text', width: 160 },
  { key: 'mo_ta', label_vi: 'Mô tả', label_en: 'Description', kind: 'long_text', width: 280 },
  { key: 'ngay', label_vi: 'Ngày', label_en: 'Date', kind: 'date', width: 90 },
  { key: 'so_luong', label_vi: 'Số lượng', label_en: 'Quantity', kind: 'number', width: 90 },
  { key: 'so_tien', label_vi: 'Số tiền', label_en: 'Amount', kind: 'money', width: 160 },
  { key: 'nguoi_phu_trach', label_vi: 'Người phụ trách', label_en: 'Owner', kind: 'user', width: 160 },
  { key: 'link', label_vi: 'Link', label_en: 'Link', kind: 'link', width: 160 },
  { key: 'ghi_chu', label_vi: 'Ghi chú', label_en: 'Note', kind: 'long_text', width: 280 },
];
