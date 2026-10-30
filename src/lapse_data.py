import pandas as pd
from sklearn.model_selection import train_test_split

CUTOFF = pd.Timestamp("2025-09-01")
END = pd.Timestamp("2025-10-01")


def build_dataset():
    orders = pd.read_csv("data/clean/orders.csv", parse_dates=["order_ts"])
    cust = pd.read_csv("data/clean/customers.csv", parse_dates=["signup_date"])
    prod = pd.read_csv("data/clean/products.csv")
    orders = orders.merge(prod[["product_id", "category"]], on="product_id", how="left")

    # features: ONLY orders before the cutoff
    before = orders[orders["order_ts"] < CUTOFF]
    done_b = before[before["status"] == "completed"]

    feat = done_b.groupby("customer_id").agg(
        last_order=("order_ts", "max"),
        frequency=("order_id", "nunique"),
        monetary=("order_amount", "sum"),
        avg_discount=("discount_pct", "mean"),
        avg_delivery=("delivery_minutes", "mean"),
    )
    feat["recency"] = (CUTOFF - feat["last_order"]).dt.days
    feat = feat.drop(columns="last_order")

    feat["cancel_rate"] = (before.assign(c=before["status"] == "cancelled")
                                 .groupby("customer_id")["c"].mean()
                                 .reindex(feat.index).fillna(0))

    fav = (done_b.groupby(["customer_id", "category"]).size().reset_index(name="n")
                 .sort_values(["customer_id", "n", "category"], ascending=[True, False, True])
                 .drop_duplicates("customer_id").set_index("customer_id")["category"])
    feat["fav_category"] = fav

    c = cust.set_index("customer_id")
    feat["city"] = c["city"]
    feat["age"] = c["age"]
    feat["gender"] = c["gender"]
    feat["tenure"] = (CUTOFF - c["signup_date"]).dt.days

    # label: no completed order in September -> lapsed = 1
    sept = orders[(orders["order_ts"] >= CUTOFF) & (orders["order_ts"] < END)
                  & (orders["status"] == "completed")]
    active = set(sept["customer_id"])
    feat["lapsed"] = (~feat.index.isin(active)).astype(int)

    cols = ["recency", "frequency", "monetary", "avg_discount", "cancel_rate",
            "avg_delivery", "fav_category", "city", "age", "gender", "tenure", "lapsed"]
    return feat[cols]


def get_split():
    df = build_dataset()
    X = df.drop(columns="lapsed")
    y = df["lapsed"]
    return train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)