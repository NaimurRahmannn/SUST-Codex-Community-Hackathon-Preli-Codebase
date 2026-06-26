FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# The judge harness calls GET /health and POST /analyze-ticket on this port.
EXPOSE 8000

# Single worker is fine for 2 vCPU / 4 GB. Increase --workers if you add an
# LLM and want more concurrency, but watch memory.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
