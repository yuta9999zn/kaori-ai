'use client';
/**
 * useApiQuery — thin, typed wrapper over TanStack `useQuery` for the Kaori
 * `api<T>()` fetcher (JWT auto-attach + auto-refresh + RFC 7807 → ApiError).
 *
 * Codifies the `/p2/dashboard/overview` REFERENCE PATTERN so screens stop
 * repeating `queryFn: () => api<T>(path)` + the `<T, ApiError>` generics on
 * every call. Domain hooks (see lib/hooks/use-dashboard.ts) build on this so a
 * screen reads `useDashboardState()` instead of an inline useQuery block.
 *
 * Errors are typed as ApiError → call sites can branch on `error.status` /
 * `error.code` (the RFC 7807 machine code) for friendly, i18n'd messages.
 */
import {
  useQuery,
  type UseQueryOptions,
  type UseQueryResult,
} from '@tanstack/react-query';
import { api, type ApiError } from '@/lib/api';

export function useApiQuery<T>(
  key: readonly unknown[],
  path: string,
  options?: Omit<
    UseQueryOptions<T, ApiError, T, readonly unknown[]>,
    'queryKey' | 'queryFn'
  >,
): UseQueryResult<T, ApiError> {
  return useQuery<T, ApiError, T, readonly unknown[]>({
    queryKey: key,
    queryFn: () => api<T>(path),
    ...options,
  });
}
