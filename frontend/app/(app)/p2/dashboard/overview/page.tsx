'use client';

/**
 * P2-03 — Enterprise Dashboard Overview (F-028).
 *
 * ⭐ REFERENCE PATTERN for the FE restructure (pilot-first, 2026-05-24).
 * This is the first screen wired to the REAL backend instead of hardcoded
 * mock data. Replicate this shape when wiring the other screens:
 *
 *   1. `'use client'` + `useQuery` (lib/query-client provides the provider).
 *   2. Fetch via `api<T>()` from `@/lib/api` — sends the JWT; the gateway
 *      injects X-Enterprise-ID from claims (K-7 / K-12, never sent by FE).
 *   3. One query per endpoint; independent queries so a slow one (insights →
 *      LLM) never blocks the cheap SQL tiles.
 *   4. Explicit response types matching the router (no `any`, no @ts-nocheck).
 *   5. Every query renders loading (Skeleton) / error (message + retry) /
 *      empty states — never a blank frame.
 *   6. Money via fmtVND / fmtVNDShort (K-9 + VND format rule); Vietnamese
 *      business language (tenet 7).
 *
 * The mock design lives in `components/p2/templates/09-dashboard-overview.tsx`
 * (kept as visual reference; do not import — it runs on hardcoded data).
 *
 * Backend (ai-orchestrator, via gateway :8080):
 *   GET /api/v1/dashboard/state       — 5-state machine
 *   GET /api/v1/dashboard/north-star  — ROI headline (North Star metric)
 *   GET /api/v1/billing/summary       — K-11 quota usage
 *   GET /api/v1/insights/feed         — AI insight cards (LLM, may be slow)
 */

import Link from 'next/link';
import {
  UploadCloud, Activity, CheckCircle2, AlertTriangle, ArrowRight,
  Sparkles, ShieldAlert, RefreshCw, TrendingUp,
} from 'lucide-react';

import {
  useDashboardState, useNorthStar, useBillingSummary, useInsightsFeed,
  type DashboardStateName,
} from '@/lib/hooks';
import { useT } from '@/lib/i18n/provider';
import { useChromeT } from '@/lib/i18n/chrome-i18n';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { KpiCard } from '@/components/ui/kpi-card';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { fmtVNDShort } from '@/lib/format';

// Response types now live with their hooks in lib/hooks/use-dashboard.ts
// (S0b foundation). DashboardStateName is imported above for PROGRESS_COPY.

// ── State-machine copy (in-progress states get a banner + a continue CTA) ────

// NOTE: values below are i18n keys (not display text) — resolved via t() at
// the render site inside the component, since this Record is module-scope
// and cannot call the useT() hook.
const PROGRESS_COPY: Record<
  Exclude<DashboardStateName, 'no_data' | 'results_ready'>,
  { label: string; tone: BadgeTone; cta: { href: string; label: string } }
> = {
  first_upload:   { label: 'overviewPage.stateFirstUpload',   tone: 'info',    cta: { href: '/p2/pipelines', label: 'overviewPage.ctaViewProgress' } },
  pending_review: { label: 'overviewPage.statePendingReview', tone: 'warning', cta: { href: '/p2/pipelines', label: 'overviewPage.ctaConfirmColumns' } },
  analysis_ready: { label: 'overviewPage.stateAnalysisReady', tone: 'brand',   cta: { href: '/p2/analysis/hub', label: 'overviewPage.ctaStartAnalysis' } },
};

const INSIGHT_TONE: Record<string, BadgeTone> = {
  trend: 'info', opportunity: 'success', anomaly: 'warning', risk: 'danger',
};

