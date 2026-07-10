// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 25. /p2/insights — Insight Feed (F-025)
// ----------------------------------------------------------------------------
// GET /api/v1/insights?cursor=&limit=&impact=&status=
//
// Sources:
//   - Bronze ingest anomaly detection (column drift, schema drift)
//   - Silver rule violations (PII spike, null spike)
//   - Gold features (churn risk delta, MoM revenue swing)
// Each insight carries `revenue_at_risk` (NUMERIC(14,4) VND) feeding the
// North Star: SUM(revenue_at_risk WHERE churn_risk_label='HIGH' AND is_actioned).
// `is_actioned` lives in `decision_actions` (Sprint 7 PR D); this page links
// to the decision row when conversion has happened.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  Lightbulb, Sparkles, Search, Bookmark, Database, Clock,
  Gavel, ChevronRight, AlertTriangle, TrendingUp, TrendingDown,
  CheckCircle2, AlertCircle, RefreshCw, LayoutGrid, List, Calculator,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  api, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type Impact   = 'HIGH' | 'MEDIUM' | 'LOW';
type Status   = 'NEW' | 'REVIEWED' | 'CONVERTED' | 'DISMISSED';
type Source   = 'bronze' | 'silver' | 'gold';

interface Insight {
  id:                   string;
  title:                string;
  description:          string;
  metric_name:          string;
  metric_value:         string;
  trend_pct?:           number;
  impact:               Impact;
  status:               Status;
  source:               Source;
  source_table:         string;
  revenue_at_risk_vnd:  number;
  churn_risk_label?:    'HIGH' | 'MEDIUM' | 'LOW';
  is_actioned?:         boolean;
  decision_id?:         string;
  bookmarked:           boolean;
  created_at:           string;
}

interface Page<T> {
  items:       T[];
  next_cursor: string | null;
  total:       number;
}

interface NorthStarSummary {
  total_revenue_at_risk_vnd: number;
  high_impact_unactioned:    number;
  high_impact_actioned:      number;
  actioned_revenue_vnd:      number;
}

const IMPACT_BADGE: Record<Impact, { variant: any; labelKey: string }> = {
  HIGH:   { variant: 'error',   labelKey: 'templates25InsightList.impactHigh' },
  MEDIUM: { variant: 'warning', labelKey: 'templates25InsightList.impactMedium' },
  LOW:    { variant: 'default', labelKey: 'templates25InsightList.impactLow' },
};

const STATUS_BADGE: Record<Status, { variant: any; labelKey: string }> = {
  NEW:       { variant: 'info',    labelKey: 'templates25InsightList.statusNew' },
  REVIEWED:  { variant: 'default', labelKey: 'templates25InsightList.statusReviewed' },
  CONVERTED: { variant: 'success', labelKey: 'templates25InsightList.statusConverted' },
  DISMISSED: { variant: 'default', labelKey: 'templates25InsightList.statusDismissed' },
};

const SOURCE_LABEL: Record<Source, string> = {
  bronze: 'Bronze',
  silver: 'Silver',
  gold:   'Gold',
};

