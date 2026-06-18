'use client';

// ============================================================================
// F-034 Frameworks — wired hub + per-framework pages (BE PR #119 landed)
// ----------------------------------------------------------------------------
// Single file exports five pages:
//   * FrameworksHub        — /p2/frameworks
//   * SwotRunPage          — /p2/frameworks/swot
//   * SixWRunPage          — /p2/frameworks/6w
//   * TwoHRunPage          — /p2/frameworks/2h
//   * FishboneRunPage      — /p2/frameworks/fishbone-ishikawa
//
// Each framework page is a generate-and-poll flow:
//   1. User fills question + optional source_ref + consent_external toggle
//   2. POST /api/v1/frameworks/generate → 202 + run_id
//   3. Poll GET /api/v1/frameworks/{run_id} every 2s until status='ready' or 'failed'
//   4. Render result with framework-specific layout (SWOT 4-quadrant, 6W list,
//      2H how/how-much, Fishbone categorised)
//
// MoM/YoY (calculation) and Custom (per-tenant prompt store) are intentionally
// NOT in this file — BE deferred to v1. The legacy mock templates 45/46
// stay at /p2/frameworks/{mom-yoy-analysis,custom-analyst} until then.
// ============================================================================

import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowRight, Calendar, ChevronLeft, Database, Fish,
  Globe, Grid3x3, HelpCircle, Loader2, Lock, RefreshCw,
  Sparkles, ShieldCheck, Star, TrendingUp, Wrench,
  AlertTriangle, AlertCircle, ChevronRight, Clock,
} from 'lucide-react';

