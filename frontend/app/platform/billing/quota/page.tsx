'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { ChevronRight, Filter, X } from 'lucide-react';

import {
  platformBillingApi,
  type BillingStatus,
} from '@/lib/api/platform';
import {
  Badge, Button, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtInt, fmtPct, fmtVND } from '@/lib/format';
import { useT } from '@/lib/i18n/provider';

const STATUS_VARIANT: Record<BillingStatus, 'operational' | 'warning' | 'error'> = {
  normal:   'operational',
  warn:     'warning',
  critical: 'error',
  overage:  'error',
};
const STATUS_LABEL_KEY: Record<BillingStatus, string> = {
  normal:   'quotaPage.statusNormal',
  warn:     'quotaPage.statusWarn',
  critical: 'quotaPage.statusCritical',
  overage:  'quotaPage.statusOverage',
};

const PLAN_OPTIONS = ['', 'PILOT', 'ENT_BASIC', 'ENT_MID', 'ENT_MAX', 'ENT_ROI'];
const STATUS_OPTIONS: ('' | BillingStatus)[] = ['', 'normal', 'warn', 'critical', 'overage'];

export default function PlatformBillingQuotaPage() {
  const t = useT();
  const [plan,   setPlan]   = useState<string>('');
  const [status, setStatus] = useState<'' | BillingStatus>('');
  const [cursor, setCursor] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ['platform-billing-quota', plan, status, cursor],
    queryFn:  () => platformBillingApi.listQuota(
      { plan: plan || undefined, status: status || undefined },
      cursor,
      50,
    ),
    retry: false,
  });

  const rows  = query.data?.data ?? [];
  const total = query.data?.meta.total ?? 0;
  const next  = query.data?.meta.cursor ?? null;
  const hasFilter = !!(plan || status);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] pb-2">
          <Filter className="w-4 h-4" />
          {t('quotaPage.filterBy')}
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-[var(--text-secondary)] block">{t('quotaPage.planLabel')}</label>
          <select
            value={plan}
            onChange={(e) => { setCursor(null); setPlan(e.target.value); }}
            className="h-10 w-44 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          >
            {PLAN_OPTIONS.map((p) => (
              <option key={p || 'all'} value={p}>{p || t('quotaPage.allPlans')}</option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <label className="text-xs text-[var(--text-secondary)] block">{t('quotaPage.statusLabel')}</label>
          <select
            value={status}
            onChange={(e) => { setCursor(null); setStatus(e.target.value as '' | BillingStatus); }}
            className="h-10 w-48 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s || 'all'} value={s}>{s ? t(STATUS_LABEL_KEY[s]) : t('quotaPage.allStatuses')}</option>
            ))}
          </select>
        </div>
        {hasFilter && (
          <Button
            variant="tertiary"
            size="sm"
            onClick={() => { setCursor(null); setPlan(''); setStatus(''); }}
          >
            <X className="w-3.5 h-3.5 mr-1" />
            {t('quotaPage.clearFilter')}
          </Button>
        )}
        <p className="text-sm text-[var(--text-secondary)] ml-auto pb-2">
          {total > 0 ? <><strong className="text-[var(--text-primary)]">{fmtInt(total)}</strong> {t('quotaPage.enterpriseCountSuffix')}</> : null}
        </p>
      </div>

      {query.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-14 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
            />
          ))}
        </div>
      )}

      {query.isError && (
        <ErrorBanner
          problem={query.error ? (query.error as unknown as ProblemDetails) : null}
          message={t('quotaPage.errLoadQuota')}
        />
      )}

      {!query.isLoading && !query.isError && (
        <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] overflow-hidden shadow-soft-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-app)]/60 text-[var(--text-secondary)]">
                <tr>
                  <th className="text-left font-medium px-4 py-2.5">{t('quotaPage.colEnterprise')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('quotaPage.planLabel')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('quotaPage.colUsage')}</th>
                  <th className="text-left font-medium px-4 py-2.5">%</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('quotaPage.colOverage')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('quotaPage.statusLabel')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('quotaPage.colRevenue')}</th>
                  <th className="text-right font-medium px-4 py-2.5 w-24"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {rows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-4 py-10 text-center text-[var(--text-secondary)]">
                      {hasFilter
                        ? t('quotaPage.emptyFiltered')
                        : t('quotaPage.emptyAll')}
                    </td>
                  </tr>
                )}
                {rows.map((r) => (
                  <tr key={r.enterprise_id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-medium text-[var(--text-primary)] truncate">{r.enterprise_name}</p>
                      <p className="text-xs text-[var(--text-secondary)] font-mono truncate">{r.enterprise_id}</p>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="current">{r.plan_code}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm text-[var(--text-primary)] tabular-nums">
                        {fmtInt(r.unique_customers)} / {fmtInt(r.quota)}
                      </p>
                      <div className="mt-1 h-1.5 w-32 rounded-full bg-[var(--bg-app)] overflow-hidden">
                        <div
                          className={
                            r.status === 'overage'  ? 'bg-[#C26B6B] h-full' :
                            r.status === 'critical' ? 'bg-[#D97C7C] h-full' :
                            r.status === 'warn'     ? 'bg-[var(--state-warning)] h-full' :
                                                      'bg-[var(--state-success)] h-full'
                          }
                          style={{ width: `${Math.min(100, r.usage_pct)}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)] tabular-nums">
                      {fmtPct(r.usage_pct / 100)}
                    </td>
                    <td className="px-4 py-3">
                      {r.overage_units > 0 ? (
                        <span className="text-sm text-[#9B5050] tabular-nums">+{fmtInt(r.overage_units)}</span>
                      ) : (
                        <span className="text-xs text-[var(--text-secondary)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[r.status]}>{t(STATUS_LABEL_KEY[r.status])}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-primary)] tabular-nums">
                      {fmtVND(r.total_amount_vnd)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/platform/billing/enterprises/${r.enterprise_id}`}
                        className="inline-flex items-center text-[var(--primary-gold-dark)] hover:text-[var(--text-primary)] text-sm transition-colors"
                      >
                        {t('quotaPage.detail')} <ChevronRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {next && (
            <div className="px-4 py-3 border-t border-[var(--border-color)]/60 flex justify-center bg-[var(--bg-app)]/40">
              <Button variant="secondary" size="sm" onClick={() => setCursor(next)}>
                {t('quotaPage.loadMore')}
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
