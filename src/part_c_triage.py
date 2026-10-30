"""Part C: support ticket triage with guardrails (offline mock LLM)."""
import json
import logging
import os
import random
import re
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mock_llm  # noqa: E402
import pandas as pd  # noqa: E402
from mock_llm import TransientLLMError, est_tokens  # noqa: E402

os.makedirs("outputs", exist_ok=True)
logging.basicConfig(filename="outputs/retry_log.txt", filemode="w",
                    level=logging.INFO, format="%(message)s")
random.seed(42)

MAX_INPUT_TOKENS = 400
BASE_DELAY = 0.05
MAX_RETRIES = 3
ALLOWED = ["billing", "delivery", "technical", "fraud"]
HUMAN = {"skipped_empty", "flagged_long", "flagged_invalid_output",
         "budget_exhausted", "llm_error"}

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"\b[6-9]\d{9}\b")
ORDER_RE = re.compile(r"ORD-\d{6}")

ZERO_SHOT = (
    "You CLASSIFY customer support tickets for a grocery delivery app. "
    "Allowed categories: billing, delivery, technical, fraud. "
    'Reply with JSON only, exactly like {"category": "...", "reason": "..."}.'
)
FEW_SHOT = (
    ZERO_SHOT + "\n"
    "EXAMPLES:\n"
    'Ticket: I was charged twice for my order. -> {"category": "billing", "reason": "double charge"}\n'
    'Ticket: My order is very late and the rider is not answering. -> {"category": "delivery", "reason": "late order"}\n'
    'Ticket: The app crashes when I open the cart. -> {"category": "technical", "reason": "app crash"}\n'
    'Ticket: There is an unauthorized transaction I did not make. -> {"category": "fraud", "reason": "unauthorized transaction"}'
)

# ---------- customer segments from Part B ----------
seg = pd.read_csv("outputs/customer_segments.csv")
SEG_NAME = dict(zip(seg["customer_id"], seg["segment_name"]))
PREMIUM = {c for c, p in zip(seg["customer_id"], seg["is_premium"]) if str(p) == "True"}


def redact(text):
    text, n_email = EMAIL_RE.subn("[EMAIL]", text)
    text, n_phone = PHONE_RE.subn("[PHONE]", text)
    text, n_order = ORDER_RE.subn("[ORDER_ID]", text)
    return text, n_email, n_phone, n_order


def assert_no_pii(messages):
    for m in messages:
        for rx in (EMAIL_RE, PHONE_RE, ORDER_RE):
            assert not rx.search(m["content"]), "PII found in a prompt!"


def call_with_retry(messages, ticket_id, label, stats):
    for attempt in range(MAX_RETRIES + 1):
        try:
            return mock_llm.chat(messages)
        except TransientLLMError:
            stats["errors"] += 1
            if attempt == MAX_RETRIES:
                raise
            wait = BASE_DELAY * (2 ** attempt) * random.uniform(0.9, 1.15)
            stats["waits"].append(wait)
            logging.info(f"[{label}] ticket={ticket_id} retry={attempt} wait={wait:.4f}s")
            time.sleep(wait)


def validate(content):
    try:
        data = json.loads(content)
    except (TypeError, json.JSONDecodeError):
        words = set(re.findall(r"[a-z]+", (content or "").lower()))
        found = [c for c in ALLOWED if c in words]
        if len(found) == 1:
            return "classified_keyword", found[0]
        return "flagged_invalid_output", ""
    if isinstance(data, dict) and data.get("category") in ALLOWED:
        return "classified_json", data["category"]
    return "flagged_invalid_output", ""


def build_row(rec, status, category, used):
    cid = rec["customer_id"]
    if status in HUMAN:
        route, priority = "human_review", "NORMAL"
    elif category == "fraud":
        route, priority = "security_team", "HIGH"
    elif cid in PREMIUM:
        route, priority = "premium_desk", "HIGH"
    else:
        route, priority = "support_queue", "NORMAL"
    return {"ticket_id": rec["ticket_id"], "customer_id": cid, "status": status,
            "category": category, "segment_name": SEG_NAME.get(cid, ""),
            "priority": priority, "route": route, "tokens_used": used}


def run_pipeline(records, system_prompt, label, token_budget=None):
    mock_llm.reset()
    stats = {"errors": 0, "waits": []}
    total_tokens = 0
    rows = []
    for rec in records:
        text = rec["text"]
        status, category, used = "", "", 0
        if text.strip() == "":
            status = "skipped_empty"
        elif est_tokens(text) > MAX_INPUT_TOKENS:
            status = "flagged_long"
        elif token_budget is not None and total_tokens >= token_budget:
            status = "budget_exhausted"
        else:
            redacted = redact(text)[0]
            messages = [{"role": "system", "content": system_prompt},
                        {"role": "user", "content": redacted}]
            assert_no_pii(messages)
            try:
                resp = call_with_retry(messages, rec["ticket_id"], label, stats)
            except TransientLLMError:
                status = "llm_error"
            else:
                used = resp.usage.total_tokens
                total_tokens += used
                status, category = validate(resp.choices[0].message.content)
        rows.append(build_row(rec, status, category, used))
    return rows, total_tokens, stats


