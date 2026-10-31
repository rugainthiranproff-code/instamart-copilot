import sqlite3
import pandas as pd

pd.set_option("display.width", 200)

con = sqlite3.connect("data/instamart.db")
df = pd.read_sql_query(
    """SELECT o.order_id, o.quantity, o.discount_pct, o.order_amount,
              o.delivery_minutes, c.city, p.category
       FROM orders o
       JOIN customers c ON o.customer_id = c.customer_id
       JOIN products p ON o.product_id = p.product_id
       WHERE o.status = 'completed'""", con)
con.close()

# (a) pivot table with margins
pv = pd.pivot_table(df, values="order_amount", index="city", columns="category",
                    aggfunc="sum", margins=True, margins_name="Total")
print("=== PIVOT (sum of order_amount) ===")
print(pv.round(2))
print("Pivot grand total:", round(pv.loc["Total", "Total"], 2), "(SQL total: 2998668.8)")

# groupby with named aggregation
g = df.groupby("city").agg(total=("order_amount", "sum"),
                           mean=("order_amount", "mean"),
                           count=("order_amount", "count")).round(2)
print("\n=== PER CITY ===")
print(g)
print("(expected Bengaluru 523643.40 / 276.47 / 1894, Mumbai 479058.50 / 297.00 / 1613)")

# (b) distribution statistics
x = df["order_amount"]
q1, q3 = x.quantile(0.25), x.quantile(0.75)
iqr = q3 - q1
low, high = q1 - 1.5 * iqr, q3 + 1.5 * iqr
print("\n=== ORDER_AMOUNT STATS ===")
print("mean:", round(x.mean(), 2), "| median:", round(x.median(), 2))
print("skewness:", round(x.skew(), 2))
print("Q1:", q1, "| Q3:", q3, "| IQR:", iqr)
print("lower fence:", low, "| upper fence:", high)
print("outliers below:", int((x < low).sum()), "| above:", int((x > high).sum()))
print("(expected mean 269.91, median 135.00, skew ~4.61, Q1 64.80, Q3 297.00,")
print(" upper fence 645.30, 897 above, 0 below)")

corr = df[["order_amount", "discount_pct", "quantity", "delivery_minutes"]].corr()
print("\n=== CORRELATION ===")
print(corr.round(3))

# find the pair with the largest |correlation| (each pair looked at once)
cols = list(corr.columns)
best_pair, best_val = None, 0.0
for i in range(len(cols)):
    for j in range(i + 1, len(cols)):
        val = corr.iloc[i, j]
        if abs(val) > abs(best_val):
            best_pair, best_val = (cols[i], cols[j]), val
print("largest |corr|:", best_pair, round(best_val, 3))
print("(expected order_amount vs discount_pct about -0.095)")