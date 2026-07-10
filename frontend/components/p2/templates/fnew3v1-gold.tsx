'use client';

// ============================================================================
// /p2/data/gold — Gold drill-down (F-NEW3 v1 BE PR #148)
// ----------------------------------------------------------------------------
// Wires:
//   GET /api/v1/data/gold/customers?cursor=&limit=&actioned=
//
// Layout:
//   Header  → back link to /p2/data
//   Filter  → "Tất cả / Chỉ chưa xử lý / Chỉ đã xử lý" pill bar
//   Table   → all gold_features rows (customer_external_id, revenue,
//             purchase_count, avg_value, actioned status)
//   Pager   → cursor stack
//
// Note this is the analyst "browse all features" view.
// /p2/customers/at-risk (F-060) is the focused HIGH-risk + revenue
// tile + action toggle workflow; this page just lists everything in
// gold so analysts can verify the aggregator output.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  Sparkles, ArrowLeft, Loader2, ChevronLeft, ChevronRight,
  CheckCircle2, AlertTriangle, Filter, Database, Users,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

interface GoldCustomer {
  customer_external_id: string;
  revenue_at_risk:      number;
  last_purchase_at:     string | null;
  total_purchases:      number | null;
  purchase_count:       number;
  avg_purchase_value:   number | null;
  is_actioned:          boolean;
  actioned_at:          string | null;
  computed_at:          string;
}

interface ListResponse {
  data: GoldCustomer[];
  meta: { cursor: string | null; limit: number; count: number; has_more: boolean };
}

type ActionedFilter = 'all' | 'pending' | 'actioned';

// ============================================================================
// Page
// ============================================================================

