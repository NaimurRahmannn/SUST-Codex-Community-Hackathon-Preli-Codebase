"""Run all 10 sample inputs through the app and compare key fields."""
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

with open("samples.json", encoding="utf-8") as f:
    pack = json.load(f)

KEY = ["relevant_transaction_id", "evidence_verdict", "case_type", "department"]
passed = 0
for case in pack["cases"]:
    inp = case["input"]
    exp = case["expected_output"]
    r = client.post("/analyze-ticket", json=inp)
    assert r.status_code == 200, f"{case['id']} -> HTTP {r.status_code}: {r.text}"
    got = r.json()
    diffs = {k: (exp[k], got[k]) for k in KEY if exp[k] != got[k]}
    ok = not diffs
    passed += ok
    print(f"{case['id']:>10} | {'PASS' if ok else 'DIFF'} | sev exp={exp['severity']} got={got['severity']} | hr exp={exp['human_review_required']} got={got['human_review_required']}")
    if diffs:
        for k, (e, g) in diffs.items():
            print(f"           - {k}: expected={e!r} got={g!r}")

# health
h = client.get("/health")
print(f"\n/health -> {h.status_code} {h.json()}")
print(f"\nKey-field exact matches: {passed}/{len(pack['cases'])}")
