FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/adoption_intel/

ENV PYTHONPATH=/app

EXPOSE 8097

CMD ["uvicorn", "adoption_intel.main:app", "--host", "0.0.0.0", "--port", "8097", "--workers", "1"]
