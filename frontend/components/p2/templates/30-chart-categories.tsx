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
import { useT } from '@/lib/i18n/provider';
type Category = 'comparison' | 'composition' | 'distribution' | 'relationship';

interface ChartItem {
  kind:           string;
  labelKey:       string;
  descriptionKey: string;
  useCaseKey:     string;
  icon:           any;
}

const CATALOGUE: Record<Category, { titleKey: string; descriptionKey: string; items: ChartItem[] }> = {
  comparison: {
    titleKey:       'templates30ChartCategories.catComparisonTitle',
    descriptionKey: 'templates30ChartCategories.catComparisonDesc',
    items: [
      { kind: 'bar',         labelKey: 'templates30ChartCategories.barLabel',        descriptionKey: 'templates30ChartCategories.barDesc',        useCaseKey: 'templates30ChartCategories.barUseCase',        icon: BarChart2 },
      { kind: 'column',      labelKey: 'templates30ChartCategories.columnLabel',     descriptionKey: 'templates30ChartCategories.columnDesc',     useCaseKey: 'templates30ChartCategories.columnUseCase',     icon: BarChart },
      { kind: 'stacked_bar', labelKey: 'templates30ChartCategories.stackedBarLabel', descriptionKey: 'templates30ChartCategories.stackedBarDesc', useCaseKey: 'templates30ChartCategories.stackedBarUseCase', icon: Layers },
      { kind: 'line',        labelKey: 'templates30ChartCategories.lineLabel',       descriptionKey: 'templates30ChartCategories.lineDesc',       useCaseKey: 'templates30ChartCategories.lineUseCase',       icon: LineChart },
      { kind: 'area',        labelKey: 'templates30ChartCategories.areaLabel',       descriptionKey: 'templates30ChartCategories.areaDesc',       useCaseKey: 'templates30ChartCategories.areaUseCase',       icon: AreaChart },
    ],
  },
  composition: {
    titleKey:       'templates30ChartCategories.catCompositionTitle',
    descriptionKey: 'templates30ChartCategories.catCompositionDesc',
    items: [
      { kind: 'pie',     labelKey: 'templates30ChartCategories.pieLabel',     descriptionKey: 'templates30ChartCategories.pieDesc',     useCaseKey: 'templates30ChartCategories.pieUseCase',     icon: PieChart },
      { kind: 'donut',   labelKey: 'templates30ChartCategories.donutLabel',   descriptionKey: 'templates30ChartCategories.donutDesc',   useCaseKey: 'templates30ChartCategories.donutUseCase',   icon: PieChart },
      { kind: 'treemap', labelKey: 'templates30ChartCategories.treemapLabel', descriptionKey: 'templates30ChartCategories.treemapDesc', useCaseKey: 'templates30ChartCategories.treemapUseCase', icon: Box },
      { kind: 'funnel',  labelKey: 'templates30ChartCategories.funnelLabel',  descriptionKey: 'templates30ChartCategories.funnelDesc',  useCaseKey: 'templates30ChartCategories.funnelUseCase',  icon: TrendingDown },
    ],
  },
  distribution: {
    titleKey:       'templates30ChartCategories.catDistributionTitle',
    descriptionKey: 'templates30ChartCategories.catDistributionDesc',
    items: [
      { kind: 'histogram', labelKey: 'templates30ChartCategories.histogramLabel', descriptionKey: 'templates30ChartCategories.histogramDesc', useCaseKey: 'templates30ChartCategories.histogramUseCase', icon: BarChart },
      { kind: 'box_plot',  labelKey: 'templates30ChartCategories.boxPlotLabel',   descriptionKey: 'templates30ChartCategories.boxPlotDesc',   useCaseKey: 'templates30ChartCategories.boxPlotUseCase',   icon: Hash },
      { kind: 'density',   labelKey: 'templates30ChartCategories.densityLabel',   descriptionKey: 'templates30ChartCategories.densityDesc',   useCaseKey: 'templates30ChartCategories.densityUseCase',   icon: Activity },
    ],
  },
  relationship: {
    titleKey:       'templates30ChartCategories.catRelationshipTitle',
    descriptionKey: 'templates30ChartCategories.catRelationshipDesc',
    items: [
      { kind: 'scatter', labelKey: 'templates30ChartCategories.scatterLabel', descriptionKey: 'templates30ChartCategories.scatterDesc', useCaseKey: 'templates30ChartCategories.scatterUseCase', icon: ScatterChart },
      { kind: 'bubble',  labelKey: 'templates30ChartCategories.bubbleLabel',  descriptionKey: 'templates30ChartCategories.bubbleDesc',  useCaseKey: 'templates30ChartCategories.bubbleUseCase',  icon: Box },
      { kind: 'heatmap', labelKey: 'templates30ChartCategories.heatmapLabel', descriptionKey: 'templates30ChartCategories.heatmapDesc', useCaseKey: 'templates30ChartCategories.heatmapUseCase', icon: Map },
    ],
  },
};

const ALL_CATEGORIES: Category[] = ['comparison', 'composition', 'distribution', 'relationship'];

export default function ChartCategoriesPage() {
  const t = useT();
  const [active, setActive] = useState<Category>('comparison');
  const cat = CATALOGUE[active];

  return (
    <>
      <PageHeader
        title={t('templates30ChartCategories.pageTitle')}
        description={t('templates30ChartCategories.pageDescription')}
        actions={<Badge variant="info">{t('templates30ChartCategories.phase2Badge')}</Badge>}
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
                  {t(CATALOGUE[c].titleKey)}
                </p>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">
                  {t(CATALOGUE[c].descriptionKey)}
                </p>
              </button>
            );
          })}
        </div>

        {/* Category detail */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60">
            <h3 className="font-serif text-lg text-[var(--text-primary)]">{t(cat.titleKey)}</h3>
            <p className="text-sm text-[var(--text-secondary)] mt-1">{t(cat.descriptionKey)}</p>
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
                    {t(item.labelKey)}
                  </p>
                  <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{t(item.descriptionKey)}</p>
                  <div className="mt-3 pt-3 border-t border-[var(--border-color)]/60">
                    <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{t('templates30ChartCategories.exampleLabel')}</p>
                    <p className="text-xs text-[var(--text-primary)] mt-1">{t(item.useCaseKey)}</p>
                  </div>
                  <div className="mt-3 flex items-center text-xs font-medium text-[var(--primary-gold-dark)] group-hover:translate-x-0.5 transition-transform">
                    {t('templates30ChartCategories.openInPicker')}
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
              <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates30ChartCategories.teaserTitle')}</h3>
              <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed">
                {t('templates30ChartCategories.teaserPre')} <span className="font-medium text-[var(--text-primary)]">{t('templates30ChartCategories.teaserSpan')}</span>{' '}
                {t('templates30ChartCategories.teaserPost')}
              </p>
            </div>
            <Button variant="secondary" onClick={() => (window.location.href = '/p2/charts/picker')}>
              {t('templates30ChartCategories.openChartPicker')}
              <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}
