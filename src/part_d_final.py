"""part_d_final.py -- clean final run of the refund agent.
Deletes old test outputs, runs everything once, and writes:
  outputs/agent_runs.jsonl, outputs/refund_ledger.jsonl, state/*.json
It also prints the tables you need for the README."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from part_d_agent import LEDGER_PATH
from part_d_run import (STATE_DIR, SimulatedCrash, refund_amount,
                        resume_agent, run_agent)

RUNS_PATH = ROOT / "outputs" / "agent_runs.jsonl"


def clean_old_outputs():
    RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    for p in STATE_DIR.glob("*.json"):
        p.unlink()
    for p in (LEDGER_PATH, RUNS_PATH):
        if p.exists():
            p.unlink()


def log_run(scenario_id, result, note):
    line = {
        "scenario_id": scenario_id,
        "note": note,
        "status": result["status"],
        "final_answer": result["final_answer"],
        "llm_calls": result["llm_calls"],
        "tokens_used": result["tokens_used"],
        "steps": [
            {"tool": s["tool"], "arguments": s["arguments"], "observation": s["observation"]}
            for s in result["steps"]
        ],
    }
    with open(RUNS_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


if __name__ == "__main__":
    clean_old_outputs()

    with open(ROOT / "data" / "raw" / "agent_scenarios.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # ---- 1. the seven scenarios ----
    table = []
    for row in rows:
        res = run_agent(row["message"], row["scenario_id"])
        log_run(row["scenario_id"], res, "scenario")
        table.append((row["scenario_id"], res["status"], refund_amount(res),
                      res["llm_calls"], res["tokens_used"]))

    s1 = rows[0]

    # ---- 2. token-limit demo ----
    tok = run_agent(s1["message"], s1["scenario_id"], token_limit=200)
    log_run("S1", tok, "demo: token_limit=200")

    # ---- 3. timeout demo ----
    tim = run_agent(s1["message"], s1["scenario_id"], time_limit_seconds=0)
    log_run("S1", tim, "demo: time_limit_seconds=0")

    # ---- 4. crash and resume demo ----
    try:
        run_agent(s1["message"], s1["scenario_id"], run_id="S1-crash-demo", crash_after_tools=2)
    except SimulatedCrash as e:
        print("CRASH:", e)
    resumed = resume_agent("S1-crash-demo")
    log_run("S1", resumed, "demo: crash after tool 2, then resume")
    tools_run = [s["tool"] for s in resumed["steps"]]

    # ---- print everything for the README ----
    print("\n| Scenario | Status | Refund (INR) | Model calls | Tokens used |")
    print("|---|---|---|---|---|")
    for sid, status, amount, calls, tokens in table:
        print(f"| {sid} | {status} | {amount:.2f} | {calls} | {tokens} |")

    print("\nDemo statuses:")
    print(f"- S1 with token_limit=200: {tok['status']} ({tok['llm_calls']} model calls, {tok['tokens_used']} tokens)")
    print(f"- S1 with time_limit_seconds=0: {tim['status']} ({tim['llm_calls']} model calls)")

    print("\nCrash and resume (S1):")
    print(f"- final status: {resumed['status']}, refund {refund_amount(resumed):.2f}")
    print("- tools executed, in order: " + " -> ".join(tools_run))