export default function InsightListPage() {
  const t = useT();
  const [items,    setItems]    = useState<Insight[]>([]);
  const [cursor,   setCursor]   = useState<string | null>(null);
  const [hasMore,  setHasMore]  = useState(false);
  const [total,    setTotal]    = useState(0);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [northStar, setNorthStar] = useState<NorthStarSummary | null>(null);

  const [impactFilter, setImpactFilter] = useState<'ALL' | Impact>('ALL');
  const [statusFilter, setStatusFilter] = useState<'ALL' | Status>('ALL');
  const [search,       setSearch]       = useState('');
  const [view,         setView]         = useState<'grid' | 'list'>('grid');

  // BE reality (services/ai-orchestrator/routers):
  //   - List endpoint is GET /api/v1/insights/feed (LLM-generated cards from the
  //     latest analysis run). It returns {insights:[{id,title,body,category,...}]}
  //     with NO cursor pagination, NO server-side impact/status filters, NO total.
  //   - North Star tile is GET /api/v1/dashboard/north-star → NorthStarTileResponse
  //     {total_at_risk_vnd, resolved_vnd, actioned_count, at_risk_count, ...}.
  // The richer Insight shape this template was designed for (impact/status/source/
  // metric/revenue) is not backed by BE yet — we map category→impact and fill
  // neutral defaults so the page renders without crashing.
  function mapFeedItem(it: any): Insight {
    const category = String(it.category ?? 'trend');
    const impact: Impact =
      category === 'risk' ? 'HIGH'
        : category === 'anomaly' ? 'MEDIUM'
        : 'LOW';
    return {
      id:                  String(it.id ?? ''),
      title:               String(it.title ?? t('templates25InsightList.noTitle')),
      description:         String(it.body ?? it.disclaimer ?? ''),
      metric_name:         category === 'opportunity' ? t('templates25InsightList.metricOpportunity')
                            : category === 'risk' ? t('templates25InsightList.metricRisk')
                            : category === 'anomaly' ? t('templates25InsightList.metricAnomaly') : t('templates25InsightList.metricTrend'),
      metric_value:        '—',
      impact,
      status:              'NEW',
      source:              'gold',
      source_table:        'analysis_results',
      revenue_at_risk_vnd: 0,
      bookmarked:          false,
      created_at:          '',
    };
  }

  async function load(reset = true) {
    setLoading(true);
    setProblem(null);
    try {
      const [feed, ns] = await Promise.all([
        api<{ insights?: any[] }>(`/api/v1/insights/feed?limit=50`),
        reset
          ? api<any>('/api/v1/dashboard/north-star').catch(() => null)
          : Promise.resolve(northStar),
      ]);
      const mapped = (feed.insights ?? []).map(mapFeedItem);
      setItems(mapped);
      // /insights/feed is a single-shot list (no cursor) — no "load more".
      setCursor(null);
      setHasMore(false);
      setTotal(mapped.length);
      // Adapt NorthStarTileResponse → the NorthStarSummary shape this card reads.
      if (ns) {
        setNorthStar({
          total_revenue_at_risk_vnd: Number(ns.total_at_risk_vnd ?? 0),
          actioned_revenue_vnd:      Number(ns.resolved_vnd ?? 0),
          high_impact_unactioned:    Math.max(0, Number(ns.at_risk_count ?? 0) - Number(ns.actioned_count ?? 0)),
          high_impact_actioned:      Number(ns.actioned_count ?? 0),
        });
      }
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }

  // /insights/feed has no server-side filters → filter client-side over the
  // single fetched page. Re-load only on mount (filters no longer hit the BE).
  useEffect(() => { load(true); }, []);

  const visibleItems = items.filter((ins) => {
    if (impactFilter !== 'ALL' && ins.impact !== impactFilter) return false;
    if (statusFilter !== 'ALL' && ins.status !== statusFilter) return false;
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      if (!`${ins.title} ${ins.description}`.toLowerCase().includes(q)) return false;
    }
    return true;
  });

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    // client-side filter recomputes from `search` state — nothing else to do.
  }

  return (
    <>
      <PageHeader
        title={t('templates25InsightList.pageTitle')}
        description={t('templates25InsightList.pageDescription')}
        actions={
          <>
            <Button variant="secondary" onClick={() => load(true)}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('templates25InsightList.btnRefresh')}
            </Button>
            <Button onClick={() => (window.location.href = '/p2/insights/generate')}>
              <Sparkles className="w-4 h-4 mr-2" />
              {t('templates25InsightList.btnCreateNew')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />

        {/* North Star tile (F-060 placeholder — uses decision_actions side table per Sprint 7 PR D) */}
        {northStar && <NorthStarCard summary={northStar} />}

        {/* Filter bar */}
        <form
          onSubmit={onSearchSubmit}
          className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-3 shadow-soft-sm flex flex-col lg:flex-row items-stretch lg:items-center gap-3"
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('templates25InsightList.searchPlaceholder')}
              className="w-full pl-9 pr-4 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
            />
          </div>
          <select
            value={impactFilter}
            onChange={(e) => setImpactFilter(e.target.value as any)}
            className="px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none"
          >
            <option value="ALL">{t('templates25InsightList.filterAllImpact')}</option>
            <option value="HIGH">{t('templates25InsightList.filterImpactHigh')}</option>
            <option value="MEDIUM">{t('templates25InsightList.filterImpactMedium')}</option>
            <option value="LOW">{t('templates25InsightList.filterImpactLow')}</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as any)}
            className="px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none"
          >
            <option value="ALL">{t('templates25InsightList.filterAllStatus')}</option>
            <option value="NEW">{t('templates25InsightList.statusNew')}</option>
            <option value="REVIEWED">{t('templates25InsightList.statusReviewed')}</option>
            <option value="CONVERTED">{t('templates25InsightList.statusConverted')}</option>
            <option value="DISMISSED">{t('templates25InsightList.statusDismissed')}</option>
          </select>
          <div className="flex items-center gap-1 px-1 py-1 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom">
            <button
              type="button"
              onClick={() => setView('grid')}
              className={cn(
                'p-1.5 rounded-sm-custom',
                view === 'grid' ? 'bg-[var(--bg-card)] shadow-soft-sm text-[var(--primary-gold-dark)]' : 'text-[var(--text-secondary)]',
              )}
              aria-label={t('templates25InsightList.ariaGridView')}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setView('list')}
              className={cn(
                'p-1.5 rounded-sm-custom',
                view === 'list' ? 'bg-[var(--bg-card)] shadow-soft-sm text-[var(--primary-gold-dark)]' : 'text-[var(--text-secondary)]',
              )}
              aria-label={t('templates25InsightList.ariaListView')}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </form>

        <p className="text-xs text-[var(--text-secondary)]">
          {t('templates25InsightList.totalCount', { total: (total ?? 0).toLocaleString('vi-VN'), shown: visibleItems.length })}
        </p>

        {loading && items.length === 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {[1,2,3,4,5,6].map((i) => (
              <div key={i} className="h-56 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
            ))}
          </div>
        ) : visibleItems.length === 0 ? (
          <EmptyState onClear={() => { setImpactFilter('ALL'); setStatusFilter('ALL'); setSearch(''); }} />
        ) : view === 'grid' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {visibleItems.map((ins) => <InsightCard key={ins.id} insight={ins} />)}
          </div>
        ) : (
          <div className="space-y-3">
            {visibleItems.map((ins) => <InsightRow key={ins.id} insight={ins} />)}
          </div>
        )}
      </div>
    </>
  );
}

