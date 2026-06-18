// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 39. /p2/analysis/scope — Analysis Scope Management (F-033 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Manage how analysis runs scope across pipelines + workspaces:
//   - Default scope per template (single / multi / cross)
//   - Per-tier guard (Basic locked to single, Advanced unlocks cross)
//   - MANAGER toggle: require approval for cross-workspace runs
//
// Phase 2 only. Phase 1: every run is implicitly single-pipeline.
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, Layers, Network, Globe, Lock, ShieldCheck, Save,
  Settings2, AlertTriangle,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, Checkbox, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Scope = 'single' | 'multi' | 'cross';
type Tier  = 'basic' | 'intermediate' | 'advanced';

interface ScopePolicy {
  default_scope_per_tier: Record<Tier, Scope>;
  require_manager_for_cross: boolean;
  allow_external_ai_in_cross: boolean;
}

const SCOPE_LABEL: Record<Scope, string> = {
  single: 'Single pipeline',
  multi:  'Multi pipeline',
  cross:  'Cross workspace',
};

const TIER_LABEL: Record<Tier, string> = {
  basic:        'Cơ bản',
  intermediate: 'Trung cấp',
  advanced:     'Nâng cao',
};

const SCOPE_ICON: Record<Scope, any> = {
  single: Layers,
  multi:  Network,
  cross:  Globe,
};

export default function AnalystScopePage() {
  const [policy,  setPolicy]  = useState<ScopePolicy | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data = await api<ScopePolicy>('/api/v2/enterprise/analysis/scope-policy');
      setPolicy(data);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  async function save() {
    if (!policy) return;
    setSaving(true);
    setProblem(null);
    try {
      await api('/api/v2/enterprise/analysis/scope-policy', {
        method: 'PATCH',
        body:   JSON.stringify(policy),
      });
      setSuccess('Đã lưu policy phạm vi phân tích');
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSaving(false);
    }
  }

  function setTierScope(tier: Tier, scope: Scope) {
    if (!policy) return;
    setPolicy({ ...policy, default_scope_per_tier: { ...policy.default_scope_per_tier, [tier]: scope } });
  }

  return (
    <>
      <PageHeader
        title="Phạm vi phân tích"
        description="Mặc định scope per-tier + guard cross-workspace. Chỉ MANAGER cập nhật được."
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

      <div className="px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {loading && !policy ? (
          <div className="h-96 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
        ) : policy ? (
          <>
            {/* Default scope per tier */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
              <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
                <h3 className="font-serif text-base text-[var(--text-primary)] inline-flex items-center gap-2">
                  <Settings2 className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  Mặc định scope theo tier
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-1">
                  Khi user vào /p2/analysis/{'{tier}'}, scope sẽ tự khởi tạo theo cấu hình này.
                </p>
              </div>

              <div className="divide-y divide-[var(--border-color)]/60">
                {(Object.keys(TIER_LABEL) as Tier[]).map((t) => (
                  <div key={t} className="px-5 py-4 flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <p className="font-medium text-sm text-[var(--text-primary)]">{TIER_LABEL[t]}</p>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                        Hiện tại: <span className="font-medium text-[var(--text-primary)]">{SCOPE_LABEL[policy.default_scope_per_tier[t]]}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {(Object.keys(SCOPE_LABEL) as Scope[]).map((s) => {
                        const Icon = SCOPE_ICON[s];
                        const isActive = policy.default_scope_per_tier[t] === s;
                        const disabled = (t === 'basic' && s !== 'single');
                        return (
                          <button
                            key={s}
                            type="button"
                            disabled={disabled}
                            onClick={() => setTierScope(t, s)}
                            className={cn(
                              'inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-sm-custom border transition-colors',
                              isActive
                                ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                                : 'border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                              disabled && 'opacity-40 cursor-not-allowed',
                            )}
                            title={disabled ? 'Tier Basic chỉ chạy single-pipeline' : SCOPE_LABEL[s]}
                          >
                            <Icon className="w-3.5 h-3.5" />
                            {SCOPE_LABEL[s]}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Guards */}
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
              <h3 className="font-serif text-base text-[var(--text-primary)]">Guard rails</h3>

              <div className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40">
                <Checkbox
                  checked={policy.require_manager_for_cross}
                  onChange={() => setPolicy({ ...policy, require_manager_for_cross: !policy.require_manager_for_cross })}
                  label={
                    <span>
                      <span className="font-medium text-[var(--text-primary)]">Yêu cầu MANAGER duyệt</span> mọi cross-workspace run
                    </span>
                  }
                />
                <p className="text-xs text-[var(--text-secondary)] mt-1.5 ml-6">Khuyến nghị BẬT — chống chia sẻ dữ liệu trái phép giữa workspace.</p>
              </div>

              <div className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40">
                <Checkbox
                  checked={policy.allow_external_ai_in_cross}
                  onChange={() => setPolicy({ ...policy, allow_external_ai_in_cross: !policy.allow_external_ai_in_cross })}
                  label={
                    <span>
                      <span className="font-medium text-[var(--text-primary)]">Cho phép AI bên ngoài</span> trong cross-workspace run (sau PII mask)
                    </span>
                  }
                />
                <p className="text-xs text-[var(--text-secondary)] mt-1.5 ml-6">Tắt để khoá Qwen nội bộ duy nhất — phù hợp khi có workspace ở chế độ strict.</p>
              </div>
            </div>

            {/* K-3/K-4 footer */}
            <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
              <p>
                <span className="font-medium text-[var(--text-primary)]">Tier Basic</span> luôn locked = single-pipeline (không thay đổi được).
                <span className="font-medium text-[var(--text-primary)]"> Tier Nâng cao</span> mặc định include cross-workspace nhưng tôn trọng RLS.
              </p>
            </div>

            <div className="flex justify-end">
              <Button onClick={save} isLoading={saving}>
                <Save className="w-4 h-4 mr-2" />
                Lưu policy
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
