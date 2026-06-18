'use client';

/**
 * /platform/workspaces — list enterprise workspaces (F-008).
 *
 * Re-skinned 2026-05-18 to the cream/gold platform design system. Combines
 * the prior implementation's strengths (react-query, cursor pagination,
 * dynamic-route link to detail page) with the cream/gold shell tokens via
 * components/platform/foundation + PageHeader.
 *
 * Backend: GET /api/v1/platform/workspaces?cursor=&limit=
 *   → { data: Workspace[], meta: { cursor, total } }
 *
 * Canonical example of the "graduated cream/gold" pattern — copy this
 * shape when re-skinning the other 20 /platform/* pages.
 */

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { Plus, Search, Eye, Edit2, Ban } from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner,
  type ProblemDetails,
} from '@/components/platform/foundation';
import { PageHeader } from '@/components/platform/shell';
import { useAuth } from '@/lib/auth-store';
import { workspaceApi, type Workspace, type WsStatus } from '@/lib/api/platform';

const PAGE_SIZE = 50;

type StatusFilter = 'all' | WsStatus;
type PlanFilter   = 'all' | string;

function statusBadgeVariant(s: WsStatus): 'operational' | 'warning' | 'degraded' {
  if (s === 'active')    return 'operational';
  if (s === 'suspended') return 'warning';
  return 'degraded';
}

function statusLabel(s: WsStatus): string {
  if (s === 'active')    return 'Đang hoạt động';
  if (s === 'suspended') return 'Tạm ngưng';
  return 'Ngừng hoạt động';
}

function planLabel(code: string): string {
  switch (code.toUpperCase()) {
    case 'PILOT':       return 'Pilot';
    case 'ENT_BASIC':   return 'Basic';
    case 'ENT_MID':     return 'Mid';
    case 'ENT_MAX':     return 'Max';
    case 'ENT_ROI':     return 'ROI Share';
    case 'TRIAL':       return 'Trial';
    case 'STARTER':     return 'Starter';
    case 'BUSINESS':    return 'Business';
    case 'ENTERPRISE':  return 'Enterprise';
    default:            return code;
  }
}

