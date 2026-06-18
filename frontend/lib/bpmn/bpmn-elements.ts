// ============================================================================
// BPMN ↔ Kaori execution catalog  (Approach A — one model, config panel)
// ----------------------------------------------------------------------------
// Per WORKFLOW_BUILDER_REDESIGN.md §11.2 (anh chốt 2026-05-29):
//
//   Tầng 1  BPMN (bpmn-js)        = bản thiết kế / blueprint (pool·lane·flow)
//   Tầng 2  engine Kaori (n8n-like) = vận hành thật (gửi mail / file / đánh giá)
//
// Một model duy nhất = **BPMN 2.0 XML**. Mỗi BPMN task/element mang thêm
// `kaori:nodeType` (+ config) qua extension; runner map element → executor.
// File này là "nơi lưu trữ" cho:
//   • KAORI_ACTIONS    — 45 executor BE hiện hữu, trình bày thành action có thể
//                        gán cho task (drives properties panel + Kaori palette).
//   • BPMN_TO_NODETYPE — element BPMN cấu trúc (gateway/event) → node_type khi
//                        không có kaori:nodeType (mapper BE/FE dùng chung quy ước).
//   • EXECUTABLE_BPMN_TYPES + isExecutable() — BPMN subset Kaori chạy được;
//                        ngoài subset → "⚙ Thiết kế — chưa thực thi".
//
// node_type_key khớp 1-1 với executor BE (workflow_runtime/executors/*). KHÔNG
// hardcode label rời rạc — nhãn hiển thị lấy từ đây, action key lấy từ BE.
// side_effect là gợi ý mirror từ BE (K-17); nguồn sự thật vẫn ở executor.
// ============================================================================

export const KAORI_BPMN_NS = 'http://kaori.ai/bpmn';
export const KAORI_NODETYPE_ATTR = 'kaori:nodeType'; // extension trên BPMN element

export type SideEffect =
  | 'pure' | 'read_only' | 'write_idempotent' | 'write_non_idempotent' | 'external';

export type KaoriActionGroup =
  | 'trigger' | 'human' | 'ai' | 'data' | 'control'
  | 'communication' | 'output' | 'integration';

export interface KaoriAction {
  /** node_type_catalog_key — khớp executor BE (workflow_runtime/executors). */
  key: string;
  vi: string;
  en: string;
  group: KaoriActionGroup;
  /** BPMN element mặc định đại diện action (export + palette). */
  bpmnType: string;
  /** Marker sự kiện cho trigger (start event). */
  marker?: 'message' | 'timer' | 'signal' | 'conditional';
  sideEffect: SideEffect;
  /** true = node khởi đầu workflow (BPMN start/trigger). */
  trigger?: boolean;
  desc?: string;
}

export const ACTION_GROUP_LABEL: Record<KaoriActionGroup, string> = {
  trigger:       'Kích hoạt (Trigger)',
  human:         'Con người',
  ai:            'AI / Đánh giá',
  data:          'Dữ liệu',
  control:       'Điều khiển luồng',
  communication: 'Gửi đi (Email/SMS/Chat)',
  output:        'Kết quả / Báo cáo',
  integration:   'Tích hợp ngoài',
};

