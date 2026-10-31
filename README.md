# Instamart Customer Intelligence Copilot

## Overview

TODO

## Reproduce

TODO

## Part A

TODO

## Part B

TODO

## Part C

TODO

## Part D

Part D has two halves: a retrieval-grounded policy assistant over the five documents in `data/policies/`, and a refund agent that decides refund requests by calling tools. All model calls use `mock_llm.py` (no network, no API key).

Code: `src/policy_rag.py` and `src/part_d_rag_eval.py` (RAG), `src/part_d_agent.py` (tools), `src/part_d_run.py` (ReAct loop, limits, resume), `src/part_d_final.py` (clean final run). Outputs: `rag_output.txt`, `outputs/agent_runs.jsonl`, `outputs/refund_ledger.jsonl`, and checkpoints in `state/`.

### Chunking and retrieval

Each document is split into chunks of 40 words with an overlap of 10 words. This gives 15 chunks in total: refund 4, delivery 3, escalation 3, payment 3, privacy 2.

Chunks are vectorised with `TfidfVectorizer` and ranked by cosine similarity. For the query "refund policy late delivery" the top three chunks all come from `refund_policy.txt` (scores 0.272, 0.251 and 0.245).

TF (term frequency) measures how often a word appears inside one chunk, and IDF (inverse document frequency) measures how rare that word is across all chunks, so rare words count more than common ones. A limitation is that TF-IDF only matches exact words: a question that says "money back" would not match a chunk that says "refund", even though the meaning is the same.

### Grounded answers and evaluation

`answer(question)` retrieves three chunks and sends them with the question to the mock model, which must answer only from the context or say it could not find the information. I ran the 14 questions in `data/raw/policy_eval.csv` (12 answerable, 2 not covered by any document):

| Chunking | Chunks | Expected doc in top 3 (12 answerable) | Expected fact in answer (12 answerable) | Fallback answer (2 unanswerable) |
|---|---|---|---|---|
| 40 words, overlap 10 | 15 | 12/12 | 12/12 | 2/2 |
| 40 words, overlap 0 | 13 | 12/12 | 10/12 | 2/2 |

With overlap 0, two questions break:

- "What delivery time makes a completed order eligible for a full refund?" The answer was only "receives a full refund of the order amount." and it lacked "more than 45 minutes".
- "How soon is money returned when a payment fails but is deducted?" The answer lacked "48 hours".

In both cases the sentence holding the fact was cut by a chunk boundary, so the words that match the question and the fact ended up in different chunks. The 10-word overlap repeats the end of one chunk at the start of the next, which keeps such sentences together.

### Refund agent: tools

The agent has five tools, described in `TOOLS_SPEC` and looked up by name in `TOOL_MAP`:

| Tool | What it does |
|---|---|
| `get_order(order_id)` | Reads the order from `data/instamart.db`, or returns an "order not found" error |
| `search_policy(query)` | Returns the top policy chunks from the retrieval above |
| `calculate_refund(order_amount, delivery_minutes)` | Refund is 100% of the order amount if delivery took more than 45 minutes, otherwise 0 |
| `issue_refund(order_id, refund_inr)` | Writes one line to `outputs/refund_ledger.jsonl` |
| `escalate_to_human(order_id, refund_inr)` | Writes one line to `outputs/refund_ledger.jsonl` (used when the refund is above INR 1000) |

### Refund agent: ReAct loop and the seven scenarios

`run_agent` asks the model what to do, runs the tool it requests, gives the result back, and repeats until the model gives a final answer. Results for the seven scenarios in `data/raw/agent_scenarios.csv`:

| Scenario | Status | Refund (INR) | Model calls | Tokens used |
|---|---|---|---|---|
| S1 | REFUND | 128.25 | 5 | 1062 |
| S2 | REFUND | 135.00 | 5 | 1062 |
| S3 | ESCALATE | 1999.00 | 5 | 1049 |
| S4 | DENIED | 0.00 | 4 | 737 |
| S5 | DENIED | 0.00 | 3 | 436 |
| S6 | NOT_FOUND | 0.00 | 2 | 138 |
| S7 | FALLBACK_MAX_ITERATIONS | 0.00 | 6 | 3198 |

All refund amounts match `expected_refund_inr`. Every run is logged as one line in `outputs/agent_runs.jsonl`.

### Refund agent: safety limits

The agent stops safely with a hand-off message for a human in three cases:

- After 6 model calls without a final answer: `FALLBACK_MAX_ITERATIONS` (this is how S7 ends, with the default token limit of 6000).
- When total tokens go above the token limit, checked right after each model call and before the requested tool runs: `FALLBACK_TOKEN_LIMIT`.
- When the elapsed time reaches the time limit, checked at the start of each iteration: `FALLBACK_TIMEOUT`.

Demonstrations, both on S1:

- With `token_limit=200`: status `FALLBACK_TOKEN_LIMIT` after 3 model calls and 453 tokens.
- With `time_limit_seconds=0`: status `FALLBACK_TIMEOUT` after 0 model calls.

### Refund agent: crash and resume

After every tool result, the agent saves a checkpoint to `state/<run_id>.json` (messages, tokens used, step number and tools executed so far). For the demo, S1 was crashed on purpose right after its second tool, and `resume_agent` continued from the checkpoint. The tools executed across the crash and the resume, in order, were:

get_order -> search_policy -> calculate_refund -> issue_refund

That is four executions with none repeated. The final status was REFUND with 128.25.

### ReAct versus plan-and-execute

My agent is ReAct: after every tool result it calls the model again, so each step is chosen after seeing the latest observation. It used 5 model calls for S1 (1062 tokens), 3 for S5 (436 tokens) and 2 for S6 (138 tokens).

A plan-and-execute design asks the model once for the whole list of steps and replans only on error. I did not build it, so this is an estimate: it would need about 2 model calls for S1 and fewer tokens, because the growing message history is not sent again after every tool.

Its weakness is an unexpected observation. The plan is written before the order is read. For S6 (order not found) or S5 (order not completed) the rest of the plan is useless, so it must stop, replan and spend an extra model call. ReAct handles this directly: S6 ended after 2 calls and S5 after 3, because the model saw the result and answered NOT_FOUND or DENIED at once.

For this refund workflow I would choose ReAct. The next step depends on the order (status, delivery minutes, refund above INR 1000), money is involved, and each step should be checked against fresh data. The extra model calls are cheap here: the longest normal run used 1062 tokens, far below the limit of 6000.

## Limitations and Next Steps

TODO