export default function GoldDrillDownPage() {
  const t = useT();
  const [customers, setCustomers]     = useState<GoldCustomer[]>([]);
  const [loading, setLoading]         = useState(true);
  const [problem, setProblem]         = useState<ProblemDetails | null>(null);
  const [nextCursor, setNextCursor]   = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [filter, setFilter]           = useState<ActionedFilter>('all');

  async function loadList(cursor: string | null = null) {
    setLoading(true);
    setProblem(null);
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (filter === 'pending')  params.set('actioned', 'false');
      if (filter === 'actioned') params.set('actioned', 'true');
      if (cursor) params.set('cursor', cursor);
      const r = await api<ListResponse>(`/api/v1/data/gold/customers?${params}`);
      setCustomers(r.data ?? []);
      setNextCursor(r.meta.cursor);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setCursorStack([]);
    loadList(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  function pageNext() {
    if (!nextCursor) return;
    setCursorStack((prev) => [...prev, nextCursor]);
    loadList(nextCursor);
  }
  function pagePrev() {
    if (cursorStack.length === 0) return;
    const prev = cursorStack.slice(0, -1);
    setCursorStack(prev);
    loadList(prev.at(-1) ?? null);
  }

  return (
    <>
      <PageHeader
        title={t('templatesFnew3v1Gold.pageTitle')}
        description={t('templatesFnew3v1Gold.pageDescription')}
        actions={
          <>
            <Badge variant="info">F-NEW3 v1</Badge>
            <a href="/p2/customers/at-risk">
              <Button variant="secondary" size="md">
                {t('templatesFnew3v1Gold.atRiskCustomers')}
              </Button>
            </a>
            <a href="/p2/data">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templatesFnew3v1Gold.explore')}</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}

        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex items-center gap-3 shadow-soft-sm flex-wrap">
          <span className="text-xs text-[var(--text-secondary)] inline-flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> {t('templatesFnew3v1Gold.filterLabel')}
          </span>
          {([
            { code: 'all',      label: t('templatesFnew3v1Gold.filterAll') },
            { code: 'pending',  label: t('templatesFnew3v1Gold.filterPending') },
            { code: 'actioned', label: t('templatesFnew3v1Gold.filterActioned') },
          ] as const).map((f) => (
            <button
              key={f.code}
              onClick={() => setFilter(f.code)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-sm-custom border transition-colors',
                filter === f.code
                  ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                  : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)]',
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">{t('templatesFnew3v1Gold.colCustomer')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesFnew3v1Gold.colRevenueAtRisk')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesFnew3v1Gold.colLifetime')}</th>
                  <th className="px-5 py-3 text-center">{t('templatesFnew3v1Gold.colOrderCount')}</th>
                  <th className="px-5 py-3 text-right">AOV</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Gold.colLastPurchase')}</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Gold.colActioned')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading && customers.length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-12 text-center text-[var(--text-secondary)]">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templatesFnew3v1Gold.loading')}
                  </td></tr>
                ) : customers.length === 0 ? (
                  <tr><td colSpan={7} className="px-5 py-12 text-center">
                    <Database className="w-10 h-10 mx-auto text-[var(--text-secondary)]/40 mb-3" />
                    <p className="text-sm text-[var(--text-secondary)]">
                      {t('templatesFnew3v1Gold.emptyGoldRows')}
                    </p>
                  </td></tr>
                ) : (
                  customers.map((c) => <GoldCustomerRow key={c.customer_external_id} customer={c} t={t} />)
                )}
              </tbody>
            </table>
          </div>

          {(cursorStack.length > 0 || nextCursor) && (
            <div className="px-5 py-3 border-t border-[var(--border-color)] flex items-center justify-between">
              <Button
                variant="tertiary" size="sm" onClick={pagePrev}
                disabled={cursorStack.length === 0 || loading}
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" /> {t('templatesFnew3v1Gold.prevPage')}
              </Button>
              <span className="text-xs text-[var(--text-secondary)]">{t('templatesFnew3v1Gold.pageNumber', { n: cursorStack.length + 1 })}</span>
              <Button
                variant="tertiary" size="sm" onClick={pageNext}
                disabled={!nextCursor || loading}
              >
                {t('templatesFnew3v1Gold.nextPage')} <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templatesFnew3v1Gold.k9Note')}{' '}
            <a href="/p2/customers/at-risk" className="text-[var(--primary-gold-dark)] hover:underline">
              {t('templatesFnew3v1Gold.atRiskCustomersLink')}
            </a>{' '}
            {t('templatesFnew3v1Gold.k9NoteSuffix')}
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function GoldCustomerRow({ customer: c, t }: { customer: GoldCustomer; t: ReturnType<typeof useT> }) {
  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4">
        <p className="font-mono text-sm text-[var(--text-primary)]">{c.customer_external_id}</p>
        <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
          {t('templatesFnew3v1Gold.computedAt', { time: formatRelative(c.computed_at, t) })}
        </p>
      </td>
      <td className="px-5 py-4 text-right">
        {c.revenue_at_risk > 0 ? (
          <p className="font-serif text-sm text-[var(--state-error)]">
            {formatVND(c.revenue_at_risk)}
          </p>
        ) : (
          <span className="text-xs text-[var(--text-secondary)]">—</span>
        )}
      </td>
      <td className="px-5 py-4 text-right text-xs text-[var(--text-primary)]">
        {c.total_purchases != null ? formatVND(c.total_purchases) : '—'}
      </td>
      <td className="px-5 py-4 text-center text-xs text-[var(--text-primary)]">
        {c.purchase_count}
      </td>
      <td className="px-5 py-4 text-right text-xs text-[var(--text-primary)]">
        {c.avg_purchase_value != null ? formatVND(c.avg_purchase_value) : '—'}
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
        {c.last_purchase_at ? formatRelative(c.last_purchase_at, t) : '—'}
      </td>
      <td className="px-5 py-4">
        {c.is_actioned ? (
          <Badge variant="success">
            <CheckCircle2 className="w-3 h-3 mr-1" /> {t('templatesFnew3v1Gold.statusActioned')}
          </Badge>
        ) : c.revenue_at_risk > 0 ? (
          <Badge variant="warning">
            <AlertTriangle className="w-3 h-3 mr-1" /> {t('templatesFnew3v1Gold.statusPending')}
          </Badge>
        ) : (
          <Badge variant="default">
            <Users className="w-3 h-3 mr-1" /> {t('templatesFnew3v1Gold.statusCustomerOk')}
          </Badge>
        )}
      </td>
    </tr>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatRelative(iso: string | null, t: ReturnType<typeof useT>): string {
  if (!iso) return '—';
  const diff = Date.now() - +new Date(iso);
  if (Number.isNaN(diff))     return iso;
  if (diff < 60_000)          return t('templatesFnew3v1Gold.relJustNow');
  if (diff < 3_600_000)       return t('templatesFnew3v1Gold.relMinutesAgo', { n: Math.round(diff / 60_000) });
  if (diff < 86_400_000)      return t('templatesFnew3v1Gold.relHoursAgo', { n: Math.round(diff / 3_600_000) });
  if (diff < 7 * 86_400_000)  return t('templatesFnew3v1Gold.relDaysAgo', { n: Math.round(diff / 86_400_000) });
  return new Date(iso).toLocaleDateString('vi-VN');
}
