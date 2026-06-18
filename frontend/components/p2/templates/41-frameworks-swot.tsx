// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 41. /p2/frameworks/swot — SWOT (F-034 🔵 Phase 2)
// ----------------------------------------------------------------------------
// 4 quadrant: Strengths / Weaknesses / Opportunities / Threats.
// Auto-fill mỗi quadrant qua LLM router (K-3) — mặc định Qwen nội bộ (K-4 OFF).
//
// POST /api/v2/enterprise/frameworks/generate
//   body: { framework: 'SWOT', source_id, question, consent_external }
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, Grid3x3, Sparkles, ShieldCheck, Lock, Globe,
  TrendingUp, AlertTriangle, Star, Activity, Database, Loader2,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface Source { id: string; label: string; }
interface Quadrant {
  items: Array<{ text: string; confidence: number }>;
}
interface SwotResult {
  strengths:     Quadrant;
  weaknesses:    Quadrant;
  opportunities: Quadrant;
  threats:       Quadrant;
}

export default function SwotPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [question, setQuestion] = useState('');
  const [consentExternal, setConsentExternal] = useState(false);
  const [result, setResult] = useState<SwotResult | null>(null);
  const [running, setRunning] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    api<{ items: Source[] }>('/api/v1/data/gold/features?limit=20')
      .then((r) => { setSources(r.items); if (r.items[0]) setSourceId(r.items[0].id); })
      .catch((err) => setProblem(err));
  }, []);

  async function generate() {
    if (!sourceId || !question.trim()) return;
    setRunning(true);
    setProblem(null);
    try {
      const r = await api<SwotResult>('/api/v2/enterprise/frameworks/generate', {
        method: 'POST',
        body:   JSON.stringify({ framework: 'SWOT', source_id: sourceId, question: question.trim(), consent_external: consentExternal }),
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
        title="SWOT"
        description="Strengths · Weaknesses · Opportunities · Threats — auto-fill 4 quadrant qua LLM router."
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

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {/* Inputs */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Nguồn dữ liệu</label>
              <div className="relative mt-1">
                <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
                <select
                  value={sourceId}
                  onChange={(e) => setSourceId(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
                >
                  {sources.length === 0 && <option value="">— Chưa có Gold feature —</option>}
                  {sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Câu hỏi (1 câu — K-10)</label>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ví dụ: Đánh giá vị thế cạnh tranh segment SMB Q2"
                className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              />
            </div>
          </div>

          <div className={cn(
            'p-3 rounded-md-custom border-2',
            consentExternal ? 'border-[var(--state-warning)]/50 bg-[var(--state-warning)]/5' : 'border-[var(--state-success)]/40 bg-[var(--state-success)]/5',
          )}>
            <Checkbox
              checked={consentExternal}
              onChange={() => setConsentExternal(!consentExternal)}
              label={
                <span className="inline-flex items-center gap-2">
                  {consentExternal ? <Globe className="w-4 h-4 text-[var(--state-warning)]" /> : <Lock className="w-4 h-4 text-[var(--state-success)]" />}
                  {consentExternal ? 'AI bên ngoài (PII đã mask, K-5)' : 'Qwen 2.5 nội bộ (mặc định, K-4 OFF)'}
                </span>
              }
            />
          </div>

          <Button onClick={generate} isLoading={running} disabled={!sourceId || !question.trim() || true} className="w-full" title="Phase 2 — Sắp ra mắt">
            <Sparkles className="w-4 h-4 mr-2" />
            Auto-fill SWOT
          </Button>
        </div>

        {/* SWOT 4-quadrant grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Quadrant title="Strengths · Điểm mạnh"      icon={Star}           tone="success" items={result?.strengths.items}      empty="Auto-fill sẽ điền tại đây" />
          <Quadrant title="Weaknesses · Điểm yếu"      icon={AlertTriangle}  tone="warning" items={result?.weaknesses.items}     empty="Auto-fill sẽ điền tại đây" />
          <Quadrant title="Opportunities · Cơ hội"      icon={TrendingUp}     tone="info"    items={result?.opportunities.items}  empty="Auto-fill sẽ điền tại đây" />
          <Quadrant title="Threats · Mối đe doạ"        icon={Activity}       tone="error"   items={result?.threats.items}        empty="Auto-fill sẽ điền tại đây" />
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mỗi quadrant là một LLM call riêng qua <span className="font-mono">llm_router.py</span> (K-3). Confidence được hiển thị per-bullet.
            Audit log K-6 ghi đầy đủ prompt_hash + provider + consent_external_at_dispatch.
          </p>
        </div>
      </div>
    </>
  );
}

function Quadrant({
  title, icon: Icon, tone, items, empty,
}: { title: string; icon: any; tone: 'success' | 'warning' | 'info' | 'error'; items?: Array<{ text: string; confidence: number }>; empty: string }) {
  const toneBg: Record<string, string> = {
    success: 'bg-[var(--state-success)]/5 border-[var(--state-success)]/30',
    warning: 'bg-[var(--state-warning)]/5 border-[var(--state-warning)]/30',
    info:    'bg-[var(--state-info)]/5 border-[var(--state-info)]/30',
    error:   'bg-[var(--state-error)]/5 border-[var(--state-error)]/30',
  };
  const toneText: Record<string, string> = {
    success: 'text-[#5C856A]',
    warning: 'text-[#9E814D]',
    info:    'text-[#52647D]',
    error:   'text-[#9B5050]',
  };
  return (
    <div className={cn('rounded-lg-custom border p-4 shadow-soft-sm', toneBg[tone])}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className={cn('w-4 h-4', toneText[tone])} />
        <h3 className={cn('font-serif text-sm', toneText[tone])}>{title}</h3>
      </div>
      {(!items || items.length === 0) ? (
        <p className="text-xs text-[var(--text-secondary)] italic">{empty}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((it, i) => (
            <li key={i} className="text-sm text-[var(--text-primary)]">
              <p className="leading-relaxed">{it.text}</p>
              <p className="text-[10px] text-[var(--text-secondary)] mt-0.5">Confidence: {(it.confidence * 100).toFixed(0)}%</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
