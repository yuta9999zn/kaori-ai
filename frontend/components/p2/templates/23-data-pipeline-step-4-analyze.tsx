// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 23. /p2/pipelines/{id}/step-4-analyze — Step 4 Analysis Config (F-020)
// ----------------------------------------------------------------------------
// GET  /api/v1/analytics/templates                  → catalog
// POST /api/v1/analytics/runs                        → start analysis
//
// CRITICAL — K-4 (External AI Consent):
//   Default consent_external = false → all LLM calls go to Qwen 14B local.
//   Toggle ON requires user confirmation modal explaining:
//     - PII auto-redacted via guardrails (K-5) BEFORE leaving boundary
//     - Data sent to Claude Sonnet / GPT-4o (named explicitly)
//     - Decision logged to decision_audit_log (K-6) with consent flag
//     - Per-tenant audit accessible at /p2/decisions
//
// K-3 / K-10 also enforced here:
//   - All LLM via llm_router (FE just sets flag)
//   - 1 question = 1 framework (no parallel SWOT+5Why selection)
// ============================================================================

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  ChevronLeft, ShieldCheck, AlertTriangle, Lock, Globe,
  Sparkles, BarChart3, X, Check, Zap,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { WizardStepper } from '@/components/p2/foundation-wizard';
import { useT } from '@/lib/i18n/provider';

interface AnalysisTemplate {
  id:          string;
  category:    'statistical' | 'ml' | 'forecasting' | 'anomaly';
  name:        string;
  description: string;
  min_rows:          number;     // BE-declared minimum rows for this analysis
  eligible:          boolean;     // BE eligibility for the detected data profile
  estimated_minutes: number;
  needs_external_ai: boolean;
  is_recommended:    boolean;
}

const CATEGORY_KEY: Record<string, string> = {
  statistical: 'templates23DataPipelineStep4Analyze.categoryStatistical',
  ml:          'templates23DataPipelineStep4Analyze.categoryMl',
  forecasting: 'templates23DataPipelineStep4Analyze.categoryForecasting',
  anomaly:     'templates23DataPipelineStep4Analyze.categoryAnomaly',
};

