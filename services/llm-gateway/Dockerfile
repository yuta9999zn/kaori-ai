FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source as the `llm_gateway` package, matching how other Python services
# are mounted (data-pipeline, ai-orchestrator).
COPY . /app/llm_gateway/

ENV PYTHONPATH=/app

EXPOSE 8095

# B3 PR #9 — bounded request concurrency. Two workers share the
# Ollama upstream (rate-limited at provider side too); 100 in-flight
# requests per worker is generous given typical infer latency
# (Qwen 2.5 14B p50 ~3s on the pilot box). Larger windows just queue
# at the OS layer instead of returning 503 cleanly.
CMD ["uvicorn", "llm_gateway.main:app", "--host", "0.0.0.0", "--port", "8095", "--workers", "2", "--limit-concurrency", "100"]
