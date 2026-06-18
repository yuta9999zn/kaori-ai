// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 44. /p2/frameworks/fishbone — Fishbone / Ishikawa (F-034 🔵 Phase 2)
// ----------------------------------------------------------------------------
// 6M categories: Manpower / Method / Machine / Material / Measurement / Mother Nature.
// Hiển thị visual cá xương (placeholder canvas).
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, Fish, Sparkles, ShieldCheck, Lock, Globe,
  Database, Users, GitMerge, Cpu, Box, Activity, Cloud,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface Source { id: string; label: string; }
interface FishboneResult {
  effect:    string;
  causes: {
    manpower:      string[];
    method:        string[];
    machine:       string[];
    material:      string[];
    measurement:   string[];
    mother_nature: string[];
  };
}

const CATEGORIES = [
  { key: 'manpower',      label: 'Manpower · Con người',     icon: Users },
  { key: 'method',        label: 'Method · Quy trình',        icon: GitMerge },
  { key: 'machine',       label: 'Machine · Hệ thống',        icon: Cpu },
  { key: 'material',      label: 'Material · Vật liệu/dữ liệu', icon: Box },
  { key: 'measurement',   label: 'Measurement · Đo lường',    icon: Activity },
  { key: 'mother_nature', label: 'Mother Nature · Môi trường',  icon: Cloud },
] as const;

export default function FishbonePage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [sourceId, setSourceId] = useState('');
  const [effect, setEffect] = useState('');
  const [consentExternal, setConsentExternal] = useState(false);
  const [result, setResult] = useState<FishboneResult | null>(null);
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
      const r = await api<FishboneResult>('/api/v2/enterprise/frameworks/generate', {
        method: 'POST',
        body:   JSON.stringify({ framework: 'Fishbone', source_id: sourceId, effect: effect.trim(), consent_external: consentExternal }),
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
        title="Fishbone · Ishikawa"
        description="Truy nguyên gốc rễ theo 6M (Manpower / Method / Machine / Material / Measurement / Mother Nature)."
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
              <label className="text-sm font-medium text-[var(--text-primary)]">Vấn đề / hiệu ứng cần truy nguyên</label>
              <input type="text" value={effect} onChange={(e) => setEffect(e.target.value)} placeholder="Ví dụ: Tỉ lệ hoàn đơn tăng 35% trong tháng 4" className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30" />
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

          <Button onClick={generate} isLoading={running} disabled={!sourceId || !effect.trim() || true} className="w-full" title="Phase 2 — Sắp ra mắt">
            <Sparkles className="w-4 h-4 mr-2" />
            Phân tích Fishbone
          </Button>
        </div>

        {/* Visual placeholder + categories */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60 flex items-center justify-between gap-3 flex-wrap">
            <h3 className="font-serif text-base text-[var(--text-primary)]">
              {result?.effect ? `Hiệu ứng: ${result.effect}` : 'Sơ đồ Ishikawa'}
            </h3>
            <Badge variant="default">6M</Badge>
          </div>

          <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {CATEGORIES.map((c) => {
              const items = result?.causes[c.key as keyof FishboneResult['causes']] ?? [];
              const Icon = c.icon;
              return (
                <div key={c.key} className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                    <h4 className="font-serif text-sm text-[var(--text-primary)]">{c.label}</h4>
                  </div>
                  {items.length === 0 ? (
                    <p className="text-xs text-[var(--text-secondary)] italic">Auto-fill sẽ điền nguyên nhân thuộc nhóm này.</p>
                  ) : (
                    <ul className="space-y-1 text-sm text-[var(--text-primary)] list-disc list-inside">
                      {items.map((it, i) => <li key={i} className="leading-snug">{it}</li>)}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>6 nhóm 6M = 6 LLM call qua <span className="font-mono">llm_router.py</span> (K-3). Phase 2 sẽ render visual cá xương SVG đầy đủ.</p>
        </div>
      </div>
    </>
  );
}
