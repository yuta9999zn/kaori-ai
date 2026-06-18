'use client';

import { useQuery } from '@tanstack/react-query';
import {
  Building2, Wallet, AlertTriangle, TrendingUp, Users, Gauge, Clock,
  CheckCircle2, XCircle,
} from 'lucide-react';

import { platformBillingApi, type BillingStatus } from '@/lib/api/platform';
import {
  ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtInt, fmtVND, fmtVNDShort, fmtDate, fmtDateTime } from '@/lib/format';

const STATUS_COLOR: Record<BillingStatus, string> = {
  normal:   'bg-[var(--state-success)]',
  warn:     'bg-[var(--state-warning)]',
  critical: 'bg-[#D97C7C]',
  overage:  'bg-[#C26B6B]',
};
const STATUS_LABEL: Record<BillingStatus, string> = {
  normal:   'Bình thường',
  warn:     'Cảnh báo (≥80%)',
  critical: 'Nguy hiểm (≥95%)',
  overage:  'Vượt hạn mức',
};

export default function PlatformBillingOverviewPage() {
  const query = useQuery({
    queryKey: ['platform-billing-overview'],
    queryFn:  () => platformBillingApi.overview(),
    staleTime: 60_000,
    retry: false,
  });

  if (query.isLoading) {
    return (
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className="h-28 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
          />
        ))}
      </div>
    );
  }

  if (query.isError || !query.data) {
    return (
      <ErrorBanner
        problem={query.error ? (query.error as unknown as ProblemDetails) : null}
        message="Không thể tải tổng quan thanh toán."
      />
    );
  }

  const o = query.data.data;
  const overUsageCount = o.by_status.warn + o.by_status.critical + o.by_status.overage;
  const utilisationPct = o.total_quota > 0
    ? Math.round((o.total_unique_customers * 100) / o.total_quota)
    : 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <Kpi
          label="Doanh thu tháng này"
          value={fmtVNDShort(o.total_revenue_vnd)}
          hint={fmtVND(o.total_revenue_vnd)}
          icon={<Wallet className="w-5 h-5" />}
          tone="gold"
        />
        <Kpi
          label="Doanh nghiệp đang hoạt động"
          value={fmtInt(o.enterprise_count)}
          hint={`Kỳ thanh toán ${o.billing_month}`}
          icon={<Building2 className="w-5 h-5" />}
          tone="gold"
        />
        <Kpi
          label="Khách hàng độc nhất"
          value={fmtInt(o.total_unique_customers)}
          hint={`${utilisationPct}% trên tổng hạn mức ${fmtInt(o.total_quota)}`}
          icon={<Users className="w-5 h-5" />}
          tone="info"
        />
        <Kpi
          label="Cần chú ý"
          value={fmtInt(overUsageCount)}
          hint="Doanh nghiệp ≥80% hạn mức hoặc đã vượt"
          icon={<AlertTriangle className="w-5 h-5" />}
          tone={overUsageCount > 0 ? 'warning' : 'success'}
        />
      </div>

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-serif text-lg text-[var(--text-primary)]">Phân bố theo trạng thái</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Ngưỡng cảnh báo: 80% · Ngưỡng nguy hiểm: 95% · Vượt hạn mức ngay khi có overage.
            </p>
          </div>
          <Gauge className="w-5 h-5 text-[var(--text-secondary)]" />
        </div>

        {o.enterprise_count > 0 ? (
          <>
            <div className="h-3 rounded-full bg-[var(--bg-app)] overflow-hidden flex">
              {(['normal', 'warn', 'critical', 'overage'] as BillingStatus[]).map((s) => {
                const v = o.by_status[s];
                const w = (v / o.enterprise_count) * 100;
                return v > 0 ? (
                  <div
                    key={s}
                    className={STATUS_COLOR[s]}
                    style={{ width: `${w}%` }}
                    title={`${STATUS_LABEL[s]}: ${v}`}
                  />
                ) : null;
              })}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {(['normal', 'warn', 'critical', 'overage'] as BillingStatus[]).map((s) => (
                <div key={s} className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${STATUS_COLOR[s]}`} />
                  <span className="text-[var(--text-primary)]">{STATUS_LABEL[s]}</span>
                  <span className="ml-auto tabular-nums text-[var(--text-secondary)]">
                    {fmtInt(o.by_status[s])}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-[var(--text-secondary)]">Chưa có doanh nghiệp đang hoạt động.</p>
        )}
      </section>

      <CronHealthCard
        lastAggregatedAt={o.last_aggregated_at}
        staleCount={o.stale_enterprise_count}
        totalCount={o.enterprise_count}
      />

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-3">
        <h2 className="font-serif text-lg text-[var(--text-primary)]">Chi tiết doanh thu</h2>
        <dl className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Doanh thu cơ sở</dt>
            <dd className="font-serif text-xl text-[var(--text-primary)] tabular-nums mt-1">
              {fmtVND(o.total_base_amount_vnd)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Doanh thu vượt hạn mức</dt>
            <dd className="font-serif text-xl text-[var(--text-primary)] tabular-nums mt-1">
              {fmtVND(o.total_overage_amount_vnd)}
            </dd>
            <dd className="text-[11px] text-[var(--text-secondary)] mt-1">
              Phụ phí theo đơn giá sẽ áp dụng từ F-059 (hiện tạm tính 0).
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Tổng doanh thu</dt>
            <dd className="font-serif text-xl text-[var(--primary-gold-dark)] tabular-nums mt-1">
              {fmtVND(o.total_revenue_vnd)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Đơn vị vượt hạn mức</dt>
            <dd className="font-medium text-sm text-[var(--text-primary)] tabular-nums mt-1">
              {fmtInt(o.total_overage_units)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Kỳ thanh toán tiếp theo</dt>
            <dd className="font-medium text-sm text-[var(--text-primary)] mt-1">{fmtDate(o.next_invoice_date)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Xu hướng</dt>
            <dd className="font-medium text-sm text-[var(--text-primary)] flex items-center gap-1.5 mt-1">
              <TrendingUp className="w-4 h-4 text-[#5C856A]" /> Cập nhật theo ngày
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}

function Kpi({
  label, value, hint, icon, tone,
}: {
  label: string;
  value: string;
  hint:  string;
  icon:  React.ReactNode;
  tone:  'gold' | 'info' | 'warning' | 'success';
}) {
  const halo =
    tone === 'warning' ? 'bg-[var(--state-warning)]/15 text-[#9E814D]'
    : tone === 'success' ? 'bg-[var(--state-success)]/15 text-[#5C856A]'
    : tone === 'info'    ? 'bg-[var(--state-info)]/15 text-[#52647D]'
    :                      'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)]';
  return (
    <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] p-5 shadow-soft-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wider text-[var(--text-secondary)] font-medium">{label}</p>
          <p className="font-serif text-2xl text-[var(--text-primary)] mt-1.5 tabular-nums">{value}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1.5">{hint}</p>
        </div>
        <div className={`shrink-0 w-10 h-10 rounded-md-custom flex items-center justify-center ${halo}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}

function CronHealthCard({
  lastAggregatedAt, staleCount, totalCount,
}: {
  lastAggregatedAt: string | null;
  staleCount:       number;
  totalCount:       number;
}) {
  const recent = lastAggregatedAt
    ? Date.now() - new Date(lastAggregatedAt).getTime() < 25 * 3600 * 1000
    : false;
  const tier: 'ok' | 'warn' | 'critical' =
    !lastAggregatedAt || (totalCount > 0 && staleCount === totalCount) ? 'critical' :
    staleCount > 0 || !recent                                          ? 'warn'     :
    'ok';

  const label = tier === 'ok'
    ? 'Bình thường'
    : tier === 'warn'
      ? 'Cảnh báo — có doanh nghiệp chưa cập nhật'
      : 'Sự cố — cron có thể đang dừng';

  const Icon = tier === 'ok' ? CheckCircle2 : tier === 'critical' ? XCircle : AlertTriangle;
  const tone =
    tier === 'ok'   ? 'text-[#5C856A] bg-[var(--state-success)]/12 border-[var(--state-success)]/40'
    : tier === 'warn' ? 'text-[#9E814D] bg-[var(--state-warning)]/12 border-[var(--state-warning)]/40'
    :                 'text-[#9B5050] bg-[var(--state-error)]/12 border-[var(--state-error)]/40';

  return (
    <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)]">Sức khoẻ tác vụ tổng hợp (F-031)</h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            Cron chạy hằng ngày 02:00 ICT — cập nhật{' '}
            <code className="font-mono">last_aggregated_at</code> trên mỗi doanh nghiệp.
          </p>
        </div>
        <Clock className="w-5 h-5 text-[var(--text-secondary)]" />
      </div>

      <div className={`rounded-md-custom border px-4 py-3 flex items-start gap-3 ${tone}`}>
        <Icon className="w-5 h-5 mt-0.5 shrink-0" />
        <div className="flex-1 text-sm">
          <p className="font-medium">{label}</p>
          <p className="opacity-80 mt-0.5">
            {lastAggregatedAt
              ? `Lần chạy gần nhất: ${fmtDateTime(lastAggregatedAt)}`
              : 'Chưa có lần chạy nào trong tháng này.'}
            {' · '}
            Doanh nghiệp chưa cập nhật trong 25h:{' '}
            <strong>{fmtInt(staleCount)}</strong>/{fmtInt(totalCount)}.
          </p>
        </div>
      </div>
    </section>
  );
}
