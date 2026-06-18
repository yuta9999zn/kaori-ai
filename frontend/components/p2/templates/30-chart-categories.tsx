// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 30. /p2/charts/category — Chart Catalogue by Category (Phase 2 🔵)
// ----------------------------------------------------------------------------
// Browse the 15 chart kinds grouped by analytical purpose, with a sample
// preview per kind. Phase 2 will let users save chart "templates" (combo of
// kind + default fields + theme) — that work is out of scope for Phase 1.
//
// For Phase 1, this is a learning / reference page that links each kind to
// the picker (file 29). No backend wiring yet.
// ============================================================================

import React, { useState } from 'react';
import {
  BarChart2, BarChart, LineChart, AreaChart, PieChart, ScatterChart,
  Activity, TrendingDown, Layers, Hash, Map, Box, ChevronRight, Sparkles,
} from 'lucide-react';

import { Badge, Button, cn } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Category = 'comparison' | 'composition' | 'distribution' | 'relationship';

interface ChartItem {
  kind:        string;
  label:       string;
  description: string;
  use_case:    string;
  icon:        any;
}

const CATALOGUE: Record<Category, { title: string; description: string; items: ChartItem[] }> = {
  comparison: {
    title:       'So sánh',
    description: 'Đối chiếu giá trị giữa các nhóm hoặc theo thời gian',
    items: [
      { kind: 'bar',         label: 'Cột ngang',  description: 'So sánh giá trị giữa các category',  use_case: 'Doanh thu theo chi nhánh', icon: BarChart2 },
      { kind: 'column',      label: 'Cột dọc',    description: 'Cột dọc — mặc định cho category',     use_case: 'Số khách theo tháng',     icon: BarChart },
      { kind: 'stacked_bar', label: 'Cột chồng',  description: 'Nhiều series cùng trục',                use_case: 'Doanh thu theo product line × tháng', icon: Layers },
      { kind: 'line',        label: 'Đường',      description: 'Xu hướng theo thời gian',              use_case: 'MAU 12 tháng',           icon: LineChart },
      { kind: 'area',        label: 'Vùng',       description: 'Xu hướng cumulative',                   use_case: 'Khách lũy kế',           icon: AreaChart },
    ],
  },
  composition: {
    title:       'Tỉ trọng',
    description: 'Một tổng thể được chia thành các phần như thế nào',
    items: [
      { kind: 'pie',     label: 'Tròn',       description: 'Tỉ trọng cho ≤6 nhóm',                use_case: 'Cơ cấu doanh thu theo segment', icon: PieChart },
      { kind: 'donut',   label: 'Tròn rỗng',  description: 'Pie + tổng giữa',                       use_case: 'Cơ cấu khách + tổng',           icon: PieChart },
      { kind: 'treemap', label: 'Treemap',    description: 'Phân cấp theo diện tích',              use_case: 'Cơ cấu chi phí phòng ban',      icon: Box },
      { kind: 'funnel',  label: 'Funnel',     description: 'Conversion qua các bước',              use_case: 'Bước trong sales funnel',       icon: TrendingDown },
    ],
  },
  distribution: {
    title:       'Phân phối',
    description: 'Cách giá trị phân bố trên một dải số',
    items: [
      { kind: 'histogram', label: 'Histogram',  description: 'Tần suất theo bin',                    use_case: 'Phân phối giá trị đơn hàng',    icon: BarChart },
      { kind: 'box_plot',  label: 'Box plot',   description: 'Median + quartiles + outlier',         use_case: 'So sánh phân phối lương',       icon: Hash },
      { kind: 'density',   label: 'Density',    description: 'Phân phối liên tục (KDE)',             use_case: 'Phân phối tuổi khách',          icon: Activity },
    ],
  },
  relationship: {
    title:       'Tương quan',
    description: 'Hai (hoặc ba) biến quan hệ với nhau ra sao',
    items: [
      { kind: 'scatter', label: 'Scatter', description: 'Tương quan 2 biến',                      use_case: 'Marketing spend vs conversion', icon: ScatterChart },
      { kind: 'bubble',  label: 'Bubble',  description: 'Scatter + size theo biến thứ 3',       use_case: 'Spend × ROI × volume',          icon: Box },
      { kind: 'heatmap', label: 'Heatmap', description: 'Mật độ theo 2 chiều rời rạc',           use_case: 'Hour-of-day × day-of-week',     icon: Map },
    ],
  },
};

const ALL_CATEGORIES: Category[] = ['comparison', 'composition', 'distribution', 'relationship'];

export default function ChartCategoriesPage() {
  const [active, setActive] = useState<Category>('comparison');
  const cat = CATALOGUE[active];

  return (
    <>
      <PageHeader
        title="Biểu đồ theo loại"
        description="Tài liệu 15 loại biểu đồ chia theo mục đích phân tích. Phase 2 sẽ thêm tính năng lưu template."
        actions={<Badge variant="info">Phase 2 · Lưu template</Badge>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-5">
        {/* Category tabs */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-2 shadow-soft-sm flex flex-wrap gap-1">
          {ALL_CATEGORIES.map((c) => {
            const isActive = c === active;
            return (
              <button
                key={c}
                type="button"
                onClick={() => setActive(c)}
                className={cn(
                  'flex-1 min-w-[140px] px-4 py-3 rounded-md-custom text-left transition-colors',
                  isActive
                    ? 'bg-[var(--primary-gold)]/10 border border-[var(--primary-gold)]/30'
                    : 'border border-transparent hover:bg-[var(--bg-app)]/50',
                )}
              >
                <p className={cn(
                  'font-serif text-sm',
                  isActive ? 'text-[var(--text-primary)]' : 'text-[var(--text-secondary)]',
                )}>
                  {CATALOGUE[c].title}
                </p>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">
                  {CATALOGUE[c].description}
                </p>
              </button>
            );
          })}
        </div>

        {/* Category detail */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{cat.title}</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">{cat.description}</p>
          </div>

          <div className="p-5 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {cat.items.map((item) => {
              const Icon = item.icon;
              return (
                <a
                  key={item.kind}
                  href={`/p2/charts/picker?kind=${item.kind}`}
                  className="group block bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/50 hover:shadow-soft-sm transition-all p-4"
                >
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
                      <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                    </div>
                    <Badge variant="default">{item.kind}</Badge>
                  </div>
                  <p className="font-medium text-sm text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors">
                    {item.label}
                  </p>
                  <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{item.description}</p>
                  <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60">
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">Ví dụ</p>
                    <p className="text-xs text-[var(--text-primary)] mt-1">{item.use_case}</p>
                  </div>
                  <div className="mt-3 flex items-center text-xs font-medium text-[var(--primary-gold-dark)] group-hover:translate-x-0.5 transition-transform">
                    Mở trong picker
                    <ChevronRight className="w-3 h-3 ml-0.5" />
                  </div>
                </a>
              );
            })}
          </div>
        </div>

        {/* Phase 2 teaser */}
        <div className="bg-[var(--primary-gold)]/8 rounded-lg-custom border border-[var(--primary-gold)]/30 p-5 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-1" />
            <div className="flex-1">
              <h3 className="font-serif text-base text-[var(--text-primary)]">Phase 2 — Chart Templates</h3>
              <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">
                Sắp tới bạn sẽ lưu được tổ hợp <span className="font-medium text-[var(--text-primary)]">loại + cột mặc định + theme</span> thành
                template, dùng lại cho mọi pipeline mới mà không cần config từ đầu.
              </p>
            </div>
            <Button variant="secondary" onClick={() => (window.location.href = '/p2/charts/picker')}>
              Mở Chart Picker
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
