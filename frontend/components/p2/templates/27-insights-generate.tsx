// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 27. /p2/insights/generate — Insight Generator wizard (F-025 + K-3 + K-4)
// ----------------------------------------------------------------------------
// 4-step wizard:
//   1. Source     — pick a Gold feature OR a recent pipeline run
//   2. Question   — pick framework (1=1 per K-10) + free-text question
//   3. Privacy    — choose Qwen internal (default) vs External AI (consent)
//   4. Review     — confirm + dispatch POST /api/v1/insights/generate
//
// K-rules in play:
//   K-3  — every LLM call routed via llm_router.py (no direct SDK)
//   K-4  — external AI requires consent_external=true (default OFF)
//   K-5  — PII redacted before any external call
//   K-10 — 1 question = 1 framework (radio, never multi-select)
//
// Returns { insight_id }; redirects to /p2/insights/:id on success.
// ============================================================================

import React, { useState } from 'react';
import {
  Sparkles, Database, Layers, ShieldCheck, Lock, Globe, AlertTriangle,
  ChevronLeft, ChevronRight, Check, Lightbulb, Loader2, Eye,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, cn,
  api,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type SourceKind = 'gold_feature' | 'pipeline_run';
type Framework  = 'NONE' | 'SWOT' | '6W' | '2H' | 'Fishbone' | 'MoM' | 'YoY';

interface GoldFeature  { id: string; name: string; description: string; last_aggregated_at: string; is_stale: boolean; }
interface PipelineRun  { id: string; title: string; finished_at: string; row_count: number; }

interface SourceSelection {
  kind:        SourceKind;
  source_id:   string;
  source_label: string;
}

function getFrameworkOptions(
  t: (key: string, params?: Record<string, string | number>) => string,
): Array<{ value: Framework; title: string; description: string }> {
  return [
    { value: 'NONE',     title: t('templates27InsightsGenerate.frameworkFreeTitle'), description: t('templates27InsightsGenerate.frameworkFreeDesc') },
    { value: 'SWOT',     title: 'SWOT',      description: 'Strengths · Weaknesses · Opportunities · Threats' },
    { value: '6W',       title: '6W',        description: 'Who · What · When · Where · Why · How' },
    { value: '2H',       title: '2H',        description: t('templates27InsightsGenerate.framework2hDesc') },
    { value: 'Fishbone', title: 'Fishbone',  description: t('templates27InsightsGenerate.frameworkFishboneDesc') },
    { value: 'MoM',      title: 'MoM',       description: t('templates27InsightsGenerate.frameworkMomDesc') },
    { value: 'YoY',      title: 'YoY',       description: t('templates27InsightsGenerate.frameworkYoyDesc') },
  ];
}

export default function InsightGeneratePage() {
  const t = useT();
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);

  const [source,    setSource]    = useState<SourceSelection | null>(null);
  const [question,  setQuestion]  = useState('');
  const [framework, setFramework] = useState<Framework>('NONE');
  const [consentExternal, setConsentExternal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [problem,    setProblem]    = useState<ProblemDetails | null>(null);

  function next() { setStep((s) => Math.min(4, s + 1) as any); }
  function prev() { setStep((s) => Math.max(1, s - 1) as any); }

  async function submit() {
    if (!source || !question.trim()) return;
    setSubmitting(true);
    setProblem(null);
    try {
      const res = await api<{ insight_id: string }>('/api/v1/insights/generate', {
        method: 'POST',
        body: JSON.stringify({
          source_kind:       source.kind,
          source_id:         source.source_id,
          question:          question.trim(),
          framework:         framework === 'NONE' ? null : framework,
          consent_external:  consentExternal,
        }),
      });
      window.location.href = `/p2/insights/${res.insight_id}`;
    } catch (err: any) {
      setProblem(err);
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates27InsightsGenerate.title')}
        description={t('templates27InsightsGenerate.pageDescription')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />

        <Stepper current={step} />

        {step === 1 && (
          <StepSource
            value={source}
            onChange={(s) => { setSource(s); next(); }}
          />
        )}
        {step === 2 && (
          <StepQuestion
            question={question}
            framework={framework}
            onQuestionChange={setQuestion}
            onFrameworkChange={setFramework}
          />
        )}
        {step === 3 && (
          <StepPrivacy
            consentExternal={consentExternal}
            onChange={setConsentExternal}
          />
        )}
        {step === 4 && source && (
          <StepReview
            source={source}
            question={question}
            framework={framework}
            consentExternal={consentExternal}
          />
        )}

        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            onClick={prev}
            disabled={step === 1 || submitting}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            {t('templates27InsightsGenerate.btnBack')}
          </Button>
          {step < 4 ? (
            <Button
              onClick={next}
              disabled={
                (step === 1 && !source) ||
                (step === 2 && !question.trim())
              }
            >
              {t('templates27InsightsGenerate.btnNext')}
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          ) : (
            <Button onClick={submit} isLoading={submitting}>
              <Sparkles className="w-4 h-4 mr-2" />
              {t('templates27InsightsGenerate.btnSubmit')}
            </Button>
          )}
        </div>
      </div>
    </>
  );
}

// ----------------------------------------------------------------------------
// Stepper
// ----------------------------------------------------------------------------

function Stepper({ current }: { current: 1 | 2 | 3 | 4 }) {
  const t = useT();
  const STEPS = [
    { n: 1, title: t('templates27InsightsGenerate.stepSourceLabel') },
    { n: 2, title: t('templates27InsightsGenerate.stepQuestionLabel') },
    { n: 3, title: t('templates27InsightsGenerate.stepPrivacyLabel') },
    { n: 4, title: t('templates27InsightsGenerate.stepReviewLabel') },
  ];
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
      <div className="flex items-center justify-between gap-2">
        {STEPS.map((s, idx) => {
          const done = current > s.n;
          const cur  = current === s.n;
          return (
            <React.Fragment key={s.n}>
              <div className="flex items-center gap-2 shrink-0">
                <div className={cn(
                  'w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium border',
                  done ? 'bg-[var(--state-success)] text-white border-[var(--state-success)]'
                       : cur  ? 'bg-[var(--primary-gold)] text-[var(--text-primary)] border-[var(--primary-gold)]'
                              : 'bg-[var(--bg-app)] text-[var(--text-secondary)] border-[var(--border-color)]',
                )}>
                  {done ? <Check className="w-4 h-4" /> : s.n}
                </div>
                <span className={cn(
                  'text-sm font-medium hidden sm:block',
                  done || cur ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]',
                )}>
                  {s.title}
                </span>
              </div>
              {idx < STEPS.length - 1 && (
                <div className={cn('flex-1 h-px', done ? 'bg-[var(--state-success)]' : 'bg-[var(--border-color)]')} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Step 1 — Source picker
// ----------------------------------------------------------------------------

function StepSource({
  value, onChange,
}: {
  value: SourceSelection | null;
  onChange: (s: SourceSelection) => void;
}) {
  const t = useT();
  const [tab,      setTab]      = useState<SourceKind>('gold_feature');
  const [features, setFeatures] = useState<GoldFeature[]>([]);
  const [runs,     setRuns]     = useState<PipelineRun[]>([]);
  const [loading,  setLoading]  = useState(false);

  React.useEffect(() => {
    setLoading(true);
    if (tab === 'gold_feature') {
      api<{ items: GoldFeature[] }>('/api/v1/data/gold/features?limit=20')
        .then((r) => setFeatures(r.items))
        .catch(() => setFeatures([]))
        .finally(() => setLoading(false));
    } else {
      api<{ items: PipelineRun[] }>('/api/v1/pipelines?status=analysis_complete&limit=20')
        .then((r) => setRuns(r.items))
        .catch(() => setRuns([]))
        .finally(() => setLoading(false));
    }
  }, [tab]);

  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
        <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates27InsightsGenerate.step1Title')}</h3>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          {t('templates27InsightsGenerate.step1Desc')}
        </p>
      </div>

      <div className="px-5 py-3 border-b border-[var(--border-color)]/60 flex gap-1">
        <TabButton active={tab === 'gold_feature'} onClick={() => setTab('gold_feature')}>
          <Layers className="w-4 h-4 mr-2" />
          {t('templates27InsightsGenerate.tabGoldFeature')}
        </TabButton>
        <TabButton active={tab === 'pipeline_run'} onClick={() => setTab('pipeline_run')}>
          <Database className="w-4 h-4 mr-2" />
          {t('templates27InsightsGenerate.tabPipelineRun')}
        </TabButton>
      </div>

      <div className="p-5 space-y-2 max-h-[420px] overflow-y-auto">
        {loading ? (
          <div className="space-y-2">
            {[1,2,3].map((i) => <div key={i} className="h-16 rounded-md-custom bg-[var(--bg-app)] animate-pulse" />)}
          </div>
        ) : tab === 'gold_feature' ? (
          features.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)] text-center py-8">
              {t('templates27InsightsGenerate.emptyGoldFeatures')}
            </p>
          ) : features.map((f) => (
            <button
              key={f.id}
              type="button"
              onClick={() => onChange({ kind: 'gold_feature', source_id: f.id, source_label: f.name })}
              className={cn(
                'w-full text-left p-3 rounded-md-custom border transition-all',
                value?.source_id === f.id
                  ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                  : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-sm text-[var(--text-primary)]">{f.name}</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5">{f.description}</p>
                  <p className="text-[11px] text-[var(--text-secondary)] mt-1">{t('templates27InsightsGenerate.updatedAt', { date: f.last_aggregated_at })}</p>
                </div>
                {f.is_stale && <Badge variant="warning">{t('templates27InsightsGenerate.badgeStale')}</Badge>}
              </div>
            </button>
          ))
        ) : (
          runs.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)] text-center py-8">
              {t('templates27InsightsGenerate.emptyPipelineRuns')}
            </p>
          ) : runs.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => onChange({ kind: 'pipeline_run', source_id: r.id, source_label: r.title })}
              className={cn(
                'w-full text-left p-3 rounded-md-custom border transition-all',
                value?.source_id === r.id
                  ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                  : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40',
              )}
            >
              <p className="font-medium text-sm text-[var(--text-primary)]">{r.title}</p>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t('templates27InsightsGenerate.rowsSummary', { count: r.row_count.toLocaleString('vi-VN'), date: r.finished_at })}</p>
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function TabButton({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center px-4 py-2 text-sm font-medium rounded-md-custom transition-colors',
        active
          ? 'bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
          : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)]',
      )}
    >
      {children}
    </button>
  );
}

// ----------------------------------------------------------------------------
// Step 2 — Question + framework (K-10: 1=1)
// ----------------------------------------------------------------------------

function StepQuestion({
  question, framework, onQuestionChange, onFrameworkChange,
}: {
  question: string;
  framework: Framework;
  onQuestionChange: (q: string) => void;
  onFrameworkChange: (f: Framework) => void;
}) {
  const t = useT();
  const FRAMEWORK_OPTIONS = getFrameworkOptions(t);
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
        <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates27InsightsGenerate.step2Title')}</h3>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          {t('templates27InsightsGenerate.step2Desc')}
        </p>
      </div>

      <div className="p-5 space-y-5">
        <div className="space-y-2">
          <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates27InsightsGenerate.questionLabel')}</label>
          <textarea
            value={question}
            onChange={(e) => onQuestionChange(e.target.value)}
            placeholder={t('templates27InsightsGenerate.questionPlaceholder')}
            rows={3}
            className="w-full px-3 py-2 text-sm bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
          />
          <p className="text-xs text-[var(--text-secondary)]">
            {t('templates27InsightsGenerate.questionHint')}
          </p>
        </div>

        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates27InsightsGenerate.frameworkLabel')}</label>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t('templates27InsightsGenerate.frameworkHint')}</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {FRAMEWORK_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => onFrameworkChange(opt.value)}
                className={cn(
                  'text-left p-3 rounded-md-custom border transition-all',
                  framework === opt.value
                    ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                    : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="font-medium text-sm text-[var(--text-primary)]">{opt.title}</p>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">{opt.description}</p>
                  </div>
                  {framework === opt.value && (
                    <Check className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Step 3 — Privacy / consent (K-3 + K-4 + K-5)
// ----------------------------------------------------------------------------

function StepPrivacy({
  consentExternal, onChange,
}: { consentExternal: boolean; onChange: (v: boolean) => void }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
        <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates27InsightsGenerate.step3Title')}</h3>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          {t('templates27InsightsGenerate.step3Desc')}
        </p>
      </div>

      <div className="p-5 space-y-4">
        {/* Internal Qwen — recommended */}
        <button
          type="button"
          onClick={() => onChange(false)}
          className={cn(
            'w-full text-left p-4 rounded-md-custom border-2 transition-all',
            !consentExternal
              ? 'border-[var(--state-success)] bg-[var(--state-success)]/5'
              : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--state-success)]/40',
          )}
        >
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-md-custom bg-[var(--state-success)]/15 flex items-center justify-center shrink-0">
              <Lock className="w-5 h-5 text-[var(--state-success)]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-medium text-sm text-[var(--text-primary)]">{t('templates27InsightsGenerate.qwenTitle')}</p>
                <Badge variant="success">{t('templates27InsightsGenerate.badgeRecommended')}</Badge>
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                {t('templates27InsightsGenerate.qwenDesc')}
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-[var(--text-secondary)]">
                <li className="flex items-center gap-1.5"><Check className="w-3 h-3 text-[var(--state-success)]" /> {t('templates27InsightsGenerate.qwenBenefit1')}</li>
                <li className="flex items-center gap-1.5"><Check className="w-3 h-3 text-[var(--state-success)]" /> {t('templates27InsightsGenerate.qwenBenefit2')}</li>
                <li className="flex items-center gap-1.5"><Check className="w-3 h-3 text-[var(--state-success)]" /> {t('templates27InsightsGenerate.qwenBenefit3')}</li>
              </ul>
            </div>
            {!consentExternal && <Check className="w-5 h-5 text-[var(--state-success)] shrink-0" />}
          </div>
        </button>

        {/* External AI — opt-in */}
        <button
          type="button"
          onClick={() => onChange(true)}
          className={cn(
            'w-full text-left p-4 rounded-md-custom border-2 transition-all',
            consentExternal
              ? 'border-[var(--state-warning)] bg-[var(--state-warning)]/5'
              : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--state-warning)]/40',
          )}
        >
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-md-custom bg-[var(--state-warning)]/15 flex items-center justify-center shrink-0">
              <Globe className="w-5 h-5 text-[var(--state-warning)]" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <p className="font-medium text-sm text-[var(--text-primary)]">{t('templates27InsightsGenerate.externalTitle')}</p>
                <Badge variant="warning">{t('templates27InsightsGenerate.badgeConsentRequired')}</Badge>
              </div>
              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                {t('templates27InsightsGenerate.externalDescPre')} <span className="font-medium text-[var(--text-primary)]">PII-mask</span> {t('templates27InsightsGenerate.externalDescMid')}
                (email/{t('templates27InsightsGenerate.externalDescPhone')}/ID → <span className="font-mono text-[10px]">[redacted]</span>) — K-5.
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-[var(--text-secondary)]">
                <li className="flex items-center gap-1.5"><AlertTriangle className="w-3 h-3 text-[var(--state-warning)]" /> {t('templates27InsightsGenerate.externalRisk1')}</li>
                <li className="flex items-center gap-1.5"><AlertTriangle className="w-3 h-3 text-[var(--state-warning)]" /> {t('templates27InsightsGenerate.externalRisk2')}</li>
                <li className="flex items-center gap-1.5"><AlertTriangle className="w-3 h-3 text-[var(--state-warning)]" /> {t('templates27InsightsGenerate.externalRisk3Pre')} <span className="font-mono">privacy=strict</span></li>
              </ul>
            </div>
            {consentExternal && <Check className="w-5 h-5 text-[var(--state-warning)] shrink-0" />}
          </div>
        </button>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates27InsightsGenerate.footerPre')} <span className="font-mono">llm_router.py</span> (K-3). {t('templates27InsightsGenerate.footerPost')}
          </p>
        </div>
      </div>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Step 4 — Review + dispatch
// ----------------------------------------------------------------------------

function StepReview({
  source, question, framework, consentExternal,
}: {
  source: SourceSelection;
  question: string;
  framework: Framework;
  consentExternal: boolean;
}) {
  const t = useT();
  const FRAMEWORK_OPTIONS = getFrameworkOptions(t);
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
        <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates27InsightsGenerate.step4Title')}</h3>
        <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates27InsightsGenerate.step4Desc')}</p>
      </div>

      <div className="p-5 space-y-4">
        <ReviewRow icon={Database} label={t('templates27InsightsGenerate.labelSource')}>
          <p className="font-medium text-sm text-[var(--text-primary)]">{source.source_label}</p>
          <p className="text-[11px] text-[var(--text-secondary)] font-mono">
            {source.kind === 'gold_feature' ? 'gold_feature' : 'pipeline_run'} · {source.source_id}
          </p>
        </ReviewRow>

        <ReviewRow icon={Lightbulb} label={t('templates27InsightsGenerate.labelQuestion')}>
          <p className="text-sm text-[var(--text-primary)] whitespace-pre-line">{question}</p>
        </ReviewRow>

        <ReviewRow icon={Layers} label={t('templates27InsightsGenerate.frameworkLabel')}>
          <Badge variant="current">
            {FRAMEWORK_OPTIONS.find((f) => f.value === framework)?.title ?? framework}
          </Badge>
        </ReviewRow>

        <ReviewRow icon={consentExternal ? Globe : Lock} label="LLM">
          <div className="flex items-center gap-2">
            <Badge variant={consentExternal ? 'warning' : 'success'}>
              {consentExternal ? t('templates27InsightsGenerate.reviewExternalConsented') : t('templates27InsightsGenerate.qwenTitle')}
            </Badge>
            {consentExternal && (
              <span className="text-[11px] text-[var(--text-secondary)]">{t('templates27InsightsGenerate.piiMaskNotice')}</span>
            )}
          </div>
        </ReviewRow>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 text-xs text-[var(--text-primary)]">
          <Eye className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates27InsightsGenerate.reviewFooter')}
          </p>
        </div>
      </div>
    </div>
  );
}

function ReviewRow({
  icon: Icon, label, children,
}: { icon: any; label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/30 border border-[var(--border-color)]/40">
      <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">{label}</p>
        {children}
      </div>
    </div>
  );
}
