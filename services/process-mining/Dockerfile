FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/process_mining/

ENV PYTHONPATH=/app

EXPOSE 8096

CMD ["uvicorn", "process_mining.main:app", "--host", "0.0.0.0", "--port", "8096", "--workers", "1"]
