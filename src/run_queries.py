import re
import sqlite3
import pandas as pd

pd.set_option("display.width", 200)

text = open("sql/queries.sql", encoding="utf-8").read()
parts = re.split(r"(?m)^-- (Q\d)[^\n]*$", text)
queries = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}

con = sqlite3.connect("data/instamart.db")
res = {name: pd.read_sql_query(sql, con) for name, sql in queries.items()}
con.close()

q1 = res["Q1"]
print("Q1 customers:", len(q1), "(expected 30)")

q2 = res["Q2"]
print("\nQ2 rows:", len(q2), "(expected 30)")
print("Q2 total revenue:", round(q2["revenue"].sum(), 2), "(expected 2998668.8)")
print("Q2 largest cell:", q2.iloc[0].to_dict(), "(expected Bengaluru / Electronics 233909.45)")

q3 = res["Q3"]
print("\nQ3 products:", len(q3), "(expected 11)")

q4 = res["Q4"]
print("\nQ4 customers with no completed order:", len(q4), "(expected 25)")

q5 = res["Q5"]
print("\nQ5 customers above average:", len(q5), "(expected 550)")
print("Q5 average:", q5["avg_total"].iloc[0], "(expected 2552.06)")

q6 = res["Q6"]
print("\nQ6 top customer per city (expected Bengaluru C0082 12856.20, Chennai C0930 10151.40,")
print("   Delhi C0291 13742.60, Hyderabad C0743 12730.05, Mumbai C0693 14766.55, Pune C0426 10377.10)")
print(q6[q6["row_num"] == 1][["city", "customer_id", "total_spend"]].to_string(index=False))
print("Q6 rows where RANK != ROW_NUMBER:", int((q6["rnk"] != q6["row_num"]).sum()), "(expected 8)")

q7 = res["Q7"]
print("\nQ7 daily rows:", len(q7), "(expected 183)")
print("Q7 last cumulative:", q7["cumulative_revenue"].iloc[-1], "(expected 2998668.8)")