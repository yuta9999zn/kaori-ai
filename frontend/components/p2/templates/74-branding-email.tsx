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
type TemplateKey =
  | 'invite'
  | 'password_reset'
  | 'quota_warning'
  | 'quota_critical'
  | 'decision_summary_weekly';

interface Template {
  key:        TemplateKey;
  label:      string;
  description: string;
  phase:      1 | 2;
  variables:  string[];
  subject:    string;
  body_md:    string;
}

const TEMPLATES: Template[] = [
  {
    key:         'invite',
    label:       'Mời thành viên',
    description: 'Gửi khi MANAGER invite member mới qua RBAC page (F-015).',
    phase:       1,
    variables:   ['{{recipient_name}}', '{{workspace_name}}', '{{inviter_name}}', '{{role}}', '{{magic_link}}'],
    subject:     '{{inviter_name}} mời bạn vào workspace {{workspace_name}}',
    body_md:     'Chào {{recipient_name}},\n\n{{inviter_name}} vừa mời bạn vào workspace **{{workspace_name}}** với vai trò **{{role}}**.\n\nClick để xác nhận: {{magic_link}}',
  },
  {
    key:         'password_reset',
    label:       'Đặt lại mật khẩu',
    description: 'Gửi khi user yêu cầu reset password ở /p2/auth/forgot.',
    phase:       1,
    variables:   ['{{recipient_name}}', '{{magic_link}}', '{{expires_in_minutes}}'],
    subject:     'Đặt lại mật khẩu Kaori',
    body_md:     'Chào {{recipient_name}},\n\nClick để đặt lại mật khẩu (link hết hạn sau {{expires_in_minutes}} phút):\n\n{{magic_link}}',
  },
  {
    key:         'quota_warning',
    label:       'Cảnh báo 80% hạn mức',
    description: 'Gửi khi enterprise dùng 80% quota khách hàng tháng (F-037).',
    phase:       2,
    variables:   ['{{workspace_name}}', '{{used}}', '{{limit}}', '{{cycle_end}}', '{{upgrade_link}}'],
    subject:     'Workspace {{workspace_name}} đã dùng 80% hạn mức tháng',
    body_md:     'Workspace **{{workspace_name}}** đã xử lý {{used}} / {{limit}} khách hàng tháng này.\n\nChu kỳ kết thúc: {{cycle_end}}.\n\nCân nhắc nâng cấp gói: {{upgrade_link}}',
  },
  {
    key:         'quota_critical',
    label:       'Cảnh báo 95% hạn mức',
    description: 'Gửi khi enterprise sắp chạm hạn mức (F-037).',
    phase:       2,
    variables:   ['{{workspace_name}}', '{{used}}', '{{limit}}', '{{cycle_end}}', '{{upgrade_link}}'],
    subject:     '⚠ Workspace {{workspace_name}} sắp chạm hạn mức',
    body_md:     'Workspace **{{workspace_name}}** đã dùng 95% hạn mức ({{used}} / {{limit}} khách hàng).\n\nNâng cấp ngay để tránh gián đoạn: {{upgrade_link}}',
  },
  {
    key:         'decision_summary_weekly',
    label:       'Tóm tắt quyết định tuần',
    description: 'Báo cáo weekly các quyết định AI đã ra trong tuần.',
    phase:       2,
    variables:   ['{{workspace_name}}', '{{decision_count}}', '{{actioned_count}}', '{{revenue_at_risk_vnd}}', '{{dashboard_link}}'],
    subject:     'Tóm tắt quyết định tuần · {{workspace_name}}',
    body_md:     'Workspace **{{workspace_name}}** tuần này:\n\n- {{decision_count}} quyết định mới\n- {{actioned_count}} đã hành động\n- Doanh thu rủi ro đã xử lý: {{revenue_at_risk_vnd}}\n\nXem dashboard: {{dashboard_link}}',
  },
];

