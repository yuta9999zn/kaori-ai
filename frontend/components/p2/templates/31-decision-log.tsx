// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 31. /p2/decisions — AI Decision Log (F-029 + Sprint 7 PR D North Star)
// ----------------------------------------------------------------------------
// GET /api/v1/decisions?cursor=&limit=&q=&framework=&risk=&actioned=
// POST /api/v1/decisions/{id}/action  (UPSERT into decision_actions)
// GET /api/v1/decisions/export.csv    (UTF-8 BOM, 10k row hard cap)
//
// Per `decision_audit_log` schema (K-6) — every automated decision is logged
// with confidence + alternatives_considered + audit_log_link. Sprint 7 PR D
// added the manual `is_actioned` toggle (lives in a side table
// `decision_actions` with FK CASCADE; one row per decision; UPSERT semantics).
// Phase 2 F-060 promotes this to the canonical `gold_features.is_actioned`
// column.
//
// Critical guardrails:
//   - cursor pagination (max 500 per page per CLAUDE.md §6)
//   - CSV export uses fetch + Blob; UTF-8 BOM for Vietnamese Excel compat;
//     server enforces 10k row cap (returns 413 problem+json above that)
//   - Idempotency-Key on PATCH/POST (handled by `api()` helper, K-13)
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  CheckSquare, Square, Search, Filter, Download, RefreshCw,
  Gavel, ShieldCheck, AlertTriangle, ChevronRight, ExternalLink,
  Loader2, FileText, Sparkles,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api, formatVND,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type Framework = 'NONE' | 'SWOT' | '6W' | '2H' | 'Fishbone' | 'MoM' | 'YoY';
type RiskLabel = 'HIGH' | 'MEDIUM' | 'LOW';

interface AlternativeConsidered {
  title:       string;
  rejected_reason: string;
  confidence:  number;
}

interface Decision {
  id:                       string;
  title:                    string;
  summary:                  string;
  framework:                Framework;
  confidence:               number;
  churn_risk_label?:        RiskLabel;
  revenue_at_risk_vnd:      number;

  // K-6 audit
  alternatives_considered:  AlternativeConsidered[];
  audit_log_id:             string;

  // Linkage
  insight_id?:              string;
  pipeline_id?:             string;
  owner_user?:              string;
  owner_role?:              'MANAGER' | 'OPERATOR' | 'ANALYST';

  // Sprint 7 PR D — North Star side table
  is_actioned:              boolean;
  actioned_at?:             string;
  actioned_by?:             string;

  created_at:               string;
}

// BE list envelope: { data: [...], meta: { cursor } }. Both optional so a
// shape change never crashes the page — load() guards every access.
interface DecisionPage {
  data?: Decision[];
  meta?: { cursor?: string | null };
}

// NONE is display-translated at render time (t('templates31DecisionLog.frameworkFree'));
// the rest are framework codes (SWOT/6W/2H/...) and stay as-is in every locale.
const FRAMEWORK_LABEL: Record<Framework, string> = {
  NONE:     'Tự do',
  SWOT:     'SWOT',
  '6W':     '6W',
  '2H':     '2H',
  Fishbone: 'Fishbone',
  MoM:      'MoM',
  YoY:      'YoY',
};

const RISK_VARIANT: Record<RiskLabel, any> = {
  HIGH:   'error',
  MEDIUM: 'warning',
  LOW:    'default',
};

const RISK_LABEL_KEY: Record<RiskLabel, string> = {
  HIGH:   'templates31DecisionLog.riskHigh',
  MEDIUM: 'templates31DecisionLog.riskMedium',
  LOW:    'templates31DecisionLog.riskLow',
};

const PAGE_LIMIT       = 50;
const CSV_EXPORT_CAP   = 10_000;

