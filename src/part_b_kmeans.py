import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

rfm = pd.read_csv("data/clean/rfm.csv")
X = StandardScaler().fit_transform(rfm[["recency", "frequency", "monetary"]])

print("K   inertia   silhouette")
for k in range(2, 9):
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    sil = silhouette_score(X, km.labels_)
    print(f"{k}   {km.inertia_:8.1f}   {sil:.3f}")

print("""
Expected (inertia +-5%, silhouette +-0.05):
K=2: 1820.8 / 0.465   K=3: 1268.2 / 0.445   K=4: 743.1 / 0.526   K=5: 617.4 / 0.481
K=6: 503.2 / 0.482    K=7: 408.5 / 0.416    K=8: 366.5 / 0.412""")