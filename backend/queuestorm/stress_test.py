"""Stress-test the current classifier against harder hidden-test-like inputs.

This file intentionally does not import or change classifier internals. It calls
the real FastAPI endpoint through TestClient, just like test_samples.py.
"""

import os
import time
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from fastapi.testclient import TestClient

# Load local env files before importing the FastAPI app so USE_LLM/GEMINI_API_KEY
# are visible to app.llm during the test run. Values are never printed.
load_dotenv(Path(__file__).with_name(".env"))
load_dotenv(Path(__file__).parent / "app" / ".env")

from app.main import app


client = TestClient(app)
PACE_SECONDS = float(
    os.getenv(
        "STRESS_TEST_PACE_SECONDS",
        "2.5" if os.getenv("USE_LLM") == "1" else "0",
    )
)


def txn(transaction_id, timestamp, txn_type, amount, counterparty, status):
    return {
        "transaction_id": transaction_id,
        "timestamp": timestamp,
        "type": txn_type,
        "amount": amount,
        "counterparty": counterparty,
        "status": status,
    }


CASES = [
    {
        "id": "PE-01",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-01",
            "language": "en",
            "complaint": "I paid 2400 to someone, but the recipient I meant to pay never got it.",
            "transaction_history": [
                txn("TXN-PE-001", "2026-05-01T10:00:00Z", "transfer", 2400, "+8801700000001", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Sender reports intended recipient did not receive the transfer.",
    },
    {
        "id": "PE-02",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-02",
            "language": "en",
            "complaint": "The shop screen said it could not process my 1190 bill, yet my wallet balance went down.",
            "transaction_history": [
                txn("TXN-PE-002", "2026-05-01T11:00:00Z", "payment", 1190, "MERCHANT-42", "failed")
            ],
        },
        "expected_case_type": "payment_failed",
        "expected_department": "payments_ops",
        "justification": "A failed merchant payment still deducted balance.",
    },
    {
        "id": "PE-03",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-03",
            "language": "en",
            "complaint": "My card-style wallet was debited for the same grocery bill two separate times.",
            "transaction_history": [
                txn("TXN-PE-003A", "2026-05-01T12:00:00Z", "payment", 750, "GROCERY-9", "completed"),
                txn("TXN-PE-003B", "2026-05-01T12:01:00Z", "payment", 750, "GROCERY-9", "completed"),
            ],
        },
        "expected_case_type": "duplicate_payment",
        "expected_department": "payments_ops",
        "justification": "Same bill debited two separate times should be duplicate payment.",
    },
    {
        "id": "PE-04",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-04",
            "language": "en",
            "user_type": "merchant",
            "complaint": "Yesterday's sales payout has not arrived in my business wallet yet.",
            "transaction_history": [
                txn("TXN-PE-004", "2026-05-01T18:00:00Z", "settlement", 18600, "MERCHANT-WALLET-77", "pending")
            ],
        },
        "expected_case_type": "merchant_settlement_delay",
        "expected_department": "merchant_operations",
        "justification": "Merchant payout delay is a settlement operations issue.",
    },
    {
        "id": "PE-05",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-05",
            "language": "en",
            "complaint": "I handed cash to your local representative for 3000, but the wallet balance stayed unchanged.",
            "transaction_history": [
                txn("TXN-PE-005", "2026-05-02T09:00:00Z", "cash_in", 3000, "AGENT-118", "completed")
            ],
        },
        "expected_case_type": "agent_cash_in_issue",
        "expected_department": "agent_operations",
        "justification": "Cash given to a field representative did not appear as wallet balance.",
    },
    {
        "id": "PE-06",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-06",
            "language": "en",
            "complaint": "A caller said my account would be frozen unless I read out the six digit login code.",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Caller pressures customer to disclose a login code.",
    },
    {
        "id": "PE-07",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-07",
            "language": "en",
            "complaint": "I changed my mind about this online order and need the charge cancelled.",
            "transaction_history": [
                txn("TXN-PE-007", "2026-05-02T12:00:00Z", "payment", 1500, "SHOP-101", "completed")
            ],
        },
        "expected_case_type": "refund_request",
        "expected_department": "customer_support",
        "justification": "Customer wants cancellation/return of a completed merchant charge.",
    },
    {
        "id": "PE-08",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-08",
            "language": "en",
            "complaint": "My transfer of 5000 landed with an unintended person in my contacts.",
            "transaction_history": [
                txn("TXN-PE-008", "2026-05-02T13:00:00Z", "transfer", 5000, "+8801700000008", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Money went to an unintended recipient.",
    },
    {
        "id": "PE-09",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-09",
            "language": "en",
            "complaint": "The utility bill attempt ended with an error message, but 860 taka is missing.",
            "transaction_history": [
                txn("TXN-PE-009", "2026-05-02T14:00:00Z", "payment", 860, "UTILITY-1", "pending")
            ],
        },
        "expected_case_type": "payment_failed",
        "expected_department": "payments_ops",
        "justification": "Error during bill payment with missing balance should be payment-failed/deducted.",
    },
    {
        "id": "PE-10",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "PE-10",
            "language": "en",
            "complaint": "Something is off in my account today, please check.",
            "transaction_history": [],
        },
        "expected_case_type": "other",
        "expected_department": "customer_support",
        "justification": "Vague complaint has no issue type or transaction clue.",
    },
    {
        "id": "BN-01",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-01",
            "language": "bn",
            "complaint": "আমি ২০০০ টাকা পাঠিয়েছি কিন্তু যার কাছে পাঠানোর কথা ছিল সে পায়নি।",
            "transaction_history": [
                txn("TXN-BN-001", "2026-05-03T09:00:00Z", "transfer", 2000, "+8801711111111", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Bangla transfer complaint says intended recipient did not get the money.",
    },
    {
        "id": "BN-02",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-02",
            "language": "bn",
            "complaint": "বিল দিতে গিয়ে সমস্যা দেখিয়েছে, কিন্তু আমার ব্যালেন্স থেকে ৭৫০ টাকা কেটে গেছে।",
            "transaction_history": [
                txn("TXN-BN-002", "2026-05-03T10:00:00Z", "payment", 750, "BILLER-BN", "pending")
            ],
        },
        "expected_case_type": "payment_failed",
        "expected_department": "payments_ops",
        "justification": "Bangla payment error with balance deduction.",
    },
    {
        "id": "BN-03",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-03",
            "language": "bn",
            "complaint": "একই দোকানের বিলের জন্য আমার টাকা দুইবার কাটা হয়েছে।",
            "transaction_history": [
                txn("TXN-BN-003A", "2026-05-03T11:00:00Z", "payment", 430, "SHOP-BN", "completed"),
                txn("TXN-BN-003B", "2026-05-03T11:01:00Z", "payment", 430, "SHOP-BN", "completed"),
            ],
        },
        "expected_case_type": "duplicate_payment",
        "expected_department": "payments_ops",
        "justification": "Same merchant bill charged twice in Bangla.",
    },
    {
        "id": "BN-04",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-04",
            "language": "bn",
            "user_type": "merchant",
            "complaint": "গতকালের বিক্রির টাকা এখনো আমার মার্চেন্ট ওয়ালেটে জমা হয়নি।",
            "transaction_history": [
                txn("TXN-BN-004", "2026-05-03T18:00:00Z", "settlement", 9200, "MERCHANT-BN", "pending")
            ],
        },
        "expected_case_type": "merchant_settlement_delay",
        "expected_department": "merchant_operations",
        "justification": "Merchant says sales proceeds have not reached wallet.",
    },
    {
        "id": "BN-05",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-05",
            "language": "bn",
            "complaint": "এজেন্টকে নগদ ১৫০০ টাকা দিয়েছি, কিন্তু আমার অ্যাপে ব্যালেন্স বাড়েনি।",
            "transaction_history": [
                txn("TXN-BN-005", "2026-05-04T09:00:00Z", "cash_in", 1500, "AGENT-BN", "completed")
            ],
        },
        "expected_case_type": "agent_cash_in_issue",
        "expected_department": "agent_operations",
        "justification": "Bangla agent cash-in did not reflect in app balance.",
    },
    {
        "id": "BN-06",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-06",
            "language": "bn",
            "complaint": "একজন ফোন করে বলেছে অ্যাকাউন্ট বন্ধ হয়ে যাবে, তাই গোপন কোড বলতে হবে।",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Caller asks for secret code under account-closure threat.",
    },
    {
        "id": "BN-07",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-07",
            "language": "bn",
            "complaint": "আমি অর্ডারটা নিতে চাই না, পেমেন্টের টাকা ফেরত চাই।",
            "transaction_history": [
                txn("TXN-BN-007", "2026-05-04T11:00:00Z", "payment", 980, "SHOP-BN-2", "completed")
            ],
        },
        "expected_case_type": "refund_request",
        "expected_department": "customer_support",
        "justification": "Customer changed mind and wants payment returned.",
    },
    {
        "id": "BN-08",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-08",
            "language": "bn",
            "complaint": "টাকাটা অন্য একজনের কাছে চলে গেছে, যাকে দেওয়ার কথা ছিল তাকে যায়নি।",
            "transaction_history": [
                txn("TXN-BN-008", "2026-05-04T12:00:00Z", "transfer", 3200, "+8801788888888", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Money went to another person instead of intended recipient.",
    },
    {
        "id": "BN-09",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-09",
            "language": "bn",
            "complaint": "কেউ মেসেজে লিংক পাঠিয়ে বলছে অ্যাকাউন্ট যাচাই না করলে বন্ধ হবে।",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Threatening verification link message is social engineering.",
    },
    {
        "id": "BN-10",
        "category": "Bangla",
        "input": {
            "ticket_id": "BN-10",
            "language": "bn",
            "complaint": "আমার লেনদেনে সমস্যা হয়েছে, একটু দেখে দিন।",
            "transaction_history": [],
        },
        "expected_case_type": "other",
        "expected_department": "customer_support",
        "justification": "Vague Bangla complaint lacks actionable issue details.",
    },
    {
        "id": "BL-01",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-01",
            "language": "mixed",
            "complaint": "amar taka 2500 onno lok er kache chole gese, jar kache dewar kotha she pay nai",
            "transaction_history": [
                txn("TXN-BL-001", "2026-05-05T09:00:00Z", "transfer", 2500, "+8801811111111", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Banglish says money went to another person, not intended recipient.",
    },
    {
        "id": "BL-02",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-02",
            "language": "mixed",
            "complaint": "amar taka kete nilo kintu payment hoy nai, bill ta ekhono unpaid",
            "transaction_history": [
                txn("TXN-BL-002", "2026-05-05T10:00:00Z", "payment", 640, "BILLER-BL", "pending")
            ],
        },
        "expected_case_type": "payment_failed",
        "expected_department": "payments_ops",
        "justification": "Banglish says balance was cut but payment did not happen.",
    },
    {
        "id": "BL-03",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-03",
            "language": "mixed",
            "complaint": "same dokaner bill e double cut hoise, duita debit dekhacche",
            "transaction_history": [
                txn("TXN-BL-003A", "2026-05-05T11:00:00Z", "payment", 510, "SHOP-BL", "completed"),
                txn("TXN-BL-003B", "2026-05-05T11:01:00Z", "payment", 510, "SHOP-BL", "completed"),
            ],
        },
        "expected_case_type": "duplicate_payment",
        "expected_department": "payments_ops",
        "justification": "Banglish duplicate debit for same merchant bill.",
    },
    {
        "id": "BL-04",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-04",
            "language": "mixed",
            "user_type": "merchant",
            "complaint": "kalke sales er payout amar merchant wallet e ashe nai ekhono",
            "transaction_history": [
                txn("TXN-BL-004", "2026-05-05T18:00:00Z", "settlement", 12800, "MERCHANT-BL", "pending")
            ],
        },
        "expected_case_type": "merchant_settlement_delay",
        "expected_department": "merchant_operations",
        "justification": "Banglish merchant sales payout delay.",
    },
    {
        "id": "BL-05",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-05",
            "language": "mixed",
            "complaint": "agent ke 1800 cash dilam, app e balance add hoy nai",
            "transaction_history": [
                txn("TXN-BL-005", "2026-05-06T09:00:00Z", "cash_in", 1800, "AGENT-BL", "completed")
            ],
        },
        "expected_case_type": "agent_cash_in_issue",
        "expected_department": "agent_operations",
        "justification": "Banglish agent cash-in not reflected in app balance.",
    },
    {
        "id": "BL-06",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-06",
            "language": "mixed",
            "complaint": "ekjon call kore bolse account bondho hobe, tai secret code bolte hobe",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Banglish caller asks for secret code with account-blocking threat.",
    },
    {
        "id": "BL-07",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-07",
            "language": "mixed",
            "complaint": "order ta cancel korte chai, amar taka back chai",
            "transaction_history": [
                txn("TXN-BL-007", "2026-05-06T11:00:00Z", "payment", 1320, "SHOP-BL-2", "completed")
            ],
        },
        "expected_case_type": "refund_request",
        "expected_department": "customer_support",
        "justification": "Banglish change-of-mind cancellation asks for money back.",
    },
    {
        "id": "BL-08",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-08",
            "language": "mixed",
            "complaint": "vul manush er kache 900 taka chole gese",
            "transaction_history": [
                txn("TXN-BL-008", "2026-05-06T12:00:00Z", "transfer", 900, "+8801888888888", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Banglish says money went to wrong person.",
    },
    {
        "id": "BL-09",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-09",
            "language": "mixed",
            "complaint": "unknown number theke link dise, verify na korle account off bole",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Banglish verification-link threat from unknown number.",
    },
    {
        "id": "BL-10",
        "category": "Banglish",
        "input": {
            "ticket_id": "BL-10",
            "language": "mixed",
            "complaint": "amar transaction e problem, details mone nai",
            "transaction_history": [],
        },
        "expected_case_type": "other",
        "expected_department": "customer_support",
        "justification": "Vague Banglish complaint lacks enough detail.",
    },
]


def verdict(result, case):
    expected = (case["expected_case_type"], case["expected_department"])
    got = (result["case_type"], result["department"])
    return expected == got


def main():
    failures = []
    records = []
    source_counts = Counter()
    latencies_ms = []
    passed = 0

    print("QueueStorm classifier stress test")
    print("=" * 95)
    print(f"USE_LLM={os.getenv('USE_LLM', '') or '<unset>'}")
    print(f"Pacing seconds between cases: {PACE_SECONDS:g}")
    print("=" * 95)

    for index, case in enumerate(CASES):
        if index > 0 and PACE_SECONDS > 0:
            time.sleep(PACE_SECONDS)

        started = time.perf_counter()
        response = client.post("/analyze-ticket", json=case["input"])
        latency_ms = (time.perf_counter() - started) * 1000
        latencies_ms.append(latency_ms)

        if response.status_code != 200:
            got_case = f"HTTP_{response.status_code}"
            got_department = response.text.replace("\n", " ")
            source = "http_error"
            ok = False
        else:
            result = response.json()
            got_case = result["case_type"]
            got_department = result["department"]
            source = next(
                (
                    code
                    for code in result.get("reason_codes", [])
                    if code in ("llm_classified", "rule_classified")
                ),
                "unknown_source",
            )
            ok = verdict(result, case)
        source_counts[source] += 1
        records.append(
            {
                "id": case["id"],
                "category": case["category"],
                "case_type": case["expected_case_type"],
                "ok": ok,
                "source": source,
                "latency_ms": latency_ms,
            }
        )

        if ok:
            passed += 1
            status = "PASS"
        else:
            status = "FAIL"
            failures.append(
                {
                    "id": case["id"],
                    "category": case["category"],
                    "case_type": case["expected_case_type"],
                    "department": case["expected_department"],
                    "got_case_type": got_case,
                    "got_department": got_department,
                    "source": source,
                }
            )

        print(
            f"{case['id']:>5} | {case['category']:<20} | "
            f"expected {case['expected_case_type']}/{case['expected_department']} | "
            f"got {got_case}/{got_department} | source {source} | {status}"
        )
        print(f"      why: {case['justification']}")

    print()
    print("Summary")
    print("=" * 95)
    print(f"Total cases: {len(CASES)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")
    print(f"Average latency ms: {sum(latencies_ms) / len(latencies_ms):.1f}")
    print(f"Max latency ms: {max(latencies_ms):.1f}")

    print()
    print("Classification source counts")
    print("-" * 95)
    for source in ["llm_classified", "rule_classified", "unknown_source", "http_error"]:
        print(f"{source:<20} {source_counts.get(source, 0)}")

    print()
    print("Pass/fail by language category")
    print("-" * 95)
    category_counts = Counter()
    for record in records:
        key = (record["category"], "PASS" if record["ok"] else "FAIL")
        category_counts[key] += 1
    for category in ["paraphrased-English", "Bangla", "Banglish"]:
        print(
            f"{category:<20} PASS {category_counts.get((category, 'PASS'), 0):<2} "
            f"FAIL {category_counts.get((category, 'FAIL'), 0):<2}"
        )

    print()
    print("Pass/fail by expected case_type")
    print("-" * 95)
    case_type_counts = Counter()
    for record in records:
        key = (record["case_type"], "PASS" if record["ok"] else "FAIL")
        case_type_counts[key] += 1
    for case_type in [
        "wrong_transfer",
        "payment_failed",
        "refund_request",
        "duplicate_payment",
        "merchant_settlement_delay",
        "agent_cash_in_issue",
        "phishing_or_social_engineering",
        "other",
    ]:
        print(
            f"{case_type:<35} PASS {case_type_counts.get((case_type, 'PASS'), 0):<2} "
            f"FAIL {case_type_counts.get((case_type, 'FAIL'), 0):<2}"
        )

    print()
    print("Failures by language category")
    print("-" * 95)
    failure_category_counts = Counter(f["category"] for f in failures)
    for category in ["paraphrased-English", "Bangla", "Banglish"]:
        print(f"{category:<20} {failure_category_counts.get(category, 0)}")

    print()
    print("Failures by expected case_type")
    print("-" * 95)
    failure_case_type_counts = Counter(f["case_type"] for f in failures)
    for case_type in [
        "wrong_transfer",
        "payment_failed",
        "refund_request",
        "duplicate_payment",
        "merchant_settlement_delay",
        "agent_cash_in_issue",
        "phishing_or_social_engineering",
        "other",
    ]:
        print(f"{case_type:<35} {failure_case_type_counts.get(case_type, 0)}")

    print()
    print("Failure details")
    print("-" * 95)
    if not failures:
        print("No failures.")
    else:
        for f in failures:
            print(
                f"{f['id']:>5} | {f['category']:<20} | expected "
                f"{f['case_type']}/{f['department']} | got "
                f"{f['got_case_type']}/{f['got_department']} | source {f['source']}"
            )


if __name__ == "__main__":
    main()
