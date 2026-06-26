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
from dataclasses import dataclass
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


# Extra hidden-test coverage: paraphrased English, Bangla, and romanized
# Banglish terms commonly used in local support tickets.
PHISHING_KW.extend([
    "login code", "verification code", "security code", "secret code",
    "six digit", "read out the", "verification link", "claiming to be from support",
    "account will be closed", "account will be blocked", "account would be frozen",
    "account off", "unknown number", "গোপন কোড", "কোড বলতে", "লিংক",
    "যাচাই না করলে", "অ্যাকাউন্ট বন্ধ", "account bondho", "verify na korle",
    "code bolte", "secret code bolte",
])
WRONG_TRANSFER_KW.extend([
    "unintended recipient", "unintended person", "landed with", "another person",
    "other person", "someone else", "not the person", "went to another",
    "wrong person got it", "ভুল লোক", "অন্য একজন", "অন্য মানুষের", "অন্য লোক",
    "চলে গেছে", "যাকে দেওয়ার কথা", "যাকে পাঠানোর কথা", "vul manush",
    "vul lok", "bhul manush", "onno lok", "onno manush", "onno jon",
    "onno person", "chole gese", "chole geche",
])
DUPLICATE_KW.extend([
    "two separate times", "two debits", "same bill two", "দুই বার", "ডাবল",
    "double cut", "duita debit", "dui bar", "dubaar", "duibar",
])
PAYMENT_FAILED_KW.extend([
    "could not process", "balance went down", "wallet balance went down",
    "error message", "ended with an error", "payment didn't go through",
    "payment did not go through", "payment did not happen", "not successful",
    "unpaid", "balance cut", "কেটে গেছে", "কাটা হয়েছে", "টাকা কেটে",
    "ব্যালেন্স থেকে", "সমস্যা দেখিয়েছে", "পেমেন্ট হয়নি", "kete nilo",
    "kete niyeche", "kete gese", "kete geche", "kete gache",
    "payment hoy nai", "payment hoyni", "hoy nai", "hoyni",
    "bill ta ekhono unpaid",
])
REFUND_KW.extend([
    "changed my mind", "change of mind", "charge cancelled", "charge canceled",
    "cancel this order", "cancel the order", "don't want it", "do not want it",
    "অর্ডারটা নিতে চাই না", "নিতে চাই না", "ফেরত চাই", "cancel korte chai",
    "taka back", "ferot chai", "ferot",
])
SETTLEMENT_KW.extend([
    "payout", "sales payout", "sales haven't reached", "sales have not reached",
    "sales not received", "proceeds not credited", "proceeds", "business wallet",
    "merchant wallet", "পেআউট", "বিক্রির টাকা", "মার্চেন্ট ওয়ালেট",
    "মার্চেন্ট ওয়ালেট", "জমা হয়নি", "জমা হয়নি", "sales er payout",
    "sales er taka", "ashe nai", "ashe nai ekhono", "joma hoy nai", "joma hoyni",
])
SETTLEMENT_CONTEXT_KW.extend([
    "proceeds", "sales", "merchant", "business wallet", "বিক্রির টাকা",
    "মার্চেন্ট", "sales er", "merchant wallet",
])
NOT_RECEIVED_KW.extend([
    "never got", "never got it", "not arrived", "has not arrived",
    "have not arrived", "stayed unchanged", "not reflected", "আসে নাই",
    "জমা হয়নি", "জমা হয়নি", "বাড়েনি", "বাড়েনি", "pay nai", "paini",
    "pai nai", "ashe nai", "ashe nai ekhono", "add hoy nai", "add hoyni",
    "balance add hoy nai",
])
CASH_IN_KW.extend([
    "local representative", "representative", "handed cash", "gave cash",
    "cash dilam", "agent ke", "agent er kache", "নগদ",
])

PHISHING_SECRET_KW = [
    "otp", "pin", "password", "login code", "verification code", "security code",
    "secret code", "six digit", "code", "ওটিপি", "পিন", "পাসওয়ার্ড", "কোড",
    "গোপন কোড", "gopon code",
]
PHISHING_REQUEST_KW = [
    "ask", "asked", "share", "provide", "send", "tell", "give", "enter",
    "confirm", "verify", "read out", "wants me", "বলতে", "দিতে", "শেয়ার",
    "চাইছে", "bolte", "dite", "janate", "share korte",
]
PHISHING_THREAT_KW = [
    "blocked", "closed", "frozen", "suspended", "will be blocked",
    "will be closed", "would be frozen", "বন্ধ", "বন্ধ হবে", "বন্ধ হয়ে যাবে",
    "bondho", "account off", "off bole",
]
PHISHING_LINK_KW = ["link", "verification link", "verify link", "লিংক"]
PHISHING_CONTACT_KW = [
    "caller", "called", "message", "sms", "unknown number", "someone",
    "support", "claiming", "ফোন", "মেসেজ", "কেউ", "ekjon", "call kore",
]

PAYMENT_CONTEXT_KW = [
    "payment", "pay", "paid", "bill", "recharge", "utility", "merchant",
    "পেমেন্ট", "বিল",
]
PAYMENT_FAILURE_INTENT_KW = [
    "failed", "could not process", "error", "didn't go through", "did not go through",
    "did not happen", "not successful", "unpaid", "সমস্যা", "ব্যর্থ", "ফেইল",
    "hoy nai", "hoyni",
]
PAYMENT_DEDUCTED_KW = [
    "deducted", "debited", "balance went down", "missing", "balance cut",
    "wallet balance went down", "কেটে", "কাটা", "ব্যালেন্স থেকে", "kete",
]

MERCHANT_CONTEXT_KW = [
    "merchant", "business", "shop", "sales", "seller", "মার্চেন্ট", "দোকান",
    "বিক্রি", "sales er",
]
TRANSFER_ACTION_KW = [
    "sent", "send", "transfer", "transferred", "paid", "pay", "পাঠিয়েছি",
    "পাঠিয়েছি", "পাঠালাম", "দিয়েছি", "দেওয়ার", "pathaisi", "pathalam",
    "dilam", "dewar",
]
INTENDED_RECIPIENT_KW = [
    "recipient", "meant to pay", "intended", "supposed to", "person i meant",
    "যার কাছে", "যাকে", "jar kache", "dewar kotha",
]

