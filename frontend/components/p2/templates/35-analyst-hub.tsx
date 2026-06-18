// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 35. /p2/analysis — Multi-tier Analysis Hub (F-033 PR A wired — basic + intermediate)
// ----------------------------------------------------------------------------
// 3 tiers + scope selector + recent-runs section sourced from
// GET /api/v1/analysis/runs.
//
//   - Basic         (single pipeline, N templates, Qwen narrative)
//   - Intermediate  (2-5 silver/gold sources, 1 framework, Qwen)
//   - Advanced      (PR B — cross-workspace cohort, K-4 external AI,
//                    MANAGER approval queue when privacy=strict)
//
// PR A's hub turns the basic + intermediate tile buttons live; advanced
// stays linkable but with a "PR B" badge so users know what's gated.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  FlaskConical, Sparkles, Layers, Network, Globe, Lock,
  ArrowRight, ShieldCheck, CheckCircle2, AlertTriangle, Activity, Clock,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, cn, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Tier  = 'basic' | 'intermediate' | 'advanced';
type Scope = 'single' | 'multi' | 'cross';

interface TierDef {
  code:        Tier;
  title:       string;
  tagline:     string;
  duration:    string;
  consent_external_default: boolean;
  bullets:     string[];
  href:        string;
}

const TIERS: TierDef[] = [
  {
    code:    'basic',
    title:   'Cơ bản',
    tagline: '1 câu hỏi · 1 pipeline · 1 template',
    duration: '< 1 phút',
    consent_external_default: false,
    href:    '/p2/analysis/basic',
    bullets: [
      'Chạy đúng 1 template phân tích trên 1 pipeline đã có',
      'Kết quả: narrative + chart + 3 khuyến nghị',
      'Qwen 2.5 nội bộ — 0₫ chi phí AI bên ngoài',
    ],
  },
  {
    code:    'intermediate',
    title:   'Trung cấp',
    tagline: 'Khung phân tích + nhiều bảng cùng workspace',
    duration: '1 — 3 phút',
    consent_external_default: false,
    href:    '/p2/analysis/intermediate',
    bullets: [
      'JOIN nhiều bảng Silver/Gold trong cùng workspace',
      'Áp dụng 1 framework (SWOT / 6W / 2H / Fishbone)',
      'Trả về 5-10 ChartBlock + audit log K-6',
    ],
  },
  {
    code:    'advanced',
    title:   'Nâng cao',
    tagline: 'Cross-cohort + AI bên ngoài (consent)',
    duration: '3 — 8 phút',
    consent_external_default: true,
    href:    '/p2/analysis/advanced',
    bullets: [
      'Cohort cross-workspace (chỉ workspace bạn có quyền)',
      'Gọi Claude Sonnet / GPT-4o sau khi PII-mask (K-5)',
      'Trừ vào quota external AI tháng — yêu cầu MANAGER duyệt',
    ],
  },
];

const SCOPES: Array<{ code: Scope; title: string; description: string; icon: any }> = [
  { code: 'single', title: 'Single pipeline',  description: 'Hỏi trên 1 pipeline đã chạy', icon: Layers },
  { code: 'multi',  title: 'Multi pipeline',   description: 'Tổng hợp 2-5 pipeline cùng workspace', icon: Network },
  { code: 'cross',  title: 'Cross workspace',  description: 'Bao trùm các workspace bạn có quyền', icon: Globe },
];

interface RecentRun {
  id:               string;
  tier:             Tier;
  scope:            Scope;
  framework:        string | null;
  question:         string | null;
  status:           'queued' | 'running' | 'done' | 'error';
  narrative:        string | null;
  created_at:       string;
}

