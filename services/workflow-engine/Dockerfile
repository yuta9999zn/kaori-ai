FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/workflow_engine/

ENV PYTHONPATH=/app

EXPOSE 8099

CMD ["uvicorn", "workflow_engine.main:app", "--host", "0.0.0.0", "--port", "8099", "--workers", "1"]
