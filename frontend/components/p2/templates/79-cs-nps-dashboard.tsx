// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// P2-35 — NPS Dashboard & Follow-up
// ----------------------------------------------------------------------------
// Phase 2.8 NEW. Maps to workflow D.3 NPS Follow-up.
//
// Route:        /p2/cs/nps
// Permission:   VIEWER+ xem; campaign config MANAGER+.
// URD US-ID:    US-CS-3
// BE routes:
//   GET  /api/v1/cs/nps/scorecard?from=&to=                 (aggregated)
//   GET  /api/v1/cs/nps/responses?segment=&score=           (paginated)
//   POST /api/v1/cs/nps/rules           body { trigger, action, condition }
//   POST /api/v1/cs/nps/campaigns       body { cohort_filter, survey_template, schedule }
//   GET  /api/v1/cs/nps/responses/{id}/sentiment            (re-classify on demand)
// ============================================================================

import React, { useState } from 'react';
import { TrendingUp, Smile, Meh, Frown, MessageSquare, AlertCircle } from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';

// ─── Types ───────────────────────────────────────────────────────────

interface NpsScorecard {
  overall_nps:        number;            // -100..100
  response_count:     number;
  promoter_count:     number;
  passive_count:      number;
  detractor_count:    number;
  trend_30d:          Array<{ date: string; nps: number }>;
  segments:           Array<{ segment_name: string; nps: number; n: number }>;
}

interface NpsResponse {
  response_id:    string;
  customer_name:  string;
  score:          number;                // 0..10
  comment:        string | null;
  sentiment:      'positive' | 'neutral' | 'negative' | null;
  segment_plan:   string;
  segment_dept:   string;
  followup_status: 'auto-replied' | 'awaiting' | 'done';
  created_at:     string;
}

interface FollowupRule {
  rule_id:    string;
  trigger:    'promoter' | 'passive' | 'detractor';
  action:     string;                     // 'create_ticket' | 'request_review' | ...
  condition:  string | null;
}

// ─── Page component ──────────────────────────────────────────────────

