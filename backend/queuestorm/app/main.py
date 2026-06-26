"""
QueueStorm Investigator — FastAPI application.

Endpoints (Section 4 of the problem statement):
  GET  /health          -> {"status": "ok"}
  POST /analyze-ticket  -> structured analysis (Section 6 schema)

Design:
  * Deterministic rule engine (app/investigator.py) makes the structured
    decisions that drive 55% of the score (evidence + safety).
  * Template replies (app/replies.py) are fast, free, and language-aware.
  * Every customer_reply passes through app/safety.py as the LAST step.
  * No LLM is required to run. An optional LLM hook is left as a TODO.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from .schemas import TicketRequest, TicketResponse, TransactionEntry
from .investigator import match_transaction, classify
from .replies import build_outputs
from .safety import enforce_customer_reply_safety, detect_injection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("queuestorm")

app = FastAPI(title="QueueStorm Investigator", version="1.0")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

@app.post("/analyze-ticket", response_model=TicketResponse)
def analyze_ticket(req: TicketRequest):
    # Defend against prompt injection inside the complaint. We never let
    # complaint text steer the decision; we only investigate it as data.
    injection = detect_injection(req.complaint)

    history = req.transaction_history

    # 1. Evidence reasoning: pick the relevant transaction + verdict.
    relevant_id, verdict = match_transaction(req.complaint, history)
    relevant_txn = next(
        (t for t in history if t.transaction_id == relevant_id), None
    )

    # 2. Classification + routing + severity + escalation.
    case_type, department, severity, human_review = classify(req, relevant_txn)

    # Escalate whenever evidence is unclear or inconsistent.
    if verdict in ("inconsistent", "insufficient_data") and case_type not in (
        "other",
        "refund_request",
        "merchant_settlement_delay",
    ):
        human_review = True

    # High-value heuristic: large amounts always get a human.
    if relevant_txn and relevant_txn.amount is not None and relevant_txn.amount >= 25000:
        human_review = True
        if severity in ("low", "medium"):
            severity = "high"

    # 3. Build the human-readable fields.
    summary, action, reply = build_outputs(
        req, case_type, department, verdict, relevant_txn
    )

    # 4. Safety pass — ALWAYS last, on the customer-facing string.
    reply = enforce_customer_reply_safety(reply, language=req.language or "en")

    # 5. Confidence + reason codes (optional fields, but useful signal).
    confidence = _confidence(verdict, relevant_txn, case_type)
    reason_codes = [case_type]
    if relevant_txn:
        reason_codes.append("transaction_match")
    reason_codes.append(f"evidence_{verdict}")
    if injection:
        reason_codes.append("prompt_injection_ignored")

    return TicketResponse(
        ticket_id=req.ticket_id,
        relevant_transaction_id=relevant_id,
        evidence_verdict=verdict,
        case_type=case_type,
        severity=severity,
        department=department,
        agent_summary=summary,
        recommended_next_action=action,
        customer_reply=reply,
        human_review_required=human_review,
        confidence=confidence,
        reason_codes=reason_codes,
    )


def _confidence(verdict: str, txn, case_type: str) -> float:
    base = 0.6
    if verdict == "consistent" and txn is not None:
        base = 0.9
    elif verdict == "inconsistent":
        base = 0.75
    elif verdict == "insufficient_data":
        base = 0.6
    if case_type == "phishing_or_social_engineering":
        base = max(base, 0.95)
    return round(base, 2)


# ---------------------------------------------------------------------------
# Error handling — never crash, never leak internals.
# ---------------------------------------------------------------------------

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # Malformed / missing required fields -> 400 with a non-sensitive message.
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body. Check required fields and types."},
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error")  # full trace to logs only
    return JSONResponse(
        status_code=500,
        content={"error": "Internal error while analyzing the ticket."},
    )