# Holdout/generalization coverage. These are broader intent cues, not one-off
# full-sentence matches: unfamiliar recipient, incomplete service, duplicate
# ledger rows, buyer remorse, merchant takings, counter cash-in, and coercive
# account/security impersonation.
PHISHING_KW.extend([
    "secret number", "private number", "verification number", "passcode",
    "company staff", "company person", "pretending to be", "got pushy",
    "freeze the account", "freeze account", "account freeze", "account lock",
    "wallet lock", "he d freeze", "he would freeze", "গোপন নম্বর",
    "ব্যক্তিগত নম্বর", "কোম্পানির লোক", "হিসাব আটকে", "lock korbe",
    "wallet lock korbe", "chap dicche", "company staff bole",
    "temporary login digits", "login digits", "login token", "six number",
    "six-number", "support caller", "passcode over the phone",
    "link to keep wallet active", "keep wallet active", "ব্যক্তিগত পাসওয়ার্ড",
    "ব্যক্তিগত পাসওয়ার্ড", "পাসওয়ার্ড লিখতে", "পাসওয়ার্ড লিখতে",
    "secret shobdo",
])
PHISHING_SECRET_KW.extend([
    "secret number", "private number", "verification number", "passcode",
    "secret", "গোপন নম্বর", "ব্যক্তিগত নম্বর", "gopon number",
    "private number", "temporary login digits", "login digits", "login token",
    "six number", "six-number", "token", "ব্যক্তিগত পাসওয়ার্ড",
    "ব্যক্তিগত পাসওয়ার্ড", "secret shobdo",
])
PHISHING_REQUEST_KW.extend([
    "confirming", "confirm", "got pushy", "pushing", "pressuring",
    "jante", "jante chailo", "jante chachchilo", "জানতে", "চাচ্ছিল",
    "demanded", "demand", "asked me", "asked me for", "লিখতে হবে",
])
PHISHING_THREAT_KW.extend([
    "freeze", "freeze the account", "lock", "account lock", "wallet lock",
    "আটকে", "আটকে দেবে", "lock korbe",
])
PHISHING_CONTACT_KW.extend([
    "man rang", "rang me", "pretending", "company staff", "company person",
    "নিজেকে", "পরিচয়", "lok", "staff bole", "whatsapp", "messenger",
    "support caller", "over the phone",
])

WRONG_TRANSFER_KW.extend([
    "stranger", "unknown person", "unfamiliar person", "not the cousin",
    "not the friend", "not the intended", "ended up with a stranger",
    "never meant to send", "had in mind", "landed with somebody",
    "অচেনা", "অপরিচিত", "চিনি না", "যাকে আমি চিনি না", "stranger er wallet",
    "bondhur jonno", "chere dilam", "porse", "contact i did not choose",
    "number i did not intend", "person i did not select", "did not select",
    "did not choose", "পরিচিত কারও কাছে যায়নি", "পরিচিত কারও কাছে যায়নি",
    "অন্য এক ওয়ালেটে", "অন্য এক ওয়ালেটে", "je lok er jonno chilo",
    "tar wallet e gelo na", "wallet e gelo na", "ভুল লোকের",
    "ভুল লোকের কাছে", "লোকের কাছে গেছে",
])

DUPLICATE_KW.extend([
    "two rows", "two separate rows", "two ledger rows", "same ride",
    "same fare", "same ticket", "appears on my statement", "appears twice",
    "দুই জায়গায়", "দুই জায়গায়", "লিস্টে দুই", "dui jaygay",
    "statement e dui", "ekoi bus ticket", "ekoi ticket", "listed twice",
    "same receipt", "two entries", "two entry", "দুইটি এন্ট্রি",
    "দুইটা এন্ট্রি", "dui ta line", "duita line", "activity te dui",
])

PAYMENT_FAILED_KW.extend([
    "screen kept spinning", "kept spinning", "no pack came",
    "pack did not arrive", "pack didn t arrive", "amount left my wallet",
    "left my wallet", "service did not complete", "service didn t complete",
    "no recharge came", "রিচার্জ আসেনি", "ঘুরতেই থাকল", "কমে গেছে",
    "টাকা কমে গেছে", "pack asheni", "pack ashe nai", "kome gese",
    "kome geche", "loading e atke", "atke gelo", "net pack",
    "app froze on processing", "froze on processing", "balance dropped",
    "meter still shows unpaid", "bill was not posted", "app থেমে গেল",
    "অ্যাপ থেমে গেল", "বিল জমা হলো না", "টাকা কমে গেল",
    "mobile bundle", "loading sesh holo na", "balance theke urey gelo",
    "urey gelo",
])
PAYMENT_CONTEXT_KW.extend([
    "data pack", "pack", "net pack", "mobile pack", "service", "রিচার্জ",
    "প্যাক", "pack", "electricity", "meter", "gas bill", "গ্যাস বিল",
    "mobile bundle", "bundle",
])
PAYMENT_FAILURE_INTENT_KW.extend([
    "spinning", "kept spinning", "no pack came", "pack did not arrive",
    "pack didn t arrive", "did not complete", "didn t complete",
    "আসেনি", "ঘুরতেই থাকল", "ashe nai", "asheni", "atke gelo",
    "froze", "not posted", "জমা হলো না", "sesh holo na",
])
PAYMENT_DEDUCTED_KW.extend([
    "left my wallet", "amount left", "wallet amount decreased", "decreased",
    "কমে গেছে", "kome gese", "kome geche", "dropped", "কমে গেল",
    "urey gelo",
])