// ----------------------------------------------------------------------------
// North Star tile (F-060 — uses decision_actions side table for Phase 1)
// ----------------------------------------------------------------------------

function NorthStarCard({ summary }: { summary: NorthStarSummary }) {
  const t = useT();
  const total = summary.total_revenue_at_risk_vnd;
  const acted = summary.actioned_revenue_vnd;
  const pct   = total > 0 ? Math.round((acted / total) * 100) : 0;

  return (
    <div className="bg-[var(--primary-gold)]/4 rounded-lg-custom border border-[var(--primary-gold)]/30 p-5 shadow-soft-sm">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">North Star</p>
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('templates25InsightList.nsTitle')}</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {t('templates25InsightList.nsFormula')}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="font-serif text-2xl text-[var(--text-primary)]">{formatVND(acted)}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t('templates25InsightList.nsOfTotal', { total: formatVND(total) })}</p>
          <Badge variant={pct >= 60 ? 'success' : pct >= 30 ? 'warning' : 'error'} className="mt-1">
            {t('templates25InsightList.nsPctResolved', { pct })}
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mt-4">
        <div className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{t('templates25InsightList.nsHighImpactPending')}</p>
          <p className="font-serif text-xl text-[#9B5050] mt-1">{summary.high_impact_unactioned}</p>
        </div>
        <div className="rounded-md-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-3">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{t('templates25InsightList.nsHighImpactActioned')}</p>
          <p className="font-serif text-xl text-[#5C856A] mt-1">{summary.high_impact_actioned}</p>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Card + row renderers
// ----------------------------------------------------------------------------

