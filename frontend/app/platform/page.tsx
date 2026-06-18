'use client';

/**
 * /platform — landing dashboard for platform admins.
 *
 * Re-skinned 2026-05-18 to cream/gold (components/platform/foundation +
 * PageHeader). Data fetching + 60s refetch interval preserved.
 *
 * Backend: GET /api/v1/platform/stats (PlatformController). Returns
 * counters + 3 infra health probes (Ollama / Kafka / P95 latency).
 */

import { useQuery } from '@tanstack/react-query';
import {
  Building2, Users, PlayCircle, Activity, Cpu, Wifi,
  CheckCircle2, AlertTriangle, XCircle,
} from 'lucide-react';

import { api } from '@/lib/api';
import {
  Badge, ErrorBanner, type ProblemDetails,
} from '@/components/platform/foundation';
import { PageHeader } from '@/components/platform/shell';

interface PlatformStats {
  total_workspaces:  number;
  active_workspaces: number;
  total_users:       number;
  total_runs:        number;
  runs_today:        number;
  ollama_online:     boolean;
  kafka_lag:         number;
  p95_latency_ms:    number;
}

type InfraStatus = 'ok' | 'warn' | 'error';

export default function PlatformDashboardPage() {
  const query = useQuery<{ data: PlatformStats }>({
    queryKey:        ['platform-stats'],
    queryFn:         () => api('/api/v1/platform/stats'),
    staleTime:       30_000,
    refetchInterval: 60_000,
  });

  const stats   = query.data?.data;
  const problem = query.error ? (query.error as unknown as ProblemDetails) : null;

  return (
    <>
      <PageHeader
        title="Tổng quan nền tảng"
        description="Sức khoẻ hạ tầng + đếm tăng trưởng workspace, người dùng, pipeline runs."
      />

      <div className="px-6 lg:px-8 py-6 space-y-6">
        {problem && <ErrorBanner problem={problem} />}

        {query.isLoading && !stats && (
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-28 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm animate-pulse"
              />
            ))}
          </div>
        )}

        {stats && (
          <>
            <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
              <KpiCard
                label="Tổng workspaces"
                value={stats.total_workspaces}
                icon={<Building2 className="w-5 h-5" />}
              />
              <KpiCard
                label="Đang hoạt động"
                value={stats.active_workspaces}
                icon={<Activity className="w-5 h-5" />}
                accent="success"
              />
              <KpiCard
                label="Tổng người dùng"
                value={stats.total_users}
                icon={<Users className="w-5 h-5" />}
              />
              <KpiCard
                label="Runs hôm nay"
                value={stats.runs_today}
                icon={<PlayCircle className="w-5 h-5" />}
              />
            </div>

            <section className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] shadow-soft-sm overflow-hidden">
              <header className="px-5 py-4 border-b border-[var(--border-color)]/60">
                <h2 className="font-serif text-lg text-[var(--text-primary)]">Trạng thái hạ tầng</h2>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  Refresh mỗi 60s — cảnh báo khi vượt ngưỡng.
                </p>
              </header>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-px bg-[var(--border-color)]/60">
                <InfraItem
                  label="Ollama (Qwen2.5)"
                  icon={Cpu}
                  status={stats.ollama_online ? 'ok' : 'error'}
                  detail={stats.ollama_online ? 'Online' : 'Offline'}
                />
                <InfraItem
                  label="Kafka consumer lag"
                  icon={Wifi}
                  status={stats.kafka_lag > 1000 ? 'warn' : 'ok'}
                  detail={`${stats.kafka_lag.toLocaleString('vi-VN')} messages`}
                />
                <InfraItem
                  label="P95 latency"
                  icon={Activity}
                  status={stats.p95_latency_ms > 2000 ? 'warn' : 'ok'}
                  detail={`${stats.p95_latency_ms} ms`}
                />
              </div>
            </section>

            <div className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
              <span>Tổng pipeline runs tất cả thời gian:</span>
              <span className="font-semibold text-[var(--text-primary)] tabular-nums">
                {stats.total_runs.toLocaleString('vi-VN')}
              </span>
            </div>
          </>
        )}
      </div>
    </>
  );
}

function KpiCard({
  label, value, icon, accent,
}: {
  label:   string;
  value:   number;
  icon:    React.ReactNode;
  accent?: 'success';
}) {
  return (
    <div className="rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] p-5 shadow-soft-sm hover:shadow-soft-md transition-shadow">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs uppercase tracking-wider text-[var(--text-secondary)] font-medium">
            {label}
          </p>
          <p className="font-serif text-3xl text-[var(--text-primary)] mt-1.5 tabular-nums">
            {value.toLocaleString('vi-VN')}
          </p>
        </div>
        <div
          className={
            accent === 'success'
              ? 'shrink-0 w-10 h-10 rounded-md-custom bg-[var(--state-success)]/15 text-[#5C856A] flex items-center justify-center'
              : 'shrink-0 w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/15 text-[var(--primary-gold-dark)] flex items-center justify-center'
          }
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

function InfraItem({
  label, icon: Icon, status, detail,
}: {
  label:  string;
  icon:   React.ComponentType<{ className?: string; strokeWidth?: number }>;
  status: InfraStatus;
  detail: string;
}) {
  const variant = status === 'ok' ? 'operational' : status === 'warn' ? 'warning' : 'error';
  const StatusIcon =
    status === 'ok' ? CheckCircle2 : status === 'warn' ? AlertTriangle : XCircle;
  const statusText = status === 'ok' ? 'OK' : status === 'warn' ? 'Chú ý' : 'Lỗi';

  return (
    <div className="flex items-center gap-3 p-4 bg-[var(--bg-card)]">
      <div
        className={
          status === 'ok'
            ? 'p-2 rounded-md-custom bg-[var(--state-success)]/12 text-[#5C856A]'
            : status === 'warn'
              ? 'p-2 rounded-md-custom bg-[var(--state-warning)]/12 text-[#9E814D]'
              : 'p-2 rounded-md-custom bg-[var(--state-error)]/12 text-[#9B5050]'
        }
      >
        <Icon className="w-4 h-4" strokeWidth={1.75} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-[var(--text-primary)] truncate">{label}</p>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">{detail}</p>
      </div>
      <Badge variant={variant} className="shrink-0">
        <StatusIcon className="w-3 h-3 mr-1" />
        {statusText}
      </Badge>
    </div>
  );
}
