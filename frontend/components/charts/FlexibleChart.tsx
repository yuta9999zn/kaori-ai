"use client";

import { useState } from "react";
import {
  ChartKind, DataShape, ChartBlock,
  CHART_META, COMPATIBLE_CHARTS, CHART_COLORS,
  smartDefault, renderChart,
} from "./chart-registry";

interface FlexibleChartProps {
  block: ChartBlock;
}

export default function FlexibleChart({ block }: FlexibleChartProps) {
  const shape   = block.data_shape;
  const data    = (block.data ?? []) as Record<string, unknown>[];
  const options: ChartKind[] = shape ? COMPATIBLE_CHARTS[shape] ?? [] : [];

  const initial: ChartKind =
    block.default_chart ??
    (shape ? smartDefault(data, shape) : "bar");

  const [selected, setSelected] = useState<ChartKind>(initial);
  const [open, setOpen] = useState(false);

  return (
    <div className="w-full">
      {/* Picker */}
      {options.length > 1 && (
        <div className="flex justify-end mb-3 relative">
          <button
            onClick={() => setOpen((p) => !p)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-800
                       border border-gray-200 rounded-lg px-2.5 py-1.5 hover:border-gray-300
                       transition-colors bg-white"
          >
            <ChartIcon kind={selected} />
            {CHART_META[selected].label}
            <svg className="w-3 h-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {open && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
              <div className="absolute right-0 top-full mt-1 z-20 bg-white border border-gray-200
                              rounded-xl shadow-lg min-w-[180px] py-1 overflow-hidden">
                {options.map((kind) => (
                  <button
                    key={kind}
                    onClick={() => { setSelected(kind); setOpen(false); }}
                    className={`w-full text-left flex items-center gap-2.5 px-3 py-2 text-xs
                                hover:bg-gray-50 transition-colors
                                ${selected === kind ? "bg-blue-50 text-blue-700 font-medium" : "text-gray-700"}`}
                  >
                    <ChartIcon kind={kind} />
                    <div>
                      <div className="font-medium">{CHART_META[kind].label}</div>
                      <div className="text-gray-400 text-[10px]">{CHART_META[kind].description}</div>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Chart */}
      {renderChart(selected, data, block.meta)}
    </div>
  );
}

// Minimal SVG icons per chart kind
function ChartIcon({ kind }: { kind: ChartKind }) {
  const c = CHART_COLORS[0];
  const iconMap: Partial<Record<ChartKind, string>> = {
    bar:            "M3 17h3v-7H3v7zm5 0h3V7H8v10zm5 0h3v-4h-3v4z",
    horizontal_bar: "M3 7v3h10V7H3zm0 5v3h15v-3H3zm0 5v3h7v-3H3z",
    stacked_bar:    "M3 17h3V7H3v10zm5 0h3v-7H8v7zm5 0h3v-4h-3v4z",
    line:           "M3 17l4-8 4 4 4-6 4 4",
    area:           "M3 17l4-8 4 4 4-6 4 4V17H3z",
    pie:            "M12 2v10l8.5 5A10 10 0 1 1 12 2z",
    donut:          "M12 2a10 10 0 1 0 0 20A10 10 0 0 0 12 2zm0 4a6 6 0 1 1 0 12A6 6 0 0 1 12 6z",
    scatter:        "M4 4h2v2H4V4zm6 6h2v2h-2v-2zm6-4h2v2h-2V6zM8 14h2v2H8v-2zm8 0h2v2h-2v-2z",
    heatmap:        "M3 3h4v4H3V3zm6 0h4v4H9V3zm6 0h4v4h-4V3zM3 9h4v4H3V9zm6 0h4v4H9V9zm6 0h4v4h-4V9z",
    treemap:        "M3 3h8v8H3V3zm10 0h8v5h-8V3zm0 7h8v8h-8v-8zM3 13h8v5H3v-5z",
    radar:          "M12 2l2.5 7.5H22l-6.5 4.7 2.5 7.5L12 17l-6 4.7 2.5-7.5L3 9.5h7.5L12 2z",
    funnel:         "M4 3h16l-6 8v7l-4 2v-9L4 3z",
    histogram:      "M3 17h2v-5H3v5zm4 0h2V9H7v8zm4 0h2V5h-2v12zm4 0h2v-8h-2v8zm4 0h2V7h-2v10z",
    gauge:          "M12 14a2 2 0 0 0 0-4 2 2 0 0 0 0 4zM12 6a8 8 0 0 0-7.4 11h14.8A8 8 0 0 0 12 6z",
    bubble:         "M6 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm10 6a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  };
  const path = iconMap[kind] ?? iconMap["bar"]!;
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
      stroke={c} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d={path} />
    </svg>
  );
}
