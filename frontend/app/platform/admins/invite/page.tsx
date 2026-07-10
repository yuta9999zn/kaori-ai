'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Mail, ShieldCheck, Headphones, UserCog } from 'lucide-react';

import { platformAdminApi, type PlatformRole } from '@/lib/api/platform';
import {
  Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { PageHeader } from '@/components/platform/shell';
import { useT } from '@/lib/i18n/provider';

const ROLE_DESCRIPTIONS: Record<PlatformRole, {
  icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
  descriptionKey: string;
}> = {
  SUPER_ADMIN: {
    icon: ShieldCheck,
    descriptionKey: 'invitePage.roleDescSuperAdmin',
  },
  ADMIN: {
    icon: UserCog,
    descriptionKey: 'invitePage.roleDescAdmin',
  },
  SUPPORT: {
    icon: Headphones,
    descriptionKey: 'invitePage.roleDescSupport',
  },
};

export default function InviteAdminPage() {
  const t = useT();
  const router = useRouter();
  const qc     = useQueryClient();

  const [email,    setEmail]    = useState('');
  const [fullName, setFullName] = useState('');
  const [role,     setRole]     = useState<PlatformRole>('SUPPORT');
  const [error,    setError]    = useState<ProblemDetails | null>(null);

  const inviteMut = useMutation({
    mutationFn: () => platformAdminApi.invite({ email, full_name: fullName, role }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['platform-admins'] });
      router.push(`/platform/admins/${res.data.id}`);
    },
    onError: (e: unknown) => setError(e as ProblemDetails),
  });

  const RoleIcon = ROLE_DESCRIPTIONS[role].icon;

  return (
    <>
      <div className="px-6 lg:px-8 pt-6">
        <Link
          href="/platform/admins"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          {t('invitePage.backToAdmins')}
        </Link>
      </div>

      <PageHeader
        title={t('invitePage.title')}
        description={t('invitePage.description')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-2xl">
        <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
          <div className="space-y-1.5">
            <Label htmlFor="full-name">{t('invitePage.labelFullName')}</Label>
            <Input
              id="full-name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder={t('invitePage.phFullName')}
              required
              autoFocus
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="email">{t('invitePage.labelEmail')}</Label>
            <Input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={t('invitePage.phEmail')}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="role">{t('invitePage.labelRole')}</Label>
            <select
              id="role"
              value={role}
              onChange={(e) => setRole(e.target.value as PlatformRole)}
              className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            >
              <option value="SUPPORT">{t('invitePage.roleSupport')}</option>
              <option value="ADMIN">{t('invitePage.roleAdmin')}</option>
              <option value="SUPER_ADMIN">{t('invitePage.roleSuperAdmin')}</option>
            </select>
          </div>

          <div className="flex items-start gap-2.5 text-sm text-[var(--text-primary)] bg-[var(--state-info)]/10 border border-[var(--state-info)]/30 rounded-md-custom px-3 py-2.5">
            <RoleIcon className="w-4 h-4 text-[#52647D] shrink-0 mt-0.5" />
            <span>{t(ROLE_DESCRIPTIONS[role].descriptionKey)}</span>
          </div>

          {error && <ErrorBanner problem={error} />}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => router.push('/platform/admins')}>
              {t('invitePage.cancel')}
            </Button>
            <Button
              isLoading={inviteMut.isPending}
              disabled={!email || !fullName}
              onClick={() => { setError(null); inviteMut.mutate(); }}
            >
              <Mail className="w-4 h-4 mr-1.5" />
              {t('invitePage.sendInvite')}
            </Button>
          </div>
        </section>
      </div>
    </>
  );
}
