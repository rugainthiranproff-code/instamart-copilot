# Instamart Customer Intelligence Copilot

## Overview

TODO

## Reproduce

TODO

## Part A

### Audit of the raw data

Shapes: customers (1200, 5), products (40, 4), orders (13084, 9). Data types and missing values per column:

| Table | Column | Type | Missing | Missing % |
|---|---|---|---|---|
| customers | customer_id | str | 0 | 0.00 |
| customers | city | str | 0 | 0.00 |
| customers | signup_date | str | 0 | 0.00 |
| customers | age | float64 | 61 | 5.08 |
| customers | gender | str | 30 | 2.50 |
| products | product_id | str | 0 | 0.00 |
| products | product_name | str | 0 | 0.00 |
| products | category | str | 0 | 0.00 |
| products | price_inr | int64 | 0 | 0.00 |
| orders | order_id | str | 0 | 0.00 |
| orders | customer_id | str | 0 | 0.00 |
| orders | product_id | str | 0 | 0.00 |
| orders | quantity | int64 | 0 | 0.00 |
| orders | order_ts | str | 0 | 0.00 |
| orders | status | str | 0 | 0.00 |
| orders | discount_pct | int64 | 0 | 0.00 |
| orders | order_amount | str | 53 | 0.41 |
| orders | delivery_minutes | float64 | 2541 | 19.42 |

Audit figures (on the raw files, before any cleaning):

| Check | Value |
|---|---|
| Raw order rows | 13,084 |
| Exact duplicate rows | 119 |
| Rows with status pending | 656 |
| Distinct order_id values | 12,309 |
| Non-numeric order_amount entries | 120 |
| Negative delivery_minutes | 106 |
| Blank delivery_minutes | 2,541 |
| Blank ages | 61 |
| Ages outside 10-100 | 6 |
| Distinct raw city spellings | 24 |
| Distinct non-blank raw gender spellings | 10 |
| Blank genders | 30 |

### Cleaning rules for customers

1. City: leading and trailing spaces removed and title case applied. The 24 raw spellings become exactly six cities: Pune 227, Delhi 210, Bengaluru 197, Chennai 191, Hyderabad 191, Mumbai 184.
2. Gender: every spelling is mapped to male, female or unknown, and a blank becomes unknown. Result: female 610, male 560, unknown 30.
3. Age: the 6 ages outside 10-100 were set to missing. Together with the 61 blank ages, 67 missing ages were filled with the median age of the customer's city (groupby and transform). After this there are 0 missing ages and every age is between 18 and 60.
4. signup_date was converted to a datetime.

### Cleaning rules for orders

The rules were applied in this order, starting from 13,084 rows:

1. order_ts was converted to a datetime.
2. Exact duplicate rows were removed: 119 rows, leaving 12,965.
3. For each order_id only the record with the latest order_ts was kept: 656 older records were removed, leaving 12,309 rows (one per order_id).
4. order_amount was converted to a number. The 112 entries that could not be used were filled from the product price: round(price_inr x quantity x (1 - discount_pct / 100), 2).
5. The 105 negative delivery_minutes were set to missing. For completed orders, 774 missing delivery times were filled with the median delivery time of the product category among completed orders (groupby and transform). For cancelled orders delivery_minutes was left missing, because a cancelled order was never delivered and a filled value would be invented data.

The counts in steps 4 and 5 are smaller than the raw audit counts (112 against 120 and 105 against 106) because the audit counted the raw file, while these counts come after duplicates were removed.

Result after cleaning: 12,309 rows, of which 11,110 completed and 1,199 cancelled, with no pending rows. There are 0 missing order_amount values, 0 missing delivery_minutes among completed orders and 1,199 among cancelled orders. The sum of order_amount over completed orders is INR 2,998,668.80.

### Storage and validation

The clean tables are saved as CSV files in `data/clean/` and as the tables customers, products and orders in `data/instamart.db` (order_ts stored as text, YYYY-MM-DD HH:MM:SS). `src/validate.py` checks the reference figures from the cleaning steps and prints ALL CHECKPOINTS PASSED, which it did.