export default function DecisionLogPage() {
  const t = useT();
  const [items,    setItems]    = useState<Decision[]>([]);
  const [cursor,   setCursor]   = useState<string | null>(null);
  const [hasMore,  setHasMore]  = useState(false);
  const [total,    setTotal]    = useState(0);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  // Filters
  const [search,    setSearch]    = useState('');
  const [frameworkFilter, setFrameworkFilter] = useState<'ALL' | Framework>('ALL');
  const [riskFilter,      setRiskFilter]      = useState<'ALL' | RiskLabel>('ALL');
  const [actionedFilter,  setActionedFilter]  = useState<'ALL' | 'ACTIONED' | 'PENDING'>('ALL');

  // Per-row toggle in-flight tracking
  const [pendingAction, setPendingAction] = useState<Set<string>>(new Set());

  async function load(reset = true) {
    setLoading(true);
    setProblem(null);
    try {
      const params = new URLSearchParams();
      if (!reset && cursor) params.set('cursor', cursor);
      params.set('limit', String(PAGE_LIMIT));
      if (search.trim())                 params.set('q', search.trim());
      if (frameworkFilter !== 'ALL')     params.set('framework', frameworkFilter);
      if (riskFilter !== 'ALL')          params.set('risk', riskFilter);
      if (actionedFilter === 'ACTIONED') params.set('actioned', 'true');
      if (actionedFilter === 'PENDING')  params.set('actioned', 'false');

      // BE returns the standard envelope { data: [...], meta: { cursor } } —
      // NOT { items, next_cursor, total }. Read the real shape + guard every
      // field so a missing key never crashes the page (.length / .toLocaleString).
      const page = await api<DecisionPage>(`/api/v1/decisions?${params.toString()}`);
      const arr = Array.isArray(page?.data) ? page.data : [];
      const nextItems = reset ? arr : [...items, ...arr];
      setItems(nextItems);
      const nextCursor = page?.meta?.cursor ?? null;
      setCursor(nextCursor);
      setHasMore(!!nextCursor);
      // No `total` in the envelope — use the loaded count (avoids .toLocaleString on undefined).
      setTotal(nextItems.length);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(true); }, [frameworkFilter, riskFilter, actionedFilter]);

  function onSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    load(true);
  }

  async function toggleActioned(d: Decision) {
    const next = !d.is_actioned;
    setPendingAction((s) => new Set(s).add(d.id));
    setItems((prev) => prev.map((x) => x.id === d.id ? { ...x, is_actioned: next } : x));
    try {
      await api(`/api/v1/decisions/${d.id}/action`, {
        method: 'POST',
        body:   JSON.stringify({ is_actioned: next }),
      });
    } catch (err: any) {
      // rollback
      setItems((prev) => prev.map((x) => x.id === d.id ? { ...x, is_actioned: d.is_actioned } : x));
      setProblem(err);
    } finally {
      setPendingAction((s) => { const n = new Set(s); n.delete(d.id); return n; });
    }
  }

  async function exportCsv() {
    setExporting(true);
    setProblem(null);
    try {
      const params = new URLSearchParams();
      if (search.trim())                 params.set('q', search.trim());
      if (frameworkFilter !== 'ALL')     params.set('framework', frameworkFilter);
      if (riskFilter !== 'ALL')          params.set('risk', riskFilter);
      if (actionedFilter === 'ACTIONED') params.set('actioned', 'true');
      if (actionedFilter === 'PENDING')  params.set('actioned', 'false');

      // fetch + Blob — never put JWT in URL (Sprint 7 PR A pattern)
      const res = await fetch(`/api/v1/decisions/export.csv?${params.toString()}`, {
        headers: {
          Authorization: `Bearer ${window.localStorage.getItem('kaori.access_token') ?? window.localStorage.getItem('kaori_jwt') ?? ''}`,
          Accept:        'text/csv, application/problem+json',
        },
      });
      if (!res.ok) {
        if (res.status === 413) {
          setProblem({
            title:  t('templates31DecisionLog.errExportLimitTitle'),
            detail: t('templates31DecisionLog.errExportLimitDetail', { cap: CSV_EXPORT_CAP.toLocaleString('vi-VN') }),
            status: 413,
          });
          return;
        }
        const body = await res.json().catch(() => null);
        throw {
          title:  body?.title ?? `HTTP ${res.status}`,
          detail: body?.detail,
          status: res.status,
        };
      }

      // Server returns UTF-8 BOM-prefixed CSV (PR #74 / Sprint 3) — surface as download.
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      const ts   = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
      a.download = `decisions-${ts}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setSuccess(t('templates31DecisionLog.exportSuccess', { cap: CSV_EXPORT_CAP.toLocaleString('vi-VN') }));
    } catch (err: any) {
      setProblem(err?.title ? err : { title: t('templates31DecisionLog.errExportFailedTitle'), detail: String(err?.message ?? err) });
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates31DecisionLog.pageTitle')}
        description={t('templates31DecisionLog.pageDescription')}
        actions={
          <>
            <Button variant="secondary" onClick={() => load(true)}>
              <RefreshCw className="w-4 h-4 mr-2" />
              {t('templates31DecisionLog.btnRefresh')}
            </Button>
            <Button variant="secondary" onClick={exportCsv} isLoading={exporting}>
              <Download className="w-4 h-4 mr-2" />
              {t('templates31DecisionLog.btnExportCsv')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1500px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

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
              placeholder={t('templates31DecisionLog.searchPlaceholder')}
              className="w-full pl-9 pr-4 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
            />
          </div>
          <select
            value={frameworkFilter}
            onChange={(e) => setFrameworkFilter(e.target.value as any)}
            className="px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none"
          >
            <option value="ALL">{t('templates31DecisionLog.optAllFrameworks')}</option>
            {(Object.keys(FRAMEWORK_LABEL) as Framework[]).map((f) => (
              <option key={f} value={f}>{f === 'NONE' ? t('templates31DecisionLog.frameworkFree') : FRAMEWORK_LABEL[f]}</option>
            ))}
          </select>
          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value as any)}
            className="px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none"
          >
            <option value="ALL">{t('templates31DecisionLog.optAllRisk')}</option>
            <option value="HIGH">{t(RISK_LABEL_KEY.HIGH)}</option>
            <option value="MEDIUM">{t(RISK_LABEL_KEY.MEDIUM)}</option>
            <option value="LOW">{t(RISK_LABEL_KEY.LOW)}</option>
          </select>
          <select
            value={actionedFilter}
            onChange={(e) => setActionedFilter(e.target.value as any)}
            className="px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none"
          >
            <option value="ALL">{t('templates31DecisionLog.optAllStatus')}</option>
            <option value="ACTIONED">{t('templates31DecisionLog.optActioned')}</option>
            <option value="PENDING">{t('templates31DecisionLog.optPending')}</option>
          </select>
          <button type="submit" className="px-3 py-2 bg-[var(--primary-gold)]/10 border border-[var(--primary-gold)]/30 text-[var(--primary-gold-dark)] text-xs font-medium rounded-md-custom hover:bg-[var(--primary-gold)]/20">
            <Filter className="w-3.5 h-3.5 inline mr-1" />
            {t('templates31DecisionLog.btnFilter')}
          </button>
        </form>

        <p className="text-xs text-[var(--text-secondary)]">
          {t('templates31DecisionLog.summaryLine', {
            total: (total ?? 0).toLocaleString('vi-VN'),
            showing: items.length,
            cap: CSV_EXPORT_CAP.toLocaleString('vi-VN'),
          })}
        </p>

        {/* Table */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]/60">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-32">{t('templates31DecisionLog.colActioned')}</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{t('templates31DecisionLog.colDecision')}</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-32">{t('templates31DecisionLog.colFramework')}</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-32">{t('templates31DecisionLog.colConfidence')}</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-40">{t('templates31DecisionLog.colRevenueAtRisk')}</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-40">{t('templates31DecisionLog.colAlternatives')}</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-32">{t('templates31DecisionLog.colCreatedAt')}</th>
                  <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-24" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading && items.length === 0 ? (
                  Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={8} className="px-4 py-3">
                        <div className="h-8 bg-[var(--bg-app)] rounded-sm-custom animate-pulse" />
                      </td>
                    </tr>
                  ))
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-12 text-center text-[var(--text-secondary)]">
                      <Gavel className="w-10 h-10 mx-auto mb-2 text-[var(--text-secondary)]/40" />
                      {t('templates31DecisionLog.emptyState')}
                    </td>
                  </tr>
                ) : items.map((d) => (
                  <tr key={d.id} className="hover:bg-[var(--bg-app)]/30">
                    <td className="px-4 py-3 align-top">
                      <ActionedToggle
                        decision={d}
                        pending={pendingAction.has(d.id)}
                        onToggle={() => toggleActioned(d)}
                      />
                    </td>
                    <td className="px-4 py-3 align-top">
                      <a
                        href={`/p2/decisions/${d.id}`}
                        className="font-medium text-sm text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)]"
                      >
                        {d.title}
                      </a>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5 line-clamp-2 max-w-md leading-snug">{d.summary}</p>
                      <div className="mt-1.5 flex items-center gap-1.5 flex-wrap">
                        {d.churn_risk_label && (
                          <Badge variant={RISK_VARIANT[d.churn_risk_label]}>
                            {t(RISK_LABEL_KEY[d.churn_risk_label])}
                          </Badge>
                        )}
                        {d.insight_id && (
                          <a
                            href={`/p2/insights/${d.insight_id}`}
                            className="text-[11px] text-[var(--primary-gold-dark)] hover:underline inline-flex items-center gap-0.5"
                          >
                            {t('templates31DecisionLog.linkInsightSource')}
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <Badge variant="default">{d.framework === 'NONE' ? t('templates31DecisionLog.frameworkFree') : FRAMEWORK_LABEL[d.framework]}</Badge>
                    </td>
                    <td className="px-4 py-3 align-top">
                      <ConfidencePill confidence={d.confidence} />
                    </td>
                    <td className="px-4 py-3 align-top">
                      {d.revenue_at_risk_vnd > 0 ? (
                        <span className="font-mono text-xs text-[var(--text-primary)]">
                          {formatVND(d.revenue_at_risk_vnd)}
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--text-secondary)]">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top">
                      {(d.alternatives_considered ?? []).length > 0 ? (
                        <details className="text-xs">
                          <summary className="cursor-pointer text-[var(--primary-gold-dark)] hover:underline">
                            {t('templates31DecisionLog.altCount', { count: (d.alternatives_considered ?? []).length })}
                          </summary>
                          <ul className="mt-2 space-y-1.5">
                            {(d.alternatives_considered ?? []).map((alt, i) => (
                              <li key={i} className="border-l-2 border-[var(--border-color)] pl-2">
                                <p className="font-medium text-[var(--text-primary)]">{alt.title}</p>
                                <p className="text-[var(--text-secondary)] mt-0.5">
                                  {t('templates31DecisionLog.altRejected', { reason: alt.rejected_reason })}
                                </p>
                              </li>
                            ))}
                          </ul>
                        </details>
                      ) : (
                        <span className="text-xs text-[var(--text-secondary)]">{t('templates31DecisionLog.noAlternatives')}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top text-xs text-[var(--text-secondary)] whitespace-nowrap">
                      {d.created_at}
                    </td>
                    <td className="px-4 py-3 align-top text-right">
                      <a
                        href={`/p2/decisions/${d.id}`}
                        className="inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] hover:underline"
                      >
                        {t('templates31DecisionLog.linkDetail')}
                        <ChevronRight className="w-3 h-3 ml-0.5" />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {hasMore && (
            <div className="px-4 py-3 border-t border-[var(--border-color)]/60 flex justify-center">
              <Button variant="secondary" onClick={() => load(false)} isLoading={loading}>
                {t('templates31DecisionLog.btnLoadMore')}
              </Button>
            </div>
          )}
        </div>

        {/* Footer note */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            <span className="font-medium text-[var(--text-primary)]">{t('templates31DecisionLog.footerLabel')}</span> {t('templates31DecisionLog.footerPart1')}{' '}
            <span className="font-mono">decision_actions</span> {t('templates31DecisionLog.footerPart2')}{' '}
            <span className="font-mono">gold_features.is_actioned</span> {t('templates31DecisionLog.footerPart3')}
          </p>
        </div>
      </div>
    </>
  );
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

function ActionedToggle({
  decision: d, pending, onToggle,
}: { decision: Decision; pending: boolean; onToggle: () => void }) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={pending}
      aria-pressed={d.is_actioned}
      aria-label={d.is_actioned ? t('templates31DecisionLog.ariaUnmarkActioned') : t('templates31DecisionLog.ariaMarkActioned')}
      className={cn(
        'inline-flex items-center gap-2 px-2.5 py-1 rounded-md-custom border text-xs font-medium transition-colors',
        d.is_actioned
          ? 'border-[var(--state-success)]/40 bg-[var(--state-success)]/10 text-[#5C856A] hover:bg-[var(--state-success)]/15'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--primary-gold)]/40',
        pending && 'opacity-60 cursor-not-allowed',
      )}
    >
      {pending ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : d.is_actioned ? (
        <CheckSquare className="w-3.5 h-3.5" />
      ) : (
        <Square className="w-3.5 h-3.5" />
      )}
      {d.is_actioned ? t('templates31DecisionLog.optActioned') : t('templates31DecisionLog.toggleLabelPending')}
    </button>
  );
}

function ConfidencePill({ confidence }: { confidence: number }) {
  const pct = Math.round(confidence * 100);
  const variant: any =
    pct >= 80 ? 'success' : pct >= 60 ? 'warning' : 'error';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full bg-[var(--border-color)]/60 overflow-hidden">
        <div
          className={cn(
            'h-full rounded-full',
            pct >= 80 ? 'bg-[var(--state-success)]'
              : pct >= 60 ? 'bg-[var(--state-warning)]'
              : 'bg-[var(--state-error)]',
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <Badge variant={variant}>{pct}%</Badge>
    </div>
  );
}
