"use client";

/**
 * Chart registry — 15 kinds, 8 data shapes, recharts renderers.
 * Import FlexibleChart (not this file directly) in product code.
 */

import {
  BarChart, Bar,
  LineChart, Line,
  AreaChart, Area,
  PieChart, Pie, Cell,
  ScatterChart, Scatter,
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  Treemap,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer,
} from "recharts";
import { ReactNode } from "react";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ChartKind =
  | "bar" | "horizontal_bar" | "stacked_bar"
  | "line" | "area"
  | "pie" | "donut"
  | "scatter" | "bubble"
  | "heatmap"
  | "treemap"
  | "radar"
  | "funnel"
  | "histogram"
  | "gauge";

export type DataShape =
  | "categorical_count"
  | "percentage_breakdown"
  | "time_series"
  | "scatter_2d"
  | "ranked_list"
  | "multi_dimensional"
  | "funnel_stages"
  | "single_value";

export interface ChartBlock {
  id: string;
  type: "chart" | "stats_card" | "narrative";
  title?: string;
  data_shape?: DataShape;
  default_chart?: ChartKind;
  data?: Record<string, unknown>[];
  meta?: Record<string, string>;   // axis key hints: {x_axis, y_axis, value}
  text?: string;                   // for narrative blocks
  provider?: string;               // "qwen" | "claude"
}

export interface ChartMeta {
  label: string;
  description: string;
}

// ── Colors ────────────────────────────────────────────────────────────────────

export const CHART_COLORS = [
  "#C26B63", "#E8A87C", "#D4956A",
  "#7A9E9F", "#6B8CAE", "#A8C5A0", "#9B89AC",
];

// ── Registry metadata ─────────────────────────────────────────────────────────

export const CHART_META: Record<ChartKind, ChartMeta> = {
  bar:            { label: "Cột dọc",       description: "So sánh các nhóm" },
  horizontal_bar: { label: "Cột ngang",     description: "Xếp hạng, tên dài" },
  stacked_bar:    { label: "Cột xếp chồng", description: "Nhóm + thành phần" },
  line:           { label: "Đường",         description: "Xu hướng thời gian" },
  area:           { label: "Miền",          description: "Đường + nhấn volume" },
  pie:            { label: "Bánh tròn",     description: "Tỷ trọng ≤5 nhóm" },
  donut:          { label: "Donut",         description: "Pie có lỗ + total" },
  scatter:        { label: "Phân tán",      description: "Tương quan 2 biến" },
  bubble:         { label: "Bong bóng",     description: "Phân tán + kích thước" },
  heatmap:        { label: "Heatmap",       description: "Ma trận cường độ" },
  treemap:        { label: "Treemap",       description: "Tỷ trọng dạng ô" },
  radar:          { label: "Radar",         description: "So sánh đa chiều" },
  funnel:         { label: "Phễu",          description: "Chuyển đổi theo bước" },
  histogram:      { label: "Histogram",     description: "Phân phối tần suất" },
  gauge:          { label: "Đồng hồ",       description: "Một giá trị / target" },
};

// ── Compatibility matrix ──────────────────────────────────────────────────────

export const COMPATIBLE_CHARTS: Record<DataShape, ChartKind[]> = {
  categorical_count:    ["bar", "horizontal_bar", "pie", "donut", "treemap", "histogram"],
  percentage_breakdown: ["donut", "pie", "bar", "treemap", "stacked_bar"],
  time_series:          ["line", "area", "bar", "stacked_bar"],
  scatter_2d:           ["scatter", "bubble", "heatmap"],
  ranked_list:          ["horizontal_bar", "bar", "treemap", "funnel"],
  multi_dimensional:    ["radar", "scatter", "bubble"],
  funnel_stages:        ["funnel", "bar", "horizontal_bar"],
  single_value:         ["gauge"],
};

// ── Smart default ─────────────────────────────────────────────────────────────

