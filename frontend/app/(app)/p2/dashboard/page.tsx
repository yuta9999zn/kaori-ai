import { redirect } from 'next/navigation';

/**
 * /p2/dashboard has no landing of its own — bounce to the overview tab.
 * Keeps the path bookmarkable (and matches what register/login push to
 * after auth) without needing every caller to know the sub-route layout.
 *
 * `dynamic = 'force-dynamic'` is required: Next.js 16 prerenders pages at
 * build time, and `redirect()` in a server component is not supported
 * during prerender — the page renders as 404 instead.
 */
export const dynamic = 'force-dynamic';

export default function P2DashboardIndexPage() {
  redirect('/p2/dashboard/overview');
}
