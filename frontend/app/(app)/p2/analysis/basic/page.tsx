import Template from '@/components/p2/templates/36-analyst-basic';

// Template 36 reads `useSearchParams()` to honour an optional `?scope=`
// query the hub passes through. Next.js refuses to prerender pages that
// touch the search params at build time without a Suspense boundary —
// opt this route into runtime-only rendering so build doesn't bail.
export const dynamic = 'force-dynamic';

export default function Page() {
  return <Template />;
}
