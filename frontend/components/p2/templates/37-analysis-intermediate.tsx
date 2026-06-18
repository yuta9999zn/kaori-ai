// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 37. /p2/analysis/intermediate — Intermediate Analysis (F-033 PR A wired)
// ----------------------------------------------------------------------------
// 2-5 silver/gold sources + 1 framework. Qwen nội bộ (PR A always sends
// consent_external=false; PR B unlocks the toggle). MoM/YoY frameworks
// are deferred — calculation, not LLM, so they don't fit this surface.
//
// Endpoint: POST /api/v1/analysis/runs
//   body: { tier: 'intermediate', framework, question, source_ids: [{layer, id}], consent_external }
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, FlaskConical, Network, Lock, ArrowRight, Layers,
  Database, Sparkles, ShieldCheck, Plus, X, CheckCircle2,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Framework = 'swot' | '6w' | '2h' | 'fishbone';

interface Source { id: string; label: string; layer: 'silver' | 'gold'; row_count?: number; }

const FRAMEWORKS: Array<{ code: Framework; label: string }> = [
  { code: 'swot',     label: 'SWOT' },
  { code: '6w',       label: '6W' },
  { code: '2h',       label: '2H' },
  { code: 'fishbone', label: 'Fishbone' },
];

type CreateResp = { run_id: string; tier: string; status: string };

export default function AnalystIntermediatePage() {
  const [available, setAvailable] = useState<Source[]>([]);
  const [picked,    setPicked]    = useState<Source[]>([]);
  const [framework, setFramework] = useState<Framework>('swot');
  const [question,  setQuestion]  = useState('');
  const [problem,   setProblem]   = useState<ProblemDetails | null>(null);
  const [creating,  setCreating]  = useState(false);

  useEffect(() => {
    api<{ items: Source[] }>('/api/v1/analysis/sources?layer=silver,gold')
      .then((r) => setAvailable(r.items))
      .catch((err) => setProblem(err));
  }, []);

  function pick(s: Source) {
    if (picked.length >= 5) return;
    if (picked.find((p) => p.id === s.id)) return;
    setPicked([...picked, s]);
  }
  function unpick(id: string) {
    setPicked(picked.filter((p) => p.id !== id));
  }

  async function handleRun() {
    setProblem(null);
    setCreating(true);
    try {
      const res = await api<CreateResp>('/api/v1/analysis/runs', {
        method: 'POST',
        body: JSON.stringify({
          tier:             'intermediate',
          framework,
          question:         question.trim(),
          source_ids:       picked.map((p) => ({ layer: p.layer, id: p.id, label: p.label })),
          consent_external: false,
        }),
      });
      window.location.href = `/p2/analysis/runs/${res.run_id}`;
    } catch (err: any) {
      setProblem(err);
      setCreating(false);
    }
  }

  const canRun = picked.length >= 2 && picked.length <= 5 && question.trim().length > 0 && !creating;

  return (
    <>
      <PageHeader
        title="Phân tích trung cấp"
        description="2-5 nguồn Silver/Gold + 1 khung phân tích."
        actions={
          <>
            <Badge variant="info">F-033 · Intermediate</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/analysis')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Hub
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
              <Network className="w-5 h-5 text-[var(--primary-gold-dark)]" />
            </div>
            <div>
              <h3 className="font-serif text-base text-[var(--text-primary)]">Trung cấp</h3>
              <p className="text-xs text-[var(--text-secondary)]">Multi-source · 1 framework · Qwen nội bộ</p>
            </div>
          </div>
          <Badge variant="success"><Lock className="w-3 h-3 mr-1 inline" />Qwen nội bộ</Badge>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Available sources */}
          <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--border-color)]/60">
              <h4 className="font-serif text-sm text-[var(--text-primary)]">Nguồn có sẵn (Silver / Gold)</h4>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">Tối đa 5 nguồn / lần phân tích</p>
            </div>
            <div className="p-3 space-y-1.5 max-h-[400px] overflow-y-auto">
              {available.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)] text-center py-8">— Chưa có nguồn —</p>
              ) : available.map((s) => {
                const isPicked = !!picked.find((p) => p.id === s.id);
                return (
                  <button
                    key={`${s.layer}-${s.id}`}
                    type="button"
                    onClick={() => isPicked ? unpick(s.id) : pick(s)}
                    disabled={!isPicked && picked.length >= 5}
                    className={cn(
                      'w-full text-left p-2.5 rounded-md-custom border transition-all text-sm',
                      isPicked
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40 disabled:opacity-50',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        {isPicked ? <CheckCircle2 className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0" /> : <Plus className="w-3.5 h-3.5 text-[var(--text-secondary)] shrink-0" />}
                        <span className="text-[var(--text-primary)] truncate">{s.label}</span>
                      </div>
                      <Badge variant={s.layer === 'gold' ? 'current' : 'default'}>{s.layer.toUpperCase()}</Badge>
                    </div>
                    {typeof s.row_count === 'number' && s.row_count > 0 && (
                      <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 ml-5">{s.row_count.toLocaleString('vi-VN')} hàng</p>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Picked sources + config */}
          <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--border-color)]/60 flex items-center justify-between">
              <h4 className="font-serif text-sm text-[var(--text-primary)]">Đã chọn ({picked.length}/5)</h4>
              {picked.length > 0 && (
                <Button size="sm" variant="tertiary" onClick={() => setPicked([])}>
                  Xoá hết
                </Button>
              )}
            </div>
            <div className="p-3 space-y-1.5 min-h-[120px]">
              {picked.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)] text-center py-6">Chọn ít nhất 2 nguồn để chạy phân tích</p>
              ) : picked.map((s) => (
                <div key={`${s.layer}-${s.id}`} className="flex items-center justify-between p-2 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40">
                  <div className="flex items-center gap-2">
                    <Database className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                    <span className="text-sm text-[var(--text-primary)]">{s.label}</span>
                    <Badge variant={s.layer === 'gold' ? 'current' : 'default'}>{s.layer.toUpperCase()}</Badge>
                  </div>
                  <button onClick={() => unpick(s.id)} className="text-[var(--text-secondary)] hover:text-[var(--state-error)]" aria-label="Xoá">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>

            <div className="px-4 py-3 border-t border-[var(--border-color)]/60 space-y-3">
              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Khung (chọn 1 — K-10)</label>
                <div className="mt-1.5 grid grid-cols-4 gap-1.5">
                  {FRAMEWORKS.map((f) => (
                    <button
                      key={f.code}
                      type="button"
                      onClick={() => setFramework(f.code)}
                      className={cn(
                        'px-2 py-1.5 text-xs font-medium rounded-sm-custom border transition-colors',
                        framework === f.code
                          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                          : 'border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                      )}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Câu hỏi</label>
                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  rows={2}
                  placeholder="Ví dụ: Mối liên hệ giữa marketing spend và conversion của 3 segment lớn nhất?"
                  className="mt-1 w-full px-3 py-2 text-sm bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
                />
              </div>

              <Button onClick={handleRun} disabled={!canRun} isLoading={creating} className="w-full">
                <Sparkles className="w-4 h-4 mr-2" />
                Chạy phân tích trung cấp
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            <span className="font-medium text-[var(--text-primary)]">K-10:</span> mỗi câu hỏi chỉ chạy được 1 khung. Để chạy nhiều khung trên cùng câu hỏi, dispatch lại từ <a href="/p2/frameworks" className="text-[var(--primary-gold-dark)] underline">trang Frameworks</a>.
          </p>
        </div>
      </div>
    </>
  );
}
