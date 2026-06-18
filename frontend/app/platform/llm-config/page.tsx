'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { SlidersHorizontal, Check, Loader2 } from 'lucide-react';

import { platformLLMConfigApi, type AIConfig } from '@/lib/api/llm-config';
import { ErrorBanner, type ProblemDetails } from '@/components/platform/foundation';

// CR-0019 / FR-PLT-08 — SUPER_ADMIN screen to tune AI knobs (RAG / memory /
// grounding / embedding) at runtime instead of editing source + redeploying.
export default function PlatformLLMConfigPage() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ['platform-ai-config'],
    queryFn: () => platformLLMConfigApi.list(),
    staleTime: 30_000,
    retry: false,
  });

  if (query.isLoading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} className="h-20 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse" />
        ))}
      </div>
    );
  }
  if (query.isError || !query.data) {
    return (
      <ErrorBanner
        problem={query.error ? (query.error as unknown as ProblemDetails) : null}
        message="Không thể tải cấu hình AI (cần quyền SUPER_ADMIN)."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] flex items-center justify-center">
          <SlidersHorizontal className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-serif text-xl text-[var(--text-primary)]">Tinh chỉnh AI</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-0.5">
            Chỉnh knob RAG / memory / grounding / embedding tại runtime, không cần redeploy.
            Knob <em>"chưa áp dụng"</em> đã hiển thị nhưng runtime chưa đọc — sẽ wire dần.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {query.data.map((c) => (
          <ConfigRow
            key={c.config_key}
            cfg={c}
            onSaved={() => qc.invalidateQueries({ queryKey: ['platform-ai-config'] })}
          />
        ))}
      </div>
    </div>
  );
}

function ConfigRow({ cfg, onSaved }: { cfg: AIConfig; onSaved: () => void }) {
  const [value, setValue] = useState(cfg.config_value);
  const [err, setErr] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: (v: string) => platformLLMConfigApi.update(cfg.config_key, v),
    onSuccess: () => { setErr(null); onSaved(); },
    onError: (e: any) => setErr(e?.message ?? 'Lỗi cập nhật'),
  });

  const dirty = value !== cfg.config_value;
  const bounds = cfg.value_type !== 'string' && (cfg.min_value != null || cfg.max_value != null)
    ? `${cfg.min_value ?? '−∞'} … ${cfg.max_value ?? '∞'}`
    : null;

  return (
    <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm p-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 flex-wrap">
          <code className="text-sm font-mono text-[var(--text-primary)]">{cfg.config_key}</code>
          <span className={`text-[10px] px-2 py-0.5 rounded-full ${
            cfg.applied
              ? 'bg-[var(--state-success)]/15 text-[#5C856A]'
              : 'bg-[var(--bg-app)] text-[var(--text-secondary)]'
          }`}>
            {cfg.applied ? 'đang áp dụng' : 'chưa áp dụng'}
          </span>
          <span className="text-[10px] text-[var(--text-secondary)]">
            {cfg.value_type}{bounds ? ` · ${bounds}` : ''}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={value}
            onChange={(e) => { setValue(e.target.value); setErr(null); }}
            className="w-32 border border-[var(--border-color)] rounded-md-custom px-2 py-1 text-sm bg-[var(--bg-app)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/40"
          />
          <button
            disabled={!dirty || m.isPending}
            onClick={() => m.mutate(value)}
            className="px-3 py-1.5 rounded-md-custom text-sm bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] disabled:opacity-40 flex items-center gap-1"
          >
            {m.isPending ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
            Lưu
          </button>
        </div>
      </div>
      {cfg.description && (
        <p className="text-xs text-[var(--text-secondary)] mt-2">{cfg.description}</p>
      )}
      {err && <p className="text-xs text-[#9B5050] mt-1.5">{err}</p>}
    </div>
  );
}
