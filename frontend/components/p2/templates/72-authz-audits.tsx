// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 72. /p2/authz/audit — Authorization Audit Feed (Phase 2 🔵)
// ----------------------------------------------------------------------------
// Phase 1 đã có:
//   - decision_audit_log     (K-6 — mọi automated decision)
//   - workspace_audit_log    (workspace lifecycle: invite, role change, suspend)
//   - platform_admin_audit_log (P1 platform side)
//
// Phase 2 thêm AUTHZ audit feed dành riêng cho RBAC + ABAC events:
//   - permission denied
//   - role escalation
//   - cross-workspace access
//   - ABAC policy match (allow/deny)
//
// Endpoint: GET /api/v2/enterprise/authz/audit?cursor=&limit=&kind=&actor=
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, Shield, Search, Filter, RefreshCw, Download,
  CheckCircle2, Ban, ArrowUpRight, Globe, ShieldCheck,
  AlertTriangle, ExternalLink,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type AuditKind =
  | 'permission_denied'
  | 'permission_allowed'
  | 'role_changed'
  | 'role_escalated'
  | 'cross_workspace_access'
  | 'abac_match';

interface AuthzAuditRow {
  id:               string;
  kind:             AuditKind;
  actor_email:      string;
  actor_role:       string;
  resource:         string;
  action:           string;
  decision:         'ALLOW' | 'DENY';
  reason:           string;
  policy_id?:       string;
  ip_address:       string;
  created_at:       string;
}

interface Page<T> {
  items:       T[];
  next_cursor: string | null;
  total:       number;
}

const KIND_BADGE: Record<AuditKind, { label: string; tone: 'success' | 'warning' | 'error' | 'info' | 'default' }> = {
  permission_denied:      { label: 'Từ chối quyền',         tone: 'error' },
  permission_allowed:     { label: 'Cấp quyền',              tone: 'success' },
  role_changed:           { label: 'Đổi vai trò',            tone: 'info' },
  role_escalated:         { label: 'Nâng vai trò',           tone: 'warning' },
  cross_workspace_access: { label: 'Truy cập cross-workspace', tone: 'warning' },
  abac_match:             { label: 'ABAC match',             tone: 'default' },
};

const PAGE_LIMIT = 50;

