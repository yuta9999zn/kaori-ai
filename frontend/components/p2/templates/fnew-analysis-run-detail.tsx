// @ts-nocheck — template; tighten when wiring real chart-registry blocks.
'use client';

// ============================================================================
// /p2/analysis/runs/[id] — Multi-tier Analysis Run Detail (F-033 PR A wired)
// ----------------------------------------------------------------------------
// Polls GET /api/v1/analysis/runs/{id} until status is terminal (done /
// error). Renders:
//   * Header: tier badge + framework badge + question + status pill
//   * Narrative card
//   * Overview card — for SWOT/6W/2H/Fishbone we render the framework-
//     shaped JSON; for basic tier we just render the cross-template
//     narrative under "Tổng kết".
//   * Audit footer — created_at, completed_at, consent_external, schema
//     repair flag (Issue #3 audit channel).
//
// No chart-registry hookup yet — basic tier overview shape isn't pinned.
// PR C just renders the JSON as a structured tree so users see *something*;
// proper ChartBlock[] rendering ships when the engine output schema is
// formalised (likely with F-035 cohort retention which will pin it).
// ============================================================================

import React, { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import {
  ChevronLeft, FlaskConical, Lock, Globe, CheckCircle2, AlertCircle,
  Activity, Clock, RefreshCw, Lightbulb, ShieldCheck,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import FlexibleChart from '@/components/charts/FlexibleChart';
import { useT } from '@/lib/i18n/provider';

type Tier   = 'basic' | 'intermediate' | 'advanced';
type Status = 'queued' | 'running' | 'done' | 'error';

interface RunDetail {
  id:               string;
  pipeline_run_id:  string | null;
  tier:             Tier;
  scope:            string;
  framework:        string | null;
  question:         string | null;
  source_ids:       Array<{ layer: string; id: string; label?: string | null }> | null;
  consent_external: boolean;
  status:           Status;
  narrative:        string | null;
  templates:        string[];
  config:           Record<string, unknown>;
  workspace_ids:    string[];
  requires_approval: boolean;
  approved_by:      string | null;
  approved_at:      string | null;
  overview:         any;
  output_schema_repaired: boolean | null;
  started_at:       string | null;
  completed_at:     string | null;
  created_at:       string;
}

export default function AnalysisRunDetailPage() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const runId = params?.id ?? '';

  const TIER_LABEL: Record<Tier, string> = {
    basic:        t('templatesFnewAnalysisRunDetail.tierBasic'),
    intermediate: t('templatesFnewAnalysisRunDetail.tierIntermediate'),
    advanced:     t('templatesFnewAnalysisRunDetail.tierAdvanced'),
  };

  const STATUS_META: Record<Status, { variant: any; label: string }> = {
    queued:  { variant: 'default', label: t('templatesFnewAnalysisRunDetail.statusQueued') },
    running: { variant: 'warning', label: t('templatesFnewAnalysisRunDetail.statusRunning') },
    done:    { variant: 'success', label: t('templatesFnewAnalysisRunDetail.statusDone') },
    error:   { variant: 'error',   label: t('templatesFnewAnalysisRunDetail.statusError') },
  };
  const [run, setRun]         = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [approving, setApproving] = useState(false);
  const pollRef = useRef<number | null>(null);

  // Pending approval = advanced row that requires approval and hasn't
  // been approved yet. We hold polling in this state because the BE
  // dispatcher won't progress without /approve being hit.
  const isPendingApproval = !!run
    && run.tier === 'advanced'
    && run.requires_approval
    && run.approved_at === null
    && run.status === 'queued';

  async function load() {
    if (!runId) return;
    try {
      const r = await api<RunDetail>(`/api/v1/analysis/runs/${runId}`);
      setRun(r);
      setLoading(false);
    } catch (err: any) {
      setProblem(err);
      setLoading(false);
    }
  }

  async function handleApprove() {
    setProblem(null);
    setApproving(true);
    try {
      const r = await api<RunDetail>(`/api/v1/analysis/runs/${runId}/approve`, {
        method: 'POST',
      });
      setRun(r);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setApproving(false);
    }
  }

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  // Poll while non-terminal AND not waiting for human approval. Stop
  // once status is done|error or the approval gate is up.
  useEffect(() => {
    if (!run) return;
    const stop = run.status === 'done' || run.status === 'error' || isPendingApproval;
    if (stop) {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
    if (pollRef.current) return;
    pollRef.current = window.setInterval(() => { load(); }, 2000);
    return () => { if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null; } };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run?.status, isPendingApproval]);

  return (
    <>
      <PageHeader
        title={t('templatesFnewAnalysisRunDetail.title')}
        description={run ? `${TIER_LABEL[run.tier]} · ${run.scope}${run.framework ? ` · ${run.framework.toUpperCase()}` : ''}` : '—'}
        actions={
          <>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/analysis')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              {t('templatesFnewAnalysisRunDetail.hubButton')}
            </Button>
            <Button variant="secondary" onClick={load} disabled={loading}>
              <RefreshCw className={cn('w-4 h-4 mr-1', loading && 'animate-spin')} />
              {t('templatesFnewAnalysisRunDetail.refreshButton')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {loading && !run && (
          <div className="h-32 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
        )}

        {run && (
          <>
            {/* Header card */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                <Badge variant={run.tier === 'advanced' ? 'warning' : run.tier === 'intermediate' ? 'info' : 'default'}>
                  {TIER_LABEL[run.tier]}
                </Badge>
                {run.framework && <Badge variant="current">{run.framework.toUpperCase()}</Badge>}
                <Badge variant={STATUS_META[run.status].variant}>
                  {run.status === 'running' && <Activity className="w-3 h-3 mr-1 inline animate-pulse" />}
                  {run.status === 'done' && <CheckCircle2 className="w-3 h-3 mr-1 inline" />}
                  {run.status === 'error' && <AlertCircle className="w-3 h-3 mr-1 inline" />}
                  {STATUS_META[run.status].label}
                </Badge>
                <Badge variant={run.consent_external ? 'warning' : 'success'}>
                  {run.consent_external
                    ? <><Globe className="w-3 h-3 mr-1 inline" />{t('templatesFnewAnalysisRunDetail.externalAiBadge')}</>
                    : <><Lock className="w-3 h-3 mr-1 inline" />{t('templatesFnewAnalysisRunDetail.qwenInternalBadge')}</>}
                </Badge>
                {run.output_schema_repaired === true && (
                  <Badge variant="info" title={t('templatesFnewAnalysisRunDetail.schemaRepairedTooltip')}>{t('templatesFnewAnalysisRunDetail.schemaRepairedBadge')}</Badge>
                )}
              </div>
              {run.question && (
                <p className="text-sm text-[var(--text-primary)] leading-relaxed">
                  <span className="font-medium">{t('templatesFnewAnalysisRunDetail.questionLabel')}</span> {run.question}
                </p>
              )}
              {run.tier === 'basic' && run.pipeline_run_id && (
                <p className="text-xs text-[var(--text-secondary)]">
                  {t('templatesFnewAnalysisRunDetail.pipelineLabel')} <a href={`/p2/pipelines/${run.pipeline_run_id}`} className="text-[var(--primary-gold-dark)] underline">{run.pipeline_run_id}</a>
                </p>
              )}
              {run.source_ids && run.source_ids.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs text-[var(--text-secondary)]">{t('templatesFnewAnalysisRunDetail.sourceLabel')}</span>
                  {run.source_ids.map((s) => (
                    <Badge key={`${s.layer}-${s.id}`} variant={s.layer === 'gold' ? 'current' : 'default'}>
                      {(s.label || s.id) as string} · {s.layer.toUpperCase()}
                    </Badge>
                  ))}
                </div>
              )}
              {run.tier === 'basic' && run.templates.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs text-[var(--text-secondary)]">{t('templatesFnewAnalysisRunDetail.templateLabel')}</span>
                  {run.templates.map((tpl) => <Badge key={tpl} variant="default">{tpl}</Badge>)}
                </div>
              )}
            </div>

            {/* Approval gate */}
            {isPendingApproval && (
              <div className="bg-[var(--state-warning)]/10 rounded-lg-custom border border-[var(--state-warning)]/30 p-5 shadow-soft-sm">
                <p className="font-serif text-sm text-[var(--text-primary)] mb-2">
                  {t('templatesFnewAnalysisRunDetail.pendingApprovalTitle')}
                </p>
                <p className="text-xs text-[#9E814D] mb-3 leading-relaxed">
                  {t('templatesFnewAnalysisRunDetail.pendingApprovalDescPre')} <span className="font-mono">consent_external_ai</span> {t('templatesFnewAnalysisRunDetail.pendingApprovalDescPost')}
                </p>
                <Button onClick={handleApprove} disabled={approving} isLoading={approving} variant="primary">
                  <CheckCircle2 className="w-4 h-4 mr-2" />
                  {t('templatesFnewAnalysisRunDetail.approveDispatchButton')}
                </Button>
                <p className="text-[11px] text-[var(--text-secondary)] mt-2">
                  {t('templatesFnewAnalysisRunDetail.approveHintBe403')}
                </p>
              </div>
            )}
            {run.tier === 'advanced' && run.approved_at && (
              <div className="text-xs text-[var(--text-secondary)] flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-[var(--state-success)]" />
                {t('templatesFnewAnalysisRunDetail.approvedAtLabel')} <span className="font-mono">{formatTime(run.approved_at)}</span>
                {run.approved_by && <> · {t('templatesFnewAnalysisRunDetail.approvedByLabel')} <span className="font-mono">{run.approved_by.slice(0, 8)}…</span></>}
              </div>
            )}

            {/* Narrative */}
            {run.narrative && (
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
                <div className="flex items-start gap-3">
                  <Lightbulb className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                  <div>
                    <p className="font-serif text-sm text-[var(--text-primary)] mb-1">{t('templatesFnewAnalysisRunDetail.narrativeTitle')}</p>
                    <p className="text-sm text-[var(--text-primary)] leading-relaxed">{run.narrative}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Overview */}
            {run.status === 'done' && run.overview && (
              <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
                <h3 className="font-serif text-base text-[var(--text-primary)] mb-3">
                  {run.framework ? t('templatesFnewAnalysisRunDetail.overviewFrameworkResult', { framework: run.framework.toUpperCase() }) : t('templatesFnewAnalysisRunDetail.overviewDefaultTitle')}
                </h3>
                {run.framework === 'swot' ? <SwotView c={run.overview} />
                  : run.framework === '6w' ? <ListView c={run.overview} keys={['who','what','when','where','why','how','summary']} />
                  : run.framework === '2h' ? <TwoHView c={run.overview} />
                  : run.framework === 'fishbone' ? <FishboneView c={run.overview} />
                  : Array.isArray(run.overview?.blocks) ? <BlocksView blocks={run.overview.blocks} summary={run.overview?.summary} />
                  : <pre className="text-xs bg-[var(--bg-app)]/40 p-3 rounded-md-custom overflow-auto">{JSON.stringify(run.overview, null, 2)}</pre>}
              </div>
            )}

            {run.status === 'error' && (
              <div className="bg-[var(--state-error)]/10 rounded-lg-custom border border-[var(--state-error)]/30 p-5 text-sm text-[#9B5050]">
                <p className="font-medium mb-1">{t('templatesFnewAnalysisRunDetail.analysisFailedTitle')}</p>
                {typeof run.overview?.error === 'string' ? (
                  <p className="text-xs leading-relaxed">{run.overview.error}</p>
                ) : (
                  <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(run.overview, null, 2)}</pre>
                )}
              </div>
            )}

            {/* Audit footer */}
            <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
              <p>
                {t('templatesFnewAnalysisRunDetail.createdAtLabel')} <span className="font-mono">{formatTime(run.created_at)}</span>
                {run.completed_at && (
                  <> · {t('templatesFnewAnalysisRunDetail.completedAtLabel')} <span className="font-mono">{formatTime(run.completed_at)}</span></>
                )}
                {' · '}
                {t('templatesFnewAnalysisRunDetail.auditLlmPre')} <span className="font-mono">llm_router</span> {t('templatesFnewAnalysisRunDetail.auditLlmMid')} <span className="font-mono">decision_audit_log</span> {t('templatesFnewAnalysisRunDetail.auditLlmPost')}
              </p>
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ─── Framework-shaped views ──────────────────────────────────────

function SwotView({ c }: { c: any }) {
  const t = useT();
  if (!c?.strengths || !c?.weaknesses || !c?.opportunities || !c?.threats) {
    return <pre className="text-xs">{JSON.stringify(c, null, 2)}</pre>;
  }
  const Q = ({ title, items, tone }: { title: string; items: any[]; tone: 'good' | 'bad' | 'neutral' }) => (
    <div className={cn('p-3 rounded-md-custom border',
      tone === 'good' ? 'border-[var(--state-success)]/40 bg-[var(--state-success)]/5'
      : tone === 'bad' ? 'border-[var(--state-error)]/40 bg-[var(--state-error)]/5'
      : 'border-[var(--border-color)]/60 bg-[var(--bg-app)]/30',
    )}>
      <p className="font-medium text-sm text-[var(--text-primary)] mb-1.5">{title}</p>
      <ul className="space-y-1 text-sm">
        {items.map((it: any, i: number) => (
          <li key={i} className="flex items-baseline gap-2">
            <span className="text-[var(--text-primary)]">{it.text}</span>
            {typeof it.confidence === 'number' && (
              <span className="text-[10px] text-[var(--text-secondary)] font-mono">{Math.round(it.confidence * 100)}%</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Q title={t('templatesFnewAnalysisRunDetail.swotStrengths')}   items={c.strengths.items   ?? []} tone="good" />
        <Q title={t('templatesFnewAnalysisRunDetail.swotWeaknesses')}  items={c.weaknesses.items  ?? []} tone="bad" />
        <Q title={t('templatesFnewAnalysisRunDetail.swotOpportunities')} items={c.opportunities.items ?? []} tone="good" />
        <Q title={t('templatesFnewAnalysisRunDetail.swotThreats')}     items={c.threats.items     ?? []} tone="bad" />
      </div>
      {c.summary && (
        <div className="p-3 rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 text-sm text-[var(--text-primary)]">
          <span className="font-medium">{t('templatesFnewAnalysisRunDetail.summaryLabel')}</span>{c.summary}
        </div>
      )}
    </div>
  );
}

function ListView({ c, keys }: { c: any; keys: string[] }) {
  return (
    <dl className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
      {keys.map((k) => c?.[k] && (
        <div key={k} className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60">
          <dt className="text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wider">{k}</dt>
          <dd className="text-[var(--text-primary)] mt-1 leading-relaxed">{String(c[k])}</dd>
        </div>
      ))}
    </dl>
  );
}

function TwoHView({ c }: { c: any }) {
  const t = useT();
  return (
    <div className="space-y-3 text-sm">
      {c?.how && (
        <div className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60">
          <p className="font-medium text-[var(--text-primary)] mb-1">{t('templatesFnewAnalysisRunDetail.twoHHowLabel')} — {c.how.approach}</p>
          <ol className="list-decimal pl-5 space-y-1 text-[var(--text-primary)]">
            {(c.how.steps ?? []).map((s: string, i: number) => <li key={i}>{s}</li>)}
          </ol>
        </div>
      )}
      {c?.how_much && (
        <div className="p-3 rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30">
          <p className="font-medium text-[var(--text-primary)] mb-1">
            {t('templatesFnewAnalysisRunDetail.twoHHowMuchLabel')}: {c.how_much.estimate} {c.how_much.unit}
            {typeof c.how_much.confidence === 'number' && (
              <span className="ml-2 text-[10px] text-[var(--text-secondary)] font-mono">
                {t('templatesFnewAnalysisRunDetail.confidenceLabel')} {Math.round(c.how_much.confidence * 100)}%
              </span>
            )}
          </p>
          {Array.isArray(c.how_much.assumptions) && c.how_much.assumptions.length > 0 && (
            <ul className="mt-1.5 list-disc pl-5 text-xs text-[var(--text-secondary)]">
              {c.how_much.assumptions.map((a: string, i: number) => <li key={i}>{a}</li>)}
            </ul>
          )}
        </div>
      )}
      {c?.summary && <p className="text-sm text-[var(--text-primary)]"><span className="font-medium">{t('templatesFnewAnalysisRunDetail.summaryLabel')}</span>{c.summary}</p>}
    </div>
  );
}

function FishboneView({ c }: { c: any }) {
  const t = useT();
  return (
    <div className="space-y-3 text-sm">
      {c?.problem && (
        <p className="p-3 rounded-md-custom bg-[var(--state-error)]/10 border border-[var(--state-error)]/30">
          <span className="font-medium">{t('templatesFnewAnalysisRunDetail.problemLabel')}</span>{c.problem}
        </p>
      )}
      {Array.isArray(c?.categories) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {c.categories.map((cat: any, i: number) => (
            <div key={i} className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60">
              <p className="font-medium text-[var(--text-primary)] mb-1.5">{cat.name}</p>
              <ul className="space-y-1">
                {(cat.causes ?? []).map((cs: any, j: number) => (
                  <li key={j} className="flex items-baseline gap-2">
                    <span className="text-[10px] font-mono text-[var(--text-secondary)] shrink-0">L{cs.depth}</span>
                    <span className="text-[var(--text-primary)]">{cs.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      {c?.root_cause_hypothesis && (
        <p className="p-3 rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30">
          <span className="font-medium">{t('templatesFnewAnalysisRunDetail.rootCauseLabel')}</span>{c.root_cause_hypothesis}
        </p>
      )}
    </div>
  );
}

// ─── Block list view (basic tier — multi-template ChartBlock[]) ──

function BlocksView({ blocks, summary }: { blocks: any[]; summary?: string }) {
  return (
    <div className="space-y-4">
      {summary && (
        <p className="text-sm text-[var(--text-primary)] leading-relaxed">{summary}</p>
      )}
      {blocks.map((b, i) => (
        <div key={b.id ?? i} className="space-y-2">
          {b.title && <p className="font-serif text-sm text-[var(--text-primary)]">{b.title}</p>}
          {b.type === 'chart' && b.data_shape ? (
            <FlexibleChart block={b} />
          ) : b.type === 'stats_card' ? (
            <StatsCard data={b.data ?? {}} />
          ) : (
            <pre className="text-xs bg-[var(--bg-app)]/40 p-3 rounded-md-custom overflow-auto">{JSON.stringify(b, null, 2)}</pre>
          )}
        </div>
      ))}
    </div>
  );
}

function StatsCard({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;
  return (
    <dl className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {entries.map(([k, v]) => (
        <div key={k} className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/60">
          <dt className="text-[10px] font-medium text-[var(--text-secondary)] uppercase tracking-wider">{k.replace(/_/g, ' ')}</dt>
          <dd className="font-serif text-base text-[var(--text-primary)] mt-0.5">{v == null ? '—' : String(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

// ─── Helpers ─────────────────────────────────────────────────────

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('vi-VN');
  } catch {
    return iso;
  }
}
