from sklearn.metrics import accuracy_score, f1_score
from lapse_data import build_dataset, get_split

df = build_dataset()
print("cohort:", len(df), "(expected 1156)")
print("lapsed:", int(df["lapsed"].sum()), "=", round(df["lapsed"].mean() * 100, 2), "% (expected 443 = 38.32%)")

X_train, X_test, y_train, y_test = get_split()
print("train rows:", len(X_train), "| test rows:", len(X_test), "(expected 924 / 232)")
print("missing values in features:", int(df.drop(columns="lapsed").isna().sum().sum()))

pred = [0] * len(y_test)
print("baseline accuracy:", round(accuracy_score(y_test, pred) * 100, 1), "% (expected 61.6%)")
print("baseline lapsed F1:", f1_score(y_test, pred, zero_division=0), "(expected 0)")