export default function PipelineStep4Analyze() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const pipelineId = params?.id ?? '';

  const [templates,  setTemplates]  = useState<AnalysisTemplate[]>([]);
  const [selected,   setSelected]   = useState<Set<string>>(new Set());
  const [consentExt, setConsentExt] = useState(false);
  const [showConsent, setShowConsent] = useState(false);
  const [loading,   setLoading]   = useState(true);
  const [problem,   setProblem]   = useState<ProblemDetails | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      // Real BE: GET /analytics/templates → ARRAY of
      // {template_id, display_name, description, eligible, min_rows, ...}.
      // Run-aware eligibility: BE profiles this run's Silver (types + rows)
      // so the picker stops warning "chưa đủ điều kiện" on clean data.
      const res = await api<any[]>(
        `/api/v1/analytics/templates?run_id=${encodeURIComponent(pipelineId)}`
      );
      const mapped: AnalysisTemplate[] = (res ?? []).map((t: any) => ({
        id:                t.template_id,
        category:          (['statistical', 'ml', 'forecasting', 'anomaly'].includes(t.category) ? t.category : 'statistical'),
        name:              t.display_name,
        description:       t.description,
        min_rows:          t.min_rows ?? 0,
        eligible:          !!t.eligible,
        estimated_minutes: 1,
        needs_external_ai: !!t.needs_external_ai,
        is_recommended:    !!t.eligible,
      }));
      setTemplates(mapped);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  function toggleTemplate(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function handleConsentToggle() {
    if (!consentExt) {
      setShowConsent(true);
    } else {
      setConsentExt(false);
    }
  }

  function confirmConsent() {
    setConsentExt(true);
    setShowConsent(false);
  }

  async function startAnalysis() {
    setSubmitting(true);
    setProblem(null);
    try {
      // Real BE: POST /analytics/runs {run_id, templates, config} → 202
      // {analysis_run_id}. Step 5 reads the analysis_run_id from ?run_id=.
      const res = await api<{ analysis_run_id: string }>('/api/v1/analytics/runs', {
        method: 'POST',
        body: JSON.stringify({
          run_id:    pipelineId,
          templates: Array.from(selected),
          config:    { consent_external: consentExt },
        }),
      });
      window.location.href = `/p2/pipelines/${pipelineId}/step-5-results?run_id=${res.analysis_run_id}`;
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSubmitting(false);
    }
  }

  const blockedSelections = templates.filter((t) => selected.has(t.id) && t.needs_external_ai && !consentExt);

  return (
    <>
      <PageHeader
        title={t('templates23DataPipelineStep4Analyze.title')}
        description={t('templates23DataPipelineStep4Analyze.description')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        <WizardStepper current={4} pipelineId={pipelineId} />

        <ErrorBanner problem={problem} />

        <div className={cn(
          'rounded-lg-custom border-2 p-5 shadow-soft-sm transition-colors',
          consentExt
            ? 'bg-[var(--state-warning)]/8 border-[var(--state-warning)]/40'
            : 'bg-[var(--primary-gold)]/8 border-[var(--primary-gold)]/30',
        )}>
          <div className="flex items-start gap-4">
            <div className={cn(
              'w-12 h-12 rounded-full flex items-center justify-center shrink-0',
              consentExt ? 'bg-[var(--state-warning)]/20' : 'bg-[var(--primary-gold)]/20',
            )}>
              {consentExt
                ? <Globe className="w-6 h-6 text-[var(--state-warning)]" />
                : <Lock className="w-6 h-6 text-[var(--primary-gold-dark)]" />}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-3 mb-2 flex-wrap">
                <h3 className="font-serif text-lg text-[var(--text-primary)]">
                  {t('templates23DataPipelineStep4Analyze.aiSourceLabel')} {consentExt ? t('templates23DataPipelineStep4Analyze.aiSourceExternal') : t('templates23DataPipelineStep4Analyze.aiSourceInternal')}
                </h3>
                <Button
                  size="sm"
                  variant={consentExt ? 'destructive' : 'secondary'}
                  onClick={handleConsentToggle}
                >
                  {consentExt ? t('templates23DataPipelineStep4Analyze.disableExternalAi') : t('templates23DataPipelineStep4Analyze.enableExternalAi')}
                </Button>
              </div>
              <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                {consentExt ? (
                  <>
                    <span className="text-[#9E814D] font-medium">{t('templates23DataPipelineStep4Analyze.consentBannerExternalLabel')}</span>{' '}
                    {t('templates23DataPipelineStep4Analyze.consentBannerExternalBody')}{' '}
                    <a href="/p2/decisions" className="underline">{t('templates23DataPipelineStep4Analyze.decisionAuditLogLinkText')}</a> {t('templates23DataPipelineStep4Analyze.consentBannerFlagPrefix')} <span className="font-mono">consent_external=true</span>.
                  </>
                ) : (
                  <>
                    <span className="text-[var(--text-primary)] font-medium">{t('templates23DataPipelineStep4Analyze.consentBannerPrivateLabel')}</span>{' '}
                    {t('templates23DataPipelineStep4Analyze.consentBannerPrivateBody')}
                  </>
                )}
              </p>
            </div>
          </div>
        </div>

        {blockedSelections.length > 0 && (
          <div className="rounded-md-custom bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 p-3 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-[var(--state-error)] shrink-0 mt-0.5" />
            <p className="text-sm text-[#9B5050]">
              {t('templates23DataPipelineStep4Analyze.blockedSelectionsWarning', { count: blockedSelections.length })}
            </p>
          </div>
        )}

        <div>
          <h3 className="font-serif text-base text-[var(--text-primary)] mb-3">
            {t('templates23DataPipelineStep4Analyze.templatesSectionTitle')} {selected.size > 0 && <span className="text-sm text-[var(--text-secondary)] font-sans">{t('templates23DataPipelineStep4Analyze.selectedCountSuffix', { count: selected.size })}</span>}
          </h3>
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {[1,2,3,4].map((i) => <div key={i} className="h-32 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {templates.map((t) => (
                <TemplateCard
                  key={t.id}
                  template={t}
                  selected={selected.has(t.id)}
                  blocked={t.needs_external_ai && !consentExt}
                  onToggle={() => toggleTemplate(t.id)}
                />
              ))}
            </div>
          )}
        </div>

        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates23DataPipelineStep4Analyze.footerLlmRouterPart1')} <span className="font-medium text-[var(--text-primary)]">llm_router</span> {t('templates23DataPipelineStep4Analyze.footerLlmRouterPart2')} <span className="font-mono">&lt;EMAIL_1&gt;</span>, <span className="font-mono">&lt;PHONE_1&gt;</span>{t('templates23DataPipelineStep4Analyze.footerLlmRouterPart3')}
          </p>
        </div>

        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            onClick={() => (window.location.href = `/p2/pipelines/${pipelineId}/step-3-clean`)}
            disabled={submitting}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            {t('templates23DataPipelineStep4Analyze.backButton')}
          </Button>
          <Button
            onClick={startAnalysis}
            isLoading={submitting}
            disabled={selected.size === 0 || blockedSelections.length > 0}
          >
            <Sparkles className="w-4 h-4 mr-2" />
            {t('templates23DataPipelineStep4Analyze.startAnalysisButton', { count: selected.size })}
          </Button>
        </div>
      </div>

      {showConsent && (
        <ConsentModal
          onCancel={() => setShowConsent(false)}
          onConfirm={confirmConsent}
        />
      )}
    </>
  );
}

