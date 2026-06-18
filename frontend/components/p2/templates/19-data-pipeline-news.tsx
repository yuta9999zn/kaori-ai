// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 19. /p2/pipelines/new — Pipeline wizard entry (5-step explainer)
// ----------------------------------------------------------------------------
// Decision page before the user enters the wizard:
//   - Choose data source (upload / connect existing dataset / template)
//   - See the 5 steps + estimated time + what they'll need
//   - "Bắt đầu" → /p2/pipelines/new/upload?source=<kind>
//
// No backend call here. The pipeline_run row is created by POST /api/v1/upload
// (bronze/ingestor.py auto-allocates run_id) — there is no separate
// `POST /api/v1/pipelines` shell-create endpoint. Source picker is FE-only;
// passed via query string so step-1 can branch without losing state on refresh.
// ============================================================================

import React, { useState } from 'react';
import {
  UploadCloud, ArrowRight, FileSpreadsheet,
  ShieldCheck, Clock, Layers, BarChart2, Lightbulb, Check, Sparkles,
} from 'lucide-react';

import {
  Button,
  cn,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type SourceKind = 'upload' | 'silver' | 'template';

const SOURCE_OPTIONS: Array<{
  id: SourceKind;
  title: string;
  desc: string;
  icon: any;
  recommended?: boolean;
}> = [
  {
    id: 'upload',
    title: 'Tải file mới (CSV / Excel / ZIP)',
    desc: 'Phù hợp khi bạn có dữ liệu mới. SHA-256 sẽ chống upload trùng (K-8).',
    icon: UploadCloud,
    recommended: true,
  },
  {
    id: 'silver',
    title: 'Dùng dataset Silver có sẵn',
    desc: 'Bỏ qua ingest — chạy phân tích trên dataset đã sạch & che PII.',
    icon: Layers,
  },
  {
    id: 'template',
    title: 'Bắt đầu từ template phân tích',
    desc: 'Mẫu nghiệp vụ phổ biến (RFM churn, anomaly, time series) có sẵn.',
    icon: Sparkles,
  },
];

const STEPS = [
  { n: 1, title: 'Upload',         desc: 'Tải file gốc. Kaori tính SHA-256 + đẩy về Bronze.', icon: UploadCloud },
  { n: 2, title: 'Cột',            desc: 'Map cột — exact / fuzzy / AI suggest với confidence.', icon: FileSpreadsheet },
  { n: 3, title: 'Làm sạch',       desc: 'Áp dụng quy tắc (null, dedup, kiểu dữ liệu, AI detect).', icon: Layers },
  { n: 4, title: 'Phân tích',      desc: 'Chọn template + bật/tắt consent_external (K-4).',     icon: BarChart2 },
  { n: 5, title: 'Kết quả',        desc: 'Dashboard ChartBlock + insight + decision audit log.', icon: Lightbulb },
];

export default function PipelineNew() {
  const [source,  setSource]  = useState<SourceKind>('upload');
  const [name,    setName]    = useState('');

  function handleStart() {
    const params = new URLSearchParams({ source });
    if (name.trim()) params.set('name', name.trim());
    window.location.href = `/p2/pipelines/new/upload?${params.toString()}`;
  }

  return (
    <>
      <PageHeader
        title="Tạo pipeline mới"
        description="Chọn nguồn dữ liệu và đặt tên. Wizard 5 bước sẽ hướng dẫn phần còn lại."
      />

      <div className="px-6 lg:px-8 py-8 max-w-[960px] mx-auto space-y-6">
        {/* Source picker */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-6 shadow-soft-sm">
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-4">Nguồn dữ liệu</h2>
          <div className="space-y-3">
            {SOURCE_OPTIONS.map((opt) => {
              const Icon = opt.icon;
              const sel = source === opt.id;
              return (
                <button
                  type="button"
                  key={opt.id}
                  onClick={() => setSource(opt.id)}
                  className={cn(
                    'w-full relative flex items-start p-4 border rounded-md-custom text-left transition-all',
                    sel
                      ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8 ring-1 ring-[var(--primary-gold)]'
                      : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]/30 hover:bg-[var(--bg-app)]/40',
                  )}
                >
                  <div className={cn(
                    'p-3 rounded-md-custom mr-4 shrink-0',
                    sel ? 'bg-[var(--primary-gold)] text-[var(--text-primary)]' : 'bg-[var(--bg-app)] text-[var(--text-secondary)]',
                  )}>
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-[var(--text-primary)]">{opt.title}</h3>
                    <p className="text-xs text-[var(--text-secondary)] mt-1">{opt.desc}</p>
                  </div>
                  {opt.recommended && !sel && (
                    <span className="absolute top-3 right-4 text-[10px] font-bold uppercase tracking-wide px-2 py-0.5 rounded-sm-custom bg-[var(--primary-gold)]/15 text-[#9E814D]">
                      Khuyến nghị
                    </span>
                  )}
                  <div className={cn(
                    'w-5 h-5 rounded-full border flex items-center justify-center ml-4 shrink-0 mt-0.5',
                    sel ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]' : 'border-[var(--border-color)]',
                  )}>
                    {sel && <Check className="w-3 h-3 text-white" strokeWidth={3} />}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="mt-5 pt-5 border-t border-[var(--border-color)]/60">
            <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">Tên pipeline</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ví dụ: Phân tích doanh thu Q3 NA"
              className="w-full h-10 rounded-md-custom border border-[var(--border-color)] bg-white px-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/40 focus:border-[var(--primary-gold)]"
            />
            <p className="text-xs text-[var(--text-secondary)] mt-1">Tuỳ chọn — có thể đổi sau khi tạo.</p>
          </div>
        </div>

        {/* 5-step preview */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-6 shadow-soft-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-serif text-lg text-[var(--text-primary)]">5 bước trong wizard</h2>
            <span className="text-xs text-[var(--text-secondary)] flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              5–15 phút tuỳ kích thước file
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
            {STEPS.map((s) => {
              const Icon = s.icon;
              return (
                <div key={s.n} className="rounded-md-custom border border-[var(--border-color)] p-3 bg-[var(--bg-app)]/40">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="w-6 h-6 rounded-full bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] text-xs font-semibold flex items-center justify-center">
                      {s.n}
                    </span>
                    <Icon className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
                  </div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">{s.title}</p>
                  <p className="text-[11px] text-[var(--text-secondary)] mt-1 leading-relaxed">{s.desc}</p>
                </div>
              );
            })}
          </div>

          <div className="mt-5 flex items-start gap-3 p-3 rounded-md-custom bg-[var(--bg-app)]/60 border border-[var(--border-color)]">
            <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <p className="text-xs text-[var(--text-secondary)]">
              Mọi LLM call đi qua <span className="font-medium text-[var(--text-primary)]">llm_router</span> (K-3) — Qwen 2.5 local là mặc định.
              External AI (Claude / GPT-4o) chỉ bật khi bạn chọn ở Bước 4 (K-4) — PII đã được che (K-5).
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <Button variant="secondary" onClick={() => (window.location.href = '/p2/pipelines')}>
            Huỷ
          </Button>
          <Button onClick={handleStart}>
            Bắt đầu
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>
      </div>
    </>
  );
}
