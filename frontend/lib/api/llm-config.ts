/**
 * Platform AI tuning config (CR-0019 / FR-PLT-08) — typed client.
 *
 * Talks to ai-orchestrator routers/llm_ops.py via the gateway route
 * `/api/v1/platform/llm/**` (RouteConfig "platform-llm"). SUPER_ADMIN only —
 * the gateway JwtAuthFilter injects X-User-Role from the JWT, so the FE sends
 * no role header. These endpoints return a BARE list/object (ai-orchestrator),
 * not the auth-service { data } envelope.
 */
import { api } from '@/lib/api';

export interface AIConfig {
  config_key:   string;
  config_value: string;
  value_type:   'int' | 'float' | 'string';
  min_value:    number | null;
  max_value:    number | null;
  description:  string | null;
  applied:      boolean;
  updated_at:   string;
}

export const platformLLMConfigApi = {
  list: () => api<AIConfig[]>('/api/v1/platform/llm/config'),

  update: (key: string, configValue: string) =>
    api<AIConfig>(`/api/v1/platform/llm/config/${encodeURIComponent(key)}`, {
      method: 'PATCH',
      body: JSON.stringify({ config_value: configValue }),
    }),
};
