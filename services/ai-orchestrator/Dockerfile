FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service source as the 'ai_orchestrator' Python package
# Build context is ./services/ai-orchestrator (set in docker-compose)
COPY . /app/ai_orchestrator/

# config/, utils/, etl/ are volume-mounted from repo root at runtime.
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
