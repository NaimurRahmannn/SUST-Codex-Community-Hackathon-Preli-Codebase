"""Fresh holdout set for the QueueStorm rule classifier.

These cases intentionally avoid many phrases used in stress_test.py. The goal
is measurement only: do not tune investigator.py from this file in the same run.
"""

import os
from collections import Counter

from fastapi.testclient import TestClient

# Force pure rules before importing app.main, regardless of local .env settings.
os.environ["USE_LLM"] = "0"
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GEMINI_API_KEYS", None)

from app.main import app  # noqa: E402


client = TestClient(app)


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
        "id": "HPE-01",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-01",
            "language": "en",
            "complaint": "I moved 1700 from my wallet and it ended up with a stranger, not the cousin I had in mind.",
            "transaction_history": [
                txn("H-TXN-PE-01", "2026-06-01T09:10:00Z", "transfer", 1700, "+8801600000001", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Money reached a stranger instead of the intended cousin.",
    },
    {
        "id": "HPE-02",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-02",
            "language": "en",
            "complaint": "I bought a data pack for 399; the screen kept spinning and no pack came, but 399 left my wallet.",
            "transaction_history": [
                txn("H-TXN-PE-02", "2026-06-01T10:05:00Z", "payment", 399, "TELCO-DATA", "pending")
            ],
        },
        "expected_case_type": "payment_failed",
        "expected_department": "payments_ops",
        "justification": "Customer paid for a service that did not complete while funds left wallet.",
    },
    {
        "id": "HPE-03",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-03",
            "language": "en",
            "complaint": "The metro pass fare appears on my statement in two separate rows for the same ride.",
            "transaction_history": [
                txn("H-TXN-PE-03A", "2026-06-01T11:00:00Z", "payment", 120, "METRO-PASS", "completed"),
                txn("H-TXN-PE-03B", "2026-06-01T11:00:45Z", "payment", 120, "METRO-PASS", "completed"),
            ],
        },
        "expected_case_type": "duplicate_payment",
        "expected_department": "payments_ops",
        "justification": "Same fare is present as two ledger rows.",
    },
    {
        "id": "HPE-04",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-04",
            "language": "en",
            "complaint": "I no longer need the concert ticket I bought; please undo that purchase.",
            "transaction_history": [
                txn("H-TXN-PE-04", "2026-06-01T12:00:00Z", "payment", 2200, "EVENT-TIX", "completed")
            ],
        },
        "expected_case_type": "refund_request",
        "expected_department": "customer_support",
        "justification": "Customer wants to undo a completed purchase for personal reasons.",
    },
    {
        "id": "HPE-05",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-05",
            "language": "en",
            "user_type": "merchant",
            "complaint": "I run a kiosk; yesterday's customer takings are still absent from my account.",
            "transaction_history": [
                txn("H-TXN-PE-05", "2026-06-01T18:00:00Z", "settlement", 13400, "KIOSK-ACCOUNT", "pending")
            ],
        },
        "expected_case_type": "merchant_settlement_delay",
        "expected_department": "merchant_operations",
        "justification": "Merchant takings from customers have not reached the account.",
    },
    {
        "id": "HPE-06",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-06",
            "language": "en",
            "complaint": "I gave 2600 paper money to the shop counter person, but my wallet total is still the old amount.",
            "transaction_history": [
                txn("H-TXN-PE-06", "2026-06-02T09:00:00Z", "cash_in", 2600, "COUNTER-44", "completed")
            ],
        },
        "expected_case_type": "agent_cash_in_issue",
        "expected_department": "agent_operations",
        "justification": "Cash-in equivalent did not increase wallet balance.",
    },
    {
        "id": "HPE-07",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-07",
            "language": "en",
            "complaint": "A man rang me pretending to be from the company and got pushy about confirming my secret number or he'd freeze the account.",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Impersonator pressures customer for a secret number under account-freeze threat.",
    },
    {
        "id": "HPE-08",
        "category": "paraphrased-English",
        "input": {
            "ticket_id": "HPE-08",
            "language": "en",
            "complaint": "My wallet feels confusing today; can someone review it?",
            "transaction_history": [],
        },
        "expected_case_type": "other",
        "expected_department": "customer_support",
        "justification": "Vague complaint has no concrete transaction or issue type.",
    },
    {
        "id": "HBN-01",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-01",
            "language": "bn",
            "complaint": "আমি ১৮০০ টাকা ছাড়লাম, কিন্তু টাকা এমন একজনের কাছে গেছে যাকে আমি চিনি না।",
            "transaction_history": [
                txn("H-TXN-BN-01", "2026-06-02T10:00:00Z", "transfer", 1800, "+8801611111111", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Money reached an unknown person.",
    },
    {
        "id": "HBN-02",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-02",
            "language": "bn",
            "complaint": "রিচার্জ নিতে গিয়ে ঘুরতেই থাকল, রিচার্জ আসেনি কিন্তু ৬৫ টাকা কমে গেছে।",
            "transaction_history": [
                txn("H-TXN-BN-02", "2026-06-02T11:00:00Z", "payment", 65, "TELCO-BN", "pending")
            ],
        },
        "expected_case_type": "payment_failed",
        "expected_department": "payments_ops",
        "justification": "Recharge did not arrive while balance decreased.",
    },
    {
        "id": "HBN-03",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-03",
            "language": "bn",
            "complaint": "বাস টিকিটের একই ভাড়া লিস্টে দুই জায়গায় উঠেছে।",
            "transaction_history": [
                txn("H-TXN-BN-03A", "2026-06-02T12:00:00Z", "payment", 90, "BUS-TICKET", "completed"),
                txn("H-TXN-BN-03B", "2026-06-02T12:01:00Z", "payment", 90, "BUS-TICKET", "completed"),
            ],
        },
        "expected_case_type": "duplicate_payment",
        "expected_department": "payments_ops",
        "justification": "Same fare appears in two ledger places.",
    },
    {
        "id": "HBN-04",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-04",
            "language": "bn",
            "complaint": "জুতাটা আর লাগবে না, দোকানের ওই কেনাকাটাটা বাতিল করতে চাই।",
            "transaction_history": [
                txn("H-TXN-BN-04", "2026-06-02T13:00:00Z", "payment", 1450, "SHOE-STORE", "completed")
            ],
        },
        "expected_case_type": "refund_request",
        "expected_department": "customer_support",
        "justification": "Customer wants to cancel a completed purchase because item is no longer needed.",
    },
    {
        "id": "HBN-05",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-05",
            "language": "bn",
            "user_type": "merchant",
            "complaint": "আমি দোকান চালাই, গত রাতের ক্রেতাদের টাকা এখনো আমার হিসাবে দেখা যাচ্ছে না।",
            "transaction_history": [
                txn("H-TXN-BN-05", "2026-06-02T18:00:00Z", "settlement", 7700, "SHOP-BN-HOLD", "pending")
            ],
        },
        "expected_case_type": "merchant_settlement_delay",
        "expected_department": "merchant_operations",
        "justification": "Merchant customer takings are not visible in account.",
    },
    {
        "id": "HBN-06",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-06",
            "language": "bn",
            "complaint": "কাউন্টারের লোককে ১২০০ নগদ দিলাম, কিন্তু ওয়ালেটের মোট টাকা একই রয়ে গেছে।",
            "transaction_history": [
                txn("H-TXN-BN-06", "2026-06-03T09:00:00Z", "cash_in", 1200, "COUNTER-BN", "completed")
            ],
        },
        "expected_case_type": "agent_cash_in_issue",
        "expected_department": "agent_operations",
        "justification": "Cash given at counter did not change wallet balance.",
    },
    {
        "id": "HBN-07",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-07",
            "language": "bn",
            "complaint": "একজন নিজেকে কোম্পানির লোক বলে পরিচয় দিয়ে আমার গোপন নম্বর জানতে চাচ্ছিল, না বললে হিসাব আটকে দেবে বলেছে।",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Impersonator asks for secret number and threatens account lock.",
    },
    {
        "id": "HBN-08",
        "category": "Bangla",
        "input": {
            "ticket_id": "HBN-08",
            "language": "bn",
            "complaint": "অ্যাপে কিছু অদ্ভুত দেখাচ্ছে, বুঝতে পারছি না।",
            "transaction_history": [],
        },
        "expected_case_type": "other",
        "expected_department": "customer_support",
        "justification": "Vague app/account concern without issue details.",
    },
    {
        "id": "HBL-01",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-01",
            "language": "mixed",
            "complaint": "ami 950 tk chere dilam, taka ek stranger er wallet e porse, bondhur jonno chilo",
            "transaction_history": [
                txn("H-TXN-BL-01", "2026-06-03T10:00:00Z", "transfer", 950, "+8801622222222", "completed")
            ],
        },
        "expected_case_type": "wrong_transfer",
        "expected_department": "dispute_resolution",
        "justification": "Money reached a stranger instead of the friend.",
    },
    {
        "id": "HBL-02",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-02",
            "language": "mixed",
            "complaint": "net pack nite giye loading e atke gelo, pack asheni but 289 tk kome gese",
            "transaction_history": [
                txn("H-TXN-BL-02", "2026-06-03T11:00:00Z", "payment", 289, "TELCO-BL", "pending")
            ],
        },
        "expected_case_type": "payment_failed",
        "expected_department": "payments_ops",
        "justification": "Pack did not arrive while wallet amount decreased.",
    },
    {
        "id": "HBL-03",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-03",
            "language": "mixed",
            "complaint": "ekoi bus ticket er bhara statement e dui jaygay uthse",
            "transaction_history": [
                txn("H-TXN-BL-03A", "2026-06-03T12:00:00Z", "payment", 110, "BUS-BL", "completed"),
                txn("H-TXN-BL-03B", "2026-06-03T12:01:00Z", "payment", 110, "BUS-BL", "completed"),
            ],
        },
        "expected_case_type": "duplicate_payment",
        "expected_department": "payments_ops",
        "justification": "Same ticket fare appears twice in statement.",
    },
    {
        "id": "HBL-04",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-04",
            "language": "mixed",
            "complaint": "product ta ar lagbe na, oi purchase ta undo korte chai",
            "transaction_history": [
                txn("H-TXN-BL-04", "2026-06-03T13:00:00Z", "payment", 640, "SHOP-BL-HOLD", "completed")
            ],
        },
        "expected_case_type": "refund_request",
        "expected_department": "customer_support",
        "justification": "Customer wants to undo a completed purchase.",
    },
    {
        "id": "HBL-05",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-05",
            "language": "mixed",
            "user_type": "merchant",
            "complaint": "ami choto dokan chalai, kal rater customer der taka amar hisab e ekhono dekha jacche na",
            "transaction_history": [
                txn("H-TXN-BL-05", "2026-06-03T18:00:00Z", "settlement", 6900, "SHOP-BL-ACCT", "pending")
            ],
        },
        "expected_case_type": "merchant_settlement_delay",
        "expected_department": "merchant_operations",
        "justification": "Merchant customer takings are not visible in account.",
    },
    {
        "id": "HBL-06",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-06",
            "language": "mixed",
            "complaint": "counter er bhai ke 700 cash dilam, wallet total ager motoi ache",
            "transaction_history": [
                txn("H-TXN-BL-06", "2026-06-04T09:00:00Z", "cash_in", 700, "COUNTER-BL", "completed")
            ],
        },
        "expected_case_type": "agent_cash_in_issue",
        "expected_department": "agent_operations",
        "justification": "Cash handed at counter did not change wallet total.",
    },
    {
        "id": "HBL-07",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-07",
            "language": "mixed",
            "complaint": "ek lok company staff bole amar private number jante chailo, na dile wallet lock korbe bole chap dicche",
            "transaction_history": [],
        },
        "expected_case_type": "phishing_or_social_engineering",
        "expected_department": "fraud_risk",
        "justification": "Impersonator pressures for private number with lock threat.",
    },
    {
        "id": "HBL-08",
        "category": "Banglish",
        "input": {
            "ticket_id": "HBL-08",
            "language": "mixed",
            "complaint": "app e ajke kichu ulta palta lagche, bujhte parchi na",
            "transaction_history": [],
        },
        "expected_case_type": "other",
        "expected_department": "customer_support",
        "justification": "Vague app concern without transaction or issue details.",
    },
]


