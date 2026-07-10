'use client';

import { use, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Save, Trash2, AlertTriangle } from 'lucide-react';

import { workspaceApi, type WsStatus } from '@/lib/api/platform';
import {
  Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { useT } from '@/lib/i18n/provider';

const STATUS_OPTIONS: Array<{ value: WsStatus; labelKey: string }> = [
  { value: 'active',    labelKey: 'editPage.statusActive' },
  { value: 'inactive',  labelKey: 'editPage.statusInactive' },
  { value: 'suspended', labelKey: 'editPage.statusSuspended' },
];

export default function WorkspaceEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const t = useT();
  const { id } = use(params);
  const router = useRouter();
  const qc     = useQueryClient();

  const query = useQuery({
    queryKey: ['platform-workspace', id],
    queryFn:  () => workspaceApi.get(id),
    retry: false,
  });

  const [name,     setName]     = useState('');
  const [planCode, setPlanCode] = useState('');
  const [status,   setStatus]   = useState<WsStatus>('active');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [error,    setError]    = useState<ProblemDetails | null>(null);

  useEffect(() => {
    if (query.data?.data) {
      setName(query.data.data.name);
      setPlanCode(query.data.data.plan_code);
      setStatus(query.data.data.status);
    }
  }, [query.data]);

  const updateMut = useMutation({
    mutationFn: () => workspaceApi.update(id, { name, plan_code: planCode, status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['platform-workspace', id] });
      qc.invalidateQueries({ queryKey: ['platform-workspaces'] });
      router.push(`/platform/workspaces/${id}`);
    },
    onError: (e: unknown) => setError(e as ProblemDetails),
  });

  const deleteMut = useMutation({
    mutationFn: () => workspaceApi.softDelete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['platform-workspaces'] });
      router.push('/platform/workspaces');
    },
    onError: (e: unknown) => setError(e as ProblemDetails),
  });

  if (query.isLoading) {
    return <div className="h-96 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse" />;
  }

  if (query.isError || !query.data) {
    return (
      <ErrorBanner
        problem={query.error ? (query.error as unknown as ProblemDetails) : null}
        message={t('editPage.errLoadFailed')}
      />
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
        <h2 className="font-serif text-lg text-[var(--text-primary)]">{t('editPage.sectionGeneral')}</h2>

        <div className="space-y-1.5">
          <Label htmlFor="ws-name">{t('editPage.fieldName')}</Label>
          <Input
            id="ws-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            minLength={2}
            maxLength={200}
            required
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="ws-plan">{t('editPage.fieldPlanCode')}</Label>
          <Input
            id="ws-plan"
            value={planCode}
            onChange={(e) => setPlanCode(e.target.value.toUpperCase())}
            pattern="^[A-Za-z0-9_-]{2,20}$"
            maxLength={20}
            required
          />
          <p className="text-xs text-[var(--text-secondary)]">
            {t('editPage.planCodeHint')}
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="ws-status">{t('editPage.fieldStatus')}</Label>
          <select
            id="ws-status"
            value={status}
            onChange={(e) => setStatus(e.target.value as WsStatus)}
            className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s.value} value={s.value}>{t(s.labelKey)}</option>
            ))}
          </select>
        </div>

        {error && <ErrorBanner problem={error} />}

        <div className="flex justify-end gap-2 pt-2">
          <Button
            variant="secondary"
            onClick={() => router.push(`/platform/workspaces/${id}`)}
            type="button"
          >
            {t('editPage.cancel')}
          </Button>
          <Button
            isLoading={updateMut.isPending}
            onClick={() => { setError(null); updateMut.mutate(); }}
          >
            <Save className="w-4 h-4 mr-1.5" />
            {t('editPage.saveChanges')}
          </Button>
        </div>
      </section>

      <section className="rounded-md-custom border border-[var(--state-error)]/30 bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-3">
        <h2 className="font-serif text-lg text-[#9B5050] flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          {t('editPage.dangerZone')}
        </h2>
        <p className="text-sm text-[var(--text-secondary)]">
          {t('editPage.softDeleteInfoPre')} <strong>{t('editPage.statusInactive')}</strong>.
          {' '}{t('editPage.softDeleteInfoPost')}
        </p>
        <Button variant="destructive" onClick={() => setConfirmDelete(true)}>
          <Trash2 className="w-4 h-4 mr-1.5" />
          {t('editPage.softDeleteWorkspace')}
        </Button>
      </section>

      {confirmDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--text-primary)]/40 backdrop-blur-sm p-4"
          role="dialog"
          aria-modal="true"
        >
          <div className="w-full max-w-md rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-lg p-6 space-y-4 animate-slide-up-fade">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{t('editPage.confirmDeleteTitle')}</h3>
            <p className="text-sm text-[var(--text-secondary)]">
              {t('editPage.confirmDeleteBodyPre')} <strong className="text-[var(--text-primary)]">"{query.data.data.name}"</strong> {t('editPage.confirmDeleteBodyPost')}
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setConfirmDelete(false)}>
                {t('editPage.cancel')}
              </Button>
              <Button
                variant="destructive"
                isLoading={deleteMut.isPending}
                onClick={() => deleteMut.mutate()}
              >
                {t('editPage.softDelete')}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
