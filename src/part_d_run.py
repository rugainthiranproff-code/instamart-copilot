"""part_d_run.py -- Part D refund agent. Piece 4: ReAct loop + safety limits + resume."""
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # mock_llm.py is in the project root
sys.path.insert(0, str(ROOT / "src"))  # part_d_agent.py is in src

from mock_llm import chat
from part_d_agent import TOOL_MAP, TOOLS_SPEC

STATE_DIR = ROOT / "state"

SYSTEM_PROMPT = (
    "You are a refund AGENT for Instamart. Use the tools to decide each refund request. "
    "When you are done, answer with one of REFUND, ESCALATE, DENIED or NOT_FOUND, "
    "then a colon, then a short reason."
)


class SimulatedCrash(Exception):
    """Used only for the crash-and-resume demo."""


def fallback_result(status, reason, steps, llm_calls, tokens_used):
    """Used by every limit: returns the steps done so far and a hand-off message."""
    done = ", ".join(s["tool"] for s in steps) if steps else "none"
    final_answer = (
        f"{status}: {reason} Tools run so far: {done}. "
        "Please hand this request to a human agent."
    )
    return {
        "status": status,
        "final_answer": final_answer,
        "steps": steps,
        "llm_calls": llm_calls,
        "tokens_used": tokens_used,
    }


def save_checkpoint(run_id, scenario_id, messages, tokens_used, steps, llm_calls):
    """Save the whole progress of the run to state/<run_id>.json"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "messages": messages,
        "tokens_used": tokens_used,
        "step_number": len(steps),
        "llm_calls": llm_calls,
        "tools_executed": [s["tool"] for s in steps],
        "steps": steps,
    }
    with open(STATE_DIR / f"{run_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _run_loop(run_id, scenario_id, messages, steps, llm_calls, tokens_used,
              max_iterations, token_limit, time_limit_seconds, crash_after_tools=None):
    """The ReAct loop. Used by both run_agent (fresh start) and resume_agent (continue)."""
    start = time.monotonic()
    final_answer = None
    status = None

    while llm_calls < max_iterations:
        # limit (c): time -- checked at the top of every iteration
        elapsed = time.monotonic() - start
        if elapsed >= time_limit_seconds:
            return fallback_result(
                "FALLBACK_TIMEOUT",
                f"time limit of {time_limit_seconds} seconds reached.",
                steps, llm_calls, tokens_used,
            )

        # 1. ask the model what to do next
        response = chat(messages, tools=TOOLS_SPEC)
        llm_calls += 1
        tokens_used += response.usage.total_tokens

        # limit (b): tokens -- checked right after the model call, before running any tool
        if tokens_used > token_limit:
            return fallback_result(
                "FALLBACK_TOKEN_LIMIT",
                f"token limit of {token_limit} exceeded ({tokens_used} used).",
                steps, llm_calls, tokens_used,
            )

        msg = response.choices[0].message

        # 2. no tool requested -> this is the final answer
        if not msg.tool_calls:
            final_answer = msg.content
            status = final_answer.split(":")[0].strip()
            break

        # 3. model asked for a tool -> run it
        call = msg.tool_calls[0]
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": call.id, "name": call.name, "arguments": call.arguments}],
        })
        if call.name in TOOL_MAP:
            result = TOOL_MAP[call.name](**call.arguments)
        else:
            result = {"error": "unknown tool"}

        # 4. give the result back to the model
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "name": call.name,
            "content": json.dumps(result),
        })
        steps.append({"tool": call.name, "arguments": call.arguments, "observation": result})

        # 5. save a checkpoint after every tool observation
        save_checkpoint(run_id, scenario_id, messages, tokens_used, steps, llm_calls)

        # demo only: crash right after the checkpoint is saved
        if crash_after_tools is not None and len(steps) == crash_after_tools:
            raise SimulatedCrash(f"simulated crash after tool number {len(steps)}")

    # limit (a): max iterations -- loop ended without a final answer
    if final_answer is None:
        return fallback_result(
            "FALLBACK_MAX_ITERATIONS",
            f"no final answer after {llm_calls} model calls.",
            steps, llm_calls, tokens_used,
        )

    return {
        "status": status,
        "final_answer": final_answer,
        "steps": steps,
        "llm_calls": llm_calls,
        "tokens_used": tokens_used,
    }


def run_agent(user_message, scenario_id, max_iterations=6, token_limit=6000,
              time_limit_seconds=10, run_id=None, crash_after_tools=None):
    if run_id is None:
        run_id = f"{scenario_id}-{time.time_ns()}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    return _run_loop(run_id, scenario_id, messages, [], 0, 0,
                     max_iterations, token_limit, time_limit_seconds, crash_after_tools)


def resume_agent(run_id, max_iterations=6, token_limit=6000, time_limit_seconds=10):
    """Load state/<run_id>.json and continue from where the run stopped."""
    with open(STATE_DIR / f"{run_id}.json", encoding="utf-8") as f:
        data = json.load(f)
    return _run_loop(
        data["run_id"], data["scenario_id"], data["messages"], data["steps"],
        data["llm_calls"], data["tokens_used"],
        max_iterations, token_limit, time_limit_seconds,
    )


def refund_amount(result):
    """Refund shown in the results table: taken from the issue/escalate step."""
    for step in reversed(result["steps"]):
        if step["tool"] in ("issue_refund", "escalate_to_human"):
            return float(step["observation"]["refund_inr"])
    return 0.0


# ---------- test: 7 scenarios + the two limit demos + crash-and-resume demo ----------
if __name__ == "__main__":
    with open(ROOT / "data" / "raw" / "agent_scenarios.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print("id  status                    refund    expected  calls tokens  check")
    for row in rows:
        res = run_agent(row["message"], row["scenario_id"])
        amount = refund_amount(res)
        expected = float(row["expected_refund_inr"])
        ok = res["status"].startswith(row["expected_outcome"]) and abs(amount - expected) <= 0.01
        print(
            f"{row['scenario_id']:3} {res['status']:25} {amount:8.2f}  {expected:8.2f}  "
            f"{res['llm_calls']:5} {res['tokens_used']:6}  {'OK' if ok else 'CHECK'}"
        )

    s1 = rows[0]

    print("\n--- demo: S1 with token_limit=200 ---")
    r = run_agent(s1["message"], s1["scenario_id"], token_limit=200)
    print(r["status"], "| calls:", r["llm_calls"], "| tokens:", r["tokens_used"], "| steps:", len(r["steps"]))

    print("\n--- demo: S1 with time_limit_seconds=0 ---")
    r = run_agent(s1["message"], s1["scenario_id"], time_limit_seconds=0)
    print(r["status"], "| calls:", r["llm_calls"], "| tokens:", r["tokens_used"], "| steps:", len(r["steps"]))

    print("\n--- demo: S1 crash after 2nd tool, then resume ---")
    try:
        run_agent(s1["message"], s1["scenario_id"], run_id="S1-crash-demo", crash_after_tools=2)
    except SimulatedCrash as e:
        print("CRASH:", e)
    r = resume_agent("S1-crash-demo")
    print("status:", r["status"], "| refund:", refund_amount(r), "| calls:", r["llm_calls"])
    print("tools executed in order:", [s["tool"] for s in r["steps"]])