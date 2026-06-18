// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 50. /p2/reports/templates — Report Templates Catalog (F-038 🔵 Phase 2 — UI mock only)
// ----------------------------------------------------------------------------
// Catalog mẫu báo cáo (built-in từ Kaori + custom của workspace). Người dùng:
//   - Lọc theo ngành (Bán lẻ · Sản xuất · Tài chính · Dịch vụ · Marketing).
//   - Toggle giữa "Mẫu Kaori" (built-in) vs "Của workspace" (đã tự lưu).
//   - Bấm "Dùng mẫu" → clone vào Builder (file 49) với block đã preset.
//
// Wire (Phase 2): `GET /api/v1/reports/templates?scope=builtin|workspace`
// + `POST /api/v1/reports/templates/{id}/clone`. Mặc định show fixture demo
// nếu endpoint chưa sẵn sàng.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  ShoppingBag, Factory, Landmark, Briefcase, Megaphone, Layers as AllIcon,
  Search, Sparkles, ArrowRight, BookMarked, FileText, Plus, ArrowLeft,
  Loader2, User, Globe, ShieldCheck,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type Scope    = 'builtin' | 'workspace';
type Industry = 'all' | 'retail' | 'manufacturing' | 'finance' | 'services' | 'marketing';

interface IndustryMeta {
  code:  Industry;
  label: string;
  icon:  any;
}

const INDUSTRIES: IndustryMeta[] = [
  { code: 'all',           label: 'Tất cả',     icon: AllIcon },
  { code: 'retail',        label: 'Bán lẻ',     icon: ShoppingBag },
  { code: 'manufacturing', label: 'Sản xuất',   icon: Factory },
  { code: 'finance',       label: 'Tài chính',  icon: Landmark },
  { code: 'services',      label: 'Dịch vụ',    icon: Briefcase },
  { code: 'marketing',     label: 'Marketing',  icon: Megaphone },
];

interface TemplateRow {
  id:           string;
  name:         string;
  description:  string;
  industry:     Industry;
  block_count:  number;
  scope:        Scope;
  author:       string;
  used_count?:  number;
}

const MOCK_TEMPLATES: TemplateRow[] = [
  // Built-in
  { id: 'tpl_retail_monthly',  name: 'Doanh thu bán lẻ tháng',          description: 'KPI doanh thu + so sánh cửa hàng + top SKU.',                industry: 'retail',        block_count: 8, scope: 'builtin',   author: 'Kaori',      used_count: 1240 },
  { id: 'tpl_retail_cohort',   name: 'Phân tích cohort bán lẻ',         description: 'Retention 6 tháng + LTV theo nguồn khách.',                  industry: 'retail',        block_count: 6, scope: 'builtin',   author: 'Kaori',      used_count: 412 },
  { id: 'tpl_mfg_oee',         name: 'OEE máy móc theo dây chuyền',      description: 'Availability · Performance · Quality + alert dừng máy.',     industry: 'manufacturing', block_count: 9, scope: 'builtin',   author: 'Kaori',      used_count: 287 },
  { id: 'tpl_mfg_inventory',   name: 'Tỷ suất tồn kho ngành SX',        description: 'Days of Inventory + slow-moving + reorder point.',           industry: 'manufacturing', block_count: 7, scope: 'builtin',   author: 'Kaori',      used_count: 198 },
  { id: 'tpl_fin_pnl',         name: 'P&L tóm tắt cho ban GĐ',          description: 'Doanh thu · giá vốn · biên lãi · top 5 chi phí.',           industry: 'finance',       block_count: 8, scope: 'builtin',   author: 'Kaori',      used_count: 632 },
  { id: 'tpl_fin_aging',       name: 'Aging công nợ phải thu',          description: 'Phân nhóm tuổi nợ + cảnh báo vượt 90 ngày.',                  industry: 'finance',       block_count: 5, scope: 'builtin',   author: 'Kaori',      used_count: 154 },
  { id: 'tpl_svc_csat',        name: 'CSAT + NPS dịch vụ',              description: 'Trend NPS + driver phản hồi + alert dropped score.',         industry: 'services',      block_count: 6, scope: 'builtin',   author: 'Kaori',      used_count: 221 },
  { id: 'tpl_mkt_attribution', name: 'Marketing attribution multi-touch', description: 'CPA · CPL · ROI theo kênh · last-touch vs linear vs Markov.', industry: 'marketing',     block_count: 8, scope: 'builtin',   author: 'Kaori',      used_count: 309 },
  // Workspace
  { id: 'tpl_ws_q1_review',    name: 'Q1 2026 — Review nội bộ Acme',    description: 'Bản tuỳ chỉnh của Acme Corp cho cuộc họp QBR.',              industry: 'all',           block_count: 12, scope: 'workspace', author: 'minh@acme.vn', used_count: 4 },
  { id: 'tpl_ws_apac_roi',     name: 'ROI APAC — chi nhánh',            description: 'Mẫu của workspace, lock vào dataset apac_roi_gold.',         industry: 'finance',       block_count: 7, scope: 'workspace', author: 'lan@acme.vn',  used_count: 3 },
];

// ============================================================================
// Page
// ============================================================================

