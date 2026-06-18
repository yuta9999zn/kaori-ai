import Template from '@/components/p2/templates/24-data-pipeline-step-5-results';

// Template 24 reads `useSearchParams()` for ?run_id=. Pages that touch
// search params can't be statically prerendered without a Suspense
// boundary — opt out of static export instead.
export const dynamic = 'force-dynamic';

export default function Page() {
  return <Template />;
}
