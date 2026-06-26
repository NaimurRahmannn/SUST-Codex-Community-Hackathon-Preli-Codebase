"""
Reply / summary generation.

Template-based by default (fast, free, safe). If you add an LLM, generate the
draft here and STILL pass customer_reply through safety.enforce_customer_reply_safety
before returning it.

The Bangla branch demonstrates language-matched replies: if the input language
is 'bn', reply in Bangla with a Bangla credential-safety reminder.
"""

from typing import Optional
from .schemas import TicketRequest, TransactionEntry

BN_PIN_REMINDER = "অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।"
EN_PIN_REMINDER = "Please do not share your PIN or OTP with anyone."


def _txn_ref(txn: Optional[TransactionEntry]) -> str:
    return txn.transaction_id if txn else "your reported transaction"


def build_outputs(
    req: TicketRequest,
    case_type: str,
    department: str,
    evidence_verdict: str,
    relevant_txn: Optional[TransactionEntry],
):
    """Return (agent_summary, recommended_next_action, customer_reply)."""
    bn = req.language == "bn"
    reminder = BN_PIN_REMINDER if bn else EN_PIN_REMINDER
    tid = _txn_ref(relevant_txn)

    # --- per-case templates -------------------------------------------------

    if case_type == "phishing_or_social_engineering":
        summary = (
            "Customer reports a suspicious contact attempting to obtain credentials. "
            "Likely social engineering. Escalate to fraud team."
        )
        action = (
            "Escalate to fraud_risk immediately. Reassure the customer that the "
            "company never asks for PIN/OTP. Log any reported number for analysis."
        )
        reply = (
            "Thank you for reaching out before sharing any information. We never ask "
            "for your PIN, OTP, or password under any circumstances, and neither does "
            "anyone legitimately representing us. Our fraud team has been notified. "
            + reminder
        )

    elif case_type == "duplicate_payment":
        summary = (
            f"Customer reports a duplicate payment. Transaction {tid} appears to be "
            "the duplicate charge and requires verification with the biller/merchant."
        )
        action = (
            f"Verify the duplicate with payments_ops. If only one payment was received, "
            f"initiate reversal of {tid} per policy."
        )
        reply = (
            f"We have noted the possible duplicate payment for transaction {tid}. Our "
            "payments team will verify and any eligible amount will be returned through "
            "official channels. " + reminder
        )

    elif case_type == "payment_failed":
        summary = (
            f"Customer reports a failed payment ({tid}) with a possible balance "
            "deduction. Requires payments operations investigation."
        )
        action = (
            f"Investigate {tid} ledger status. If balance was deducted on a failed "
            "payment, initiate the automatic reversal flow within SLA."
        )
        reply = (
            f"We have noted that transaction {tid} may have caused an unexpected balance "
            "deduction. Our payments team will review and any eligible amount will be "
            "returned through official channels. " + reminder
        )

    elif case_type == "merchant_settlement_delay":
        summary = (
            f"Merchant reports settlement {tid} delayed beyond the expected window. "
            "Settlement status appears pending."
        )
        action = (
            "Route to merchant_operations to verify settlement batch status and "
            "communicate a revised ETA if delayed."
        )
        reply = (
            f"We have noted your concern about settlement {tid}. Our merchant operations "
            "team will check the batch status and update you on the expected settlement "
            "time through official channels."
        )

    elif case_type == "agent_cash_in_issue":
        summary = (
            f"Customer reports a cash-in via agent ({tid}) not reflected in balance. "
            "Requires agent operations investigation."
        )
        action = (
            f"Investigate {tid} status with agent operations. Confirm settlement state "
            "and resolve within the standard cash-in SLA."
        )
        if bn:
            reply = (
                f"আপনার লেনদেন {tid} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স দল "
                "এটি দ্রুত যাচাই করবে এবং অফিসিয়াল চ্যানেলে আপনাকে জানাবে। " + reminder
            )
        else:
            reply = (
                f"We have noted your concern about transaction {tid}. Our agent operations "
                "team will verify it and update you through official channels. " + reminder
            )

    elif case_type == "wrong_transfer":
        summary = (
            f"Customer reports a wrong transfer via {tid}. "
            + (
                "Evidence is inconsistent with the claim (established recipient pattern)."
                if evidence_verdict == "inconsistent"
                else "Evidence supports the claim."
                if evidence_verdict == "consistent"
                else "Could not confirm the specific transaction from history."
            )
        )
        action = (
            "Flag for human review and verify details with the customer before "
            "initiating the wrong-transfer dispute workflow."
        )
        reply = (
            f"We have noted your concern about transaction {tid}. Our dispute team will "
            "review the case carefully and contact you through official support channels. "
            + reminder
        )

    elif case_type == "refund_request":
        summary = (
            f"Customer requests a refund for {tid}. Appears to be a change-of-mind "
            "request rather than a service failure."
        )
        action = (
            "Inform the customer that refund eligibility depends on the merchant's own "
            "policy and provide guidance on contacting the merchant directly."
        )
        reply = (
            "Thank you for reaching out. Refunds for completed merchant payments depend "
            "on the merchant's own policy. We recommend contacting the merchant directly, "
            "and we can guide you if needed. " + reminder
        )

    else:  # other / insufficient
        summary = (
            "Customer reports a concern without enough detail to identify a specific "
            "transaction or issue."
        )
        action = (
            "Reply asking for specifics: transaction ID, amount, what went wrong, and "
            "approximate time."
        )
        reply = (
            "Thank you for reaching out. To help you faster, please share the transaction "
            "ID, the amount involved, and a short description of what went wrong. " + reminder
        )

    # Special case: ambiguous match within an otherwise-known case type.
    if evidence_verdict == "insufficient_data" and relevant_txn is None and case_type == "wrong_transfer":
        action = (
            "Ask the customer for the intended recipient's number to identify the correct "
            "transaction. Do not initiate a dispute until confirmed."
        )
        reply = (
            "Thank you for reaching out. We see more than one transaction that could match. "
            "Could you share the recipient's number so we can identify the right one? " + reminder
        )

    return summary, action, reply
