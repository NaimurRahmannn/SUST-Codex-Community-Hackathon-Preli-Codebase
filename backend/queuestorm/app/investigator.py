"""
The investigator core: deterministic, rule-based reasoning.

This is where the bulk of the score lives (Evidence Reasoning = 35%). It is
intentionally LLM-free so it is fast, free, and predictable. An optional LLM
layer can sit ON TOP of this for nicer phrasing, but the structured decisions
(relevant_transaction_id, evidence_verdict, case_type, department) should be
driven by these rules so they stay correct and reproducible.

Replace / extend the heuristics here as you discover hidden-test edge cases.
This is a STARTER, not a finished classifier.
"""

import re
from typing import List, Optional, Tuple

from .schemas import TicketRequest, TransactionEntry


# ---------------------------------------------------------------------------
# Keyword lexicons (English + common Bangla/Banglish terms)
# ---------------------------------------------------------------------------

PHISHING_KW = [
    "otp", "pin", "password", "scam", "fraud", "phishing", "suspicious",
    "fake call", "asked for my", "blocked if", "share my", "প্রতারণা",
    "ওটিপি", "পিন", "সন্দেহজনক",
]
WRONG_TRANSFER_KW = [
    "wrong number", "wrong recipient", "wrong person", "wrong account",
    "sent to wrong", "mistakenly sent", "typed it wrong", "ভুল নম্বর",
    "ভুল মানুষ", "ভুল করে",
]
DUPLICATE_KW = [
    "twice", "two times", "double", "duplicate", "charged again",
    "deducted twice", "দুইবার", "দুবার",
]
PAYMENT_FAILED_KW = [
    "failed", "showed failed", "but deducted", "balance was deducted",
    "deducted but", "ব্যর্থ", "ফেইল",
]
REFUND_KW = [
    "refund", "money back", "return my", "want my money", "ফেরত", "রিফান্ড",
]
SETTLEMENT_KW = [
    "settlement", "settle", "not settled", "settled to", "সেটেলমেন্ট",
]
# Used together with settlement intent — a merchant talking about delayed payout.
SETTLEMENT_CONTEXT_KW = ["settlement", "settle", "settled", "payout", "সেটেলমেন্ট"]
NOT_RECEIVED_KW = [
    "didn't get", "did not get", "didn't receive", "did not receive",
    "not received", "hasn't received", "has not received", "never received",
    "he says he didn't", "she says she didn't", "পায়নি", "পাইনি", "আসেনি",
]
CASH_IN_KW = [
    "cash in", "cash-in", "agent", "deposit", "ক্যাশ ইন", "ক্যাশইন", "এজেন্ট",
]


def _contains(text: str, keywords: List[str]) -> bool:
    low = text.lower()
    return any(k in low for k in keywords)


# ---------------------------------------------------------------------------
# Amount extraction from free text
# ---------------------------------------------------------------------------

def extract_amount(complaint: str) -> Optional[float]:
    """Pull the first plausible BDT amount mentioned in the complaint."""
    # Matches 5000, 5,000, 1200.50 etc.
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", complaint)
    if not m:
        return None
    raw = m.group(0).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Transaction matching
# ---------------------------------------------------------------------------

