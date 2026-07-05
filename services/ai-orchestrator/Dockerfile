FROM python:3.11-slim
WORKDIR /app

# A1 — build context is the REPO ROOT (set in docker-compose:
#   build: { context: ., dockerfile: services/ai-orchestrator/Dockerfile }).
# This lets the image bake the formerly-mounted shared assets so it runs
# self-contained on any host (EKS / EC2 / VPS), not only a machine that
# has the repo checked out to volume-mount. See docs/runbooks/aws-eks-readiness.md.
COPY services/ai-orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service source as the 'ai_orchestrator' Python package.
COPY services/ai-orchestrator/ /app/ai_orchestrator/

# A1 — bake config/, etl/, utils/ and the Kafka event-schema registry at
# the SAME paths the docker-compose volumes used to mount them, so imports
# and LANGUAGE_DICT_PATH resolve unchanged. Dev compose still mounts these
# read-write over the baked copies for hot-reload; prod/cloud uses the baked
# ones (docker-compose.prod.yml drops the mounts).
COPY config/ /app/config/
COPY etl/ /app/etl/
COPY utils/ /app/utils/
COPY infrastructure/kafka/schemas/ /app/infrastructure/kafka/schemas/

# Adding /app/ai_orchestrator to PYTHONPATH lets sibling-package imports
# (`from shared.X import ...`) resolve from inside the package the same way
# they resolve under pytest in CI (cwd=services/ai-orchestrator/). Keeping
# both paths means the source files don't need per-context import shims and
# `DbWriteExhausted` (etc.) keeps a single module identity across the runtime
# and the test process — the alternative (`from ..shared.X`) loaded the class
# twice when tests imported the same file via two different module paths.
ENV PYTHONPATH=/app:/app/ai_orchestrator

EXPOSE 8093

# B3 PR #9 — bounded request concurrency. Same rationale as
# data-pipeline/Dockerfile. ai-orchestrator's chat SSE endpoints
# can hold connections open for tens of seconds; the per-worker
# concurrency cap stops a flood of long-lived chats from starving
# the request executor.
CMD ["uvicorn", "ai_orchestrator.main:app", "--host", "0.0.0.0", "--port", "8093", "--workers", "2", "--limit-concurrency", "100"]