export default function ReportTemplatesPage() {
  const [templates, setTemplates] = useState<TemplateRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  const [scope, setScope] = useState<Scope>('builtin');
  const [industry, setIndustry] = useState<Industry>('all');
  const [search, setSearch] = useState('');
  const [cloning, setCloning] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<{ items: TemplateRow[] }>('/api/v1/reports/templates?limit=200');
        if (!cancelled) setTemplates(data.items ?? []);
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          setTemplates(MOCK_TEMPLATES);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return templates.filter((t) => {
      if (t.scope !== scope) return false;
      if (industry !== 'all' && t.industry !== industry && t.industry !== 'all') return false;
      if (q && !t.name.toLowerCase().includes(q) && !t.description.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [templates, scope, industry, search]);

  async function onClone(t: TemplateRow) {
    setCloning(t.id);
    try {
      const data = await api<{ id: string }>(`/api/v1/reports/templates/${t.id}/clone`, { method: 'POST' });
      window.location.href = `/p2/reports/builder?from_template=${data.id}`;
    } catch {
      // Phase 2: navigate anyway with template hint so Builder loads fixture.
      window.location.href = `/p2/reports/builder?from_template=${t.id}`;
    } finally {
      setCloning(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Mẫu báo cáo"
        description="Bộ template dựng sẵn theo ngành. Bấm 'Dùng mẫu' để clone vào Builder."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-038</Badge>
            <a href="/p2/reports">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Về danh sách</Button>
            </a>
            <a href="/p2/reports/builder">
              <Button variant="primary" size="md">
                <Plus className="w-4 h-4 mr-2" /> Tạo từ trống
              </Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  'Đang xem catalog demo',
              detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}. Hiển thị ${MOCK_TEMPLATES.length} mẫu fixture cho tới khi /api/v1/reports/templates sẵn sàng.`,
            }}
          />
        )}

        {/* Scope tabs */}
        <div className="flex items-center gap-1 border-b border-[var(--border-color)]">
          {[
            { value: 'builtin' as Scope,   label: 'Mẫu Kaori',    icon: Globe },
            { value: 'workspace' as Scope, label: 'Của workspace', icon: User },
          ].map((s) => {
            const active = scope === s.value;
            const Icon = s.icon;
            const count = templates.filter((t) => t.scope === s.value).length;
            return (
              <button
                key={s.value}
                onClick={() => setScope(s.value)}
                className={cn(
                  'flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
                  active
                    ? 'border-[var(--primary-gold)] text-[var(--text-primary)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                )}
              >
                <Icon className="w-4 h-4" />
                {s.label}
                <Badge variant="default">{count}</Badge>
              </button>
            );
          })}
        </div>

        {/* Toolbar: industry pills + search */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex flex-col lg:flex-row items-stretch lg:items-center gap-3 shadow-soft-sm">
          <div className="flex flex-wrap items-center gap-1.5 flex-1">
            {INDUSTRIES.map((i) => {
              const Icon = i.icon;
              const active = industry === i.code;
              return (
                <button
                  key={i.code}
                  onClick={() => setIndustry(i.code)}
                  className={cn(
                    'inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-sm-custom transition-colors',
                    active
                      ? 'bg-[var(--primary-gold)]/15 text-[var(--text-primary)] border border-[var(--primary-gold)]/40'
                      : 'text-[var(--text-secondary)] hover:bg-[var(--bg-app)] border border-transparent',
                  )}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {i.label}
                </button>
              );
            })}
          </div>
          <div className="relative w-full lg:w-72">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo tên mẫu..."
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all"
            />
          </div>
        </div>

        {/* Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-20 text-[var(--text-secondary)]">
            <Loader2 className="w-5 h-5 animate-spin mr-2" /> Đang tải catalog...
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom py-16 text-center">
            <BookMarked className="w-12 h-12 mx-auto text-[var(--text-secondary)]/40 mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">
              {scope === 'workspace'
                ? 'Workspace chưa có mẫu nào. Vào Builder, bấm "Lưu thành mẫu" để tạo.'
                : 'Không có mẫu khớp bộ lọc.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((t) => (
              <TemplateCard
                key={t.id}
                tpl={t}
                cloning={cloning === t.id}
                onClone={() => onClone(t)}
              />
            ))}
          </div>
        )}

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Clone mẫu sẽ tạo bản sao block — chỉnh sửa không ảnh hưởng nguồn. Mọi mẫu Kaori đã qua kiểm duyệt nội dung
            (không có dataset PII, không có narrative cố ý dẫn dắt thiên lệch — K-6 transparency).
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Card
// ============================================================================

function TemplateCard({
  tpl: t, cloning, onClone,
}: { tpl: TemplateRow; cloning: boolean; onClone: () => void }) {
  const industry = INDUSTRIES.find((i) => i.code === t.industry) ?? INDUSTRIES[0];
  const Icon = industry.icon;

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm hover:border-[var(--primary-gold)]/40 hover:shadow-soft-md transition-all flex flex-col">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center shrink-0">
          <Icon className="w-5 h-5 text-[var(--primary-gold-dark)]" />
        </div>
        <Badge variant={t.scope === 'builtin' ? 'info' : 'current'}>
          {t.scope === 'builtin' ? 'Kaori' : 'Workspace'}
        </Badge>
      </div>

      <h3 className="font-serif text-base text-[var(--text-primary)]">{t.name}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed line-clamp-3 flex-1">{t.description}</p>

      <div className="mt-4 pt-3 border-t border-[var(--border-color)]/60 space-y-1.5">
        <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
          <span className="inline-flex items-center gap-1"><FileText className="w-3 h-3" /> {t.block_count} block</span>
          <span>{industry.label}</span>
        </div>
        <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
          <span>Tác giả: <span className="text-[var(--text-primary)]">{t.author}</span></span>
          {t.used_count != null && <span>Đã dùng {t.used_count.toLocaleString('vi-VN')}×</span>}
        </div>
      </div>

      <Button
        variant="primary"
        size="sm"
        onClick={onClone}
        isLoading={cloning}
        className="mt-4"
      >
        <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Dùng mẫu
        <ArrowRight className="w-3.5 h-3.5 ml-1.5" />
      </Button>
    </div>
  );
}
