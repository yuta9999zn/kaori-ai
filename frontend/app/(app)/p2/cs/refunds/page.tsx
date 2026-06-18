// /p2/cs/refunds — P2-36 Refund Approval Queue
// Phase 2.8 NEW per PHASE_2_8_FE_IMPL_SPEC.md §P2-36. Maps workflow D.4.
// Permission: OPERATOR+ xem; approve action MANAGER+ với claim `approve_refund`.
// K-6 audit per approval (mig 098).
import RefundQueuePage from '@/components/p2/templates/80-cs-refund-queue';

export default function Page() {
  return <RefundQueuePage />;
}
