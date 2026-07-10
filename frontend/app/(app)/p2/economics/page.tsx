'use client';

/**
 * P2 — Giá trị AI (NOV) & ROI  (S3 moat UI).
 *
 * Makes the "is the AI worth it?" story visible in manager language:
 *   NOV (Net Operating Value) = doanh thu AI tạo ra − chi phí vận hành AI.
 * Plus the ROI-Hybrid subscription state (ENT ROI eligibility).
 *
 * Wired to ai-orchestrator economics.py / roi_billing.py via the new
 * /api/v1/economics/** gateway route. Follows the /p2/dashboard/overview
 * reference pattern: per-domain hooks (lib/hooks), explicit types, every
 * query has loading / error / empty states, VND via fmtVNDShort (K-9),
 * Vietnamese business language (tenet 7).
 */
import {
  TrendingUp, TrendingDown, RefreshCw, ShieldAlert, BadgeCheck, Hourglass, Coins,
} from 'lucide-react';

import {
  useNovCurrent, useNovTrend, useRoiSubscription,
  type NovMonthEntry,
} from '@/lib/hooks';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { PageHeader } from '@/components/p2/shell';
import { fmtVNDShort } from '@/lib/format';
import { useT } from '@/lib/i18n/provider';

// VND fields arrive Decimal-as-str (precision-safe) — parse only for display.
const num = (s: string | null | undefined): number => {
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
};
// fmtVNDShort doesn't sign negatives; NOV can be negative (cost > revenue).
const fmtSignedVND = (n: number): string => (n < 0 ? `−${fmtVNDShort(-n)}` : fmtVNDShort(n));

const monthLabel = (iso: string): string => {
  // 'YYYY-MM-01' → 'MM/YYYY'
  const [y, m] = iso.split('-');
  return m && y ? `${m}/${y}` : iso;
};

const CONFIDENCE_KEYS: Record<string, string> = {
  high: 'economicsPage.confidenceHigh', medium: 'economicsPage.confidenceMedium', low: 'economicsPage.confidenceLow',
};
const METHOD_KEYS: Record<string, string> = {
  pre_post: 'economicsPage.methodPrePost', a_b: 'economicsPage.methodAb',
  industry_benchmark: 'economicsPage.methodBenchmark', variance: 'economicsPage.methodVariance',
};