CASE_TYPES = [
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "duplicate_payment",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "phishing_or_social_engineering",
    "other",
]
CATEGORIES = ["paraphrased-English", "Bangla", "Banglish"]


def verdict(result, case):
    return (
        result["case_type"] == case["expected_case_type"]
        and result["department"] == case["expected_department"]
    )


def main():
    failures = []
    records = []
    source_counts = Counter()
    passed = 0

    print("QueueStorm holdout test")
    print("=" * 100)
    print(f"USE_LLM={os.getenv('USE_LLM', '') or '<unset>'}")
    print("=" * 100)

    for case in CASES:
        response = client.post("/analyze-ticket", json=case["input"])
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
                "category": case["category"],
                "case_type": case["expected_case_type"],
                "ok": ok,
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
                    "justification": case["justification"],
                }
            )

        print(
            f"{case['id']:>6} | {case['category']:<20} | "
            f"expected {case['expected_case_type']}/{case['expected_department']} | "
            f"got {got_case}/{got_department} | {status}"
        )
        print(f"       why: {case['justification']}")

    print()
    print("Summary")
    print("=" * 100)
    print(f"Total cases: {len(CASES)}")
    print(f"Passed: {passed}")
    print(f"Failed: {len(failures)}")

    print()
    print("Classification source counts")
    print("-" * 100)
    for source in ["llm_classified", "rule_classified", "unknown_source", "http_error"]:
        print(f"{source:<20} {source_counts.get(source, 0)}")

    print()
    print("Pass/fail by language category")
    print("-" * 100)
    category_counts = Counter()
    for record in records:
        category_counts[(record["category"], "PASS" if record["ok"] else "FAIL")] += 1
    for category in CATEGORIES:
        print(
            f"{category:<20} PASS {category_counts.get((category, 'PASS'), 0):<2} "
            f"FAIL {category_counts.get((category, 'FAIL'), 0):<2}"
        )

    print()
    print("Pass/fail by expected case_type")
    print("-" * 100)
    case_type_counts = Counter()
    for record in records:
        case_type_counts[(record["case_type"], "PASS" if record["ok"] else "FAIL")] += 1
    for case_type in CASE_TYPES:
        print(
            f"{case_type:<35} PASS {case_type_counts.get((case_type, 'PASS'), 0):<2} "
            f"FAIL {case_type_counts.get((case_type, 'FAIL'), 0):<2}"
        )

    print()
    print("Failure details")
    print("-" * 100)
    if not failures:
        print("No failures.")
    else:
        for f in failures:
            print(
                f"{f['id']:>6} | {f['category']:<20} | expected "
                f"{f['case_type']}/{f['department']} | got "
                f"{f['got_case_type']}/{f['got_department']} | {f['justification']}"
            )


if __name__ == "__main__":
    main()
