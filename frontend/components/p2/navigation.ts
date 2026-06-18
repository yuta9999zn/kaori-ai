// @ts-nocheck
// ============================================================================
// Kaori AI — User Enterprise (P2) — Shared Sidebar Navigation Tree
// ----------------------------------------------------------------------------
// Single source of truth for the P2 sidebar across all 27 modules.
// Imported by every screen that renders the cream sidebar (file 9 onwards).
//
// Phase 2 / 3 entries are kept (with `phase` flag) so the same tree drives
// future portals — UI may visually dim or gate them by feature flag at the
// shell level rather than removing entries here.
//
// Groups carry a `section` so the shell can render ~5 collapsible super-
// sections (by business painpoint) instead of ~20 flat top-level groups —
// this cuts cognitive load for non-technical SME users. SECTION_ORDER fixes
// the section display order. Removed the "Auto DB" group: it pointed at
// /p2/auto-db/* pages with no backend capability (dead end) — re-add when
// the feature actually ships, ideally gated by a backend capability flag.
// ============================================================================

import {
  LayoutDashboard, Database, GitMerge, Lightbulb, BarChart2, Users,
  CheckSquare, FileText, Target, AlertTriangle, Bell, Workflow,
  Shield, Palette, CreditCard, Layers, BookOpen, FlaskConical, TrendingUp,
  ShieldCheck,
} from 'lucide-react';

export interface NavChild {
  title: string;
  path:  string;
  /** 1 = Phase 1 ✅, 2 = Phase 2 🔵, 3 = Phase 3 🟣 */
  phase?: 1 | 2 | 3;
}

export interface NavGroup {
  title:    string;
  icon:     any;
  /** Super-section this group lives under (see SECTION_ORDER). */
  section:  string;
  children: NavChild[];
}

/** Display order of the collapsible super-sections in the sidebar. */
export const SECTION_ORDER: string[] = [
  'Dữ liệu & Pipeline',
  'Quy trình',
  'Phân tích & Rủi ro',
  'Khách hàng & Báo cáo',
  'Hệ thống',
];

