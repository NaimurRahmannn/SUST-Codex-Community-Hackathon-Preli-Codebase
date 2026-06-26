# RUNBOOK

A stranger can bring this service up with the steps below. No secrets required.

## Option A — Docker (recommended)
```bash
git clone <this-repo-url>
cd queuestorm
docker build -t queuestorm .
docker run -p 8000:8000 queuestorm
```
Service is now at `http://localhost:8000`.

## Option B — Local Python
```bash
git clone <this-repo-url>
cd queuestorm
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Verify readiness
```bash
curl http://localhost:8000/health
# expected: {"status":"ok"}
```

## Smoke-test the analyzer
```bash
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"TKT-001","complaint":"I sent 5000 taka to a wrong number","language":"en","transaction_history":[{"transaction_id":"TXN-9101","timestamp":"2026-04-14T14:08:22Z","type":"transfer","amount":5000,"counterparty":"+8801719876543","status":"completed"}]}'
```

## Run the full sample-case suite
```bash
pip install -r requirements.txt   # if not already
python test_samples.py
# expected: Key-field exact matches: 10/10
```

## Deploying to a public host (Render / Railway / Fly / EC2)
- Point the platform at this repo; it auto-detects the Dockerfile.
- Ensure the platform routes external traffic to container port **8000**
  (or set the platform's `$PORT` and change the CMD to use it).
- No environment variables are required.
