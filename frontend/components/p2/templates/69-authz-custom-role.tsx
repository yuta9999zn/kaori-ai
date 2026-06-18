// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 69. /p2/authz/custom-roles — Custom Roles (F-007 mở rộng — Phase 2 🔵)
// ----------------------------------------------------------------------------
// 4 vai trò chuẩn (MANAGER/OPERATOR/ANALYST/VIEWER) đáp ứng MVP, nhưng
// một số khách hàng cần role hẹp hơn (ví dụ "Chỉ xem doanh thu chi nhánh A").
// Phase 2 mở khả năng tự định nghĩa role với permission set + tag scope.
//
// Endpoints (Phase 2):
//   GET    /api/v2/enterprise/authz/custom-roles
//   POST   /api/v2/enterprise/authz/custom-roles
//   PATCH  /api/v2/enterprise/authz/custom-roles/{id}
//   DELETE /api/v2/enterprise/authz/custom-roles/{id}
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  Shield, Plus, X, Save, Trash2, Sparkles, ShieldCheck, Lock,
  Eye, FlaskConical, Wrench, Crown, Tag, ChevronLeft,
} from 'lucide-react';

import {
  Button, Badge, Checkbox, ErrorBanner, SuccessBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface CustomRole {
  id:           string;
  name:         string;
  description:  string;
  base_role:    'VIEWER' | 'ANALYST' | 'OPERATOR';
  permissions:  string[];
  scope_tags:   string[];
  member_count: number;
}

const PERMISSION_GROUPS: Record<string, Array<{ key: string; label: string }>> = {
  'Pipeline': [
    { key: 'pipeline:read',    label: 'Xem pipeline' },
    { key: 'pipeline:create',  label: 'Tạo pipeline mới' },
    { key: 'pipeline:run',     label: 'Chạy pipeline' },
    { key: 'pipeline:delete',  label: 'Xoá pipeline' },
  ],
  'Insights & Decisions': [
    { key: 'insight:read',          label: 'Xem insight' },
    { key: 'insight:generate',      label: 'Tạo insight mới' },
    { key: 'decision:read',         label: 'Xem quyết định' },
    { key: 'decision:action',       label: 'Đánh dấu đã hành động' },
  ],
  'Data layers': [
    { key: 'data:bronze:read', label: 'Xem Bronze' },
    { key: 'data:silver:read', label: 'Xem Silver' },
    { key: 'data:gold:read',   label: 'Xem Gold' },
  ],
  'Settings': [
    { key: 'settings:read',  label: 'Xem cài đặt workspace' },
    { key: 'settings:write', label: 'Chỉnh sửa cài đặt' },
    { key: 'billing:read',   label: 'Xem gói cước + hoá đơn' },
  ],
};

export default function CustomRolesPage() {
  const [roles,    setRoles]    = useState<CustomRole[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);

  const [showBuilder, setShowBuilder] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await api<{ items: CustomRole[] }>('/api/v2/enterprise/authz/custom-roles');
      setRoles(r.items);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  return (
    <>
      <PageHeader
        title="Vai trò tuỳ chỉnh"
        description="Định nghĩa role hẹp hơn 4 vai trò chuẩn — phù hợp policy nội bộ doanh nghiệp."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-007 mở rộng</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/authz/rbac')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              RBAC chuẩn
            </Button>
            <Button onClick={() => setShowBuilder(true)} disabled title="Phase 2 — Sắp ra mắt">
              <Plus className="w-4 h-4 mr-2" />
              Tạo vai trò mới
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {/* Phase 2 banner */}
        <div className="bg-[var(--primary-gold)]/8 rounded-lg-custom border border-[var(--primary-gold)]/30 p-5 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-1" />
            <div>
              <p className="font-serif text-base text-[var(--text-primary)]">Sắp ra mắt</p>
              <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">
                Phase 1 đã đủ 4 vai trò chuẩn (MANAGER/OPERATOR/ANALYST/VIEWER). Phase 2 thêm builder tuỳ chỉnh — đặt
                tên role, kế thừa từ 1 vai trò chuẩn, ghi đè permission set, gắn scope tag (vd: <span className="font-mono">branch=HCM</span>).
              </p>
              <Button
                variant="secondary"
                className="mt-3"
                onClick={() => (window.location.href = '/p2/authz/rbac')}
              >
                Dùng RBAC chuẩn ngay (Phase 1)
              </Button>
            </div>
          </div>
        </div>

        {/* Existing roles list (placeholder) */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h3 className="font-serif text-base text-[var(--text-primary)]">Vai trò tuỳ chỉnh đã có ({roles.length})</h3>
          </div>
          {loading ? (
            <div className="p-5"><div className="h-24 bg-[var(--bg-app)] rounded-md-custom animate-pulse" /></div>
          ) : roles.length === 0 ? (
            <div className="p-12 text-center text-[var(--text-secondary)]">
              <Shield className="w-10 h-10 mx-auto mb-2 text-[var(--text-secondary)]/40" />
              <p className="text-sm">Chưa có vai trò tuỳ chỉnh nào.</p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border-color)]/60">
              {roles.map((r) => <RoleRow key={r.id} role={r} />)}
            </div>
          )}
        </div>

        {/* Permission catalogue preview */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h3 className="font-serif text-base text-[var(--text-primary)]">Bảng quyền dự kiến</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">Phase 2 sẽ cho phép pick từng quyền sau đây.</p>
          </div>
          <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(PERMISSION_GROUPS).map(([group, perms]) => (
              <div key={group} className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-3">
                <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">{group}</p>
                <ul className="space-y-1">
                  {perms.map((p) => (
                    <li key={p.key} className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
                      <Lock className="w-3 h-3 text-[var(--text-secondary)]/60" />
                      <span className="font-mono text-xs">{p.key}</span>
                      <span className="text-[var(--text-secondary)] text-xs">— {p.label}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Phase 2 sẽ chuyển PDP sang Hybrid (RBAC + ABAC) trả về <span className="font-mono">{`{ allow, reason, policy_id, missing_perms[] }`}</span> theo CLAUDE.md §9.
          </p>
        </div>
      </div>

      {showBuilder && <RoleBuilderPlaceholder onClose={() => setShowBuilder(false)} />}
    </>
  );
}

function RoleRow({ role: r }: { role: CustomRole }) {
  const baseIcon: any = r.base_role === 'OPERATOR' ? Wrench : r.base_role === 'ANALYST' ? FlaskConical : Eye;
  const BaseIcon = baseIcon;
  return (
    <div className="px-5 py-4 flex items-start justify-between gap-3 flex-wrap">
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
          <Shield className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-sm text-[var(--text-primary)]">{r.name}</p>
            <Badge variant="default">
              <BaseIcon className="w-3 h-3 mr-1 inline" />
              kế thừa {r.base_role}
            </Badge>
            <span className="text-[11px] text-[var(--text-secondary)]">{r.member_count} thành viên</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{r.description}</p>
          {r.scope_tags.length > 0 && (
            <div className="flex items-center gap-1 mt-1.5 flex-wrap">
              {r.scope_tags.map((t) => (
                <span key={t} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm-custom text-[10px] font-mono text-[var(--primary-gold-dark)] bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30">
                  <Tag className="w-2.5 h-2.5" />
                  {t}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      <Button variant="tertiary" size="sm" disabled title="Phase 2">Sửa</Button>
    </div>
  );
}

function RoleBuilderPlaceholder({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 bg-[var(--text-primary)]/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-lg w-full max-w-md p-5 animate-slide-up-fade">
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-lg text-[var(--text-primary)]">Tạo vai trò</h3>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-2">Builder Phase 2 — chưa khả dụng.</p>
        <div className="mt-4 flex justify-end">
          <Button onClick={onClose}>Đóng</Button>
        </div>
      </div>
    </div>
  );
}
