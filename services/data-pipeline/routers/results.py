"""Results router — GET /results/{run_id}"""
import json
from uuid import UUID

from fastapi import APIRouter, Header, Path
from ..shared.db import acquire_for_tenant

router = APIRouter()


@router.get("/{run_id}")
async def get_results(
    run_id: UUID = Path(..., description="Pipeline run UUID"),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Get all analysis results for a pipeline run.

    Validation: UUID-typed run_id and X-Enterprise-ID return 422 on
    malformed values.
    """
    async with acquire_for_tenant(x_enterprise_id) as conn:
        analyses = await conn.fetch(
            """SELECT ar.id, ar.templates, ar.status, ar.tier, ar.framework,
                      ar.completed_at, ar.narrative
               FROM analysis_runs ar
               WHERE ar.run_id = $1 AND ar.enterprise_id = $2
               ORDER BY ar.created_at""",
            run_id, x_enterprise_id,
        )
        results = []
        for analysis in analyses:
            result_rows = await conn.fetch(
                """SELECT template_id, status, results_payload, error_message
                   FROM analysis_results
                   WHERE analysis_run_id = $1
                   ORDER BY created_at""",
                analysis["id"],
            )
            results.append({
                "analysis_run_id": str(analysis["id"]),
                "templates": list(analysis["templates"]) if analysis["templates"] else [],
                "status": analysis["status"],
                "tier": analysis["tier"],
                "framework": analysis["framework"],
                "narrative": analysis["narrative"],
                "completed_at": analysis["completed_at"].isoformat() if analysis["completed_at"] else None,
                "results": [
                    {
                        "template_id": r["template_id"],
                        "status": r["status"],
                        "payload": (json.loads(r["results_payload"])
                                    if isinstance(r["results_payload"], str)
                                    else r["results_payload"]),
                        "error_message": r["error_message"],
                    }
                    for r in result_rows
                ],
            })

    return {"run_id": str(run_id), "analyses": results}