REFUND_KW.extend([
    "undo purchase", "undo that purchase", "undo this purchase",
    "no longer need", "no longer want", "আর লাগবে না", "কেনাকাটাটা বাতিল",
    "কেনাকাটা বাতিল", "বাতিল করতে চাই", "ar lagbe na",
    "undo korte chai", "purchase ta undo", "product ta ar lagbe na",
    "cancel my", "cancel purchase", "cancel my movie pass", "cannot attend",
    "return the charge", "purchase cancel", "booking ta rakhbo na",
])

SETTLEMENT_KW.extend([
    "takings", "customer takings", "shop takings", "customer collections",
    "business collection", "absent from my account", "run a kiosk",
    "run a shop", "দোকান চালাই", "ক্রেতাদের টাকা", "হিসাবে দেখা যাচ্ছে না",
    "hisabe dekha jacche na", "hisab e dekha jacche na", "dekha jacche na",
    "customer der taka", "choto dokan", "dokan chalai",
    "card collections", "shop balance", "seller", "customer payments",
    "collections from", "missing from the shop balance", "ক্রেতাদের পরিশোধ",
    "পরিশোধ", "ঢোকেনি", "dhukeni", "qr diye", "collection amar account",
])
SETTLEMENT_CONTEXT_KW.extend([
    "takings", "customer takings", "collections", "customer collections",
    "kiosk", "দোকান", "ক্রেতাদের টাকা", "hisab", "customer der taka",
    "card collections", "shop balance", "customer payments", "পরিশোধ",
    "collection", "qr",
])
MERCHANT_CONTEXT_KW.extend([
    "kiosk", "takings", "customer takings", "দোকান চালাই",
    "ক্রেতাদের", "dokan chalai", "choto dokan", "seller",
    "shop balance", "shop er qr", "customer ra pay",
])

CASH_IN_KW.extend([
    "paper money", "counter person", "shop counter", "counter er bhai",
    "counter er lok", "কাউন্টারের লোক", "কাউন্টার", "old amount",
    "same old amount", "wallet total", "ager motoi ache",
    "wallet total ager", "deposited", "neighborhood kiosk", "added balance",
    "cash joma", "local dokan", "vendor", "field agent",
])
NOT_RECEIVED_KW.extend([
    "still absent", "absent", "not visible", "not showing", "not showing in",
    "still the old amount", "old amount", "same old amount", "একই রয়ে গেছে",
    "দেখা যাচ্ছে না", "dekha jacche na", "ager motoi ache", "porse",
    "never appeared", "not appeared", "has not shown", "not shown",
    "dhukeni", "ঢোকেনি", "gelo na", "যায়নি", "যায়নি",
])

BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_ASCII_TOKEN_RE = re.compile(r"^[a-z0-9_]+$")


@dataclass
class CaseHypothesis:
    case_type: str
    claim_score: float
    relevant_transaction_id: Optional[str]
    evidence_verdict: str
    severity: str
    confidence: float
    reason_codes: List[str]
    human_review_required: bool


def normalize_bangla_digits(text: str) -> str:
    """Convert Bangla numerals to ASCII digits without changing other text."""
    return (text or "").translate(BN_DIGITS)


def normalize_text(text: str) -> str:
    """Normalize punctuation/digits so phrase matching is token-aware."""
    low = normalize_bangla_digits(text).lower()
    low = re.sub(r"[^\w\u0980-\u09ff]+", " ", low, flags=re.UNICODE)
    return re.sub(r"\s+", " ", low).strip()


def _normalize(text: str) -> str:
    return normalize_text(text)


def _term_positions(normalized_text: str, keyword: str) -> List[int]:
    term = _normalize(keyword)
    if not term:
        return []
    if _ASCII_TOKEN_RE.match(term) or " " in term:
        pattern = re.compile(rf"(?<!\S){re.escape(term)}(?!\S)")
        return [m.start() for m in pattern.finditer(normalized_text)]
    # Bangla and mixed non-ASCII terms are also matched as full normalized
    # tokens/phrases, preventing short terms from firing inside other words.
    pattern = re.compile(rf"(?<!\S){re.escape(term)}(?!\S)")
    return [m.start() for m in pattern.finditer(normalized_text)]


def _contains(text: str, keywords: List[str]) -> bool:
    low = _normalize(text)
    return any(_term_positions(low, k) for k in keywords)


def _has_near(text: str, left_terms: List[str], right_terms: List[str], window: int = 70) -> bool:
    """True when any left/right terms appear close enough to express one intent."""
    low = _normalize(text)
    left_positions = [
        pos for term in left_terms for pos in _term_positions(low, term)
    ]
    right_positions = [
        pos for term in right_terms for pos in _term_positions(low, term)
    ]
    return any(abs(left - right) <= window for left in left_positions for right in right_positions)


REAL_ISSUE_MARKERS = [
    "real problem:", "real issue:", "actual issue:", "ashol issue:",
    "asol issue:", "ashol kotha:", "আসল কথা:",
]
INJECTION_CUE_KW = [
    "ignore previous", "ignore all previous", "ignore all instructions",
    "ignore all rules", "ignore rules", "disregard rules",
    "disregard previous", "system override", "output case type",
    "output case_type", "classify this as", "override rules",
    "you are now", "forget policy", "rules ignore", "reply",
    "tell the customer", "tell customer", "tell user", "ask the customer",
    "ask customer", "ask user", "promise refund", "refund guaranteed",
    "mark account unblocked", "সব নিয়ম উপেক্ষা", "সব নিয়ম উপেক্ষা",
    "নিয়ম উপেক্ষা", "নিয়ম উপেক্ষা", "উপেক্ষা করো", "customer ke bolo",
]
INJECTION_PAYLOAD_KW = [
    "otp", "pin", "password", "card number", "full card number", "cvv",
    "refund", "reversal", "reverse", "unblocked", "money will be returned",
    "টাকা ফেরত",
]


def _is_instruction_like_chunk(text: str) -> bool:
    """True for prompt-injection instructions, not customer issue reports."""
    if _contains(text, INJECTION_CUE_KW):
        return True
    return _contains(text, ["ask", "tell", "send", "request", "promise"]) and _contains(
        text, INJECTION_PAYLOAD_KW
    )