export default function AnalystHubPage() {
  const [scope, setScope] = useState<Scope>('single');
  const [recent, setRecent] = useState<RecentRun[]>([]);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    api<{ items: RecentRun[] }>('/api/v1/analysis/runs?limit=10')
      .then((r) => setRecent(r.items))
      .catch((err) => setProblem(err));
  }, []);

  return (
    <>
      <PageHeader
        title="Phân tích"
        description="3 tier × 3 scope. Chọn tier theo độ phức tạp câu hỏi, scope theo phạm vi dữ liệu."
        actions={<Badge variant="info">F-033</Badge>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />

        {/* Scope picker */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-3">Phạm vi dữ liệu</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {SCOPES.map((s) => {
              const isActive = s.code === scope;
              const Icon = s.icon;
              return (
                <button
                  key={s.code}
                  type="button"
                  onClick={() => setScope(s.code)}
                  className={cn(
                    'text-left p-3 rounded-md-custom border transition-all',
                    isActive
                      ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
                      : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                    {isActive && <CheckCircle2 className="w-4 h-4 text-[var(--primary-gold-dark)]" />}
                  </div>
                  <p className="font-medium text-sm text-[var(--text-primary)] mt-2">{s.title}</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug">{s.description}</p>
                </button>
              );
            })}
          </div>
          {scope === 'cross' && (
            <div className="mt-3 flex items-start gap-2 p-3 rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 text-xs text-[#9E814D]">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <p>
                Cross-workspace tôn trọng RLS — bạn chỉ thấy workspace mà bạn có vai trò ≥ ANALYST. Kaori sẽ list rõ workspace nào được include trước khi chạy.
              </p>
            </div>
          )}
        </div>

        {/* Tier cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {TIERS.map((t) => <TierCard key={t.code} tier={t} scope={scope} />)}
        </div>

        {/* Recent runs */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-[var(--border-color)]/60 flex items-center justify-between">
            <h3 className="font-serif text-base text-[var(--text-primary)]">Lần chạy gần đây</h3>
            <Badge variant="default">{recent.length}</Badge>
          </div>
          {recent.length === 0 ? (
            <p className="px-5 py-8 text-sm text-[var(--text-secondary)] text-center">
              Chưa có lần phân tích nào — chọn tier ở trên để bắt đầu.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--border-color)]/50">
              {recent.map((r) => (
                <li key={r.id}>
                  <a
                    href={`/p2/analysis/runs/${r.id}`}
                    className="flex items-start gap-3 px-5 py-3 hover:bg-[var(--bg-app)]/40 transition-colors"
                  >
                    <RecentStatusIcon status={r.status} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-baseline gap-2 flex-wrap">
                        <Badge variant={r.tier === 'advanced' ? 'warning' : r.tier === 'intermediate' ? 'info' : 'default'}>
                          {r.tier}
                        </Badge>
                        {r.framework && <Badge variant="current">{r.framework.toUpperCase()}</Badge>}
                        <p className="text-sm font-medium text-[var(--text-primary)] truncate">
                          {r.question || '(không có câu hỏi)'}
                        </p>
                      </div>
                      {r.narrative && (
                        <p className="text-xs text-[var(--text-secondary)] mt-1 line-clamp-2">{r.narrative}</p>
                      )}
                    </div>
                    <span className="text-[11px] text-[var(--text-secondary)] shrink-0 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatRelative(r.created_at)}
                    </span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer note */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mọi tier đi qua <span className="font-mono">llm_router.py</span> (K-3). Tier <span className="font-medium text-[var(--text-primary)]">Nâng cao</span> mặc
            định bật <span className="font-mono">consent_external=true</span> — cần MANAGER duyệt trong workspace có chế độ <span className="font-mono">privacy=strict</span>.
          </p>
        </div>
      </div>
    </>
  );
}

function TierCard({ tier: t, scope }: { tier: TierDef; scope: Scope }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm flex flex-col overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60 bg-[var(--bg-app)]/30">
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="font-serif text-base text-[var(--text-primary)]">{t.title}</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t.tagline}</p>
          </div>
          <Badge variant={t.consent_external_default ? 'warning' : 'success'}>
            {t.consent_external_default
              ? <><Globe className="w-3 h-3 mr-1 inline" /> Có thể gọi AI ngoài</>
              : <><Lock className="w-3 h-3 mr-1 inline" /> Qwen nội bộ</>}
          </Badge>
        </div>
      </div>
      <div className="p-5 flex-1">
        <ul className="space-y-2 text-sm">
          {t.bullets.map((b, i) => (
            <li key={i} className="flex items-start gap-2">
              <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0 mt-0.5" />
              <span className="text-[var(--text-primary)]">{b}</span>
            </li>
          ))}
        </ul>
        <p className="text-[11px] text-[var(--text-secondary)] mt-4">
          Thời gian chạy ước tính: <span className="font-medium text-[var(--text-primary)]">{t.duration}</span>
        </p>
      </div>
      <div className="px-5 py-3 border-t border-[var(--border-color)]/60 bg-[var(--bg-app)]/30">
        <Button
          onClick={() => (window.location.href = `${t.href}?scope=${scope}`)}
          className="w-full"
          variant="primary"
        >
          Mở tier {t.title}
          <ArrowRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

function RecentStatusIcon({ status }: { status: RecentRun['status'] }) {
  const cfg = ({
    queued:  { className: 'text-[var(--text-secondary)]',         label: 'Q' },
    running: { className: 'text-[var(--state-warning)] animate-pulse', label: 'R' },
    done:    { className: 'text-[var(--state-success)]',          label: '✓' },
    error:   { className: 'text-[var(--state-error)]',            label: '!' },
  } as const)[status];
  return (
    <span className={cn('w-5 h-5 rounded-full border flex items-center justify-center text-[10px] shrink-0 mt-0.5', cfg.className)}>
      {status === 'running' ? <Activity className="w-3 h-3" /> : cfg.label}
    </span>
  );
}

function formatRelative(iso: string): string {
  const diff = Date.now() - +new Date(iso);
  if (Number.isNaN(diff))    return iso;
  if (diff < 60_000)         return 'vừa xong';
  if (diff < 3_600_000)      return `${Math.round(diff / 60_000)} phút`;
  if (diff < 86_400_000)     return `${Math.round(diff / 3_600_000)} giờ`;
  if (diff < 7 * 86_400_000) return `${Math.round(diff / 86_400_000)} ngày`;
  return new Date(iso).toLocaleDateString('vi-VN');
}
