'use client';

import { use } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Receipt, Users, AlertTriangle, Calendar } from 'lucide-react';

import { useT } from '@/lib/i18n/provider';
import { workspaceBillingApi } from '@/lib/api/platform';
import {
  Badge, ErrorBanner, QuotaBar, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtVND, fmtInt, fmtDate } from '@/lib/format';

type BillingStatus = 'normal' | 'warn' | 'critical' | 'overage';

const STATUS_VARIANT: Record<BillingStatus, 'operational' | 'warning' | 'error'> = {
  normal:   'operational',
  warn:     'warning',
  critical: 'warning',
  overage:  'error',
};
const STATUS_LABEL_KEY: Record<BillingStatus, string> = {
  normal:   'billingPage.statusNormal',
  warn:     'billingPage.statusWarn',
  critical: 'billingPage.statusCritical',
  overage:  'billingPage.statusOverage',
};

export default function WorkspaceBillingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const t = useT();

  const query = useQuery({
    queryKey: ['workspace-billing', id],
    queryFn:  () => workspaceBillingApi.get(id),
    retry: false,
  });

  if (query.isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
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
        message={t('billingPage.errNotReady', { id })}
      />
    );
  }

  const b        = query.data.data;
  const usagePct = b.quota > 0 ? Math.min(100, (b.unique_customers / b.quota) * 100) : 0;
  const isOver   = b.unique_customers > b.quota;
  const variant  = STATUS_VARIANT[b.status as BillingStatus] ?? 'operational';
  const label    = STATUS_LABEL_KEY[b.status as BillingStatus]
    ? t(STATUS_LABEL_KEY[b.status as BillingStatus])
    : b.status;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <BillingKpi
          label={t('billingPage.kpiUniqueCustomers')}
          value={fmtInt(b.unique_customers)}
          hint={t('billingPage.kpiQuotaHint', { quota: fmtInt(b.quota), plan: b.plan_code })}
          icon={<Users className="w-5 h-5" />}
          tone={isOver ? 'error' : usagePct >= 80 ? 'warning' : 'gold'}
        />
        <BillingKpi
          label={t('billingPage.kpiTotalAmount')}
          value={fmtVND(b.total_amount_vnd)}
          hint={t('billingPage.kpiAmountBreakdown', {
            base: fmtVND(b.base_amount_vnd),
            overage: fmtVND(b.overage_amount_vnd),
          })}
          icon={<Receipt className="w-5 h-5" />}
          tone="gold"
        />
        <BillingKpi
          label={t('billingPage.kpiOverageUnits')}
          value={fmtInt(b.overage_units)}
          hint={b.overage_units > 0 ? t('billingPage.hintOverageCharged') : t('billingPage.hintWithinQuota')}
          icon={<AlertTriangle className="w-5 h-5" />}
          tone={b.overage_units > 0 ? 'warning' : 'gold'}
        />
      </div>

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-5 space-y-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h2 className="font-serif text-lg text-[var(--text-primary)]">
              {t('billingPage.periodTitle', { month: b.billing_month })}
            </h2>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {t('billingPage.periodDesc', { pct: b.quota_warn_at_pct })}
            </p>
          </div>
          <Badge variant={variant}>{label}</Badge>
        </div>

        <QuotaBar
          current={b.unique_customers}
          limit={b.quota}
          unit={t('billingPage.unitUniqueCustomers')}
        />

        {b.next_invoice_date && (
          <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)] pt-2 border-t border-[var(--border-color)]/60">
            <Calendar className="w-4 h-4" />
            {t('billingPage.nextInvoiceLabel')}{' '}
            <span className="text-[var(--text-primary)] font-medium">{fmtDate(b.next_invoice_date)}</span>
          </div>
        )}
      </section>
    </div>
  );
}

function BillingKpi({
  label, value, hint, icon, tone,
}: {
  label: string;
  value: string;
  hint:  string;
  icon:  React.ReactNode;
  tone:  'gold' | 'warning' | 'error';
}) {
  const haloClass =
    tone === 'error'
      ? 'bg-[var(--state-error)]/15 text-[#9B5050]'
      : tone === 'warning'
        ? 'bg-[var(--state-warning)]/15 text-[#9E814D]'
        : 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)]';
  return (
    <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] p-5 shadow-soft-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wider text-[var(--text-secondary)] font-medium">{label}</p>
          <p className="font-serif text-2xl text-[var(--text-primary)] mt-1.5 tabular-nums">{value}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1.5">{hint}</p>
        </div>
        <div className={`shrink-0 w-10 h-10 rounded-md-custom flex items-center justify-center ${haloClass}`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
