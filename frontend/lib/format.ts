/**
 * Vietnamese business formatters. Single source of truth — NEVER
 * hardcode "VND" or "₫" in components.
 */

const VND = new Intl.NumberFormat('vi-VN', {
  style: 'currency',
  currency: 'VND',
  maximumFractionDigits: 0,
});

const INT = new Intl.NumberFormat('vi-VN');

const PCT = new Intl.NumberFormat('vi-VN', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export const fmtVND = (n: number | null | undefined) =>
  n == null ? '—' : VND.format(n);

export const fmtInt = (n: number | null | undefined) =>
  n == null ? '—' : INT.format(n);

export const fmtPct = (n: number | null | undefined) =>
  n == null ? '—' : PCT.format(n);

export function fmtVNDShort(n: number | null | undefined): string {
  if (n == null) return '—';
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)} tỷ ₫`;
  if (n >= 1_000_000)     return `${(n / 1_000_000).toFixed(1)} triệu ₫`;
  if (n >= 1_000)         return `${(n / 1_000).toFixed(0)} nghìn ₫`;
  return `${n} ₫`;
}

export const fmtQuotaVi = (billed: number, quota: number) =>
  `${fmtInt(billed)}/${fmtInt(quota)} bộ dữ liệu đã phân tích`;

export const RISK_VI: Record<string, string> = {
  HIGH:   'Nguy cơ cao',
  MEDIUM: 'Nguy cơ vừa',
  LOW:    'Nguy cơ thấp',
};
export const fmtRisk = (k: string) => RISK_VI[k] ?? k;

export function fmtDate(d: string | Date | null | undefined): string {
  if (!d) return '—';
  const dt = typeof d === 'string' ? new Date(d) : d;
  return dt.toLocaleDateString('vi-VN');
}

export function fmtDateTime(d: string | Date | null | undefined): string {
  if (!d) return '—';
  const dt = typeof d === 'string' ? new Date(d) : d;
  return dt.toLocaleString('vi-VN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
}