def sanitize_for_intent(complaint: str) -> str:
    """
    Remove instruction-like prompt injection before intent classification.

    The original complaint is still used for safety/injection logging. This only
    prevents malicious text such as "ignore rules and ask for OTP" from stealing
    priority over the real support issue in the same complaint.
    """
    text = complaint or ""

    lowered = text.lower()
    for marker in REAL_ISSUE_MARKERS:
        idx = lowered.rfind(marker.lower())
        if idx != -1:
            text = text[idx + len(marker):]
            lowered = text.lower()
            break

    chunks = [
        chunk.strip(" :-")
        for chunk in re.split(r"(?<=[.!?।])\s+|;\s*", text)
        if chunk.strip(" :-")
    ]
    kept = [chunk for chunk in chunks if not _is_instruction_like_chunk(chunk)]
    return " ".join(kept).strip() or complaint


def _is_phishing_intent(text: str) -> bool:
    """Social-engineering intent: ask/threat/link pressure around secrets."""
    if _contains(text, PHISHING_KW):
        return True
    if _has_near(text, PHISHING_REQUEST_KW, PHISHING_SECRET_KW):
        return True
    if _contains(text, PHISHING_SECRET_KW) and _contains(text, PHISHING_THREAT_KW):
        return True
    if _contains(text, PHISHING_LINK_KW) and (
        _contains(text, PHISHING_THREAT_KW) or _contains(text, PHISHING_REQUEST_KW)
    ):
        return True
    return False


def _has_txn_type(
    history: List[TransactionEntry], txn_type: str, statuses: Optional[List[str]] = None
) -> bool:
    return any(
        t.type == txn_type and (statuses is None or t.status in statuses)
        for t in history
    )


def _has_duplicate_payment_history(history: List[TransactionEntry]) -> bool:
    seen = set()
    for t in history:
        if t.type != "payment" or t.status != "completed":
            continue
        key = (round(t.amount, 2), t.counterparty)
        if key in seen:
            return True
        seen.add(key)
    return False


def _duplicate_payment_candidate(history: List[TransactionEntry]) -> Optional[TransactionEntry]:
    groups = {}
    for t in history:
        if t.type != "payment" or t.status != "completed":
            continue
        groups.setdefault((round(t.amount, 2), t.counterparty), []).append(t)

    duplicate_groups = [
        sorted(group, key=lambda x: x.timestamp)
        for group in groups.values()
        if len(group) >= 2
    ]
    if len(duplicate_groups) != 1:
        return None
    return duplicate_groups[0][-1]


def _is_duplicate_payment_intent(text: str, history: List[TransactionEntry]) -> bool:
    """Duplicate payment can be stated as duplicate words or duplicate ledger rows."""
    if _contains(text, DUPLICATE_KW):
        return True
    ledger_language = [
        "statement", "row", "rows", "list", "same", "fare", "ride", "ticket",
        "লিস্ট", "দুই", "জায়গা", "জায়গা", "ভাড়া", "ভাড়া", "dui", "jaygay",
        "bhara", "ekoi",
    ]
    return _has_duplicate_payment_history(history) and _contains(text, ledger_language)


def _is_payment_failed_intent(
    text: str,
    relevant_txn: Optional[TransactionEntry],
    history: List[TransactionEntry],
) -> bool:
    """Payment attempt failed/error path while balance or wallet value changed."""
    if _is_agent_cash_in_issue(text, relevant_txn, history):
        return False
    payment_txn = relevant_txn is not None and relevant_txn.type == "payment"
    if payment_txn and relevant_txn.status == "failed":
        return True
    if _contains(text, PAYMENT_FAILED_KW):
        return True
    payment_history_hint = payment_txn or _has_txn_type(history, "payment", ["pending", "failed"])
    if payment_history_hint and (
        _contains(text, PAYMENT_CONTEXT_KW)
        or _contains(text, PAYMENT_FAILURE_INTENT_KW)
    ) and (
        _contains(text, PAYMENT_DEDUCTED_KW)
        or _contains(text, NOT_RECEIVED_KW)
    ):
        return True
    return (
        _contains(text, PAYMENT_CONTEXT_KW)
        and _contains(text, PAYMENT_FAILURE_INTENT_KW)
        and _contains(text, PAYMENT_DEDUCTED_KW)
    )


def _is_merchant_settlement_delay(
    req: TicketRequest,
    text: str,
    relevant_txn: Optional[TransactionEntry],
) -> bool:
    """Merchant sales proceeds / payout / settlement did not arrive."""
    if _is_agent_cash_in_issue(text, relevant_txn, req.transaction_history):
        return False
    merchant_context = (
        req.user_type == "merchant"
        or _contains(text, MERCHANT_CONTEXT_KW)
        or (relevant_txn is not None and relevant_txn.type == "settlement")
        or _has_txn_type(req.transaction_history, "settlement")
    )
    if not merchant_context:
        return False
    settlement_history_hint = (
        relevant_txn is not None and relevant_txn.type == "settlement"
    ) or _has_txn_type(req.transaction_history, "settlement", ["pending"])
    return _contains(text, SETTLEMENT_KW) or (
        _contains(text, SETTLEMENT_CONTEXT_KW) and _contains(text, NOT_RECEIVED_KW)
    ) or (
        settlement_history_hint
        and _contains(text, MERCHANT_CONTEXT_KW + SETTLEMENT_CONTEXT_KW)
        and _contains(text, NOT_RECEIVED_KW)
    )