### SQL analysis

The seven queries are in `sql/queries.sql` and are run from `src/run_queries.py` with pd.read_sql_query. Only completed orders count as revenue or spend.

| Query | What it does | Result |
|---|---|---|
| Q1 | WHERE (completed, order_amount > 500), then HAVING (customer total > 8000) | 30 customers |
| Q2 | Revenue by city and category (three-table join) | 30 rows, total INR 2,998,668.80, largest cell Bengaluru / Electronics INR 233,909.45 |
| Q3 | Products priced above the average price (scalar subquery) | 11 products |
| Q4 | Customers with no completed order (LEFT JOIN) | 25 customers |
| Q5 | Customers whose total spend is above the average total (two CTEs) | 550 customers, average INR 2,552.06 |
| Q6 | RANK, DENSE_RANK and ROW_NUMBER of spend within each city | see below |
| Q7 | Daily completed revenue with a running total | 183 daily rows, last cumulative value INR 2,998,668.80 |

Q6, top customer per city by total spend: Bengaluru C0082 (INR 12,856.20), Chennai C0930 (INR 10,151.40), Delhi C0291 (INR 13,742.60), Hyderabad C0743 (INR 12,730.05), Mumbai C0693 (INR 14,766.55), Pune C0426 (INR 10,377.10). Exactly 8 rows have a RANK() different from ROW_NUMBER(). Ties cause this because two customers in the same city with exactly the same total spend get the same RANK(), while ROW_NUMBER() still gives them different numbers.

### pandas cross-check

Q2 was rebuilt with pd.pivot_table(margins=True). Its grand total is INR 2,998,668.80, equal to the SQL total. Completed order_amount per city (groupby with named aggregation):

| City | Sum (INR) | Mean (INR) | Count |
|---|---|---|---|
| Bengaluru | 523,643.40 | 276.47 | 1,894 |
| Chennai | 463,629.15 | 272.72 | 1,700 |
| Delhi | 502,829.80 | 243.62 | 2,064 |
| Hyderabad | 528,589.90 | 284.95 | 1,855 |
| Mumbai | 479,058.50 | 297.00 | 1,613 |
| Pune | 500,918.05 | 252.48 | 1,984 |

### Exploratory analysis of completed order_amount

| Statistic | Value |
|---|---|
| Mean | 269.91 |
| Median | 135.00 |
| Skewness | 4.61 |
| Q1 | 64.80 |
| Q3 | 297.00 |
| IQR | 232.20 |
| Lower fence (Q1 - 1.5 x IQR) | -283.50 |
| Upper fence (Q3 + 1.5 x IQR) | 645.30 |
| Outliers below the lower fence | 0 |
| Outliers above the upper fence | 897 |

Correlation matrix over completed orders:

| | order_amount | discount_pct | quantity | delivery_minutes |
|---|---|---|---|---|
| order_amount | 1.000 | -0.095 | 0.087 | -0.003 |
| discount_pct | -0.095 | 1.000 | -0.000 | -0.010 |
| quantity | 0.087 | -0.000 | 1.000 | -0.013 |
| delivery_minutes | -0.003 | -0.010 | -0.013 | 1.000 |

What is this data about? What do its distributions look like? Are there outliers? What relationships exist?

This is order data from Instamart, a quick-commerce service: 11,110 completed orders from six cities, with the amount, quantity, discount and delivery time of each order. Order amounts are strongly right-skewed: the mean (269.91) is about double the median (135.00), the skewness is 4.61, and half of all orders fall between 64.80 and 297.00. There are 897 outliers above the upper fence of 645.30 and none below the lower fence, so a few very large orders pull the average up. The raw data also had anomalies such as negative delivery times, missing amounts and duplicate records, which were cleaned. All correlations among order amount, discount, quantity and delivery time are weak. The largest in absolute value is order amount with discount percentage (-0.095), just ahead of order amount with quantity (+0.087), and delivery time is almost unrelated to everything. A correlation this small does not establish causation, so discounts should not be said to reduce order amounts.

