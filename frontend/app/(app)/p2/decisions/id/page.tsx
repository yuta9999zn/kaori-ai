import Template from '@/components/p2/templates/32-decisions-id';

// The legacy mock template reads `window.location.pathname` at render time
// (module scope inside the component body). That's fine in the browser but
// blows up Next.js prerender with `ReferenceError: window is not defined`.
// This route is only kept for the dev-mode mock link — opting it out of
// static generation is the smallest fix; the wired production page lives
// at /p2/decisions/[id] (uses 32b-decisions-id-wired).
export const dynamic = 'force-dynamic';

export default function Page() {
  return <Template />;
}
