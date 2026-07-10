'use client';

// ============================================================================
// /p2/customers/at-risk — North Star tile + at-risk customer list (F-060 BE PR #124)
// ----------------------------------------------------------------------------
// Wires the canonical North Star surface:
//
//   GET   /api/v1/dashboard/north-star               → tile payload
//   GET   /api/v1/customers/at-risk?cursor=&limit=&actioned=
//   POST  /api/v1/customers/{customer_external_id}/action
//
// Page layout:
//   Top row → 4 KPI tiles (resolved · total · resolution rate · actioned count)
//             + recent activity strip (latest 5 actioned customers)
//   Below   → cursor-paginated customer table with toggle button per row
//
// Closes CLAUDE.md §14 North Star limitation end-to-end (BE PR #124 + this FE).
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Target, TrendingUp, Users, Sparkles, CheckCircle2, Clock,
  Loader2, RotateCcw, AlertTriangle, ChevronLeft, ChevronRight,
  Filter, ShieldCheck,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api, formatVND, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types — mirror BE Pydantic shape
// ============================================================================

interface RecentActionItem {
  customer_external_id: string;
  revenue_at_risk:      number;
  actioned_at:          string;
  actioned_by_user:     string | null;
}

interface NorthStarTilePayload {
  total_at_risk_vnd:    number;
  resolved_vnd:         number;
  resolution_rate_pct:  number;
  actioned_count:       number;
  at_risk_count:        number;
  recent_actions:       RecentActionItem[];
}

interface AtRiskCustomer {
  customer_external_id: string;
  revenue_at_risk:      number;
  last_purchase_at:     string | null;
  purchase_count:       number;
  is_actioned:          boolean;
  actioned_at:          string | null;
  actioned_by_user:     string | null;
  computed_at:          string;
}

interface AtRiskListResponse {
  items:       AtRiskCustomer[];
  next_cursor: string | null;
}

type ActionedFilter = 'all' | 'pending' | 'resolved';

// ============================================================================
// Page
// ============================================================================

