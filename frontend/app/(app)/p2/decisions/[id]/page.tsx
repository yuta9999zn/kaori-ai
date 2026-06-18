// F-036 BE PR #122 wired the GET /api/v1/decisions/{id} + override/revoke
// endpoints. This dynamic route exposes them at /p2/decisions/<uuid>.
// Templates 24/25/26/31 already link here via /p2/decisions/${decisionId};
// the legacy literal /p2/decisions/id route stays in place for the dev-mode
// link the legacy mock template hardcoded.
import DecisionDetailWiredPage from '@/components/p2/templates/32b-decisions-id-wired';

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DecisionDetailWiredPage decisionId={id} />;
}