// ── 45 executor BE → action (khớp register_builtin_executors) ───────────────
export const KAORI_ACTIONS: KaoriAction[] = [
  // ── Triggers (BPMN start events) ──
  { key: 'scheduled_trigger',  vi: 'Hẹn giờ chạy',        en: 'Scheduled Trigger', group: 'trigger', bpmnType: 'bpmn:StartEvent', marker: 'timer',   sideEffect: 'read_only', trigger: true,  desc: 'Chạy theo lịch/chu kỳ' },
  { key: 'read_webhook',       vi: 'Nhận Webhook',        en: 'Webhook Trigger',   group: 'trigger', bpmnType: 'bpmn:StartEvent', marker: 'message', sideEffect: 'read_only', trigger: true,  desc: 'Kích hoạt khi có HTTP call vào' },
  { key: 'read_email',         vi: 'Nhận Email',          en: 'Email Trigger',     group: 'trigger', bpmnType: 'bpmn:StartEvent', marker: 'message', sideEffect: 'read_only', trigger: true,  desc: 'Kích hoạt khi nhận email' },
  { key: 'read_form_submission', vi: 'Nhận Form',         en: 'Form Trigger',      group: 'trigger', bpmnType: 'bpmn:StartEvent', marker: 'message', sideEffect: 'read_only', trigger: true,  desc: 'Khách gửi biểu mẫu' },
  { key: 'read_file_upload',   vi: 'Nhận File tải lên',   en: 'File Upload Trigger', group: 'trigger', bpmnType: 'bpmn:StartEvent', marker: 'message', sideEffect: 'read_only', trigger: true, desc: 'Kích hoạt khi có file upload' },
  { key: 'read_calendar',      vi: 'Theo Lịch',           en: 'Calendar Trigger',  group: 'trigger', bpmnType: 'bpmn:StartEvent', marker: 'timer',   sideEffect: 'read_only', trigger: true,  desc: 'Theo sự kiện lịch' },

  // ── Human ──
  { key: 'approval_gate',      vi: 'Phê duyệt',           en: 'Approval Gate',     group: 'human', bpmnType: 'bpmn:UserTask', sideEffect: 'write_idempotent', desc: 'Chờ người có quyền duyệt' },
  { key: 'create_task',        vi: 'Giao việc',           en: 'Create Task',       group: 'human', bpmnType: 'bpmn:UserTask', sideEffect: 'write_idempotent', desc: 'Tạo việc cho người phụ trách' },

  // ── AI / Đánh giá ──
  { key: 'classify_text',      vi: 'Phân loại văn bản',   en: 'Classify Text',     group: 'ai', bpmnType: 'bpmn:ServiceTask',      sideEffect: 'read_only', desc: 'Gán nhãn nội dung' },
  { key: 'extract_entities',   vi: 'Trích xuất thực thể', en: 'Extract Entities',  group: 'ai', bpmnType: 'bpmn:ServiceTask',      sideEffect: 'read_only', desc: 'Rút thông tin từ văn bản/file' },
  { key: 'generate_narrative', vi: 'Sinh diễn giải',      en: 'Generate Narrative',group: 'ai', bpmnType: 'bpmn:ServiceTask',      sideEffect: 'read_only', desc: 'Viết diễn giải tự nhiên' },
  { key: 'rag_query',          vi: 'Hỏi tri thức (RAG)',  en: 'RAG Query',         group: 'ai', bpmnType: 'bpmn:ServiceTask',      sideEffect: 'read_only', desc: 'Truy vấn knowledge base' },
  { key: 'call_insight_engine',vi: 'Phân tích Insight',   en: 'Insight Engine',    group: 'ai', bpmnType: 'bpmn:BusinessRuleTask', sideEffect: 'read_only', desc: 'Sinh insight kinh doanh' },
  { key: 'call_risk_detection',vi: 'Đánh giá rủi ro',     en: 'Risk Detection',    group: 'ai', bpmnType: 'bpmn:BusinessRuleTask', sideEffect: 'read_only', desc: 'Chấm điểm/cảnh báo rủi ro' },
  { key: 'call_forecasting',   vi: 'Dự báo',              en: 'Forecasting',       group: 'ai', bpmnType: 'bpmn:ServiceTask',      sideEffect: 'read_only', desc: 'Dự báo số liệu' },
  { key: 'call_recommendation_engine', vi: 'Gợi ý hành động', en: 'Recommendation', group: 'ai', bpmnType: 'bpmn:ServiceTask',     sideEffect: 'read_only', desc: 'Đề xuất hành động' },
  { key: 'validate',           vi: 'Kiểm tra / Đánh giá', en: 'Validate',          group: 'ai', bpmnType: 'bpmn:BusinessRuleTask', sideEffect: 'read_only', desc: 'Đánh giá theo tiêu chí/luật' },
  { key: 'enrich',             vi: 'Làm giàu dữ liệu',    en: 'Enrich',            group: 'ai', bpmnType: 'bpmn:ServiceTask',      sideEffect: 'read_only', desc: 'Bổ sung thông tin' },

  // ── Data ──
  { key: 'read_table',         vi: 'Đọc bảng dữ liệu',    en: 'Read Table',        group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'read_only',        desc: 'Lấy dữ liệu từ bảng' },
  { key: 'read_api',           vi: 'Đọc API',             en: 'Read API',          group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'read_only',        desc: 'Lấy dữ liệu từ API ngoài' },
  { key: 'read_chat',          vi: 'Đọc hội thoại',       en: 'Read Chat',         group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'read_only',        desc: 'Lấy nội dung chat' },
  { key: 'update_record',      vi: 'Cập nhật bản ghi',    en: 'Update Record',     group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'write_idempotent', desc: 'Sửa bản ghi' },
  { key: 'save_to_database',   vi: 'Lưu vào DB',          en: 'Save to Database',  group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'write_idempotent', desc: 'Ghi kết quả xuống DB' },
  { key: 'filter',             vi: 'Lọc',                 en: 'Filter',            group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'pure',             desc: 'Lọc bản ghi theo điều kiện' },
  { key: 'transform',          vi: 'Biến đổi',            en: 'Transform',         group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'pure',             desc: 'Map/đổi shape dữ liệu' },
  { key: 'sort',               vi: 'Sắp xếp',             en: 'Sort',              group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'pure',             desc: 'Sắp xếp' },
  { key: 'merge',              vi: 'Gộp dữ liệu',         en: 'Merge',             group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'pure',             desc: 'Gộp nhiều nguồn' },
  { key: 'deduplicate',        vi: 'Khử trùng lặp',       en: 'Deduplicate',       group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'pure',             desc: 'Bỏ bản ghi trùng' },
  { key: 'aggregate',          vi: 'Tổng hợp',            en: 'Aggregate',         group: 'data', bpmnType: 'bpmn:ServiceTask', sideEffect: 'pure',             desc: 'Gộp/tính tổng nhóm' },

  // ── Control (gateways / wait) ──
  { key: 'if_else',            vi: 'Quyết định (nếu/khác)', en: 'If-Else',         group: 'control', bpmnType: 'bpmn:ExclusiveGateway', sideEffect: 'pure', desc: 'Rẽ 1 nhánh theo điều kiện' },
  { key: 'switch',             vi: 'Phân loại nhiều nhánh', en: 'Switch',          group: 'control', bpmnType: 'bpmn:ExclusiveGateway', sideEffect: 'pure', desc: 'Rẽ theo nhiều giá trị' },
  { key: 'split',              vi: 'Tách song song',      en: 'Parallel Split',    group: 'control', bpmnType: 'bpmn:ParallelGateway',  sideEffect: 'pure', desc: 'Chạy nhiều nhánh đồng thời' },
  { key: 'join',              vi: 'Hợp nhánh',           en: 'Parallel Join',     group: 'control', bpmnType: 'bpmn:ParallelGateway',  sideEffect: 'pure', desc: 'Đợi các nhánh song song' },
  { key: 'wait_for_condition', vi: 'Chờ điều kiện',       en: 'Wait',              group: 'control', bpmnType: 'bpmn:IntermediateCatchEvent', marker: 'conditional', sideEffect: 'read_only', desc: 'Tạm dừng đến khi điều kiện đúng' },
  { key: 'loop_foreach',       vi: 'Vòng lặp (với mỗi)',  en: 'For Each',          group: 'control', bpmnType: 'bpmn:SubProcess', sideEffect: 'pure', desc: 'Với mỗi phần tử trong danh sách, chạy thân vòng lặp' },
  { key: 'loop_end',           vi: 'Kết thúc vòng lặp',   en: 'Loop End',          group: 'control', bpmnType: 'bpmn:SubProcess', sideEffect: 'pure', desc: 'Đóng vùng thân vòng lặp' },

  // ── Communication (gửi đi) ──
  { key: 'send_email',         vi: 'Gửi Email',           en: 'Send Email',        group: 'communication', bpmnType: 'bpmn:SendTask', sideEffect: 'external',             desc: 'Gửi email (đính kèm được)' },
  { key: 'send_sms',           vi: 'Gửi SMS',             en: 'Send SMS',          group: 'communication', bpmnType: 'bpmn:SendTask', sideEffect: 'external',             desc: 'Gửi tin nhắn SMS' },
  { key: 'send_chat_message',  vi: 'Gửi tin nhắn',        en: 'Send Chat',         group: 'communication', bpmnType: 'bpmn:SendTask', sideEffect: 'external',             desc: 'Zalo / Teams / chat' },
  { key: 'publish_alert',      vi: 'Gửi cảnh báo',        en: 'Publish Alert',     group: 'communication', bpmnType: 'bpmn:SendTask', sideEffect: 'write_non_idempotent', desc: 'Phát cảnh báo' },

  // ── Output / Báo cáo ──
  { key: 'publish_insight',    vi: 'Công bố Insight',     en: 'Publish Insight',   group: 'output', bpmnType: 'bpmn:ServiceTask', sideEffect: 'write_non_idempotent', desc: 'Đăng insight cho người dùng' },
  { key: 'display_dashboard',  vi: 'Hiển thị Dashboard',  en: 'Display Dashboard', group: 'output', bpmnType: 'bpmn:ServiceTask', sideEffect: 'write_idempotent',     desc: 'Cập nhật bảng điều khiển' },
  { key: 'generate_report',    vi: 'Tạo Báo cáo',         en: 'Generate Report',   group: 'output', bpmnType: 'bpmn:ServiceTask', sideEffect: 'write_idempotent',     desc: 'Sinh báo cáo' },
  { key: 'export_file',        vi: 'Xuất File',           en: 'Export File',       group: 'output', bpmnType: 'bpmn:ServiceTask', sideEffect: 'write_idempotent',     desc: 'Xuất ra file (CSV/Excel/PDF)' },
  { key: 'log',                vi: 'Ghi Log',             en: 'Log',               group: 'output', bpmnType: 'bpmn:ServiceTask', sideEffect: 'write_idempotent',     desc: 'Ghi nhật ký' },

  // ── Integration ──
  { key: 'call_api',           vi: 'Gọi API ngoài',       en: 'Call API',          group: 'integration', bpmnType: 'bpmn:ServiceTask', sideEffect: 'external', desc: 'Gọi dịch vụ ngoài (có side effect)' },
  { key: 'trigger_workflow',   vi: 'Gọi workflow khác',   en: 'Trigger Workflow',  group: 'integration', bpmnType: 'bpmn:CallActivity', sideEffect: 'external', desc: 'Chạy quy trình con/khác' },
];