export default function EconomicsPage() {
  const t = useT();
  const currentQ = useNovCurrent();
  const trendQ = useNovTrend(6);
  const roiQ = useRoiSubscription();

  return (
    <>
      <PageHeader
        title={t('economicsPage.title')}
        description={t('economicsPage.description')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        {/* ── NOV current ─────────────────────────────────────────────── */}
        {currentQ.isLoading ? (
          <Skeleton className="h-44 w-full rounded-xl" />
        ) : currentQ.isError ? (
          <ErrorCard message={currentQ.error.message} onRetry={() => currentQ.refetch()} />
        ) : currentQ.data?.classification === 'no_data' || !currentQ.data?.current ? (
          <EmptyState
            icon={Coins}
            title={t('economicsPage.emptyTitle')}
            description={t('economicsPage.emptyDescription')}
          />
        ) : (
          <NovCurrentCard entry={currentQ.data.current} />
        )}

        {/* ── NOV trend (6 tháng) ─────────────────────────────────────── */}
        <Card>
          <CardHeader><CardTitle>{t('economicsPage.trendTitle')}</CardTitle></CardHeader>
          <CardContent>
            {trendQ.isLoading ? (
              <div className="space-y-2">
                {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-7 w-full rounded" />)}
              </div>
            ) : trendQ.isError ? (
              <p className="text-sm text-ink-muted">{t('economicsPage.trendError', { message: trendQ.error.message })}</p>
            ) : !trendQ.data?.months.length ? (
              <p className="text-sm text-ink-muted">{t('economicsPage.trendNoHistory')}</p>
            ) : (
              <NovTrendBars months={trendQ.data.months} />
            )}
          </CardContent>
        </Card>

        {/* ── ROI subscription ────────────────────────────────────────── */}
        <Card>
          <CardHeader><CardTitle>{t('economicsPage.roiTitle')}</CardTitle></CardHeader>
          <CardContent>
            {roiQ.isLoading ? (
              <Skeleton className="h-20 w-full rounded" />
            ) : roiQ.isError ? (
              <p className="text-sm text-ink-muted">{t('economicsPage.roiError', { message: roiQ.error.message })}</p>
            ) : roiQ.data ? (
              <RoiSubscriptionView
                optedIn={roiQ.data.opted_in}
                months={roiQ.data.months_of_data}
                eligible={roiQ.data.eligibility_met}
                notes={roiQ.data.notes}
              />
            ) : null}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

// ── Subcomponents ──────────────────────────────────────────────────────

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  const t = useT();
  return (
    <Card className="border-danger-200/60">
      <CardContent className="flex flex-col items-start gap-3 py-8">
        <div className="flex items-center gap-2 text-danger-700">
          <ShieldAlert className="h-5 w-5" />
          <span className="font-semibold">{t('economicsPage.errNovLoad')}</span>
        </div>
        <p className="text-sm text-ink-muted">{message}</p>
        <button
          onClick={onRetry}
          className="inline-flex items-center gap-1.5 rounded-lg border border-subtle px-3 py-1.5 text-sm font-medium hover:bg-canvas"
        >
          <RefreshCw className="h-4 w-4" /> {t('economicsPage.retry')}
        </button>
      </CardContent>
    </Card>
  );
}

function NovCurrentCard({ entry }: { entry: NovMonthEntry }) {
  const t = useT();
  const nov = num(entry.nov_vnd);
  const revenue = num(entry.revenue_vnd);
  const cost = num(entry.cost_vnd);
  const positive = !entry.is_negative;
  const TrendIcon = positive ? TrendingUp : TrendingDown;
  const tone: BadgeTone = positive ? 'success' : 'danger';

  const methodKey = METHOD_KEYS[entry.revenue_method];
  const confidenceKey = CONFIDENCE_KEYS[entry.revenue_confidence];

  const costs: Array<[string, number]> = [
    [t('economicsPage.costPeople'), num(entry.people_cost_vnd)],
    [t('economicsPage.costAi'), num(entry.ai_cost_vnd)],
    [t('economicsPage.costInfra'), num(entry.infra_cost_vnd)],
    [t('economicsPage.costIntegration'), num(entry.integration_cost_vnd)],
  ];

  return (
    <Card className={positive ? 'border-emerald-200/60' : 'border-danger-200/60'}>
      <CardContent className="py-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <span>{t('economicsPage.novMonthLabel', { month: monthLabel(entry.month_start) })}</span>
              <Badge tone={tone}>{positive ? t('economicsPage.positiveLabel') : t('economicsPage.negativeLabel')}</Badge>
            </div>
            <div className={`mt-1 flex items-center gap-2 text-3xl font-semibold ${positive ? 'text-emerald-700' : 'text-danger-700'}`}>
              <TrendIcon className="h-7 w-7" />
              {fmtSignedVND(nov)}
            </div>
            <p className="mt-1 text-xs text-ink-muted">
              {t('economicsPage.estimatedByPrefix')} {methodKey ? t(methodKey) : entry.revenue_method}
              {' · '}{confidenceKey ? t(confidenceKey) : entry.revenue_confidence}
            </p>
          </div>

          <div className="flex gap-6 text-sm">
            <div>
              <div className="text-ink-muted">{t('economicsPage.revenueLabel')}</div>
              <div className="font-semibold text-emerald-700">{fmtVNDShort(revenue)}</div>
            </div>
            <div>
              <div className="text-ink-muted">{t('economicsPage.costLabel')}</div>
              <div className="font-semibold text-[#2E2A24]">−{fmtVNDShort(cost)}</div>
            </div>
          </div>
        </div>

        {/* Cost breakdown */}
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {costs.map(([label, val]) => (
            <div key={label} className="rounded-lg border border-subtle/60 px-3 py-2">
              <div className="text-xs text-ink-muted">{label}</div>
              <div className="text-sm font-medium text-[#2E2A24]">{fmtVNDShort(val)}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function NovTrendBars({ months }: { months: NovMonthEntry[] }) {
  const vals = months.map((m) => num(m.nov_vnd));
  const maxAbs = Math.max(1, ...vals.map((v) => Math.abs(v)));
  return (
    <div className="space-y-2">
      {months.map((m) => {
        const v = num(m.nov_vnd);
        const pct = Math.round((Math.abs(v) / maxAbs) * 100);
        const positive = !m.is_negative;
        return (
          <div key={m.month_start} className="flex items-center gap-3">
            <span className="w-16 shrink-0 text-xs text-ink-muted">{monthLabel(m.month_start)}</span>
            <div className="relative h-5 flex-1 rounded bg-canvas">
              <div
                className={`h-5 rounded ${positive ? 'bg-emerald-500/70' : 'bg-danger-500/70'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className={`w-28 shrink-0 text-right text-xs font-medium ${positive ? 'text-emerald-700' : 'text-danger-700'}`}>
              {fmtSignedVND(v)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

const ROI_MIN_MONTHS = 3; // ENT ROI eligibility (pricing — ≥3 months of data)

function RoiSubscriptionView({
  optedIn, months, eligible, notes,
}: { optedIn: boolean; months: number; eligible: boolean; notes: string | null }) {
  const t = useT();
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {optedIn ? (
          <><BadgeCheck className="h-5 w-5 text-emerald-700" /><span className="font-medium text-[#2E2A24]">{t('economicsPage.roiEnabledLabel')}</span></>
        ) : (
          <><Hourglass className="h-5 w-5 text-ink-muted" /><span className="font-medium text-[#2E2A24]">{t('economicsPage.roiDisabledLabel')}</span></>
        )}
      </div>
      <div className="flex flex-wrap gap-6 text-sm">
        <div>
          <div className="text-ink-muted">{t('economicsPage.roiDataAccumulated')}</div>
          <div className="font-medium text-[#2E2A24]">{t('economicsPage.monthsProgress', { months, min: ROI_MIN_MONTHS })}</div>
        </div>
        <div>
          <div className="text-ink-muted">{t('economicsPage.eligibleHeading')}</div>
          <div className="font-medium">
            <Badge tone={eligible ? 'success' : 'neutral'}>{eligible ? t('economicsPage.eligibleYes') : t('economicsPage.eligibleNo')}</Badge>
          </div>
        </div>
      </div>
      {!optedIn && eligible && (
        <p className="text-sm text-emerald-700">
          {t('economicsPage.roiEligibleHint')}
        </p>
      )}
      {notes ? <p className="text-xs text-ink-muted">{notes}</p> : null}
    </div>
  );
}
