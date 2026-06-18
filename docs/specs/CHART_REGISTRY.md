# CHART REGISTRY — Kaori System

> User không bị khóa cứng vào 1 loại biểu đồ. Với cùng data, có thể chọn 3-6 loại phù hợp.
> Trực tiếp adapted từ Kise AI Chart Registry, thay branding + loại bỏ retail-specific defaults.

---

## 1. Kiến trúc 3 layer

```
┌───────────────────────────────────────────────────┐
│ 1. CHART_REGISTRY (render functions)               │
│    15 chart kinds                                  │
│    Mỗi kind = 1 function (ChartProps) => ReactNode │
└───────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────┐
│ 2. COMPATIBLE_CHARTS (shape → valid kinds)         │
│    8 canonical data shapes                         │
│    categorical_count → [bar, horizontal_bar, ...]  │
└───────────────────────────────────────────────────┘
┌───────────────────────────────────────────────────┐
│ 3. FlexibleChart (React wrapper)                   │
│    Picker dropdown: icon + label + description     │
│    State: user-selected kind (overrides default)   │
│    Smart default: data-aware fallback              │
└───────────────────────────────────────────────────┘
```

---

## 2. 15 Chart Kinds

| Kind | Label | Tốt cho | Library |
|------|-------|---------|---------|
| `bar` | Cột dọc | So sánh 3-10 nhóm | recharts BarChart |
| `horizontal_bar` | Cột ngang | Xếp hạng, tên dài | recharts BarChart layout="vertical" |
| `stacked_bar` | Cột xếp chồng | Nhóm + thành phần | recharts Bar stackId |
| `line` | Đường | Xu hướng thời gian | recharts LineChart |
| `area` | Miền | Line + nhấn volume | recharts AreaChart |
| `pie` | Bánh | Tỷ trọng ≤5 nhóm | recharts PieChart |
| `donut` | Donut | Pie có lỗ + total center | recharts Pie innerRadius |
| `scatter` | Phân tán | Tương quan 2 biến | recharts ScatterChart |
| `bubble` | Bong bóng | Scatter + kích thước dim 3 | recharts Scatter size |
| `heatmap` | Heatmap | 2D cường độ (cohort) | Phase 2 — custom SVG |
| `treemap` | Treemap | Tỷ trọng dạng ô | recharts Treemap |
| `radar` | Radar | So sánh đa chiều | recharts RadarChart |
| `funnel` | Phễu | Conversion stages | recharts FunnelChart |
| `histogram` | Histogram | Phân phối tần suất | recharts Bar (bins) |
| `gauge` | Đồng hồ | Một giá trị / target | custom div + progress |

---

## 3. DataShape → Compatible Charts

```typescript
// frontend/src/components/charts/chart-registry.tsx

export type DataShape =
  | 'categorical_count'    // {label, count}[]
  | 'percentage_breakdown' // {label, percent}[]
  | 'time_series'          // {date, value}[]
  | 'scatter_2d'           // {x, y, label?}[]
  | 'ranked_list'          // {rank, name, value}[]
  | 'multi_dimensional'    // {label, dim1, dim2, ...dimN}[]
  | 'funnel_stages'        // {stage, count}[]
  | 'single_value';        // number

export const COMPATIBLE_CHARTS: Record<DataShape, ChartKind[]> = {
  categorical_count:    ['bar', 'horizontal_bar', 'treemap', 'pie', 'donut', 'histogram'],
  percentage_breakdown: ['pie', 'donut', 'stacked_bar', 'treemap', 'bar'],
  time_series:          ['line', 'area', 'bar', 'stacked_bar'],
  scatter_2d:           ['scatter', 'bubble', 'heatmap'],
  ranked_list:          ['horizontal_bar', 'bar', 'treemap', 'funnel'],
  multi_dimensional:    ['radar', 'scatter', 'bubble'],
  funnel_stages:        ['funnel', 'bar', 'horizontal_bar'],
  single_value:         ['gauge'],
};
```

---

## 4. Smart Defaults (data-aware)

