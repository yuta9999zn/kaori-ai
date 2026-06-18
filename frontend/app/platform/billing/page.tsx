import { redirect } from 'next/navigation';

/**
 * /platform/billing has no landing of its own — bounce to the overview tab.
 * Keeps the path bookmarkable and matches the sidebar's "Billing" group
 * expectation that anything under the section root opens the first tab.
 *
 * `dynamic = 'force-dynamic'` is required: Next.js 16 prerenders pages at
 * build time by default, and `redirect()` in a server component is not
 * supported during prerender — the page renders as 404 instead. Forcing
 * dynamic moves the redirect to request time where it actually runs.
 */
export const dynamic = 'force-dynamic';

export default function PlatformBillingIndexPage() {
  redirect('/platform/billing/overview');
}