def match_transaction(
    complaint: str, history: List[TransactionEntry]
) -> Tuple[Optional[str], str]:
    """
    Returns (relevant_transaction_id, evidence_verdict).

    Strategy:
      * No history -> (None, insufficient_data)
      * Amount in complaint matches exactly one txn -> that txn
      * Amount matches multiple txns -> ambiguous -> (None, insufficient_data)
      * For duplicate-payment language, prefer the SECOND identical txn
      * Established-recipient pattern (3+ prior transfers to same counterparty)
        on a wrong_transfer claim -> inconsistent
    """
    if not history:
        return None, "insufficient_data"

    amount = extract_amount(complaint)

    # Candidates by amount
    if amount is not None:
        matches = [t for t in history if abs(t.amount - amount) < 0.01]
    else:
        matches = []

    # Duplicate-payment: two+ identical (amount + counterparty) completed txns.
    if _contains(complaint, DUPLICATE_KW) and amount is not None:
        identical = [t for t in matches if t.status == "completed"]
        # group by counterparty
        from collections import defaultdict
        by_cp = defaultdict(list)
        for t in identical:
            by_cp[t.counterparty].append(t)
        for cp, group in by_cp.items():
            if len(group) >= 2:
                group_sorted = sorted(group, key=lambda x: x.timestamp)
                # point at the suspected duplicate (the later one)
                return group_sorted[-1].transaction_id, "consistent"

    if amount is not None:
        if len(matches) == 1:
            chosen = matches[0]
            verdict = "consistent"

            # Wrong-transfer inconsistency check: established recipient.
            if _contains(complaint, WRONG_TRANSFER_KW):
                prior_same_cp = [
                    t for t in history
                    if t.counterparty == chosen.counterparty
                    and t.type == "transfer"
                ]
                if len(prior_same_cp) >= 3:
                    verdict = "inconsistent"
            return chosen.transaction_id, verdict

        if len(matches) > 1:
            # Multiple plausible matches — do not guess.
            return None, "insufficient_data"

    # No amount, or amount not found in history.
    # If there's exactly one transaction and the complaint is specific-ish,
    # we still avoid guessing unless there's a single clear candidate.
    if len(history) == 1:
        # Single transaction; modest confidence it's the one referenced.
        return history[0].transaction_id, "consistent"

    return None, "insufficient_data"


# ---------------------------------------------------------------------------
# Classification + routing
# ---------------------------------------------------------------------------

def classify(req: TicketRequest, relevant_txn: Optional[TransactionEntry]):
    """Return (case_type, department, severity, human_review_required)."""
    c = req.complaint

    # 1. Phishing / social engineering — highest priority, often no txn.
    if _contains(c, PHISHING_KW) and not _contains(c, REFUND_KW):
        return "phishing_or_social_engineering", "fraud_risk", "critical", True

    # 2. Duplicate payment
    if _contains(c, DUPLICATE_KW):
        return "duplicate_payment", "payments_ops", "high", True

    # 3. Payment failed but deducted
    if _contains(c, PAYMENT_FAILED_KW) or (
        relevant_txn and relevant_txn.status == "failed"
    ):
        return "payment_failed", "payments_ops", "high", False

    # 4. Merchant settlement delay
    if req.user_type == "merchant" or _contains(c, SETTLEMENT_KW):
        if _contains(c, SETTLEMENT_KW):
            return "merchant_settlement_delay", "merchant_operations", "medium", False

    # 5. Agent cash-in issue
    if _contains(c, CASH_IN_KW) and (
        relevant_txn is None or relevant_txn.type == "cash_in"
    ):
        if "agent" in c.lower() or "এজেন্ট" in c or (relevant_txn and relevant_txn.type == "cash_in"):
            return "agent_cash_in_issue", "agent_operations", "high", True

    # 6. Wrong transfer (explicit wrong-recipient language)
    if _contains(c, WRONG_TRANSFER_KW):
        return "wrong_transfer", "dispute_resolution", "high", True

    # 6b. Money sent but recipient didn't receive it. Even without explicit
    #     "wrong number" wording, this is a transfer dispute. Severity is
    #     medium because intent is unconfirmed; escalation depends on whether
    #     we can pin down the transaction (handled by the verdict logic in main).
    SENT_KW = ["sent", "transfer", "transferred", "পাঠিয়েছি", "পাঠালাম"]
    if _contains(c, SENT_KW) and _contains(c, NOT_RECEIVED_KW):
        return "wrong_transfer", "dispute_resolution", "medium", False

    # 7. Refund request (change of mind etc.)
    if _contains(c, REFUND_KW):
        return "refund_request", "customer_support", "low", False

    # 8. Fallback
    return "other", "customer_support", "low", False
