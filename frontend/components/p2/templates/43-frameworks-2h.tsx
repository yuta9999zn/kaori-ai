// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 43. /p2/frameworks/2h — 2H (F-034 🔵 Phase 2)
// ----------------------------------------------------------------------------
// How (cách thức) · How much (định lượng độ lớn). Đào sâu định lượng cho
// vấn đề + giải pháp.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, Wrench, Sparkles, ShieldCheck, Lock, Globe,
  Database, Calculator, Hash,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api, formatVND, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface Source { id: string; label: string; }
interface TwoHResult {
  how:      { mechanism: string; steps: string[] };
  how_much: { metric: string; value_vnd?: number; value_pct?: number; baseline?: string; confidence: number };
}

export default function TwoHPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [question, setQuestion] = useState('');
  const [consentExternal, setConsentExternal] = useState(false);
  const [result, setResult] = useState<TwoHResult | null>(null);
  const [running, setRunning] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    api<{ items: Source[] }>('/api/v1/data/gold/features?limit=20')
      .then((r) => { setSources(r.items); if (r.items[0]) setSourceId(r.items[0].id); })
      .catch((err) => setProblem(err));
  }, []);

  async function generate() {
    setRunning(true);
    setProblem(null);
    try {
      const r = await api<TwoHResult>('/api/v2/enterprise/frameworks/generate', {
        method: 'POST',
        body:   JSON.stringify({ framework: '2H', source_id: sourceId, question: question.trim(), consent_external: consentExternal }),
      });
      setResult(r);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <PageHeader
        title="2H"
        description="How (cơ chế) · How much (định lượng) — đào sâu nguyên nhân + impact bằng số."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-034</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/frameworks')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Khung khác
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Nguồn</label>
              <div className="relative mt-1">
                <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
                <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30">
                  {sources.length === 0 && <option value="">— Chưa có Gold feature —</option>}
                  {sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Câu hỏi (K-10)</label>
              <input type="text" value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ví dụ: Bao nhiêu doanh thu mất do giao hàng trễ Q2?" className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
            </div>
          </div>

          <div className={cn('p-3 rounded-md-custom border-2', consentExternal ? 'border-[var(--state-warning)]/50 bg-[var(--state-warning)]/5' : 'border-[var(--state-success)]/40 bg-[var(--state-success)]/5')}>
            <Checkbox
              checked={consentExternal}
              onChange={() => setConsentExternal(!consentExternal)}
              label={
                <span className="inline-flex items-center gap-2">
                  {consentExternal ? <Globe className="w-4 h-4 text-[var(--state-warning)]" /> : <Lock className="w-4 h-4 text-[var(--state-success)]" />}
                  {consentExternal ? 'AI bên ngoài (PII đã mask)' : 'Qwen nội bộ'}
                </span>
              }
            />
          </div>

          <Button onClick={generate} isLoading={running} disabled={!sourceId || !question.trim() || true} className="w-full" title="Phase 2 — Sắp ra mắt">
            <Sparkles className="w-4 h-4 mr-2" />
            Phân tích 2H
          </Button>
        </div>

        {/* Two columns: How + How Much */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
                <Wrench className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              </div>
              <h3 className="font-serif text-base text-[var(--text-primary)]">How · Cơ chế</h3>
            </div>
            {result?.how ? (
              <>
                <p className="text-sm text-[var(--text-primary)] leading-relaxed mb-3">{result.how.mechanism}</p>
                <ol className="space-y-1.5 text-sm text-[var(--text-primary)] list-decimal list-inside">
                  {result.how.steps.map((s, i) => <li key={i}>{s}</li>)}
                </ol>
              </>
            ) : (
              <p className="text-xs text-[var(--text-secondary)] italic">Auto-fill sẽ giải thích cơ chế + chuỗi bước.</p>
            )}
          </div>

          <div className="bg-[var(--primary-gold)]/4 rounded-lg-custom border border-[var(--primary-gold)]/30 p-5 shadow-soft-sm">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center">
                <Calculator className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              </div>
              <h3 className="font-serif text-base text-[var(--text-primary)]">How much · Định lượng</h3>
            </div>
            {result?.how_much ? (
              <>
                <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{result.how_much.metric}</p>
                <p className="font-serif text-2xl text-[var(--text-primary)] mt-1">
                  {result.how_much.value_vnd != null
                    ? formatVND(result.how_much.value_vnd)
                    : result.how_much.value_pct != null
                      ? `${result.how_much.value_pct >= 0 ? '+' : ''}${result.how_much.value_pct.toFixed(1)}%`
                      : '—'}
                </p>
                {result.how_much.baseline && (
                  <p className="text-xs text-[var(--text-secondary)] mt-1">So với {result.how_much.baseline}</p>
                )}
                <Badge variant="default" className="mt-2">Confidence {(result.how_much.confidence * 100).toFixed(0)}%</Badge>
              </>
            ) : (
              <p className="text-xs text-[var(--text-secondary)] italic">Auto-fill sẽ trả số bằng VND hoặc %.</p>
            )}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Hash className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>How much luôn rendered VND theo K-9 (NUMERIC 14,4) — không bao giờ "1M" / "$X" trong UI.</p>
        </div>
      </div>
    </>
  );
}
