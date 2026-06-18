// /p2/cs/tickets/[id] — P2-34 CS Ticket Detail
// Phase 2.8 NEW per PHASE_2_8_FE_IMPL_SPEC.md §P2-34. Maps workflow D.1 + D.2.
// Permission: OPERATOR+ với claim `triage_cs_tickets`. Reply MANAGER+ approval cho HIGH-risk.
import CsTicketDetailPage from '@/components/p2/templates/78-cs-ticket-detail';

export default function Page({ params }: { params: { id: string } }) {
  return <CsTicketDetailPage ticketId={params.id} />;
}
