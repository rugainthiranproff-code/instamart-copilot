import os
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA

os.makedirs("outputs", exist_ok=True)

rfm = pd.read_csv("data/clean/rfm.csv")
X = StandardScaler().fit_transform(rfm[["recency", "frequency", "monetary"]])

km = KMeans(n_clusters=4, n_init=10, random_state=42).fit(X)
rfm["segment_id"] = km.labels_

prof = rfm.groupby("segment_id").agg(
    size=("customer_id", "count"),
    recency=("recency", "mean"),
    frequency=("frequency", "mean"),
    monetary=("monetary", "mean"),
).round(2)

# naming by rule (cluster numbers are only labels)
names = {}
premium = prof["monetary"].idxmax()
names[premium] = "Premium High-Spenders"
rest = prof.drop(index=premium)
loyal = rest["frequency"].idxmax()
names[loyal] = "Loyal Regulars"
rest = rest.drop(index=loyal)
risk = rest["recency"].idxmax()
names[risk] = "At-Risk Lapsing"
for sid in rest.index:
    if sid != risk:
        names[sid] = "Occasional Buyers"

rfm["segment_name"] = rfm["segment_id"].map(names)
rfm["is_premium"] = rfm["segment_id"] == premium

prof["segment_name"] = prof.index.map(names)
print("=== SEGMENT PROFILE ===")
print(prof.to_string())
print("""
Expected (K=4): sizes about 436 / 138 / 419 / 182
 - 138-customer segment: mean monetary about 7130, mean frequency about 6.8
 - 419-customer segment: mean frequency about 19.4, mean recency about 8.8""")

pca = PCA(n_components=2).fit(X)
r = pca.explained_variance_ratio_
print("\nPCA explained variance:", r.round(3), "total:", round(r.sum(), 3))
print("(expected about 0.634 and 0.218, total about 0.852)")

out = rfm[["customer_id", "recency", "frequency", "monetary",
           "segment_id", "segment_name", "is_premium"]]
out.to_csv("outputs/customer_segments.csv", index=False)
print("\nPremium rows:", int(out["is_premium"].sum()), "| saved outputs/customer_segments.csv")