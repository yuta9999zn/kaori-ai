// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 69. /p2/authz/custom-roles — Custom Roles (F-007 mở rộng — Phase 2 🔵)
// ----------------------------------------------------------------------------
// 4 vai trò chuẩn (MANAGER/OPERATOR/ANALYST/VIEWER) đáp ứng MVP, nhưng
// một số khách hàng cần role hẹp hơn (ví dụ "Chỉ xem doanh thu chi nhánh A").
// Phase 2 mở khả năng tự định nghĩa role với permission set + tag scope.
//
// Endpoints (Phase 2):
//   GET    /api/v2/enterprise/authz/custom-roles
//   POST   /api/v2/enterprise/authz/custom-roles
//   PATCH  /api/v2/enterprise/authz/custom-roles/{id}
//   DELETE /api/v2/enterprise/authz/custom-roles/{id}
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  Shield, Plus, X, Save, Trash2, Sparkles, ShieldCheck, Lock,
  Eye, FlaskConical, Wrench, Crown, Tag, ChevronLeft,
} from 'lucide-react';

import {
  Button, Badge, Checkbox, ErrorBanner, SuccessBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
interface CustomRole {
  id:           string;
  name:         string;
  description:  string;
  base_role:    'VIEWER' | 'ANALYST' | 'OPERATOR';
  permissions:  string[];
  scope_tags:   string[];
  member_count: number;
}

const PERMISSION_GROUPS: Record<string, Array<{ key: string; labelKey: string }>> = {
  'Pipeline': [
    { key: 'pipeline:read',    labelKey: 'templates69AuthzCustomRole.permPipelineRead' },
    { key: 'pipeline:create',  labelKey: 'templates69AuthzCustomRole.permPipelineCreate' },
    { key: 'pipeline:run',     labelKey: 'templates69AuthzCustomRole.permPipelineRun' },
    { key: 'pipeline:delete',  labelKey: 'templates69AuthzCustomRole.permPipelineDelete' },
  ],
  'Insights & Decisions': [
    { key: 'insight:read',          labelKey: 'templates69AuthzCustomRole.permInsightRead' },
    { key: 'insight:generate',      labelKey: 'templates69AuthzCustomRole.permInsightGenerate' },
    { key: 'decision:read',         labelKey: 'templates69AuthzCustomRole.permDecisionRead' },
    { key: 'decision:action',       labelKey: 'templates69AuthzCustomRole.permDecisionAction' },
  ],
  'Data layers': [
    { key: 'data:bronze:read', labelKey: 'templates69AuthzCustomRole.permDataBronzeRead' },
    { key: 'data:silver:read', labelKey: 'templates69AuthzCustomRole.permDataSilverRead' },
    { key: 'data:gold:read',   labelKey: 'templates69AuthzCustomRole.permDataGoldRead' },
  ],
  'Settings': [
    { key: 'settings:read',  labelKey: 'templates69AuthzCustomRole.permSettingsRead' },
    { key: 'settings:write', labelKey: 'templates69AuthzCustomRole.permSettingsWrite' },
    { key: 'billing:read',   labelKey: 'templates69AuthzCustomRole.permBillingRead' },
  ],
};

const GROUP_LABEL_KEYS: Record<string, string> = {
  'Pipeline': 'templates69AuthzCustomRole.groupPipeline',
  'Insights & Decisions': 'templates69AuthzCustomRole.groupInsightsDecisions',
  'Data layers': 'templates69AuthzCustomRole.groupDataLayers',
  'Settings': 'templates69AuthzCustomRole.groupSettings',
};

export default function CustomRolesPage() {
  const t = useT();
  const [roles,    setRoles]    = useState<CustomRole[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);

  const [showBuilder, setShowBuilder] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const r = await api<{ items: CustomRole[] }>('/api/v2/enterprise/authz/custom-roles');
      setRoles(r.items);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  return (
    <>
      <PageHeader
        title={t('templates69AuthzCustomRole.title')}
        description={t('templates69AuthzCustomRole.description')}
        actions={
          <>
            <Badge variant="info">{t('templates69AuthzCustomRole.badgePhase2')}</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/authz/rbac')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              {t('templates69AuthzCustomRole.btnRbacStandard')}
            </Button>
            <Button onClick={() => setShowBuilder(true)} disabled title={t('templates69AuthzCustomRole.btnCreateRoleTitle')}>
              <Plus className="w-4 h-4 mr-2" />
              {t('templates69AuthzCustomRole.btnCreateRole')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {/* Phase 2 banner */}
        <div className="bg-[var(--primary-gold)]/8 rounded-lg-custom border border-[var(--primary-gold)]/30 p-5 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-1" />
            <div>
              <p className="font-serif text-base text-[var(--text-primary)]">{t('templates69AuthzCustomRole.comingSoonTitle')}</p>
              <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">
                {t('templates69AuthzCustomRole.introText')} <span className="font-mono">branch=HCM</span>).
              </p>
              <Button
                variant="secondary"
                className="mt-3"
                onClick={() => (window.location.href = '/p2/authz/rbac')}
              >
                {t('templates69AuthzCustomRole.btnUseRbacNow')}
              </Button>
            </div>
          </div>
        </div>

        {/* Existing roles list (placeholder) */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates69AuthzCustomRole.existingRolesTitle', { count: roles.length })}</h3>
          </div>
          {loading ? (
            <div className="p-5"><div className="h-24 bg-[var(--bg-app)] rounded-md-custom animate-pulse" /></div>
          ) : roles.length === 0 ? (
            <div className="p-12 text-center text-[var(--text-secondary)]">
              <Shield className="w-10 h-10 mx-auto mb-2 text-[var(--text-secondary)]/40" />
              <p className="text-sm">{t('templates69AuthzCustomRole.emptyState')}</p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border-color)]/60">
              {roles.map((r) => <RoleRow key={r.id} role={r} />)}
            </div>
          )}
        </div>

        {/* Permission catalogue preview */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates69AuthzCustomRole.permCatalogTitle')}</h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t('templates69AuthzCustomRole.permCatalogDesc')}</p>
          </div>
          <div className="p-5 grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(PERMISSION_GROUPS).map(([group, perms]) => (
              <div key={group} className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-3">
                <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">{t(GROUP_LABEL_KEYS[group] ?? group)}</p>
                <ul className="space-y-1">
                  {perms.map((p) => (
                    <li key={p.key} className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
                      <Lock className="w-3 h-3 text-[var(--text-secondary)]/60" />
                      <span className="font-mono text-xs">{p.key}</span>
                      <span className="text-[var(--text-secondary)] text-xs">— {t(p.labelKey)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates69AuthzCustomRole.pdpNoteBefore')} <span className="font-mono">{`{ allow, reason, policy_id, missing_perms[] }`}</span> {t('templates69AuthzCustomRole.pdpNoteAfter')}
          </p>
        </div>
      </div>

      {showBuilder && <RoleBuilderPlaceholder onClose={() => setShowBuilder(false)} />}
    </>
  );
}

function RoleRow({ role: r }: { role: CustomRole }) {
  const t = useT();
  const baseIcon: any = r.base_role === 'OPERATOR' ? Wrench : r.base_role === 'ANALYST' ? FlaskConical : Eye;
  const BaseIcon = baseIcon;
  return (
    <div className="px-5 py-4 flex items-start justify-between gap-3 flex-wrap">
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
          <Shield className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="font-medium text-sm text-[var(--text-primary)]">{r.name}</p>
            <Badge variant="default">
              <BaseIcon className="w-3 h-3 mr-1 inline" />
              {t('templates69AuthzCustomRole.inheritsFrom', { baseRole: r.base_role })}
            </Badge>
            <span className="text-[11px] text-[var(--text-secondary)]">{t('templates69AuthzCustomRole.memberCount', { count: r.member_count })}</span>
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">{r.description}</p>
          {r.scope_tags.length > 0 && (
            <div className="flex items-center gap-1 mt-1.5 flex-wrap">
              {r.scope_tags.map((tag) => (
                <span key={tag} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm-custom text-[10px] font-mono text-[var(--primary-gold-dark)] bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30">
                  <Tag className="w-2.5 h-2.5" />
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
      <Button variant="tertiary" size="sm" disabled title={t('templates69AuthzCustomRole.editBtnTitle')}>{t('templates69AuthzCustomRole.editBtn')}</Button>
    </div>
  );
}

function RoleBuilderPlaceholder({ onClose }: { onClose: () => void }) {
  const t = useT();
  return (
    <div className="fixed inset-0 z-50 bg-[var(--text-primary)]/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-lg w-full max-w-md p-5 animate-slide-up-fade">
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('templates69AuthzCustomRole.builderTitle')}</h3>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-2">{t('templates69AuthzCustomRole.builderDesc')}</p>
        <div className="mt-4 flex justify-end">
          <Button onClick={onClose}>{t('templates69AuthzCustomRole.closeBtn')}</Button>
        </div>
      </div>
    </div>
  );
}
