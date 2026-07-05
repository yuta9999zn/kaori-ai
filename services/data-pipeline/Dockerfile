FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# A1 — build context is the REPO ROOT (docker-compose:
#   build: { context: ., dockerfile: services/data-pipeline/Dockerfile }).
# Bakes the formerly-mounted shared assets so the image runs self-contained
# on any host (EKS / EC2 / VPS). See docs/runbooks/aws-eks-readiness.md.
COPY services/data-pipeline/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service source as the 'data_pipeline' Python package.
COPY services/data-pipeline/ /app/data_pipeline/

# A1 — bake config/, etl/, utils/ and the Kafka event-schema registry at
# the same paths the compose volumes used to mount them (LANGUAGE_DICT_PATH
# + event_schema.py resolve unchanged). Dev compose still mounts over these
# for hot-reload; prod/cloud uses the baked copies.
COPY config/ /app/config/
COPY etl/ /app/etl/
COPY utils/ /app/utils/
COPY infrastructure/kafka/schemas/ /app/infrastructure/kafka/schemas/

ENV PYTHONPATH=/app

EXPOSE 8092

# B3 PR #9 — bounded request concurrency.
#   * --workers 2 spreads load across two ASGI processes so a slow
#     handler doesn't block the whole service. Each worker is its own
#     event loop; matches the asyncio pool budgeting in shared/db.py.
#   * --limit-concurrency 100 caps in-flight requests per worker; once
#     hit, new connections get a 503 Service Unavailable instead of
#     queuing forever. Pairs with the rate-limit at the gateway so
#     burst traffic gets rejected at the edge AND at the worker.
CMD ["uvicorn", "data_pipeline.main:app", "--host", "0.0.0.0", "--port", "8092", "--workers", "2", "--limit-concurrency", "100"]
