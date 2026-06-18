import { redirect } from 'next/navigation';

/**
 * /p2/insights — sidebar "Tất cả Insight" target. The actual list lives
 * under /p2/insights/list; this redirect is the landing shim. See
 * /p2/dashboard for the same pattern + dynamic explanation.
 */
export const dynamic = 'force-dynamic';

export default function P2InsightsIndexPage() {
  redirect('/p2/insights/list');
}
