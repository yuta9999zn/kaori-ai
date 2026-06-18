import * as React from 'react';
import Link from 'next/link';
import { cn } from '@/lib/cn';
import { Button } from '@/components/ui/button';

export interface Column<T> {
  key: keyof T | string;
  header: React.ReactNode;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

export function DataTable<T extends Record<string, any>>({
  columns,
  rows,
  page = 1,
  pageSize,
  limit,
  total = 0,
  onPageChange,
  onRowClick,
  rowHref,
  emptyMessage = 'Chưa có dữ liệu',
  className,
}: {
  columns: Column<T>[];
  rows: T[];
  page?: number;
  pageSize?: number;
  limit?: number;
  total?: number;
  onPageChange?: (p: number) => void;
  onRowClick?: (row: T) => void;
  rowHref?: (row: T) => string | null | undefined;
  emptyMessage?: string;
  className?: string;
}) {
  const _size = pageSize ?? limit ?? 20;
  const totalPages = Math.max(1, Math.ceil(total / _size));
  return (
    <div className={cn('rounded-2xl border border-subtle overflow-hidden bg-surface', className)}>
      <div className="overflow-x-auto">
        <table className="w-full text-body">
          <thead className="bg-muted/40">
            <tr className="text-left text-small text-[#7A7266] uppercase tracking-wide border-b border-subtle">
              {columns.map((c, i) => (
                <th key={i} className={cn('py-3 px-4 font-medium', c.className)}>{c.header}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#F1EADF]">
            {rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="py-10 text-center text-[#7A7266]">{emptyMessage}</td>
              </tr>
            ) : (
              rows.map((row, ri) => {
                const clickable = !!onRowClick || !!rowHref;
                const href = rowHref ? rowHref(row) : null;
                return (
                  <tr
                    key={ri}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn('hover:bg-muted/60', clickable && 'cursor-pointer')}
                  >
                    {columns.map((c, ci) => (
                      <td key={ci} className={cn('py-3 px-4 text-[#2E2A24]', c.className)}>
                        {href ? (
                          <Link href={href} className="block text-[#2E2A24]">
                            {c.render ? c.render(row) : (row as any)[c.key as any]}
                          </Link>
                        ) : (
                          c.render ? c.render(row) : (row as any)[c.key as any]
                        )}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {total > _size && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-subtle text-small text-[#7A7266]">
          <span>Trang {page} / {totalPages} · {total.toLocaleString('vi-VN')} dòng</span>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => onPageChange?.(page - 1)}>←</Button>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => onPageChange?.(page + 1)}>→</Button>
          </div>
        </div>
      )}
    </div>
  );
}
