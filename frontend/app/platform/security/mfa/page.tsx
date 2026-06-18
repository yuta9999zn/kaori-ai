'use client';

import { useEffect, useRef, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import QRCode from 'qrcode';
import {
  ShieldCheck, ShieldOff, Copy, Check, AlertTriangle, QrCode, Smartphone,
} from 'lucide-react';

import {
  platformSecurityApi,
  type MfaEnableResult,
} from '@/lib/api/platform';
import {
  Badge, Button, Input, Label, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';

type Step = 'idle' | 'pending' | 'verified';

export default function PlatformMfaPage() {
  const [step,         setStep]         = useState<Step>('idle');
  const [enrol,        setEnrol]        = useState<MfaEnableResult | null>(null);
  const [code,         setCode]         = useState('');
  const [verifyError,  setVerifyError]  = useState<ProblemDetails | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [copiedUrl,    setCopiedUrl]    = useState(false);
  const qrCanvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!enrol || !qrCanvasRef.current) return;
    QRCode.toCanvas(qrCanvasRef.current, enrol.otpauth_url, {
      errorCorrectionLevel: 'M',
      width: 200,
      margin: 2,
      color: { dark: '#2F2F2F', light: '#FFFFFF' },
    }).catch(() => { /* fallback to manual entry block */ });
  }, [enrol]);

  const enableMut = useMutation({
    mutationFn: () => platformSecurityApi.enableMfa(),
    onSuccess: (res) => {
      setEnrol(res.data);
      setStep('pending');
      setVerifyError(null);
      setCode('');
    },
  });

  const verifyMut = useMutation({
    mutationFn: () => platformSecurityApi.verifyMfa(code),
    onSuccess: () => {
      setStep('verified');
      setVerifyError(null);
    },
    onError: (e: unknown) => setVerifyError(e as ProblemDetails),
  });

  async function copy(text: string, which: 'secret' | 'url') {
    try {
      await navigator.clipboard.writeText(text);
      if (which === 'secret') {
        setCopiedSecret(true);
        setTimeout(() => setCopiedSecret(false), 2000);
      } else {
        setCopiedUrl(true);
        setTimeout(() => setCopiedUrl(false), 2000);
      }
    } catch { /* clipboard blocked */ }
  }

  return (
    <div className="max-w-2xl space-y-5">
      <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6">
        <div className="flex items-start gap-4">
          <div
            className={
              step === 'verified'
                ? 'w-10 h-10 rounded-md-custom bg-[var(--state-success)]/15 text-[#5C856A] flex items-center justify-center shrink-0'
                : 'w-10 h-10 rounded-md-custom bg-[var(--bg-app)] text-[var(--text-secondary)] flex items-center justify-center shrink-0'
            }
          >
            {step === 'verified' ? <ShieldCheck className="w-5 h-5" /> : <ShieldOff className="w-5 h-5" />}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="font-medium text-[var(--text-primary)]">Xác thực 2 lớp (TOTP)</h2>
              {step === 'verified'
                ? <Badge variant="operational">Đã bật</Badge>
                : <Badge variant="default">Chưa bật</Badge>}
            </div>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Mỗi lần đăng nhập sẽ yêu cầu mã 6 chữ số từ ứng dụng xác thực (Google Authenticator,
              1Password, Authy…). Khoá bí mật được lưu mã hoá AES-256-GCM trên máy chủ.
            </p>
          </div>
          {step === 'idle' && (
            <Button
              isLoading={enableMut.isPending}
              onClick={() => enableMut.mutate()}
            >
              <ShieldCheck className="w-4 h-4 mr-1.5" />
              Bật MFA
            </Button>
          )}
        </div>
      </section>

      {step === 'pending' && enrol && (
        <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
          <div className="flex items-start gap-2 text-xs text-[#9E814D] bg-[var(--state-warning)]/12 border border-[var(--state-warning)]/30 rounded-md-custom px-3 py-2">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>
              Khoá bí mật chỉ hiển thị MỘT LẦN. Quét bằng ứng dụng xác thực hoặc lưu lại trước khi đóng trang.
            </span>
          </div>

          <div className="grid md:grid-cols-2 gap-5">
            <div>
              <h3 className="font-medium text-[var(--text-primary)] flex items-center gap-2">
                <QrCode className="w-4 h-4" />
                Bước 1: Quét QR
              </h3>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Mở Google Authenticator → "+" → "Quét mã QR" rồi đưa camera đến mã bên dưới.
              </p>
              <div className="mt-3 inline-block rounded-md-custom border border-[var(--border-color)] bg-white p-2">
                <canvas
                  ref={qrCanvasRef}
                  width={200}
                  height={200}
                  aria-label="QR code chứa khoá TOTP — quét bằng Google Authenticator"
                  className="block"
                />
              </div>
              <p className="mt-2 text-xs text-[var(--text-secondary)]">
                Không quét được? Dùng cách nhập thủ công bên cạnh.
              </p>
            </div>

            <div>
              <h3 className="font-medium text-[var(--text-primary)] flex items-center gap-2">
                <Smartphone className="w-4 h-4" />
                Hoặc nhập thủ công
              </h3>
              <div className="space-y-3 mt-3">
                <div className="space-y-1.5">
                  <Label htmlFor="mfa-secret">Khoá bí mật (Base32)</Label>
                  <div className="flex gap-2">
                    <Input
                      id="mfa-secret"
                      readOnly
                      value={enrol.secret}
                      onFocus={(e) => e.currentTarget.select()}
                      className="font-mono text-sm"
                    />
                    <Button variant="secondary" size="sm" onClick={() => copy(enrol.secret, 'secret')}>
                      {copiedSecret ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="mfa-url">otpauth URL</Label>
                  <div className="flex gap-2">
                    <Input
                      id="mfa-url"
                      readOnly
                      value={enrol.otpauth_url}
                      onFocus={(e) => e.currentTarget.select()}
                      className="font-mono text-xs"
                    />
                    <Button variant="secondary" size="sm" onClick={() => copy(enrol.otpauth_url, 'url')}>
                      {copiedUrl ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>
                <p className="text-xs text-[var(--text-secondary)]">
                  Tài khoản: <code className="font-mono">{enrol.issuer}: {enrol.account}</code>
                </p>
              </div>
            </div>
          </div>

          <div className="border-t border-[var(--border-color)]/60 pt-5">
            <h3 className="font-medium text-[var(--text-primary)]">Bước 2: Nhập mã 6 chữ số</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">
              Nhập mã hiện tại đang hiển thị trên ứng dụng. Mã đổi mỗi 30 giây.
            </p>
            <div className="mt-3 flex gap-2 max-w-xs">
              <Input
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6}
                inputMode="numeric"
                pattern="\d{6}"
                placeholder="123456"
                className="font-mono text-xl text-center tracking-[0.4em]"
              />
              <Button
                isLoading={verifyMut.isPending}
                disabled={code.length !== 6}
                onClick={() => { setVerifyError(null); verifyMut.mutate(); }}
              >
                <Check className="w-4 h-4 mr-1.5" />
                Xác thực
              </Button>
            </div>
            {verifyError && (
              <div className="mt-3">
                <ErrorBanner
                  problem={verifyError}
                  message="Không thể xác thực. Hãy chắc chắn đồng hồ điện thoại đúng giờ."
                />
              </div>
            )}
          </div>
        </section>
      )}

      {step === 'verified' && (
        <section className="rounded-md-custom border border-[var(--state-success)]/40 bg-[var(--state-success)]/8 shadow-soft-sm p-6 flex items-start gap-3">
          <Check className="w-5 h-5 text-[#5C856A] shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-[#5C856A]">MFA đã được bật.</p>
            <p className="text-sm text-[#5C856A]/80 mt-1">
              Lần đăng nhập tiếp theo bạn sẽ cần nhập mã 6 chữ số từ ứng dụng xác thực.
            </p>
          </div>
        </section>
      )}
    </div>
  );
}
