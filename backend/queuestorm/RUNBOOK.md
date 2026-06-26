# QueueStorm Runbook

This runbook is for starting, testing, and troubleshooting the QueueStorm
Investigator API. The recommended submission mode is deterministic rules only:
`USE_LLM=0`.

## Prerequisites

- Python 3.12+
- Docker Desktop, if using Docker
- No API keys are required for the default runtime

## Local Run

macOS/Linux:

```bash
cd backend/queuestorm
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export USE_LLM=0
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Windows PowerShell:

```powershell
cd backend\queuestorm
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:USE_LLM = "0"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

## Docker Run

```bash
cd backend/queuestorm
docker build -t queuestorm-investigator .
docker run --rm -p 8000:8000 queuestorm-investigator
```

The Dockerfile sets `USE_LLM=0`, so it starts without `.env` or Gemini keys.

## Analyze-Ticket Smoke Request

```bash
curl -X POST http://localhost:8000/analyze-ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket_id":"RUNBOOK-001","complaint":"Recharge failed but 250 taka was deducted.","language":"en","transaction_history":[{"transaction_id":"RUNBOOK-TXN-001","timestamp":"2026-06-20T10:00:00Z","type":"payment","amount":250,"counterparty":"MOBILE-OP","status":"failed"}]}'
```

Expected high-level result:

```json
{
  "case_type": "payment_failed",
  "department": "payments_ops",
  "evidence_verdict": "consistent",
  "relevant_transaction_id": "RUNBOOK-TXN-001"
}
```

The actual response also includes summary, next action, safe customer reply,
severity, confidence, and reason codes.

## Run Tests

Run the full final regression suite:

```bash
cd backend/queuestorm
export USE_LLM=0
python -m compileall app
python test_samples.py
python stress_test.py
python holdout_test.py
python blind_hidden_test.py
python claim_evidence_regression_test.py
python final_submission_smoke_test.py
```

Windows PowerShell:

```powershell
cd backend\queuestorm
$env:USE_LLM = "0"
python -m compileall app
python test_samples.py
python stress_test.py
python holdout_test.py
python blind_hidden_test.py
python claim_evidence_regression_test.py
python final_submission_smoke_test.py
```

Expected final results:

- Public samples: 10/10
- Stress: 30/30
- Holdout: 24/24
- Blind hidden-style: 50/50
- Claim/evidence regression: 13/13
- Final submission smoke test: 0 failures
- Safety violations: 0

## Environment Variables

Default deterministic mode:

```bash
USE_LLM=0
```

Optional Gemini mode:

```bash
USE_LLM=1
GEMINI_API_KEYS=key_one,key_two,key_three
```

Backward-compatible single-key mode:

```bash
USE_LLM=1
GEMINI_API_KEY=one_key
```

Gemini is optional. It may only refine `case_type`, `severity`, and
`confidence`. It never decides `department`, `relevant_transaction_id`, or
`evidence_verdict`.

## Deployment Checklist

1. Build from `backend/queuestorm`.
2. Use the provided Dockerfile.
3. Expose container port `8000`.
4. Set `USE_LLM=0`.
5. Do not mount `.env` unless intentionally enabling Gemini.
6. Health check path: `/health`.
7. Confirm `POST /analyze-ticket` with the smoke request above.

## Troubleshooting

### Port 8000 already in use

Use a different host port:

```bash
docker run --rm -p 8001:8000 queuestorm-investigator
curl http://localhost:8001/health
```

### Import errors locally

Make sure you are inside `backend/queuestorm` and dependencies are installed:

```bash
pip install -r requirements.txt
python -m compileall app
```

### Gemini warnings

For final submission, disable Gemini:

```bash
export USE_LLM=0
```

The deterministic engine does not need keys and is the intended judge runtime.

### 400 response from `/analyze-ticket`

Check required fields:

- `ticket_id`
- non-empty `complaint`
- `transaction_history` must be a list
- transaction entries must use exact enum values for `type` and `status`

### Unsafe reply concern

Run:

```bash
python final_submission_smoke_test.py
python final_guardrail_test.py
```

Both scripts check that customer replies do not ask for credentials or promise
guaranteed refunds/reversals.
