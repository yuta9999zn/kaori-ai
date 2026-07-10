'use client';

import { use, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  KeyRound, Plus, Trash2, Copy, Check, AlertTriangle, ShieldCheck, X,
} from 'lucide-react';

import {
  workspaceKeyApi, type WorkspaceKey, type KeyStatus,
} from '@/lib/api/platform';
import {
  Badge, Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtDateTime } from '@/lib/format';
import { useT } from '@/lib/i18n/provider';

const STATUS_VARIANT: Record<KeyStatus, 'operational' | 'default'> = {
  active:  'operational',
  revoked: 'default',
};

function maskKey(keyId: string) {
  if (keyId.length <= 8) return keyId;
  return `${keyId.slice(0, 4)}…${keyId.slice(-4)}`;
}

export default function WorkspaceKeysPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const qc     = useQueryClient();
  const t = useT();

  const query = useQuery({
    queryKey: ['workspace-keys', id],
    queryFn:  () => workspaceKeyApi.list(id),
    retry: false,
  });

  const [createOpen,  setCreateOpen]  = useState(false);
  const [createLabel, setCreateLabel] = useState('');
  const [createError, setCreateError] = useState<ProblemDetails | null>(null);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [copied,      setCopied]      = useState(false);
  const [revokeTarget, setRevokeTarget] = useState<WorkspaceKey | null>(null);

  const createMut = useMutation({
    mutationFn: () => workspaceKeyApi.create(id, { label: createLabel.trim() || undefined }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['workspace-keys', id] });
      setRevealedKey(res.data.raw_key);
      setCreateLabel('');
      setCreateError(null);
    },
    onError: (e: unknown) => setCreateError(e as ProblemDetails),
  });

  const revokeMut = useMutation({
    mutationFn: (keyId: string) => workspaceKeyApi.revoke(id, keyId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['workspace-keys', id] });
      setRevokeTarget(null);
    },
  });

  async function handleCopy() {
    if (!revealedKey) return;
    try {
      await navigator.clipboard.writeText(revealedKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Browser may block clipboard outside user gesture — readOnly input still copyable.
    }
  }

  function closeCreateFlow() {
    setCreateOpen(false);
    setRevealedKey(null);
    setCopied(false);
    setCreateLabel('');
    setCreateError(null);
  }

  const keys        = query.data?.data ?? [];
  const activeCount = keys.filter((k) => k.status === 'active').length;
  const problem     = query.error ? (query.error as unknown as ProblemDetails) : null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm text-[var(--text-secondary)]">
          {keys.length > 0 ? (
            <>
              <strong className="text-[var(--text-primary)]">{activeCount}</strong> {t('keysPage.activeOfTotal')}{' '}
              <strong className="text-[var(--text-primary)]">{keys.length}</strong>
            </>
          ) : (
            t('keysPage.headerBlurb')
          )}
        </p>
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="w-4 h-4 mr-1.5" />
          {t('keysPage.createBtn')}
        </Button>
      </div>

      {query.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-14 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
            />
          ))}
        </div>
      )}

      {query.isError && (
        <ErrorBanner problem={problem} message={t('keysPage.errLoadList')} />
      )}

      {!query.isLoading && !query.isError && (
        <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] overflow-hidden shadow-soft-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-app)]/60 text-[var(--text-secondary)]">
                <tr>
                  <th className="text-left font-medium px-4 py-2.5">{t('keysPage.colKey')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('keysPage.colStatus')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('keysPage.colCreatedAt')}</th>
                  <th className="text-left font-medium px-4 py-2.5">{t('keysPage.colRevokedAt')}</th>
                  <th className="text-right font-medium px-4 py-2.5 w-20"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {keys.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-10 text-center text-[var(--text-secondary)]">
                      {t('keysPage.emptyState')}
                    </td>
                  </tr>
                )}
                {keys.map((k) => (
                  <tr key={k.key_id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-8 h-8 rounded-full bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] flex items-center justify-center shrink-0">
                          <KeyRound className="w-4 h-4" strokeWidth={1.5} />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-[var(--text-primary)] truncate">
                            {k.label || t('keysPage.noLabel')}
                          </p>
                          <p className="text-xs text-[var(--text-secondary)] font-mono truncate">{maskKey(k.key_id)}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={STATUS_VARIANT[k.status]}>
                        {t(k.status === 'active' ? 'keysPage.statusActive' : 'keysPage.statusRevoked')}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-[var(--text-secondary)] tabular-nums">
                      {fmtDateTime(k.created_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--text-secondary)] tabular-nums">
                      {k.revoked_at ? fmtDateTime(k.revoked_at) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {k.status === 'active' ? (
                        <button
                          type="button"
                          onClick={() => setRevokeTarget(k)}
                          className="p-1.5 text-[var(--text-secondary)] hover:text-[#9B5050] hover:bg-[var(--state-error)]/8 rounded-md-custom transition-colors"
                          aria-label={t('keysPage.ariaRevoke')}
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      ) : (
                        <span className="text-xs text-[var(--text-secondary)]">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {createOpen && (
        <Modal onClose={closeCreateFlow}>
          <header className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h3 className="font-serif text-lg text-[var(--text-primary)]">
                {revealedKey ? t('keysPage.modalTitleCreated') : t('keysPage.modalTitleCreate')}
              </h3>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                {revealedKey
                  ? t('keysPage.modalDescRevealed')
                  : t('keysPage.modalDescCreate')}
              </p>
            </div>
            <button
              type="button"
              onClick={closeCreateFlow}
              className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-md-custom hover:bg-[var(--bg-app)]"
              aria-label={t('keysPage.ariaClose')}
            >
              <X className="w-4 h-4" />
            </button>
          </header>

          {revealedKey ? (
            <div className="space-y-4">
              <div className="flex items-start gap-2 text-xs text-[#9E814D] bg-[var(--state-warning)]/12 border border-[var(--state-warning)]/30 rounded-md-custom px-3 py-2">
                <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>
                  {t('keysPage.warnOneTime')}
                </span>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reveal-key">{t('keysPage.labelApiKey')}</Label>
                <div className="flex gap-2">
                  <Input
                    id="reveal-key"
                    readOnly
                    value={revealedKey}
                    className="font-mono text-sm"
                    onFocus={(e) => e.currentTarget.select()}
                  />
                  <Button variant="secondary" onClick={handleCopy}>
                    {copied ? (
                      <><Check className="w-4 h-4 mr-1" /> {t('keysPage.copiedLabel')}</>
                    ) : (
                      <><Copy className="w-4 h-4 mr-1" /> {t('keysPage.copyLabel')}</>
                    )}
                  </Button>
                </div>
              </div>
              <div className="flex justify-end pt-2">
                <Button onClick={closeCreateFlow}>
                  <Check className="w-4 h-4 mr-1.5" /> {t('keysPage.confirmedCopy')}
                </Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="key-label">{t('keysPage.labelOptional')}</Label>
                <Input
                  id="key-label"
                  placeholder={t('keysPage.labelPlaceholder')}
                  maxLength={100}
                  value={createLabel}
                  onChange={(e) => setCreateLabel(e.target.value)}
                />
                <p className="text-xs text-[var(--text-secondary)]">{t('keysPage.labelHint')}</p>
              </div>

              <div className="flex items-start gap-2 text-xs text-[var(--text-secondary)] bg-[var(--state-info)]/10 border border-[var(--state-info)]/30 rounded-md-custom px-3 py-2">
                <ShieldCheck className="w-4 h-4 text-[#52647D] shrink-0 mt-0.5" />
                <span>
                  {t('keysPage.keyGenInfoPre')}{' '}
                  <code className="font-mono">KAORI-XXXXXXXX-…</code>{t('keysPage.keyGenInfoPost')}
                </span>
              </div>

              {createError && <ErrorBanner problem={createError} />}

              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={closeCreateFlow}>{t('keysPage.cancelBtn')}</Button>
                <Button
                  isLoading={createMut.isPending}
                  onClick={() => { setCreateError(null); createMut.mutate(); }}
                >
                  <Plus className="w-4 h-4 mr-1.5" /> {t('keysPage.createKeyBtn')}
                </Button>
              </div>
            </div>
          )}
        </Modal>
      )}

      {revokeTarget && (
        <Modal onClose={() => setRevokeTarget(null)} small>
          <header className="mb-3">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('keysPage.revokeModalTitle')}</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {t('keysPage.revokeConfirmPre')} <strong className="text-[var(--text-primary)]">"{revokeTarget.label || t('keysPage.unlabeledKey')}"</strong>?
              {' '}{t('keysPage.revokeConfirmPost')}
            </p>
          </header>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setRevokeTarget(null)}>{t('keysPage.cancelBtn')}</Button>
            <Button
              variant="destructive"
              isLoading={revokeMut.isPending}
              onClick={() => revokeTarget && revokeMut.mutate(revokeTarget.key_id)}
            >
              <Trash2 className="w-4 h-4 mr-1.5" /> {t('keysPage.revokeBtn')}
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