export default function BrandingEmailPage() {
  const [selected, setSelected] = useState<TemplateKey>('invite');
  const [drafts,   setDrafts]   = useState<Record<TemplateKey, { subject: string; body_md: string }>>(() => {
    const initial: any = {};
    TEMPLATES.forEach((t) => { initial[t.key] = { subject: t.subject, body_md: t.body_md }; });
    return initial;
  });
  const [sending,  setSending]  = useState(false);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);

  const tmpl  = TEMPLATES.find((t) => t.key === selected)!;
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
      setSuccess('Đã gửi email test tới địa chỉ của bạn.');
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Mẫu email"
        description="5 template được notification-service dùng. Phase 1 đã wire 2 template; Phase 2 mở editor."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-037 finalise</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/branding')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Branding
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
              <h3 className="font-serif text-sm text-[var(--text-primary)]">5 template</h3>
            </div>
            <div className="p-2 space-y-1">
              {TEMPLATES.map((t) => {
                const active = t.key === selected;
                return (
                  <button
                    key={t.key}
                    type="button"
                    onClick={() => setSelected(t.key)}
                    className={cn(
                      'w-full text-left p-2.5 rounded-md-custom transition-colors',
                      active
                        ? 'bg-[var(--primary-gold)]/10 border border-[var(--primary-gold)]/30'
                        : 'border border-transparent hover:bg-[var(--bg-app)]',
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className={cn('text-sm font-medium', active ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]')}>{t.label}</p>
                      <Badge variant={t.phase === 1 ? 'success' : 'info'}>P{t.phase}</Badge>
                    </div>
                    <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-snug">{t.description}</p>
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
                <h3 className="font-serif text-base text-[var(--text-primary)]">{tmpl.label}</h3>
                {tmpl.phase === 1 && <Badge variant="success">Phase 1 đã wire</Badge>}
              </div>
              <Button size="sm" onClick={testSend} isLoading={sending} disabled={tmpl.phase === 2} title={tmpl.phase === 2 ? 'Phase 2 — Sắp ra mắt' : ''}>
                <Send className="w-3.5 h-3.5 mr-1.5" />
                Gửi test
              </Button>
            </div>
            <div className="p-5 space-y-3 flex-1">
              <div>
                <label className="text-sm font-medium text-[var(--text-primary)]">Subject</label>
                <Input
                  value={draft.subject}
                  onChange={(e) => update({ subject: e.target.value })}
                  maxLength={100}
                  helperText={`${draft.subject.length} / 100 ký tự`}
                  disabled={tmpl.phase === 2}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-[var(--text-primary)]">Body (Markdown)</label>
                <textarea
                  value={draft.body_md}
                  onChange={(e) => update({ body_md: e.target.value })}
                  rows={14}
                  disabled={tmpl.phase === 2}
                  className="mt-1 w-full px-3 py-2 font-mono text-xs bg-white border border-[var(--border-color)] rounded-md-custom focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-60 disabled:cursor-not-allowed"
                />
                <p className="text-[11px] text-[var(--text-secondary)] mt-1">
                  Markdown sẽ render thành HTML email + plain-text fallback.
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
                  Biến khả dụng
                </h3>
              </div>
              <div className="p-3 space-y-1.5">
                {tmpl.variables.map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => navigator.clipboard.writeText(v)}
                    className="w-full text-left px-2 py-1.5 rounded-sm-custom font-mono text-[11px] text-[var(--primary-gold-dark)] bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 hover:bg-[var(--primary-gold)]/15"
                    title="Copy"
                  >
                    {v}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-[var(--border-color)]/60 flex items-center gap-2">
                <Eye className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                <h3 className="font-serif text-sm text-[var(--text-primary)]">Preview</h3>
              </div>
              <div className="p-4 text-xs">
                <p className="font-medium text-[var(--text-primary)]">Subject: {draft.subject || '(trống)'}</p>
                <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60 whitespace-pre-line text-[var(--text-primary)] leading-relaxed">
                  {draft.body_md || '(body trống)'}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Phase 1 status */}
        <div className="bg-[var(--state-success)]/8 border border-[var(--state-success)]/30 rounded-md-custom p-3 flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0 mt-0.5" />
          <p className="text-xs text-[#5C856A]">
            <span className="font-medium">Phase 1 đã wire:</span> template <span className="font-mono">invite</span> + <span className="font-mono">password_reset</span> đang dùng HTML hardcoded ở
            <span className="font-mono"> notification-service/templates/</span> (PR #85). Editor bên trên Phase 2 thay thế — vẫn dùng cùng SMTP sender.
          </p>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Email sender name lấy từ <a href="/p2/branding" className="text-[var(--primary-gold-dark)] underline">/p2/branding</a>.
            Quota templates (warning/critical) sẽ finalise tone copy trong F-037 (Phase 2).
          </p>
        </div>
      </div>
    </>
  );
}