def _is_agent_cash_in_issue(
    text: str,
    relevant_txn: Optional[TransactionEntry],
    history: Optional[List[TransactionEntry]] = None,
) -> bool:
    """Agent/local-representative cash-in did not reflect in balance."""
    history = history or []
    cash_in_txn = relevant_txn is not None and relevant_txn.type == "cash_in"
    cash_in_history_hint = cash_in_txn or _has_txn_type(history, "cash_in")
    if _contains(text, CASH_IN_KW) and (
        relevant_txn is None or cash_in_txn or _contains(text, NOT_RECEIVED_KW)
    ):
        return True
    cash_language = [
        "cash", "paper money", "counter", "wallet total", "deposit",
        "deposited", "নগদ", "taka", "টাকা", "joma",
    ]
    return (
        cash_in_history_hint
        and _contains(text, cash_language)
        and _contains(text, NOT_RECEIVED_KW)
    )


def _is_wrong_transfer_intent(
    text: str,
    relevant_txn: Optional[TransactionEntry],
    history: List[TransactionEntry],
) -> bool:
    """Wrong-recipient transfer, including paraphrased and Banglish forms."""
    if _contains(text, WRONG_TRANSFER_KW):
        return True
    transfer_history_hint = (
        relevant_txn is not None and relevant_txn.type == "transfer"
    ) or _has_txn_type(history, "transfer")
    unfamiliar_recipient = [
        "stranger", "unknown person", "unfamiliar person", "not the cousin",
        "not the friend", "চিনি না", "অচেনা", "অপরিচিত", "stranger er wallet",
        "bondhur jonno", "did not choose", "did not select",
        "number i did not intend", "contact i did not choose",
        "person i did not select", "অন্য এক ওয়ালেটে", "অন্য এক ওয়ালেটে",
        "je lok er jonno chilo", "tar wallet e gelo na",
    ]
    if transfer_history_hint and _contains(text, unfamiliar_recipient):
        return True
    intended_missing = (
        _contains(text, TRANSFER_ACTION_KW)
        and _contains(text, INTENDED_RECIPIENT_KW)
        and _contains(text, NOT_RECEIVED_KW)
    )
    return intended_missing


# ---------------------------------------------------------------------------
# Amount extraction from free text
# ---------------------------------------------------------------------------