def summarize(label, rows, total_tokens, stats, truth):
    counts = Counter(r["status"] for r in rows)
    classified = [r for r in rows if r["status"] in ("classified_json", "classified_keyword")]
    correct = sum(r["category"] == truth[r["ticket_id"]] for r in classified)
    print(f"\n--- {label} ---")
    print("status counts:", dict(counts))
    print(f"classified: {len(classified)} | correct: {correct} | "
          f"accuracy: {correct / len(classified) * 100:.1f}%")
    print(f"total tokens: {total_tokens} | tokens per classified ticket: "
          f"{total_tokens / len(classified):.1f}")
    print(f"TransientLLMErrors: {stats['errors']} | retries logged: {len(stats['waits'])}")
    if stats["waits"]:
        print(f"retry wait range: {min(stats['waits']):.4f} to {max(stats['waits']):.4f} s "
              f"(allowed 0.0450 to 0.0575)")
    return classified


# ====================== MAIN ======================
tickets = pd.read_csv("data/raw/tickets.csv", keep_default_na=False)
records = tickets.to_dict("records")
truth = {r["ticket_id"]: r["true_category"] for r in records}

print("=== TASK 1: INPUT GUARDRAILS ===")
empty = [r for r in records if r["text"].strip() == ""]
long_ = [r for r in records if r["text"].strip() != "" and est_tokens(r["text"]) > MAX_INPUT_TOKENS]
print("empty tickets:", len(empty), "| long tickets:", len(long_),
      "| est tokens of a long ticket:", est_tokens(long_[0]["text"]), "(expected 4 / 4 / 734)")

print("\n=== TASK 2: REDACTION (all 164 tickets) ===")
tot = Counter()
red_texts = []
for r in records:
    red, e, p, o = redact(r["text"])
    tot["email"] += e
    tot["phone"] += p
    tot["order_id"] += o
    red_texts.append(red)
left = sum(len(rx.findall(t)) for t in red_texts for rx in (EMAIL_RE, PHONE_RE, ORDER_RE))
print("emails:", tot["email"], "| phones:", tot["phone"], "| order ids:", tot["order_id"],
      "| total:", sum(tot.values()), "(expected 55 / 91 / 132 / 278)")
print("patterns found again in redacted texts:", left, "(expected 0)")

print("\n=== TASK 3: PROMPTS ===")
assert "CLASSIFY" in ZERO_SHOT and "CLASSIFY" in FEW_SHOT
assert "EXAMPLES:" not in ZERO_SHOT and "EXAMPLES:" in FEW_SHOT
print("zero-shot prompt tokens:", est_tokens(ZERO_SHOT), "| few-shot prompt tokens:", est_tokens(FEW_SHOT))

print("\n=== TASKS 4 to 6: FULL RUNS (no budget) ===")
zs_rows, zs_tok, zs_stats = run_pipeline(records, ZERO_SHOT, "zero_shot")
zs_cls = summarize("ZERO-SHOT", zs_rows, zs_tok, zs_stats, truth)
fs_rows, fs_tok, fs_stats = run_pipeline(records, FEW_SHOT, "few_shot")
fs_cls = summarize("FEW-SHOT", fs_rows, fs_tok, fs_stats, truth)
print("(expected: 135 json / 12 keyword / 9 invalid, 147 classified, 19 errors,"
      " zero-shot 85.7% (126/147), few-shot 100%)")

print("\nConfusion table, zero-shot (rows = true, columns = predicted):")
pairs = pd.DataFrame({"true": [truth[r["ticket_id"]] for r in zs_cls],
                      "predicted": [r["category"] for r in zs_cls]})
print(pd.crosstab(pairs["true"], pairs["predicted"]))
print("(expected errors: fraud predicted billing 11, technical predicted billing 10)")
print("extra tokens per classified ticket for few-shot:",
      round(fs_tok / len(fs_cls) - zs_tok / len(zs_cls), 1))

print("\n=== TASK 7: BUDGET DEMO AND FINAL OUTPUT ===")
demo_rows, demo_tok, demo_stats = run_pipeline(records, ZERO_SHOT, "budget_demo", token_budget=6000)
pd.DataFrame(demo_rows).to_csv("outputs/triage_budget_demo.csv", index=False)
n_ex = sum(r["status"] == "budget_exhausted" for r in demo_rows)
print("budget used: 6000 | tickets budget_exhausted:", n_ex, "| tokens spent:", demo_tok)
assert n_ex >= 1

final_rows, final_tok, final_stats = run_pipeline(records, FEW_SHOT, "final", token_budget=100000)
final = pd.DataFrame(final_rows)
final.to_csv("outputs/triage_results.csv", index=False)
print("triage_results.csv rows:", len(final), "(expected 164) | tokens:", final_tok)
print("status counts:", dict(Counter(final["status"])))
print("routes:", dict(Counter(final["route"])))
print("priorities:", dict(Counter(final["priority"])))
print("\nretry log lines in outputs/retry_log.txt:", sum(1 for _ in open("outputs/retry_log.txt")))
print("saved outputs/triage_budget_demo.csv and outputs/triage_results.csv")