## Part B

### RFM table

RFM was computed from completed orders only, as of the snapshot 2025-10-01 00:00:00. Recency is the whole days between the snapshot and the customer's latest completed order, frequency is the number of distinct completed orders, and monetary is the sum of completed order_amount.

| Check | Value |
|---|---|
| Customers with at least one completed order | 1,175 |
| Recency (days) | median 19, minimum 0, maximum 180 |
| Frequency | mean 9.46, maximum 33 |
| Monetary (INR) | mean 2,552.06, maximum 14,766.55 |

### K-means

The three RFM columns were standardised with StandardScaler, and KMeans(n_clusters=K, n_init=10, random_state=42) was fitted for K from 2 to 8:

| K | Inertia | Silhouette |
|---|---|---|
| 2 | 1820.8 | 0.465 |
| 3 | 1268.2 | 0.445 |
| 4 | 743.1 | 0.526 |
| 5 | 617.4 | 0.480 |
| 6 | 503.2 | 0.482 |
| 7 | 408.5 | 0.416 |
| 8 | 366.5 | 0.412 |

The elbow is at K=4: inertia falls by about 550 from K=2 to K=3 and by about 525 from K=3 to K=4, but only by about 126 from K=4 to K=5, and the curve is flat after that. K=4 also has the highest silhouette score (0.526), and four segments are a number the business can act on. I chose K=4 from {3, 4, 5}.

The inertia of K=8 is always lower than that of K=2 because every extra cluster puts the centres closer to the points (with one cluster per customer the inertia would be zero). So inertia alone always favours a larger K and cannot pick K; it has to be read together with the elbow, the silhouette score and how easy the segments are to explain.

### Segment profile

Cluster numbers are only labels and have no ordering. The Premium flag goes to the segment with the highest mean monetary value (segment 1).

| Segment | Name | Size | Mean recency (days) | Mean frequency | Mean monetary (INR) | Recommended action |
|---|---|---|---|---|---|---|
| 0 | Occasional Buyers | 436 | 28.86 | 3.77 | 1,057.62 | Send category offers and a second-order voucher to raise how often they order |
| 1 | Premium High-Spenders (Premium) | 138 | 24.12 | 6.77 | 7,129.70 | Offer loyalty perks and priority support instead of heavy discounts |
| 2 | Loyal Regulars | 419 | 8.77 | 19.40 | 3,410.02 | Reward with bundles and referral offers to keep the habit |
| 3 | At-Risk Lapsing | 182 | 109.04 | 2.20 | 685.99 | Run a win-back campaign with a reminder and a limited-time offer |

PCA with 2 components on the scaled RFM matrix gives explained variance ratios of 0.634 and 0.218, a total of 0.852. The file `outputs/customer_segments.csv` has the columns customer_id, recency, frequency, monetary, segment_id, segment_name, is_premium.

### Lapse problem

The cutoff is 2025-09-01. The cohort is every customer with at least one completed order before the cutoff: 1,156 customers. The label lapsed is 1 if the customer has no completed order from 2025-09-01 through 2025-09-30, otherwise 0. In the cohort 443 customers lapsed (38.32%).

The features use only orders dated before the cutoff plus the clean customer table: recency (days from the cutoff to the last completed order), frequency, monetary, average discount_pct, cancellation rate, average delivery_minutes, most frequent product category, city, age, gender and tenure in days.

The split is train_test_split(test_size=0.2, stratify=y, random_state=42): 924 training rows and 232 test rows. The baseline that always predicts "not lapsed" has an accuracy of 61.6% and an F1 of 0 for the lapsed class.

### Preprocessing and leakage checks

City, gender and favourite category are one-hot encoded with k-1 columns (OneHotEncoder with drop="first"), and the numeric features are standardised, all inside a scikit-learn Pipeline. No encoder, scaler or resampler saw test rows: they were fitted on the training rows only and just applied to the test rows. No order dated 2025-09-01 or later entered the features, and the segment labels from the RFM clustering were not used as features. The code asserts that no feature column has a missing value (0 missing values).

