'use client';

import { use, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { UserPlus, Trash2, Mail, ShieldCheck, X } from 'lucide-react';

import {
  workspaceMemberApi,
  type MemberRole,
  type WorkspaceMember,
} from '@/lib/api/platform';
import {
  Badge, Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtDateTime } from '@/lib/format';
import { useT } from '@/lib/i18n/provider';

const ROLE_VARIANT: Record<MemberRole, 'current' | 'info' | 'operational' | 'default'> = {
  MANAGER:  'current',
  OPERATOR: 'info',
  ANALYST:  'operational',
  VIEWER:   'default',
};
const STATUS_VARIANT: Record<string, 'operational' | 'warning' | 'default'> = {
  active:   'operational',
  pending:  'warning',
  inactive: 'default',
};

export default function WorkspaceMembersPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const t      = useT();
  const qc     = useQueryClient();

  const ROLE_LABEL: Record<MemberRole, string> = {
    MANAGER:  t('membersPage.roleManager'),
    OPERATOR: t('membersPage.roleOperator'),
    ANALYST:  t('membersPage.roleAnalyst'),
    VIEWER:   t('membersPage.roleViewer'),
  };
  const STATUS_LABEL: Record<string, string> = {
    active:   t('membersPage.statusActive'),
    pending:  t('membersPage.statusPending'),
    inactive: t('membersPage.statusInactive'),
  };

  const query = useQuery({
    queryKey: ['workspace-members', id],
    queryFn:  () => workspaceMemberApi.list(id),
    retry: false,
  });

  const [inviteOpen,   setInviteOpen]   = useState(false);
  const [removeTarget, setRemoveTarget] = useState<WorkspaceMember | null>(null);
  const [inviteEmail,  setInviteEmail]  = useState('');
  const [inviteRole,   setInviteRole]   = useState<MemberRole>('VIEWER');
  const [inviteError,  setInviteError]  = useState<ProblemDetails | null>(null);

  const inviteMut = useMutation({
    mutationFn: () => workspaceMemberApi.invite(id, { email: inviteEmail, role: inviteRole }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-members', id] });
      setInviteOpen(false);
      setInviteEmail('');
      setInviteRole('VIEWER');
      setInviteError(null);
    },
    onError: (e: unknown) => setInviteError(e as ProblemDetails),
  });

  const removeMut = useMutation({
    mutationFn: (userId: string) => workspaceMemberApi.remove(id, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-members', id] });
      setRemoveTarget(null);
    },
  });

  const members = query.data?.data ?? [];
  const problem = query.error ? (query.error as unknown as ProblemDetails) : null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-[var(--text-secondary)]">
          {members.length > 0
            ? <>{t('membersPage.totalCountPrefix')} <strong className="text-[var(--text-primary)]">{members.length}</strong> {t('membersPage.totalCountSuffix')}</>
            : t('membersPage.manageHint')}
        </p>
        <Button onClick={() => setInviteOpen(true)}>
          <UserPlus className="w-4 h-4 mr-1.5" />
          {t('membersPage.inviteMember')}
        </Button>
      </div>

      {query.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-14 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
            />
          ))}
        </div>
      )}

      {query.isError && (
        <ErrorBanner
          problem={problem}
          message={t('membersPage.backendNotReady', { path: `/workspaces/${id}/members` })}
        />
      )}

      {!query.isLoading && !query.isError && (
        <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] overflow-hidden shadow-soft-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-app)]/60 text-[var(--text-secondary)]">
                <tr>
                  <th className="text-left font-medium px-4 py-2.5">{t('membersPage.colMember')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('membersPage.role')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('membersPage.colStatus')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('membersPage.colLastLogin')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('membersPage.colJoined')}</th>
                  <th className="text-right font-medium px-4 py-2.5 w-16"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {members.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-10 text-center text-[var(--text-secondary)]">
                      {t('membersPage.emptyTable')}
                    </td>
                  </tr>
                )}
                {members.map((m) => (
                  <tr key={m.user_id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] flex items-center justify-center text-sm font-medium shrink-0">
                          {(m.full_name ?? m.email).charAt(0).toUpperCase()}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-[var(--text-primary)] truncate">{m.full_name ?? m.email}</p>
                          <p className="text-xs text-[var(--text-secondary)] truncate">{m.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={ROLE_VARIANT[m.role] ?? 'default'}>{ROLE_LABEL[m.role] ?? m.role}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[m.status] ?? 'default'}>
                        {STATUS_LABEL[m.status] ?? m.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)] tabular-nums">
                      {fmtDateTime(m.last_login_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--text-secondary)] tabular-nums">
                      {fmtDateTime(m.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => setRemoveTarget(m)}
                        className="p-1.5 text-[var(--text-secondary)] hover:text-[#9B5050] hover:bg-[var(--state-error)]/8 rounded-md-custom transition-colors"
                        aria-label={t('membersPage.removeMember')}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {inviteOpen && (
        <Modal onClose={() => setInviteOpen(false)}>
          <header className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('membersPage.inviteMember')}</h3>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                {t('membersPage.inviteSubtitle')}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setInviteOpen(false)}
              className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-md-custom hover:bg-[var(--bg-app)]"
              aria-label={t('membersPage.close')}
            >
              <X className="w-4 h-4" />
            </button>
          </header>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="invite-email">{t('membersPage.emailLabel')}</Label>
              <Input
                id="invite-email"
                type="email"
                placeholder={t('membersPage.emailPlaceholder')}
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="invite-role">{t('membersPage.role')}</Label>
              <select
                id="invite-role"
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as MemberRole)}
                className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              >
                <option value="MANAGER">{ROLE_LABEL.MANAGER}</option>
                <option value="OPERATOR">{ROLE_LABEL.OPERATOR}</option>
                <option value="ANALYST">{ROLE_LABEL.ANALYST}</option>
                <option value="VIEWER">{ROLE_LABEL.VIEWER}</option>
              </select>
            </div>

            <div className="flex items-start gap-2 text-xs text-[var(--text-secondary)] bg-[var(--state-info)]/10 border border-[var(--state-info)]/30 rounded-md-custom px-3 py-2">
              <ShieldCheck className="w-4 h-4 text-[#52647D] shrink-0 mt-0.5" />
              <span>{t('membersPage.managerRequiredNote')}</span>
            </div>

            {inviteError && <ErrorBanner problem={inviteError} />}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setInviteOpen(false)}>{t('membersPage.cancel')}</Button>
              <Button
                isLoading={inviteMut.isPending}
                disabled={!inviteEmail}
                onClick={() => { setInviteError(null); inviteMut.mutate(); }}
              >
                <Mail className="w-4 h-4 mr-1.5" /> {t('membersPage.sendInvite')}
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {removeTarget && (
        <Modal onClose={() => setRemoveTarget(null)} small>
          <header className="mb-3">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('membersPage.removeMember')}</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {t('membersPage.removeConfirmPrefix')} <strong className="text-[var(--text-primary)]">{removeTarget.full_name ?? removeTarget.email}</strong>{t('membersPage.removeConfirmSuffix')}
            </p>
          </header>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setRemoveTarget(null)}>{t('membersPage.cancel')}</Button>
            <Button
              variant="destructive"
              isLoading={removeMut.isPending}
              onClick={() => removeTarget && removeMut.mutate(removeTarget.user_id)}
            >
              <Trash2 className="w-4 h-4 mr-1.5" /> {t('membersPage.removeMember')}
            </Button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Modal({
  children, onClose, small,
}: {
  children: React.ReactNode;
  onClose:  () => void;
  small?:   boolean;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--text-primary)]/40 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      onClick={onClose}
    >
      <div
        className={`w-full ${small ? 'max-w-md' : 'max-w-lg'} rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-lg p-6 animate-slide-up-fade`}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>
  );
}
