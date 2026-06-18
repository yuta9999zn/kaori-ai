FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8094

# B3 PR #9 — workers already 2 (existing); add --limit-concurrency 100
# so a flood of SMTP send requests doesn't queue indefinitely.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8094", "--workers", "2", "--limit-concurrency", "100"]
