// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 12. /p2/users/invite — Invite enterprise user (F-015)
// ----------------------------------------------------------------------------
// POST /api/v1/enterprises/users
//   { email, role, welcome_message? }
// Backend creates pending invite + emails activation link → handled by
// file 2 (/p2/auth/activate/:token, flow=user_invite).
//
// Bulk invite supported (one email per line).
// Min-MANAGER guard not relevant here (creating, not removing).
// Idempotency-Key auto-attached by api() helper.
// ============================================================================

import React, { useState, useRef, useEffect } from 'react';
import { ArrowLeft, Mail, Send, CheckCircle2, X, Plus, Info } from 'lucide-react';

import {
  Button, Input, Label, ErrorBanner,
  api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type Role = 'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER';

const ROLES: Array<{ id: Role; title: string; descKey: string }> = [
  { id: 'MANAGER',  title: 'MANAGER',  descKey: 'templates12UserInvite.roleManagerDesc' },
  { id: 'OPERATOR', title: 'OPERATOR', descKey: 'templates12UserInvite.roleOperatorDesc' },
  { id: 'ANALYST',  title: 'ANALYST',  descKey: 'templates12UserInvite.roleAnalystDesc' },
  { id: 'VIEWER',   title: 'VIEWER',   descKey: 'templates12UserInvite.roleViewerDesc' },
];

interface InviteResult {
  email:  string;
  status: 'sent' | 'failed' | 'duplicate';
  message?: string;
}

export default function UserInvite() {
  const t = useT();
  const [emailsRaw, setEmailsRaw] = useState('');
  const [role,      setRole]      = useState<Role>('OPERATOR');
  const [message,   setMessage]   = useState('');
  const [problem,   setProblem]   = useState<ProblemDetails | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [results,   setResults]   = useState<InviteResult[] | null>(null);
  const emailsRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { emailsRef.current?.focus(); }, []);

  function parseEmails(): string[] {
    return emailsRaw
      .split(/[\n,;]+/)
      .map((e) => e.trim())
      .filter((e) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setProblem(null);

    const emails = parseEmails();
    if (emails.length === 0) {
      setProblem({ title: t('templates12UserInvite.errNoValidEmail') });
      emailsRef.current?.focus();
      return;
    }

    setIsSending(true);
    const out: InviteResult[] = [];
    try {
      for (const email of emails) {
        try {
          await api('/api/v1/enterprises/users', {
            method: 'POST',
            body: JSON.stringify({ email, role, welcome_message: message || undefined }),
          });
          out.push({ email, status: 'sent' });
        } catch (err: any) {
          out.push({
            email,
            status: err?.status === 409 ? 'duplicate' : 'failed',
            message: err?.title ?? err?.detail,
          });
        }
      }
      setResults(out);
      const sent = out.filter((r) => r.status === 'sent').length;
      if (sent === emails.length) {
        // Reset form on full success
        setEmailsRaw('');
        setMessage('');
      }
    } finally {
      setIsSending(false);
    }
  }

  const parsed = parseEmails();

  return (
    <>
      <PageHeader
        title={t('templates12UserInvite.pageTitle')}
        description={t('templates12UserInvite.pageDesc')}
        actions={
          <Button variant="secondary" onClick={() => (window.location.href = '/p2/users')}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('templates12UserInvite.listBtn')}
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-8 max-w-[760px] mx-auto">
        <ErrorBanner problem={problem} />

        {results && (
          <div className="mb-6 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
            <h3 className="font-serif text-base text-[var(--text-primary)] flex items-center gap-2">
              {t('templates12UserInvite.resultsTitle')}
              <button onClick={() => setResults(null)} className="ml-auto text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <X className="w-4 h-4" />
              </button>
            </h3>
            {results.map((r) => (
              <div key={r.email} className="flex items-center justify-between p-3 rounded-md-custom bg-[var(--bg-app)]/50">
                <span className="text-sm text-[var(--text-primary)]">{r.email}</span>
                {r.status === 'sent'      && <span className="text-xs text-[#5C856A] flex items-center gap-1.5"><CheckCircle2 className="w-3.5 h-3.5" /> {t('templates12UserInvite.statusSent')}</span>}
                {r.status === 'duplicate' && <span className="text-xs text-[#9E814D]">{t('templates12UserInvite.statusDuplicate')}</span>}
                {r.status === 'failed'    && <span className="text-xs text-[#9B5050]">{r.message ?? t('templates12UserInvite.statusFailed')}</span>}
              </div>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-6 shadow-soft-sm space-y-6">
          <div>
            <Label>{t('templates12UserInvite.emailLabel')}</Label>
            <textarea
              ref={emailsRef}
              value={emailsRaw}
              onChange={(e) => setEmailsRaw(e.target.value)}
              placeholder={'nguyen.an@congty.vn\ntran.binh@congty.vn'}
              rows={4}
              className="mt-2 w-full rounded-md-custom border border-[var(--border-color)] bg-white px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/40 focus:border-[var(--primary-gold)]"
              disabled={isSending}
            />
            <p className="text-xs text-[var(--text-secondary)] mt-2">
              {t('templates12UserInvite.emailHint')}
              {parsed.length > 0 && (
                <> {t('templates12UserInvite.receivedPrefix')} <span className="font-medium text-[var(--text-primary)]">{parsed.length}</span> {t('templates12UserInvite.receivedSuffix')}</>
              )}
            </p>
          </div>

          <div>
            <Label>{t('templates12UserInvite.roleLabel')}</Label>
            <div className="mt-2 space-y-2">
              {ROLES.map((r) => (
                <button
                  type="button"
                  key={r.id}
                  onClick={() => setRole(r.id)}
                  className={cn(
                    'w-full flex items-start gap-3 p-3 border rounded-md-custom text-left transition-all',
                    role === r.id
                      ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8 ring-1 ring-[var(--primary-gold)]'
                      : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]/30 hover:bg-[var(--bg-app)]/40',
                  )}
                >
                  <div className={cn(
                    'w-5 h-5 rounded-full border flex items-center justify-center mt-0.5 shrink-0',
                    role === r.id ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]' : 'border-[var(--border-color)]',
                  )}>
                    {role === r.id && <span className="w-2 h-2 rounded-full bg-white" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-[var(--text-primary)]">{r.title}</p>
                    <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t(r.descKey)}</p>
                  </div>
                </button>
              ))}
            </div>
            {role === 'MANAGER' && (
              <div className="mt-3 flex items-start gap-2 p-3 rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 text-xs text-[#9E814D]">
                <Info className="w-4 h-4 shrink-0 mt-0.5 text-[var(--state-warning)]" />
                <p>
                  {t('templates12UserInvite.managerWarning')}
                </p>
              </div>
            )}
          </div>

          <div>
            <Label>{t('templates12UserInvite.messageLabel')}</Label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={t('templates12UserInvite.messagePlaceholder')}
              rows={3}
              maxLength={500}
              className="mt-2 w-full rounded-md-custom border border-[var(--border-color)] bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/40 focus:border-[var(--primary-gold)]"
              disabled={isSending}
            />
            <p className="text-xs text-[var(--text-secondary)] mt-1">{t('templates12UserInvite.msgCharCount', { count: message.length })}</p>
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--border-color)]/60">
            <Button
              type="button"
              variant="secondary"
              onClick={() => (window.location.href = '/p2/users')}
              disabled={isSending}
            >
              {t('templates12UserInvite.cancelBtn')}
            </Button>
            <Button type="submit" isLoading={isSending} disabled={parsed.length === 0}>
              <Send className="w-4 h-4 mr-2" />
              {parsed.length > 0
                ? t('templates12UserInvite.sendWithCount', { count: parsed.length })
                : t('templates12UserInvite.sendInvite')}
            </Button>
          </div>
        </form>
      </div>
    </>
  );
}
