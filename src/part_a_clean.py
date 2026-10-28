import os
import sqlite3
import pandas as pd

os.makedirs("data/clean", exist_ok=True)

cust = pd.read_csv("data/raw/customers.csv")
prod = pd.read_csv("data/raw/products.csv")
orders = pd.read_csv("data/raw/orders.csv")

# ---------------- CLEAN CUSTOMERS ----------------
# (a) city: strip spaces + title case
cust["city"] = cust["city"].str.strip().str.title()

# (b) gender: map to male / female / unknown
g = cust["gender"].fillna("").str.strip().str.lower()
cust["gender"] = g.map({"male": "male", "m": "male",
                        "female": "female", "f": "female"}).fillna("unknown")

# (c) age: outside 10-100 -> missing, then fill with city median
cust["age"] = pd.to_numeric(cust["age"], errors="coerce")
bad_age = ((cust["age"] < 10) | (cust["age"] > 100)).sum()
cust.loc[(cust["age"] < 10) | (cust["age"] > 100), "age"] = float("nan")
missing_age = cust["age"].isna().sum()
cust["age"] = cust["age"].fillna(cust.groupby("city")["age"].transform("median"))

# (d) signup_date -> datetime
cust["signup_date"] = pd.to_datetime(cust["signup_date"])

print("=== CUSTOMERS ===")
print("ages set to missing (outside 10-100):", bad_age)
print("ages filled with city median:", missing_age)
print(cust["city"].value_counts().to_string())
print(cust["gender"].value_counts().to_string())
print("missing ages:", cust["age"].isna().sum(),
      "| min age:", cust["age"].min(), "| max age:", cust["age"].max())

# ---------------- CLEAN ORDERS ----------------
n0 = len(orders)

# 1. order_ts -> datetime
orders["order_ts"] = pd.to_datetime(orders["order_ts"])

# 2. remove exact duplicates
orders = orders.drop_duplicates()
n1 = len(orders)

# 3. keep latest record per order_id
orders = (orders.sort_values("order_ts")
                .drop_duplicates("order_id", keep="last")
                .reset_index(drop=True))
n2 = len(orders)

# 4. order_amount -> numeric, fill missing from product price
orders = orders.merge(prod[["product_id", "category", "price_inr"]],
                      on="product_id", how="left")
orders["order_amount"] = pd.to_numeric(orders["order_amount"], errors="coerce")
amt_missing = orders["order_amount"].isna().sum()
calc = (orders["price_inr"] * orders["quantity"]
        * (1 - orders["discount_pct"] / 100)).round(2)
orders["order_amount"] = orders["order_amount"].fillna(calc)

# 5. delivery_minutes: negative -> missing, fill completed with category median
orders["delivery_minutes"] = pd.to_numeric(orders["delivery_minutes"], errors="coerce")
neg = (orders["delivery_minutes"] < 0).sum()
orders.loc[orders["delivery_minutes"] < 0, "delivery_minutes"] = float("nan")
done = orders["status"] == "completed"
miss_done = orders.loc[done, "delivery_minutes"].isna().sum()
med = orders[done].groupby("category")["delivery_minutes"].transform("median")
orders.loc[done, "delivery_minutes"] = orders.loc[done, "delivery_minutes"].fillna(med)

orders = orders.drop(columns=["category", "price_inr"])

print("\n=== ORDERS ===")
print("rows at start:", n0)
print("exact duplicates removed:", n0 - n1)
print("older pending records removed (keep latest per order_id):", n1 - n2)
print("unparseable amounts filled from product price:", amt_missing)
print("negative delivery_minutes set to missing:", neg)
print("completed orders with missing delivery filled with category median:", miss_done)
print("rows now:", len(orders))
print(orders["status"].value_counts().to_string())
print("missing order_amount:", orders["order_amount"].isna().sum())
print("missing delivery (completed):", orders.loc[orders.status == "completed", "delivery_minutes"].isna().sum())
print("missing delivery (cancelled):", orders.loc[orders.status == "cancelled", "delivery_minutes"].isna().sum())
print("sum completed amount:", round(orders.loc[orders.status == "completed", "order_amount"].sum(), 2))

# ---------------- SAVE ----------------
cust_out = cust.copy()
cust_out["signup_date"] = cust_out["signup_date"].dt.strftime("%Y-%m-%d")
orders_out = orders.copy()
orders_out["order_ts"] = orders_out["order_ts"].dt.strftime("%Y-%m-%d %H:%M:%S")

cust_out.to_csv("data/clean/customers.csv", index=False)
prod.to_csv("data/clean/products.csv", index=False)
orders_out.to_csv("data/clean/orders.csv", index=False)

con = sqlite3.connect("data/instamart.db")
cust_out.to_sql("customers", con, if_exists="replace", index=False)
prod.to_sql("products", con, if_exists="replace", index=False)
orders_out.to_sql("orders", con, if_exists="replace", index=False)
con.close()
print("\nSaved: data/clean/*.csv and data/instamart.db")