The mean of frequency learned by the scaler on the training rows is 8.115, while the mean over the full cohort is 8.029. They differ because the scaler only sees the 924 training customers, which is a slightly different sample from all 1,156 customers.

### Model tuning and test results

Both models were tuned with GridSearchCV (cv=5, scoring="f1"):

- LogisticRegression(max_iter=1000) over C in {0.01, 0.1, 1, 10, 100}: best C = 100, best cross-validated F1 = 0.651.
- RandomForestClassifier(n_estimators=100, random_state=42) over max_depth in {3, 5, 8} and min_samples_leaf in {5, 10, 20} (45 fits): best max_depth = 8 and min_samples_leaf = 10, best cross-validated F1 = 0.687.

The untouched test set was used only after tuning. Metrics are for the lapsed class (89 of the 232 test customers lapsed). Confusion matrices have rows = actual [stayed, lapsed] and columns = predicted.

| Model | Confusion matrix | Precision | Recall | F1 |
|---|---|---|---|---|
| Baseline (always not lapsed) | - | 0 | 0 | 0.000 (accuracy 61.6%) |
| Logistic regression (C=100) | [[111, 32], [31, 58]] | 0.644 | 0.652 | 0.648 |
| Random forest (depth 8, leaf 10) | [[111, 32], [32, 57]] | 0.640 | 0.640 | 0.640 |

I selected the random forest because it had the higher cross-validated F1 (0.687 against 0.651), and this choice was made before looking at the test set. On the test set the two models are almost the same (F1 0.640 against 0.648), so the choice is not a strong one. The test F1 of 0.640 is above the required 0.55. For the retention team, missing a customer who is about to lapse loses all of that customer's future orders, while wrongly targeting a loyal customer only costs a message or a small offer, so recall matters more than precision here.

### Class-balance experiment

Only the training set was over-sampled: every original training row was kept and randomly chosen lapsed rows (with replacement, random_state=42) were added until both classes had 570 rows. The best logistic regression was refitted on this balanced data and evaluated on the original, unchanged test set:

| Model | Confusion matrix | Precision | Recall | F1 |
|---|---|---|---|---|
| Logistic regression, original training data | [[111, 32], [31, 58]] | 0.644 | 0.652 | 0.648 |
| Logistic regression, over-sampled training data | [[90, 53], [13, 76]] | 0.589 | 0.854 | 0.697 |

Recall moved the most (+0.202), precision fell slightly (-0.055) and F1 rose by 0.049. For the retention team this means the model finds 76 of the 89 lapsing customers instead of 58, but it also flags 53 loyal customers by mistake instead of 32. This is worth it when a missed lapsing customer costs more than a retention offer sent to someone who would have stayed.

### Interpretation and retention list

The five most important features of the random forest:

| Feature | Importance | Business reading |
|---|---|---|
| monetary | 0.278 | How much a customer has spent is the strongest signal of staying or leaving |
| frequency | 0.277 | Customers who order often are the ones who stay |
| recency | 0.111 | A long gap since the last order is a warning sign |
| average delivery minutes | 0.062 | Slow delivery has a small effect on leaving |
| average discount | 0.053 | The discounts a customer used have a small effect |

Coefficients of the best logistic regression (on standardised features; a positive sign means more likely to lapse):

| Feature | Coefficient | Business reading |
|---|---|---|
| recency | +0.04 | A longer gap since the last order slightly raises the lapse risk, but the effect is tiny |
| frequency | -1.698 | More orders strongly lower the lapse risk, so frequency is the main thing to grow |
| cancellation rate | -0.124 | A small negative sign, which is surprising and weak, so I do not read much into it |

The selected model (the random forest) was saved with joblib.dump to `outputs/lapse_model.joblib`. After joblib.load, the reloaded model reproduces the original test predictions exactly (True).

