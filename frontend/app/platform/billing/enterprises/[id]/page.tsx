'use client';

import { use } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, Building2, ExternalLink, AlertTriangle } from 'lucide-react';

import { platformBillingApi, type BillingStatus } from '@/lib/api/platform';
import {
  Badge, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtInt, fmtPct, fmtVND, fmtDate } from '@/lib/format';

const STATUS_VARIANT: Record<BillingStatus, 'operational' | 'warning' | 'error'> = {
  normal: 'operational', warn: 'warning', critical: 'error', overage: 'error',
};
const STATUS_LABEL: Record<BillingStatus, string> = {
  normal: 'Bình thường', warn: 'Cảnh báo', critical: 'Nguy hiểm', overage: 'Vượt hạn mức',
};

export default function EnterpriseBillingDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  const query = useQuery({
    queryKey: ['platform-billing-enterprise', id],
    queryFn:  () => platformBillingApi.getEnterprise(id),
    retry: false,
  });

  if (query.isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 rounded bg-[var(--bg-app)] animate-pulse" />
        <div className="h-32 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse" />
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <div className="space-y-4">
        <Link
          href="/platform/billing/quota"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Quay lại danh sách
        </Link>
        <ErrorBanner
          problem={query.error ? (query.error as unknown as ProblemDetails) : null}
          message={`Không tìm thấy doanh nghiệp ${id}.`}
        />
      </div>
    );
  }

  const s        = query.data.data;
  const usagePct = s.quota > 0 ? (s.unique_customers * 100) / s.quota : 0;
  const barColor =
    s.status === 'overage'  ? 'bg-[#C26B6B]' :
    s.status === 'critical' ? 'bg-[#D97C7C]' :
    s.status === 'warn'     ? 'bg-[var(--state-warning)]' :
                              'bg-[var(--state-success)]';

  return (
    <div className="space-y-6">
      <Link
        href="/platform/billing/quota"
        className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" />
        Quay lại danh sách hạn mức
      </Link>

      <header className="flex items-start gap-4">
        <div className="w-12 h-12 rounded-md-custom bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center shrink-0">
          <Building2 className="w-6 h-6 text-[var(--primary-gold-dark)]" strokeWidth={1.5} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h2 className="font-serif text-2xl text-[var(--text-primary)]">{s.enterprise_name}</h2>
            <Badge variant={STATUS_VARIANT[s.status]}>{STATUS_LABEL[s.status]}</Badge>
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-1 font-mono">{s.enterprise_id}</p>
          <Link
            href={`/platform/workspaces/${s.workspace_id}`}
            className="mt-2 inline-flex items-center gap-1 text-sm text-[var(--primary-gold-dark)] hover:text-[var(--text-primary)] transition-colors"
          >
            Xem workspace gốc <ExternalLink className="w-3.5 h-3.5" />
          </Link>
        </div>
      </header>

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Sử dụng</p>
            <p className="font-serif text-3xl text-[var(--text-primary)] tabular-nums mt-1">
              {fmtInt(s.unique_customers)}{' '}
              <span className="text-xl text-[var(--text-secondary)]">/ {fmtInt(s.quota)}</span>
            </p>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {fmtPct(usagePct / 100)} hạn mức tháng — Ngưỡng cảnh báo {s.quota_warn_at_pct}%
            </p>
          </div>
          <Badge variant="current">{s.plan_code}</Badge>
        </div>

        <div className="h-2 rounded-full bg-[var(--bg-app)] overflow-hidden">
          <div className={`${barColor} h-full`} style={{ width: `${Math.min(100, usagePct)}%` }} />
        </div>

        {s.overage_units > 0 && (
          <div className="flex items-start gap-2 text-xs text-[#9B5050] bg-[var(--state-error)]/12 border border-[var(--state-error)]/30 rounded-md-custom px-3 py-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Đã vượt hạn mức <strong>{fmtInt(s.overage_units)}</strong> đơn vị. Phụ phí sẽ áp dụng
              từ F-059 (hiện tạm tính 0).
            </span>
          </div>
        )}
      </section>

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-3">
        <h3 className="font-medium text-[var(--text-primary)]">Doanh thu kỳ {s.billing_month}</h3>
        <dl className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Phí cơ sở</dt>
            <dd className="font-serif text-xl text-[var(--text-primary)] tabular-nums mt-1">{fmtVND(s.base_amount_vnd)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Phí vượt hạn mức</dt>
            <dd className="font-serif text-xl text-[var(--text-primary)] tabular-nums mt-1">{fmtVND(s.overage_amount_vnd)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Tổng kỳ này</dt>
            <dd className="font-serif text-xl text-[var(--primary-gold-dark)] tabular-nums mt-1">{fmtVND(s.total_amount_vnd)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Kỳ thanh toán tiếp theo</dt>
            <dd className="font-medium text-sm text-[var(--text-primary)] mt-1">{fmtDate(s.next_invoice_date)}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
