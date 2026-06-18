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
// Templates list comes from the legacy /api/v2/enterprise/analysis/templates
// route (still served via MSW pending the BE catalogue endpoint). The
// pipeline picker uses the F-022 cursor envelope {data, meta}.
// ============================================================================

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import {
  ChevronLeft, FlaskConical, Lightbulb, ShieldCheck, Lock, ArrowRight,
  Database, Layers, Sparkles, CheckCircle2,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface PipelineRun  { id: string; title: string; finished_at?: string; }
interface Template     { id: string; name: string; description: string; }

type CreateResp = { run_id: string; tier: string; status: string };

export default function AnalystBasicPage() {
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
      api<{ items: Template[] }>('/api/v2/enterprise/analysis/templates?tier=basic'),
    ])
      .then(([p, t]) => {
        const rows = (p.data || p.items || []).map((r: any) => ({
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

  return (
    <>
      <PageHeader
        title="Phân tích cơ bản"
        description="1 pipeline · template + Qwen nội bộ. Phù hợp câu hỏi nhanh."
        actions={
          <>
            <Badge variant="info">F-033 · Basic</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/analysis')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Hub
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
                <h3 className="font-serif text-base text-[var(--text-primary)]">Cơ bản</h3>
                <p className="text-xs text-[var(--text-secondary)]">Scope: {initialScope === 'single' ? 'Single pipeline' : initialScope === 'multi' ? 'Multi pipeline' : 'Cross workspace'}</p>
              </div>
            </div>
            <Badge variant="success">
              <Lock className="w-3 h-3 mr-1 inline" />
              Qwen 2.5 nội bộ
            </Badge>
          </div>
        </div>

        {/* Form */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-4">
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">Pipeline nguồn</label>
            <div className="relative mt-1">
              <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
              <select
                value={pipelineId}
                onChange={(e) => setPipelineId(e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              >
                {pipelines.length === 0 && <option value="">— Chưa có pipeline —</option>}
                {pipelines.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">Template phân tích (chọn ≥ 1)</label>
            <div className="mt-2 space-y-1.5">
              {templates.length === 0 && (
                <p className="text-sm text-[var(--text-secondary)]">— Chưa có template —</p>
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
            <label className="text-sm font-medium text-[var(--text-primary)]">Câu hỏi cụ thể (tuỳ chọn)</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              placeholder="Ví dụ: Top 3 yếu tố ảnh hưởng doanh thu tháng 4?"
              className="mt-1 w-full px-3 py-2 text-sm bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>

          <Button onClick={handleRun} disabled={!canRun} isLoading={creating} className="w-full">
            <Sparkles className="w-4 h-4 mr-2" />
            Chạy phân tích cơ bản
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>

        {/* What you'll get */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <p className="font-serif text-sm text-[var(--text-primary)] mb-3">Kết quả sẽ gồm</p>
          <ul className="space-y-1.5 text-sm">
            <li className="flex items-start gap-2"><Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" /><span className="text-[var(--text-primary)]">Narrative tóm tắt 3-5 câu</span></li>
            <li className="flex items-start gap-2"><Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" /><span className="text-[var(--text-primary)]">Chart minh hoạ + bảng KPI từ các template đã chọn</span></li>
            <li className="flex items-start gap-2"><Lightbulb className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" /><span className="text-[var(--text-primary)]">Khuyến nghị hành động (có thể chuyển thành Decision)</span></li>
          </ul>
        </div>

        {/* Phase 1 alternative */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Pipeline Wizard step-4 (<a href="/p2/pipelines" className="text-[var(--primary-gold-dark)] underline">/p2/pipelines</a>) chạy cùng template engine — Basic tier ở đây mở thêm khả năng dispatch nhanh không cần đi qua wizard.
          </p>
        </div>
      </div>
    </>
  );
}
