"""
Safety guardrails.

This module enforces Section 8 of the problem statement. These rules are
checked automatically by the judge and carry direct point penalties plus a
disqualification risk (2+ critical violations => not eligible for top 40).

DESIGN PRINCIPLE: never trust free text — whether it comes from an LLM or a
template — to be safe by itself. Run every customer-facing string through
`enforce_customer_reply_safety()` as the LAST step before returning it.
"""

import re

# Standard safety reminder appended to customer replies. Mirrors the sample pack.
PIN_OTP_REMINDER = "Please do not share your PIN or OTP with anyone."

# Phrases that promise an unauthorized refund/reversal (penalty: -10).
# We rewrite these to safe "eligible amount" language.
_UNAUTHORIZED_PROMISE_PATTERNS = [
    (re.compile(r"\bwe will refund you\b", re.I), "any eligible amount will be returned through official channels"),
    (re.compile(r"\bwe will refund\b", re.I), "any eligible amount will be returned through official channels"),
    (re.compile(r"\bi will refund\b", re.I), "any eligible amount will be returned through official channels"),
    (re.compile(r"\byou will be refunded\b", re.I), "any eligible amount will be returned through official channels"),
    (re.compile(r"\bwe will reverse\b", re.I), "our team will review the case through official channels"),
    (re.compile(r"\bwe have reversed\b", re.I), "our team will review the case through official channels"),
    (re.compile(r"\bwe will unblock\b", re.I), "our team will review your account through official channels"),
    (re.compile(r"\byour money will be returned\b", re.I), "any eligible amount will be returned through official channels"),
]

# Requests for sensitive credentials (penalty: -15). If any appear in an
# outgoing reply we strip the offending sentence entirely.
_CREDENTIAL_REQUEST_PATTERNS = [
    re.compile(r"(share|provide|send|tell|give|enter|confirm|verify).{0,40}\b(pin|otp|password|card number|cvv)\b", re.I),
    re.compile(r"\b(pin|otp|password|card number|cvv)\b.{0,40}(share|provide|send|tell|give|enter|confirm)", re.I),
]


def _strip_credential_requests(text: str) -> str:
    """Remove any sentence that asks the customer for a credential."""
    sentences = re.split(r"(?<=[.!?।])\s+", text)
    kept = []
    for s in sentences:
        if any(p.search(s) for p in _CREDENTIAL_REQUEST_PATTERNS):
            # Drop the sentence — but only if it's a REQUEST, not a warning.
            # Warnings like "do not share your PIN" are safe and must survive.
            if re.search(r"\b(do not|don't|never|will not|won't)\b", s, re.I):
                kept.append(s)
            # otherwise: drop it
        else:
            kept.append(s)
    return " ".join(kept).strip()


def _rewrite_unauthorized_promises(text: str) -> str:
    for pattern, replacement in _UNAUTHORIZED_PROMISE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def enforce_customer_reply_safety(text: str, language: str = "en") -> str:
    """
    Final safety pass for any customer-facing reply.

    1. Strip sentences that REQUEST credentials (keep warnings).
    2. Rewrite unauthorized refund/reversal promises into safe language.
    3. Guarantee a 'do not share PIN/OTP' reminder is present.
    """
    if not text:
        text = "Thank you for reaching out. Our team will review your case and contact you through official support channels."

    text = _strip_credential_requests(text)
    text = _rewrite_unauthorized_promises(text)

    # Ensure the credential-safety reminder is present (English replies).
    # For Bangla replies the caller is expected to supply a Bangla reminder;
    # we only auto-append for English/mixed to avoid mismatched-language text.
    has_reminder = re.search(r"\b(pin|otp)\b", text, re.I) and re.search(r"\b(do not|don't|never)\b", text, re.I)
    if not has_reminder and language in ("en", "mixed"):
        text = text.rstrip() + " " + PIN_OTP_REMINDER

    return text.strip()


# ---------------------------------------------------------------------------
# Prompt-injection defense for any LLM you add later.
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = [
    re.compile(r"ignore (all |previous |the )?(instructions|rules|prompt)", re.I),
    re.compile(r"disregard (all |previous |the )?(instructions|rules)", re.I),
    re.compile(r"you are now", re.I),
    re.compile(r"system prompt", re.I),
    re.compile(r"reveal (your )?(prompt|instructions|system)", re.I),
]


def detect_injection(complaint: str) -> bool:
    """True if the complaint appears to contain prompt-injection instructions."""
    return any(p.search(complaint) for p in _INJECTION_PATTERNS)