export default function AuthzAuditPage() {
  const [items,    setItems]    = useState<AuthzAuditRow[]>([]);
  const [cursor,   setCursor]   = useState<string | null>(null);
  const [hasMore,  setHasMore]  = useState(false);
  const [total,    setTotal]    = useState(0);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);

  const [kindFilter, setKindFilter] = useState<'ALL' | AuditKind>('ALL');
  const [search,     setSearch]     = useState('');
  const [exporting,  setExporting]  = useState(false);

  async function load(reset = true) {
    setLoading(true);
    setProblem(null);
    try {
      const params = new URLSearchParams();
      if (!reset && cursor)        params.set('cursor', cursor);
      params.set('limit', String(PAGE_LIMIT));
      if (kindFilter !== 'ALL')    params.set('kind', kindFilter);
      if (search.trim())           params.set('actor', search.trim());

      const page = await api<Page<AuthzAuditRow>>(`/api/v2/enterprise/authz/audit?${params.toString()}`);
      setItems(reset ? page.items : [...items, ...page.items]);
      setCursor(page.next_cursor);
      setHasMore(!!page.next_cursor);
      setTotal(page.total);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(true); }, [kindFilter]);

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    load(true);
  }

  async function exportCsv() {
    setExporting(true);
    try {
      // Sprint 7 PR A pattern — fetch + Blob, không leak JWT
      const params = new URLSearchParams();
      if (kindFilter !== 'ALL') params.set('kind', kindFilter);
      if (search.trim())        params.set('actor', search.trim());
      const res = await fetch(`/api/v2/enterprise/authz/audit/export.csv?${params.toString()}`, {
        headers: { Authorization: `Bearer ${window.localStorage.getItem('kaori.access_token') ?? window.localStorage.getItem('kaori_jwt') ?? ''}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `authz-audit-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setProblem({ title: 'Xuất CSV thất bại', detail: String(err?.message ?? err) });
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Authz Audit"
        description="Mọi sự kiện cấp/từ chối quyền + đổi vai trò + truy cập cross-workspace."
        actions={
          <>
            <Badge variant="info">Phase 2</Badge>
            <Button variant="secondary" onClick={() => load(true)}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Làm mới
            </Button>
            <Button variant="secondary" onClick={exportCsv} isLoading={exporting}>
              <Download className="w-4 h-4 mr-2" />
              Xuất CSV
            </Button>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/authz/rbac')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              RBAC
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {/* Filter bar */}
        <form
          onSubmit={onSearchSubmit}
          className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-3 shadow-soft-sm flex flex-col sm:flex-row gap-3"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo email actor..."
              className="w-full pl-9 pr-4 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>
          <select
            value={kindFilter}
            onChange={(e) => setKindFilter(e.target.value as any)}
            className="px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none"
          >
            <option value="ALL">Mọi loại sự kiện</option>
            {(Object.keys(KIND_BADGE) as AuditKind[]).map((k) => (
              <option key={k} value={k}>{KIND_BADGE[k].label}</option>
            ))}
          </select>
          <button type="submit" className="px-3 py-2 bg-[var(--primary-gold)]/10 border border-[var(--primary-gold)]/30 text-[var(--primary-gold-dark)] text-xs font-medium rounded-md-custom hover:bg-[var(--primary-gold)]/20">
            <Filter className="w-3.5 h-3.5 inline mr-1" />
            Lọc
          </button>
        </form>

        <p className="text-xs text-[var(--text-secondary)]">
          {total.toLocaleString('vi-VN')} sự kiện · Đang hiển thị {items.length}
        </p>

        {/* Table */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]/60">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-44">Loại</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Actor</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Resource · Action</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-28">Decision</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-40">IP · Thời gian</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading && items.length === 0 ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={5} className="px-4 py-3"><div className="h-8 bg-[var(--bg-app)] rounded-sm-custom animate-pulse" /></td>
                    </tr>
                  ))
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-[var(--text-secondary)]">
                      <Shield className="w-10 h-10 mx-auto mb-2 text-[var(--text-secondary)]/40" />
                      Chưa có sự kiện authz nào.
                    </td>
                  </tr>
                ) : items.map((row) => (
                  <tr key={row.id} className="hover:bg-[var(--bg-app)]/30">
                    <td className="px-4 py-3 align-top">
                      <Badge variant={KIND_BADGE[row.kind].tone}>
                        {row.kind === 'cross_workspace_access' && <Globe className="w-3 h-3 mr-1 inline" />}
                        {row.kind === 'role_escalated' && <ArrowUpRight className="w-3 h-3 mr-1 inline" />}
                        {KIND_BADGE[row.kind].label}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <p className="text-sm text-[var(--text-primary)]">{row.actor_email}</p>
                      <p className="text-[11px] text-[var(--text-secondary)]">{row.actor_role}</p>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <p className="text-sm font-mono text-[var(--text-primary)]">{row.resource}</p>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                        action: <span className="font-mono">{row.action}</span>
                      </p>
                      {row.reason && (
                        <p className="text-xs text-[var(--text-secondary)] mt-1 leading-snug max-w-md">{row.reason}</p>
                      )}
                      {row.policy_id && (
                        <p className="text-[11px] text-[var(--primary-gold-dark)] mt-1">
                          policy: <span className="font-mono">{row.policy_id}</span>
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top">
                      {row.decision === 'ALLOW' ? (
                        <Badge variant="success"><CheckCircle2 className="w-3 h-3 mr-1 inline" />ALLOW</Badge>
                      ) : (
                        <Badge variant="error"><Ban className="w-3 h-3 mr-1 inline" />DENY</Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top text-xs text-[var(--text-secondary)] whitespace-nowrap">
                      <p className="font-mono">{row.ip_address}</p>
                      <p>{row.created_at}</p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div className="px-4 py-3 border-t border-[var(--border-color)]/60 flex justify-center">
              <Button variant="secondary" onClick={() => load(false)} isLoading={loading}>Tải thêm</Button>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Authz audit retention: 2 năm (CLAUDE.md §7 — <span className="font-mono">kaori.audit.internal</span>). Tất cả row đều immutable.
            Phase 2 sẽ thêm filter theo workspace_id (đa workspace).
          </p>
        </div>
      </div>
    </>
  );
}
