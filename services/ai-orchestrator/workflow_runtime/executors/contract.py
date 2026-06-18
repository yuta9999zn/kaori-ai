"""ADR-0037 Phase 3 — contract node executor.

The 📑 Hợp đồng builder node: on execute it instantiates a contract (status
'cho_ky') + its parties from the node config, then PAUSES the run
(awaiting_approval) until the required signatures land. The /contracts/{id}/sign
endpoint flips the contract to 'hieu_luc' when complete and resumes the run (it
carries workflow_run_id). Idempotent: re-running reuses the contract already
created for (workflow_run_id, title).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from ..node_executor import NodeContext, NodeExecutor, NodeResult, SideEffectClass

log = structlog.get_logger()


class ContractNodeExecutor(NodeExecutor):
    node_type_key = "contract"
    side_effect_class = SideEffectClass.WRITE_IDEMPOTENT

    async def execute(self, ctx: NodeContext, config: dict[str, Any]) -> NodeResult:
        from ai_orchestrator.shared.db import acquire_for_tenant

        title = (config.get("title") or "").strip()
        if not title:
            from ..node_executor import NodeExecutorError
            raise NodeExecutorError("contract.config.title required")
        parties = config.get("parties") or []
        sign_mode = config.get("sign_mode") or "all"
        required = config.get("required_signatures")
        year = datetime.now(timezone.utc).year

        async with acquire_for_tenant(ctx.enterprise_id) as conn:
            # K-12: dept from the workflow, not the config/client.
            dept = await conn.fetchval(
                "SELECT department_id FROM workflows WHERE workflow_id = $1", ctx.workflow_id)

            # Idempotent: reuse a contract already created by this run+node.
            existing = await conn.fetchrow(
                "SELECT contract_id, status FROM contracts "
                "WHERE workflow_run_id = $1 AND title = $2 LIMIT 1",
                ctx.run_id, title)
            if existing is not None:
                contract_id = existing["contract_id"]
                if existing["status"] == "hieu_luc":
                    return NodeResult(status="completed",
                                      output_data={"contract_id": str(contract_id),
                                                   "contract_status": "hieu_luc", "paused": False})
            else:
                n = await conn.fetchval(
                    "SELECT count(*) FROM contracts WHERE enterprise_id=$1 AND contract_no LIKE $2",
                    ctx.enterprise_id, f"HD-{year}-%")
                contract_no = f"HD-{year}-{(n or 0) + 1:03d}"
                row = await conn.fetchrow(
                    """INSERT INTO contracts
                           (enterprise_id, department_id, workflow_run_id, contract_no,
                            title, contract_type, value_vnd, currency, template_file_id,
                            sign_mode, required_signatures, status, created_by)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,'VND',$8,$9,$10,'cho_ky',$11)
                       RETURNING contract_id""",
                    ctx.enterprise_id, dept, ctx.run_id, contract_no, title,
                    config.get("contract_type"), config.get("value_vnd"),
                    config.get("template_file_id"), sign_mode, required, ctx.user_id)
                contract_id = row["contract_id"]
                for p in parties:
                    await conn.execute(
                        """INSERT INTO contract_parties
                               (contract_id, enterprise_id, party_role, internal_user_id,
                                external_name, external_email, sign_order)
                           VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                        contract_id, ctx.enterprise_id, p.get("party_role") or "Bên",
                        p.get("internal_user_id"), p.get("external_name"),
                        p.get("external_email"), int(p.get("sign_order") or 1))
                log.info("contract.node.created", run_id=str(ctx.run_id),
                         contract_id=str(contract_id), contract_no=contract_no)

        # Pause until the parties sign — the sign endpoint resumes the run.
        return NodeResult(
            status="awaiting_approval",
            output_data={"paused": True, "contract_id": str(contract_id),
                         "contract_status": "cho_ky", "sign_mode": sign_mode},
        )
