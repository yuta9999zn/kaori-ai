// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 42. /p2/frameworks/6w — 6W (F-034 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Who · What · When · Where · Why · How — 6 question prompt grid.
// Auto-fill từng câu qua LLM router (K-3).
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, HelpCircle, Sparkles, ShieldCheck, Lock, Globe,
  Database, Users, Target, Calendar, MapPin, Lightbulb, Wrench,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface Source { id: string; label: string; }
interface SixWResult {
  who:   { text: string; confidence: number };
  what:  { text: string; confidence: number };
  when:  { text: string; confidence: number };
  where: { text: string; confidence: number };
  why:   { text: string; confidence: number };
  how:   { text: string; confidence: number };
}

const QUESTIONS = [
  { key: 'who',   label: 'Who · Ai',         icon: Users,      hint: 'Đối tượng/khách hàng/nhân viên liên quan' },
  { key: 'what',  label: 'What · Cái gì',    icon: Target,     hint: 'Sự kiện/hành vi/metric đang quan sát' },
  { key: 'when',  label: 'When · Khi nào',   icon: Calendar,   hint: 'Cửa sổ thời gian + xu hướng' },
  { key: 'where', label: 'Where · Ở đâu',    icon: MapPin,     hint: 'Khu vực/kênh/segment xảy ra' },
  { key: 'why',   label: 'Why · Vì sao',     icon: Lightbulb,  hint: 'Giả thuyết nguyên nhân' },
  { key: 'how',   label: 'How · Như thế nào', icon: Wrench,    hint: 'Cơ chế/quy trình/chuỗi sự kiện' },
] as const;

export default function SixWPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [question, setQuestion] = useState('');
  const [consentExternal, setConsentExternal] = useState(false);
  const [result, setResult] = useState<SixWResult | null>(null);
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
      const r = await api<SixWResult>('/api/v2/enterprise/frameworks/generate', {
        method: 'POST',
        body:   JSON.stringify({ framework: '6W', source_id: sourceId, question: question.trim(), consent_external: consentExternal }),
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
        title="6W"
        description="Who · What · When · Where · Why · How — 6 câu hỏi cấu trúc."
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

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Nguồn dữ liệu</label>
              <div className="relative mt-1">
                <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
                <select value={sourceId} onChange={(e) => setSourceId(e.target.value)} className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30">
                  {sources.length === 0 && <option value="">— Chưa có Gold feature —</option>}
                  {sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-[var(--text-primary)]">Câu hỏi gốc (K-10)</label>
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ví dụ: Vì sao churn tháng 4 tăng 2x?"
                className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              />
            </div>
          </div>

          <div className={cn('p-3 rounded-md-custom border-2', consentExternal ? 'border-[var(--state-warning)]/50 bg-[var(--state-warning)]/5' : 'border-[var(--state-success)]/40 bg-[var(--state-success)]/5')}>
            <Checkbox
              checked={consentExternal}
              onChange={() => setConsentExternal(!consentExternal)}
              label={
                <span className="inline-flex items-center gap-2">
                  {consentExternal ? <Globe className="w-4 h-4 text-[var(--state-warning)]" /> : <Lock className="w-4 h-4 text-[var(--state-success)]" />}
                  {consentExternal ? 'AI bên ngoài (PII đã mask, K-5)' : 'Qwen 2.5 nội bộ (mặc định)'}
                </span>
              }
            />
          </div>

          <Button onClick={generate} isLoading={running} disabled={!sourceId || !question.trim() || true} className="w-full" title="Phase 2 — Sắp ra mắt">
            <Sparkles className="w-4 h-4 mr-2" />
            Auto-fill 6W
          </Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {QUESTIONS.map((q) => {
            const r = result?.[q.key];
            const Icon = q.icon;
            return (
              <div key={q.key} className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-8 h-8 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
                    <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  </div>
                  <h3 className="font-serif text-sm text-[var(--text-primary)]">{q.label}</h3>
                </div>
                {r ? (
                  <>
                    <p className="text-sm text-[var(--text-primary)] leading-relaxed">{r.text}</p>
                    <p className="text-[10px] text-[var(--text-secondary)] mt-2">Confidence: {(r.confidence * 100).toFixed(0)}%</p>
                  </>
                ) : (
                  <p className="text-xs text-[var(--text-secondary)] italic">{q.hint}</p>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>6 câu = 6 LLM call riêng qua <span className="font-mono">llm_router.py</span>. Audit log K-6 ghi từng call.</p>
        </div>
      </div>
    </>
  );
}
