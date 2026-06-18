import Template from '@/components/p2/templates/13-user-id-detail';

// Legacy mock template reads `window.location.pathname` at render time —
// crashes Next.js prerender. Same pattern as /p2/decisions/id; opt out of
// static generation. Production user detail flow goes through /p2/users/[id].
export const dynamic = 'force-dynamic';

export default function Page() {
  return <Template />;
}