```typescript
function smartDefault(data: any[], shape: DataShape): ChartKind {
  if (shape === 'categorical_count' && data.length > 8)
    return 'horizontal_bar';   // cột dọc sẽ chật khi > 8 category
  if (shape === 'percentage_breakdown' && data.length <= 5)
    return 'pie';
  if (shape === 'percentage_breakdown' && data.length > 5)
    return 'treemap';
  if (shape === 'time_series')
    return data.length > 30 ? 'area' : 'line';
  return COMPATIBLE_CHARTS[shape][0];  // fallback: first compatible
}
```

---

## 5. FlexibleChart Usage

```tsx
// frontend/src/components/charts/FlexibleChart.tsx

<FlexibleChart
  data={timeSeries}
  shape="time_series"
  defaultKind="line"
  title="Doanh thu theo tháng"
  xKey="date"
  yKey="revenue"
/>
```

User thấy: "Đường ▾" → click → dropdown 4 options (line/area/bar/stacked_bar).

---

## 6. Backend Block Spec

Mỗi analysis template trả về `blocks` JSON:

```python
# ai-orchestrator/analytics/composers/time_series_composer.py
{
    "blocks": [
        {
            "id": "revenue_trend",
            "type": "chart",
            "title": "Xu hướng doanh thu",
            "data_shape": "time_series",
            "default_chart": "area",
            "data": [{"date": "2026-01", "value": 120000000}, ...]
        },
        {
            "id": "summary",
            "type": "stats_card",
            "title": "Tóm tắt",
            "data": {"trend": "+12.4%", "forecast_next_month": 135000000}
        },
        {
            "id": "ai_narrative",
            "type": "narrative",
            "text": "Doanh thu tháng 4/2026 tăng 12.4% so với tháng 3...",
            "provider": "qwen"
        }
    ]
}
```

Frontend `ResultsDashboard.tsx` render mỗi block dựa trên `type`:
- `chart` → `<FlexibleChart>` với data_shape + default_chart
- `stats_card` → card UI
- `narrative` → text box có attribution (Qwen / Claude)

---

## 7. Extend Chart Registry

### Thêm chart mới (vd: sankey)
```typescript
// 1. Add to ChartKind union
export type ChartKind = ... | 'sankey';

// 2. Add to CHART_META
sankey: { label: 'Sankey', icon: GitBranch, description: 'Luồng giữa các nodes' },

// 3. Add renderer
function renderSankey(props: ChartProps) { return <SankeyDiagram {...props} />; }

// 4. Register
export const CHART_REGISTRY: Record<ChartKind, Renderer> = { ..., sankey: renderSankey };

// 5. Add to applicable shapes
COMPATIBLE_CHARTS.multi_dimensional.push('sankey');
```

5 bước, không đụng ResultsDashboard / AnalysisConfig / template registry.

---

## 8. Colors

```typescript
// Warm boutique palette (inherited from design system)
export const CHART_COLORS = [
  '#C26B63',  // warm red
  '#E8A87C',  // warm orange
  '#D4956A',  // amber
  '#7A9E9F',  // muted teal
  '#6B8CAE',  // muted blue
  '#A8C5A0',  // muted sage green
  '#9B89AC',  // muted lavender
];
```

---

## 9. Implementation Status (2026-04-22)

| Thành phần | Status |
|---|---|
| ChartKind type (15 kinds) | ⚠️ Pending — cần tạo `components/charts/chart-registry.tsx` |
| DataShape type (8 shapes) | ⚠️ Pending |
| COMPATIBLE_CHARTS matrix | ⚠️ Pending |
| FlexibleChart component | ⚠️ Pending — cần tạo `components/charts/FlexibleChart.tsx` |
| Bar / Line / Area / Pie / Donut renderers | ⚠️ Pending — recharts wrappers |
| Heatmap (cohort) | ⚠️ Phase 2 |
| Smart default logic | ⚠️ Pending |
| ResultsDashboard block renderer | ⚠️ Pending |

**Priority:** Cần implement trước Sprint 4 (Frontend).