function TemplateCard({ template: tpl, selected, blocked, onToggle }: any) {
  const t = useT();
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        'text-left rounded-lg-custom bg-[var(--bg-card)] border p-4 shadow-soft-sm transition-all',
        selected
          ? 'border-[var(--primary-gold)] ring-1 ring-[var(--primary-gold)] bg-[var(--primary-gold)]/4'
          : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]/30 hover:shadow-soft-md',
        blocked && 'opacity-60',
      )}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <h4 className="font-medium text-[var(--text-primary)]">{tpl.name}</h4>
          <Badge variant="default" className="text-[10px]">{t(CATEGORY_KEY[tpl.category] ?? CATEGORY_KEY.statistical)}</Badge>
          {tpl.is_recommended && <Badge variant="success" className="text-[10px]">{t('templates23DataPipelineStep4Analyze.recommendedBadge')}</Badge>}
          {tpl.needs_external_ai && (
            <Badge variant="warning" className="text-[10px]">
              <Globe className="w-2.5 h-2.5 mr-0.5 inline" />
              {t('templates23DataPipelineStep4Analyze.needsExternalAiBadge')}
            </Badge>
          )}
        </div>
        <div className={cn(
          'w-5 h-5 rounded-full border flex items-center justify-center shrink-0 mt-0.5',
          selected ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]' : 'border-[var(--border-color)]',
        )}>
          {selected && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
        </div>
      </div>
      <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-3">{tpl.description}</p>
      <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
        <span>{t('templates23DataPipelineStep4Analyze.estimatedMinutes', { minutes: tpl.estimated_minutes })}</span>
        {tpl.min_rows > 0 && <span>{t('templates23DataPipelineStep4Analyze.minRowsRequired', { rows: tpl.min_rows.toLocaleString('vi-VN') })}</span>}
      </div>
      {!tpl.eligible && !blocked && (
        <p className="text-[11px] text-[#9E814D] mt-2 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" />
          {t('templates23DataPipelineStep4Analyze.notEligibleHint')}
        </p>
      )}
      {blocked && (
        <p className="text-[11px] text-[#9B5050] mt-2 flex items-center gap-1">
          <AlertTriangle className="w-3 h-3" />
          {t('templates23DataPipelineStep4Analyze.blockedHint')}
        </p>
      )}
    </button>
  );
}

function ConsentModal({ onCancel, onConfirm }: any) {
  const t = useT();
  const [acked, setAcked] = useState(false);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/40 backdrop-blur-sm" onClick={onCancel}>
      <div
        className="bg-[var(--bg-card)] rounded-lg-custom shadow-soft-lg border border-[var(--border-color)] w-full max-w-[560px] p-6 animate-slide-up-fade"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[var(--state-warning)]/15 flex items-center justify-center">
              <Globe className="w-5 h-5 text-[var(--state-warning)]" />
            </div>
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('templates23DataPipelineStep4Analyze.enableExternalAi')}</h3>
          </div>
          <button onClick={onCancel} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-4">
          {t('templates23DataPipelineStep4Analyze.consentModalIntro')}
        </p>

        <ul className="space-y-2 mb-5 text-sm">
          {[
            { icon: Lock,        text: t('templates23DataPipelineStep4Analyze.consentModalItem1') },
            { icon: ShieldCheck, text: t('templates23DataPipelineStep4Analyze.consentModalItem2') },
            { icon: BarChart3,   text: t('templates23DataPipelineStep4Analyze.consentModalItem3') },
            { icon: Zap,         text: t('templates23DataPipelineStep4Analyze.consentModalItem4') },
          ].map((item, i) => {
            const Icon = item.icon;
            return (
              <li key={i} className="flex items-start gap-3 p-2 rounded-md-custom bg-[var(--bg-app)]/50 border border-[var(--border-color)]/40">
                <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                <span className="text-[var(--text-primary)]">{item.text}</span>
              </li>
            );
          })}
        </ul>

        <div className="mb-5 p-3 rounded-md-custom bg-[var(--state-warning)]/8 border border-[var(--state-warning)]/30">
          <Checkbox
            checked={acked}
            onChange={(e) => setAcked(e.target.checked)}
            label={<span className="text-[#9E814D]">{t('templates23DataPipelineStep4Analyze.consentModalAckLabel')}</span>}
          />
        </div>

        <div className="flex justify-end gap-3">
          <Button variant="secondary" onClick={onCancel}>{t('templates23DataPipelineStep4Analyze.cancelButton')}</Button>
          <Button variant="destructive" onClick={onConfirm} disabled={!acked}>
            {t('templates23DataPipelineStep4Analyze.enableExternalAi')}
          </Button>
        </div>
      </div>
    </div>
  );
}
