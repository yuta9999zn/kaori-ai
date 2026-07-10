// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 13. /p2/users/:id — User detail + role + activity log (F-015)
// ----------------------------------------------------------------------------
// GET    /api/v1/enterprises/users/:id
// PATCH  /api/v1/enterprises/users/:id   { role | status | profile fields }
// GET    /api/v1/enterprises/users/:id/activity
// POST   /api/v1/enterprises/users/:id/reset-password   (MANAGER only)
//
// PII fields (phone/id_number/dob/address) are workspace-internal — they
// live in `enterprise_users.profile_json`, not in Silver, so K-5 redaction
// doesn't apply; visibility is RBAC-gated (only MANAGER + the user themselves).
// ============================================================================

import React, { useState, useEffect } from 'react';
import { usePathname } from 'next/navigation';
import {
  ArrowLeft, User, Lock, Activity as ActivityIcon, ShieldCheck,
  Edit2, Save, Ban, Trash2, KeyRound,
} from 'lucide-react';

import {
  Button, Input, Label, Badge, ErrorBanner,
  api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
type Role   = 'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER';
type Status = 'active' | 'invited' | 'suspended';

interface UserDetail {
  id:    string;
  name:  string;
  email: string;
  role:  Role;
  status: Status;
  phone?:     string;
  dob?:       string;
  address?:   string;
  created_at: string;
  last_active_at?: string;
}

interface AuditEvent {
  id:     string;
  action: string;
  module: string;
  ip_masked: string;
  at:     string;
}

const ROLE_BADGE: Record<Role, any> = {
  MANAGER: 'current', OPERATOR: 'info', ANALYST: 'success', VIEWER: 'default',
};

export default function UserDetail() {
  const t = useT();
  // usePathname() works in SSR + client; reading `window.location.pathname`
  // at component body crashes Next prerender with "window is not defined".
  const pathname = usePathname() ?? '';
  const userId   = pathname.match(/\/users\/([^\/?]+)/)?.[1] ?? '';
  const [user,    setUser]    = useState<UserDetail | null>(null);
  const [audit,   setAudit]   = useState<AuditEvent[]>([]);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [loading, setLoading] = useState(true);

  const [editing, setEditing] = useState(false);
  const [draft,   setDraft]   = useState<Partial<UserDetail>>({});
  const [isSaving,    setIsSaving]    = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetSent,   setResetSent]   = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const [u, a] = await Promise.all([
        api<UserDetail>(`/api/v1/enterprises/users/${userId}`),
        api<{ data: AuditEvent[] }>(`/api/v1/enterprises/users/${userId}/activity?limit=20`),
      ]);
      setUser(u);
      setAudit(a.data ?? []);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { if (userId) load(); }, [userId]);

  function startEdit() {
    if (!user) return;
    setDraft({ name: user.name, role: user.role, phone: user.phone, address: user.address });
    setEditing(true);
  }

  async function saveEdit() {
    if (!user) return;
    setIsSaving(true);
    setProblem(null);
    try {
      const updated = await api<UserDetail>(`/api/v1/enterprises/users/${user.id}`, {
        method: 'PATCH',
        body: JSON.stringify(draft),
      });
      setUser(updated);
      setEditing(false);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setIsSaving(false);
    }
  }

  async function sendReset() {
    if (!user) return;
    setIsResetting(true);
    setProblem(null);
    try {
      await api(`/api/v1/enterprises/users/${user.id}/reset-password`, { method: 'POST' });
      setResetSent(true);
      setTimeout(() => setResetSent(false), 4000);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setIsResetting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={user?.name ?? t('templates13UserIdDetail.loading')}
        description={user?.email}
        actions={
          <>
            <Button variant="secondary" onClick={() => (window.location.href = '/p2/users')}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              {t('templates13UserIdDetail.back')}
            </Button>
            {!editing && user && (
              <Button onClick={startEdit}>
                <Edit2 className="w-4 h-4 mr-2" />
                {t('templates13UserIdDetail.edit')}
              </Button>
            )}
            {editing && (
              <>
                <Button variant="secondary" onClick={() => setEditing(false)} disabled={isSaving}>{t('templates13UserIdDetail.cancel')}</Button>
                <Button onClick={saveEdit} isLoading={isSaving}>
                  <Save className="w-4 h-4 mr-2" />
                  {t('templates13UserIdDetail.save')}
                </Button>
              </>
            )}
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />
        {resetSent && (
          <div className="rounded-md-custom bg-[var(--state-success)]/10 border border-[var(--state-success)]/30 p-3 text-sm text-[#5C856A]">
            {t('templates13UserIdDetail.resetSentMsg', { email: user?.email ?? '' })}
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            <div className="h-32 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
            <div className="h-64 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
          </div>
        ) : user && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-6">
              {/* Identity */}
              <Section title={t('templates13UserIdDetail.sectionAccountInfo')} icon={User}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {editing ? (
                    <Input label={t('templates13UserIdDetail.fieldName')} value={draft.name ?? ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
                  ) : (
                    <Field label={t('templates13UserIdDetail.fieldName')} value={user.name} />
                  )}
                  <Field label={t('templates13UserIdDetail.fieldEmail')} value={user.email} mono />

                  {editing ? (
                    <div className="space-y-2">
                      <Label>{t('templates13UserIdDetail.fieldRole')}</Label>
                      <select
                        value={draft.role}
                        onChange={(e) => setDraft({ ...draft, role: e.target.value as Role })}
                        className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/40 focus:border-[var(--primary-gold)]"
                      >
                        {(['MANAGER','OPERATOR','ANALYST','VIEWER'] as Role[]).map((r) => <option key={r}>{r}</option>)}
                      </select>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <Label>{t('templates13UserIdDetail.fieldRole')}</Label>
                      <div><Badge variant={ROLE_BADGE[user.role]}>{user.role}</Badge></div>
                    </div>
                  )}
                  <Field label={t('templates13UserIdDetail.fieldStatus')} value={
                    <Badge variant={user.status === 'active' ? 'success' : user.status === 'invited' ? 'warning' : 'error'}>
                      {user.status === 'active' ? t('templates13UserIdDetail.statusActive') : user.status === 'invited' ? t('templates13UserIdDetail.statusInvited') : t('templates13UserIdDetail.statusLocked')}
                    </Badge>
                  } />
                </div>
              </Section>

              {/* Contact */}
              <Section title={t('templates13UserIdDetail.sectionContact')} icon={ShieldCheck}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {editing ? (
                    <>
                      <Input label={t('templates13UserIdDetail.fieldPhone')} value={draft.phone ?? ''} onChange={(e) => setDraft({ ...draft, phone: e.target.value })} />
                      <Input label={t('templates13UserIdDetail.fieldAddress')}     value={draft.address ?? ''} onChange={(e) => setDraft({ ...draft, address: e.target.value })} />
                    </>
                  ) : (
                    <>
                      <Field label={t('templates13UserIdDetail.fieldPhone')} value={user.phone || '—'} />
                      <Field label={t('templates13UserIdDetail.fieldAddress')}    value={user.address || '—'} />
                    </>
                  )}
                  <Field label={t('templates13UserIdDetail.fieldJoined')} value={user.created_at} />
                  <Field label={t('templates13UserIdDetail.fieldLastActive')} value={user.last_active_at || '—'} />
                </div>
              </Section>

              {/* Activity */}
              <Section title={t('templates13UserIdDetail.sectionActivity')} icon={ActivityIcon}>
                {audit.length === 0 ? (
                  <p className="text-sm text-[var(--text-secondary)] text-center py-6">{t('templates13UserIdDetail.noActivity')}</p>
                ) : (
                  <div className="space-y-2">
                    {audit.map((e) => (
                      <div key={e.id} className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)]/40">
                        <div className="w-2 h-2 rounded-full bg-[var(--primary-gold)] mt-2 shrink-0" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-[var(--text-primary)]">{e.action}</p>
                          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                            {t('templates13UserIdDetail.activityMeta', { module: e.module, at: e.at, ip: e.ip_masked })}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Section>
            </div>

            {/* Sidebar actions */}
            <div className="lg:col-span-1 space-y-4">
              <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
                <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates13UserIdDetail.security')}</h3>
                <Button variant="secondary" onClick={sendReset} isLoading={isResetting} className="w-full">
                  <KeyRound className="w-4 h-4 mr-2" />
                  {t('templates13UserIdDetail.sendResetLink')}
                </Button>
                <p className="text-xs text-[var(--text-secondary)]">
                  {t('templates13UserIdDetail.resetHint')}
                </p>
              </div>

              <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
                <h3 className="font-serif text-base text-[var(--state-error)]">{t('templates13UserIdDetail.dangerZone')}</h3>
                <Button variant="secondary" onClick={() => { /* TODO: trigger suspend like list page */ }} className="w-full">
                  <Ban className="w-4 h-4 mr-2" />
                  {t('templates13UserIdDetail.lockAccount')}
                </Button>
                <Button variant="destructive" onClick={() => { /* TODO: trigger delete confirm */ }} className="w-full">
                  <Trash2 className="w-4 h-4 mr-2" />
                  {t('templates13UserIdDetail.deleteFromWorkspace')}
                </Button>
                <p className="text-xs text-[var(--text-secondary)]">
                  {t('templates13UserIdDetail.deleteHint')}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function Section({ title, icon: Icon, children }: any) {
  return (
    <div className="rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-6 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-4">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-base text-[var(--text-primary)]">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: any; mono?: boolean }) {
  return (
    <div className="space-y-1">
      <p className="text-xs uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <div className={cn('text-sm text-[var(--text-primary)]', mono && 'font-mono')}>{value}</div>
    </div>
  );
}
