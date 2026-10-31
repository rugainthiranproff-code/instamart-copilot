"""part_d_agent.py -- Part D refund agent. Piece 1: the five tools."""
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # mock_llm.py is in the project root
sys.path.insert(0, str(ROOT / "src"))  # policy_rag.py is in src

from policy_rag import retrieve

DB_PATH = ROOT / "data" / "instamart.db"
LEDGER_PATH = ROOT / "outputs" / "refund_ledger.jsonl"


# ---------- Tool 1: get_order ----------
def get_order(order_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT order_id, status, order_amount, delivery_minutes "
        "FROM orders WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return {"error": "order not found"}
    return {
        "order_id": row[0],
        "status": row[1],
        "order_amount": row[2],
        "delivery_minutes": row[3],
    }


# ---------- Tool 2: search_policy ----------
def search_policy(query):
    results = retrieve(query, k=3)
    clean = [
        {"source": r["source"], "score": float(r["score"]), "text": r["text"]}
        for r in results
    ]
    return {"results": clean}


# ---------- Tool 3: calculate_refund ----------
def calculate_refund(order_amount, delivery_minutes):
    if delivery_minutes is not None and delivery_minutes > 45:
        return {"refund_inr": round(float(order_amount), 2)}
    return {"refund_inr": 0.0}


# ---------- helper: write one line to the ledger ----------
def _append_ledger(tool_name, order_id, refund_inr):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "tool": tool_name,
        "order_id": order_id,
        "refund_inr": refund_inr,
    }
    with open(LEDGER_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


# ---------- Tool 4: issue_refund ----------
def issue_refund(order_id, refund_inr):
    _append_ledger("issue_refund", order_id, refund_inr)
    return {"refund_inr": refund_inr}


# ---------- Tool 5: escalate_to_human ----------
def escalate_to_human(order_id, refund_inr):
    _append_ledger("escalate_to_human", order_id, refund_inr)
    return {"refund_inr": refund_inr}


# ---------- Tool descriptions (what the model is told about the tools) ----------
TOOLS_SPEC = [
    {
        "name": "get_order",
        "description": "Look up an order in the database by its order id.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "search_policy",
        "description": "Search the policy documents and return the top matching chunks.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "calculate_refund",
        "description": "Compute the refund in INR from the order amount and delivery minutes.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_amount": {"type": "number"},
                "delivery_minutes": {"type": "number"},
            },
            "required": ["order_amount", "delivery_minutes"],
        },
    },
    {
        "name": "issue_refund",
        "description": "Issue the refund automatically and record it in the ledger.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "refund_inr": {"type": "number"},
            },
            "required": ["order_id", "refund_inr"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Send a large refund to a human lead and record it in the ledger.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "refund_inr": {"type": "number"},
            },
            "required": ["order_id", "refund_inr"],
        },
    },
]

# tool name -> python function (the agent looks the name up here)
TOOL_MAP = {
    "get_order": get_order,
    "search_policy": search_policy,
    "calculate_refund": calculate_refund,
    "issue_refund": issue_refund,
    "escalate_to_human": escalate_to_human,
}


# ---------- quick test (does NOT touch the ledger) ----------
if __name__ == "__main__":
    print(get_order("ORD-100048"))
    print(get_order("ORD-999999"))
    print(calculate_refund(128.25, 60))
    print(calculate_refund(128.25, 30))
    print(len(search_policy("refund policy late delivery")["results"]), "policy chunks found")