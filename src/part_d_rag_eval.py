"""Part D (task 4): evaluate retrieval and grounding, overlap 10 and overlap 0."""
from collections import Counter

import pandas as pd
from policy_rag import PolicyIndex, answer

ev = pd.read_csv("data/raw/policy_eval.csv", keep_default_na=False)


def evaluate(overlap):
    idx = PolicyIndex(overlap=overlap)
    counts = Counter(c["source"] for c in idx.chunks)
    print(f"\n##### chunk size 40, overlap {overlap} #####")
    print("chunks total:", len(idx.chunks), dict(sorted(counts.items())))
    doc_hit = fact_hit = fallback = 0
    n_ans = n_unans = 0
    bad = []
    for r in ev.to_dict("records"):
        ans, sources = answer(r["question"], idx)
        if r["expected_doc"] == "NONE":
            n_unans += 1
            if ans.startswith("I could not find"):
                fallback += 1
            else:
                bad.append((r["question"], "should say not found, got: " + ans))
        else:
            n_ans += 1
            d = r["expected_doc"] in sources
            f = r["expected_fact"] in ans
            doc_hit += int(d)
            fact_hit += int(f)
            if not (d and f):
                why = []
                if not d:
                    why.append("expected document not in top 3")
                if not f:
                    why.append("answer lacks '" + r["expected_fact"] + "' (answer: " + ans + ")")
                bad.append((r["question"], "; ".join(why)))
    print(f"answerable: expected_doc in top 3 = {doc_hit}/{n_ans} | "
          f"expected_fact in answer = {fact_hit}/{n_ans}")
    print(f"unanswerable: fallback answers = {fallback}/{n_unans}")
    if bad:
        print("questions that fail:")
        for q, why in bad:
            print(" -", q, "->", why)


print("=== TASK 2: RETRIEVAL DEMO ===")
demo = PolicyIndex().retrieve("refund policy late delivery", k=3)
for h in demo:
    print(round(h["score"], 3), h["source"])
print("(expected: all three from refund_policy.txt)")

evaluate(10)
print("\n(expected overlap 10: chunks 15 = refund 4, delivery 3, escalation 3, payment 3, privacy 2;"
      " results 12/12, 12/12, 2/2)")
evaluate(0)
print("\n(expected overlap 0: at least one answerable question fails)")