// Vietnamese error/success/info message catalog.
//
// Source: docs/specs/MESSAGE_DEFINITIONS.md (PDF v1.0.3 — 28 Aug 2025).
// Used by FE components to render user-facing messages with consistent
// tone, terminology, and error-code attribution (X-Request-ID for
// support escalation).
//
// Add new messages here ONLY when the source PDF adds a row. Do NOT
// invent codes on the fly.

// ─── System errors (toast — technical/infra) ────────────────────────

export const SYS_ERR_GENERIC =
  'Hệ thống đang trong quá trình bảo trì. Vui lòng quay lại sau ít phút.';

export const SYS_ERRORS = {
  'SYS-ERR1': 'Không kết nối được máy chủ. Kiểm tra mạng.',
  'SYS-ERR2': 'Máy chủ phản hồi quá lâu. Vui lòng thử lại.',
  'SYS-ERR3': 'Máy chủ nội bộ gặp sự cố.',
  'SYS-ERR4': 'Lỗi không xác định khi xử lý.',
  'SYS-ERR5': 'Cạn kiệt bộ nhớ / tài nguyên.',
} as const;

// ─── User errors (inline — input/auth/business) ─────────────────────

export const USR_ERRORS = {
  'USR-ERR1': 'Thông tin đăng nhập không chính xác.',
  'USR-ERR2': 'Không tìm thấy dữ liệu phù hợp.',
  'USR-ERR3': (field: string) => `Vui lòng nhập ${field}.`,
  'USR-ERR4': (field: string) => `${field}: định dạng dữ liệu không hợp lệ.`,
  'USR-ERR5': (field: string, min: number, max: number) =>
    min > 0
      ? `${field} phải có độ dài từ ${min} đến ${max} ký tự.`
      : `${field} không được vượt quá ${max} ký tự.`,
  'USR-ERR6': (field: string) => `${field} đã tồn tại trong hệ thống.`,
  'USR-ERR7': (field: string) => `Giá trị nhập vào ${field} nằm ngoài phạm vi cho phép.`,
  'USR-ERR8': (startField: string, endField: string) =>
    `${startField} phải diễn ra trước ${endField}.`,
  'USR-ERR9': (field: string) => `${field} đã được cập nhật. Vui lòng tải lại trang.`,
  'USR-ERR10': 'Không được phép nhập khoảng trống.',
} as const;

// ─── Business errors (per-feature) ──────────────────────────────────

export const BIZ_ERRORS: Record<string, string> = {
  // RAG router whitelist excluded all engines (P15-S10 R1).
  'BIZ-ERR1': 'Không có engine RAG nào khả dụng với cấu hình hiện tại.',
  // Workflow cross-link cross-workspace (Vingroup-class).
  'BIZ-ERR2': 'Liên kết workflow xuyên tập đoàn chưa được hỗ trợ.',
  // Department in different workspace.
  'BIZ-ERR3': 'Phòng ban được chọn nằm ngoài tập đoàn hiện tại.',
  // EU AI Act — workflow uses a prohibited-tier AI capability (Art 5).
  'COMPLIANCE.PROHIBITED_USE':
    'Quy trình này bị chặn vì thuộc nhóm bị cấm theo EU AI Act. Liên hệ quản trị để phân loại lại.',
  // EU AI Act — workflow not yet risk-classified before activation.
  'COMPLIANCE.NOT_CLASSIFIED':
    'Quy trình chưa được phân loại rủi ro. Vui lòng phân loại trước khi kích hoạt.',
};

// ─── Success / info / confirmation ───────────────────────────────────

export const SUCCESS = {
  workflow_created:    'Đã tạo workflow.',
  workflow_updated:    'Đã lưu thay đổi.',
  workflow_deleted:    'Đã xoá workflow.',
  node_added:          'Đã thêm bước.',
  node_deleted:        'Đã xoá bước.',
  edge_added:          'Đã nối hai bước.',
  template_cloned:     'Đã tạo workflow từ template.',
  cross_link_created:  'Đã tạo liên kết workflow.',
  folder_created:      'Đã tạo folder.',
  enterprise_moved:    'Đã di chuyển công ty sang mảng mới.',
  file_uploaded:       'Đã tải lên tệp.',
};

// ─── ProblemDetails → user-facing message ────────────────────────────

export interface ProblemLike {
  status?: number;
  title?: string;
  detail?: string;
  code?: string;
  type?: string;
}

/** Map a backend ProblemDetails into a Vietnamese user-facing message.
 *
 *  Priority:
 *   1. Explicit code field (SYS-ERRn / USR-ERRn / BIZ-ERRn) — use catalog.
 *   2. HTTP status 5xx → SYS-ERR3 generic.
 *   3. HTTP status 404 → USR-ERR2 generic.
 *   4. HTTP status 401/403 → USR-ERR1 / "no permission".
 *   5. Fall back to problem.detail or problem.title verbatim.
 */
export function formatProblem(p: ProblemLike | null | undefined): string {
  if (!p) return SYS_ERR_GENERIC;

  const code = p.code || '';
  if (code in SYS_ERRORS) {
    return (SYS_ERRORS as Record<string, string>)[code];
  }
  if (code in BIZ_ERRORS) {
    return BIZ_ERRORS[code];
  }
  // USR-ERR* need parameters, surface verbatim detail if BE provided one.
  if (code.startsWith('USR-ERR') && p.detail) {
    return p.detail;
  }

  const status = p.status ?? 0;
  if (status >= 500) return SYS_ERRORS['SYS-ERR3'];
  if (status === 408 || status === 504) return SYS_ERRORS['SYS-ERR2'];
  if (status === 404) return USR_ERRORS['USR-ERR2'];
  if (status === 401) return USR_ERRORS['USR-ERR1'];
  if (status === 403) return 'Bạn không có quyền thực hiện thao tác này.';
  if (status === 429) return 'Bạn đang thao tác quá nhanh. Vui lòng đợi vài giây.';

  return p.detail || p.title || SYS_ERR_GENERIC;
}
