'use client';

import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Monitor, Smartphone, Trash2, Globe, AlertTriangle, ShieldAlert, CheckCircle2,
} from 'lucide-react';

import {
  platformSecurityApi,
  type AdminSession,
} from '@/lib/api/platform';
import {
  Badge, Button, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { fmtDateTime } from '@/lib/format';

function deviceIcon(label: string | null) {
  const l = (label ?? '').toLowerCase();
  if (l.includes('iphone') || l.includes('android') || l.includes('ios')) {
    return <Smartphone className="w-4 h-4" />;
  }
  return <Monitor className="w-4 h-4" />;
}

export default function PlatformSessionsPage() {
  const qc    = useQueryClient();
  const query = useQuery({
    queryKey: ['platform-sessions'],
    queryFn:  () => platformSecurityApi.listSessions(),
    retry: false,
  });

  const [revokeTarget,      setRevokeTarget]      = useState<AdminSession | null>(null);
  const [postRevokeMessage, setPostRevokeMessage] = useState<string | null>(null);
  const [revokeAllOpen,     setRevokeAllOpen]     = useState(false);
  const [revokeAllSuccess,  setRevokeAllSuccess]  = useState<string | null>(null);
  const [revokeAllError,    setRevokeAllError]    = useState<ProblemDetails | null>(null);

  const revokeMut = useMutation({
    mutationFn: (sessionId: string) => platformSecurityApi.revokeSession(sessionId),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['platform-sessions'] });
      setRevokeTarget(null);
      if (res.meta.signed_out) {
        setPostRevokeMessage(
          'Bạn vừa thu hồi phiên hiện tại. Có thể cần đăng nhập lại sau khi token hết hạn.',
        );
      } else {
        setPostRevokeMessage(null);
      }
    },
  });

  const revokeAllMut = useMutation({
    mutationFn: () => platformSecurityApi.revokeOtherSessions(),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['platform-sessions'] });
      setRevokeAllOpen(false);
      setRevokeAllError(null);
      setRevokeAllSuccess(
        res.data.revoked_count > 0
          ? `Đã thu hồi ${res.data.revoked_count} phiên khác. Phiên hiện tại của bạn vẫn hoạt động.`
          : 'Không có phiên nào khác để thu hồi.',
      );
    },
    onError: (e: unknown) => setRevokeAllError(e as ProblemDetails),
  });

  const sessions   = query.data?.data ?? [];
  const otherCount = sessions.filter((s) => !s.is_current).length;
  const listProblem = query.error ? (query.error as unknown as ProblemDetails) : null;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-sm text-[var(--text-secondary)]">
          {sessions.length > 0 ? (
            <><strong className="text-[var(--text-primary)]">{sessions.length}</strong> phiên đang hoạt động</>
          ) : (
            'Mọi thiết bị bạn đang đăng nhập sẽ xuất hiện ở đây.'
          )}
        </p>
        {otherCount > 0 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { setRevokeAllError(null); setRevokeAllOpen(true); }}
          >
            <ShieldAlert className="w-3.5 h-3.5 mr-1.5" />
            Thu hồi tất cả phiên khác ({otherCount})
          </Button>
        )}
      </div>

      {revokeAllSuccess && (
        <div className="flex items-start gap-2 text-xs text-[#5C856A] bg-[var(--state-success)]/12 border border-[var(--state-success)]/30 rounded-md-custom px-3 py-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{revokeAllSuccess}</span>
        </div>
      )}

      {postRevokeMessage && (
        <div className="flex items-start gap-2 text-xs text-[#9E814D] bg-[var(--state-warning)]/12 border border-[var(--state-warning)]/30 rounded-md-custom px-3 py-2">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{postRevokeMessage}</span>
        </div>
      )}

      {query.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="h-20 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
            />
          ))}
        </div>
      )}

      {query.isError && (
        <ErrorBanner problem={listProblem} message="Không thể tải danh sách phiên đăng nhập." />
      )}

      {!query.isLoading && !query.isError && sessions.length === 0 && (
        <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 text-sm text-[var(--text-secondary)]">
          Chưa có phiên hoạt động nào được ghi nhận.
        </section>
      )}

      <div className="space-y-3">
        {sessions.map((s) => (
          <section
            key={s.session_id}
            className={
              s.is_current
                ? 'rounded-md-custom border border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/8 shadow-soft-sm p-5'
                : 'rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-5'
            }
          >
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-md-custom bg-[var(--bg-app)] text-[var(--text-secondary)] flex items-center justify-center shrink-0">
                {deviceIcon(s.device_label)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-medium text-[var(--text-primary)]">
                    {s.device_label || 'Thiết bị không xác định'}
                  </p>
                  {s.is_current && <Badge variant="current">Phiên hiện tại</Badge>}
                </div>
                <div className="text-xs text-[var(--text-secondary)] mt-1 space-y-0.5">
                  <div className="flex items-center gap-1.5">
                    <Globe className="w-3 h-3" />
                    <span className="font-mono">{s.ip_address ?? '—'}</span>
                  </div>
                  <p className="font-mono opacity-70 truncate">{s.user_agent ?? '—'}</p>
                  <p>
                    Hoạt động lần cuối <strong className="text-[var(--text-primary)]">{fmtDateTime(s.last_active_at)}</strong>
                    <span className="opacity-60"> · Bắt đầu {fmtDateTime(s.created_at)}</span>
                  </p>
                </div>
              </div>
              <Button
                variant="tertiary"
                size="sm"
                onClick={() => setRevokeTarget(s)}
                className="text-[#9B5050] hover:bg-[var(--state-error)]/8"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1" />
                Thu hồi
              </Button>
            </div>
          </section>
        ))}
      </div>

      {revokeAllOpen && (
        <Modal onClose={() => setRevokeAllOpen(false)} small>
          <header className="mb-3">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">Thu hồi tất cả phiên khác?</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Sẽ đăng xuất {otherCount} thiết bị khác đang dùng tài khoản này. Phiên hiện tại của bạn sẽ vẫn hoạt động bình thường.
            </p>
          </header>
          {revokeAllError && <ErrorBanner problem={revokeAllError} />}
          <div className="flex justify-end gap-2 pt-3">
            <Button variant="secondary" onClick={() => setRevokeAllOpen(false)}>Hủy</Button>
            <Button
              variant="destructive"
              isLoading={revokeAllMut.isPending}
              onClick={() => revokeAllMut.mutate()}
            >
              <ShieldAlert className="w-4 h-4 mr-1.5" />
              Thu hồi tất cả ({otherCount})
            </Button>
          </div>
        </Modal>
      )}

      {revokeTarget && (
        <Modal onClose={() => setRevokeTarget(null)} small>
          <header className="mb-3">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">
              {revokeTarget.is_current ? 'Đăng xuất khỏi thiết bị này?' : 'Thu hồi phiên'}
            </h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              {revokeTarget.is_current
                ? 'Đây là phiên bạn đang dùng. Sau khi thu hồi, token sẽ hết hạn và bạn cần đăng nhập lại.'
                : `Thu hồi phiên trên ${revokeTarget.device_label || 'thiết bị này'}? Người dùng sẽ bị đăng xuất ngay.`}
            </p>
          </header>
          <div className="flex justify-end gap-2 pt-3">
            <Button variant="secondary" onClick={() => setRevokeTarget(null)}>Hủy</Button>
            <Button
              variant="destructive"
              isLoading={revokeMut.isPending}
              onClick={() => revokeTarget && revokeMut.mutate(revokeTarget.session_id)}
            >
              <Trash2 className="w-4 h-4 mr-1.5" />
              Thu hồi phiên
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
