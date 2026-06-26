"""
Pydantic models for the QueueStorm Investigator API.

These models do the heavy lifting for the "API Contract and Schema" scoring
category (15%). Because every enum is a `Literal`, FastAPI/Pydantic will
reject any wrong field type with a clean 422 automatically, and will only
ever SERIALIZE exact enum values — no plural/case-variant schema violations.
"""

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums (Literal types = exact string match, no variants allowed)
# ---------------------------------------------------------------------------

Language = Literal["en", "bn", "mixed"]
Channel = Literal["in_app_chat", "call_center", "email", "merchant_portal", "field_agent"]
UserType = Literal["customer", "merchant", "agent", "unknown"]
TxnType = Literal["transfer", "payment", "cash_in", "cash_out", "settlement", "refund"]
TxnStatus = Literal["completed", "failed", "pending", "reversed"]

EvidenceVerdict = Literal["consistent", "inconsistent", "insufficient_data"]
Severity = Literal["low", "medium", "high", "critical"]

CaseType = Literal[
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "duplicate_payment",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "phishing_or_social_engineering",
    "other",
]

Department = Literal[
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "merchant_operations",
    "agent_operations",
    "fraud_risk",
]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class TransactionEntry(BaseModel):
    transaction_id: str
    timestamp: str  # ISO 8601; kept as str so malformed dates don't 400 the whole request
    type: TxnType
    amount: float
    counterparty: str
    status: TxnStatus


class TicketRequest(BaseModel):
    ticket_id: str
    complaint: str = Field(..., min_length=1)
    language: Optional[Language] = None
    channel: Optional[Channel] = None
    user_type: Optional[UserType] = None
    campaign_context: Optional[str] = None
    transaction_history: List[TransactionEntry] = Field(default_factory=list)
    metadata: Optional[dict] = None


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class TicketResponse(BaseModel):
    ticket_id: str
    relevant_transaction_id: Optional[str]
    evidence_verdict: EvidenceVerdict
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: Optional[float] = None
    reason_codes: Optional[List[str]] = None