export const KAORI_ACTION_BY_KEY: Record<string, KaoriAction> =
  Object.fromEntries(KAORI_ACTIONS.map((a) => [a.key, a]));

// ── Mapper: BPMN element cấu trúc → node_type khi KHÔNG có kaori:nodeType ────
// (Task/ServiceTask/SendTask… luôn lấy từ kaori:nodeType; gateway/event suy ra.)
export const BPMN_TO_NODETYPE: Record<string, string> = {
  'bpmn:ExclusiveGateway': 'if_else',
  'bpmn:InclusiveGateway': 'switch',
  'bpmn:ParallelGateway':  'split',   // runner phân biệt split/join theo in/out degree
};

// BPMN element types Kaori chạy được (ngoài đây = chỉ thiết kế).
// Task carriers cần kaori:nodeType; gateway/start/end map trực tiếp.
export const EXECUTABLE_BPMN_TYPES = new Set<string>([
  'bpmn:Task', 'bpmn:ServiceTask', 'bpmn:SendTask', 'bpmn:ReceiveTask',
  'bpmn:UserTask', 'bpmn:BusinessRuleTask', 'bpmn:ScriptTask', 'bpmn:ManualTask',
  'bpmn:ExclusiveGateway', 'bpmn:InclusiveGateway', 'bpmn:ParallelGateway',
  'bpmn:StartEvent', 'bpmn:EndEvent', 'bpmn:IntermediateCatchEvent',
  'bpmn:CallActivity', 'bpmn:SubProcess',
]);

