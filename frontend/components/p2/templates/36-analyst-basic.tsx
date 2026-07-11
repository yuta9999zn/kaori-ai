// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 36. /p2/analysis/basic — Basic Analysis (F-033 PR A wired)
// ----------------------------------------------------------------------------
// 1 pipeline + 1+ template + Qwen nội bộ → narrative + chart + 3 khuyến nghị.
//
// Endpoint:  POST /api/v1/analysis/runs
//   body: { tier: 'basic', pipeline_run_id, templates: [...], question?, consent_external? }
//
// Templates list comes from GET /api/v1/analysis/templates (ai-orchestrator
// multi_tier.py — sourced from the canonical TEMPLATE_REGISTRY). The old
// /api/v2/enterprise/analysis/templates path was MSW-only and 503'd live.
// The pipeline picker uses the F-022 cursor envelope {data, meta}.
// ============================================================================

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  ChevronLeft, FlaskConical, Lightbulb, ShieldCheck, Lock, ArrowRight,
  Database, Layers, Sparkles, CheckCircle2,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
interface PipelineRun  { id: string; title: string; finished_at?: string; }
interface Template     { id: string; name: string; description: string; }

type CreateResp = { run_id: string; tier: string; status: string };

export default function AnalystBasicPage() {
  const t = useT();
  const search = useSearchParams();
  const initialScope = (search?.get('scope') ?? 'single') as 'single' | 'multi' | 'cross';

  const [pipelines,  setPipelines]  = useState<PipelineRun[]>([]);
  const [templates,  setTemplates]  = useState<Template[]>([]);
  const [pipelineId, setPipelineId] = useState<string>('');
  const [picked,     setPicked]     = useState<Set<string>>(new Set());
  const [question,   setQuestion]   = useState('');
  const [problem,    setProblem]    = useState<ProblemDetails | null>(null);
  const [creating,   setCreating]   = useState(false);

  useEffect(() => {
    Promise.all([
      // F-022 cursor envelope: {data: [...], meta: {...}}
      api<{ data?: any[]; items?: any[] }>('/api/v1/pipelines?limit=20'),
      api<{ items: Template[] }>('/api/v1/analysis/templates?tier=basic'),
    ])
      .then(([p, t]) => {
        // Chỉ liệt kê nguồn CÓ dòng bảng Silver — run của tài liệu văn bản
        // (docx/pdf, DocSage bóc chữ) vẫn silver_complete nhưng 0 dòng bảng,
        // và run csv mới dừng ở Bronze (chưa qua 5 bước làm sạch) cũng chưa
        // phân tích được; chọn vào là lỗi "không có dữ liệu Silver".
        const rows = (p.data || p.items || [])
          .filter((r: any) => (r.row_count_silver ?? 0) > 0)
          .map((r: any) => ({
            id:    r.run_id || r.id,
            title: r.filename || r.title || r.run_id,
            finished_at: r.created_at || r.finished_at,
          }));
        const completed = rows.filter((r: any) =>
          !r.status || r.status === 'analysis_complete' || r.id);
        setPipelines(completed);
        setTemplates(t.items);
        if (completed[0]) setPipelineId(completed[0].id);
        if (t.items[0]) setPicked(new Set([t.items[0].id]));
      })
      .catch((err) => setProblem(err));
  }, []);

  function togglePicked(id: string) {
    setPicked((prev) => {
      const n = new Set(prev);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  async function handleRun() {
    setProblem(null);
    setCreating(true);
    try {
      const res = await api<CreateResp>('/api/v1/analysis/runs', {
        method: 'POST',
        body: JSON.stringify({
          tier:             'basic',
          pipeline_run_id:  pipelineId,
          templates:        Array.from(picked),
          question:         question.trim() || null,
          consent_external: false,
        }),
      });
      window.location.href = `/p2/analysis/runs/${res.run_id}`;
    } catch (err: any) {
      setProblem(err);
      setCreating(false);
    }
  }

  const canRun = pipelineId && picked.size > 0 && !creating;

  const scopeLabel = initialScope === 'single'
    ? t('templates36AnalystBasic.scopeSingle')
    : initialScope === 'multi'
      ? t('templates36AnalystBasic.scopeMulti')
      : t('templates36AnalystBasic.scopeCross');

  return (
    <>
      <PageHeader
        title={t('templates36AnalystBasic.title')}
        description={t('templates36AnalystBasic.description')}
        actions={
          <>
            <Badge variant="info">F-033 · Basic</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/analysis')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              {t('templates36AnalystBasic.hub')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {/* Tier strip */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
                <FlaskConical className="w-5 h-5 text-[var(--primary-gold-dark)]" />
              </div>
              <div>
                <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates36AnalystBasic.basicTier')}</h3>
                <p className="text-xs text-[var(--text-secondary)]">{t('templates36AnalystBasic.scopeText', { scope: scopeLabel })}</p>
              </div>
            </div>
            <Badge variant="success">
              <Lock className="w-3 h-3 mr-1 inline" />
              {t('templates36AnalystBasic.qwenInternal')}
            </Badge>
          </div>
        </div>

        {/* Form */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-4">
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates36AnalystBasic.sourcePipeline')}</label>
            <div className="relative mt-1">
              <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
              <select
                value={pipelineId}
                onChange={(e) => setPipelineId(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              >
                {pipelines.length === 0 && <option value="">{t('templates36AnalystBasic.noPipeline')}</option>}
                {pipelines.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates36AnalystBasic.analysisTemplate')}</label>
            <div className="mt-2 space-y-1.5">
              {templates.length === 0 && (
                <p className="text-sm text-[var(--text-secondary)]">{t('templates36AnalystBasic.noTemplate')}</p>
              )}
              {templates.map((t) => {
                const sel = picked.has(t.id);
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => togglePicked(t.id)}
                    className={cn(
                      'w-full text-left flex items-start gap-3 p-3 rounded-md-custom border transition-all',
                      sel
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40',
                    )}
                  >
                    {sel
                      ? <CheckCircle2 className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                      : <Layers className="w-4 h-4 text-[var(--text-secondary)] shrink-0 mt-0.5" />}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[var(--text-primary)]">{t.name}</p>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug">{t.description}</p>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates36AnalystBasic.specificQuestion')}</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              placeholder={t('templates36AnalystBasic.questionPlaceholder')}
              className="mt-1 w-full px-3 py-2 text-sm bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>

          <Button onClick={handleRun} disabled={!canRun} isLoading={creating} className="w-full">
            <Sparkles className="w-4 h-4 mr-2" />
            {t('templates36AnalystBasic.runBasicAnalysis')}
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>

        {/* What you'll get */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <p className="font-serif text-sm text-[var(--text-primary)] mb-3">{t('templates36AnalystBasic.resultsInclude')}</p>
          <ul className="space-y-1.5 text-sm">
            <li className="flex items-start gap-2"><Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" /><span className="text-[var(--text-primary)]">{t('templates36AnalystBasic.resultNarrative')}</span></li>
            <li className="flex items-start gap-2"><Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" /><span className="text-[var(--text-primary)]">{t('templates36AnalystBasic.resultChart')}</span></li>
            <li className="flex items-start gap-2"><Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" /><span className="text-[var(--text-primary)]">{t('templates36AnalystBasic.resultRecommendation')}</span></li>
          </ul>
        </div>

        {/* Phase 1 alternative */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates36AnalystBasic.wizardAltPrefix')} (<a href="/p2/pipelines" className="text-[var(--primary-gold-dark)] underline">/p2/pipelines</a>) {t('templates36AnalystBasic.wizardAltSuffix')}
          </p>
        </div>
      </div>
    </>
  );
}
