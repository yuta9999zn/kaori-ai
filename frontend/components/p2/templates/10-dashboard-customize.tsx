// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 10. /p2/dashboard/customize — Widget layout customization (F-028)
// ----------------------------------------------------------------------------
// User picks/orders/sizes widgets shown on /p2/dashboard. Persists to
// PATCH /api/v1/dashboard/preferences { widgets: [...] }.
//
// 8 widget kinds available — user can add/remove/reorder + save. Reset
// returns to default layout.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  Plus, Trash2, GripHorizontal, Save, RotateCcw, Eye, EyeOff,
  BarChart2, LineChart, Activity, Bell, Sparkles, Layers, Users, CreditCard,
} from 'lucide-react';

import { Button, Badge, ErrorBanner, api, cn, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface Widget {
  id:      string;
  type:    'kpi' | 'chart' | 'pipeline_runs' | 'alerts' | 'insights' | 'quota' | 'users' | 'billing';
  title:   string;
  size:    'sm' | 'md' | 'lg';
  visible: boolean;
}

const TYPE_META: Record<Widget['type'], { icon: any; label: string; defaultSize: Widget['size'] }> = {
  kpi:           { icon: BarChart2,   label: 'Thẻ KPI',          defaultSize: 'sm' },
  chart:         { icon: LineChart,   label: 'Biểu đồ',          defaultSize: 'md' },
  pipeline_runs: { icon: Activity,    label: 'Pipeline gần đây', defaultSize: 'lg' },
  alerts:        { icon: Bell,        label: 'Cảnh báo',         defaultSize: 'md' },
  insights:      { icon: Sparkles,    label: 'Insight ưu tiên',  defaultSize: 'md' },
  quota:         { icon: Layers,      label: 'Hạn mức gói',      defaultSize: 'md' },
  users:         { icon: Users,       label: 'Người dùng',       defaultSize: 'sm' },
  billing:       { icon: CreditCard,  label: 'Hoá đơn gần đây',  defaultSize: 'md' },
};

const DEFAULT_LAYOUT: Widget[] = [
  { id: 'w-1', type: 'quota',         title: 'Hạn mức tháng này',  size: 'md', visible: true },
  { id: 'w-2', type: 'kpi',           title: 'Thẻ KPI tổng quan',  size: 'sm', visible: true },
  { id: 'w-3', type: 'pipeline_runs', title: 'Pipeline gần đây',    size: 'lg', visible: true },
  { id: 'w-4', type: 'alerts',        title: 'Cảnh báo',            size: 'md', visible: true },
  { id: 'w-5', type: 'insights',      title: 'Insight ưu tiên',     size: 'md', visible: true },
];

export default function DashboardCustomize() {
  const [widgets, setWidgets]   = useState<Widget[]>(DEFAULT_LAYOUT);
  const [dragId,  setDragId]    = useState<string | null>(null);
  const [problem, setProblem]   = useState<ProblemDetails | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [savedAt,  setSavedAt]  = useState<string | null>(null);

  useEffect(() => {
    api<{ widgets: Widget[] }>('/api/v1/dashboard/preferences')
      .then((r) => { if (r?.widgets?.length) setWidgets(r.widgets); })
      .catch((err: any) => {
        // 404 = no saved prefs yet, fine — keep DEFAULT_LAYOUT
        if (err?.status !== 404) setProblem(err);
      });
  }, []);

  function move(from: number, to: number) {
    if (from === to) return;
    setWidgets((prev) => {
      const next = [...prev];
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  }

  function toggleVisibility(id: string) {
    setWidgets((prev) => prev.map((w) => (w.id === id ? { ...w, visible: !w.visible } : w)));
  }

  function setSize(id: string, size: Widget['size']) {
    setWidgets((prev) => prev.map((w) => (w.id === id ? { ...w, size } : w)));
  }

  function remove(id: string) {
    setWidgets((prev) => prev.filter((w) => w.id !== id));
  }

  function add(type: Widget['type']) {
    const meta = TYPE_META[type];
    setWidgets((prev) => [
      ...prev,
      { id: `w-${Date.now()}`, type, title: meta.label, size: meta.defaultSize, visible: true },
    ]);
  }

  async function save() {
    setIsSaving(true);
    setProblem(null);
    try {
      await api('/api/v1/dashboard/preferences', {
        method: 'PATCH',
        body: JSON.stringify({ widgets }),
      });
      setSavedAt(new Date().toLocaleTimeString('vi-VN'));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setIsSaving(false);
    }
  }

  function reset() {
    setWidgets(DEFAULT_LAYOUT);
  }

  return (
    <>
      <PageHeader
        title="Tuỳ chỉnh dashboard"
        description="Kéo thả để sắp lại thứ tự, đổi kích thước, ẩn/hiện widget."
        actions={
          <>
            <Button variant="secondary" onClick={reset}>
              <RotateCcw className="w-4 h-4 mr-2" />
              Mặc định
            </Button>
            <Button onClick={save} isLoading={isSaving}>
              <Save className="w-4 h-4 mr-2" />
              Lưu thay đổi
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {savedAt && (
          <div className="rounded-md-custom bg-[var(--state-success)]/10 border border-[var(--state-success)]/30 p-3 text-sm text-[#5C856A]">
            Đã lưu lúc {savedAt}.
          </div>
        )}
        <ErrorBanner problem={problem} />

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Layout list */}
          <div className="lg:col-span-3 space-y-3">
            <h2 className="font-serif text-base text-[var(--text-primary)]">Thứ tự hiện tại</h2>
            {widgets.length === 0 ? (
              <div className="rounded-lg-custom border border-dashed border-[var(--border-color)] p-10 text-center text-[var(--text-secondary)] bg-[var(--bg-card)]">
                Chưa có widget nào. Thêm từ panel bên phải.
              </div>
            ) : widgets.map((w, idx) => (
              <WidgetRow
                key={w.id}
                widget={w}
                index={idx}
                isDragging={dragId === w.id}
                onDragStart={() => setDragId(w.id)}
                onDragEnd={() => setDragId(null)}
                onDragOver={(e: any) => {
                  e.preventDefault();
                  if (!dragId || dragId === w.id) return;
                  const from = widgets.findIndex((x) => x.id === dragId);
                  const to   = idx;
                  if (from !== -1) move(from, to);
                }}
                onToggleVisibility={() => toggleVisibility(w.id)}
                onSizeChange={(s: any) => setSize(w.id, s)}
                onRemove={() => remove(w.id)}
              />
            ))}
          </div>

          {/* Add widget panel */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-5 shadow-soft-sm">
              <h3 className="font-serif text-base text-[var(--text-primary)] mb-3">Thêm widget</h3>
              <div className="space-y-2">
                {Object.entries(TYPE_META).map(([type, meta]) => {
                  const Icon = meta.icon;
                  return (
                    <button
                      key={type}
                      onClick={() => add(type as Widget['type'])}
                      className="w-full flex items-center gap-3 p-2.5 rounded-md-custom border border-[var(--border-color)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--primary-gold)]/5 transition-colors text-left"
                    >
                      <Icon className="w-4 h-4 text-[var(--text-secondary)] shrink-0" />
                      <span className="text-sm text-[var(--text-primary)]">{meta.label}</span>
                      <Plus className="w-3.5 h-3.5 text-[var(--text-secondary)] ml-auto" />
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function WidgetRow({
  widget, index, isDragging,
  onDragStart, onDragEnd, onDragOver,
  onToggleVisibility, onSizeChange, onRemove,
}: any) {
  const Icon = TYPE_META[widget.type].icon;
  const sizes: Array<Widget['size']> = ['sm', 'md', 'lg'];
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      onDragOver={onDragOver}
      className={cn(
        'flex items-center gap-4 p-4 rounded-md-custom bg-[var(--bg-card)] border transition-all',
        isDragging
          ? 'border-[var(--primary-gold)] shadow-soft-md opacity-70'
          : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]/30',
        !widget.visible && 'opacity-50',
      )}
    >
      <button className="cursor-grab text-[var(--text-secondary)] hover:text-[var(--text-primary)]" aria-label="Kéo để sắp xếp">
        <GripHorizontal className="w-5 h-5" />
      </button>

      <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center shrink-0">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[var(--text-primary)]">{widget.title}</p>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">Vị trí #{index + 1} · loại {widget.type}</p>
      </div>

      <div className="flex items-center gap-1 rounded-md-custom border border-[var(--border-color)] p-0.5">
        {sizes.map((s) => (
          <button
            key={s}
            onClick={() => onSizeChange(s)}
            className={cn(
              'px-2 py-1 text-xs rounded-sm-custom transition-colors',
              widget.size === s
                ? 'bg-[var(--primary-gold)] text-[var(--text-primary)] font-medium'
                : 'text-[var(--text-secondary)] hover:bg-[var(--bg-app)]',
            )}
          >
            {s.toUpperCase()}
          </button>
        ))}
      </div>

      <Button
        variant="tertiary"
        size="sm"
        onClick={onToggleVisibility}
        title={widget.visible ? 'Ẩn widget' : 'Hiện widget'}
      >
        {widget.visible ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
      </Button>

      <Button
        variant="tertiary"
        size="sm"
        onClick={onRemove}
        title="Xoá khỏi dashboard"
        className="text-[var(--state-error)] hover:text-[#9B5050]"
      >
        <Trash2 className="w-4 h-4" />
      </Button>
    </div>
  );
}