import {
  Button, Badge, Checkbox, ErrorBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types — mirror BE Pydantic models in services/ai-orchestrator/routers/frameworks.py
// ============================================================================

type FrameworkCode = 'swot' | '6w' | '2h' | 'fishbone';
type RunStatus = 'queued' | 'running' | 'ready' | 'failed';

interface RunListItem {
  run_id:           string;
  framework_code:   FrameworkCode;
  question:         string;
  source_ref:       string | null;
  consent_external: boolean;
  status:           RunStatus;
  narrative:        string | null;
  created_at:       string;
  completed_at:     string | null;
  last_error:       string | null;
}

interface RunDetail extends RunListItem {
  content_json: any | null;
}

interface RunListResponse  { items: RunListItem[]; next_cursor?: string | null }
interface CatalogueItem    { code: FrameworkCode; name: string; description: string }
interface CatalogueResponse { items: CatalogueItem[] }

// ============================================================================
// Framework metadata — UI-side mirror so we can render icons + colours
// without round-tripping the catalogue endpoint on every page.
// ============================================================================

const META: Record<FrameworkCode, {
  title:        string;
  subtitle:     string;
  icon:         any;
  shortLabel:   string;  // breadcrumb / list-row label
}> = {
  swot:     { title: 'SWOT',     subtitle: 'Strengths · Weaknesses · Opportunities · Threats',     icon: Grid3x3,  shortLabel: 'SWOT' },
  '6w':     { title: '6W',       subtitle: 'Who · What · When · Where · Why · How',                 icon: HelpCircle, shortLabel: '6W' },
  '2h':     { title: '2H',       subtitle: 'How (cách thực hiện) · How much (định lượng quy mô)',   icon: Wrench,   shortLabel: '2H' },
  fishbone: { title: 'Fishbone (Ishikawa)', subtitle: 'Truy nguyên gốc rễ — nhóm nguyên nhân theo 4M', icon: Fish,     shortLabel: 'Fishbone' },
};

// MoM/YoY + Custom are placeholder cards on the hub — link to legacy mock
// templates so the URL still works. BE-side they're v1 follow-ups.
const PLACEHOLDER_CARDS = [
  { code: 'mom-yoy', title: 'MoM/YoY',  subtitle: 'So sánh tháng-trên-tháng + năm-trên-năm', icon: TrendingUp, href: '/p2/frameworks/mom-yoy-analysis' },
  { code: 'custom',  title: 'Tuỳ chỉnh', subtitle: 'Tự định nghĩa khung cho domain riêng',     icon: Star,        href: '/p2/frameworks/custom-analyst' },
] as const;

// ============================================================================
// Hub — gallery + recent runs
// ============================================================================

export function FrameworksHub() {
  const [catalogue, setCatalogue] = useState<CatalogueItem[]>([]);
  const [recent, setRecent]       = useState<RunListItem[]>([]);
  const [loading, setLoading]     = useState(true);
  const [problem, setProblem]     = useState<ProblemDetails | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [cat, runs] = await Promise.all([
          api<CatalogueResponse>('/api/v1/frameworks/templates'),
          api<RunListResponse>('/api/v1/frameworks?limit=10'),
        ]);
        if (cancelled) return;
        setCatalogue(cat.items ?? []);
        setRecent(runs.items ?? []);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <>
      <PageHeader
        title="Khung phân tích"
        description="4 framework nền tảng + 2 placeholder. Một câu hỏi = một khung (K-10)."
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  'Không tải được catalogue',
              detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}.`,
            }}
          />
        )}

        {/* K-10 banner */}
        <div className="bg-[var(--state-warning)]/8 rounded-lg-custom border border-[var(--state-warning)]/30 p-4 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <ShieldCheck className="w-5 h-5 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <div>
              <p className="font-serif text-sm text-[var(--text-primary)]">K-10 — Một câu hỏi = một khung</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                Kaori không cho phép chạy SWOT + Fishbone song song trên cùng một câu hỏi. Để so sánh nhiều khung,
                hãy tạo nhiều run riêng biệt và đối chiếu từ phần Lịch sử bên dưới.
              </p>
            </div>
          </div>
        </div>

        {/* Gallery — wired frameworks */}
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">Khung sẵn sàng</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {catalogue.map((c) => {
              const m = META[c.code];
              if (!m) return null;
              const Icon = m.icon;
              return (
                <a
                  key={c.code}
                  href={`/p2/frameworks/${c.code === 'fishbone' ? 'fishbone-ishikawa' : c.code}`}
                  className="group bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 hover:border-[var(--primary-gold)] hover:shadow-soft-md transition-all"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center text-[var(--primary-gold-dark)]">
                      <Icon className="w-5 h-5" />
                    </div>
                    <h3 className="font-serif text-base text-[var(--text-primary)]">{c.name}</h3>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] line-clamp-2 mb-3">{c.description}</p>
                  <span className="text-xs text-[var(--primary-gold-dark)] inline-flex items-center font-medium">
                    Mở khung <ArrowRight className="w-3 h-3 ml-1 group-hover:translate-x-0.5 transition-transform" />
                  </span>
                </a>
              );
            })}
          </div>
        </div>

        {/* Placeholder cards — BE deferred to v1 */}
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">
            Sắp ra mắt
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {PLACEHOLDER_CARDS.map((p) => {
              const Icon = p.icon;
              return (
                <a
                  key={p.code}
                  href={p.href}
                  className="bg-[var(--bg-card)]/60 border border-dashed border-[var(--border-color)] rounded-lg-custom p-5 hover:bg-[var(--bg-card)] transition-colors"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className="w-10 h-10 rounded-md-custom bg-[var(--bg-app)] flex items-center justify-center text-[var(--text-secondary)]">
                      <Icon className="w-5 h-5" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-serif text-base text-[var(--text-primary)]">{p.title}</h3>
                    </div>
                    <Badge variant="default">v1</Badge>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] line-clamp-2">{p.subtitle}</p>
                </a>
              );
            })}
          </div>
        </div>

        {/* Recent runs */}
        <div>
          <h2 className="font-serif text-lg text-[var(--text-primary)] mb-3">Lịch sử gần đây</h2>
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
            {loading ? (
              <div className="px-5 py-12 text-center text-[var(--text-secondary)]">
                <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải...
              </div>
            ) : recent.length === 0 ? (
              <div className="px-5 py-12 text-center">
                <Clock className="w-10 h-10 mx-auto text-[var(--text-secondary)]/30 mb-3" />
                <p className="text-sm text-[var(--text-secondary)]">
                  Chưa có run nào — hãy mở một khung phía trên để bắt đầu.
                </p>
              </div>
            ) : (
              <table className="w-full text-sm text-left">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-5 py-3">Khung</th>
                    <th className="px-5 py-3">Câu hỏi / Kết quả</th>
                    <th className="px-5 py-3">Trạng thái</th>
                    <th className="px-5 py-3 text-right">Thời điểm</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-color)]/60">
                  {recent.map((r) => {
                    const m = META[r.framework_code];
                    if (!m) return null;
                    const Icon = m.icon;
                    const detailHref = `/p2/frameworks/${r.framework_code === 'fishbone' ? 'fishbone-ishikawa' : r.framework_code}?run=${r.run_id}`;
                    return (
                      <tr key={r.run_id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                        <td className="px-5 py-4">
                          <span className="inline-flex items-center gap-2 text-xs">
                            <Icon className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                            <span className="font-medium text-[var(--text-primary)]">{m.shortLabel}</span>
                          </span>
                        </td>
                        <td className="px-5 py-4 max-w-md">
                          <a href={detailHref} className="text-sm text-[var(--text-primary)] hover:text-[var(--primary-gold-dark)] line-clamp-1">
                            {r.question}
                          </a>
                          {r.narrative && (
                            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">{r.narrative}</p>
                          )}
                        </td>
                        <td className="px-5 py-4">
                          <StatusBadge status={r.status} />
                        </td>
                        <td className="px-5 py-4 text-xs text-[var(--text-secondary)] text-right">
                          {formatRelative(r.completed_at ?? r.created_at)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Per-framework page — generic shell + framework-specific result renderer
// ============================================================================

interface FrameworkPageProps {
  code: FrameworkCode;
  /** Route segment for breadcrumb back-link — e.g. 'fishbone-ishikawa'. */
  routeSegment: string;
}

export function FrameworkRunPage({ code, routeSegment }: FrameworkPageProps) {
  const m = META[code];

  // Generate-and-poll state
  const [question, setQuestion] = useState('');
  const [sourceRef, setSourceRef] = useState('');
  const [consentExternal, setConsentExternal] = useState(false);

  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<RunDetail | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  // On mount, check ?run=<id> in URL — lets the hub link straight into a
  // completed run.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const r = params.get('run');
    if (r) setRunId(r);
  }, []);

  // Poll the active run.
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const r = await api<RunDetail>(`/api/v1/frameworks/${runId}`);
        if (cancelled) return;
        setRun(r);
        if (r.status === 'ready' || r.status === 'failed') {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
        }
      }
    };
    tick();
    pollRef.current = setInterval(tick, 2000);
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [runId]);

  async function generate() {
    if (!question.trim() || question.trim().length < 3) return;
    setSubmitting(true);
    setProblem(null);
    try {
      const r = await api<{ run_id: string; status: string }>('/api/v1/frameworks/generate', {
        method: 'POST',
        body: JSON.stringify({
          framework_code:   code,
          question:         question.trim(),
          source_ref:       sourceRef.trim() || null,
          consent_external: consentExternal,
        }),
      });
      setRunId(r.run_id);
      setRun(null);                      // clear stale rendering while polling restarts
      // Update URL so refresh keeps the run open. Replace history so
      // back-button still goes to the hub.
      if (typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        url.searchParams.set('run', r.run_id);
        window.history.replaceState({}, '', url);
      }
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setRunId(null);
    setRun(null);
    setProblem(null);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('run');
      window.history.replaceState({}, '', url);
    }
  }

  const Icon = m.icon;

  return (
    <>
      <PageHeader
        title={m.title}
        description={m.subtitle}
        actions={
          <Button variant="tertiary" onClick={() => (window.location.href = '/p2/frameworks')}>
            <ChevronLeft className="w-4 h-4 mr-1" /> Khung khác
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  problem.title ?? 'Không hoàn thành được run',
              detail: problem.detail ?? '',
            }}
          />
        )}

        {/* Form */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-4">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center text-[var(--primary-gold-dark)]">
              <Icon className="w-5 h-5" />
            </div>
            <div>
              <h2 className="font-serif text-base text-[var(--text-primary)]">Câu hỏi của bạn</h2>
              <p className="text-xs text-[var(--text-secondary)]">
                LLM sẽ điền cấu trúc {m.shortLabel} dựa trên dữ liệu tham chiếu (nếu có).
              </p>
            </div>
          </div>

          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={questionPlaceholder(code)}
            rows={3}
            maxLength={2000}
            className="w-full px-3 py-2.5 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] resize-none transition-all"
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5 block">
                Nguồn dữ liệu (tuỳ chọn)
              </span>
              <div className="relative">
                <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={sourceRef}
                  onChange={(e) => setSourceRef(e.target.value)}
                  maxLength={200}
                  placeholder="vd. gold:retail_2026q1"
                  className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 transition-all"
                />
              </div>
            </label>

            <label className="block">
              <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5 block">
                AI (mặc định Qwen nội bộ)
              </span>
              <div className="flex items-center gap-2 h-9">
                <Checkbox
                  checked={consentExternal}
                  onChange={(e) => setConsentExternal(e.target.checked)}
                />
                <span className="text-xs text-[var(--text-primary)] inline-flex items-center gap-1">
                  {consentExternal ? <Globe className="w-3.5 h-3.5 text-[var(--state-warning)]" /> : <Lock className="w-3.5 h-3.5 text-[var(--state-success)]" />}
                  {consentExternal ? 'Cho phép AI ngoài (K-4)' : 'Chỉ Qwen nội bộ'}
                </span>
              </div>
            </label>
          </div>

          <div className="flex items-center justify-between">
            <p className="text-[11px] text-[var(--text-secondary)]">
              {question.length}/2000 ký tự — tối thiểu 3.
            </p>
            <div className="inline-flex items-center gap-2">
              {runId && (
                <Button variant="tertiary" onClick={reset}>
                  <RefreshCw className="w-3.5 h-3.5 mr-1" /> Run mới
                </Button>
              )}
              <Button
                variant="primary"
                onClick={generate}
                disabled={submitting || question.trim().length < 3}
              >
                {submitting
                  ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> Đang gửi...</>
                  : <><Sparkles className="w-4 h-4 mr-1.5" /> Phân tích</>}
              </Button>
            </div>
          </div>
        </div>

        {/* Status / result */}
        {runId && (
          <RunStatusPanel
            run={run}
            framework={code}
          />
        )}
      </div>
    </>
  );
}

function questionPlaceholder(code: FrameworkCode): string {
  switch (code) {
    case 'swot':     return 'vd. Đối thủ X giảm giá 8% — chiến lược giữ thị phần Q2 thế nào?';
    case '6w':       return 'vd. Vì sao churn vùng APAC tăng 12% trong Q1?';
    case '2h':       return 'vd. Triển khai loyalty mới — bao nhiêu khách bị ảnh hưởng và chi phí?';
    case 'fishbone': return 'vd. Doanh thu kênh A giảm 20% — gốc rễ ở đâu?';
  }
}

// ============================================================================
// Status panel + result renderer
// ============================================================================

function RunStatusPanel({ run, framework }: { run: RunDetail | null; framework: FrameworkCode }) {
  if (!run) {
    return (
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-8 text-center shadow-soft-sm">
        <Loader2 className="w-6 h-6 mx-auto text-[var(--primary-gold-dark)] animate-spin mb-3" />
        <p className="text-sm text-[var(--text-secondary)]">Đang khởi tạo run...</p>
      </div>
    );
  }

  if (run.status === 'queued' || run.status === 'running') {
    return (
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-8 text-center shadow-soft-sm">
        <Loader2 className="w-6 h-6 mx-auto text-[var(--primary-gold-dark)] animate-spin mb-3" />
        <p className="text-sm text-[var(--text-primary)] font-medium">
          {run.status === 'queued' ? 'Đã xếp hàng — đang chờ worker' : 'Đang phân tích bằng LLM'}
        </p>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          Thường mất 5-15 giây với Qwen nội bộ. Trang sẽ tự cập nhật.
        </p>
      </div>
    );
  }

  if (run.status === 'failed') {
    return (
      <div className="bg-[var(--state-error)]/8 border border-[var(--state-error)]/30 rounded-lg-custom p-5 shadow-soft-sm">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-[var(--state-error)] shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--text-primary)]">Run thất bại</p>
            <p className="text-xs text-[var(--text-secondary)] mt-1 break-words">
              {run.last_error || 'Không có chi tiết lỗi.'}
            </p>
            <p className="text-[11px] text-[var(--text-secondary)] mt-2">
              Hãy chỉnh lại câu hỏi hoặc bật "AI ngoài" rồi thử lại — Qwen 7B đôi khi sinh JSON sai schema.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // status === 'ready'
  if (!run.content_json) {
    return (
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <p className="text-sm text-[var(--text-secondary)]">Run hoàn thành nhưng không có nội dung — vui lòng tạo run mới.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {run.narrative && (
        <div className="bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 rounded-lg-custom p-4 shadow-soft-sm">
          <div className="flex items-start gap-2">
            <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <p className="text-sm text-[var(--text-primary)]">{run.narrative}</p>
          </div>
        </div>
      )}

      {framework === 'swot'     && <SwotResult content={run.content_json} />}
      {framework === '6w'       && <SixWResult content={run.content_json} />}
      {framework === '2h'       && <TwoHResult content={run.content_json} />}
      {framework === 'fishbone' && <FishboneResult content={run.content_json} />}
    </div>
  );
}

// ============================================================================
// SWOT — 4 quadrant grid
// ============================================================================

function SwotResult({ content }: { content: any }) {
  const quadrants: Array<{ key: string; label: string; tone: string; data: any }> = [
    { key: 'strengths',     label: 'Strengths',     tone: 'text-[var(--state-success)] border-[var(--state-success)]/30 bg-[var(--state-success)]/5', data: content?.strengths },
    { key: 'weaknesses',    label: 'Weaknesses',    tone: 'text-[var(--state-warning)] border-[var(--state-warning)]/30 bg-[var(--state-warning)]/5', data: content?.weaknesses },
    { key: 'opportunities', label: 'Opportunities', tone: 'text-[var(--primary-gold-dark)] border-[var(--primary-gold)]/40 bg-[var(--primary-gold)]/5', data: content?.opportunities },
    { key: 'threats',       label: 'Threats',       tone: 'text-[var(--state-error)] border-[var(--state-error)]/30 bg-[var(--state-error)]/5', data: content?.threats },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {quadrants.map((q) => (
        <div key={q.key} className={cn('rounded-lg-custom border p-4 shadow-soft-sm', q.tone.split(' ').slice(2).join(' '), q.tone.split(' ')[1])}>
          <h3 className={cn('font-serif text-sm font-medium mb-3', q.tone.split(' ')[0])}>{q.label}</h3>
          <ul className="space-y-2">
            {Array.isArray(q.data?.items) && q.data.items.length > 0 ? q.data.items.map((it: any, idx: number) => (
              <li key={idx} className="text-sm text-[var(--text-primary)] flex items-start gap-2">
                <span className="font-mono text-[10px] text-[var(--text-secondary)] mt-0.5 shrink-0 w-12 text-right">
                  {Math.round((it.confidence ?? 0) * 100)}%
                </span>
                <span>{it.text}</span>
              </li>
            )) : (
              <li className="text-xs text-[var(--text-secondary)] italic">Không có ý.</li>
            )}
          </ul>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// 6W — 6 fields list
// ============================================================================

function SixWResult({ content }: { content: any }) {
  const fields: Array<{ key: string; label: string }> = [
    { key: 'who',   label: 'Who · Ai' },
    { key: 'what',  label: 'What · Cái gì' },
    { key: 'when',  label: 'When · Khi nào' },
    { key: 'where', label: 'Where · Ở đâu' },
    { key: 'why',   label: 'Why · Vì sao' },
    { key: 'how',   label: 'How · Như thế nào' },
  ];
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] divide-y divide-[var(--border-color)]/60 shadow-soft-sm">
      {fields.map((f) => (
        <div key={f.key} className="px-5 py-4">
          <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1">{f.label}</p>
          <p className="text-sm text-[var(--text-primary)] leading-relaxed">{content?.[f.key] ?? '—'}</p>
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// 2H — How section + How much section
// ============================================================================

function TwoHResult({ content }: { content: any }) {
  const how = content?.how ?? {};
  const hm  = content?.how_much ?? {};
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <h3 className="font-serif text-sm font-medium text-[var(--text-primary)] mb-3 inline-flex items-center gap-2">
          <Wrench className="w-4 h-4 text-[var(--primary-gold-dark)]" /> How — Cách thực hiện
        </h3>
        <p className="text-sm text-[var(--text-primary)] mb-3">{how.approach ?? '—'}</p>
        <ol className="list-decimal list-inside space-y-1.5 text-sm text-[var(--text-primary)]">
          {Array.isArray(how.steps) && how.steps.length > 0 ? how.steps.map((s: string, i: number) => (
            <li key={i}>{s}</li>
          )) : (
            <li className="text-xs text-[var(--text-secondary)] italic list-none">Không có bước.</li>
          )}
        </ol>
      </div>

      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <h3 className="font-serif text-sm font-medium text-[var(--text-primary)] mb-3 inline-flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[var(--primary-gold-dark)]" /> How much — Định lượng
        </h3>
        <p className="font-serif text-2xl text-[var(--text-primary)] mb-1">
          {hm.estimate ?? '—'} <span className="text-base text-[var(--text-secondary)]">{hm.unit ?? ''}</span>
        </p>
        <p className="text-xs text-[var(--text-secondary)] mb-3">
          Confidence: {typeof hm.confidence === 'number' ? `${Math.round(hm.confidence * 100)}%` : '—'}
        </p>
        {Array.isArray(hm.assumptions) && hm.assumptions.length > 0 && (
          <>
            <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5">Giả định</p>
            <ul className="list-disc list-inside space-y-0.5 text-xs text-[var(--text-secondary)]">
              {hm.assumptions.map((a: string, i: number) => <li key={i}>{a}</li>)}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Fishbone — categories grid + root cause callout
// ============================================================================

function FishboneResult({ content }: { content: any }) {
  const categories: any[] = Array.isArray(content?.categories) ? content.categories : [];
  return (
    <div className="space-y-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
        <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1">Vấn đề</p>
        <p className="text-sm text-[var(--text-primary)] font-medium">{content?.problem ?? '—'}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {categories.map((cat, i) => (
          <div key={i} className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm">
            <h3 className="font-serif text-sm font-medium text-[var(--text-primary)] mb-3 inline-flex items-center gap-2">
              <Fish className="w-4 h-4 text-[var(--primary-gold-dark)]" /> {cat.name}
            </h3>
            <ul className="space-y-2">
              {(Array.isArray(cat.causes) ? cat.causes : []).map((c: any, idx: number) => (
                <li key={idx} className="flex items-start gap-2 text-sm">
                  <DepthBadge depth={c.depth} />
                  <span className="text-[var(--text-primary)]">{c.text}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="bg-[var(--state-error)]/5 border border-[var(--state-error)]/30 rounded-lg-custom p-5 shadow-soft-sm">
        <p className="text-[11px] uppercase tracking-wider font-medium text-[var(--state-error)] mb-1">Giả thuyết gốc rễ</p>
        <p className="text-sm text-[var(--text-primary)]">{content?.root_cause_hypothesis ?? '—'}</p>
      </div>
    </div>
  );
}

function DepthBadge({ depth }: { depth: number | undefined }) {
  const d = Number(depth) || 1;
  const label = d === 1 ? 'triệu chứng' : d === 2 ? 'trực tiếp' : 'gốc rễ';
  const tone = d === 1
    ? 'bg-[var(--state-warning)]/10 text-[var(--state-warning)]'
    : d === 2
      ? 'bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)]'
      : 'bg-[var(--state-error)]/10 text-[var(--state-error)]';
  return (
    <span className={cn('font-mono text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-sm-custom shrink-0 mt-0.5', tone)}>
      {label}
    </span>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function StatusBadge({ status }: { status: RunStatus }) {
  if (status === 'ready')   return <Badge variant="success">Hoàn thành</Badge>;
  if (status === 'failed')  return <Badge variant="error">Thất bại</Badge>;
  if (status === 'running') return <Badge variant="info">Đang chạy</Badge>;
  return <Badge variant="default">Đang chờ</Badge>;
}

function formatRelative(iso: string): string {
  const diff = Date.now() - +new Date(iso);
  if (diff < 60_000)        return 'vừa xong';
  if (diff < 3_600_000)     return `${Math.round(diff / 60_000)} phút trước`;
  if (diff < 86_400_000)    return `${Math.round(diff / 3_600_000)} giờ trước`;
  if (diff < 7 * 86_400_000) return `${Math.round(diff / 86_400_000)} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}