export const NAV_TREE: NavGroup[] = [
  // ── Dữ liệu & Pipeline ───────────────────────────────────────────────
  {
    title: 'Tổng quan',
    icon:  LayoutDashboard,
    section: 'Dữ liệu & Pipeline',
    children: [
      { title: 'Bảng điều khiển',  path: '/p2/dashboard',           phase: 1 },
      { title: 'Tuỳ chỉnh',         path: '/p2/dashboard/customize', phase: 1 },
    ],
  },
  {
    title: 'Dữ liệu',
    icon:  Database,
    section: 'Dữ liệu & Pipeline',
    children: [
      { title: 'Khám phá',  path: '/p2/data',         phase: 1 },
      { title: 'Bronze',    path: '/p2/data/bronze',  phase: 1 },
      { title: 'Silver',    path: '/p2/data/silver',  phase: 1 },
      { title: 'Gold',      path: '/p2/data/gold',    phase: 1 },
    ],
  },
  {
    title: 'Pipelines',
    icon:  GitMerge,
    section: 'Dữ liệu & Pipeline',
    children: [
      { title: 'Lịch sử chạy', path: '/p2/pipelines',     phase: 1 },
      { title: 'Tạo mới',       path: '/p2/pipelines/new', phase: 1 },
    ],
  },
  {
    title: 'Insight',
    icon:  Lightbulb,
    section: 'Dữ liệu & Pipeline',
    children: [
      { title: 'Tất cả Insight', path: '/p2/insights',                phase: 1 },
      { title: 'Tạo Insight',     path: '/p2/insights/generate',       phase: 1 },
      { title: 'Knowledge Base',   path: '/p2/insights/knowledge-base', phase: 2 },
    ],
  },
  {
    title: 'Biểu đồ',
    icon:  BarChart2,
    section: 'Dữ liệu & Pipeline',
    children: [
      { title: 'Chart Picker',  path: '/p2/charts/picker',    phase: 1 },
      { title: 'Theo loại',      path: '/p2/charts/categories', phase: 2 },
    ],
  },

  // ── Quy trình ────────────────────────────────────────────────────────
  {
    title: 'Workflow',
    icon:  Workflow,
    section: 'Quy trình',
    children: [
      { title: 'Phòng ban',          path: '/p2/departments', phase: 1 },
      { title: 'Cơ cấu tổ chức',     path: '/p2/org-tree',    phase: 2 },
      { title: 'Tất cả workflow',    path: '/p2/workflows',   phase: 2 },
      { title: 'Hợp đồng',           path: '/p2/contracts',   phase: 2 },
      { title: 'Duyệt & Phân quyền', path: '/p2/approvals',   phase: 2 },
      { title: 'Kho tài liệu',       path: '/p2/documents',   phase: 2 },
    ],
  },
  {
    title: 'Quyết định',
    icon:  CheckSquare,
    section: 'Quy trình',
    children: [
      { title: 'Nhật ký quyết định', path: '/p2/decisions', phase: 1 },
    ],
  },
  {
    title: 'Phân quyền',
    icon:  Shield,
    section: 'Quy trình',
    children: [
      { title: 'RBAC',           path: '/p2/authz/rbac',          phase: 1 },
      { title: 'Vai trò tuỳ chỉnh', path: '/p2/authz/custom-roles',  phase: 2 },
      { title: 'ABAC builder',    path: '/p2/authz/abac/builder',  phase: 2 },
      { title: 'Mô phỏng',        path: '/p2/authz/abac/simulate', phase: 2 },
      { title: 'Audit',           path: '/p2/authz/audit',         phase: 2 },
    ],
  },

  // ── Phân tích & Rủi ro ───────────────────────────────────────────────
  {
    title: 'Phân tích',
    icon:  FlaskConical,
    section: 'Phân tích & Rủi ro',
    children: [
      { title: 'Tổng quan',     path: '/p2/analysis',              phase: 2 },
      { title: 'Cơ bản',         path: '/p2/analysis/basic',        phase: 2 },
      { title: 'Trung cấp',      path: '/p2/analysis/intermediate', phase: 2 },
      { title: 'Nâng cao',       path: '/p2/analysis/advanced',     phase: 2 },
      { title: 'Phạm vi',        path: '/p2/analysis/scope',        phase: 2 },
    ],
  },
  {
    title: 'Khung phân tích',
    icon:  Layers,
    section: 'Phân tích & Rủi ro',
    children: [
      { title: 'Tổng quan',  path: '/p2/frameworks',          phase: 2 },
      { title: 'SWOT',        path: '/p2/frameworks/swot',     phase: 2 },
      { title: '6W',          path: '/p2/frameworks/6w',       phase: 2 },
      { title: '2H',          path: '/p2/frameworks/2h',       phase: 2 },
      { title: 'Fishbone',    path: '/p2/frameworks/fishbone', phase: 2 },
      { title: 'MoM/YoY',     path: '/p2/frameworks/mom-yoy',  phase: 2 },
      { title: 'Tuỳ chỉnh',   path: '/p2/frameworks/custom',   phase: 2 },
    ],
  },
  {
    title: 'Chiến lược',
    icon:  Target,
    section: 'Phân tích & Rủi ro',
    children: [
      { title: 'Tổng quan',  path: '/p2/strategy',                  phase: 2 },
      { title: 'OKR',         path: '/p2/strategy/okr',              phase: 2 },
      { title: 'Lộ trình',    path: '/p2/strategy/timeline',         phase: 2 },
      { title: 'Họp review',  path: '/p2/strategy/review-meetings',  phase: 2 },
    ],
  },
  {
    title: 'Giá trị AI',
    icon:  TrendingUp,
    section: 'Phân tích & Rủi ro',
    children: [
      { title: 'NOV & ROI', path: '/p2/economics', phase: 2 },
    ],
  },
  {
    title: 'Rủi ro',
    icon:  AlertTriangle,
    section: 'Phân tích & Rủi ro',
    children: [
      { title: 'Danh sách',  path: '/p2/risks',         phase: 2 },
      { title: 'Xuất',        path: '/p2/risks/export',  phase: 2 },
    ],
  },
  {
    title: 'Cảnh báo',
    icon:  Bell,
    section: 'Phân tích & Rủi ro',
    children: [
      { title: 'Cảnh báo',  path: '/p2/alerts', phase: 2 },
    ],
  },

  // ── Khách hàng & Báo cáo ─────────────────────────────────────────────
  {
    title: 'Khách hàng',
    icon:  Users,
    section: 'Khách hàng & Báo cáo',
    children: [
      { title: 'Rủi ro & ROI',  path: '/p2/customers/at-risk',  phase: 2 },
    ],
  },
  {
    title: 'Người dùng',
    icon:  Users,
    section: 'Khách hàng & Báo cáo',
    children: [
      { title: 'Danh sách',  path: '/p2/users',         phase: 1 },
      { title: 'Mời người',   path: '/p2/users/invite',  phase: 1 },
    ],
  },
  {
    title: 'Báo cáo',
    icon:  FileText,
    section: 'Khách hàng & Báo cáo',
    children: [
      { title: 'Tổng quan',           path: '/p2/reports',          phase: 2 },
      { title: 'Tự động',              path: '/p2/reports/auto',     phase: 2 },
      { title: 'Builder',              path: '/p2/reports/builder',  phase: 2 },
      { title: 'Mẫu',                  path: '/p2/reports/templates',phase: 2 },
    ],
  },

  // ── Hệ thống ─────────────────────────────────────────────────────────
  {
    title: 'Tuân thủ AI',
    icon:  ShieldCheck,
    section: 'Hệ thống',
    children: [
      { title: 'EU AI Act', path: '/p2/compliance', phase: 2 },
    ],
  },
  {
    title: 'Gói cước',
    icon:  CreditCard,
    section: 'Hệ thống',
    children: [
      { title: 'Tổng quan',  path: '/p2/subscription',         phase: 1 },
      { title: 'Nâng cấp',    path: '/p2/subscription/upgrade', phase: 1 },
    ],
  },
  {
    title: 'Thương hiệu',
    icon:  Palette,
    section: 'Hệ thống',
    children: [
      { title: 'Tổng quan',  path: '/p2/branding',       phase: 1 },
      { title: 'Email',       path: '/p2/branding/email', phase: 2 },
    ],
  },
  {
    title: 'Tài liệu',
    icon:  BookOpen,
    section: 'Hệ thống',
    children: [
      { title: 'Cài đặt',  path: '/settings', phase: 1 },
    ],
  },
];

/** Helper: flatten all paths (handy for active-route detection). */
export function allPaths(): string[] {
  return NAV_TREE.flatMap((g) => g.children.map((c) => c.path));
}
