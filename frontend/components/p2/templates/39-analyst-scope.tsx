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
import { useT } from '@/lib/i18n/provider';
type Scope = 'single' | 'multi' | 'cross';
type Tier  = 'basic' | 'intermediate' | 'advanced';

interface ScopePolicy {
  default_scope_per_tier: Record<Tier, Scope>;
  require_manager_for_cross: boolean;
  allow_external_ai_in_cross: boolean;
}

const SCOPE_ICON: Record<Scope, any> = {
  single: Layers,
  multi:  Network,
  cross:  Globe,
};

// Scope-policy service is Phase-2 (not wired on the pilot). When the endpoint
// isn't available we render these documented per-tier defaults so the page
// shows the config instead of an error banner (Basic=single, Advanced=cross).
const DEFAULT_SCOPE_POLICY: ScopePolicy = {
  default_scope_per_tier: { basic: 'single', intermediate: 'multi', advanced: 'cross' },
  require_manager_for_cross:  true,
  allow_external_ai_in_cross: false,
};

export default function AnalystScopePage() {
  const t = useT();
  const SCOPE_LABEL: Record<Scope, string> = {
    single: t('templates39AnalystScope.scopeSingle'),
    multi:  t('templates39AnalystScope.scopeMulti'),
    cross:  t('templates39AnalystScope.scopeCross'),
  };
  const TIER_LABEL: Record<Tier, string> = {
    basic:        t('templates39AnalystScope.tierBasic'),
    intermediate: t('templates39AnalystScope.tierIntermediate'),
    advanced:     t('templates39AnalystScope.tierAdvanced'),
  };
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
    } catch {
      // Endpoint not wired on the pilot → show documented defaults, not an error.
      setPolicy(DEFAULT_SCOPE_POLICY);
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
      setSuccess(t('templates39AnalystScope.saveSuccess'));
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
        title={t('templates39AnalystScope.pageTitle')}
        description={t('templates39AnalystScope.pageDesc')}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-033</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/analysis')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              {t('templates39AnalystScope.hubBtn')}
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
                  {t('templates39AnalystScope.tierScopeSectionTitle')}
                </h3>
                <p className="text-xs text-[var(--text-secondary)] mt-1">
                  {t('templates39AnalystScope.tierScopeHint', { path: '/p2/analysis/{tier}' })}
                </p>
              </div>

              <div className="divide-y divide-[var(--border-color)]/60">
                {(Object.keys(TIER_LABEL) as Tier[]).map((tier) => (
                  <div key={tier} className="px-5 py-4 flex items-center justify-between gap-3 flex-wrap">
                    <div>
                      <p className="font-medium text-sm text-[var(--text-primary)]">{TIER_LABEL[tier]}</p>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                        {t('templates39AnalystScope.currentLabel')} <span className="font-medium text-[var(--text-primary)]">{SCOPE_LABEL[policy.default_scope_per_tier[tier]]}</span>
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
                      {(Object.keys(SCOPE_LABEL) as Scope[]).map((s) => {
                        const Icon = SCOPE_ICON[s];
                        const isActive = policy.default_scope_per_tier[tier] === s;
                        const disabled = (tier === 'basic' && s !== 'single');
                        return (
                          <button
                            key={s}
                            type="button"
                            disabled={disabled}
                            onClick={() => setTierScope(tier, s)}
                            className={cn(
                              'inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium rounded-sm-custom border transition-colors',
                              isActive
                                ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                                : 'border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                              disabled && 'opacity-40 cursor-not-allowed',
                            )}
                            title={disabled ? t('templates39AnalystScope.basicLockedTitle') : SCOPE_LABEL[s]}
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
              <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates39AnalystScope.guardRailsTitle')}</h3>

              <div className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40">
                <Checkbox
                  checked={policy.require_manager_for_cross}
                  onChange={() => setPolicy({ ...policy, require_manager_for_cross: !policy.require_manager_for_cross })}
                  label={
                    <span>
                      <span className="font-medium text-[var(--text-primary)]">{t('templates39AnalystScope.requireManagerLabel')}</span> {t('templates39AnalystScope.requireManagerSuffix')}
                    </span>
                  }
                />
                <p className="text-xs text-[var(--text-secondary)] mt-1.5 ml-6">{t('templates39AnalystScope.requireManagerHint')}</p>
              </div>

              <div className="p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40">
                <Checkbox
                  checked={policy.allow_external_ai_in_cross}
                  onChange={() => setPolicy({ ...policy, allow_external_ai_in_cross: !policy.allow_external_ai_in_cross })}
                  label={
                    <span>
                      <span className="font-medium text-[var(--text-primary)]">{t('templates39AnalystScope.allowExternalAiLabel')}</span> {t('templates39AnalystScope.allowExternalAiSuffix')}
                    </span>
                  }
                />
                <p className="text-xs text-[var(--text-secondary)] mt-1.5 ml-6">{t('templates39AnalystScope.allowExternalAiHint')}</p>
              </div>
            </div>

            {/* K-3/K-4 footer */}
            <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
              <p>
                <span className="font-medium text-[var(--text-primary)]">{t('templates39AnalystScope.footerTierBasicLabel')}</span> {t('templates39AnalystScope.footerTierBasicText')}
                <span className="font-medium text-[var(--text-primary)]"> {t('templates39AnalystScope.footerTierAdvancedLabel')}</span> {t('templates39AnalystScope.footerTierAdvancedText')}
              </p>
            </div>

            <div className="flex justify-end">
              <Button onClick={save} isLoading={saving}>
                <Save className="w-4 h-4 mr-2" />
                {t('templates39AnalystScope.saveBtn')}
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </>
  );
}