function formatDateVi(iso: string): string {
  try {
    return new Intl.DateTimeFormat('vi-VN', {
      day: '2-digit', month: '2-digit', year: 'numeric',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function PlatformWorkspacesPage() {
  const canCreate = useAuth((s) => s.canSee(['SUPER_ADMIN']));

  // Cursor history: index N holds the cursor used to fetch page N+1.
  // Empty stack ⇒ on page 1 (no cursor).
  const [cursors, setCursors] = useState<(string | null)[]>([]);
  const currentCursor = cursors.length === 0 ? null : cursors[cursors.length - 1];
  const pageNumber    = cursors.length + 1;

  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [plan,   setPlan]   = useState<PlanFilter>('all');

  const query = useQuery({
    queryKey: ['platform-workspaces', pageNumber, currentCursor],
    queryFn:  () => workspaceApi.list(currentCursor, PAGE_SIZE),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const data       = query.data?.data ?? [];
  const total      = query.data?.meta.total ?? 0;
  const nextCursor = query.data?.meta.cursor ?? null;
  const canGoBack  = cursors.length > 0;
  const canGoNext  = !!nextCursor;

  function goNext() {
    if (!nextCursor) return;
    setCursors((s) => [...s, nextCursor]);
  }
  function goBack() {
    setCursors((s) => s.slice(0, -1));
  }

  const planOptions = useMemo<string[]>(
    () => Array.from(new Set(data.map((w) => w.plan_code))).sort(),
    [data],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return data.filter((w) => {
      const matchesSearch =
        !q ||
        w.name.toLowerCase().includes(q) ||
        w.workspace_id.toLowerCase().includes(q);
      const matchesStatus = status === 'all' || w.status === status;
      const matchesPlan   = plan === 'all'   || w.plan_code === plan;
      return matchesSearch && matchesStatus && matchesPlan;
    });
  }, [data, search, status, plan]);

  // api() (from p2/foundation) throws ProblemDetails on non-2xx — react-query
  // surfaces it as `unknown`, so widen the cast.
  const problem = query.error ? (query.error as unknown as ProblemDetails) : null;

  return (
    <>
      <PageHeader
        title="Workspaces"
        description={`Quản lý workspace của các enterprise đang dùng nền tảng.${total ? ` Tổng ${total} workspace.` : ''}`}
        actions={
          canCreate ? (
            <Link href="/platform/workspaces/new">
              <Button variant="primary" size="sm">
                <Plus className="w-4 h-4 mr-1.5" />
                Tạo workspace mới
              </Button>
            </Link>
          ) : null
        }
      />

      <div className="px-6 lg:px-8 py-6 space-y-4">
        {problem && <ErrorBanner problem={problem} />}

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <Input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo tên hoặc workspace ID"
              className="pl-9"
              aria-label="Tìm workspace"
            />
          </div>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as StatusFilter)}
            aria-label="Lọc theo trạng thái"
            className="h-10 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          >
            <option value="all">Mọi trạng thái</option>
            <option value="active">Đang hoạt động</option>
            <option value="suspended">Tạm ngưng</option>
            <option value="inactive">Ngừng hoạt động</option>
          </select>
          <select
            value={plan}
            onChange={(e) => setPlan(e.target.value)}
            aria-label="Lọc theo gói cước"
            className="h-10 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          >
            <option value="all">Mọi gói cước</option>
            {planOptions.map((code) => (
              <option key={code} value={code}>{planLabel(code)}</option>
            ))}
          </select>
        </div>

        <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] overflow-hidden shadow-soft-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-app)]/60 text-[var(--text-secondary)]">
                <tr>
                  <th className="text-left font-medium px-4 py-2.5">Workspace</th>
                  <th className="text-left font-medium px-4 py-2.5">Ngành</th>
                  <th className="text-left font-medium px-4 py-2.5">Gói cước</th>
                  <th className="text-left font-medium px-4 py-2.5">Trạng thái</th>
                  <th className="text-left font-medium px-4 py-2.5">Tạo lúc</th>
                  <th className="text-right font-medium px-4 py-2.5 w-24">Hành động</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {query.isLoading && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-[var(--text-secondary)]">
                      Đang tải workspace…
                    </td>
                  </tr>
                )}

                {!query.isLoading && filtered.length === 0 && !problem && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-[var(--text-secondary)]">
                      {data.length === 0
                        ? 'Chưa có workspace nào.'
                        : 'Không có workspace nào khớp bộ lọc hiện tại.'}
                    </td>
                  </tr>
                )}

                {!query.isLoading && filtered.map((ws) => (
                  <tr key={ws.workspace_id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                    <td className="px-4 py-3">
                      <Link
                        href={`/platform/workspaces/${ws.workspace_id}`}
                        className="font-medium text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] transition-colors"
                      >
                        {ws.name}
                      </Link>
                      <div className="text-xs text-[var(--text-secondary)] font-mono">{ws.workspace_id}</div>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{ws.industry || '—'}</td>
                    <td className="px-4 py-3">
                      <Badge variant="current">{planLabel(ws.plan_code)}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={statusBadgeVariant(ws.status)}>{statusLabel(ws.status)}</Badge>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-secondary)]">{formatDateVi(ws.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <Link
                          href={`/platform/workspaces/${ws.workspace_id}`}
                          className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors"
                          aria-label="Xem chi tiết"
                        >
                          <Eye className="w-4 h-4" />
                        </Link>
                        {canCreate && (
                          <Link
                            href={`/platform/workspaces/${ws.workspace_id}/edit`}
                            className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors"
                            aria-label="Chỉnh sửa"
                          >
                            <Edit2 className="w-4 h-4" />
                          </Link>
                        )}
                        {canCreate && ws.status === 'active' && (
                          <button
                            type="button"
                            className="p-1.5 text-[var(--text-secondary)] hover:text-[var(--state-warning)] hover:bg-[var(--bg-app)] rounded-md-custom transition-colors"
                            aria-label="Tạm ngưng"
                            title="Tạm ngưng workspace"
                          >
                            <Ban className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {(canGoBack || canGoNext || data.length > 0) && (
            <div className="px-4 py-2.5 border-t border-[var(--border-color)]/60 flex items-center justify-between bg-[var(--bg-app)]/40 text-xs text-[var(--text-secondary)]">
              <span>
                Trang <strong className="text-[var(--text-primary)]">{pageNumber}</strong>
                {' · '}
                Hiển thị <strong className="text-[var(--text-primary)]">{filtered.length}</strong> / <strong className="text-[var(--text-primary)]">{data.length}</strong>
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={goBack}
                  disabled={!canGoBack || query.isFetching}
                >
                  ← Trước
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={goNext}
                  disabled={!canGoNext || query.isFetching}
                >
                  Sau →
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
