'use client';

import { use, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ArrowLeft, KeyRound, ShieldAlert, CheckCircle2 } from 'lucide-react';

import { platformAdminApi } from '@/lib/api/platform';
import {
  Button, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { PageHeader } from '@/components/platform/shell';

export default function AdminResetPasswordPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();

  const query = useQuery({
    queryKey: ['platform-admin', id],
    queryFn:  () => platformAdminApi.get(id),
    retry: false,
  });

  const [error, setError] = useState<ProblemDetails | null>(null);

  const resetMut = useMutation({
    mutationFn: () => platformAdminApi.resetPassword(id),
    onError: (e: unknown) => setError(e as ProblemDetails),
  });

  if (query.isLoading) {
    return (
      <div className="px-6 lg:px-8 py-6 max-w-2xl">
        <div className="h-72 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse" />
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <div className="px-6 lg:px-8 py-6 max-w-2xl">
        <ErrorBanner
          problem={query.error ? (query.error as unknown as ProblemDetails) : null}
          message="Không thể tải quản trị viên."
        />
      </div>
    );
  }

  const a       = query.data.data;
  const success = resetMut.isSuccess;
  const sentTo  = resetMut.data?.data.reset_token_sent_to ?? a.email;

  return (
    <>
      <div className="px-6 lg:px-8 pt-6">
        <Link
          href={`/platform/admins/${id}`}
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Quay lại chi tiết
        </Link>
      </div>

      <PageHeader
        title="Đặt lại mật khẩu"
        description={`${a.full_name ?? a.email} · ${a.email}`}
      />

      <div className="px-6 lg:px-8 py-6 max-w-2xl">
        {success ? (
          <section className="rounded-md-custom border border-[var(--state-success)]/40 bg-[var(--state-success)]/8 shadow-soft-sm p-6 space-y-3">
            <div className="flex items-center gap-2 text-[#5C856A]">
              <CheckCircle2 className="w-5 h-5" />
              <h2 className="font-serif text-lg">Đã gửi email</h2>
            </div>
            <p className="text-sm text-[var(--text-primary)]">
              Liên kết đặt lại mật khẩu đã được gửi tới{' '}
              <strong>{sentTo}</strong>. Token có hiệu lực trong 60 phút.
            </p>
            <div className="pt-2">
              <Button variant="secondary" onClick={() => router.push(`/platform/admins/${id}`)}>
                Quay lại chi tiết
              </Button>
            </div>
          </section>
        ) : (
          <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-4">
            <div className="flex items-start gap-3 bg-[var(--state-warning)]/12 border border-[var(--state-warning)]/30 rounded-md-custom px-3 py-2.5">
              <ShieldAlert className="w-5 h-5 text-[#9E814D] shrink-0 mt-0.5" />
              <div className="text-sm text-[var(--text-primary)]">
                <p className="font-medium">Hành động này:</p>
                <ul className="list-disc list-inside text-[var(--text-secondary)] text-xs mt-1 space-y-0.5">
                  <li>Gửi email tới <strong>{a.email}</strong> với liên kết đặt lại mật khẩu.</li>
                  <li>Vô hiệu hóa các phiên đăng nhập hiện tại của tài khoản này.</li>
                  <li>
                    {a.mfa_enabled
                      ? 'Giữ nguyên thiết lập MFA — người dùng vẫn cần TOTP để đăng nhập.'
                      : 'KHÔNG bật MFA — bạn nên yêu cầu người dùng bật MFA sau khi đặt lại.'}
                  </li>
                  <li>
                    Ghi nhận trong nhật ký kiểm toán dưới dạng{' '}
                    <code className="font-mono">admin.password_reset_requested</code>.
                  </li>
                </ul>
              </div>
            </div>

            {error && <ErrorBanner problem={error} />}

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="secondary" onClick={() => router.push(`/platform/admins/${id}`)}>
                Hủy
              </Button>
              <Button
                isLoading={resetMut.isPending}
                onClick={() => { setError(null); resetMut.mutate(); }}
              >
                <KeyRound className="w-4 h-4 mr-1.5" />
                Gửi email đặt lại mật khẩu
              </Button>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
