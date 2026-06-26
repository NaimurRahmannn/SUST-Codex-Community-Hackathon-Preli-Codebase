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
from .investigator import (
    match_transaction,
    investigate,
    department_for,
    refine_evidence_for_case,
    human_review_for,
)
from .llm import classify_with_llm
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

    # 1. Claim-evidence reasoning: detect the customer claim first, then verify it.
    hypothesis = investigate(req)
    relevant_id = hypothesis.relevant_transaction_id
    verdict = hypothesis.evidence_verdict
    relevant_txn = next(
        (t for t in history if t.transaction_id == relevant_id), None
    )

    # 2. Classification + severity + escalation.
    #    Deterministic rules first — they are the guaranteed fallback.
    case_type = hypothesis.case_type
    severity = hypothesis.severity
    human_review = hypothesis.human_review_required

    # 2b. Optional LLM refinement. May ONLY override case_type / severity. It
    #     never touches relevant_id, evidence_verdict, or department, and returns
    #     None when disabled or on any error.
    llm_result = classify_with_llm(req.complaint, req.language)
    llm_used = llm_result is not None
    if llm_used:
        case_type = llm_result["case_type"]
        severity = llm_result["severity"]

    # 2c. Evidence semantics depend on the final case_type. For example,
    #     phishing reports usually should not attach to an unrelated transaction,
    #     and duplicate-payment claims need two matching completed payments.
    if llm_used:
        base_id, base_verdict = match_transaction(req.complaint, history)
        relevant_id, verdict = refine_evidence_for_case(
            req, case_type, base_id, base_verdict
        )
        relevant_txn = next(
            (t for t in history if t.transaction_id == relevant_id), None
        )
        human_review = human_review_for(case_type, severity, verdict, relevant_txn)

    # 2d. Department is a deterministic function of the FINAL case_type (taxonomy
    #     source of truth), applied identically whether the LLM or the rules
    #     chose the case_type — so routing is never guessed and never mis-routed.
    department = department_for(case_type)

    # Escalate contradicted claims, but let low-risk ambiguous cases ask for
    # clarification instead of forcing manual review.
    if verdict == "inconsistent" and case_type not in (
        "other",
        "refund_request",
        "merchant_settlement_delay",
    ):
        human_review = True
    elif verdict == "insufficient_data" and case_type in (
        "payment_failed",
        "duplicate_payment",
        "agent_cash_in_issue",
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
    confidence = _confidence(verdict, relevant_txn, case_type) if llm_used else hypothesis.confidence
    reason_codes = [case_type]
    for code in hypothesis.reason_codes:
        if code not in reason_codes:
            reason_codes.append(code)
    if relevant_txn and "transaction_match" not in reason_codes:
        reason_codes.append("transaction_match")
    evidence_code = f"evidence_{verdict}"
    if evidence_code not in reason_codes:
        reason_codes.append(evidence_code)
    reason_codes.append("llm_classified" if llm_used else "rule_classified")
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
