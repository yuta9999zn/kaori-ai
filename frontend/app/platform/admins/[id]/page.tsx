'use client';

import { use, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft, ShieldCheck, Headphones, UserCog, KeyRound, Power, Save, X,
} from 'lucide-react';

import {
  platformAdminApi,
  type PlatformRole,
  type UpdateAdminBody,
} from '@/lib/api/platform';
import {
  Badge, Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtDateTime } from '@/lib/format';

interface RoleMeta {
  variant: 'error' | 'current' | 'info';
  label:   string;
  icon:    React.ComponentType<{ className?: string; strokeWidth?: number }>;
  tile:    string;
}

const ROLE_META: Record<PlatformRole, RoleMeta> = {
  SUPER_ADMIN: { variant: 'error',   label: 'Super Admin',     icon: ShieldCheck, tile: 'bg-[var(--state-error)]/15 text-[#9B5050]' },
  ADMIN:       { variant: 'current', label: 'Quản trị viên',   icon: UserCog,     tile: 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)]' },
  SUPPORT:     { variant: 'info',    label: 'Hỗ trợ kỹ thuật', icon: Headphones,  tile: 'bg-[var(--state-info)]/15 text-[#52647D]' },
};

export default function AdminDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const qc     = useQueryClient();

  const query = useQuery({
    queryKey: ['platform-admin', id],
    queryFn:  () => platformAdminApi.get(id),
    retry: false,
  });

  const [editOpen,      setEditOpen]      = useState(false);
  const [confirmToggle, setConfirmToggle] = useState(false);
  const [editFullName,  setEditFullName]  = useState('');
  const [editRole,      setEditRole]      = useState<PlatformRole>('SUPPORT');
  const [editError,     setEditError]     = useState<ProblemDetails | null>(null);

  const updateMut = useMutation({
    mutationFn: (body: UpdateAdminBody) => platformAdminApi.update(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['platform-admin', id] });
      qc.invalidateQueries({ queryKey: ['platform-admins'] });
      setEditOpen(false);
      setConfirmToggle(false);
    },
    onError: (e: unknown) => setEditError(e as ProblemDetails),
  });

  if (query.isLoading) {
    return (
      <div className="px-6 lg:px-8 py-6">
        <div className="h-72 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse" />
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <div className="px-6 lg:px-8 py-6">
        <ErrorBanner
          problem={query.error ? (query.error as unknown as ProblemDetails) : null}
          message="Không thể tải quản trị viên."
        />
      </div>
    );
  }

  const a    = query.data.data;
  const meta = ROLE_META[a.role];
  const Icon = meta.icon;

  function openEdit() {
    setEditFullName(a.full_name ?? '');
    setEditRole(a.role);
    setEditError(null);
    setEditOpen(true);
  }

  return (
    <>
      <div className="px-6 lg:px-8 pt-6">
        <Link
          href="/platform/admins"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Tất cả quản trị viên
        </Link>
      </div>

      <header className="px-6 lg:px-8 py-5 border-b border-[var(--border-color)] bg-[var(--bg-card)]">
        <div className="flex items-start gap-4">
          <div className={`p-3 rounded-md-custom shrink-0 ${meta.tile}`}>
            <Icon className="w-7 h-7" strokeWidth={1.5} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="font-serif text-2xl text-[var(--text-primary)]">
                {a.full_name ?? a.email}
              </h1>
              <Badge variant={meta.variant}>{meta.label}</Badge>
              {!a.is_active && <Badge variant="default">Vô hiệu</Badge>}
              {a.mfa_enabled && <Badge variant="operational">MFA</Badge>}
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-1">{a.email}</p>
          </div>
        </div>
      </header>

      <div className="px-6 lg:px-8 py-6 space-y-6">
        <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6">
            <Fact label="Đăng nhập gần nhất" value={fmtDateTime(a.last_login_at)} />
            <Fact label="Ngày tạo"            value={fmtDateTime(a.created_at)} />
            <Fact label="MFA"                 value={a.mfa_enabled ? 'Đã bật' : 'Chưa bật'} />
          </div>
        </section>

        <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-3">
          <h2 className="font-serif text-lg text-[var(--text-primary)]">Hành động</h2>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={openEdit}>
              <UserCog className="w-4 h-4 mr-1.5" />
              Đổi vai trò / tên
            </Button>
            <Link href={`/platform/admins/${id}/reset-password`}>
              <Button variant="secondary">
                <KeyRound className="w-4 h-4 mr-1.5" />
                Đặt lại mật khẩu
              </Button>
            </Link>
            <Button
              variant={a.is_active ? 'destructive' : 'primary'}
              onClick={() => setConfirmToggle(true)}
            >
              <Power className="w-4 h-4 mr-1.5" />
              {a.is_active ? 'Vô hiệu hóa' : 'Kích hoạt lại'}
            </Button>
          </div>
        </section>
      </div>

      {editOpen && (
        <Modal onClose={() => setEditOpen(false)}>
          <header className="flex items-start justify-between gap-4 mb-4">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">Cập nhật quản trị viên</h3>
            <button
              type="button"
              onClick={() => setEditOpen(false)}
              className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-md-custom hover:bg-[var(--bg-app)]"
              aria-label="Đóng"
            >
              <X className="w-4 h-4" />
            </button>
          </header>

          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="edit-full-name">Họ tên</Label>
              <Input
                id="edit-full-name"
                value={editFullName}
                onChange={(e) => setEditFullName(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-role">Vai trò</Label>
              <select
                id="edit-role"
                value={editRole}
                onChange={(e) => setEditRole(e.target.value as PlatformRole)}
                className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              >
                <option value="SUPPORT">Hỗ trợ kỹ thuật</option>
                <option value="ADMIN">Quản trị viên</option>
                <option value="SUPER_ADMIN">Super Admin</option>
              </select>
            </div>
            {editError && <ErrorBanner problem={editError} />}
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => setEditOpen(false)}>Hủy</Button>
              <Button
                isLoading={updateMut.isPending}
                onClick={() => updateMut.mutate({ full_name: editFullName, role: editRole })}
              >
                <Save className="w-4 h-4 mr-1.5" />
                Lưu
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {confirmToggle && (
        <Modal onClose={() => setConfirmToggle(false)} small>
          <header className="mb-3">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">
              {a.is_active ? 'Xác nhận vô hiệu hóa' : 'Xác nhận kích hoạt lại'}
            </h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {a.is_active
                ? `${a.full_name ?? a.email} sẽ không thể đăng nhập cho đến khi được kích hoạt lại.`
                : `${a.full_name ?? a.email} sẽ được phép đăng nhập trở lại.`}
            </p>
          </header>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={() => setConfirmToggle(false)}>Hủy</Button>
            <Button
              variant={a.is_active ? 'destructive' : 'primary'}
              isLoading={updateMut.isPending}
              onClick={() => updateMut.mutate({ is_active: !a.is_active })}
            >
              {a.is_active ? 'Vô hiệu hóa' : 'Kích hoạt lại'}
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

function Fact({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">{label}</p>
      <p className="font-medium text-sm text-[var(--text-primary)] tabular-nums">{value}</p>
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
