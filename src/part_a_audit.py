import pandas as pd

pd.set_option("display.width", 200)

cust = pd.read_csv("data/raw/customers.csv")
prod = pd.read_csv("data/raw/products.csv")
orders = pd.read_csv("data/raw/orders.csv")

for name, df in [("customers", cust), ("products", prod), ("orders", orders)]:
    print(f"\n=== {name}: shape={df.shape} ===")
    print(df.dtypes)
    miss = df.isna().sum()
    print(pd.DataFrame({"missing": miss, "pct": (miss / len(df) * 100).round(2)}))

amt = pd.to_numeric(orders["order_amount"], errors="coerce")
dm = pd.to_numeric(orders["delivery_minutes"], errors="coerce")

audit = {
    "order rows": len(orders),
    "exact duplicate rows": orders.duplicated().sum(),
    "pending rows": (orders["status"] == "pending").sum(),
    "distinct order_id": orders["order_id"].nunique(),
    "non-numeric amounts": amt.isna().sum(),
    "negative delivery_minutes": (dm < 0).sum(),
    "blank delivery_minutes": dm.isna().sum(),
    "blank age": cust["age"].isna().sum(),
    "age outside 10-100": ((cust["age"] < 10) | (cust["age"] > 100)).sum(),
    "distinct city spellings": cust["city"].nunique(),
    "distinct gender spellings": cust["gender"].dropna().nunique(),
    "blank gender": cust["gender"].isna().sum(),
}
print("\n=== AUDIT FIGURES ===")
print(pd.Series(audit))