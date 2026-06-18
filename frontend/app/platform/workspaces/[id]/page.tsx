'use client';

import { use } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import {
  Briefcase, Tag, Calendar, RefreshCw, Users, Receipt, FileClock, Pencil,
} from 'lucide-react';

import { workspaceApi } from '@/lib/api/platform';
import { ErrorBanner, type ProblemDetails } from '@/components/platform/foundation';
import { fmtDateTime } from '@/lib/format';

export default function WorkspaceOverviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const query = useQuery({
    queryKey: ['platform-workspace', id],
    queryFn:  () => workspaceApi.get(id),
    staleTime: 30_000,
    retry: false,
  });

  if (query.isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-32 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse" />
        <div className="h-40 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse" />
      </div>
    );
  }

  if (query.isError || !query.data) {
    const problem = query.error ? (query.error as unknown as ProblemDetails) : null;
    return (
      <ErrorBanner
        problem={problem}
        message={`Không thể tải workspace ${id}. Endpoint GET /api/v1/platform/workspaces/{id} có thể chưa được triển khai.`}
      />
    );
  }

  const ws = query.data.data;
  const facts = [
    { label: 'Mã gói',   value: ws.plan_code,                              icon: Tag },
    { label: 'Ngành',    value: ws.industry?.trim() ? ws.industry : '—',  icon: Briefcase },
    { label: 'Tạo lúc',  value: fmtDateTime(ws.created_at),                icon: Calendar },
    { label: 'Cập nhật', value: fmtDateTime(ws.updated_at),                icon: RefreshCw },
  ];

  return (
    <div className="space-y-6">
      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {facts.map(({ label, value, icon: Icon }) => (
            <div key={label} className="min-w-0">
              <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">
                <Icon className="w-3 h-3" strokeWidth={2} />
                {label}
              </div>
              <div className="font-medium text-sm text-[var(--text-primary)] truncate">{value}</div>
            </div>
          ))}
        </div>
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <section className="lg:col-span-2 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-5">
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">Hoạt động gần đây</h2>
          <p className="text-sm text-[var(--text-secondary)]">
            Nhật ký hoạt động sẽ hiển thị tại đây khi backend audit log
            (<code className="font-mono">/workspaces/{id}/audit</code>) sẵn sàng.
          </p>
          <div className="mt-4">
            <Link
              href={`/platform/workspaces/${id}/audit`}
              className="inline-flex items-center h-8 px-3 text-xs rounded-sm-custom border border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-primary)] hover:bg-[var(--bg-app)] transition-colors"
            >
              Xem nhật ký kiểm toán
            </Link>
          </div>
        </section>

        <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-5">
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">Tác vụ nhanh</h2>
          <div className="flex flex-col gap-2">
            <QuickAction href={`/platform/workspaces/${id}/members`} icon={Users}    label="Quản lý thành viên" />
            <QuickAction href={`/platform/workspaces/${id}/billing`} icon={Receipt}  label="Xem thanh toán" />
            <QuickAction href={`/platform/workspaces/${id}/audit`}   icon={FileClock} label="Nhật ký kiểm toán" />
            <QuickAction href={`/platform/workspaces/${id}/edit`}    icon={Pencil}    label="Chỉnh sửa workspace" />
          </div>
        </section>
      </div>
    </div>
  );
}

function QuickAction({
  href, icon: Icon, label,
}: {
  href:  string;
  icon:  React.ComponentType<{ className?: string; strokeWidth?: number }>;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2.5 px-3 py-2 rounded-md-custom border border-[var(--border-color)] text-sm text-[var(--text-primary)] hover:bg-[var(--bg-app)] hover:border-[var(--primary-gold)]/40 transition-colors"
    >
      <Icon className="w-4 h-4 text-[var(--text-secondary)]" strokeWidth={1.75} />
      {label}
    </Link>
  );
}
