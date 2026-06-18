import { redirect } from 'next/navigation';

/**
 * /p2/charts — sidebar "Biểu đồ" group root. Bookmark / direct URL
 * hits land on the picker (the first nav child). See /p2/dashboard
 * for the same pattern + dynamic explanation.
 */
export const dynamic = 'force-dynamic';

export default function P2ChartsIndexPage() {
  redirect('/p2/charts/picker');
}