function InsightCard({ insight: ins }: { insight: Insight }) {
  const t = useT();
  return (
    <a
      href={`/p2/insights/${ins.id}`}
      className="group bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 transition-all hover:shadow-soft-md flex flex-col"
    >
      <div className="p-5 flex-1 flex flex-col">
        <div className="flex items-start justify-between gap-2 mb-3">
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant={IMPACT_BADGE[ins.impact].variant}>{t(IMPACT_BADGE[ins.impact].labelKey)}</Badge>
            <Badge variant={STATUS_BADGE[ins.status].variant}>{t(STATUS_BADGE[ins.status].labelKey)}</Badge>
          </div>
          <Bookmark
            className={cn(
              'w-4 h-4 shrink-0',
              ins.bookmarked ? 'text-[var(--primary-gold-dark)] fill-current' : 'text-[var(--text-secondary)]/40',
            )}
          />
        </div>

        <h3 className="font-serif text-base text-[var(--text-primary)] leading-snug mb-2 group-hover:text-[var(--primary-gold-dark)] transition-colors">
          {ins.title}
        </h3>
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed line-clamp-3 mb-3">
          {ins.description}
        </p>

        <div className="rounded-md-custom bg-[var(--bg-app)]/50 border border-[var(--border-color)]/40 p-3 mb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Calculator className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
              <span className="text-xs text-[var(--text-secondary)]">{ins.metric_name}</span>
            </div>
            <span className="font-mono text-sm font-semibold text-[var(--text-primary)]">{ins.metric_value}</span>
          </div>
          {ins.trend_pct != null && (
            <div className={cn(
              'mt-1 flex items-center gap-1 text-xs',
              ins.trend_pct >= 0 ? 'text-[#5C856A]' : 'text-[#9B5050]',
            )}>
              {ins.trend_pct >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
              <span>{ins.trend_pct >= 0 ? '+' : ''}{ins.trend_pct.toFixed(1)}%</span>
            </div>
          )}
        </div>

        {ins.revenue_at_risk_vnd > 0 && (
          <div className="flex items-center gap-2 text-xs mb-3">
            <AlertTriangle className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
            <span className="text-[var(--text-secondary)]">{t('templates25InsightList.revenueAtRiskLabel')}</span>
            <span className="font-medium text-[var(--text-primary)]">{formatVND(ins.revenue_at_risk_vnd)}</span>
          </div>
        )}

        <div className="mt-auto flex items-center gap-3 text-[11px] text-[var(--text-secondary)]">
          <span className="inline-flex items-center gap-1">
            <Database className="w-3 h-3" />
            {SOURCE_LABEL[ins.source]} · <span className="font-mono">{ins.source_table}</span>
          </span>
          <span className="inline-flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {ins.created_at}
          </span>
        </div>
      </div>

      <div className="px-5 py-3 border-t border-[var(--border-color)]/60 bg-[var(--bg-app)]/30 rounded-b-lg-custom flex items-center justify-between">
        <span className="text-xs text-[var(--text-secondary)] inline-flex items-center">
          {t('templates25InsightList.viewDetails')} <ChevronRight className="w-3 h-3 ml-0.5" />
        </span>
        {ins.is_actioned && ins.decision_id ? (
          <a
            href={`/p2/decisions/${ins.decision_id}`}
            onClick={(e) => e.stopPropagation()}
            className="text-xs font-medium text-[#5C856A] inline-flex items-center gap-1 hover:underline"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            {t('templates25InsightList.actioned')}
          </a>
        ) : ins.status === 'NEW' || ins.status === 'REVIEWED' ? (
          <span className="text-xs font-medium text-[var(--primary-gold-dark)] inline-flex items-center gap-1">
            <Gavel className="w-3.5 h-3.5" />
            {t('templates25InsightList.createDecision')}
          </span>
        ) : null}
      </div>
    </a>
  );
}

function InsightRow({ insight: ins }: { insight: Insight }) {
  const t = useT();
  return (
    <a
      href={`/p2/insights/${ins.id}`}
      className="block bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 hover:shadow-soft-sm transition-all p-4"
    >
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
          <Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <Badge variant={IMPACT_BADGE[ins.impact].variant}>{t(IMPACT_BADGE[ins.impact].labelKey)}</Badge>
            <Badge variant={STATUS_BADGE[ins.status].variant}>{t(STATUS_BADGE[ins.status].labelKey)}</Badge>
            <span className="text-[11px] text-[var(--text-secondary)]">{ins.created_at}</span>
          </div>
          <h3 className="font-medium text-sm text-[var(--text-primary)] leading-snug mb-0.5">{ins.title}</h3>
          <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{ins.description}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="font-mono text-sm font-semibold text-[var(--text-primary)]">{ins.metric_value}</p>
          {ins.revenue_at_risk_vnd > 0 && (
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{formatVND(ins.revenue_at_risk_vnd)}</p>
          )}
        </div>
      </div>
    </a>
  );
}

function EmptyState({ onClear }: { onClear: () => void }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-dashed border-[var(--border-color)] p-12 text-center">
      <div className="w-14 h-14 mx-auto rounded-full bg-[var(--bg-app)] flex items-center justify-center mb-3">
        <Lightbulb className="w-6 h-6 text-[var(--text-secondary)]/60" />
      </div>
      <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('templates25InsightList.emptyTitle')}</h3>
      <p className="text-sm text-[var(--text-secondary)] mt-1 max-w-sm mx-auto">
        {t('templates25InsightList.emptyDesc')}
      </p>
      <div className="mt-4 flex items-center justify-center gap-2">
        <Button variant="secondary" onClick={onClear}>{t('templates25InsightList.clearFilters')}</Button>
        <Button onClick={() => (window.location.href = '/p2/insights/generate')}>
          <Sparkles className="w-4 h-4 mr-2" />
          {t('templates25InsightList.createInsight')}
        </Button>
      </div>
    </div>
  );
}
