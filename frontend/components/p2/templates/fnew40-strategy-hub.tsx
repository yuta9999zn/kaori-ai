'use client';

// ============================================================================
// /p2/strategy — Strategy Hub (F-040 BE PR #144)
// ----------------------------------------------------------------------------
// Wires the BE rollup endpoint:
//   GET /api/v1/enterprises/strategy/summary?quarter=
//
// Layout (per template 52):
//   - Quarter selector
//   - 4 KPI tiles (total OKR / on_track / at_risk / off_track) from rollup
//   - 3 module cards: OKR (linked), Timeline, Review Meetings
//     Timeline + Review = "Sắp ra mắt" — BE doesn't have those entities yet
//     (deferred Phase 2 v1, see PR #144 commit message)
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Target, GanttChartSquare, CalendarCheck, ArrowRight, RefreshCw,
  CheckCircle2, AlertTriangle, TrendingUp, Sparkles,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

type Status = 'on_track' | 'at_risk' | 'off_track';

interface SummaryResponse {
  data: {
    by_status: Record<Status, number>;
    total:     number;
    quarter:   string;
  };
}

const STATUS_META: Record<Status, { label: string; tone: string }> = {
  on_track:  { label: 'On-track',  tone: 'text-[var(--state-success)]' },
  at_risk:   { label: 'At-risk',   tone: 'text-[var(--state-warning)]' },
  off_track: { label: 'Off-track', tone: 'text-[var(--state-error)]'   },
};

// Quarter options — current quarter ± 4 (covers retrospective + next quarter
// planning). FE-side enum, BE accepts free-form Q[1-4] YYYY string.
function buildQuarterOptions(): string[] {
  const now    = new Date();
  const month  = now.getMonth();
  const year   = now.getFullYear();
  const curQ   = Math.floor(month / 3) + 1;

  const opts: string[] = [];
  for (let offset = -2; offset <= 2; offset++) {
    let q = curQ + offset;
    let y = year;
    while (q < 1) { q += 4; y -= 1; }
    while (q > 4) { q -= 4; y += 1; }
    opts.push(`Q${q} ${y}`);
  }
  return opts;
}

// ============================================================================
// Page
// ============================================================================

export default function StrategyHubPage() {
  const t = useT();
  const quarters = useMemo(buildQuarterOptions, []);
  const defaultQuarter = quarters[2];   // current quarter (middle of the 5)

  const [quarter, setQuarter] = useState(defaultQuarter);
  const [summary, setSummary] = useState<SummaryResponse['data'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const r = await api<SummaryResponse>(
        `/api/v1/enterprises/strategy/summary?quarter=${encodeURIComponent(quarter)}`);
      setSummary(r.data);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quarter]);

  return (
    <>
      <PageHeader
        title={t('templatesFnew40StrategyHub.title')}
        description={t('templatesFnew40StrategyHub.headerDesc')}
        actions={
          <>
            <Badge variant="info">F-040</Badge>
            <Button variant="secondary" size="md" onClick={load} disabled={loading}>
              <RefreshCw className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
              {t('templatesFnew40StrategyHub.refresh')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}

        {/* Quarter selector */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex items-center gap-3 shadow-soft-sm">
          <span className="text-xs text-[var(--text-secondary)] uppercase tracking-wider font-medium">
            {t('templatesFnew40StrategyHub.quarterLabel')}
          </span>
          {quarters.map((q) => (
            <button
              key={q}
              onClick={() => setQuarter(q)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-sm-custom border transition-colors',
                q === quarter
                  ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                  : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)]',
              )}
            >
              {q}
            </button>
          ))}
        </div>

        {/* KPI tiles */}
        {loading && !summary ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-28 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
            ))}
          </div>
        ) : summary ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <KpiTile
              label={t('templatesFnew40StrategyHub.totalOkr', { quarter })}
              value={summary.total}
              icon={Target}
              tone="text-[var(--text-primary)]"
            />
            <KpiTile
              label={t('templatesFnew40StrategyHub.onTrack')}
              value={summary.by_status.on_track}
              icon={CheckCircle2}
              tone="text-[var(--state-success)]"
            />
            <KpiTile
              label={t('templatesFnew40StrategyHub.atRisk')}
              value={summary.by_status.at_risk}
              icon={TrendingUp}
              tone="text-[var(--state-warning)]"
            />
            <KpiTile
              label={t('templatesFnew40StrategyHub.offTrack')}
              value={summary.by_status.off_track}
              icon={AlertTriangle}
              tone="text-[var(--state-error)]"
            />
          </div>
        ) : null}

        {/* Module cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <ModuleCard
            title={t('templatesFnew40StrategyHub.moduleOkrTitle')}
            description={t('templatesFnew40StrategyHub.moduleOkrDesc')}
            href="/p2/strategy/okr"
            icon={Target}
            metric={summary
              ? t('templatesFnew40StrategyHub.metricOkrRunning', { count: summary.total })
              : t('templatesFnew40StrategyHub.loadingEllipsis')}
            available
          />
          <ModuleCard
            title={t('templatesFnew40StrategyHub.timelineTitle')}
            description={t('templatesFnew40StrategyHub.timelineDesc')}
            href="/p2/strategy/timeline"
            icon={GanttChartSquare}
            metric={t('templatesFnew40StrategyHub.comingSoon')}
            available={false}
          />
          <ModuleCard
            title={t('templatesFnew40StrategyHub.reviewMeetingTitle')}
            description={t('templatesFnew40StrategyHub.reviewMeetingDesc')}
            href="/p2/strategy/review-meeting"
            icon={CalendarCheck}
            metric={t('templatesFnew40StrategyHub.comingSoon')}
            available={false}
          />
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templatesFnew40StrategyHub.statusAutoNote')}
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function KpiTile({
  label, value, icon: Icon, tone,
}: { label: string; value: number; icon: React.ComponentType<{ className?: string }>; tone: string }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">
          {label}
        </span>
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
      <p className="font-serif text-3xl text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

interface ModuleCardProps {
  title:       string;
  description: string;
  href:        string;
  icon:        React.ComponentType<{ className?: string }>;
  metric:      string;
  available:   boolean;
}

function ModuleCard({
  title, description, href, icon: Icon, metric, available,
}: ModuleCardProps) {
  const cls = cn(
    'block rounded-lg-custom border p-5 shadow-soft-sm transition-all',
    available
      ? 'bg-[var(--bg-card)] border-[var(--border-color)] hover:shadow-soft-md hover:-translate-y-0.5 hover:border-[var(--primary-gold)]/40'
      : 'bg-[var(--bg-app)]/40 border-[var(--border-color)] opacity-70',
  );
  const inner = (
    <>
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/12 flex items-center justify-center">
          <Icon className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        {available && <ArrowRight className="w-4 h-4 text-[var(--text-secondary)] mt-2" />}
      </div>
      <h3 className="font-serif text-lg text-[var(--text-primary)]">{title}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{description}</p>
      <p className={cn(
        'text-[11px] mt-3',
        available ? 'text-[var(--primary-gold-dark)]' : 'text-[var(--text-secondary)] italic',
      )}>
        {metric}
      </p>
    </>
  );
  return available
    ? <a href={href} className={cls}>{inner}</a>
    : <div className={cls}>{inner}</div>;
}