/** Suy node_type_catalog_key cho 1 BPMN element (đọc kaori:nodeType trước). */
export function resolveNodeType(bpmnType: string, kaoriNodeType?: string | null): string | null {
  if (kaoriNodeType && KAORI_ACTION_BY_KEY[kaoriNodeType]) return kaoriNodeType;
  return BPMN_TO_NODETYPE[bpmnType] ?? null;
}

/** Element này Kaori chạy thật được không (để gắn badge "⚙ Thiết kế — chưa thực thi"). */
export function isExecutable(bpmnType: string, kaoriNodeType?: string | null): boolean {
  if (!EXECUTABLE_BPMN_TYPES.has(bpmnType)) return false;
  // Task carriers phải có kaori:nodeType hợp lệ mới thực thi.
  const isTaskCarrier = bpmnType.endsWith('Task') || bpmnType === 'bpmn:CallActivity' || bpmnType === 'bpmn:SubProcess';
  if (isTaskCarrier) return !!(kaoriNodeType && KAORI_ACTION_BY_KEY[kaoriNodeType]);
  return true; // gateway / start / end map trực tiếp
}

/** Actions hợp lệ để gán cho 1 BPMN element type (drives properties panel). */
export function actionsForBpmnType(bpmnType: string): KaoriAction[] {
  if (bpmnType === 'bpmn:StartEvent') return KAORI_ACTIONS.filter((a) => a.trigger);
  if (bpmnType.endsWith('Task') || bpmnType === 'bpmn:CallActivity')
    return KAORI_ACTIONS.filter((a) => !a.trigger && a.group !== 'control');
  return [];
}
