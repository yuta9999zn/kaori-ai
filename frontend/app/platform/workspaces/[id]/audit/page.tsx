'use client';

import { use, useState } from 'react';
import { useQuery } from '@tanstack/react-query';

import { workspaceAuditApi, type AuditEvent } from '@/lib/api/platform';
import { Badge, Button, ErrorBanner, type ProblemDetails } from '@/components/platform/foundation';
import { fmtDateTime } from '@/lib/format';
import { useT } from '@/lib/i18n/provider';

const PAGE_SIZE = 50;

export default function WorkspaceAuditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const t = useT();

  const [cursors, setCursors] = useState<(string | null)[]>([]);
  const currentCursor = cursors.length === 0 ? null : cursors[cursors.length - 1];
  const pageNumber    = cursors.length + 1;

  const query = useQuery({
    queryKey: ['workspace-audit', id, pageNumber, currentCursor],
    queryFn:  () => workspaceAuditApi.list(id, currentCursor, PAGE_SIZE),
    placeholderData: (prev) => prev,
    retry: false,
  });

  const events     = query.data?.data ?? [];
  const nextCursor = query.data?.meta.cursor ?? null;
  const canBack    = cursors.length > 0;
  const canNext    = !!nextCursor;
  const problem    = query.error ? (query.error as unknown as ProblemDetails) : null;

  return (
    <div className="space-y-5">
      <p className="text-sm text-[var(--text-secondary)]">
        {t('auditPage.subtitle')}
      </p>

      {query.isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-12 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
            />
          ))}
        </div>
      )}

      {query.isError && (
        <ErrorBanner
          problem={problem}
          message={t('auditPage.errMsg', { id })}
        />
      )}

      {!query.isLoading && !query.isError && (
        <>
          <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] overflow-hidden shadow-soft-sm">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-[var(--bg-app)]/60 text-[var(--text-secondary)]">
                  <tr>
                    <th className="text-left font-medium px-4 py-2.5 whitespace-nowrap">{t('auditPage.colTime')}</th>
                    <th className="text-left font-medium px-4 py-2.5">{t('auditPage.colEvent')}</th>
                    <th className="text-left font-medium px-4 py-2.5">{t('auditPage.colActor')}</th>
                    <th className="text-left font-medium px-4 py-2.5">{t('auditPage.colResource')}</th>
                    <th className="text-left font-medium px-4 py-2.5">{t('auditPage.colDetail')}</th>
                    <th className="text-left font-medium px-4 py-2.5">{t('auditPage.colIp')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-color)]/60">
                  {events.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-10 text-center text-[var(--text-secondary)]">
                        {t('auditPage.emptyState')}
                      </td>
                    </tr>
                  )}
                  {events.map((e) => (
                    <tr key={`${e.created_at}-${e.event_type}-${e.actor_email ?? ''}`} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                      <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)] tabular-nums whitespace-nowrap">
                        {fmtDateTime(e.created_at)}
                      </td>
                      <td className="px-4 py-2.5">
                        <code className="font-mono text-xs text-[var(--primary-gold-dark)] bg-[var(--primary-gold)]/12 px-1.5 py-0.5 rounded">
                          {e.event_type}
                        </code>
                      </td>
                      <td className="px-4 py-2.5">
                        {e.actor_email ? (
                          <div className="min-w-0">
                            <p className="text-sm text-[var(--text-primary)] truncate">{e.actor_email}</p>
                            {e.actor_role && (
                              <p className="text-[11px] text-[var(--text-secondary)]">{e.actor_role}</p>
                            )}
                          </div>
                        ) : (
                          <Badge variant="default">{t('auditPage.systemActor')}</Badge>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-sm text-[var(--text-secondary)] truncate">{e.resource ?? '—'}</td>
                      <td className="px-4 py-2.5 text-sm text-[var(--text-primary)]">{e.detail ?? '—'}</td>
                      <td className="px-4 py-2.5 text-xs text-[var(--text-secondary)] font-mono">{e.ip_address ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {(canBack || canNext || events.length > 0) && (
              <div className="px-4 py-2.5 border-t border-[var(--border-color)]/60 flex items-center justify-between bg-[var(--bg-app)]/40 text-xs text-[var(--text-secondary)]">
                <span>{t('auditPage.pageLabel')} <strong className="text-[var(--text-primary)]">{pageNumber}</strong></span>
                <div className="flex items-center gap-1">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setCursors((s) => s.slice(0, -1))}
                    disabled={!canBack || query.isFetching}
                  >
                    ← {t('auditPage.prevBtn')}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => nextCursor && setCursors((s) => [...s, nextCursor])}
                    disabled={!canNext || query.isFetching}
                  >
                    {t('auditPage.nextBtn')} →
                  </Button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
