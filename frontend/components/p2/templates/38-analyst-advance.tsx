// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 38. /p2/analysis/advanced — Advanced Analysis (F-033 PR B wired)
// ----------------------------------------------------------------------------
// Cohort + AI bên ngoài (consent K-4) + MANAGER approval gate.
//
// Flow:
//   1. User picks workspace(s) — PR B only ships single-workspace today
//      (Phase 1 user model is one user per enterprise; multi-workspace
//      memberships ship in PR D).
//   2. Toggles consent_external (K-4) — required for the advanced tier
//      to dispatch externally; the BE refuses without it.
//   3. Submits → POST /api/v1/analysis/runs tier='advanced'.
//      * If tenant_settings.consent_external_ai = true (workspace already
//        opted in at the tenant level) → status='queued', dispatcher
//        kicks off straight away → result page polls until done.
//      * Else → status='awaiting_approval', dispatcher short-circuits
//        until a MANAGER hits POST /api/v1/analysis/runs/{id}/approve.
//
// Result page handles both shapes via its own polling loop.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, FlaskConical, Globe, Sparkles, ArrowRight, ShieldCheck,
  AlertTriangle, Lock, CheckCircle2, Activity, Users, Calendar, X,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Checkbox, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface Workspace { id: string; name: string; can_include: boolean; member_role: string; }
interface Quota     { external_calls_used: number; external_calls_limit: number; period: string; }
interface Source    { id: string; label: string; layer: 'silver' | 'gold'; row_count?: number; }

type Framework = 'swot' | '6w' | '2h' | 'fishbone';
type CreateResp = { run_id: string; tier: string; status: 'queued' | 'awaiting_approval' };

const FRAMEWORKS: Array<{ code: Framework; label: string }> = [
  { code: 'swot',     label: 'SWOT' },
  { code: '6w',       label: '6W' },
  { code: '2h',       label: '2H' },
  { code: 'fishbone', label: 'Fishbone' },
];