export function smartDefault(data: unknown[], shape: DataShape): ChartKind {
  const n = data.length;
  if (shape === "categorical_count")    return n > 8 ? "horizontal_bar" : "bar";
  if (shape === "percentage_breakdown") return n <= 5 ? "donut" : "treemap";
  if (shape === "time_series")          return n > 30 ? "area" : "line";
  if (shape === "ranked_list")          return "horizontal_bar";
  if (shape === "multi_dimensional")    return "radar";
  if (shape === "funnel_stages")        return "funnel";
  if (shape === "single_value")         return "gauge";
  return COMPATIBLE_CHARTS[shape][0];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function firstStringKey(row: Record<string, unknown>): string {
  return Object.entries(row).find(([, v]) => typeof v === "string")?.[0] ?? Object.keys(row)[0];
}

function firstNumericKey(row: Record<string, unknown>, exclude: string[] = []): string {
  return (
    Object.entries(row).find(
      ([k, v]) => !exclude.includes(k) && (typeof v === "number" || !isNaN(Number(v)))
    )?.[0] ?? Object.keys(row)[1] ?? Object.keys(row)[0]
  );
}

const H = 300; // standard chart height

// Mixed-magnitude guard: when a bar chart compares metrics whose values span
// >100× (e.g. unit_price 25M next to age 30 / quantity 5), a linear axis makes
// the small bars invisible. Switch that axis to a log scale so every metric is
// readable. Only valid when ALL plotted values are strictly positive (log of
// 0/negative is undefined) — otherwise keep linear.
export function spansLargeMagnitude(values: number[]): boolean {
  const v = values.filter((x) => Number.isFinite(x));
  if (v.length < 2 || v.some((x) => x <= 0)) return false;
  return Math.max(...v) / Math.min(...v) > 100;
}

function barValues(data: Record<string, unknown>[], valueKey: string): number[] {
  return data.map((d) => Number(d[valueKey]));
}

// ── Renderers ─────────────────────────────────────────────────────────────────

function RBar({ data, stacked }: { data: Record<string, unknown>[]; stacked?: boolean }) {
  if (!data.length) return <Empty />;
  const labelKey = firstStringKey(data[0]);
  const valueKey = firstNumericKey(data[0], [labelKey]);
  const useLog = !stacked && spansLargeMagnitude(barValues(data, valueKey));
  return (
    <ResponsiveContainer width="100%" height={H}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={labelKey} tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }}
          scale={useLog ? "log" : "auto"}
          domain={useLog ? ["auto", "auto"] : undefined}
          allowDataOverflow={useLog} />
        <Tooltip />
        <Bar dataKey={valueKey} stackId={stacked ? "a" : undefined}
          fill={CHART_COLORS[0]} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function RHorizontalBar({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const labelKey = firstStringKey(data[0]);
  const valueKey = firstNumericKey(data[0], [labelKey]);
  const dynH = Math.max(H, data.length * 28);
  const useLog = spansLargeMagnitude(barValues(data, valueKey));
  return (
    <ResponsiveContainer width="100%" height={dynH}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis type="number" tick={{ fontSize: 11 }}
          scale={useLog ? "log" : "auto"}
          domain={useLog ? ["auto", "auto"] : undefined}
          allowDataOverflow={useLog} />
        <YAxis type="category" dataKey={labelKey} tick={{ fontSize: 11 }} width={120} />
        <Tooltip />
        <Bar dataKey={valueKey} fill={CHART_COLORS[0]} radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

function RLine({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const xKey = (data[0] as Record<string,unknown>)["date"] !== undefined ? "date" : firstStringKey(data[0]);
  const yKey = "value" in data[0] ? "value" : firstNumericKey(data[0], [xKey]);
  return (
    <ResponsiveContainer width="100%" height={H}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Line type="monotone" dataKey={yKey} stroke={CHART_COLORS[0]} strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function RArea({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const xKey = "date" in data[0] ? "date" : firstStringKey(data[0]);
  const yKey = "value" in data[0] ? "value" : firstNumericKey(data[0], [xKey]);
  return (
    <ResponsiveContainer width="100%" height={H}>
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey={xKey} tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <defs>
          <linearGradient id="grad0" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={CHART_COLORS[0]} stopOpacity={0.3} />
            <stop offset="95%" stopColor={CHART_COLORS[0]} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey={yKey} stroke={CHART_COLORS[0]}
          fill="url(#grad0)" strokeWidth={2} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function RPie({ data, inner }: { data: Record<string, unknown>[]; inner?: boolean }) {
  if (!data.length) return <Empty />;
  const nameKey = firstStringKey(data[0]);
  const valKey  = firstNumericKey(data[0], [nameKey]);
  const centreText = inner ? String(data.reduce((s, r) => s + Number(r[valKey] ?? 0), 0)) : undefined;
  return (
    <ResponsiveContainer width="100%" height={H}>
      <PieChart>
        {inner && centreText && (
          <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle"
            style={{ fontSize: 16, fontWeight: 600, fill: "#374151" }}>
            {centreText}
          </text>
        )}
        <Pie
          data={data}
          cx="50%" cy="50%"
          innerRadius={inner ? 68 : 0}
          outerRadius={110}
          dataKey={valKey}
          nameKey={nameKey}
          label={({ name, percent }) => {
  if (!percent) return "";
  return percent > 0.04
    ? `${name} ${(percent * 100).toFixed(0)}%`
    : "";
}}
          labelLine={false}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

function RScatter({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const clusters = data[0]["cluster"] !== undefined
    ? [...new Set(data.map((r) => String(r["cluster"])))]
    : null;

  if (clusters) {
    return (
      <ResponsiveContainer width="100%" height={H}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis type="number" dataKey="x" name="x" tick={{ fontSize: 11 }} />
          <YAxis type="number" dataKey="y" name="y" tick={{ fontSize: 11 }} />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} />
          <Legend />
          {clusters.map((cl, i) => (
            <Scatter
              key={cl}
              name={`Nhóm ${cl}`}
              data={data.filter((r) => String(r["cluster"]) === cl)}
              fill={CHART_COLORS[i % CHART_COLORS.length]}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={H}>
      <ScatterChart>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis type="number" dataKey="x" tick={{ fontSize: 11 }} />
        <YAxis type="number" dataKey="y" tick={{ fontSize: 11 }} />
        <Tooltip cursor={{ strokeDasharray: "3 3" }} />
        <Scatter data={data} fill={CHART_COLORS[0]} />
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function RBubble({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const zKey = Object.keys(data[0]).find(
    (k) => !["x", "y", "cluster"].includes(k) && typeof data[0][k] === "number"
  ) ?? "x";
  return (
    <ResponsiveContainer width="100%" height={H}>
      <ScatterChart>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis type="number" dataKey="x" tick={{ fontSize: 11 }} />
        <YAxis type="number" dataKey="y" tick={{ fontSize: 11 }} />
        <Tooltip />
        <Scatter data={data} fill={CHART_COLORS[0]}>
          {data.map((row, i) => (
            <Cell
              key={i}
              fill={CHART_COLORS[i % CHART_COLORS.length]}
            />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}

function RHeatmap({
  data,
  meta,
}: {
  data: Record<string, unknown>[];
  meta?: Record<string, string>;
}) {
  if (!data.length) return <Empty />;
  const rowKey = meta?.y_axis ?? "cohort";
  const colKey = meta?.x_axis ?? "period";
  const valKey = meta?.value  ?? "retention";

  const rows = [...new Set(data.map((d) => String(d[rowKey])))];
  const cols = [...new Set(data.map((d) => String(d[colKey])))].sort(
    (a, b) => Number(a) - Number(b)
  );

  const lookup: Record<string, number> = {};
  data.forEach((d) => {
    lookup[`${d[rowKey]}__${d[colKey]}`] = Number(d[valKey] ?? 0);
  });

  const toColor = (v: number) => {
    const pct = Math.min(1, Math.max(0, v));
    const r = Math.round(194 + (71 - 194) * pct);   // #C24747 → #477FC2
    const g = Math.round(103 + (127 - 103) * pct);
    const b = Math.round(99  + (194 - 99)  * pct);
    return `rgb(${r},${g},${b})`;
  };

  return (
    <div className="overflow-x-auto">
      <table className="text-xs border-collapse">
        <thead>
          <tr>
            <th className="p-1.5 text-left text-gray-500 font-medium">{rowKey}</th>
            {cols.map((c) => (
              <th key={c} className="p-1.5 text-center text-gray-500 font-medium min-w-[48px]">
                M{c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row}>
              <td className="p-1.5 font-medium text-gray-600 whitespace-nowrap">{row}</td>
              {cols.map((col) => {
                const v = lookup[`${row}__${col}`] ?? 0;
                return (
                  <td
                    key={col}
                    className="p-1.5 text-center rounded text-white font-medium"
                    style={{ backgroundColor: toColor(v) }}
                  >
                    {v > 0 ? `${(v * 100).toFixed(0)}%` : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RTreemap({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const nameKey  = firstStringKey(data[0]);
  const valueKey = firstNumericKey(data[0], [nameKey]);

  const normalized = data.map((r, i) => ({
    name: String(r[nameKey] ?? `Item ${i}`),
    value: Number(r[valueKey] ?? 0),
    fill: CHART_COLORS[i % CHART_COLORS.length],
  }));

  return (
    <ResponsiveContainer width="100%" height={H}>
      <Treemap
        data={normalized}
        dataKey="value"
        nameKey="name"
        aspectRatio={4 / 3}
        stroke="#fff"
        content={({ x, y, width, height, name, fill }: Record<string, unknown>) => {
          const px = Number(x), py = Number(y), pw = Number(width), ph = Number(height);
          return (
            <g>
              <rect x={px} y={py} width={pw} height={ph}
                style={{ fill: fill as string, stroke: "#fff", strokeWidth: 2 }} />
              {pw > 40 && ph > 20 && (
                <text x={px + pw / 2} y={py + ph / 2}
                  textAnchor="middle" dominantBaseline="middle"
                  style={{ fontSize: 11, fill: "#fff", fontWeight: 500 }}>
                  {String(name)}
                </text>
              )}
            </g>
          );
        }}
      />
    </ResponsiveContainer>
  );
}

function RRadar({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const labelKey = firstStringKey(data[0]);
  const numKeys = Object.keys(data[0]).filter(
    (k) => k !== labelKey && !isNaN(Number(data[0][k]))
  );
  if (!numKeys.length) return <RBar data={data} />;

  // Pivot: subjects = numeric columns, series = label values
  const subjects = numKeys.map((k) => {
    const entry: Record<string, unknown> = { subject: k };
    data.forEach((row) => {
      entry[String(row[labelKey])] = Number(row[k] ?? 0);
    });
    return entry;
  });

  const seriesKeys = data.map((r) => String(r[labelKey]));

  return (
    <ResponsiveContainer width="100%" height={H}>
      <RadarChart data={subjects}>
        <PolarGrid />
        <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11 }} />
        <PolarRadiusAxis tick={{ fontSize: 10 }} />
        {seriesKeys.map((k, i) => (
          <Radar
            key={k}
            name={k}
            dataKey={k}
            stroke={CHART_COLORS[i % CHART_COLORS.length]}
            fill={CHART_COLORS[i % CHART_COLORS.length]}
            fillOpacity={0.25}
          />
        ))}
        <Legend />
        <Tooltip />
      </RadarChart>
    </ResponsiveContainer>
  );
}

function RFunnel({ data }: { data: Record<string, unknown>[] }) {
  // Render as horizontal_bar — recharts FunnelChart API varies across versions
  if (!data.length) return <Empty />;
  const nameKey  = firstStringKey(data[0]);
  const valueKey = firstNumericKey(data[0], [nameKey]);
  const max = Math.max(...data.map((r) => Number(r[valueKey] ?? 0)));

  return (
    <div className="space-y-2 py-2">
      {data.map((row, i) => {
        const val = Number(row[valueKey] ?? 0);
        const pct = max > 0 ? val / max : 0;
        return (
          <div key={i} className="flex items-center gap-3">
            <span className="text-xs text-gray-500 w-36 truncate text-right">
              {String(row[nameKey])}
            </span>
            <div className="flex-1 bg-gray-100 rounded-full h-6 overflow-hidden">
              <div
                className="h-6 rounded-full flex items-center justify-end pr-2 transition-all"
                style={{
                  width: `${pct * 100}%`,
                  backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                }}
              >
                <span className="text-xs text-white font-medium">
                  {val.toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RHistogram({ data }: { data: Record<string, unknown>[] }) {
  // Data already bucketed by backend: [{label, count}]
  return <RBar data={data} />;
}

function RGauge({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return <Empty />;
  const single = data[0];
  const valKey = firstNumericKey(single);
  const val  = Number(single[valKey] ?? 0);
  const max = Number((single["max"] ?? single["target"] ?? (val * 1.5)) || 100);
  const pct  = Math.min(1, val / (max || 1));
  const label = String(single[firstStringKey(single)] ?? valKey);

  return (
    <div className="flex flex-col items-center justify-center py-8 gap-4">
      <div className="text-3xl font-bold text-gray-800">
        {val.toLocaleString()}
      </div>
      <div className="text-sm text-gray-500">{label}</div>
      <div className="w-48 bg-gray-100 rounded-full h-3">
        <div
          className="h-3 rounded-full"
          style={{
            width: `${pct * 100}%`,
            backgroundColor: pct > 0.75 ? CHART_COLORS[0] : pct > 0.4 ? CHART_COLORS[1] : CHART_COLORS[3],
          }}
        />
      </div>
      <div className="text-xs text-gray-400">{(pct * 100).toFixed(0)}% of {max.toLocaleString()}</div>
    </div>
  );
}

function Empty() {
  return (
    <div className="flex items-center justify-center h-32 text-gray-400 text-sm">
      Không có dữ liệu
    </div>
  );
}

// ── Dispatch ──────────────────────────────────────────────────────────────────

export function renderChart(
  kind: ChartKind,
  data: Record<string, unknown>[],
  meta?: Record<string, string>
): ReactNode {
  switch (kind) {
    case "bar":            return <RBar data={data} />;
    case "horizontal_bar": return <RHorizontalBar data={data} />;
    case "stacked_bar":    return <RBar data={data} stacked />;
    case "line":           return <RLine data={data} />;
    case "area":           return <RArea data={data} />;
    case "pie":            return <RPie data={data} />;
    case "donut":          return <RPie data={data} inner />;
    case "scatter":        return <RScatter data={data} />;
    case "bubble":         return <RBubble data={data} />;
    case "heatmap":        return <RHeatmap data={data} meta={meta} />;
    case "treemap":        return <RTreemap data={data} />;
    case "radar":          return <RRadar data={data} />;
    case "funnel":         return <RFunnel data={data} />;
    case "histogram":      return <RHistogram data={data} />;
    case "gauge":          return <RGauge data={data} />;
  }
}
