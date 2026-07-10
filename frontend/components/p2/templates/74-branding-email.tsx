// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 74. /p2/branding/email — Email Template Editor (Phase 2 🔵)
// ----------------------------------------------------------------------------
// Phase 1 đã có (PR B / Sprint 7 PR #85):
//   - notification-service wired vào AuthService (password reset)
//   - notification-service wired vào EnterpriseUserService.invite (F-015 invite)
//   - Templates HTML hardcoded ở `notification-service/templates/`
//
// Phase 2 (file 74) mở UI editor cho 5 template chính:
//   - invite                    (lời mời thành viên)
//   - password_reset            (đặt lại mật khẩu)
//   - quota_warning             (đạt 80% — F-037 finalise)
//   - quota_critical            (đạt 95% — F-037 finalise)
//   - decision_summary_weekly   (báo cáo quyết định tuần — Phase 2)
//
// Per-template:
//   - Subject line (Vietnamese, max 100 chars)
//   - Body MD/HTML editor with placeholder variables ({{recipient_name}},
//     {{workspace_name}}, {{magic_link}}, ...)
//   - Test send → /api/v2/enterprise/branding/email/test
// ============================================================================

import React, { useState } from 'react';
import {
  ChevronLeft, Mail, Send, Eye, ShieldCheck, Sparkles, Lock,
  CheckCircle2, AlertTriangle, FileText, Calendar,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type TemplateKey =
  | 'invite'
  | 'password_reset'
  | 'quota_warning'
  | 'quota_critical'
  | 'decision_summary_weekly';

interface Template {
  key:           TemplateKey;
  labelKey:      string;
  descriptionKey: string;
  phase:         1 | 2;
  variables:     string[];
  subjectKey:    string;
  bodyKey:       string;
}

const TEMPLATES: Template[] = [
  {
    key:            'invite',
    labelKey:       'templates74BrandingEmail.tmplInviteLabel',
    descriptionKey: 'templates74BrandingEmail.tmplInviteDescription',
    phase:          1,
    variables:      ['{{recipient_name}}', '{{workspace_name}}', '{{inviter_name}}', '{{role}}', '{{magic_link}}'],
    subjectKey:     'templates74BrandingEmail.tmplInviteSubject',
    bodyKey:        'templates74BrandingEmail.tmplInviteBody',
  },
  {
    key:            'password_reset',
    labelKey:       'templates74BrandingEmail.tmplPasswordResetLabel',
    descriptionKey: 'templates74BrandingEmail.tmplPasswordResetDescription',
    phase:          1,
    variables:      ['{{recipient_name}}', '{{magic_link}}', '{{expires_in_minutes}}'],
    subjectKey:     'templates74BrandingEmail.tmplPasswordResetSubject',
    bodyKey:        'templates74BrandingEmail.tmplPasswordResetBody',
  },
  {
    key:            'quota_warning',
    labelKey:       'templates74BrandingEmail.tmplQuotaWarningLabel',
    descriptionKey: 'templates74BrandingEmail.tmplQuotaWarningDescription',
    phase:          2,
    variables:      ['{{workspace_name}}', '{{used}}', '{{limit}}', '{{cycle_end}}', '{{upgrade_link}}'],
    subjectKey:     'templates74BrandingEmail.tmplQuotaWarningSubject',
    bodyKey:        'templates74BrandingEmail.tmplQuotaWarningBody',
  },
  {
    key:            'quota_critical',
    labelKey:       'templates74BrandingEmail.tmplQuotaCriticalLabel',
    descriptionKey: 'templates74BrandingEmail.tmplQuotaCriticalDescription',
    phase:          2,
    variables:      ['{{workspace_name}}', '{{used}}', '{{limit}}', '{{cycle_end}}', '{{upgrade_link}}'],
    subjectKey:     'templates74BrandingEmail.tmplQuotaCriticalSubject',
    bodyKey:        'templates74BrandingEmail.tmplQuotaCriticalBody',
  },
  {
    key:            'decision_summary_weekly',
    labelKey:       'templates74BrandingEmail.tmplDecisionSummaryLabel',
    descriptionKey: 'templates74BrandingEmail.tmplDecisionSummaryDescription',
    phase:          2,
    variables:      ['{{workspace_name}}', '{{decision_count}}', '{{actioned_count}}', '{{revenue_at_risk_vnd}}', '{{dashboard_link}}'],
    subjectKey:     'templates74BrandingEmail.tmplDecisionSummarySubject',
    bodyKey:        'templates74BrandingEmail.tmplDecisionSummaryBody',
  },
];

export default function BrandingEmailPage() {
  const t = useT();
  const [selected, setSelected] = useState<TemplateKey>('invite');
  const [drafts,   setDrafts]   = useState<Record<TemplateKey, { subject: string; body_md: string }>>(() => {
    const initial: any = {};
    TEMPLATES.forEach((tp) => { initial[tp.key] = { subject: t(tp.subjectKey), body_md: t(tp.bodyKey) }; });
    return initial;
  });
  const [sending,  setSending]  = useState(false);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);

  const tmpl  = TEMPLATES.find((tp) => tp.key === selected)!;
  const draft = drafts[selected];

  function update(patch: Partial<{ subject: string; body_md: string }>) {
    setDrafts({ ...drafts, [selected]: { ...draft, ...patch } });
  }

  async function testSend() {
    setSending(true);
    setProblem(null);
    try {
      await api('/api/v2/enterprise/branding/email/test', {
        method: 'POST',
        body:   JSON.stringify({ template: selected, subject: draft.subject, body_md: draft.body_md }),
      });
      setSuccess(t('templates74BrandingEmail.testSendSuccess'));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates74BrandingEmail.title')}
        description={t('templates74BrandingEmail.pageDescription')}
        actions={
          <>
            <Badge variant="info">{t('templates74BrandingEmail.phaseBadge')}</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/branding')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              {t('templates74BrandingEmail.backToBranding')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
          {/* Template list */}
          <div className="lg:col-span-1 bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--border-color)]/60">
              <h3 className="font-serif text-sm text-[var(--text-primary)]">{t('templates74BrandingEmail.templateListTitle')}</h3>
            </div>
            <div className="p-2 space-y-1">
              {TEMPLATES.map((tp) => {
                const active = tp.key === selected;
                return (
                  <button
                    key={tp.key}
                    type="button"
                    onClick={() => setSelected(tp.key)}
                    className={cn(
                      'w-full text-left p-2.5 rounded-md-custom transition-colors',
                      active
                        ? 'bg-[var(--primary-gold)]/10 border border-[var(--primary-gold)]/30'
                        : 'border border-transparent hover:bg-[var(--bg-app)]',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className={cn('text-sm font-medium', active ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]')}>{t(tp.labelKey)}</p>
                      <Badge variant={tp.phase === 1 ? 'success' : 'info'}>P{tp.phase}</Badge>
                    </div>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-snug">{t(tp.descriptionKey)}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Editor */}
          <div className="lg:col-span-2 bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden flex flex-col">
            <div className="px-5 py-3 border-b border-[var(--border-color)]/60 flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Mail className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                <h3 className="font-serif text-base text-[var(--text-primary)]">{t(tmpl.labelKey)}</h3>
                {tmpl.phase === 1 && <Badge variant="success">{t('templates74BrandingEmail.phase1WiredBadge')}</Badge>}
              </div>
              <Button size="sm" onClick={testSend} isLoading={sending} disabled={tmpl.phase === 2} title={tmpl.phase === 2 ? t('templates74BrandingEmail.comingSoonTooltip') : ''}>
                <Send className="w-3.5 h-3.5 mr-1.5" />
                {t('templates74BrandingEmail.sendTestButton')}
              </Button>
            </div>
            <div className="p-5 space-y-3 flex-1">
              <div>
                <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates74BrandingEmail.subjectLabel')}</label>
                <Input
                  value={draft.subject}
                  onChange={(e) => update({ subject: e.target.value })}
                  maxLength={100}
                  helperText={t('templates74BrandingEmail.subjectCharCount', { count: draft.subject.length })}
                  disabled={tmpl.phase === 2}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates74BrandingEmail.bodyLabel')}</label>
                <textarea
                  value={draft.body_md}
                  onChange={(e) => update({ body_md: e.target.value })}
                  rows={14}
                  disabled={tmpl.phase === 2}
                  className="mt-1 w-full px-3 py-2 font-mono text-xs bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-60 disabled:cursor-not-allowed"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1">
                  {t('templates74BrandingEmail.markdownHint')}
                </p>
              </div>
            </div>
          </div>

          {/* Variables + preview */}
          <div className="lg:col-span-1 space-y-4">
            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-[var(--border-color)]/60">
                <h3 className="font-serif text-sm text-[var(--text-primary)] inline-flex items-center gap-2">
                  <FileText className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                  {t('templates74BrandingEmail.variablesTitle')}
                </h3>
              </div>
              <div className="p-3 space-y-1.5">
                {tmpl.variables.map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => navigator.clipboard.writeText(v)}
                    className="w-full text-left px-2 py-1.5 rounded-sm-custom font-mono text-[11px] text-[var(--primary-gold-dark)] bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 hover:bg-[var(--primary-gold)]/15"
                    title={t('templates74BrandingEmail.copyTooltip')}
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-[var(--border-color)]/60 flex items-center gap-2">
                <Eye className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                <h3 className="font-serif text-sm text-[var(--text-primary)]">{t('templates74BrandingEmail.previewTitle')}</h3>
              </div>
              <div className="p-4 text-xs">
                <p className="font-medium text-[var(--text-primary)]">{t('templates74BrandingEmail.subjectLabel')}: {draft.subject || t('templates74BrandingEmail.emptyPlaceholder')}</p>
                <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60 whitespace-pre-line text-[var(--text-primary)] leading-relaxed">
                  {draft.body_md || t('templates74BrandingEmail.emptyBodyPlaceholder')}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Phase 1 status */}
        <div className="bg-[var(--state-success)]/8 border border-[var(--state-success)]/30 rounded-md-custom p-3 flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0 mt-0.5" />
          <p className="text-xs text-[#5C856A]">
            <span className="font-medium">{t('templates74BrandingEmail.phase1WireLabel')}</span> {t('templates74BrandingEmail.phase1WireTemplate')} <span className="font-mono">invite</span> + <span className="font-mono">password_reset</span> {t('templates74BrandingEmail.phase1WireUsing')}
            <span className="font-mono"> notification-service/templates/</span> {t('templates74BrandingEmail.phase1WireSuffix')}
          </p>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates74BrandingEmail.senderNamePrefix')} <a href="/p2/branding" className="text-[var(--primary-gold-dark)] underline">/p2/branding</a>{t('templates74BrandingEmail.senderNameSuffix')}
          </p>
        </div>
      </div>
    </>
  );
}