export default function DashboardOverviewPage() {
  // S0b: per-domain hooks replace the inline useQuery boilerplate. Same
  // independent-queries contract — a slow insights (LLM) query never blocks
  // the cheap SQL tiles.
  const t = useT();
  const stateQ = useDashboardState();
  const northStarQ = useNorthStar();
  const billingQ = useBillingSummary();
  const insightsQ = useInsightsFeed(5);
  const cT = useChromeT();

  // ── Primary query: loading / error gate the whole page ─────────────────────
  if (stateQ.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28 w-full rounded-xl" />)}
        </div>
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  if (stateQ.isError) {
    return (
      <Card className="border-danger-200/60">
        <CardContent className="flex flex-col items-start gap-3 py-8">
          <div className="flex items-center gap-2 text-danger-700">
            <ShieldAlert className="h-5 w-5" />
            <span className="font-semibold">{t('overviewPage.errLoadFailed')}</span>
          </div>
          <p className="text-sm text-ink-muted">
            {stateQ.error.message}
            {stateQ.error.trace_id ? (
              <span className="ml-1 opacity-60">
                {t('overviewPage.errTraceId', { traceId: stateQ.error.trace_id })}
              </span>
            ) : null}
          </p>
          <button
            onClick={() => stateQ.refetch()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-subtle px-3 py-1.5 text-sm font-medium hover:bg-canvas"
          >
            <RefreshCw className="h-4 w-4" /> {t('overviewPage.retry')}
          </button>
        </CardContent>
      </Card>
    );
  }

  const state = stateQ.data!;

  // ── Empty: no data uploaded yet ────────────────────────────────────────────
  if (state.state === 'no_data') {
    return (
      <EmptyState
        icon={UploadCloud}
        title={t('overviewPage.emptyTitle')}
        description={t('overviewPage.emptyDescription')}
        action={{ href: '/p2/pipelines/new/upload', label: t('overviewPage.emptyActionLabel') }}
      />
    );
  }

  const progress = state.state !== 'results_ready' ? PROGRESS_COPY[state.state] : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[#2E2A24]">{t('overviewPage.title')}</h1>
        {progress ? (
          <Badge tone={progress.tone}>{t(progress.label)}</Badge>
        ) : (
          <Badge tone="success">
            <CheckCircle2 className="mr-1 inline h-3.5 w-3.5" /> {t('overviewPage.resultsReady')}
          </Badge>
        )}
      </div>

      {/* In-progress banner with a continue CTA */}
      {progress ? (
        <Card className="border-brand-200/50 bg-brand-50/40">
          <CardContent className="flex items-center justify-between py-4">
            <div className="flex items-center gap-2 text-sm text-[#2E2A24]">
              <Activity className="h-4 w-4 text-brand-700" />
              {t('overviewPage.pipelineStepPrefix')} <strong>{state.pipeline_status ?? state.state}</strong>
            </div>
            <Link
              href={progress.cta.href}
              className="inline-flex items-center gap-1 rounded-lg bg-brand-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-800"
            >
              {t(progress.cta.label)} <ArrowRight className="h-4 w-4" />
            </Link>
          </CardContent>
        </Card>
      ) : null}

      {/* North Star ROI tile + headline KPIs */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiCard
          label={cT('Doanh thu đã cứu (North Star)')}
          value={northStarQ.isLoading ? '…' : fmtVNDShort(northStarQ.data?.resolved_vnd)}
          hint={northStarQ.data ? t('overviewPage.hintResolved', { pct: northStarQ.data.resolution_rate_pct }) : undefined}
          trendPct={northStarQ.data?.resolution_rate_pct}
          icon={<TrendingUp className="h-4 w-4" />}
        />
        <KpiCard
          label={cT('Doanh thu rủi ro')}
          value={northStarQ.isLoading ? '…' : fmtVNDShort(northStarQ.data?.total_at_risk_vnd)}
          hint={northStarQ.data ? t('overviewPage.hintAtRiskCount', { count: northStarQ.data.at_risk_count }) : undefined}
          icon={<AlertTriangle className="h-4 w-4" />}
        />
        <KpiCard
          label={cT('Khách đã xử lý')}
          value={northStarQ.isLoading ? '…' : (northStarQ.data?.actioned_count ?? 0)}
          icon={<CheckCircle2 className="h-4 w-4" />}
        />
        <KpiCard
          label={cT('Hạn mức khách / tháng (K-11)')}
          value={billingQ.isLoading ? '…' : `${billingQ.data?.unique_customers ?? 0}${billingQ.data?.monthly_quota ? ` / ${billingQ.data.monthly_quota}` : ''}`}
          hint={billingQ.data ? t('overviewPage.hintPlanUsage', { plan: billingQ.data.plan_code, pct: billingQ.data.usage_pct }) : undefined}
          trendPct={billingQ.data?.usage_pct}
        />
      </div>

      {/* Analysis-result KPI cards (state-machine: results_ready) */}
      {state.kpis && state.kpis.length > 0 ? (
        <Card>
          <CardHeader><CardTitle>{t('overviewPage.analysisKpisTitle')}</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {state.kpis.map((k, i) => (
                <div key={i} className="rounded-lg border border-subtle p-3">
                  <div className="text-xs text-ink-muted">{k.title || k.template}</div>
                  <div className="mt-1 text-sm font-medium text-[#2E2A24]">
                    {Object.entries(k.data).slice(0, 3).map(([key, val]) => (
                      <div key={key} className="flex justify-between gap-2">
                        <span className="text-ink-muted">{key}</span>
                        <span>{String(val)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* Insights feed (LLM — independent query, graceful empty/error) */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-brand-700" /> {t('overviewPage.insightsTitle')}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {insightsQ.isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-12 w-full" />
            </div>
          ) : insightsQ.isError ? (
            <p className="text-sm text-ink-muted">{t('overviewPage.insightsErrorPrefix')} {insightsQ.error.message}</p>
          ) : (insightsQ.data?.insights.length ?? 0) === 0 ? (
            <p className="text-sm text-ink-muted">{insightsQ.data?.note ?? t('overviewPage.insightsEmptyDefault')}</p>
          ) : (
            <ul className="space-y-3">
              {insightsQ.data!.insights.map((ins) => (
                <li key={ins.id} className="flex items-start gap-3 rounded-lg border border-subtle p-3">
                  <Badge tone={INSIGHT_TONE[ins.category] ?? 'neutral'}>{ins.category}</Badge>
                  <div>
                    <div className="text-sm font-medium text-[#2E2A24]">{ins.title}</div>
                    <div className="text-sm text-ink-muted">{ins.body}</div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
