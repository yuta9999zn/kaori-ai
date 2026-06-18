'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ArrowRight, Check, Building2, Tag, ClipboardCheck } from 'lucide-react';

import { workspaceApi, type CreateWorkspaceBody } from '@/lib/api/platform';
import {
  Badge, Button, Input, Label, ErrorBanner, cn, type ProblemDetails,
} from '@/components/platform/foundation';
import { PageHeader } from '@/components/platform/shell';

const STEPS = [
  { id: 1, title: 'Thông tin chung', icon: Building2 },
  { id: 2, title: 'Gói & ngành',      icon: Tag },
  { id: 3, title: 'Xác nhận',         icon: ClipboardCheck },
] as const;

const PLAN_OPTIONS = [
  { value: 'PILOT',     label: 'PILOT — 1.000.000 ₫/tháng · 500 KH duy nhất' },
  { value: 'ENT_BASIC', label: 'ENT BASIC — 2.000.000 ₫/tháng · 1.000 KH' },
  { value: 'ENT_MID',   label: 'ENT MID — 5.000.000 ₫/tháng · 4.000 KH' },
  { value: 'ENT_MAX',   label: 'ENT MAX — 8.000.000 ₫/tháng · 10.000 KH' },
];

export default function NewWorkspacePage() {
  const router = useRouter();
  const qc     = useQueryClient();

  const [step,     setStep]     = useState<1 | 2 | 3>(1);
  const [name,     setName]     = useState('');
  const [planCode, setPlanCode] = useState('PILOT');
  const [industry, setIndustry] = useState('');
  const [error,    setError]    = useState<string | null>(null);
  const [apiError, setApiError] = useState<ProblemDetails | null>(null);

  const createMut = useMutation({
    mutationFn: () => {
      const body: CreateWorkspaceBody = { name, plan_code: planCode };
      if (industry.trim()) body.industry = industry.trim();
      return workspaceApi.create(body);
    },
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['platform-workspaces'] });
      router.push(`/platform/workspaces/${res.data.workspace_id}`);
    },
    onError: (e: unknown) => setApiError(e as ProblemDetails),
  });

  function next() {
    setError(null);
    setApiError(null);
    if (step === 1 && name.trim().length < 2) {
      setError('Tên workspace cần ≥ 2 ký tự.');
      return;
    }
    if (step < 3) setStep((step + 1) as 1 | 2 | 3);
  }
  function prev() {
    setError(null);
    setApiError(null);
    if (step > 1) setStep((step - 1) as 1 | 2 | 3);
  }

  return (
    <>
      <div className="px-6 lg:px-8 pt-6">
        <Link
          href="/platform/workspaces"
          className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Tất cả workspaces
        </Link>
      </div>

      <PageHeader
        title="Tạo workspace mới"
        description="Cấp phát môi trường tenant mới cho khách hàng doanh nghiệp."
      />

      <div className="px-6 lg:px-8 py-6 max-w-3xl space-y-6">
        <ol className="flex items-center gap-2">
          {STEPS.map((s, i) => {
            const done   = step > s.id;
            const active = step === s.id;
            const Icon   = done ? Check : s.icon;
            return (
              <li key={s.id} className="flex items-center gap-2 flex-1">
                <div
                  className={cn(
                    'flex items-center gap-2 px-3 py-1.5 rounded-full text-sm border whitespace-nowrap',
                    active && 'bg-[var(--primary-gold)]/15 border-[var(--primary-gold)]/40 text-[var(--text-primary)] font-medium',
                    done   && 'bg-[var(--state-success)]/15 border-[var(--state-success)]/40 text-[#5C856A]',
                    !active && !done && 'bg-[var(--bg-app)] border-[var(--border-color)] text-[var(--text-secondary)]',
                  )}
                >
                  <Icon className="w-3.5 h-3.5" strokeWidth={2} />
                  <span>{s.id}. {s.title}</span>
                </div>
                {i < STEPS.length - 1 && (
                  <div className={cn('flex-1 h-px', done ? 'bg-[var(--state-success)]/40' : 'bg-[var(--border-color)]')} />
                )}
              </li>
            );
          })}
        </ol>

        <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-6 space-y-5">
          {step === 1 && (
            <>
              <h2 className="font-serif text-lg text-[var(--text-primary)]">Thông tin chung</h2>
              <div className="space-y-1.5">
                <Label htmlFor="name">Tên workspace</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="VD: Acme Production"
                  minLength={2}
                  maxLength={200}
                  autoFocus
                />
                <p className="text-xs text-[var(--text-secondary)]">2–200 ký tự. Sẽ hiển thị cho thành viên trong workspace.</p>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <h2 className="font-serif text-lg text-[var(--text-primary)]">Gói & ngành</h2>
              <div className="space-y-1.5">
                <Label htmlFor="plan">Mã gói</Label>
                <select
                  id="plan"
                  value={planCode}
                  onChange={(e) => setPlanCode(e.target.value)}
                  className="h-10 w-full rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-3 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
                >
                  {PLAN_OPTIONS.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
                <p className="text-xs text-[var(--text-secondary)]">
                  Tính cước theo COUNT(DISTINCT customer_external_id) mỗi tháng — K-11.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="industry">Ngành (tùy chọn)</Label>
                <Input
                  id="industry"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  placeholder="VD: Bán lẻ, Tài chính, Sản xuất"
                  maxLength={100}
                />
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <h2 className="font-serif text-lg text-[var(--text-primary)]">Xác nhận</h2>
              <div className="space-y-3 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/30 p-4">
                <ConfirmRow label="Tên"   value={name} />
                <ConfirmRow label="Gói"   value={<Badge variant="current">{planCode}</Badge>} />
                <ConfirmRow label="Ngành" value={industry || '—'} />
              </div>
              <p className="text-xs text-[var(--text-secondary)]">
                Bạn có thể mời thành viên và cấp khoá API ngay sau khi tạo xong.
              </p>
            </>
          )}

          {error && (
            <div className="bg-[var(--state-error)]/10 border border-[var(--state-error)]/30 rounded-md-custom px-3 py-2 text-sm text-[#9B5050]">
              {error}
            </div>
          )}
          {apiError && <ErrorBanner problem={apiError} />}

          <div className="flex justify-between pt-2">
            <Button variant="secondary" onClick={prev} disabled={step === 1}>
              <ArrowLeft className="w-4 h-4 mr-1.5" />
              Quay lại
            </Button>
            {step < 3 ? (
              <Button onClick={next}>
                Tiếp tục
                <ArrowRight className="w-4 h-4 ml-1.5" />
              </Button>
            ) : (
              <Button
                isLoading={createMut.isPending}
                onClick={() => { setError(null); setApiError(null); createMut.mutate(); }}
              >
                <Check className="w-4 h-4 mr-1.5" />
                Tạo workspace
              </Button>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

function ConfirmRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-[var(--text-secondary)]">{label}</span>
      <span className="font-medium text-sm text-[var(--text-primary)]">{value}</span>
    </div>
  );
}