export default function CustomersAtRiskPage() {
  const t = useT();
  const [tile, setTile] = useState<NorthStarTilePayload | null>(null);
  const [tileLoading, setTileLoading] = useState(true);
  const [tileProblem, setTileProblem] = useState<ProblemDetails | null>(null);

  const [customers, setCustomers] = useState<AtRiskCustomer[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listProblem, setListProblem] = useState<ProblemDetails | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);

  const [filter, setFilter] = useState<ActionedFilter>('pending');
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function loadTile() {
    setTileLoading(true);
    setTileProblem(null);
    try {
      const r = await api<NorthStarTilePayload>('/api/v1/dashboard/north-star');
      setTile(r);
    } catch (e: any) {
      setTileProblem(e);
    } finally {
      setTileLoading(false);
    }
  }

  async function loadList(cursor: string | null = null) {
    setListLoading(true);
    setListProblem(null);
    try {
      const params = new URLSearchParams({ limit: '20' });
      if (filter === 'pending')  params.set('actioned', 'false');
      if (filter === 'resolved') params.set('actioned', 'true');
      if (cursor) params.set('cursor', cursor);

      const r = await api<AtRiskListResponse>(`/api/v1/customers/at-risk?${params}`);
      setCustomers(r.items ?? []);
      setNextCursor(r.next_cursor ?? null);
    } catch (e: any) {
      setListProblem(e);
    } finally {
      setListLoading(false);
    }
  }

  useEffect(() => {
    loadTile();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setCursorStack([]);
    loadList(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  async function toggleAction(c: AtRiskCustomer) {
    const next = !c.is_actioned;
    let notes: string | undefined;
    if (next) {
      const input = window.prompt(
        t('templatesF060CustomersAtRisk.promptNotes'),
        '',
      );
      if (input === null) return;            // cancelled
      notes = input.trim() || undefined;
    } else {
      if (!window.confirm(t('templatesF060CustomersAtRisk.confirmUnaction', { id: c.customer_external_id }))) return;
    }

    setPendingId(c.customer_external_id);
    setSuccess(null);
    try {
      await api(`/api/v1/customers/${encodeURIComponent(c.customer_external_id)}/action`, {
        method: 'POST',
        body:   JSON.stringify({ is_actioned: next, notes }),
      });
      setSuccess(next
        ? t('templatesF060CustomersAtRisk.successActioned', { id: c.customer_external_id })
        : t('templatesF060CustomersAtRisk.successUnactioned', { id: c.customer_external_id }),
      );
      // Refresh both — tile updates resolution rate, list updates the row.
      await Promise.all([loadTile(), loadList(cursorStack.at(-1) ?? null)]);
    } catch (e: any) {
      setListProblem(e);
    } finally {
      setPendingId(null);
    }
  }

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
        title={t('templatesF060CustomersAtRisk.pageTitle')}
        description={t('templatesF060CustomersAtRisk.pageDescription')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-6">
        {tileProblem && (
          <ErrorBanner
            problem={{
              ...tileProblem,
              title:  t('templatesF060CustomersAtRisk.errTileTitle'),
              detail: `${tileProblem.title}${tileProblem.detail ? ' — ' + tileProblem.detail : ''}.`,
            }}
          />
        )}
        {success && <SuccessBanner message={success} />}

        <NorthStarTile tile={tile} loading={tileLoading} />

        {/* Filter bar */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex items-center gap-3 shadow-soft-sm flex-wrap">
          <span className="text-xs text-[var(--text-secondary)] inline-flex items-center gap-1">
            <Filter className="w-3.5 h-3.5" /> {t('templatesF060CustomersAtRisk.filterLabel')}
          </span>
          {([
            { code: 'pending',  label: t('templatesF060CustomersAtRisk.filterPending') },
            { code: 'resolved', label: t('templatesF060CustomersAtRisk.filterResolved') },
            { code: 'all',      label: t('templatesF060CustomersAtRisk.filterAll') },
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

        {/* Customer table */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          {listProblem && (
            <div className="px-5 py-3 border-b border-[var(--border-color)]">
              <ErrorBanner
                problem={{
                  ...listProblem,
                  title:  listProblem.title ?? t('templatesF060CustomersAtRisk.errListTitle'),
                  detail: listProblem.detail ?? '',
                }}
              />
            </div>
          )}
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">{t('templatesF060CustomersAtRisk.thCustomer')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesF060CustomersAtRisk.thRevenueAtRisk')}</th>
                  <th className="px-5 py-3">{t('templatesF060CustomersAtRisk.thLastPurchase')}</th>
                  <th className="px-5 py-3 text-center">{t('templatesF060CustomersAtRisk.thOrderCount')}</th>
                  <th className="px-5 py-3">{t('templatesF060CustomersAtRisk.thStatus')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesF060CustomersAtRisk.thAction')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {listLoading && customers.length === 0 ? (
                  <tr><td colSpan={6} className="px-5 py-12 text-center text-[var(--text-secondary)]">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templatesF060CustomersAtRisk.loading')}
                  </td></tr>
                ) : customers.length === 0 ? (
                  <tr><td colSpan={6} className="px-5 py-12 text-center">
                    <CheckCircle2 className="w-10 h-10 mx-auto text-[var(--state-success)]/40 mb-3" />
                    <p className="text-sm text-[var(--text-secondary)]">
                      {filter === 'pending'
                        ? t('templatesF060CustomersAtRisk.emptyPending')
                        : filter === 'resolved'
                          ? t('templatesF060CustomersAtRisk.emptyResolved')
                          : t('templatesF060CustomersAtRisk.emptyAll')}
                    </p>
                  </td></tr>
                ) : (
                  customers.map((c) => (
                    <CustomerRow
                      key={c.customer_external_id}
                      customer={c}
                      pending={pendingId === c.customer_external_id}
                      onToggle={() => toggleAction(c)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {(cursorStack.length > 0 || nextCursor) && (
            <div className="px-5 py-3 border-t border-[var(--border-color)] flex items-center justify-between">
              <Button
                variant="tertiary" size="sm"
                onClick={pagePrev}
                disabled={cursorStack.length === 0 || listLoading}
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" /> {t('templatesF060CustomersAtRisk.pagePrev')}
              </Button>
              <span className="text-xs text-[var(--text-secondary)]">
                {t('templatesF060CustomersAtRisk.pageIndicator', { page: cursorStack.length + 1 })}
              </span>
              <Button
                variant="tertiary" size="sm"
                onClick={pageNext}
                disabled={!nextCursor || listLoading}
              >
                {t('templatesF060CustomersAtRisk.pageNext')} <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          )}
        </div>

        {/* Footer hint */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templatesF060CustomersAtRisk.footerPart1')} <span className="font-mono">kaori.feedback.actions</span> {t('templatesF060CustomersAtRisk.footerPart2')}{' '}
            <span className="font-mono">customer.actioned</span> / <span className="font-mono">customer.unactioned</span>.
            {t('templatesF060CustomersAtRisk.footerPart3')} <span className="font-mono">gold_features.is_actioned=true</span>.
            {t('templatesF060CustomersAtRisk.footerPart4')} <em>{t('templatesF060CustomersAtRisk.filterPending')}</em> {t('templatesF060CustomersAtRisk.footerPart5')}
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// North Star tile (reusable — exported for /dashboard wire later)
// ============================================================================

export function NorthStarTile({
  tile, loading,
}: { tile: NorthStarTilePayload | null; loading: boolean }) {
  const t = useT();
  if (loading && !tile) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-28 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse"
          />
        ))}
      </div>
    );
  }
  if (!tile) return null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KpiCard
          label={t('templatesF060CustomersAtRisk.kpiResolvedLabel')}
          value={formatVND(tile.resolved_vnd)}
          secondary={t('templatesF060CustomersAtRisk.kpiResolvedSecondary')}
          icon={Target}
          tone="success"
          highlight
        />
        <KpiCard
          label={t('templatesF060CustomersAtRisk.kpiTotalAtRiskLabel')}
          value={formatVND(tile.total_at_risk_vnd)}
          secondary={t('templatesF060CustomersAtRisk.kpiTotalAtRiskSecondary', { count: tile.at_risk_count })}
          icon={TrendingUp}
        />
        <KpiCard
          label={t('templatesF060CustomersAtRisk.kpiResolutionRateLabel')}
          value={`${tile.resolution_rate_pct.toFixed(1)}%`}
          secondary={t('templatesF060CustomersAtRisk.kpiResolutionRateSecondary', { actioned: tile.actioned_count, total: tile.at_risk_count })}
          icon={Sparkles}
        />
        <KpiCard
          label={t('templatesF060CustomersAtRisk.kpiActionedLabel')}
          value={tile.actioned_count.toLocaleString('vi-VN')}
          secondary={tile.at_risk_count > 0
            ? t('templatesF060CustomersAtRisk.kpiActionedSecondary', { count: tile.at_risk_count - tile.actioned_count })
            : '—'
          }
          icon={Users}
        />
      </div>

      {tile.recent_actions.length > 0 && (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4 text-[var(--state-success)]" />
            <h3 className="font-serif text-sm font-medium text-[var(--text-primary)]">
              {t('templatesF060CustomersAtRisk.recentActivity')}
            </h3>
            <Badge variant="default">{tile.recent_actions.length}</Badge>
          </div>
          <ul className="space-y-2">
            {tile.recent_actions.map((a) => (
              <li
                key={`${a.customer_external_id}-${a.actioned_at}`}
                className="flex items-center justify-between gap-3 text-xs"
              >
                <span className="font-mono text-[var(--text-primary)] truncate">
                  {a.customer_external_id}
                </span>
                <span className="font-medium text-[var(--state-success)]">
                  {formatVND(a.revenue_at_risk)}
                </span>
                <span className="text-[var(--text-secondary)] inline-flex items-center gap-1 shrink-0">
                  <Clock className="w-3 h-3" /> {formatRelative(a.actioned_at, t)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function KpiCard({
  label, value, secondary, icon: Icon, tone, highlight,
}: {
  label: string;
  value: string;
  secondary?: string;
  icon: any;
  tone?: 'success';
  highlight?: boolean;
}) {
  return (
    <div className={cn(
      'rounded-lg-custom border p-4 shadow-soft-sm',
      highlight
        ? 'bg-[var(--primary-gold)]/8 border-[var(--primary-gold)]/40'
        : 'bg-[var(--bg-card)] border-[var(--border-color)]',
    )}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">
          {label}
        </span>
        <Icon className={cn('w-4 h-4', tone === 'success' ? 'text-[var(--state-success)]' : 'text-[var(--primary-gold-dark)]')} />
      </div>
      <p className={cn(
        'font-serif text-[var(--text-primary)]',
        highlight ? 'text-2xl' : 'text-xl',
      )}>
        {value}
      </p>
      {secondary && (
        <p className="text-[11px] text-[var(--text-secondary)] mt-1 leading-snug">{secondary}</p>
      )}
    </div>
  );
}

// ============================================================================
// Customer row
// ============================================================================

function CustomerRow({
  customer: c, pending, onToggle,
}: {
  customer: AtRiskCustomer;
  pending: boolean;
  onToggle: () => void;
}) {
  const t = useT();
  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4">
        <p className="font-mono text-sm text-[var(--text-primary)]">{c.customer_external_id}</p>
        <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">
          {t('templatesF060CustomersAtRisk.computedAt')} {formatRelative(c.computed_at, t)}
        </p>
      </td>
      <td className="px-5 py-4 text-right">
        <p className="font-serif text-base text-[var(--text-primary)]">
          {formatVND(c.revenue_at_risk)}
        </p>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
        {c.last_purchase_at ? formatRelative(c.last_purchase_at, t) : '—'}
      </td>
      <td className="px-5 py-4 text-center text-xs text-[var(--text-primary)]">
        {c.purchase_count}
      </td>
      <td className="px-5 py-4">
        {c.is_actioned ? (
          <div className="inline-flex flex-col gap-0.5">
            <Badge variant="success">
              <CheckCircle2 className="w-3 h-3 mr-1" /> {t('templatesF060CustomersAtRisk.filterResolved')}
            </Badge>
            {c.actioned_at && (
              <span className="text-[10px] text-[var(--text-secondary)]">
                {formatRelative(c.actioned_at, t)}
              </span>
            )}
          </div>
        ) : (
          <Badge variant="warning">
            <AlertTriangle className="w-3 h-3 mr-1" /> {t('templatesF060CustomersAtRisk.filterPending')}
          </Badge>
        )}
      </td>
      <td className="px-5 py-4 text-right">
        <Button
          variant={c.is_actioned ? 'tertiary' : 'primary'}
          size="sm"
          onClick={onToggle}
          disabled={pending}
        >
          {pending ? (
            <><Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> {t('templatesF060CustomersAtRisk.writingInProgress')}</>
          ) : c.is_actioned ? (
            <><RotateCcw className="w-3.5 h-3.5 mr-1" /> {t('templatesF060CustomersAtRisk.unmarkAction')}</>
          ) : (
            <><CheckCircle2 className="w-3.5 h-3.5 mr-1" /> {t('templatesF060CustomersAtRisk.markResolvedAction')}</>
          )}
        </Button>
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
  if (Number.isNaN(diff)) return iso;
  if (diff < 60_000)         return t('templatesF060CustomersAtRisk.timeJustNow');
  if (diff < 3_600_000)      return t('templatesF060CustomersAtRisk.timeMinutesAgo', { count: Math.round(diff / 60_000) });
  if (diff < 86_400_000)     return t('templatesF060CustomersAtRisk.timeHoursAgo', { count: Math.round(diff / 3_600_000) });
  if (diff < 7 * 86_400_000) return t('templatesF060CustomersAtRisk.timeDaysAgo', { count: Math.round(diff / 86_400_000) });
  return new Date(iso).toLocaleDateString('vi-VN');
}
