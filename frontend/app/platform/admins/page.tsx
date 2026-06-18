'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldCheck, Headphones, UserCog, UserPlus, ChevronRight,
} from 'lucide-react';

import { api } from '@/lib/api';
import {
  Badge, Button, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { PageHeader } from '@/components/platform/shell';
import { fmtDateTime } from '@/lib/format';

type PlatformRole = 'SUPER_ADMIN' | 'ADMIN' | 'SUPPORT';

interface PlatformAdmin {
  id:          string;
  email:       string;
  full_name?:  string;
  role:        PlatformRole;
  is_active:   boolean;
  created_at:  string;
}

interface RoleMeta {
  variant: 'error' | 'current' | 'info';
  label:   string;
  icon:    React.ComponentType<{ className?: string; strokeWidth?: number }>;
  tile:    string;
}

const ROLE_META: Record<PlatformRole, RoleMeta> = {
  SUPER_ADMIN: {
    variant: 'error',
    label:   'Super Admin',
    icon:    ShieldCheck,
    tile:    'bg-[var(--state-error)]/15 text-[#9B5050]',
  },
  ADMIN: {
    variant: 'current',
    label:   'Quản trị viên',
    icon:    UserCog,
    tile:    'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)]',
  },
  SUPPORT: {
    variant: 'info',
    label:   'Hỗ trợ kỹ thuật',
    icon:    Headphones,
    tile:    'bg-[var(--state-info)]/15 text-[#52647D]',
  },
};

export default function PlatformAdminsPage() {
  const query = useQuery<{ data: PlatformAdmin[] }>({
    queryKey:  ['platform-admins'],
    queryFn:   () => api('/api/v1/platform/admins'),
    staleTime: 60_000,
  });

  const admins  = query.data?.data ?? [];
  const problem = query.error ? (query.error as unknown as ProblemDetails) : null;

  return (
    <>
      <PageHeader
        title="Quản trị viên Platform"
        description="Tài khoản có quyền quản trị toàn hệ thống. Super Admin bắt buộc MFA."
        actions={
          <Link href="/platform/admins/invite">
            <Button variant="primary" size="sm">
              <UserPlus className="w-4 h-4 mr-1.5" />
              Mời quản trị viên
            </Button>
          </Link>
        }
      />

      <div className="px-6 lg:px-8 py-6 space-y-4">
        {problem && <ErrorBanner problem={problem} />}

        {query.isLoading && (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div
                key={i}
                className="h-16 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
              />
            ))}
          </div>
        )}

        {!query.isLoading && admins.length === 0 && !problem && (
          <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-10 text-center text-[var(--text-secondary)]">
            Chưa có quản trị viên nào.
          </div>
        )}

        {!query.isLoading && admins.length > 0 && (
          <div className="space-y-2">
            {admins.map((admin) => {
              const meta = ROLE_META[admin.role];
              const Icon = meta.icon;
              return (
                <Link
                  key={admin.id}
                  href={`/platform/admins/${admin.id}`}
                  className="block rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm hover:shadow-soft-md hover:border-[var(--primary-gold)]/40 transition-all"
                >
                  <div className="py-4 px-4 flex items-center gap-4">
                    <div className={`p-2.5 rounded-md-custom shrink-0 ${meta.tile}`}>
                      <Icon className="w-5 h-5" strokeWidth={1.75} />
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="font-medium text-[var(--text-primary)]">
                          {admin.full_name ?? admin.email}
                        </p>
                        <Badge variant={meta.variant}>{meta.label}</Badge>
                        {!admin.is_active && <Badge variant="default">Vô hiệu</Badge>}
                      </div>
                      <p className="text-xs text-[var(--text-secondary)] mt-0.5">{admin.email}</p>
                    </div>

                    <p className="text-xs text-[var(--text-secondary)] shrink-0 hidden sm:block tabular-nums">
                      {fmtDateTime(admin.created_at)}
                    </p>
                    <ChevronRight className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
