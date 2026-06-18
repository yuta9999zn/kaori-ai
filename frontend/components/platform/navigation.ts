/**
 * Platform admin portal — sidebar navigation tree.
 *
 * Routes match the existing `/platform/*` tree under `frontend/app/platform/`
 * (production tree, not the deleted `/p1/*` scaffold). Dynamic detail pages
 * (e.g. `/platform/workspaces/[id]`) are reached via list pages, not from
 * the sidebar — list pages link to them.
 *
 * Role flag gates a child to SUPER_ADMIN per CLAUDE.md §9. The shell
 * collapses a whole group when every child is hidden for the user's role.
 *
 * Phase flag: 1 = Phase 1 ✅, 2 = Phase 2 🔵, 3 = Phase 3 🟣.
 */

import type { LucideIcon } from 'lucide-react';
import {
  LayoutDashboard,
  Briefcase,
  Shield,
  CreditCard,
  Key,
  Settings,
  SlidersHorizontal,
} from 'lucide-react';

export interface NavChild {
  title: string;
  path:  string;
  phase?: 1 | 2 | 3;
  /** Restrict visibility to platform roles. Omitted = visible to all P1 roles. */
  role?:  'SUPER_ADMIN' | 'ADMIN' | 'SUPPORT' | 'CSM';
}

export interface NavGroup {
  title:    string;
  icon:     LucideIcon;
  children: NavChild[];
}

export const NAV_TREE: NavGroup[] = [
  {
    title: 'Tổng quan',
    icon:  LayoutDashboard,
    children: [
      { title: 'Bảng điều khiển', path: '/platform', phase: 1 },
    ],
  },
  {
    title: 'Workspaces',
    icon:  Briefcase,
    children: [
      { title: 'Danh sách', path: '/platform/workspaces',     phase: 1 },
      { title: 'Tạo mới',   path: '/platform/workspaces/new', phase: 1, role: 'SUPER_ADMIN' },
    ],
  },
  {
    title: 'Quản trị viên',
    icon:  Shield,
    children: [
      { title: 'Danh sách',  path: '/platform/admins',        phase: 1, role: 'SUPER_ADMIN' },
      { title: 'Mời admin',  path: '/platform/admins/invite', phase: 1, role: 'SUPER_ADMIN' },
    ],
  },
  {
    title: 'Billing',
    icon:  CreditCard,
    children: [
      { title: 'Tổng quan', path: '/platform/billing/overview', phase: 1 },
      { title: 'Hạn mức',   path: '/platform/billing/quota',    phase: 1 },
      { title: 'Xuất CSV',  path: '/platform/billing/export',   phase: 1 },
    ],
  },
  {
    title: 'Bảo mật',
    icon:  Key,
    children: [
      { title: 'MFA',           path: '/platform/security/mfa',      phase: 1 },
      { title: 'Phiên đăng nhập', path: '/platform/security/sessions', phase: 1 },
    ],
  },
  {
    title: 'LLM & AI',
    icon:  SlidersHorizontal,
    children: [
      // CR-0019 / FR-PLT-08 — runtime AI tuning knobs.
      { title: 'Tinh chỉnh AI', path: '/platform/llm-config', phase: 2, role: 'SUPER_ADMIN' },
    ],
  },
];

/** Flatten all child paths — handy for active-route detection in the shell. */
export function allPaths(): string[] {
  return NAV_TREE.flatMap((g) => g.children.map((c) => c.path));
}
