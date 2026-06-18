'use client';

/**
 * Workspace detail layout — breadcrumb back link + section header + tab bar.
 *
 * Re-skinned 2026-05-18 to cream/gold tokens (p1/foundation). Tab bar uses
 * usePathname() to mark the active section instead of the prior shared
 * `<TabNav>` (kept minimal so the surrounding AppShell `<main>` controls
 * scroll/overflow without the extra wrapper div).
 */

import { use } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Building2 } from 'lucide-react';

import { workspaceApi, type WsStatus } from '@/lib/api/platform';
import { Badge, cn } from '@/components/platform/foundation';

const STATUS_VARIANT: Record<WsStatus, 'operational' | 'warning' | 'degraded'> = {
  active:    'operational',
  inactive:  'degraded',
  suspended: 'warning',
};
const STATUS_LABEL: Record<WsStatus, string> = {
  active:    'Đang hoạt động',
  inactive:  'Ngừng hoạt động',
  suspended: 'Tạm ngưng',
};

export default function WorkspaceDetailLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params:   Promise<{ id: string }>;
}) {
  const { id }   = use(params);
  const pathname = usePathname() ?? '';

  const query = useQuery({
    queryKey: ['platform-workspace', id],
    queryFn:  () => workspaceApi.get(id),
    staleTime: 30_000,
    retry: false,
  });

  const ws = query.data?.data;

  const tabs = [
    { href: `/platform/workspaces/${id}`,         label: 'Tổng quan' },
    { href: `/platform/workspaces/${id}/members`, label: 'Thành viên' },
    { href: `/platform/workspaces/${id}/keys`,    label: 'Khoá API' },
    { href: `/platform/workspaces/${id}/billing`, label: 'Thanh toán' },
    { href: `/platform/workspaces/${id}/audit`,   label: 'Nhật ký kiểm toán' },
    { href: `/platform/workspaces/${id}/edit`,    label: 'Chỉnh sửa' },
  ];

  return (
    <>
      <div className="px-6 lg:px-8 pt-6">
        <Link
          href="/platform/workspaces"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Tất cả workspaces
        </Link>
      </div>

      <header className="px-6 lg:px-8 py-5 border-b border-[var(--border-color)] bg-[var(--bg-card)]">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center shrink-0">
            <Building2 className="w-6 h-6 text-[var(--primary-gold-dark)]" strokeWidth={1.5} />
          </div>
          <div className="flex-1 min-w-0">
            {query.isLoading && (
              <div className="space-y-2">
                <div className="h-7 w-64 rounded bg-[var(--bg-app)] animate-pulse" />
                <div className="h-4 w-40 rounded bg-[var(--bg-app)] animate-pulse" />
              </div>
            )}
            {query.isError && !ws && (
              <>
                <h1 className="font-serif text-2xl text-[var(--text-primary)]">Workspace không tồn tại</h1>
                <p className="text-xs text-[var(--text-secondary)] mt-1 font-mono">{id}</p>
              </>
            )}
            {ws && (
              <>
                <div className="flex items-center gap-3 flex-wrap">
                  <h1 className="font-serif text-2xl text-[var(--text-primary)]">{ws.name}</h1>
                  <Badge variant={STATUS_VARIANT[ws.status]}>
                    {STATUS_LABEL[ws.status]}
                  </Badge>
                </div>
                <p className="text-xs text-[var(--text-secondary)] mt-1 font-mono">{ws.workspace_id}</p>
              </>
            )}
          </div>
        </div>
      </header>

      <nav className="px-6 lg:px-8 border-b border-[var(--border-color)] bg-[var(--bg-card)] overflow-x-auto">
        <div className="flex items-center gap-1">
          {tabs.map((tab) => {
            const active = pathname === tab.href;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={cn(
                  'px-3 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap',
                  active
                    ? 'border-[var(--primary-gold)] text-[var(--text-primary)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                )}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>
      </nav>

      <div className="px-6 lg:px-8 py-6">{children}</div>
    </>
  );
}
