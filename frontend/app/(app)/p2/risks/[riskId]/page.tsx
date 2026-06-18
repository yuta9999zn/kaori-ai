// F-039 BE PR #126 + #140 wired GET/PATCH/DELETE for individual risks.
// Dynamic route exposes them at /p2/risks/<uuid>. The hub table links here
// via /p2/risks/${risk_id}.
import RiskDetailPage from '@/components/p2/templates/f039-risks-detail';

export default async function Page({ params }: { params: Promise<{ riskId: string }> }) {
  const { riskId } = await params;
  return <RiskDetailPage riskId={riskId} />;
}
