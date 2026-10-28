import sqlite3
import pandas as pd

raw_orders = pd.read_csv("data/raw/orders.csv")
cust = pd.read_csv("data/clean/customers.csv")
orders = pd.read_csv("data/clean/orders.csv")

# --- raw audit checkpoints (task 2) ---
assert len(raw_orders) == 13084, "raw order rows"
assert raw_orders.duplicated().sum() == 119, "exact duplicates"
assert (raw_orders["status"] == "pending").sum() == 656, "pending rows"
assert raw_orders["order_id"].nunique() == 12309, "distinct order_id"

# --- clean customers (task 3) ---
city = cust["city"].value_counts().to_dict()
assert city == {"Pune": 227, "Delhi": 210, "Bengaluru": 197,
                "Chennai": 191, "Hyderabad": 191, "Mumbai": 184}, "city counts"
gender = cust["gender"].value_counts().to_dict()
assert gender == {"female": 610, "male": 560, "unknown": 30}, "gender counts"
assert cust["age"].isna().sum() == 0, "missing ages"
assert cust["age"].between(18, 60).all(), "age range"

# --- clean orders (task 4) ---
assert len(orders) == 12309, "clean order rows"
assert orders["order_id"].is_unique, "one row per order_id"
assert (orders["status"] == "completed").sum() == 11110, "completed count"
assert (orders["status"] == "cancelled").sum() == 1199, "cancelled count"
assert not (orders["status"] == "pending").any(), "pending rows remain"
assert orders["order_amount"].isna().sum() == 0, "missing order_amount"
done = orders["status"] == "completed"
assert orders.loc[done, "delivery_minutes"].isna().sum() == 0, "missing delivery (completed)"
canc = orders["status"] == "cancelled"
assert orders.loc[canc, "delivery_minutes"].isna().sum() == 1199, "missing delivery (cancelled)"
assert round(orders.loc[done, "order_amount"].sum(), 2) == 2998668.80, "sum of completed amount"

# --- database (task 5) ---
con = sqlite3.connect("data/instamart.db")
tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
assert {"customers", "products", "orders"} <= tables, "db tables"
assert con.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 12309, "db order rows"
con.close()

print("ALL CHECKPOINTS PASSED")