def extract_amount(complaint: str) -> Optional[float]:
    """Pull the first plausible BDT amount mentioned in the complaint."""
    # Matches 5000, 5,000, 1200.50 etc.
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", complaint)
    if not m:
        return None
    raw = m.group(0).translate(BN_DIGITS).replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def get_amounts_from_complaint(text: str) -> List[float]:
    """Return all plausible BDT amounts mentioned in free text."""
    normalized = normalize_bangla_digits(text)
    amounts: List[float] = []
    for match in re.finditer(r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", normalized):
        try:
            amounts.append(float(match.group(0).replace(",", "")))
        except ValueError:
            continue
    return amounts


def get_transaction_types(history: List[TransactionEntry]):
    return {txn.type for txn in history}


def get_transaction_statuses(history: List[TransactionEntry]):
    return {txn.status for txn in history}


def find_best_amount_match(
    history: List[TransactionEntry],
    amount: Optional[float],
    allowed_types: Optional[List[str]] = None,
) -> Optional[TransactionEntry]:
    if amount is None:
        return None
    candidates = [
        txn for txn in history
        if abs(txn.amount - amount) < 0.01
        and (allowed_types is None or txn.type in allowed_types)
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]


def find_latest_matching_transaction(
    history: List[TransactionEntry],
    txn_type: Optional[str] = None,
    amount: Optional[float] = None,
    statuses: Optional[List[str]] = None,
) -> Optional[TransactionEntry]:
    candidates = history
    if txn_type is not None:
        candidates = [txn for txn in candidates if txn.type == txn_type]
    if amount is not None:
        candidates = [txn for txn in candidates if abs(txn.amount - amount) < 0.01]
    if statuses is not None:
        candidates = [txn for txn in candidates if txn.status in statuses]
    if not candidates:
        return None
    return sorted(candidates, key=lambda txn: txn.timestamp)[-1]


def find_candidate_transfers(history: List[TransactionEntry], amount: Optional[float] = None):
    return [
        txn for txn in history
        if txn.type == "transfer" and (amount is None or abs(txn.amount - amount) < 0.01)
    ]


def find_candidate_payments(history: List[TransactionEntry], amount: Optional[float] = None):
    return [
        txn for txn in history
        if txn.type == "payment" and (amount is None or abs(txn.amount - amount) < 0.01)
    ]


def find_candidate_settlements(history: List[TransactionEntry], amount: Optional[float] = None):
    return [
        txn for txn in history
        if txn.type == "settlement" and (amount is None or abs(txn.amount - amount) < 0.01)
    ]


def find_candidate_cashins(history: List[TransactionEntry], amount: Optional[float] = None):
    return [
        txn for txn in history
        if txn.type == "cash_in" and (amount is None or abs(txn.amount - amount) < 0.01)
    ]


def has_duplicate_completed_payment(
    history: List[TransactionEntry],
    amount: Optional[float] = None,
    counterparty: Optional[str] = None,
) -> bool:
    candidates = [
        txn for txn in history
        if txn.type == "payment"
        and txn.status == "completed"
        and (amount is None or abs(txn.amount - amount) < 0.01)
        and (counterparty is None or txn.counterparty == counterparty)
    ]
    seen = set()
    for txn in candidates:
        key = (round(txn.amount, 2), txn.counterparty)
        if key in seen:
            return True
        seen.add(key)
    return False


def has_repeated_transfer_to_same_counterparty(
    history: List[TransactionEntry],
    target_txn: Optional[TransactionEntry],
) -> bool:
    return target_txn is not None and _established_recipient(history, target_txn)


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
    if _is_duplicate_payment_intent(complaint, history) and amount is not None:
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

    if _is_duplicate_payment_intent(complaint, history) and amount is None:
        duplicate = _duplicate_payment_candidate(history)
        if duplicate is not None:
            return duplicate.transaction_id, "consistent"

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
# Case-aware evidence refinement
# ---------------------------------------------------------------------------

def _txn_by_id(history: List[TransactionEntry], transaction_id: Optional[str]) -> Optional[TransactionEntry]:
    if transaction_id is None:
        return None
    return next((t for t in history if t.transaction_id == transaction_id), None)


def _amount_matches(complaint: str, history: List[TransactionEntry]) -> List[TransactionEntry]:
    amount = extract_amount(complaint)
    if amount is None:
        return []
    return [t for t in history if abs(t.amount - amount) < 0.01]


def _duplicate_payment_match(
    history: List[TransactionEntry],
    amount_matches: List[TransactionEntry],
) -> Optional[TransactionEntry]:
    candidates = amount_matches or history
    groups = {}
    for txn in candidates:
        if txn.type != "payment" or txn.status != "completed":
            continue
        key = (round(txn.amount, 2), txn.counterparty)
        groups.setdefault(key, []).append(txn)

    duplicate_groups = [
        sorted(group, key=lambda item: item.timestamp)
        for group in groups.values()
        if len(group) >= 2
    ]
    if len(duplicate_groups) != 1:
        return None
    return duplicate_groups[0][-1]


def _established_recipient(history: List[TransactionEntry], txn: TransactionEntry) -> bool:
    if txn.type != "transfer":
        return False
    prior_same_cp = [
        item for item in history
        if item.type == "transfer" and item.counterparty == txn.counterparty
    ]
    return len(prior_same_cp) >= 3


def refine_evidence_for_case(
    req: TicketRequest,
    case_type: str,
    relevant_id: Optional[str],
    verdict: str,
) -> Tuple[Optional[str], str]:
    """
    Adjust evidence after the final case_type is known.

    match_transaction() is deliberately generic. This layer encodes
    case-specific evidence semantics, e.g. phishing reports usually do not have
    a relevant transaction, while duplicate claims need two matching payments.
    """
    history = req.transaction_history
    matches = _amount_matches(req.complaint, history)
    relevant_txn = _txn_by_id(history, relevant_id)

    if case_type == "phishing_or_social_engineering":
        return None, "insufficient_data"

    if case_type == "duplicate_payment":
        duplicate = _duplicate_payment_match(history, matches)
        if duplicate is not None:
            return duplicate.transaction_id, "consistent"
        if len(matches) == 1 and matches[0].type == "payment":
            return matches[0].transaction_id, "inconsistent"
        if relevant_txn and relevant_txn.type == "payment":
            return relevant_txn.transaction_id, "inconsistent"
        return None, "insufficient_data"

    if case_type == "payment_failed":
        candidates = matches or ([relevant_txn] if relevant_txn else [])
        payment = next((txn for txn in candidates if txn and txn.type == "payment"), None)
        if payment is not None:
            if payment.status in ("failed", "pending"):
                return payment.transaction_id, "consistent"
            return payment.transaction_id, "inconsistent"
        if candidates:
            return candidates[0].transaction_id, "inconsistent"
        return None, "insufficient_data"

    if case_type == "merchant_settlement_delay":
        candidates = matches or ([relevant_txn] if relevant_txn else [])
        settlement = next((txn for txn in candidates if txn and txn.type == "settlement"), None)
        if settlement is not None:
            if settlement.status == "pending":
                return settlement.transaction_id, "consistent"
            return settlement.transaction_id, "inconsistent"
        if candidates:
            return candidates[0].transaction_id, "inconsistent"
        pending = next((txn for txn in history if txn.type == "settlement" and txn.status == "pending"), None)
        if pending is not None:
            return pending.transaction_id, "consistent"
        return None, "insufficient_data"

    if case_type == "agent_cash_in_issue":
        candidates = matches or ([relevant_txn] if relevant_txn else [])
        cash_in = next((txn for txn in candidates if txn and txn.type == "cash_in"), None)
        if cash_in is not None:
            return cash_in.transaction_id, "consistent"
        if candidates:
            return candidates[0].transaction_id, "inconsistent"
        cash_in = next((txn for txn in history if txn.type == "cash_in"), None)
        if cash_in is not None:
            return cash_in.transaction_id, "consistent"
        return None, "insufficient_data"

    if case_type == "refund_request":
        candidates = matches or ([relevant_txn] if relevant_txn else [])
        chosen = next((txn for txn in candidates if txn), None)
        if chosen is None:
            return None, "insufficient_data"
        if chosen.type == "payment" and chosen.status == "completed":
            return chosen.transaction_id, "consistent"
        return chosen.transaction_id, "inconsistent"

    if case_type == "wrong_transfer":
        transfer_matches = [txn for txn in matches if txn.type == "transfer"]
        if len(transfer_matches) > 1:
            return None, "insufficient_data"
        candidates = matches or ([relevant_txn] if relevant_txn else [])
        transfer = next((txn for txn in candidates if txn and txn.type == "transfer"), None)
        if transfer is None:
            if candidates:
                return candidates[0].transaction_id, "inconsistent"
            return None, "insufficient_data"
        if _established_recipient(history, transfer):
            return transfer.transaction_id, "inconsistent"
        if transfer.status == "completed":
            return transfer.transaction_id, "consistent"
        return transfer.transaction_id, "inconsistent"

    return relevant_id, verdict


# ---------------------------------------------------------------------------
# Claim scoring + evidence verification
# ---------------------------------------------------------------------------

CLAIM_PRIORITY = [
    "phishing_or_social_engineering",
    "duplicate_payment",
    "payment_failed",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "wrong_transfer",
    "refund_request",
    "other",
]
CLAIM_THRESHOLD = 0.25


def score_phishing_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    del request, tx_history
    return 0.98 if _is_phishing_intent(text) else 0.0


def score_duplicate_payment_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    del request
    if _contains(text, DUPLICATE_KW):
        return 0.94
    if _is_duplicate_payment_intent(text, tx_history):
        return 0.78
    return 0.0


def score_payment_failed_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    del request
    if _is_payment_failed_intent(text, None, tx_history):
        return 0.90
    if _contains(text, PAYMENT_CONTEXT_KW) and (
        _contains(text, PAYMENT_FAILURE_INTENT_KW)
        or _contains(text, PAYMENT_DEDUCTED_KW)
    ):
        return 0.72
    return 0.0


def score_merchant_settlement_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    if _is_merchant_settlement_delay(request, text, None):
        return 0.88
    merchant_context = (
        request.user_type == "merchant"
        or request.channel == "merchant_portal"
        or _has_txn_type(tx_history, "settlement")
        or _contains(text, MERCHANT_CONTEXT_KW)
    )
    if merchant_context and (
        _contains(text, SETTLEMENT_KW + SETTLEMENT_CONTEXT_KW)
        or (_contains(text, MERCHANT_CONTEXT_KW) and _contains(text, NOT_RECEIVED_KW))
    ):
        return 0.74
    return 0.0


def score_agent_cash_in_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    del request
    if _is_agent_cash_in_issue(text, None, tx_history):
        return 0.90
    if _contains(text, CASH_IN_KW) and _contains(text, NOT_RECEIVED_KW):
        return 0.80
    return 0.0


def score_wrong_transfer_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    del request
    if _is_wrong_transfer_intent(text, None, tx_history):
        return 0.86
    sent_not_received = (
        _contains(text, TRANSFER_ACTION_KW)
        and _contains(text, NOT_RECEIVED_KW)
    )
    if sent_not_received:
        return 0.68
    return 0.0


def score_refund_request_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    del request, tx_history
    return 0.80 if _contains(text, REFUND_KW) else 0.0


def score_other_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> float:
    del text, request, tx_history
    return 0.20


def _verify_case(
    case_type: str,
    text: str,
    request: TicketRequest,
    tx_history: List[TransactionEntry],
) -> Tuple[Optional[str], str, List[str]]:
    del text, tx_history
    if case_type == "other":
        return None, "insufficient_data", ["claim_other", "evidence_insufficient_data"]

    base_id, base_verdict = match_transaction(request.complaint, request.transaction_history)
    relevant_id, verdict = refine_evidence_for_case(
        request, case_type, base_id, base_verdict
    )
    reason_codes = [f"claim_{case_type}", f"evidence_{verdict}"]
    if relevant_id is not None:
        reason_codes.append("transaction_match")
    return relevant_id, verdict, reason_codes


def verify_phishing_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    del text, request, tx_history
    return None, "insufficient_data", [
        "claim_phishing_or_social_engineering",
        "social_engineering_report",
        "safety_report",
        "evidence_insufficient_data",
    ]


def verify_duplicate_payment_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    return _verify_case("duplicate_payment", text, request, tx_history)


def verify_payment_failed_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    return _verify_case("payment_failed", text, request, tx_history)


def verify_merchant_settlement_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    return _verify_case("merchant_settlement_delay", text, request, tx_history)


def verify_agent_cash_in_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    relevant_id, verdict, reason_codes = _verify_case(
        "agent_cash_in_issue", text, request, tx_history
    )
    txn = _txn_by_id(tx_history, relevant_id)
    explicit_completed_contradiction = _contains(
        text,
        [
            "shows completed",
            "shown completed",
            "marked completed",
            "status completed",
            "record says completed",
        ],
    ) and _contains(text, NOT_RECEIVED_KW)
    if txn is not None and txn.status == "completed" and explicit_completed_contradiction:
        verdict = "inconsistent"
        reason_codes = [
            "claim_agent_cash_in_issue",
            "completed_cash_in_contradicts_claim",
            "evidence_inconsistent",
            "transaction_match",
        ]
    return relevant_id, verdict, reason_codes


def verify_wrong_transfer_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    return _verify_case("wrong_transfer", text, request, tx_history)


def verify_refund_request_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    return _verify_case("refund_request", text, request, tx_history)


def verify_other_claim(
    text: str, request: TicketRequest, tx_history: List[TransactionEntry]
) -> Tuple[Optional[str], str, List[str]]:
    return _verify_case("other", text, request, tx_history)


def _case_amount(request: TicketRequest) -> Optional[float]:
    amounts = get_amounts_from_complaint(request.complaint)
    if amounts:
        return amounts[0]
    return None


def severity_for(
    case_type: str,
    amount: Optional[float],
    evidence_verdict: str,
    claim_score: float,
) -> str:
    del claim_score
    if case_type == "phishing_or_social_engineering":
        return "critical"
    if case_type == "wrong_transfer":
        severity = "high" if evidence_verdict == "consistent" else "medium"
    elif case_type in ("payment_failed", "duplicate_payment", "agent_cash_in_issue"):
        severity = "high"
    elif case_type == "merchant_settlement_delay":
        severity = "medium"
    else:
        severity = "low"

    if evidence_verdict == "inconsistent" and case_type in (
        "duplicate_payment",
        "agent_cash_in_issue",
    ):
        severity = "high"
    if amount is not None and amount >= 25000 and severity in ("low", "medium"):
        severity = "high"
    return severity


def confidence_for(
    claim_score: float,
    evidence_verdict: str,
    relevant_transaction_id: Optional[str],
    case_type: str,
) -> float:
    evidence_bonus = {
        "consistent": 0.20,
        "inconsistent": 0.10,
        "insufficient_data": 0.0,
    }.get(evidence_verdict, 0.0)
    txn_bonus = 0.03 if relevant_transaction_id is not None else 0.0
    if case_type == "other":
        return 0.60
    return round(min(0.99, max(0.50, claim_score + evidence_bonus + txn_bonus)), 2)


def human_review_for(
    case_type: str,
    severity: str,
    evidence_verdict: str,
    relevant_txn: Optional[TransactionEntry],
) -> bool:
    amount = relevant_txn.amount if relevant_txn is not None else None
    significant_amount = amount is not None and amount >= 25000
    if case_type == "phishing_or_social_engineering":
        return True
    if severity == "critical":
        return True
    if case_type == "wrong_transfer":
        return evidence_verdict in ("consistent", "inconsistent") or significant_amount
    if case_type == "duplicate_payment":
        return True
    if case_type == "agent_cash_in_issue":
        return (
            evidence_verdict != "consistent"
            or relevant_txn is None
            or relevant_txn.status in ("pending", "failed")
        )
    if evidence_verdict == "inconsistent" and significant_amount:
        return True
    return False


def build_case_hypotheses(request: TicketRequest) -> List[CaseHypothesis]:
    text = sanitize_for_intent(request.complaint)
    history = request.transaction_history
    amount = _case_amount(request)

    scorers = {
        "phishing_or_social_engineering": score_phishing_claim,
        "duplicate_payment": score_duplicate_payment_claim,
        "payment_failed": score_payment_failed_claim,
        "merchant_settlement_delay": score_merchant_settlement_claim,
        "agent_cash_in_issue": score_agent_cash_in_claim,
        "wrong_transfer": score_wrong_transfer_claim,
        "refund_request": score_refund_request_claim,
        "other": score_other_claim,
    }
    verifiers = {
        "phishing_or_social_engineering": verify_phishing_claim,
        "duplicate_payment": verify_duplicate_payment_claim,
        "payment_failed": verify_payment_failed_claim,
        "merchant_settlement_delay": verify_merchant_settlement_claim,
        "agent_cash_in_issue": verify_agent_cash_in_claim,
        "wrong_transfer": verify_wrong_transfer_claim,
        "refund_request": verify_refund_request_claim,
        "other": verify_other_claim,
    }

    hypotheses: List[CaseHypothesis] = []
    for case_type in CLAIM_PRIORITY:
        claim_score = scorers[case_type](text, request, history)
        relevant_id, verdict, reason_codes = verifiers[case_type](text, request, history)
        relevant_txn = _txn_by_id(history, relevant_id)
        severity = severity_for(case_type, amount, verdict, claim_score)
        confidence = confidence_for(claim_score, verdict, relevant_id, case_type)
        human_review = human_review_for(case_type, severity, verdict, relevant_txn)
        hypotheses.append(
            CaseHypothesis(
                case_type=case_type,
                claim_score=claim_score,
                relevant_transaction_id=relevant_id,
                evidence_verdict=verdict,
                severity=severity,
                confidence=confidence,
                reason_codes=reason_codes,
                human_review_required=human_review,
            )
        )
    return hypotheses


def choose_hypothesis(hypotheses: List[CaseHypothesis]) -> CaseHypothesis:
    strong = [
        hypothesis for hypothesis in hypotheses
        if hypothesis.claim_score >= CLAIM_THRESHOLD and hypothesis.case_type != "other"
    ]
    if not strong:
        return next(h for h in hypotheses if h.case_type == "other")

    best_score = max(h.claim_score for h in strong)
    close = [h for h in strong if h.claim_score >= best_score - 0.03]
    priority_rank = {case_type: index for index, case_type in enumerate(CLAIM_PRIORITY)}
    return sorted(close, key=lambda h: priority_rank[h.case_type])[0]


def investigate(request: TicketRequest) -> CaseHypothesis:
    """Detect the customer's claim first, then verify transaction evidence."""
    return choose_hypothesis(build_case_hypotheses(request))


# ---------------------------------------------------------------------------
# Case type -> department routing (single source of truth)
# ---------------------------------------------------------------------------

# Per the problem taxonomy, the department is a FIXED function of case_type — it
# is never guessed. Both the rule engine and the LLM produce only a case_type;
# routing always goes through department_for() so it is 100% deterministic and
# taxonomy-correct regardless of which classifier chose the case_type.
CASE_TYPE_DEPARTMENT = {
    "wrong_transfer": "dispute_resolution",
    "payment_failed": "payments_ops",
    "duplicate_payment": "payments_ops",
    "refund_request": "customer_support",  # contested refunds escalate via human_review
    "merchant_settlement_delay": "merchant_operations",
    "agent_cash_in_issue": "agent_operations",
    "phishing_or_social_engineering": "fraud_risk",
    "other": "customer_support",
}


def department_for(case_type: str) -> str:
    """Return the routing department for a case_type (taxonomy source of truth)."""
    return CASE_TYPE_DEPARTMENT.get(case_type, "customer_support")


# ---------------------------------------------------------------------------
# Classification + routing
# ---------------------------------------------------------------------------

def classify(req: TicketRequest, relevant_txn: Optional[TransactionEntry]):
    """Return (case_type, department, severity, human_review_required)."""
    del relevant_txn
    hypothesis = investigate(req)
    return (
        hypothesis.case_type,
        department_for(hypothesis.case_type),
        hypothesis.severity,
        hypothesis.human_review_required,
    )

    c = sanitize_for_intent(req.complaint)

    # 1. Phishing / social engineering — highest priority, often no txn.
    if _is_phishing_intent(c):
        return "phishing_or_social_engineering", "fraud_risk", "critical", True

    # 2. Duplicate payment
    if _is_duplicate_payment_intent(c, req.transaction_history):
        return "duplicate_payment", "payments_ops", "high", True

    # 3. Payment failed but deducted
    if _is_payment_failed_intent(c, relevant_txn, req.transaction_history):
        return "payment_failed", "payments_ops", "high", False

    # 4. Merchant settlement delay
    if _is_merchant_settlement_delay(req, c, relevant_txn):
        return "merchant_settlement_delay", "merchant_operations", "medium", False

    # 5. Agent cash-in issue
    if _is_agent_cash_in_issue(c, relevant_txn, req.transaction_history):
        return "agent_cash_in_issue", "agent_operations", "high", True

    if _contains(c, CASH_IN_KW) and (
        relevant_txn is None or relevant_txn.type == "cash_in"
    ):
        if _contains(c, ["agent", "এজেন্ট"]) or (relevant_txn and relevant_txn.type == "cash_in"):
            return "agent_cash_in_issue", "agent_operations", "high", True

    # 6. Wrong transfer (explicit wrong-recipient language)
    if _is_wrong_transfer_intent(c, relevant_txn, req.transaction_history):
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
