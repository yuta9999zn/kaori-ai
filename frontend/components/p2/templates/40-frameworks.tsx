// @ts-nocheck
'use client';

// ============================================================================
// 40. /p2/frameworks — Frameworks Hub (F-034 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Gallery cho 6 framework + custom builder. K-10: 1 câu hỏi = 1 khung —
// hub không cho phép multi-select; mỗi card mở 1 page riêng cho framework đó.
//
// Phase 1 đã có:
//   - Insight Generator wizard (file 27) cho phép pick framework qua radio
//   - Pipeline step-4 dispatch template phân tích đơn lẻ
//
// Phase 2 (F-034) sẽ wire LLM auto-fill từng quadrant của framework.
// ============================================================================

import React from 'react';
import {
  Layers, Sparkles, ShieldCheck, ArrowRight,
  Grid3x3, HelpCircle, Wrench, Fish, TrendingUp, Calendar, Settings2,
} from 'lucide-react';

import { Button, Badge, cn } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface Frame {
  code:        string;
  title:       string;
  description: string;
  use_case:    string;
  href:        string;
  icon:        any;
  /** Phase the framework lands. */
  phase:       1 | 2;
}

const FRAMES: Frame[] = [
  { code: 'swot',     title: 'SWOT',     description: 'Strengths · Weaknesses · Opportunities · Threats',                  use_case: 'Đánh giá vị thế cạnh tranh',           href: '/p2/frameworks/swot',     icon: Grid3x3,  phase: 2 },
  { code: '6w',       title: '6W',       description: 'Who · What · When · Where · Why · How',                              use_case: 'Phân tích nguyên nhân + bối cảnh',     href: '/p2/frameworks/6w',       icon: HelpCircle, phase: 2 },
  { code: '2h',       title: '2H',       description: 'How · How much (đào sâu định lượng)',                                use_case: 'Định lượng độ lớn vấn đề + giải pháp', href: '/p2/frameworks/2h',       icon: Wrench,   phase: 2 },
  { code: 'fishbone', title: 'Fishbone', description: 'Ishikawa — root cause cho dị thường',                                use_case: 'Truy nguyên gốc rễ sự cố',             href: '/p2/frameworks/fishbone', icon: Fish,     phase: 2 },
  { code: 'mom-yoy',  title: 'MoM/YoY',  description: 'So sánh tháng-trên-tháng + năm-trên-năm',                            use_case: 'Phân tích xu hướng theo thời gian',    href: '/p2/frameworks/mom-yoy',  icon: TrendingUp, phase: 2 },
  { code: 'custom',   title: 'Tuỳ chỉnh', description: 'Tự định nghĩa khung phân tích cho domain riêng',                  use_case: 'Khung industry-specific',              href: '/p2/frameworks/custom',   icon: Settings2, phase: 2 },
];

export default function FrameworksHubPage() {
  return (
    <>
      <PageHeader
        title="Khung phân tích"
        description="6 framework + 1 builder. Chọn 1 cho mỗi câu hỏi (K-10)."
        actions={<Badge variant="info">Phase 2 · F-034</Badge>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        {/* K-10 banner */}
        <div className="bg-[var(--state-warning)]/8 rounded-lg-custom border border-[var(--state-warning)]/30 p-4 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <div>
              <p className="font-serif text-sm text-[var(--text-primary)]">K-10 — Một câu hỏi = một khung</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                Kaori không cho phép chạy SWOT + 5Why song song trên cùng một câu hỏi. Để so sánh nhiều khung, hãy dispatch
                multiple analysis runs từ <a href="/p2/insights/generate" className="text-[var(--primary-gold-dark)] underline">Insight Generator</a>.
              </p>
            </div>
          </div>
        </div>

        {/* Gallery */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FRAMES.map((f) => <FrameCard key={f.code} frame={f} />)}
        </div>

        {/* K-3 footer */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Auto-fill mỗi quadrant đi qua <span className="font-mono">llm_router.py</span> (K-3). Mặc định Qwen 2.5 nội bộ — có thể đổi sang AI ngoài
            (consent K-4) ngay trong từng framework page.
          </p>
        </div>
      </div>
    </>
  );
}

function FrameCard({ frame: f }: { frame: Frame }) {
  const Icon = f.icon;
  return (
    <a
      href={f.href}
      className="group block bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 hover:shadow-soft-md transition-all p-5"
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
          <Icon className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        {f.phase > 1 && <Badge variant="info">Phase {f.phase}</Badge>}
      </div>
      <h3 className="font-serif text-lg text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors">{f.title}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{f.description}</p>
      <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60">
        <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Phù hợp khi</p>
        <p className="text-xs text-[var(--text-primary)] mt-1">{f.use_case}</p>
      </div>
      <div className="mt-3 inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)] group-hover:translate-x-0.5 transition-transform">
        Mở khung
        <ArrowRight className="w-3 h-3 ml-1" />
      </div>
    </a>
  );
}