export default function AnalystAdvancedPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [includes,   setIncludes]   = useState<Set<string>>(new Set());
  const [quota,      setQuota]      = useState<Quota | null>(null);
  const [sources,    setSources]    = useState<Source[]>([]);
  const [picked,     setPicked]     = useState<Source[]>([]);
  const [framework,  setFramework]  = useState<Framework>('swot');
  const [consent,    setConsent]    = useState(true);
  const [question,   setQuestion]   = useState('');
  const [problem,    setProblem]    = useState<ProblemDetails | null>(null);
  const [dispatching, setDispatching] = useState(false);

  useEffect(() => {
    Promise.all([
      api<{ items: Workspace[] }>('/api/v1/analysis/cross-workspaces'),
      api<Quota>('/api/v1/analysis/quota/external-ai'),
      api<{ items: Source[] }>('/api/v1/analysis/sources?layer=silver,gold'),
    ])
      .then(([w, q, s]) => {
        setWorkspaces(w.items);
        setQuota(q);
        setSources(s.items);
        // Auto-include the calling workspace so users only have to
        // expand the cohort, not pick the obvious starting point.
        const callable = w.items.filter((x) => x.can_include).map((x) => x.id);
        setIncludes(new Set(callable));
      })
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

  async function handleDispatch() {
    setProblem(null);
    setDispatching(true);
    try {
      const res = await api<CreateResp>('/api/v1/analysis/runs', {
        method: 'POST',
        body: JSON.stringify({
          tier:             'advanced',
          framework,
          question:         question.trim(),
          source_ids:       picked.map((p) => ({ layer: p.layer, id: p.id, label: p.label })),
          consent_external: consent,
          workspace_ids:    Array.from(includes),
        }),
      });
      window.location.href = `/p2/analysis/runs/${res.run_id}`;
    } catch (err: any) {
      setProblem(err);
      setDispatching(false);
    }
  }

  function toggle(id: string) {
    setIncludes((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }

  const quotaPct = quota ? Math.round((quota.external_calls_used / Math.max(1, quota.external_calls_limit)) * 100) : 0;
  const canDispatch = consent
    && picked.length >= 2
    && picked.length <= 5
    && question.trim().length > 0
    && includes.size > 0
    && !dispatching;

  return (
    <>
      <PageHeader
        title="Phân tích nâng cao"
        description="Cohort cross-workspace · AI bên ngoài · cần MANAGER duyệt nếu workspace ở chế độ strict."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-033</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/analysis')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Hub
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {/* Tier strip + quota */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
                <FlaskConical className="w-5 h-5 text-[var(--primary-gold-dark)]" />
              </div>
              <div>
                <h3 className="font-serif text-base text-[var(--text-primary)]">Nâng cao</h3>
                <p className="text-xs text-[var(--text-secondary)]">Cross-workspace · AI bên ngoài</p>
              </div>
            </div>
            {quota && (
              <div className="flex items-center gap-2">
                <Badge variant={quotaPct >= 80 ? 'warning' : 'default'}>
                  AI ngoài: {quota.external_calls_used} / {quota.external_calls_limit}
                </Badge>
                {consent && <Badge variant="warning"><Globe className="w-3 h-3 mr-1 inline" />Sẽ trừ quota</Badge>}
              </div>
            )}
          </div>
        </div>

        {/* Workspace cohort picker */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h4 className="font-serif text-sm text-[var(--text-primary)]">Workspace tham gia cohort</h4>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">Bạn chỉ thấy workspace có vai trò ≥ ANALYST. RLS được giữ nguyên ở mọi query.</p>
          </div>
          <div className="p-3 space-y-1.5 max-h-[280px] overflow-y-auto">
            {workspaces.length === 0 ? (
              <p className="text-sm text-[var(--text-secondary)] text-center py-6">— Bạn chỉ thuộc 1 workspace —</p>
            ) : workspaces.map((w) => (
              <div
                key={w.id}
                className={cn(
                  'flex items-center justify-between gap-3 p-2.5 rounded-md-custom border',
                  includes.has(w.id)
                    ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                    : 'border-[var(--border-color)] bg-[var(--bg-card)]',
                  !w.can_include && 'opacity-60',
                )}
              >
                <Checkbox
                  checked={includes.has(w.id)}
                  disabled={!w.can_include}
                  onChange={() => toggle(w.id)}
                  label={
                    <span className="inline-flex items-center gap-2">
                      <Users className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                      <span className="text-[var(--text-primary)]">{w.name}</span>
                    </span>
                  }
                />
                <Badge variant={w.member_role === 'MANAGER' ? 'success' : 'default'}>{w.member_role}</Badge>
              </div>
            ))}
          </div>
        </div>

        {/* Sources picker (2-5) */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60 flex items-center justify-between">
            <div>
              <h4 className="font-serif text-sm text-[var(--text-primary)]">Nguồn dữ liệu (2-5)</h4>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">Silver / Gold trong workspace cohort. Đã chọn: {picked.length}/5</p>
            </div>
            {picked.length > 0 && (
              <Button size="sm" variant="tertiary" onClick={() => setPicked([])}>Xoá hết</Button>
            )}
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 divide-x divide-[var(--border-color)]/40">
            <div className="p-3 space-y-1.5 max-h-[260px] overflow-y-auto">
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Có sẵn</p>
              {sources.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)] text-center py-6">— Chưa có nguồn —</p>
              ) : sources.map((s) => {
                const isPicked = !!picked.find((p) => p.id === s.id);
                return (
                  <button
                    key={`${s.layer}-${s.id}`}
                    type="button"
                    onClick={() => isPicked ? unpick(s.id) : pick(s)}
                    disabled={!isPicked && picked.length >= 5}
                    className={cn(
                      'w-full text-left p-2 rounded-md-custom border transition-all text-sm',
                      isPicked
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 disabled:opacity-50',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[var(--text-primary)] truncate">{s.label}</span>
                      <Badge variant={s.layer === 'gold' ? 'current' : 'default'}>{s.layer.toUpperCase()}</Badge>
                    </div>
                  </button>
                );
              })}
            </div>
            <div className="p-3 space-y-1.5 min-h-[120px]">
              <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Đã chọn</p>
              {picked.length === 0 ? (
                <p className="text-sm text-[var(--text-secondary)] text-center py-6">Chọn ít nhất 2 nguồn</p>
              ) : picked.map((s) => (
                <div key={`${s.layer}-${s.id}`} className="flex items-center justify-between p-2 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40 text-sm">
                  <div className="flex items-center gap-2 min-w-0">
                    <CheckCircle2 className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0" />
                    <span className="text-[var(--text-primary)] truncate">{s.label}</span>
                  </div>
                  <button onClick={() => unpick(s.id)} className="text-[var(--text-secondary)] hover:text-[var(--state-error)]">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Privacy + question */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-4">
          <div className={cn(
            'p-3 rounded-md-custom border-2 transition-colors',
            consent
              ? 'border-[var(--state-warning)]/60 bg-[var(--state-warning)]/5'
              : 'border-[var(--state-success)]/40 bg-[var(--state-success)]/5',
          )}>
            <Checkbox
              checked={consent}
              onChange={() => setConsent(!consent)}
              label={
                <span className="inline-flex items-center gap-2">
                  {consent ? <Globe className="w-4 h-4 text-[var(--state-warning)]" /> : <Lock className="w-4 h-4 text-[var(--state-success)]" />}
                  <span className="text-[var(--text-primary)]">
                    {consent ? 'Đồng ý gọi AI bên ngoài (Claude / GPT-4o) sau khi PII-mask (K-5)' : 'Chỉ dùng Qwen 2.5 nội bộ'}
                  </span>
                </span>
              }
            />
            {consent && (
              <p className="text-xs text-[#9E814D] mt-2 ml-6">
                Sẽ trừ vào quota external AI tháng. PII (email/SĐT/ID) được mask trước khi gửi.
              </p>
            )}
          </div>

          <div>
            <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Khung phân tích</label>
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
            <label className="text-sm font-medium text-[var(--text-primary)]">Câu hỏi cohort</label>
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={3}
              placeholder="Ví dụ: So sánh churn rate Q1/Q2 giữa các workspace bán lẻ thuộc cohort SMB."
              className="mt-1 w-full px-3 py-2 text-sm bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>

          <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--state-info)]/10 border border-[var(--state-info)]/30 text-xs text-[#52647D]">
            <ShieldCheck className="w-4 h-4 shrink-0 mt-0.5" />
            <p>
              Nếu workspace của bạn <span className="font-medium">chưa bật</span> external AI ở Settings, run sẽ vào trạng thái <span className="font-mono">awaiting_approval</span> và chờ MANAGER duyệt qua endpoint <span className="font-mono">/runs/{'{id}'}/approve</span>. Workspaces đã bật sẽ dispatch ngay.
            </p>
          </div>

          <Button onClick={handleDispatch} disabled={!canDispatch} isLoading={dispatching} className="w-full">
            <Sparkles className="w-4 h-4 mr-2" />
            Dispatch
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>

        {/* Footer */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mọi cohort run đi qua <span className="font-mono">llm_router.py</span> (K-3) → <span className="font-mono">llm-gateway:8095</span>. Audit log K-6 ghi
            đầy đủ workspace_ids + provider + prompt_hash.
          </p>
        </div>
      </div>
    </>
  );
}