The test set has 40 Premium customers. They were ranked by predicted lapse probability and the top 10 were written to `outputs/retention_list.csv` (columns customer_id, lapse_probability, actually_lapsed). Of these 10 customers, 1 truly lapsed. The Premium flag comes from the whole-window RFM, which includes the September window that defines the lapse label, so the retention list is illustrative and not a leakage-free evaluation (the model's own features still use only orders before the cutoff).

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

### Audit of the raw data

Shapes: customers (1200, 5), products (40, 4), orders (13084, 9). Data types and missing values per column:

| Table | Column | Type | Missing | Missing % |
|---|---|---|---|---|
| customers | customer_id | str | 0 | 0.00 |
| customers | city | str | 0 | 0.00 |
| customers | signup_date | str | 0 | 0.00 |
| customers | age | float64 | 61 | 5.08 |
| customers | gender | str | 30 | 2.50 |
| products | product_id | str | 0 | 0.00 |
| products | product_name | str | 0 | 0.00 |
| products | category | str | 0 | 0.00 |
| products | price_inr | int64 | 0 | 0.00 |
| orders | order_id | str | 0 | 0.00 |
| orders | customer_id | str | 0 | 0.00 |
| orders | product_id | str | 0 | 0.00 |
| orders | quantity | int64 | 0 | 0.00 |
| orders | order_ts | str | 0 | 0.00 |
| orders | status | str | 0 | 0.00 |
| orders | discount_pct | int64 | 0 | 0.00 |
| orders | order_amount | str | 53 | 0.41 |
| orders | delivery_minutes | float64 | 2541 | 19.42 |

Audit figures (on the raw files, before any cleaning):

| Check | Value |
|---|---|
| Raw order rows | 13,084 |
| Exact duplicate rows | 119 |
| Rows with status pending | 656 |
| Distinct order_id values | 12,309 |
| Non-numeric order_amount entries | 120 |
| Negative delivery_minutes | 106 |
| Blank delivery_minutes | 2,541 |
| Blank ages | 61 |
| Ages outside 10-100 | 6 |
| Distinct raw city spellings | 24 |
| Distinct non-blank raw gender spellings | 10 |
| Blank genders | 30 |

### Cleaning rules for customers

1. City: leading and trailing spaces removed and title case applied. The 24 raw spellings become exactly six cities: Pune 227, Delhi 210, Bengaluru 197, Chennai 191, Hyderabad 191, Mumbai 184.
2. Gender: every spelling is mapped to male, female or unknown, and a blank becomes unknown. Result: female 610, male 560, unknown 30.
3. Age: the 6 ages outside 10-100 were set to missing. Together with the 61 blank ages, 67 missing ages were filled with the median age of the customer's city (groupby and transform). After this there are 0 missing ages and every age is between 18 and 60.
4. signup_date was converted to a datetime.

### Cleaning rules for orders

The rules were applied in this order, starting from 13,084 rows:

1. order_ts was converted to a datetime.
2. Exact duplicate rows were removed: 119 rows, leaving 12,965.
3. For each order_id only the record with the latest order_ts was kept: 656 older records were removed, leaving 12,309 rows (one per order_id).
4. order_amount was converted to a number. The 112 entries that could not be used were filled from the product price: round(price_inr x quantity x (1 - discount_pct / 100), 2).
5. The 105 negative delivery_minutes were set to missing. For completed orders, 774 missing delivery times were filled with the median delivery time of the product category among completed orders (groupby and transform). For cancelled orders delivery_minutes was left missing, because a cancelled order was never delivered and a filled value would be invented data.

The counts in steps 4 and 5 are smaller than the raw audit counts (112 against 120 and 105 against 106) because the audit counted the raw file, while these counts come after duplicates were removed.

Result after cleaning: 12,309 rows, of which 11,110 completed and 1,199 cancelled, with no pending rows. There are 0 missing order_amount values, 0 missing delivery_minutes among completed orders and 1,199 among cancelled orders. The sum of order_amount over completed orders is INR 2,998,668.80.

### Storage and validation

The clean tables are saved as CSV files in `data/clean/` and as the tables customers, products and orders in `data/instamart.db` (order_ts stored as text, YYYY-MM-DD HH:MM:SS). `src/validate.py` checks the reference figures from the cleaning steps and prints ALL CHECKPOINTS PASSED, which it did.

### SQL analysis

The seven queries are in `sql/queries.sql` and are run from `src/run_queries.py` with pd.read_sql_query. Only completed orders count as revenue or spend.

| Query | What it does | Result |
|---|---|---|
| Q1 | WHERE (completed, order_amount > 500), then HAVING (customer total > 8000) | 30 customers |
| Q2 | Revenue by city and category (three-table join) | 30 rows, total INR 2,998,668.80, largest cell Bengaluru / Electronics INR 233,909.45 |
| Q3 | Products priced above the average price (scalar subquery) | 11 products |
| Q4 | Customers with no completed order (LEFT JOIN) | 25 customers |
| Q5 | Customers whose total spend is above the average total (two CTEs) | 550 customers, average INR 2,552.06 |
| Q6 | RANK, DENSE_RANK and ROW_NUMBER of spend within each city | see below |
| Q7 | Daily completed revenue with a running total | 183 daily rows, last cumulative value INR 2,998,668.80 |

Q6, top customer per city by total spend: Bengaluru C0082 (INR 12,856.20), Chennai C0930 (INR 10,151.40), Delhi C0291 (INR 13,742.60), Hyderabad C0743 (INR 12,730.05), Mumbai C0693 (INR 14,766.55), Pune C0426 (INR 10,377.10). Exactly 8 rows have a RANK() different from ROW_NUMBER(). Ties cause this because two customers in the same city with exactly the same total spend get the same RANK(), while ROW_NUMBER() still gives them different numbers.

### pandas cross-check

Q2 was rebuilt with pd.pivot_table(margins=True). Its grand total is INR 2,998,668.80, equal to the SQL total. Completed order_amount per city (groupby with named aggregation):

| City | Sum (INR) | Mean (INR) | Count |
|---|---|---|---|
| Bengaluru | 523,643.40 | 276.47 | 1,894 |
| Chennai | 463,629.15 | 272.72 | 1,700 |
| Delhi | 502,829.80 | 243.62 | 2,064 |
| Hyderabad | 528,589.90 | 284.95 | 1,855 |
| Mumbai | 479,058.50 | 297.00 | 1,613 |
| Pune | 500,918.05 | 252.48 | 1,984 |

### Exploratory analysis of completed order_amount

| Statistic | Value |
|---|---|
| Mean | 269.91 |
| Median | 135.00 |
| Skewness | 4.61 |
| Q1 | 64.80 |
| Q3 | 297.00 |
| IQR | 232.20 |
| Lower fence (Q1 - 1.5 x IQR) | -283.50 |
| Upper fence (Q3 + 1.5 x IQR) | 645.30 |
| Outliers below the lower fence | 0 |
| Outliers above the upper fence | 897 |

Correlation matrix over completed orders:

| | order_amount | discount_pct | quantity | delivery_minutes |
|---|---|---|---|---|
| order_amount | 1.000 | -0.095 | 0.087 | -0.003 |
| discount_pct | -0.095 | 1.000 | -0.000 | -0.010 |
| quantity | 0.087 | -0.000 | 1.000 | -0.013 |
| delivery_minutes | -0.003 | -0.010 | -0.013 | 1.000 |

What is this data about? What do its distributions look like? Are there outliers? What relationships exist?

This is order data from Instamart, a quick-commerce service: 11,110 completed orders from six cities, with the amount, quantity, discount and delivery time of each order. Order amounts are strongly right-skewed: the mean (269.91) is about double the median (135.00), the skewness is 4.61, and half of all orders fall between 64.80 and 297.00. There are 897 outliers above the upper fence of 645.30 and none below the lower fence, so a few very large orders pull the average up. The raw data also had anomalies such as negative delivery times, missing amounts and duplicate records, which were cleaned. All correlations among order amount, discount, quantity and delivery time are weak. The largest in absolute value is order amount with discount percentage (-0.095), just ahead of order amount with quantity (+0.087), and delivery time is almost unrelated to everything. A correlation this small does not establish causation, so discounts should not be said to reduce order amounts.