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
import { useT } from '@/lib/i18n/provider';

const STATUS_COLOR: Record<BillingStatus, string> = {
  normal:   'bg-[var(--state-success)]',
  warn:     'bg-[var(--state-warning)]',
  critical: 'bg-[#D97C7C]',
  overage:  'bg-[#C26B6B]',
};
const STATUS_LABEL_KEY: Record<BillingStatus, string> = {
  normal:   'overviewPage2.statusNormal',
  warn:     'overviewPage2.statusWarn',
  critical: 'overviewPage2.statusCritical',
  overage:  'overviewPage2.statusOverage',
};

export default function PlatformBillingOverviewPage() {
  const t = useT();
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
        message={t('overviewPage2.errLoadFailed')}
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
          label={t('overviewPage2.kpiRevenueLabel')}
          value={fmtVNDShort(o.total_revenue_vnd)}
          hint={fmtVND(o.total_revenue_vnd)}
          icon={<Wallet className="w-5 h-5" />}
          tone="gold"
        />
        <Kpi
          label={t('overviewPage2.kpiActiveEnterprisesLabel')}
          value={fmtInt(o.enterprise_count)}
          hint={t('overviewPage2.kpiBillingPeriodHint', { month: o.billing_month })}
          icon={<Building2 className="w-5 h-5" />}
          tone="gold"
        />
        <Kpi
          label={t('overviewPage2.kpiUniqueCustomersLabel')}
          value={fmtInt(o.total_unique_customers)}
          hint={t('overviewPage2.kpiUtilisationHint', { pct: utilisationPct, quota: fmtInt(o.total_quota) })}
          icon={<Users className="w-5 h-5" />}
          tone="info"
        />
        <Kpi
          label={t('overviewPage2.kpiNeedsAttentionLabel')}
          value={fmtInt(overUsageCount)}
          hint={t('overviewPage2.kpiNeedsAttentionHint')}
          icon={<AlertTriangle className="w-5 h-5" />}
          tone={overUsageCount > 0 ? 'warning' : 'success'}
        />
      </div>

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="font-serif text-lg text-[var(--text-primary)]">{t('overviewPage2.statusDistributionTitle')}</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {t('overviewPage2.statusThresholdsHint')}
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
                    title={`${t(STATUS_LABEL_KEY[s])}: ${v}`}
                  />
                ) : null;
              })}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              {(['normal', 'warn', 'critical', 'overage'] as BillingStatus[]).map((s) => (
                <div key={s} className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${STATUS_COLOR[s]}`} />
                  <span className="text-[var(--text-primary)]">{t(STATUS_LABEL_KEY[s])}</span>
                  <span className="ml-auto tabular-nums text-[var(--text-secondary)]">
                    {fmtInt(o.by_status[s])}
                  </span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="text-sm text-[var(--text-secondary)]">{t('overviewPage2.noActiveEnterprises')}</p>
        )}
      </section>

      <CronHealthCard
        lastAggregatedAt={o.last_aggregated_at}
        staleCount={o.stale_enterprise_count}
        totalCount={o.enterprise_count}
      />

      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-3">
        <h2 className="font-serif text-lg text-[var(--text-primary)]">{t('overviewPage2.revenueDetailTitle')}</h2>
        <dl className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{t('overviewPage2.dtBaseRevenue')}</dt>
            <dd className="font-serif text-xl text-[var(--text-primary)] tabular-nums mt-1">
              {fmtVND(o.total_base_amount_vnd)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{t('overviewPage2.dtOverageRevenue')}</dt>
            <dd className="font-serif text-xl text-[var(--text-primary)] tabular-nums mt-1">
              {fmtVND(o.total_overage_amount_vnd)}
            </dd>
            <dd className="text-[11px] text-[var(--text-secondary)] mt-1">
              {t('overviewPage2.overageNote')}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{t('overviewPage2.dtTotalRevenue')}</dt>
            <dd className="font-serif text-xl text-[var(--primary-gold-dark)] tabular-nums mt-1">
              {fmtVND(o.total_revenue_vnd)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{t('overviewPage2.dtOverageUnits')}</dt>
            <dd className="font-medium text-sm text-[var(--text-primary)] tabular-nums mt-1">
              {fmtInt(o.total_overage_units)}
            </dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{t('overviewPage2.dtNextInvoiceDate')}</dt>
            <dd className="font-medium text-sm text-[var(--text-primary)] mt-1">{fmtDate(o.next_invoice_date)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{t('overviewPage2.dtTrend')}</dt>
            <dd className="font-medium text-sm text-[var(--text-primary)] flex items-center gap-1.5 mt-1">
              <TrendingUp className="w-4 h-4 text-[#5C856A]" /> {t('overviewPage2.trendUpdatedDaily')}
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
  const t = useT();
  const recent = lastAggregatedAt
    ? Date.now() - new Date(lastAggregatedAt).getTime() < 25 * 3600 * 1000
    : false;
  const tier: 'ok' | 'warn' | 'critical' =
    !lastAggregatedAt || (totalCount > 0 && staleCount === totalCount) ? 'critical' :
    staleCount > 0 || !recent                                          ? 'warn'     :
    'ok';

  const label = tier === 'ok'
    ? t('overviewPage2.cronTierOk')
    : tier === 'warn'
      ? t('overviewPage2.cronTierWarn')
      : t('overviewPage2.cronTierCritical');

  const Icon = tier === 'ok' ? CheckCircle2 : tier === 'critical' ? XCircle : AlertTriangle;
  const tone =
    tier === 'ok'   ? 'text-[#5C856A] bg-[var(--state-success)]/12 border-[var(--state-success)]/40'
    : tier === 'warn' ? 'text-[#9E814D] bg-[var(--state-warning)]/12 border-[var(--state-warning)]/40'
    :                 'text-[#9B5050] bg-[var(--state-error)]/12 border-[var(--state-error)]/40';

  return (
    <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)]">{t('overviewPage2.cronHealthTitle')}</h2>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            {t('overviewPage2.cronHealthDescPre')}{' '}
            <code className="font-mono">last_aggregated_at</code> {t('overviewPage2.cronHealthDescPost')}
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
              ? t('overviewPage2.lastRunAt', { time: fmtDateTime(lastAggregatedAt) })
              : t('overviewPage2.noRunThisMonth')}
            {' · '}
            {t('overviewPage2.staleEnterprisesLabel')}{' '}
            <strong>{fmtInt(staleCount)}</strong>/{fmtInt(totalCount)}.
          </p>
        </div>
      </div>
    </section>
  );
}
