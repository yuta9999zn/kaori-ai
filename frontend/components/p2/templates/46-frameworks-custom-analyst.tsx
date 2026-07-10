// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 46. /p2/frameworks/custom — Custom Framework Builder (F-034 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Cho phép MANAGER tự định nghĩa khung phân tích industry-specific:
//   - Đặt tên + mô tả ngắn
//   - Liệt kê N section/quadrant (mỗi cái có question prompt)
//   - Chọn output format (bullets / narrative / KPI)
//   - Save → registry, có thể chọn ở Insight Generator + Pipeline step-4
//
// Phase 2 only. K-10 vẫn áp dụng (1 framework / 1 question).
// ============================================================================

import React, { useState } from 'react';
import {
  ChevronLeft, Settings2, Plus, X, Save, Sparkles, ShieldCheck,
  GripVertical,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
interface Section {
  id:        string;
  title:     string;
  prompt:    string;
  output:    'bullets' | 'narrative' | 'kpi';
}

const newSection = (): Section => ({
  id:     `s-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
  title:  '',
  prompt: '',
  output: 'bullets',
});

export default function CustomFrameworkPage() {
  const t = useT();
  const [name,        setName]        = useState('');
  const [description, setDescription] = useState('');
  const [sections,    setSections]    = useState<Section[]>([newSection(), newSection()]);
  const [saving,      setSaving]      = useState(false);
  const [problem,     setProblem]     = useState<ProblemDetails | null>(null);
  const [success,     setSuccess]     = useState<string | null>(null);

  function update(id: string, patch: Partial<Section>) {
    setSections((prev) => prev.map((s) => s.id === id ? { ...s, ...patch } : s));
  }
  function add()    { setSections((prev) => [...prev, newSection()]); }
  function remove(id: string) {
    if (sections.length <= 2) return;
    setSections((prev) => prev.filter((s) => s.id !== id));
  }

  async function save() {
    setSaving(true);
    setProblem(null);
    try {
      await api('/api/v2/enterprise/frameworks/custom', {
        method: 'POST',
        body:   JSON.stringify({
          name:        name.trim(),
          description: description.trim(),
          sections:    sections.map(({ id, ...rest }) => rest),
        }),
      });
      setSuccess(t('templates46FrameworksCustomAnalyst.successMsg', { name: name.trim() }));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSaving(false);
    }
  }

  const canSave = name.trim() && sections.every((s) => s.title.trim() && s.prompt.trim());

  return (
    <>
      <PageHeader
        title={t('templates46FrameworksCustomAnalyst.title')}
        description={t('templates46FrameworksCustomAnalyst.pageDescription')}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-034</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/frameworks')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              {t('templates46FrameworksCustomAnalyst.otherFrameworks')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {/* Metadata */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates46FrameworksCustomAnalyst.nameLabel')}</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('templates46FrameworksCustomAnalyst.namePlaceholder')}
              className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates46FrameworksCustomAnalyst.descLabel')}</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder={t('templates46FrameworksCustomAnalyst.descPlaceholder')}
              className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>
        </div>

        {/* Sections */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-[var(--border-color)]/60 flex items-center justify-between">
            <div>
              <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates46FrameworksCustomAnalyst.sectionsCount', { count: sections.length })}</h3>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">{t('templates46FrameworksCustomAnalyst.sectionsHint')}</p>
            </div>
            <Button size="sm" variant="secondary" onClick={add}>
              <Plus className="w-3.5 h-3.5 mr-1" />
              {t('templates46FrameworksCustomAnalyst.addSection')}
            </Button>
          </div>
          <div className="divide-y divide-[var(--border-color)]/60">
            {sections.map((s, i) => (
              <div key={s.id} className="p-4 flex items-start gap-3">
                <div className="pt-2 text-[var(--text-secondary)]/60">
                  <GripVertical className="w-4 h-4" />
                </div>
                <div className="flex-1 space-y-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="default">{i + 1}</Badge>
                    <input
                      type="text"
                      value={s.title}
                      onChange={(e) => update(s.id, { title: e.target.value })}
                      placeholder={t('templates46FrameworksCustomAnalyst.sectionTitlePlaceholder')}
                      className="flex-1 px-3 py-1.5 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
                    />
                    <select
                      value={s.output}
                      onChange={(e) => update(s.id, { output: e.target.value as Section['output'] })}
                      className="px-2 py-1.5 bg-white border border-[var(--border-color)] rounded-md-custom text-xs focus:outline-none"
                    >
                      <option value="bullets">{t('templates46FrameworksCustomAnalyst.outputBullets')}</option>
                      <option value="narrative">{t('templates46FrameworksCustomAnalyst.outputNarrative')}</option>
                      <option value="kpi">{t('templates46FrameworksCustomAnalyst.outputKpi')}</option>
                    </select>
                  </div>
                  <textarea
                    value={s.prompt}
                    onChange={(e) => update(s.id, { prompt: e.target.value })}
                    rows={2}
                    placeholder={t('templates46FrameworksCustomAnalyst.sectionPromptPlaceholder')}
                    className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
                  />
                </div>
                <button
                  type="button"
                  onClick={() => remove(s.id)}
                  disabled={sections.length <= 2}
                  className={cn(
                    'p-2 text-[var(--text-secondary)] hover:text-[var(--state-error)] rounded-sm-custom',
                    sections.length <= 2 && 'opacity-30 cursor-not-allowed',
                  )}
                  aria-label={t('templates46FrameworksCustomAnalyst.removeSectionAria')}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>{t('templates46FrameworksCustomAnalyst.k10Note')}</p>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => (window.location.href = '/p2/frameworks')}>{t('templates46FrameworksCustomAnalyst.cancel')}</Button>
          <Button onClick={save} isLoading={saving} disabled={!canSave}>
            <Save className="w-4 h-4 mr-2" />
            {t('templates46FrameworksCustomAnalyst.saveFramework')}
          </Button>
        </div>
      </div>
    </>
  );
}