export default function NpsDashboardPage() {
  const t = useT();
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d'>('30d');
  // TODO P2-35-DATA: useQuery(['nps-scorecard', timeRange])
  const scorecard: NpsScorecard | null = null;
  const responses: NpsResponse[] = [];
  const rules: FollowupRule[] = [];
  const isLoading = false;
  const error: ProblemDetails | null = null;

  if (error) return <ErrorBanner message={error.detail ?? t('templates79CsNpsDashboard.errLoad')} />;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t('templates79CsNpsDashboard.title')}
        subtitle={t('templates79CsNpsDashboard.subtitle')}
      />

      {/* Time range filter */}
      <div className="flex gap-2">
        {(['7d', '30d', '90d'] as const).map(r => (
          <button
            key={r}
            onClick={() => setTimeRange(r)}
            className={cn(
              'rounded-full border px-3 py-1 text-sm',
              timeRange === r ? 'bg-primary-gold/10 border-primary-gold' : 'bg-white'
            )}
          >{r}</button>
        ))}
      </div>

      {/* Scorecard */}
      {isLoading ? (
        <div className="h-32 animate-pulse rounded bg-gray-100" />
      ) : !scorecard ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
          <MessageSquare className="mx-auto size-8" />
          <div className="mt-2">{t('templates79CsNpsDashboard.emptyScorecard')}</div>
          <Button className="mt-3">{t('templates79CsNpsDashboard.addTriggerBtn')}</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          <ScorecardTile label={t('templates79CsNpsDashboard.tileNpsTotal')} value={scorecard.overall_nps.toFixed(1)} accent />
          <ScorecardTile label={t('templates79CsNpsDashboard.tilePromoters')} value={scorecard.promoter_count.toString()} icon={<Smile className="size-4" />} />
          <ScorecardTile label={t('templates79CsNpsDashboard.tilePassives')} value={scorecard.passive_count.toString()} icon={<Meh className="size-4" />} />
          <ScorecardTile label={t('templates79CsNpsDashboard.tileDetractors')} value={scorecard.detractor_count.toString()} icon={<Frown className="size-4" />} />
        </div>
      )}

      {/* Low volume warning */}
      {scorecard && scorecard.response_count < 30 && (
        <div className="flex items-center gap-3 rounded-lg border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800">
          <AlertCircle className="size-4" />
          {t('templates79CsNpsDashboard.lowVolumeWarning', { count: scorecard.response_count })}
        </div>
      )}

      {/* Trend chart placeholder */}
      <div className="rounded-lg border bg-white p-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <TrendingUp className="size-4" /> {t('templates79CsNpsDashboard.trendHeading')}
        </div>
        <div className="mt-4 h-40 rounded bg-gray-50 p-4 text-sm text-muted-foreground">
          {t('templates79CsNpsDashboard.featureWip')}
        </div>
      </div>

      {/* Response table */}
      <div className="rounded-lg border bg-white">
        <div className="border-b px-4 py-3 font-medium">{t('templates79CsNpsDashboard.responsesHeading')}</div>
        {responses.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">{t('templates79CsNpsDashboard.emptyResponses')}</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2">{t('templates79CsNpsDashboard.colCustomer')}</th>
                <th className="px-4 py-2">{t('templates79CsNpsDashboard.colScore')}</th>
                <th className="px-4 py-2">{t('templates79CsNpsDashboard.colSentiment')}</th>
                <th className="px-4 py-2">{t('templates79CsNpsDashboard.colComment')}</th>
                <th className="px-4 py-2">{t('templates79CsNpsDashboard.colSegment')}</th>
                <th className="px-4 py-2">{t('templates79CsNpsDashboard.colFollowup')}</th>
              </tr>
            </thead>
            <tbody>
              {responses.map(r => <NpsResponseRow key={r.response_id} response={r} />)}
            </tbody>
          </table>
        )}
      </div>

      {/* Followup rules editor */}
      <div className="rounded-lg border bg-white">
        <div className="border-b px-4 py-3 flex items-center justify-between">
          <span className="font-medium">{t('templates79CsNpsDashboard.rulesHeading')}</span>
          {/* TODO P2-35-PERM: gate edit on MANAGER+ */}
          <Button size="sm">{t('templates79CsNpsDashboard.addRuleBtn')}</Button>
        </div>
        <div className="space-y-2 p-4">
          {rules.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t('templates79CsNpsDashboard.emptyRules', { btn: t('templates79CsNpsDashboard.addRuleBtn') })}</div>
          ) : (
            rules.map(r => (
              <div key={r.rule_id} className="rounded border bg-gray-50 p-3 text-sm">
                <strong>{r.trigger}</strong> → {r.action}
                {r.condition && <span className="ml-2 text-muted-foreground">{t('templates79CsNpsDashboard.ifLabel')} {r.condition}</span>}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Campaign manager placeholder */}
      <div className="rounded-lg border bg-white p-4">
        <div className="font-medium">{t('templates79CsNpsDashboard.campaignsHeading')}</div>
        <div className="mt-2 text-sm text-muted-foreground">{t('templates79CsNpsDashboard.featureWip')}</div>
      </div>
    </div>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function ScorecardTile({ label, value, icon, accent = false }: { label: string; value: string; icon?: React.ReactNode; accent?: boolean }) {
  return (
    <div className={cn('rounded-lg border p-4', accent ? 'bg-primary-gold/5 border-primary-gold' : 'bg-white')}>
      <div className="flex items-center gap-2 text-xs uppercase text-muted-foreground">{icon}{label}</div>
      <div className="mt-2 text-2xl font-medium">{value}</div>
    </div>
  );
}

function NpsResponseRow({ response }: { response: NpsResponse }) {
  const scoreColor = response.score >= 9 ? 'text-green-600' : response.score >= 7 ? 'text-yellow-600' : 'text-red-600';
  const sentimentIcon = response.sentiment === 'positive' ? <Smile className="size-4 text-green-600" />
    : response.sentiment === 'negative' ? <Frown className="size-4 text-red-600" />
    : <Meh className="size-4 text-gray-500" />;
  return (
    <tr className="border-b">
      <td className="px-4 py-2">{response.customer_name}</td>
      <td className={cn('px-4 py-2 font-medium', scoreColor)}>{response.score}/10</td>
      <td className="px-4 py-2">{sentimentIcon}</td>
      <td className="px-4 py-2 max-w-md truncate text-muted-foreground">{response.comment ?? '—'}</td>
      <td className="px-4 py-2 text-xs">{response.segment_plan} · {response.segment_dept}</td>
      <td className="px-4 py-2"><Badge variant="outline">{response.followup_status}</Badge></td>
    </tr>
  );
}
