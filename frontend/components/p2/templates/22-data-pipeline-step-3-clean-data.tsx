// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 22. /p2/pipelines/{id}/step-3-clean — Step 3 Cleaning Review (F-019)
// ----------------------------------------------------------------------------
// GET  /api/v1/clean/suggestions/{runId}    → grouped rule suggestions
// POST /api/v1/clean/apply                   → user-selected rules → Silver
//
// Rule categories (services/data-pipeline/silver/rule_catalog.py):
//   UNIVERSAL    — drop fully null rows, trim whitespace, dedup exact duplicates
//   BY_TYPE      — type coercion (date parse, number cast), null-rate threshold
//   BY_PURPOSE   — domain rules (email validate, phone normalize, currency parse)
//   AI_DETECTED  — anomaly heuristics surfaced by Qwen (low confidence, manual review)
//
// User toggles each rule. Apply = synchronous for small datasets, async with
// SSE progress for large ones. Audit log entry per rule applied (K-6).
// ============================================================================

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  ChevronLeft, ChevronRight, ShieldCheck, AlertCircle, Brain, Eraser,
  Layers, Sparkles, Filter,
} from 'lucide-react';

import {
  Button, Badge, Checkbox, ErrorBanner, cn,
  api,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { WizardStepper } from '@/components/p2/foundation-wizard';
import { useT } from '@/lib/i18n/provider';

type Category = 'UNIVERSAL' | 'BY_TYPE' | 'BY_PURPOSE' | 'AI_DETECTED';

interface CleaningRule {
  id:           string;
  category:     Category;
  name:         string;
  description:  string;
  affected_columns: string[];
  estimated_impact: string;
  is_recommended:   boolean;
  ai_confidence?:   number;
  is_destructive:   boolean;
}

function getCategoryMeta(t: (key: string) => string): Record<Category, { label: string; icon: any; desc: string }> {
  return {
    UNIVERSAL:    { label: t('templates22DataPipelineStep3CleanData.categoryUniversalLabel'),   icon: Layers, desc: t('templates22DataPipelineStep3CleanData.categoryUniversalDesc') },
    BY_TYPE:      { label: t('templates22DataPipelineStep3CleanData.categoryByTypeLabel'),       icon: Filter, desc: t('templates22DataPipelineStep3CleanData.categoryByTypeDesc') },
    BY_PURPOSE:   { label: t('templates22DataPipelineStep3CleanData.categoryByPurposeLabel'),    icon: Eraser, desc: t('templates22DataPipelineStep3CleanData.categoryByPurposeDesc') },
    AI_DETECTED:  { label: t('templates22DataPipelineStep3CleanData.categoryAiDetectedLabel'),   icon: Brain,  desc: t('templates22DataPipelineStep3CleanData.categoryAiDetectedDesc') },
  };
}

export default function PipelineStep3Clean() {
  const t = useT();
  const params = useParams<{ id: string }>();
  const pipelineId = params?.id ?? '';

  const [rules,    setRules]    = useState<CleaningRule[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [applying, setApplying] = useState(false);
  // Already-cleaned: a run at silver_complete must NOT be re-cleaned (BE guard
  // 400s). Show a calm "done → Step 4" state instead of a hard red error.
  const [cleaned,  setCleaned]  = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      // If Silver is already built (e.g. user navigated back to Step 3), don't
      // offer cleaning again — surface the done-state. Cheap status probe.
      const st = await api<{ status: string }>(`/api/v1/upload/${pipelineId}/status`);
      if (st.status === 'silver_complete' || st.status === 'analysis_complete') {
        setCleaned(true);
        setLoading(false);
        return;
      }
      // Real BE: POST /clean/suggestions {run_id} → {rules:[{rule_id, name,
      // description, category, applies_to_col, safe}]}.
      const res = await api<{ rules: any[] }>(`/api/v1/clean/suggestions`, {
        method: 'POST',
        body: JSON.stringify({ run_id: pipelineId }),
      });
      const mapped: CleaningRule[] = (res.rules ?? []).map((r: any) => ({
        id:               r.rule_id,
        category:         r.category,
        name:             r.name,
        description:      r.description,
        affected_columns: [],
        estimated_impact: '',
        is_recommended:   !!r.safe,
        is_destructive:   !r.safe,
      }));
      setRules(mapped);
      setSelected(new Set(mapped.filter((r) => r.is_recommended).map((r) => r.id)));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { if (pipelineId) load(); }, [pipelineId]);

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function apply() {
    setApplying(true);
    setProblem(null);
    try {
      // ASYNC: /clean/apply returns 202 and writes Silver in a background task
      // (a multi-sheet workbook is tens of thousands of rows — too slow to do
      // synchronously). Poll the run status until 'silver_complete'/'failed'.
      await api('/api/v1/clean/apply', {
        method: 'POST',
        body: JSON.stringify({
          run_id:    pipelineId,
          rule_ids:  Array.from(selected),
        }),
      });
      await pollUntilSilver();
      window.location.href = `/p2/pipelines/${pipelineId}/step-4-analyze`;
    } catch (err: any) {
      setProblem(err);
      setApplying(false);   // keep the spinner only while genuinely working
    }
  }

  async function pollUntilSilver() {
    // ~5 min ceiling at 2s intervals — large workbooks take a while.
    for (let i = 0; i < 150; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      const s = await api<{ status: string; error_message?: string }>(
        `/api/v1/upload/${pipelineId}/status`,
      );
      if (s.status === 'silver_complete') return;
      if (s.status === 'failed') {
        throw { title: s.error_message || t('templates22DataPipelineStep3CleanData.errCleanFailed'), status: 500 } as ProblemDetails;
      }
    }
    throw { title: t('templates22DataPipelineStep3CleanData.errCleanTimeout'), status: 504 } as ProblemDetails;
  }

  const byCat: Record<Category, CleaningRule[]> = {
    UNIVERSAL: [], BY_TYPE: [], BY_PURPOSE: [], AI_DETECTED: [],
  };
  rules.forEach((r) => byCat[r.category].push(r));

  const destructiveSelected = rules.filter((r) => selected.has(r.id) && r.is_destructive);
  const categoryMeta = getCategoryMeta(t);

  return (
    <>
      <PageHeader
        title={t('templates22DataPipelineStep3CleanData.pageTitle')}
        description={t('templates22DataPipelineStep3CleanData.pageDescription')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        <WizardStepper current={3} pipelineId={pipelineId} />

        {cleaned ? (
          <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm p-8 text-center space-y-4">
            <div className="w-12 h-12 mx-auto rounded-full bg-[var(--state-success)]/12 flex items-center justify-center">
              <ShieldCheck className="w-6 h-6 text-[var(--state-success)]" />
            </div>
            <div>
              <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('templates22DataPipelineStep3CleanData.cleanedTitle')}</h3>
              <p className="text-sm text-[var(--text-secondary)] mt-1 max-w-md mx-auto">
                {t('templates22DataPipelineStep3CleanData.cleanedDesc')}
              </p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-1">
              <Button
                variant="secondary"
                onClick={() => (window.location.href = `/p2/pipelines/${pipelineId}/step-2-columns`)}
              >
                <ChevronLeft className="w-4 h-4 mr-1" />
                {t('templates22DataPipelineStep3CleanData.backStep2')}
              </Button>
              <Button onClick={() => (window.location.href = `/p2/pipelines/${pipelineId}/step-4-analyze`)}>
                {t('templates22DataPipelineStep3CleanData.goStep4')}
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            </div>
          </div>
        ) : (
        <>
        <ErrorBanner problem={problem} />

        {destructiveSelected.length > 0 && (
          <div className="rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 p-3 flex items-start gap-3">
            <AlertCircle className="w-4 h-4 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <div className="flex-1 text-sm">
              <p className="font-medium text-[#9E814D]">
                {t('templates22DataPipelineStep3CleanData.destructiveWarning', { count: destructiveSelected.length })}
              </p>
              <p className="text-xs text-[#9E814D]/90 mt-0.5">
                {t('templates22DataPipelineStep3CleanData.destructiveNote')}
              </p>
            </div>
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            {[1,2,3].map((i) => <div key={i} className="h-40 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
          </div>
        ) : (
          (Object.keys(byCat) as Category[]).map((cat) => {
            const cRules = byCat[cat];
            if (cRules.length === 0) return null;
            const meta = categoryMeta[cat];
            const Icon = meta.icon;
            return (
              <div key={cat} className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
                <div className="px-5 py-4 border-b border-[var(--border-color)]/60 flex items-start gap-3 bg-[var(--bg-app)]/30">
                  <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/12 flex items-center justify-center shrink-0">
                    <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-serif text-base text-[var(--text-primary)]">{meta.label}</h3>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">{meta.desc}</p>
                  </div>
                  <Badge variant="default">
                    {t('templates22DataPipelineStep3CleanData.selectedCount', { selected: cRules.filter((r) => selected.has(r.id)).length, total: cRules.length })}
                  </Badge>
                </div>
                <div className="divide-y divide-[var(--border-color)]/60">
                  {cRules.map((r) => (
                    <RuleRow key={r.id} rule={r} checked={selected.has(r.id)} onToggle={() => toggle(r.id)} />
                  ))}
                </div>
              </div>
            );
          })
        )}

        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates22DataPipelineStep3CleanData.auditNotePrefix')} <span className="font-medium text-[var(--text-primary)]">decision_audit_log</span> {t('templates22DataPipelineStep3CleanData.auditNoteSuffix')}
          </p>
        </div>

        <div className="flex items-center justify-between">
          <Button
            variant="secondary"
            onClick={() => (window.location.href = `/p2/pipelines/${pipelineId}/step-2-columns`)}
            disabled={applying}
          >
            <ChevronLeft className="w-4 h-4 mr-1" />
            {t('templates22DataPipelineStep3CleanData.back')}
          </Button>
          <Button onClick={apply} isLoading={applying} disabled={selected.size === 0}>
            {t('templates22DataPipelineStep3CleanData.applyRules', { count: selected.size })}
            <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
        </>
        )}
      </div>
    </>
  );
}

function RuleRow({ rule, checked, onToggle }: any) {
  const t = useT();
  return (
    <div className={cn(
      'p-4 flex items-start gap-4 transition-colors',
      checked ? 'bg-[var(--primary-gold)]/4' : 'hover:bg-[var(--bg-app)]/40',
    )}>
      <div className="pt-0.5">
        <Checkbox checked={checked} onChange={onToggle} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center flex-wrap gap-2 mb-1">
          <p className="text-sm font-medium text-[var(--text-primary)]">{rule.name}</p>
          {rule.is_recommended && <Badge variant="success">{t('templates22DataPipelineStep3CleanData.badgeRecommended')}</Badge>}
          {rule.is_destructive && <Badge variant="warning">{t('templates22DataPipelineStep3CleanData.badgeDeleteRows')}</Badge>}
          {rule.ai_confidence != null && (
            <Badge variant="info" className="font-mono">
              AI {(rule.ai_confidence * 100).toFixed(0)}%
            </Badge>
          )}
        </div>
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{rule.description}</p>
        <div className="flex items-center flex-wrap gap-x-4 gap-y-1 mt-2 text-[11px] text-[var(--text-secondary)]">
          {rule.affected_columns.length > 0 && (
            <span>
              {t('templates22DataPipelineStep3CleanData.columnsLabel')} {rule.affected_columns.slice(0, 3).map((c: string) => (
                <span key={c} className="font-mono mr-1.5">{c}</span>
              ))}
              {rule.affected_columns.length > 3 && <span>+{rule.affected_columns.length - 3} {t('templates22DataPipelineStep3CleanData.moreSuffix')}</span>}
            </span>
          )}
          <span>{t('templates22DataPipelineStep3CleanData.impactLabel')} <span className="font-medium text-[var(--text-primary)]">{rule.estimated_impact}</span></span>
        </div>
      </div>
    </div>
  );
}
