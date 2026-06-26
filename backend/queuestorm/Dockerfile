FROM python:3.12-slim

WORKDIR /app

# Reliable judge/runtime default: deterministic rules only. Set USE_LLM=1 and
# provide Gemini keys only if you have stable quota.
ENV USE_LLM=0

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
